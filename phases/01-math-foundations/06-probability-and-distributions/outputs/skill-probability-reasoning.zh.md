---
name: skill-probability-reasoning
description: Choose the right probability distribution for a given ML problem
version: 1.0.0
phase: 1
lesson: 6
tags: [probability, distributions, modeling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="probability-distribution-selection"></a>

# 概率分布选择

在数据建模、设计 loss functions 或设置先验时如何选择正确的分布。

<a id="decision-checklist"></a>

## 决策清单

1. 结果是离散的（类别、计数）还是连续的（测量、分数）？
2. 结果是有界的（例如，[0、1]）还是无界的？
3. 有多少种可能的结果？二？ k？无限？
4. 数据是对称的还是倾斜的？
5. 事件是独立的还是相关的？
6. 您正在对比率、计数、比例或测量进行建模吗？

<a id="distribution-decision-tree"></a>

## 分布决策树

```
Is the variable discrete?
  Yes --> Only 2 outcomes? --> Bernoulli (p)
     |    k outcomes, one trial? --> Categorical (p1...pk)
     |    k outcomes, n trials? --> Multinomial (n, p1...pk)
     |    Count of successes in n trials? --> Binomial (n, p)
     |    Count of events per interval? --> Poisson (lambda)
     |    Count of trials until first success? --> Geometric (p)
     |    Count of trials until r successes? --> Negative Binomial (r, p)
  No --> Symmetric, bell-shaped? --> Normal (mu, sigma)
     |   Positive values, right-skewed? --> Log-normal or Exponential
     |   Bounded in [0, 1]? --> Beta (alpha, beta)
     |   Positive values, flexible shape? --> Gamma (alpha, beta)
     |   Time between events? --> Exponential (lambda)
     |   Heavy tails needed? --> Student's t (nu) or Cauchy
     |   Multivariate, bell-shaped? --> Multivariate Normal
     |   On a simplex (sums to 1)? --> Dirichlet (alpha)
```

<a id="mapping-real-world-ml-scenarios-to-distributions"></a>

## 将现实世界的 ML 场景映射到分布

| 场景 | 分布 | Parameters |
|---|---|---|
| 二元分类输出 | 伯努利 | p = sigmoid(logit) |
| 多类分类输出 | 分类的 | p = softmax(logits) |
| Token 语言模型中的预测 | 分类优于词汇 | p来自softmax |
| 像素强度（标准化） | Beta 或统一 [0、1] | 取决于图像统计数据 |
| 文档中的字数统计 | 泊松 | lambda = 平均字数 |
| 用户请求之间的时间 | 指数 | lambda = 请求率 |
| 测量误差 | 正常 | mu = 0，数据中的西格玛 |
| Weight初始化 | 正常或均匀 | 凯明/泽维尔规则 |
| VAE latent space 优先 | 标准 正常 | mu = 0, sigma = 1 |
| 比例的贝叶斯先验 | 贝塔 | 来自信仰的阿尔法、贝塔 |
| 贝叶斯先验类别 weights | 狄利克雷 | 阿尔法向量 |
| 回归目标中的噪声 | 正常 | mu = 0，西格玛估计 |
| 异常值稳健回归 | 学生的t | 低自由度 |
| 持续时间/生命周期建模 | 威布尔或伽玛 | 形状和规模 |
| 每个文档的主题分布 (LDA) | 狄利克雷 | alpha < 1 表示稀疏 |

<a id="when-distributions-go-wrong"></a>

## 当分配出错时

- 当数据具有硬性下限（例如价格、距离）时使用“正常”。正态将非零概率分配给负值。请改用对数正态或伽玛。
- 当方差与均值不同时使用泊松。泊松假设均值 = 方差。如果方差 > 平均值，则使用负二项式。
- 使用伯努利解决多类问题。伯努利是严格二元的。对于 k > 2 使用分类。
- 当观察值相关时假设独立性。时间序列、空间数据和分组数据违反了独立性。使用 autoregressive 或分层模型。

<a id="common-mistakes"></a>

## 常见错误

- 将 PDF 值与概率混淆。 PDF 可以超过 1。概率来自于对某个区间内的 PDF 进行积分。
- 忘记 softmax 输出是分类概率，而不是独立的伯努利概率。通过构造它们的总和为 1。
- 当您拥有领域知识时，使用统一先验。如果选择得当，信息先验可以减少方差，而不会使结果产生偏差。
- 将对数概率视为概率。对数概率始终为负（或零）。它们的总和不等于 1。

<a id="quick-reference-distribution-properties"></a>

## 快速参考：分布属性

| 分布 | 支持 | 平均值 | 方差 | 主要财产 |
|---|---|---|---|---|
| Bernoulli(p) | {0, 1} | p | p(1-p) | 最简单的离散 |
| Binomial(n, p) | {0..n} | NP | np(1-p) | n 伯努利之和 |
| Poisson(lam) | {0, 1, 2, ...} | 林 | 林 | 均值 = 方差 |
| Normal(mu, s^2) | （-inf、inf） | 亩 | s^2 | 给定均值/var 的最大熵 |
| Exponential(lam) | [0，inf) | 1/lam | 1/lam^2 | 无记忆 |
| Beta(a, b) | [0, 1] | a/(a+b) | ab/((a+b)^2(a+b+1)) | 与二项式共轭 |
| Gamma(a, b) | （0，无穷大） | a/b | a/b^2 | 与泊松共轭 |
| Dirichlet(alpha) | 单纯形 | alpha_i/sum | （见公式） | 共轭到分类 |
