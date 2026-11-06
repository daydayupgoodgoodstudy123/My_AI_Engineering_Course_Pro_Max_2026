# 02-ml-fundamentals：CoderPad 练习

本章 18 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [What Is Machine Learning](01-what-is-machine-learning/coderpad/README.md) | 可复现数据划分 | 分类混淆矩阵指标 |
| 02 | [Linear Regression](02-linear-regression/coderpad/README.md) | 线性层前向 | 回归误差与形状 |
| 03 | [Logistic Regression](03-logistic-regression/coderpad/README.md) | 稳定 Sigmoid | 分类交叉熵 |
| 04 | [Decision Trees and Random Forests](04-decision-trees/coderpad/README.md) | 决策树分裂纯度 | 概率分布熵 |
| 05 | [Support Vector Machines](05-support-vector-machines/coderpad/README.md) | 距离与形状校验 | 确定性的最近邻 |
| 06 | [K-Nearest Neighbors and Distances](06-knn-and-distances/coderpad/README.md) | 确定性的最近邻 | 训练统计量与变换 |
| 07 | [Unsupervised Learning](07-unsupervised-learning/coderpad/README.md) | 向量量化最近码字 | 距离与形状校验 |
| 08 | [Feature Engineering & Selection](08-feature-engineering/coderpad/README.md) | 训练统计量与变换 | 词袋向量 |
| 09 | [Model Evaluation](09-model-evaluation/coderpad/README.md) | 分类混淆矩阵指标 | Expected Calibration Error |
| 10 | [Bias-Variance Tradeoff](10-bias-variance/coderpad/README.md) | 回归误差与形状 | 均值与总体方差 |
| 11 | [Ensemble Methods](11-ensemble-methods/coderpad/README.md) | 集成投票与并列 | 分类混淆矩阵指标 |
| 12 | [Hyperparameter Tuning](12-hyperparameter-tuning/coderpad/README.md) | 超参数网格与预算 | 稀疏路由 Top-K |
| 13 | [ML Pipelines](13-ml-pipelines/coderpad/README.md) | 训练统计量与变换 | 可复现数据划分 |
| 14 | [Naive Bayes](14-naive-bayes/coderpad/README.md) | 词袋向量 | 贝叶斯更新 |
| 15 | [Time Series Fundamentals](15-time-series/coderpad/README.md) | 时间序列滞后特征 | 回归误差与形状 |
| 16 | [Anomaly Detection](16-anomaly-detection/coderpad/README.md) | 阈值异常检测 | 均值与总体方差 |
| 17 | [Handling Imbalanced Data](17-imbalanced-data/coderpad/README.md) | 类别权重 | 分类混淆矩阵指标 |
| 18 | [Feature Selection](18-feature-selection/coderpad/README.md) | 训练统计量与变换 | 稀疏路由 Top-K |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
