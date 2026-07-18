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
* { margin: 0; padding: 0; box-sizing: border-box; }
.app-container {
  display: flex; height: 100vh; overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
</style>
