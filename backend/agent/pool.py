# backend/agent/pool.py
"""Agent 实例缓存池 — 懒加载 + 定时过期清理"""

import os
import time
import logging
from agent.engine import build_agent, build_data_analyst_subagent
from tools import create_data_tools
from config import PROJECT_ROOT

logger = logging.getLogger(__name__)


class AgentPool:
    """管理 agent 实例的懒加载缓存池

    _agents: {session_id: (agent, last_accessed_at)}
    """

    def __init__(self):
        self._agents: dict[str, tuple[object, float]] = {}

    def get_agent(self, session_id: str):
        """获取或创建 agent 实例，同时更新最后访问时间"""
        now = time.time()
        if session_id in self._agents:
            agent, _ = self._agents[session_id]
            self._agents[session_id] = (agent, now)
            return agent

        worktree = os.path.join(PROJECT_ROOT, "sandboxes", session_id)

        # 用闭包创建绑定 worktree_root 的工具实例
        load_csv, _ = create_data_tools(worktree)
        tools = [load_csv]
        subagent = build_data_analyst_subagent(worktree)
        agent = build_agent(session_id, tools, [subagent])
        self._agents[session_id] = (agent, now)
        return agent

    def cleanup_idle(self, max_idle_seconds: int = 3600):
        """清理超过 max_idle_seconds 秒未访问的 agent 实例

        判断逻辑：get_agent() 每次调用会更新 last_accessed_at。
        如果距离上次 get_agent() 超过 max_idle_seconds，说明该 session
        已长时间无交互，agent 可以被安全移除。

        注意：正在执行流式响应的 agent 也会被更新 last_accessed_at，
        因为 stream_handler 在流开始时通过 get_agent() 获取了引用。
        流式过程中不会再次调用 get_agent()，但如果流式时间超过
        max_idle_seconds 且没有新的 get_agent() 调用就会误清。
        默认 1 小时超时足够覆盖绝大多数场景。
        """
        now = time.time()
        expired = [
            sid for sid, (_, last) in self._agents.items()
            if now - last > max_idle_seconds
        ]
        for sid in expired:
            self._agents.pop(sid, None)
            logger.info("清理过期 agent: session_id=%s", sid)


# 全局单例
agent_pool = AgentPool()
