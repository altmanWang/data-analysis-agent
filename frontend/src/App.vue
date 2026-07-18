<template>
  <div class="app-container">
    <SessionSidebar />
    <router-view :key="$route.params.id" />
    <WorktreePanel v-if="fileStore.tree.length > 0 || fileStore.previewPath" :sessionId="$route.params.id" />
  </div>
</template>

<script>
import SessionSidebar from './components/SessionSidebar.vue'
import WorktreePanel from './components/WorktreePanel.vue'
import { useFileStore } from './stores/fileStore'

export default {
  components: { SessionSidebar, WorktreePanel },
  setup() {
    return { fileStore: useFileStore() }
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
</style>
