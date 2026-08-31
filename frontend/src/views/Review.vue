<template>
  <NavBar title="留言审核" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="pendingVoices.length === 0 && rejectedVoices.length === 0" class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-text">暂无待审核或已驳回留言</div>
      </div>
      <template v-else>
        <!-- 待审核 -->
        <div v-if="pendingVoices.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:10px;padding-left:4px;">待审核 ({{ pendingVoices.length }})</div>
          <div
            v-for="v in pendingVoices"
            :key="v.id"
            class="post-card"
            style="margin-bottom:12px;"
            v-longpress="() => onLongPressDelete(v)"
          >
            <div class="post-header">
              <div class="post-avatar">🎭</div>
              <span class="post-anon">
                {{ v.anonName }}
                <span v-if="v.realName && v.isAnonymous" style="color:var(--accent);font-size:12px;font-weight:400;">(真实姓名: {{ v.realName }})</span>
              </span>
              <span class="post-time">{{ v.timeText }}</span>
              <button class="review-del-btn" style="margin-left:6px;padding:4px;" @click.stop="onDelete(v)">
                <svg viewBox="0 0 24 24" fill="none" style="width:16px;height:16px;display:inline-block;vertical-align:-2px"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><line x1="10" y1="11" x2="10" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="14" y1="11" x2="14" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
              </button>
            </div>
            <div class="post-content" style="margin-top:4px;">{{ v.content }}</div>
            <div class="review-actions">
              <button class="btn-approve" @click.stop="onApprove(v)">通过</button>
              <button class="btn-reject" @click.stop="onReject(v)">驳回</button>
            </div>
          </div>
        </div>

        <!-- 已驳回 -->
        <div v-if="rejectedVoices.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-left:4px;">
            <span style="font-size:13px;font-weight:600;color:var(--text-secondary);">已驳回 ({{ rejectedVoices.length }})</span>
            <button
              class="clear-all-btn"
              :disabled="clearingAll"
              @click="onClearAllRejected"
            >{{ clearingAll ? '处理中…' : '🗑 一键清除审核记录' }}</button>
          </div>
          <div
            v-for="v in rejectedVoices"
            :key="v.id"
            class="post-card"
            style="margin-bottom:12px;"
            v-longpress="() => onLongPressDelete(v)"
          >
            <div class="post-header">
              <div class="post-avatar">🎭</div>
              <span class="post-anon">{{ v.anonName }}</span>
              <span class="post-time">{{ v.timeText }}</span>
              <StatusBadge :status="v.status" />
              <button class="review-del-btn" style="margin-left:6px;padding:4px;" @click.stop="onDelete(v)">
                <svg viewBox="0 0 24 24" fill="none" style="width:16px;height:16px;display:inline-block;vertical-align:-2px"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><line x1="10" y1="11" x2="10" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="14" y1="11" x2="14" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
              </button>
            </div>
            <div class="post-content" style="margin-top:4px;">{{ v.content }}</div>
            <div v-if="v.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ v.rejectReason }}</div>
            <!-- 单条清除审核记录按钮 -->
            <div class="review-actions">
              <button class="btn-clear-review" @click.stop="onClearReview(v)">清除审核记录</button>
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
import { updateVoiceStatus, deleteVoice, clearVoiceReview, clearAllVoiceReviews } from '@/api/voice'

const dataStore = useDataStore()
const uiStore = useUiStore()
const authStore = useAuthStore()

const clearingAll = ref(false)

const pendingVoices = computed(() => dataStore.voices.filter((v) => v.status === 'pending'))
const rejectedVoices = computed(() => dataStore.voices.filter((v) => v.status === 'rejected'))

// 通过审核（乐观更新：先移除列表项，再调API，失败则回滚）
async function onApprove(v) {
  const oldStatus = v.status
  const oldRejectReason = v.rejectReason
  // 乐观更新：立即从待审核列表移除
  v.status = 'approved'
  v.rejectReason = ''
  try {
    await updateVoiceStatus(v.id, { status: 'approved' })
    uiStore.showToast('已通过')
  } catch (e) {
    // 回滚
    v.status = oldStatus
    v.rejectReason = oldRejectReason
    if (e && e.status === 409) {
      uiStore.showToast('该内容已被其他管理员审核')
      await dataStore.loadAll(true)
    } else {
      uiStore.showToast('操作失败：' + e.message)
    }
  }
}

// 驳回（打开驳回弹窗）
function onReject(v) {
  uiStore.openRejectModal({
    title: '驳回留言',
    voiceId: v.id
  })
}

// 删除
async function onDelete(v) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认删除这条留言？删除后不可恢复。', danger: true })) return
  try {
    await deleteVoice(v.id)
    const idx = dataStore.voices.findIndex((x) => x.id === v.id)
    if (idx !== -1) dataStore.voices.splice(idx, 1)
    uiStore.showToast('已删除')
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

// 长按删除（管理员）
function onLongPressDelete(v) {
  if (!authStore.isAdmin) return
  onDelete(v)
}

// 单条清除审核记录
async function onClearReview(v) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认清除这条审核记录？内容不会被删除。', danger: false })) return
  try {
    await clearVoiceReview(v.id)
    v.reviewCleared = true
    // 从已驳回列表中移除该卡片
    const idx = dataStore.voices.findIndex((x) => x.id === v.id)
    if (idx !== -1) dataStore.voices.splice(idx, 1)
    uiStore.showToast('审核记录已清除')
  } catch (e) {
    uiStore.showToast('清除失败：' + e.message)
  }
}

// 一键清除所有已驳回审核记录
async function onClearAllRejected() {
  if (!authStore.isAdmin) return
  if (clearingAll.value) return
  if (!await uiStore.showConfirm({ message: '确认清除所有已驳回留言的审核记录？内容不会被删除。', danger: false })) return
  clearingAll.value = true
  try {
    const res = await clearAllVoiceReviews()
    // 从列表中移除所有已驳回留言
    dataStore.voices = dataStore.voices.filter((v) => v.status !== 'rejected')
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
