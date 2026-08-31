<template>
  <div class="chat-view">
    <!-- 管理员视角：显示标题栏和返回按钮 -->
    <div v-if="isAdminView" class="chat-header">
      <span class="chat-back-btn" @click="handleBack">‹</span>
      <span class="chat-title">{{ title || '私信对话' }}</span>
    </div>

    <!-- 消息列表 -->
    <div ref="messagesContainer" class="chat-messages" @scroll="onScroll">
      <div v-if="loading" class="chat-loading">
        <span>加载中...</span>
      </div>
      <div v-else-if="messages.length === 0" class="chat-empty">
        <span>暂无消息记录，发送第一条消息开始对话</span>
      </div>
      <template v-else>
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-message"
          :class="{ mine: isMine(msg) }"
          @touchstart.passive="startLongPress(msg)"
          @touchend="cancelLongPress"
          @touchmove="cancelLongPress"
          @contextmenu.prevent="showDeleteConfirm"
        >
          <div class="chat-avatar">{{ getAvatarText(msg) }}</div>
          <div class="chat-bubble">
            <div v-if="showSenderName(msg)" class="chat-sender">{{ getSenderName(msg) }}</div>
            <div class="chat-content">{{ msg.content }}</div>
            <div class="chat-time">{{ formatTime(msg.createdAt) }}</div>
          </div>
        </div>
      </template>
    </div>

    <!-- 管理员视角提示 -->
    <div v-if="isAdminView" class="admin-hint">
      <span>长按消息可删除整个会话</span>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <textarea
        v-model="inputText"
        class="chat-input"
        placeholder="输入消息..."
        maxlength="1000"
        rows="1"
        :disabled="sending"
        @keydown.enter.prevent="handleSend"
        @input="autoResize"
      ></textarea>
      <button
        class="chat-send-btn"
        :class="{ loading: sending }"
        :disabled="sending || !inputText.trim()"
        @click="handleSend"
      >
        {{ sending ? '' : '发送' }}
      </button>
    </div>

    <!-- 删除确认弹窗（管理员长按删除会话） -->
    <div v-if="deleteConfirm" class="confirm-dialog" @click.self="deleteConfirm = false">
      <div class="confirm-content">
        <p class="confirm-title">确定要删除这个会话吗？</p>
        <p class="confirm-hint">删除后无法恢复，所有聊天记录将清除</p>
        <div class="confirm-actions">
          <button class="cancel-btn" :disabled="deleting" @click="deleteConfirm = false">取消</button>
          <button class="confirm-btn" :disabled="deleting" @click="handleDeleteConversation">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { useWebSocket } from '@/composables/useWebSocket'
import { deleteMessage } from '@/api/message'

const props = defineProps({
  conversationId: { type: String, required: true },
  isAdminView: { type: Boolean, default: false },
  title: { type: String, default: '' }
})

const emit = defineEmits(['back'])

const chatStore = useChatStore()
const uiStore = useUiStore()
const { on: onWsEvent, off: offWsEvent, send: sendWs, joinRoom, leaveRoom } = useWebSocket()

const messagesContainer = ref(null)
const inputText = ref('')
const sending = ref(false)
const loading = ref(false)
const deleteConfirm = ref(false)
const deleting = ref(false)

// 从 store 获取响应式数据
const messages = ref([])

// 长按定时器
let longPressTimer = null
const LONG_PRESS_DURATION = 500

// ========== 判断消息是否属于当前用户 ==========
function isMine(msg) {
  if (props.isAdminView) {
    return msg.senderType === 'admin'
  }
  return msg.senderType === 'user'
}

// ========== 获取头像文字 ==========
function getAvatarText(msg) {
  if (isMine(msg)) return '我'
  // 对方消息：优先显示真实姓名首字，其次按发送方类型占位
  if (msg.realName) return msg.realName.charAt(0)
  return msg.senderType === 'admin' ? '管' : '你'
}

// ========== 是否显示发件人姓名 ==========
// 管理员视角：对方（用户）消息显示真实姓名；普通用户视角不显示
function showSenderName(msg) {
  if (!props.isAdminView) return false
  if (isMine(msg)) return false
  return !!msg.realName
}

// ========== 获取发件人姓名 ==========
function getSenderName(msg) {
  return msg.realName || ''
}

// ========== 格式化时间为 HH:MM ==========
function formatTime(isoStr) {
  if (!isoStr) return ''
  const iso = isoStr.indexOf('Z') >= 0 || isoStr.indexOf('+') >= 0 ? isoStr : isoStr + 'Z'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return pad(d.getHours()) + ':' + pad(d.getMinutes())
}

// ========== 滚动到底部 ==========
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// ========== 滚动事件（预留：向上滚动加载更多历史） ==========
function onScroll() {
  // 当前一次性加载全部历史，无需分页
}

// ========== textarea 自适应高度 ==========
function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 80) + 'px'
}

// ========== 发送消息 ==========
async function handleSend() {
  if (sending.value) return
  const content = inputText.value.trim()
  if (!content) return
  if (content.length > 1000) {
    uiStore.showToast('消息不能超过1000字')
    return
  }
  sending.value = true
  try {
    await chatStore.sendMessage(props.conversationId, content, {
      senderType: props.isAdminView ? 'admin' : 'user',
      sendFn: sendWs
    })
    // 清空输入框并重置高度
    inputText.value = ''
    nextTick(() => {
      if (messagesContainer.value) {
        const textarea = messagesContainer.value.parentElement.querySelector('.chat-input')
        if (textarea) textarea.style.height = 'auto'
      }
    })
    // 滚动到底部
    scrollToBottom()
  } catch (e) {
    console.error('发送消息失败：', e)
    uiStore.showToast('发送失败：' + (e.message || '请重试'))
  } finally {
    sending.value = false
  }
}

// ========== 返回（管理员返回会话列表） ==========
function handleBack() {
  emit('back')
}

// ========== 长按开始 ==========
function startLongPress(msg) {
  if (!props.isAdminView) return
  cancelLongPress()
  longPressTimer = setTimeout(() => {
    showDeleteConfirm()
  }, LONG_PRESS_DURATION)
}

// ========== 取消长按 ==========
function cancelLongPress() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// ========== 显示删除确认弹窗 ==========
function showDeleteConfirm() {
  if (!props.isAdminView) return
  cancelLongPress()
  deleteConfirm.value = true
}

// ========== 执行删除会话 ==========
async function handleDeleteConversation() {
  if (deleting.value) return
  deleting.value = true
  try {
    await deleteMessage(props.conversationId)
    uiStore.showFadeToast('会话已删除')
    deleteConfirm.value = false
    // 返回会话列表
    emit('back')
  } catch (e) {
    uiStore.showToast('删除失败：' + (e.message || '请重试'))
  } finally {
    deleting.value = false
  }
}

// ========== 同步 store 消息到本地 ref ==========
function syncMessages() {
  messages.value = chatStore.messages
  scrollToBottom()
}

// ========== 监听消息列表变化，自动滚动到底部 ==========
watch(
  () => chatStore.messages.length,
  () => {
    syncMessages()
  },
  { flush: 'post' }
)

// ========== WebSocket 事件处理 ==========
function onChatMessage(data) {
  chatStore.handleIncomingMessage(data)
}

function onChatRead(data) {
  chatStore.handleReadReceipt(data)
}

onMounted(async () => {
  // 加载消息历史（一次性加载全部）
  loading.value = true
  await chatStore.loadMessages(props.conversationId)
  loading.value = false
  syncMessages()

  // 加入聊天房间（通过 WebSocket）
  joinRoom(props.conversationId)

  // 监听 WebSocket 聊天消息事件
  onWsEvent('chat_message', onChatMessage)
  // 监听 WebSocket 已读回执事件
  onWsEvent('chat_read', onChatRead)

  // 标记当前会话已读
  chatStore.markAsRead(props.conversationId)
})

onUnmounted(() => {
  // 清理长按定时器
  cancelLongPress()
  // 离开聊天房间
  leaveRoom(props.conversationId)
  // 移除 WebSocket 事件监听
  offWsEvent('chat_message', onChatMessage)
  offWsEvent('chat_read', onChatRead)
  // 清空当前会话消息
  chatStore.clearMessages()
})
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1;
  min-height: 0;
  background: var(--bg-app);
}

/* ========== 管理员标题栏 ========== */
.chat-header {
  height: 44px;
  background: var(--nav-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.chat-back-btn {
  position: absolute;
  left: 12px;
  font-size: 22px;
  color: var(--accent);
  cursor: pointer;
  padding: 0 4px;
}

.chat-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== 消息列表区域 ========== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 12px;
  background: var(--board-bg);
}

.chat-loading {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: var(--text-secondary);
}

.chat-empty {
  text-align: center;
  padding: 40px 20px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ========== 单条消息 ========== */
.chat-message {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: flex-start;
}

.chat-message.mine {
  flex-direction: row-reverse;
}

/* ========== 头像 ========== */
.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: #999;
  flex-shrink: 0;
}

.chat-message.mine .chat-avatar {
  background: #0066CC;
}

/* ========== 气泡 ========== */
.chat-bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: 12px;
  background: var(--bg-card);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  word-break: break-word;
  overflow-wrap: break-word;
}

.chat-message.mine .chat-bubble {
  background: #95EC69;
}

.chat-sender {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 4px;
}

.chat-content {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
}

.chat-message.mine .chat-content {
  color: #000;
}

.chat-time {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-align: right;
}

.chat-message.mine .chat-time {
  color: rgba(0, 0, 0, 0.4);
}

/* ========== 管理员提示 ========== */
.admin-hint {
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  padding: 4px 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

/* ========== 输入区域 ========== */
.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
  flex-shrink: 0;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 14px;
  outline: none;
  background: var(--bg-input);
  color: var(--text-primary);
  resize: none;
  max-height: 80px;
  line-height: 1.4;
  box-sizing: border-box;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.chat-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-dim);
}

.chat-send-btn {
  padding: 8px 16px;
  background: #07C160;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.2s, transform 0.1s;
  min-height: 36px;
}

.chat-send-btn:active {
  transform: scale(0.96);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn.loading {
  opacity: 0.6;
  pointer-events: none;
  position: relative;
}

.chat-send-btn.loading::after {
  content: '';
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: block;
  margin: 0 auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
