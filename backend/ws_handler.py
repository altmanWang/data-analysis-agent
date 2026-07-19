# backend/ws_handler.py
"""WebSocket 处理器，基于 LangGraph astream_events v3"""

import asyncio
import json
import logging
import os
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent_pool import agent_pool
from session_manager import session_manager
from worktree_manager import worktree_manager
from config import WORKTREE_ROOT

logger = logging.getLogger(__name__)
router = APIRouter()

# 可重试的网络层异常（LLM API 连接中断等）
RETRYABLE_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
)
MAX_RETRIES = 2


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

    # 发送历史消息（从 .history.json 或 LangGraph state 读取）
    try:
        history_file = os.path.join(WORKTREE_ROOT, session_id, ".history.json")
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            for msg in history:
                await ws.send_json({
                    "type": "chat.response",
                    "payload": {"role": msg["role"], "content": msg["content"], "done": True},
                })
    except Exception:
        pass  # 首次对话无历史

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            assistant_full = ""
            turn_history = []

            if msg.get("type") == "chat.send":
                content = msg["payload"]["content"]

                # 初始化本轮对话的历史记录
                turn_history = [{"role": "user", "content": content}]
                assistant_full = ""

                # 带重试的 agent 流式调用（利用 LangGraph checkpoint 安全恢复）
                stream_config = {
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 50,
                }
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        async for event in agent.astream_events(
                            {"messages": [{"role": "user", "content": content}]},
                            config=stream_config,
                            version="v2",
                        ):
                            evt = event.get("event", "")
                            data = event.get("data", {})
                            name = event.get("name", "")

                            # 映射 LangGraph v2 事件到前端消息
                            if evt == "on_chat_model_stream" and data.get("chunk"):
                                chunk = data["chunk"]
                                if hasattr(chunk, "content") and chunk.content:
                                    assistant_full += chunk.content
                                    await ws.send_json({
                                        "type": "chat.response",
                                        "payload": {"content": chunk.content, "done": False},
                                    })
                            elif evt == "on_tool_start":
                                await ws.send_json({
                                    "type": "chat.tool_call",
                                    "payload": {"tool": name, "input": str(data.get("input", {}))[:200]},
                                })
                            elif evt == "on_tool_end":
                                await ws.send_json({
                                    "type": "chat.tool_result",
                                    "payload": {"tool": name, "output": str(data.get("output", ""))[:500]},
                                })
                                # 工具完成后推送文件树（图表/报告可能已生成）
                                tree = worktree_manager.get_file_tree(session_id)
                                await ws.send_json({"type": "file.tree", "payload": {"tree": tree}})
                        break  # 流完成，退出重试循环

                    except RETRYABLE_ERRORS as e:
                        if attempt < MAX_RETRIES:
                            wait = 2 ** attempt
                            logger.warning(
                                f"LLM 连接中断 (attempt {attempt + 1}/{MAX_RETRIES + 1}): {type(e).__name__}: {e}"
                            )
                            # 通知前端正在重试，并重置已累积内容（checkpoint 恢复会重新生成）
                            retry_msg = f"\n\n[连接中断，正在重试 ({attempt + 1}/{MAX_RETRIES})...]\n"
                            await ws.send_json({
                                "type": "chat.response",
                                "payload": {"content": retry_msg, "done": False},
                            })
                            assistant_full = ""
                            await asyncio.sleep(wait)
                        else:
                            raise  # 重试耗尽，向上抛出

                # 保存本轮对话到历史文件
                if assistant_full.strip():
                    turn_history.append({"role": "assistant", "content": assistant_full})
                    history_file = os.path.join(WORKTREE_ROOT, session_id, ".history.json")
                    existing = []
                    if os.path.exists(history_file):
                        with open(history_file, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    existing.extend(turn_history)
                    with open(history_file, "w", encoding="utf-8") as f:
                        json.dump(existing, f, ensure_ascii=False)

                # 对话完成，推送更新后的文件树
                tree = worktree_manager.get_file_tree(session_id)
                await ws.send_json({"type": "file.tree", "payload": {"tree": tree}})

            elif msg.get("type") == "chat.cancel":
                if assistant_full.strip():
                    turn_history.append({"role": "assistant", "content": assistant_full + "\n[执行已中断]"})
                else:
                    turn_history.append({"role": "assistant", "content": "[执行已中断]"})
                history_file = os.path.join(WORKTREE_ROOT, session_id, ".history.json")
                existing = []
                if os.path.exists(history_file):
                    with open(history_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing.extend(turn_history)
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False)
                await ws.send_json({
                    "type": "chat.response",
                    "payload": {"content": "[执行已中断]", "done": True},
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: {session_id}")
    except RETRYABLE_ERRORS as e:
        logger.error(f"LLM API 连接失败（重试已耗尽）: {e}")
        await ws.send_json({
            "type": "error",
            "payload": {"message": "AI 服务连接失败，请稍后重试"},
        })
    except Exception as e:
        import traceback
        logger.error(f"WebSocket 错误: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await ws.send_json({
            "type": "error",
            "payload": {"message": "处理请求时发生错误，请重试"},
        })
