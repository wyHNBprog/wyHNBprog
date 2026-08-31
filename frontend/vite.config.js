import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import viteCompression from 'vite-plugin-compression'
import { fileURLToPath, URL } from 'node:url'

// Vite 配置：PWA、压缩、分包、WebSocket 代理
export default defineConfig({
  plugins: [
    vue(),
    // PWA 插件：自动更新 + 离线缓存
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'VoiceHub',
        short_name: 'VoiceHub',
        theme_color: '#0066CC',
      },
      workbox: {
        cacheId: 'voicehub-v2p05', // 版本缓存标识：每次发版递增，强制旧缓存失效
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024, // 3MB
        // 关键修复：禁止 Service Worker 接管 /wecom/ 路径的导航请求，
        // 避免企业微信 OAuth 回调被 SW 拦截导致登录死循环
        navigateFallbackDenylist: [/^\/wecom\//],
      },
    }),
    // 压缩插件：brotli + gzip
    viteCompression({
      algorithm: 'brotliCompress',
      deleteOriginFile: false,
    }),
    viteCompression({
      algorithm: 'gzip',
      deleteOriginFile: false,
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      // WebSocket 代理
      '/api/ws': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // 分包策略：vendor 独立 chunk，提升缓存命中率
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'query-vendor': ['@tanstack/vue-query'],
          'ui-vendor': ['@vueuse/core', 'vue-virtual-scroller'],
          'animation-vendor': ['gsap'],
          'axios-vendor': ['axios']
        }
      }
    }
  }
})
