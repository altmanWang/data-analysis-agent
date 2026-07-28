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
            # 迁移 session_agents：旧表 unique key 是 (session_id)，改为复合唯一 (session_id, agent_id)
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='session_agents' AND CONSTRAINT_NAME='uk_session'",
                    (DB_NAME,),
                )
                if cur.fetchone()[0] > 0:
                    cur.execute("ALTER TABLE session_agents DROP INDEX uk_session")
            except Exception:
                pass
            conn.commit()

        # 创建 checkpointer 表
        from storage.mysql_saver import MySQLSaver
        MySQLSaver.from_conn_string(conn)

        # 创建 message_history 表
        with conn.cursor() as cur:
            # 兼容旧表：删除废弃的 extra 列 + 重命名 thread_id → session_id
            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id      VARCHAR(36) NOT NULL COMMENT '会话 ID',
                    role            VARCHAR(16) NOT NULL COMMENT 'user / assistant / tool',
                    content         LONGTEXT COMMENT '消息内容',
                    thinking_content LONGTEXT COMMENT '推理思考过程 (仅 assistant)',
                    tool_name       VARCHAR(128) COMMENT '工具名 (仅 tool 角色)',
                    tool_args       JSON COMMENT '工具参数 (仅 tool 角色)',
                    tool_result     JSON COMMENT '工具结果 (仅 tool 角色)',
                    tool_status     VARCHAR(16) COMMENT 'running / done (仅 tool 角色)',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_session (session_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # 迁移已有表：删除 extra 列，重命名 thread_id→session_id，新增 thinking_content
            # 通过检查 thinking_content 列是否存在判断迁移是否已完成
            cur.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='message_history' AND COLUMN_NAME='thinking_content'",
                (DB_NAME,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE message_history DROP COLUMN IF EXISTS extra")
                try:
                    cur.execute(
                        "ALTER TABLE message_history "
                        "CHANGE COLUMN thread_id session_id VARCHAR(36) NOT NULL COMMENT '会话 ID'"
                    )
                except Exception:
                    pass  # 列可能已改名或不存在
                cur.execute(
                    "ALTER TABLE message_history "
                    "ADD COLUMN thinking_content LONGTEXT COMMENT '推理思考过程'"
                )
            conn.commit()

        # 创建 agents 表 — 用户自定义 Agent 元数据
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    name            VARCHAR(100) NOT NULL COMMENT 'Agent 名称',
                    description     VARCHAR(500) DEFAULT '' COMMENT 'Agent 描述（用于主 Agent 路由判断）',
                    system_prompt   LONGTEXT NOT NULL COMMENT '系统提示词',
                    user_id         VARCHAR(100) DEFAULT '' COMMENT '创建者',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_name_user (name, user_id),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # 迁移：旧表无 description 列则新增
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='agents' AND COLUMN_NAME='description'",
                    (DB_NAME,),
                )
                if cur.fetchone()[0] == 0:
                    cur.execute(
                        "ALTER TABLE agents "
                        "ADD COLUMN description VARCHAR(500) DEFAULT '' COMMENT 'Agent 描述'"
                    )
            except Exception:
                pass
            conn.commit()

        # 创建 session_agents 表 — 会话与 Agent 的关联
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_agents (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    session_id      VARCHAR(36) NOT NULL COMMENT '会话 ID',
                    agent_id        INT NOT NULL COMMENT 'Agent ID',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_session_agent (session_id, agent_id),
                    INDEX idx_session (session_id),
                    INDEX idx_agent_id (agent_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
    finally:
        conn.close()
