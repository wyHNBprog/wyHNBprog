<template>
  <div class="nav-bar">
    <span class="back-btn" @click="goBack">‹</span>
    <span class="nav-title">{{ title }}</span>
    <span v-if="showHome" class="nav-home-btn" @click="goHome">首页</span>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, default: '' },
  showHome: { type: Boolean, default: false },
  fallback: { type: String, default: 'home' },
  customBack: { type: Boolean, default: false }
})

const emit = defineEmits(['back'])

const router = useRouter()

// 返回上一页：customBack 模式下仅触发 back 事件由父组件处理；
// 默认模式下有浏览器历史就 back，否则回退到 fallback 页
function goBack() {
  if (props.customBack) {
    emit('back')
    return
  }
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push({ name: props.fallback })
  }
}

function goHome() {
  router.push({ name: 'home' })
}
</script>
