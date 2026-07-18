<template>
  <aside class="worktree-panel" :class="{ collapsed }" :style="panelStyle">
    <div v-show="!collapsed" class="resize-handle" @mousedown="startResize" />
    <div v-show="!collapsed" class="panel-content">
      <div class="panel-tabs">
        <button :class="{ active: activeTab === 'tree' }" @click="activeTab = 'tree'">文件</button>
        <button v-if="fileStore.previewPath" :class="{ active: activeTab === 'preview' }" @click="activeTab = 'preview'">预览</button>
        <button class="collapse-btn" @click="togglePanel" title="收起面板">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>
      <div v-if="activeTab === 'tree'" class="file-tree">
        <div class="tree-header">工作空间</div>
        <div v-if="fileStore.tree.length === 0" class="tree-empty">上传文件开始分析</div>
        <TreeNode v-for="item in fileStore.tree" :key="item.name"
          :item="item" :depth="0" :sessionId="sessionId" parentPath=""
          @preview="onPreview" @delete="onDelete" />
      </div>
      <div v-else class="file-preview">
        <div class="preview-header">
          <span class="preview-path">{{ fileStore.previewPath }}</span>
          <button @click="closePreview" class="close-btn">x</button>
        </div>
        <div class="preview-body">
          <iframe v-if="isHtml" :src="fileStore.previewBlobUrl" class="html-preview" />
          <div v-else-if="isMarkdown" class="md-preview" v-html="renderMd(fileStore.previewContent)" />
          <img v-else-if="isImage" :src="fileStore.previewBlobUrl" class="img-preview" />
          <div v-else class="unsupported">不支持预览此文件类型</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script>
import { useFileStore } from '../stores/fileStore'
import { marked } from 'marked'
import TreeNode from './TreeNode.vue'

const MIN_WIDTH = 200
const MAX_WIDTH = 900

export default {
  components: { TreeNode },
  props: { sessionId: String },
  data: () => ({
    activeTab: 'tree',
    collapsed: false,
    panelWidth: 360,
  }),
  setup() { return { fileStore: useFileStore() } },
  computed: {
    isHtml() { return (this.fileStore.previewMime || '').startsWith('text/html') },
    isMarkdown() { return (this.fileStore.previewMime || '').includes('markdown') || (this.fileStore.previewPath || '').endsWith('.md') },
    isImage() { return (this.fileStore.previewMime || '').startsWith('image/') },
    panelStyle() {
      return {
        '--panel-width': this.collapsed ? '0px' : `${this.panelWidth}px`,
      }
    },
  },
  watch: {
    'fileStore.previewPath'(val) { if (val) this.activeTab = 'preview' },
  },
  methods: {
    renderMd(text) { return marked.parse(text || '') },
    async onPreview(path) { await useFileStore().preview(this.sessionId, path) },
    async onDelete(path) { await useFileStore().deleteFile(this.sessionId, path) },
    closePreview() {
      const s = useFileStore()
      if (s.previewBlobUrl) URL.revokeObjectURL(s.previewBlobUrl)
      s.previewPath = null; s.previewContent = null; s.previewMime = null; s.previewBlobUrl = null
      this.activeTab = 'tree'
    },
    togglePanel() {
      this.collapsed = !this.collapsed
      this.$emit('update:collapsed', this.collapsed)
    },
    startResize(e) {
      e.preventDefault()
      const startX = e.clientX
      const startWidth = this.panelWidth

      const onMove = (ev) => {
        const delta = startX - ev.clientX
        const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta))
        this.panelWidth = newWidth
      }
      const onUp = () => {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
      }

      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    },
  },
}
</script>

<style scoped>
.worktree-panel {
  width: var(--panel-width);
  min-width: var(--panel-width);
  height: 100vh;
  border-left: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  transition: width var(--transition-base), min-width var(--transition-base);
  position: relative;
  flex-shrink: 0;
}

.worktree-panel.collapsed {
  min-width: 0;
  border-left: none;
}

.panel-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── Resize handle (left edge) ── */
.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: var(--z-sticky);
  transition: background var(--transition-fast);
}

.resize-handle:hover,
.resize-handle:active {
  background: var(--color-primary);
  opacity: 0.3;
}

/* ── Panel tabs ── */
.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
}

.panel-tabs button {
  flex: 1;
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  background: none;
  cursor: pointer;
  font-size: var(--font-size-base);
  color: var(--color-text-muted);
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.panel-tabs button:hover {
  color: var(--color-text-secondary);
}

.panel-tabs button.active {
  color: var(--color-primary);
  border-bottom: 2px solid var(--color-primary);
  font-weight: var(--font-weight-medium);
}

.collapse-btn {
  flex: 0 0 auto !important;
  padding: var(--spacing-sm) var(--spacing-sm) !important;
  display: flex;
  align-items: center;
  justify-content: center;
  border-left: 1px solid var(--color-border) !important;
}

.collapse-btn:hover {
  color: var(--color-text) !important;
  background: var(--color-bg-hover) !important;
}

/* ── File tree ── */
.file-tree {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm) 0;
}

.tree-header {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: var(--font-weight-medium);
}

.tree-empty {
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
}

/* ── File preview ── */
.file-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  background: var(--color-bg-muted);
}

.preview-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
  font-family: monospace;
}

.close-btn {
  background: none;
  border: none;
  font-size: var(--font-size-lg);
  cursor: pointer;
  color: var(--color-text-muted);
  line-height: 1;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-btn:hover {
  color: var(--color-text);
  background: var(--color-bg-hover);
}

.preview-body {
  flex: 1;
  overflow-y: auto;
}

.html-preview {
  width: 100%;
  height: 100%;
  border: none;
}

.md-preview {
  padding: var(--spacing-lg);
  line-height: var(--line-height);
  font-size: var(--font-size-md);
}

.img-preview {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  padding: var(--spacing-lg);
}

.unsupported {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
}
</style>
