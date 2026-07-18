---
name: data-analysis-guide
description: |
  数据分析方法论指南。当 agent 需要对数据进行统计分析时使用。
  包括描述性统计、相关性分析、趋势分析等方法。
---

# 数据分析方法论

## 分析流程
1. 数据概览：shape, columns, dtypes, missing values
2. 描述性统计：mean, median, std, quartiles
3. 数据清洗：处理缺失值、异常值、重复值
4. 探索性分析：分组聚合、交叉分析、相关性
5. 结论与建议

## 分析方法选择
| 场景             | 方法              | Python 示例                     |
|-----------------|-------------------|---------------------------------|
| 看分布           | describe + hist   | df.describe(); df.hist()        |
| 看趋势           | groupby + line    | df.groupby('date').sum().plot()|
| 看占比           | value_counts + pie| df['cat'].value_counts().plot.pie()|
| 看相关性         | corr + heatmap    | df.corr()                       |
| 找异常           | boxplot + IQR     | df.boxplot()                    |
