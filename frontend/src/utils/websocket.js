export function createWS(sessionId, chatStore, fileStore) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/ws/${sessionId}`)

  ws.onopen = () => console.log('WS connected:', sessionId)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    const { type, payload, source } = data

    switch (type) {
      case 'messages': {
        const msgs = payload.data || []
        msgs.forEach(m => {
          if (m.event === 'content-block-delta') {
            const delta = m.delta || {}
            if (delta.text) chatStore.appendToLast(delta.text, source)
          }
        })
        break
      }
      case 'chat.response':
        if (payload.done) chatStore.finishLastMessage()
        else if (payload.content) chatStore.appendToLast(payload.content, source)
        break
      case 'tool_calls':
        if (payload && payload.input) {
          try {
            const input = typeof payload.input === 'string' ? JSON.parse(payload.input) : payload.input
            if (input.todos) chatStore.updateTodos(input.todos)
          } catch {}
        }
        break
      case 'file.tree':
        if (payload.tree) fileStore.tree = payload.tree
        break
      case 'session.status':
        console.log('Session status:', payload.status)
        break
      case 'error':
        chatStore.addMessage({ role: 'system', content: `错误: ${payload.message}` })
        break
    }
  }

  ws.onerror = () => chatStore.addMessage({ role: 'system', content: '连接失败' })
  ws.onclose = () => console.log('WS disconnected')

  return ws
}
