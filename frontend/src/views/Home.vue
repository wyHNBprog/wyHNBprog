<template>
  <!-- Sticky Header（品牌+Tab+统计固定不动） -->
  <div class="home-sticky-header">
  <!-- Brand Header -->
  <div class="brand-header">
    <div class="brand-logo">
      <div class="brand-n">N</div>
      <div class="brand-text">NNIT 论坛</div>
    </div>
    <div class="brand-slogan">OPEN&amp;HONEST</div>
  </div>

  <!-- Home Tabs（三个：公告 / 留言墙 / 金点子） -->
  <div class="home-tabs">
    <div
      class="home-tab"
      :class="{ active: currentTab === 'announce' }"
      @click="switchTab('announce')"
    >
      <div class="home-tab-icon">
        <svg viewBox="0 0 24 24" fill="none"><path d="M3 11l18-5v12L3 13v-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
      </div>
      论坛公告
    </div>
    <div
      class="home-tab"
      :class="{ active: currentTab === 'voice' }"
      @click="switchTab('voice')"
    >
      <div class="home-tab-icon">
        <svg viewBox="0 0 24 24" fill="none"><rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.6"/><polyline points="8 21 12 17 16 21" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      留言墙
    </div>
    <div
      class="home-tab"
      :class="{ active: currentTab === 'idea' }"
      @click="switchTab('idea')"
    >
      <div class="home-tab-icon">
        <svg viewBox="0 0 24 24" fill="none"><path d="M9 18h6M10 22h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 2a7 7 0 0 0-2 13.6V16a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2v-.4A7 7 0 0 0 12 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
      </div>
      金点子
    </div>
  </div>

  <!-- Stats -->
  <div class="user-stats fade-in" style="padding:12px 16px;background:var(--bg-card);margin:0 12px;border-radius:12px;box-shadow:var(--shadow-card);">
    <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="approvedVoicesCount">0</span></div><div class="mine-stat-label">留言</div></div>
    <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="publicIdeasCount">0</span></div><div class="mine-stat-label">金点子</div></div>
    <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="totalLikesAndIdeaLikes">0</span></div><div class="mine-stat-label">获赞</div></div>
    <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="totalComments">0</span></div><div class="mine-stat-label">评论</div></div>
  </div>

  </div><!-- /home-sticky-header -->

  <!-- Board Area（可上下滚动） -->
  <div ref="boardAreaRef" class="board-area">
    <div :key="currentTab" class="fade-in">
    <!-- 公告 Tab -->
    <template v-if="currentTab === 'announce'">
      <div v-if="dataStore.announcements.length === 0" class="board-empty">
        <div class="board-empty-icon">📢</div>
        <div class="board-empty-text">暂无公告</div>
      </div>
      <div v-else class="sticky-list">
        <div
          v-for="(a, idx) in dataStore.announcements"
          :key="a.id"
          class="sticky-note stagger-item"
          :style="{ borderLeft: '3px solid #C9A24B', animationDelay: (idx % 10) * 50 + 'ms' }"
          @click="goAnnounceView"
        >
          <div class="sticky-author">
            {{ a.timeText }}
            <span v-if="a.pinned" class="sticky-tag" style="background:rgba(196,149,106,0.12);color:#C4956A;">置顶</span>
          </div>
          <div class="sticky-content" style="font-weight:600;">{{ a.title }}</div>
          <div class="announce-full-content">{{ a.content }}</div>
        </div>
      </div>
    </template>

    <!-- 留言墙 Tab -->
    <template v-else-if="currentTab === 'voice'">
      <div v-if="approvedVoices.length === 0" class="board-empty">
        <div class="board-empty-icon">📝</div>
        <div class="board-empty-text">还没有留言<br>快来留下第一条吧</div>
      </div>
      <template v-else>
        <div class="sticky-list">
          <div
            v-for="(v, idx) in displayVoices"
            :key="v.id"
            class="sticky-note stagger-item"
            :style="{ animationDelay: (idx % 10) * 50 + 'ms' }"
            @click="openVoice(v.id)"
          >
            <div class="sticky-author">
              {{ (authStore.isAdmin && v.realName) ? v.realName : (v.anonName || '匿名') }}
              <span v-if="authStore.isAdmin" class="card-del-btn" @click.stop="onDeleteVoice(v)">删除</span>
            </div>
            <div class="sticky-content">{{ v.content }}</div>
            <div class="sticky-footer">
              <span>{{ v.timeText }}</span>
              <span
                class="like-btn"
                :class="{ liked: v.isLiked }"
                @click.stop="toggleLike(v)"
              >❤ {{ v.likeCount || 0 }}</span>
              <span>💬 {{ approvedCommentCount(v) }}</span>
            </div>
          </div>
        </div>
        <div v-if="hasMoreVoices" ref="voiceSentinelRef" class="lazy-sentinel" style="text-align:center;padding:8px;font-size:12px;color:var(--text-secondary);">下拉加载更多…</div>
        <div style="text-align:center;padding:8px;font-size:12px;color:var(--text-muted);">已显示 {{ displayVoices.length }} / {{ approvedVoices.length }}</div>
      </template>
    </template>

    <!-- 金点子 Tab -->
    <template v-else-if="currentTab === 'idea'">
      <!-- 分类筛选 pills -->
      <div class="tag-scroll" style="margin:-16px -16px 12px;border-bottom:1px solid var(--border-color);border-radius:0;background:var(--bg-card);">
        <div
          v-for="c in ideaCategories"
          :key="c"
          class="tag-chip"
          :class="{ active: currentIdeaCategory === c }"
          @click="setIdeaCategory(c)"
        >{{ c }}</div>
      </div>

      <div v-if="filteredIdeas.length === 0" class="board-empty">
        <div class="board-empty-icon">💡</div>
        <div class="board-empty-text">暂时没有金点子<br>快来贡献你的金点子吧</div>
      </div>
      <template v-else>
        <div class="sticky-list">
          <div
            v-for="(i, idx) in displayIdeas"
            :key="i.id"
            class="sticky-note stagger-item"
            :style="{ borderLeft: '3px solid var(--accent)', animationDelay: (idx % 10) * 50 + 'ms' }"
          >
            <div class="sticky-author">
              {{ (authStore.isAdmin && i.realName) ? i.realName : (i.anonName || '匿名') }} · {{ i.timeText }}
              <span v-if="authStore.isAdmin" class="card-del-btn" @click.stop="onDeleteIdea(i)">删除</span>
            </div>
            <div class="sticky-content" style="font-weight:600;">
              {{ i.title }}
              <span v-if="i.hasFlower" class="idea-flower-mark"> 🌸</span>
              <span v-if="i.hasFirework" class="idea-firework-mark"> ✨</span>
            </div>
            <div v-if="i.desc" style="font-size:12px;color:var(--text-secondary);line-height:1.4;margin-top:2px;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;">{{ truncate(i.desc, 40) }}</div>
            <div class="sticky-footer" style="align-items:center;">
              <span
                class="like-btn"
                :class="{ liked: i.hasVoted }"
                @click.stop="toggleIdeaLike(i)"
              >❤ {{ i.voteCount || 0 }}</span>
              <span
                v-if="authStore.isAdmin"
                class="like-btn flower-btn"
                :class="{ liked: i.hasFlower }"
                style="color:#E8A0B4;"
                @click.stop="toggleFlower(i)"
              >{{ i.hasFlower ? '🌸 已认可' : '🌸 献花' }}</span>
              <!-- 献星星按钮：仅管理员可见，非管理员不显示（与献花不同） -->
              <span
                v-if="authStore.isAdmin"
                class="like-btn firework-btn"
                :class="{ liked: i.hasFirework }"
                style="color:#FF6B6B;"
                @click.stop="toggleFirework(i)"
              >{{ i.hasFirework ? '✨ 已献星星' : '✨ 献星星' }}</span>
              <span v-if="i.category" class="sticky-tag" style="font-size:11px;">{{ i.category }}</span>
            </div>
          </div>
        </div>
        <div v-if="hasMoreIdeas" ref="ideaSentinelRef" class="lazy-sentinel" style="text-align:center;padding:8px;font-size:12px;color:var(--text-secondary);">下拉加载更多…</div>
        <div style="text-align:center;padding:8px;font-size:12px;color:var(--text-muted);">已显示 {{ displayIdeas.length }} / {{ filteredIdeas.length }}</div>
      </template>
    </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onActivated, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { likeVoice, deleteVoice } from '@/api/voice'
import { voteIdea, flowerIdea, toggleFirework as apiToggleFirework, deleteIdea } from '@/api/idea'
import { IDEA_CATS, LAZY_PAGE_SIZE } from '@/utils/constants'
import { truncate } from '@/utils/format'

const router = useRouter()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

// 当前 Tab
const currentTab = ref('announce')

// 金点子分类筛选
const currentIdeaCategory = ref('全部')
const ideaCategories = computed(() => ['全部', ...IDEA_CATS])

// 懒加载显示数量
const displayCounts = ref({ voice: LAZY_PAGE_SIZE, idea: LAZY_PAGE_SIZE })

// DOM 引用
const boardAreaRef = ref(null)
const voiceSentinelRef = ref(null)
const ideaSentinelRef = ref(null)
let lazyObserver = null

// ========== 计算属性：统计 ==========
const approvedVoices = computed(() => {
  return dataStore.voices.filter((v) => v.status === 'approved')
})

const approvedVoicesCount = computed(() => approvedVoices.value.length)

const publicIdeas = computed(() => {
  return (dataStore.ideas.voting || []).filter((i) => i.status === 'voting')
})

const publicIdeasCount = computed(() => publicIdeas.value.length)

const totalLikes = computed(() => {
  return approvedVoices.value.reduce((s, v) => s + (v.likeCount || 0), 0)
})

const ideaLikes = computed(() => {
  // 献花和献星星不统计在获赞中，与 socket 版本一致
  return publicIdeas.value.reduce((s, i) => s + (i.voteCount || 0), 0)
})

const totalLikesAndIdeaLikes = computed(() => totalLikes.value + ideaLikes.value)

const totalComments = computed(() => {
  return approvedVoices.value.reduce((s, v) => {
    return s + (v.comments ? v.comments.filter((c) => c.status === 'approved').length : 0)
  }, 0)
})

// ========== 计算属性：列表显示 ==========
const displayVoices = computed(() => {
  return approvedVoices.value.slice(0, displayCounts.value.voice)
})

const hasMoreVoices = computed(() => {
  return displayCounts.value.voice < approvedVoices.value.length
})

const filteredIdeas = computed(() => {
  const allIdeas = publicIdeas.value
  const filtered = currentIdeaCategory.value === '全部' ? allIdeas : allIdeas.filter((i) => i.category === currentIdeaCategory.value)
  // 按点赞数排序，但使用 _sortVoteCount 快照字段（点赞时不更新此字段，避免位置跳动）
  // _sortVoteCount 仅在数据加载/刷新时同步，保证排序稳定
  return filtered.slice().sort((a, b) => (b._sortVoteCount || b.voteCount || 0) - (a._sortVoteCount || a.voteCount || 0))
})

const displayIdeas = computed(() => {
  return filteredIdeas.value.slice(0, displayCounts.value.idea)
})

const hasMoreIdeas = computed(() => {
  return displayCounts.value.idea < filteredIdeas.value.length
})

// ========== 已通过评论计数 ==========
function approvedCommentCount(v) {
  return v.comments ? v.comments.filter((c) => c.status === 'approved').length : 0
}

// ========== 切换 Tab ==========
function switchTab(tab) {
  if (currentTab.value === tab) return
  currentTab.value = tab
  displayCounts.value[tab] = LAZY_PAGE_SIZE
  try {
    sessionStorage.setItem('home_tab', tab)
  } catch (e) {}
  nextTick(() => setupLazyLoad())
}

// ========== 设置金点子分类 ==========
function setIdeaCategory(cat) {
  currentIdeaCategory.value = cat
  displayCounts.value.idea = LAZY_PAGE_SIZE
  nextTick(() => setupLazyLoad())
}

// ========== 懒加载 ==========
function setupLazyLoad() {
  if (lazyObserver) {
    lazyObserver.disconnect()
    lazyObserver = null
  }
  const sentinel = currentTab.value === 'voice' ? voiceSentinelRef.value : ideaSentinelRef.value
  if (!sentinel || typeof IntersectionObserver === 'undefined') return
  lazyObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0] && entries[0].isIntersecting) {
        displayCounts.value[currentTab.value] = (displayCounts.value[currentTab.value] || LAZY_PAGE_SIZE) + LAZY_PAGE_SIZE
        lazyObserver.disconnect()
        lazyObserver = null
        nextTick(() => setupLazyLoad())
      }
    },
    { threshold: 0.1, root: boardAreaRef.value }
  )
  lazyObserver.observe(sentinel)
}

// ========== 点赞留言（乐观更新）==========
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

// ========== 点赞金点子（乐观更新）==========
function toggleIdeaLike(i) {
  if (i._voting) return
  i._voting = true
  const willLike = !i.hasVoted
  i.hasVoted = willLike
  i.voteCount = (i.voteCount || 0) + (willLike ? 1 : -1)
  if (i.voteCount < 0) i.voteCount = 0
  voteIdea(i.id)
    .then((res) => {
      if (res && typeof res.voteCount === 'number') {
        i.voteCount = res.voteCount
        i.hasVoted = res.hasVoted != null ? res.hasVoted : willLike
      }
    })
    .catch((e) => {
      i.hasVoted = !willLike
      i.voteCount = (i.voteCount || 0) + (willLike ? -1 : 1)
      if (i.voteCount < 0) i.voteCount = 0
      uiStore.showToast('操作失败：' + e.message)
    })
    .finally(() => {
      i._voting = false
    })
}

// ========== 献花（管理员，乐观更新）==========
function toggleFlower(i) {
  if (i._flowering) return
  i._flowering = true
  i.hasFlower = !i.hasFlower
  // 修复：flowerCount 是总献花数，应增减而非直接设为 1/0
  i.flowerCount = Math.max(0, (i.flowerCount || 0) + (i.hasFlower ? 1 : -1))
  flowerIdea(i.id)
    .then((res) => {
      if (res && typeof res.flowerCount === 'number') {
        i.flowerCount = res.flowerCount
        i.hasFlower = !!res.hasFlower
      }
    })
    .catch((e) => {
      i.hasFlower = !i.hasFlower
      i.flowerCount = Math.max(0, (i.flowerCount || 0) + (i.hasFlower ? 1 : -1))
      uiStore.showToast('操作失败：' + e.message)
    })
    .finally(() => {
      i._flowering = false
    })
}

// ========== 献星星（管理员，乐观更新）==========
// 与献花不同：献星星仅管理员可见，非管理员看不到按钮
function toggleFirework(i) {
  if (i._fireworking) return
  i._fireworking = true
  i.hasFirework = !i.hasFirework
  // 修复：与献花一致，fireworkCount 是总献星星数，应增减而非直接设为 1/0
  i.fireworkCount = Math.max(0, (i.fireworkCount || 0) + (i.hasFirework ? 1 : -1))
  apiToggleFirework(i.id)
    .then((res) => {
      if (res && res.idea && typeof res.idea.fireworkCount === 'number') {
        i.fireworkCount = res.idea.fireworkCount
        i.hasFirework = !!res.idea.hasFirework
      }
    })
    .catch((e) => {
      i.hasFirework = !i.hasFirework
      i.fireworkCount = Math.max(0, (i.fireworkCount || 0) + (i.hasFirework ? 1 : -1))
      uiStore.showToast('操作失败：' + e.message)
    })
    .finally(() => {
      i._fireworking = false
    })
}

// ========== 跳转 ==========
function openVoice(id) {
  router.push({ name: 'voice-detail', params: { id } })
}

function goAnnounceView() {
  router.push({ name: 'announce-view' })
}

// ========== 管理员删除留言 ==========
async function onDeleteVoice(v) {
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

// ========== 管理员删除金点子 ==========
async function onDeleteIdea(i) {
  if (!authStore.isAdmin) return
  if (!await uiStore.showConfirm({ message: '确认删除这条金点子？删除后不可恢复。', danger: true })) return
  try {
    await deleteIdea(i.id)
    const arr = dataStore.ideas.voting || []
    const idx = arr.findIndex((x) => x.id === i.id)
    if (idx !== -1) arr.splice(idx, 1)
    uiStore.showToast('已删除')
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

onMounted(() => {
  try {
    const savedTab = sessionStorage.getItem('home_tab')
    if (savedTab && savedTab !== 'announce') {
      currentTab.value = savedTab
    }
  } catch (e) {}
  nextTick(() => setupLazyLoad())
})

// keep-alive 激活时重新设置懒加载观察器（DOM 重新挂载后需重新观察哨兵元素）
onActivated(() => {
  nextTick(() => setupLazyLoad())
})

// 组件销毁时清理 IntersectionObserver，避免内存泄漏
onUnmounted(() => {
  if (lazyObserver) {
    lazyObserver.disconnect()
    lazyObserver = null
  }
})

// 监听 Tab 切换，重新设置懒加载
watch([currentTab, currentIdeaCategory], () => {
  nextTick(() => setupLazyLoad())
})
</script>
