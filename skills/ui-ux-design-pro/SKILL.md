---
name: ui-ux-design-pro
description: |
  当生成 HTML 分析报告时使用此技能。提供专业的数据分析报告设计规范，
  包括配色方案、排版、图表集成、响应式布局。
---

# 数据分析报告设计规范

## 设计原则
- 专业简洁：去除多余装饰，突出数据
- 信息层次：标题 -> KPI 卡片 -> 图表 -> 详细表格
- 可读性优先：字体 14-16px，行高 1.6

## 配色方案
| 用途       | 色值     |
|-----------|---------|
| 主色       | #1a365d |
| 强调色     | #e53e3e |
| 成功/增长  | #38a169 |
| 背景       | #f7fafc |
| 卡片       | #ffffff |

## 报告结构模板
参考 /skills/ui-ux-design-pro/templates/ 目录下的模板文件。
- dashboard.html: 仪表盘风格，适合概览
- executive.html: 高管摘要，简洁一页
- detailed.html: 详细分析，含交互式图表

## 图表集成
使用 Chart.js CDN 嵌入交互式图表：
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
