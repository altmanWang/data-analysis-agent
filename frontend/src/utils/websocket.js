export function createWS(sessionId, chatStore, fileStore) {
  let ws = null
  let reconnectTimer = null
  let reconnectDelay = 1000
  let intentionalClose = false // 主动关闭时不重连
  const MAX_DELAY = 30000

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)

    ws.onopen = () => {
      console.log('WS connected:', sessionId)
      reconnectDelay = 1000
      intentionalClose = false
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
        case 'chat.tool_call':
          // 从 tool 输入中提取 todos
          try {
            const input = typeof payload.input === 'string' ? JSON.parse(payload.input) : payload.input
            if (input && input.todos) chatStore.updateTodos(input.todos)
          } catch {}
          chatStore.addToolStatus({ status: 'running', tool: payload.tool || '', detail: payload.input || '' })
          break
        case 'chat.tool_result':
          chatStore.addToolStatus({ status: 'done', tool: payload.tool || '', detail: (payload.output || '').slice(0, 200) })
          break
        case 'file.tree':
          if (payload.tree) fileStore.tree = payload.tree
          break
        case 'session.status':
          console.log('Session status:', payload.status)
          break
        case 'error':
          // 致命错误（会话不存在）不重连
          if (payload.message && payload.message.includes('会话不存在')) {
            intentionalClose = true
          }
          chatStore.addMessage({ role: 'system', content: `错误: ${payload.message}` })
          break
      }
    }

    ws.onerror = () => {
      chatStore.setWsStatus('error')
    }

    ws.onclose = () => {
      if (intentionalClose) {
        console.log('WS closed (intentional), not reconnecting')
        chatStore.setWsStatus('error')
        return
      }
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
    // CONNECTING 或 CLOSED：等待连接建立后发送
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      chatStore.setWsStatus('reconnecting')
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        reconnectDelay = 500
        connect()
      }
      // 等待连接就绪（轮询 readyState，最多等 5 秒）
      const maxWait = 5000
      const start = Date.now()
      const trySend = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(data)
        } else if (Date.now() - start < maxWait) {
          setTimeout(trySend, 100)
        } else {
          chatStore.addMessage({ role: 'system', content: '连接超时，请重试' })
          chatStore.isStreaming = false
        }
      }
      setTimeout(trySend, 100)
      return false
    }
    return false
  }

  function close() {
    intentionalClose = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  }

  connect()

  return { send, close, get readyState() { return ws ? ws.readyState : WebSocket.CLOSED } }
}
