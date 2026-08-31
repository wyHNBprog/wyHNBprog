import { http } from './index'

// ========== 管理员 API ==========

// 数据看板统计
export function getAdminStats() {
  return http.get('/api/admin/stats')
}

// 用户列表（超管）
export function getAdminUsers() {
  return http.get('/api/admin/users')
}

// 修改用户角色（超管）
export function updateUserRole(uid, data) {
  return http.put('/api/admin/users/' + uid + '/role', data)
}

// 获取企业微信通讯录成员（超管）
export function getWecomMembers() {
  return http.get('/api/admin/wecom-members')
}
