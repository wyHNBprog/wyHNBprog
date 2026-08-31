<template>
  <NavBar title="提交金点子" :show-home="true" />
  <div class="page">
    <div class="form-page">
      <div class="form-card">
        <div class="form-label">金点子标题</div>
        <input
          v-model="title"
          class="form-input"
          placeholder="给你的金点子起个名字"
          maxlength="30"
        />
        <div class="form-label">详细描述</div>
        <textarea
          v-model="desc"
          class="form-textarea"
          placeholder="详细描述你的金点子…"
          maxlength="500"
          style="min-height:120px;"
        ></textarea>
        <div class="form-label">选择分类</div>
        <div class="form-cats">
          <div
            v-for="cat in IDEA_CATS"
            :key="cat"
            class="form-cat"
            :class="{ selected: selectedCat === cat }"
            @click="selectCat(cat)"
          >{{ cat }}</div>
        </div>
        <div v-if="selectedCat === '其他'" style="margin-top:10px;">
          <input
            v-model="customCat"
            class="form-input"
            placeholder="输入自定义分类名称"
            maxlength="12"
          />
        </div>
      </div>
      <button
        class="form-submit"
        :class="{ loading: submitting }"
        @click="onSubmit"
      >{{ submitting ? '提交中...' : '提交金点子' }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { useUiStore } from '@/stores/ui'
import { createIdea } from '@/api/idea'
import { IDEA_CATS, ANON_NAME } from '@/utils/constants'

const router = useRouter()
const authStore = useAuthStore()
const dataStore = useDataStore()
const uiStore = useUiStore()

const title = ref('')
const desc = ref('')
const selectedCat = ref('')
const customCat = ref('')
const submitting = ref(false)

function selectCat(cat) {
  selectedCat.value = cat
}

async function onSubmit() {
  if (submitting.value) return
  const t = title.value.trim()
  const d = desc.value.trim()
  if (!t) {
    uiStore.showToast('请输入标题')
    return
  }
  if (t.length > 30) {
    uiStore.showToast('标题不能超过30字')
    return
  }
  if (!d) {
    uiStore.showToast('请输入描述')
    return
  }
  if (d.length > 500) {
    uiStore.showToast('描述不能超过500字')
    return
  }
  // 分类
  let category = '其他'
  if (selectedCat.value === '其他') {
    const custom = customCat.value.trim()
    if (!custom) {
      uiStore.showToast('选择了"其他"，请填写自定义分类名')
      return
    }
    category = custom
  } else if (selectedCat.value) {
    category = selectedCat.value
  }
  submitting.value = true
  try {
    const res = await createIdea({
      title: t,
      desc: d,
      category: category,
      isAnonymous: true,
      anonName: ANON_NAME
    })
    if (res && res.idea) {
      dataStore.ideas.voting.unshift(dataStore.normalizeIdea(res.idea))
      if (!authStore.isAdmin) {
        dataStore.notifications.unshift(
          dataStore.normalizeNotification({
            id: 'n_' + Date.now(),
            type: 'system',
            text: '你的金点子已提交，等待管理员审核',
            created_at: new Date().toISOString()
          })
        )
      }
      uiStore.showFadeToast(authStore.isAdmin ? '已发布' : '已提交，正在等待管理员审核')
      router.reLaunch({ name: 'home' })
    }
  } catch (e) {
    uiStore.showToast('提交失败：' + e.message)
  } finally {
    submitting.value = false
  }
}
</script>
