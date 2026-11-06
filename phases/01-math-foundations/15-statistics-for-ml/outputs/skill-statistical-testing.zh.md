---
name: skill-statistical-testing
description: Choose the right statistical test for comparing ML models and evaluating experiments
version: 1.0.0
phase: 1
lesson: 15
tags: [statistics, hypothesis-testing, model-comparison]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="statistical-testing-for-ml"></a>

# ML 统计测试

在比较模型、运行 A/B 实验或验证结果时如何选择正确的测试。

<a id="decision-checklist"></a>

## 决策清单

1. 你在比较什么？平均值、比例、分布或相关性？
2. 有多少组？一个样本与参考、两组还是多组？
3. 观察结果是配对的（相同的测试集，相同的折叠）还是独立的？
4. 数据是否呈正态分布？如果 n < 30 并且不明显正态，则使用非参数。
5. 数据是连续的、有序的还是分类的？
6. 您正在运行多少个测试？如果超过一个，则应用更正。

<a id="decision-tree"></a>

## 决策树

```text
Comparing means?
  Two groups?
    Paired (same data splits)? --> Paired t-test (or Wilcoxon signed-rank if non-normal)
    Independent? --> Welch's t-test (or Mann-Whitney U if non-normal)
  Multiple groups?
    Paired? --> Repeated measures ANOVA (or Friedman test)
    Independent? --> One-way ANOVA (or Kruskal-Wallis)

Comparing proportions?
  Two groups? --> Chi-squared test or Fisher's exact test (small n)
  Multiple groups? --> Chi-squared test

Comparing distributions?
  Is one distribution a reference? --> Kolmogorov-Smirnov test
  Are both empirical? --> Two-sample KS test

Measuring association?
  Both continuous, roughly normal? --> Pearson correlation
  Ordinal or non-normal? --> Spearman rank correlation
  Categorical x Categorical? --> Chi-squared test of independence

Running many tests?
  Apply Bonferroni correction: alpha_adjusted = alpha / number_of_tests
  Or use Holm-Bonferroni (less conservative, still controls family-wise error)
```

<a id="when-to-use-each-test"></a>

## 何时使用每个测试

| 测试 | 数据类型 | 假设 | 机器学习用例 |
|---|---|---|---|
| 配对t检验 | 连续、成对 | 正常差异 | 比较相同 k 倍分割的 2 个模型 |
| Wilcoxon 符号秩 | 连续/顺序、配对 | 无（非参数） | 比较2款，小k（5-10折） |
| 韦尔奇的 t 检验 | 连续、独立 | 大致正常 | 比较两个单独数据集的模型 |
| 曼惠特尼大学 | 连续/顺序、独立 | 无 | 比较延迟分布 |
| 方差分析 | 连续，3组以上 | 正态、等方差 | 比较多个模型架构 |
| 克鲁斯卡尔-瓦利斯 | 连续/顺序，3组以上 | 无 | 比较多个模型、非正态指标 |
| 卡方 | 分类计数 | 预期计数 >= 5 | 比较类别分布、混淆矩阵 |
| 费舍尔精确 | 分类计数 | 小样品 | 罕见事件比较 |
| KS测试 | 连续 | 无 | 检查预测是否遵循预期分布 |
| 引导持续集成 | 任何统计数据 | 无 | AUC、F1、任何指标的置信区间 |
| 麦克尼马尔试验 | 配对二进制 | 无 | 比较同一测试集上的两个分类器 |

<a id="model-comparison-recipe"></a>

## 型号对比配方

1. 在运行实验之前定义指标和显着性水平 (alpha = 0.05)。
2. 在相同的 k 倍交叉验证分割（k = 5 或 10）上运行两个模型。
3. 收集配对分数：(a_1，b_1)，(a_2，b_2)，...，(a_k， b_k)。
4. 计算差异：d_i = b_i - a_i。
5. 运行配对检验（k <= 10 时使用 Wilcoxon，k > 10 时使用配对 t 检验或正常差异）。
6. 报告：p 值、平均差、95% 置信区间、效应大小（Cohen's d）。
7. 如果 p < alpha 并且效应大小有意义，则差异是真实的并且值得采取行动。

<a id="common-mistakes"></a>

## 常见错误

- 数据配对时使用独立测试。如果两个模型在相同的测试折叠上进行评估，则必须使用配对测试。独立测试抛弃了配对并失去了统计功效。
- 报告 p < 0.05，无效应大小。统计上显着的 0.1% 准确度提升并不值得部署。始终计算 Cohen's d 或原始平均差。
- 比较不同测试集的模型。两个模型的测试集必须相同。不同的测试集使得比较毫无意义。
- 运行 20 次比较并报告未经 Bonferroni 校正的最佳比较。在 alpha = 0.05 的情况下进行 20 次测试，您预计会偶然出现 1 个误报。
- 使用不平衡数据的准确性。在 99% 多数类别上，普通分类器可以达到 99%。使用 F1、精确召回 AUC 或 Matthews 相关系数。
- 将交叉验证折叠视为独立样本。他们共享训练数据，这违反了独立性假设。修正后的重采样 t 检验解释了这一点。

<a id="quick-reference-effect-size-interpretation"></a>

## 快速参考：效应量解释

| 科恩的D | 解读 |
|---|---|
| 0.2 | 影响较小 |
| 0.5 | 中等效果 |
| 0.8 | 效果大 |
| > 1.0 | 作用非常大 |

| 报告什么 | 为什么 |
|---|---|
| p 值 | 差异是真实的吗？ |
| 置信区间 | 差别有多大？ |
| 效应大小（Cohen's d） | 差异有意义吗？ |
| 样本大小（n 或 k 次） | 我们可以相信结果吗？ |
