# backend/mysql_saver.py
"""MySQL Checkpointer - 实现 LangGraph BaseCheckpointSaver 协议

参照 langgraph/checkpoint/sqlite/__init__.py 源码适配为 pymysql。
"""

from typing import Any, AsyncIterator, Iterator, Optional, Sequence, Tuple
import asyncio

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

import pymysql

_DEFAULT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id              BIGINT AUTO_INCREMENT,
    thread_id       VARCHAR(128) NOT NULL,
    checkpoint_ns   VARCHAR(128) NOT NULL DEFAULT '',
    checkpoint_id   VARCHAR(128) NOT NULL,
    parent_checkpoint_id VARCHAR(128),
    type            VARCHAR(128),
    checkpoint      LONGBLOB NOT NULL,
    metadata        LONGBLOB,
    PRIMARY KEY (id),
    UNIQUE KEY uk_checkpoint (thread_id, checkpoint_ns, checkpoint_id),
    INDEX idx_thread (thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    id              BIGINT AUTO_INCREMENT,
    thread_id       VARCHAR(128) NOT NULL,
    checkpoint_ns   VARCHAR(128) NOT NULL DEFAULT '',
    checkpoint_id   VARCHAR(128) NOT NULL,
    task_id         VARCHAR(128) NOT NULL,
    idx             INT NOT NULL,
    channel         VARCHAR(128) NOT NULL,
    type            VARCHAR(128),
    value           LONGBLOB,
    PRIMARY KEY (id),
    UNIQUE KEY uk_writes (thread_id(64), checkpoint_ns(64), checkpoint_id(64), task_id(64), idx),
    INDEX idx_thread_cp (thread_id, checkpoint_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    id              BIGINT AUTO_INCREMENT,
    thread_id       VARCHAR(128) NOT NULL,
    checkpoint_ns   VARCHAR(128) NOT NULL DEFAULT '',
    channel         VARCHAR(128) NOT NULL,
    version         VARCHAR(128) NOT NULL,
    type            VARCHAR(128),
    `blob`            LONGBLOB,
    PRIMARY KEY (id),
    UNIQUE KEY uk_blobs (thread_id(64), checkpoint_ns(64), channel(64), version(64)),
    INDEX idx_thread (thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class MySQLSaver(BaseCheckpointSaver):
    """基于 MySQL 的 LangGraph checkpointer"""

    serde = JsonPlusSerializer()

    def __init__(self):
        super().__init__()
        # 不复用连接（pymysql 非线程安全），每次操作创建新连接

    @classmethod
    def from_conn_string(cls, conn: pymysql.connections.Connection) -> "MySQLSaver":
        """从已有连接创建并自动建表（建表后丢弃连接）"""
        saver = cls()
        saver._setup_with_conn(conn)
        return saver

    def _get_conn(self) -> pymysql.connections.Connection:
        """每次操作获取独立连接（线程安全）"""
        from db import get_connection
        return get_connection()

    def _setup_with_conn(self, conn):
        """用指定连接建表"""
        with conn.cursor() as cur:
            for statement in _DEFAULT_TABLE_SQL.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
            conn.commit()

    def setup(self) -> None:
        """创建 checkpointer 所需的三张表"""
        conn = self._get_conn()
        try:
            self._setup_with_conn(conn)
        finally:
            conn.close()

    def _cursor(self):
        """获取游标（每次新建连接以确保线程安全）"""
        conn = self._get_conn()
        return conn, conn.cursor()

    # ─── get_tuple ──────────────────────────────────

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """读取 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        conn, cur = self._cursor()
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
            if metadata_data is not None:
                metadata = self.serde.loads_typed((ckpt_type, metadata_data))

            # 加载 pending writes
            cur.execute(
                "SELECT task_id, channel, type, value FROM checkpoint_writes "
                "WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s "
                "ORDER BY task_id, idx",
                (thread_id, checkpoint_ns, checkpoint["id"]),
            )
            pending_writes = [
                (task_id, channel, self.serde.loads_typed((w_type, value)))
                for task_id, channel, w_type, value in cur.fetchall()
            ]

            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint["id"],
                    }
                },
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
            conn.close()

    # ─── put ────────────────────────────────────────

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

        conn, cur = self._cursor()
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
                (
                    thread_id, checkpoint_ns, checkpoint["id"],
                    parent_checkpoint_id, ckpt_type, ckpt_bytes, meta_bytes,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    # ─── put_writes ─────────────────────────────────

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

        conn, cur = self._cursor()
        try:
            for idx, (channel, value) in enumerate(writes):
                w_type, w_bytes = self.serde.dumps_typed(value)
                cur.execute(
                    "INSERT INTO checkpoint_writes "
                    "(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "channel=VALUES(channel), type=VALUES(type), value=VALUES(value)",
                    (
                        thread_id, checkpoint_ns, checkpoint_id,
                        task_id, idx, channel, w_type, w_bytes,
                    ),
                )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    # ─── put_blobs ─────────────────────────────────

    def put_blobs(
        self,
        config: dict,
        thread_id: str,
        checkpoint_ns: str,
        values: Sequence[Tuple[str, str, Any]],
    ) -> None:
        """写入 checkpoint blobs"""
        conn, cur = self._cursor()
        try:
            for channel, version, value in values:
                blob_type, blob_bytes = self.serde.dumps_typed(value)
                cur.execute(
                    "INSERT INTO checkpoint_blobs "
                    "(thread_id, checkpoint_ns, channel, version, type, `blob`) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "type=VALUES(type), `blob`=VALUES(`blob`)",
                    (thread_id, checkpoint_ns, channel, version, blob_type, blob_bytes),
                )
            conn.commit()
        finally:
            cur.close()
            conn.close()

    # ─── list ───────────────────────────────────────

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

        conn, cur = self._cursor()
        try:
            sql = (
                "SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, "
                "type, checkpoint, metadata FROM checkpoints WHERE 1=1"
            )
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
                metadata = (
                    self.serde.loads_typed((ckpt_type, meta_bytes))
                    if meta_bytes else {}
                )
                yield CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": tid,
                            "checkpoint_ns": ns,
                            "checkpoint_id": cid,
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config={
                        "configurable": {
                            "thread_id": tid,
                            "checkpoint_ns": ns,
                            "checkpoint_id": parent_id,
                        }
                    } if parent_id else None,
                )
        finally:
            cur.close()
            conn.close()

    # ─── Async wrappers (LangGraph astream 需要) ───

    async def aget_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self, config: dict, checkpoint: Checkpoint,
        metadata: CheckpointMetadata, new_versions: ChannelVersions,
    ) -> dict:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self, config: dict, writes: Sequence[Tuple[str, Any]], task_id: str,
    ) -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id)

    async def alist(
        self, config: Optional[dict], *, filter: Optional[dict] = None,
        before: Optional[dict] = None, limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item
