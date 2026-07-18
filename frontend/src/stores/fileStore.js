import { defineStore } from 'pinia'

export const useFileStore = defineStore('file', {
  state: () => ({
    tree: [],
    previewPath: null,
    previewContent: null,
    previewMime: null,
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
      this.previewMime = res.headers.get('content-type')
      this.previewContent = await res.text()
    },
    async deleteFile(sessionId, path) {
      await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`, { method: 'DELETE' })
      await this.fetchTree(sessionId)
    },
  },
})
