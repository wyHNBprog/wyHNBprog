<template>
  <NavBar title="金点子评审" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="pendingIdeas.length === 0 && rejectedIdeas.length === 0" class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-text">暂无待审核或已驳回金点子</div>
      </div>
      <template v-else>
        <!-- 待审核 -->
        <div v-if="pendingIdeas.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="font-size:13px;font-weight:600;color:var(--text-secondary);margin-bottom:10px;padding-left:4px;">待审核 ({{ pendingIdeas.length }})</div>
          <div
            v-for="i in pendingIdeas"
            :key="i.id"
            class="idea-card"
            v-longpress="() => onLongPressDelete(i)"
          >
            <div class="idea-title">
              {{ i.title }}
              <span v-if="i.hasFlower" class="idea-flower-mark"> 🌸</span>
              <span v-if="i.hasFirework" class="idea-firework-mark"> ✨</span>
            </div>
            <div class="idea-desc">{{ i.desc }}</div>
            <div class="post-footer" style="margin-bottom:8px;">
              <span class="sticky-tag">{{ i.category }}</span>
              <span style="margin-left:auto;font-size:12px;color:var(--text-secondary);">{{ (authStore.isAdmin && i.realName) ? i.realName : (i.anonName || '匿名') }} · {{ i.timeText }}</span>
            </div>
            <div class="review-actions">
              <button class="btn-approve" @click="onApprove(i)">通过</button>
              <button class="btn-reject" @click="onReject(i)">驳回</button>
            </div>
          </div>
        </div>

        <!-- 已驳回 -->
        <div v-if="rejectedIdeas.length > 0" style="margin-bottom:20px;padding-top:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-left:4px;">
            <span style="font-size:13px;font-weight:600;color:var(--text-secondary);">已驳回 ({{ rejectedIdeas.length }})</span>
            <button
              class="clear-all-btn"
              :disabled="clearingAll"
              @click="onClearAllRejected"
            >{{ clearingAll ? '处理中…' : '🗑 一键清除审核记录' }}</button>
          </div>
          <div
            v-for="i in rejectedIdeas"
            :key="i.id"
            class="idea-card"
            v-longpress="() => onLongPressDelete(i)"
          >
            <div class="idea-title">
              {{ i.title }}
              <span v-if="i.hasFlower" class="idea-flower-mark"> 🌸</span>
              <span v-if="i.hasFirework" class="idea-firework-mark"> ✨</span>
            </div>
            <div class="idea-desc">{{ i.desc }}</div>
            <div class="post-footer" style="margin-bottom:8px;">
              <StatusBadge :status="i.status" />
              <span class="sticky-tag" style="margin-left:8px;">{{ i.category }}</span>
              <span style="margin-left:auto;font-size:12px;color:var(--text-secondary);">{{ i.timeText }}</span>
            </div>
            <div v-if="i.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ i.rejectReason }}</div>
            <!-- 单条清除审核记录按钮 -->
            <div class="review-actions">
              <button class="btn-clear-review" @click.stop="onClearReview(i)">清除审核记录</button>
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
import { updateIdeaStatus, deleteIdea, clearIdeaReview, clearAllIdeaReviews } from '@/api/idea'

const dataStore = useDataStore()
const uiStore = useUiStore()
const authStore = useAuthStore()

const clearingAll = ref(false)

// 待审核金点子
const pendingIdeas = computed(() => {
  return Object.values(dataStore.ideas).reduce((arr, a) => arr.concat(a.filter((i) => i.status === 'pending')), [])
})

// 已驳回金点子
const rejectedIdeas = computed(() => {
  return Object.values(dataStore.ideas).reduce((arr, a) => arr.concat(a.filter((i) => i.status === 'rejected')), [])
})

// 通过审核（乐观更新：先移除列表项，再调API，失败则回滚）
async function onApprove(i) {
  const oldStatus = i.status
  const oldRejectReason = i.rejectReason
  // 乐观更新：立即从原列表移除并加入voting
  i.status = 'voting'
  i.rejectReason = ''
  Object.keys(dataStore.ideas).forEach((key) => {
    const arr = dataStore.ideas[key]
    const idx = arr.findIndex((x) => x.id === i.id)
    if (idx !== -1 && key !== 'voting') {
      arr.splice(idx, 1)
      if (!dataStore.ideas.voting.find((x) => x.id === i.id)) {
        dataStore.ideas.voting.unshift(i)
      }
    }
  })
  try {
    await updateIdeaStatus(i.id, { status: 'voting' })
    uiStore.showToast('已通过')
  } catch (e) {
    // 回滚
    i.status = oldStatus
    i.rejectReason = oldRejectReason
    // 回滚列表位置：所有 idea 统一放在 voting 数组，从 voting 移除后放回
    dataStore.ideas.voting = dataStore.ideas.voting.filter((x) => x.id !== i.id)
    if (!dataStore.ideas.voting.find((x) => x.id === i.id)) {
      dataStore.ideas.voting.unshift(i)
    }
    if (e && e.status === 409) {
      uiStore.showToast('该内容已被其他管理员审核')
      await dataStore.loadAll(true)
    } else {
      uiStore.showToast('操作失败：' + e.message)
    }
  }
}

// 驳回
function onReject(i) {
  uiStore.openRejectModal({
    title: '驳回金点子',
    ideaId: i.id
  })
}

// 删除金点子
async function onDelete(i) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认删除这条金点子？删除后不可恢复。', danger: true })) return
  try {
    await deleteIdea(i.id)
    // 从所有分类列表中移除
    Object.keys(dataStore.ideas).forEach((key) => {
      const arr = dataStore.ideas[key]
      const idx = arr.findIndex((x) => x.id === i.id)
      if (idx !== -1) arr.splice(idx, 1)
    })
    uiStore.showToast('已删除')
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

// 长按删除（管理员）
function onLongPressDelete(i) {
  if (!authStore.isAdmin) return
  onDelete(i)
}

// 单条清除审核记录
async function onClearReview(i) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认清除这条审核记录？内容不会被删除。', danger: false })) return
  try {
    await clearIdeaReview(i.id)
    i.reviewCleared = true
    // 从所有分类列表中移除该卡片
    Object.keys(dataStore.ideas).forEach((key) => {
      const arr = dataStore.ideas[key]
      const idx = arr.findIndex((x) => x.id === i.id)
      if (idx !== -1) arr.splice(idx, 1)
    })
    uiStore.showToast('审核记录已清除')
  } catch (e) {
    uiStore.showToast('清除失败：' + e.message)
  }
}

// 一键清除所有已驳回审核记录
async function onClearAllRejected() {
  if (!authStore.isAdmin) return
  if (clearingAll.value) return
  if (!await uiStore.showConfirm({ message: '确认清除所有已驳回金点子的审核记录？内容不会被删除。', danger: false })) return
  clearingAll.value = true
  try {
    const res = await clearAllIdeaReviews()
    // 从所有分类列表中移除已驳回金点子
    Object.keys(dataStore.ideas).forEach((key) => {
      dataStore.ideas[key] = dataStore.ideas[key].filter((i) => i.status !== 'rejected')
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
.idea-firework-mark {
  font-size: 14px;
}
</style>
