"""results.py 数据类的单元测试（纯 Python，无需 Node）。

验证结构化结果的字段语义：
- stdout / stderr 分离
- output 合并（兼容旧接口）
- success 由 exit_code 推导
- traceback 异常堆栈快照
- 冻结（不可变）
"""
import dataclasses

import pytest

from sandbox.results import CommandResult, PythonResult


def test_command_result_output_concatenates_stdout_stderr():
    """output 应等于 stdout + stderr 的合并。"""
    r = CommandResult(stdout="hello\n", stderr="warning\n", exit_code=0)
    assert r.output == "hello\nwarning\n"


def test_command_result_success_by_exit_code():
    """exit_code == 0 视为成功，非 0 视为失败。"""
    assert CommandResult(exit_code=0).success is True
    assert CommandResult(exit_code=1).success is False
    assert CommandResult(exit_code=127).success is False


def test_command_result_defaults():
    """默认构造应为空输出 + 成功状态。"""
    r = CommandResult()
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.exit_code == 0
    assert r.success is True


def test_python_result_success_by_exit_code():
    assert PythonResult(exit_code=0).success is True
    assert PythonResult(exit_code=1).success is False


def test_python_result_traceback_defaults_none():
    """未设置 traceback 时默认为 None。"""
    assert PythonResult().traceback is None


def test_python_result_traceback_preserved():
    """traceback 字段应保留传入的异常堆栈内容。"""
    tb = "Traceback (most recent call last):\n  ...\nZeroDivisionError\n"
    r = PythonResult(stderr=tb, exit_code=1, traceback=tb)
    assert r.traceback == tb
    assert r.success is False


def test_command_result_is_frozen():
    """结果对象应不可变（frozen dataclass）。"""
    r = CommandResult(stdout="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.stdout = "changed"


def test_python_result_is_frozen():
    r = PythonResult(exit_code=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.exit_code = 1
