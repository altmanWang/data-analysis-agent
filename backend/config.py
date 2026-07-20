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

# Skills 目录
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
