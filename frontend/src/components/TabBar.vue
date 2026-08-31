<template>
  <div class="tab-bar">
    <div
      class="tab-item"
      :class="{ active: activeTab === 'home' }"
      @click="goHome"
    >
      <div class="tab-icon">
        <svg viewBox="0 0 24 24" style="width:22px;height:22px">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          <polyline points="9 22 9 12 15 12 15 22" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
        </svg>
      </div>
      首页
    </div>

    <div class="tab-item" @click="onPublishClick">
      <button class="tab-publish" :class="{ active: uiStore.publishModal.show }">
        <svg viewBox="0 0 24 24" fill="none">
          <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
      发布
    </div>

    <div
      class="tab-item"
      :class="{ active: activeTab === 'mine' }"
      @click="goMine"
    >
      <div class="tab-icon" style="position:relative">
        <svg viewBox="0 0 24 24" style="width:22px;height:22px">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="1.6"/>
        </svg>
        <span v-if="unreadCount > 0" class="nav-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
      </div>
      我的
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { useDataStore } from '@/stores/data'

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const dataStore = useDataStore()

// 当前激活的 tab
const activeTab = computed(() => {
  if (route.name === 'home') return 'home'
  if (route.name === 'mine') return 'mine'
  return ''
})

// 未读通知数量
const unreadCount = computed(() => {
  return dataStore.notifications.filter((n) => !n.read).length
})

function goHome() {
  router.push({ name: 'home' })
}

function goMine() {
  router.push({ name: 'mine' })
}

// 发布按钮点击：根据当前页面 Tab 限制发布类型
function onPublishClick() {
  if (uiStore.publishModal.show) {
    uiStore.closePublishModal()
  } else {
    // 从 sessionStorage 读取当前 Home Tab，限制发布类型
    let forceType = null
    try {
      const homeTab = sessionStorage.getItem('home_tab') || 'announce'
      if (homeTab === 'idea') forceType = 'idea'
      else if (homeTab === 'voice') forceType = 'voice'
    } catch (e) {}
    uiStore.openPublishModal(forceType)
  }
}
</script>
