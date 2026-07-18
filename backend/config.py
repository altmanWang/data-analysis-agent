# backend/config.py
"""全局配置常量"""

import os

# 工作空间根目录
WORKTREE_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sandboxes")

# MySQL 配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "data_analysis_agent",
    "charset": "utf8mb4",
}

# Agent 模型配置
MODEL_CONFIG = {
    "model": "anthropic:claude-sonnet-4-6",  # 根据实际替换
}

# Skills 目录
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# 归档配置
ARCHIVE_IDLE_MINUTES = 30
