import axios from 'axios'

// ========== axios 实例 ==========
// 自动附加 JWT、401 处理、响应解包（兼容 {code,message,data} 包装）

const TOKEN_KEY = 'voicehub_token'

// 401 回调（由 auth store 注册，避免循环依赖）
let _onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  _onUnauthorized = fn
}

// 401 防抖：同一时间窗内多个并发 401 只触发一次回调，避免重复重连/计数
let _unauthorizedLocked = false
let _unauthorizedTimer = null
function triggerUnauthorized() {
  if (_unauthorizedLocked) return
  _unauthorizedLocked = true
  if (_unauthorizedTimer) clearTimeout(_unauthorizedTimer)
  // 短暂锁定时长，覆盖并发批量请求的 401 洪峰
  _unauthorizedTimer = setTimeout(() => {
    _unauthorizedLocked = false
    _unauthorizedTimer = null
  }, 300)
  if (_onUnauthorized) {
    _onUnauthorized()
  }
}

// 读取本地 token
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch (e) {
    return ''
  }
}

// 保存 token
export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch (e) {}
}

// 清除 token
export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch (e) {}
}

const request = axios.create({
  baseURL: '',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动附加 Authorization 头
request.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers['Authorization'] = 'Bearer ' + token
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：401 处理 + 响应解包
request.interceptors.response.use(
  (response) => {
    let data = response.data
    // 兼容包装式响应 { code, message, data }：自动解包
    if (data && typeof data === 'object' && 'code' in data && 'data' in data && (data.code === 200 || data.code === 0)) {
      data = data.data
    }
    if (data && data.error) {
      return Promise.reject(new Error(data.error))
    }
    return data
  },
  (error) => {
    const res = error.response
    // 401 时清除过期 token，触发重新登录（防抖收敛并发 401）
    if (res && res.status === 401) {
      clearToken()
      triggerUnauthorized()
    }
    // 提取错误信息
    let errMsg = '请求失败'
    if (res) {
      const d = res.data
      errMsg = (d && (d.error || d.message)) || '请求失败 (' + res.status + ')'
    } else if (error.message) {
      errMsg = error.message
    }
    const err = new Error(errMsg)
    err.status = res ? res.status : 0
    // 透传后端响应数据（便于 409 并发冲突处理）
    if (res && res.data) err.data = res.data
    return Promise.reject(err)
  }
)

// ========== 通用请求方法 ==========
export const http = {
  get: (url, config) => request.get(url, config),
  post: (url, data, config) => request.post(url, data, config),
  put: (url, data, config) => request.put(url, data, config),
  del: (url, config) => request.delete(url, config)
}

// ========== 实时通信 URL 构建 ==========
// EventSource / WebSocket 均无法设置自定义请求头，
// 因此 JWT token 通过 query 参数传递（后端需支持从 query 读取 token）。

// 构建 SSE 连接 URL
export function buildSseUrl(token) {
  const t = token || getToken()
  // 开发环境通过 vite proxy 代理到后端
  const base = import.meta.env.DEV ? '' : window.location.origin
  const url = base + '/api/sse/stream'
  return t ? url + '?token=' + encodeURIComponent(t) : url
}

// 构建 WebSocket 连接 URL
export function buildWsUrl(token) {
  const t = token || getToken()
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 开发环境通过 vite proxy 代理到后端（使用相对路径，与 SSE 一致）
  const host = import.meta.env.DEV ? window.location.host : window.location.host
  const url = proto + '//' + host + '/api/ws'
  return t ? url + '?token=' + encodeURIComponent(t) : url
}

export default request
