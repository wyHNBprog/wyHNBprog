import { ref } from 'vue'
import { getToken, buildSseUrl } from '@/api/index'
import { useDataStore } from '@/stores/data'
import { useRealtimeStore } from '@/stores/realtime'

// ========== SSE（Server-Sent Events）实时推送 composable（单例）==========
// 替代 60 秒轮询：服务端有新数据时主动推送，前端收到后刷新对应 store
// 后端推送命名事件（event: unread_count / notification / review_update / chat_message / heartbeat），
// 前端使用 addEventListener 监听具体事件名，onmessage 仅作为兜底。

// 模块级单例状态
let eventSource = null
let reconnectTimer = null
let reconnectAttempts = 0
let manuallyClosed = false

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY = 5000

// 响应式连接状态
const connected = ref(false)

// 需要监听的命名事件列表
const NAMED_EVENTS = ['unread_count', 'notification', 'chat_message', 'review_update', 'heartbeat']

// 连接 SSE
function connect() {
  // 已连接则不重复连接
  if (eventSource) {
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
    eventSource = new EventSource(buildSseUrl())
  } catch (e) {
    console.error('[SSE] 连接失败：', e)
    scheduleReconnect()
    return
  }

  eventSource.onopen = () => {
    connected.value = true
    reconnectAttempts = 0
  }

  // ===== 使用 addEventListener 监听命名事件 =====
  // 后端推送 event: <name> 格式的命名事件，onmessage 只能收到无事件名或 event: message 的消息，
  // 因此必须用 addEventListener 才能收到 unread_count / notification / review_update / chat_message 等事件。

  // 未读计数事件
  eventSource.addEventListener('unread_count', (event) => {
    try {
      const data = JSON.parse(event.data)
      const realtimeStore = useRealtimeStore()
      if (typeof data.count === 'number') {
        realtimeStore.updateUnreadCount(data.count)
      }
    } catch (e) {
      // 非 JSON 数据，忽略
    }
  })

  // 通知事件
  eventSource.addEventListener('notification', (event) => {
    try {
      const data = JSON.parse(event.data)
      const realtimeStore = useRealtimeStore()
      // 更新通知列表（去重后置顶），内部已更新未读计数和分类红点
      realtimeStore.handleNotification(data)
    } catch (e) {
      // 非 JSON 数据，忽略
    }
  })

  // 审核更新事件
  eventSource.addEventListener('review_update', (event) => {
    // 收到审核更新事件即刷新全量数据（无需解析 data 内容）
    const realtimeStore = useRealtimeStore()
    realtimeStore.handleReviewUpdate()
  })

  // 聊天消息事件
  eventSource.addEventListener('chat_message', (event) => {
    try {
      const data = JSON.parse(event.data)
      const realtimeStore = useRealtimeStore()
      realtimeStore.handleChatMessage(data)
    } catch (e) {
      // 非 JSON 数据，忽略
    }
  })

  // 心跳事件（仅用于保活，无需处理数据）
  eventSource.addEventListener('heartbeat', () => {
    // 心跳包，无需处理
  })

  // ===== onmessage 兜底：收到无事件名或 event: message 的消息 =====
  // 注意：onmessage 可能收到通知类型或数据变更类型的事件，
  // 不能用 validateNotification（要求 id 为字符串）做前置检查，
  // 否则数据变更事件（可能不含 id 或 id 为数字）会被误拦截，导致 handleEvent 永不执行。
  // 直接调用 handleEvent，由其内部按 type 分发处理。
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleEvent(data)
    } catch (e) {
      // 非 JSON 消息（如心跳 ping），忽略
    }
  }

  eventSource.onerror = () => {
    connected.value = false
    // EventSource 出错后会自动重连，但浏览器内置重连不可控，
    // 这里主动关闭后用自定义逻辑重连，以便控制重试次数
    closeSource()
    scheduleReconnect()
  }
}

// 主动关闭 EventSource（不触发重连）
function closeSource() {
  if (eventSource) {
    try {
      eventSource.close()
    } catch (e) {}
    eventSource = null
  }
}

// 断开连接（主动关闭，不触发重连）
function disconnect() {
  manuallyClosed = true
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  closeSource()
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

// 验证 SSE 推送数据结构
function validateNotification(data) {
  if (!data || typeof data !== 'object') return false
  // id 必须是非空字符串
  if (!data.id || typeof data.id !== 'string') return false
  // 防止原型污染：id 不能是危险键
  if (data.id === '__proto__' || data.id === 'constructor' || data.id === 'prototype') return false
  // type 如果存在必须是字符串
  if (data.type != null && typeof data.type !== 'string') return false
  // 防止原型污染：type 不能是危险键
  if (data.type === '__proto__' || data.type === 'constructor' || data.type === 'prototype') return false
  return true
}

// 防抖定时器：连续多个数据变更事件合并为一次 loadAll 刷新
let _dataUpdateTimer = null

// 处理服务端推送事件：按事件类型刷新对应数据
function handleEvent(data) {
  if (!data || !data.type) return
  switch (data.type) {
    case 'data_update':
    case 'new_voice':
    case 'voice_approved':
    case 'voice_rejected':
    case 'new_idea':
    case 'idea_voted':
    case 'idea_status_changed':
    case 'new_feedback':
    case 'feedback_replied':
    case 'new_message':
    case 'message_replied':
    case 'new_announcement':
    case 'new_notification':
    case 'notification_read':
      // 收到任意数据变更事件，防抖 500ms 后刷新全量数据，
      // 避免连续多个 SSE 事件触发多次 loadAll
      if (_dataUpdateTimer) clearTimeout(_dataUpdateTimer)
      _dataUpdateTimer = setTimeout(() => {
        const dataStore = useDataStore()
        dataStore.loadAll(true).catch(() => {})
        _dataUpdateTimer = null
      }, 500)
      break
    default:
      break
  }
}

export function useSSE() {
  return {
    connected,
    connect,
    disconnect
  }
}
