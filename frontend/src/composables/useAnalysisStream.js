/**
 * useAnalysisStream — 直接调用后端 Protocol v2 API，SDK 仅用于消息渲染。
 *
 * 流程：
 * 1. submit() → POST /api/threads/{id}/commands (run.start)
 * 2. POST /api/threads/{id}/stream (SSE) → 解析 Protocol v2 事件
 * 3. 消息和 toolCalls 通过独立 ref 暴露给 ChatPanel
 */
import { ref, shallowRef, isRef, computed } from 'vue'

export function useAnalysisStream(threadId) {
  const tid = isRef(threadId) ? threadId : ref(threadId)

  const messages = shallowRef([])
  const toolCalls = shallowRef([])
  const isLoading = ref(false)
  const error = ref(null)
  const values = ref(null)
  let abortController = null

  async function submit({ content }) {
    if (!content || isLoading.value) return

    const currentTid = tid.value
    if (!currentTid) return

    isLoading.value = true
    error.value = null
    abortController = new AbortController()

    try {
      // Step 1: 发送 run.start 命令
      const cmdRes = await fetch(`/api/threads/${currentTid}/commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: Date.now(),
          method: 'run.start',
          params: { input: { messages: [{ role: 'user', content }] } },
        }),
        signal: abortController.signal,
      })
      if (!cmdRes.ok) throw new Error(`命令失败: ${cmdRes.status}`)

      // Step 2: 打开 SSE 流
      const streamRes = await fetch(`/api/threads/${currentTid}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channels: ['messages', 'tools', 'lifecycle'],
          content,
        }),
        signal: abortController.signal,
      })

      if (!streamRes.ok) throw new Error(`流失败: ${streamRes.status}`)

      // Step 3: 解析 SSE
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
                  currentMsg = { role: 'assistant', content: '', done: false }
                  messages.value = [...messages.value, currentMsg]
                } else if (data.event === 'content-block-delta') {
                  const text = data.delta?.text || ''
                  currentText += text
                  currentMsg.content = currentText
                  messages.value = [...messages.value] // trigger reactivity
                } else if (data.event === 'message-finish') {
                  if (currentMsg) currentMsg.done = true
                  messages.value = [...messages.value]
                }
              } else if (method === 'tools/update') {
                if (data.event === 'tool-started') {
                  const tc = {
                    id: data.tool_call_id,
                    name: data.tool_name,
                    args: data.input,
                    status: 'running',
                  }
                  toolCalls.value = [...toolCalls.value, tc]
                } else if (data.event === 'tool-finished') {
                  toolCalls.value = toolCalls.value.map(tc =>
                    tc.id === data.tool_call_id
                      ? { ...tc, status: 'done', result: data.output }
                      : tc
                  )
                }
              }
            } catch {
              // 跳过非 JSON 行（heartbeat、空行等）
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        error.value = err
        console.error('Stream error:', err)
      }
    } finally {
      isLoading.value = false
      abortController = null
    }
  }

  function stop() {
    abortController?.abort()
  }

  function disconnect() {
    abortController?.abort()
  }

  return {
    messages,
    toolCalls,
    isLoading,
    error,
    values,
    submit,
    stop,
    disconnect,
    threadId: tid,
    respond: () => {},
    interrupt: ref(null),
    interrupts: ref([]),
    subagents: ref([]),
    getThread: ref(() => {}),
    isThreadLoading: ref(false),
  }
}
