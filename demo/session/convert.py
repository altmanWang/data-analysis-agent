"""沙箱内执行的 Python 脚本：使用 pandas 将 Excel 转换为 CSV。

该脚本由 ``demo/run_sandbox_demo.py`` 通过 WasmshSandbox 上传并执行，
运行在隔离的 Pyodide（CPython 3.13）环境中。所有路径均为沙箱 VFS 根目录，
与宿主机 ``demo/session/`` 目录一一对应。

注意：Windows 下 wasmsh 子进程以 GBK 解码输出，脚本内 print 请使用 ASCII 字符，
否则会触发 UnicodeDecodeError（详见 run_sandbox_demo.py 顶部的说明）。
"""
import pandas as pd

# 输入 Excel 与输出 CSV 均位于沙箱 VFS 根目录
INPUT_EXCEL = "/test.xlsx"
OUTPUT_CSV = "/output.csv"

df = pd.read_excel(INPUT_EXCEL)
print(f"Read {INPUT_EXCEL}: {df.shape[0]} rows x {df.shape[1]} cols")
print(df.to_string())

df.to_csv(OUTPUT_CSV, index=False)
print(f"Wrote {OUTPUT_CSV}")
