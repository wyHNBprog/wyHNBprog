import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getChatHistory, sendChatMessage, markConversationRead, deleteMessage } from '@/api/message'

// ========== 聊天消息 store ==========
// 管理当前会话的消息列表、未读计数、消息收发

// 兼容 snake_case 和 camelCase
function normalizeChatMessage(m) {
  if (!m) return null
  return {
    id: m.id,
    conversationId: m.conversationId || m.conversation_id || null,
    content: m.content || '',
    senderType: m.senderType || m.sender_type || 'user',
    senderId: m.senderId || m.sender_id || null,
    isRead: m.isRead != null ? m.isRead : (m.is_read != null ? m.is_read : false),
    createdAt: m.createdAt || m.created_at || new Date().toISOString(),
    realName: m.realName || m.real_name || null
  }
}

// 安全键校验：防止通过 WebSocket 注入 __proto__/constructor/prototype 等危险键
// 虽然简单方括号赋值不会污染 Object.prototype，但仍需防御性编程
function isSafeObjectKey(key) {
  if (key == null) return false
  const s = String(key)
  if (s === '__proto__' || s === 'constructor' || s === 'prototype') return false
  return true
}

export const useChatStore = defineStore('chat', () => {
  // 当前会话的消息列表
  const messages = ref([])
  // 当前会话 ID
  const currentConversationId = ref(null)
  // 加载状态
  const loading = ref(false)
  // 各会话未读计数 { [conversationId]: number }
  const unreadCounts = ref({})
  // 已处理的消息 id 集合：SSE 与 WebSocket 双通道可能推送同一消息，
  // 用 id 去重，避免非当前会话未读计数被重复累加
  const processedMessageIds = new Set()
  // 乐观消息确认超时定时器映射 { tempId: timer }
  const pendingTimers = new Map()

  // 为乐观消息设置确认超时：超时仍为 _pending 则移除并提示
  function pendingTimer(tempId, conversationId) {
    const timer = setTimeout(() => {
      pendingTimers.delete(tempId)
      // 仅当消息仍处于待确认状态且属于当前会话时才移除
      if (conversationId === currentConversationId.value) {
        const idx = messages.value.findIndex((m) => m.id === tempId && m._pending)
        if (idx >= 0) {
          messages.value.splice(idx, 1)
        }
      }
    }, 10000)
    pendingTimers.set(tempId, timer)
  }

  // 清除乐观消息的确认超时定时器
  function clearPendingTimer(tempId) {
    const timer = pendingTimers.get(tempId)
    if (timer) {
      clearTimeout(timer)
      pendingTimers.delete(tempId)
    }
  }

  // ========== 加载会话全部消息历史 ==========
  async function loadMessages(conversationId) {
    currentConversationId.value = conversationId
    loading.value = true
    try {
      const res = await getChatHistory(conversationId)
      // 后端返回数组或 { messages: [...] }，兼容两种格式
      let list = []
      if (Array.isArray(res)) {
        list = res
      } else if (res && res.messages) {
        list = res.messages
      }
      messages.value = list.map(normalizeChatMessage).filter(Boolean)
    } catch (e) {
      console.error('[ChatStore] 加载聊天记录失败：', e)
      messages.value = []
    } finally {
      loading.value = false
    }
  }

  // ========== 发送消息 ==========
  // 优先通过 WebSocket 发送，同时本地 push 一条乐观消息（临时 ID）确保即时显示。
  // 服务器确认后通过 chat_sent 事件回传真实消息，替换临时消息。
  // WebSocket 不可用时走 HTTP API 兜底，返回的消息 push 到列表。
  // options.sendFn: WebSocket send 函数
  // options.senderType: 'user' | 'admin'
  async function sendMessage(conversationId, content, options = {}) {
    const senderType = options.senderType || 'user'
    const sendFn = options.sendFn || null

    // 尝试通过 WebSocket 发送
    if (sendFn) {
      // 先 push 乐观消息（临时 ID），确保消息立即显示，不丢失
      const tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
      const tempMsg = {
        id: tempId,
        conversationId: conversationId,
        content: content,
        senderType: senderType,
        senderId: null,
        isRead: false,
        createdAt: new Date().toISOString(),
        _pending: true
      }
      // 仅当当前会话匹配时才 push 到列表
      if (conversationId === currentConversationId.value) {
        messages.value.push(tempMsg)
      }

      const sent = sendFn({
        event: 'send_chat',
        data: {
          conversationId: conversationId,
          content: content,
          tempId: tempId
        }
      })
      if (sent) {
        // WebSocket 发送成功：乐观消息已 push，等待 chat_sent 确认替换
        // 设置确认超时：若 10s 内未收到 chat_sent/chat_message 确认，则移除该乐观消息，
        // 避免 WS 消息实际丢失时留下永久"幽灵"已发消息
        pendingTimer(tempId, conversationId)
        return tempMsg
      }
      // WebSocket 发送失败：移除乐观消息，走 HTTP 兜底
      if (conversationId === currentConversationId.value) {
        const idx = messages.value.findIndex((m) => m.id === tempId)
        if (idx >= 0) messages.value.splice(idx, 1)
      }
    }

    // WebSocket 不可用，走 HTTP API 兜底
    try {
      const res = await sendChatMessage(conversationId, { content, senderType })
      if (res && res.message) {
        const realMsg = normalizeChatMessage(res.message)
        // REST 发送时，将返回的消息 push 到列表
        if (realMsg) {
          messages.value.push(realMsg)
        }
        return realMsg
      }
      return null
    } catch (e) {
      console.error('[ChatStore] 发送消息失败：', e)
      throw e
    }
  }

  // ========== 处理 WebSocket 收到的消息（chat_message 广播）==========
  function handleIncomingMessage(data) {
    if (!data) return
    const convId = data.conversationId || data.conversation_id
    const msg = normalizeChatMessage(data)
    if (!msg) return
    // 校验 convId 安全性，防止原型污染
    if (!isSafeObjectKey(convId)) return
    // 消息 id 去重：SSE 与 WebSocket 双通道可能推送同一消息，避免重复插入/重复计数
    if (msg.id && processedMessageIds.has(msg.id)) return
    if (msg.id) processedMessageIds.add(msg.id)

    // 仅处理当前会话的消息（直接追加到列表）
    if (convId && convId === currentConversationId.value) {
      // 避免重复（WebSocket 广播可能重复到达）
      if (!messages.value.find((m) => m.id === msg.id)) {
        // 移除匹配的待确认临时消息（内容 + 发送者类型一致），
        // 当服务器广播 chat_message 时，乐观消息会被真实消息替换
        const tempIdx = messages.value.findIndex(
          (m) => m._pending && m.content === msg.content
        )
        if (tempIdx >= 0) {
          // 清除该乐观消息的确认超时定时器
          clearPendingTimer(messages.value[tempIdx].id)
          messages.value.splice(tempIdx, 1)
        }
        messages.value.push(msg)
      }
    } else if (convId) {
      // 非当前会话：增加未读计数（id 去重后只加一次）
      unreadCounts.value[convId] = (unreadCounts.value[convId] || 0) + 1
    }
  }

  // ========== 处理 WebSocket 发送确认（chat_sent 事件）==========
  // 服务器确认收到消息后回传真实消息，用真实消息替换临时乐观消息
  function handleSentConfirmation(data) {
    if (!data) return
    const msg = normalizeChatMessage(data)
    if (!msg) return
    const convId = msg.conversationId
    if (!isSafeObjectKey(convId)) return
    // 仅处理当前会话的消息
    if (convId !== currentConversationId.value) return

    // 查找匹配的待确认临时消息（内容一致即可，不要求 senderType 一致，
    // 因为 token 切换可能导致乐观消息的 senderType 与服务器回传的不一致）
    const tempIdx = messages.value.findIndex(
      (m) => m._pending && m.content === msg.content
    )
    if (tempIdx >= 0) {
      // 清除该乐观消息的确认超时定时器
      clearPendingTimer(messages.value[tempIdx].id)
      // 如果真实消息已存在（chat_message 广播先到达），直接删除临时消息
      if (messages.value.find((m) => m.id === msg.id)) {
        messages.value.splice(tempIdx, 1)
      } else {
        // 用真实消息替换临时消息
        messages.value.splice(tempIdx, 1, msg)
      }
      return
    }
    // 没有匹配的临时消息：如果真实消息不存在则添加
    if (!messages.value.find((m) => m.id === msg.id)) {
      messages.value.push(msg)
    }
  }

  // ========== 处理已读回执 ==========
  function handleReadReceipt(data) {
    if (!data) return
    const convId = data.conversationId || data.conversation_id
    // 校验 convId 安全性，防止原型污染
    if (!isSafeObjectKey(convId)) return
    if (convId) {
      unreadCounts.value[convId] = 0
    }
  }

  // ========== 标记会话已读 ==========
  async function markAsRead(conversationId) {
    // 校验键安全性
    if (!isSafeObjectKey(conversationId)) return
    // 清除本地未读计数
    if (unreadCounts.value[conversationId]) {
      unreadCounts.value[conversationId] = 0
    }
    // 调用后端 API 标记已读
    try {
      await markConversationRead(conversationId)
    } catch (e) {
      console.error('[ChatStore] 标记已读失败：', e)
    }
  }

  // ========== 获取会话未读数 ==========
  function getUnreadCount(conversationId) {
    if (!isSafeObjectKey(conversationId)) return 0
    return unreadCounts.value[conversationId] || 0
  }

  // ========== 删除会话（管理员） ==========
  async function deleteConversation(conversationId) {
    if (!isSafeObjectKey(conversationId)) return false
    try {
      await deleteMessage(conversationId)
      // 如果删除的是当前会话，清空消息
      if (currentConversationId.value === conversationId) {
        messages.value = []
        currentConversationId.value = null
      }
      // 清除未读计数
      delete unreadCounts.value[conversationId]
      return true
    } catch (e) {
      console.error('[ChatStore] 删除会话失败：', e)
      throw e
    }
  }

  // ========== 删除单条聊天消息（管理员） ==========
  async function deleteChatMessage(conversationId, messageId) {
    // 目前后端没有单独删除聊天消息的接口，此处预留
    // 如需实现，后端需添加 DELETE /api/messages/{mid}/chat/{cid} 接口
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx >= 0) {
      messages.value.splice(idx, 1)
    }
  }

  // ========== 清空当前会话 ==========
  function clearMessages() {
    messages.value = []
    currentConversationId.value = null
  }

  // ========== 重置所有状态 ==========
  function resetAll() {
    messages.value = []
    currentConversationId.value = null
    loading.value = false
    unreadCounts.value = {}
    processedMessageIds.clear()
    pendingTimers.forEach((t) => clearTimeout(t))
    pendingTimers.clear()
  }

  return {
    messages,
    currentConversationId,
    loading,
    unreadCounts,
    loadMessages,
    sendMessage,
    handleIncomingMessage,
    handleSentConfirmation,
    handleReadReceipt,
    markAsRead,
    getUnreadCount,
    deleteConversation,
    deleteChatMessage,
    clearMessages,
    resetAll
  }
})
