import { http } from './index'

// ========== 私信 API ==========

// 私信列表（走 /api/messages/list 返回 {messages: [...]} 包装格式）
export function getMessages() {
  return http.get('/api/messages/list')
}

// 发送私信
export function createMessage(data) {
  return http.post('/api/messages', data)
}

// 标记会话已读
export function markConversationRead(conversationId) {
  return http.put('/api/messages/' + conversationId + '/read')
}

// 删除私信（管理员）
export function deleteMessage(id) {
  return http.del('/api/messages/' + id)
}

// ========== 实时聊天 API ==========

// 获取会话聊天记录（返回 { messages: [...] }）
export function getChatHistory(conversationId) {
  return http.get('/api/messages/' + conversationId + '/chat')
}

// 发送聊天消息（HTTP 兜底，WebSocket 不可用时使用）
export function sendChatMessage(conversationId, data) {
  return http.post('/api/messages/' + conversationId + '/chat', data)
}
