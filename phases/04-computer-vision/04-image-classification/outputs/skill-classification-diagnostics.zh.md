---
name: skill-classification-diagnostics
description: Given a confusion matrix and class names, surface per-class failures and propose the single most impactful fix
version: 1.0.0
phase: 4
lesson: 4
tags: [computer-vision, classification, evaluation, debugging]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="classification-diagnostics"></a>

# 分类诊断

混淆矩阵的读取透镜。聚合准确度告诉您分类器是否有效。混淆矩阵告诉你 * 它还不知道什么*。

<a id="when-to-use"></a>

## 何时使用

- 首先看一下经过训练的分类器的验证性能。
- 在训练之间决定下一步要改变什么。
- 在交付模型之前：验证没有关键类默默地失败。
- 调试生产回归时，整体准确度下降了一个点，您需要知道原因。

<a id="inputs"></a>

## 输入

- `cm`：CxC 混淆矩阵（行 = true，列 = 预测）。
- `labels`：C类名称列表，顺序相同。
- 可选 `class_priors`：每类训练频率（默认为 `cm` 的行总和）。

<a id="steps"></a>

## 步骤

1. **计算每个类的度量。** 将任何除以零的度量视为该类未定义的度量，并将其报告为 `n/a`；切勿默默地用 0 替换。
   - precision_i = cm[i,i] / sum(cm[:, i]) （当从未预测该类时未定义）
   - call_i = cm[i,i] / sum(cm[i, :]) （当类没有真实样本时未定义）
   - f1_i = 2 * p * r / (p + r) （当任一分量未定义时，未定义）

2. ** 按 F1 排名最多三个最差类别**。如果混淆矩阵的类别少于三个，则对存在的类别进行排名。排除所有指标未定义的类。

3. ** 查找每行顶部的非对角单元格 ** — 最常从此类中窃取的一个类。报告为 `true -> predicted`。

4. ** 对每个最坏类别的故障模式进行分类**。使用这些定量阈值使标签具有可重复性：
   - `ambiguity` — 与另一个类双向混淆：`cm[i,j] / sum(cm[i, :]) >= 0.15` 和 `cm[j,i] / sum(cm[j, :]) >= 0.15`。
   - `imbalance` — 该班级的最高混淆者的训练计数为 `< 0.5x`。
   - `label_noise` — `|precision_i - recall_i| >= 0.2` 并且该类不在不平衡/模糊路径上。
   - `systematic` — 没有任何一个混淆器超过此类错误的 0.2 份额；错误分布在三个或更多其他类别中。

5. **推荐最具影响力的下一步行动**：
   - `ambiguity` -> 收集或合成有区别的示例，添加有针对性的增强以保留区别性的 feature。
   - `imbalance` -> 对少数类别进行过采样或应用类别加权损失。
   - `label_noise` -> 审核班级的分层样本；在进行任何其他更改之前修复错误标签。
   - `systematic` -> 增加该类的数据或使用更高的 weight 对该类的损失进行微调。

<a id="report"></a>

## 报告

```
[diagnostics]
  aggregate accuracy: X.XX
  macro F1:           X.XX

[top-3 worst classes]
  1. class <name>  F1 = X.XX  prec = X.XX  rec = X.XX
     top confusion: <name> -> <other>  (N cases)
     failure mode:  ambiguity | imbalance | label_noise | systematic
     action:        <one sentence>

  2. ...
  3. ...

[recommendation]
  single biggest lever: <one sentence naming the class and the fix>
```

<a id="rules"></a>

## 规则

- 最多返回三类。更多隐藏信号。
- 列出每个最差类别的主要混淆者；永远不要概括为“与许多人混淆”。
- 将每项建议都建立在混淆矩阵证据中。如果不指定哪个类，就没有通用的“添加更多数据”。
- 当精度和召回率不一致超过 0.2 时，始终将标签噪声标记为候选者 - 真实的类通常在训练后对齐 P 和 R。
