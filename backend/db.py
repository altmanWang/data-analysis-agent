# backend/db.py
"""MySQL 数据库连接管理"""

import pymysql
from .config import DB_CONFIG

DB_NAME = DB_CONFIG["database"]


def get_connection() -> pymysql.connections.Connection:
    """获取 MySQL 连接，自动创建数据库"""
    # 先连接不指定数据库，创建数据库
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset=DB_CONFIG["charset"],
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn.close()

    # 连接目标数据库
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_NAME,
        charset=DB_CONFIG["charset"],
    )
    return conn


def init_db():
    """初始化所有表"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id      VARCHAR(36) PRIMARY KEY COMMENT 'UUID',
                    title           VARCHAR(200) DEFAULT '新会话' COMMENT '会话标题',
                    user_id         VARCHAR(100) DEFAULT '' COMMENT '用户标识',
                    worktree_path   VARCHAR(500) NOT NULL COMMENT '沙盒路径',
                    obs_archive_key VARCHAR(500) DEFAULT '' COMMENT 'OBS归档key(打桩)',
                    status          VARCHAR(20) DEFAULT 'active' COMMENT 'active/archiving/archived/restoring/deleted',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_status (status),
                    INDEX idx_last_active (last_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
        conn.commit()
    finally:
        conn.close()
