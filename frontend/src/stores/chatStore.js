import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    todos: [],
    isStreaming: false,
    ws: null,
    wsStatus: 'connecting', // 'connecting' | 'connected' | 'reconnecting' | 'error'
  }),
  actions: {
    reset() {
      this.messages = []
      this.todos = []
      this.isStreaming = false
      this.wsStatus = 'connecting'
    },
    addMessage(msg) {
      this.messages.push({ ...msg, timestamp: Date.now() })
    },
    appendToLast(content, source = 'coordinator') {
      const last = this.messages[this.messages.length - 1]
      if (last && last.role === 'assistant' && !last.done) {
        last.content += content
      } else {
        this.messages.push({ role: 'assistant', content, source, done: false, timestamp: Date.now() })
      }
    },
    finishLastMessage() {
      const last = this.messages[this.messages.length - 1]
      if (last) last.done = true
    },
    updateTodos(todos) { this.todos = todos },
    setWsStatus(status) { this.wsStatus = status },
    addToolCall(tool, input) {
      this.messages.push({
        role: 'tool',
        type: 'tool-call',
        tool,
        status: 'running',
        input,
        output: null,
        expanded: true,
        timestamp: Date.now(),
      })
    },
    updateToolResult(tool, output) {
      for (let i = this.messages.length - 1; i >= 0; i--) {
        const m = this.messages[i]
        if (m.role === 'tool' && m.type === 'tool-call' && m.tool === tool && m.status === 'running') {
          m.status = 'done'
          m.output = output
          m.expanded = false
          return
        }
      }
      // 找不到匹配的 running 卡片时，作为独立完成消息插入
      this.messages.push({
        role: 'tool',
        type: 'tool-call',
        tool,
        status: 'done',
        input: null,
        output,
        expanded: false,
        timestamp: Date.now(),
      })
    },
  },
})
