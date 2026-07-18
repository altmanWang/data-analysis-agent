# backend/api/sessions.py
"""REST API: 会话管理"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from ..session_manager import session_manager
from ..worktree_manager import worktree_manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
async def create_session(
    user_id: str = "",
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None),
):
    """创建新会话，返回 session_id + 元数据"""
    # TODO: 生产环境校验 authorization token + cookie
    session = session_manager.create(user_id=user_id)
    worktree_manager.create_worktree(session["session_id"])
    return session


@router.get("")
async def list_sessions(user_id: str = ""):
    """获取会话列表"""
    return session_manager.list_by_user(user_id=user_id)


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取单个会话详情 + 文件树"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    tree = worktree_manager.get_file_tree(session_id)
    session["file_tree"] = tree
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话（软删除 + 清理磁盘）"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    worktree_manager.delete_worktree(session_id)
    session_manager.soft_delete(session_id)
    return {"message": "已删除"}


@router.post("/{session_id}/archive")
async def archive_session(session_id: str):
    """手动归档会话"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="仅 active 状态可归档")

    session_manager.update_status(session_id, "archiving")
    worktree_manager.archive_session(session_id)
    session_manager.update_status(session_id, "archived")
    return {"message": "已归档"}
