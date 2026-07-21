<template>
  <div class="chat-input" :class="{ 'has-content': hasMessages }">
    <div class="mention-dropdown" v-if="showMention">
      <div v-for="f in mentionFiles" :key="f" class="mention-item" @click="insertMention(f)">{{ f }}</div>
      <div v-if="mentionFiles.length === 0" class="mention-empty">无匹配文件</div>
    </div>
    <div class="input-row">
      <label class="upload-btn" title="上传文件">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <input type="file" hidden @change="onUpload" accept=".csv,.xlsx,.xls" />
      </label>
      <textarea ref="inputRef" v-model="text" @keydown.enter.exact.prevent="handleSend"
        @keydown.escape="text=''" @input="onInput"
        :disabled="disabled" placeholder="输入分析需求，@ 引用文件..." rows="1" />
      <button @click="handleSend" :disabled="!text.trim() || disabled || isLoading" class="send-btn">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
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
  position: relative;
  flex-shrink: 0;
}
.chat-input.has-content {
  padding: var(--spacing-md) var(--spacing-2xl) var(--spacing-lg);
  border-top: 1px solid #CBD5E1;
}
.input-row {
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-sm);
  max-width: 800px;
  margin: 0 auto;
  border: 1px solid #CBD5E1;
  border-radius: var(--radius-xl);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input-row:focus-within {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.has-content .input-row {
  border: 1px solid #CBD5E1;
  border-radius: var(--radius-lg);
  padding: var(--spacing-xs) var(--spacing-md);
  background: var(--color-bg-card);
}
textarea {
  flex: 1;
  padding: var(--spacing-sm) 0;
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
  width: 32px;
  height: 32px;
  padding: 0;
  background: var(--color-text);
  color: var(--color-text-inverse);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), transform var(--transition-fast);
  margin-bottom: 2px;
}
.send-btn:hover:not(:disabled) { background: var(--color-primary); }
.send-btn:active:not(:disabled) { transform: scale(0.92); }
.send-btn:disabled { background: var(--color-border); cursor: not-allowed; }
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
  width: 28px;
  height: 28px;
}
.upload-btn:hover { color: var(--color-text); background: var(--color-bg-muted); }
.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: var(--spacing-2xl);
  right: var(--spacing-2xl);
  max-width: 800px;
  margin: 0 auto var(--spacing-xs);
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
}
.mention-item:hover { background: var(--color-bg-muted); }
.mention-item:first-child { border-radius: var(--radius-lg) var(--radius-lg) 0 0; }
.mention-item:last-child { border-radius: 0 0 var(--radius-lg) var(--radius-lg); }
.mention-empty {
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-muted);
  font-size: var(--font-size-base);
}
</style>
