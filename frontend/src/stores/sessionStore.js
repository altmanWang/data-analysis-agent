import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentId: null,
    currentMeta: null,
    pendingInput: null, // { text, mentions } — 新会话创建后自动发送
  }),
  actions: {
    async fetchSessions(userId = '') {
      try {
        const res = await fetch(`/api/sessions?user_id=${userId}`)
        if (!res.ok) throw new Error(`获取会话列表失败: ${res.status}`)
        this.sessions = await res.json()
      } catch (e) {
        console.error('获取会话列表失败:', e)
      }
    },
    async createSession(userId = '') {
      const res = await fetch(`/api/sessions?user_id=${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '新会话' }),
      })
      if (!res.ok) throw new Error(`创建会话失败: ${res.status}`)
      const session = await res.json()
      this.sessions.unshift(session)
      return session
    },
    async fetchSession(id) {
      const res = await fetch(`/api/sessions/${id}`)
      if (!res.ok) throw new Error('会话不存在')
      this.currentMeta = await res.json()
      return this.currentMeta
    },
    async deleteSession(id) {
      try {
        const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
        if (!res.ok) throw new Error(`删除会话失败: ${res.status}`)
        this.sessions = this.sessions.filter(s => s.session_id !== id)
        if (this.currentId === id) this.currentId = null
      } catch (e) {
        console.error('删除会话失败:', e)
      }
    },
  },
})
