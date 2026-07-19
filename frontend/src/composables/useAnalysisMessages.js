/**
 * useAnalysisMessages — 直接使用 stream.items 作为统一时间线。
 */
import { computed } from 'vue'

export function useAnalysisMessages(stream) {
  const timeline = computed(() => stream.items?.value || [])
  const rawMessages = computed(() => stream.messages?.value || [])
  const rawToolCalls = computed(() => stream.toolCalls?.value || [])
  return { timeline, rawMessages, rawToolCalls }
}
