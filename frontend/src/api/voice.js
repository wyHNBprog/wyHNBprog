import { http } from './index'

// ========== 留言 API ==========

// 留言列表（走 /api/voices/list 返回 {voices: [...]} 包装格式）
export function getVoices() {
  return http.get('/api/voices/list')
}

// 发布留言
export function createVoice(data) {
  return http.post('/api/voices', data)
}

// 点赞留言
export function likeVoice(id) {
  return http.put('/api/voices/' + id + '/like')
}

// 审核留言（管理员）
export function updateVoiceStatus(id, data) {
  return http.put('/api/voices/' + id + '/status', data)
}

// 删除留言（管理员）
export function deleteVoice(id) {
  return http.del('/api/voices/' + id)
}

// 发布评论
export function createComment(voiceId, data) {
  return http.post('/api/voices/' + voiceId + '/comments', data)
}

// 评论点赞
export function likeComment(voiceId, commentId) {
  return http.put('/api/voices/' + voiceId + '/comments/' + commentId + '/like')
}

// 审核评论（管理员）
export function updateCommentStatus(voiceId, commentId, data) {
  return http.put('/api/voices/' + voiceId + '/comments/' + commentId + '/status', data)
}

// 删除评论（管理员）
export function deleteComment(voiceId, commentId) {
  return http.del('/api/voices/' + voiceId + '/comments/' + commentId)
}

// 清除单条留言审核记录（管理员，仅清除审核标记，不删除内容）
export function clearVoiceReview(vid) {
  return http.put('/api/voices/' + vid + '/clear-review')
}

// 一键清除所有已驳回留言审核记录（管理员）
export function clearAllVoiceReviews() {
  return http.post('/api/voices/clear-rejected')
}

// 清除单条评论审核记录（管理员）
export function clearCommentReview(vid, cid) {
  return http.put('/api/voices/' + vid + '/comments/' + cid + '/clear-review')
}

// 一键清除所有已驳回评论审核记录（管理员）
export function clearAllCommentReviews() {
  return http.post('/api/comments/clear-rejected')
}
