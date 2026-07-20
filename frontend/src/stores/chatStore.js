import { defineStore } from 'pinia'

/**
 * chatStore — 聊天消息与流式状态中心
 *
 * 替代原 useAnalysisStream composable 内部的 shallowRef，
 * 让 ChatPanel、SessionSidebar 等组件共享同一会话的消息状态。
 */
export const useChatStore = defineStore('chat', {
  state: () => ({
    /** 完整时间线: 消息 + 工具调用混合数组 */
    items: [],
    /** 加载中标志 */
    isLoading: false,
    /** 最近错误 */
    error: null,
    /** 当前绑定的 threadId */
    currentThreadId: null,
  }),

  getters: {
    /** 仅消息项 */
    messages: (state) => state.items.filter(i => i.kind === 'message'),

    /** 仅工具调用项 */
    toolCalls: (state) => state.items.filter(i => i.kind === 'tool_call'),

    /** 是否有任意内容 */
    hasContent: (state) => state.items.length > 0,

    /** 正在执行中的工具调用 */
    activeToolCalls: (state) =>
      state.toolCalls.filter(tc => tc.status === 'running'),
  },

  actions: {
    // ── 基础操作 ──

    /** 追加一条时间线项（触发响应式更新） */
    appendItem(item) {
      this.items = [...this.items, item]
    },

    /** 更新指定 id 的时间线项（触发响应式更新） */
    updateItem(id, patch) {
      this.items = this.items.map(i =>
        i.id === id ? { ...i, ...patch } : i
      )
    },

    /** 清空所有消息状态 */
    clearItems() {
      this.items = []
      this.error = null
    },

    setLoading(val) {
      this.isLoading = val
    },

    setError(err) {
      this.error = err
    },

    // ── 历史加载 ──

    /** 从后端加载消息历史 */
    async loadHistory(threadId) {
      if (!threadId) return
      try {
        const res = await fetch(`/api/threads/${threadId}/messages`)
        if (!res.ok) return
        const rows = await res.json()
        if (!rows?.length) return

        const messages = []
        const tools = []
        for (const r of rows) {
          if (r.role === 'tool') {
            tools.push({
              id: `${threadId}-tool-${Math.random()}`,
              kind: 'tool_call',
              role: 'tool',
              name: r.tool_name || '',
              args: r.tool_args || null,
              status: r.tool_status || 'done',
              result: r.tool_result || null,
              _expanded: false,
            })
          } else {
            messages.push({
              id: `${threadId}-${r.role}-${Math.random()}`,
              kind: 'message',
              role: r.role === 'assistant' ? 'assistant' : 'user',
              content: r.content || '',
              done: true,
            })
          }
        }

        if (messages.length > 0) {
          this.items = [...messages, ...tools]
        }
      } catch (e) {
        console.error('加载历史失败:', e)
      }
    },
  },
})
