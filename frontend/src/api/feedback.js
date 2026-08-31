import { http } from './index'

// ========== 反馈 API ==========

// 反馈列表（走 /api/feedbacks/list 返回 {feedbacks: [...]} 包装格式）
export function getFeedbacks() {
  return http.get('/api/feedbacks/list')
}

// 提交反馈
export function createFeedback(data) {
  return http.post('/api/feedbacks', data)
}

// 管理员回复反馈
export function replyFeedback(id, data) {
  return http.put('/api/feedbacks/' + id + '/reply', data)
}
