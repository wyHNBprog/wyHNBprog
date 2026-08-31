// ========== 长按删除自定义指令 v-longpress ==========
// 参考 socket 版本 _attachLongPress（js/common.js 第1487-1526行）
// 用法：v-longpress="() => onLongPress(item)" —— 长按 600ms 触发回调
// 管理员权限检查由组件回调内部完成（组件可访问 authStore）

const LONG_PRESS_DURATION = 600 // 长按时间阈值（毫秒）

export const vLongPress = {
  mounted(el, binding) {
    // binding.value 应为回调函数
    if (typeof binding.value !== 'function') return

    let timer = null
    let longPressFired = false
    // 标记最近是否发生过 touch 事件，用于跳过 touch 合成的 mouse 事件，避免长按回调双重触发
    let touchedRecently = false

    const startTimer = (e) => {
      // 记录 touch 事件来源
      if (e.type === 'touchstart') {
        touchedRecently = true
      }
      // 跳过 touch 事件合成的 mouse 事件（移动端 touchend 后约 300ms 会合成 mousedown）
      if (e.type === 'mousedown' && touchedRecently) {
        return
      }
      // 如果事件源是按钮或交互元素，不触发长按（避免误触）
      const target = e.target
      if (target && (target.tagName === 'BUTTON' || target.tagName === 'A' || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.closest('button') || target.closest('a') || target.closest('[data-no-longpress]'))) {
        return
      }
      longPressFired = false
      timer = setTimeout(() => {
        longPressFired = true
        // 触觉反馈
        if (navigator.vibrate) navigator.vibrate(50)
        // 调用回调
        try {
          binding.value()
        } catch (e) {
          // 回调执行异常，忽略
        }
      }, LONG_PRESS_DURATION)
    }

    const cancelTimer = () => {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
    }

    // touchend：取消定时器并延迟重置 touchedRecently 标记
    const touchEndHandler = () => {
      cancelTimer()
      setTimeout(() => { touchedRecently = false }, 500)
    }

    // 阻止长按触发后的 click 事件（防止误跳转）
    const clickHandler = (e) => {
      if (longPressFired) {
        e.preventDefault()
        e.stopPropagation()
        longPressFired = false
      }
    }

    el.addEventListener('touchstart', startTimer, { passive: true })
    el.addEventListener('touchend', touchEndHandler, { passive: true })
    el.addEventListener('touchmove', cancelTimer, { passive: true })
    el.addEventListener('mousedown', startTimer)
    el.addEventListener('mouseup', cancelTimer)
    el.addEventListener('mouseleave', cancelTimer)
    el.addEventListener('click', clickHandler, true)

    // 存储引用以便卸载时移除
    el._longpressHandlers = {
      startTimer,
      cancelTimer,
      touchEndHandler,
      clickHandler
    }
  },
  unmounted(el) {
    if (el._longpressHandlers) {
      const { startTimer, cancelTimer, touchEndHandler, clickHandler } = el._longpressHandlers
      el.removeEventListener('touchstart', startTimer)
      el.removeEventListener('touchend', touchEndHandler)
      el.removeEventListener('touchmove', cancelTimer)
      el.removeEventListener('mousedown', startTimer)
      el.removeEventListener('mouseup', cancelTimer)
      el.removeEventListener('mouseleave', cancelTimer)
      el.removeEventListener('click', clickHandler, true)
      delete el._longpressHandlers
    }
  }
}

export default vLongPress
