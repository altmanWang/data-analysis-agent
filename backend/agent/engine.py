# backend/agent/engine.py
"""Deep Agent 工厂函数"""

import os
import logging
from deepagents import create_deep_agent, FilesystemPermission

logger = logging.getLogger(__name__)
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


# System Prompt（模板，{custom_agents_section} 在 build_agent 中动态替换）
MAIN_SYSTEM_PROMPT = """你是一个通用Agent。

## 工作空间
- 你的工作根目录是 `/`，所有上传的数据文件和生成的报告都在这里。
- `/skills/` 目录包含只读的技能参考文件（SKILL.md），可读取但不能修改。
- 除 `/` 和 `/skills/` 外，不存在其他目录（如 /tmp、/home、/root、/app），请勿尝试访问。
"""


def _load_session_agents(session_id: str) -> list[dict]:
    """从 MySQL 加载当前 session 选中的自定义 Agent，构建 subagent 配置。

    直接查 session_agents 表，不依赖文件系统。subagent dict 格式：
    {name, description, system_prompt}
    """
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT a.name, a.description, a.system_prompt "
                "FROM agents a "
                "INNER JOIN session_agents sa ON a.id = sa.agent_id "
                "WHERE sa.session_id=%s "
                "ORDER BY sa.created_at",
                (session_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    subagents = []
    for name, description, system_prompt in rows:
        subagents.append({
            "name": name,
            "description": description or f"用户自定义 Agent: {name}",
            "system_prompt": system_prompt,
        })

    if subagents:
        logger.info(
            "session=%s 从数据库加载自定义 Agent: %s",
            session_id, [s["name"] for s in subagents],
        )
    return subagents


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

    # 从 MySQL 加载用户自定义 Agent + 默认 subagents
    custom_agents = _load_session_agents(session_id)
    all_subagents = custom_agents + subagents

    # 动态构建系统提示词：提及当前可用的自定义 Agent
    custom_agents_section = ""
    if custom_agents:
        names = [a["name"] for a in custom_agents]
        custom_agents_section = (
            "\n## 当前激活的自定义 Agent\n"
            + "\n".join(f"- **{n}**：{a['description']}" for n, a in zip(names, custom_agents))
            + "\n\n以上 Agent 已激活，请在任务中根据需要使用其专业能力。"
        )
        logger.info(
            "session=%s 共 %d 个 subagent（自定义=%d 默认=%d）",
            session_id, len(all_subagents), len(custom_agents), len(subagents),
        )

    system_prompt = MAIN_SYSTEM_PROMPT.format(custom_agents_section=custom_agents_section)

    agent = create_deep_agent(
        model=model,
        backend=backend,
        tools=tools,
        subagents=all_subagents,
        skills=skill_paths,
        permissions=permissions,
        system_prompt=system_prompt,
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
        "system_prompt": """你是数据分析执行者，负责读取 CSV/Excel 数据并生成 HTML 报告。
        ## 铁律
        当前没有shell执行权限，所以不要写任何可执行的代码进行数据分析
        ## 分析要求
        - 灵活加载 skill 美化 HTML 报告。
        - 图表保存到 `/reports/` 目录，HTML 报告保存到 `/` 根目录。""",
        "tools": [load_csv],
        "skills": skill_paths,
    }
