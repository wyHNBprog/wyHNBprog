// ========== 工具函数 ==========

// 时间格式化：MM-DD HH:MM
// 后端存的是 naive UTC，补 'Z' 让 JS 解析为 UTC，再转本地时区展示
export function fmtTime(s) {
  if (!s) return '刚刚'
  if (typeof s !== 'string') return '刚刚'
  const iso = s.indexOf('Z') >= 0 || s.indexOf('+') >= 0 ? s : s + 'Z'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '刚刚'
  const pad = (n) => (n < 10 ? '0' + n : '' + n)
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

// 相对时间格式化（刚刚 / X 分钟前 / X 小时前 / X 天前）
export function formatTime(d) {
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return Math.floor(diff / 86400000) + '天前'
}

// 截断字符串
export function truncate(str, max) {
  if (!str) return ''
  return str.length > max ? str.substring(0, max) + '...' : str
}

// HTML 转义（防止 XSS）
export function escapeHtml(str) {
  if (str == null) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 属性转义（同 escapeHtml）
export function escapeAttr(str) {
  return escapeHtml(str)
}

// 防抖函数
export function debounce(fn, wait) {
  let timer
  return function () {
    const args = arguments
    const ctx = this
    clearTimeout(timer)
    timer = setTimeout(function () {
      fn.apply(ctx, args)
    }, wait || 300)
  }
}

// 计算柱状图百分比：val 占各比较值最大值的比例（最小 2% 保证可见）
export function pct(val, ...rest) {
  let max = 0
  for (let i = 0; i < rest.length; i++) {
    if (typeof rest[i] === 'number' && rest[i] > max) max = rest[i]
  }
  if (max <= 0) return 0
  return Math.max(2, Math.round((val / max) * 100))
}
