/**
 * 性能优化 composables
 * 集成 VueUse + GSAP + vue-virtual-scroller
 */
import { ref, watch, nextTick } from 'vue'
import { useDebounceFn, useIntersectionObserver, useScroll, useElementSize } from '@vueuse/core'
import { gsap } from 'gsap'

/**
 * 防抖搜索
 */
export function useDebouncedSearch(delay = 300) {
  const keyword = ref('')
  const debouncedKeyword = ref('')

  const debouncedUpdate = useDebounceFn((val) => {
    debouncedKeyword.value = val
  }, delay)

  watch(keyword, (val) => debouncedUpdate(val))

  return { keyword, debouncedKeyword }
}

/**
 * 无限滚动加载
 */
export function useInfiniteScroll(loadMore, options = {}) {
  const { threshold = 100, hasMore = ref(true) } = options
  const loading = ref(false)
  const sentinel = ref(null)

  const { stop } = useIntersectionObserver(
    sentinel,
    async ([{ isIntersecting }]) => {
      if (isIntersecting && hasMore.value && !loading.value) {
        loading.value = true
        try {
          await loadMore()
        } finally {
          loading.value = false
        }
      }
    },
    { rootMargin: `${threshold}px` }
  )

  return { sentinel, loading, stop }
}

/**
 * GSAP 入场动画
 */
export function useEnterAnimation(options = {}) {
  const { duration = 0.3, y = 20, stagger = 0.05, ease = 'power2.out' } = options
  const container = ref(null)

  function play() {
    nextTick(() => {
      if (!container.value) return
      const items = container.value.children
      if (items.length === 0) return
      gsap.from(items, {
        duration,
        y,
        opacity: 0,
        stagger,
        ease,
      })
    })
  }

  return { container, play }
}

/**
 * GSAP 数字滚动动画（比 v-count-up 更流畅）
 */
export function useCountUp(targetRef, options = {}) {
  const { duration = 1.2, ease = 'expo.out' } = options
  const displayValue = ref(0)

  watch(targetRef, (newVal) => {
    if (typeof newVal !== 'number') return
    const obj = { val: displayValue.value }
    gsap.to(obj, {
      val: newVal,
      duration,
      ease,
      onUpdate: () => {
        displayValue.value = Math.round(obj.val)
      },
    })
  })

  return displayValue
}

/**
 * 乐观更新工具
 */
export function useOptimisticUpdate() {
  /**
   * 执行乐观更新
   * @param {Function} updateFn 本地状态更新函数
   * @param {Function} apiFn API 调用函数
   * @param {Function} rollbackFn 回滚函数
   */
  async function optimisticUpdate(updateFn, apiFn, rollbackFn) {
    // 1. 立即更新 UI
    updateFn()
    try {
      // 2. 调用 API
      await apiFn()
    } catch (err) {
      // 3. API 失败时回滚
      if (rollbackFn) rollbackFn()
      throw err
    }
  }

  return { optimisticUpdate }
}

/**
 * 平滑滚动到底部（聊天场景）
 */
export function useSmoothScrollToBottom() {
  const container = ref(null)

  function scrollToBottom() {
    nextTick(() => {
      if (!container.value) return
      gsap.to(container.value, {
        scrollTop: container.value.scrollHeight,
        duration: 0.3,
        ease: 'power2.out',
      })
    })
  }

  return { container, scrollToBottom }
}
