# backend/services/skill_service.py
"""Skill 技能包管理 — zip 上传/解压验证/CRUD/Agent 绑定"""

import os
import shutil
import zipfile
import tempfile
import logging
from io import BytesIO
from db import get_connection
from config import SKILLS_DIR

logger = logging.getLogger(__name__)


class SkillService:
    """技能包生命周期管理"""

    # ────────── 上传 & 安装 ──────────

    def upload_and_install(self, zip_bytes: bytes, user_id: str = "") -> dict:
        """解压 zip，验证 SKILL.md，安装到磁盘 + 存储 zip 到 DB"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                for member in zf.namelist():
                    if member.startswith("/") or ".." in member:
                        raise ValueError(f"非法路径: {member}")
                zf.extractall(tmpdir)

            # 递归查找 SKILL.md（支持有无父目录两种打包方式）
            skill_md_path = None
            for root, dirs, files in os.walk(tmpdir):
                if "SKILL.md" in files:
                    skill_md_path = os.path.join(root, "SKILL.md")
                    break

            if not skill_md_path:
                raise ValueError("技能包必须包含 SKILL.md 文件")

            # skill_root = 包含 SKILL.md 的目录
            skill_root = os.path.dirname(skill_md_path)
            name = self._parse_skill_name(skill_md_path) or os.path.basename(skill_root)
            if not name:
                raise ValueError("无法确定技能名称")
            name = name.lower().replace(" ", "-").strip("-")

            dest_dir = os.path.join(SKILLS_DIR, name)
            if os.path.exists(dest_dir):
                raise ValueError(f"技能 '{name}' 已存在")

            shutil.copytree(skill_root, dest_dir)
            logger.info("技能已安装到磁盘: %s", name)

            frontmatter_desc = self._read_frontmatter_description(skill_md_path)

            # 写入 DB
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO skills (name, display_name, description, zip_data, user_id) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (name, name, frontmatter_desc or name, zip_bytes, user_id),
                    )
                    conn.commit()
                    skill_id = cur.lastrowid
                    return self.get_by_id(skill_id)
            finally:
                conn.close()

    def get_by_id(self, skill_id: int) -> dict | None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, display_name, description, user_id, created_at "
                    "FROM skills WHERE id=%s", (skill_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {"id": row[0], "name": row[1], "display_name": row[2],
                        "description": row[3], "user_id": row[4], "created_at": str(row[5])}
        finally:
            conn.close()

    def get_zip_data(self, skill_name: str) -> bytes | None:
        """从 DB 读取原始 zip"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT zip_data FROM skills WHERE name=%s", (skill_name,))
                row = cur.fetchone()
                return row[0] if row and row[0] else None
        finally:
            conn.close()

    def _parse_skill_name(self, skill_md_path: str) -> str | None:
        """从 SKILL.md 的 YAML frontmatter 中提取 name"""
        try:
            with open(skill_md_path, encoding="utf-8") as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    fm = yaml.safe_load(parts[1]) or {}
                    return fm.get("name", "")
        except Exception:
            pass
        return None

    def _read_frontmatter_description(self, skill_md_path: str) -> str:
        """读取 SKILL.md 的 description 字段"""
        try:
            with open(skill_md_path, encoding="utf-8") as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    fm = yaml.safe_load(parts[1]) or {}
                    return fm.get("description", "")
        except Exception:
            pass
        return ""

    # ────────── DB CRUD ──────────

    def list_all(self, user_id: str = "") -> list[dict]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "SELECT id, name, display_name, description, user_id, created_at "
                        "FROM skills WHERE user_id=%s ORDER BY created_at DESC",
                        (user_id,),
                    )
                else:
                    cur.execute(
                        "SELECT id, name, display_name, description, user_id, created_at "
                        "FROM skills ORDER BY created_at DESC"
                    )
                rows = cur.fetchall()
                return [
                    {"id": r[0], "name": r[1], "display_name": r[2],
                     "description": r[3], "user_id": r[4], "created_at": str(r[5])}
                    for r in rows
                ]
        finally:
            conn.close()

    def delete(self, skill_id: int) -> bool:
        """删除技能包：清理文件 + DB 记录 + 关联"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM skills WHERE id=%s", (skill_id,))
                row = cur.fetchone()
                if not row:
                    return False
                name = row[0]
                # 删除磁盘文件
                skill_dir = os.path.join(SKILLS_DIR, name)
                if os.path.isdir(skill_dir):
                    shutil.rmtree(skill_dir)
                # 清理 DB
                cur.execute("DELETE FROM agent_skills WHERE skill_id=%s", (skill_id,))
                cur.execute("DELETE FROM skills WHERE id=%s", (skill_id,))
                conn.commit()
                logger.info("技能已删除: %s", name)
                return True
        finally:
            conn.close()

    # ────────── Agent-Skill 绑定 ──────────

    def get_agent_skills(self, agent_id: int) -> list[dict]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT s.id, s.name, s.display_name, s.description "
                    "FROM skills s INNER JOIN agent_skills ags ON s.id = ags.skill_id "
                    "WHERE ags.agent_id=%s ORDER BY s.name",
                    (agent_id,),
                )
                rows = cur.fetchall()
                return [
                    {"id": r[0], "name": r[1], "display_name": r[2], "description": r[3]}
                    for r in rows
                ]
        finally:
            conn.close()

    def attach_skill_to_agent(self, agent_id: int, skill_id: int) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO agent_skills (agent_id, skill_id) VALUES (%s, %s)",
                    (agent_id, skill_id),
                )
                conn.commit()
        finally:
            conn.close()

    def detach_skill_from_agent(self, agent_id: int, skill_id: int) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agent_skills WHERE agent_id=%s AND skill_id=%s",
                    (agent_id, skill_id),
                )
                conn.commit()
        finally:
            conn.close()

    def set_agent_skills(self, agent_id: int, skill_ids: list[int]) -> None:
        """全量替换：先清空，再逐个绑定"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agent_skills WHERE agent_id=%s", (agent_id,))
                for sid in skill_ids:
                    cur.execute(
                        "INSERT INTO agent_skills (agent_id, skill_id) VALUES (%s, %s)",
                        (agent_id, sid),
                    )
                conn.commit()
        finally:
            conn.close()


skill_service = SkillService()
