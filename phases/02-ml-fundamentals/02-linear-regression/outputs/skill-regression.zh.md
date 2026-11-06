---
name: skill-regression
description: Choose the right regression approach based on data characteristics and problem constraints
version: 1.0.0
phase: 2
lesson: 2
tags: [regression, linear-regression, polynomial-regression, ridge, regularization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="regression-strategy-guide"></a>

# 回归策略指南

回归预测连续值。正确的做法取决于features与目标之间的关系、features的数量以及overfitting的风险。

<a id="decision-checklist"></a>

## 决策清单

1. features 与目标之间的关系近似线性吗？
   - 是：从普通线性回归开始
   - 否：尝试多项式 features 或非线性模型

2. 您有多少个与样品相关的features？
   - features 很少，样本很多：普通线性回归效果很好
   - 许多 features，少量样本：使用正则化（Ridge 或 Lasso）
   - features 比样本更多：套索 (L1) 选择 features，或脊 (L2) 缩小所有 weights

3. 您需要可解释性吗？
   - 是：使用少量 features 进行线性回归，或用于自动选择 feature 的 Lasso
   - 否：多项式 features，或转向基于树的模型或神经网络

4. 您的数据集很小（少于 10,000 行）吗？
   - 使用正规方程（封闭式解）计算速度
   - 交叉验证对于可靠至关重要 evaluation

5. 您的数据集很大（数百万行）吗？
   - 使用 stochastic gradient descent (SGD) 或小批量 gradient descent
   - 由于 O(n^3) 矩阵求逆，正规方程太慢

<a id="when-to-use-each-approach"></a>

## 何时使用每种方法

**普通线性回归**：任何回归任务的基线。从这里开始。如果 R 方可以接受并且模型很简单，则到此为止。

**多项式回归**：散点图显示的是曲线，而不是直线。从 2 级开始。仅当验证性能合理时才增加。度数 > 5 几乎总是过拟合。

**岭回归（L2）**：许多相关的features。所有 weights 都向零收缩，但没有一个完全为零。当您相信所有 features 的贡献时，这很好。

**Lasso 回归 (L1)**：很多 features 而您怀疑只有少数几个重要。 Lasso 将不相关的 feature weights 精确地驱动为零，执行自动 feature 选择。

**Elastic Net**：结合了L1和L2惩罚。当您有许多相关的 features 并想要一些 feature 选择时使用。

<a id="common-mistakes"></a>

## 常见错误

- 在 gradient descent 之前跳过 feature 缩放（收敛变得非常慢）
- 使用测试集性能调优 hyperparameters（使用验证集或交叉验证）
- 拟合高次多项式而不检查验证误差（训练 R^2 总是随次数增加）
- 忽略残差图（如果残差显示模式，R^2 可能会产生误导）
- 将 R^2 视为唯一指标（检查残差分布、MAE 和特定于域的阈值）

<a id="quick-reference"></a>

## 快速参考

| 方法 | 何时使用 | 正则化 | Feature选择 |
|--------|------------|---------------|-------------------|
| 最小二乘法 | 基线，几features | 无 | 手册 |
| 山脊 | 很多features，全部相关 | L2（收缩） | 否 |
| 套索 | 很多features，相关的很少 | L1（清零） | 自动 |
| 弹性网 | 许多相关features | L1 + L2 | 部分 |
| 多项式 | 非线性关系 | 在顶部添加山脊/套索 | 手动度数选择 |
