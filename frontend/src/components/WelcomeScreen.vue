<template>
  <div class="welcome-hint">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="welcome-icon">
      <path d="M21 21H3v-4a2 2 0 012-2h14a2 2 0 012 2v4z"/>
      <path d="M7 15V9a5 5 0 0110 0v6"/>
      <circle cx="12" cy="6" r="2"/>
    </svg>
    <h2>数据分析 Agent</h2>
    <p>上传 CSV / Excel 文件，用自然语言进行数据分析</p>
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
  padding: 0 var(--spacing-lg) var(--spacing-xl);
}
.welcome-icon {
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-lg);
}
.welcome-hint h2 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  margin-bottom: var(--spacing-xs);
}
.welcome-hint p {
  font-size: var(--font-size-md);
  color: var(--color-text-muted);
  max-width: 360px;
  line-height: 1.6;
}
</style>
