# backend/config.py
"""全局配置常量，优先从 .env 文件读取"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

# 工作空间根目录
WORKTREE_ROOT = os.path.join(PROJECT_ROOT, "sandboxes")

# MySQL 配置
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "data_analysis_agent"),
    "charset": "utf8mb4",
}

# Agent 模型配置（DeepSeek）
MODEL_CONFIG = {
    "model": os.getenv("LLM_MODEL", "deepseek-v4-flash"),
    "model_provider": "openai",
    "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    "api_key": os.getenv("LLM_API_KEY", ""),
}

# Agent 运行时参数
AGENT_CONFIG = {
    "temperature": 0,
    "max_retries": 3,
    "timeout": 120,
    "max_tokens": 8192,
}

# Agent 缓存池清理策略
CLEANUP_CONFIG = {
    "interval_seconds": 600,       # 清理检查间隔（10 分钟）
    "idle_timeout_seconds": 3600,  # 闲置超时（1 小时）
}

# SSE 流配置
STREAM_CONFIG = {
    "keepalive_seconds": 15,       # 心跳间隔
    "db_executor_workers": 4,      # DB 写入线程池大小
    "content_truncate": 10000,     # 消息内容截断长度
    "thinking_truncate": 50000,    # 思考内容截断长度
    "tool_input_truncate": 200,    # 工具输入截断长度
}

# Skills 目录
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# ============================================================
# Wasmsh 沙箱配置（Python 代码执行沙箱）
# ============================================================
SANDBOX_CONFIG = {
    # VM 步数预算（0=不限制），用于限制 shell 命令的 VM 指令数。
    # 注意：Python 代码不受 step_budget 约束，需用 execution_timeout 兜底。
    "step_budget": 100_000,

    # 执行超时（秒），宿主端 asyncio.wait_for 强制执行。
    "execution_timeout": 60,

    # 网络白名单。数据科学包通过 backend/sandbox_wheels/ 离线预加载，
    # 无需网络，保留空列表以确保安全。
    "allowed_hosts": [],

    # py_eval 工具单次输出最大字符数，超出截断。
    "max_result_chars": 8000,

    # pickle 快照最大字节数（默认 8 MiB），超出则丢弃快照。
    "max_snapshot_bytes": 8 * 1024 * 1024,
}
