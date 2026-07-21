import { defineStore } from 'pinia'

export const useFileStore = defineStore('file', {
  state: () => ({
    tree: [],
    previewPath: null,
    previewContent: null,
    previewMime: null,
    previewBlobUrl: null,
  }),
  actions: {
    async fetchTree(sessionId) {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/files`)
        if (!res.ok) throw new Error(`获取文件列表失败: ${res.status}`)
        const data = await res.json()
        this.tree = data.tree || []
      } catch (e) {
        console.error('获取文件列表失败:', e)
      }
    },
    async upload(sessionId, file) {
      try {
        const form = new FormData()
        form.append('file', file)
        const res = await fetch(`/api/sessions/${sessionId}/files`, { method: 'POST', body: form })
        if (!res.ok) throw new Error(`上传失败: ${res.status}`)
        await this.fetchTree(sessionId)
      } catch (e) {
        console.error('上传文件失败:', e)
        throw e
      }
    },
    async preview(sessionId, path) {
      try {
        this.previewPath = path
        const res = await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`)
        if (!res.ok) throw new Error(`预览失败: ${res.status}`)
        const mime = res.headers.get('content-type')
        this.previewMime = mime

        // 图片和 HTML 用 Blob URL，文本用 text()
        if (mime && (mime.startsWith('image/') || mime.startsWith('text/html'))) {
          const blob = await res.blob()
          if (this.previewBlobUrl) URL.revokeObjectURL(this.previewBlobUrl)
          this.previewBlobUrl = URL.createObjectURL(blob)
          this.previewContent = null
        } else {
          this.previewContent = await res.text()
          this.previewBlobUrl = null
        }
      } catch (e) {
        console.error('预览文件失败:', e)
        this.previewPath = null
      }
    },
    async deleteFile(sessionId, path) {
      try {
        const res = await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`, { method: 'DELETE' })
        if (!res.ok) throw new Error(`删除文件失败: ${res.status}`)
        await this.fetchTree(sessionId)
      } catch (e) {
        console.error('删除文件失败:', e)
      }
    },
    reset() {
      // 清理 Blob URL 防止内存泄漏
      if (this.previewBlobUrl) URL.revokeObjectURL(this.previewBlobUrl)
      this.tree = []
      this.previewPath = null
      this.previewContent = null
      this.previewMime = null
      this.previewBlobUrl = null
    },
  },
})
