---
name: skill-imbalanced-data
description: Decision checklist for handling imbalanced classification problems
version: 1.0.0
phase: 2
lesson: 17
tags: [imbalanced-data, smote, class-weights, threshold-tuning, evaluation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="imbalanced-data-strategy"></a>

# 不平衡的数据策略

用于处理不平衡分类的决策清单。按照此顺序为您的问题选择正确的方法。

<a id="step-1-measure-the-imbalance"></a>

## 第 1 步：测量不平衡度

- 计算每类的样本数
- 计算不平衡比率（多数/少数）
- 轻度：比例 < 3:1（例如 70/30）
- 中等：比例为 3:1 至 20:1（例如 95/5）
- 严重：比率 > 20:1（例如 99/1）

<a id="step-2-pick-the-right-metric"></a>

## 第 2 步：选择正确的指标

对于不平衡的数据集，更喜欢精确率/召回率/F1 而不是准确性。根据您的问题选择：

| 情况 | 主要指标 | 次要指标 |
|-----------|---------------|-----------------|
| 缺失阳性结果的代价非常高昂（欺诈、疾病） | 召回 | F2分数 |
| 误报代价高昂（垃圾邮件过滤器、建议） | 精度 | F0.5分数 |
| 两者的重要性大致相同 | F1成绩 | 中冶集团 |
| 需要一个单一的排名指标 | 澳大利亚UPRC | AUC-ROC |
| 需要跨数据集进行比较 | 中冶集团 | 澳大利亚UPRC |

<a id="step-3-choose-a-rebalancing-strategy"></a>

## 第 3 步：选择再平衡策略

<a id="by-imbalance-severity"></a>

### 按不平衡严重程度

| 不平衡 | 第一次尝试 | 第二次尝试 | 避免 |
|-----------|-----------|------------|-------|
| 轻度（< 3:1） | 类别 weights | 阈值调整 | 过采样（不必要） |
| 中等（3:1 至 20:1） | SMOTE + 类 weights | 顶部阈值调整 | 欠采样（数据丢失过多） |
| 严重 (> 20:1) | SMOTE + 类 weights + 阈值 | 具有平衡装袋的合奏 | 单独欠采样 |

<a id="by-dataset-size"></a>

### 按数据集大小

| 数据集大小 | 首选策略 | 原因 |
|-------------|-------------------|--------|
| < 1,000 个样本 | 过采样或 SMOTE | 无法承受丢失大部分数据的损失 |
| 1,000 - 10,000 | SMOTE + 阈值调整 | 足够的少数样本用于 k-NN |
| > 10,000 | weights 类或欠采样 | 快速、充足的少数群体数据 |

<a id="step-4-apply-the-technique"></a>

## 第四步：应用该技术

<a id="class-weights-always-try-first"></a>

### 类 weights （始终先尝试）
- 在sklearn中：`class_weight='balanced'`
- 无需修改数据
- 适用于任何基于损失的模型
- 相当于期望中的过采样

<a id="smote"></a>

### 斯莫特
- 仅适用于训练数据（从不测试/验证）
- 使用 k=5 个邻居（默认）
- 与 weights 类结合以获得最佳效果
- 留意边界附近的噪声合成点

<a id="threshold-tuning"></a>

### 阈值调整
- 训练模型，获得验证集的预测概率
- 扫描阈值从 0.05 到 0.95
- 选择最大化您选择的指标的阈值
- 始终调整验证数据，而不是测试数据

<a id="step-5-validate-properly"></a>

## 第 5 步：正确验证

- 使用分层交叉验证（保留每次折叠中的类别比率）
- 报告原始（未重新采样）测试集的指标
- 切勿在分割前应用 SMOTE——仅在训练折叠时应用
- 与“始终预测多数”基线进行比较

<a id="step-6-common-mistakes-to-avoid"></a>

## 第 6 步：要避免的常见错误

- 在训练/测试分割之前将 SMOTE 应用于整个数据集 (data leakage)
- 使用准确度作为 evaluation 指标
- 不首先尝试类 weights （最简单的方法，通常就足够了）
- 过采样然后交叉验证（合成点跨折叠泄漏）
- 忽略阈值调整（自由性能，无需重新训练）
- 对小数据集使用随机欠采样（丢弃太多数据）

<a id="quick-decision-tree"></a>

## 快速决策树

1. 不平衡比是否< 3:1？ -> 仅尝试类 weights
2. 数据集是否超过 10,000 个样本？ -> weights 类 + 阈值调整
3. 数据集是否少于 1,000 个样本？ -> SMOTE + 类 weights
4. 否则 -> SMOTE + 类 weights + 阈值调整
5. 还是不够好？ -> 平衡装袋整体
