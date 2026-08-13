"""Wasmsh 沙箱使用示例：在隔离的 Pyodide 环境中执行 pandas 脚本，将 Excel 转为 CSV。

演示了 sandbox 功能的完整生命周期：

  1. 复用 ``backend/sandbox`` 的离线 wheel 预加载（numpy / pandas / matplotlib / openpyxl）
  2. 创建 ``WasmshSandbox``（WASM 级 Python 执行沙箱，完全离线）
  3. 将 ``demo/session/`` 下的 ``test.xlsx`` 与 ``convert.py`` 上传到沙箱 VFS
  4. 在沙箱内执行 ``convert.py``（pandas 读取 Excel → 写出 CSV）
  5. 将生成的 ``output.csv`` 下载回 ``demo/session/``
  6. 关闭沙箱，释放 Node.js 子进程

运行方式（项目根目录）:

    python demo/run_sandbox_demo.py

前置条件:

    - Node.js >= 20（沙箱由 Node.js 子进程承载，每个沙箱一个子进程）
    - 已安装依赖 ``langchain-wasmsh>=0.7.0``（见 requirements.txt）

Windows 注意事项:

    langchain-wasmsh 通过 ``subprocess.Popen(text=True)`` 启动 Node 子进程，
    在 Windows 上默认用 GBK 解码子进程输出。因此沙箱内脚本（convert.py）
    的 print 输出必须为 ASCII，否则会触发 UnicodeDecodeError。本脚本自身已
    将 stdout 强制为 UTF-8，不影响该限制。
"""
import sys
from pathlib import Path

# 强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台对 ✓ 等字符报 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── 路径准备 ──────────────────────────────────────────────────────────────
DEMO_DIR = Path(__file__).resolve().parent        # demo/
SESSION_DIR = DEMO_DIR / "session"                # demo/session/
PROJECT_ROOT = DEMO_DIR.parent                    # 项目根目录
sys.path.insert(0, str(PROJECT_ROOT / "backend"))  # 使 demo 复用 backend/sandbox

from langchain_wasmsh import WasmshSandbox          # noqa: E402
from sandbox import get_preload_files, BOOTSTRAP_SCRIPT  # noqa: E402

# 沙箱内文件路径（与项目约定一致：两端统一使用根路径）
EXCEL_PATH = "/test.xlsx"     # 输入 Excel（宿主端 demo/session/test.xlsx）
SCRIPT_PATH = "/convert.py"   # 沙箱内执行的 Python 脚本（宿主端 demo/session/convert.py）
CSV_PATH = "/output.csv"      # 输出 CSV（宿主端 demo/session/output.csv）


def main() -> None:
    # 1. 创建沙箱：注入离线 wheel，allowed_hosts=[] 表示完全离线、无 SSRF 风险
    preload = get_preload_files()
    sandbox = WasmshSandbox(
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

        # 3. 上传 demo/session/ 下的 Excel 与脚本到沙箱 VFS
        uploads = [
            (EXCEL_PATH, (SESSION_DIR / "test.xlsx").read_bytes()),
            (SCRIPT_PATH, (SESSION_DIR / "convert.py").read_bytes()),
        ]
        for resp in sandbox.upload_files(uploads):
            if resp.error:
                raise RuntimeError(f"上传失败 {resp.path}: {resp.error}")
        print("✓ test.xlsx 与 convert.py 已上传到沙箱")

        # 4. 在沙箱内执行 pandas 脚本（读取 Excel → 转换 CSV）
        result = sandbox.execute(f"python3 {SCRIPT_PATH}")
        if result.exit_code != 0:
            raise RuntimeError(f"脚本执行失败: {result.output}")
        print("── 沙箱内执行输出 ──")
        print(result.output)

        # 5. 下载生成的 CSV 回 demo/session/
        resp = sandbox.download_files([CSV_PATH])[0]
        if resp.error or resp.content is None:
            raise RuntimeError(f"下载失败: {resp.error}")
        (SESSION_DIR / "output.csv").write_bytes(resp.content)
        print(f"✓ CSV 已下载到 {SESSION_DIR / 'output.csv'}")
        print("── CSV 内容 ──")
        print(resp.content.decode("utf-8"))
    finally:
        # 6. 关闭沙箱，终止 Node.js 子进程
        sandbox.close()
        print("✓ 沙箱已关闭")


if __name__ == "__main__":
    main()
