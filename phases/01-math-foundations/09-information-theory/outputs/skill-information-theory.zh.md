---
name: skill-information-theory
description: Apply information theory concepts to ML loss functions, model evaluation, and feature selection
version: 1.0.0
phase: 1
lesson: 9
tags: [information-theory, entropy, loss-functions]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="information-theory-for-ml"></a>

# 机器学习信息论

何时在机器学习系统中使用熵、cross-entropy、KL 散度和互信息。

<a id="decision-checklist"></a>

## 决策清单

1. 测量单一分布的不确定性？使用**entropy**。
2. 衡量模型与真实标签的近似程度如何？使用 **cross-entropy** （这是你的分类损失）。
3. 测量两个分布之间的距离？使用**KL散度**。
4. 检查两个变量是否相关？使用**互信息**。
5. 报告语言模型质量？使用**perplexity**（cross-entropy的指数）。
6. 将一种模型提炼成另一种模型？最小化从教师到学生的 **KL 分歧**。

<a id="when-to-use-each-measure"></a>

## 何时使用每项措施

| 测量 | 公式 | 应用场景 | 机器学习应用 |
|---|---|---|---|
| 熵H(P) | -sum(p log p) | 这个分布的不确定性有多大？ | 数据复杂性、最大熵模型 |
| Cross-entropy H(P,Q) | -sum(p log q) | 模型 Q 预测真实 P 的效果如何？ | 分类损失、语言模型损失 |
| KL散度D(P\|\|Q) | sum(p log(p/q)) | P 和 Q 有何不同？ | VAE 损失（ELBO）、knowledge distillation、RLHF |
| 互信息 I(X;Y) | H(X) - H(X\|Y) | Y 告诉我们多少关于 X 的信息？ | Feature选择，表示学习 |
| Perplexity | exp(H(P,Q)) 或 2^H | 模型有多混乱？ | 语言模型 evaluation |
| 条件熵H(X\|Y) | -sum(p(x,y) log p(x\|y)) | 知道 Y 后 X 的剩余不确定性 | Feature 信息量 |

<a id="key-relationships"></a>

## 关键关系

```
Cross-entropy  = Entropy + KL divergence
H(P, Q)        = H(P)   + D_KL(P || Q)

Since H(P) is constant during training:
  Minimizing cross-entropy = Minimizing KL divergence

Mutual information = Entropy - Conditional entropy
I(X; Y) = H(X) - H(X|Y) = H(Y) - H(Y|X)

Perplexity = exp(cross-entropy in nats)
           = 2^(cross-entropy in bits)
```

<a id="quick-reference-formulas-and-units"></a>

## 快速参考：公式和单位

| 公式 | 位（以 2 为底的对数） | Nats（以 e 为底的对数） |
|---|---|---|
| 信息：-log(p) | -log2(p) | -ln(p) |
| 熵：-sum(p log p) | 位 | 纳兹 |
| 1 nat = | 1.4427 位 | 1 纳特 |
| PyTorch 默认 | -- | 纳兹 |
| 信息论论文 | 位 | -- |

<a id="interpreting-values"></a>

## 解读价值观

| 熵值 | 这意味着什么 |
|---|---|
| 0 | 确定性的。一种结果的概率为 1。 |
| log(n) | 最大的不确定性。 n 个结果的均匀分布。 |
| 低 | 分布达到峰值。模特自信满满。 |
| 高 | 分布平坦。模型不确定。 |

| Perplexity 值 | 语言模型质量 |
|---|---|
| 1 | 完美的预测（实践中从未发生过） |
| 10 | 平均在约 10 个 tokens 中进行选择 |
| 50 | 标准基准上的 GPT-2 级别 |
| < 10 | 具有代表性的领域的最先进技术 |

<a id="common-mistakes"></a>

## 常见错误

- 计算 KL 散度并将其视为对称的。 D_KL(P||Q) != D_KL(Q||P）。对于对称度量，请使用 Jensen-Shannon 散度：JS = 0.5 * KL(P||M) + 0.5 * KL(Q||M) 其中 M = 0.5*(P+Q)。
- 忘记带有 one-hot 标签的 cross-entropy 会简化为 -log(p_true_class)。当真实分布是独热分布时，您不需要对所有类求和。
- 在代码中使用对数基数 2 但报告 nats（反之亦然）。 PyTorch 默认使用自然对数。乘以 log2(e) = 1.4427 将 nat 转换为位。
- 计算空事件或零概率事件的熵。约定：0 * log(0) = 0，因为 lim(p->0) p*log(p) = 0。
- 比较不同 vocabularies 之间的 perplexity。词汇大小为 50k 和 perplexity 30 的模型不能直接与词汇大小为 10k 和 perplexity 30 的模型进行比较。

<a id="where-each-concept-appears-in-production-ml"></a>

## 每个概念在生产 ML 中出现的位置

| 概念 | 你在哪里看到它 |
|---|---|
| Cross-entropy 损失 | 每个分类模型（nn.CrossEntropyLoss） |
| KL散度 | VAE ELBO，PPO 剪辑，knowledge distillation |
| 熵正则化 | RL 中的探索奖励（更高的熵 = 更多的探索） |
| 互信息 | Feature选择，InfoNCE丢失（contrastive learning） |
| Perplexity | 语言模型基准（较低=更好） |
| 标签平滑 | 用软目标替换 one-hot，减少 cross-entropy 过度自信 |
| Temperature 缩放 | 在softmax之前将logits除以T，控制输出的熵 |
