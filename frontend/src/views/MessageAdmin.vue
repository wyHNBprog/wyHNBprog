<template>
  <div class="message-admin-page">
    <!-- 会话列表 -->
    <template v-if="!selectedConversation">
      <NavBar title="私信管理" :show-home="true" />
      <div class="conversation-list">
        <div v-if="messages.length === 0 && !loading" class="empty-state">
          <div class="empty-state-icon">📭</div>
          <div class="empty-state-text">暂无私信</div>
        </div>
        <div
          v-for="msg in sortedMessages"
          :key="msg.id"
          class="conversation-item"
          :class="{ unread: getUnreadCount(msg) > 0 }"
          @click="selectConversation(msg)"
        >
          <div class="conv-avatar">{{ getAvatarChar(msg) }}</div>
          <div class="conv-content">
            <div class="conv-header">
              <span class="conv-name">{{ msg.realName || msg.anonName }}</span>
              <span class="conv-time">{{ msg.timeText }}</span>
            </div>
            <div class="conv-preview">{{ getPreview(msg) }}</div>
          </div>
          <div v-if="getUnreadCount(msg) > 0" class="unread-badge">{{ getUnreadCount(msg) }}</div>
          <button class="delete-btn" @click.stop="confirmDelete(msg)">删除</button>
        </div>
      </div>
    </template>

    <!-- 聊天界面 -->
    <ChatView
      v-else
      :conversation-id="selectedConversation.id"
      :is-admin-view="true"
      :title="selectedConversation.realName || selectedConversation.anonName"
      @back="backToList"
    />

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="confirm-dialog" @click.self="deleteTarget = null">
      <div class="confirm-content">
        <p class="confirm-title">确定要删除这条私信吗？</p>
        <p class="confirm-hint">删除后无法恢复</p>
        <div class="confirm-actions">
          <button class="cancel-btn" :disabled="deleting" @click="deleteTarget = null">取消</button>
          <button class="confirm-btn" :disabled="deleting" @click="handleDelete">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import ChatView from '@/components/ChatView.vue'
import { getMessages, deleteMessage } from '@/api/message'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { useWebSocket } from '@/composables/useWebSocket'

const chatStore = useChatStore()
const uiStore = useUiStore()
const { on: onWsEvent, off: offWsEvent } = useWebSocket()

const messages = ref([])
const loading = ref(true)
const selectedConversation = ref(null)
const deleteTarget = ref(null)
const deleting = ref(false)

// ========== 排序后的会话列表（按最新活动时间降序） ==========
const sortedMessages = computed(() => {
  return [...messages.value].sort((a, b) => {
    const timeA = getLastTime(a)
    const timeB = getLastTime(b)
    return timeB - timeA
  })
})

// ========== 获取会话最后活动时间戳 ==========
function getLastTime(msg) {
  if (msg.chatMessages && msg.chatMessages.length > 0) {
    const last = msg.chatMessages[msg.chatMessages.length - 1]
    const ts = last.createdAt || last.created_at
    if (ts) {
      const d = new Date(ts.indexOf('Z') >= 0 || ts.indexOf('+') >= 0 ? ts : ts + 'Z')
      if (!isNaN(d.getTime())) return d.getTime()
    }
  }
  return 0
}

// ========== 获取头像首字 ==========
function getAvatarChar(msg) {
  const name = msg.realName || msg.anonName
  if (name) {
    return name.charAt(0)
  }
  return '匿'
}

// ========== 获取会话预览（最后一条消息） ==========
function getPreview(msg) {
  if (msg.chatMessages && msg.chatMessages.length > 0) {
    const last = msg.chatMessages[msg.chatMessages.length - 1]
    const prefix = last.senderType === 'admin' ? '管理员：' : ''
    return prefix + (last.content || '')
  }
  if (msg.replies && msg.replies.length > 0) {
    return '管理员：' + msg.replies[msg.replies.length - 1].content
  }
  return msg.content || '暂无消息'
}

// ========== 获取未读数 ==========
function getUnreadCount(msg) {
  // 优先使用后端返回的 unreadCount，其次使用 chatStore 的实时计数
  const storeCount = chatStore.getUnreadCount(String(msg.id))
  return storeCount > 0 ? storeCount : (msg.unreadCount || 0)
}

// ========== 选择会话（进入聊天） ==========
function selectConversation(msg) {
  selectedConversation.value = msg
  // 标记已读
  chatStore.markAsRead(String(msg.id))
}

// ========== 返回列表 ==========
function backToList() {
  selectedConversation.value = null
  // 重新加载列表以更新未读数和预览
  loadMessageList()
}

// ========== 确认删除 ==========
function confirmDelete(msg) {
  deleteTarget.value = msg
}

// ========== 执行删除 ==========
async function handleDelete() {
  if (deleting.value || !deleteTarget.value) return
  deleting.value = true
  try {
    await deleteMessage(deleteTarget.value.id)
    // 从列表中移除
    messages.value = messages.value.filter((m) => m.id !== deleteTarget.value.id)
    uiStore.showFadeToast('已删除')
    deleteTarget.value = null
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  } finally {
    deleting.value = false
  }
}

// ========== 加载会话列表 ==========
async function loadMessageList() {
  loading.value = true
  try {
    const res = await getMessages()
    if (res && res.messages) {
      messages.value = res.messages
    } else if (Array.isArray(res)) {
      messages.value = res
    } else {
      messages.value = []
    }
  } catch (e) {
    console.error('加载私信列表失败：', e)
    messages.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadMessageList()
  // 订阅 WebSocket：新私信到达时刷新列表（管理员实时收到新会话）
  onWsEvent('chat_message', handleRealtimeMessage)
  onWsEvent('chat_read', handleRealtimeRead)
})

onUnmounted(() => {
  offWsEvent('chat_message', handleRealtimeMessage)
  offWsEvent('chat_read', handleRealtimeRead)
})

// ========== WebSocket 实时消息处理 ==========
// 新私信到达：用户发来的消息触发列表刷新，让新会话实时出现在列表
function handleRealtimeMessage(data) {
  if (!data || !data.conversationId) return
  // 管理员自己的回复也走 chat_message，但不影响列表刷新（重载是最新状态）
  // 避免频繁刷新：新用户消息到达时更新本地条目，否则整表重载
  const convId = data.conversationId
  const senderType = data.senderType || 'user'
  if (senderType === 'user') {
    // 用户新消息：若会话已存在则原地更新预览/未读，否则整表重载
    const existed = messages.value.some((m) => String(m.id) === String(convId))
    if (existed) {
      // 已有会话：更新该条目的预览与未读计数
      messages.value = messages.value.map((m) => {
        if (String(m.id) !== String(convId)) return m
        const chatMsgs = m.chatMessages || []
        const updated = {
          ...m,
          chatMessages: [
            ...chatMsgs.filter((c) => c.id !== data.id),
            {
              id: data.id,
              createdAt: data.createdAt || data.created_at,
              senderType: data.senderType,
              content: data.content,
              isRead: false
            }
          ],
          unreadCount: (m.unreadCount || 0) + 1
        }
        return updated
      })
    } else {
      // 新会话：整表重载以获取完整会话信息
      loadMessageList()
    }
  }
}

// ========== WebSocket 已读回执处理 ==========
// 标记已读后清除对应会话未读角标
function handleRealtimeRead(data) {
  if (!data || !data.conversationId) return
  const convId = data.conversationId
  messages.value = messages.value.map((m) => {
    if (String(m.id) === String(convId)) {
      return { ...m, unreadCount: 0 }
    }
    return m
  })
}
</script>

<style scoped>
.message-admin-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ========== 会话列表 ========== */
.conversation-list {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 12px 16px;
  padding-bottom: calc(70px + env(safe-area-inset-bottom));
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-state-text {
  font-size: 14px;
  line-height: 1.6;
}

/* ========== 单条会话 ========== */
.conversation-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-card);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: transform 0.1s;
  position: relative;
}

.conversation-item:active {
  transform: scale(0.985);
}

.conversation-item.unread {
  border-left: 3px solid var(--accent);
}

/* ========== 头像 ========== */
.conv-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--accent-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
  flex-shrink: 0;
}

/* ========== 会话内容 ========== */
.conv-content {
  flex: 1;
  min-width: 0;
}

.conv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.conv-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  margin-left: 8px;
}

.conv-preview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== 未读徽章 ========== */
.unread-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #e5484d;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
  box-sizing: border-box;
  flex-shrink: 0;
}

/* ========== 删除按钮 ========== */
.delete-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: #e5484d;
  background: transparent;
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.delete-btn:active {
  transform: scale(0.95);
}

/* ========== 删除确认弹窗 ========== */
.confirm-dialog {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-content {
  background: var(--bg-card);
  border-radius: 14px;
  padding: 24px 20px 20px;
  width: calc(100% - 48px);
  max-width: 320px;
  text-align: center;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15);
}

.confirm-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.confirm-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.confirm-actions {
  display: flex;
  gap: 12px;
}

.cancel-btn,
.confirm-btn {
  flex: 1;
  padding: 10px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}

.cancel-btn {
  background: var(--bg-input);
  color: var(--text-secondary);
}

.cancel-btn:active {
  transform: scale(0.97);
}

.confirm-btn {
  background: #e5484d;
  color: #fff;
}

.confirm-btn:active {
  transform: scale(0.97);
}

.cancel-btn:disabled,
.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
