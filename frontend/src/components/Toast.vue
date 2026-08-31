<template>
  <div class="toast" :class="{ show: uiStore.toast.show }">{{ uiStore.toast.text }}</div>
</template>

<script setup>
import { useUiStore } from '@/stores/ui'
const uiStore = useUiStore()
</script>
