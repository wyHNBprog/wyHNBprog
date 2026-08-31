<template>
  <NavBar title="反馈中心" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="dataStore.feedbacks.length === 0" class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div class="empty-state-text">暂无反馈<br>点击下方按钮提交反馈</div>
      </div>
      <template v-else>
        <div
          v-for="f in dataStore.feedbacks"
          :key="f.id"
          class="post-card"
          style="cursor:pointer;margin-bottom:10px;"
          @click="openDetail(f.id)"
        >
          <div class="post-header">
            <div class="post-avatar">📧</div>
            <span class="post-anon">{{ f.category }}</span>
            <span class="post-time">{{ f.timeText }}</span>
          </div>
          <div class="post-content">{{ truncate(f.content, 60) }}</div>
          <div class="post-footer">
            <StatusBadge v-if="f.status === 'replied'" status="approved" />
            <StatusBadge v-else status="pending" />
          </div>
        </div>
      </template>
      <button
        class="form-submit"
        style="position:fixed;bottom:calc(80px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);width:calc(100% - 32px);max-width:398px;"
        @click="goTo('feedback-submit')"
      >+ 提交反馈</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useDataStore } from '@/stores/data'
import { truncate } from '@/utils/format'

const router = useRouter()
const dataStore = useDataStore()

function openDetail(id) {
  router.push({ name: 'feedback-detail', params: { id } })
}

function goTo(name) {
  router.push({ name })
}

onMounted(async () => {
  await dataStore.loadFeedbacks()
})
</script>
