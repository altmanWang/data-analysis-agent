# backend/agent_pool.py
"""Agent 实例缓存池"""

import os
from agent_engine import build_agent, build_data_analyst_subagent
from tools import create_data_tools
from config import PROJECT_ROOT


class AgentPool:
    """管理 agent 实例的懒加载缓存池"""

    def __init__(self):
        self._agents: dict[str, object] = {}

    def get_agent(self, session_id: str):
        """获取或创建 agent 实例"""
        if session_id in self._agents:
            return self._agents[session_id]

        worktree = os.path.join(PROJECT_ROOT, "sandboxes", session_id)

        # 用闭包创建绑定 worktree_root 的工具实例
        load_csv, load_excel, execute_python = create_data_tools(worktree)
        tools = [load_csv]
        subagent = build_data_analyst_subagent(worktree)
        agent = build_agent(session_id, tools, [subagent])
        self._agents[session_id] = agent
        return agent

    def remove(self, session_id: str):
        """从缓存中移除 agent"""
        self._agents.pop(session_id, None)


# 全局单例
agent_pool = AgentPool()
