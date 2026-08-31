import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'

import App from './App.vue'
import router from './router'
import './assets/style.css'
import { vCountUp as countUp } from './directives/countUp'
import { vLongPress as longpress } from './directives/longpress'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000,      // 30秒内不重复请求
        refetchOnWindowFocus: true, // 窗口聚焦时刷新
        retry: 1,
      },
    },
  },
})
app.use(VueVirtualScroller)
app.directive('count-up', countUp)
app.directive('longpress', longpress)

// Service Worker 由 VitePWA 插件自动注册（registerType: 'autoUpdate'），无需手动注册

app.mount('#app')
