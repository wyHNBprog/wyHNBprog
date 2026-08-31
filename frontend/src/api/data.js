import { http } from './index'

// ========== 全量数据 API ==========

// 获取全量数据（voices/ideas/feedbacks/messages/announcements/notifications）
export function getAllData() {
  return http.get('/api/data')
}
