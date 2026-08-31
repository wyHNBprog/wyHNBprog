<template>
  <div class="message-send-page">
    <NavBar title="私信管理员" :show-home="true" />

    <!-- 有会话时：直接显示聊天界面 -->
    <ChatView
      v-if="conversationId"
      :conversation-id="conversationId"
      :is-admin-view="false"
    />

    <!-- 无会话时：显示首次发送表单 -->
    <div v-else-if="!loading" class="initial-message">
      <div class="empty-state">
        <div class="empty-state-icon">✉</div>
        <p class="empty-state-text">还没有和管理员的私信记录</p>
        <p class="hint">发送一条消息开始对话</p>
      </div>
      <div class="input-area">
        <textarea
          v-model="content"
          class="msg-textarea"
          placeholder="输入消息内容..."
          maxlength="500"
          rows="4"
        ></textarea>
        <div class="actions">
          <span class="char-count">{{ content.length }}/500</span>
          <button
            class="send-btn"
            :class="{ loading: sending }"
            :disabled="!content.trim() || sending"
            @click="handleSendInitial"
          >
            {{ sending ? '发送中...' : '发送' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-else class="loading-state">
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import ChatView from '@/components/ChatView.vue'
import { getMessages, createMessage } from '@/api/message'
import { useUiStore } from '@/stores/ui'
import { ANON_NAME } from '@/utils/constants'

const uiStore = useUiStore()

const conversationId = ref(null)
const content = ref('')
const loading = ref(true)
const sending = ref(false)

// ========== 发送首条消息（创建新会话） ==========
async function handleSendInitial() {
  if (sending.value) return
  const c = content.value.trim()
  if (!c) {
    uiStore.showToast('请输入消息内容')
    return
  }
  if (c.length > 500) {
    uiStore.showToast('内容不能超过500字')
    return
  }
  sending.value = true
  try {
    const res = await createMessage({
      content: c,
      anonName: ANON_NAME
    })
    if (res && res.message) {
      uiStore.showFadeToast('私信已发送')
      // 切换到聊天界面
      conversationId.value = res.message.id
    }
  } catch (e) {
    uiStore.showToast('发送失败：' + e.message)
  } finally {
    sending.value = false
  }
}

// ========== 页面加载：查找已有会话 ==========
onMounted(async () => {
  loading.value = true
  try {
    const res = await getMessages()
    if (res && res.messages) {
      // 过滤有效会话（status 非 deleted），取最新一条
      const validMessages = res.messages.filter((m) => m.status !== 'deleted')
      if (validMessages.length > 0) {
        // 列表已按 created_at desc 排序，取第一条
        conversationId.value = validMessages[0].id
      }
    }
  } catch (e) {
    console.error('加载私信列表失败：', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.message-send-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* ========== 首次发送表单 ========== */
.initial-message {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 16px;
  display: flex;
  flex-direction: column;
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

.hint {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.input-area {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--shadow-card);
  margin-top: auto;
}

.msg-textarea {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
  resize: none;
  background: var(--bg-input);
  color: var(--text-primary);
  box-sizing: border-box;
}

.msg-textarea::placeholder {
  color: var(--text-muted);
}

.msg-textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-dim);
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.char-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.send-btn {
  padding: 8px 24px;
  background: var(--accent);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}

.send-btn:active {
  transform: scale(0.96);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-btn.loading {
  opacity: 0.6;
  pointer-events: none;
}

/* ========== 加载状态 ========== */
.loading-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--text-secondary);
}
</style>
