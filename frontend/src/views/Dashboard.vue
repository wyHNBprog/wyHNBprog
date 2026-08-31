<template>
  <NavBar title="数据看板" :show-home="true" />
  <div class="page">
    <div class="page-container">
      <div v-if="loading" class="empty-state">
        <div class="empty-state-icon">⏳</div>
        <div class="empty-state-text">加载中...</div>
      </div>
      <template v-else-if="stats">
        <!-- KPI -->
        <div class="dash-kpis">
          <div class="dash-kpi">
            <div class="dash-kpi-num">{{ stats.voices?.total || 0 }}</div>
            <div class="dash-kpi-label">留言总数</div>
            <div class="dash-kpi-sub">已通过 {{ stats.voices?.approved || 0 }} · 待审 {{ stats.voices?.pending || 0 }} · 已驳回 {{ stats.voices?.rejected || 0 }}</div>
          </div>
          <div class="dash-kpi">
            <div class="dash-kpi-num">{{ stats.ideas?.total || 0 }}</div>
            <div class="dash-kpi-label">金点子总数</div>
            <div class="dash-kpi-sub">已发布 {{ stats.ideas?.voting || 0 }} · 待审 {{ stats.ideas?.pending || 0 }} · 已驳回 {{ stats.ideas?.rejected || 0 }}</div>
          </div>
          <div class="dash-kpi">
            <div class="dash-kpi-num">{{ stats.comments?.total || 0 }}</div>
            <div class="dash-kpi-label">评论总数</div>
            <div class="dash-kpi-sub">已通过 {{ stats.comments?.approved || 0 }} · 待审 {{ stats.comments?.pending || 0 }}</div>
          </div>
          <div class="dash-kpi">
            <div class="dash-kpi-num">{{ stats.users?.active || 0 }}</div>
            <div class="dash-kpi-label">活跃用户</div>
            <div class="dash-kpi-sub">总用户 {{ stats.users?.total || 0 }}</div>
          </div>
        </div>

        <!-- 内容数据对比 -->
        <div class="dash-section">
          <div class="dash-section-title">📊 内容数据对比</div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">留言</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill a" :style="{ width: pct(stats.voices?.total || 0, stats.voices?.total || 0, stats.ideas?.total || 0, stats.comments?.total || 0) + '%' }">{{ stats.voices?.total || 0 }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">金点子</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill b" :style="{ width: pct(stats.ideas?.total || 0, stats.voices?.total || 0, stats.ideas?.total || 0, stats.comments?.total || 0) + '%' }">{{ stats.ideas?.total || 0 }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">评论</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill c" :style="{ width: pct(stats.comments?.total || 0, stats.voices?.total || 0, stats.ideas?.total || 0, stats.comments?.total || 0) + '%' }">{{ stats.comments?.total || 0 }}</div>
            </div>
          </div>
        </div>

        <!-- 金点子状态分布 -->
        <div class="dash-section">
          <div class="dash-section-title">💡 金点子状态分布</div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">已发布</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill a" :style="{ width: pct(stats.ideas?.voting || 0, stats.ideas?.total || 0) + '%' }">{{ stats.ideas?.voting || 0 }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">待审核</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill d" :style="{ width: pct(stats.ideas?.pending || 0, stats.ideas?.total || 0) + '%' }">{{ stats.ideas?.pending || 0 }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">已驳回</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill c" :style="{ width: pct(stats.ideas?.rejected || 0, stats.ideas?.total || 0) + '%' }">{{ stats.ideas?.rejected || 0 }}</div>
            </div>
          </div>
        </div>

        <!-- 互动数据 -->
        <div class="dash-section">
          <div class="dash-section-title">❤ 互动数据</div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">点赞</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill a" :style="{ width: pct(totalLikes, totalLikes, totalVotes, totalFlowers, totalFireworks) + '%' }">{{ totalLikes }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">金点子赞</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill b" :style="{ width: pct(totalVotes, totalLikes, totalVotes, totalFlowers, totalFireworks) + '%' }">{{ totalVotes }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">献花</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill c" :style="{ width: pct(totalFlowers, totalLikes, totalVotes, totalFlowers, totalFireworks) + '%' }">{{ totalFlowers }}</div>
            </div>
          </div>
          <div class="dash-bar-row">
            <div class="dash-bar-label">献星星</div>
            <div class="dash-bar-track">
              <div class="dash-bar-fill e" :style="{ width: pct(totalFireworks, totalLikes, totalVotes, totalFlowers, totalFireworks) + '%' }">{{ totalFireworks }}</div>
            </div>
          </div>
        </div>

        <!-- 排行榜 -->
        <div class="dash-section">
          <div class="dash-section-title">🏆 季度积分排行榜（Top 20）</div>
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">仅统计已通过 + 实名的内容</div>
          <div style="font-size:12px;color:var(--text-secondary);background:var(--bg-input);padding:8px 10px;border-radius:6px;margin-bottom:12px;line-height:1.6;">留言<strong>10分</strong>/条 · 金点子<strong>100分</strong>/条 · 获赞<strong>2分</strong>/个 · 被献花<strong>20分</strong>/条 · 被献星星<strong>50分</strong>/条</div>
          <div v-if="!stats.ranking || stats.ranking.length === 0" class="empty-state">
            <div class="empty-state-icon">🏆</div>
            <div class="empty-state-text">暂无排行榜数据</div>
          </div>
          <template v-else>
            <div
              v-for="(u, i) in stats.ranking"
              :key="i"
              style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg-card);border:1px solid var(--border-color);border-radius:10px;margin-bottom:8px;"
              :style="u.isMe ? { background: 'var(--accent-dim)', border: '1px solid var(--accent)' } : {}"
            >
              <span style="font-size:22px;min-width:32px;text-align:center;">{{ i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : (i + 1) }}</span>
              <div style="flex:1;">
                <div style="font-size:14px;font-weight:600;">{{ u.nickname || u.name || '匿名' }} <span style="font-size:11px;color:var(--text-secondary);font-weight:400;">{{ u.department || '' }}</span></div>
                <div style="font-size:11px;color:var(--text-secondary);">{{ (u.voices || 0) + '条留言 · ' + (u.ideas || 0) + '金点子 · 获赞' + (u.total_likes || 0) }}</div>
              </div>
              <div style="font-size:20px;font-weight:700;color:var(--accent);">{{ u.score || 0 }}</div>
            </div>
          </template>
        </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-state-icon">📊</div>
        <div class="empty-state-text">暂无数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import NavBar from '@/components/NavBar.vue'
import { getAdminStats } from '@/api/admin'
import { pct } from '@/utils/format'

const stats = ref(null)
const loading = ref(true)

const totalLikes = computed(() => stats.value?.engagement?.totalLikes || 0)
const totalVotes = computed(() => stats.value?.engagement?.totalVotes || 0)
const totalFlowers = computed(() => stats.value?.engagement?.totalFlowers || 0)
const totalFireworks = computed(() => stats.value?.engagement?.totalFireworks || 0)

onMounted(async () => {
  try {
    stats.value = await getAdminStats()
  } catch (e) {
    console.error('加载看板失败：', e)
  } finally {
    loading.value = false
  }
})
</script>
