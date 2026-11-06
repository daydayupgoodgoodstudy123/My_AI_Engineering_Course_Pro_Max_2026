---
name: skill-classification-baseline
description: Establish a strong classification baseline before reaching for complex models
version: 1.0.0
phase: 2
lesson: 3
tags: [classification, logistic-regression, baseline, preprocessing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="classification-baseline-guide"></a>

# 分类基线指南

在尝试复杂模型之前，请使用逻辑回归建立基线。它可以在几秒钟内完成训练，产生概率，并且是完全可解释的。数量惊人的现实世界问题根本不需要更奇特的东西。

<a id="decision-checklist"></a>

## 决策清单

1. 决策边界可能是线性的吗？
   - 是的：逻辑回归可能就足够了
   - 否：您仍然希望将其作为衡量改进的基准

2. 您有多少个features？
   - 50 岁以下：标准逻辑回归效果很好
   - 50 到 10,000：添加 L2 正则化（Ridge）
   - 超过 10,000 个（例如 TF-IDF 文本 features）：使用 L1 正则化 (Lasso) 或 LinearSVC

3. 数据集是否不平衡？
   - 低于 5:1 比例：无需调整可能没问题
   - 5:1 到 50:1：在 sklearn 中使用 `class_weight="balanced"`
   - 超过 50:1：将类别权重与适当的指标（精确率、召回率或 F1）相结合

4. features 是否有不同的尺度？
   - 在逻辑回归之前始终进行标准化。它使用基于 gradient 的优化，并且未缩放的 features 收敛速度慢或扭曲决策边界。

5. 是否存在缺失值？
   - 拟合前进行插补。逻辑回归无法处理 NaNs。
   - 对数字列使用中值插补，对分类列使用众数。

<a id="when-logistic-regression-is-good-enough"></a>

## 当逻辑回归足够好时

- 具有大部分线性 feature 关系的二元分类
- 您需要概率输出（不仅仅是类标签）
- 需要可解释性（系数表示标准化后feature重要性方向和相对大小）
- 训练数据很小（数百到数千个样本）
- 您需要一个用于实时服务的快速模型（inference 的单点产品）
- 监管或合规要求需要可解释性

<a id="when-to-upgrade"></a>

## 何时升级

- 精度远低于目标，并且您已尝试 feature 工程
- features 和目标之间的关系明显是非线性的（检查残差图）
- 您有大量表格数据（10k+ 行）：尝试 gradient 提升（XGBoost 或 LightGBM）
- Features 具有多项式 features 无法捕获的复杂相互作用
- 您有图像、文本或序列数据：原始输入的逻辑回归不起作用

<a id="preprocessing-steps-for-a-classification-baseline"></a>

## 分类基线的预处理步骤

1. ** 在进行任何预处理之前，首先训练/测试拆分 **。这可以防止 data leakage。
2. **处理缺失值**：中位数插补数值，众数插补分类。
3. **Encode categoricals**：低基数（低于10个值）的one-hot，目标编码更高的基数。仅在训练折叠上拟合目标编码（使用折叠外编码以防止泄漏）。
4. **Scale numerics**：StandardScaler（零均值，单位方差）。适合火车，改造两者。
5. ** 使用 `C=1.0` 拟合逻辑回归 **（默认正则化）。
6. **Evaluate**：混淆矩阵、精确率、召回率、F1。不仅仅是准确性。
7. **调整阈值**：默认0.5很少是最佳的。扫描 0.1 到 0.9，然后选择与您的精确度/召回率优先级相匹配的阈值。

<a id="common-mistakes"></a>

## 常见错误

- 仅评估不平衡数据的准确性（预测多数类别得分高但无用的模型）
- 忘记缩放 features（未缩放 features 的逻辑回归训练缓慢并收敛到更差的解决方案）
- 使用测试集调整决策阈值（使用验证或交叉验证）
- 跳过基线并直接跳到 XGBoost（你失去了可解释性并且没有参考点）
- 不检查多重共线性（高度相关的 features 膨胀系数方差）

<a id="quick-reference"></a>

## 快速参考

| 场景 | 模型 | 正则化 | 按键设置 |
|----------|-------|---------------|-------------|
| 几个features，可解释 | 逻辑回归 | L2（默认） | C=1.0 |
| 很多features，有些不相关 | 逻辑回归 | L1 | 惩罚=“l1”，解算器=“saga” |
| 高暗稀疏（文本） | SGD分类器 | L1 或 ElasticNet | 损失=“log_loss” |
| 类别不平衡 | 逻辑回归 | L2 | class_weight =“平衡” |
| 需要概率 | 逻辑回归 | L2 | predict_proba() |
| 仅需要类标签 | 线性SVC | L2 | 对于大数据来说比 LR 更快 |
