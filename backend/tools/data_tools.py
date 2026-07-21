# backend/tools/data_tools.py
"""数据分析自定义工具：CSV/Excel 读取"""

import json
import os
import pandas as pd
from langchain.tools import tool

_PAGE_SIZE = 20
"""数据预览每页行数"""


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
    def load_csv(file_path: str, encoding: str = "utf-8", offset: int = 0) -> str:
        """加载 CSV 文件，返回列信息和分页预览数据（每页 20 行）。

        Args:
            file_path: 文件路径，如 /sh600176.csv 或完整虚拟路径
            encoding: 文件编码，默认 utf-8
            offset:   数据偏移量，默认 0，每页返回 20 行
        """
        full_path = _resolve_path(file_path)
        df = pd.read_csv(full_path, encoding=encoding)
        total_rows = len(df)
        info = {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.iloc[offset:offset + _PAGE_SIZE].to_dict(orient="records"),
            "total_rows": total_rows,
            "offset": offset,
            "page_size": _PAGE_SIZE,
            "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
        }
        return json.dumps(info, ensure_ascii=False, default=str)

    @tool
    def load_excel(file_path: str, sheet_name: str = "0", offset: int = 0) -> str:
        """加载 Excel 文件，返回列信息和分页预览数据（每页 20 行）。

        Args:
            file_path:  文件路径，如 /data.xlsx 或完整虚拟路径
            sheet_name: 目标 Sheet 名称，默认 "0"（即第一个 sheet）；传入 Sheet 名称或索引
            offset:     数据偏移量，默认 0，每页返回 20 行
        """
        full_path = _resolve_path(file_path)
        try:
            sheet_name = int(sheet_name)
        except ValueError:
            pass
        df = pd.read_excel(full_path, sheet_name=sheet_name)
        total_rows = len(df)
        info = {
            "shape": list(df.shape),
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.iloc[offset:offset + _PAGE_SIZE].to_dict(orient="records"),
            "total_rows": total_rows,
            "offset": offset,
            "page_size": _PAGE_SIZE,
            "describe": json.loads(df.describe(include="all").to_json(force_ascii=False)),
        }
        return json.dumps(info, ensure_ascii=False, default=str)

    return load_csv, load_excel
