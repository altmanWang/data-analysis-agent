# backend/api/files.py
"""REST API: 文件管理（上传、目录树、预览、删除）"""

import os
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from services.session_manager import session_manager
from services.worktree_manager import worktree_manager
from config import WORKTREE_ROOT

router = APIRouter(prefix="/api/sessions/{session_id}/files", tags=["files"])


@router.get("")
async def get_file_tree(session_id: str):
    """获取会话工作空间的文件目录树"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"tree": worktree_manager.get_file_tree(session_id)}


@router.post("")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """上传文件到沙盒根目录"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="会话非 active 状态")

    upload_dir = os.path.join(WORKTREE_ROOT, session_id)
    os.makedirs(upload_dir, exist_ok=True)

    # 安全：仅取文件名，防止路径穿越（如 ../../etc/passwd）
    safe_name = os.path.basename(file.filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名")
    file_path = os.path.join(upload_dir, safe_name)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {
        "message": "上传成功",
        "path": f"/{file.filename}",
        "size": len(content),
    }


@router.delete("/{file_path:path}")
async def delete_file(session_id: str, file_path: str):
    """删除沙盒中的文件或目录"""
    safe_path = file_path.lstrip("/")
    if ".." in safe_path:
        raise HTTPException(status_code=400, detail="非法文件路径")

    full_path = os.path.normpath(
        os.path.join(WORKTREE_ROOT, session_id, safe_path)
    )
    real_root = os.path.normpath(os.path.join(WORKTREE_ROOT, session_id))
    if not full_path.startswith(real_root):
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if os.path.isdir(full_path):
        import shutil
        shutil.rmtree(full_path)
    else:
        os.remove(full_path)
    return {"message": "已删除"}


@router.get("/{file_path:path}")
async def preview_file(session_id: str, file_path: str):
    """预览文件内容（HTML/MD/图片/CSV）"""
    try:
        content, mime = worktree_manager.read_file_content(session_id, file_path)
        return Response(content=content, media_type=mime)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
