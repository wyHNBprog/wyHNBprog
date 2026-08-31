<template>
  <NavBar title="消息通知" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <!-- 分类标签栏：横向滚动 + 数字徽章 -->
      <div class="notif-tabs">
        <div
          v-for="tab in notifTabs"
          :key="tab.key"
          class="notif-tab"
          :class="{ active: currentTab === tab.key }"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
          <span v-if="tab.key !== 'all' && getTabUnread(tab.key) > 0" class="notif-tab-badge">{{ getTabUnread(tab.key) > 99 ? '99+' : getTabUnread(tab.key) }}</span>
        </div>
      </div>

      <!-- 顶部操作栏 -->
      <div v-if="dataStore.notifications.length > 0 && totalUnread > 0" class="notif-header">
        <span class="notif-unread-count">{{ totalUnread > 99 ? '99+' : totalUnread }} 条未读</span>
        <div style="display:flex;gap:8px;">
          <button
            v-if="currentTab !== 'all' && getTabUnread(currentTab) > 0"
            class="notif-read-all-btn"
            :disabled="markingType"
            @click="markTypeRead(currentTab)"
          >{{ markingType ? '...' : '本类已读' }}</button>
          <button
            class="notif-read-all-btn"
            :disabled="markingAll"
            @click="markAllReadAction"
          >{{ markingAll ? '...' : '全部已读' }}</button>
        </div>
      </div>
      <div v-if="filteredNotifications.length === 0" class="empty-state">
        <div class="empty-state-icon">🔔</div>
        <div class="empty-state-text">{{ currentTab === 'all' ? '暂无消息通知' : '该分类暂无通知' }}</div>
      </div>
      <TransitionGroup v-else name="notif-list" tag="div">
        <div
          v-for="n in filteredNotifications"
          :key="n.id"
          class="post-card notif-item"
          :class="{ 'notif-unread': !n.read }"
          @click="handleNotifClick(n)"
        >
          <div class="notif-item-inner">
            <div
              class="notif-icon"
              :style="{ background: getNotifIconBg(n.type) }"
            >{{ getNotifIcon(n.type) }}</div>
            <div class="notif-body">
              <div class="notif-text">{{ n.text }}</div>
              <div class="notif-meta">
                <span class="notif-type-tag" :style="{ color: getNotifTagColor(n.type) }">{{ getNotifTypeLabel(n.type) }}</span>
                <span class="notif-time">{{ n.timeText }}</span>
              </div>
            </div>
            <div v-if="!n.read" class="notif-dot"></div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { useRealtimeStore } from '@/stores/realtime'
import { markNotificationRead as apiMarkRead, markAllRead as apiMarkAllRead, readByType as apiReadByType } from '@/api/notification'

const dataStore = useDataStore()
const uiStore = useUiStore()
const realtimeStore = useRealtimeStore()

const markingAll = ref(false)
const markingType = ref(false)
const currentTab = ref('all')

// 分类标签配置
const notifTabs = [
  { key: 'all', label: '全部' },
  { key: 'voice', label: '留言' },
  { key: 'idea', label: '金点子' },
  { key: 'comment', label: '评论' },
  { key: 'message', label: '私信' },
  { key: 'feedback', label: '反馈' },
  { key: 'system', label: '系统' },
]

// 通知类型 -> 分类映射
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

// 通知类型 -> 图标映射
const NOTIF_ICON = {
  voice_approved: '✅',
  voice_rejected: '❌',
  idea_approved: '💡',
  idea_rejected: '💡',
  message_replied: '✉',
  message_received: '✉',
  feedback_replied: '📧',
  comment_approved: '💬',
  comment_rejected: '💬',
  system: '📢',
}

// 通知类型 -> 标签文案
const NOTIF_TYPE_LABEL = {
  voice_approved: '留言通过',
  voice_rejected: '留言驳回',
  idea_approved: '金点子通过',
  idea_rejected: '金点子驳回',
  message_replied: '私信回复',
  message_received: '私信',
  feedback_replied: '反馈回复',
  comment_approved: '评论通过',
  comment_rejected: '评论驳回',
  system: '系统',
}

// 通知类型 -> 标签颜色
const NOTIF_TAG_COLOR = {
  voice_approved: '#52c41a',
  voice_rejected: '#ff4d4f',
  idea_approved: '#722ed1',
  idea_rejected: '#ff4d4f',
  message_replied: '#d4838a',
  message_received: '#d4838a',
  feedback_replied: '#ba7517',
  comment_approved: '#52c41a',
  comment_rejected: '#ff4d4f',
  system: 'var(--accent)',
}

// 获取通知图标
function getNotifIcon(type) {
  return NOTIF_ICON[type] || '📢'
}

// 获取通知图标背景色
function getNotifIconBg(type) {
  const cat = NOTIF_TYPE_CATEGORY[type] || 'system'
  const bgMap = {
    voice: 'rgba(123,158,135,0.12)',
    idea: 'rgba(83,74,183,0.12)',
    comment: 'rgba(89,160,212,0.12)',
    message: 'rgba(212,83,126,0.12)',
    feedback: 'rgba(186,117,23,0.12)',
    system: 'var(--accent-dim)',
  }
  return bgMap[cat] || 'var(--accent-dim)'
}

// 获取通知类型标签
function getNotifTypeLabel(type) {
  return NOTIF_TYPE_LABEL[type] || '通知'
}

// 获取通知标签颜色
function getNotifTagColor(type) {
  return NOTIF_TAG_COLOR[type] || 'var(--text-secondary)'
}

// 按当前分类筛选通知
const filteredNotifications = computed(() => {
  if (currentTab.value === 'all') {
    return dataStore.notifications
  }
  return dataStore.notifications.filter((n) => {
    const cat = NOTIF_TYPE_CATEGORY[n.type] || 'system'
    return cat === currentTab.value
  })
})

// 总未读数
const totalUnread = computed(() => {
  return dataStore.notifications.filter((n) => !n.read).length
})

// 获取某个分类的未读数
function getTabUnread(category) {
  return dataStore.notifications.filter((n) => {
    if (n.read) return false
    const cat = NOTIF_TYPE_CATEGORY[n.type] || 'system'
    return cat === category
  }).length
}

// 切换分类标签
function switchTab(key) {
  currentTab.value = key
}

// 点击通知卡片：标记已读（整体可点击，无需单独按钮）
async function handleNotifClick(n) {
  if (n.read) return
  // 客户端临时通知（id 以 n_ 开头）后端不存在，直接本地更新
  if (typeof n.id === 'string' && n.id.indexOf('n_') === 0) {
    n.read = true
    realtimeStore.updateUnreadByType()
    return
  }
  // 乐观更新
  n.read = true
  realtimeStore.updateUnreadByType()
  try {
    await apiMarkRead(n.id)
  } catch (e) {
    n.read = false
    realtimeStore.updateUnreadByType()
    uiStore.showToast('操作失败')
  }
}

// 按分类标记已读（乐观更新）
async function markTypeRead(category) {
  if (markingType.value) return
  if (!category || category === 'all') return
  markingType.value = true
  const previouslyUnread = dataStore.notifications.filter((n) => {
    if (n.read) return false
    const cat = NOTIF_TYPE_CATEGORY[n.type] || 'system'
    return cat === category
  })
  previouslyUnread.forEach((n) => { n.read = true })
  realtimeStore.updateUnreadByType()
  try {
    await apiReadByType(category)
  } catch (e) {
    previouslyUnread.forEach((n) => { n.read = false })
    realtimeStore.updateUnreadByType()
    uiStore.showToast('操作失败')
  } finally {
    markingType.value = false
  }
}

// 全部标记已读（乐观更新）
async function markAllReadAction() {
  if (markingAll.value) return
  markingAll.value = true
  const previouslyUnread = dataStore.notifications.filter((n) => !n.read)
  previouslyUnread.forEach((n) => { n.read = true })
  realtimeStore.updateUnreadByType()
  try {
    await apiMarkAllRead()
  } catch (e) {
    previouslyUnread.forEach((n) => { n.read = false })
    realtimeStore.updateUnreadByType()
    uiStore.showToast('操作失败')
  } finally {
    markingAll.value = false
  }
}

onMounted(async () => {
  await dataStore.loadNotifications()
  realtimeStore.updateUnreadByType()
})
</script>

<style scoped>
.notif-tabs {
  display: flex;
  gap: 6px;
  padding: 8px 0;
  margin-bottom: 8px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.notif-tabs::-webkit-scrollbar {
  display: none;
}
.notif-tab {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
}
.notif-tab.active {
  color: var(--accent);
  background: var(--accent-dim);
  border-color: var(--accent);
}
.notif-tab-badge {
  font-size: 11px;
  color: #fff;
  background: #e5484d;
  border-radius: 10px;
  padding: 1px 6px;
  min-width: 16px;
  text-align: center;
  line-height: 1.4;
}
.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 4px;
  margin-bottom: 8px;
}
.notif-unread-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.notif-read-all-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--accent);
  background: var(--accent-dim);
  border: none;
  border-radius: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.notif-read-all-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 通知卡片：整体可点击 */
.notif-item {
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
  padding: 0;
  overflow: hidden;
}
.notif-item:active {
  transform: scale(0.98);
  background: var(--bg-input);
}
.notif-unread {
  border-left: 3px solid var(--accent);
}
.notif-item-inner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
}
.notif-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}
.notif-body {
  flex: 1;
  min-width: 0;
}
.notif-text {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
  word-break: break-word;
}
.notif-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.notif-type-tag {
  font-size: 11px;
  font-weight: 500;
  background: var(--bg-input);
  padding: 1px 6px;
  border-radius: 4px;
}
.notif-time {
  color: var(--text-secondary);
}
.notif-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e5484d;
  flex-shrink: 0;
  margin-top: 14px;
}

/* 列表过渡动画 */
.notif-list-enter-active,
.notif-list-leave-active {
  transition: all 0.3s ease;
}
.notif-list-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.notif-list-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
