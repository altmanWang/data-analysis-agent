<template>
  <div class="agent-selector">
    <button class="agent-trigger" @click="toggle" :class="{ active: currentAgent }">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/>
        <path d="M8 14v.01"/><path d="M16 14v.01"/><path d="M12 14v.01"/>
        <path d="M5 20h14a2 2 0 0 0 2-2v-3a2 2 0 0 0-4 0v1H7v-1a2 2 0 0 0-4 0v3a2 2 0 0 0 2 2z"/>
      </svg>
      <span class="agent-label">{{ currentAgent ? currentAgent.name : '默认' }}</span>
      <svg class="chevron" :class="{ open: showDropdown }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
    </button>

    <div v-if="showDropdown" class="agent-dropdown">
      <div class="dropdown-header">选择 Agent</div>
      <div class="agent-option" :class="{ selected: !currentAgentId }" @click="selectNone">
        <div class="option-info">
          <span class="option-name">默认</span>
          <span class="option-desc">使用默认数据分析 Agent</span>
        </div>
        <svg v-if="!currentAgentId" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
      <div v-for="agent in store.agents" :key="agent.id"
        class="agent-option" :class="{ selected: currentAgentId === agent.id }"
        @click="select(agent)">
        <div class="option-info">
          <span class="option-name">{{ agent.name }}</span>
          <span class="option-desc">{{ agent.system_prompt.slice(0, 60) }}{{ agent.system_prompt.length > 60 ? '...' : '' }}</span>
        </div>
        <svg v-if="currentAgentId === agent.id" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/>        </svg>
      </div>
      <div v-if="store.agents.length === 0" class="dropdown-empty">暂无自定义 Agent</div>
    </div>

    <div v-if="showDropdown" class="dropdown-backdrop" @click="showDropdown = false" />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useSessionStore } from '../stores/sessionStore'

const props = defineProps({ sessionId: { type: String, default: '' } })
const emit = defineEmits([])

const store = useSessionStore()
const showDropdown = ref(false)

const currentAgent = ref(null)
const currentAgentId = ref(null)

// 同步 store 状态
watch(() => store.currentAgent, (v) => { currentAgent.value = v }, { immediate: true })
watch(() => store.currentAgentId, (v) => { currentAgentId.value = v }, { immediate: true })

function toggle() {
  showDropdown.value = !showDropdown.value
  if (showDropdown.value) store.fetchAgents()
}

async function select(agent) {
  if (!props.sessionId) return
  try {
    await store.selectAgent(props.sessionId, agent.id)
  } catch (e) {
    alert('切换 Agent 失败: ' + e.message)
  }
  showDropdown.value = false
}

async function selectNone() {
  if (!props.sessionId) return
  await store.clearAgent(props.sessionId)
  showDropdown.value = false
}
</script>

<style scoped>
.agent-selector {
  position: relative;
  flex-shrink: 0;
}

.agent-trigger {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}
.agent-trigger:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.agent-trigger.active {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.agent-label {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chevron {
  transition: transform var(--transition-fast);
}
.chevron.open { transform: rotate(180deg); }

.agent-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 300px;
  max-height: 360px;
  overflow-y: auto;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-dropdown);
  z-index: var(--z-dropdown);
}

.dropdown-header {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  font-weight: var(--font-weight-medium);
  border-bottom: 1px solid var(--color-border-light);
}

.agent-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  border-bottom: 1px solid var(--color-border-light);
}
.agent-option:hover { background: var(--color-bg-hover); }
.agent-option.selected { background: var(--color-primary-light); }

.option-info {
  flex: 1;
  min-width: 0;
}
.option-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
  display: block;
}
.option-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.dropdown-footer {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-base);
  color: var(--color-primary);
  cursor: pointer;
  text-align: center;
  transition: background var(--transition-fast);
}
.dropdown-footer:hover { background: var(--color-bg-hover); }

.dropdown-empty {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.dropdown-backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-dropdown) - 1);
}
</style>
