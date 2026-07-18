<template>
  <aside class="worktree-panel">
    <div class="panel-tabs">
      <button :class="{ active: activeTab === 'tree' }" @click="activeTab = 'tree'">文件</button>
      <button v-if="fileStore.previewPath" :class="{ active: activeTab === 'preview' }" @click="activeTab = 'preview'">预览</button>
    </div>
    <div v-if="activeTab === 'tree'" class="file-tree">
      <div class="tree-header">工作空间</div>
      <div v-if="fileStore.tree.length === 0" class="tree-empty">上传文件开始分析</div>
      <TreeNode v-for="item in fileStore.tree" :key="item.name"
        :item="item" :depth="0" :sessionId="sessionId"
        @preview="onPreview" @delete="onDelete" />
    </div>
    <div v-else class="file-preview">
      <div class="preview-header">
        <span class="preview-path">{{ fileStore.previewPath }}</span>
        <button @click="closePreview" class="close-btn">x</button>
      </div>
      <div class="preview-body">
        <iframe v-if="isHtml" :srcdoc="fileStore.previewContent" class="html-preview" sandbox="allow-scripts allow-same-origin" />
        <div v-else-if="isMarkdown" class="md-preview" v-html="renderMd(fileStore.previewContent)" />
        <img v-else-if="isImage" :src="imgSrc" class="img-preview" />
        <div v-else class="unsupported">不支持预览此文件类型</div>
      </div>
    </div>
  </aside>
</template>

<script>
import { useFileStore } from '../stores/fileStore'
import { marked } from 'marked'
import TreeNode from './TreeNode.vue'

export default {
  components: { TreeNode },
  props: { sessionId: String },
  data: () => ({ activeTab: 'tree' }),
  setup() { return { fileStore: useFileStore() } },
  computed: {
    isHtml() { return this.fileStore.previewMime === 'text/html' },
    isMarkdown() { return this.fileStore.previewMime === 'text/markdown' || (this.fileStore.previewPath || '').endsWith('.md') },
    isImage() { return (this.fileStore.previewMime || '').startsWith('image/') },
    imgSrc() { return `data:${this.fileStore.previewMime};base64,${btoa(this.fileStore.previewContent)}` },
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
      s.previewPath = null; s.previewContent = null; s.previewMime = null
      this.activeTab = 'tree'
    },
  },
}
</script>

<style scoped>
.worktree-panel { width: 360px; min-width: 360px; height: 100vh; border-left: 1px solid #e2e8f0; display: flex; flex-direction: column; background: #f8fafc; }
.panel-tabs { display: flex; border-bottom: 1px solid #e2e8f0; }
.panel-tabs button { flex: 1; padding: 10px; border: none; background: none; cursor: pointer; font-size: 13px; color: #718096; }
.panel-tabs button.active { color: #1a365d; border-bottom: 2px solid #1a365d; font-weight: 500; }
.file-tree { flex: 1; overflow-y: auto; padding: 8px 0; }
.tree-header { padding: 8px 12px; font-size: 11px; color: #a0aec0; }
.tree-empty { padding: 20px; text-align: center; color: #a0aec0; font-size: 13px; }
.file-preview { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.preview-header { display: flex; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 12px; }
.preview-path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #718096; }
.close-btn { background: none; border: none; font-size: 18px; cursor: pointer; color: #a0aec0; }
.preview-body { flex: 1; overflow-y: auto; }
.html-preview { width: 100%; height: 100%; border: none; }
.md-preview { padding: 16px; line-height: 1.7; font-size: 14px; }
.img-preview { max-width: 100%; max-height: 100%; object-fit: contain; padding: 16px; }
.unsupported { display: flex; align-items: center; justify-content: center; height: 100%; color: #a0aec0; }
</style>
