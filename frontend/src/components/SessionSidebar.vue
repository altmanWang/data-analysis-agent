<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed }">
    <!-- 顶部栏: Logo + 名称 | 收起按钮 -->
    <div class="sidebar-topbar">
      <div class="topbar-logo" @click="$router.push('/')">
        <svg class="logo-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="14" width="4" height="8" rx="1" fill="var(--color-primary)"/>
          <rect x="9" y="9" width="4" height="13" rx="1" fill="var(--color-primary)" opacity="0.7"/>
          <rect x="16" y="4" width="4" height="18" rx="1" fill="var(--color-primary)" opacity="0.45"/>
        </svg>
        <span class="logo-name" v-show="!isCollapsed">Data Analysis</span>
      </div>
      <button class="collapse-toggle" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开' : '收起'">
        <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" class="chevron-icon" :class="{ rotated: isCollapsed }">
          <path d="M12.5 4.17L6.67 10L12.5 15.83" stroke="currentColor" stroke-width="1.67" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>

    <!-- Agent 管理入口 -->
    <button class="agent-entry" @click="$emit('open-agent-manager')" v-show="!isCollapsed">
      <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" class="agent-icon">
        <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z" stroke="currentColor" stroke-width="1.2"/>
        <path d="M8 14v.01M16 14v.01M12 14v.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M5 20h14a2 2 0 0 0 2-2v-3a2 2 0 0 0-4 0v1H7v-1a2 2 0 0 0-4 0v3a2 2 0 0 0 2 2z" stroke="currentColor" stroke-width="1.2" transform="scale(0.67) translate(5, 3)"/>
      </svg>
      <span>Agent</span>
    </button>

    <!-- 搜索框 -->
    <div class="search-box" v-show="!isCollapsed">
      <svg class="search-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="6.67" cy="6.67" r="4.67" stroke="currentColor" stroke-width="1.33"/>
        <path d="M10.67 10.67L14 14" stroke="currentColor" stroke-width="1.33" stroke-linecap="round"/>
      </svg>
      <input
        v-model="searchText"
        type="text"
        class="search-input"
        placeholder="搜索会话..."
      />
    </div>

    <!-- 新建会话按钮 -->
    <button class="new-session-btn" @click="onCreate" v-show="!isCollapsed">
      <svg class="plus-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 3.33V12.67M3.33 8H12.67" stroke="currentColor" stroke-width="1.33" stroke-linecap="round"/>
      </svg>
      <span>开启新会话</span>
    </button>

    <!-- 会话列表 (按时间分组) -->
    <div class="session-list" v-show="!isCollapsed">
      <template v-for="group in groupedSessions" :key="group.label">
        <div class="time-group-header">{{ group.label }}</div>
        <div
          v-for="s in group.items"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === sessionStore.currentId }"
          @click="navigateTo(s.session_id)"
          @mouseenter="hoveredId = s.session_id"
          @mouseleave="handleItemLeave(s.session_id)"
        >
          <span class="item-title">{{ s.title }}</span>
          <div class="item-menu" v-show="hoveredId === s.session_id || openMenuId === s.session_id" @click.stop>
            <button class="menu-trigger" @click="toggleMenu(s.session_id)">
              <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="8" cy="3" r="1.33" fill="currentColor"/>
                <circle cx="8" cy="8" r="1.33" fill="currentColor"/>
                <circle cx="8" cy="13" r="1.33" fill="currentColor"/>
              </svg>
            </button>
            <div class="dropdown-menu" v-if="openMenuId === s.session_id">
              <button class="dropdown-item" @click="startRename(s)">
                <svg viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.33 10.25V11.67H3.75L9.06 6.36L7.64 4.94L2.33 10.25Z" fill="currentColor"/>
                  <path d="M11.07 4.35L9.65 2.93L10.48 2.1C10.87 1.71 11.5 1.71 11.89 2.1L11.9 2.11C12.29 2.5 12.29 3.13 11.9 3.52L11.07 4.35Z" fill="currentColor"/>
                </svg>
                <span>重命名</span>
              </button>
              <button class="dropdown-item danger" @click="onDelete(s.session_id)">
                <svg viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.92 4.08H11.08M5.25 2.33H8.75M5.83 4.08V10.5C5.83 10.82 6.09 11.08 6.42 11.08H7.58C7.91 11.08 8.17 10.82 8.17 10.5V4.08M3.5 4.08L4.08 11.08C4.08 11.73 4.6 12.25 5.25 12.25H8.75C9.4 12.25 9.92 11.73 9.92 11.08L10.5 4.08" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>删除</span>
              </button>
            </div>
          </div>
          <!-- 内联重命名 -->
          <div class="rename-overlay" v-if="renamingId === s.session_id" @click.stop>
            <input
              ref="renameInput"
              v-model="renameTitle"
              class="rename-input"
              @keyup.enter="confirmRename(s)"
              @keyup.escape="cancelRename"
              @blur="cancelRename"
            />
          </div>
        </div>
      </template>
      <div v-if="groupedSessions.length === 0 && sessionStore.sessions.length === 0" class="empty">暂无会话</div>
      <div v-else-if="groupedSessions.length === 0" class="empty">无匹配会话</div>
    </div>

    <!-- 底部用户区域 -->
    <div class="user-area" v-show="!isCollapsed">
      <svg class="user-avatar" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="10" cy="10" r="10" fill="var(--color-bg-muted)"/>
        <circle cx="10" cy="8" r="3.33" fill="var(--color-text-muted)"/>
        <ellipse cx="10" cy="16.67" rx="5.83" ry="3.33" fill="var(--color-text-muted)"/>
      </svg>
      <span class="username">用户</span>
    </div>
  </aside>
</template>

<script>
import { useSessionStore } from '../stores/sessionStore'
import { useFileStore } from '../stores/fileStore'

export default {
  emits: ['open-agent-manager'],
  setup() {
    const s = useSessionStore()
    s.fetchSessions()
    return { sessionStore: s }
  },
  data() {
    return {
      searchText: '',
      isCollapsed: false,
      hoveredId: null,
      openMenuId: null,
      renamingId: null,
      renameTitle: '',
    }
  },
  computed: {
    filteredSessions() {
      const q = this.searchText.trim().toLowerCase()
      if (!q) return this.sessionStore.sessions
      return this.sessionStore.sessions.filter(s =>
        s.title && s.title.toLowerCase().includes(q)
      )
    },
    groupedSessions() {
      const now = new Date()
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      const yesterdayStart = new Date(todayStart.getTime() - 86400000)
      const sevenDaysAgo = new Date(todayStart.getTime() - 7 * 86400000)
      const thirtyDaysAgo = new Date(todayStart.getTime() - 30 * 86400000)

      const predefined = { '今天': [], '昨天': [], '7天内': [], '30天内': [] }
      const monthMap = {}

      for (const s of this.filteredSessions) {
        const d = new Date(s.last_active || s.created_at)
        if (isNaN(d.getTime())) {
          // 无效日期归入其他
          if (!monthMap['更早']) monthMap['更早'] = []
          monthMap['更早'].push(s)
        } else if (d >= todayStart) {
          predefined['今天'].push(s)
        } else if (d >= yesterdayStart) {
          predefined['昨天'].push(s)
        } else if (d >= sevenDaysAgo) {
          predefined['7天内'].push(s)
        } else if (d >= thirtyDaysAgo) {
          predefined['30天内'].push(s)
        } else {
          const key = `${d.getFullYear()}年${String(d.getMonth() + 1).padStart(2, '0')}月`
          if (!monthMap[key]) monthMap[key] = []
          monthMap[key].push(s)
        }
      }

      const result = []
      for (const [label, items] of Object.entries(predefined)) {
        if (items.length > 0) result.push({ label, items })
      }
      for (const label of Object.keys(monthMap).sort().reverse()) {
        result.push({ label, items: monthMap[label] })
      }
      return result
    },
  },
  watch: {
    '$route'() { this.sessionStore.fetchSessions() },
  },
  methods: {
    navigateTo(id) {
      this.$router.push(`/session/${id}`)
    },
    onCreate() {
      // 不创建 session，仅回到居中的首页视图
      // session 只在用户发送消息时由 ChatPanel 自动创建
      this.$router.push('/')
    },
    async onDelete(id) {
      const wasCurrent = this.sessionStore.currentId === id
      await this.sessionStore.deleteSession(id)
      if (wasCurrent) {
        useFileStore().reset()
        if (this.sessionStore.sessions.length > 0) {
          this.$router.push(`/session/${this.sessionStore.sessions[0].session_id}`)
        } else {
          this.$router.push('/')
        }
      }
    },
    toggleMenu(id) {
      this.openMenuId = this.openMenuId === id ? null : id
    },
    startRename(s) {
      this.openMenuId = null
      this.renamingId = s.session_id
      this.renameTitle = s.title || ''
      this.$nextTick(() => {
        const input = this.$refs.renameInput
        if (input) {
          // $refs.renameInput might be an array in v-for
          const el = Array.isArray(input) ? input[input.length - 1] : input
          if (el) {
            el.focus()
            el.select()
          }
        }
      })
    },
    confirmRename(s) {
      const newTitle = this.renameTitle.trim()
      if (newTitle && newTitle !== s.title) {
        s.title = newTitle
        // 可选：调用 store 的 update 方法（如果存在）
        // 目前 store 无 rename API，仅前端更新 title 显示
      }
      this.renamingId = null
      this.renameTitle = ''
    },
    cancelRename() {
      this.renamingId = null
      this.renameTitle = ''
    },
    handleItemLeave(id) {
      this.hoveredId = null
      // 菜单打开时不随 hover 离开而消失
    },
  },
  mounted() {
    // 点击外部关闭菜单
    document.addEventListener('click', this._closeMenu)
  },
  beforeUnmount() {
    document.removeEventListener('click', this._closeMenu)
  },
  beforeCreate() {
    this._closeMenu = (e) => {
      // 如果点击的不是菜单内部，关闭菜单
      if (this.openMenuId) {
        const el = e.target
        if (!el.closest('.item-menu')) {
          this.openMenuId = null
        }
      }
    }
  },
}
</script>

<style scoped>
/* ===== 侧边栏容器 ===== */
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-sidebar);
  border-right: 0.67px solid var(--color-border-light);
  transition: width var(--transition-base);
  overflow: hidden;
}

.sidebar.collapsed {
  width: 56px;
  min-width: 56px;
}

/* ===== 顶部栏 ===== */
.sidebar-topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-md);
  flex-shrink: 0;
  border-bottom: 0.67px solid var(--color-border-light);
}

.topbar-logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.logo-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.logo-name {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  white-space: nowrap;
}

.collapse-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-text-muted);
  flex-shrink: 0;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.collapse-toggle:hover {
  background: var(--color-bg-hover);
  color: var(--color-text);
}

.chevron-icon {
  width: 20px;
  height: 20px;
  transition: transform var(--transition-fast);
}

.chevron-icon.rotated {
  transform: rotate(180deg);
}

/* ===== 搜索框 ===== */
.search-box {
  position: relative;
  margin: var(--spacing-md);
  flex-shrink: 0;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--color-text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 36px;
  padding: 0 var(--spacing-md) 0 32px;
  border: 0.67px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--font-size-sm);
  color: var(--color-text);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.search-input::placeholder {
  color: var(--color-text-muted);
}

.search-input:focus {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}

/* ===== Agent 管理入口 ===== */
.agent-entry {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin: 0 var(--spacing-md) var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-fast), color var(--transition-fast);
  width: calc(100% - var(--spacing-md) * 2);
}
.agent-entry:hover {
  background: var(--color-bg-hover);
  color: var(--color-primary);
}
.agent-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* ===== 新建会话按钮 ===== */
.new-session-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  margin: 0 var(--spacing-md) var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-lg);
  border: 0.67px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
}

.new-session-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.plus-icon {
  width: 16px;
  height: 16px;
}

/* ===== 会话列表 ===== */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xs) 0;
}

/* 时间分组标题 */
.time-group-header {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  font-weight: var(--font-weight-medium);
  padding: 2px 10px;
  user-select: none;
}

/* 会话项 */
.session-item {
  display: flex;
  align-items: center;
  font-size: var(--font-size-base);
  padding: 9px 6px 9px 10px;
  cursor: pointer;
  position: relative;
  transition: background var(--transition-fast);
}

.session-item:hover {
  background: var(--color-bg-hover);
}

.session-item.active {
  background: var(--color-bg-active);
}

.session-item.active .item-title {
  color: var(--color-primary);
}

.item-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: var(--font-weight-normal);
  color: var(--color-text);
  min-width: 0;
}

/* 三点菜单 */
.item-menu {
  position: relative;
  flex-shrink: 0;
  margin-left: var(--spacing-xs);
}

.menu-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.menu-trigger svg {
  width: 16px;
  height: 16px;
}

.menu-trigger:hover {
  background: var(--color-bg-muted);
  color: var(--color-text);
}

/* 下拉菜单 */
.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: var(--z-dropdown);
  min-width: 120px;
  background: var(--color-bg);
  border: 0.67px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-dropdown);
  padding: var(--spacing-xs) 0;
  margin-top: 2px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  background: none;
  font-size: var(--font-size-sm);
  color: var(--color-text);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast);
}

.dropdown-item svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.dropdown-item:hover {
  background: var(--color-bg-hover);
}

.dropdown-item.danger {
  color: var(--color-error);
}

.dropdown-item.danger:hover {
  background: #FEF2F2;
}

/* 内联重命名 */
.rename-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  padding: 0 6px 0 10px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  z-index: 2;
}

.rename-input {
  width: 100%;
  height: 28px;
  padding: 0 var(--spacing-sm);
  border: 1px solid var(--color-border-focus);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  color: var(--color-text);
  background: var(--color-bg);
  outline: none;
}

/* 空状态 */
.empty {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--spacing-3xl) var(--spacing-lg);
  font-size: var(--font-size-base);
}

/* ===== 底部用户区域 ===== */
.user-area {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-top: 0.67px solid var(--color-border-light);
  flex-shrink: 0;
  margin-top: auto;
}

.user-avatar {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.username {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
