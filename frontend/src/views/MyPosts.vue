<template>
  <NavBar title="我的留言" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="myVoices.length === 0" class="empty-state">
        <div class="empty-state-icon">📝</div>
        <div class="empty-state-text">你还没有发布过留言<br>快去留言墙留下第一条吧</div>
      </div>
      <template v-else>
        <div
          v-for="v in myVoices"
          :key="v.id"
          class="post-card"
          style="cursor:pointer;margin-bottom:10px;"
          @click="openVoice(v.id)"
        >
          <div class="post-header">
            <div class="post-avatar">🎭</div>
            <span class="post-anon">{{ v.anonName }}</span>
            <span class="post-time">{{ v.timeText }}</span>
            <StatusBadge :status="v.status" />
          </div>
          <div class="post-content">{{ v.content }}</div>
          <div v-if="v.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ v.rejectReason }}</div>
          <div class="post-footer" style="margin-top:8px;">
            <span>❤ {{ v.likeCount || 0 }}</span>
            <span>💬 {{ approvedCommentCount(v) }}</span>
          </div>
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

const router = useRouter()
const dataStore = useDataStore()

const myVoices = computed(() => dataStore.voices.filter((v) => v.isMine))

function approvedCommentCount(v) {
  return v.comments ? v.comments.filter((c) => c.status === 'approved').length : 0
}

function openVoice(id) {
  router.push({ name: 'voice-detail', params: { id } })
}

onMounted(async () => {
  await dataStore.loadAll(true)
})
</script>
