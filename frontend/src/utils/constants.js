// ========== 常量定义 ==========

// 匿名默认昵称
export const ANON_NAME = 'nnit热心网友'

// 反馈分类
export const FB_CATS = ['食堂餐饮', '办公环境', 'IT设备', '制度流程', '福利待遇', '团队协作', '其他']

// 金点子分类
export const IDEA_CATS = ['产品创新', '流程优化', '技术升级', '管理创新', '文化建设', '降本增效', '其他']

// 留言标签
export const VOICE_TAGS = ['工作感悟', '吐槽一下', '建议想法', '生活分享', '技术讨论', '团队协作']

// 状态映射
export const STATUS_MAP = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  voting: '已发布'
}

// 状态徽章样式映射
export const STATUS_BADGE_CLASS = {
  approved: 'badge-green',
  rejected: 'badge-red',
  pending: 'badge-orange',
  voting: 'badge-purple'
}

// 懒加载每页条数
export const LAZY_PAGE_SIZE = 20

// 评论分页每页条数
export const COMMENT_PAGE_SIZE = 10

// loadAll 缓存有效期（30 秒）
export const LOAD_CACHE_MS = 30000

// 数据轮询间隔（60 秒，页面不可见时自动暂停）
export const POLL_INTERVAL_MS = 60000

// 积分说明（数据看板展示用）
export const POINTS_EXPLANATION = '留言10分/条 · 评论2分/条 · 点赞1分/个 · 被点赞2分/个 · 金点子20分/条 · 被献花20分/条 · 被献星星50分/条'

// 实时通信配置
export const WS_RECONNECT_INTERVAL = 3000   // WebSocket 重连间隔
export const SSE_RECONNECT_INTERVAL = 5000  // SSE 重连间隔
export const CHAT_SCROLL_THRESHOLD = 100    // 聊天滚动阈值
