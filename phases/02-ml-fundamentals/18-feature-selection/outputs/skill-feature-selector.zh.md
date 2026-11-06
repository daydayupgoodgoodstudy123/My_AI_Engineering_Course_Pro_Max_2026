---
name: skill-feature-selector
description: Quick reference decision tree for choosing the right feature selection method
version: 1.0.0
phase: 2
lesson: 18
tags: [feature-selection, mutual-information, rfe, lasso, tree-importance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="feature-selection-strategy"></a>

# Feature选型策略

选择和应用正确的 feature 选择方法的快速参考。

<a id="step-1-start-with-cleanup"></a>

## 第 1 步：从清理开始

在应用任何方法之前，删除明显无用的features：

- **Constant features**：方差 = 0。删除它们。
- **接近常数 features**：方差 < 0.01（或您的阈值）。删除它们。
- **重复 features**：相同的列。保留一个，删除rest。
- **ID 列**：每行唯一，不携带可概括的信息。删除它们。

这需要几秒钟的时间，并且可以消除杂乱的现实数据集中 10-30% 的 features。

<a id="step-2-choose-a-method-based-on-your-situation"></a>

## 第二步：根据自己的情况选择方法

<a id="quick-decision-tree"></a>

### 快速决策树

1. **< 50 features?** 从互信息排名开始。保留上K。
2. **50 - 500 features?** 如果使用线性模型，则首先使用方差阈值，然后使用 L1（套索），或者如果使用树，则使用树重要性。
3. **> 500 features?** 链式方法：方差阈值 -> 互信息过滤器（前 50%） -> 对幸存者进行 RFE。
4. **需要可解释性吗？** L1正则化为您提供精确的零/非零。树的重要性给出了排名分数。
5. **需要捕获非线性关系？** 相互信息或基于树的重要性。避免 L1（仅限线性）。
6. **需要feature交互吗？** RFE或基于树的重要性。过滤方法会错过交互。

<a id="method-reference"></a>

### 方法参考

| 方法 | 何时使用 | 何时避免 |
|--------|------------|---------------|
| 方差阈值 | 始终作为第一步 | 永远不要跳过这个 |
| 互信息 | 快速排名，非线性关系 | 当您需要feature交互检测时 |
| 射频E | 精挑细选，feature数量适中 | 非常昂贵的型号，> 1000 features |
| L1 / 套索 | 线性模型，快速嵌入选择 | 非线性问题，高度相关 features |
| 树的重要性 | 非线性关系，feature 交互 | 高基数偏置 features |
| 排列重要性 | 与模型无关的验证、最终检查 | 初始筛选速度太慢 |

<a id="step-3-validate-your-selection"></a>

## 第 3 步：验证您的选择

- 将选定的 features 与所有 features 的模型性能进行比较
- 使用交叉验证，而不是单个训练/测试分割
- 如果性能下降超过 1-2%，您可能已经删除了有用的 features
- 如果性能提高，则您已成功消除噪音

<a id="step-4-handle-common-pitfalls"></a>

## 第 4 步：处理常见陷阱

<a id="correlated-features"></a>

### 相关features
- L1 从相关组中任意选择一个，并将其他组归零
- 首先计算相关矩阵并决定保留哪些相关features
- 树的重要性在相关的 features 之间传播重要性

<a id="data-leakage"></a>

### Data leakage
- 仅在训练数据上拟合 feature 选择
- 对测试数据应用相同的选择
- 在交叉验证中，feature 选择必须发生在每个折叠内

<a id="overfitting-to-feature-selection"></a>

### Overfitting 至 feature 选择
- 迭代次数过多的 RFE 可能会过度拟合训练集
- 验证保留的数据，而不是用于选择的数据
- 使用稳定性选择（在子样本上重复）以获得更稳健的结果

<a id="step-5-production-checklist"></a>

## 第 5 步：生产清单

- [ ] 方差阈值用作第一个过滤器
- [ ] Feature 选择仅适用于训练数据
- [ ] 选定的 features 已记录（名称、使用的方法、分数）
- [ ] 性能比较：选定的 features 与所有 features
- [ ] 交叉验证，非单分割 evaluation
- [ ] Feature 选择集成到训练管道中（不手动完成）
- [ ] 对 feature 漂移进行适当监控（选定的 features 可能会变得过时）
