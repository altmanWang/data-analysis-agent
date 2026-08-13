"""wasmsh 沙箱系统化封装使用示例。

演示 ``sandbox`` 包的完整能力：

1. SandboxManager 生命周期管理（会话绑定 + close_all 收尾）
2. 执行用户 Python 脚本（run_python），结构化捕获输出 / 异常 / 打印
3. 上传 / 下载文件
4. VFS 复用（跨多次 run_python 持久化）
5. 文件系统 / 网络隔离验证

运行方式（项目根目录）:

    python demo/run_sandbox_demo.py

前置条件:

    - Node.js >= 20（沙箱由 Node.js 子进程承载）
    - 已安装依赖 ``wasmsh-pyodide-runtime``（见 requirements.txt）
"""
import sys
from pathlib import Path

# 强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台对 ✓ 等字符报 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from sandbox import SandboxManager  # noqa: E402

SESSION_DIR = Path(__file__).resolve().parent / "session"  # demo/session/
SESSION_ID = "demo-session"

# 沙箱内文件路径（两端统一使用根路径）
EXCEL_PATH = "/test.xlsx"     # 输入 Excel（宿主端 demo/session/test.xlsx）
SCRIPT_PATH = "/convert.py"   # 沙箱内执行的 Python 脚本（宿主端 demo/session/convert.py）
CSV_PATH = "/output.csv"      # 输出 CSV（宿主端 demo/session/output.csv）


def verify_isolation(manager: SandboxManager) -> None:
    """验证宿主机与执行机之间的文件系统 / 网络隔离。"""
    print("── 文件系统隔离验证 ──")

    # (a) 沙箱 VFS 根目录只含注入的 wheel，看不到宿主机 C:\ 等内容
    r = manager.execute(SESSION_ID, "ls /")
    print("沙箱 VFS 根目录：")
    print(r.stdout)

    # (b) 沙箱内无法读取宿主机文件（VFS 中不存在 /etc/passwd）
    r = manager.execute(SESSION_ID, "python3 -c \"open('/etc/passwd').read()\"")
    print(f"读取宿主机 /etc/passwd → exit_code={r.exit_code}（应非 0）")

    # (c) 网络完全隔离（allowed_hosts=[]，发起请求应被拦截）
    r = manager.execute(
        SESSION_ID,
        "python3 -c \"import urllib.request; urllib.request.urlopen('http://example.com')\"",
    )
    print(f"发起外网请求 → exit_code={r.exit_code}（应非 0，被拦截）")


def verify_os_paths(manager: SandboxManager) -> None:
    """用 os 模块校验沙箱内可访问的路径范围，验证宿主机文件系统隔离。

    沙箱运行在 Emscripten（WASM）Pyodide 环境中，os 模块看到的是
    虚拟文件系统（MemoryFS），与宿主机磁盘物理隔离：

    - os 能访问：沙箱 VFS 目录（/lib /tmp /home /proc /dev /workspace 等）
    - os 无法访问：宿主机路径（/etc/passwd、/root、C:/Windows 等）
    - os.uname().sysname == 'Emscripten'，证明运行在 WASM 而非宿主机
    """
    print("── os 路径校验 ──")

    # (a) os 能访问的沙箱内部路径与运行环境特征
    code = (
        "import os, sys\n"
        "print('os.getcwd()   =', os.getcwd())\n"
        "print('sys.prefix    =', sys.prefix)\n"
        "print('uname.sysname =', os.uname().sysname)\n"
        "print('根目录 listdir =', sorted(os.listdir('/')))\n"
        "print('沙箱内可访问路径:')\n"
        "for p in ['/tmp', '/home', '/lib/python3.13', '/workspace', '/wheels']:\n"
        "    print(f'  os.path.exists({p!r}) =', os.path.exists(p))\n"
    )
    result = manager.run_python(SESSION_ID, code)
    print(result.stdout, end="")

    # (b) os 无法访问宿主机路径（隔离验证，应全部 False）
    code = (
        "import os\n"
        "print('宿主机路径（应全部 False）:')\n"
        "for p in ['/etc/passwd', '/etc/hosts', '/root', '/home/pyodide', 'C:/Windows', '/Users']:\n"
        "    print(f'  os.path.exists({p!r}) =', os.path.exists(p))\n"
    )
    result = manager.run_python(SESSION_ID, code)
    print(result.stdout, end="")


def main() -> None:
    # 1. 创建 SandboxManager（会话绑定 + 空闲回收 + 超时重建）
    manager = SandboxManager(step_budget=100_000)
    try:
        # 2. 上传 Excel 与转换脚本到沙箱 VFS
        manager.upload_files(
            SESSION_ID,
            [
                (EXCEL_PATH, (SESSION_DIR / "test.xlsx").read_bytes()),
                (SCRIPT_PATH, (SESSION_DIR / "convert.py").read_bytes()),
            ],
        )
        print("✓ test.xlsx 与 convert.py 已上传到沙箱")

        # 3. 执行 Python 脚本（读取 Excel → 转换 CSV）
        result = manager.execute(SESSION_ID, f"python3 {SCRIPT_PATH}")
        if not result.success:
            raise RuntimeError(f"脚本执行失败: {result.stderr}")
        print("── 沙箱内执行输出 ──")
        print(result.stdout)

        # 4. 结构化捕获异常（run_python 直接执行代码字符串）
        result = manager.run_python(SESSION_ID, "raise ValueError('demo error')")
        print("── 异常捕获 ──")
        print(f"success={result.success} exit_code={result.exit_code}")
        print(f"traceback 末行: {result.traceback.strip().splitlines()[-1]}")

        # 5. VFS 复用：跨多次 run_python 持久化文件
        manager.run_python(SESSION_ID, "open('/note.txt', 'w').write('persisted-data')")
        result = manager.run_python(SESSION_ID, "print(open('/note.txt').read())")
        print("── VFS 复用 ──")
        print(f"读回 /note.txt: {result.stdout.strip()}")

        # 6. 下载生成的 CSV 回宿主机
        csv_bytes = manager.download_files(SESSION_ID, [CSV_PATH])[0][1]
        (SESSION_DIR / "output.csv").write_bytes(csv_bytes)
        print(f"✓ CSV 已下载到 {SESSION_DIR / 'output.csv'}")
        print("── CSV 内容 ──")
        print(csv_bytes.decode("utf-8"))

        # 7. 验证宿主机 ↔ 执行机文件系统 / 网络隔离
        verify_isolation(manager)

        # 8. 用 os 模块校验沙箱可访问路径 + 宿主机隔离
        verify_os_paths(manager)
    finally:
        # 9. 关闭所有沙箱，终止 Node.js 子进程
        manager.close_all()
        print("✓ 沙箱已全部关闭")


if __name__ == "__main__":
    main()
