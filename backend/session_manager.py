# backend/session_manager.py
"""会话元数据管理（MySQL CRUD）"""

import uuid
from db import get_connection


class SessionManager:
    """会话元数据 CRUD"""

    def create(self, user_id: str = "", title: str = "新会话") -> dict:
        session_id = str(uuid.uuid4())
        worktree_path = f"sandboxes/{session_id}"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id, title, user_id, worktree_path) "
                    "VALUES (%s, %s, %s, %s)",
                    (session_id, title, user_id, worktree_path),
                )
                conn.commit()
            return self.get(session_id)
        finally:
            conn.close()

    def get(self, session_id: str) -> dict | None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, title, user_id, worktree_path, "
                    "obs_archive_key, status, created_at, last_active "
                    "FROM sessions WHERE session_id=%s AND status != 'deleted'",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "session_id": row[0],
                    "title": row[1],
                    "user_id": row[2],
                    "worktree_path": row[3],
                    "obs_archive_key": row[4],
                    "status": row[5],
                    "created_at": str(row[6]),
                    "last_active": str(row[7]),
                }
        finally:
            conn.close()

    def list_by_user(self, user_id: str = "") -> list[dict]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "SELECT session_id, title, status, created_at, last_active "
                        "FROM sessions WHERE user_id=%s AND status != 'deleted' "
                        "ORDER BY last_active DESC",
                        (user_id,),
                    )
                else:
                    cur.execute(
                        "SELECT session_id, title, status, created_at, last_active "
                        "FROM sessions WHERE status != 'deleted' "
                        "ORDER BY last_active DESC"
                    )
                rows = cur.fetchall()
                return [
                    {
                        "session_id": r[0],
                        "title": r[1],
                        "status": r[2],
                        "created_at": str(r[3]),
                        "last_active": str(r[4]),
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def update_status(self, session_id: str, status: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET status=%s WHERE session_id=%s",
                    (status, session_id),
                )
                conn.commit()
        finally:
            conn.close()

    def update_last_active(self, session_id: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET last_active=NOW() WHERE session_id=%s",
                    (session_id,),
                )
                conn.commit()
        finally:
            conn.close()

    def update_obs_key(self, session_id: str, obs_key: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET obs_archive_key=%s WHERE session_id=%s",
                    (obs_key, session_id),
                )
                conn.commit()
        finally:
            conn.close()

    def soft_delete(self, session_id: str) -> None:
        self.update_status(session_id, "deleted")


# 全局单例
session_manager = SessionManager()
