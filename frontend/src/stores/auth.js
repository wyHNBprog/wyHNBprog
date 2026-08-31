import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, logout as apiLogout, getAdminStatus, getAuthConfig, getWecomLoginUrl } from '@/api/auth'
import { getToken, setToken, clearToken, setUnauthorizedHandler } from '@/api/index'
import { useDataStore } from '@/stores/data'
import { useChatStore } from '@/stores/chat'
import { useRealtimeStore } from '@/stores/realtime'
import { useUiStore } from '@/stores/ui'

// 断开实时连接（SSE/WebSocket），避免 token 失效后旧连接悬空
// 动态加载 composable，避免与 App.vue 的循环依赖
function cleanupRealtime() {
  try {
    import('@/composables/useSSE').then((m) => m.useSSE().disconnect()).catch(() => {})
    import('@/composables/useWebSocket').then((m) => m.useWebSocket().disconnect()).catch(() => {})
  } catch (e) {}
}

// ========== 认证状态 store ==========
// 仅支持企业微信 OAuth 登录，管理员由数据库 is_admin 字段指定

export const useAuthStore = defineStore('auth', () => {
  // 当前用户对象
  const user = ref({
    nickname: '未登录',
    department: '',
    role: 'user',
    avatar: '',
    is_logged_in: false,
    id: null,
    points: 0
  })

  // token
  const token = ref(getToken())

  // 是否管理员
  const isAdmin = ref(false)

  // 是否超级管理员
  const isSuperAdmin = ref(false)

  // 是否已初始化
  const initialized = ref(false)

  // 是否正在登录中
  const loading = ref(false)

  // 企微是否启用
  const wecomEnabled = ref(false)

  // 是否需要显示登录页（无有效 token 时）
  const needLogin = ref(false)

  // 计算属性：是否已登录
  const isLoggedIn = computed(() => !!token.value)

  // ========== 注册 401 处理器 ==========
  setUnauthorizedHandler(() => {
    clearToken()
    token.value = ''
    isAdmin.value = false
    isSuperAdmin.value = false
    try { useDataStore().resetAll() } catch (e) {}
    try { useChatStore().resetAll() } catch (e) {}
    try { useRealtimeStore().resetAll() } catch (e) {}
    // 断开实时连接并清理，避免旧 token 连接悬空继续推事件
    cleanupRealtime()
    // 401 说明 token 已失效，直接进入登录态（api/index.js 已做并发防抖）
    if (!loading.value) {
      needLogin.value = true
    }
  })

  // ========== 初始化认证：检查 token → 有效则登录，无效则显示登录页 ==========
  let _initPromise = null
  async function initAuth(forceRelogin = false) {
    // 防止并发调用（路由守卫 + App.vue onMounted 可能同时触发）
    if (!forceRelogin && _initPromise) return _initPromise
    _initPromise = _doInitAuth(forceRelogin)
    try {
      return await _initPromise
    } finally {
      _initPromise = null
    }
  }

  async function _doInitAuth(forceRelogin = false) {
    loading.value = true
    // 清理旧版残留的管理员 token（已废弃双认证机制）
    try { localStorage.removeItem('voicehub_admin_token') } catch (e) {}
    try {
      // 1. 获取认证配置
      try {
        const config = await getAuthConfig()
        wecomEnabled.value = !!(config && config.wecom_enabled)
      } catch (e) {
        wecomEnabled.value = false
      }

      // 2. 有 token 时验证有效性
      if (getToken() && !forceRelogin) {
        try {
          const res = await getMe()
          if (res && res.user) {
            setUserFromApi(res.user)
            // 如果 setUserFromApi 未能确定管理员身份，调用 checkAdminStatus 兜底
            if (!isAdmin.value && !isSuperAdmin.value) {
              await checkAdminStatus()
            }
            initialized.value = true
            needLogin.value = false
            return
          }
          // getMe 返回 {user: null}（HTTP 200）：token 无效但未抛异常，需手动清除
          clearToken()
          token.value = ''
        } catch (e) {
          // token 无效，清除
          clearToken()
          token.value = ''
        }
      }

      // 3. 无有效 token：显示登录页
      needLogin.value = true
      initialized.value = true
    } catch (e) {
      console.error('认证初始化失败：', e)
      initialized.value = true
      needLogin.value = true
    } finally {
      loading.value = false
    }
  }

  // ========== 企微登录：获取授权链接并跳转 ==========
  async function wecomLogin() {
    const ui = useUiStore()
    try {
      const res = await getWecomLoginUrl()
      if (res && res.url) {
        window.location.href = res.url
      } else {
        ui.showToast('获取企微授权链接失败')
      }
    } catch (e) {
      console.error('企微登录失败：', e)
      const msg = (e && e.message) || '企微登录失败'
      ui.showToast(msg)
    }
  }

  // ========== 企微回调：URL 中携带 token 时处理 ==========
  async function handleWecomCallback(cbToken) {
    if (!cbToken) return false
    loading.value = true
    try {
      setToken(cbToken)
      token.value = cbToken
      const res = await getMe()
      if (res && res.user) {
        setUserFromApi(res.user)
        initialized.value = true
        needLogin.value = false
        return true
      }
      // getMe 返回 {user: null}：回调 token 无效，清除并显示登录页
      clearToken()
      token.value = ''
      needLogin.value = true
      initialized.value = true
      return false
    } catch (e) {
      console.error('企微回调处理失败：', e)
      clearToken()
      token.value = ''
      needLogin.value = true
      initialized.value = true
      return false
    } finally {
      loading.value = false
    }
  }

  // ========== 设置用户信息（从 API 响应）==========
  function setUserFromApi(u) {
    const beRole = u.role
    user.value = {
      nickname: u.nickname || '用户',
      department: u.department || '',
      role: beRole || (u.is_admin ? 'admin' : 'employee'),
      is_super_admin: !!(u.is_super_admin || beRole === 'super_admin'),
      avatar: u.avatar || '',
      is_logged_in: !!u.is_logged_in,
      id: u.id,
      points: typeof u.points === 'number' ? u.points : 0
    }
    // 兼容后端返回 camelCase(isAdmin) 或 snake_case(is_admin)，并从 role 推导
    const adminFlag = u.isAdmin != null ? u.isAdmin : u.is_admin
    isAdmin.value = !!adminFlag || beRole === 'admin' || beRole === 'super_admin'
    isSuperAdmin.value = !!(u.is_super_admin || beRole === 'super_admin')
  }

  // ========== 检查管理员状态 ==========
  async function checkAdminStatus() {
    try {
      const res = await getAdminStatus()
      if (res && res.isAdmin) {
        isAdmin.value = true
        isSuperAdmin.value = !!res.isSuperAdmin
        user.value.is_super_admin = !!res.isSuperAdmin
        if (res.isSuperAdmin) {
          user.value.role = 'super_admin'
        }
      } else {
        isAdmin.value = false
        isSuperAdmin.value = false
        user.value.is_super_admin = false
      }
    } catch (e) {
      isAdmin.value = false
      isSuperAdmin.value = false
    }
  }

  // ========== 退出登录 ==========
  async function logoutAction() {
    try {
      await apiLogout()
    } catch (e) {}
    clearToken()
    token.value = ''
    isAdmin.value = false
    isSuperAdmin.value = false
    try { useDataStore().resetAll() } catch (e) {}
    try { useChatStore().resetAll() } catch (e) {}
    try { useRealtimeStore().resetAll() } catch (e) {}
    cleanupRealtime()
    needLogin.value = true
  }

  return {
    user,
    token,
    isAdmin,
    isSuperAdmin,
    initialized,
    loading,
    isLoggedIn,
    wecomEnabled,
    needLogin,
    initAuth,
    wecomLogin,
    handleWecomCallback,
    logout: logoutAction,
    checkAdminStatus,
    setUserFromApi
  }
})
