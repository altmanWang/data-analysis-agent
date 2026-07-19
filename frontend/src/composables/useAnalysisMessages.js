/**
 * useAnalysisMessages — 将 stream 的 messages + toolCalls 合并为统一时间线。
 */
import { computed } from 'vue'

export function useAnalysisMessages(stream) {
  const messages = computed(() => stream.messages.value || [])
  const toolCalls = computed(() => stream.toolCalls.value || [])

  const timeline = computed(() => {
    const items = []
    for (const msg of messages.value) {
      items.push({ id: msg.id || crypto.randomUUID(), role: msg.role, kind: 'message', content: msg.content, raw: msg })
    }
    for (const tc of toolCalls.value) {
      items.push({ id: tc.id, role: 'tool', kind: 'tool_call', name: tc.name, args: tc.args, status: tc.status, result: tc.result, raw: tc })
    }
    return items
  })

  return { timeline, rawMessages: messages, rawToolCalls: toolCalls }
}
