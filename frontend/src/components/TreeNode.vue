<template>
  <div class="tree-node" :style="{ paddingLeft: depth * 16 + 12 + 'px' }">
    <div class="node-row" @click="toggle" @contextmenu.prevent="showMenu = !showMenu">
      <span class="node-icon" :style="item.type !== 'dir' ? { color: fileIconColor } : {}">
        <template v-if="item.type === 'dir'">
          <svg v-if="expanded" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <path d="M9 14l2 2 4-4"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </template>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
      </span>
      <span class="node-name" @click.stop="item.type === 'file' && $emit('preview', getFullPath())">{{ item.name }}</span>
      <span v-if="item.size" class="node-size">{{ fmtSize(item.size) }}</span>
    </div>
    <div v-if="showMenu" class="ctx-menu">
      <div @click="$emit('preview', getFullPath()); showMenu = false">预览</div>
      <div @click="$emit('delete', getFullPath()); showMenu = false">删除</div>
    </div>
    <template v-if="expanded && item.children">
      <TreeNode v-for="child in item.children" :key="child.name"
        :item="child" :depth="depth + 1" :sessionId="sessionId" :parentPath="getFullPath()"
        @preview="p => $emit('preview', p)" @delete="d => $emit('delete', d)" />
    </template>
  </div>
</template>

<script>
export default {
  name: 'TreeNode',
  props: { item: Object, depth: Number, sessionId: String, parentPath: { type: String, default: '' } },
  emits: ['preview', 'delete'],
  data: () => ({ expanded: false, showMenu: false }),
  mounted() {
    // depth <= 1 的目录自动展开（根目录 + 第一层如 reports/）
    if (this.item.type === 'dir' && this.item.children && this.item.children.length > 0 && this.depth <= 1) {
      this.expanded = true
    }
  },
  computed: {
    fileIconColor() {
      if (this.item.type === 'dir') return null
      const ext = (this.item.ext || this.item.name || '').split('.').pop()?.toLowerCase()
      const colorMap = {
        csv: 'var(--color-accent)',
        xlsx: 'var(--color-secondary)',
        xls: 'var(--color-secondary)',
        html: 'var(--color-warning)',
        htm: 'var(--color-warning)',
        png: '#7C3AED',
        jpg: '#7C3AED',
        jpeg: '#7C3AED',
        gif: '#7C3AED',
        svg: '#7C3AED',
        webp: '#7C3AED',
      }
      return colorMap[ext] || 'var(--color-text-muted)'
    },
  },
  methods: {
    toggle() { if (this.item.type === 'dir') this.expanded = !this.expanded },
    getFullPath() { return this.parentPath + '/' + this.item.name },
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
.tree-node {
  position: relative;
}

.node-row {
  display: flex;
  align-items: center;
  padding: 5px var(--spacing-xs);
  cursor: pointer;
  font-size: var(--font-size-base);
  gap: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.node-row:hover {
  background: var(--color-bg-hover);
}

.node-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text);
}

.node-name:hover {
  color: var(--color-secondary);
}

.node-size {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.ctx-menu {
  position: absolute;
  left: 12px;
  top: 28px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-dropdown);
  z-index: var(--z-dropdown);
  font-size: var(--font-size-sm);
  min-width: 100px;
  overflow: hidden;
}

.ctx-menu div {
  padding: var(--spacing-xs) var(--spacing-lg);
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.ctx-menu div:hover {
  background: var(--color-primary-light);
  color: var(--color-primary);
}
</style>
