import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAllData } from '@/api/data'
import { getVoices } from '@/api/voice'
import { getIdeas } from '@/api/idea'
import { getFeedbacks } from '@/api/feedback'
import { getMessages } from '@/api/message'
import { getAnnouncements } from '@/api/announce'
import { getNotifications } from '@/api/notification'
import { fmtTime } from '@/utils/format'
import { ANON_NAME, LOAD_CACHE_MS } from '@/utils/constants'

// ========== 数据 normalize（兼容 snake_case 和 camelCase）==========
function normalizeVoice(v) {
  if (!v) return null
  return {
    id: v.id,
    content: v.content,
    anonName: v.anonName || v.anon_name || ANON_NAME,
    isAnonymous: v.isAnonymous != null ? v.isAnonymous : v.is_anonymous != null ? v.is_anonymous : true,
    tags: v.tags || [],
    timeText: v.timeText || fmtTime(v.created_at),
    likeCount: v.likeCount != null ? v.likeCount : v.like_count || 0,
    isLiked: !!(v.isLiked || v.is_liked),
    isMine: !!(v.isMine || v.is_mine),
    status: v.status || 'approved',
    rejectReason: v.rejectReason || v.reject_reason || '',
    reviewCleared: !!(v.reviewCleared || v.review_cleared),
    commentCount: v.commentCount != null ? v.commentCount : v.comment_count || 0,
    comments: (v.comments || []).map(normalizeComment).filter(Boolean),
    realName: v.realName || v.real_name || null
  }
}

function normalizeComment(c) {
  if (!c) return null
  return {
    id: c.id,
    content: c.content,
    anonName: c.anonName || c.anon_name || ANON_NAME,
    timeText: c.timeText || fmtTime(c.created_at),
    status: c.status || 'approved',
    rejectReason: c.rejectReason || c.reject_reason || '',
    reviewCleared: !!(c.reviewCleared || c.review_cleared),
    realName: c.realName || c.real_name || null,
    isMine: !!(c.isMine || c.is_mine),
    likeCount: c.likeCount != null ? c.likeCount : c.like_count || 0,
    isLiked: !!(c.isLiked || c.is_liked)
  }
}

function normalizeIdea(i) {
  if (!i) return null
  const voteCount = i.voteCount != null ? i.voteCount : i.vote_count || 0
  return {
    id: i.id,
    title: i.title,
    desc: i.desc || i.description || '',
    category: i.category || '其他',
    anonName: i.anonName || i.anon_name || ANON_NAME,
    realName: i.realName || i.real_name || null,
    isAnonymous: i.isAnonymous != null ? i.isAnonymous : i.is_anonymous != null ? i.is_anonymous : true,
    timeText: i.timeText || fmtTime(i.created_at),
    voteCount: voteCount,
    // 排序快照：仅在此处（数据加载时）同步，点赞时不更新此字段，避免列表位置跳动
    _sortVoteCount: voteCount,
    hasVoted: !!(i.hasVoted || i.has_voted),
    isMine: !!(i.isMine || i.is_mine),
    status: i.status || 'voting',
    hasFlower: !!(i.hasFlower || i.has_flower),
    flowerCount: i.flowerCount || i.flower_count || 0,
    hasFirework: !!(i.hasFirework || i.has_firework),
    fireworkCount: i.fireworkCount || i.firework_count || 0,
    likes: i.likes || 0,
    rejectReason: i.rejectReason || i.reject_reason || '',
    reviewCleared: !!(i.reviewCleared || i.review_cleared)
  }
}

function normalizeFeedback(f) {
  if (!f) return null
  return {
    id: f.id,
    category: f.category || f.type || '其他',
    content: f.content,
    anonName: f.anonName || f.anon_name || ANON_NAME,
    timeText: f.timeText || fmtTime(f.created_at),
    status: f.status || 'pending',
    reply: f.reply || null,
    replyTime: f.replyTime || f.reply_time || null
  }
}

function normalizeMessage(m) {
  if (!m) return null
  return {
    id: m.id,
    content: m.content,
    anonName: m.anonName || m.anon_name || ANON_NAME,
    realName: m.realName || m.real_name || null,
    timeText: m.timeText || fmtTime(m.created_at),
    status: m.status || 'unread',
    replies: m.replies || (m.admin_reply ? [{ content: m.admin_reply, timeText: fmtTime(m.reply_time) }] : [])
  }
}

function normalizeAnnouncement(a) {
  if (!a) return null
  return {
    id: a.id,
    title: a.title,
    content: a.content,
    pinned: !!(a.pinned || a.is_pinned),
    timeText: a.timeText || fmtTime(a.created_at)
  }
}

function normalizeNotification(n) {
  if (!n) return null
  return {
    id: n.id,
    type: n.type || 'system',
    text: n.text,
    timeText: n.timeText || fmtTime(n.created_at),
    read: !!(n.read || n.is_read)
  }
}

// ========== 数据状态 store ==========
export const useDataStore = defineStore('data', () => {
  const voices = ref([])
  const ideas = ref({ voting: [], adopted: [], completed: [] })
  const feedbacks = ref([])
  const messages = ref([])
  const announcements = ref([])
  const notifications = ref([])

  let _lastLoadTime = 0
  // in-flight Promise 去重：避免并发 loadAll 请求互相覆盖（审核页与 App.vue 同时触发）
  let _loadAllPromise = null

  // ========== 加载全量数据（30 秒缓存，force 强制刷新）==========
  async function loadAll(force = false) {
    const now = Date.now()
    // 非强制且有缓存：直接返回
    if (!force && _lastLoadTime && now - _lastLoadTime < LOAD_CACHE_MS) {
      return
    }
    // 已有在飞请求：非 force 时复用，force 时等待在飞完成后再强制刷新
    if (_loadAllPromise) {
      if (!force) {
        return _loadAllPromise
      }
      // force=true 时等待在飞请求完成，再发起强制刷新拿最新数据
      try { await _loadAllPromise } catch (e) {}
    }
    _loadAllPromise = (async () => {
      try {
        const d = await getAllData()
        if (!d) return
        _lastLoadTime = Date.now()

        // 记录旧数据的点赞/投票/献花/烟花状态（避免详情页/列表页之间跳转时丢失，SSE 刷新时保留乐观更新）
        const oldLiked = {}
        const oldVoted = {}
        const oldFlowered = {}
        const oldFirework = {}
        voices.value.forEach((v) => {
          oldLiked[v.id] = v.isLiked
        })
        Object.values(ideas.value || {}).forEach((arr) => {
          arr.forEach((i) => {
            oldVoted[i.id] = i.hasVoted
            oldFlowered[i.id] = i.hasFlower
            oldFirework[i.id] = i.hasFirework
          })
        })

        voices.value = (d.voices || []).map((raw) => {
          const n = normalizeVoice(raw)
          if (n && oldLiked[n.id] != null) n.isLiked = oldLiked[n.id]
          return n
        }).filter(Boolean)

        ideas.value = {
          voting: (d.ideas && d.ideas.voting ? d.ideas.voting : []).map((raw) => {
            const n = normalizeIdea(raw)
            if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
            if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
            if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
            return n
          }).filter(Boolean),
          adopted: (d.ideas && d.ideas.adopted ? d.ideas.adopted : []).map((raw) => {
            const n = normalizeIdea(raw)
            if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
            if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
            if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
            return n
          }).filter(Boolean),
          completed: (d.ideas && d.ideas.completed ? d.ideas.completed : []).map((raw) => {
            const n = normalizeIdea(raw)
            if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
            if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
            if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
            return n
          }).filter(Boolean)
        }

        feedbacks.value = (d.feedbacks || []).map(normalizeFeedback).filter(Boolean)
        messages.value = (d.messages || []).map(normalizeMessage).filter(Boolean)
        announcements.value = (d.announcements || []).map(normalizeAnnouncement).filter(Boolean).sort((a, b) => {
          return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0)
        })
        // 保留本地临时通知（id 以 n_ 开头），避免被服务器数据覆盖清空
        const localNotifs = notifications.value.filter((n) => typeof n.id === 'string' && n.id.indexOf('n_') === 0)
        notifications.value = [
          ...localNotifs,
          ...(d.notifications || []).map(normalizeNotification).filter(Boolean)
        ]
      } finally {
        _loadAllPromise = null
      }
    })()
    return _loadAllPromise
  }

  // ========== 按需加载：留言列表 ==========
  async function loadVoices() {
    const d = await getVoices()
    if (!d) return
    const oldLiked = {}
    voices.value.forEach((v) => {
      oldLiked[v.id] = v.isLiked
    })
    voices.value = (d.voices || []).map((raw) => {
      const n = normalizeVoice(raw)
      if (n && oldLiked[n.id] != null) n.isLiked = oldLiked[n.id]
      return n
    }).filter(Boolean)
  }

  // ========== 按需加载：金点子 ==========
  async function loadIdeas() {
    const d = await getIdeas()
    if (!d) return
    const oldVoted = {}
    const oldFlowered = {}
    const oldFirework = {}
    Object.values(ideas.value || {}).forEach((arr) => {
      arr.forEach((i) => {
        oldVoted[i.id] = i.hasVoted
        oldFlowered[i.id] = i.hasFlower
        oldFirework[i.id] = i.hasFirework
      })
    })
    ideas.value = {
      voting: (d.ideas && d.ideas.voting ? d.ideas.voting : []).map((raw) => {
        const n = normalizeIdea(raw)
        if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
        if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
        if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
        return n
      }).filter(Boolean),
      adopted: (d.ideas && d.ideas.adopted ? d.ideas.adopted : []).map((raw) => {
        const n = normalizeIdea(raw)
        if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
        if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
        if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
        return n
      }).filter(Boolean),
      completed: (d.ideas && d.ideas.completed ? d.ideas.completed : []).map((raw) => {
        const n = normalizeIdea(raw)
        if (n && oldVoted[n.id] != null) n.hasVoted = oldVoted[n.id]
        if (n && oldFlowered[n.id] != null) n.hasFlower = oldFlowered[n.id]
        if (n && oldFirework[n.id] != null) n.hasFirework = oldFirework[n.id]
        return n
      }).filter(Boolean)
    }
  }

  // ========== 按需加载：公告 ==========
  async function loadAnnouncements() {
    const d = await getAnnouncements()
    if (!d) return
    announcements.value = (d.announcements || []).map(normalizeAnnouncement).filter(Boolean).sort((a, b) => {
      return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0)
    })
  }

  // ========== 按需加载：反馈 ==========
  async function loadFeedbacks() {
    const d = await getFeedbacks()
    if (!d) return
    feedbacks.value = (d.feedbacks || []).map(normalizeFeedback).filter(Boolean)
  }

  // ========== 按需加载：私信 ==========
  async function loadMessages() {
    const d = await getMessages()
    if (!d) return
    messages.value = (d.messages || []).map(normalizeMessage).filter(Boolean)
  }

  // ========== 按需加载：通知 ==========
  async function loadNotifications() {
    const d = await getNotifications()
    if (!d) return
    // 保留本地临时通知（id 以 n_ 开头），避免被服务器数据覆盖清空
    const localNotifs = notifications.value.filter((n) => typeof n.id === 'string' && n.id.indexOf('n_') === 0)
    notifications.value = [
      ...localNotifs,
      ...(d.notifications || []).map(normalizeNotification).filter(Boolean)
    ]
  }

  // ========== 工具方法：查找留言 ==========
  function findVoiceById(id) {
    return voices.value.find((v) => v.id === id) || null
  }

  // ========== 工具方法：查找金点子 ==========
  function findIdeaById(id) {
    // 遍历所有分类数组，避免遗漏 pending/adopted/completed 中的 idea
    for (const key of Object.keys(ideas.value || {})) {
      const item = (ideas.value[key] || []).find((x) => x.id === id)
      if (item) return { tab: key, idea: item }
    }
    return null
  }

  // ========== 重置所有数据（用户切换/登出时调用，防止跨用户数据残留）==========
  function resetAll() {
    voices.value = []
    ideas.value = { voting: [], adopted: [], completed: [] }
    feedbacks.value = []
    messages.value = []
    announcements.value = []
    notifications.value = []
    _lastLoadTime = 0
    _loadAllPromise = null
  }

  // ========== 导出 normalize 工具函数 ==========
  return {
    voices,
    ideas,
    feedbacks,
    messages,
    announcements,
    notifications,
    loadAll,
    loadVoices,
    loadIdeas,
    loadAnnouncements,
    loadFeedbacks,
    loadMessages,
    loadNotifications,
    resetAll,
    findVoiceById,
    findIdeaById,
    normalizeVoice,
    normalizeComment,
    normalizeIdea,
    normalizeFeedback,
    normalizeMessage,
    normalizeAnnouncement,
    normalizeNotification
  }
})
