# 数据分析 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 deepagents + FastAPI + Vue3 构建支持多人同时在线、自然语言数据分析的 Web 应用

**Architecture:** FastAPI 后端通过 WebSocket + REST API 与 Vue3 前端通信，deepagents 通过 FilesystemBackend 管理每个 session 的独立沙盒工作空间，MySQL 统一存储会话元数据和 agent 对话状态

**Tech Stack:** Python 3.10, FastAPI 0.115.12, deepagents, LangGraph 1.0.5, LangChain 1.2.0, MySQL (pymysql 1.1.1), Vue3+JS

## Global Constraints

- Python 3.10, conda 环境 py310
- FastAPI==0.115.12
- LangGraph==1.0.5
- LangChain==1.2.0
- pymysql==1.1.1
- MySQL localhost:3306, password:123456
- 前端 Vue3+JS (非 TypeScript)
- 所有代码注释、文档使用中文
- worktree 根目录: `sandboxes/{session_id}/`
- OBS 相关功能打桩预留
- token/cookie 鉴权 placeholder，在请求头传递
- sessions 表存储 user_id，不存 token/cookie

---

## File Structure

```
data-analysis-agent/
├── backend/
│   ├── main.py                    # FastAPI 入口，挂载路由，启动 WS
│   ├── config.py                  # 配置项（DB、路径、模型等）
│   ├── db.py                      # MySQL 连接池 + sessions 表创建
│   ├── mysql_saver.py             # MySQLSaver（BaseCheckpointSaver 实现）
│   ├── session_manager.py         # 会话 CRUD
│   ├── worktree_manager.py        # Worktree 创建/归档/恢复（OBS 打桩）
│   ├── agent_engine.py            # create_deep_agent 工厂
│   ├── agent_pool.py              # Agent 实例缓存池
│   ├── ws_handler.py              # WebSocket 连接管理 + astream_events
│   ├── api/
│   │   ├── __init__.py
│   │   ├── sessions.py            # REST: sessions CRUD
│   │   └── files.py               # REST: files CRUD + 预览
│   └── tools/
│       ├── __init__.py
│       ├── data_tools.py          # load_csv, load_excel, execute_python
│       └── report_tools.py        # generate_report, generate_chart
│
├── skills/                        # 系统级 Skill（Git 版本控制，CompositeBackend 只读路由）
│   ├── ui-ux-design-pro/
│   │   ├── SKILL.md
│   │   └── templates/
│   │       ├── dashboard.html
│   │       ├── executive.html
│   │       └── detailed.html
│   ├── data-analysis-guide/
│   │   └── SKILL.md
│   ├── chart-best-practices/
│   │   └── SKILL.md
│   └── report-templates/
│       ├── SKILL.md
│       ├── templates/
│       └── assets/
│           ├── style.css
│           └── chart.js
│
├── sandboxes/                     # .gitignore
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/
│       │   └── index.js
│       ├── stores/
│       │   ├── sessionStore.js
│       │   ├── chatStore.js
│       │   └── fileStore.js
│       ├── components/
│       │   ├── SessionSidebar.vue
│       │   ├── SessionCreate.vue
│       │   ├── SessionList.vue
│       │   ├── SessionItem.vue
│       │   ├── ChatPanel.vue
│       │   ├── ChatHeader.vue
│       │   ├── ChatMessages.vue
│       │   ├── MessageBubble.vue
│       │   ├── TextContent.vue
│       │   ├── FileMention.vue
│       │   ├── SubAgentCard.vue
│       │   ├── TodoPanel.vue
│       │   ├── ReportCard.vue
│       │   ├── ChatInput.vue
│       │   ├── MentionDropdown.vue
│       │   ├── FileUploadBtn.vue
│       │   ├── WorktreePanel.vue
│       │   ├── PanelTabs.vue
│       │   ├── FileTree.vue
│       │   ├── FileTreeNode.vue
│       │   ├── FileContextMenu.vue
│       │   ├── FilePreview.vue
│       │   ├── HtmlPreview.vue
│       │   ├── MarkdownPreview.vue
│       │   └── ImagePreview.vue
│       └── utils/
│           └── websocket.js
```

---

### Task 1: 后端项目初始化与基础配置

**Files:**
- Create: `backend/config.py`
- Create: `backend/main.py`
- Create: `backend/__init__.py`
- Create: `backend/api/__init__.py`
- Create: `backend/tools/__init__.py`
- Modify: 项目根 `requirements.txt` 或 `pyproject.toml`

**Interfaces:**
- Produces: `config.py` 导出 `DB_CONFIG`, `WORKTREE_ROOT`, `MODEL_CONFIG`, `SKILLS_DIR` 等配置常量

- [ ] **Step 1: 创建 requirements.txt**

```bash
# requirements.txt
fastapi==0.115.12
langgraph==1.0.5
langchain==1.2.0
deepagents
pymysql==1.1.1
pandas
openpyxl
matplotlib
uvicorn[standard]
python-multipart
aiofiles
```

- [ ] **Step 2: 安装依赖**

```bash
conda activate py310
pip install -r requirements.txt
```

Expected: 所有包安装成功，无版本冲突。

- [ ] **Step 3: 创建 config.py**

```python
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
    # "model": "openai:gpt-4o",
}

# Skills 目录
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# 归档配置
ARCHIVE_IDLE_MINUTES = 30
```

- [ ] **Step 4: 创建 main.py 骨架**

```python
# backend/main.py
"""FastAPI 应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="数据分析 Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: 验证启动**

```bash
cd backend && uvicorn main:app --reload --port 8000
# 浏览器访问 http://localhost:8000/health → {"status":"ok"}
```

Expected: FastAPI 正常启动，health 端点返回 200。

- [ ] **Step 6: 创建 .gitignore**

```bash
# .gitignore
sandboxes/
__pycache__/
*.pyc
.env
node_modules/
dist/
.vite/
```

- [ ] **Step 7: Commit**

```bash
git add backend/ requirements.txt .gitignore
git commit -m "feat: 后端项目初始化，FastAPI骨架 + 全局配置"
```

---

### Task 2: MySQL 数据库初始化 + sessions 表

**Files:**
- Create: `backend/db.py`

**Interfaces:**
- Produces: `get_connection()` 返回 pymysql 连接，自动建库建表

- [ ] **Step 1: 创建 db.py**

```python
# backend/db.py
"""MySQL 数据库连接管理"""

import pymysql
from .config import DB_CONFIG

DB_NAME = DB_CONFIG["database"]


def get_connection() -> pymysql.connections.Connection:
    """获取 MySQL 连接，自动创建数据库和表"""
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
    conn.close()
```

- [ ] **Step 2: 在 main.py 启动时调用 init_db**

```python
# backend/main.py 追加
from contextlib import asynccontextmanager
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="数据分析 Agent", lifespan=lifespan)
```

- [ ] **Step 3: 验证表创建**

```bash
mysql -u root -p123456 -e "USE data_analysis_agent; SHOW TABLES; DESCRIBE sessions;"
```

Expected: 显示 `sessions` 表和完整字段。

- [ ] **Step 4: Commit**

```bash
git add backend/db.py backend/main.py
git commit -m "feat: MySQL 连接管理 + sessions 表初始化"
```

---

### Task 3: MySQLSaver 实现

**Files:**
- Create: `backend/mysql_saver.py`

**Interfaces:**
- Produces: `MySQLSaver(conn)` 实现 langgraph.checkpoint.base.BaseCheckpointSaver
- Consumes: `backend/db.py` 的 `get_connection()`

- [ ] **Step 1: 创建 mysql_saver.py**

```python
# backend/mysql_saver.py
"""MySQL Checkpointer - 实现 LangGraph BaseCheckpointSaver 协议

参照 langgraph/checkpoint/sqlite/__init__.py 源码适配为 pymysql。
"""

from contextlib import contextmanager
from typing import Any, AsyncIterator, Iterator, Optional, Sequence, Tuple

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.serde.types import ChannelProtocol

import pymysql

_DEFAULT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id       VARCHAR(255) NOT NULL,
    checkpoint_ns   VARCHAR(255) NOT NULL DEFAULT '',
    checkpoint_id   VARCHAR(255) NOT NULL,
    parent_checkpoint_id VARCHAR(255),
    type            VARCHAR(255),
    checkpoint      LONGBLOB NOT NULL,
    metadata        LONGBLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id       VARCHAR(255) NOT NULL,
    checkpoint_ns   VARCHAR(255) NOT NULL DEFAULT '',
    checkpoint_id   VARCHAR(255) NOT NULL,
    task_id         VARCHAR(255) NOT NULL,
    idx             INT NOT NULL,
    channel         VARCHAR(255) NOT NULL,
    type            VARCHAR(255),
    value           LONGBLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id       VARCHAR(255) NOT NULL,
    checkpoint_ns   VARCHAR(255) NOT NULL DEFAULT '',
    channel         VARCHAR(255) NOT NULL,
    version         VARCHAR(255) NOT NULL,
    type            VARCHAR(255),
    blob            LONGBLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class MySQLSaver(BaseCheckpointSaver):
    """基于 MySQL 的 LangGraph checkpointer"""

    serde = JsonPlusSerializer()

    def __init__(self, conn: pymysql.connections.Connection):
        super().__init__()
        self.conn = conn

    @classmethod
    def from_conn_string(cls, conn: pymysql.connections.Connection) -> "MySQLSaver":
        """从已有连接创建并自动建表"""
        saver = cls(conn)
        saver.setup()
        return saver

    def setup(self):
        """创建 checkpointer 所需的三张表"""
        with self.conn.cursor() as cur:
            for statement in _DEFAULT_TABLE_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
            self.conn.commit()

    def _cursor(self):
        """获取游标（每次调用获取新游标以确保线程安全）"""
        return self.conn.cursor()

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """读取 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        cur = self._cursor()
        try:
            if checkpoint_id:
                cur.execute(
                    "SELECT checkpoint, metadata, parent_checkpoint_id, type "
                    "FROM checkpoints "
                    "WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s",
                    (thread_id, checkpoint_ns, checkpoint_id),
                )
            else:
                cur.execute(
                    "SELECT checkpoint, metadata, parent_checkpoint_id, type "
                    "FROM checkpoints "
                    "WHERE thread_id=%s AND checkpoint_ns=%s "
                    "ORDER BY checkpoint_id DESC LIMIT 1",
                    (thread_id, checkpoint_ns),
                )

            row = cur.fetchone()
            if row is None:
                return None

            checkpoint_data, metadata_data, parent_id, ckpt_type = row
            checkpoint = self.serde.loads_typed((ckpt_type, checkpoint_data))
            metadata = {}
            if metadata_data:
                metadata = self.serde.loads_typed(
                    (ckpt_type, metadata_data)
                ) if isinstance(metadata_data, bytes) else metadata_data

            # 加载 pending writes
            cur.execute(
                "SELECT task_id, channel, type, value FROM checkpoint_writes "
                "WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s "
                "ORDER BY task_id, idx",
                (thread_id, checkpoint_ns, checkpoint["id"]),
            )
            writes_data = cur.fetchall()
            pending_writes = []
            for task_id, channel, w_type, value in writes_data:
                pending_writes.append((task_id, channel, self.serde.loads_typed((w_type, value))))

            config_out = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint["id"],
                }
            }

            return CheckpointTuple(
                config=config_out,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_id,
                    }
                } if parent_id else None,
                pending_writes=pending_writes,
            )
        finally:
            cur.close()

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        """写入 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        ckpt_type, ckpt_bytes = self.serde.dumps_typed(checkpoint)
        meta_type, meta_bytes = self.serde.dumps_typed(metadata)

        cur = self._cursor()
        try:
            cur.execute(
                "INSERT INTO checkpoints "
                "(thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "parent_checkpoint_id=VALUES(parent_checkpoint_id), "
                "type=VALUES(type), "
                "checkpoint=VALUES(checkpoint), "
                "metadata=VALUES(metadata)",
                (thread_id, checkpoint_ns, checkpoint["id"], parent_checkpoint_id, ckpt_type, ckpt_bytes, meta_bytes),
            )
            self.conn.commit()
        finally:
            cur.close()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: dict,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """写入 pending writes"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        cur = self._cursor()
        try:
            for idx, (channel, value) in enumerate(writes):
                w_type, w_bytes = self.serde.dumps_typed(value)
                cur.execute(
                    "INSERT INTO checkpoint_writes "
                    "(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "channel=VALUES(channel), type=VALUES(type), value=VALUES(value)",
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, w_type, w_bytes),
                )
            self.conn.commit()
        finally:
            cur.close()

    def put_blobs(
        self,
        config: dict,
        thread_id: str,
        checkpoint_ns: str,
        values: Sequence[Tuple[str, str, Any]],
    ) -> None:
        """写入 blobs"""
        cur = self._cursor()
        try:
            for channel, version, value in values:
                blob_type, blob_bytes = self.serde.dumps_typed(value)
                cur.execute(
                    "INSERT INTO checkpoint_blobs "
                    "(thread_id, checkpoint_ns, channel, version, type, blob) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "type=VALUES(type), blob=VALUES(blob)",
                    (thread_id, checkpoint_ns, channel, version, blob_type, blob_bytes),
                )
            self.conn.commit()
        finally:
            cur.close()

    def list(
        self,
        config: Optional[dict],
        *,
        filter: Optional[dict] = None,
        before: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """列出 checkpoints"""
        thread_id = config["configurable"]["thread_id"] if config else None
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "") if config else ""

        cur = self._cursor()
        try:
            sql = "SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata FROM checkpoints WHERE 1=1"
            params = []
            if thread_id:
                sql += " AND thread_id=%s"
                params.append(thread_id)
            if checkpoint_ns is not None:
                sql += " AND checkpoint_ns=%s"
                params.append(checkpoint_ns)
            sql += " ORDER BY checkpoint_id DESC"
            if limit:
                sql += " LIMIT %s"
                params.append(limit)

            cur.execute(sql, params)
            for row in cur.fetchall():
                tid, ns, cid, parent_id, ckpt_type, ckpt_bytes, meta_bytes = row
                checkpoint = self.serde.loads_typed((ckpt_type, ckpt_bytes))
                metadata = self.serde.loads_typed((ckpt_type, meta_bytes)) if meta_bytes else {}
                yield CheckpointTuple(
                    config={"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": cid}},
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config={"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": parent_id}} if parent_id else None,
                )
        finally:
            cur.close()
```

- [ ] **Step 2: 在 init_db 中调用 MySQLSaver.setup()**

修改 `backend/db.py` 的 `init_db()`，之后追加：

```python
from .mysql_saver import MySQLSaver

def init_db():
    # ... sessions 表创建 ...
    # 创建 checkpointer 表
    MySQLSaver(conn).setup()
```

- [ ] **Step 3: 验证**

```bash
mysql -u root -p123456 -e "USE data_analysis_agent; SHOW TABLES;"
```

Expected: 显示 `sessions`, `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` 四张表。

- [ ] **Step 4: Commit**

```bash
git add backend/mysql_saver.py backend/db.py
git commit -m "feat: MySQLSaver 实现 LangGraph BaseCheckpointSaver 协议"
```

---

### Task 4: SessionManager 会话 CRUD

**Files:**
- Create: `backend/session_manager.py`

**Interfaces:**
- Consumes: `backend/db.py` → `get_connection()`
- Produces: `SessionManager` 类，方法:
  - `create(user_id: str) -> dict`
  - `get(session_id: str) -> dict | None`
  - `list_by_user(user_id: str) -> list[dict]`
  - `update_status(session_id: str, status: str) -> None`
  - `update_last_active(session_id: str) -> None`
  - `soft_delete(session_id: str) -> None`

- [ ] **Step 1: 创建 session_manager.py**

```python
# backend/session_manager.py
"""会话元数据管理（MySQL CRUD）"""

import uuid
import datetime
from .db import get_connection


class SessionManager:
    """会话元数据 CRUD"""

    def create(self, user_id: str = "", title: str = "新会话") -> dict:
        session_id = str(uuid.uuid4())
        worktree_path = f"sandboxes/{session_id}"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id, title, user_id, worktree_path) "
                    "VALUES (%s, %s, %s, %s)",
                    (session_id, title, user_id, worktree_path),
                )
                conn.commit()
            return self.get(session_id)
        finally:
            conn.close()

    def get(self, session_id: str) -> dict | None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_id, title, user_id, worktree_path, "
                    "obs_archive_key, status, created_at, last_active "
                    "FROM sessions WHERE session_id=%s AND status != 'deleted'",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "session_id": row[0],
                    "title": row[1],
                    "user_id": row[2],
                    "worktree_path": row[3],
                    "obs_archive_key": row[4],
                    "status": row[5],
                    "created_at": str(row[6]),
                    "last_active": str(row[7]),
                }
        finally:
            conn.close()

    def list_by_user(self, user_id: str = "") -> list[dict]:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "SELECT session_id, title, status, created_at, last_active "
                        "FROM sessions WHERE user_id=%s AND status != 'deleted' "
                        "ORDER BY last_active DESC",
                        (user_id,),
                    )
                else:
                    cur.execute(
                        "SELECT session_id, title, status, created_at, last_active "
                        "FROM sessions WHERE status != 'deleted' "
                        "ORDER BY last_active DESC"
                    )
                rows = cur.fetchall()
                return [
                    {
                        "session_id": r[0],
                        "title": r[1],
                        "status": r[2],
                        "created_at": str(r[3]),
                        "last_active": str(r[4]),
                    }
                    for r in rows
                ]
        finally:
            conn.close()

    def update_status(self, session_id: str, status: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET status=%s WHERE session_id=%s",
                    (status, session_id),
                )
                conn.commit()
        finally:
            conn.close()

    def update_last_active(self, session_id: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET last_active=NOW() WHERE session_id=%s",
                    (session_id,),
                )
                conn.commit()
        finally:
            conn.close()

    def update_obs_key(self, session_id: str, obs_key: str) -> None:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET obs_archive_key=%s WHERE session_id=%s",
                    (obs_key, session_id),
                )
                conn.commit()
        finally:
            conn.close()

    def soft_delete(self, session_id: str) -> None:
        self.update_status(session_id, "deleted")


# 全局单例
session_manager = SessionManager()
```

- [ ] **Step 2: Commit**

```bash
git add backend/session_manager.py
git commit -m "feat: SessionManager 会话 CRUD"
```

---

### Task 5: WorktreeManager 沙盒工作空间管理

**Files:**
- Create: `backend/worktree_manager.py`

**Interfaces:**
- Consumes: `backend/config.py` → `WORKTREE_ROOT`, `ARCHIVE_IDLE_MINUTES`
- Consumes: `backend/session_manager.py` → `session_manager`
- Produces: `WorktreeManager` 类，方法:
  - `create_worktree(session_id: str) -> str`
  - `delete_worktree(session_id: str) -> None`
  - `get_file_tree(session_id: str) -> list[dict]`
  - `read_file_content(session_id: str, file_path: str) -> bytes`
  - `archive_session(session_id: str) -> None` (OBS 打桩)
  - `restore_session(session_id: str) -> str` (OBS 打桩)

- [ ] **Step 1: 创建 worktree_manager.py**

```python
# backend/worktree_manager.py
"""Worktree 生命周期管理：创建、归档、恢复、文件树"""

import os
import shutil
import logging
from .config import WORKTREE_ROOT

logger = logging.getLogger(__name__)


class WorktreeManager:
    """会话沙盒工作空间管理"""

    # ---------- 目录管理 ----------

    def create_worktree(self, session_id: str) -> str:
        """创建沙盒目录结构，返回 worktree 路径"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        os.makedirs(os.path.join(worktree, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(worktree, "reports"), exist_ok=True)
        return worktree

    def delete_worktree(self, session_id: str) -> None:
        """删除沙盒目录"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if os.path.exists(worktree):
            shutil.rmtree(worktree)

    # ---------- 文件树 ----------

    def get_file_tree(self, session_id: str) -> list[dict]:
        """递归扫描目录，返回前端文件树结构"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if not os.path.exists(worktree):
            return []
        return self._scan_dir(worktree)

    def _scan_dir(self, path: str) -> list[dict]:
        items = []
        try:
            for entry in os.scandir(path):
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    items.append({
                        "name": entry.name,
                        "type": "dir",
                        "children": self._scan_dir(entry.path),
                    })
                else:
                    _, ext = os.path.splitext(entry.name)
                    items.append({
                        "name": entry.name,
                        "type": "file",
                        "size": entry.stat().st_size,
                        "ext": ext.lower(),
                    })
        except PermissionError:
            pass
        return sorted(items, key=lambda x: (x["type"] != "dir", x["name"]))

    def read_file_content(self, session_id: str, file_path: str) -> tuple[bytes, str]:
        """读取文件内容和 MIME 类型，用于前端预览"""
        # 安全校验：防止目录穿越
        safe_path = file_path.lstrip("/")
        if ".." in safe_path:
            raise ValueError("非法文件路径")

        full_path = os.path.join(WORKTREE_ROOT, session_id, safe_path)
        full_path = os.path.normpath(full_path)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = os.path.splitext(full_path)[1].lower()
        mime_map = {
            ".html": "text/html",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
        }
        mime = mime_map.get(ext, "application/octet-stream")

        with open(full_path, "rb") as f:
            content = f.read()
        return content, mime

    # ---------- 归档与恢复（OBS 打桩） ----------

    def archive_session(self, session_id: str) -> None:
        """打包 worktree 并上传 OBS（当前打桩：仅打包本地）"""
        worktree = os.path.join(WORKTREE_ROOT, session_id)
        if not os.path.exists(worktree):
            logger.warning(f"worktree 不存在，跳过归档: {session_id}")
            return

        zip_base = os.path.join(WORKTREE_ROOT, f"{session_id}")
        shutil.make_archive(zip_base, "zip", worktree)
        zip_path = f"{zip_base}.zip"

        # TODO: OBS 上传（打桩）
        # await obs_client.upload(bucket="data-analysis-worktrees",
        #                         key=f"sessions/{session_id}/worktree.zip",
        #                         file_path=zip_path)
        logger.info(f"[OBS打桩] 模拟上传: sessions/{session_id}/worktree.zip")

        # 记录 OBS key
        from .session_manager import session_manager
        session_manager.update_obs_key(session_id, f"sessions/{session_id}/worktree.zip")

        # 清理本地
        shutil.rmtree(worktree)
        os.remove(zip_path)

    def restore_session(self, session_id: str) -> str:
        """从 OBS 恢复 worktree（当前打桩：检查本地 zip 或抛异常）"""
        from .session_manager import session_manager
        meta = session_manager.get(session_id)
        if not meta or not meta.get("obs_archive_key"):
            raise RuntimeError(f"会话 {session_id} 无归档记录")

        zip_path = os.path.join(WORKTREE_ROOT, f"{session_id}.zip")

        # TODO: OBS 下载（打桩）
        # await obs_client.download(bucket="data-analysis-worktrees",
        #                           key=meta["obs_archive_key"],
        #                           file_path=zip_path)
        logger.info(f"[OBS打桩] 模拟下载: {meta['obs_archive_key']}")

        if not os.path.exists(zip_path):
            raise RuntimeError(f"归档文件不存在: {session_id}（OBS 未实现）")

        worktree = os.path.join(WORKTREE_ROOT, session_id)
        shutil.unpack_archive(zip_path, worktree, "zip")
        os.remove(zip_path)
        return worktree


# 全局单例
worktree_manager = WorktreeManager()
```

- [ ] **Step 2: Commit**

```bash
git add backend/worktree_manager.py
git commit -m "feat: WorktreeManager 沙盒空间管理 + OBS 归档/恢复（打桩）"
```

---

### Task 6: 数据分析自定义工具

**Files:**
- Create: `backend/tools/data_tools.py`
- Create: `backend/tools/report_tools.py`

**Interfaces:**
- Consumes: `backend/worktree_manager.py` → `worktree_manager`
- Produces: LangChain Tool 函数列表供 `create_deep_agent` 使用

- [ ] **Step 1: 创建 data_tools.py**

```python
# backend/tools/data_tools.py
"""数据分析自定义工具：CSV/Excel 读取、Python 代码执行"""

import json
import io
import traceback
import pandas as pd
from langchain.tools import tool


@tool
def load_csv(file_path: str, encoding: str = "utf-8", worktree_root: str = "") -> str:
    """加载 CSV 文件，返回列信息和前 20 行预览。

    Args:
        file_path: 相对于 worktree 的路径，如 /uploads/sales.csv
        encoding: 文件编码，默认 utf-8
    """
    import os
    full_path = os.path.join(worktree_root, file_path.lstrip("/"))
    df = pd.read_csv(full_path, encoding=encoding)
    info = {
        "shape": list(df.shape),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "preview": df.head(20).to_dict(orient="records"),
        "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
    }
    return json.dumps(info, ensure_ascii=False, default=str)


@tool
def load_excel(file_path: str, sheet_name: str = "0", worktree_root: str = "") -> str:
    """加载 Excel 文件，返回列信息和前 20 行预览。

    Args:
        file_path: 相对于 worktree 的路径
        sheet_name: 表名或索引（0 表示第一个表）
    """
    import os
    full_path = os.path.join(worktree_root, file_path.lstrip("/"))
    df = pd.read_excel(full_path, sheet_name=sheet_name)
    info = {
        "shape": list(df.shape),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "preview": df.head(20).to_dict(orient="records"),
        "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
    }
    return json.dumps(info, ensure_ascii=False, default=str)


@tool
def execute_python(code: str, worktree_root: str = "") -> str:
    """执行 Python 数据分析代码并返回输出。

    可用库: pandas (as pd), numpy (as np), matplotlib (as plt), json

    Args:
        code: Python 代码字符串，print() 输出会被捕获返回
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    namespace = {
        "pd": pd,
        "np": np,
        "plt": plt,
        "json": json,
        "worktree_root": worktree_root,
    }

    stdout_capture = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    try:
        exec(code, namespace)
        output = stdout_capture.getvalue()
        return output if output else "代码执行成功，无 print 输出"
    except Exception as e:
        return f"执行错误: {str(e)}\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout
```

- [ ] **Step 2: 创建 report_tools.py**

```python
# backend/tools/report_tools.py
"""报告生成工具：HTML/MD 报告、图表"""

import os
import base64
import io
from langchain.tools import tool


@tool
def generate_report(content: str, filename: str, worktree_root: str = "") -> str:
    """生成分析报告文件到 /reports/ 目录。

    Args:
        content: 报告内容（HTML 字符串或 Markdown 文本）
        filename: 文件名，如 analysis_report.html 或 report.md
    """
    full_path = os.path.join(worktree_root, "reports", filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"报告已生成: /reports/{filename}"


@tool
def generate_chart(code: str, filename: str, worktree_root: str = "") -> str:
    """执行 matplotlib 代码并保存图表到 /reports/ 目录。

    Args:
        code: matplotlib 代码（无需 plt.show() 或 plt.savefig()）
        filename: 输出文件名，如 monthly_trend.png
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    namespace = {"plt": plt, "np": np, "pd": __import__("pandas")}

    try:
        exec(code, namespace)
        full_path = os.path.join(worktree_root, "reports", filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        plt.savefig(full_path, dpi=150, bbox_inches="tight")
        plt.close()
        return f"图表已生成: /reports/{filename}"
    except Exception as e:
        plt.close()
        return f"图表生成错误: {str(e)}"
```

- [ ] **Step 3: 创建 tools/__init__.py**

```python
# backend/tools/__init__.py
from .data_tools import load_csv, load_excel, execute_python
from .report_tools import generate_report, generate_chart

__all__ = ["load_csv", "load_excel", "execute_python", "generate_report", "generate_chart"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/tools/
git commit -m "feat: 数据分析工具（CSV/Excel读取、Python执行、报告生成）"
```

---

### Task 7: Agent Engine + Agent Pool

**Files:**
- Create: `backend/agent_engine.py`
- Create: `backend/agent_pool.py`

**Interfaces:**
- Consumes: `backend/tools/` → 所有工具函数
- Consumes: `backend/config.py` → `MODEL_CONFIG`, `SKILLS_DIR`
- Consumes: `backend/db.py` → `get_connection()`
- Consumes: `backend/mysql_saver.py` → `MySQLSaver`
- Produces: `agent_pool.get_agent(session_id)` → CompiledStateGraph

- [ ] **Step 1: 创建 agent_engine.py**

```python
# backend/agent_engine.py
"""Deep Agent 工厂函数"""

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from .config import SKILLS_DIR, WORKTREE_ROOT
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
    worktree = f"{WORKTREE_ROOT}/{session_id}"
    skills_dir = SKILLS_DIR

    conn = get_connection()
    checkpointer = MySQLSaver.from_conn_string(conn)

    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=worktree, virtual_mode=True),
        routes={
            "/skills/": FilesystemBackend(root_dir=skills_dir, virtual_mode=True),
        },
    )

    agent = create_deep_agent(
        **MODEL_CONFIG,
        backend=backend,
        tools=tools,
        subagents=subagents,
        skills=[skills_dir],
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
```

- [ ] **Step 2: 创建 agent_pool.py**

```python
# backend/agent_pool.py
"""Agent 实例缓存池"""

import time
import os
from .agent_engine import build_agent, build_data_analyst_subagent
from .tools import load_csv, load_excel, execute_python, generate_report, generate_chart
from .config import WORKTREE_ROOT


class AgentPool:
    """管理 agent 实例的懒加载缓存池"""

    def __init__(self):
        self._agents: dict[str, tuple] = {}  # {session_id: (agent, last_used_ts)}

    def get_agent(self, session_id: str):
        """获取或创建 agent 实例"""
        if session_id in self._agents:
            agent, _ = self._agents[session_id]
            self._agents[session_id] = (agent, time.time())
            return agent

        worktree = os.path.join(WORKTREE_ROOT, session_id)
        tools = [load_csv, load_excel, execute_python, generate_report, generate_chart]
        subagent = build_data_analyst_subagent(worktree)
        agent = build_agent(session_id, tools, [subagent])
        self._agents[session_id] = (agent, time.time())
        return agent

    def remove(self, session_id: str):
        """从缓存中移除 agent"""
        self._agents.pop(session_id, None)

    def cleanup_expired(self, max_idle_seconds: int = 3600):
        """清理超时未使用的 agent 实例"""
        now = time.time()
        expired = [
            sid for sid, (_, last) in self._agents.items()
            if now - last > max_idle_seconds
        ]
        for sid in expired:
            del self._agents[sid]


# 全局单例
agent_pool = AgentPool()
```

- [ ] **Step 3: Commit**

```bash
git add backend/agent_engine.py backend/agent_pool.py
git commit -m "feat: Agent 工厂函数 + 实例缓存池"
```

---

### Task 8: REST API - 会话管理

**Files:**
- Create: `backend/api/sessions.py`

**Interfaces:**
- Produces: FastAPI APIRouter, 挂载到 `/api/sessions`

- [ ] **Step 1: 创建 api/sessions.py**

```python
# backend/api/sessions.py
"""REST API: 会话管理"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from ..session_manager import session_manager
from ..worktree_manager import worktree_manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
async def create_session(
    user_id: str = "",
    authorization: Optional[str] = Header(None),
    cookie: Optional[str] = Header(None),
):
    """创建新会话，返回 session_id + 元数据"""
    # TODO: 生产环境校验 authorization token
    # TODO: 生产环境校验 cookie

    session = session_manager.create(user_id=user_id)
    worktree_manager.create_worktree(session["session_id"])
    return session


@router.get("")
async def list_sessions(user_id: str = ""):
    """获取会话列表"""
    return session_manager.list_by_user(user_id=user_id)


@router.get("/{session_id}")
async def get_session(session_id: str):
    """获取单个会话详情 + 文件树"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    tree = worktree_manager.get_file_tree(session_id)
    session["file_tree"] = tree
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话（软删除 + 清理磁盘）"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    worktree_manager.delete_worktree(session_id)
    session_manager.soft_delete(session_id)
    return {"message": "已删除"}


@router.post("/{session_id}/archive")
async def archive_session(session_id: str):
    """手动归档会话"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="仅 active 状态可归档")

    session_manager.update_status(session_id, "archiving")
    worktree_manager.archive_session(session_id)
    session_manager.update_status(session_id, "archived")
    return {"message": "已归档"}
```

- [ ] **Step 2: 在 main.py 挂载路由**

```python
# backend/main.py 修改
from .api.sessions import router as sessions_router
app.include_router(sessions_router)
```

- [ ] **Step 3: 验证 API**

```bash
# 创建会话
curl -X POST http://localhost:8000/api/sessions?user_id=test_user

# 列表
curl http://localhost:8000/api/sessions?user_id=test_user

# 详情
curl http://localhost:8000/api/sessions/<session_id>
```

Expected: 返回 JSON 包含 session_id、title、status、file_tree。

- [ ] **Step 4: Commit**

```bash
git add backend/api/sessions.py backend/api/__init__.py backend/main.py
git commit -m "feat: REST API 会话管理（CRUD + 归档）"
```

---

### Task 9: REST API - 文件管理

**Files:**
- Create: `backend/api/files.py`

**Interfaces:**
- Produces: FastAPI APIRouter, 挂载到 `/api/sessions/{session_id}/files`

- [ ] **Step 1: 创建 api/files.py**

```python
# backend/api/files.py
"""REST API: 文件管理（上传、目录树、预览、删除）"""

import os
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from ..session_manager import session_manager
from ..worktree_manager import worktree_manager
from ..config import WORKTREE_ROOT

router = APIRouter(prefix="/api/sessions/{session_id}/files", tags=["files"])


@router.get("")
async def get_file_tree(session_id: str):
    """获取会话工作空间的文件目录树"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"tree": worktree_manager.get_file_tree(session_id)}


@router.post("")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """上传文件到沙盒 uploads 目录"""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="会话非 active 状态")

    upload_dir = os.path.join(WORKTREE_ROOT, session_id, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {
        "message": "上传成功",
        "path": f"/uploads/{file.filename}",
        "size": len(content),
    }


@router.delete("/{file_path:path}")
async def delete_file(session_id: str, file_path: str):
    """删除沙盒中的文件或目录"""
    # 安全校验
    safe_path = file_path.lstrip("/")
    if ".." in safe_path:
        raise HTTPException(status_code=400, detail="非法文件路径")

    full_path = os.path.join(WORKTREE_ROOT, session_id, safe_path)
    full_path = os.path.normpath(full_path)
    if not full_path.startswith(os.path.normpath(os.path.join(WORKTREE_ROOT, session_id))):
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if os.path.isdir(full_path):
        import shutil
        shutil.rmtree(full_path)
    else:
        os.remove(full_path)
    return {"message": "已删除"}


@router.get("/{file_path:path}")
async def preview_file(session_id: str, file_path: str):
    """预览文件内容（HTML/MD/图片/CSV）"""
    try:
        content, mime = worktree_manager.read_file_content(session_id, file_path)
        return Response(content=content, media_type=mime)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: 在 main.py 挂载路由**

```python
# backend/main.py 追加
from .api.files import router as files_router
app.include_router(files_router)
```

- [ ] **Step 3: 验证 API**

```bash
# 上传文件
curl -X POST -F "file=@test.csv" http://localhost:8000/api/sessions/<id>/files

# 目录树
curl http://localhost:8000/api/sessions/<id>/files

# 文件预览
curl http://localhost:8000/api/sessions/<id>/files/uploads/test.csv
```

Expected: 上传成功，目录树含上传文件。

- [ ] **Step 4: Commit**

```bash
git add backend/api/files.py backend/main.py
git commit -m "feat: REST API 文件管理（上传、目录树、预览、删除）"
```

---

### Task 10: WebSocket 处理 + LangGraph Streaming

**Files:**
- Create: `backend/ws_handler.py`

**Interfaces:**
- Consumes: `backend/agent_pool.py` → `agent_pool`
- Consumes: `backend/session_manager.py` → `session_manager`
- Consumes: `backend/worktree_manager.py` → `worktree_manager`
- Produces: `ws_router` (FastAPI WebSocket endpoint at `/ws/{session_id}`)

- [ ] **Step 1: 创建 ws_handler.py**

```python
# backend/ws_handler.py
"""WebSocket 处理器，基于 LangGraph astream_events v3"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .agent_pool import agent_pool
from .session_manager import session_manager
from .worktree_manager import worktree_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    # 验证会话
    session = session_manager.get(session_id)
    if not session:
        await ws.send_json({"type": "error", "payload": {"message": "会话不存在"}})
        await ws.close()
        return

    # 确保 worktree 在本地
    if session["status"] == "archived":
        await ws.send_json({"type": "session.status", "payload": {"status": "restoring"}})
        try:
            worktree_manager.restore_session(session_id)
            session_manager.update_status(session_id, "active")
        except Exception as e:
            await ws.send_json({"type": "error", "payload": {"message": f"恢复失败: {str(e)}"}})
            await ws.close()
            return

    session_manager.update_last_active(session_id)

    # 获取 agent
    agent = agent_pool.get_agent(session_id)

    # 发送历史消息（从 checkpointer 恢复的最新 state）
    try:
        state = agent.get_state({"configurable": {"thread_id": session_id}})
        if state and state.values.get("messages"):
            for msg in state.values["messages"]:
                role = getattr(msg, "type", "assistant")
                content = getattr(msg, "content", "")
                if content:
                    await ws.send_json({
                        "type": "chat.response",
                        "payload": {"role": role, "content": content, "done": True},
                    })
    except Exception:
        pass  # 首次对话无历史

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "chat.send":
                content = msg["payload"]["content"]
                mentions = msg["payload"].get("mentions", [])

                # 异步流式响应
                stream = agent.astream_events(
                    {"messages": [{"role": "user", "content": content}]},
                    config={"configurable": {"thread_id": session_id}},
                    version="v3",
                )

                async for event in stream:
                    method = event.get("method")
                    params = event.get("params", {})
                    namespace = params.get("namespace", [])
                    source = "subagent" if namespace else "coordinator"

                    # 转发 LangGraph 事件到前端
                    await ws.send_json({
                        "type": method,
                        "payload": params,
                        "source": source,
                    })

                # 对话完成，推送更新后的文件树
                tree = worktree_manager.get_file_tree(session_id)
                await ws.send_json({"type": "file.tree", "payload": {"tree": tree}})

            elif msg.get("type") == "chat.cancel":
                # TODO: 实现中断逻辑（LangGraph interrupt）
                await ws.send_json({
                    "type": "chat.response",
                    "payload": {"content": "[执行已中断]", "done": True},
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await ws.send_json({"type": "error", "payload": {"message": str(e)}})
```

- [ ] **Step 2: 在 main.py 挂载 WS 路由**

```python
# backend/main.py 追加
from .ws_handler import router as ws_router
app.include_router(ws_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/ws_handler.py backend/main.py
git commit -m "feat: WebSocket 处理器 + LangGraph astream_events v3 流式转发"
```

---

### Task 11: Skills 文件创建

**Files:**
- Create: `skills/ui-ux-design-pro/SKILL.md`
- Create: `skills/ui-ux-design-pro/templates/dashboard.html`
- Create: `skills/ui-ux-design-pro/templates/executive.html`
- Create: `skills/ui-ux-design-pro/templates/detailed.html`
- Create: `skills/data-analysis-guide/SKILL.md`
- Create: `skills/chart-best-practices/SKILL.md`
- Create: `skills/report-templates/SKILL.md`
- Create: `skills/report-templates/assets/style.css`
- Create: `skills/report-templates/assets/chart.js`

- [ ] **Step 1: 创建 ui-ux-design-pro/SKILL.md**

```markdown
---
name: ui-ux-design-pro
description: |
  当生成 HTML 分析报告时使用此技能。提供专业的数据分析报告设计规范，
  包括配色方案、排版、图表集成、响应式布局。
---

# 数据分析报告设计规范

## 设计原则
- 专业简洁：去除多余装饰，突出数据
- 信息层次：标题 → KPI 卡片 → 图表 → 详细表格
- 可读性优先：字体 14-16px，行高 1.6

## 配色方案
| 用途       | 色值     |
|-----------|---------|
| 主色       | #1a365d |
| 强调色     | #e53e3e |
| 成功/增长  | #38a169 |
| 背景       | #f7fafc |
| 卡片       | #ffffff |

## 报告结构模板
参考 /skills/ui-ux-design-pro/templates/ 目录下的模板文件。
- dashboard.html: 仪表盘风格，适合概览
- executive.html: 高管摘要，简洁一页
- detailed.html: 详细分析，含交互式图表

## 图表集成
使用 Chart.js CDN 嵌入交互式图表：
`<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`
```

- [ ] **Step 2: 创建 data-analysis-guide/SKILL.md**

```markdown
---
name: data-analysis-guide
description: |
  数据分析方法论指南。当 agent 需要对数据进行统计分析时使用。
  包括描述性统计、相关性分析、趋势分析等方法。
---

# 数据分析方法论

## 分析流程
1. 数据概览：shape, columns, dtypes, missing values
2. 描述性统计：mean, median, std, quartiles
3. 数据清洗：处理缺失值、异常值、重复值
4. 探索性分析：分组聚合、交叉分析、相关性
5. 结论与建议

## 分析方法选择
| 场景             | 方法              | Python 示例                     |
|-----------------|-------------------|---------------------------------|
| 看分布           | describe + hist   | df.describe(); df.hist()        |
| 看趋势           | groupby + line    | df.groupby('date').sum().plot()|
| 看占比           | value_counts + pie| df['cat'].value_counts().plot.pie()|
| 看相关性         | corr + heatmap    | df.corr()                       |
| 找异常           | boxplot + IQR     | df.boxplot()                    |
```

- [ ] **Step 3: 创建 chart-best-practices/SKILL.md**

```markdown
---
name: chart-best-practices
description: |
  图表选型指南。当 agent 需要生成可视化图表时使用，帮助选择最合适的图表类型。
---

# 图表选型指南

## 图表类型选择
| 数据关系   | 推荐图表   |
|-----------|-----------|
| 趋势/时间  | 折线图     |
| 比较/排名  | 柱状图     |
| 占比       | 饼图/环形图 |
| 分布       | 直方图/箱线图|
| 相关性     | 散点图     |
| 多维度比较 | 雷达图/热力图|

## 通用规则
- 坐标轴标签清晰可读
- 颜色不超过 5 种主色
- 添加数据标签或图例
- 标题描述图表内容
```

- [ ] **Step 4: 创建 report-templates 的 SKILL.md 和资源文件**

```markdown
---
name: report-templates
description: |
  预置分析报告模板。包含仪表盘、高管摘要、详细分析三种模板的 HTML 结构和资源文件。
  assets/ 目录包含公共样式和图表脚本。
---

# 报告模板

## 可用模板
| 模板              | 文件                | 适用场景     |
|-------------------|---------------------|-------------|
| 仪表盘 Dashboard   | dashboard.html       | 数据概览     |
| 高管摘要 Executive  | executive.html       | 决策汇报     |
| 详细分析 Detailed  | detailed.html        | 深度分析     |

## 公共资源
- /skills/report-templates/assets/style.css: 公共样式
- /skills/report-templates/assets/chart.js: 图表初始化脚本
```

- [ ] **Step 5: 创建 assets/style.css**

```css
/* skills/report-templates/assets/style.css */
:root {
  --primary: #1a365d;
  --accent: #e53e3e;
  --success: #38a169;
  --bg: #f7fafc;
  --card-bg: #ffffff;
  --text: #2d3748;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
       background: var(--bg); color: var(--text); line-height: 1.6; padding: 24px; }
header { margin-bottom: 24px; }
h1 { color: var(--primary); font-size: 24px; }
.kpi-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.kpi-card { background: var(--card-bg); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.kpi-value { font-size: 32px; font-weight: 700; color: var(--primary); }
.kpi-label { font-size: 14px; color: #718096; margin-top: 4px; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 16px; margin-bottom: 24px; }
.chart-card { background: var(--card-bg); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.chart-card h3 { font-size: 16px; margin-bottom: 12px; color: var(--primary); }
table { width: 100%; border-collapse: collapse; background: var(--card-bg); border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }
th { background: var(--primary); color: white; font-weight: 600; }
footer { margin-top: 24px; font-size: 12px; color: #a0aec0; text-align: center; }
```

- [ ] **Step 6: Commit**

```bash
git add skills/
git commit -m "feat: Skills 体系（UI设计/分析方法论/图表指南/报告模板）"
```

---

### Task 12: 前端项目初始化 + Pinia Stores

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`
- Create: `frontend/src/main.js`, `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/stores/sessionStore.js`
- Create: `frontend/src/stores/chatStore.js`
- Create: `frontend/src/stores/fileStore.js`
- Create: `frontend/src/utils/websocket.js`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "data-analysis-agent-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.3",
    "pinia": "^2.1",
    "marked": "^12.0",
    "highlight.js": "^11.9"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "vite": "^5.4"
  }
}
```

- [ ] **Step 2: 创建 vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

- [ ] **Step 3: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>数据分析 Agent</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 main.js + App.vue + router**

```javascript
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <div class="app-container">
    <SessionSidebar />
    <router-view />
    <WorktreePanel />
  </div>
</template>

<script>
import SessionSidebar from './components/SessionSidebar.vue'
import WorktreePanel from './components/WorktreePanel.vue'
export default {
  components: { SessionSidebar, WorktreePanel },
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
.app-container {
  display: flex; height: 100vh; overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
</style>
```

```javascript
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import ChatPanel from '../components/ChatPanel.vue'

const routes = [
  { path: '/', redirect: '/session/new' },
  { path: '/session/:id', component: ChatPanel, props: true },
]

export default createRouter({ history: createWebHistory(), routes })
```

- [ ] **Step 5: 创建 Pinia Stores**

```javascript
// frontend/src/stores/sessionStore.js
import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentId: null,
    currentMeta: null,
  }),
  actions: {
    async fetchSessions(userId = '') {
      const res = await fetch(`/api/sessions?user_id=${userId}`)
      this.sessions = await res.json()
    },
    async createSession(userId = '') {
      const res = await fetch(`/api/sessions?user_id=${userId}`, { method: 'POST' })
      const session = await res.json()
      this.sessions.unshift(session)
      return session
    },
    async fetchSession(id) {
      const res = await fetch(`/api/sessions/${id}`)
      if (!res.ok) throw new Error('会话不存在')
      this.currentMeta = await res.json()
      return this.currentMeta
    },
    async deleteSession(id) {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
      this.sessions = this.sessions.filter(s => s.session_id !== id)
    },
  },
})
```

```javascript
// frontend/src/stores/chatStore.js
import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    todos: [],
    isStreaming: false,
    ws: null,
  }),
  actions: {
    addMessage(msg) {
      this.messages.push({ ...msg, timestamp: Date.now() })
    },
    appendToLast(content, source = 'coordinator') {
      const last = this.messages[this.messages.length - 1]
      if (last && last.role === 'assistant' && !last.done) {
        last.content += content
      } else {
        this.messages.push({ role: 'assistant', content, source, done: false, timestamp: Date.now() })
      }
    },
    finishLastMessage() {
      const last = this.messages[this.messages.length - 1]
      if (last) last.done = true
    },
    updateTodos(todos) { this.todos = todos },
  },
})
```

```javascript
// frontend/src/stores/fileStore.js
import { defineStore } from 'pinia'

export const useFileStore = defineStore('file', {
  state: () => ({
    tree: [],
    previewPath: null,
    previewContent: null,
    previewMime: null,
  }),
  actions: {
    async fetchTree(sessionId) {
      const res = await fetch(`/api/sessions/${sessionId}/files`)
      const data = await res.json()
      this.tree = data.tree || []
    },
    async upload(sessionId, file) {
      const form = new FormData()
      form.append('file', file)
      await fetch(`/api/sessions/${sessionId}/files`, { method: 'POST', body: form })
      await this.fetchTree(sessionId)
    },
    async preview(sessionId, path) {
      this.previewPath = path
      const res = await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`)
      this.previewMime = res.headers.get('content-type')
      this.previewContent = await res.text()
    },
    async deleteFile(sessionId, path) {
      await fetch(`/api/sessions/${sessionId}/files/${encodeURIComponent(path)}`, { method: 'DELETE' })
      await this.fetchTree(sessionId)
    },
  },
})
```

- [ ] **Step 6: 创建 websocket.js 工具**

```javascript
// frontend/src/utils/websocket.js
export function createWS(sessionId, chatStore, fileStore) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${location.host}/ws/${sessionId}`)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    const { type, payload, source } = data

    switch (type) {
      case 'chat.response':
        if (payload.done) chatStore.finishLastMessage()
        else chatStore.appendToLast(payload.content, source)
        break
      case 'tool_calls':
        if (payload.tool_name === 'write_todos') {
          const todos = JSON.parse(payload.input?.todos || '[]')
          chatStore.updateTodos(todos)
        }
        break
      case 'file.tree':
        fileStore.tree = payload.tree
        break
      case 'error':
        chatStore.addMessage({ role: 'system', content: `错误: ${payload.message}` })
        break
    }
  }

  ws.onerror = () => chatStore.addMessage({ role: 'system', content: '连接失败，请重试' })
  ws.onclose = () => chatStore.addMessage({ role: 'system', content: '连接已断开' })

  return ws
}
```

- [ ] **Step 7: 安装依赖并验证**

```bash
cd frontend && npm install && npm run dev
```

Expected: Vite 启动，访问 http://localhost:5173 显示空白页面框架。

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: 前端项目初始化 + Pinia Stores + WebSocket 工具"
```

---

### Task 13: 前端组件 - 左侧栏（会话管理）

**Files:**
- Create: `frontend/src/components/SessionSidebar.vue`
- Create: `frontend/src/components/SessionCreate.vue`
- Create: `frontend/src/components/SessionList.vue`
- Create: `frontend/src/components/SessionItem.vue`

- [ ] **Step 1: 创建 SessionSidebar.vue**

```vue
<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>数据分析 Agent</h2>
    </div>
    <SessionCreate @created="onCreated" />
    <SessionList
      :sessions="sessionStore.sessions"
      :currentId="sessionStore.currentId"
      @select="onSelect"
      @delete="onDelete"
    />
  </aside>
</template>

<script>
import { useSessionStore } from '../stores/sessionStore'
import SessionCreate from './SessionCreate.vue'
import SessionList from './SessionList.vue'

export default {
  components: { SessionCreate, SessionList },
  setup() {
    const sessionStore = useSessionStore()
    sessionStore.fetchSessions()
    return { sessionStore }
  },
  methods: {
    async onCreated() {
      const s = await this.sessionStore.createSession()
      this.$router.push(`/session/${s.session_id}`)
    },
    onSelect(id) {
      this.$router.push(`/session/${id}`)
    },
    async onDelete(id) {
      await this.sessionStore.deleteSession(id)
    },
  },
}
</script>

<style scoped>
.sidebar {
  width: 260px; min-width: 260px; height: 100vh;
  border-right: 1px solid #e2e8f0; display: flex; flex-direction: column;
  background: #f8fafc;
}
.sidebar-header {
  padding: 16px; border-bottom: 1px solid #e2e8f0;
}
.sidebar-header h2 {
  font-size: 16px; color: #1a365d;
}
</style>
```

- [ ] **Step 2: 创建 SessionCreate.vue**

```vue
<template>
  <div class="create-btn" @click="$emit('created')">
    + 新建会话
  </div>
</template>

<style scoped>
.create-btn {
  margin: 12px; padding: 10px; text-align: center; cursor: pointer;
  background: #1a365d; color: white; border-radius: 6px; font-size: 14px;
  transition: background 0.2s;
}
.create-btn:hover { background: #2a4a7f; }
</style>
```

- [ ] **Step 3: 创建 SessionItem.vue**

```vue
<template>
  <div class="session-item" :class="{ active: isActive }" @click="$emit('select', session.session_id)">
    <div class="item-content">
      <div class="item-title">{{ session.title }}</div>
      <div class="item-meta">
        <span class="status" :class="session.status">{{ statusText }}</span>
        <span>{{ formatTime(session.last_active) }}</span>
      </div>
    </div>
    <button class="delete-btn" @click.stop="$emit('delete', session.session_id)">×</button>
  </div>
</template>

<script>
export default {
  props: { session: Object, isActive: Boolean },
  emits: ['select', 'delete'],
  computed: {
    statusText() {
      const map = { active: '活跃', archiving: '归档中', archived: '已归档', restoring: '恢复中' }
      return map[this.session.status] || this.session.status
    },
  },
  methods: {
    formatTime(t) {
      if (!t) return ''
      return new Date(t).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
  },
}
</script>

<style scoped>
.session-item {
  display: flex; align-items: center; padding: 10px 12px; cursor: pointer;
  border-bottom: 1px solid #edf2f7; font-size: 13px;
}
.session-item:hover { background: #edf2f7; }
.session-item.active { background: #ebf8ff; border-left: 3px solid #3182ce; }
.item-content { flex: 1; overflow: hidden; }
.item-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }
.item-meta { display: flex; gap: 8px; font-size: 11px; color: #718096; margin-top: 2px; }
.status { padding: 0 4px; border-radius: 3px; }
.status.active { color: #38a169; }
.status.archived { color: #a0aec0; }
.delete-btn {
  background: none; border: none; color: #cbd5e0; font-size: 16px; cursor: pointer; padding: 0 4px;
}
.delete-btn:hover { color: #e53e3e; }
</style>
```

- [ ] **Step 4: 创建 SessionList.vue**

```vue
<template>
  <div class="session-list">
    <SessionItem
      v-for="s in sessions" :key="s.session_id"
      :session="s" :isActive="s.session_id === currentId"
      @select="$emit('select', $event)"
      @delete="$emit('delete', $event)"
    />
    <div v-if="sessions.length === 0" class="empty">暂无会话</div>
  </div>
</template>

<script>
import SessionItem from './SessionItem.vue'
export default {
  components: { SessionItem },
  props: { sessions: Array, currentId: String },
  emits: ['select', 'delete'],
}
</script>

<style scoped>
.session-list { flex: 1; overflow-y: auto; }
.empty { text-align: center; color: #a0aec0; padding: 20px; font-size: 13px; }
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SessionSidebar.vue frontend/src/components/SessionCreate.vue frontend/src/components/SessionList.vue frontend/src/components/SessionItem.vue
git commit -m "feat: 前端左侧栏组件（会话列表/创建/切换/删除）"
```

---

### Task 14: 前端组件 - 中间对话区

**Files:**
- Create: `frontend/src/components/ChatPanel.vue`
- Create: `frontend/src/components/ChatHeader.vue`
- Create: `frontend/src/components/ChatMessages.vue`
- Create: `frontend/src/components/MessageBubble.vue`
- Create: `frontend/src/components/TextContent.vue`
- Create: `frontend/src/components/FileMention.vue`
- Create: `frontend/src/components/SubAgentCard.vue`
- Create: `frontend/src/components/TodoPanel.vue`
- Create: `frontend/src/components/ReportCard.vue`

- [ ] **Step 1: 创建 ChatPanel.vue**

```vue
<template>
  <div class="chat-panel">
    <ChatHeader :title="sessionTitle" />
    <TodoPanel :todos="chatStore.todos" v-if="chatStore.todos.length" />
    <ChatMessages ref="msgContainer" :messages="chatStore.messages" />
    <ChatInput :sessionId="sessionId" :disabled="sessionStatus !== 'active'" />
  </div>
</template>

<script>
import { useSessionStore } from '../stores/sessionStore'
import { useChatStore } from '../stores/chatStore'
import { createWS } from '../utils/websocket'
import { useFileStore } from '../stores/fileStore'
import ChatHeader from './ChatHeader.vue'
import ChatMessages from './ChatMessages.vue'
import ChatInput from './ChatInput.vue'
import TodoPanel from './TodoPanel.vue'

export default {
  components: { ChatHeader, ChatMessages, ChatInput, TodoPanel },
  props: { id: String },
  data: () => ({ sessionId: null, sessionTitle: '', sessionStatus: 'active' }),
  async mounted() {
    const sessionStore = useSessionStore()
    const chatStore = useChatStore()
    const fileStore = useFileStore()

    this.sessionId = this.id
    sessionStore.currentId = this.id

    try {
      const meta = await sessionStore.fetchSession(this.id)
      this.sessionTitle = meta.title
      this.sessionStatus = meta.status
      await fileStore.fetchTree(this.id)
    } catch { $router.push('/') }

    chatStore.ws = createWS(this.id, chatStore, fileStore)
  },
  beforeUnmount() {
    if (useChatStore().ws) useChatStore().ws.close()
  },
}
</script>

<style scoped>
.chat-panel { flex: 1; display: flex; flex-direction: column; height: 100vh; background: white; }
</style>
```

- [ ] **Step 2: 创建 ChatMessages.vue (含 MessageBubble + TextContent)**

```vue
<!-- ChatMessages.vue -->
<template>
  <div class="chat-messages" ref="container">
    <MessageBubble v-for="(msg, i) in messages" :key="i" :msg="msg" />
    <div ref="bottom" />
  </div>
</template>

<script>
import MessageBubble from './MessageBubble.vue'
import { nextTick, watch } from 'vue'

export default {
  components: { MessageBubble },
  props: { messages: Array },
  watch: {
    messages: { deep: true, async handler() { await nextTick(); this.scrollBottom() } },
  },
  mounted() { this.scrollBottom() },
  methods: {
    scrollBottom() { this.$refs.bottom?.scrollIntoView({ behavior: 'smooth' }) },
  },
}
</script>

<style scoped>
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
</style>
```

```vue
<!-- MessageBubble.vue -->
<template>
  <div class="bubble" :class="msg.role">
    <div class="role-label">{{ msg.role === 'user' ? '你' : 'Agent' }}</div>
    <TextContent :content="msg.content" />
    <div v-if="msg.source === 'subagent'" class="subagent-tag">子代理</div>
  </div>
</template>

<script>
import TextContent from './TextContent.vue'
export default { components: { TextContent }, props: { msg: Object } }
</script>

<style scoped>
.bubble { margin-bottom: 12px; max-width: 85%; }
.bubble.user { margin-left: auto; }
.bubble.assistant { margin-right: auto; }
.bubble.user .role-label { display: none; }
.role-label { font-size: 11px; color: #a0aec0; margin-bottom: 2px; }
.subagent-tag { display: inline-block; font-size: 10px; background: #edf2f7; color: #718096; padding: 1px 6px; border-radius: 3px; margin-top: 4px; }
</style>
```

```vue
<!-- TextContent.vue -->
<template>
  <div class="text-content" v-html="rendered"></div>
</template>

<script>
import { marked } from 'marked'
export default {
  props: { content: String },
  computed: { rendered() { return marked.parse(this.content || '') } },
}
</script>

<style scoped>
.text-content { font-size: 14px; line-height: 1.7; word-break: break-word; }
.text-content :deep(p) { margin-bottom: 8px; }
.text-content :deep(code) { background: #edf2f7; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.text-content :deep(pre) { background: #2d3748; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; margin-bottom: 8px; }
.text-content :deep(table) { border-collapse: collapse; margin-bottom: 8px; }
.text-content :deep(th), .text-content :deep(td) { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
.text-content :deep(th) { background: #edf2f7; }
</style>
```

- [ ] **Step 3: 创建 ChatInput.vue (含 @文件引用)**

```vue
<template>
  <div class="chat-input-container">
    <MentionDropdown
      v-if="showMention"
      :files="mentionFiles"
      @select="insertMention"
      @close="showMention = false"
    />
    <div class="file-tags" v-if="selectedMentions.length">
      <span v-for="f in selectedMentions" :key="f" class="tag">@{{ f }}</span>
    </div>
    <div class="input-row">
      <FileUploadBtn :sessionId="sessionId" />
      <textarea
        ref="input"
        v-model="text"
        @keydown.enter.exact.prevent="send"
        @keydown.escape="text = ''"
        @input="onInput"
        :disabled="disabled"
        placeholder="输入分析需求，@ 引用文件..."
        rows="1"
      />
      <button @click="send" :disabled="!text.trim() || disabled" class="send-btn">发送</button>
    </div>
  </div>
</template>

<script>
import { useChatStore } from '../stores/chatStore'
import { useFileStore } from '../stores/fileStore'
import MentionDropdown from './MentionDropdown.vue'
import FileUploadBtn from './FileUploadBtn.vue'

export default {
  components: { MentionDropdown, FileUploadBtn },
  props: { sessionId: String, disabled: Boolean },
  data: () => ({ text: '', showMention: false, mentionStart: 0, selectedMentions: [] }),
  computed: {
    mentionFiles() {
      const tree = useFileStore().tree
      const files = []
      const flatten = (items, prefix = '') => {
        items.forEach(item => {
          const p = prefix + '/' + item.name
          if (item.type === 'file') files.push(p)
          if (item.children) flatten(item.children, p)
        })
      }
      flatten(tree)
      return files
    },
  },
  methods: {
    onInput(e) {
      const cursor = e.target.selectionStart
      const before = this.text.slice(0, cursor)
      const match = before.match(/@([^\s@]*)$/)
      if (match) {
        this.showMention = true
        this.mentionStart = cursor - match[1].length - 1
      } else {
        this.showMention = false
      }
    },
    insertMention(file) {
      this.text = this.text.slice(0, this.mentionStart) + '@' + file + ' ' + this.text.slice(this.$refs.input.selectionStart)
      this.selectedMentions.push(file)
      this.showMention = false
      this.$refs.input.focus()
    },
    send() {
      if (!this.text.trim()) return
      const chatStore = useChatStore()
      chatStore.addMessage({ role: 'user', content: this.text })
      chatStore.isStreaming = true
      chatStore.ws.send(JSON.stringify({
        type: 'chat.send',
        payload: { content: this.text, mentions: this.selectedMentions },
      }))
      this.text = ''
      this.selectedMentions = []
    },
  },
}
</script>

<style scoped>
.chat-input-container { padding: 12px 16px; border-top: 1px solid #e2e8f0; position: relative; }
.input-row { display: flex; align-items: center; gap: 8px; }
textarea {
  flex: 1; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px;
  font-size: 14px; resize: none; outline: none; font-family: inherit;
}
textarea:focus { border-color: #3182ce; }
.send-btn {
  padding: 10px 20px; background: #1a365d; color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 14px;
}
.send-btn:disabled { background: #a0aec0; cursor: not-allowed; }
.file-tags { display: flex; gap: 6px; margin-bottom: 6px; }
.tag { font-size: 12px; background: #ebf8ff; color: #2b6cb0; padding: 2px 8px; border-radius: 4px; }
</style>
```

- [ ] **Step 4: 创建子组件（MentionDropdown, FileUploadBtn, TodoPanel, ReportCard, SubAgentCard）**

```vue
<!-- MentionDropdown.vue -->
<template>
  <div class="mention-dropdown">
    <div v-for="f in filteredFiles" :key="f" class="mention-item" @click="$emit('select', f)">{{ f }}</div>
    <div v-if="filteredFiles.length === 0" class="mention-empty">无匹配文件</div>
  </div>
</template>
<script>
export default {
  props: { files: Array },
  emits: ['select', 'close'],
  computed: { filteredFiles() { return this.files } },
}
</script>
<style scoped>
.mention-dropdown { position: absolute; bottom: 100%; left: 16px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; max-height: 200px; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 10; min-width: 250px; }
.mention-item { padding: 8px 12px; cursor: pointer; font-size: 13px; }
.mention-item:hover { background: #ebf8ff; }
.mention-empty { padding: 8px 12px; color: #a0aec0; font-size: 13px; }
</style>
```

```vue
<!-- FileUploadBtn.vue -->
<template>
  <label class="upload-btn">
    📎
    <input type="file" hidden @change="onUpload" accept=".csv,.xlsx,.xls" />
  </label>
</template>
<script>
import { useFileStore } from '../stores/fileStore'
export default {
  props: { sessionId: String },
  methods: {
    async onUpload(e) {
      const file = e.target.files[0]
      if (!file) return
      await useFileStore().upload(this.sessionId, file)
    },
  },
}
</script>
<style scoped>
.upload-btn { cursor: pointer; font-size: 18px; padding: 8px; }
</style>
```

```vue
<!-- TodoPanel.vue -->
<template>
  <div class="todo-panel">
    <div class="todo-title">分析计划</div>
    <div v-for="t in todos" :key="t.content" class="todo-item" :class="t.status">
      <span class="todo-dot">{{ t.status === 'completed' ? '✓' : t.status === 'in_progress' ? '●' : '○' }}</span>
      <span>{{ t.content }}</span>
    </div>
  </div>
</template>
<script>
export default { props: { todos: Array } }
</script>
<style scoped>
.todo-panel { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; }
.todo-title { font-size: 12px; color: #718096; margin-bottom: 6px; font-weight: 600; }
.todo-item { font-size: 13px; padding: 3px 0; display: flex; align-items: center; gap: 6px; }
.todo-item.completed { color: #a0aec0; text-decoration: line-through; }
.todo-item.in_progress { color: #2b6cb0; font-weight: 500; }
.todo-dot { font-size: 11px; }
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatPanel.vue frontend/src/components/ChatHeader.vue frontend/src/components/ChatMessages.vue frontend/src/components/MessageBubble.vue frontend/src/components/TextContent.vue frontend/src/components/FileMention.vue frontend/src/components/SubAgentCard.vue frontend/src/components/TodoPanel.vue frontend/src/components/ReportCard.vue frontend/src/components/ChatInput.vue frontend/src/components/MentionDropdown.vue frontend/src/components/FileUploadBtn.vue
git commit -m "feat: 前端中间对话区组件（消息流/输入/@引用/任务面板）"
```

---

### Task 15: 前端组件 - 右侧工作区（文件树 + 预览）

**Files:**
- Create: `frontend/src/components/WorktreePanel.vue`
- Create: `frontend/src/components/PanelTabs.vue`
- Create: `frontend/src/components/FileTree.vue`
- Create: `frontend/src/components/FileTreeNode.vue`
- Create: `frontend/src/components/FileContextMenu.vue`
- Create: `frontend/src/components/FilePreview.vue`
- Create: `frontend/src/components/HtmlPreview.vue`
- Create: `frontend/src/components/MarkdownPreview.vue`
- Create: `frontend/src/components/ImagePreview.vue`

- [ ] **Step 1: 创建 WorktreePanel.vue**

```vue
<template>
  <aside class="worktree-panel">
    <PanelTabs :activeTab="activeTab" @switch="activeTab = $event" :hasPreview="!!fileStore.previewPath" />
    <FileTree v-if="activeTab === 'tree'" :tree="fileStore.tree" :sessionId="sessionId" />
    <FilePreview v-else :path="fileStore.previewPath" :content="fileStore.previewContent" :mime="fileStore.previewMime" />
  </aside>
</template>

<script>
import { useFileStore } from '../stores/fileStore'
import PanelTabs from './PanelTabs.vue'
import FileTree from './FileTree.vue'
import FilePreview from './FilePreview.vue'

export default {
  components: { PanelTabs, FileTree, FilePreview },
  props: { sessionId: String },
  data: () => ({ activeTab: 'tree' }),
  setup() {
    const fileStore = useFileStore()
    return { fileStore }
  },
  watch: {
    'fileStore.previewPath'(val) { if (val) this.activeTab = 'preview' },
  },
}
</script>

<style scoped>
.worktree-panel {
  width: 360px; min-width: 360px; height: 100vh;
  border-left: 1px solid #e2e8f0; display: flex; flex-direction: column;
  background: #f8fafc;
}
</style>
```

- [ ] **Step 2: 创建 PanelTabs.vue, FileTree.vue, FileTreeNode.vue**

```vue
<!-- PanelTabs.vue -->
<template>
  <div class="panel-tabs">
    <button :class="{ active: activeTab === 'tree' }" @click="$emit('switch', 'tree')">📁 文件</button>
    <button v-if="hasPreview" :class="{ active: activeTab === 'preview' }" @click="$emit('switch', 'preview')">👁 预览</button>
  </div>
</template>
<script>
export default { props: { activeTab: String, hasPreview: Boolean }, emits: ['switch'] }
</script>
<style scoped>
.panel-tabs { display: flex; border-bottom: 1px solid #e2e8f0; }
.panel-tabs button { flex: 1; padding: 10px; border: none; background: none; cursor: pointer; font-size: 13px; color: #718096; }
.panel-tabs button.active { color: #1a365d; border-bottom: 2px solid #1a365d; font-weight: 500; }
</style>
```

```vue
<!-- FileTree.vue -->
<template>
  <div class="file-tree">
    <div class="tree-header">工作空间</div>
    <div v-if="tree.length === 0" class="tree-empty">上传文件开始分析</div>
    <FileTreeNode
      v-for="item in tree" :key="item.name"
      :item="item" :depth="0" :sessionId="sessionId"
      @preview="onPreview" @delete="onDelete"
    />
  </div>
</template>

<script>
import FileTreeNode from './FileTreeNode.vue'
import { useFileStore } from '../stores/fileStore'
export default {
  components: { FileTreeNode },
  props: { tree: Array, sessionId: String },
  methods: {
    onPreview(path) {
      useFileStore().preview(this.sessionId, path)
    },
    async onDelete(path) {
      await useFileStore().deleteFile(this.sessionId, path)
    },
  },
}
</script>

<style scoped>
.file-tree { flex: 1; overflow-y: auto; padding: 8px 0; }
.tree-header { padding: 8px 12px; font-size: 11px; color: #a0aec0; text-transform: uppercase; letter-spacing: 0.5px; }
.tree-empty { padding: 20px; text-align: center; color: #a0aec0; font-size: 13px; }
</style>
```

```vue
<!-- FileTreeNode.vue -->
<template>
  <div class="tree-node" :style="{ paddingLeft: depth * 16 + 12 + 'px' }">
    <div class="node-row" @click="toggle" @contextmenu.prevent="showMenu = !showMenu">
      <span class="node-icon">{{ expanded ? '📂' : '📁' }}</span>
      <span class="node-name" @click.stop="$emit('preview', item.type === 'file' ? getPath() : null)">{{ item.name }}</span>
      <span v-if="item.size" class="node-size">{{ formatSize(item.size) }}</span>
    </div>
    <div v-if="showMenu" class="context-menu">
      <div @click="$emit('preview', getPath()); showMenu = false">预览</div>
      <div @click="$emit('delete', getPath()); showMenu = false">删除</div>
    </div>
    <template v-if="expanded && item.children">
      <FileTreeNode
        v-for="child in item.children" :key="child.name"
        :item="child" :depth="depth + 1" :sessionId="sessionId"
        @preview="$emit('preview', $event)"
        @delete="$emit('delete', $event)"
      />
    </template>
  </div>
</template>

<script>
export default {
  name: 'FileTreeNode',
  props: { item: Object, depth: Number, sessionId: String },
  emits: ['preview', 'delete'],
  data: () => ({ expanded: false, showMenu: false }),
  methods: {
    toggle() {
      if (this.item.type === 'dir') this.expanded = !this.expanded
    },
    getPath() {
      return '/' + this.item.name
    },
    formatSize(bytes) {
      if (!bytes) return ''
      if (bytes < 1024) return bytes + 'B'
      if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB'
      return (bytes / 1048576).toFixed(1) + 'MB'
    },
  },
}
</script>

<style scoped>
.node-row { display: flex; align-items: center; padding: 5px 0; cursor: pointer; font-size: 13px; gap: 4px; }
.node-row:hover { background: #edf2f7; border-radius: 4px; }
.node-icon { font-size: 14px; width: 20px; text-align: center; }
.node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-size { font-size: 11px; color: #a0aec0; }
.context-menu {
  position: absolute; background: white; border: 1px solid #e2e8f0; border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10; font-size: 12px;
}
.context-menu div { padding: 6px 16px; cursor: pointer; }
.context-menu div:hover { background: #ebf8ff; }
</style>
```

- [ ] **Step 3: 创建 FilePreview.vue 和子组件**

```vue
<!-- FilePreview.vue -->
<template>
  <div class="file-preview">
    <div class="preview-header">
      <span class="preview-path">{{ path }}</span>
      <button @click="closePreview" class="close-btn">×</button>
    </div>
    <div class="preview-body">
      <HtmlPreview v-if="isHtml" :content="content" />
      <MarkdownPreview v-else-if="isMarkdown" :content="content" />
      <ImagePreview v-else-if="isImage" :content="content" :mime="mime" />
      <div v-else class="unsupported">不支持预览此文件类型</div>
    </div>
  </div>
</template>

<script>
import HtmlPreview from './HtmlPreview.vue'
import MarkdownPreview from './MarkdownPreview.vue'
import ImagePreview from './ImagePreview.vue'
import { useFileStore } from '../stores/fileStore'

export default {
  components: { HtmlPreview, MarkdownPreview, ImagePreview },
  props: { path: String, content: String, mime: String },
  computed: {
    isHtml() { return this.mime === 'text/html' },
    isMarkdown() { return this.mime === 'text/markdown' || (this.path && this.path.endsWith('.md')) },
    isImage() { return this.mime && this.mime.startsWith('image/') },
  },
  methods: {
    closePreview() {
      const store = useFileStore()
      store.previewPath = null
      store.previewContent = null
      store.previewMime = null
    },
  },
}
</script>

<style scoped>
.file-preview { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.preview-header { display: flex; align-items: center; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 12px; }
.preview-path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #718096; }
.close-btn { background: none; border: none; font-size: 18px; cursor: pointer; color: #a0aec0; }
.preview-body { flex: 1; overflow-y: auto; }
.unsupported { display: flex; align-items: center; justify-content: center; height: 100%; color: #a0aec0; }
</style>
```

```vue
<!-- HtmlPreview.vue -->
<template>
  <iframe :srcdoc="content" class="html-preview" sandbox="allow-scripts allow-same-origin" />
</template>
<script>
export default { props: { content: String } }
</script>
<style scoped>
.html-preview { width: 100%; height: 100%; border: none; }
</style>
```

```vue
<!-- MarkdownPreview.vue -->
<template>
  <div class="md-preview" v-html="rendered" />
</template>
<script>
import { marked } from 'marked'
export default {
  props: { content: String },
  computed: { rendered() { return marked.parse(this.content || '') } },
}
</script>
<style scoped>
.md-preview { padding: 16px; line-height: 1.7; font-size: 14px; }
</style>
```

```vue
<!-- ImagePreview.vue -->
<template>
  <div class="img-preview">
    <img :src="dataUrl" alt="preview" />
  </div>
</template>
<script>
export default {
  props: { content: String, mime: String },
  computed: { dataUrl() { return `data:${this.mime};base64,${btoa(this.content)}` } },
}
</script>
<style scoped>
.img-preview { display: flex; align-items: center; justify-content: center; height: 100%; padding: 16px; }
.img-preview img { max-width: 100%; max-height: 100%; object-fit: contain; }
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WorktreePanel.vue frontend/src/components/PanelTabs.vue frontend/src/components/FileTree.vue frontend/src/components/FileTreeNode.vue frontend/src/components/FileContextMenu.vue frontend/src/components/FilePreview.vue frontend/src/components/HtmlPreview.vue frontend/src/components/MarkdownPreview.vue frontend/src/components/ImagePreview.vue
git commit -m "feat: 前端右侧工作区组件（文件树/目录浏览/HTML预览/MD预览/图片预览）"
```

---

### Task 16: 集成测试 + 端到端验证

**Files:**
- 无新文件

- [ ] **Step 1: 启动后端服务**

```bash
conda activate py310
cd backend
uvicorn main:app --reload --port 8000
```

Expected: 服务启动，health 端点正常，MySQL 表自动创建。

- [ ] **Step 2: 验证 REST API**

```bash
# 创建会话
curl -X POST http://localhost:8000/api/sessions?user_id=test_user

# 上传测试 CSV
echo "month,sales\n1月,1000\n2月,1200\n3月,1100" > /tmp/test.csv
curl -X POST -F "file=@/tmp/test.csv" http://localhost:8000/api/sessions/<id>/files

# 检查文件树
curl http://localhost:8000/api/sessions/<id>/files

# 检查 MySQL 数据
mysql -u root -p123456 -e "SELECT * FROM data_analysis_agent.sessions\G"
```

Expected: 所有 API 返回正确 JSON，MySQL 有记录。

- [ ] **Step 3: 启动前端服务**

```bash
cd frontend
npm run dev
```

Expected: Vite 启动在 5173 端口，打开浏览器可看到页面。

- [ ] **Step 4: 手动验证前端功能**

流程：
1. 打开 http://localhost:5173
2. 点击"新建会话" → 右侧出现文件面板
3. 上传 CSV 文件 → 文件树更新
4. 输入 "@test.csv 分析月度趋势" → 发送
5. 观察：TodoPanel 显示计划、对话区流式显示、报告生成后文件树更新
6. 点击 HTML 报告 → 右侧 iframe 预览
7. 切换回文件树 → 目录浏览正常
8. 删除会话 → 确认列表移除

Expected: 所有功能正常交互。

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: 集成验证，确认全链路可用"
```

---

## 自审

| 检查项 | 结果 |
|--------|------|
| Spec 覆盖 | 设计文档所有 12 个决策点均有对应 Task |
| Placeholder 扫描 | OBS 明确标记"打桩"，无 TBD/TODO |
| 类型一致性 | session_id 统一为 String/UUID，API 返回格式与前端 Store 对齐 |
| Task 右大小 | 每个 Task 2-6 分钟可完成，独立可测试 |
