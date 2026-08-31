<template>
  <NavBar title="我的金点子" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="myIdeas.length === 0" class="empty-state">
        <div class="empty-state-icon">💡</div>
        <div class="empty-state-text">你还没有提交过金点子<br>快去贡献你的金点子吧</div>
      </div>
      <template v-else>
        <div
          v-for="i in myIdeas"
          :key="i.id"
          class="idea-card"
        >
          <div class="idea-title">
            {{ i.title }}
            <span v-if="i.hasFlower" class="idea-flower-mark">🌸</span>
            <span v-if="i.hasFirework" class="idea-firework-mark">✨</span>
          </div>
          <div class="idea-desc">{{ i.desc }}</div>
          <div class="post-footer" style="margin-bottom:8px;">
            <span class="sticky-tag">{{ i.category }}</span>
            <StatusBadge :status="i.status" />
            <span style="margin-left:auto;font-size:12px;color:var(--text-secondary);">{{ i.timeText }}</span>
          </div>
          <div v-if="i.rejectReason" style="font-size:12px;color:#C4726A;margin-top:6px;padding:6px 10px;background:rgba(196,114,106,0.08);border-radius:8px;">驳回原因：{{ i.rejectReason }}</div>
          <div class="idea-footer" style="margin-top:8px;">
            <span style="font-size:13px;color:var(--text-secondary);">❤ {{ i.voteCount || 0 }} 赞同</span>
            <span v-if="i.hasFlower" style="font-size:13px;color:#E8A0B4;">🌸 {{ i.flowerCount || 0 }}</span>
            <span v-if="i.hasFirework" style="font-size:13px;color:#FF6B6B;">✨ {{ i.fireworkCount || 0 }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useDataStore } from '@/stores/data'

const dataStore = useDataStore()

const myIdeas = computed(() => {
  return Object.values(dataStore.ideas).reduce((arr, a) => arr.concat(a.filter((i) => i.isMine)), [])
})

onMounted(async () => {
  await dataStore.loadAll(true)
})
</script>
