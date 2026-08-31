import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// ========== 路由配置 ==========
// 所有页面注册为路由，需要管理员权限的页面加路由守卫
// 使用 hash 模式（兼容静态部署）

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/Home.vue'),
    meta: { title: 'NNIT 论坛', showTabBar: true }
  },
  {
    path: '/voice-list',
    name: 'voice-list',
    component: () => import('@/views/VoiceList.vue'),
    meta: { title: '留言墙' }
  },
  {
    path: '/voice-detail/:id',
    name: 'voice-detail',
    component: () => import('@/views/VoiceDetail.vue'),
    meta: { title: '留言详情' }
  },
  {
    path: '/idea-submit',
    name: 'idea-submit',
    component: () => import('@/views/IdeaSubmit.vue'),
    meta: { title: '提交金点子' }
  },
  {
    path: '/idea-review',
    name: 'idea-review',
    component: () => import('@/views/IdeaReview.vue'),
    meta: { title: '金点子评审', requireAdmin: true }
  },
  {
    path: '/comment-review',
    name: 'comment-review',
    component: () => import('@/views/CommentReview.vue'),
    meta: { title: '评论审核', requireAdmin: true }
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/views/Review.vue'),
    meta: { title: '留言审核', requireAdmin: true }
  },
  {
    path: '/feedback-list',
    name: 'feedback-list',
    component: () => import('@/views/FeedbackList.vue'),
    meta: { title: '反馈列表' }
  },
  {
    path: '/feedback-detail/:id',
    name: 'feedback-detail',
    component: () => import('@/views/FeedbackDetail.vue'),
    meta: { title: '反馈详情' }
  },
  {
    path: '/feedback-submit',
    name: 'feedback-submit',
    component: () => import('@/views/FeedbackSubmit.vue'),
    meta: { title: '提交反馈' }
  },
  {
    path: '/message-send',
    name: 'message-send',
    component: () => import('@/views/MessageSend.vue'),
    meta: { title: '私信管理员' }
  },
  {
    path: '/message-admin',
    name: 'message-admin',
    component: () => import('@/views/MessageAdmin.vue'),
    meta: { title: '私信管理', requireAdmin: true }
  },
  {
    path: '/announce-view',
    name: 'announce-view',
    component: () => import('@/views/AnnounceView.vue'),
    meta: { title: '公告查看' }
  },
  {
    path: '/announce-edit',
    name: 'announce-edit',
    component: () => import('@/views/AnnounceEdit.vue'),
    meta: { title: '编辑公告', requireAdmin: true }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '数据看板', requireAdmin: true }
  },
  {
    path: '/mine',
    name: 'mine',
    component: () => import('@/views/Mine.vue'),
    meta: { title: '我的', showTabBar: true, requiresAuth: false }
  },
  {
    path: '/notifications',
    name: 'notifications',
    component: () => import('@/views/Notifications.vue'),
    meta: { title: '通知' }
  },
  {
    path: '/my-posts',
    name: 'my-posts',
    component: () => import('@/views/MyPosts.vue'),
    meta: { title: '我的留言' }
  },
  {
    path: '/my-ideas',
    name: 'my-ideas',
    component: () => import('@/views/MyIdeas.vue'),
    meta: { title: '我的金点子' }
  },
  {
    path: '/my-comments',
    name: 'my-comments',
    component: () => import('@/views/MyComments.vue'),
    meta: { title: '我的评论' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '设置' }
  },
  {
    path: '/user-mgmt',
    name: 'user-mgmt',
    component: () => import('@/views/UserMgmt.vue'),
    meta: { title: '用户管理', requireAdmin: true, requireSuperAdmin: true }
  },
  // 404 兜底：所有未匹配路由重定向到首页
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  }
})

// ========== reLaunch：跳转到指定页（不增加历史栈）==========
// 类似小程序 reLaunch，用于提交成功、登录/登出等需要清空历史的场景
// 注意：hash 模式下无法真正清空浏览器历史栈，这里使用 replace 语义——
// 不会在历史记录中留下旧页面，用户点击返回不会回到提交前页面。
// 不再手动调用 history.replaceState，因为 replace 是异步的，同步 replaceState
// 会在导航完成前执行，破坏 Vue Router 内部状态导致竞态问题。
router.reLaunch = function (to) {
  this.replace(to)
}

// 路由守卫：检查管理员权限（异步等待 authStore 初始化完成，避免刷新时丢失权限）
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  // 设置页面标题
  if (to.meta.title) {
    document.title = to.meta.title
  }
  // 等待 authStore 初始化完成（企微启用时不会自动登录，needLogin 由 App.vue 处理）
  if (!authStore.initialized) {
    await authStore.initAuth()
  }
  // 登录态拦截：企微启用且未登录时，阻止访问需要登录的页面（受保护页面统一回到 mine，由 App.vue 显示登录页）
  if (!authStore.isLoggedIn && to.meta.requiresAuth !== false) {
    next({ name: 'mine' })
    return
  }
  // 需要管理员权限的页面
  if (to.meta.requireAdmin && !authStore.isAdmin) {
    next({ name: 'mine' })
    return
  }
  // 需要超级管理员权限的页面
  if (to.meta.requireSuperAdmin && !authStore.isSuperAdmin) {
    next({ name: 'mine' })
    return
  }
  next()
})

export default router
