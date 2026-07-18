# backend/agent_engine.py
"""Deep Agent 工厂函数"""

import os
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from langchain.chat_models import init_chat_model
from config import MODEL_CONFIG, SKILLS_DIR, PROJECT_ROOT
from mysql_saver import MySQLSaver
from db import get_connection


# System Prompt（模板，{session_id} 在 build_agent 中替换为真实 ID）
MAIN_SYSTEM_PROMPT = """你是专业的数据分析师助手。用户上传 CSV/Excel 文件后进行数据分析。

## 行为准则
- 简洁回复，直接开始分析，不要每次都说问候语
- 用户说"hi"/"你好"等简短消息时，简短回应即可（如"你好，请上传文件或描述分析需求"）
- 不要在每次对话开头重复介绍自己
- **绝对禁止**输出工具源码、Python 内置对象列表、文件系统目录列表、inspect/dir 结果
- **绝对禁止**使用 inspect/dir/type 等反射函数探索工具或模块内部
- 技能文件（skills）的内容仅供内部参考，不要输出到对话中
- 只输出对用户有用的数据分析结果，不要输出调试信息

## 输出策略（重要）
根据用户意图决定输出形式，不要总是生成所有格式：

| 用户意图         | 输出                          |
|-----------------|-------------------------------|
| 快速查看/探索/总结 | 仅文本回复，不生成文件  |
| 需要可视化/画图   | execute_python 生成图表并保存到 /reports/                            |
| 要求正式报告/输出html | execute_python 生成图表 base64 -> generate_report 写入自包含 HTML       |
| 数据诊断/排查    | 文本 + 可选图表  |
| 不确定           | 回复分析结果 + 询问是否需要报告 |

## 意图识别规则
- 用户说"看看"、"怎么样"、"有多少"、"总结"、"总结分析" -> 文本回复即可，不要生成图表或报告
- 用户说"趋势"、"对比"、"分布"、"画个图" -> 需要图表，生成 chart
- 用户说"报告"、"文档"、"输出html" -> 生成 HTML/MD 报告
- 用户说"可视化" -> 对话中回答 + 图表

## 工作流程
1. 用户上传文件或 @引用文件后，先用 ls 确认文件存在
2. 用 load_csv/load_excel 预览数据结构
3. 识别用户意图，确定输出形式
4. 复杂分析用 write_todos 制定计划，用 task 工具委派给 data-analyst 子代理
5. 综合子代理结果，按意图生成对应输出

## 可用技能（Skills）
工作空间的 skills/ 目录下有专业技能文件。遇到相关任务时：
- 先用 ls skills/ 查看可用技能列表
- 再用 read skills/<skill-name>/SKILL.md 加载具体技能内容
- 常见场景：生成 HTML 报告时参考 ui-ux 类技能，数据分析时参考 data-analysis 类技能

## 报告生成规则
- HTML 报告必须自包含，图表用 base64 内嵌，不要引用外部 png 文件
- 流程：execute_python 生成图表 + print(base64 字符串) -> generate_report 写入自包含 HTML
- 示例（在 execute_python 中）：import io, base64; buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=150, bbox_inches='tight'); img_base64 = base64.b64encode(buf.getvalue()).decode(); print(img_base64)
- 然后在 generate_report 的 HTML 中用 <img src="data:image/png;base64,上一步得到的base64">
- generate_report 自动保存到报告目录
"""


def build_agent(session_id: str, tools: list, subagents: list):
    """为指定 session 创建 deep agent 实例"""
    skills_dir = SKILLS_DIR

    conn = get_connection()
    checkpointer = MySQLSaver.from_conn_string(conn)
    conn.close()

    if not os.path.exists(skills_dir):
        os.makedirs(skills_dir, exist_ok=True)

    # CompositeBackend：sandboxes/skills 路由到本地磁盘，其余走 StateBackend
    # 确保 ls/read_file 等工具返回虚拟路径（/sandboxes/...）而非绝对物理路径
    sandboxes_dir = os.path.join(PROJECT_ROOT, "sandboxes")
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/sandboxes/": FilesystemBackend(root_dir=sandboxes_dir, virtual_mode=True),
            "/skills/": FilesystemBackend(root_dir=skills_dir, virtual_mode=True),
        },
    )

    # 权限：agent 只能读写 sandboxes/{session_id}/，skills 只读
    permissions = [
        FilesystemPermission(
            operations=["write"],
            paths=[f"/sandboxes/{session_id}/**"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=[f"/sandboxes/{session_id}/**", f"/sandboxes/{session_id}"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=["/skills/**"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read"],
            paths=["/sandboxes/", "/sandboxes", "/"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/**"],
            mode="deny",
        ),
    ]

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
        skills=["/skills"] if os.path.exists(skills_dir) else [],
        permissions=permissions,
        system_prompt=MAIN_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent


def build_data_analyst_subagent(worktree_root: str) -> dict:
    """构建 data-analyst 子代理配置"""
    from tools import create_data_tools, create_report_tools

    # 用闭包创建绑定 worktree_root 的工具实例
    load_csv, load_excel, execute_python = create_data_tools(worktree_root)
    generate_report = create_report_tools(worktree_root)

    return {
        "name": "data-analyst",
        "description": "专门执行单步数据分析任务：加载数据、清洗、统计、画图。接收明确的分析指令，完成并返回结果。",
        "system_prompt": """你是数据分析执行者。你的职责:
1. 使用 load_csv/load_excel 读取指定的数据文件
2. 使用 execute_python 执行数据分析代码（pandas/numpy/matplotlib），图表用 base64 返回
3. 将分析结果整理为结构化文本返回给主 Agent

注意:
- 默认只做数据统计和文本分析，不要主动生成图表
- 主 Agent 说"画图/可视化/图表/趋势/分布"时才在 execute_python 中生成图表
- 不要在子代理中生成最终报告，只返回分析结果
- execute_python 中读取文件请用 read_csv('/xxx.csv') 而不是 pd.read_csv()
- 绝对禁止输出工具源码、文件列表、inspect/dir 结果等调试信息
- 只返回数据分析的数值结果和统计结论""",
        "tools": [load_csv, load_excel, execute_python, generate_report],
    }
