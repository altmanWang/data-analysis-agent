# backend/agent_engine.py
"""Deep Agent 工厂函数"""

import os
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain.chat_models import init_chat_model
from config import MODEL_CONFIG, SKILLS_DIR, PROJECT_ROOT
from mysql_saver import MySQLSaver
from db import get_connection


# System Prompt（模板，{session_id} 在 build_agent 中替换为真实 ID）
MAIN_SYSTEM_PROMPT = """你是专业的数据分析师助手。用户上传 CSV/Excel 文件后进行数据分析。"""


def build_agent(session_id: str, tools: list, subagents: list):
    """为指定 session 创建 deep agent 实例"""
    skills_dir = SKILLS_DIR

    conn = get_connection()
    checkpointer = MySQLSaver.from_conn_string(conn)
    conn.close()

    if not os.path.exists(skills_dir):
        os.makedirs(skills_dir, exist_ok=True)

    # CompositeBackend：所有文件操作默认写入 sandboxes/{session_id}，skills 只读路由
    # 确保 ls/read_file/write_file 等工具返回虚拟路径而非绝对物理路径
    sandboxes_dir = os.path.join(PROJECT_ROOT, "sandboxes", session_id)
    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=sandboxes_dir, virtual_mode=True),
        routes={
            "/skills/": FilesystemBackend(root_dir=skills_dir, virtual_mode=True),
        },
    )

    # 权限：agent 只能读写 sandboxes/{session_id}/，skills 只读
    permissions = [
        FilesystemPermission(
            operations=["read", "write"],
            paths=[f"/sandboxes/{session_id}/**"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=["/skills/**"],
            mode="allow",
        ),

    ]

    model = init_chat_model(
        model=MODEL_CONFIG["model"],
        model_provider=MODEL_CONFIG["model_provider"],
        base_url=MODEL_CONFIG["base_url"],
        api_key=MODEL_CONFIG["api_key"],
        temperature=0,
        max_retries=3,     # API 调用失败时自动重试
        timeout=120,        # 单次请求超时（秒），防止长时间 hang
        max_tokens=8192,    # 限制单次响应最大 token，减少连接中断概率
    )

    agent = create_deep_agent(
        model=model,
        backend=backend,
        tools=tools,
        subagents=subagents,
        skills=["/skills"] if os.path.exists(skills_dir) else [],
        permissions=permissions,
        system_prompt=MAIN_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent


def build_data_analyst_subagent(worktree_root: str) -> dict:
    """构建 data-analyst 子代理配置"""
    from tools import create_data_tools

    # 用闭包创建绑定 worktree_root 的工具实例
    load_csv, load_excel, execute_python = create_data_tools(worktree_root)

    return {
        "name": "data-analyst",
        "description": "数据分析执行者。",
        "system_prompt": """你是数据分析执行者。""",
        "tools": [load_csv],
    }
