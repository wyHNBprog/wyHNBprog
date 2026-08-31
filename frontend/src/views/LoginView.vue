<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo -->
      <div class="login-logo">
        <div class="login-logo-circle">N</div>
        <div class="login-logo-text">NNIT 论坛</div>
        <div class="login-logo-sub">OPEN & HONEST</div>
      </div>

      <!-- 企微登录按钮 -->
      <div class="login-actions">
        <button class="login-btn wecom-btn" @click="authStore.wecomLogin" :disabled="authStore.loading">
          <span v-if="authStore.loading" class="login-spinner"></span>
          <span v-else>💬</span>
          企业微信登录
        </button>
        <div class="login-hint">使用企业微信账号授权登录</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f5f0 0%, #e8e8e0 100%);
  padding: 20px;
}
.login-card {
  background: #fff;
  border-radius: 20px;
  padding: 40px 32px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  text-align: center;
}
.login-logo {
  margin-bottom: 36px;
}
.login-logo-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #7B9E87;
  color: #fff;
  font-size: 32px;
  font-weight: 700;
  line-height: 64px;
  margin: 0 auto 12px;
}
.login-logo-text {
  font-size: 20px;
  font-weight: 700;
  color: #333;
}
.login-logo-sub {
  font-size: 12px;
  color: #999;
  letter-spacing: 2px;
  margin-top: 4px;
}
.login-actions {
  margin-bottom: 24px;
}
.login-btn {
  width: 100%;
  height: 48px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: opacity 0.2s, transform 0.1s;
}
.login-btn:active {
  transform: scale(0.98);
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.wecom-btn {
  background: #07C160;
  color: #fff;
}
.login-hint {
  font-size: 12px;
  color: #999;
  margin-top: 10px;
}
.login-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
