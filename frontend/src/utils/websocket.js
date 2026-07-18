export function createWS(sessionId, chatStore, fileStore) {
  let ws = null
  let reconnectTimer = null
  let reconnectDelay = 1000
  const MAX_DELAY = 30000

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return // 已连接或正在连接，不重复创建
    }

    ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)

    ws.onopen = () => {
      console.log('WS connected:', sessionId)
      reconnectDelay = 1000 // 重置延迟
      chatStore.setWsStatus('connected')
    }

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
        case 'chat.response': {
          const backendRole = payload.role || 'assistant'
          const frontendRole = backendRole === 'human' ? 'user'
            : backendRole === 'ai' ? 'assistant'
            : backendRole

          if (payload.done) {
            if (frontendRole === 'user') {
              chatStore.addMessage({ role: 'user', content: payload.content })
            } else {
              chatStore.appendToLast(payload.content, source)
              chatStore.finishLastMessage()
            }
          } else if (payload.content) {
            chatStore.appendToLast(payload.content, source)
          }
          break
        }
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

    ws.onerror = () => {
      chatStore.setWsStatus('error')
    }

    ws.onclose = () => {
      console.log('WS disconnected, reconnecting in', reconnectDelay, 'ms')
      chatStore.setWsStatus('reconnecting')
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY)
        connect()
      }, reconnectDelay)
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
      return true
    }
    // 未连接时触发重连，并提示用户
    if (!ws || ws.readyState === WebSocket.CLOSED) {
      chatStore.setWsStatus('reconnecting')
      reconnectDelay = 500 // 用户主动操作时快速重连
      connect()
      // 延迟发送：等待连接建立
      setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(data)
        } else {
          chatStore.addMessage({ role: 'system', content: '连接失败，请刷新页面重试' })
          chatStore.isStreaming = false
        }
      }, 1500)
      return false
    }
    return false
  }

  function close() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  }

  connect()

  return { send, close, get readyState() { return ws ? ws.readyState : WebSocket.CLOSED } }
}
