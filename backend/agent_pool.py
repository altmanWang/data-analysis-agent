# backend/agent_pool.py
"""Agent 实例缓存池"""

import time
import os
from .agent_engine import build_agent, build_data_analyst_subagent
from .tools import load_csv, load_excel, execute_python, generate_report, generate_chart
from .config import WORKTREE_ROOT


class AgentPool:
    """管理 agent 实例的懒加载缓存池"""

    def __init__(self):
        self._agents: dict[str, tuple] = {}  # {session_id: (agent, last_used_ts)}

    def get_agent(self, session_id: str):
        """获取或创建 agent 实例"""
        if session_id in self._agents:
            agent, _ = self._agents[session_id]
            self._agents[session_id] = (agent, time.time())
            return agent

        worktree = os.path.join(WORKTREE_ROOT, session_id)
        tools = [load_csv, load_excel, execute_python, generate_report, generate_chart]
        subagent = build_data_analyst_subagent(worktree)
        agent = build_agent(session_id, tools, [subagent])
        self._agents[session_id] = (agent, time.time())
        return agent

    def remove(self, session_id: str):
        """从缓存中移除 agent"""
        self._agents.pop(session_id, None)

    def cleanup_expired(self, max_idle_seconds: int = 3600):
        """清理超时未使用的 agent 实例"""
        now = time.time()
        expired = [
            sid for sid, (_, last) in self._agents.items()
            if now - last > max_idle_seconds
        ]
        for sid in expired:
            del self._agents[sid]


# 全局单例
agent_pool = AgentPool()
