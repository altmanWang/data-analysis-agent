# backend/agent/pool.py
"""Agent 实例缓存池 — 懒加载 + 定时过期清理

_agents: {session_id: (agent, last_accessed_at, cleanup_fn)}
    cleanup_fn 用于关闭该 session 的 wasmsh 沙箱 Node.js 子进程。
"""

import os
import time
import logging
from agent.engine import build_agent, build_data_analyst_subagent
from tools import create_data_tools
from config import PROJECT_ROOT

logger = logging.getLogger(__name__)


class AgentPool:
    """管理 agent 实例的懒加载缓存池

    _agents: {session_id: (agent, last_accessed_at, cleanup_fn)}
    """

    def __init__(self):
        self._agents: dict[str, tuple[object, float, callable | None]] = {}

    def get_agent(self, session_id: str):
        """获取或创建 agent 实例，同时更新最后访问时间"""
        now = time.time()
        if session_id in self._agents:
            agent, _, _ = self._agents[session_id]
            self._agents[session_id] = (agent, now, None)
            return agent

        worktree = os.path.join(PROJECT_ROOT, "sandboxes", session_id)

        # 用闭包创建绑定 worktree_root 的工具实例
        load_csv, _ = create_data_tools(worktree)
        tools = [load_csv]
        subagent = build_data_analyst_subagent(worktree)
        agent, cleanup_fn = build_agent(session_id, tools, [subagent])
        self._agents[session_id] = (agent, now, cleanup_fn)
        return agent

    def cleanup_idle(self, max_idle_seconds: int = 3600):
        """清理超过 max_idle_seconds 秒未访问的 agent 实例。

        清理时同时关闭该 session 的 wasmsh 沙箱 Node.js 子进程，
        防止僵尸进程累积。
        """
        now = time.time()
        expired = [
            sid for sid, (_, last, _) in self._agents.items()
            if now - last > max_idle_seconds
        ]
        for sid in expired:
            _, _, cleanup_fn = self._agents.pop(sid, (None, None, None))
            if cleanup_fn is not None:
                try:
                    cleanup_fn()
                    logger.info("已关闭沙箱: session_id=%s", sid)
                except Exception as e:
                    logger.warning("沙箱关闭失败 session_id=%s: %s", sid, e)
            logger.info("清理过期 agent: session_id=%s", sid)

    def evict_session(self, session_id: str):
        """强制驱逐指定 session（用于手动删除 session 时清理资源）"""
        entry = self._agents.pop(session_id, None)
        if entry is None:
            return
        _, _, cleanup_fn = entry
        if cleanup_fn is not None:
            try:
                cleanup_fn()
                logger.info("已关闭沙箱: session_id=%s", session_id)
            except Exception as e:
                logger.warning("沙箱关闭失败 session_id=%s: %s", session_id, e)


# 全局单例
agent_pool = AgentPool()
