# backend/services/worktree_manager.py
"""Worktree 生命周期管理：创建、归档、恢复、文件树"""

import os
import shutil
import logging
from config import WORKTREE_ROOT, SKILLS_DIR

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
            logger.warning("跳过无权限目录: %s", path, exc_info=True)
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
        from services.session_manager import session_manager as sm
        sm.update_obs_key(session_id, f"sessions/{session_id}/worktree.zip")

        # 清理本地
        shutil.rmtree(worktree)
        os.remove(zip_path)

# 全局单例
worktree_manager = WorktreeManager()


def sync_agent_skills_to_worktree(session_id: str, agent_ids: list[int]):
    """从 DB 读取 Agent 绑定的 Skills 的 zip，解压到 sandboxes/{sid}/.skills/"""
    from services.skill_service import skill_service
    import zipfile

    dest_root = os.path.join(WORKTREE_ROOT, session_id, ".skills")
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    os.makedirs(dest_root, exist_ok=True)

    seen = set()
    for aid in agent_ids:
        for skill in skill_service.get_agent_skills(aid):
            if skill["name"] in seen:
                continue
            seen.add(skill["name"])
            zip_bytes = skill_service.get_zip_data(skill["name"])
            if zip_bytes:
                from io import BytesIO
                dst = os.path.join(dest_root, skill["name"])
                os.makedirs(dst, exist_ok=True)
                with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                    # 找到 skill root 并解压到 dst
                    names = [n for n in zf.namelist() if not n.startswith("/") and ".." not in n]
                    # 检测是否有顶层目录
                    top_dirs = set()
                    for n in names:
                        parts = n.split("/")
                        if parts[0]:
                            top_dirs.add(parts[0])
                    if len(top_dirs) == 1:
                        # 有单一顶层目录 → 去掉前缀
                        prefix = list(top_dirs)[0]
                        for n in names:
                            if n.endswith("/"):
                                continue  # 跳过目录条目
                            if n.startswith(prefix + "/"):
                                rel = n[len(prefix) + 1:]
                                if rel:
                                    target = os.path.join(dst, rel)
                                    os.makedirs(os.path.dirname(target), exist_ok=True)
                                    with zf.open(n) as src, open(target, "wb") as out:
                                        out.write(src.read())
                    else:
                        # 无单一顶层目录 → 直接解压
                        for n in names:
                            if n.endswith("/"):
                                continue
                            target = os.path.join(dst, n)
                            os.makedirs(os.path.dirname(target), exist_ok=True)
                            with zf.open(n) as src, open(target, "wb") as out:
                                out.write(src.read())
            logger.info("已同步 Skill 到 session: skill=%s session=%s", skill["name"], session_id)


def clear_session_skills(session_id: str):
    """清空 session 的 .skills/ 目录"""
    dest = os.path.join(WORKTREE_ROOT, session_id, ".skills")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
