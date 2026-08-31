<template>
  <div class="app" id="app-shell">
    <!-- 加载遮罩（初始化时显示骨架屏） -->
    <SkeletonLoader v-if="authStore.loading && !authStore.initialized" type="home" :count="4" />

    <!-- 登录页（企微启用且未登录时） -->
    <LoginView v-else-if="authStore.needLogin" />

    <!-- 路由出口（:key 变化时组件重建，触发内部入场动画） -->
    <router-view v-else v-slot="{ Component }">
      <keep-alive :include="cachedViews">
        <component :is="Component" :key="route.path" />
      </keep-alive>
    </router-view>

    <!-- 底部导航（仅首页/我的页面显示，且已登录） -->
    <TabBar v-if="showTabBar && !authStore.needLogin" />

    <!-- 全局浮窗/弹窗 -->
    <Toast />
    <PublishModal />
    <ConfirmDialog />
    <RejectModal />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { useChatStore } from '@/stores/chat'
import { useRealtimeStore } from '@/stores/realtime'
import { getToken } from '@/api/index'
import { useSSE } from '@/composables/useSSE'
import { useWebSocket } from '@/composables/useWebSocket'
import TabBar from '@/components/TabBar.vue'
import Toast from '@/components/Toast.vue'
import PublishModal from '@/components/PublishModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import RejectModal from '@/components/RejectModal.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import LoginView from '@/views/LoginView.vue'

const route = useRoute()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

// keep-alive 缓存的组件名称（首页/我的页面，避免反复创建/销毁）
const cachedViews = ['Home', 'Mine']

// 初始化实时连接（SSE 替代轮询 + WebSocket 实时聊天）
const { connect: connectSSE, disconnect: disconnectSSE } = useSSE()
const { connect: connectWS, disconnect: disconnectWS, on: onWsEvent } = useWebSocket()

// 是否显示底部导航（首页/我的页面显示）
const showTabBar = computed(() => {
  return route.meta.showTabBar === true
})

// ========== 实时连接管理（SSE + WebSocket 替代 60 秒轮询）==========

// 页面可见性变化：不可见时保持连接（SSE/WS 本身是低功耗长连接），
// 重新可见时检查连接状态，必要时重连并刷新数据
function onVisibilityChange() {
  if (document.hidden) {
    // 页面不可见时保持连接（SSE/WS 本身就是低功耗长连接，无需断开）
  } else {
    // 页面恢复可见时检查连接状态，必要时重连
    connectSSE()
    connectWS()
    // 刷新数据（仅在已登录时，避免未登录时触发 401 浪费重试次数）
    if (!authStore.needLogin) {
      dataStore.loadAll(true).catch(() => {})
    }
  }
}

// BFCache：浏览器前进/后退恢复时刷新数据，避免显示陈旧状态
function onPageShow(e) {
  if (e.persisted) {
    // BFCache 恢复后重连实时连接
    connectSSE()
    connectWS()
    dataStore.loadAll(true).catch(() => {})
  }
}

// 应用启动时初始化
onMounted(async () => {
  // 初始化暗黑模式
  uiStore.initDarkMode()

  // 监听 BFCache pageshow 事件 + 页面可见性变化
  window.addEventListener('pageshow', onPageShow)
  window.addEventListener('visibilitychange', onVisibilityChange)
  // 监听跨 Tab token 同步（另一 Tab 登出/401 时本 Tab 同步登出）
  window.addEventListener('storage', onStorageChange)

  // 检查企微回调：URL 中携带 token 参数（/?token=xxx&wecom=1）
  const urlParams = new URLSearchParams(window.location.search)
  const wecomToken = urlParams.get('token')
  const isWecomCallback = urlParams.get('wecom') === '1'

  if (wecomToken && isWecomCallback) {
    // 企微 OAuth 回调：用 token 验证用户身份
    const ok = await authStore.handleWecomCallback(wecomToken)
    // 清除 URL 中的 token 参数（安全考虑，保持 hash 路由完整）
    const cleanUrl = window.location.origin + window.location.pathname + window.location.hash
    window.history.replaceState({}, '', cleanUrl)
    if (ok) {
      // 登录成功，加载数据
      try { await dataStore.loadAll(true) } catch (e) {}
    }
  } else {
    // 正常初始化：检查 token → 有效则登录，无效则显示企微登录页
    // 路由守卫可能已触发 initAuth()，此处仅在未初始化时调用，避免重复
    if (!authStore.initialized) {
      await authStore.initAuth()
    }
    if (!authStore.needLogin) {
      try { await dataStore.loadAll(true) } catch (e) {}
    }
  }

  // 初始化完成后启动实时连接（替代 60 秒轮询）
  connectSSE()
  connectWS()

  // 监听 WebSocket 聊天消息
  onWsEvent('chat_message', (data) => {
    const chatStore = useChatStore()
    chatStore.handleIncomingMessage(data)
  })

  // 监听 WebSocket 发送确认（chat_sent）：用真实消息替换临时乐观消息
  onWsEvent('chat_sent', (data) => {
    const chatStore = useChatStore()
    chatStore.handleSentConfirmation(data)
  })

  // 监听 WebSocket 已读回执
  onWsEvent('chat_read', (data) => {
    const chatStore = useChatStore()
    chatStore.handleReadReceipt(data)
  })
})

// ========== token 变化时重连实时连接（管理员登录/退出后 token 变化，必须重连 WS/SSE）==========
watch(
  () => authStore.token,
  (newToken, oldToken) => {
    if (newToken && newToken !== oldToken) {
      // token 变化：断开旧连接，用新 token 重新连接
      disconnectSSE()
      disconnectWS()
      // 等待一下确保旧连接完全关闭
      setTimeout(() => {
        connectSSE()
        connectWS()
      }, 200)
    } else if (!newToken && oldToken) {
      // token 被清空（如 401/登出）：断开实时连接，避免旧连接悬空
      disconnectSSE()
      disconnectWS()
    }
  }
)

// ========== 跨 Tab 同步：其他 Tab 登出/401 清空 token 时，本 Tab 同步进入登录态 ==========
function onStorageChange(e) {
  if (e.key !== 'voicehub_token') return
  const authStore = useAuthStore()
  if (!e.newValue && authStore.isLoggedIn) {
    // 其他 Tab 清除了 token：本 Tab 同步登出并断开实时连接
    disconnectSSE()
    disconnectWS()
    try { useDataStore().resetAll() } catch (e2) {}
    try { useChatStore().resetAll() } catch (e2) {}
    try { useRealtimeStore().resetAll() } catch (e2) {}
    authStore.token = ''
    authStore.isAdmin = false
    authStore.isSuperAdmin = false
    authStore.needLogin = true
  }
}

onUnmounted(() => {
  // 清理实时连接和事件监听，防止内存泄漏
  disconnectSSE()
  disconnectWS()
  window.removeEventListener('pageshow', onPageShow)
  window.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('storage', onStorageChange)
})
</script>
