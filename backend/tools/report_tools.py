# backend/tools/report_tools.py
"""报告生成工具：HTML/MD 报告写入磁盘"""

import os
from langchain.tools import tool


def create_report_tools(worktree_root: str):
    """创建绑定到特定工作空间的报告工具（闭包捕获 worktree_root）"""

    @tool
    def generate_report(content: str, filename: str) -> str:
        """生成分析报告文件到 /reports/ 目录。

        HTML 报告必须自包含，图表用 base64 内嵌（在 execute_python 中生成 base64 字符串后传入此工具）。
        不要引用外部 png 文件。

        Args:
            content: 报告内容（HTML 字符串或 Markdown 文本）
            filename: 文件名，如 analysis_report.html 或 report.md
        """
        full_path = os.path.join(worktree_root, "reports", filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"报告已生成: /reports/{filename}"

    return generate_report
