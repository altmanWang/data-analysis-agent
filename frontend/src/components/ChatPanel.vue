<template>
  <div class="chat-panel" :class="{ 'has-messages': messages.length > 0 || chatStore.todos.length > 0 }">
    <div v-if="sessionTitle && sessionTitle !== '新会话'" class="chat-header">{{ sessionTitle }}</div>
    <div v-if="chatStore.todos.length" class="todo-panel">
      <div class="todo-title">分析计划</div>
      <div v-for="t in chatStore.todos" :key="t.content" class="todo-item" :class="t.status">
        <span class="todo-dot">{{ t.status === 'completed' ? '✓' : t.status === 'in_progress' ? '●' : '○' }}</span>
        <span>{{ t.content }}</span>
      </div>
    </div>
    <div class="chat-messages" ref="msgContainer">
      <!-- 无会话时的欢迎提示 -->
      <div v-if="messages.length === 0 && chatStore.todos.length === 0" class="welcome-hint">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="welcome-icon">
          <path d="M21 21H3v-4a2 2 0 012-2h14a2 2 0 012 2v4z"/>
          <path d="M7 15V9a5 5 0 0110 0v6"/>
          <circle cx="12" cy="6" r="2"/>
        </svg>
        <h2>数据分析 Agent</h2>
        <p>上传 CSV / Excel 文件，用自然语言进行数据分析</p>
      </div>
      <div v-for="(msg, i) in messages" :key="i" class="message-row" :class="msg.role">
        <div v-if="msg.role !== 'user'" class="msg-avatar">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/></svg>
        </div>
        <div class="msg-body">
          <div class="text-content" v-html="renderMd(msg.content)"></div>
          <div v-if="msg.source === 'subagent'" class="sub-tag">子代理</div>
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
        <textarea ref="input" v-model="text" @keydown.enter.exact.prevent="send"
          @keydown.escape="text=''" @input="onInput"
          :disabled="sessionStatus === 'archived'" placeholder="输入分析需求，@ 引用文件..." rows="1" />
        <button @click="send" :disabled="!text.trim()" class="send-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { useSessionStore } from '../stores/sessionStore'
import { useChatStore } from '../stores/chatStore'
import { useFileStore } from '../stores/fileStore'
import { createWS } from '../utils/websocket'
import { marked } from 'marked'
import { nextTick, watch } from 'vue'

export default {
  props: { id: String },
  data: () => ({
    sessionId: null, sessionTitle: '', sessionStatus: 'active',
    text: '', showMention: false, mentionStart: 0, selectedMentions: [],
  }),
  mounted() {
    const sessionStore = useSessionStore()
    const chatStore = useChatStore()
    const fileStore = useFileStore()

    // 切换会话时清空旧数据
    chatStore.reset()

    // 有效的会话 ID：加载数据并建立连接
    if (this.id && this.id !== 'new') {
      this.sessionId = this.id
      sessionStore.currentId = this.id

      sessionStore.fetchSession(this.id).then(m => {
        this.sessionTitle = m.title
        this.sessionStatus = m.status
        fileStore.fetchTree(this.id)
      }).catch(() => this.$router.push('/'))

      chatStore.ws = createWS(this.id, chatStore, fileStore)

      // 有待发送的输入（从上一个无效会话迁移过来）
      if (sessionStore.pendingInput) {
        const pending = sessionStore.pendingInput
        sessionStore.pendingInput = null
        this.$nextTick(() => {
          this.text = pending.text
          this.selectedMentions = pending.mentions
          this.send()
        })
      }
    }
  },
  computed: {
    chatStore() { return useChatStore() },
    messages() { return this.chatStore.messages },
    isNewSession() { return !this.sessionId },
    mentionFiles() {
      const tree = useFileStore().tree
      const files = []
      const flatten = (items, p = '') => items.forEach(i => {
        const fp = p + '/' + i.name
        if (i.type === 'file') files.push(fp)
        if (i.children) flatten(i.children, fp)
      })
      flatten(tree)
      return files
    },
  },
  watch: {
    'chatStore.messages': { deep: true, handler() { this.$nextTick(() => this.scrollBottom()) } },
  },
  methods: {
    scrollBottom() { this.$refs.bottom?.scrollIntoView({ behavior: 'smooth' }) },
    renderMd(text) { return marked.parse(text || '') },
    onInput(e) {
      const match = this.text.slice(0, e.target.selectionStart).match(/@([^\s@]*)$/)
      this.showMention = !!match
      if (match) this.mentionStart = e.target.selectionStart - match[1].length - 1
    },
    insertMention(f) {
      this.text = this.text.slice(0, this.mentionStart) + '@' + f + ' '
      this.selectedMentions.push(f)
      this.showMention = false
      this.$refs.input.focus()
    },
    send() {
      if (!this.text.trim()) return
      const chatStore = useChatStore()
      const sessionStore = useSessionStore()

      // 无会话或有无效会话时：自动创建新会话
      if (!this.sessionId || this.sessionStatus !== 'active') {
        sessionStore.pendingInput = { text: this.text, mentions: this.selectedMentions }
        sessionStore.createSession().then(s => {
          this.$router.push(`/session/${s.session_id}`)
        })
        return
      }

      chatStore.addMessage({ role: 'user', content: this.text })
      chatStore.isStreaming = true
      chatStore.ws.send(JSON.stringify({
        type: 'chat.send',
        payload: { content: this.text, mentions: this.selectedMentions },
      }))
      this.text = ''
      this.selectedMentions = []
    },
    async onUpload(e) {
      const file = e.target.files[0]
      if (!file) return
      const sessionStore = useSessionStore()
      // 无会话时自动创建
      if (!this.sessionId) {
        const s = await sessionStore.createSession()
        const fileStore = useFileStore()
        await fileStore.upload(s.session_id, file)
        this.$router.push(`/session/${s.session_id}`)
        return
      }
      await useFileStore().upload(this.sessionId, file)
    },
  },
  beforeUnmount() {
    const ws = useChatStore().ws
    if (ws) ws.close()
  },
}
</script>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-bg);
  justify-content: center;
}

.chat-panel.has-messages {
  justify-content: flex-start;
}

/* ---- header ---- */
.chat-header {
  padding: var(--spacing-md) var(--spacing-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  font-size: var(--font-size-md);
  flex-shrink: 0;
}

.has-messages .chat-header {
  border-bottom: 1px solid var(--color-border-light);
}

/* ---- messages area ---- */
.chat-messages {
  overflow-y: auto;
  padding: 0;
}

.has-messages .chat-messages {
  flex: 1;
}

/* 无会话时的欢迎提示 */
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

.message-row {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-2xl);
  max-width: 800px;
  margin: 0 auto;
}

.message-row.user {
  flex-direction: row-reverse;
}

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

.msg-body {
  min-width: 0;
  flex: 1;
}

/* user message */
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

/* assistant message — no bubble, clean text */
.message-row:not(.user) .text-content {
  color: var(--color-text);
  padding: 0;
  line-height: 1.8;
}

.text-content {
  font-size: var(--font-size-md);
  word-break: break-word;
}

/* ---- markdown content ---- */
.text-content :deep(p) {
  margin-bottom: var(--spacing-md);
}
.text-content :deep(p:last-child) {
  margin-bottom: 0;
}

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

.text-content :deep(tr:hover td) {
  background: var(--color-bg-muted);
}

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

.text-content :deep(li) {
  margin-bottom: var(--spacing-xs);
}

.text-content :deep(a) {
  color: var(--color-secondary);
  text-decoration: none;
}
.text-content :deep(a:hover) {
  text-decoration: underline;
}

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

/* sub-agent tag */
.sub-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  background: var(--color-border-light);
  color: var(--color-text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  margin-top: var(--spacing-xs);
}

/* ---- input area ---- */
.chat-input {
  padding: 0 var(--spacing-2xl) var(--spacing-2xl);
  position: relative;
  flex-shrink: 0;
}

.has-messages .chat-input {
  padding: var(--spacing-md) var(--spacing-2xl) var(--spacing-lg);
  border-top: 1px solid #CBD5E1;
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-sm);
  max-width: 800px;
  margin: 0 auto;
  border: 1px solid #CBD5E1;
  border-radius: var(--radius-xl);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.input-row:focus-within {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.has-messages .input-row {
  border: 1px solid #CBD5E1;
  border-radius: var(--radius-lg);
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--color-bg-card);
}

textarea {
  flex: 1;
  padding: var(--spacing-sm) 0;
  border: none;
  font-size: var(--font-size-md);
  line-height: 1.6;
  resize: none;
  outline: none;
  font-family: inherit;
  color: var(--color-text);
  background: transparent;
  max-height: 120px;
}

textarea::placeholder {
  color: var(--color-text-muted);
}

textarea:disabled {
  color: var(--color-text-muted);
  cursor: not-allowed;
}

.send-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  background: var(--color-text);
  color: var(--color-text-inverse);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), transform var(--transition-fast);
  margin-bottom: 2px;
}

.send-btn:hover:not(:disabled) {
  background: var(--color-primary);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.92);
}

.send-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.upload-btn {
  cursor: pointer;
  padding: var(--spacing-xs);
  color: var(--color-text-muted);
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
}

.upload-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-muted);
}

/* ---- @mention dropdown ---- */
.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: var(--spacing-2xl);
  right: var(--spacing-2xl);
  max-width: 800px;
  margin: 0 auto var(--spacing-xs);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  max-height: 200px;
  overflow-y: auto;
  box-shadow: var(--shadow-dropdown);
  z-index: var(--z-dropdown);
}

.mention-item {
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  font-size: var(--font-size-base);
  color: var(--color-text);
  transition: background var(--transition-fast);
}

.mention-item:hover {
  background: var(--color-bg-muted);
}

.mention-item:first-child {
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.mention-item:last-child {
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}

.mention-empty {
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
}

/* ---- todo panel ---- */
.todo-panel {
  padding: var(--spacing-md) var(--spacing-2xl);
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-bg);
  flex-shrink: 0;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.todo-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.3px;
}

.todo-item {
  font-size: var(--font-size-base);
  padding: var(--spacing-xs) 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  color: var(--color-text-secondary);
}

.todo-dot {
  min-width: 16px;
  text-align: center;
  font-size: var(--font-size-xs);
}

.todo-item.completed {
  color: var(--color-text-muted);
  text-decoration: line-through;
}

.todo-item.in_progress {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}

.todo-item.in_progress .todo-dot {
  color: var(--color-secondary);
}
</style>
