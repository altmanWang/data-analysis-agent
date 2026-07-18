<template>
  <div class="tree-node" :style="{ paddingLeft: depth * 16 + 12 + 'px' }">
    <div class="node-row" @click="toggle" @contextmenu.prevent="showMenu = !showMenu">
      <span class="node-icon">{{ expanded ? '📂' : '📁' }}</span>
      <span class="node-name" @click.stop="item.type === 'file' && $emit('preview', getFullPath())">{{ item.name }}</span>
      <span v-if="item.size" class="node-size">{{ fmtSize(item.size) }}</span>
    </div>
    <div v-if="showMenu" class="ctx-menu">
      <div @click="$emit('preview', getFullPath()); showMenu = false">预览</div>
      <div @click="$emit('delete', getFullPath()); showMenu = false">删除</div>
    </div>
    <template v-if="expanded && item.children">
      <TreeNode v-for="child in item.children" :key="child.name"
        :item="child" :depth="depth + 1" :sessionId="sessionId"
        @preview="p => $emit('preview', p)" @delete="d => $emit('delete', d)" />
    </template>
  </div>
</template>

<script>
export default {
  name: 'TreeNode',
  props: { item: Object, depth: Number, sessionId: String },
  emits: ['preview', 'delete'],
  data: () => ({ expanded: false, showMenu: false }),
  methods: {
    toggle() { if (this.item.type === 'dir') this.expanded = !this.expanded },
    getFullPath() { return '/' + this.item.name },
    fmtSize(b) {
      if (!b) return ''
      if (b < 1024) return b + 'B'
      if (b < 1048576) return (b / 1024).toFixed(1) + 'KB'
      return (b / 1048576).toFixed(1) + 'MB'
    },
  },
}
</script>

<style scoped>
.node-row { display: flex; align-items: center; padding: 5px 0; cursor: pointer; font-size: 13px; gap: 4px; }
.node-row:hover { background: #edf2f7; border-radius: 4px; }
.node-icon { font-size: 14px; width: 20px; text-align: center; }
.node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-size { font-size: 11px; color: #a0aec0; }
.ctx-menu { position: absolute; background: white; border: 1px solid #e2e8f0; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10; font-size: 12px; }
.ctx-menu div { padding: 6px 16px; cursor: pointer; }
.ctx-menu div:hover { background: #ebf8ff; }
</style>
