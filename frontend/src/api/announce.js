import { http } from './index'

// ========== 公告 API ==========

// 公告列表（走 /api/announcements/list 返回 {announcements: [...]} 包装格式）
export function getAnnouncements() {
  return http.get('/api/announcements/list')
}

// 创建公告（管理员）
export function createAnnouncement(data) {
  return http.post('/api/announcements', data)
}

// 更新公告（管理员）
export function updateAnnouncement(id, data) {
  return http.put('/api/announcements/' + id, data)
}

// 删除公告（管理员）
export function deleteAnnouncement(id) {
  return http.del('/api/announcements/' + id)
}
