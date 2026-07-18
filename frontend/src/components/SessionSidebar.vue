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
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
}

.sidebar-header {
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
}
.sidebar-header h2 {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
  letter-spacing: -0.01em;
}

.create-btn {
  margin: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: center;
  cursor: pointer;
  background: var(--color-primary);
  color: var(--color-text-inverse);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}
.create-btn:hover {
  background: var(--color-primary-hover);
  box-shadow: var(--shadow-sm);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xs) 0;
}

.session-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  border-left: 3px solid transparent;
  font-size: var(--font-size-base);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.session-item:hover {
  background: var(--color-bg-hover);
}
.session-item.active {
  background: var(--color-bg-active);
  border-left-color: var(--color-secondary);
}

.item-content {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.item-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
  font-size: var(--font-size-base);
}

.item-meta {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  margin-top: var(--spacing-xs);
}

.status.active {
  color: var(--color-success);
  font-weight: var(--font-weight-medium);
}
.status.archiving {
  color: var(--color-warning);
}
.status.archived {
  color: var(--color-text-muted);
}

.del-btn {
  background: none;
  border: none;
  color: var(--color-text-muted);
  font-size: var(--font-size-md);
  cursor: pointer;
  padding: 0 var(--spacing-xs);
  line-height: 1;
  transition: color var(--transition-fast), transform var(--transition-fast);
}
.del-btn:hover {
  color: var(--color-error);
  transform: scale(1.15);
}

.empty {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--spacing-3xl) var(--spacing-lg);
  font-size: var(--font-size-base);
}
</style>
