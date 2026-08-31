<template>
  <NavBar title="我的评论" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="myComments.length === 0" class="empty-state">
        <div class="empty-state-icon">💬</div>
        <div class="empty-state-text">你还没有发表过评论</div>
      </div>
      <template v-else>
        <div
          v-for="item in myComments"
          :key="item.comment.id"
          class="post-card"
          style="cursor:pointer;margin-bottom:10px;"
          @click="openVoice(item.voice.id)"
        >
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px;">来自留言：{{ truncate(item.voice.content, 40) }}</div>
          <div class="post-header">
            <div class="post-avatar">{{ item.comment.anonName ? item.comment.anonName.charAt(0) : '?' }}</div>
            <span class="post-anon">{{ item.comment.anonName }}</span>
            <span class="post-time">{{ item.comment.timeText }}</span>
            <StatusBadge :status="item.comment.status" />
          </div>
          <div class="post-content" style="margin-top:4px;">{{ item.comment.content }}</div>
          <div v-if="item.comment.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ item.comment.rejectReason }}</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useDataStore } from '@/stores/data'
import { truncate } from '@/utils/format'

const router = useRouter()
const dataStore = useDataStore()

const myComments = computed(() => {
  const result = []
  dataStore.voices.forEach((v) => {
    ;(v.comments || []).forEach((c) => {
      if (c.isMine) {
        result.push({ voice: v, comment: c })
      }
    })
  })
  return result
})

function openVoice(id) {
  router.push({ name: 'voice-detail', params: { id } })
}

onMounted(async () => {
  await dataStore.loadAll(true)
})
</script>
