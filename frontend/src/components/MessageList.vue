<template>
  <div v-for="(item, i) in items" :key="item.id || i" :class="msgRowClass(item)">
    <!-- ── 错误 ── -->
    <div v-if="item.kind === 'error'" class="error-bar">
      <svg class="error-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>{{ item.content }}</span>
    </div>

    <!-- ── 思考过程（独立） ── -->
    <template v-else-if="item.kind === 'thinking'">
      <div class="msg-avatar assistant-avatar">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="8" r="4"/>
          <path d="M4 20c0-4 4-7 8-7s8 3 8 7"/>
        </svg>
      </div>
      <div class="msg-body">
        <div class="thinking-block" @click="toggleExpand(item)">
          <div class="thinking-header">
            <!-- Brain 图标 -->
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="thinking-brain-icon">
              <path d="M12 4a4 4 0 0 1 3.5 2 4 4 0 0 1 3 2.5 4 4 0 0 1 0 3 4 4 0 0 1-2 3 4 4 0 0 1-2 5.5H9.5a4 4 0 0 1-2-5.5 4 4 0 0 1-2-3 4 4 0 0 1 0-3 4 4 0 0 1 3-2.5A4 4 0 0 1 12 4Z"/>
              <path d="M9.5 16h5"/>
              <path d="M10 20h4"/>
            </svg>
            <span>思考中...</span>
            <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
          <div v-if="item._expanded" class="thinking-body">{{ item.content }}</div>
        </div>
      </div>
    </template>

    <!-- ── 工具调用卡片 ── -->
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

    <!-- ── 中断问题（ask_user） ── -->
    <template v-else-if="item.kind === 'interrupt'">
      <div class="msg-avatar assistant-avatar">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      </div>
      <div class="msg-body">
        <div class="interrupt-msg" v-html="renderMd(item.content)"></div>
      </div>
    </template>

    <!-- ── 完成标记 ── -->
    <div v-else-if="item.kind === 'done'" class="done-marker">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="8 12 11 15 16 9"/>
      </svg>
      <span>分析完成</span>
    </div>

    <!-- ── 普通消息（用户 / 助手） ── -->
    <template v-else>
      <!-- 助手头像 -->
      <div v-if="item.role !== 'user'" class="msg-avatar assistant-avatar">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="8" r="4"/>
          <path d="M4 20c0-4 4-7 8-7s8 3 8 7"/>
        </svg>
      </div>
      <div class="msg-body">
        <!-- 历史思考过程 -->
        <div v-if="item.thinking" class="thinking-block" @click="toggleExpand(item)">
          <div class="thinking-header">
            <!-- Brain 图标 -->
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="thinking-brain-icon">
              <path d="M12 4a4 4 0 0 1 3.5 2 4 4 0 0 1 3 2.5 4 4 0 0 1 0 3 4 4 0 0 1-2 3 4 4 0 0 1-2 5.5H9.5a4 4 0 0 1-2-5.5 4 4 0 0 1-2-3 4 4 0 0 1 0-3 4 4 0 0 1 3-2.5A4 4 0 0 1 12 4Z"/>
              <path d="M9.5 16h5"/>
              <path d="M10 20h4"/>
            </svg>
            <span>思考过程</span>
            <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
          <div v-if="item._expanded" class="thinking-body">{{ item.thinking }}</div>
        </div>
        <div class="text-content" v-html="renderMd(item.content)"></div>
        <!-- 复制按钮（仅助手消息） -->
        <button v-if="item.role !== 'user'" class="copy-btn" @click.stop="copyContent(item.content)" title="复制内容">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
      </div>
    </template>
  </div>

  <!-- ── 打字指示器 ── -->
  <div v-if="isLoading" class="message-row assistant">
    <div class="msg-avatar assistant-avatar">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="8" r="4"/>
        <path d="M4 20c0-4 4-7 8-7s8 3 8 7"/>
      </svg>
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
  if (item.kind === 'interrupt') return 'message-row assistant'
  if (item.kind === 'done') return 'message-row assistant'
  if (item.kind === 'tool_call') return ''
  return ['message-row', item.role]
}

// ── 展开/折叠 ──
function toggleExpand(item) {
  toggleItemExpand?.(item.id)
}

// ── 复制内容 ──
async function copyContent(text) {
  try {
    await navigator.clipboard.writeText(String(text || ''))
  } catch {
    // 静默失败
  }
}

// ── 工具卡片工具函数 ──
function isTodos(item) {
  return item.name === 'write_todos' && item.result
}

function parseTodos(item) {
  try {
    let raw = item.result
    if (typeof raw !== 'string') raw = JSON.stringify(raw)
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
  } catch {}
  return null
}

function formatToolName(name) {
  const labels = {
    'load_csv': '读取 CSV',
    'load_excel': '读取 Excel',
    'load-data': '读取数据',
    'execute_python': '执行代码',
    'run_python': '执行代码',
    'py_eval': 'Python 执行',
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
  const firstLine = text.split('\n')[0].trim()
  if (firstLine.length <= 80) return firstLine
  const m = firstLine.match(/^(.+?[。.!！?？])/)
  return m ? m[1] : firstLine.slice(0, 80) + '...'
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════
   打字指示器
   ═══════════════════════════════════════════════════════ */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: typing 1.4s infinite both;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* ═══════════════════════════════════════════════════════
   消息行布局
   ═══════════════════════════════════════════════════════ */
.message-row {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-2xl);
  max-width: var(--chat-max-width);
  margin: 0 auto;
}
.message-row.user {
  flex-direction: row-reverse;
}
.message-row.error {
  justify-content: center;
}

/* ── 头像 ── */
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

/* ── 消息体 ── */
.msg-body {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}
.message-row.user .msg-body {
  align-items: flex-end;
}

/* ═══════════════════════════════════════════════════════
   用户消息气泡
   ═══════════════════════════════════════════════════════ */
.message-row.user .text-content {
  background: var(--user-bubble-bg);
  color: var(--color-text);
  border-radius: var(--radius-bubble);
  padding: 10px 16px;
  font-size: var(--font-size-md);
  line-height: var(--line-height);
  max-width: calc(100% - 88px);
}

/* ═══════════════════════════════════════════════════════
   助手消息文本
   ═══════════════════════════════════════════════════════ */
.message-row:not(.user) .text-content {
  color: var(--color-text-secondary);
  padding: 0;
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
}

.text-content {
  word-break: break-word;
}

/* ═══════════════════════════════════════════════════════
   错误条
   ═══════════════════════════════════════════════════════ */
.error-bar {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: #FEF2F2;
  border-left: 3px solid var(--color-error);
  border-radius: var(--radius-md);
  color: #DC2626;
  font-size: var(--font-size-sm);
  width: 100%;
  max-width: var(--chat-max-width);
}
.error-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

/* ═══════════════════════════════════════════════════════
   完成标记
   ═══════════════════════════════════════════════════════ */
.done-marker {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--spacing-sm) 0;
}

/* ═══════════════════════════════════════════════════════
   思考块
   ═══════════════════════════════════════════════════════ */
.thinking-block {
  margin-bottom: var(--spacing-sm);
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: var(--color-bg);
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
.thinking-brain-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}
.thinking-header .tool-card-chevron {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}
.thinking-header .tool-card-chevron.expanded {
  transform: rotate(180deg);
}
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

/* ═══════════════════════════════════════════════════════
   复制按钮
   ═══════════════════════════════════════════════════════ */
.copy-btn {
  align-self: flex-end;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  color: var(--color-text-muted);
  cursor: pointer;
  margin-top: var(--spacing-xs);
  opacity: 0;
  transition: opacity var(--transition-fast);
  padding: 0;
}
.copy-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-muted);
}
.message-row.assistant:hover .copy-btn {
  opacity: 1;
}

/* ═══════════════════════════════════════════════════════
   Markdown 内容样式
   ═══════════════════════════════════════════════════════ */
.text-content :deep(p) { margin-bottom: var(--spacing-md); }
.text-content :deep(p:last-child) { margin-bottom: 0; }
.text-content :deep(code) {
  background: var(--color-bg-muted);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
  color: var(--color-secondary, #3964FE);
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
  color: var(--color-primary);
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

/* ── 中断问题 ── */
.interrupt-msg {
  border-left: 3px solid var(--color-primary);
  background: var(--color-primary-subtle);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: var(--spacing-md);
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  color: var(--color-text);
}
.interrupt-msg :deep(p) { margin-bottom: var(--spacing-xs); }
.interrupt-msg :deep(p:last-child) { margin-bottom: 0; }
.interrupt-msg :deep(strong) { color: var(--color-text); }
.interrupt-msg :deep(li) { margin-bottom: var(--spacing-xs); }
</style>
