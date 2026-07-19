/**
 * useAnalysisStream — 直接调用后端 Protocol v2 API，按 SSE 事件顺序维护单条时间线。
 */
import { ref, shallowRef, isRef } from 'vue'

export function useAnalysisStream(threadId) {
  const tid = isRef(threadId) ? threadId : ref(threadId)

  const items = shallowRef([])  // 统一时间线: 消息 + 工具调用
  const messages = shallowRef([])  // 纯消息 (兼容 useAnalysisMessages)
  const toolCalls = shallowRef([])  // 纯工具 (兼容 useAnalysisMessages)
  const isLoading = ref(false)
  const error = ref(null)
  let abortController = null

  function _push(item) {
    items.value = [...items.value, item]
    if (item.kind === 'tool_call') {
      toolCalls.value = [...toolCalls.value, { id: item.id, name: item.name, args: item.args, status: item.status, result: item.result }]
    } else {
      messages.value = [...messages.value, { id: item.id, role: item.role, content: item.content, done: item.done }]
    }
  }

  function _updateTool(id, updates) {
    items.value = items.value.map(i => i.id === id ? { ...i, ...updates } : i)
    toolCalls.value = toolCalls.value.map(tc => tc.id === id ? { ...tc, ...updates } : tc)
  }

  async function submit({ content }) {
    if (!content || isLoading.value) return
    const currentTid = tid.value
    if (!currentTid) return

    isLoading.value = true
    error.value = null
    abortController = new AbortController()

    try {
      const cmdRes = await fetch(`/api/threads/${currentTid}/commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: Date.now(), method: 'run.start', params: { input: { messages: [{ role: 'user', content }] } } }),
        signal: abortController.signal,
      })
      if (!cmdRes.ok) throw new Error(`命令失败: ${cmdRes.status}`)

      _push({ id: Date.now().toString(), role: 'user', kind: 'message', content, done: true })

      const streamRes = await fetch(`/api/threads/${currentTid}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channels: ['messages', 'tools', 'lifecycle'], content }),
        signal: abortController.signal,
      })
      if (!streamRes.ok) throw new Error(`流失败: ${streamRes.status}`)

      const reader = streamRes.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentText = ''
      let currentMsg = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              const method = event.method
              const data = event.params?.data || {}

              if (method === 'messages/update') {
                if (data.event === 'message-start') {
                  currentText = ''
                  currentMsg = { id: Date.now().toString() + '-ai', role: 'assistant', kind: 'message', content: '', done: false }
                  _push(currentMsg)
                } else if (data.event === 'content-block-delta') {
                  const text = data.delta?.text || ''
                  currentText += text
                  currentMsg.content = currentText
                  items.value = [...items.value] // 触发响应式
                } else if (data.event === 'message-finish') {
                  if (currentMsg) currentMsg.done = true
                  items.value = [...items.value]
                }
              } else if (method === 'tools/update') {
                if (data.event === 'tool-started') {
                  _push({ id: data.tool_call_id, role: 'tool', kind: 'tool_call', name: data.tool_name, args: data.input, status: 'running', result: null, _expanded: true })
                } else if (data.event === 'tool-finished') {
                  _updateTool(data.tool_call_id, { status: 'done', result: data.output, _expanded: false })
                }
              }
            } catch { /* skip non-JSON */ }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') { error.value = err; console.error('Stream error:', err) }
    } finally {
      isLoading.value = false
      abortController = null
    }
  }

  async function loadHistory() {
    const currentTid = tid.value
    if (!currentTid) return
    try {
      const res = await fetch(`/api/threads/${currentTid}/messages`)
      if (!res.ok) return
      const rows = await res.json()
      if (!rows?.length) return
      const history = []
      for (const r of rows) {
        if (r.role === 'tool') {
          history.push({ id: `${currentTid}-tool-${Math.random()}`, role: 'tool', kind: 'tool_call', name: r.tool_name || '', args: r.tool_args || null, status: r.tool_status || 'done', result: r.tool_result || null, _expanded: false })
        } else {
          history.push({ id: `${currentTid}-${r.role}-${Math.random()}`, role: r.role === 'assistant' ? 'assistant' : 'user', kind: 'message', content: r.content || '', done: true })
        }
      }
      items.value = history
      messages.value = history.filter(i => i.kind === 'message').map(i => ({ id: i.id, role: i.role, content: i.content, done: i.done }))
      toolCalls.value = history.filter(i => i.kind === 'tool_call').map(i => ({ id: i.id, name: i.name, args: i.args, status: i.status, result: i.result }))
    } catch (e) { console.error('加载历史失败:', e) }
  }

  function stop() { abortController?.abort() }
  function disconnect() { abortController?.abort() }

  return { messages, toolCalls, items, isLoading, error, submit, stop, disconnect, loadHistory, threadId: tid, respond: () => {}, interrupt: ref(null), interrupts: ref([]), subagents: ref([]), getThread: ref(() => {}), isThreadLoading: ref(false) }
}
