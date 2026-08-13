"""demo 沙箱封装 —— 自包含的 wasmsh 沙箱模块（不依赖 langchain）。

对外提供：

- ``Sandbox``：底层沙箱运行时（执行 shell 命令 / Python 脚本、上传下载文件）
- ``SandboxManager``：多会话沙箱生命周期管理（会话绑定 + 复用 + 超时重建 + 空闲回收）
- ``CommandResult`` / ``PythonResult``：结构化执行结果（stdout / stderr / traceback / exit_code）
- ``get_preload_files`` / ``BOOTSTRAP_SCRIPT``：离线 wheel 预加载工具

典型用法::

    from sandbox import SandboxManager

    manager = SandboxManager()
    result = manager.run_python("session-1", "print('hello')")
    print(result.stdout)
    manager.close_all()
"""
from sandbox.manager import SandboxManager
from sandbox.results import CommandResult, PythonResult
from sandbox.runtime import BOOTSTRAP_SCRIPT, Sandbox, get_preload_files

__all__ = [
    "CommandResult",
    "PythonResult",
    "Sandbox",
    "SandboxManager",
    "BOOTSTRAP_SCRIPT",
    "get_preload_files",
]
