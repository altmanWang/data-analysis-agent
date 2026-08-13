"""runtime.py 增强 Sandbox 的集成测试（需要 Node >= 20 与 wasmsh-pyodide-runtime）。

验证核心能力：
- execute 分离 stdout / stderr / exit_code
- run_python 执行用户脚本并结构化捕获 print / 异常 traceback
- 宿主端超时（kill 子进程 + is_alive=False）
- 上传 / 下载文件往返
- VFS 文件级持久化（跨多次 run_python）
- 生命周期（is_alive / close 幂等）
"""
import pytest

from sandbox.results import CommandResult, PythonResult


# ── execute：stdout / stderr 分离 ──────────────────────────────────────────

def test_execute_separates_stdout_stderr(sandbox):
    """execute 应分别返回 stdout 与 stderr（而非合并的 output）。"""
    sandbox.write(
        "/test_io.py",
        "import sys\nprint('OUT')\nprint('ERR', file=sys.stderr)\n",
    )
    r = sandbox.execute("python3 /test_io.py")
    assert isinstance(r, CommandResult)
    assert "OUT" in r.stdout
    assert "ERR" in r.stderr
    assert "OUT" not in r.stderr
    assert r.exit_code == 0
    assert r.success is True


def test_execute_reports_nonzero_exit(sandbox):
    """命令失败时 exit_code 非 0 且 success 为 False（sys.exit 码正确传播）。"""
    r = sandbox.execute("python3 -c \"import sys; sys.exit(7)\"")
    assert r.exit_code == 7
    assert r.success is False


# ── run_python：执行脚本 + 捕获输出 / 异常 ────────────────────────────────

def test_run_python_captures_stdout(sandbox):
    """run_python 应捕获 print 输出到 stdout。"""
    r = sandbox.run_python("print('hello sandbox')")
    assert isinstance(r, PythonResult)
    assert r.success is True
    assert r.exit_code == 0
    assert "hello sandbox" in r.stdout
    assert r.traceback is None


def test_run_python_captures_exception(sandbox):
    """未捕获异常应被结构化捕获：success=False + traceback 含异常信息。"""
    r = sandbox.run_python("raise ValueError('boom')")
    assert r.success is False
    assert r.exit_code != 0
    assert "ValueError" in r.stderr
    assert "boom" in r.stderr
    assert r.traceback is not None
    assert "ValueError" in r.traceback


def test_run_python_multiline_script(sandbox):
    """多行脚本（含变量、循环、pandas 可用性）应正常执行。"""
    r = sandbox.run_python(
        "import pandas as pd\n"
        "df = pd.DataFrame({'a': [1, 2, 3]})\n"
        "print(df['a'].sum())\n"
    )
    assert r.success is True
    assert "6" in r.stdout


# ── 超时：宿主端 kill ──────────────────────────────────────────────────────

def test_run_python_timeout(fresh_sandbox):
    """死循环脚本应在超时后被 kill，并抛出 TimeoutError + 标记沙箱失效。"""
    assert fresh_sandbox.is_alive is True
    with pytest.raises(TimeoutError):
        fresh_sandbox.run_python("while True:\n    pass", timeout=3)
    assert fresh_sandbox.is_alive is False


# ── 上传 / 下载 ────────────────────────────────────────────────────────────

def test_upload_download_roundtrip(sandbox):
    """上传后应能原样下载回。"""
    sandbox.upload_files([("/roundtrip.txt", b"hello sandbox")])
    results = sandbox.download_files(["/roundtrip.txt"])
    assert len(results) == 1
    path, content = results[0]
    assert path == "/roundtrip.txt"
    assert content == b"hello sandbox"


def test_download_missing_file_returns_empty(sandbox):
    """下载不存在的文件应返回空 bytes 且不抛异常（wasmsh readFile 对缺失文件返回空流）。"""
    results = sandbox.download_files(["/nonexistent.txt"])
    assert results[0][0] == "/nonexistent.txt"
    assert results[0][1] == b""


# ── VFS 持久化 ─────────────────────────────────────────────────────────────

def test_run_python_vfs_persists(sandbox):
    """第一次 run_python 写入的文件，第二次应能读回（文件级持久化）。"""
    sandbox.run_python("open('/persist.txt', 'w').write('persisted-data')")
    r = sandbox.run_python("print(open('/persist.txt').read())")
    assert r.success is True
    assert "persisted-data" in r.stdout


# ── 生命周期 ───────────────────────────────────────────────────────────────

def test_is_alive_and_close_idempotent(fresh_sandbox):
    """close 应幂等，关闭后 is_alive 为 False。"""
    assert fresh_sandbox.is_alive is True
    fresh_sandbox.close()
    assert fresh_sandbox.is_alive is False
    fresh_sandbox.close()  # 幂等，不抛异常
