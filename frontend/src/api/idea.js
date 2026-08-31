import { http } from './index'

// ========== 金点子 API ==========

// 金点子列表（走 /api/ideas/list 返回 {ideas: {voting:[...]}} 包装格式）
export function getIdeas() {
  return http.get('/api/ideas/list')
}

// 提交金点子
export function createIdea(data) {
  return http.post('/api/ideas', data)
}

// 投票（点赞）
export function voteIdea(id) {
  return http.put('/api/ideas/' + id + '/vote')
}

// 献花（管理员）
export function flowerIdea(id) {
  return http.put('/api/ideas/' + id + '/flower')
}

// 献星星（管理员）
export function toggleFirework(iid) {
  return http.put('/api/ideas/' + iid + '/firework')
}

// 审核金点子（管理员）
export function updateIdeaStatus(id, data) {
  return http.put('/api/ideas/' + id + '/status', data)
}

// 删除金点子（管理员）
export function deleteIdea(id) {
  return http.del('/api/ideas/' + id)
}

// 清除单条金点子审核记录（管理员，仅清除审核标记，不删除内容）
export function clearIdeaReview(iid) {
  return http.put('/api/ideas/' + iid + '/clear-review')
}

// 一键清除所有已驳回金点子审核记录（管理员）
export function clearAllIdeaReviews() {
  return http.post('/api/ideas/clear-rejected')
}
