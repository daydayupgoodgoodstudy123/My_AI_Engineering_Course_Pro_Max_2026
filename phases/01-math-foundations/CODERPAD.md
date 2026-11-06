# 01-math-foundations：CoderPad 练习

本章 22 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Linear Algebra Intuition](01-linear-algebra-intuition/coderpad/README.md) | 向量内积 | L2 归一化 |
| 02 | [Vectors, Matrices & Operations](02-vectors-matrices-operations/coderpad/README.md) | 矩阵乘法 | 矩阵转置 |
| 03 | [Matrix Transformations](03-matrix-transformations/coderpad/README.md) | 二维仿射变换 | 2×2 实特征值 |
| 04 | [Calculus for Machine Learning](04-calculus-for-ml/coderpad/README.md) | 多项式求导与链式法则 | 数值梯度 |
| 05 | [Chain Rule & Automatic Differentiation](05-chain-rule-and-autodiff/coderpad/README.md) | 数值梯度 | 梯度下降一步更新 |
| 06 | [Probability and Distributions](06-probability-and-distributions/coderpad/README.md) | 逆 CDF 抽样 | 概率分布熵 |
| 07 | [Bayes' Theorem](07-bayes-theorem/coderpad/README.md) | 贝叶斯更新 | 分类混淆矩阵指标 |
| 08 | [Optimization](08-optimization/coderpad/README.md) | 梯度下降一步更新 | 梯度范数裁剪 |
| 09 | [Information Theory](09-information-theory/coderpad/README.md) | 概率分布熵 | 分类交叉熵 |
| 10 | [Dimensionality Reduction](10-dimensionality-reduction/coderpad/README.md) | 2×2 实特征值 | 训练统计量与变换 |
| 11 | [Singular Value Decomposition](11-singular-value-decomposition/coderpad/README.md) | 2×2 实特征值 | 2×2 线性方程 |
| 12 | [Tensor Operations](12-tensor-operations/coderpad/README.md) | 矩阵转置 | 模型参数与内存估算 |
| 13 | [Numerical Stability](13-numerical-stability/coderpad/README.md) | 数值稳定的 Softmax | 稳定 LogSumExp |
| 14 | [Norms and Distances](14-norms-and-distances/coderpad/README.md) | 距离与形状校验 | Embedding 余弦相似度 |
| 15 | [Statistics for Machine Learning](15-statistics-for-ml/coderpad/README.md) | 均值与总体方差 | Expected Calibration Error |
| 16 | [Sampling Methods](16-sampling-methods/coderpad/README.md) | 逆 CDF 抽样 | 马尔可夫状态分布 |
| 17 | [Linear Systems](17-linear-systems/coderpad/README.md) | 2×2 线性方程 | 矩阵乘法 |
| 18 | [Convex Optimization](18-convex-optimization/coderpad/README.md) | 2×2 实特征值 | 数值梯度 |
| 19 | [Complex Numbers for AI](19-complex-numbers/coderpad/README.md) | 离散傅里叶变换 | 二维仿射变换 |
| 20 | [The Fourier Transform](20-fourier-transform/coderpad/README.md) | 离散傅里叶变换 | 音频分帧 |
| 21 | [Graph Theory for Machine Learning](21-graph-theory/coderpad/README.md) | 最短路径搜索 | 依赖计划拓扑排序 |
| 22 | [Stochastic Processes](22-stochastic-processes/coderpad/README.md) | 马尔可夫状态分布 | 折扣回报 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
