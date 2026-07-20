# backend/db.py
"""MySQL 数据库连接管理"""

import pymysql
from config import DB_CONFIG

DB_NAME = DB_CONFIG["database"]


def _ensure_database():
    """确保数据库存在（仅在 init_db 时调用一次）"""
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset=DB_CONFIG["charset"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def get_connection() -> pymysql.connections.Connection:
    """获取 MySQL 连接"""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_NAME,
        charset=DB_CONFIG["charset"],
    )


def init_db():
    """初始化所有表（sessions + checkpointer 三张表）"""
    _ensure_database()
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

        # 创建 checkpointer 表
        from mysql_saver import MySQLSaver
        MySQLSaver.from_conn_string(conn)

        # 创建 message_history 表
        with conn.cursor() as cur:
            # 兼容旧表：删除废弃的 extra 列 + 重命名 thread_id → session_id
            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id  VARCHAR(36) NOT NULL COMMENT '会话 ID',
                    role        VARCHAR(16) NOT NULL COMMENT 'user / assistant / tool',
                    content     LONGTEXT COMMENT '消息内容',
                    tool_name   VARCHAR(128) COMMENT '工具名 (仅 tool 角色)',
                    tool_args   JSON COMMENT '工具参数 (仅 tool 角色)',
                    tool_result JSON COMMENT '工具结果 (仅 tool 角色)',
                    tool_status VARCHAR(16) COMMENT 'running / done (仅 tool 角色)',
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_session (session_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # 迁移已有表：删除 extra 列，重命名 thread_id → session_id
            try:
                cur.execute("ALTER TABLE message_history DROP COLUMN IF EXISTS extra")
            except Exception:
                pass
            try:
                cur.execute(
                    "ALTER TABLE message_history "
                    "CHANGE COLUMN thread_id session_id VARCHAR(36) NOT NULL COMMENT '会话 ID'"
                )
            except Exception:
                pass
            conn.commit()
    finally:
        conn.close()
