import { http } from './index'

// ========== 认证 API ==========

// 获取认证配置（企微是否启用）
export function getAuthConfig() {
  return http.get('/api/auth/config')
}

// 获取企业微信授权链接
export function getWecomLoginUrl() {
  return http.get('/api/wecom/login-url')
}

// 获取当前登录用户
export function getMe() {
  return http.get('/api/auth/me')
}

// 退出登录
export function logout() {
  return http.post('/api/auth/logout')
}

// 获取管理员状态
export function getAdminStatus() {
  return http.get('/api/admin/status')
}
