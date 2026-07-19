# backend/api/threads.py
"""REST API: Protocol v2 Thread 管理"""

import logging
from fastapi import APIRouter, HTTPException
from session_manager import session_manager
from mysql_saver import MySQLSaver
from agent_pool import agent_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads", tags=["threads"])


def _get_saver() -> MySQLSaver:
    """创建 MySQLSaver 实例（每次调用新建，内部 _get_conn 按需取连接）"""
    return MySQLSaver()


@router.post("")
async def create_thread(title: str = "新会话"):
    """创建线程（等价于创建 session）"""
    session = session_manager.create(user_id="", title=title)
    return {
        "thread_id": session["session_id"],
        "title": session["title"],
        "created_at": session["created_at"],
    }


@router.get("")
async def list_threads():
    """获取线程列表"""
    return session_manager.list_by_user(user_id="")


@router.get("/{thread_id}")
async def get_thread(thread_id: str):
    """获取线程元数据"""
    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="线程不存在")
    return session


@router.get("/{thread_id}/state")
async def get_thread_state(thread_id: str):
    """读取线程最新检查点状态（channel_values）"""
    saver = _get_saver()
    try:
        checkpoint_tuple = await saver.aget_tuple(
            {"configurable": {"thread_id": thread_id}}
        )
    except Exception as e:
        logger.error("读取状态失败 thread_id=%s: %s", thread_id, e)
        raise HTTPException(status_code=500, detail="读取状态失败")

    if not checkpoint_tuple:
        raise HTTPException(status_code=404, detail="无检查点数据")

    values = checkpoint_tuple.checkpoint.get("channel_values", {})
    return {"values": values}


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


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """删除线程（软删除 + 清理 agent 缓存）"""
    session = session_manager.get(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="线程不存在")

    agent_pool.remove(thread_id)
    session_manager.soft_delete(thread_id)
    return {"message": "已删除"}
