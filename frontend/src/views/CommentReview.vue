<template>
  <NavBar title="评论审核" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="pendingComments.length === 0 && rejectedComments.length === 0" class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-text">暂无待审核或已驳回评论</div>
      </div>
      <template v-else>
        <!-- 待审核 -->
        <div v-if="pendingComments.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:10px;padding-left:4px;">待审核 ({{ pendingComments.length }})</div>
          <div
            v-for="item in pendingComments"
            :key="item.comment.id"
            class="post-card"
            style="margin-bottom:12px;"
          >
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px;">来自留言：{{ truncate(item.voice.content, 40) }}</div>
            <div class="post-header">
              <div class="post-avatar">{{ item.comment.anonName ? item.comment.anonName.charAt(0) : '?' }}</div>
              <span class="post-anon">{{ item.comment.anonName }}</span>
              <span class="post-time">{{ item.comment.timeText }}</span>
            </div>
            <div class="post-content" style="margin-top:4px;">{{ item.comment.content }}</div>
            <div class="review-actions">
              <button class="btn-approve" @click="onApprove(item)">通过</button>
              <button class="btn-reject" @click="onReject(item)">驳回</button>
            </div>
          </div>
        </div>

        <!-- 已驳回 -->
        <div v-if="rejectedComments.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-left:4px;">
            <span style="font-size:13px;font-weight:600;color:var(--text-secondary);">已驳回 ({{ rejectedComments.length }})</span>
            <button
              class="clear-all-btn"
              :disabled="clearingAll"
              @click="onClearAllRejected"
            >{{ clearingAll ? '处理中…' : '🗑 一键清除审核记录' }}</button>
          </div>
          <div
            v-for="item in rejectedComments"
            :key="item.comment.id"
            class="post-card"
            style="margin-bottom:12px;"
          >
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px;">来自留言：{{ truncate(item.voice.content, 40) }}</div>
            <div class="post-header">
              <div class="post-avatar">{{ item.comment.anonName ? item.comment.anonName.charAt(0) : '?' }}</div>
              <span class="post-anon">{{ item.comment.anonName }}</span>
              <span class="post-time">{{ item.comment.timeText }}</span>
              <StatusBadge :status="item.comment.status" />
            </div>
            <div class="post-content" style="margin-top:4px;">{{ item.comment.content }}</div>
            <div v-if="item.comment.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ item.comment.rejectReason }}</div>
            <!-- 单条清除审核记录按钮 -->
            <div class="review-actions">
              <button class="btn-clear-review" @click.stop="onClearReview(item)">清除审核记录</button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { updateCommentStatus, clearCommentReview, clearAllCommentReviews } from '@/api/voice'
import { truncate } from '@/utils/format'

const dataStore = useDataStore()
const uiStore = useUiStore()
const authStore = useAuthStore()

const clearingAll = ref(false)

// 待审核评论（附带所属留言信息）
const pendingComments = computed(() => {
  const result = []
  dataStore.voices.forEach((v) => {
    ;(v.comments || []).forEach((c) => {
      if (c.status === 'pending') {
        result.push({ voice: v, comment: c })
      }
    })
  })
  return result
})

// 已驳回评论
const rejectedComments = computed(() => {
  const result = []
  dataStore.voices.forEach((v) => {
    ;(v.comments || []).forEach((c) => {
      if (c.status === 'rejected') {
        result.push({ voice: v, comment: c })
      }
    })
  })
  return result
})

// 通过审核（乐观更新：先移除列表项，再调API，失败则回滚）
async function onApprove(item) {
  const oldStatus = item.comment.status
  const oldRejectReason = item.comment.rejectReason
  // 乐观更新：立即标记为已通过
  item.comment.status = 'approved'
  item.comment.rejectReason = ''
  try {
    await updateCommentStatus(item.voice.id, item.comment.id, { status: 'approved' })
    uiStore.showToast('已通过')
  } catch (e) {
    // 回滚
    item.comment.status = oldStatus
    item.comment.rejectReason = oldRejectReason
    if (e && e.status === 409) {
      uiStore.showToast('该内容已被其他管理员审核')
      await dataStore.loadAll(true)
    } else {
      uiStore.showToast('操作失败：' + e.message)
    }
  }
}

// 驳回
function onReject(item) {
  uiStore.openRejectModal({
    title: '驳回评论',
    commentInfo: { voiceId: item.voice.id, commentId: item.comment.id }
  })
}

// 单条清除审核记录
async function onClearReview(item) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认清除这条审核记录？内容不会被删除。', danger: false })) return
  try {
    await clearCommentReview(item.voice.id, item.comment.id)
    item.comment.reviewCleared = true
    // 从留言的评论列表中移除该评论
    const v = item.voice
    const idx = v.comments.findIndex((c) => c.id === item.comment.id)
    if (idx !== -1) v.comments.splice(idx, 1)
    uiStore.showToast('审核记录已清除')
  } catch (e) {
    uiStore.showToast('清除失败：' + e.message)
  }
}

// 一键清除所有已驳回评论审核记录
async function onClearAllRejected() {
  if (!authStore.isAdmin) return
  if (clearingAll.value) return
  if (!await uiStore.showConfirm({ message: '确认清除所有已驳回评论的审核记录？内容不会被删除。', danger: false })) return
  clearingAll.value = true
  try {
    const res = await clearAllCommentReviews()
    // 从所有留言中移除已驳回评论
    dataStore.voices.forEach((v) => {
      if (v.comments) {
        v.comments = v.comments.filter((c) => c.status !== 'rejected')
      }
    })
    uiStore.showToast('已清除 ' + (res && res.count ? res.count : '所有') + ' 条审核记录')
  } catch (e) {
    uiStore.showToast('清除失败：' + e.message)
  } finally {
    clearingAll.value = false
  }
}

onMounted(async () => {
  try {
    await dataStore.loadAll(true)
  } catch (e) {
    uiStore.showToast('加载失败，请稍后重试')
  }
})
</script>

<style scoped>
.clear-all-btn {
  padding: 5px 12px;
  font-size: 12px;
  color: #C4726A;
  background: rgba(196,114,106,0.08);
  border: 1px solid rgba(196,114,106,0.2);
  border-radius: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}
.clear-all-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-clear-review {
  padding: 5px 14px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-clear-review:active {
  opacity: 0.7;
}
</style>
