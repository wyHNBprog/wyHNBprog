<template>
  <NavBar title="留言详情" :show-home="true" />
  <div class="page detail-page">
    <div v-if="!voice" class="empty-state">
      <div class="empty-state-icon">🔍</div>
      <div class="empty-state-text">留言不存在或已被删除</div>
    </div>
    <template v-else>
      <!-- 留言卡片 -->
      <div class="detail-card">
        <div class="post-header" style="margin-bottom:10px;">
          <div class="post-avatar">🎭</div>
          <span class="post-anon">{{ voice.anonName }}</span>
          <span class="post-time">{{ voice.timeText }}</span>
          <button
            v-if="authStore.isAdmin"
            class="review-del-btn"
            style="margin-left:auto;"
            @click.stop="onDeleteVoice"
          >
            <svg viewBox="0 0 24 24" fill="none" style="width:16px;height:16px;display:inline-block;vertical-align:-2px"><polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><line x1="10" y1="11" x2="10" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="14" y1="11" x2="14" y2="16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </button>
        </div>
        <div class="detail-content">{{ voice.content }}</div>
        <div class="post-footer" style="margin-top:12px;">
          <span
            class="post-action"
            :class="{ liked: voice.isLiked }"
            @click="toggleLike"
          >❤ {{ voice.likeCount || 0 }}</span>
          <span>💬 {{ approvedComments.length }}</span>
        </div>
      </div>

      <!-- 评论区 -->
      <div ref="commentScrollRef" class="comment-section" style="padding:0 16px;">
        <div class="comment-title" style="margin-bottom:12px;">评论 ({{ approvedComments.length }})</div>
        <div v-if="approvedComments.length === 0" class="empty-state" style="padding:30px 20px;">
          <div class="empty-state-icon">💬</div>
          <div class="empty-state-text">还没有评论，快来抢沙发</div>
        </div>
        <template v-else>
          <div
            v-for="c in displayComments"
            :key="c.id"
            class="comment-item"
            v-longpress="() => onLongPressDeleteComment(c)"
          >
            <div class="comment-avatar">{{ c.anonName ? c.anonName.charAt(0) : '?' }}</div>
            <div class="comment-body">
              <div class="comment-name">{{ c.anonName }}</div>
              <div class="comment-text">{{ c.content }}</div>
              <div class="comment-meta">
                <span>{{ c.timeText }}</span>
                <span
                  class="comment-like-btn"
                  data-no-longpress
                  :class="{ liked: c.isLiked }"
                  @click="toggleCommentLike(c)"
                >❤ {{ c.likeCount || 0 }}</span>
                <span
                  v-if="authStore.isAdmin"
                  class="comment-del-btn"
                  data-no-longpress
                  @click.stop="onDeleteComment(c)"
                >删除</span>
              </div>
            </div>
          </div>
          <div v-if="hasMoreComments" ref="commentSentinelRef" class="lazy-sentinel" style="text-align:center;padding:8px;font-size:12px;color:var(--text-secondary);">已显示 {{ displayComments.length }} / {{ approvedComments.length }} 条，上拉加载更多…</div>
        </template>
      </div>

      <!-- 评论输入栏 -->
      <div class="comment-input-bar">
        <input
          v-model="commentInput"
          class="comment-input"
          placeholder="写下你的评论..."
          @keyup.enter="addComment"
        />
        <button class="comment-send" :class="{ loading: submitting }" @click="addComment">发送</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { likeVoice, createComment, likeComment, deleteComment, deleteVoice } from '@/api/voice'
import { COMMENT_PAGE_SIZE } from '@/utils/constants'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

const commentInput = ref('')
const submitting = ref(false)
const commentScrollRef = ref(null)
const commentSentinelRef = ref(null)
let commentObserver = null

// 当前留言
const voice = computed(() => {
  const id = route.params.id
  return dataStore.findVoiceById(id)
})

// 已通过评论
const approvedComments = computed(() => {
  if (!voice.value) return []
  return (voice.value.comments || []).filter((c) => c.status === 'approved')
})

// 评论显示数量（懒加载）
const commentDisplayCount = ref(COMMENT_PAGE_SIZE)
const displayComments = computed(() => {
  return approvedComments.value.slice(0, commentDisplayCount.value)
})
const hasMoreComments = computed(() => {
  return commentDisplayCount.value < approvedComments.value.length
})

// 点赞留言（乐观更新）
function toggleLike() {
  const v = voice.value
  if (!v || v._liking) return
  v._liking = true
  const willLike = !v.isLiked
  v.isLiked = willLike
  v.likeCount = (v.likeCount || 0) + (willLike ? 1 : -1)
  if (v.likeCount < 0) v.likeCount = 0
  likeVoice(v.id)
    .then((res) => {
      if (res && typeof res.likeCount === 'number') {
        v.likeCount = res.likeCount
        v.isLiked = res.isLiked != null ? res.isLiked : willLike
      }
    })
    .catch((e) => {
      v.isLiked = !willLike
      v.likeCount = (v.likeCount || 0) + (willLike ? -1 : 1)
      if (v.likeCount < 0) v.likeCount = 0
      uiStore.showToast('操作失败：' + e.message)
    })
    .finally(() => {
      v._liking = false
    })
}

// 点赞评论（乐观更新）
function toggleCommentLike(c) {
  if (c._liking) return
  c._liking = true
  const willLike = !c.isLiked
  c.isLiked = willLike
  c.likeCount = (c.likeCount || 0) + (willLike ? 1 : -1)
  if (c.likeCount < 0) c.likeCount = 0
  likeComment(voice.value.id, c.id)
    .then((res) => {
      if (res && typeof res.likeCount === 'number') {
        c.likeCount = res.likeCount
        c.isLiked = res.isLiked != null ? res.isLiked : willLike
      }
    })
    .catch((e) => {
      c.isLiked = !willLike
      c.likeCount = (c.likeCount || 0) + (willLike ? -1 : 1)
      if (c.likeCount < 0) c.likeCount = 0
      uiStore.showToast('操作失败：' + e.message)
    })
    .finally(() => {
      c._liking = false
    })
}

// 添加评论
async function addComment() {
  if (submitting.value) return
  const content = commentInput.value.trim()
  if (!content) {
    uiStore.showToast('请输入内容')
    return
  }
  if (!voice.value) {
    uiStore.showToast('页面状态异常')
    return
  }
  submitting.value = true
  try {
    const res = await createComment(voice.value.id, { content: content })
    if (res && res.comment) {
      voice.value.comments.push(dataStore.normalizeComment(res.comment))
      voice.value.commentCount = voice.value.comments.filter((c) => c.status === 'approved').length
      commentInput.value = ''
      commentDisplayCount.value = COMMENT_PAGE_SIZE
      uiStore.showFadeToast(authStore.isAdmin ? '已发布' : '已提交，正在等待管理员审核')
    }
  } catch (e) {
    uiStore.showToast('评论失败：' + e.message)
  } finally {
    submitting.value = false
  }
}

// 删除评论
async function onDeleteComment(c) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认删除这条评论？删除后不可恢复。', danger: true })) return
  try {
    await deleteComment(voice.value.id, c.id)
    const v = voice.value
    const idx = v.comments.findIndex((x) => x.id === c.id)
    if (idx !== -1) v.comments.splice(idx, 1)
    v.commentCount = v.comments.filter((x) => x.status === 'approved').length
    uiStore.showToast('评论已删除')
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

// 长按删除评论（管理员）
function onLongPressDeleteComment(c) {
  if (!authStore.isAdmin) return
  onDeleteComment(c)
}

// 删除留言
async function onDeleteVoice() {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认删除这条留言？删除后不可恢复。', danger: true })) return
  try {
    await deleteVoice(voice.value.id)
    const idx = dataStore.voices.findIndex((x) => x.id === voice.value.id)
    if (idx !== -1) dataStore.voices.splice(idx, 1)
    uiStore.showToast('已删除')
    if (window.history.length > 1) {
      router.back()
    } else {
      router.push({ name: 'home' })
    }
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

onMounted(async () => {
  // 如果数据未加载，先加载
  if (dataStore.voices.length === 0) {
    try {
      await dataStore.loadAll(true)
    } catch (e) {
      uiStore.showToast('加载失败，请稍后重试')
    }
  }
  // 等待 DOM 渲染后初始化评论懒加载
  await nextTick()
  setupCommentLazyLoad()
})

// 评论懒加载：IntersectionObserver 监听哨兵元素，滚动到可视区域时加载更多
function setupCommentLazyLoad() {
  if (commentObserver) {
    commentObserver.disconnect()
    commentObserver = null
  }
  const sentinel = commentSentinelRef.value
  if (!sentinel) return
  commentObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && hasMoreComments.value) {
          // 每次加载 COMMENT_PAGE_SIZE 条评论
          commentDisplayCount.value += COMMENT_PAGE_SIZE
        }
      })
    },
    { root: null, rootMargin: '50px', threshold: 0.1 }
  )
  commentObserver.observe(sentinel)
}

// 组件销毁时清理 IntersectionObserver，避免内存泄漏
onUnmounted(() => {
  if (commentObserver) {
    commentObserver.disconnect()
    commentObserver = null
  }
})
</script>
