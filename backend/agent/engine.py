# backend/agent/engine.py
"""Deep Agent 工厂函数"""

import os
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain.chat_models import init_chat_model
from config import MODEL_CONFIG, AGENT_CONFIG, SKILLS_DIR, PROJECT_ROOT
from storage.mysql_saver import MySQLSaver
from db import get_connection


def _discover_skills(skills_dir: str) -> list[str]:
    """扫描 skills 目录，返回所有包含 SKILL.md 的子目录路径列表。
    
    deepagents 的 skills 参数期望每个技能一个目录路径（如 /skills/ui-ux-pro-max/），
    而非父目录。此函数自动发现所有可用技能。
    """
    if not os.path.isdir(skills_dir):
        return []
    discovered = []
    for entry in os.scandir(skills_dir):
        if entry.is_dir() and os.path.isfile(os.path.join(entry.path, "SKILL.md")):
            discovered.append(f"/skills/{entry.name}/")
    return discovered


# System Prompt（模板，{session_id} 在 build_agent 中替换为真实 ID）
MAIN_SYSTEM_PROMPT = """你是专业的数据分析师助手。用户上传 CSV/Excel 文件后进行数据分析。

## 工作空间
- 你的工作根目录是 `/`，所有上传的数据文件和生成的报告都在这里。
- `/skills/` 目录包含只读的技能参考文件（SKILL.md），可读取但不能修改。
- 除 `/` 和 `/skills/` 外，不存在其他目录（如 /tmp、/home、/root、/app），请勿尝试访问。

## 数据分析工具
使用 data-analyst 子代理执行具体的数据分析任务。"""


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
        FilesystemPermission(
            operations=["write"],
            paths=["/skills/**"],
            mode="deny",
        ),
    ]

    model = init_chat_model(
        model=MODEL_CONFIG["model"],
        model_provider=MODEL_CONFIG["model_provider"],
        base_url=MODEL_CONFIG["base_url"],
        api_key=MODEL_CONFIG["api_key"],
        temperature=AGENT_CONFIG["temperature"],
        max_retries=AGENT_CONFIG["max_retries"],
        timeout=AGENT_CONFIG["timeout"],
        max_tokens=AGENT_CONFIG["max_tokens"],
    )

    # 自动发现 skills 目录下所有有效技能
    skill_paths = _discover_skills(skills_dir)
    agent = create_deep_agent(
        model=model,
        backend=backend,
        tools=tools,
        subagents=subagents,
        skills=skill_paths,
        permissions=permissions,
        system_prompt=MAIN_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent


def build_data_analyst_subagent(worktree_root: str) -> dict:
    """构建 data-analyst 子代理配置"""
    from tools import create_data_tools

    # 用闭包创建绑定 worktree_root 的工具实例
    load_csv, _ = create_data_tools(worktree_root)

    # 子代理也需要显式配置技能（不继承父 agent）
    skill_paths = _discover_skills(SKILLS_DIR)

    return {
        "name": "data-analyst",
        "description": "数据分析执行者，负责读取数据、生成 HTML 报告。",
        "system_prompt": """你是数据分析执行者，负责读取 CSV/Excel 数据、执行分析代码并生成 HTML 报告。

## 工作空间
- 你的工作根目录是 `/`，所有数据文件和生成的报告（如 HTML、图表）都保存在这里。
- `/skills/` 目录包含只读的技能参考文件，可读取但不可修改。
- 除 `/` 和 `/skills/` 外，不存在其他目录，请勿尝试访问或列出系统路径。

## 分析要求
- 灵活加载 skill 美化 HTML 报告。
- 图表保存到 `/reports/` 目录，HTML 报告保存到 `/` 根目录。""",
        "tools": [load_csv],
        "skills": skill_paths,
    }
