<template>
  <NavBar title="留言墙" :show-home="true" />
  <div class="page">
    <!-- 骨架屏 -->
    <div v-if="loading" class="post-list">
      <SkeletonLoader type="voice-card" :count="4" />
    </div>
    <!-- 空状态 -->
    <div v-else-if="approvedVoices.length === 0" class="empty-state">
      <div class="empty-state-icon">📭</div>
      <div class="empty-state-text">暂无内容</div>
    </div>
    <!-- 列表 -->
    <div v-else class="post-list">
      <div
        v-for="(v, idx) in approvedVoices"
        :key="v.id"
        class="post-card stagger-item"
        :style="{ cursor: 'pointer', animationDelay: (idx % 10) * 50 + 'ms' }"
        @click="openVoice(v.id)"
      >
        <div class="post-header">
          <div class="post-avatar">🎭</div>
          <span class="post-anon">{{ (authStore.isAdmin && v.realName) ? v.realName : (v.anonName || '匿名') }}</span>
          <span class="post-time">{{ v.timeText }}</span>
        </div>
        <div class="post-content">{{ v.content }}</div>
        <div class="post-footer">
          <span
            class="post-action"
            :class="{ liked: v.isLiked }"
            @click.stop="toggleLike(v)"
          >❤ {{ v.likeCount || 0 }}</span>
          <span>💬 {{ approvedCommentCount(v) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { likeVoice } from '@/api/voice'

const router = useRouter()
const dataStore = useDataStore()
const uiStore = useUiStore()
const authStore = useAuthStore()

// 加载状态
const loading = ref(true)

// 已通过的留言
const approvedVoices = computed(() => {
  return dataStore.voices.filter((v) => v.status === 'approved')
})

// 已通过评论计数
function approvedCommentCount(v) {
  return v.comments ? v.comments.filter((c) => c.status === 'approved').length : 0
}

// 点赞（乐观更新）
function toggleLike(v) {
  if (v._liking) return
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

function openVoice(id) {
  router.push({ name: 'voice-detail', params: { id } })
}

onMounted(async () => {
  try {
    await dataStore.loadVoices()
  } catch (e) {
    uiStore.showToast('加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
})
</script>
