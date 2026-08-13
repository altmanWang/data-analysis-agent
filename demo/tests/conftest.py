"""pytest 全局配置。

- 将 demo/ 加入 sys.path，使 `from sandbox import ...` 可解析
- 强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台对 ✓ 等字符报 UnicodeEncodeError
"""
import sys
from pathlib import Path

# demo/ 目录加入 sys.path（test_results.py 等测试需要）
DEMO_DIR = Path(__file__).resolve().parent.parent
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

# Windows 下强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 延迟导入，确保 sys.path 已就绪
import pytest  # noqa: E402
from sandbox.runtime import BOOTSTRAP_SCRIPT, Sandbox, get_preload_files  # noqa: E402


def _make_sandbox(step_budget: int = 100_000) -> Sandbox:
    """创建一个已 bootstrap（安装离线 wheel）的沙箱。

    step_budget=0 表示不限制 VM 步数（供超时测试使用，确保死循环只被宿主端超时中断）。
    """
    preload = get_preload_files()
    sb = Sandbox(
        step_budget=step_budget,
        allowed_hosts=[],
        working_directory="/",
        initial_files=preload,
    )
    if preload:
        sb.write("/bootstrap.py", BOOTSTRAP_SCRIPT)
        r = sb.execute("python3 /bootstrap.py")
        if r.exit_code != 0:
            sb.close()
            raise RuntimeError(f"bootstrap 失败: {r.stderr or r.stdout}")
    return sb


@pytest.fixture(scope="session")
def sandbox():
    """session 级沙箱：bootstrap 一次，供多个测试复用（不涉及 kill 的测试）。"""
    sb = _make_sandbox()
    yield sb
    sb.close()


@pytest.fixture()
def fresh_sandbox():
    """fresh 沙箱：每个测试独立，供超时（kill）与 close 幂等测试使用。"""
    sb = _make_sandbox(step_budget=0)
    yield sb
    sb.close()


# manager fixture（延迟导入，避免 test_results 等无 Node 测试也被拖累）
from sandbox.manager import SandboxManager  # noqa: E402


@pytest.fixture(scope="session")
def manager():
    """session 级 manager：复用同一批沙箱，供复用/VFS 持久化测试。"""
    mgr = SandboxManager(idle_timeout=3600, reaper_interval=3600, step_budget=100_000)
    yield mgr
    mgr.close_all()


@pytest.fixture()
def fresh_manager():
    """fresh manager：idle_timeout=1s 供空闲回收测试，step_budget=0 供超时测试。"""
    mgr = SandboxManager(idle_timeout=1, reaper_interval=3600, step_budget=0)
    yield mgr
    mgr.close_all()
