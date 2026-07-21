<template>
  <div v-for="(item, i) in items" :key="item.id || i" :class="msgRowClass(item)">
    <!-- 错误 -->
    <div v-if="item.kind === 'error'" class="error-bar">❌ {{ item.content }}</div>

    <!-- 思考过程 -->
    <div v-else-if="item.kind === 'thinking'" class="thinking-block" @click="toggleExpand(item)">
      <div class="thinking-header">
        <span class="thinking-icon">💭</span>
        <span>思考中...</span>
        <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div v-if="item._expanded" class="thinking-body">{{ item.content }}</div>
    </div>

    <!-- 工具调用卡片 -->
    <ToolCard
      v-else-if="item.kind === 'tool_call'"
      :item="item"
      :sessionId="sessionId"
      :renderMd="renderMd"
      :isTodos="isTodos"
      :parseTodos="parseTodos"
      :parseTaskMd="parseTaskMd"
      :taskPreviewMd="taskPreviewMd"
      :formatToolName="formatToolName"
      :fmtResult="fmtResult"
      @toggle="toggleExpand(item)"
    />

    <!-- 完成标记 -->
    <div v-else-if="item.kind === 'done'" class="done-marker">✅ 分析完成</div>

    <!-- 普通消息 -->
    <template v-else>
      <div v-if="item.role !== 'user'" class="msg-avatar">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/></svg>
      </div>
      <div class="msg-body">
        <!-- 历史思考过程 -->
        <div v-if="item.thinking" class="thinking-block" @click="toggleExpand(item)">
          <div class="thinking-header">
            <span class="thinking-icon">💭</span>
            <span>思考过程</span>
            <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div v-if="item._expanded" class="thinking-body">{{ item.thinking }}</div>
        </div>
        <div class="text-content" v-html="renderMd(item.content)"></div>
      </div>
    </template>
  </div>

  <div v-if="isLoading" class="message-row assistant">
    <div class="msg-avatar">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/></svg>
    </div>
    <div class="msg-body">
      <div class="typing-indicator"><span></span><span></span><span></span></div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import { marked } from 'marked'
import ToolCard from './ToolCard.vue'

const props = defineProps({
  items: { type: Array, required: true },
  sessionId: { type: String, default: '' },
  isLoading: { type: Boolean, default: false },
})

const toggleItemExpand = inject('toggleItemExpand')

// ── Markdown 渲染 ──
function renderMd(text_) {
  const text = Array.isArray(text_)
    ? text_.map(b => (typeof b === 'string' ? b : b.text || '')).join('')
    : (text_ || '')
  let html = marked.parse(text)
  const tid = props.sessionId
  if (tid && tid !== 'new') {
    html = html.replace(/src="(?!https?:\/\/|\/api\/)([^"]*\.(?:png|jpg|jpeg|gif|svg))"/gi,
      (_, path) => `src="/api/sessions/${tid}/files/${path.replace(/^\//, '')}"`)
    html = html.replace(/href="(?!https?:\/\/|\/api\/)([^"]*\.(?:html))"/gi,
      (_, path) => `href="/api/sessions/${tid}/files/${path.replace(/^\//, '')}"`)
  }
  return html
}

// ── 消息行 class ──
function msgRowClass(item) {
  if (item.kind === 'error') return 'message-row error'
  if (item.kind === 'thinking') return 'message-row assistant'
  if (item.kind === 'done') return 'message-row assistant'
  if (item.kind === 'tool_call') return ''
  return ['message-row', item.role]
}

// ── 展开/折叠 ──
function toggleExpand(item) {
  toggleItemExpand?.(item.id)
}

// ── 工具卡片工具函数 ──
function isTodos(item) {
  return item.name === 'write_todos' && item.result
}

function parseTodos(item) {
  try {
    let raw = item.result
    // 兼容 MySQL JSON 列返回对象的情况
    if (typeof raw !== 'string') raw = JSON.stringify(raw)
    // 兼容 Python dict 格式 {'todos': [...]} 的字符串表示
    const match = raw.match(/'todos':\s*(\[[\s\S]*?\])\s*[,}]/)
    if (match) {
      const parsed = JSON.parse(match[1].replace(/'/g, '"'))
      if (Array.isArray(parsed)) return parsed
    }
    const direct = typeof item.result === 'string' ? JSON.parse(item.result) : item.result
    if (direct?.todos) return direct.todos
  } catch {}
  return []
}

function parseTaskMd(item) {
  try {
    let raw = item.result
    if (typeof raw !== 'string') raw = JSON.stringify(raw)
    let content = null
    const m1 = raw.match(/ToolMessage\(content='([\s\S]*?)'(?:,\s*tool_call_id|\))/)
    if (m1) content = m1[1]
    else {
      const m2 = raw.match(/content='([\s\S]+?)'\s*[\)\}]/)
      if (m2) content = m2[1]
    }
    if (content) {
      content = content.replace(/\\n/g, '\n').replace(/\\'/g, "'").replace(/\\"/g, '"')
      return content
    }
  } catch {
    // 静默失败
  }
  return null
}

function formatToolName(name) {
  const labels = {
    'load_csv': '读取 CSV',
    'load_excel': '读取 Excel',
    'load-data': '读取数据',
    'execute_python': '执行代码',
    'run_python': '执行代码',
    'write_file': '写入文件',
    'write-file': '写入文件',
    'read_file': '读取文件',
    'read-file': '读取文件',
    'ls': '列出文件',
    'list_files': '列出文件',
    'data-analyst': '数据分析子代理',
  }
  return labels[name] || name
}

function fmtResult(result) {
  if (typeof result === 'string') return result
  try { return JSON.stringify(result, null, 2) } catch { return String(result) }
}

function taskPreviewMd(item) {
  if (!item.result) return '子代理执行完成'
  const text = String(item.result)
  // 只取第一句话（中文到。英文到. 换行），避免与外层消息重复
  const firstLine = text.split('\n')[0].trim()
  if (firstLine.length <= 80) return firstLine
  const m = firstLine.match(/^(.+?[。.!！?？])/)
  return m ? m[1] : firstLine.slice(0, 80) + '...'
}
</script>

<style scoped>
/* ── typing indicator ── */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-muted);
  animation: typing 1.4s infinite both;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* ── messages ── */
.message-row {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-2xl);
  max-width: 800px;
  margin: 0 auto;
}
.message-row.user { flex-direction: row-reverse; }
.message-row.error { justify-content: center; }
.msg-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: var(--color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}
.msg-body { min-width: 0; flex: 1; }
.message-row.user .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.message-row.user .text-content {
  background: var(--color-bg-muted);
  color: var(--color-text);
  border-radius: var(--radius-xl);
  padding: var(--spacing-sm) var(--spacing-lg);
  max-width: 75%;
  line-height: var(--line-height);
}
.message-row:not(.user) .text-content {
  color: var(--color-text);
  padding: 0;
  line-height: 1.8;
}
.text-content {
  font-size: var(--font-size-md);
  word-break: break-word;
}

/* ── error bar ── */
.error-bar {
  text-align: center;
  padding: var(--spacing-sm) var(--spacing-lg);
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: var(--radius-md);
  color: #DC2626;
  font-size: var(--font-size-sm);
  max-width: 400px;
  margin: 0 auto;
}

/* ── done marker ── */
.done-marker {
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--spacing-sm) 0;
}

/* ── thinking block ── */
.thinking-block {
  margin-bottom: var(--spacing-sm);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: #F8FAFC;
  overflow: hidden;
  cursor: pointer;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
.thinking-icon { font-size: var(--font-size-base); }
.thinking-header .tool-card-chevron {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}
.thinking-header .tool-card-chevron.expanded { transform: rotate(180deg); }
.thinking-body {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  line-height: 1.6;
  border-top: 1px solid var(--color-border-light);
  max-height: 300px;
  overflow-y: auto;
}

/* ── markdown ── */
.text-content :deep(p) { margin-bottom: var(--spacing-md); }
.text-content :deep(p:last-child) { margin-bottom: 0; }
.text-content :deep(code) {
  background: var(--color-bg-muted);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
  color: var(--color-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}
.text-content :deep(pre) {
  background: #1a1a2e;
  color: #e2e8f0;
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  overflow-x: auto;
  margin: var(--spacing-md) 0;
  font-size: var(--font-size-base);
}
.text-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
.text-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: var(--spacing-md) 0;
  font-size: var(--font-size-base);
}
.text-content :deep(th),
.text-content :deep(td) {
  border: 1px solid var(--color-border);
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
}
.text-content :deep(th) {
  background: var(--color-bg-muted);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
}
.text-content :deep(tr:hover td) { background: var(--color-bg-muted); }
.text-content :deep(blockquote) {
  border-left: 3px solid var(--color-border);
  padding-left: var(--spacing-md);
  color: var(--color-text-secondary);
  margin: var(--spacing-md) 0;
}
.text-content :deep(ul),
.text-content :deep(ol) {
  padding-left: var(--spacing-xl);
  margin-bottom: var(--spacing-md);
}
.text-content :deep(li) { margin-bottom: var(--spacing-xs); }
.text-content :deep(a) {
  color: var(--color-secondary);
  text-decoration: none;
}
.text-content :deep(a:hover) { text-decoration: underline; }
.text-content :deep(h1),
.text-content :deep(h2),
.text-content :deep(h3) {
  color: var(--color-text);
  margin-top: var(--spacing-xl);
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-weight-semibold);
}
.text-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border-light);
  margin: var(--spacing-xl) 0;
}
.text-content :deep(img) {
  max-width: 100%;
  max-height: 360px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  margin: var(--spacing-sm) 0;
}
</style>
