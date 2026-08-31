<template>
  <NavBar :title="isEdit ? '编辑公告' : '发布公告'" :show-home="true" />
  <div class="page">
    <div class="form-page">
      <div class="form-card">
        <div class="form-label">公告标题</div>
        <input
          v-model="title"
          class="form-input"
          placeholder="公告标题"
          maxlength="50"
        />
        <div class="form-label">公告内容</div>
        <textarea
          v-model="content"
          class="form-textarea"
          placeholder="公告内容..."
          maxlength="1000"
          style="min-height:160px;"
        ></textarea>
        <div style="text-align:right;font-size:12px;color:var(--text-secondary);">{{ content.length }}/1000</div>
        <div class="anon-toggle" @click="pinned = !pinned">
          <div class="anon-left">
            <span class="anon-icon">📌</span>
            <span class="anon-label">置顶</span>
          </div>
          <div class="switch" :class="{ on: pinned }"><div class="switch-dot"></div></div>
        </div>
      </div>
      <button
        class="form-submit"
        :class="{ loading: submitting }"
        @click="onSubmit"
      >{{ submitting ? (isEdit ? '保存中...' : '发布中...') : (isEdit ? '保存修改' : '发布公告') }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { createAnnouncement, updateAnnouncement } from '@/api/announce'

const route = useRoute()
const router = useRouter()
const dataStore = useDataStore()
const uiStore = useUiStore()

// 编辑模式：通过 query.id 传入公告 id
const editId = computed(() => route.query.id || '')
const isEdit = computed(() => !!editId.value)

const title = ref('')
const content = ref('')
const pinned = ref(false)
const submitting = ref(false)

// 编辑模式：从本地数据填充表单
if (isEdit.value) {
  const target = dataStore.announcements.find((a) => a.id === editId.value)
  if (target) {
    title.value = target.title || ''
    content.value = target.content || ''
    pinned.value = !!target.pinned
  } else {
    uiStore.showToast('未找到该公告')
  }
}

async function onSubmit() {
  if (submitting.value) return
  const t = title.value.trim()
  const c = content.value.trim()
  if (!t) {
    uiStore.showToast('请输入标题')
    return
  }
  if (!c) {
    uiStore.showToast('请输入内容')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: t,
      content: c,
      pinned: pinned.value
    }
    if (isEdit.value) {
      const res = await updateAnnouncement(editId.value, payload)
      if (res && res.announcement) {
        // 更新本地列表
        const idx = dataStore.announcements.findIndex((a) => a.id === editId.value)
        if (idx >= 0) {
          dataStore.announcements[idx] = dataStore.normalizeAnnouncement(res.announcement)
          // 重新排序（置顶优先）
          dataStore.announcements.sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
        }
        uiStore.showFadeToast('公告已更新')
        router.back()
      }
    } else {
      const res = await createAnnouncement(payload)
      if (res && res.announcement) {
        dataStore.announcements.unshift(dataStore.normalizeAnnouncement(res.announcement))
        uiStore.showFadeToast('公告已发布')
        router.back()
      }
    }
  } catch (e) {
    uiStore.showToast((isEdit.value ? '保存失败：' : '发布失败：') + e.message)
  } finally {
    submitting.value = false
  }
}
</script>
