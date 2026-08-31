<template>
  <NavBar title="用户管理" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <!-- 帮助说明 -->
      <div class="umg-help">
        <div class="umg-help-head" @click="showHelp = !showHelp">
          <span>权限说明</span>
          <span class="umg-help-arrow">{{ showHelp ? '▾' : '▸' }}</span>
        </div>
        <div v-if="showHelp" class="umg-help-body">
          <p><strong>超管</strong>：可访问所有管理功能，包括用户管理、公告、数据看板等。</p>
          <p><strong>管理员</strong>：可审核留言/评论/金点子、回复反馈/私信、编辑公告、查看数据看板。</p>
          <p><strong>普通用户</strong>：仅可浏览已通过的内容、发布留言/评论/金点子、提交反馈、发私信。</p>
        </div>
      </div>

      <!-- 只读模式提示 -->
      <div v-if="!authStore.isSuperAdmin" class="umg-readonly-tip">
        仅超级管理员可修改用户角色，你当前为只读模式。
      </div>

      <!-- 主选项卡：已注册用户 / 全部成员（通讯录） -->
      <div class="umg-main-tabs">
        <div
          class="umg-main-tab"
          :class="{ active: currentMainTab === 'registered' }"
          @click="switchMainTab('registered')"
        >已注册用户</div>
        <div
          class="umg-main-tab"
          :class="{ active: currentMainTab === 'all' }"
          @click="switchMainTab('all')"
        >全部成员</div>
      </div>

      <!-- 通讯录拉取错误提示 -->
      <div v-if="currentMainTab === 'all' && wecomError" class="umg-error-tip">
        ⚠️ {{ wecomError }}
      </div>

      <!-- 搜索 -->
      <div class="umg-search">
        <input
          v-if="currentMainTab === 'registered'"
          v-model="keyword"
          class="umg-search-input"
          placeholder="搜索用户名或部门..."
        />
        <input
          v-else
          v-model="wecomKeyword"
          class="umg-search-input"
          placeholder="搜索成员姓名或部门..."
        />
      </div>

      <!-- 筛选 -->
      <div class="umg-filter-tabs">
        <div
          v-for="r in roleFilters"
          :key="r.value"
          class="umg-filter-tab"
          :class="{ active: currentRoleFilter === r.value }"
          @click="currentRoleFilter = r.value"
        >{{ r.label }}</div>
      </div>

      <!-- 用户列表 -->
      <div v-if="loading" class="empty-state">
        <div class="empty-state-icon">⏳</div>
        <div class="empty-state-text">加载中...</div>
      </div>
      <template v-else>
        <!-- 已注册用户列表 -->
        <template v-if="currentMainTab === 'registered'">
          <div v-if="filteredUsers.length === 0" class="empty-state">
            <div class="empty-state-icon">👤</div>
            <div class="empty-state-text">暂无用户</div>
          </div>
          <div
            v-for="u in filteredUsers"
            :key="u.id"
            class="umg-user-row"
          >
            <div class="umg-user-left">
              <div class="umg-avatar">{{ (u.nickname || u.name || '?').charAt(0) }}</div>
              <div class="umg-user-info">
                <div class="umg-user-name">
                  {{ u.nickname || u.name || '匿名用户' }}
                  <span v-if="u.is_self" class="umg-self-tag">我</span>
                </div>
                <div class="umg-user-dept">{{ u.department || '未填写部门' }}</div>
              </div>
            </div>
            <span class="role-badge" :class="'role-' + (u.role || 'user')">{{ roleLabel(u.role) }}</span>
            <button
              v-if="authStore.isSuperAdmin && !u.is_self"
              class="admin-btn"
              style="padding:6px 14px;font-size:12px;margin-left:8px;"
              @click="openRolePanel(u)"
            >角色</button>
          </div>
        </template>

        <!-- 全部成员（通讯录）占位：功能开发中 -->
        <template v-else>
          <div class="empty-state">
            <div class="empty-state-icon">🚧</div>
            <div class="empty-state-text">功能正在开发，尽情期待</div>
          </div>
        </template>
      </template>
    </div>

    <!-- 角色操作面板 -->
    <div v-if="rolePanel.show" class="umg-mask" @click.self="closeRolePanel">
      <div class="umg-role-panel">
        <div class="umg-role-panel-title">修改用户角色</div>
        <div class="umg-role-panel-user">{{ rolePanel.user ? (rolePanel.user.nickname || rolePanel.user.name) : '' }}</div>
        <div class="umg-role-options">
          <div
            v-for="r in roleOptions"
            :key="r.value"
            class="umg-role-opt"
            :class="{ active: selectedRole === r.value, danger: r.value === 'super_admin' }"
            @click="selectedRole = r.value"
          >
            <div class="umg-role-opt-main">
              <span>{{ r.label }}</span>
              <span v-if="rolePanel.user && rolePanel.user.role === r.value" class="umg-role-opt-cur">当前</span>
            </div>
            <div class="umg-role-opt-desc">{{ r.desc }}</div>
          </div>
        </div>
        <button
          class="form-submit"
          style="margin-bottom:10px;"
          :class="{ loading: rolePanel.submitting }"
          @click="confirmRole"
        >{{ rolePanel.submitting ? '保存中...' : '确认修改' }}</button>
        <div class="umg-role-panel-cancel" @click="closeRolePanel">取消</div>
      </div>
    </div>

    <!-- 二次确认弹窗（升超管） -->
    <div v-if="confirmPanel.show" class="umg-mask" @click.self="confirmPanel.show = false">
      <div class="umg-confirm-panel">
        <div class="umg-confirm-title">确认提升为超级管理员</div>
        <div class="umg-confirm-text">{{ confirmPanel.text }}</div>
        <div class="umg-confirm-actions">
          <button class="umg-btn umg-btn-cancel" @click="confirmPanel.show = false">取消</button>
          <button class="umg-btn umg-btn-danger" @click="confirmUpgrade">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { getAdminUsers, updateUserRole, getWecomMembers } from '@/api/admin'

const authStore = useAuthStore()
const uiStore = useUiStore()

const users = ref([])
const loading = ref(true)
const keyword = ref('')
const currentRoleFilter = ref('all')
const showHelp = ref(false)

// 主选项卡：已注册用户 / 全部成员（通讯录）
const currentMainTab = ref('registered')

// 通讯录成员状态
const wecomMembers = ref([])
const wecomLoading = ref(false)
const wecomError = ref('')
const wecomKeyword = ref('')
let wecomLoaded = false

const roleFilters = [
  { label: '全部', value: 'all' },
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
  { label: '超管', value: 'super_admin' }
]

const roleOptions = [
  { value: 'user', label: '普通用户', desc: '仅可浏览内容、发布留言/评论/金点子、反馈、私信' },
  { value: 'admin', label: '管理员', desc: '可审核内容、回复反馈/私信、编辑公告、查看看板' },
  { value: 'super_admin', label: '超级管理员', desc: '拥有所有权限，包括用户管理。请谨慎授权' }
]

// 角色面板
const rolePanel = ref({
  show: false,
  user: null,
  submitting: false
})
const selectedRole = ref('user')

// 二次确认弹窗（升超管）
const confirmPanel = ref({
  show: false,
  text: '',
  pendingUser: null,
  pendingRole: 'user'
})

// 筛选后的用户列表
const filteredUsers = computed(() => {
  let list = users.value
  // 角色筛选
  if (currentRoleFilter.value !== 'all') {
    list = list.filter((u) => (u.role || 'user') === currentRoleFilter.value)
  }
  // 关键字搜索
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((u) => {
      const name = (u.nickname || u.name || '').toLowerCase()
      const dept = (u.department || '').toLowerCase()
      return name.indexOf(kw) !== -1 || dept.indexOf(kw) !== -1
    })
  }
  return list
})

// 筛选后的通讯录成员
const filteredWecomMembers = computed(() => {
  let list = wecomMembers.value
  // 角色筛选
  if (currentRoleFilter.value !== 'all') {
    list = list.filter((m) => (m.role || 'user') === currentRoleFilter.value)
  }
  // 关键字搜索
  const kw = wecomKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((m) => {
      const name = (m.name || '').toLowerCase()
      const dept = (m.department || '').toLowerCase()
      return name.indexOf(kw) !== -1 || dept.indexOf(kw) !== -1
    })
  }
  return list
})

// 切换主选项卡
function switchMainTab(tab) {
  if (currentMainTab.value === tab) return
  currentMainTab.value = tab
  // 全部成员（通讯录）功能开发中，暂不触发拉取；loadWecomMembers 保留备用
  // if (tab === 'all' && !wecomLoaded) {
  //   loadWecomMembers()
  // }
}

// 拉取企业微信通讯录成员
async function loadWecomMembers() {
  if (wecomLoading.value) return
  wecomLoading.value = true
  wecomError.value = ''
  try {
    const res = await getWecomMembers()
    wecomMembers.value = (res && res.members) || []
    if (res && res.error) {
      wecomError.value = res.error
    }
    wecomLoaded = true
  } catch (e) {
    wecomError.value = (e && e.message) || '拉取通讯录失败'
  } finally {
    wecomLoading.value = false
  }
}

// 角色标签
function roleLabel(role) {
  if (role === 'super_admin') return '超管'
  if (role === 'admin') return '管理员'
  return '用户'
}

// 打开角色面板
function openRolePanel(u) {
  rolePanel.value.show = true
  rolePanel.value.user = u
  selectedRole.value = u.role || 'user'
}

function closeRolePanel() {
  rolePanel.value.show = false
  rolePanel.value.user = null
}

// 确认修改角色
async function confirmRole() {
  if (rolePanel.value.submitting) return
  const u = rolePanel.value.user
  if (!u) return
  const newRole = selectedRole.value
  if (newRole === (u.role || 'user')) {
    uiStore.showToast('角色未变化')
    closeRolePanel()
    return
  }
  // 升超管需二次确认
  if (newRole === 'super_admin') {
    confirmPanel.value = {
      show: true,
      text: '即将把 "' + (u.nickname || u.name) + '" 提升为超级管理员。\n该用户将获得包括用户管理在内的所有权限，且无法被其他管理员降级。\n\n确认继续？',
      pendingUser: u,
      pendingRole: newRole
    }
    return
  }
  await doUpdateRole(u, newRole)
}

// 二次确认升超管
async function confirmUpgrade() {
  confirmPanel.value.show = false
  await doUpdateRole(confirmPanel.value.pendingUser, confirmPanel.value.pendingRole)
}

// 执行角色更新
async function doUpdateRole(u, newRole) {
  rolePanel.value.submitting = true
  // 未注册成员（通讯录中）用 wecom_user_id 作为目标；已注册用户用数据库 id
  const targetId = u.id || u.userid
  const needPreset = u.id ? false : true
  try {
    await updateUserRole(targetId, { role: newRole, nickname: u.name || u.userid })
    u.role = newRole
    // 预设角色成功的未注册成员标记为已注册（后续登录会自动匹配）
    if (needPreset) {
      u.registered = true
      u.id = u.userid
    }
    uiStore.showToast('角色已更新')
    closeRolePanel()
    // 若在"全部成员"下修改了角色，同步刷新已注册列表
    if (currentMainTab.value === 'all') {
      try {
        const res = await getAdminUsers()
        users.value = (res && res.users) || []
      } catch (e) {}
    }
  } catch (e) {
    uiStore.showToast('更新失败：' + e.message)
  } finally {
    rolePanel.value.submitting = false
  }
}

onMounted(async () => {
  try {
    const res = await getAdminUsers()
    users.value = (res && res.users) || []
  } catch (e) {
    uiStore.showToast('加载用户列表失败：' + e.message)
  } finally {
    loading.value = false
  }
})
</script>
