"""wasmsh 沙箱运行时封装 —— 直接基于 wasmsh-pyodide-runtime，不依赖 langchain。

在 :mod:`demo.sandbox_runtime` 的基础上系统性增强，提供：

- ``execute``：执行 shell 命令，分离捕获 stdout / stderr / exit_code
- ``run_python``：执行用户 Python 脚本，结构化捕获输出 / 异常 traceback
- ``upload_files`` / ``download_files`` / ``write``：文件上传下载
- 宿主端执行超时（worker 线程 + join(timeout)，超时 kill 子进程并标记沙箱失效）
- 生命周期管理（``is_alive`` / 幂等 ``close`` / 上下文管理器）

隔离模型（由 wasmsh 底层保证，与本封装无关）：

- 沙箱文件系统 = Emscripten MemoryFS（纯内存），与宿主机磁盘物理隔离
- WASM 沙箱无 syscall 通道，沙箱内代码无法访问宿主机文件
- 唯一文件交换通道 = 显式的 upload_files / download_files（base64 over JSON-RPC）
- allowed_hosts=[] 完全离线，无 SSRF 风险

依赖：

- ``wasmsh-pyodide-runtime``（提供 node-host.mjs + Pyodide WASM 资产）
- Node.js >= 20（每个沙箱一个子进程）
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import threading
from pathlib import Path

from wasmsh_pyodide_runtime import get_dist_dir, get_node_host_script

from sandbox.results import CommandResult, PythonResult

# wheel 缓存目录（只读复用主程序 backend/sandbox_wheels 里的离线 wheel）
_WHEELS_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "sandbox_wheels"

# run_python 写用户代码到沙箱 VFS 的固定路径（双下划线前缀，避免与用户文件冲突）
_CODE_PATH = "/__sandbox_code__.py"


# 沙箱启动脚本：在沙箱内执行，安装预缓存 wheel + 配置 UTF-8 编码
# （与 backend/sandbox/__init__.py 中的 BOOTSTRAP_SCRIPT 保持一致）
BOOTSTRAP_SCRIPT = r"""
import os, sys, zipfile, io

# ── 强制 UTF-8 编码，防止 Windows GBK 环境导致的 UnicodeDecodeError ──
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
# Pyodide 中 locale 不可用，直接用环境变量
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# ── 安装预缓存 wheel ──
sp = "/lib/python3.13/site-packages"
wheels_dir = "/wheels"

count = 0
for f in sorted(os.listdir(wheels_dir)):
    if not f.endswith(".whl"):
        continue
    whl = os.path.join(wheels_dir, f)
    try:
        with zipfile.ZipFile(whl) as zf:
            zf.extractall(sp)
        count += 1
    except Exception:
        pass  # 重复安装忽略

if sp not in sys.path:
    sys.path.insert(0, sp)

pass
""".strip()


def get_preload_files() -> dict[str, bytes]:
    """读取本地缓存的 wheel 文件，返回 {sandbox_path: bytes} 映射。

    缓存目录不存在或为空时返回空字典（沙箱将以纯 Python 运行）。
    """
    if not _WHEELS_DIR.is_dir():
        return {}
    files: dict[str, bytes] = {}
    for wheel_file in sorted(_WHEELS_DIR.glob("*.whl")):
        try:
            files[f"/wheels/{wheel_file.name}"] = wheel_file.read_bytes()
        except OSError:
            continue
    return files


class Sandbox:
    """基于 wasmsh-pyodide-runtime 的轻量沙箱。

    启动一个 Node.js 子进程承载 Pyodide WASM 运行时，通过 JSON-RPC
    协议（init / run / writeFile / readFile / close）与沙箱交互。

    单个沙箱实例内部用 ``_lock``（JSON-RPC 请求配对）与 ``_exec_lock``
    （整次 execute/run_python 原子性）保证线程安全，同一时刻只允许一个
    执行操作。
    """

    def __init__(
        self,
        *,
        initial_files: dict[str, str | bytes] | None = None,
        allowed_hosts: list[str] | None = None,
        step_budget: int = 0,
        working_directory: str = "/",
    ) -> None:
        self._working_directory = working_directory
        self._request_id = 0
        self._lock = threading.Lock()
        self._exec_lock = threading.RLock()
        self._dead = False

        node_path = shutil.which("node")
        if node_path is None:
            raise FileNotFoundError("未找到 node，请安装 Node.js >= 20")

        host_script = str(get_node_host_script())
        dist_dir = str(get_dist_dir())
        cmd = [node_path, host_script, "--asset-dir", dist_dir]

        # encoding="utf-8" 是关键：避免 Windows 下默认 GBK 解码子进程 UTF-8
        # 输出导致的 UnicodeDecodeError（langchain-wasmsh 未设置此参数）。
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        # 独立线程持续排空 stderr，防止子进程 stderr 管道写满而阻塞
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

        # 发送 init：注入初始文件 + 配置网络白名单 / 步数预算
        payload_files = []
        for path, content in (initial_files or {}).items():
            raw = content.encode("utf-8") if isinstance(content, str) else content
            payload_files.append(
                {
                    "path": path,
                    "contentBase64": base64.b64encode(raw).decode("ascii"),
                }
            )
        self._request(
            "init",
            {
                "stepBudget": step_budget,
                "initialFiles": payload_files,
                "allowedHosts": allowed_hosts or [],
            },
        )

    # ── 生命周期 ──────────────────────────────────────────────────────────

    @property
    def is_alive(self) -> bool:
        """沙箱进程是否存活且未被标记失效（超时 kill 后为 False）。"""
        return not self._dead and self._process.poll() is None

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    # ── 内部：JSON-RPC 协议 ──────────────────────────────────────────────

    def _drain_stderr(self) -> None:
        """持续读取子进程 stderr，避免管道阻塞（内容丢弃）。"""
        try:
            for _ in self._process.stderr:
                pass
        except (OSError, ValueError):
            pass

    def _request(self, method: str, params: dict) -> dict:
        """发送一条 JSON-RPC 请求并读取对应响应。"""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            self._process.stdin.write(
                json.dumps({"id": request_id, "method": method, "params": params})
                + "\n"
            )
            self._process.stdin.flush()

            while True:
                line = self._process.stdout.readline()
                if not line:
                    raise RuntimeError("wasmsh 宿主进程意外终止")
                message = json.loads(line)
                if message.get("type") == "ack":
                    continue  # 启动确认消息，跳过
                if message.get("id") != request_id:
                    continue  # 非当前请求的响应，跳过
                if not message.get("ok"):
                    raise RuntimeError(str(message.get("error", "未知错误")))
                return message.get("result", {})

    def _kill_process(self) -> None:
        """终止 Node.js 子进程（超时兜底），确保进程真正死亡。"""
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    @staticmethod
    def _to_command_result(result: dict) -> CommandResult:
        """将 run 的 JSON-RPC 结果映射为 CommandResult（分离 stdout/stderr）。"""
        return CommandResult(
            stdout=str(result.get("stdout", "")),
            stderr=str(result.get("stderr", "")),
            exit_code=result.get("exitCode") or 0,
        )

    def _execute_locked(self, command: str, timeout: float | None) -> CommandResult:
        """执行一条完整 shell 命令（调用方需已持有 _exec_lock）。

        超时实现：worker 线程执行阻塞的 _request，主线程 join(timeout)；
        超时则 kill 子进程并标记沙箱失效，抛出 TimeoutError。
        """
        if not self.is_alive:
            raise RuntimeError("沙箱已失效（进程已终止），无法执行")

        full_cmd = f"cd {self._working_directory} && {command}"

        if timeout is None:
            return self._to_command_result(self._request("run", {"command": full_cmd}))

        holder: dict = {}

        def worker() -> None:
            try:
                holder["result"] = self._request("run", {"command": full_cmd})
            except Exception as exc:  # 捕获所有异常传递回主线程
                holder["error"] = exc

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join(timeout)

        if t.is_alive():
            self._dead = True
            self._kill_process()
            raise TimeoutError(f"沙箱命令执行超时（>{timeout}s）: {command[:120]}")

        if "error" in holder:
            raise holder["error"]
        return self._to_command_result(holder["result"])

    # ── 对外 API ─────────────────────────────────────────────────────────

    def execute(self, command: str, *, timeout: float | None = None) -> CommandResult:
        """在沙箱内执行一条 shell 命令（含 python3），分离捕获 stdout/stderr。

        Args:
            command: shell 命令，如 ``python3 /script.py``
            timeout: 可选执行超时（秒）；超时则 kill 子进程并抛 TimeoutError。
        """
        with self._exec_lock:
            return self._execute_locked(command, timeout)

    def run_python(self, code: str, *, timeout: float | None = None) -> PythonResult:
        """执行一段用户 Python 脚本，结构化捕获输出 / 异常。

        将 code 写入沙箱 VFS 的固定路径后执行 ``python3 /__sandbox_code__.py``，
        脚本的 print 进入 stdout，未捕获异常的 traceback 进入 stderr。

        Args:
            code:    用户 Python 源码。
            timeout: 可选执行超时（秒）；超时则 kill 子进程并抛 TimeoutError。

        Returns:
            PythonResult：stdout（print）/ stderr（异常 traceback）/ exit_code / traceback。
        """
        with self._exec_lock:
            if not self.is_alive:
                raise RuntimeError("沙箱已失效（进程已终止），无法执行")
            self.write(_CODE_PATH, code)
            cmd_result = self._execute_locked(f"python3 {_CODE_PATH}", timeout)
        return PythonResult(
            stdout=cmd_result.stdout,
            stderr=cmd_result.stderr,
            exit_code=cmd_result.exit_code,
            traceback=cmd_result.stderr if cmd_result.exit_code != 0 else None,
        )

    def write(self, file_path: str, content: str) -> None:
        """向沙箱 VFS 写入一个文本文件。"""
        self.upload_files([(file_path, content.encode("utf-8"))])

    def upload_files(self, files: list[tuple[str, bytes]]) -> None:
        """将宿主机文件内容上传到沙箱 VFS（files 为 [(path, bytes), ...]）。"""
        for path, content in files:
            self._request(
                "writeFile",
                {
                    "path": path,
                    "contentBase64": base64.b64encode(content).decode("ascii"),
                },
            )

    def download_files(self, paths: list[str]) -> list[tuple[str, bytes | None]]:
        """从沙箱 VFS 下载文件，返回 [(path, bytes|None), ...]。"""
        results: list[tuple[str, bytes | None]] = []
        for path in paths:
            try:
                result = self._request("readFile", {"path": path})
                content = base64.b64decode(result["contentBase64"])
                results.append((path, content))
            except RuntimeError:
                results.append((path, None))
        return results

    def close(self) -> None:
        """关闭沙箱，终止 Node.js 子进程（幂等，可重复调用）。"""
        try:
            if not self._dead and self._process.poll() is None:
                self._request("close", {})
        except (RuntimeError, OSError, ValueError):
            pass
        finally:
            self._dead = True
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
