<template>
  <div class="chat-panel" :class="{ 'has-messages': hasContent }">
    <div v-if="hasValidThread && sessionTitle" class="chat-topbar">
      <span class="topbar-title">{{ sessionTitle }}</span>
      <span class="topbar-mode-tag">数据分析模式</span>
    </div>

    <div class="chat-messages" ref="msgContainer" @scroll="onScroll">
      <WelcomeScreen v-if="!id && timelineItems.length === 0" />
      <MessageList :items="timelineItems" :sessionId="id" :isLoading="isLoading" />
      <div ref="bottom" />
      <div v-show="showScrollBtn" class="scroll-bottom-wrapper">
        <button class="scroll-to-bottom" @click="scrollToBottom" aria-label="滚动到底部">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="4,6 8,10 12,6" />
          </svg>
        </button>
      </div>
    </div>

    <ChatInput ref="chatInputRef" :sessionId="id" :disabled="sessionStatus === 'archived'" :isLoading="isLoading"
      :hasMessages="hasContent" @send="onSend" />
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, watch, nextTick, onMounted, onBeforeUnmount, provide } from 'vue'
import { useRouter } from 'vue-router'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useSessionStore } from '../stores/sessionStore'
import { useFileStore } from '../stores/fileStore'
import WelcomeScreen from './WelcomeScreen.vue'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'

const props = defineProps({ id: String })
const router = useRouter()

// ── 本地状态 ──
const msgContainer = ref(null)
const bottom = ref(null)
const chatInputRef = ref(null)
const sessionTitle = ref('')
const sessionStatus = ref('active')
const timelineItems = shallowRef([])
const isLoading = ref(false)
const showScrollBtn = ref(false)
let abortController = null

// ── 计算属性 ──
const hasValidThread = computed(() => props.id && props.id !== 'new')
const hasContent = computed(() => timelineItems.value.length > 0)

// ── provide: shallowRef 刷新机制（浅拷贝目标 item 确保 Vue 检测到变化）──
provide('toggleItemExpand', (itemId) => {
  timelineItems.value = timelineItems.value.map(i =>
    i.id === itemId ? { ...i, _expanded: !i._expanded } : i
  )
})

// ── 会话信息加载 ──
onMounted(async () => {
  const sessionStore = useSessionStore()
  if (hasValidThread.value) {
    sessionStore.currentId = props.id
    try {
      const m = await sessionStore.fetchSession(props.id)
      sessionTitle.value = m.title
      sessionStatus.value = m.status
      useFileStore().fetchTree(props.id)
      await loadHistory()
    } catch { router.push('/') }
    if (sessionStore.pendingInput) {
      const p = sessionStore.pendingInput
      sessionStore.pendingInput = null
      nextTick(() => { chatInputRef.value?.restore(p.text, p.mentions); doSend(p.text, p.mentions) })
    }
  } else {
    sessionStore.currentId = null
    useFileStore().reset()
  }
})

// ── 加载历史 ──
async function loadHistory() {
  try {
    const res = await fetch(`/api/threads/${props.id}/messages`)
    if (!res.ok) throw new Error(`加载历史失败: ${res.status}`)
    const rows = await res.json()
    if (!rows?.length) return
    const items = []
    for (const r of rows) {
      if (r.role === 'tool') {
        items.push({
          id: `${props.id}-tool-${Math.random()}`, kind: 'tool_call', role: 'tool',
          name: r.tool_name || '', input: r.tool_args || '',
          status: r.tool_status || 'done', result: r.tool_result || null, _expanded: false,
        })
      } else {
        items.push({
          id: `${props.id}-${r.role}-${Math.random()}`, kind: 'message',
          role: r.role === 'assistant' ? 'assistant' : 'user',
          content: r.content || '', done: true,
          thinking: r.thinking_content || '',
        })
      }
    }
    if (items.length > 0) timelineItems.value = items
  } catch (e) { console.error('加载历史失败:', e) }
}

// ── 自动滚动 ──
function autoScroll() {
  const el = msgContainer.value
  if (!el) return
  if (el.scrollHeight - el.scrollTop - el.clientHeight > 150) return
  nextTick(() => bottom.value?.scrollIntoView({ behavior: 'smooth' }))
}
watch(() => timelineItems.value.length, () => { nextTick(() => autoScroll()) })

// ── 滚动检测 ──
function onScroll() {
  const el = msgContainer.value
  if (!el) return
  showScrollBtn.value = el.scrollHeight - el.scrollTop - el.clientHeight > 150
}

function scrollToBottom() {
  bottom.value?.scrollIntoView({ behavior: 'smooth' })
}

// ── ChatInput send 事件处理 ──
function onSend({ content, mentions }) {
  doSend(content, mentions)
}

async function doSend(content, _mentions) {
  if (!hasValidThread.value) {
    const sessionStore = useSessionStore()
    sessionStore.pendingInput = { text: content, mentions: [] }
    try {
      const res = await fetch('/api/sessions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: content.slice(0, 50) }),
      })
      router.push(`/session/${(await res.json()).session_id}`)
    } catch { chatInputRef.value?.restore(content, []); sessionStore.pendingInput = null }
    return
  }

  isLoading.value = true
  abortController = new AbortController()

  timelineItems.value = [...timelineItems.value, {
    id: Date.now().toString(), kind: 'message', role: 'user', content, done: true,
  }]

  const tid = props.id
  let currentMsgId = null
  let currentText = ''
  let currentThinkingId = null
  let currentThinking = ''

  try {
    await fetchEventSource(`/api/threads/${tid}/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      signal: abortController.signal,
      openWhenHidden: true,

      onmessage(event) {
        if (!event.data) return
        let data
        try { data = JSON.parse(event.data) } catch { return }

        if (data.type === 'thinking') {
          if (!currentThinkingId) {
            currentThinkingId = `${Date.now()}-think`
            timelineItems.value = [...timelineItems.value, {
              id: currentThinkingId, kind: 'thinking', role: 'assistant',
              content: '', _expanded: false,
            }]
          }
          currentThinking += data.content
          timelineItems.value = timelineItems.value.map(i =>
            i.id === currentThinkingId ? { ...i, content: currentThinking } : i)
        } else if (data.type === 'text') {
          if (!currentMsgId) {
            currentMsgId = `${Date.now()}-ai`
            timelineItems.value = [...timelineItems.value, {
              id: currentMsgId, kind: 'message', role: 'assistant', content: '', done: false,
            }]
          }
          currentText += data.content
          timelineItems.value = timelineItems.value.map(i =>
            i.id === currentMsgId ? { ...i, content: currentText } : i)
        } else if (data.type === 'tool') {
          timelineItems.value = [...timelineItems.value, {
            id: data.id || `${Date.now()}-tool`, kind: 'tool_call', role: 'tool',
            name: data.name, status: 'done', result: data.result, input: data.input || '', _expanded: false,
          }]
          // task（子代理）结束后另起一条消息
          if (data.name === 'task') {
            currentMsgId = null
            currentText = ''
          }
        } else if (data.type === 'done') {
          if (currentMsgId) {
            timelineItems.value = timelineItems.value.map(i =>
              i.id === currentMsgId ? { ...i, done: true } : i)
          }
          timelineItems.value = [...timelineItems.value, {
            id: `${Date.now()}-done`, kind: 'done',
          }]
          useFileStore().fetchTree(tid)
          abortController.abort()
        } else if (data.type === 'error') {
          timelineItems.value = [...timelineItems.value, {
            id: `${Date.now()}-err`, kind: 'error', content: data.content || '服务器内部错误',
          }]
          abortController.abort()
        }
      },

      onerror(err) {
        throw err
      },
    })
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.error('Stream error:', err)
      timelineItems.value = [...timelineItems.value, {
        id: `${Date.now()}-err`, kind: 'error', content: '连接中断，请重试',
      }]
    }
  } finally {
    isLoading.value = false
    abortController = null
  }
}

// ── 清理 ──
onBeforeUnmount(() => {
  abortController?.abort()
})
</script>

<style scoped>
/* ── layout ── */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-bg);
  justify-content: center;
  position: relative;
}
.chat-panel.has-messages { justify-content: flex-start; }

/* ── top bar ── */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--topbar-height);
  padding: 0 var(--spacing-2xl);
  background: var(--color-bg);
  border-bottom: 0.67px solid var(--color-border-light);
  flex-shrink: 0;
}
.topbar-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.topbar-mode-tag {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  background: var(--color-bg-muted);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
  flex-shrink: 0;
  margin-left: var(--spacing-md);
}

/* ── messages ── */
.chat-messages { overflow-y: auto; padding: 0; }
.has-messages .chat-messages { flex: 1; }

/* ── scroll to bottom ── */
.scroll-bottom-wrapper {
  position: sticky;
  bottom: var(--spacing-lg);
  display: flex;
  justify-content: flex-end;
  padding-right: var(--spacing-lg);
  pointer-events: none;
  margin-top: -40px;
}
.scroll-to-bottom {
  pointer-events: auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 0.67px solid var(--color-border);
  background: var(--color-bg);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}
.scroll-to-bottom:hover {
  background: var(--color-bg-hover);
  color: var(--color-text);
}
</style>
