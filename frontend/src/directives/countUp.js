/**
 * 数字滚动指令 v-count-up
 * 用法：<span v-count-up="value">0</span>
 * 当 value 变化时，数字从当前值平滑滚动到目标值
 */
import { ref, watch, onMounted } from 'vue'

// 缓动函数：easeOutExpo
function easeOutExpo(t) {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
}

// 执行数字滚动动画（返回 rAF id，便于取消）
function animateNumber(el, from, to, duration = 800) {
  // 取消前一个未完成的动画，避免并发动画导致数字跳动
  if (el._rafId) {
    cancelAnimationFrame(el._rafId)
    el._rafId = null
  }
  const start = performance.now()
  const step = (now) => {
    const elapsed = now - start
    const progress = Math.min(elapsed / duration, 1)
    const eased = easeOutExpo(progress)
    const current = Math.round(from + (to - from) * eased)
    el.textContent = current
    if (progress < 1) {
      el._rafId = requestAnimationFrame(step)
    } else {
      el.textContent = to
      el._rafId = null
    }
  }
  el._rafId = requestAnimationFrame(step)
}

export const vCountUp = {
  mounted(el, binding) {
    el._rafId = null
    el._lastValue = 0
    const target = Number(binding.value) || 0
    el.classList.add('count-up')
    // 首次挂载：从 0 滚动到目标值
    animateNumber(el, 0, target, 900)
    el._lastValue = target
  },
  updated(el, binding) {
    const target = Number(binding.value) || 0
    const from = el._lastValue || 0
    if (target !== from) {
      animateNumber(el, from, target, 600)
      el._lastValue = target
    }
  },
  // 组件卸载时取消未完成的 rAF，避免内存泄漏
  unmounted(el) {
    if (el._rafId) {
      cancelAnimationFrame(el._rafId)
      el._rafId = null
    }
  }
}

/**
 * 组合式函数版本：useCountUp
 * 返回一个 ref，更新时自动滚动
 * 用法：const num = useCountUp(0); num.value = 100
 */
export function useCountUp(initial = 0) {
  const display = ref(initial)
  const target = ref(initial)
  let rafId = null

  watch(target, (newVal, oldVal) => {
    if (rafId) cancelAnimationFrame(rafId)
    const from = oldVal || 0
    const to = newVal || 0
    const duration = 700
    const start = performance.now()
    const step = (now) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = easeOutExpo(progress)
      display.value = Math.round(from + (to - from) * eased)
      if (progress < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        display.value = to
        rafId = null
      }
    }
    rafId = requestAnimationFrame(step)
  })

  return { display, target }
}
