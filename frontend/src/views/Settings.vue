<template>
  <NavBar title="设置" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div class="menu-section">
        <div class="menu-item" @click="uiStore.toggleDarkMode()">
          <div class="menu-icon">🌙</div>
          <div class="menu-title">深色模式</div>
          <div class="switch" :class="{ on: uiStore.darkMode }"><div class="switch-dot"></div></div>
        </div>
        <div class="menu-item" @click="goTo('feedback-submit')">
          <div class="menu-icon">📧</div>
          <div class="menu-title">意见反馈</div>
          <div class="menu-arrow">›</div>
        </div>
      </div>

      <div class="menu-section">
        <div class="menu-item" @click="clearCache">
          <div class="menu-icon">🗑</div>
          <div class="menu-title">清除缓存</div>
          <div class="menu-arrow">›</div>
        </div>
      </div>

      <div class="about-section" @click="showAbout">
        NNIT 论坛 · VoiceHub v2.0<br />
        <span style="font-size:11px;">OPEN&amp;HONEST</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import NavBar from '@/components/NavBar.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

import { useRouter } from 'vue-router'
const router = useRouter()

function goTo(name) {
  router.push({ name })
}

function clearCache() {
  try {
    sessionStorage.clear()
  } catch (e) {}
  uiStore.showToast('缓存已清除')
}

function showAbout() {
  uiStore.showToast('NNIT 论坛 v2.02')
}
</script>
