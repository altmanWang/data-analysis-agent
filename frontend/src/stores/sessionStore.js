import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentId: null,
    currentMeta: null,
    pendingInput: null, // { text, mentions } — 新会话创建后自动发送
    // ── Agent 相关（多选）──
    agents: [],               // 用户创建的所有 agent 列表
    selectedAgentIds: [],     // 当前 session 选中的 agent ID 列表
    selectedAgents: [],       // 当前选中的 agent 详情列表
  }),
  actions: {
    // ── Session ──
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

    // ── Agent ──
    async fetchAgents(userId = '') {
      try {
        const res = await fetch(`/api/agents?user_id=${userId}`)
        if (!res.ok) throw new Error(`获取 Agent 列表失败: ${res.status}`)
        this.agents = await res.json()
      } catch (e) {
        console.error('获取 Agent 列表失败:', e)
      }
    },
    async createAgent(name, description, systemPrompt, userId = '') {
      const res = await fetch(`/api/agents?user_id=${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description, system_prompt: systemPrompt }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `创建 Agent 失败: ${res.status}`)
      }
      const agent = await res.json()
      this.agents.unshift(agent)
      return agent
    },
    async deleteAgent(id) {
      const res = await fetch(`/api/agents/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`删除 Agent 失败: ${res.status}`)
      this.agents = this.agents.filter(a => a.id !== id)
      this.selectedAgentIds = this.selectedAgentIds.filter(aid => aid !== id)
      this.selectedAgents = this.selectedAgents.filter(a => a.id !== id)
    },
    async toggleAgent(sessionId, agentId) {
      // 无 session 时仅本地切换，等会话创建后再同步
      if (!sessionId) {
        const isSelected = this.selectedAgentIds.includes(agentId)
        if (isSelected) {
          this.selectedAgentIds = this.selectedAgentIds.filter(id => id !== agentId)
          this.selectedAgents = this.selectedAgents.filter(a => a.id !== agentId)
        } else {
          const agent = this.agents.find(a => a.id === agentId)
          if (agent) {
            this.selectedAgentIds.push(agentId)
            this.selectedAgents.push(agent)
          }
        }
        return { added: !isSelected, agents: this.selectedAgents }
      }
      const res = await fetch(`/api/sessions/${sessionId}/agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId }),
      })
      if (!res.ok) throw new Error(`切换 Agent 失败: ${res.status}`)
      const data = await res.json()
      this.selectedAgentIds = data.agents.map(a => a.id)
      this.selectedAgents = data.agents
      return data
    },
    async clearAgents(sessionId) {
      if (!sessionId) {
        this.selectedAgentIds = []
        this.selectedAgents = []
        return
      }
      const res = await fetch(`/api/sessions/${sessionId}/agent`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`取消 Agent 失败: ${res.status}`)
      this.selectedAgentIds = []
      this.selectedAgents = []
    },
    async fetchSessionAgents(sessionId) {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/agent`)
        if (!res.ok) return
        const data = await res.json()
        this.selectedAgentIds = (data.agents || []).map(a => a.id)
        this.selectedAgents = data.agents || []
      } catch (e) {
        console.error('获取 session agents 失败:', e)
      }
    },
  },
})
