<template>
  <aside class="sidebar">
    <div class="sidebar-header"><h2>数据分析 Agent</h2></div>
    <div class="create-btn" @click="onCreate">+ 新建会话</div>
    <div class="session-list">
      <div v-for="s in sessionStore.sessions" :key="s.session_id"
        class="session-item" :class="{ active: s.session_id === sessionStore.currentId }"
        @click="$router.push(`/session/${s.session_id}`)">
        <div class="item-content">
          <div class="item-title">{{ s.title }}</div>
          <div class="item-meta">
            <span :class="'status ' + s.status">{{ statusMap[s.status] || s.status }}</span>
            <span>{{ fmt(s.last_active) }}</span>
          </div>
        </div>
        <button class="del-btn" @click.stop="onDelete(s.session_id)">x</button>
      </div>
      <div v-if="sessionStore.sessions.length === 0" class="empty">暂无会话</div>
    </div>
  </aside>
</template>

<script>
import { useSessionStore } from '../stores/sessionStore'
export default {
  data: () => ({ statusMap: { active: '活跃', archiving: '归档中', archived: '已归档' } }),
  setup() {
    const s = useSessionStore()
    s.fetchSessions()
    return { sessionStore: s }
  },
  methods: {
    async onCreate() {
      const s = await this.sessionStore.createSession()
      this.$router.push(`/session/${s.session_id}`)
    },
    async onDelete(id) {
      await this.sessionStore.deleteSession(id)
    },
    fmt(t) {
      if (!t) return ''
      return new Date(t).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
  },
}
</script>

<style scoped>
.sidebar { width: 260px; min-width: 260px; height: 100vh; border-right: 1px solid #e2e8f0; display: flex; flex-direction: column; background: #f8fafc; }
.sidebar-header { padding: 16px; border-bottom: 1px solid #e2e8f0; }
.sidebar-header h2 { font-size: 16px; color: #1a365d; }
.create-btn { margin: 12px; padding: 10px; text-align: center; cursor: pointer; background: #1a365d; color: white; border-radius: 6px; font-size: 14px; }
.create-btn:hover { background: #2a4a7f; }
.session-list { flex: 1; overflow-y: auto; }
.session-item { display: flex; align-items: center; padding: 10px 12px; cursor: pointer; border-bottom: 1px solid #edf2f7; font-size: 13px; }
.session-item:hover { background: #edf2f7; }
.session-item.active { background: #ebf8ff; border-left: 3px solid #3182ce; }
.item-content { flex: 1; overflow: hidden; }
.item-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.item-meta { display: flex; gap: 8px; font-size: 11px; color: #718096; margin-top: 2px; }
.status.active { color: #38a169; }
.status.archived { color: #a0aec0; }
.del-btn { background: none; border: none; color: #cbd5e0; font-size: 16px; cursor: pointer; padding: 0 4px; }
.del-btn:hover { color: #e53e3e; }
.empty { text-align: center; color: #a0aec0; padding: 20px; font-size: 13px; }
</style>
