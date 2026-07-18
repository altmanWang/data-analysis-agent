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
    addToolStatus(info) {
      // 追加到消息流中作为系统消息，同时去重
      const key = `${info.tool}:${info.status}`
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg && lastMsg.role === 'tool' && lastMsg.toolKey === key) {
        // 同一工具同一状态不重复
        return
      }
      this.messages.push({
        role: 'tool',
        toolKey: key,
        content: info.status === 'running'
          ? `🔧 ${info.tool}...`
          : `✅ ${info.tool} 完成`,
        detail: info.detail,
        timestamp: Date.now(),
      })
    },
  },
})
