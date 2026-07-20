/**
 * useAnalysisStream — 基于 fetchEventSource 的 SSE 流式通信。
 *
 * 网络层负责 HTTP 请求与事件解析，消息状态委托给 chatStore（Pinia）。
 * 替代了旧版手动 ReadableStream + TextDecoder + buffer 拼接的方案。
 */
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useChatStore } from '../stores/chatStore'

export function useAnalysisStream(threadId) {
  const store = useChatStore()
  store.currentThreadId = threadId
  let abortController = null

  async function submit({ content }) {
    if (!content || store.isLoading) return
    if (!threadId) return

    store.setLoading(true)
    store.setError(null)
    abortController = new AbortController()

    try {
      // ── Phase 1: 启动 agent run ──
      const cmdRes = await fetch(`/api/threads/${threadId}/commands`, {
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

      // 立即显示用户消息
      store.appendItem({
        id: Date.now().toString(),
        role: 'user',
        kind: 'message',
        content,
        done: true,
      })

      // 用于 SSE 流中累积 assistant 消息内容
      let currentMsgId = null
      let currentText = ''

      // ── Phase 2: fetchEventSource 消费 SSE ──
      await fetchEventSource(`/api/threads/${threadId}/stream/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channels: ['messages', 'tools', 'lifecycle'],
          content,
        }),
        signal: abortController.signal,
        openWhenHidden: true, // 后台标签页不断流

        onmessage(event) {
          if (!event.data) return
          try {
            const parsed = JSON.parse(event.data)
            // Protocol v2: params.data 是实际事件体
            const data = parsed.params?.data || {}

            // ── 消息事件 ──
            if (parsed.method === 'messages/update') {
              if (data.event === 'message-start') {
                currentMsgId = `${Date.now()}-ai`
                currentText = ''
                store.appendItem({
                  id: currentMsgId,
                  role: 'assistant',
                  kind: 'message',
                  content: '',
                  done: false,
                })
              } else if (data.event === 'content-block-delta') {
                currentText += data.delta?.text || ''
                if (currentMsgId) {
                  store.updateItem(currentMsgId, { content: currentText })
                }
              } else if (data.event === 'message-finish') {
                if (currentMsgId) {
                  store.updateItem(currentMsgId, { done: true })
                }
                currentMsgId = null
                currentText = ''
              }
            }

            // ── 工具事件 ──
            else if (parsed.method === 'tools/update') {
              if (data.event === 'tool-started') {
                store.appendItem({
                  id: data.tool_call_id,
                  kind: 'tool_call',
                  role: 'tool',
                  name: data.tool_name,
                  args: data.input,
                  status: 'running',
                  result: null,
                  _expanded: true,
                })
              } else if (data.event === 'tool-finished') {
                store.updateItem(data.tool_call_id, {
                  status: 'done',
                  result: data.output,
                  _expanded: false,
                })
              }
            }
          } catch {
            // 非关键事件静默跳过（heartbeat、格式异常等）
          }
        },

        onerror(err) {
          store.setError(err instanceof Error ? err : new Error(String(err)))
          throw err // 不重试，直接终止流
        },
      })
    } catch (err) {
      if (err.name !== 'AbortError') {
        store.setError(err instanceof Error ? err : new Error(String(err)))
        console.error('Stream error:', err)
      }
    } finally {
      store.setLoading(false)
      abortController = null
    }
  }

  function stop() {
    abortController?.abort()
  }

  function disconnect() {
    abortController?.abort()
  }

  async function loadHistory() {
    await store.loadHistory(threadId)
  }

  return { submit, stop, disconnect, loadHistory }
}
