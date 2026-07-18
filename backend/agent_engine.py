# backend/agent_engine.py
"""Deep Agent 工厂函数"""

import os
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from langchain.chat_models import init_chat_model
from .config import MODEL_CONFIG, SKILLS_DIR, WORKTREE_ROOT
from .mysql_saver import MySQLSaver
from .db import get_connection


# System Prompt
MAIN_SYSTEM_PROMPT = """你是专业的数据分析师助手。用户上传 CSV/Excel 文件后进行数据分析。

## 输出策略（重要）
根据用户意图决定输出形式，不要总是生成所有格式：

| 用户意图         | 输出                          |
|-----------------|-------------------------------|
| 快速查看/探索    | 仅在对话中回复文本，不生成文件  |
| 需要可视化       | 文本解释 + generate_chart()    |
| 要求正式报告     | generate_report(html+md)       |
| 数据诊断/排查    | 文本 + 可选 generate_report()  |
| 不确定           | 回复分析结果 + 询问是否需要报告 |

## 意图识别规则
- 用户说"看看"、"怎么样"、"有多少" → 快速探索，文本回复即可
- 用户说"趋势"、"对比"、"分布" → 需要图表，生成 chart
- 用户说"报告"、"总结"、"文档" → 生成 HTML/MD 报告
- 用户说"画个图"、"可视化" → 仅在对话中回答 + 图表

## 工作流程
1. 用户上传文件或 @引用文件后，先用 ls 确认文件存在
2. 用 load_csv/load_excel 预览数据结构
3. 识别用户意图，确定输出形式
4. 复杂分析用 write_todos 制定计划，用 task 工具委派给 data-analyst 子代理
5. 综合子代理结果，按意图生成对应输出

## 可用技能（Skills）
工作空间中有以下专业技能，遇到相关任务时会自动加载：
- ui-ux-design-pro: HTML 报告设计规范（配色/排版/模板）
- data-analysis-guide: 数据分析方法论
- chart-best-practices: 图表选型指南
- report-templates: 预置报告模板（dashboard/executive/detailed）

## 文件路径
你的工作空间根目录为 /，用户上传文件在 /uploads/，报告保存在 /reports/
"""


def build_agent(session_id: str, tools: list, subagents: list):
    """为指定 session 创建 deep agent 实例"""
    worktree = os.path.join(WORKTREE_ROOT, session_id)
    skills_dir = SKILLS_DIR

    conn = get_connection()
    checkpointer = MySQLSaver.from_conn_string(conn)

    # Debug: print which backend paths exist
    if not os.path.exists(skills_dir):
        print(f"[WARNING] Skills dir not found: {skills_dir}")
        os.makedirs(skills_dir, exist_ok=True)

    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=worktree, virtual_mode=True),
        routes={
            "/skills/": FilesystemBackend(root_dir=skills_dir, virtual_mode=True),
        },
    )

    model = init_chat_model(
        model=MODEL_CONFIG["model"],
        model_provider=MODEL_CONFIG["model_provider"],
        base_url=MODEL_CONFIG["base_url"],
        api_key=MODEL_CONFIG["api_key"],
        temperature=0,
    )

    agent = create_deep_agent(
        model=model,
        backend=backend,
        tools=tools,
        subagents=subagents,
        skills=[skills_dir] if os.path.exists(skills_dir) else [],
        system_prompt=MAIN_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent


def build_data_analyst_subagent(worktree_root: str) -> dict:
    """构建 data-analyst 子代理配置"""
    from .tools import load_csv, load_excel, execute_python, generate_chart

    return {
        "name": "data-analyst",
        "description": "专门执行单步数据分析任务：加载数据、清洗、统计、画图。接收明确的分析指令，完成并返回结果。",
        "system_prompt": """你是数据分析执行者。你的职责:
1. 使用 load_csv/load_excel 读取指定的数据文件
2. 使用 execute_python 执行数据分析代码（pandas/numpy/matplotlib）
3. 使用 generate_chart 生成可视化图表
4. 将分析结果整理为结构化文本返回给主 Agent

注意:
- 不要在子代理中生成最终报告，只返回分析结果
- 文件路径格式: /uploads/xxx.csv
- 图表保存到 /reports/ 目录""",
        "tools": [load_csv, load_excel, execute_python, generate_chart],
    }
