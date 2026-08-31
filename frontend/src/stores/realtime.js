import { defineStore } from 'pinia'
import { ref } from 'vue'
// 静态导入 data store / chat store，但在函数内部调用 useXxxStore()，
// 以避免循环依赖与 Pinia 初始化顺序问题。
import { useDataStore } from '@/stores/data'
import { useChatStore } from '@/stores/chat'

// 通知类型 -> 分类映射（与后端 NOTIFICATION_TYPE_CATEGORY 保持一致）
const NOTIF_TYPE_CATEGORY = {
  voice_approved: 'voice',
  voice_rejected: 'voice',
  idea_approved: 'idea',
  idea_rejected: 'idea',
  message_replied: 'message',
  message_received: 'message',
  feedback_replied: 'feedback',
  comment_approved: 'comment',
  comment_rejected: 'comment',
  system: 'system',
}

// 防抖定时器：审核更新事件防抖，避免连续审核时频繁刷新
let _reviewUpdateTimer = null

export const useRealtimeStore = defineStore('realtime', () => {
  const unreadCount = ref(0)
  const connected = ref(false)

  // 分类未读计数（用于"我的留言""我的金点子"等入口红点）
  const unreadByType = ref({ voice: 0, idea: 0, comment: 0, message: 0, feedback: 0, system: 0 })

  function updateUnreadCount(count) {
    unreadCount.value = count
  }

  // 根据本地通知列表计算分类未读数（无需额外 API 请求）
  function updateUnreadByType() {
    const dataStore = useDataStore()
    const result = { voice: 0, idea: 0, comment: 0, message: 0, feedback: 0, system: 0 }
    dataStore.notifications.forEach((n) => {
      if (!n.read) {
        const cat = NOTIF_TYPE_CATEGORY[n.type] || 'system'
        result[cat] = (result[cat] || 0) + 1
      }
    })
    unreadByType.value = result
    // 同步总数
    unreadCount.value = result.voice + result.idea + result.comment + result.message + result.feedback + result.system
  }

  function handleNotification(notification) {
    const dataStore = useDataStore()
    // 先 normalize 通知数据（映射 is_read -> read 等），避免未读计数虚高
    const normalized = dataStore.normalizeNotification(notification)
    if (normalized && normalized.id) {
      // 去重后置顶，保持最新通知在前
      dataStore.notifications = [
        normalized,
        ...dataStore.notifications.filter((n) => n.id !== normalized.id)
      ]
      // 更新未读数（仅当通知未读时才计数）
      if (!normalized.read) {
        unreadCount.value++
      }
    }
    // 更新分类红点
    updateUnreadByType()
  }

  function handleReviewUpdate() {
    // 防抖 500ms：连续审核多条内容时只刷新一次，避免频繁请求
    if (_reviewUpdateTimer) clearTimeout(_reviewUpdateTimer)
    _reviewUpdateTimer = setTimeout(() => {
      const dataStore = useDataStore()
      dataStore.loadAll(true).catch(() => {})
      _reviewUpdateTimer = null
    }, 500)
  }

  function handleChatMessage(message) {
    // 转发给 chat store 处理
    const chatStore = useChatStore()
    chatStore.handleIncomingMessage(message)
  }

  function setConnected(val) {
    connected.value = val
  }

  // ========== 重置所有状态（登出/401 时调用）==========
  function resetAll() {
    unreadCount.value = 0
    connected.value = false
    unreadByType.value = { voice: 0, idea: 0, comment: 0, message: 0, feedback: 0, system: 0 }
  }

  return {
    unreadCount,
    connected,
    unreadByType,
    updateUnreadCount,
    updateUnreadByType,
    handleNotification,
    handleReviewUpdate,
    handleChatMessage,
    setConnected,
    resetAll
  }
})
