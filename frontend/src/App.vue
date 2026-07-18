<template>
  <div class="app-container">
    <SessionSidebar />
    <router-view />
    <WorktreePanel />
  </div>
</template>

<script>
import SessionSidebar from './components/SessionSidebar.vue'
import WorktreePanel from './components/WorktreePanel.vue'

export default {
  components: { SessionSidebar, WorktreePanel },
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
