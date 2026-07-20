<template>
  <div class="chat-panel" :class="{ 'has-messages': hasContent }">
    <div v-if="sessionTitle && sessionTitle !== '新会话'" class="chat-header">{{ sessionTitle }}</div>

    <div v-if="todos.length" class="todo-panel">
      <div class="todo-title">分析计划</div>
      <div v-for="t in todos" :key="t.content" class="todo-item" :class="t.status">
        <span class="todo-dot">{{ t.status === 'completed' ? '✓' : t.status === 'in_progress' ? '●' : '○' }}</span>
        <span>{{ t.content }}</span>
      </div>
    </div>

    <div class="chat-messages" ref="msgContainer">
      <div v-if="!props.id && timelineItems.length === 0 && todos.length === 0" class="welcome-hint">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="welcome-icon">
          <path d="M21 21H3v-4a2 2 0 012-2h14a2 2 0 012 2v4z"/>
          <path d="M7 15V9a5 5 0 0110 0v6"/>
          <circle cx="12" cy="6" r="2"/>
        </svg>
        <h2>数据分析 Agent</h2>
        <p>上传 CSV / Excel 文件，用自然语言进行数据分析</p>
      </div>

      <div v-for="(item, i) in timelineItems" :key="item.id || i" class="message-row" :class="item.role">
        <!-- 工具调用卡片 -->
        <div v-if="item.kind === 'tool_call'" class="tool-card" :class="tcClass(item.status)" @click="toggleExpand(item)">
          <div class="tool-card-header">
            <span class="tool-card-dot"></span>
            <span class="tool-card-name">{{ item.name }}</span>
            <span class="tool-card-status">{{ tcLabel(item.status) }}</span>
            <svg class="tool-card-chevron" :class="{ expanded: item._expanded }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div v-if="item._expanded" class="tool-card-body">
            <div v-if="item.args" class="card-section">
              <div class="card-label">输入</div>
              <pre class="card-pre">{{ fmtArgs(item.args) }}</pre>
            </div>
            <div v-if="item.result != null" class="card-section">
              <div class="card-label">输出</div>
              <pre class="card-pre">{{ fmtResult(item.result) }}</pre>
            </div>
            <div v-if="!item.args && item.result == null" class="card-empty">等待结果...</div>
          </div>
        </div>

        <template v-else>
          <div v-if="item.role !== 'user'" class="msg-avatar">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/></svg>
          </div>
          <div class="msg-body">
            <div class="text-content" v-html="renderMd(item.content)"></div>
            <div v-if="item.source === 'subagent'" class="sub-tag">子代理</div>
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

      <div ref="bottom" />
    </div>

    <div class="chat-input">
      <div class="mention-dropdown" v-if="showMention">
        <div v-for="f in mentionFiles" :key="f" class="mention-item" @click="insertMention(f)">{{ f }}</div>
        <div v-if="mentionFiles.length === 0" class="mention-empty">无匹配文件</div>
      </div>
      <div class="input-row">
        <label class="upload-btn" title="上传文件">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <input type="file" hidden @change="onUpload" accept=".csv,.xlsx,.xls" />
        </label>
        <textarea ref="inputRef" v-model="text" @keydown.enter.exact.prevent="send"
          @keydown.escape="text=''" @input="onInput"
          :disabled="sessionStatus === 'archived'" placeholder="输入分析需求，@ 引用文件..." rows="1" />
        <button @click="send" :disabled="!text.trim() || isLoading" class="send-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useSessionStore } from '../stores/sessionStore'
import { useFileStore } from '../stores/fileStore'

const props = defineProps({ id: String })
const router = useRouter()

// ── 本地状态 ──
const text = ref('')
const showMention = ref(false)
const mentionStart = ref(0)
const selectedMentions = ref([])
const msgContainer = ref(null)
const bottom = ref(null)
const inputRef = ref(null)
const sessionTitle = ref('')
const sessionStatus = ref('active')
const todos = ref([])
const timelineItems = shallowRef([])
const isLoading = ref(false)
let abortController = null

// ── 是否为有效 session（已创建的线程） ──
const hasValidThread = computed(() => props.id && props.id !== 'new')
const hasContent = computed(() => timelineItems.value.length > 0 || todos.value.length > 0)

// ── 会话信息加载 ──
onMounted(async () => {
  if (hasValidThread.value) {
    const sessionStore = useSessionStore()
    try {
      const m = await sessionStore.fetchSession(props.id)
      sessionTitle.value = m.title
      sessionStatus.value = m.status
      useFileStore().fetchTree(props.id)
      await loadHistory()
    } catch { router.push('/') }
    if (sessionStore.pendingInput) {
      const p = sessionStore.pendingInput
      sessionStore.pendingInput = null
      nextTick(() => { text.value = p.text; selectedMentions.value = p.mentions; send() })
    }
  }
})

// ── 加载历史 ──
async function loadHistory() {
  try {
    const res = await fetch(`/api/threads/${props.id}/messages`)
    if (!res.ok) return
    const rows = await res.json()
    if (!rows?.length) return
    const items = []
    for (const r of rows) {
      if (r.role === 'tool') {
        items.push({
          id: `${props.id}-tool-${Math.random()}`, kind: 'tool_call', role: 'tool',
          name: r.tool_name || '', args: r.tool_args || null,
          status: r.tool_status || 'done', result: r.tool_result || null, _expanded: false,
        })
      } else {
        items.push({
          id: `${props.id}-${r.role}-${Math.random()}`, kind: 'message',
          role: r.role === 'assistant' ? 'assistant' : 'user',
          content: r.content || '', done: true,
        })
      }
    }
    if (items.length > 0) timelineItems.value = items
  } catch (e) { console.error('加载历史失败:', e) }
}

// ── 自动滚动 ──
function autoScroll() {
  const el = msgContainer.value
  if (!el) return
  if (el.scrollHeight - el.scrollTop - el.clientHeight > 150) return
  bottom.value?.scrollIntoView({ behavior: 'smooth' })
}
watch(() => timelineItems.value.length, () => { nextTick(() => autoScroll()) })

// ── Markdown 渲染 ──
function renderMd(text_) {
  const text = Array.isArray(text_)
    ? text_.map(b => (typeof b === 'string' ? b : b.text || '')).join('')
    : (text_ || '')
  let html = marked.parse(text)
  const tid = props.id
  if (tid && tid !== 'new') {
    html = html.replace(/src="(?!https?:\/\/|\/api\/)([^"]*\.(?:png|jpg|jpeg|gif|svg))"/gi,
      (_, path) => `src="/api/sessions/${tid}/files/${path.replace(/^\//, '')}"`)
    html = html.replace(/href="(?!https?:\/\/|\/api\/)([^"]*\.(?:html))"/gi,
      (_, path) => `href="/api/sessions/${tid}/files/${path.replace(/^\//, '')}"`)
  }
  return html
}

// ── 发送消息 ──
async function send() {
  if (!text.value.trim() || isLoading.value) return
  const content = text.value
  text.value = ''
  selectedMentions.value = []

  if (!hasValidThread.value) {
    const sessionStore = useSessionStore()
    sessionStore.pendingInput = { text: content, mentions: [] }
    try {
      const res = await fetch('/api/threads', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: content.slice(0, 50) }),
      })
      router.push(`/session/${(await res.json()).thread_id}`)
    } catch { text.value = content; sessionStore.pendingInput = null }
    return
  }

  isLoading.value = true
  abortController = new AbortController()

  // 追加用户消息
  timelineItems.value = [...timelineItems.value, {
    id: Date.now().toString(), kind: 'message', role: 'user', content, done: true,
  }]

  const tid = props.id
  let currentMsgId = null
  let currentText = ''

  try {
    await fetchEventSource(`/api/threads/${tid}/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      signal: abortController.signal,
      openWhenHidden: true,

      onmessage(event) {
        if (!event.data) return
        try { var data = JSON.parse(event.data) } catch { return }

        if (data.type === 'text') {
          if (!currentMsgId) {
            currentMsgId = `${Date.now()}-ai`
            timelineItems.value = [...timelineItems.value, {
              id: currentMsgId, kind: 'message', role: 'assistant', content: '', done: false,
            }]
          }
          currentText += data.content
          timelineItems.value = timelineItems.value.map(i =>
            i.id === currentMsgId ? { ...i, content: currentText } : i)
        } else if (data.type === 'tool_start') {
          timelineItems.value = [...timelineItems.value, {
            id: data.id, kind: 'tool_call', role: 'tool',
            name: data.name, args: data.input, status: 'running', result: null, _expanded: true,
          }]
        } else if (data.type === 'tool_end') {
          timelineItems.value = timelineItems.value.map(i =>
            i.id === data.id ? { ...i, status: 'done', result: data.output, _expanded: false } : i)
        } else if (data.type === 'done') {
          if (currentMsgId) {
            timelineItems.value = timelineItems.value.map(i =>
              i.id === currentMsgId ? { ...i, done: true } : i)
          }
          abortController.abort() // 主动关闭连接，让 finally 执行
        }
      },

      onerror(err) {
        throw err
      },
    })
  } catch (err) {
    if (err.name !== 'AbortError') console.error('Stream error:', err)
  } finally {
    isLoading.value = false
    abortController = null
  }
}

// ── @mention ──
const mentionFiles = computed(() => {
  const tree = useFileStore().tree
  const files = []
  const flatten = (items, p = '') => items.forEach(i => {
    const fp = p + '/' + i.name
    if (i.type === 'file') files.push(fp)
    if (i.children) flatten(i.children, fp)
  })
  flatten(tree)
  return files
})

function onInput(e) {
  const match = text.value.slice(0, e.target.selectionStart).match(/@([^\s@]*)$/)
  showMention.value = !!match
  if (match) mentionStart.value = e.target.selectionStart - match[1].length - 1
}

function insertMention(f) {
  text.value = text.value.slice(0, mentionStart.value) + '@' + f + ' '
  selectedMentions.value.push(f)
  showMention.value = false
  inputRef.value?.focus()
}

async function onUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const sessionStore = useSessionStore()
  if (!props.id || props.id === 'new') {
    const s = await sessionStore.createSession()
    await useFileStore().upload(s.session_id, file)
    router.push(`/session/${s.session_id}`)
    return
  }
  await useFileStore().upload(props.id, file)
}

// ── 工具调用卡片 ──
function toggleExpand(item) { item._expanded = !item._expanded }

function tcClass(status) {
  if (status === 'running' || status === 'pending') return 'running'
  if (status === 'success') return 'done'
  return ''
}

function tcLabel(status) {
  if (status === 'pending') return '等待中...'
  if (status === 'running') return '执行中...'
  if (status === 'success') return '完成'
  if (status === 'error') return '失败'
  return status || ''
}

function fmtArgs(args) {
  if (typeof args === 'string') return args
  try { return JSON.stringify(args, null, 2) } catch { return String(args) }
}

function fmtResult(result) {
  if (typeof result === 'string') return result
  try { return JSON.stringify(result, null, 2) } catch { return String(result) }
}

// ── 清理 ──
onBeforeUnmount(() => {
  abortController?.abort()
})
</script>

<style scoped>
/* ── layout ── */
.chat-panel { flex: 1; display: flex; flex-direction: column; height: 100vh; background: var(--color-bg); justify-content: center; }
.chat-panel.has-messages { justify-content: flex-start; }
.chat-header { padding: var(--spacing-md) var(--spacing-2xl); font-weight: var(--font-weight-semibold); color: var(--color-text); font-size: var(--font-size-md); flex-shrink: 0; }
.has-messages .chat-header { border-bottom: 1px solid var(--color-border-light); }

/* ── typing indicator ── */
.typing-indicator { display: flex; gap: 4px; padding: 4px 0; }
.typing-indicator span { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); animation: typing 1.4s infinite both; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); } 30% { opacity: 1; transform: scale(1); } }

/* ── messages ── */
.chat-messages { overflow-y: auto; padding: 0; }
.has-messages .chat-messages { flex: 1; }
.welcome-hint { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 0 var(--spacing-lg) var(--spacing-xl); }
.welcome-icon { color: var(--color-text-muted); margin-bottom: var(--spacing-lg); }
.welcome-hint h2 { font-size: var(--font-size-2xl); font-weight: var(--font-weight-semibold); color: var(--color-text); margin-bottom: var(--spacing-xs); }
.welcome-hint p { font-size: var(--font-size-md); color: var(--color-text-muted); max-width: 360px; line-height: 1.6; }
.message-row { display: flex; gap: var(--spacing-md); padding: var(--spacing-md) var(--spacing-2xl); max-width: 800px; margin: 0 auto; }
.message-row.user { flex-direction: row-reverse; }
.msg-avatar { flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary); color: var(--color-text-inverse); display: flex; align-items: center; justify-content: center; margin-top: 2px; }
.msg-body { min-width: 0; flex: 1; }
.message-row.user .msg-body { display: flex; flex-direction: column; align-items: flex-end; }
.message-row.user .text-content { background: var(--color-bg-muted); color: var(--color-text); border-radius: var(--radius-xl); padding: var(--spacing-sm) var(--spacing-lg); max-width: 75%; line-height: var(--line-height); }
.message-row:not(.user) .text-content { color: var(--color-text); padding: 0; line-height: 1.8; }
.text-content { font-size: var(--font-size-md); word-break: break-word; }
.sub-tag { display: inline-block; font-size: var(--font-size-xs); background: var(--color-border-light); color: var(--color-text-muted); padding: 2px 8px; border-radius: var(--radius-sm); margin-top: var(--spacing-xs); }

/* ── tool card ── */
.tool-card { margin: 4px auto; border-radius: var(--radius-md); border: 1px solid var(--color-border); background: var(--color-bg-card); cursor: pointer; overflow: hidden; transition: border-color var(--transition-fast); max-width: 800px; width: calc(100% - var(--spacing-2xl) * 2); }
.tool-card.running { border-color: var(--color-border-focus); background: #EFF6FF; }
.tool-card.done { border-color: var(--color-success); }
.tool-card-header { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); font-size: var(--font-size-sm); }
.tool-card-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.running .tool-card-dot { background: var(--color-border-focus); animation: pulse 1.5s infinite; }
.done .tool-card-dot { background: var(--color-success); }
.tool-card-name { font-weight: var(--font-weight-medium); color: var(--color-text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-card-status { color: var(--color-text-muted); font-size: var(--font-size-xs); flex-shrink: 0; }
.tool-card-chevron { flex-shrink: 0; color: var(--color-text-muted); transition: transform var(--transition-fast); }
.tool-card-chevron.expanded { transform: rotate(180deg); }
.tool-card-body { padding: 0 var(--spacing-md) var(--spacing-md); border-top: 1px solid var(--color-border-light); }
.card-section { margin-top: var(--spacing-sm); }
.card-label { font-size: var(--font-size-xs); color: var(--color-text-muted); margin-bottom: var(--spacing-xs); text-transform: uppercase; letter-spacing: 0.5px; }
.card-pre { font-size: var(--font-size-xs); background: var(--color-bg-muted); padding: var(--spacing-sm); border-radius: var(--radius-sm); overflow-x: auto; max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; color: var(--color-text-secondary); font-family: 'JetBrains Mono', monospace; }
.card-empty { text-align: center; color: var(--color-text-muted); font-size: var(--font-size-sm); padding: var(--spacing-md); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ── markdown ── */
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

/* ── input ── */
.chat-input { padding: 0 var(--spacing-2xl) var(--spacing-2xl); position: relative; flex-shrink: 0; }
.has-messages .chat-input { padding: var(--spacing-md) var(--spacing-2xl) var(--spacing-lg); border-top: 1px solid #CBD5E1; }
.input-row { display: flex; align-items: flex-end; gap: var(--spacing-sm); max-width: 800px; margin: 0 auto; border: 1px solid #CBD5E1; border-radius: var(--radius-xl); padding: var(--spacing-sm) var(--spacing-md); background: var(--color-bg-card); box-shadow: var(--shadow-sm); transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.input-row:focus-within { border-color: var(--color-border-focus); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15); }
.has-messages .input-row { border: 1px solid #CBD5E1; border-radius: var(--radius-lg); padding: var(--spacing-xs) var(--spacing-md); background: var(--color-bg-card); }
textarea { flex: 1; padding: var(--spacing-sm) 0; border: none; font-size: var(--font-size-md); line-height: 1.6; resize: none; outline: none; font-family: inherit; color: var(--color-text); background: transparent; max-height: 120px; }
textarea::placeholder { color: var(--color-text-muted); }
textarea:disabled { color: var(--color-text-muted); cursor: not-allowed; }
.send-btn { flex-shrink: 0; width: 32px; height: 32px; padding: 0; background: var(--color-text); color: var(--color-text-inverse); border: none; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background var(--transition-fast), transform var(--transition-fast); margin-bottom: 2px; }
.send-btn:hover:not(:disabled) { background: var(--color-primary); }
.send-btn:active:not(:disabled) { transform: scale(0.92); }
.send-btn:disabled { background: var(--color-border); cursor: not-allowed; }
.upload-btn { cursor: pointer; padding: var(--spacing-xs); color: var(--color-text-muted); border-radius: var(--radius-md); transition: color var(--transition-fast), background var(--transition-fast); display: flex; align-items: center; justify-content: center; flex-shrink: 0; width: 28px; height: 28px; }
.upload-btn:hover { color: var(--color-text); background: var(--color-bg-muted); }
.mention-dropdown { position: absolute; bottom: 100%; left: var(--spacing-2xl); right: var(--spacing-2xl); max-width: 800px; margin: 0 auto var(--spacing-xs); background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: var(--radius-lg); max-height: 200px; overflow-y: auto; box-shadow: var(--shadow-dropdown); z-index: var(--z-dropdown); }
.mention-item { padding: var(--spacing-sm) var(--spacing-md); cursor: pointer; font-size: var(--font-size-base); color: var(--color-text); transition: background var(--transition-fast); }
.mention-item:hover { background: var(--color-bg-muted); }
.mention-item:first-child { border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
.mention-item:last-child { border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
.mention-empty { padding: var(--spacing-sm) var(--spacing-md); color: var(--color-text-muted); font-size: var(--font-size-base); }

/* ── todo panel ── */
.todo-panel { padding: var(--spacing-md) var(--spacing-2xl); border-bottom: 1px solid var(--color-border-light); background: var(--color-bg); flex-shrink: 0; max-width: 800px; margin: 0 auto; width: 100%; }
.todo-title { font-size: var(--font-size-sm); color: var(--color-text-muted); margin-bottom: var(--spacing-sm); font-weight: var(--font-weight-semibold); letter-spacing: 0.3px; }
.todo-item { font-size: var(--font-size-base); padding: var(--spacing-xs) 0; display: flex; align-items: center; gap: var(--spacing-sm); color: var(--color-text-secondary); }
.todo-dot { min-width: 16px; text-align: center; font-size: var(--font-size-xs); }
.todo-item.completed { color: var(--color-text-muted); text-decoration: line-through; }
.todo-item.in_progress { color: var(--color-primary); font-weight: var(--font-weight-medium); }
.todo-item.in_progress .todo-dot { color: var(--color-secondary); }
</style>
