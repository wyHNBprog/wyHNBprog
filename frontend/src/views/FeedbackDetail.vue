<template>
  <NavBar title="反馈详情" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="!feedback" class="empty-state">
        <div class="empty-state-icon">🔍</div>
        <div class="empty-state-text">反馈不存在或已被删除</div>
      </div>
      <template v-else>
        <div class="detail-card">
          <div class="post-header" style="margin-bottom:10px;">
            <div class="post-avatar">📧</div>
            <span class="post-anon">{{ feedback.category }}</span>
            <span class="post-time">{{ feedback.timeText }}</span>
          </div>
          <div class="detail-content">{{ feedback.content }}</div>
          <div class="post-footer" style="margin-top:12px;">
            <StatusBadge v-if="feedback.status === 'replied'" status="approved" />
            <StatusBadge v-else status="pending" />
          </div>
        </div>

        <!-- 管理员回复 -->
        <div v-if="feedback.reply" class="reply-item" style="margin:0 16px 16px;">
          <div class="reply-author">管理员回复</div>
          <div class="reply-text">{{ feedback.reply }}</div>
          <div v-if="feedback.replyTime" class="reply-time">{{ feedback.replyTime }}</div>
        </div>

        <!-- 管理员回复框 -->
        <div v-if="authStore.isAdmin && !feedback.reply" class="admin-reply-area">
          <div class="form-label">管理员回复</div>
          <textarea
            v-model="replyInput"
            class="admin-textarea"
            placeholder="输入回复内容..."
          ></textarea>
          <button
            class="admin-btn"
            :class="{ loading: submitting }"
            @click="submitReply"
          >{{ submitting ? '回复中...' : '提交回复' }}</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { replyFeedback } from '@/api/feedback'

const route = useRoute()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

const replyInput = ref('')
const submitting = ref(false)

const feedback = computed(() => {
  const id = route.params.id
  return dataStore.feedbacks.find((f) => f.id == id) || null
})

async function submitReply() {
  if (submitting.value) return
  const content = replyInput.value.trim()
  if (!content) {
    uiStore.showToast('请输入回复内容')
    return
  }
  submitting.value = true
  try {
    const res = await replyFeedback(feedback.value.id, { reply: content })
    if (feedback.value) {
      feedback.value.reply = content
      feedback.value.status = 'replied'
      feedback.value.replyTime = res && res.feedback && res.feedback.replyTime ? res.feedback.replyTime : ''
    }
    uiStore.showToast('回复成功')
  } catch (e) {
    uiStore.showToast('回复失败：' + e.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (dataStore.feedbacks.length === 0) {
    await dataStore.loadFeedbacks()
  }
})
</script>
