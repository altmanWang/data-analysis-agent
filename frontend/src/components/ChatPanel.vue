<template>
  <div class="chat-panel">
    <div class="chat-header">{{ sessionTitle }}</div>
    <div v-if="chatStore.todos.length" class="todo-panel">
      <div class="todo-title">分析计划</div>
      <div v-for="t in chatStore.todos" :key="t.content" class="todo-item" :class="t.status">
        <span>{{ t.status === 'completed' ? '√' : t.status === 'in_progress' ? '●' : '○' }}</span>
        <span>{{ t.content }}</span>
      </div>
    </div>
    <div class="chat-messages" ref="msgContainer">
      <div v-for="(msg, i) in messages" :key="i" class="bubble" :class="msg.role">
        <div v-if="msg.role !== 'user'" class="role-label">Agent</div>
        <div class="text-content" v-html="renderMd(msg.content)"></div>
        <div v-if="msg.source === 'subagent'" class="sub-tag">子代理</div>
      </div>
      <div ref="bottom" />
    </div>
    <div class="chat-input">
      <div class="mention-dropdown" v-if="showMention">
        <div v-for="f in mentionFiles" :key="f" class="mention-item" @click="insertMention(f)">{{ f }}</div>
        <div v-if="mentionFiles.length === 0" class="mention-empty">无匹配文件</div>
      </div>
      <div class="input-row">
        <label class="upload-btn">
          +
          <input type="file" hidden @change="onUpload" accept=".csv,.xlsx,.xls" />
        </label>
        <textarea ref="input" v-model="text" @keydown.enter.exact.prevent="send"
          @keydown.escape="text=''" @input="onInput"
          :disabled="sessionStatus !== 'active'" placeholder="输入分析需求，@ 引用文件..." rows="1" />
        <button @click="send" :disabled="!text.trim() || sessionStatus !== 'active'" class="send-btn">发送</button>
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
    this.sessionId = this.id
    sessionStore.currentId = this.id

    sessionStore.fetchSession(this.id).then(m => {
      this.sessionTitle = m.title
      this.sessionStatus = m.status
      fileStore.fetchTree(this.id)
    }).catch(() => this.$router.push('/'))

    chatStore.ws = createWS(this.id, chatStore, fileStore)
  },
  computed: {
    chatStore() { return useChatStore() },
    messages() { return this.chatStore.messages },
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
      if (file) await useFileStore().upload(this.sessionId, file)
    },
  },
  beforeUnmount() {
    const ws = useChatStore().ws
    if (ws) ws.close()
  },
}
</script>

<style scoped>
.chat-panel { flex: 1; display: flex; flex-direction: column; height: 100vh; background: white; }
.chat-header { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #1a365d; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.bubble { margin-bottom: 12px; max-width: 85%; }
.bubble.user { margin-left: auto; }
.role-label { font-size: 11px; color: #a0aec0; margin-bottom: 2px; }
.sub-tag { display: inline-block; font-size: 10px; background: #edf2f7; color: #718096; padding: 1px 6px; border-radius: 3px; margin-top: 4px; }
.text-content { font-size: 14px; line-height: 1.7; word-break: break-word; }
.text-content :deep(p) { margin-bottom: 8px; }
.text-content :deep(code) { background: #edf2f7; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.text-content :deep(pre) { background: #2d3748; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; }
.text-content :deep(table) { border-collapse: collapse; }
.text-content :deep(th), .text-content :deep(td) { border: 1px solid #e2e8f0; padding: 8px 12px; }
.text-content :deep(th) { background: #edf2f7; }
.chat-input { padding: 12px 16px; border-top: 1px solid #e2e8f0; position: relative; }
.input-row { display: flex; align-items: center; gap: 8px; }
textarea { flex: 1; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; resize: none; outline: none; font-family: inherit; }
textarea:focus { border-color: #3182ce; }
.send-btn { padding: 10px 20px; background: #1a365d; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.send-btn:disabled { background: #a0aec0; cursor: not-allowed; }
.upload-btn { cursor: pointer; font-size: 22px; padding: 8px; color: #718096; }
.upload-btn:hover { color: #1a365d; }
.mention-dropdown { position: absolute; bottom: 100%; left: 16px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; max-height: 200px; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 10; min-width: 250px; }
.mention-item { padding: 8px 12px; cursor: pointer; font-size: 13px; }
.mention-item:hover { background: #ebf8ff; }
.mention-empty { padding: 8px 12px; color: #a0aec0; font-size: 13px; }
.todo-panel { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; }
.todo-title { font-size: 12px; color: #718096; margin-bottom: 6px; font-weight: 600; }
.todo-item { font-size: 13px; padding: 3px 0; display: flex; align-items: center; gap: 6px; }
.todo-item.completed { color: #a0aec0; text-decoration: line-through; }
.todo-item.in_progress { color: #2b6cb0; font-weight: 500; }
</style>
