<template>
  <div class="chat-input" :class="{ 'has-content': hasMessages }">
    <div class="input-wrapper">
      <div class="mention-dropdown" v-if="showMention">
        <div v-for="f in mentionFiles" :key="f" class="mention-item" @click="insertMention(f)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mention-file-icon">
            <path d="M14.5 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          {{ f }}
        </div>
        <div v-if="mentionFiles.length === 0" class="mention-empty">无匹配文件</div>
      </div>
      <div class="input-row">
        <label class="upload-btn" title="上传文件">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
          </svg>
          <input type="file" hidden @change="onUpload" accept=".csv,.xlsx,.xls" />
        </label>
        <textarea ref="inputRef" v-model="text" @keydown.enter.exact.prevent="handleSend"
          @keydown.escape="text=''" @input="onInput"
          :disabled="disabled" placeholder="输入分析需求，@ 引用文件..." rows="1" />
        <button @click="handleSend" :disabled="!text.trim() || disabled || isLoading" class="send-btn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="19" x2="12" y2="5"/>
            <polyline points="5 12 12 5 19 12"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="disclaimer">数据分析 Agent 可能产生错误信息，请核实重要数据</div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/sessionStore'
import { useFileStore } from '../stores/fileStore'

const props = defineProps({
  sessionId: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  isLoading: { type: Boolean, default: false },
  hasMessages: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])
const router = useRouter()

// ── 本地状态 ──
const text = ref('')
const showMention = ref(false)
const mentionStart = ref(0)
const selectedMentions = ref([])
const inputRef = ref(null)

// ── @mention 文件列表 ──
const mentionFiles = computed(() => {
  const tree = useFileStore().tree
  const files = []
  const flatten = (items, p = '') => items.forEach(i => {
    const fp = p + '/' + i.name
    if (i.type === 'file') files.push(fp)
    if (i.children) flatten(i.children, fp)
  })
  flatten(tree)
  return files
})

// ── 发送 ──
function handleSend() {
  if (!text.value.trim() || props.disabled || props.isLoading) return
  const content = text.value
  const mentions = [...selectedMentions.value]
  text.value = ''
  selectedMentions.value = []
  emit('send', { content, mentions })
}

// ── @mention 处理 ──
function onInput(e) {
  const match = text.value.slice(0, e.target.selectionStart).match(/@([^\s@]*)$/)
  showMention.value = !!match
  if (match) mentionStart.value = e.target.selectionStart - match[1].length - 1
}

function insertMention(f) {
  text.value = text.value.slice(0, mentionStart.value) + '@' + f + ' '
  selectedMentions.value.push(f)
  showMention.value = false
  inputRef.value?.focus()
}

// ── 上传文件 ──
async function onUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const sessionStore = useSessionStore()

  // 无有效 session → 先创建再上传
  if (!props.sessionId || props.sessionId === 'new' || props.sessionId === 'undefined') {
    const s = await sessionStore.createSession()
    await useFileStore().upload(s.session_id, file)
    router.push(`/session/${s.session_id}`)
    return
  }
  await useFileStore().upload(props.sessionId, file)
}

// ── 对外暴露 (供父组件在失败时恢复输入) ──
defineExpose({
  restore(inputText, mentions) {
    text.value = inputText
    selectedMentions.value = mentions || []
    nextTick(() => inputRef.value?.focus())
  },
})
</script>

<style scoped>
.chat-input {
  padding: 0 var(--spacing-2xl) var(--spacing-2xl);
  flex-shrink: 0;
}
.chat-input.has-content {
  padding: var(--spacing-md) var(--spacing-2xl) var(--spacing-lg);
  border-top: 1px solid var(--color-border);
}

.input-wrapper {
  position: relative;
  max-width: var(--chat-max-width);
  margin: 0 auto;
}

.mention-dropdown {
  position: absolute;
  bottom: calc(100% + var(--spacing-xs));
  left: 0;
  right: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  max-height: 200px;
  overflow-y: auto;
  box-shadow: var(--shadow-dropdown);
  z-index: var(--z-dropdown);
}

.mention-item {
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  font-size: var(--font-size-base);
  color: var(--color-text);
  transition: background var(--transition-fast);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}
.mention-item:hover { background: var(--color-bg-muted); }
.mention-item:first-child { border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
.mention-item:last-child { border-radius: 0 0 var(--radius-lg) var(--radius-lg); }

.mention-file-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}

.mention-empty {
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
}

.input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-input);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input-row:focus-within {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px rgba(57, 100, 254, 0.15), var(--shadow-input);
}

textarea {
  flex: 1;
  padding: var(--spacing-md) var(--spacing-md) 0 var(--spacing-lg);
  border: none;
  font-size: var(--font-size-md);
  line-height: 1.6;
  resize: none;
  outline: none;
  font-family: inherit;
  color: var(--color-text);
  background: transparent;
  max-height: 120px;
}
textarea::placeholder { color: var(--color-text-muted); }
textarea:disabled { color: var(--color-text-muted); cursor: not-allowed; }

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  padding: 0;
  background: var(--color-primary);
  color: var(--color-text-inverse);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), transform var(--transition-fast), opacity var(--transition-fast);
  margin-bottom: 2px;
}
.send-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: scale(1.05);
}
.send-btn:active:not(:disabled) { transform: scale(0.95); }
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.upload-btn {
  cursor: pointer;
  padding: var(--spacing-xs);
  color: var(--color-text-muted);
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
}
.upload-btn:hover {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.disclaimer {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  text-align: center;
  padding-top: var(--spacing-sm);
  max-width: var(--chat-max-width);
  margin: 0 auto;
}
</style>
