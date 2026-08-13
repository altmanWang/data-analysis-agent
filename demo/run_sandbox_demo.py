"""wasmsh 沙箱使用示例：在隔离的 Pyodide 环境中执行 pandas 脚本，将 Excel 转为 CSV。

本示例直接基于 wasmsh-pyodide-runtime（不依赖 langchain），演示沙箱功能的
完整生命周期，并验证宿主机与执行机之间的文件系统隔离：

  1. 创建 ``Sandbox``（自包含轻量封装，见 sandbox_runtime.py）
  2. 安装离线 wheel（numpy / pandas / matplotlib / openpyxl）
  3. 文件系统 / 网络隔离验证（沙箱看不到宿主机文件、无法联网）
  4. 将 ``demo/session/`` 下的 ``test.xlsx`` 与 ``convert.py`` 上传到沙箱 VFS
  5. 在沙箱内执行 ``convert.py``（pandas 读取 Excel → 写出 CSV）
  6. 将生成的 ``output.csv`` 下载回 ``demo/session/``
  7. 关闭沙箱，释放 Node.js 子进程

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

from sandbox_runtime import BOOTSTRAP_SCRIPT, Sandbox, get_preload_files  # noqa: E402

SESSION_DIR = Path(__file__).resolve().parent / "session"  # demo/session/

# 沙箱内文件路径（两端统一使用根路径）
EXCEL_PATH = "/test.xlsx"     # 输入 Excel（宿主端 demo/session/test.xlsx）
SCRIPT_PATH = "/convert.py"   # 沙箱内执行的 Python 脚本（宿主端 demo/session/convert.py）
CSV_PATH = "/output.csv"      # 输出 CSV（宿主端 demo/session/output.csv）


def verify_isolation(sandbox: Sandbox) -> None:
    """验证宿主机与执行机之间的文件系统 / 网络隔离。"""
    print("── 文件系统隔离验证 ──")

    # (a) 沙箱 VFS 根目录只含注入的 wheel，看不到宿主机 C:\ 等内容
    r = sandbox.execute("ls /")
    print("沙箱 VFS 根目录：")
    print(r.output)

    # (b) 沙箱内无法读取宿主机文件（VFS 中不存在 /etc/passwd）
    r = sandbox.execute("python3 -c \"open('/etc/passwd').read()\"")
    print(f"读取宿主机 /etc/passwd → exit_code={r.exit_code}（应非 0）")
    print(r.output)

    # (c) 网络完全隔离（allowed_hosts=[]，发起请求应被拦截）
    r = sandbox.execute(
        "python3 -c \"import urllib.request; urllib.request.urlopen('http://example.com')\""
    )
    print(f"发起外网请求 → exit_code={r.exit_code}（应非 0，被拦截）")
    print(r.output)


def main() -> None:
    # 1. 创建沙箱：注入离线 wheel，allowed_hosts=[] 表示完全离线、无 SSRF 风险
    preload = get_preload_files()
    sandbox = Sandbox(
        step_budget=100_000,       # VM 步数预算，限制 shell 命令的 VM 指令数
        allowed_hosts=[],          # 空列表 = 完全离线，无法发起任何网络请求
        working_directory="/",     # 工作目录统一为根路径，两端无需记忆前缀
        initial_files=preload,     # 注入 numpy/pandas/matplotlib/openpyxl 离线 wheel
    )
    print(f"✓ 沙箱已创建（预加载 {len(preload)} 个离线 wheel）")

    try:
        # 2. 安装离线 wheel（bootstrap 脚本用 zipfile 解压到 site-packages）
        sandbox.write("/bootstrap.py", BOOTSTRAP_SCRIPT)
        result = sandbox.execute("python3 /bootstrap.py")
        if result.exit_code != 0:
            raise RuntimeError(f"bootstrap 失败: {result.output}")
        print("✓ 离线依赖安装完成（numpy / pandas / matplotlib / openpyxl）")

        # 3. 验证宿主机 ↔ 执行机文件系统 / 网络隔离
        verify_isolation(sandbox)

        # 4. 上传 demo/session/ 下的 Excel 与脚本到沙箱 VFS
        sandbox.upload_files(
            [
                (EXCEL_PATH, (SESSION_DIR / "test.xlsx").read_bytes()),
                (SCRIPT_PATH, (SESSION_DIR / "convert.py").read_bytes()),
            ]
        )
        print("✓ test.xlsx 与 convert.py 已上传到沙箱")

        # 5. 在沙箱内执行 pandas 脚本（读取 Excel → 转换 CSV）
        result = sandbox.execute(f"python3 {SCRIPT_PATH}")
        if result.exit_code != 0:
            raise RuntimeError(f"脚本执行失败: {result.output}")
        print("── 沙箱内执行输出 ──")
        print(result.output)

        # 6. 下载生成的 CSV 回 demo/session/
        csv_path, csv_bytes = sandbox.download_files([CSV_PATH])[0]
        if csv_bytes is None:
            raise RuntimeError(f"下载失败: {csv_path}")
        (SESSION_DIR / "output.csv").write_bytes(csv_bytes)
        print(f"✓ CSV 已下载到 {SESSION_DIR / 'output.csv'}")
        print("── CSV 内容 ──")
        print(csv_bytes.decode("utf-8"))
    finally:
        # 7. 关闭沙箱，终止 Node.js 子进程
        sandbox.close()
        print("✓ 沙箱已关闭")


if __name__ == "__main__":
    main()
