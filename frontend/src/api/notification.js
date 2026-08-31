import { http } from './index'

// ========== 通知 API ==========

// 通知列表（走 /api/notifications/list 返回 {notifications: [...]} 包装格式）
export function getNotifications() {
  return http.get('/api/notifications/list')
}

// 未读通知数量
export function getUnreadCount() {
  return http.get('/api/notifications/unread-count')
}

// 标记通知为已读（不删除，仅更新 is_read）
export function markNotificationRead(id) {
  return http.put('/api/notifications/' + id + '/read')
}

// 全部标记已读
export function markAllRead() {
  return http.put('/api/notifications/read-all')
}

// 按分类标记通知已读（type: 'voice'|'idea'|'comment'|'message'|'feedback'|'system'）
export function readByType(type) {
  return http.put('/api/notifications/read-by-type', { type: type })
}
