<template>
  <div class="tool-card" :style="{ borderLeftColor: stripeColor }" @click="toggleExpand">
    <div class="tool-card-header">
      <span class="tool-card-name">{{ formatToolName(item.name) }}</span>
      <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div v-if="item.name === 'task'" v-show="!item._expanded" class="tool-card-preview tool-card-preview-md" v-html="renderMd(taskPreviewMd(item))"></div>
    <div v-if="item._expanded" class="tool-card-body">
      <div v-if="item.input && item.name !== 'task'" class="card-section">
        <div class="card-label">参数</div>
        <pre class="card-pre">{{ item.input }}</pre>
      </div>
      <!-- write_todos 特殊渲染：列表形式 -->
      <div v-if="isTodos(item)" class="todo-mini-list">
        <div v-for="(t, ti) in parseTodos(item)" :key="ti" class="todo-mini-item" :class="t.status">
          <span class="todo-mini-dot">{{ t.status === 'completed' ? '✓' : t.status === 'in_progress' ? '●' : '○' }}</span>
          <span>{{ t.content }}</span>
        </div>
      </div>
      <!-- task 工具：result 已是纯净 Markdown，直接渲染 -->
      <div v-else-if="item.name === 'task' && item.result" class="text-content" v-html="renderMd(item.result)"></div>
      <!-- 通用：原始 JSON -->
      <div v-else-if="item.result != null" class="card-section">
        <pre class="card-pre">{{ fmtResult(item.result) }}</pre>
      </div>
      <div v-else class="card-empty">等待结果...</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  sessionId: { type: String, default: '' },
  renderMd: { type: Function, required: true },
  isTodos: { type: Function, required: true },
  parseTodos: { type: Function, required: true },
  parseTaskMd: { type: Function, required: true },
  taskPreviewMd: { type: Function, required: true },
  formatToolName: { type: Function, required: true },
  fmtResult: { type: Function, required: true },
})

const emit = defineEmits(['toggle'])

function toggleExpand() {
  emit('toggle')
}

// 左侧色条 — 根据工具类型分类
const stripeColor = computed(() => {
  const name = (props.item?.name || '').toLowerCase()
  const dataTools = ['load_csv', 'load_excel', 'load-data', 'read_file', 'read-file', 'ls', 'list_files']
  const codeTools = ['execute_python', 'run_python', 'write_file', 'write-file']
  const agentTools = ['task', 'data-analyst']

  if (dataTools.includes(name)) return 'var(--color-primary)'
  if (codeTools.includes(name)) return 'var(--color-success)'
  if (agentTools.includes(name)) return '#8B5CF6'
  return 'var(--color-text-muted)'
})
</script>

<style scoped>
.tool-card {
  margin: 8px auto;
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-text-muted);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  overflow: hidden;
  max-width: var(--chat-max-width);
  width: calc(100% - var(--spacing-2xl) * 2);
  transition: all var(--transition-fast);
}
.tool-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
.tool-card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
}
.tool-card-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-base);
}
.tool-card-chevron {
  flex-shrink: 0;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}
.tool-card-chevron.expanded {
  transform: rotate(180deg);
}
.tool-card-preview {
  padding: 0 var(--spacing-md) var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.tool-card-preview-md {
  white-space: normal;
  max-height: 4.2em;
  overflow: hidden;
  font-family: inherit;
  line-height: 1.6;
  font-size: var(--font-size-base);
}
.tool-card-body {
  padding: 0 var(--spacing-md) var(--spacing-md);
  border-top: 1px solid #D1D5DB;
}
.card-section {
  margin-top: var(--spacing-sm);
}
.card-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-xs);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.card-pre {
  font-size: var(--font-size-sm);
  background: #FAFBFC;
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-text-secondary);
  font-family: 'JetBrains Mono', monospace;
}
.card-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--spacing-md);
}
/* write_todos mini list */
.todo-mini-list {
  padding: var(--spacing-sm) 0;
}
.todo-mini-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 3px 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.todo-mini-dot {
  min-width: 14px;
  text-align: center;
  font-size: var(--font-size-xs);
}
.todo-mini-item.completed {
  color: var(--color-text-muted);
  text-decoration: line-through;
}
.todo-mini-item.in_progress {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}
.todo-mini-item.in_progress .todo-mini-dot {
  color: var(--color-secondary);
}
/* deep markdown selectors for preview */
.tool-card-preview-md :deep(p) { margin: 0 0 2px; }
.tool-card-preview-md :deep(em) { color: var(--color-text-muted); font-size: var(--font-size-xs); }
.tool-card-preview-md :deep(code) { font-size: 0.9em; background: transparent; }
.tool-card-preview-md :deep(pre) { display: none; }
.tool-card-preview-md :deep(h1),
.tool-card-preview-md :deep(h2),
.tool-card-preview-md :deep(h3) { font-size: var(--font-size-base); margin: 0; font-weight: var(--font-weight-medium); }
.tool-card-preview-md :deep(ul),
.tool-card-preview-md :deep(ol) { padding-left: var(--spacing-lg); margin: 2px 0; }
.tool-card-preview-md :deep(li) { margin: 0; }
.text-content {
  font-size: var(--font-size-md);
  word-break: break-word;
}
/* markdown rendering (工具卡片内 task 结果) */
.text-content :deep(p) { margin-bottom: var(--spacing-md); }
.text-content :deep(p:last-child) { margin-bottom: 0; }
.text-content :deep(code) { background: var(--color-bg-muted); padding: 2px 6px; border-radius: var(--radius-sm); font-size: 0.9em; color: var(--color-secondary); font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace; }
.text-content :deep(pre) { background: #1a1a2e; color: #e2e8f0; padding: var(--spacing-lg); border-radius: var(--radius-lg); overflow-x: auto; margin: var(--spacing-md) 0; font-size: var(--font-size-base); }
.text-content :deep(pre code) { background: transparent; color: inherit; padding: 0; font-size: inherit; }
.text-content :deep(table) { border-collapse: collapse; width: 100%; margin: var(--spacing-md) 0; font-size: var(--font-size-base); }
.text-content :deep(th), .text-content :deep(td) { border: 1px solid var(--color-border); padding: var(--spacing-sm) var(--spacing-md); text-align: left; }
.text-content :deep(th) { background: var(--color-bg-muted); font-weight: var(--font-weight-semibold); color: var(--color-text-secondary); }
.text-content :deep(tr:hover td) { background: var(--color-bg-muted); }
.text-content :deep(blockquote) { border-left: 3px solid var(--color-border); padding-left: var(--spacing-md); color: var(--color-text-secondary); margin: var(--spacing-md) 0; }
.text-content :deep(ul), .text-content :deep(ol) { padding-left: var(--spacing-xl); margin-bottom: var(--spacing-md); }
.text-content :deep(li) { margin-bottom: var(--spacing-xs); }
.text-content :deep(a) { color: var(--color-secondary); text-decoration: none; }
.text-content :deep(a:hover) { text-decoration: underline; }
.text-content :deep(h1), .text-content :deep(h2), .text-content :deep(h3) { color: var(--color-text); margin-top: var(--spacing-xl); margin-bottom: var(--spacing-sm); font-weight: var(--font-weight-semibold); }
.text-content :deep(hr) { border: none; border-top: 1px solid var(--color-border-light); margin: var(--spacing-xl) 0; }
.text-content :deep(img) { max-width: 100%; max-height: 360px; border-radius: var(--radius-md); border: 1px solid var(--color-border-light); margin: var(--spacing-sm) 0; }
</style>
