<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Agent 管理</h3>
          <button class="close-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <!-- 创建/编辑表单 -->
        <div class="form-section">
          <label class="form-label">Agent 名称</label>
          <input v-model="formName" class="form-input" placeholder="例如: 代码审查助手" maxlength="100" />

          <label class="form-label">描述（用于路由判断）</label>
          <input v-model="formDesc" class="form-input" placeholder="例如: 审查代码安全性、性能和最佳实践" maxlength="500" />

          <label class="form-label">系统提示词</label>
          <textarea v-model="formPrompt" class="form-textarea" rows="6"
            placeholder="描述 Agent 的角色、职责和工作流程..."
            maxlength="50000" />

          <div class="form-actions">
            <button class="btn btn-primary" @click="onSave" :disabled="!formName.trim() || !formPrompt.trim()">
              {{ editingId ? '保存修改' : '创建 Agent' }}
            </button>
            <button v-if="editingId" class="btn btn-ghost" @click="resetForm">取消编辑</button>
          </div>
        </div>

        <!-- 已有 Agent 列表 -->
        <div class="list-section" v-if="store.agents.length > 0">
          <div class="list-header">已创建的 Agent</div>
          <div v-for="agent in store.agents" :key="agent.id" class="agent-card" @click="editAgent(agent)">
            <div class="card-body">
              <span class="card-name">{{ agent.name }}</span>
              <span class="card-desc">{{ agent.description || '无描述' }}</span>
              <span class="card-prompt">{{ agent.system_prompt.slice(0, 40) }}{{ agent.system_prompt.length > 40 ? '...' : '' }}</span>
            </div>
            <button class="card-del" @click.stop="onDelete(agent.id)" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
        <div v-else class="list-empty">暂无自定义 Agent，在上方创建第一个</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useSessionStore } from '../stores/sessionStore'

const props = defineProps({ visible: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const store = useSessionStore()

// 打开弹窗时刷新 agent 列表
watch(() => props.visible, (v) => {
  if (v) store.fetchAgents()
})

const formName = ref('')
const formDesc = ref('')
const formPrompt = ref('')
const editingId = ref(null)

function resetForm() {
  formName.value = ''
  formDesc.value = ''
  formPrompt.value = ''
  editingId.value = null
}

function editAgent(agent) {
  formName.value = agent.name
  formDesc.value = agent.description || ''
  formPrompt.value = agent.system_prompt
  editingId.value = agent.id
}

async function onSave() {
  if (!formName.value.trim() || !formPrompt.value.trim()) return
  try {
    if (editingId.value) {
      // 编辑模式：通过 PUT 更新
      await fetch(`/api/agents/${editingId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: formName.value.trim(), description: formDesc.value.trim(), system_prompt: formPrompt.value.trim() }),
      })
    } else {
      await store.createAgent(formName.value.trim(), formDesc.value.trim(), formPrompt.value.trim())
    }
    resetForm()
    await store.fetchAgents()
  } catch (e) {
    alert('保存失败: ' + e.message)
  }
}

async function onDelete(id) {
  if (!confirm('确定要删除这个 Agent？')) return
  try {
    await store.deleteAgent(id)
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

.form-section {
  padding: var(--spacing-lg) var(--spacing-xl);
  flex-shrink: 0;
}
.form-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-xs);
  margin-top: var(--spacing-md);
}
.form-label:first-child { margin-top: 0; }
.form-input, .form-textarea {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-family: inherit;
  color: var(--color-text);
  background: var(--color-bg);
  outline: none;
  transition: border-color var(--transition-fast);
}
.form-input:focus, .form-textarea:focus {
  border-color: var(--color-border-focus);
}
.form-textarea { resize: vertical; min-height: 100px; }
.form-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}
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
.btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}
.btn-ghost:hover { background: var(--color-bg-hover); }

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
.agent-card {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.agent-card:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
}
.card-body {
  flex: 1;
  min-width: 0;
}
.card-name {
  display: block;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
}
.card-desc {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 1px;
}
.card-prompt {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
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
