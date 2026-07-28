<template>
  <div class="welcome-hint">
    <!-- 主图标：64px，渐变填充的图表/分析图标 -->
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" class="welcome-icon">
      <defs>
        <linearGradient id="icon-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" style="stop-color:var(--color-primary)" />
          <stop offset="100%" style="stop-color:var(--color-primary-hover)" />
        </linearGradient>
      </defs>
      <!-- 柱状图 — 三根圆角柱 -->
      <rect x="8" y="22" width="10" height="30" rx="3" fill="url(#icon-gradient)" />
      <rect x="22" y="12" width="10" height="40" rx="3" fill="url(#icon-gradient)" />
      <rect x="36" y="18" width="10" height="34" rx="3" fill="url(#icon-gradient)" />
      <!-- 基线 -->
      <line x1="3" y1="52" x2="50" y2="52" stroke="var(--color-text-muted)" stroke-width="1.5" opacity="0.3" stroke-linecap="round" />
      <!-- 趋势折线 + 数据点 -->
      <polyline points="46,30 54,20 62,10" stroke="url(#icon-gradient)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="62" cy="10" r="4" fill="url(#icon-gradient)" />
    </svg>

    <h2>数据分析 Agent</h2>
    <p>上传 CSV / Excel 文件，用自然语言进行数据分析</p>

    <!-- 快速引导卡片 -->
    <div class="quick-start-cards">
      <div class="quick-card">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17,8 12,3 7,8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <span>上传数据文件</span>
      </div>

      <div class="quick-card">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          <line x1="8" y1="9" x2="16" y2="9" />
          <line x1="8" y1="13" x2="14" y2="13" />
        </svg>
        <span>输入分析需求</span>
      </div>

      <div class="quick-card">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12V20" />
          <path d="M12 6V20" />
          <path d="M19 10V20" />
          <line x1="2" y1="20" x2="22" y2="20" stroke="var(--color-text-muted)" stroke-width="1" />
        </svg>
        <span>获取分析结果</span>
      </div>
    </div>
  </div>
</template>

<script setup>
// 纯展示组件，无需逻辑
</script>

<style scoped>
.welcome-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-top: 10vh;
}

.welcome-icon {
  margin-bottom: var(--spacing-xl);
}

.welcome-hint h2 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text);
  margin-bottom: var(--spacing-sm);
}

.welcome-hint p {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
  max-width: 420px;
  line-height: var(--line-height);
}

/* ───── 快速引导卡片 ───── */
.quick-start-cards {
  display: flex;
  gap: var(--spacing-md);
  justify-content: center;
  margin-top: var(--spacing-2xl);
  flex-wrap: wrap;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: default;
  transition: box-shadow var(--transition-base), border-color var(--transition-base);
}

.quick-card:hover {
  box-shadow: var(--shadow-md);
  border-color: rgba(57, 100, 254, 0.25);
}

.quick-card span {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  white-space: nowrap;
}
</style>
