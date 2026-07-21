# backend/worktree_manager.py
"""Worktree 生命周期管理：创建、归档、恢复、文件树"""

import os
import shutil
import logging
from config import WORKTREE_ROOT

logger = logging.getLogger(__name__)


class WorktreeManager:
    """会话沙盒工作空间管理"""

    # ────────── 目录管理 ──────────

    def create_worktree(self, session_id: str) -> str:
        """创建沙盒目录结构，返回 worktree 路径"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        os.makedirs(worktree, exist_ok=True)
        return worktree

    def delete_worktree(self, session_id: str) -> None:
        """删除沙盒目录"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if os.path.exists(worktree):
            shutil.rmtree(worktree)

    # ────────── 文件树 ──────────

    def get_file_tree(self, session_id: str) -> list[dict]:
        """递归扫描目录，返回前端文件树结构"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if not os.path.exists(worktree):
            return []
        return self._scan_dir(worktree)

    def _scan_dir(self, path: str) -> list[dict]:
        items = []
        try:
            for entry in os.scandir(path):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    items.append({
                        "name": entry.name,
                        "type": "dir",
                        "children": self._scan_dir(entry.path),
                    })
                else:
                    _, ext = os.path.splitext(entry.name)
                    items.append({
                        "name": entry.name,
                        "type": "file",
                        "size": entry.stat().st_size,
                        "ext": ext.lower(),
                    })
        except PermissionError:
            pass
        return sorted(items, key=lambda x: (x["type"] != "dir", x["name"]))

    def read_file_content(self, session_id: str, file_path: str) -> tuple[bytes, str]:
        """读取文件内容和 MIME 类型，用于前端预览"""
        safe_path = file_path.lstrip("/")
        if ".." in safe_path:
            raise ValueError("非法文件路径")

        full_path = os.path.join(WORKTREE_ROOT, session_id, safe_path)
        full_path = os.path.normpath(full_path)

        # 安全检查：确保不越出 sandboxes 目录
        real_root = os.path.normpath(os.path.join(WORKTREE_ROOT, session_id))
        if not full_path.startswith(real_root):
            raise ValueError("非法文件路径")

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = os.path.splitext(full_path)[1].lower()
        mime_map = {
            ".html": "text/html",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
        }
        mime = mime_map.get(ext, "application/octet-stream")

        with open(full_path, "rb") as f:
            content = f.read()
        return content, mime

    # ────────── 归档与恢复（OBS 打桩）──────────

    def archive_session(self, session_id: str) -> None:
        """打包 worktree 并上传 OBS（当前打桩：仅打包本地）"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if not os.path.exists(worktree):
            logger.warning(f"worktree 不存在，跳过归档: {session_id}")
            return

        zip_base = os.path.join(WORKTREE_ROOT, f"{session_id}")
        shutil.make_archive(zip_base, "zip", worktree)
        zip_path = f"{zip_base}.zip"

        # TODO: OBS 上传（打桩）
        logger.info(f"[OBS打桩] 模拟上传: sessions/{session_id}/worktree.zip")

        # 记录 OBS key
        from session_manager import session_manager as sm
        sm.update_obs_key(session_id, f"sessions/{session_id}/worktree.zip")

        # 清理本地
        shutil.rmtree(worktree)
        os.remove(zip_path)

# 全局单例
worktree_manager = WorktreeManager()
