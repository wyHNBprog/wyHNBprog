<template>
  <!-- 骨架屏 -->
  <SkeletonLoader v-if="loading" type="mine" :count="6" />
  <div v-else class="mine-page">
    <!-- 用户卡片 -->
    <div class="user-card">
      <div class="user-info">
        <div class="user-avatar" :class="{ 'admin': authStore.isAdmin, 'super-admin': authStore.isSuperAdmin }">
          <template v-if="authStore.user.avatar">
            <img :src="authStore.user.avatar" style="width:100%;height:100%;border-radius:50%;object-fit:cover;" />
          </template>
          <template v-else>
            {{ authStore.isSuperAdmin ? '👑' : authStore.isAdmin ? '🔧' : (authStore.user.nickname || '?').charAt(0) }}
          </template>
        </div>
        <div>
          <div class="user-name">
            {{ authStore.user.nickname }}
            <span v-if="authStore.isSuperAdmin" class="admin-badge super-admin-badge">超级管理员</span>
            <span v-else-if="authStore.isAdmin" class="admin-badge admin-badge-plain">管理员</span>
          </div>
          <div v-if="authStore.user.department" class="user-dept">{{ authStore.user.department }}</div>
        </div>
        <div class="mine-auth-btn mine-logout-btn" @click="onLogout">退出登录</div>
      </div>
      <div class="user-stats">
        <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="myApprovedVoices">0</span></div><div class="mine-stat-label">留言</div></div>
        <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="myIdeasCount">0</span></div><div class="mine-stat-label">金点子</div></div>
        <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="myTotalLikes">0</span></div><div class="mine-stat-label">获赞</div></div>
        <div class="mine-stat"><div class="mine-stat-num"><span v-count-up="myTotalFlowers">0</span></div><div class="mine-stat-label">获花</div></div>
      </div>
      <!-- 积分卡片 -->
      <div class="mine-points-card">
        <div class="mine-points-icon">⭐</div>
        <div class="mine-points-info">
          <div class="mine-points-label">我的积分</div>
          <div class="mine-points-num">{{ authStore.user.points || 0 }}</div>
        </div>
        <div class="mine-points-tip">登录领10分 · 留言/评论/金点子/点赞/被赞均可加分</div>
      </div>
    </div>

    <!-- 菜单 -->
    <div class="menu-section">
      <div class="menu-item" @click="goTo('my-posts')">
        <div class="menu-icon">📝</div>
        <div class="menu-title">我的留言</div>
        <span v-if="myVoicesCount > 0" class="menu-count" style="display:inline;">{{ myVoicesCount }}</span>
        <span v-if="unreadByType.voice > 0" class="menu-dot"></span>
        <div class="menu-arrow">›</div>
      </div>
      <div class="menu-item" @click="goTo('my-ideas')">
        <div class="menu-icon">💡</div>
        <div class="menu-title">我的金点子</div>
        <span v-if="myIdeasCount > 0" class="menu-count" style="display:inline;">{{ myIdeasCount }}</span>
        <span v-if="unreadByType.idea > 0" class="menu-dot"></span>
        <div class="menu-arrow">›</div>
      </div>
      <div class="menu-item" @click="goTo('my-comments')">
        <div class="menu-icon">💬</div>
        <div class="menu-title">我的评论</div>
        <span v-if="myCommentsCount > 0" class="menu-count" style="display:inline;">{{ myCommentsCount }}</span>
        <div class="menu-arrow">›</div>
      </div>
      <div class="menu-item" @click="goTo('notifications')">
        <div class="menu-icon">🔔</div>
        <div class="menu-title">消息通知</div>
        <span v-if="unreadCount > 0" class="menu-count" style="display:inline;color:#e5484d;">{{ unreadCount }}</span>
        <div class="menu-arrow">›</div>
      </div>
      <div class="menu-item" @click="goTo('feedback-list')">
        <div class="menu-icon">📧</div>
        <div class="menu-title">反馈中心</div>
        <span v-if="unreadByType.feedback > 0" class="menu-dot"></span>
        <div class="menu-arrow">›</div>
      </div>
      <div v-if="!authStore.isAdmin" class="menu-item" @click="goTo('message-send')">
        <div class="menu-icon">✉</div>
        <div class="menu-title">私信管理员</div>
        <div class="menu-arrow">›</div>
      </div>
      <div class="menu-item" @click="goTo('settings')">
        <div class="menu-icon">⚙</div>
        <div class="menu-title">设置</div>
        <div class="menu-arrow">›</div>
      </div>
    </div>

    <!-- 管理面板（仅管理员，管理员身份由数据库指定） -->
    <div v-if="authStore.isAdmin" class="mine-admin-card">
      <div class="mine-admin-title">
        <span class="mine-admin-title-text">🛠 管理后台</span>
      </div>
      <div class="mine-admin-grid">
        <div class="mine-admin-item" @click="goTo('review')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </div>
          <div class="mine-admin-item-title">留言审核</div>
          <div class="mine-admin-item-desc">{{ pendingVoicesCount }} 条</div>
        </div>
        <div class="mine-admin-item" @click="goTo('comment-review')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
          </div>
          <div class="mine-admin-item-title">评论审核</div>
          <div class="mine-admin-item-desc">{{ pendingCommentsCount }} 条</div>
        </div>
        <div class="mine-admin-item" @click="goTo('idea-review')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M9 18h6M10 22h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 2a7 7 0 0 0-2 13.6V16a2 2 0 0 0 2 2h0a2 2 0 0 0 2-2v-.4A7 7 0 0 0 12 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
          </div>
          <div class="mine-admin-item-title">金点子评审</div>
          <div class="mine-admin-item-desc">{{ pendingIdeasCount }} 条</div>
        </div>
        <div class="mine-admin-item" @click="goTo('message-admin')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><polyline points="22 6 12 13 2 6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
          </div>
          <div class="mine-admin-item-title">私信管理</div>
          <div class="mine-admin-item-desc">{{ unreadMsgsCount }} 条</div>
        </div>
        <div class="mine-admin-item" @click="goTo('announce-edit')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M18.5 2.5a2.1 2.1 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
          </div>
          <div class="mine-admin-item-title">编辑公告</div>
          <div class="mine-admin-item-desc">{{ announcementsCount }} 条</div>
        </div>
        <div class="mine-admin-item" @click="goTo('dashboard')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><line x1="18" y1="20" x2="18" y2="10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="12" y1="20" x2="12" y2="4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="6" y1="20" x2="6" y2="14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </div>
          <div class="mine-admin-item-title">数据看板</div>
          <div class="mine-admin-item-desc">统计</div>
        </div>
        <div v-if="authStore.isSuperAdmin" class="mine-admin-item" @click="goTo('user-mgmt')">
          <div class="mine-admin-item-icon">
            <svg viewBox="0 0 24 24" fill="none" style="width:22px;height:22px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="1.6"/><path d="M23 21v-2a4 4 0 0 0-3-3.87" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 3.13a4 4 0 0 1 0 7.75" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
          <div class="mine-admin-item-title">用户管理</div>
          <div class="mine-admin-item-desc">角色权限</div>
        </div>
      </div>
    </div>

    <!-- 关于 -->
    <div class="about-section">NNIT 论坛 · VoiceHub v2.03</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { useRealtimeStore } from '@/stores/realtime'

const router = useRouter()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()
const realtimeStore = useRealtimeStore()

// 加载状态
const loading = ref(true)

// 分类未读计数（用于"我的留言""我的金点子"等入口红点）
const unreadByType = computed(() => realtimeStore.unreadByType)

// 我的统计
const myVoices = computed(() => dataStore.voices.filter((v) => v.isMine))
const myApprovedVoices = computed(() => myVoices.value.filter((v) => v.status === 'approved').length)
const myVoicesCount = computed(() => myVoices.value.length)
const myIdeas = computed(() => {
  return Object.values(dataStore.ideas).reduce((arr, a) => arr.concat(a.filter((i) => i.isMine)), [])
})
const myIdeasCount = computed(() => myIdeas.value.length)
const myTotalLikes = computed(() => myVoices.value.reduce((s, v) => s + (v.likeCount || 0), 0))
const myTotalFlowers = computed(() => myIdeas.value.filter((i) => i.hasFlower).length)
const myCommentsCount = computed(() => {
  return dataStore.voices.reduce((sum, v) => sum + (v.comments || []).filter((c) => c.isMine).length, 0)
})
const unreadCount = computed(() => dataStore.notifications.filter((n) => !n.read).length)

// 管理员统计
const pendingVoicesCount = computed(() => dataStore.voices.filter((v) => v.status === 'pending').length)
const pendingCommentsCount = computed(() => {
  return dataStore.voices.reduce((s, v) => s + (v.comments || []).filter((c) => c.status === 'pending').length, 0)
})
const pendingIdeasCount = computed(() => {
  return Object.values(dataStore.ideas).reduce((s, arr) => s + arr.filter((i) => i.status === 'pending').length, 0)
})
const unreadMsgsCount = computed(() => dataStore.messages.filter((m) => m.status === 'unread').length)
const announcementsCount = computed(() => dataStore.announcements.length)

function goTo(name) {
  router.push({ name })
}

async function onLogout() {
  await authStore.logout()
  uiStore.showToast('已退出登录')
}

onMounted(async () => {
  try {
    await dataStore.loadAll()
    // 数据加载后更新分类未读计数
    realtimeStore.updateUnreadByType()
  } catch (e) {
    uiStore.showToast('加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
})

// keep-alive 激活时刷新未读计数（数据由 SSE/可见性监听自动刷新，此处仅更新红点）
onActivated(() => {
  realtimeStore.updateUnreadByType()
})
</script>
