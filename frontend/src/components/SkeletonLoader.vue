<template>
  <!-- 通用骨架屏组件：支持多种预设场景 -->
  <div class="skeleton-screen">
    <!-- 留言便签骨架 -->
    <template v-if="type === 'voice-sticky'">
      <div v-for="i in count" :key="i" class="skel-sticky">
        <div class="skeleton skeleton-text sm" style="width: 40%; margin-bottom: 8px;"></div>
        <div class="skeleton skeleton-text lg"></div>
        <div class="skeleton skeleton-text md"></div>
        <div style="display:flex; gap:14px; margin-top:10px;">
          <div class="skeleton" style="width:50px; height:12px;"></div>
          <div class="skeleton" style="width:40px; height:12px;"></div>
          <div class="skeleton" style="width:40px; height:12px;"></div>
        </div>
      </div>
    </template>

    <!-- 留言卡片骨架（列表页用） -->
    <template v-else-if="type === 'voice-card'">
      <div v-for="i in count" :key="i" class="skel-card">
        <div class="skeleton-row">
          <div class="skeleton skeleton-avatar"></div>
          <div class="skeleton skeleton-text sm" style="width: 30%; margin-bottom: 0;"></div>
          <div class="skeleton" style="width:40px; height:11px; margin-left:auto;"></div>
        </div>
        <div class="skeleton skeleton-text lg"></div>
        <div class="skeleton skeleton-text md"></div>
        <div style="display:flex; gap:16px; margin-top:10px;">
          <div class="skeleton" style="width:50px; height:13px;"></div>
          <div class="skeleton" style="width:50px; height:13px;"></div>
        </div>
      </div>
    </template>

    <!-- 金点子骨架 -->
    <template v-else-if="type === 'idea'">
      <div v-for="i in count" :key="i" class="skel-idea">
        <div class="skeleton skeleton-text sm" style="width:55%; margin-bottom:8px;"></div>
        <div class="skeleton skeleton-title" style="width:70%; margin-bottom:8px;"></div>
        <div class="skeleton skeleton-text md"></div>
        <div style="display:flex; gap:12px; margin-top:10px; align-items:center;">
          <div class="skeleton" style="width:60px; height:28px; border-radius:18px;"></div>
          <div class="skeleton" style="width:50px; height:20px; border-radius:10px;"></div>
        </div>
      </div>
    </template>

    <!-- 公告便签骨架 -->
    <template v-else-if="type === 'announce'">
      <div v-for="i in count" :key="i" class="skel-sticky" style="border-left:3px solid #C9A24B;">
        <div class="skeleton skeleton-text sm" style="width:35%; margin-bottom:8px;"></div>
        <div class="skeleton skeleton-title" style="width:75%; margin-bottom:8px;"></div>
        <div class="skeleton skeleton-text lg"></div>
        <div class="skeleton skeleton-text md"></div>
      </div>
    </template>

    <!-- 统计数字骨架 -->
    <template v-else-if="type === 'stats'">
      <div class="skel-stats">
        <div v-for="i in (count || 4)" :key="i" class="skel-stat">
          <div class="skeleton skel-stat-num"></div>
          <div class="skeleton skel-stat-label"></div>
        </div>
      </div>
    </template>

    <!-- 首页骨架（品牌头 + Tabs + 统计 + 看板） -->
    <template v-else-if="type === 'home'">
      <!-- 品牌头骨架 -->
      <div style="text-align:center; padding:16px 20px 12px;">
        <div style="display:inline-flex; align-items:center; gap:10px; margin-bottom:8px;">
          <div class="skeleton" style="width:36px; height:36px; border-radius:50%;"></div>
          <div class="skeleton" style="width:110px; height:20px;"></div>
        </div>
        <div class="skeleton" style="width:100px; height:11px; margin:0 auto;"></div>
      </div>
      <!-- Tabs 骨架 -->
      <div class="skel-tab-bar">
        <div v-for="i in 3" :key="i" class="skel-tab">
          <div class="skeleton skel-tab-icon"></div>
          <div class="skeleton skel-tab-text"></div>
        </div>
      </div>
      <!-- 统计骨架 -->
      <div style="padding:12px 16px; background:var(--bg-card); margin:0 12px; border-radius:12px;">
        <div class="skel-stats">
          <div v-for="i in 4" :key="i" class="skel-stat">
            <div class="skeleton skel-stat-num"></div>
            <div class="skeleton skel-stat-label"></div>
          </div>
        </div>
      </div>
      <!-- 看板骨架 -->
      <div style="margin:12px; padding:16px; background:var(--board-bg); border-radius:12px;">
        <div v-for="i in (count || 4)" :key="i" class="skel-sticky">
          <div class="skeleton skeleton-text sm" style="width:40%; margin-bottom:8px;"></div>
          <div class="skeleton skeleton-text lg"></div>
          <div class="skeleton skeleton-text md"></div>
        </div>
      </div>
    </template>

    <!-- 个人中心骨架 -->
    <template v-else-if="type === 'mine'">
      <!-- 用户卡片骨架 -->
      <div class="skel-user-card">
        <div class="skeleton-row" style="margin-bottom:16px;">
          <div class="skeleton skeleton-circle-lg"></div>
          <div style="flex:1;">
            <div class="skeleton" style="width:120px; height:18px; margin-bottom:8px;"></div>
            <div class="skeleton" style="width:80px; height:12px;"></div>
          </div>
        </div>
        <div class="skel-stats">
          <div v-for="i in 4" :key="i" class="skel-stat">
            <div class="skeleton skel-stat-num"></div>
            <div class="skeleton skel-stat-label"></div>
          </div>
        </div>
      </div>
      <!-- 菜单骨架 -->
      <div style="background:var(--bg-card); border-radius:12px; margin:0 16px 12px; overflow:hidden; box-shadow:var(--shadow-card);">
        <div v-for="i in (count || 6)" :key="i" class="skel-menu-item">
          <div class="skeleton skel-menu-icon"></div>
          <div class="skeleton skel-menu-line"></div>
          <div class="skeleton" style="width:12px; height:12px;"></div>
        </div>
      </div>
    </template>

    <!-- 通知列表骨架 -->
    <template v-else-if="type === 'notification'">
      <div v-for="i in count" :key="i" class="skel-card">
        <div class="skeleton-row">
          <div class="skeleton" style="width:32px; height:32px; border-radius:8px; flex-shrink:0;"></div>
          <div style="flex:1;">
            <div class="skeleton skeleton-text md" style="margin-bottom:6px;"></div>
            <div class="skeleton" style="width:50px; height:11px;"></div>
          </div>
        </div>
      </div>
    </template>

    <!-- 通用列表骨架 -->
    <template v-else>
      <div v-for="i in count" :key="i" class="skel-card">
        <div class="skeleton skeleton-row">
          <div class="skeleton skeleton-avatar"></div>
          <div class="skeleton skeleton-text sm" style="margin-bottom:0; width:40%;"></div>
        </div>
        <div class="skeleton skeleton-text lg"></div>
        <div class="skeleton skeleton-text md"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * 通用骨架屏组件
 * type: voice-sticky | voice-card | idea | announce | stats | home | mine | notification | default
 * count: 骨架项数量
 */
defineProps({
  type: { type: String, default: 'default' },
  count: { type: Number, default: 4 }
})
</script>
