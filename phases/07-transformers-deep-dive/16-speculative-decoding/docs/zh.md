<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="speculative-decoding--draft-verify-repeat"></a>

# Speculative Decoding — 草稿、验证、重复

> Autoregressive 解码是串行的。每个 token 等待前一个。 Speculative decoding 打破链条：廉价模型起草 N tokens，昂贵模型验证所有 N 合一 forward pass。当选秀合适时，你为 N 代人支付了一笔大额预付款。

**类型：** 构建
**语言：** Python
**先决条件：** 第 7·07 阶段（GPT 因果 LM）、第 7·12 阶段（KV Cache 和 Flash Attention）
**时间：** ~60 分钟

<a id="the-problem"></a>

## 问题

在 H100 上，一个 70B LLM sampling 一个 token 大约需要 30 毫秒。 3B 草稿模型大约需要 3 毫秒。如果我们让 3B 草案 5 tokens 领先，然后运行 70B *once* 来验证所有 5 个，则总计为 `5×3 + 30 = 45 ms`，最多 5 个已接受的 tokens — 与`5×30 = 150 ms` 用于直线生成。这就是完整的推测解码要点：用少量额外的 GPU 内存（草稿模型）换取 2-4 倍的较低解码延迟。

诀窍是保留分布。推测性 sampling，由 Leviathan 等人提出。 (2023) 和 Chen 等人。同时，保证输出序列 ** 与大模型自己生成的序列一致分布 **。没有质量权衡。只是更快。

四个系列的草案验证器对在 2026 年 inference 中占主导地位：

1. **Vanilla 推测（Leviathan 2023）。** 单独的草案模型（例如，Llama 3 1B）+验证者（例如，Llama 3 70B）。
2. **Medusa (Cai 2024).** 验证器上的多个解码头并行预测位置 `t+1..t+k`。没有单独的草稿模型。
3. **EAGLE家族（Li 2024, 2025）。** 重用验证者隐藏状态的轻量级草案；比普通版更接近接受率； 3–4× 典型值。
4. **Lookahead解码（Fu 2024）。**雅可比迭代；根本不需要草稿模型。自我推测。利基但无依赖性。

2026 年每个生产的 inference 堆栈默认发货为 speculative decoding。 vLLM、TensorRT-LLM、SGLang 和 llama.cpp 都至少支持 vanilla + EAGLE-2。

<a id="the-concept"></a>

## 概念

<a id="the-core-algorithm"></a>

### 核心算法

给定一个验证者 `M_q` 和一个更便宜的草稿 `M_p`：

1. 令 `x_1..x_k` 为已解码的前缀。
2. **Draft**：使用`M_p`以自回归方式提出`d_{k+1}, d_{k+2}, ..., d_{k+N}`，草稿概率为`p_1..p_N`。
3. **并行验证**：在`x_1..x_k, d_{k+1}, ..., d_{k+N}`上运行一次`M_q`，获得位置`k+1..k+N+1`的验证者概率`q_1..q_{N+1}`。
4. **接受/拒绝每个草稿token从左到右**：对于每个`i`，以概率`min(1, q_i(d_i) / p_i(d_i))`接受。
5. 在位置 `j` 处第一次拒绝时：来自标准化“残差”分布 `(q_j - p_j)_+` 的样本 `t_j`。 `j` 之后的所有草稿均被丢弃。
6. 接受所有 `N` 时：从 `q_{N+1}` 中额外抽取一份 token `t_{N+1}`（免费奖金 token）。

残差分布技巧是一种数学见解，它使输出保持精确分布，就像 `M_q` 从头开始采样一样。

<a id="what-determines-speedup"></a>

### 加速比由什么决定

令 `α` = 每份草案的预期接受率 token。令 `c` = 草案与验证者成本比率。每一步：

- 天真的一代根据 token 进行 1 个大模型调用。
- 当 `α` 为高时，投机性对每个 `(1 - α^{N+1}) / (1 - α) ≈ 1/(1-α)` tokens 进行 1 次大模型调用。

`α = 0.75` 和 `N = 5` 的典型经验法则：大模型调用减少 3 倍。草稿成本便宜 5 倍。总挂钟下降约 2.5 倍。

**α 取决于：**

- 草稿与验证者的近似程度。相同的家庭/相同的训练数据显着提高了α。
- Decoding strategy。贪婪草稿对抗贪婪验证者：高α。 Temperature sampling：较难匹配；接受度下降。
- 任务类型。代码和structured output接受更多（可预见）；自由形式的创意写作接受的较少。

<a id="medusa--drafts-without-a-draft-model"></a>

### 美杜莎 — 没有草稿模型的草稿

美杜莎在验证器上用额外的输出头取代了草案模型。在位置 `t`：

```
shared trunk → hidden h_t
    ├── head_0: predict token at t+1  (standard LM head)
    ├── head_1: predict token at t+2
    ├── head_2: predict token at t+3
    ├── head_3: predict token at t+4
```

每个头输出自己的logits。在 inference，您从每个头采样以获得候选序列，然后使用一个 forward pass 使用树 attention 方案进行验证，该方案一次考虑所有候选延续。

优点：没有第二个模型。缺点：添加可训练的 parameters；需要一个受监督的 fine-tuning 阶段（~1B tokens）；接受率比普通投机性好的选秀要低一些。

<a id="eagle--better-draft-by-reusing-hidden-states"></a>

### EAGLE — 通过重用隐藏状态来更好的草稿

EAGLE-1/2/3（Li 等人，2024-2025）将草稿模型设为一个微小的 transformer（通常为 1 层），用于摄取验证者的最后一层隐藏状态。由于草稿看到验证者的 feature 表示，因此其预测与验证者的输出分布密切相关。录取率从 ~0.6（普通）攀升至 0.85+。

EAGLE-3 (2025) 添加了对候选延续的树搜索。 vLLM 和 SGLang 将 EAGLE-2/3 作为 Llama 3/4 和 Qwen 3 的默认规格路径。

<a id="the-kv-cache-dance"></a>

### KV cache舞蹈

验证将 `N` 草稿 tokens 馈送到一个 forward pass 中的验证器中。这将验证者的 KV cache 扩展为 `N` 条目。如果某些草稿被拒绝，您必须将缓存回滚到可接受的前缀长度。

生产实现（vLLM 的 `--speculative-config`、TensorRT-LLM 的 LookaheadDecoder）使用暂存 KV 缓冲区来处理此问题。验收时先写commit。这在概念上并不难，但很繁琐。

```figure
draft-verify-tokens
```

<a id="build-it"></a>

## 动手实现

参见 `code/main.py`。我们通过以下方式实现核心推测性sampling算法（拒绝步骤+残差分布）：

- 一个“大模型”，它是手动编码分布上的确定性 softmax（因此我们可以通过分析来验证接受数学）。
- “草稿模型”是大模型的扰动。
- 接受/拒绝循环产生与直接 sampling 相同的边际分布。

<a id="step-1-the-rejection-step"></a>

### 第一步：拒绝步骤

```python
def accept_or_reject(q_prob, p_prob, draft_token, u):
    ratio = q_prob / p_prob if p_prob > 0 else float("inf")
    return u < min(1.0, ratio)
```

`u` 是一个统一随机数。 `q_prob` 是验证者对起草的 token 的概率。 `p_prob` 是草稿模型的概率。利维坦定理是，这个伯努利决策，以及来自拒绝残差的 sampling ，准确地保留了验证者的分布。

<a id="step-2-residual-distribution"></a>

### 步骤2：残差分布

```python
def residual_dist(q, p):
    raw = [max(0.0, qi - pi) for qi, pi in zip(q, p)]
    s = sum(raw)
    return [r / s for r in raw]
```

从 `q` 逐个元素减去 `p`，将负值钳位为零，重新标准化。如有任何拒绝，请从中取样。

<a id="step-3-one-speculative-step"></a>

### 第三步：一个推测步骤

```python
def spec_step(prefix, q_model, p_model, N, rng):
    drafts = []
    p_probs = []
    ctx = list(prefix)
    for _ in range(N):
        p_dist = p_model(ctx)
        d = sample(p_dist, rng)
        drafts.append(d)
        p_probs.append(p_dist[d])
        ctx.append(d)

    q_dists = [q_model(prefix + drafts[:i]) for i in range(N + 1)]

    for i, d in enumerate(drafts):
        u = rng.random()
        q_prob = q_dists[i][d]
        p_prob = p_probs[i]
        if u < min(1.0, q_prob / p_prob if p_prob > 0 else float("inf")):
            prefix = prefix + [d]
        else:
            res = residual_dist(q_dists[i], p_model(prefix))
            prefix = prefix + [sample(res, rng)]
            return prefix
    prefix = prefix + [sample(q_dists[N], rng)]
    return prefix
```

五个接受→一个奖励→在一个验证者通行证中产生六个 tokens。

<a id="step-4-measure-acceptance-rate"></a>

### 第 4 步：衡量接受率

在不同的草稿质量级别运行 10,000 个推测步骤。绘制接受率与草稿分布和验证者分布之间的 KL 差异的图。您应该看到一个干净单调的关系。

<a id="step-5-verify-distribution-equivalence"></a>

### 第 5 步：验证分布等价性

根据经验：推测循环生成的 tokens 的直方图应该与直接从验证者生成的 sampling 的直方图匹配。这就是实践中的利维坦定理。卡方检验确认 sampling 误差范围内。

<a id="use-it"></a>

## 实际应用

生产：

```bash
# vLLM with EAGLE
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --speculative-config '{"method": "eagle", "model": "/models/llama-3.1-eagle-70b", "draft_tensor_parallel_size": 1, "num_speculative_tokens": 5}'

# vLLM with vanilla draft model
vllm serve meta-llama/Llama-3.1-70B-Instruct \
    --speculative-config '{"method": "draft_model", "model": "meta-llama/Llama-3.2-1B-Instruct", "num_speculative_tokens": 5}'
```

截至 2026 年中期，TensorRT-LLM 拥有最快的 Medusa 路径。 `faster-whisper` 包装 speculative decoding 用于 Whisper-large 和小草案。

**取草稿：**

| 策略 | 何时采摘 | 加速比 |
|----------|--------------|---------|
| 香草草稿（1B/3B Llama 系列） | 快速原型，无需培训 | 1.8–2.3× |
| 美杜莎头 | 您可以微调验证器 | 2–3× |
| 鹰-2 / 3 | 生产，最大速度 | 3–4× |
| 前瞻 | 没有草稿，没有训练，没有额外的参数 | 1.3–1.6× |

**何时不进行规范解码：**

- 1-5 tokens 的单序列生成。开销占主导地位。
- 狂野创意/高temperature sampling（α滴）。
- 内存受限的部署（草案模型添加了 VRAM）。

<a id="ship-it"></a>

## 交付成果

参见 `outputs/skill-spec-decode-picker.md`。该技能选择 speculative decoding 策略（普通/美杜莎/EAGLE/前瞻）并针对新的 inference 工作负载调整 parameters（N，草案 temperature）。

<a id="exercises"></a>

## 练习

1. **Easy.** 运行`code/main.py`。确认推测的 token 分布与验证者在 50,000 个 tokens 上的直接样本分布相匹配，且卡方 p > 0.05。
2. **Medium.** 将加速（tokens 每个大模型转发）绘制为 `N` 的函数（对于 `α = 0.5, 0.7, 0.85`）。确定每个 α 的最佳 `N`。 （提示：每次验证调用预计为 tokens = `(1 - α^{N+1}) / (1 - α)`。）
3. **Hard.** 实现一个小型美杜莎：从第 14 课中获取综合项目 GPT，添加 3 个额外的 LM 头来预测位置 t+2、t+3、t+4。在小莎士比亚上进行联合多头损失的训练。将接受率与通过截断同一模型制作的普通草稿进行比较。
4. **Hard.** 实施 rollback：以 10-token 前缀 KV cache 开始，馈送 5 草稿 tokens，在位置 3 模拟拒绝。验证您的缓存读取在下一次迭代时正确匹配“前缀+前 2 个接受的草稿”。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 草案模型 | “便宜的那个” | 提出候选 tokens 的较小模型；通常比验证者便宜 10-50 倍。 |
| 验证者 | “那个大的” | 我们保留其分布的目标模型；每个推测步骤运行一次。 |
| 接受率（α） | “草稿多久是对的” | 每 token 验证者接受草稿的概率。 0.7–0.9（典型值）。 |
| 剩余分布 | “拒绝后退” | `(q - p)_+`归一化； sampling 由此拒绝保留验证者的分布。 |
| 奖金token | “免费的” | 当所有 N 个草稿都被接受后，从验证者的下一步分布中再抽取一个。 |
| 美杜莎 | “无草案投机” | 验证器上的多个 LM 头并行预测位置 t+1..t+k。 |
| 鹰 | 《隐藏状态草案》 | 微小的 transformer 草案以验证者的最后一层隐藏状态为条件。 |
| 前瞻解码 | “雅可比迭代” | 使用定点迭代进行自我推测；没有草稿模型。 |
| 树attention | “同时验证多个候选人” | 同时考虑多个草稿延续的分支验证。 |
| KV rollback | “撤消拒绝的草稿” | 暂存KV缓冲区； commit 接受时，拒绝时丢弃。 |

<a id="further-reading"></a>

## 进一步阅读

- [利维坦、卡尔曼、马蒂亚斯 (2023)。来自 Transformers 的快速 Inference 通过 Speculative Decoding](https://arxiv.org/abs/2211.17192) — 核心算法和等价定理。
- [Chen 等人。 （2023）。利用推测性加速大型语言模型解码 Sampling](https://arxiv.org/abs/2302.01318) — 并发介绍；干净的伯努利拒绝证明。
- [Cai 等人。 （2024）。 Medusa：简单 LLM Inference 具有多个解码头的加速框架](https://arxiv.org/abs/2401.10774) — Medusa 论文；树-attention验证。
- [Li 等人。 （2024）。 EAGLE：投机性 Sampling 需要重新思考 Feature 不确定性](https://arxiv.org/abs/2401.15077) — EAGLE-1；隐藏状态条件草稿。
- [Li 等人。 （2024）。 EAGLE-2：具有动态草图树的更快的语言模型 Inference](https://arxiv.org/abs/2406.16858) — EAGLE-2；动态树深度。
- [Li 等人。 （2025）。 EAGLE-3：通过训练时间测试扩展 Inference 大型语言模型加速 ](https://arxiv.org/abs/2503.01840) — EAGLE-3。
- [Fu 等人。 （2024）。使用前瞻解码打破 LLM Inference 的顺序依赖性](https://arxiv.org/abs/2402.02057) — 前瞻、无草稿方法。
- [vLLM 文档 — Speculative Decoding](https://docs.vllm.ai/en/latest/features/spec_decode.html) — 已连接所有四种策略的规范生产参考。
- [SafeAILab / EAGLE 参考实现](https://github.com/SafeAILab/EAGLE) — EAGLE-1/2/3 的参考代码。
