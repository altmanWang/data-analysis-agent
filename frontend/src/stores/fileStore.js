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
      const res = await fetch(`/api/sessions/${sessionId}/files`)
      const data = await res.json()
      this.tree = data.tree || []
    },
    async upload(sessionId, file) {
      const form = new FormData()
      form.append('file', file)
      await fetch(`/api/sessions/${sessionId}/files`, { method: 'POST', body: form })
      await this.fetchTree(sessionId)
    },
    async preview(sessionId, path) {
      this.previewPath = path
      const res = await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`)
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
    },
    async deleteFile(sessionId, path) {
      await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`, { method: 'DELETE' })
      await this.fetchTree(sessionId)
    },
  },
})
