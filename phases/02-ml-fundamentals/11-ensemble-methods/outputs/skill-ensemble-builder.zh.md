---
name: skill-ensemble-builder
description: Choose the right ensemble method and configure it for your problem
version: 1.0.0
phase: 2
lesson: 11
tags: [ensemble, bagging, boosting, random-forest, xgboost, stacking]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="ensemble-method-selection-guide"></a>

# 集成方法选择指南

集成结合了多个模型，可以产生比任何单个模型更好的预测。问题始终是：哪种类型、何时？

<a id="decision-checklist"></a>

## 决策清单

1. 您当前模型的主要问题是什么？
   - 高方差（overfitting）：使用装袋（随机森林）
   - 高偏置（underfitting）：使用Boosting（Gradient Boosting、XGBoost）
   - 两者都可以，或者您想要最大的精度：使用堆叠

2. 您有多少数据？
   - 1,000 行以下：随机森林（稳健、不易配置错误）
   - 1,000 到 100,000：XGBoost 或 LightGBM（表格总体最佳）
   - 超过100,000：LightGBM（最快的gradient boosting，可以很好地处理大数据）

3. 您可以投入多少调整时间？
   - 最小：具有默认值的随机森林（几乎总是有效）
   - 中等：XGBoost 学习_rate=0.1，调整 n_estimators 并提前停止
   - 最大值：带有贝叶斯 hyperparameter 搜索的 LightGBM 或 XGBoost

4. 您需要可解释性吗？
   - 是：单个决策树或小型随机森林，重要性为 feature
   - 部分：gradient 使用 SHAP 值进行提升
   - 否：堆叠或深度集成

5. 数据是否有很多异常值，充满噪音？
   - 是：随机森林（装袋对噪声具有鲁棒性）
   - 否：gradient 提升（可以进一步提高干净数据的准确性）

<a id="when-to-use-each-method"></a>

## 何时使用每种方法

**随机森林（Bagging）**：您的安全首选。根据引导样本和平均值训练许多树。减少方差而不增加偏差。几乎不可能对中等数据进行过度拟合。所需的最小调整：设置 n_estimators=100-500 并保留默认值。

**AdaBoost**：通过样本重新加权进行顺序提升。与简单的基础学习器（决策树桩）配合良好。对异常值和噪声标签敏感，因为它会增加错误分类点的权重。实践中大部分被 gradient boosting 取代。

**Gradient Boosting**：将每棵新树拟合到迄今为止集成的残差。减少偏见。适用于表格数据的最强大方法。需要调整：学习_rate、n_estimators、max_深度、min_child_weight、子样本。

**XGBoost**：gradient 通过正则化、二阶优化和系统级加速进行提升。本机处理缺失值。 Kaggle 竞赛和表格数据生产 ML 的默认设置。

**LightGBM**：gradient 促进叶向生长（而不是水平生长）。在大型数据集上比 XGBoost 更快。使用基于直方图的分割。最适合超过 50k 行的数据集。

**CatBoost**：gradient 使用本机分类 feature 处理进行提升。无需进行one-hot 编码。当您有许多分类 features 时，这很好。

**Stacking**：训练元学习器对多个不同基础模型的预测。当您需要绝对最佳精度并且有空闲计算资源时使用。始终通过交叉验证生成基本模型预测，以避免泄漏。

**Voting**：最简单的集成。硬投票（多数类别）或软投票（平均概率）。无需元学习器即可快速组合 2-3 个不同模型的方法。

<a id="common-mistakes"></a>

## 常见错误

- 使用gradient boosting而不提前停止（如果让它运行太多轮，它会过度拟合）
- 设置learning_rate太高（高于0.3通常会导致不稳定）
- 不调整 max_深度以进行 gradient 提升（默认无限或非常深的树过度拟合）
- 与所有相同类型的模型堆叠（多样性是堆叠的重点）
- 在噪声数据上使用 AdaBoost（每轮异常值变得越来越高 weight）
- 期望随机森林修复 underfitting （它减少方差，而不是偏差）

<a id="tuning-priorities-by-method"></a>

## 通过方法调整优先级

**随机森林：**
1. n_estimators：100-500（更多很少会更糟，只是更慢）
2. max_深度：无（让树木充分生长）或上限为 10-20 以提高速度
3. max_features：“sqrt”用于分类，“log2”或 n/3 用于回归

**XGBoost / LightGBM:**
1. Learning_rate：0.01-0.3（如果您有更多树的计算，则越低越好）
2. n_estimators：在验证集上使用早期停止而不是猜测
3. max_深度：3-8（从6开始）
4. min_child_weight / min_data_in_leaf：1-20（较高可防止 overfitting）
5. 子样本：0.7-1.0
6. colsample_bytree：0.7-1.0
7. reg_alpha (L1) 和 reg_lambda (L2)：0-10

<a id="quick-reference"></a>

## 快速参考

| 方法 | 减少 | 速度 | 调整工作量 | 最适合 |
|--------|---------|-------|--------------|----------|
| 随机森林 | 方差 | 快 | 低 | 噪声数据、快速基线 |
| 阿达助推器 | 偏差 | 快 | 低 | 简单的基础学习器，干净的数据 |
| Gradient 升压 | 偏差 | 中等 | 高 | 表格数据、竞赛 |
| XGBoost | 两者都 | 快 | 高 | 生产表格 ML |
| 光GBM | 两者都 | 最快 | 高 | 大型数据集（50k+ 行） |
| 猫助推器 | 两者都 | 中等 | 中等 | 多分类 features |
| 堆叠 | 两者都 | 慢 | 高 | 最高精度、多种型号 |
| 投票 | 方差 | 快 | 无 | 2-3个模型的快速组合 |
