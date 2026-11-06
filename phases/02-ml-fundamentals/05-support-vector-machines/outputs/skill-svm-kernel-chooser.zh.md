---
name: skill-svm-kernel-chooser
description: Choose the right SVM kernel and tune C and gamma for your problem
version: 1.0.0
phase: 2
lesson: 5
tags: [svm, kernel, classification, hyperparameter-tuning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="svm-kernel-selection-guide"></a>

# SVM 内核选择指南

SVM 由两个选择定义：内核（决定决策边界的形状）和正则化 parameters（控制间隔宽度和分类误差之间的权衡）。正确处理这些问题是无用模型和强大模型之间的区别。

<a id="decision-checklist"></a>

## 决策清单

1. 数据是否线性可分（或接近线性可分）？
   - 是的：使用线性内核。它更快、更容易解释。
   - 否：转至步骤 2。

2. 有多少个 features 与样本？
   - Features >> 样本（例如，带有 TF-IDF 的文本）：使用线性内核。高维数据通常是线性可分的。 RBF 增加了复杂性却没有任何好处。
   - 示例 >> features（例如，具有 10-50 features 的表格数据）：RBF 内核是默认选择。

3. 决策边界是否预计是平滑的？
   - 平滑、连续的边界：RBF 核
   - 多项式形边界：多项式核（从 2 或 3 次开始）
   - 领域知识建议特定的交互项：具有匹配度的多项式核

4. 数据集有多大？
   - 10,000 个样本以下：任何内核都可以工作，RBF 是安全的默认值
   - 10,000 到 100,000：线性内核或 LinearSVC（原始公式，O(n) 根据 epoch）
   - 超过 100,000：不使用内核 SVM。切换到线性 SVM、gradient boosting 或神经网络。

5. 您缩放了 features 吗？
   - SVM 需要 feature 缩放。在拟合之前始终进行标准化（零均值，单位方差）。未缩放的 features 会扭曲边距几何形状。

<a id="kernel-selection-flowchart"></a>

## 内核选择流程图

```
Start
  |
  v
Features > 1000 or features >> samples?
  Yes --> Linear kernel (LinearSVC for speed)
  No  --> Dataset < 10k samples?
            Yes --> Try RBF first (best general-purpose kernel)
            No  --> Linear kernel (kernel SVMs are O(n^2) to O(n^3))
```

如果 RBF 效果不好，请尝试 2-3 次多项式。如果失败，则该问题可能不适合 SVM。

<a id="tuning-c-regularization"></a>

## 调整C（正则化）

C 控制错误分类的惩罚。它与正则化强度成反比。

| C值 | 效果 | 何时使用 |
|---------|--------|-------------|
| 0.001 - 0.01 | 差距较大，允许许多违规行为 | 噪声数据，需要泛化 |
| 0.1 - 1.0 | 平衡 | 良好的起始范围 |
| 10 - 1000 | 利润微薄，违法行为少 | 数据干净，准确度要求高 |

调优策略：
- 从 C=1.0 开始
- 以对数刻度搜索：[0.001, 0.01, 0.1, 1, 10, 100, 1000]
- 使用交叉验证来选择最佳值
- 如果最佳 C 位于范围的边缘，则朝该方向扩展范围

<a id="tuning-gamma-rbf-kernel"></a>

## 调整伽玛（RBF 内核）

Gamma控制单个训练点的影响力达到多远。它定义了高斯的宽度。

| 伽玛值 | 效果 | 何时使用 |
|-------------|--------|-------------|
| 小 (0.001) | 每个点都会影响一个大区域。平滑、简单的边界 | Underfitting 或几个 features |
| 中（自动：1/n_features） | sklearn默认。合理的出发点 | 一般用途 |
| 大号（10+） | 每个点仅影响附近的点。复杂、摇摆的边界 | overfitting的风险 |

调优策略：
- 从 gamma="scale" 开始（1 / (n_features * X.var())，sklearn 默认值）
- 以对数刻度搜索：[0.001, 0.01, 0.1, 1, 10]
- 低 gamma + 高 C 容易过度拟合
- 高 gamma + 低 C 往往会欠拟合

<a id="joint-c-and-gamma-tuning"></a>

## 联合 C 和伽玛调谐

C和伽马相互作用。始终将它们一起调整，而不是单独调整。

推荐方法：
1. 粗网格搜索：C在[0.01, 0.1, 1, 10, 100]，gamma在[0.001, 0.01, 0.1, 1, 10] （25 连击）
2. 寻找最佳区域
3. 围绕最佳区域进行精细网格搜索（例如 [5, 10, 20, 50] 中的 C，[0.05, 0.1, 0.2] 中的 gamma）
4. 全程使用 5 倍交叉验证

<a id="common-mistakes"></a>

## 常见错误

- 在高维稀疏数据上使用 RBF 核（线性更好，速度快 100 倍）
- 忘记缩放 features（最常见的 SVM 错误）
- 在噪声数据上将 C 设置得太高（记住噪声而不是学习边界）
- 在超过 50k 样本的数据集上使用内核 SVM（训练时间令人望而却步）
- 不一起调整 C 和 gamma（它们相互补偿）
- 默认多项式次数为 5+（过度拟合，首先尝试 2 或 3）

<a id="quick-reference"></a>

## 快速参考

| 内核 | 何时使用 | 密钥 parameters | 训练复杂性 |
|--------|------------|----------------|-------------------|
| 线性 | Text/TF-IDF，很多features，大数据 | 仅 C | O(n) 根据 epoch |
| 径向基函数 | 通用，10k 样本以下 | C、伽玛 | O(n^2) 到 O(n^3) |
| 多项式 | 已知多项式关系 | C，度，coef0 | O(n^2) 到 O(n^3) |
| Sigmoid | 很少有用（相当于两层神经网络） | C、伽玛、coef0 | O(n^2) 到 O(n^3) |
