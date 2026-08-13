"""沙箱生命周期管理器 —— 会话绑定 + 复用 + 重建 + 空闲回收。

在 :mod:`sandbox.runtime.Sandbox` 之上提供多会话的沙箱生命周期管理：

- **会话绑定**：以 session_id 为键，每个会话一个沙箱实例
- **跨调用复用**：同一会话多次执行复用同一沙箱，VFS 文件状态持久
- **超时重建**：沙箱被超时 kill（is_alive=False）后，下次调用透明重建
- **空闲回收**：后台 daemon 线程定期关闭闲置超时的会话沙箱
- **线程安全**：全局锁保护会话字典，每会话锁串行化该会话的沙箱操作

典型用法::

    manager = SandboxManager()
    result = manager.run_python("session-1", "print('hello')")
    manager.close_all()  # 程序退出前收尾
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from sandbox.results import CommandResult, PythonResult
from sandbox.runtime import BOOTSTRAP_SCRIPT, Sandbox, get_preload_files


@dataclass
class _SessionEntry:
    """单个会话的沙箱状态。

    sandbox 采用懒加载（首次使用时创建），被超时 kill 后置为 dead，
    下次 _get_sandbox_locked 检测到会重建。
    """

    sandbox: Sandbox | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_used_at: float = 0.0


class SandboxManager:
    """管理多个会话的沙箱生命周期。"""

    def __init__(
        self,
        *,
        idle_timeout: float = 3600,
        reaper_interval: float = 600,
        default_timeout: float | None = None,
        step_budget: int = 100_000,
    ) -> None:
        """
        Args:
            idle_timeout:    会话闲置超时（秒），超过则被后台线程回收。
            reaper_interval: 后台回收线程扫描间隔（秒）。
            default_timeout: 默认执行超时（秒）；None 表示不超时。
            step_budget:     wasmsh VM 步数预算（0=不限制）。
        """
        self._idle_timeout = idle_timeout
        self._reaper_interval = reaper_interval
        self._default_timeout = default_timeout
        self._step_budget = step_budget

        self._sessions: dict[str, _SessionEntry] = {}
        self._global_lock = threading.Lock()
        self._closed = False

        # 后台空闲回收线程
        self._reaper = threading.Thread(target=self._reap_loop, daemon=True)
        self._reaper.start()

    # ── 内部 ──────────────────────────────────────────────────────────────

    def _make_sandbox(self) -> Sandbox:
        """创建并 bootstrap（安装离线 wheel）一个新沙箱。"""
        preload = get_preload_files()
        sb = Sandbox(
            step_budget=self._step_budget,
            allowed_hosts=[],
            working_directory="/",
            initial_files=preload,
        )
        if preload:
            sb.write("/bootstrap.py", BOOTSTRAP_SCRIPT)
            result = sb.execute("python3 /bootstrap.py")
            if result.exit_code != 0:
                sb.close()
                raise RuntimeError(f"bootstrap 失败: {result.stderr or result.stdout}")
        return sb

    def _get_entry(self, session_id: str) -> _SessionEntry:
        """获取会话 entry，不存在则创建（不加载沙箱，懒加载交给调用方）。"""
        with self._global_lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                entry = _SessionEntry(last_used_at=time.monotonic())
                self._sessions[session_id] = entry
            return entry

    def _get_sandbox_locked(self, entry: _SessionEntry) -> Sandbox:
        """在已持有 entry.lock 的前提下，懒加载或重建沙箱。"""
        if entry.sandbox is None or not entry.sandbox.is_alive:
            entry.sandbox = self._make_sandbox()
        return entry.sandbox

    def _resolve_timeout(self, timeout: float | None) -> float | None:
        return timeout if timeout is not None else self._default_timeout

    def _reap_loop(self) -> None:
        """后台线程：定期回收闲置会话。"""
        while not self._closed:
            time.sleep(self._reaper_interval)
            if not self._closed:
                self.cleanup_idle()

    # ── 对外 API ─────────────────────────────────────────────────────────

    def get_or_create(self, session_id: str) -> Sandbox:
        """获取会话沙箱，不存在或已失效则创建/重建。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            entry.last_used_at = time.monotonic()
            return sandbox

    def run_python(
        self, session_id: str, code: str, *, timeout: float | None = None
    ) -> PythonResult:
        """在指定会话沙箱内执行 Python 脚本，结构化返回结果。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            result = sandbox.run_python(code, timeout=self._resolve_timeout(timeout))
            entry.last_used_at = time.monotonic()
            return result

    def execute(
        self, session_id: str, command: str, *, timeout: float | None = None
    ) -> CommandResult:
        """在指定会话沙箱内执行 shell 命令。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            result = sandbox.execute(command, timeout=self._resolve_timeout(timeout))
            entry.last_used_at = time.monotonic()
            return result

    def upload_files(self, session_id: str, files: list[tuple[str, bytes]]) -> None:
        """上传文件到指定会话沙箱。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            sandbox.upload_files(files)
            entry.last_used_at = time.monotonic()

    def download_files(
        self, session_id: str, paths: list[str]
    ) -> list[tuple[str, bytes | None]]:
        """从指定会话沙箱下载文件。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            result = sandbox.download_files(paths)
            entry.last_used_at = time.monotonic()
            return result

    def write(self, session_id: str, file_path: str, content: str) -> None:
        """向指定会话沙箱写入文本文件。"""
        entry = self._get_entry(session_id)
        with entry.lock:
            sandbox = self._get_sandbox_locked(entry)
            sandbox.write(file_path, content)
            entry.last_used_at = time.monotonic()

    def is_active(self, session_id: str) -> bool:
        """会话当前是否有沙箱记录（不含其是否失效）。"""
        with self._global_lock:
            return session_id in self._sessions

    def close(self, session_id: str) -> None:
        """关闭指定会话的沙箱并移除记录（幂等）。"""
        with self._global_lock:
            entry = self._sessions.pop(session_id, None)
        if entry is not None:
            with entry.lock:
                if entry.sandbox is not None:
                    entry.sandbox.close()
                    entry.sandbox = None

    def close_all(self) -> None:
        """关闭所有会话沙箱并清空记录。"""
        self._closed = True
        with self._global_lock:
            entries = list(self._sessions.values())
            self._sessions.clear()
        for entry in entries:
            with entry.lock:
                if entry.sandbox is not None:
                    entry.sandbox.close()
                    entry.sandbox = None

    def cleanup_idle(self, max_idle_seconds: float | None = None) -> list[str]:
        """回收闲置超过阈值的会话，返回被回收的 session_id 列表。"""
        threshold = (
            max_idle_seconds if max_idle_seconds is not None else self._idle_timeout
        )
        now = time.monotonic()
        with self._global_lock:
            stale = [
                sid
                for sid, entry in self._sessions.items()
                if now - entry.last_used_at > threshold
            ]
        for sid in stale:
            self.close(sid)
        return stale
