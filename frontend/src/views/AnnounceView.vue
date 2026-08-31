<template>
  <NavBar title="论坛公告" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="dataStore.announcements.length === 0" class="empty-state">
        <div class="empty-state-icon">📢</div>
        <div class="empty-state-text">暂无公告</div>
      </div>
      <template v-else>
        <div
          v-for="a in dataStore.announcements"
          :key="a.id"
          class="post-card"
          style="margin-bottom:12px;border-left:3px solid #C9A24B;"
        >
          <div class="post-header">
            <div class="post-avatar">📢</div>
            <span class="post-anon">{{ a.title }}</span>
            <span v-if="a.pinned" class="sticky-tag" style="background:rgba(196,149,106,0.12);color:#C4956A;">置顶</span>
            <span class="post-time">{{ a.timeText }}</span>
          </div>
          <div class="post-content" style="white-space:pre-wrap;">{{ a.content }}</div>
          <div v-if="authStore.isAdmin" class="post-footer" style="margin-top:10px;">
            <button class="btn-reject" style="flex:none;padding:6px 14px;background:var(--bg-tag);color:var(--text-primary);" @click="onEdit(a)">编辑</button>
            <button class="btn-reject" style="flex:none;padding:6px 14px;" @click="onDelete(a)">删除</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { deleteAnnouncement } from '@/api/announce'

const router = useRouter()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

function onEdit(a) {
  router.push({ name: 'announce-edit', query: { id: a.id } })
}

async function onDelete(a) {
  if (!await uiStore.showConfirm({ message: '确认删除这条公告？删除后不可恢复。', danger: true })) return
  try {
    await deleteAnnouncement(a.id)
    const idx = dataStore.announcements.findIndex((x) => x.id === a.id)
    if (idx !== -1) dataStore.announcements.splice(idx, 1)
    uiStore.showToast('已删除')
  } catch (e) {
    uiStore.showToast('删除失败：' + e.message)
  }
}

onMounted(async () => {
  await dataStore.loadAnnouncements()
})
</script>
