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
  },
})
