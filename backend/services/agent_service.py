# backend/services/agent_service.py
"""Agent 元数据管理 (MySQL CRUD) + 会话关联"""

from db import get_connection


class AgentService:
    """用户自定义 Agent 的 CRUD 与 session 关联管理"""

    # ────────── Agent CRUD ──────────

    def create(self, name: str, description: str, system_prompt: str, user_id: str = "") -> dict:
        """创建自定义 Agent"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agents (name, description, system_prompt, user_id) VALUES (%s, %s, %s, %s)",
                    (name, description, system_prompt, user_id),
                )
                conn.commit()
                agent_id = cur.lastrowid
                return self.get(agent_id)
        finally:
            conn.close()

    def list_all(self, user_id: str = "") -> list[dict]:
        """获取所有 Agent 列表"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "SELECT id, name, description, system_prompt, user_id, created_at, updated_at "
                        "FROM agents WHERE user_id=%s ORDER BY created_at DESC",
                        (user_id,),
                    )
                else:
                    cur.execute(
                        "SELECT id, name, description, system_prompt, user_id, created_at, updated_at "
                        "FROM agents ORDER BY created_at DESC"
                    )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "description": r[2],
                        "system_prompt": r[3],
                        "user_id": r[4],
                        "created_at": str(r[5]),
                        "updated_at": str(r[6]),
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def get(self, agent_id: int) -> dict | None:
        """获取单个 Agent 详情"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, description, system_prompt, user_id, created_at, updated_at "
                    "FROM agents WHERE id=%s",
                    (agent_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "system_prompt": row[3],
                    "user_id": row[4],
                    "created_at": str(row[5]),
                    "updated_at": str(row[6]),
                }
        finally:
            conn.close()

    def update(self, agent_id: int, name: str, description: str, system_prompt: str) -> dict | None:
        """更新 Agent"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE agents SET name=%s, description=%s, system_prompt=%s WHERE id=%s",
                    (name, description, system_prompt, agent_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                return self.get(agent_id)
        finally:
            conn.close()

    def delete(self, agent_id: int) -> bool:
        """删除 Agent（级联清理 session_agents）"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # 先清理所有引用该 agent 的 session 关联
                cur.execute("DELETE FROM session_agents WHERE agent_id=%s", (agent_id,))
                cur.execute("DELETE FROM agents WHERE id=%s", (agent_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    # ────────── Session-Agent 关联（支持多选）──────────

    def get_session_agents(self, session_id: str) -> list[dict]:
        """获取指定 session 当前选中的所有 Agent"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.id, a.name, a.description, a.system_prompt, a.user_id, a.created_at, a.updated_at "
                    "FROM agents a "
                    "INNER JOIN session_agents sa ON a.id = sa.agent_id "
                    "WHERE sa.session_id=%s "
                    "ORDER BY sa.created_at",
                    (session_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "description": r[2],
                        "system_prompt": r[3],
                        "user_id": r[4],
                        "created_at": str(r[5]),
                        "updated_at": str(r[6]),
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def toggle_session_agent(self, session_id: str, agent_id: int) -> dict:
        """切换 session 的 Agent：已选则移除，未选则添加。返回当前选中的 Agent 列表"""
        agent = self.get(agent_id)
        if not agent:
            return {"added": False, "agents": self.get_session_agents(session_id)}

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM session_agents WHERE session_id=%s AND agent_id=%s",
                    (session_id, agent_id),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "DELETE FROM session_agents WHERE session_id=%s AND agent_id=%s",
                        (session_id, agent_id),
                    )
                    added = False
                else:
                    cur.execute(
                        "INSERT INTO session_agents (session_id, agent_id) VALUES (%s, %s)",
                        (session_id, agent_id),
                    )
                    added = True
                conn.commit()
        finally:
            conn.close()

        return {"added": added, "agents": self.get_session_agents(session_id)}

    def remove_session_agents(self, session_id: str) -> None:
        """清空 session 的所有 Agent 选择"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM session_agents WHERE session_id=%s",
                    (session_id,),
                )
                conn.commit()
        finally:
            conn.close()


# 全局单例
agent_service = AgentService()
