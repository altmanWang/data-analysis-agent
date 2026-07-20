# backend/api/threads.py
"""REST API: Agent 状态查询（检查点、消息历史）"""

import logging
from fastapi import APIRouter, HTTPException
from mysql_saver import MySQLSaver
from db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["threads"])


def _get_saver() -> MySQLSaver:
    """创建 MySQLSaver 实例（每次调用新建，内部 _get_conn 按需取连接）"""
    return MySQLSaver()


@router.get("/{thread_id}/state")
async def get_thread_state(thread_id: str):
    """读取线程最新检查点状态"""
    saver = _get_saver()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        checkpoint_tuple = await saver.aget_tuple(config)
    except Exception as e:
        logger.error("读取状态失败 thread_id=%s: %s", thread_id, e)
        raise HTTPException(status_code=500, detail="读取状态失败")

    if not checkpoint_tuple:
        raise HTTPException(status_code=404, detail="无检查点数据")

    values = dict(checkpoint_tuple.checkpoint.get("channel_values", {}))
    return {"values": values}


@router.get("/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """读取线程消息历史（从 message_history 表）"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, thinking_content, tool_name, tool_args, tool_result, tool_status "
                "FROM message_history WHERE session_id = %s ORDER BY id ASC",
                (thread_id,),
            )
            rows = cur.fetchall()
        return [
            {k: v for k, v in zip(
                ["role", "content", "thinking_content", "tool_name", "tool_args", "tool_result", "tool_status"], row
            )}
            for row in rows
        ]
    finally:
        conn.close()


@router.get("/{thread_id}/history")
async def get_thread_history(thread_id: str, limit: int = 50):
    """获取检查点历史列表"""
    saver = _get_saver()
    try:
        checkpoints = list(
            saver.list(
                config={"configurable": {"thread_id": thread_id}},
                limit=limit,
            )
        )
    except Exception as e:
        logger.error("读取历史失败 thread_id=%s: %s", thread_id, e)
        raise HTTPException(status_code=500, detail="读取历史失败")

    return [
        {
            "checkpoint_id": cp.checkpoint["id"],
            "parent_checkpoint_id": (
                cp.parent_config["configurable"]["checkpoint_id"]
                if cp.parent_config else None
            ),
            "step": cp.metadata.get("step"),
            "source": cp.metadata.get("source"),
            "metadata": cp.metadata,
        }
        for cp in checkpoints
    ]
