<template>
  <Transition name="confirm-fade">
    <div v-if="uiStore.confirmDialog.show" class="confirm-mask" @click.self="onCancel">
      <Transition name="confirm-pop" appear>
        <div v-if="uiStore.confirmDialog.show" class="confirm-sheet">
          <div v-if="uiStore.confirmDialog.title" class="confirm-title">{{ uiStore.confirmDialog.title }}</div>
          <div class="confirm-message">{{ uiStore.confirmDialog.message }}</div>
          <div class="confirm-actions">
            <button class="confirm-btn cancel" @click="onCancel">{{ uiStore.confirmDialog.cancelText }}</button>
            <button
              class="confirm-btn ok"
              :class="{ danger: uiStore.confirmDialog.danger }"
              @click="onConfirm"
            >{{ uiStore.confirmDialog.confirmText }}</button>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<script setup>
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

function onConfirm() {
  uiStore.resolveConfirm(true)
}

function onCancel() {
  uiStore.resolveConfirm(false)
}
</script>

<style scoped>
.confirm-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.45);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 40px;
  box-sizing: border-box;
}
.confirm-sheet {
  width: 100%;
  max-width: 300px;
  background: var(--bg-card);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}
.confirm-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
  padding: 20px 20px 8px;
}
.confirm-message {
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  padding: 8px 20px 20px;
  line-height: 1.5;
}
.confirm-actions {
  display: flex;
  border-top: 1px solid var(--border-color);
}
.confirm-btn {
  flex: 1;
  padding: 14px 0;
  font-size: 16px;
  border: none;
  background: none;
  cursor: pointer;
  transition: background 0.15s;
}
.confirm-btn.cancel {
  color: var(--text-secondary);
  border-right: 1px solid var(--border-color);
}
.confirm-btn.cancel:active {
  background: var(--bg-input);
}
.confirm-btn.ok {
  color: var(--accent);
  font-weight: 600;
}
.confirm-btn.ok.danger {
  color: #e5484d;
}
.confirm-btn.ok:active {
  background: var(--bg-input);
}

/* 动画 */
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s ease;
}
.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}
.confirm-pop-enter-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease;
}
.confirm-pop-enter-from {
  transform: scale(0.85);
  opacity: 0;
}
.confirm-pop-leave-active {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.confirm-pop-leave-to {
  transform: scale(0.9);
  opacity: 0;
}
</style>
