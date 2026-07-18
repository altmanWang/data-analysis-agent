# backend/tools/data_tools.py
"""数据分析自定义工具：CSV/Excel 读取、Python 代码执行"""

import json
import io
import os
import traceback
import pandas as pd
from langchain.tools import tool


def create_data_tools(worktree_root: str):
    """创建绑定到特定工作空间的工具（闭包捕获 worktree_root）"""

    def _resolve_path(file_path: str) -> str:
        """解析文件路径，自动去掉重复的 sandboxes 前缀"""
        clean = file_path.lstrip("/")
        # 如果路径包含 sandboxes/ 前缀，说明 LLM 传了完整虚拟路径，去掉重复部分
        parts = clean.replace("\\", "/").split("/")
        if "sandboxes" in parts:
            idx = len(parts)
            for i, p in enumerate(parts):
                if p == "sandboxes" and i + 1 < len(parts):
                    idx = i + 2  # 跳过 sandboxes/{id}/
            clean = "/".join(parts[idx:]) if idx < len(parts) else clean
        return os.path.join(worktree_root, clean)

    @tool
    def load_csv(file_path: str, encoding: str = "utf-8") -> str:
        """加载 CSV 文件，返回列信息和前 20 行预览。

        Args:
            file_path: 文件路径，如 /sh600176.csv 或完整虚拟路径
            encoding: 文件编码，默认 utf-8
        """
        full_path = _resolve_path(file_path)
        df = pd.read_csv(full_path, encoding=encoding)
        info = {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(20).to_dict(orient="records"),
            "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
        }
        return json.dumps(info, ensure_ascii=False, default=str)

    @tool
    def load_excel(file_path: str, sheet_name: str = "0") -> str:
        """加载 Excel 文件，返回列信息和前 20 行预览。

        Args:
            file_path: 文件路径，如 /data.xlsx 或完整虚拟路径
            sheet_name: 表名或索引（0 表示第一个表）
        """
        full_path = _resolve_path(file_path)
        df = pd.read_excel(full_path, sheet_name=sheet_name)
        info = {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(20).to_dict(orient="records"),
            "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
        }
        return json.dumps(info, ensure_ascii=False, default=str)

    @tool
    def execute_python(code: str) -> str:
        """执行 Python 数据分析代码并返回输出。

        可用库: pandas (pd), numpy (np), matplotlib (plt), json, os, io, base64
        pd.read_csv() / pd.read_excel() 自动拼接工作空间路径，直接用即可
        保存图表到 worktree_root 下: plt.savefig(os.path.join(worktree_root, 'reports', 'xxx.png'))
        HTML 报告中的图表用 base64 内嵌: io.BytesIO() + base64.b64encode() + <img src="data:image/png;base64,...">

        Args:
            code: Python 代码字符串，print() 输出会被捕获返回
        """
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        def _read_csv(filepath, **kwargs):
            return pd.read_csv(_resolve_path(filepath), **kwargs)
        def _read_excel(filepath, **kwargs):
            return pd.read_excel(_resolve_path(filepath), **kwargs)

        # pd 代理：read_csv/read_excel 自动解析路径，其余方法透传到真实 pandas
        class _PdProxy:
            def read_csv(self, filepath, **kwargs):
                return pd.read_csv(_resolve_path(filepath), **kwargs)
            def read_excel(self, filepath, **kwargs):
                return pd.read_excel(_resolve_path(filepath), **kwargs)
            def __getattr__(self, name):
                return getattr(pd, name)

        namespace = {
            "pd": _PdProxy(),
            "np": np,
            "plt": plt,
            "json": json,
            "os": os,
            "io": __import__("io"),
            "base64": __import__("base64"),
            "worktree_root": worktree_root,
            "read_csv": _read_csv,
            "read_excel": _read_excel,
        }

        stdout_capture = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = stdout_capture

        # 拦截 import pandas：agent 代码中的 import pandas as pd 会用 sys.modules
        # 里的真实模块覆盖 namespace['pd']，注入代理确保 import 返回我们的代理
        _real_pandas = sys.modules.get("pandas")
        sys.modules["pandas"] = _PdProxy()

        try:
            exec(code, namespace)
            output = stdout_capture.getvalue()
            return output if output else "代码执行成功，无 print 输出"
        except Exception as e:
            return f"执行错误: {str(e)}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
            # 恢复真实 pandas 模块
            if _real_pandas is not None:
                sys.modules["pandas"] = _real_pandas
            elif "pandas" in sys.modules:
                del sys.modules["pandas"]

    return load_csv, load_excel, execute_python
