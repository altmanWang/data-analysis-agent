<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Skill 管理</h3>
          <button class="close-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <!-- 上传区域 -->
        <div class="upload-section">
          <div class="section-label">上传 Skill 包</div>
          <div class="upload-row">
            <label class="file-picker-label">
              <input
                ref="fileInputRef"
                type="file"
                accept=".zip"
                class="file-picker-input"
                @change="onFileChange"
              />
              <span class="file-picker-btn">选择文件</span>
            </label>
            <span class="file-name">{{ selectedFile ? selectedFile.name : '未选择文件' }}</span>
            <button
              class="btn btn-primary btn-upload"
              :disabled="!selectedFile || uploading"
              @click="onUpload"
            >
              {{ uploading ? '上传中...' : '上传' }}
            </button>
          </div>
          <div v-if="uploadStatus" class="upload-status" :class="{ 'upload-error': uploadError }">
            {{ uploadStatus }}
          </div>
        </div>

        <!-- 已安装列表 -->
        <div class="list-section">
          <div class="list-header">已安装的 Skills</div>
          <div v-if="loading" class="list-loading">加载中...</div>
          <template v-else-if="skills.length > 0">
            <div v-for="skill in skills" :key="skill.id" class="skill-card">
              <div class="card-body">
                <span class="card-name">
                  <svg class="card-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                  {{ skill.display_name || skill.name }}
                </span>
                <span class="card-desc">{{ skill.description || '无描述' }}</span>
              </div>
              <button class="card-del" @click="onDelete(skill)" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </template>
          <div v-else class="list-empty">暂无已安装的 Skill，上传 .zip 包开始使用</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ visible: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const fileInputRef = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)
const uploadStatus = ref('')
const uploadError = ref(false)
const skills = ref([])
const loading = ref(false)

watch(() => props.visible, (v) => {
  if (v) {
    fetchSkills()
    resetUpload()
  }
})

function onFileChange(e) {
  selectedFile.value = e.target.files[0] || null
  uploadStatus.value = ''
  uploadError.value = false
}

function resetUpload() {
  selectedFile.value = null
  uploadStatus.value = ''
  uploadError.value = false
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function fetchSkills() {
  loading.value = true
  try {
    const res = await fetch('/api/skills')
    if (!res.ok) throw new Error('获取列表失败')
    skills.value = await res.json()
  } catch (e) {
    skills.value = []
  } finally {
    loading.value = false
  }
}

async function onUpload() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadStatus.value = '上传中...'
  uploadError.value = false
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await fetch('/api/skills/upload', { method: 'POST', body: formData })
    if (!res.ok) {
      const errData = await res.json().catch(() => null)
      throw new Error(errData?.detail || `上传失败 (${res.status})`)
    }
    const skill = await res.json()
    uploadStatus.value = `上传成功: ${skill.display_name || skill.name}`
    uploadError.value = false
    resetUpload()
    await fetchSkills()
  } catch (e) {
    uploadStatus.value = e.message
    uploadError.value = true
  } finally {
    uploading.value = false
  }
}

async function onDelete(skill) {
  if (!confirm(`确定要删除 "${skill.display_name || skill.name}"？`)) return
  try {
    const res = await fetch(`/api/skills/${skill.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`删除失败 (${res.status})`)
    skills.value = skills.value.filter(s => s.id !== skill.id)
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-scrim);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
}
.modal-container {
  width: 520px;
  max-height: 80vh;
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}
.modal-header h3 {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
}
.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}
.close-btn:hover { background: var(--color-bg-hover); }

/* ─── 上传 ─── */
.upload-section {
  padding: var(--spacing-lg) var(--spacing-xl);
  flex-shrink: 0;
}
.section-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-sm);
}
.upload-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}
.file-picker-label {
  cursor: pointer;
}
.file-picker-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  overflow: hidden;
}
.file-picker-btn {
  display: inline-block;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  background: var(--color-bg);
  transition: border-color var(--transition-fast), background var(--transition-fast);
  user-select: none;
  white-space: nowrap;
}
.file-picker-btn:hover { border-color: var(--color-primary); background: var(--color-bg-hover); }
.file-name {
  flex: 1;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.btn-upload {
  flex-shrink: 0;
}
.upload-status {
  margin-top: var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--color-success);
}
.upload-status.upload-error { color: var(--color-error); }

/* ─── 按钮 ─── */
.btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  cursor: pointer;
  font-family: inherit;
  transition: background var(--transition-fast);
}
.btn-primary {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

/* ─── 列表 ─── */
.list-section {
  flex: 1;
  overflow-y: auto;
  border-top: 1px solid var(--color-border-light);
  padding: var(--spacing-md) var(--spacing-xl) var(--spacing-lg);
}
.list-header {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--spacing-sm);
}
.list-loading {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--spacing-xl);
  font-size: var(--font-size-base);
}
.skill-card {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-sm);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.skill-card:hover { background: var(--color-bg-hover); }
.card-body {
  flex: 1;
  min-width: 0;
}
.card-icon {
  vertical-align: middle;
  margin-right: var(--spacing-xs);
  color: var(--color-text-muted);
  flex-shrink: 0;
}
.card-name {
  display: flex;
  align-items: center;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
}
.card-desc {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 2px;
  padding-left: 22px;
}
.card-del {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted);
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast);
  flex-shrink: 0;
}
.card-del:hover { color: var(--color-error); }
.list-empty {
  text-align: center;
  color: var(--color-text-muted);
  padding: var(--spacing-2xl);
  font-size: var(--font-size-base);
}
</style>
