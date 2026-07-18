# backend/ws_handler.py
"""WebSocket 处理器，基于 LangGraph astream_events v3"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent_pool import agent_pool
from session_manager import session_manager
from worktree_manager import worktree_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    # 验证会话
    session = session_manager.get(session_id)
    if not session:
        await ws.send_json({"type": "error", "payload": {"message": "会话不存在"}})
        await ws.close()
        return

    # 确保 worktree 在本地
    if session["status"] == "archived":
        await ws.send_json({"type": "session.status", "payload": {"status": "restoring"}})
        try:
            worktree_manager.restore_session(session_id)
            session_manager.update_status(session_id, "active")
        except Exception as e:
            await ws.send_json({"type": "error", "payload": {"message": f"恢复失败: {str(e)}"}})
            await ws.close()
            return

    session_manager.update_last_active(session_id)

    # 获取 agent
    try:
        agent = agent_pool.get_agent(session_id)
    except Exception as e:
        await ws.send_json({"type": "error", "payload": {"message": f"Agent 初始化失败: {str(e)}"}})
        await ws.close()
        return

    # 发送历史消息
    try:
        state = agent.get_state({"configurable": {"thread_id": session_id}})
        if state and state.values and state.values.get("messages"):
            for msg in state.values["messages"]:
                role = getattr(msg, "type", "assistant")
                content = getattr(msg, "content", "")
                if content:
                    await ws.send_json({
                        "type": "chat.response",
                        "payload": {"role": role, "content": content, "done": True},
                    })
    except Exception:
        pass  # 首次对话无历史

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "chat.send":
                content = msg["payload"]["content"]

                async for event in agent.astream_events(
                    {"messages": [{"role": "user", "content": content}]},
                    config={"configurable": {"thread_id": session_id}},
                    version="v2",
                ):
                    method = event.get("method")
                    params = event.get("params", {})
                    namespace = params.get("namespace", [])
                    source = "subagent" if namespace else "coordinator"

                    await ws.send_json({
                        "type": method,
                        "payload": params,
                        "source": source,
                    })

                # 对话完成，推送更新后的文件树
                tree = worktree_manager.get_file_tree(session_id)
                await ws.send_json({"type": "file.tree", "payload": {"tree": tree}})

            elif msg.get("type") == "chat.cancel":
                await ws.send_json({
                    "type": "chat.response",
                    "payload": {"content": "[执行已中断]", "done": True},
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: {session_id}")
    except Exception as e:
        import traceback
        logger.error(f"WebSocket 错误: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await ws.send_json({"type": "error", "payload": {"message": str(e)}})
