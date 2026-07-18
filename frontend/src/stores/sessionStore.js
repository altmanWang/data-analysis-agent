import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentId: null,
    currentMeta: null,
  }),
  actions: {
    async fetchSessions(userId = '') {
      const res = await fetch(`/api/sessions?user_id=${userId}`)
      this.sessions = await res.json()
    },
    async createSession(userId = '') {
      const res = await fetch(`/api/sessions?user_id=${userId}`, { method: 'POST' })
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
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
      this.sessions = this.sessions.filter(s => s.session_id !== id)
      if (this.currentId === id) this.currentId = null
    },
  },
})
