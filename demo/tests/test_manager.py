"""SandboxManager 生命周期管理的集成测试（需要 Node >= 20）。

验证：
- 会话绑定（同一 session_id 复用同一沙箱）
- 跨会话隔离
- VFS 持久化（跨多次 run_python 复用）
- 超时后自动重建（dead 沙箱 → 下次调用重建）
- 空闲回收（cleanup_idle 关闭闲置会话）
- close / close_all 生命周期收尾
"""
import time

import pytest


# ── 会话绑定与复用 ─────────────────────────────────────────────────────────

def test_get_or_create_reuses_same_sandbox(manager):
    """同一 session_id 应返回同一沙箱实例（复用）。"""
    sb1 = manager.get_or_create("s1")
    sb2 = manager.get_or_create("s1")
    assert sb1 is sb2
    assert sb1.is_alive is True


def test_different_sessions_isolated(manager):
    """不同 session_id 应使用独立沙箱。"""
    sb_a = manager.get_or_create("a")
    sb_b = manager.get_or_create("b")
    assert sb_a is not sb_b


def test_run_python_vfs_persists(manager):
    """跨多次 run_python，VFS 文件应持久化。"""
    manager.run_python("s1", "open('/persist.txt', 'w').write('persisted')")
    r = manager.run_python("s1", "print(open('/persist.txt').read())")
    assert r.success is True
    assert "persisted" in r.stdout


def test_run_python_captures_exception(manager):
    """run_python 应结构化返回异常。"""
    r = manager.run_python("s1", "raise ValueError('boom')")
    assert r.success is False
    assert "ValueError" in r.stderr


# ── 超时重建 ───────────────────────────────────────────────────────────────

def test_rebuild_after_timeout(fresh_manager):
    """超时 kill 后，下次调用应自动重建沙箱。"""
    sb_before = fresh_manager.get_or_create("s1")
    assert sb_before.is_alive is True

    with pytest.raises(TimeoutError):
        fresh_manager.run_python("s1", "while True:\n    pass", timeout=3)

    assert sb_before.is_alive is False

    # 下次调用自动重建（新实例，非复用 dead 沙箱）
    sb_after = fresh_manager.get_or_create("s1")
    assert sb_after is not sb_before
    assert sb_after.is_alive is True

    r = fresh_manager.run_python("s1", "print('rebuilt')")
    assert r.success is True
    assert "rebuilt" in r.stdout


# ── 空闲回收 ───────────────────────────────────────────────────────────────

def test_idle_reclamation(fresh_manager):
    """闲置超过 idle_timeout 的会话应被 cleanup_idle 回收。"""
    fresh_manager.run_python("s1", "print('hi')")
    assert fresh_manager.is_active("s1") is True

    time.sleep(1.5)  # 超过 fresh_manager 的 idle_timeout=1 秒

    stale = fresh_manager.cleanup_idle()
    assert "s1" in stale
    assert fresh_manager.is_active("s1") is False


def test_active_session_not_reclaimed(fresh_manager):
    """活跃会话（最近使用）不应被回收。"""
    fresh_manager.run_python("s1", "print('hi')")
    # 立即回收（未超过 idle_timeout）
    stale = fresh_manager.cleanup_idle()
    assert "s1" not in stale
    assert fresh_manager.is_active("s1") is True


# ── 生命周期收尾 ───────────────────────────────────────────────────────────

def test_close_session(fresh_manager):
    """close 应关闭指定会话的沙箱并移除记录。"""
    fresh_manager.run_python("s1", "print('hi')")
    assert fresh_manager.is_active("s1") is True

    fresh_manager.close("s1")
    assert fresh_manager.is_active("s1") is False


def test_close_all(fresh_manager):
    """close_all 应关闭所有会话并清空。"""
    fresh_manager.run_python("a", "print('a')")
    fresh_manager.run_python("b", "print('b')")
    assert fresh_manager.is_active("a") and fresh_manager.is_active("b")

    fresh_manager.close_all()
    assert not fresh_manager.is_active("a")
    assert not fresh_manager.is_active("b")
