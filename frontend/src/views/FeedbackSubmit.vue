<template>
  <NavBar title="提交反馈" :show-home="true" />
  <div class="page">
    <div class="form-page">
      <div class="form-card">
        <div class="form-label">反馈分类</div>
        <div class="form-cats">
          <div
            v-for="cat in FB_CATS"
            :key="cat"
            class="form-cat"
            :class="{ selected: selectedCat === cat }"
            @click="selectedCat = cat"
          >{{ cat }}</div>
        </div>
        <div class="form-label">反馈内容</div>
        <textarea
          v-model="content"
          class="form-textarea"
          placeholder="请详细描述你的反馈..."
          maxlength="500"
          style="min-height:140px;"
        ></textarea>
        <div style="text-align:right;font-size:12px;color:var(--text-secondary);">{{ content.length }}/500</div>
      </div>
      <button
        class="form-submit"
        :class="{ loading: submitting }"
        @click="onSubmit"
      >{{ submitting ? '提交中...' : '提交反馈' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { createFeedback } from '@/api/feedback'
import { FB_CATS, ANON_NAME } from '@/utils/constants'

const router = useRouter()
const dataStore = useDataStore()
const uiStore = useUiStore()

const selectedCat = ref('其他')
const content = ref('')
const submitting = ref(false)

async function onSubmit() {
  if (submitting.value) return
  const c = content.value.trim()
  if (!c) {
    uiStore.showToast('请输入反馈内容')
    return
  }
  if (c.length > 500) {
    uiStore.showToast('内容不能超过500字')
    return
  }
  submitting.value = true
  try {
    const res = await createFeedback({
      category: selectedCat.value,
      content: c,
      anonName: ANON_NAME
    })
    if (res && res.feedback) {
      dataStore.feedbacks.unshift(dataStore.normalizeFeedback(res.feedback))
      uiStore.showFadeToast('反馈已提交，感谢你的支持')
      router.back()
    }
  } catch (e) {
    uiStore.showToast('提交失败：' + e.message)
  } finally {
    submitting.value = false
  }
}
</script>
