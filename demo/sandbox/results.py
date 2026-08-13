"""沙箱执行的结构化结果类型。

将沙箱内一次执行的输出拆分为 stdout（正常输出 / print）与 stderr（错误 /
异常 traceback），并提供 success / output 等便捷属性，供上层结构化判断
脚本执行是否成功、异常堆栈是什么。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    """沙箱内一次 shell 命令执行的返回结果。

    Attributes:
        stdout:    标准输出（正常打印）。
        stderr:    标准错误（错误信息 / 异常 traceback）。
        exit_code: 退出码，0 表示成功，非 0 表示失败。
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    @property
    def output(self) -> str:
        """stdout 与 stderr 的合并输出（兼容旧接口）。"""
        return self.stdout + self.stderr

    @property
    def success(self) -> bool:
        """命令是否成功执行（exit_code == 0）。"""
        return self.exit_code == 0


@dataclass(frozen=True)
class PythonResult:
    """沙箱内一次 Python 脚本执行的返回结果。

    Attributes:
        stdout:    标准输出（print 等正常打印）。
        stderr:    标准错误（错误信息 / 未捕获异常 traceback）。
        exit_code: 退出码，0 表示成功，非 0 表示脚本异常退出。
        traceback: 异常堆栈快照；脚本成功时为 None，异常退出时为 stderr 的副本。
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    traceback: str | None = None

    @property
    def success(self) -> bool:
        """脚本是否成功执行（exit_code == 0）。"""
        return self.exit_code == 0

    @property
    def output(self) -> str:
        """stdout 与 stderr 的合并输出。"""
        return self.stdout + self.stderr
