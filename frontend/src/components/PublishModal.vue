<template>
  <div v-if="uiStore.publishModal.show" class="publish-mask" :class="{ closing: isClosing }" @click.self="onClose">
    <div class="publish-sheet" :class="{ closing: isClosing }" @click.stop>
      <div class="publish-handle"></div>

      <!-- 关闭按钮 -->
      <div class="publish-close" @click="onClose">
        <svg viewBox="0 0 24 24" fill="none" style="width:20px;height:20px"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      </div>

      <!-- Tab 切换（仅在不强制类型时显示） -->
      <div v-if="!uiStore.publishModal.forceType" class="publish-tabs">
        <div
          class="publish-tab"
          :class="{ active: uiStore.publishModal.type === 'voice' }"
          @click="uiStore.switchPublishType('voice')"
        >发布留言</div>
        <div
          class="publish-tab"
          :class="{ active: uiStore.publishModal.type === 'idea' }"
          @click="uiStore.switchPublishType('idea')"
        >金点子</div>
      </div>

      <!-- 留言表单 -->
      <div v-if="uiStore.publishModal.type === 'voice'" class="publish-body">
        <textarea
          ref="voiceTextarea"
          v-model="voiceContent"
          class="pub-textarea"
          placeholder="写下你想说的话…&#10;匿名发布，畅所欲言"
          maxlength="500"
        ></textarea>
        <div class="pub-charcount"><span>{{ voiceContent.length }}</span>/500</div>
        <div class="anon-toggle" @click="voiceAnon = !voiceAnon">
          <div class="anon-left">
            <span class="anon-icon">🎭</span>
            <span class="anon-label">匿名发布</span>
          </div>
          <div class="switch" :class="{ on: voiceAnon }"><div class="switch-dot"></div></div>
        </div>
      </div>

      <!-- 金点子表单 -->
      <div v-if="uiStore.publishModal.type === 'idea'" class="publish-body">
        <div class="form-input-wrap">
          <div class="form-input-label">金点子标题</div>
          <input
            v-model="ideaTitle"
            class="form-input"
            placeholder="给你的金点子起个名字"
            maxlength="30"
          />
        </div>
        <div class="form-input-wrap">
          <div class="form-input-label">详细描述</div>
          <textarea
            v-model="ideaDesc"
            class="form-textarea"
            placeholder="详细描述你的金点子…"
            maxlength="500"
            style="min-height:120px;"
          ></textarea>
        </div>
        <div class="form-input-wrap">
          <div class="form-input-label">选择分类</div>
          <div class="form-cats">
            <div
              v-for="cat in IDEA_CATS"
              :key="cat"
              class="form-cat"
              :class="{ selected: selectedCats.includes(cat) }"
              @click="toggleIdeaCat(cat)"
            >{{ cat }}</div>
          </div>
        </div>
        <div v-if="selectedCats.includes('其他')" class="form-input-wrap">
          <div class="form-input-label">自定义分类名称（将填入"其他"字段）</div>
          <input
            v-model="customCat"
            class="form-input"
            placeholder="例如：弹性工位 / 内部培训"
            maxlength="10"
          />
        </div>
        <div class="anon-toggle" @click="ideaAnon = !ideaAnon">
          <div class="anon-left">
            <span class="anon-icon">💡</span>
            <span class="anon-label">匿名提交</span>
          </div>
          <div class="switch" :class="{ on: ideaAnon }"><div class="switch-dot"></div></div>
        </div>
      </div>

      <button class="publish-submit" :class="{ loading: submitting }" @click="onSubmit">
        {{ submitting ? '发布中...' : '发布' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useDataStore } from '@/stores/data'
import { createVoice } from '@/api/voice'
import { createIdea } from '@/api/idea'
import { IDEA_CATS, ANON_NAME } from '@/utils/constants'

const uiStore = useUiStore()
const authStore = useAuthStore()
const dataStore = useDataStore()

// 关闭动画状态
const isClosing = ref(false)

// 带动画的关闭
function onClose() {
  if (isClosing.value) return
  isClosing.value = true
  setTimeout(() => {
    uiStore.closePublishModal()
    isClosing.value = false
  }, 300) // 与 slideDown 动画时长一致
}

// 留言表单
const voiceContent = ref('')
const voiceAnon = ref(true)

// 金点子表单
const ideaTitle = ref('')
const ideaDesc = ref('')
const ideaAnon = ref(true)
const selectedCats = ref([])
const customCat = ref('')

// 提交中状态（防重复点击）
const submitting = ref(false)

// 切换金点子分类（单选效果）
function toggleIdeaCat(cat) {
  // 单选：点击即选中该分类，取消其他
  if (selectedCats.value.includes(cat)) {
    selectedCats.value = []
  } else {
    selectedCats.value = [cat]
  }
}

// 浮窗打开时重置表单
watch(
  () => uiStore.publishModal.show,
  (show) => {
    if (show) {
      voiceContent.value = ''
      voiceAnon.value = true
      ideaTitle.value = ''
      ideaDesc.value = ''
      ideaAnon.value = true
      selectedCats.value = []
      customCat.value = ''
      submitting.value = false
      isClosing.value = false
    }
  }
)

// 提交
async function onSubmit() {
  if (submitting.value || isClosing.value) return
  submitting.value = true
  try {
    if (uiStore.publishModal.type === 'voice') {
      await submitVoice()
    } else {
      await submitIdea()
    }
  } catch (e) {
    uiStore.showToast('发布失败：' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

// 发布留言
async function submitVoice() {
  const content = voiceContent.value.trim()
  if (!content) {
    uiStore.showToast('请输入内容')
    return
  }
  if (content.length > 500) {
    uiStore.showToast('内容不能超过500字')
    return
  }
  const res = await createVoice({
    content: content,
    isAnonymous: voiceAnon.value,
    anonName: voiceAnon.value ? ANON_NAME : authStore.user.nickname,
    tags: []
  })
  if (res && res.voice) {
    dataStore.voices.unshift(dataStore.normalizeVoice(res.voice))
    if (!authStore.isAdmin) {
      dataStore.notifications.unshift(
        dataStore.normalizeNotification({
          id: 'n_' + Date.now(),
          type: 'system',
          text: '你的留言已提交，等待管理员审核',
          created_at: new Date().toISOString()
        })
      )
    }
    uiStore.showFadeToast(authStore.isAdmin ? '已发布' : '已提交，正在等待管理员审核')
    onClose()
  } else {
    uiStore.showToast('发布成功，请刷新查看')
    onClose()
  }
}

// 提交金点子
async function submitIdea() {
  const title = ideaTitle.value.trim()
  const desc = ideaDesc.value.trim()
  if (!title) {
    uiStore.showToast('请输入标题')
    return
  }
  if (title.length > 30) {
    uiStore.showToast('标题不能超过30字')
    return
  }
  if (!desc) {
    uiStore.showToast('请输入描述')
    return
  }
  if (desc.length > 500) {
    uiStore.showToast('描述不能超过500字')
    return
  }
  // 收集分类：若选「其他」则用自定义输入；否则用所选分类
  let category = '其他'
  if (selectedCats.value.includes('其他')) {
    const custom = customCat.value.trim()
    if (!custom) {
      uiStore.showToast('选择了"其他"，请填写自定义分类名')
      return
    }
    category = custom
  } else if (selectedCats.value.length > 0) {
    category = selectedCats.value[0]
  }
  const res = await createIdea({
    title: title,
    desc: desc,
    category: category,
    isAnonymous: ideaAnon.value,
    anonName: ideaAnon.value ? ANON_NAME : authStore.user.nickname
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
    onClose()
  } else {
    uiStore.showToast('发布成功，请刷新查看')
    onClose()
  }
}
</script>
