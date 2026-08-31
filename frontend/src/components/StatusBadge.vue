<template>
  <span class="status-badge" :class="badgeClass">{{ text }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { STATUS_MAP, STATUS_BADGE_CLASS } from '@/utils/constants'

const props = defineProps({
  status: { type: String, required: true }
})

const text = computed(() => STATUS_MAP[props.status] || props.status)
const badgeClass = computed(() => STATUS_BADGE_CLASS[props.status] || 'badge-orange')
</script>
