---
name: skill-sampling-strategy
description: Choose the right sampling method for generation, estimation, or inference
version: 1.0.0
phase: 1
lesson: 16
tags: [sampling, mcmc, generation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="sampling-strategy-selection"></a>

# Sampling 策略选择

如何选择正确的 sampling 方法进行文本生成、贝叶斯 inference、Monte Carlo 估计和训练。

<a id="decision-checklist"></a>

## 决策清单

1. 您是在生成输出（文本、图像）还是估计数量（积分、期望）？
2. 您可以直接从目标分布中采样，还是只评估其密度？
3. 目标分布是离散的还是连续的？
4. 样本空间的维度是多少？低 (< 5)、中 (5-100) 还是高 (> 100)？
5. 您需要精确的样本还是近似的样本？
6. 通过sampling操作是否需要gradients？

<a id="when-to-use-each-method"></a>

## 何时使用每种方法

| 方法 | 何时使用 | 复杂性 | 准确吗？ |
|---|---|---|---|
| 直接sampling | 您有 CDF 或者可以使用库函数 | 每个样本 O(1) | 是的 |
| 逆累积分布函数 | 已知的封闭式 CDF 逆（指数、柯西） | 每个样本 O(1) | 是的 |
| 博克斯-穆勒 | 需要没有库的普通样品 | 每个样本 O(1) | 是的 |
| 拒绝 sampling | 可以评估目标 PDF，低维 (1-3) | 每个样本 O(1/验收) | 是的 |
| Importance sampling | 需要期望，而不是单个样本 | n 个样本的 O(n) | 大约 |
| 分层sampling | Monte Carlo估计，想要更低的方差 | n 个样本的 O(n) | 大约 |
| 大都会-黑斯廷斯 | 高维，可以评估非归一化密度 | 每步 O(1) + 预烧 | 渐近地 |
| 吉布斯 sampling | 可以从每个条件分布中采样 | 每次完整扫描 O(d) | 渐近地 |
| HMC/坚果 | 高维连续、平滑密度 | 每步 O(L * d) | 渐近地 |
| Temperature sampling | LLM文字生成，掌控创意 | O(V) 表示词汇大小 V | 不适用 |
| Top-k sampling | LLM生成，删除不太可能的tokens | O(V log k) | 不适用 |
| Top-p（核） | LLM生成，自适应候选集 | O(V log V) | 不适用 |
| 重新参数化 | 需要gradients通过高斯sampling（VAEs） | O(d) | 是的 |
| Gumbel-Softmax | 需要gradients通过分类sampling | k 类的 O(k) | 大约 |

<a id="llm-generation-settings"></a>

## LLM生成设置

| 应用场景 | Temperature | Top-p | 前k | 注释 |
|---|---|---|---|---|
| 事实问答 | 0.0（贪婪） | -- | -- | 确定性、无随机性 |
| 代码生成 | 0.2-0.5 | 0.9 | -- | 创造力低，连贯性高 |
| 一般聊天 | 0.7 | 0.9 | -- | 平衡 |
| 创意写作 | 0.9-1.2 | 0.95 | -- | 更高的多样性 |
| 头脑风暴 | 1.0-1.5 | 0.95 | -- | 最大程度的多样性，可能会失去连贯性 |

Temperature 和 top-p 可以组合。首先应用 temperature（缩放 logits），然后应用 top-p 过滤。

<a id="mcmc-method-selection"></a>

## MCMC方法选择

| 财产 | 大都会-黑斯廷斯 | 吉布斯 | HMC/坚果 |
|---|---|---|---|
| 尺寸 | 任意 | 任何（最好 < 100） | 高（100+） |
| 需要条件句 | 否 | 是的 | 否 |
| 需要 gradient | 否 | 否 | 是的 |
| 录取率 | 调至~23% | 始终为 100% | 调至 ~65% |
| 相关性 | 高（随机游走） | 中等 | 低 |
| 老化 | 长 | 中等 | 短 |
| 最适合 | 探索、简单模型 | 共轭模型、贝叶斯网络 | 连续后验，深度概率模型 |

<a id="common-mistakes"></a>

## 常见错误

- 在高维度中使用拒绝 sampling。接受率随维度呈指数下降。 5个维度以上，改用MCMC。
- 将 MCMC 提案方差设置得太高或太低。太高：大多数提案被拒绝，链条被卡住。太低：所有提案均被接受，链条移动缓慢。随机游走 MH 的目标接受度约为 23%。
- 忘记老化。 MCMC 的前 N ​​个样本因起始点而有偏差。丢弃至少 1000 个步骤（对于复杂的分布则丢弃更多）。
- 使用 importance sampling 的提案与目标非常不同。一些样本得到巨大的 weights，使得估计不可靠。监控有效样本量：ESS = (sum w_i)^2 / sum(w_i^2)。
- 对于需要确定性输出的任务（例如分类、结构化提取），使用 temperature > 0。请改用贪婪 (T=0) 或波束搜索。
- 不将 top-p 与 temperature 结合起来。 Temperature 本身并不能从长尾中删除垃圾 tokens。 Top-p 确实如此。
- 通过标准 sampling 操作进行反向传播。对连续（高斯）使用重新参数化技巧，对离散（分类）使用 Gumbel-Softmax。

<a id="quick-reference-variance-reduction-techniques"></a>

## 快速参考：方差减少技术

| 技术 | 它是如何运作的 | 方差减少 |
|---|---|---|
| 分层sampling | 将空间划分为几层，对每一层进行采样 | 始终 <= 标准 MC |
| 对立变量 | 同时使用 U 和 1-U | 适用于单调函数 |
| 控制变量 | 减去已知均值变量 | 与相关性成正比 |
| Importance sampling | 从更好的提案中重新加权样本 | 取决于提案质量 |
| 拉丁超立方体 | 独立地对每个维度进行分层 | 优于高维分层 |
