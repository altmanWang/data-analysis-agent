# backend/tools/report_tools.py
"""报告生成工具：HTML/MD 报告、图表"""

import os
from langchain.tools import tool


def create_report_tools(worktree_root: str):
    """创建绑定到特定工作空间的报告工具（闭包捕获 worktree_root）"""

    @tool
    def generate_report(content: str, filename: str) -> str:
        """生成分析报告文件到 /reports/ 目录。

        Args:
            content: 报告内容（HTML 字符串或 Markdown 文本）
            filename: 文件名，如 analysis_report.html 或 report.md
        """
        full_path = os.path.join(worktree_root, "reports", filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"报告已生成: /reports/{filename}"

    @tool
    def generate_chart(code: str, filename: str) -> str:
        """执行 matplotlib 代码并保存图表到 /reports/ 目录。

        Args:
            code: matplotlib 代码（无需 plt.show() 或 plt.savefig()）
            filename: 输出文件名，如 monthly_trend.png
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        namespace = {"plt": plt, "np": np, "pd": __import__("pandas")}

        try:
            exec(code, namespace)
            full_path = os.path.join(worktree_root, "reports", filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            plt.savefig(full_path, dpi=150, bbox_inches="tight")
            plt.close()
            return f"图表已生成: /reports/{filename}"
        except Exception as e:
            plt.close()
            return f"图表生成错误: {str(e)}"

    return generate_report, generate_chart
