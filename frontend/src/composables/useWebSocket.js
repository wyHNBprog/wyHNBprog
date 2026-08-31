import { ref } from 'vue'
import { getToken, buildWsUrl } from '@/api/index'

// ========== WebSocket 实时通信 composable（单例）==========
// 管理 WebSocket 连接、自动重连、事件订阅、房间加入/离开

// 模块级单例状态（所有调用 useWebSocket() 的组件共享同一连接）
let ws = null
let listeners = {} // { eventType: [handler, ...] }
let reconnectTimer = null
let reconnectAttempts = 0
let manuallyClosed = false
let joinedRooms = new Set() // 已加入的房间，重连后自动重新加入

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY = 3000

// 响应式连接状态（模块级 ref，跨组件共享）
const connected = ref(false)

// 连接 WebSocket
function connect() {
  // 已连接或正在连接中，不重复连接
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }
  // 清除待重连定时器
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  manuallyClosed = false
  reconnectAttempts = 0

  // 无 token 时不连接（等待登录完成）
  if (!getToken()) {
    return
  }

  try {
    ws = new WebSocket(buildWsUrl())
  } catch (e) {
    console.error('[WS] 连接失败：', e)
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    connected.value = true
    reconnectAttempts = 0
    // 重连后自动重新加入所有房间
    joinedRooms.forEach((roomId) => {
      try {
        ws.send(JSON.stringify({ event: 'join_chat', data: { conversationId: roomId } }))
      } catch (e) {}
    })
  }

  ws.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data)
      if (!parsed || typeof parsed !== 'object') return

      // 兼容两种协议格式：
      // 1. { type, ...payload }  —— 旧格式，直接按 type 分发
      // 2. { event, data }       —— 后端格式，按 event 分发，将 data 展开传给监听器
      let type = parsed.type || parsed.event
      if (!type) return
      // 防止原型污染
      if (type === '__proto__' || type === 'constructor' || type === 'prototype') return

      // 对 { event, data } 格式：将内层 data 展开后传给监听器
      let dispatchData = parsed
      if (parsed.event && parsed.data) {
        dispatchData = { ...parsed.data, event: parsed.event }
      }

      if (listeners[type] && Array.isArray(listeners[type])) {
        listeners[type].forEach((fn) => {
          try { fn(dispatchData) } catch (e) { console.error('[WS] 事件处理异常：', e) }
        })
      }
    } catch (e) {
      console.error('[WS] 消息解析失败：', e)
    }
  }

  ws.onclose = () => {
    connected.value = false
    if (!manuallyClosed) {
      scheduleReconnect()
    }
  }

  ws.onerror = () => {
    connected.value = false
  }
}

// 断开连接（主动关闭，不触发重连）
function disconnect() {
  manuallyClosed = true
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.onclose = null
    ws.onerror = null
    try {
      ws.close()
    } catch (e) {}
    ws = null
  }
  connected.value = false
}

// 安排重连（指数退避，达到上限后改为固定长间隔持续兜底重连）
function scheduleReconnect() {
  if (manuallyClosed) return
  if (reconnectTimer) return
  reconnectAttempts++
  let delay
  if (reconnectAttempts <= MAX_RECONNECT_ATTEMPTS) {
    delay = RECONNECT_BASE_DELAY * reconnectAttempts
  } else {
    // 达到上限后不再停摆：以固定 30s 持续兜底重连，网络恢复后自动续上
    delay = 30000
  }
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    connect()
  }, delay)
}

// 订阅事件
function on(event, handler) {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(handler)
  // 返回取消订阅函数
  return () => {
    off(event, handler)
  }
}

// 取消订阅事件
function off(event, handler) {
  if (!listeners[event]) return
  if (handler) {
    listeners[event] = listeners[event].filter((fn) => fn !== handler)
  } else {
    delete listeners[event]
  }
}

// 发送消息（返回是否成功）
function send(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send(JSON.stringify(data))
      return true
    } catch (e) {
      console.error('[WS] 发送失败：', e)
      return false
    }
  }
  return false
}

// 加入房间（重连后会自动重新加入）
// 后端 WebSocket 使用 event/data 协议，join_chat 事件加入会话房间
function joinRoom(roomId) {
  joinedRooms.add(roomId)
  return send({ event: 'join_chat', data: { conversationId: roomId } })
}

// 离开房间（后端无 leave 事件，仅本地清理）
function leaveRoom(roomId) {
  joinedRooms.delete(roomId)
}

export function useWebSocket() {
  return {
    connected,
    connect,
    disconnect,
    on,
    off,
    send,
    joinRoom,
    leaveRoom
  }
}
