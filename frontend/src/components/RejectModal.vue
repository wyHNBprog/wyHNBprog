<template>
  <div v-if="uiStore.rejectModal.show" class="modal-mask" id="reject-modal">
    <div class="modal-dialog modal-content">
      <div class="modal-header">
        <div class="modal-title">{{ uiStore.rejectModal.title }}</div>
      </div>
      <div class="modal-body">
        <div class="modal-desc">请输入驳回理由（作者可见）</div>
        <textarea
          v-model="reason"
          class="modal-input"
          style="height:80px;letter-spacing:0;text-align:left;resize:none;"
          placeholder="请输入驳回理由..."
          maxlength="200"
        ></textarea>
        <div class="modal-error">{{ error }}</div>
      </div>
      <div class="modal-footer">
        <div class="modal-btn modal-btn--cancel" @click="cancel">取消</div>
        <div class="modal-btn modal-btn--confirm" @click="confirm">确认驳回</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useDataStore } from '@/stores/data'
import { updateVoiceStatus, updateCommentStatus } from '@/api/voice'
import { updateIdeaStatus } from '@/api/idea'

const uiStore = useUiStore()
const dataStore = useDataStore()

const reason = ref('')
const error = ref('')

// 监听弹窗打开/关闭，重置表单
watch(
  () => uiStore.rejectModal.show,
  (show) => {
    if (show) {
      reason.value = ''
      error.value = ''
    }
  }
)

function cancel() {
  uiStore.closeRejectModal()
}

// 确认驳回
async function confirm() {
  const r = reason.value.trim()
  if (!r) {
    error.value = '请输入驳回理由'
    return
  }
  error.value = ''

  const m = uiStore.rejectModal
  try {
    if (m.voiceId) {
      // 驳回留言
      await updateVoiceStatus(m.voiceId, { status: 'rejected', rejectReason: r })
      const v = dataStore.findVoiceById(m.voiceId)
      if (v) {
        v.status = 'rejected'
        v.rejectReason = r
      }
      uiStore.closeRejectModal()
      uiStore.showToast('已驳回')
    } else if (m.ideaId) {
      // 驳回金点子
      await updateIdeaStatus(m.ideaId, { status: 'rejected', rejectReason: r })
      const found = dataStore.findIdeaById(m.ideaId)
      if (found) {
        found.idea.status = 'rejected'
        found.idea.rejectReason = r
      }
      uiStore.closeRejectModal()
      uiStore.showToast('已驳回')
    } else if (m.commentInfo) {
      // 驳回评论
      const { voiceId, commentId } = m.commentInfo
      await updateCommentStatus(voiceId, commentId, { status: 'rejected', rejectReason: r })
      const v = dataStore.findVoiceById(voiceId)
      if (v) {
        const c = (v.comments || []).find((x) => x.id === commentId)
        if (c) {
          c.status = 'rejected'
          c.rejectReason = r
        }
        v.commentCount = v.comments.filter((x) => x.status === 'approved').length
      }
      uiStore.closeRejectModal()
      uiStore.showToast('已驳回')
    }
  } catch (e) {
    // 409 并发冲突：其他管理员已审核
    if (e && e.status === 409) {
      uiStore.showToast('该内容已被其他管理员审核')
      uiStore.closeRejectModal()
      await dataStore.loadAll(true)
    } else {
      uiStore.showToast('操作失败：' + e.message)
    }
  }
}
</script>
