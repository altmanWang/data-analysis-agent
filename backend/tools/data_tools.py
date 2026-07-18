# backend/tools/data_tools.py
"""数据分析自定义工具：CSV/Excel 读取、Python 代码执行"""

import json
import io
import os
import traceback
import contextvars
import pandas as pd
from langchain.tools import tool

# 使用 contextvars 注入 worktree_root，无需 LLM 感知此参数
_worktree_root_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "worktree_root", default=""
)


def set_worktree_root(root: str) -> None:
    """设置当前上下文的 worktree 根目录"""
    _worktree_root_ctx.set(root)


@tool
def load_csv(file_path: str, encoding: str = "utf-8") -> str:
    """加载 CSV 文件，返回列信息和前 20 行预览。

    Args:
        file_path: 相对于 worktree 的路径，如 /sh600176.csv
        encoding: 文件编码，默认 utf-8
    """
    worktree_root = _worktree_root_ctx.get()
    full_path = os.path.join(worktree_root, file_path.lstrip("/"))
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
        file_path: 相对于 worktree 的路径
        sheet_name: 表名或索引（0 表示第一个表）
    """
    worktree_root = _worktree_root_ctx.get()
    full_path = os.path.join(worktree_root, file_path.lstrip("/"))
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

    可用库: pandas (pd), numpy (np), matplotlib (plt), json

    文件路径使用方式:
        worktree_root = __import__('tools.data_tools', fromlist=['_worktree_root_ctx'])._worktree_root_ctx.get()
        # 或直接用相对路径如 'sh600176.csv'

    Args:
        code: Python 代码字符串，print() 输出会被捕获返回
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    worktree_root = _worktree_root_ctx.get()

    namespace = {
        "pd": pd,
        "np": np,
        "plt": plt,
        "json": json,
        "worktree_root": worktree_root,
    }

    stdout_capture = io.StringIO()
    import sys
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    try:
        exec(code, namespace)
        output = stdout_capture.getvalue()
        return output if output else "代码执行成功，无 print 输出"
    except Exception as e:
        return f"执行错误: {str(e)}\n{traceback.format_exc()}"
    finally:
        sys.stdout = old_stdout
