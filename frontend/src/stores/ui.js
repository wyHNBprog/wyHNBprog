import { defineStore } from 'pinia'
import { ref } from 'vue'

// ========== UI 状态 store ==========
// darkMode / toast 消息 / publishModal 开关

export const useUiStore = defineStore('ui', () => {
  // 暗黑模式
  const darkMode = ref(false)

  // Toast 消息
  const toast = ref({
    show: false,
    text: ''
  })
  let _toastTimer = null

  // 发布浮窗
  const publishModal = ref({
    show: false,
    type: 'voice', // 'voice' | 'idea' | 'both'
    forceType: null // 强制发布类型（页面上下文感知）
  })

  // 驳回弹窗
  const rejectModal = ref({
    show: false,
    title: '驳回',
    voiceId: null,
    ideaId: null,
    commentInfo: null, // { voiceId, commentId }
    reason: '',
    error: ''
  })

  // ========== 暗黑模式 ==========
  function applyDarkMode() {
    if (darkMode.value) {
      document.documentElement.classList.add('dark-theme')
    } else {
      document.documentElement.classList.remove('dark-theme')
    }
  }

  function initDarkMode() {
    try {
      const saved = localStorage.getItem('voicehub-dark')
      darkMode.value = saved === '1'
    } catch (e) {}
    applyDarkMode()
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    applyDarkMode()
    try {
      localStorage.setItem('voicehub-dark', darkMode.value ? '1' : '0')
    } catch (e) {}
  }

  // 自定义确认弹窗（替代 window.confirm）
const confirmDialog = ref({ show: false, title: '', message: '', confirmText: '确认', cancelText: '取消', danger: false, resolve: null })

function showConfirm(options = {}) {
  return new Promise((resolve) => {
    // 如果存在未 resolved 的上一个确认弹窗，先以 false（取消）resolve，避免 Promise 泄漏
    if (confirmDialog.value.resolve) {
      confirmDialog.value.resolve(false)
    }
    confirmDialog.value = {
      show: true,
      title: options.title || '提示',
      message: options.message || '',
      confirmText: options.confirmText || '确认',
      cancelText: options.cancelText || '取消',
      danger: options.danger === true,
      resolve,
    }
    // 阻止背景滚动
    document.body.classList.add('modal-open')
  })
}

function resolveConfirm(result) {
  if (confirmDialog.value.resolve) {
    confirmDialog.value.resolve(result)
  }
  confirmDialog.value.show = false
  confirmDialog.value.resolve = null
  // 恢复背景滚动
  document.body.classList.remove('modal-open')
}
  function showToast(msg) {
    toast.value.text = msg
    toast.value.show = true
    clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => {
      toast.value.show = false
    }, 2000)
  }

  // 渐隐提示（3 秒）
  function showFadeToast(msg) {
    toast.value.text = msg
    toast.value.show = true
    clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => {
      toast.value.show = false
    }, 3000)
  }

  // ========== 发布浮窗 ==========
  function openPublishModal(forceType = null) {
    publishModal.value.show = true
    publishModal.value.forceType = forceType
    publishModal.value.type = forceType || 'voice'
    document.body.classList.add('modal-open')
  }

  function closePublishModal() {
    publishModal.value.show = false
    publishModal.value.forceType = null
    document.body.classList.remove('modal-open')
  }

  function switchPublishType(type) {
    publishModal.value.type = type
  }

  // ========== 驳回弹窗 ==========
  function openRejectModal(payload) {
    // payload: { title, voiceId?, ideaId?, commentInfo? }
    rejectModal.value = {
      show: true,
      title: payload.title || '驳回',
      voiceId: payload.voiceId || null,
      ideaId: payload.ideaId || null,
      commentInfo: payload.commentInfo || null,
      reason: '',
      error: ''
    }
  }

  function closeRejectModal() {
    rejectModal.value.show = false
    rejectModal.value.voiceId = null
    rejectModal.value.ideaId = null
    rejectModal.value.commentInfo = null
    rejectModal.value.reason = ''
    rejectModal.value.error = ''
  }

  return {
    darkMode,
    toast,
    publishModal,
    rejectModal,
    confirmDialog,
    initDarkMode,
    toggleDarkMode,
    applyDarkMode,
    showToast,
    showFadeToast,
    showConfirm,
    resolveConfirm,
    openPublishModal,
    closePublishModal,
    switchPublishType,
    openRejectModal,
    closeRejectModal
  }
})
