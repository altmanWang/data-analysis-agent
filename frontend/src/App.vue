<template>
  <div class="app-container">
    <SessionSidebar @open-agent-manager="showAgentManager = true" />
    <router-view :key="$route.params.id" />
    <WorktreePanel
      v-if="fileStore.tree.length > 0 || fileStore.previewPath"
      ref="worktreePanel"
      :sessionId="$route.params.id"
      @update:collapsed="panelCollapsed = $event"
    />
    <button
      v-if="panelCollapsed && (fileStore.tree.length > 0 || fileStore.previewPath)"
      class="floating-panel-toggle"
      @click="$refs.worktreePanel.togglePanel()"
      title="展开面板"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>
    <AgentManagerModal :visible="showAgentManager" @close="showAgentManager = false" />
  </div>
</template>

<script>
import { ref, provide } from 'vue'
import SessionSidebar from './components/SessionSidebar.vue'
import WorktreePanel from './components/WorktreePanel.vue'
import AgentManagerModal from './components/AgentManagerModal.vue'
import { useFileStore } from './stores/fileStore'

export default {
  components: { SessionSidebar, WorktreePanel, AgentManagerModal },
  data: () => ({
    panelCollapsed: false,
  }),
  setup() {
    const showAgentManager = ref(false)
    provide('showAgentManager', showAgentManager)
    provide('openAgentManager', () => { showAgentManager.value = true })
    return { fileStore: useFileStore(), showAgentManager }
  },
}
</script>

<style>
.app-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--color-bg);
}

.floating-panel-toggle {
  position: fixed;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  cursor: pointer;
  color: var(--color-text-muted);
  z-index: var(--z-sticky);
  transition: color var(--transition-fast), background var(--transition-fast);
  box-shadow: var(--shadow-dropdown);
  padding: 0;
}

.floating-panel-toggle:hover {
  color: var(--color-primary);
  background: var(--color-bg-hover);
}
</style>
