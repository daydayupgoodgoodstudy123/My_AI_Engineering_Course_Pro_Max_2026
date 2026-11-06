# 测验 · 预训练 Mini GPT（Pre-Training a Mini GPT (124M Parameters)）

> **阶段 10 · 从零构建 LLM · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | GPT 前向计算图 | token embedding + position embedding → N 个 Transformer block → 最终 LayerNorm → 线性投影到词表 → softmax |
| 2 | Pre-norm block | `x = x + attn(ln1(x))`；`x = x + ffn(ln2(x))`。残差连接给梯度一条"直通"路径，才能堆 12、32、96 层 |
| 3 | 缩放点积注意力 + 因果 mask | `softmax(QKᵀ/√d_k + mask)·V`，`√64 = 8`；mask 把未来位置设为 −∞（代码里用 −1e9），保证自回归 |
| 4 | 多头注意力 | `(B,S,768) → (B,S,12,64) → (B,12,S,64)`，每个头独立做注意力，再拼回 768 维并经 `W_out` 投影 |
| 5 | FFN | 768 → 3072（4 倍）→ 768；GPT-2 用 GELU，本节代码用 ReLU 简化 |
| 6 | Weight tying | 输出层直接用 `token_embed.T`：`logits = x @ token_embed.T`，GPT-2 Small 省下约 38.6M 参数 |
| 7 | 训练目标 | next-token prediction：输入 `tokens[:-1]`、目标 `tokens[1:]`，交叉熵；随机初始化时 loss ≈ `ln(V)`（V=256 时约 5.55） |
| 8 | 采样 | temperature 越低越确定、越高越随机；top-k / top-p 截断长尾；超出上下文窗口时只保留最近 `seq_len` 个 token |
| 9 | KV cache 与推理两阶段 | 每 token 缓存 `2 × 层数 × 头数 × head_dim` 个值；prefill 并行处理 prompt（算力瓶颈），decode 逐 token 生成（显存带宽瓶颈） |
| 10 | 训练配方 | Adam + 学习率 warmup + cosine 衰减；生产中还要梯度累积与梯度裁剪 |

### 核心技能（能动手做到）

- [ ] 用 NumPy 写出 Embedding、LayerNorm、多头因果注意力、FFN、Transformer block 和完整 `MiniGPT.forward`，并说清每一步的张量形状
- [ ] 手算 GPT-2 Small 的参数量（含/不含 bias、是否 weight tying），解释 124M 是怎么来的
- [ ] 写出数值稳定的 softmax 与交叉熵，并用"初始 loss ≈ ln V"做训练前的健全性检查
- [ ] 看懂本节手写反向传播（交叉熵 → 输出头 → LayerNorm → FFN），并指出它**漏掉了哪些参数的梯度**
- [ ] 实现 temperature = 0 的贪心解码、top-k 与 top-p 采样
- [ ] 按公式估算任意模型的 KV cache 显存，并考虑 GQA（分组查询注意力）的影响

---

## 二、基础自测（选择题）

**Q1.** 下列哪一组是本节（以及 GPT-2）采用的 **pre-norm** Transformer block？

- A. `x = ln1(x + attn(x))`；`x = ln2(x + ffn(x))`
- B. `x = x + attn(ln1(x))`；`x = x + ffn(ln2(x))`
- C. `x = attn(ln1(x))`；`x = ffn(ln2(x))`
- D. `x = ln1(x) + attn(x)`；`x = ln2(x) + ffn(x)`

**Q2.** 词表大小 V = 256、参数随机初始化（输出接近均匀分布）时，交叉熵 loss 最接近：

- A. 0
- B. 1.0
- C. 5.55
- D. 256

**Q3.** GPT-2 Small 使用 weight tying（输出层复用 token embedding 矩阵）。相比不共享，它省下的参数量约为：

- A. 0.8M（位置 embedding 的大小）
- B. 2.4M（一个 block 的注意力权重）
- C. 38.6M（50,257 × 768）
- D. 124M（整个模型）

**Q4.** 注意力分数要除以 `√d_k`，主要是因为：

- A. 减少矩阵乘法的计算量
- B. d_k 较大时点积数值很大，softmax 会进入饱和区、梯度接近 0；缩放后训练更稳定
- C. 让注意力权重之和等于 1
- D. 实现因果 mask

**Q5.** GPT-2 Small（12 层、12 头、head_dim = 64）的 KV cache，每个 token 需要缓存多少个数值？

- A. 768
- B. 9,216
- C. 18,432
- D. 36,864

**Q6.** 关于推理的 prefill 与 decode 两个阶段，说法正确的是：

- A. prefill 逐 token 进行，是显存带宽瓶颈
- B. decode 一次处理整个 prompt，是算力瓶颈
- C. prefill 并行处理整个 prompt，偏算力瓶颈；decode 每步只生成一个 token，偏显存带宽瓶颈
- D. 两个阶段的瓶颈相同，都只取决于 FLOPs

**Q7.** 在本节 `MultiHeadAttention.forward` 中，输入 `x` 形状为 `(2, 10, 768)`、12 个头。注意力分数 `scores` 的形状是：

- A. `(2, 10, 10)`
- B. `(2, 12, 10, 10)`
- C. `(2, 12, 64, 64)`
- D. `(2, 10, 12, 12)`

**Q8.** 对 logits `[2.0, 1.0, 0.5, 0.0, -1.0]` 做 temperature 采样，下列说法正确的是：

- A. T = 0.5 时最高概率 token 的概率比 T = 1.0 时更低
- B. T = 1.5 时分布更平坦，低概率 token 被选中的机会变大
- C. temperature 改变的是 logits 的排序
- D. 无论 T 取何值，本节的 `generate` 都能正常运行

---

## 三、动手 / 代码题

**Q9.** 阅读本节 `train_mini_gpt` 的反向传播部分（节选）：

```python
        dx = dx_pre_ln
        for i in range(len(model.blocks) - 1, -1, -1):
            block = model.blocks[i]
            block_in = block_inputs[i]

            ln2_in = block_in + block.attn.forward(block.ln1.forward(block_in), mask)
            ln2_out = block.ln2.forward(ln2_in)

            dffn, gW1, gb1, gW2, gb2 = ffn_backward(dx, ln2_out, block.ffn)

            dln2_out = dffn
            dln2_in, g_ln2_gamma, g_ln2_beta = layernorm_backward(
                dln2_out, ln2_in, block.ln2
            )

            dx = dx + dln2_in

            block.ffn.W1 -= lr * gW1
            block.ffn.b1 -= lr * gb1
            block.ffn.W2 -= lr * gW2
            block.ffn.b2 -= lr * gb2
            block.ln2.gamma -= lr * g_ln2_gamma
            block.ln2.beta -= lr * g_ln2_beta

        model.ln_f.gamma -= lr * grad_ln_gamma
        model.ln_f.beta -= lr * grad_ln_beta
        model.embedding.token_embed -= lr * grad_token_embed
```

1. 哪些参数在训练中**从未被更新**？它们占默认配置（4 层、128 维、832,256 参数）的多大比例？
2. `grad_token_embed` 只包含了哪一部分梯度？漏掉了哪一部分？
3. 既然梯度不完整，为什么 loss 仍然从 5.57 降到了约 5.06？
4. 如果要把它改成"完整训练"，工程上最合理的做法是什么？

**Q10.** 讲义说"Temperature 0.0 is greedy decoding"，但执行 `generate(model, prompt, temperature=0.0)` 会抛出 `ValueError: probabilities contain NaN`。

```python
        next_logits = next_logits / temperature
        probs = np.exp(next_logits - next_logits.max())
        probs = probs / probs.sum()

        next_token = np.random.choice(len(probs), p=probs)
```

1. 解释 NaN 是怎么产生的。
2. 写一个 `sample_next(next_logits, temperature, top_k=None, top_p=None)`：temperature 为 0 时走贪心；支持 top-k 与 top-p（讲义练习 4）。

**Q11.** 关于 GPT-2 Small 的参数量出现了三个数字：本节 `parameter_breakdown()` 输出 **124,402,944**；讲义表格的合计为 **124,438,272**；Hugging Face 的 GPT-2（`gpt2`）实际参数量为 **124,439,808**。请解释这三个数字分别差在哪里。（提示：GPT-2 的 Q/K/V 投影、注意力输出投影、FFN 两层都带 bias。）

**Q12.** `memory_estimate()` 输出 Llama 3 405B 的 KV cache 为 **1082.3 GB**（FP16、131,072 token）：

```python
        kv_per_token = 2 * layers * heads * head_dim * 2
        kv_full = kv_per_token * max_seq
```

其中 405B 的配置是 `layers=126, heads=128, head_dim=128`。已知 Llama 3 系列使用 GQA（Grouped-Query Attention），所有尺寸都只有 **8 个 KV 头**。请指出问题并重新计算 8B（32 层）、70B（80 层）、405B（126 层）的 KV cache。

---

## 四、面试高频题

**Q13.**（基础必考）从 token ID 到下一个 token 的概率，GPT 的前向传播经过哪些步骤？请标出每一步的张量形状，并说明 GPT-2 Small 的参数主要集中在哪里。

**Q14.**（原理深挖）为什么 GPT-2 及之后的大模型普遍用 pre-norm 而不是原始 Transformer 的 post-norm？残差连接和 LayerNorm 各起什么作用？

**Q15.**（原理深挖）KV cache 是什么？它省掉了哪些计算、又付出了什么代价？为什么说 decode 阶段是 memory-bound？有哪些手段降低 KV cache？

**Q16.**（工程实践）如果让你在单机多卡上真正从零预训练一个 124M 的 GPT-2，你的训练配方是什么？训练开始后你会看哪些信号判断"一切正常"？

**Q17.**（追问型）temperature、top-k、top-p 有什么区别？贪心解码有什么问题？线上对话产品一般怎么设置？

---

## 五、参考答案与解析

### Q1 — 答案：B

Pre-norm：先 LayerNorm，再进子层，再加残差。代码原文：

```python
    def forward(self, x, mask=None):
        x = x + self.attn.forward(self.ln1.forward(x), mask)
        x = x + self.ffn.forward(self.ln2.forward(x))
        return x
```

A 是原始 Transformer 的 post-norm；C 去掉了残差；D 把 LayerNorm 放在了残差支路上，不是任何标准结构。

### Q2 — 答案：C

均匀分布下正确 token 的概率是 `1/V`，交叉熵 = `−ln(1/256) = ln 256 ≈ 5.545`。本次实际运行 Step 0 的 loss 为 5.5682，与理论值吻合。这是训练前最重要的健全性检查：初始 loss 明显偏离 `ln V`，说明初始化或 loss 实现有问题。

### Q3 — 答案：C

token embedding 矩阵是 `50,257 × 768 = 38,597,376`。不共享时输出层需要一个同样大小的矩阵，共享后省下这部分。讲义："it reduces the parameter count by 38M"。同时它让"理解 token"和"预测 token"使用同一个向量空间。

### Q4 — 答案：B

若 q、k 各分量独立、均值 0、方差 1，点积方差为 d_k。d_k = 64 时标准差为 8，softmax 容易变成接近 one-hot，梯度几乎为 0。除以 `√d_k = 8` 把方差拉回 1。C 是 softmax 本身的性质；D 是 mask 的作用。

### Q5 — 答案：C

`2（K 和 V）× 12 层 × 12 头 × 64 维 = 18,432` 个值。FP32 下 1,024 个 token 约 `18,432 × 4 × 1,024 ≈ 75.5MB`（讲义"about 75MB"）；FP16 减半约 37.7MB（代码 `memory_estimate` 输出的 "38 MB"）。D（36,864）是 FP16 下每个 token 的**字节数**。

### Q6 — 答案：C

prefill 时所有 prompt token 已知，可以一次性并行算完注意力，GPU 在做大矩阵乘法，偏算力瓶颈；decode 每步只算一个 token，计算量小，但每一步都要从显存读取全部权重和 KV cache，偏显存带宽瓶颈。讲义："Prefill throughput scales with GPU compute... Decode throughput scales with memory bandwidth."

### Q7 — 答案：B

`x @ W_q` 仍是 `(2, 10, 768)`，`reshape` 成 `(2, 10, 12, 64)`，`transpose(0, 2, 1, 3)` 得到 `(2, 12, 10, 64)`。`Q @ Kᵀ`（`K.transpose(0, 1, 3, 2)` 为 `(2, 12, 64, 10)`）得到 `(2, 12, 10, 10)`：每个 batch、每个头一个 `10 × 10` 的注意力矩阵。因果 mask 形状为 `(10, 10)`，靠广播加到每个头上。

### Q8 — 答案：B

实际计算（softmax 后取 3 位小数）：T = 0.5 → `[0.829, 0.112, 0.041, 0.015, 0.002]`；T = 1.0 → `[0.563, 0.207, 0.126, 0.076, 0.028]`；T = 1.5 → `[0.439, 0.225, 0.161, 0.116, 0.059]`。T 越大越平坦。A 说反了；C 错，除以正数不改变排序；D 错，T = 0 会导致除以 0 产生 NaN（见 Q10）。

### Q9 — 参考答案

1. **从未更新的参数**（已用"训练前后快照对比"实际验证）：每个 block 的 `W_q`、`W_k`、`W_v`、`W_out` 和 `ln1`，以及位置 embedding `pos_embed`。
   - 注意力权重：`4 层 × 4 × 128 × 128 = 262,144`
   - `ln1`：`4 层 × 256 = 1,024`
   - `pos_embed`：`64 × 128 = 8,192`
   - 合计 271,360，占 832,256 的约 **32.6%**。被更新的只有 FFN、`ln2`、`ln_f` 和 `token_embed`。
2. `grad_token_embed = Σ dlogitsᵀ @ x_normed` 只是**输出头**（weight tying 的那一侧）的梯度。token embedding 同时也是**输入层**：反传到最底层的 `dx` 应该按 token ID 累加（scatter-add）到对应的 embedding 行上，这部分被丢弃了；`dx` 在循环结束后没有再被使用。另外，`dx = dx + dln2_in` 只考虑了残差和 FFN 支路，**注意力支路的梯度完全没有反传**。
3. loss 仍能下降，是因为被更新的部分（输出头、FFN、LayerNorm）已经足以学到"字节的边缘分布"和部分局部模式；输出头、`ln_f` 和最上层 block 的 FFN/`ln2` 梯度是精确的，更低层 block 的梯度因为漏掉了上层注意力支路的贡献只是近似值，但方向大体可用。然而模型无法学会"看上下文"——注意力权重始终是随机的，这也是生成结果几乎是乱码的原因之一（200 步、SGD、lr = 3e-4 也是原因）。
4. 合理做法：用 PyTorch/JAX 等自动微分框架实现同一结构，由 autograd 计算全部梯度，再配 AdamW、warmup + cosine、梯度裁剪。讲义也说明真实的 124M 训练"需要 GPU 和 PyTorch"。若坚持用 NumPy 手写，需要补齐注意力的反传（softmax、QKᵀ、多头 reshape 的反向）、`ln1` 反传和 embedding 的 scatter-add，并用有限差分做梯度检查。

### Q10 — 参考答案

1. `next_logits / 0.0`：正数变 `+inf`、负数变 `-inf`、恰好为 0 的变 `nan`。接着 `next_logits - next_logits.max()` 中出现 `inf - inf = nan`，`exp` 后概率向量含 NaN，`np.random.choice` 校验 `p` 时报错。"T = 0 等于贪心"只是 T → 0 时的极限，实现上必须单独分支处理。

2. 参考实现（已在小例子上运行验证）：

```python
import numpy as np

def sample_next(next_logits, temperature=0.8, top_k=None, top_p=None):
    if temperature == 0:                          # 贪心：直接取最大值
        return int(np.argmax(next_logits))
    logits = next_logits / temperature
    if top_k is not None:                         # 只保留前 k 个
        kth = np.sort(logits)[-top_k]
        logits = np.where(logits < kth, -np.inf, logits)
    probs = np.exp(logits - logits.max())
    probs = probs / probs.sum()
    if top_p is not None:                         # nucleus：累计概率首次 ≥ p 的最小集合
        order = np.argsort(probs)[::-1]
        cum = np.cumsum(probs[order])
        cutoff = np.searchsorted(cum, top_p) + 1
        keep = np.zeros_like(probs)
        keep[order[:cutoff]] = 1
        probs = probs * keep
        probs = probs / probs.sum()
    return int(np.random.choice(len(probs), p=probs))
```

验证：logits `[2, 1, 0.5, 0, -1]` 在 T = 1 时概率为 `[0.563, 0.207, 0.126, 0.076, 0.028]`，累计为 `[0.563, 0.770, 0.896, ...]`。`top_p = 0.8` 时保留前 3 个（累计 0.896 首次 ≥ 0.8），`top_k = 2` 时只会采到 0 或 1，T = 0 时恒返回 0。

要点：top-k 先于 softmax 用 `-inf` 屏蔽；top-p 在 softmax 之后按概率排序截断，再重新归一化；先 temperature 再截断是常见顺序。

### Q11 — 参考答案

逐项对比每个 block 的参数（d = 768，FFN 隐层 3072）：

| 部分 | 权重 | bias |
|------|------|------|
| Q/K/V 投影 | `3 × 768 × 768` | `3 × 768 = 2,304` |
| 注意力输出投影 | `768 × 768` | `768` |
| FFN 两层 | `768 × 3072 + 3072 × 768` | `3072 + 768 = 3,840` |
| 两个 LayerNorm | `2 × 2 × 768 = 3,072` | — |

- **HF 实际值 124,439,808**：每 block `7,080,960`（权重 + LN）+ `6,912`（全部 bias）= `7,087,872`；× 12 = `85,054,464`；加 embedding `38,597,376 + 786,432 = 39,383,808`；再加最终 LayerNorm `1,536`。
- **代码 124,402,944**：`per_block_ff = 2 * dim * ff + dim + ff` 计入了 FFN bias，但注意力只算 `4 * dim * dim`，**漏了注意力 bias**：`12 × 3,072 = 36,864`，`124,439,808 − 36,864 = 124,402,944`。（`MiniGPT` 类本身的注意力也没有 bias，代码内部是自洽的。）
- **讲义 124,438,272**：表格里"每 block 7,080,960"是**不含 bias** 的数，但"12 blocks = 85,054,464"用的却是**含 bias** 的数；而且合计时**漏加了表中列出的最终 LayerNorm（1,536）**：`124,439,808 − 1,536 = 124,438,272`。

结论：数参数时要明确"是否含 bias、是否 weight tying、是否含最终 LN"。面试中能说出"embedding 约占 31%（38.6M / 124M），12 个 block 约占 68%"就足够有说服力。

### Q12 — 参考答案

问题：代码用**查询头数**（128）计算 KV cache。GQA 中多个查询头共享一组 K/V，KV cache 只与 **KV 头数**有关。修正为：

```python
kv_per_token = 2 * layers * num_kv_heads * head_dim * 2   # 2(K,V) × ... × 2 字节(FP16)
```

重新计算（KV 头 = 8、head_dim = 128、FP16；已实际计算验证）：

| 模型 | 每 token 字节 | 序列长度 | KV cache（修正） | 代码原输出 |
|------|-------------|---------|----------------|-----------|
| Llama 3 8B（32 层） | 131,072 | 8,192 | ≈ 1.07 GB | 4.3 GB（高估 4 倍） |
| Llama 3 70B（80 层） | 327,680 | 8,192 | ≈ 2.68 GB | 21.5 GB（高估 8 倍） |
| Llama 3 405B（126 层） | 516,096 | 131,072 | ≈ 67.6 GB | 1082.3 GB（高估 16 倍） |

高估倍数正好等于"查询头数 / KV 头数"（32/8、64/8、128/8）。GQA 正是为降低 KV cache 而设计的。修正后，"405B 单条 128K 序列的 KV cache 超过 10GB"（讲义原话）依然成立，但量级是几十 GB 而不是 1TB。附带一点：讲义写 405B 有 128 层，实际是 126 层（代码中的 126 是对的）。

### Q13 — 参考回答要点

- **步骤与形状**（B = batch，S = 序列长度）：
  1. token IDs `(B, S)`；
  2. token embedding 查表 `(B, S, 768)`；position embedding `(S, 768)` 广播相加；
  3. 12 个 block，每个 block 内：LN → 多头注意力（`(B,12,S,64)`，分数 `(B,12,S,S)`）→ 残差；LN → FFN（`768→3072→768`）→ 残差；形状始终保持 `(B, S, 768)`；
  4. 最终 LayerNorm；
  5. 乘以 `token_embedᵀ` 得 logits `(B, S, 50257)`；
  6. softmax 得到每个位置下一个 token 的分布（训练时对全部位置算 loss，生成时只取最后一个位置）。
- **参数分布**：每个 block 约 7.08M（注意力 2.36M + FFN 4.72M），12 个 block 约 85M；token embedding 38.6M（约 31%）；位置 embedding 0.79M。FFN 占 block 参数的约 2/3。
- 加分点：说明 weight tying 让 embedding 同时充当输出层；训练时的 logits 计算 `S × 768 × 50257` 是不小的开销。

### Q14 — 参考回答要点

- **残差连接**：`x + f(x)` 让梯度可以绕过子层直接回传，避免深层网络梯度消失；讲义："gradients can flow directly from the loss to any layer through the skip path"。
- **LayerNorm**：在特征维度上把激活归一化为均值 0、方差 1，再用可学习的 γ、β 缩放平移，稳定每层输入的尺度。
- **Pre-norm vs post-norm**：
  - post-norm：`LN(x + f(x))`，LayerNorm 在残差主干上，深层时梯度需要穿过每一层的 LN，训练不稳定，通常依赖精细的 warmup；
  - pre-norm：`x + f(LN(x))`，残差主干是一条"干净的恒等路径"，梯度更容易传到底层，深模型更容易训练；代价是需要在最后加一个 `ln_f`（本节代码中的 `self.ln_f`）。
- 加分点：很多后续开源模型把 LayerNorm 换成更便宜的 RMSNorm，但仍是 pre-norm 结构。

### Q15 — 参考回答要点

- **是什么**：自回归生成时，历史 token 的 K、V 不会改变，把每层的 K、V 缓存下来；生成新 token 时只为它计算 Q、K、V，再与缓存拼接后做注意力。
- **省掉了什么**：避免每步对全部历史 token 重新做 `x @ W_k`、`x @ W_v`。讲义：没有缓存时生成第 N 个 token 要重算前 N−1 个 token，总代价 O(N³)；有缓存后 K/V 计算每步 O(1)，注意力分数仍是 O(N)。
- **代价**：显存。每 token `2 × 层数 × KV 头数 × head_dim × 字节数`，与序列长度和并发数成正比；长上下文推理因此成为 memory-bound。
- **为什么 decode 是 memory-bound**：每步只处理 1 个（或少量）token，计算量很小，但必须把全部权重和 KV cache 从显存读一遍，瓶颈在带宽。所以 decode 吞吐主要看显存带宽，常用"增大 batch 并发"来摊薄读权重的开销。
- **降低 KV cache 的手段**：MQA/GQA 减少 KV 头数（见 Q12，Llama 3 用 8 个 KV 头）；KV cache 量化（FP8/INT8）；分页管理（PagedAttention）减少碎片；滑动窗口注意力限制缓存长度。
- 加分点：能现场估算一个模型的 KV cache，并指出原代码忽略 GQA 的问题。

### Q16 — 参考回答要点

- **数据**：用 03 节的管道把语料预先分词、打包成定长序列，存成二进制分片；划出验证集。
- **模型与初始化**：12 层、12 头、768 维，embedding 和线性层 std = 0.02 初始化，weight tying。
- **优化器与调度**：AdamW（带 weight decay），学习率先线性 warmup 再 cosine 衰减（讲义："warmup-then-decay 被每个主流 LLM 使用"）；梯度裁剪（如全局范数 1.0）；用梯度累积达到足够大的有效 batch。
- **效率**：混合精度（bf16）、FlashAttention 类实现、多卡数据并行（见下一节）。
- **健康信号**：
  - 第 0 步 loss ≈ `ln(50257) ≈ 10.8`；
  - 训练/验证 loss 平稳下降，无 NaN、无剧烈尖峰；
  - 梯度范数稳定，学习率曲线符合预期；
  - 定期采样生成文本，观察从乱码 → 单词 → 通顺短句的演进；
  - GPU 利用率高，dataloader 不成为瓶颈。
- 常见误区：不做 warmup 直接用峰值学习率（讲义："Starting with a high learning rate causes the model to diverge"）；只看训练 loss 不看验证 loss。

### Q17 — 参考回答要点

- **temperature**：logits 除以 T 再 softmax。T < 1 更尖锐、更确定；T > 1 更平坦、更多样；T → 0 退化为贪心（实现上需单独处理）。
- **top-k**：只在概率最高的 k 个 token 中采样。缺点是 k 固定：分布很尖时 k 个里也可能混入垃圾，分布很平时又可能截掉合理选项。
- **top-p（nucleus）**：取累计概率首次达到 p 的最小集合，集合大小随分布自适应。
- **贪心的问题**：容易陷入重复循环、输出单调；对开放式生成质量差，但对需要确定性的任务（分类式回答、代码补全中的部分场景）可以用。
- **线上常见设置**：对话类常用 T 在 0.7 左右并配合 top-p 0.9–0.95；需要可复现或结构化输出时用低温度或贪心；再配合重复惩罚、停止词。具体数值需按产品评测调整。
- 加分点：说明采样参数只改变"从分布中怎么选"，不改变模型本身；讲义练习 4 要求比较 T = 0.8 时 top-k = 50 与 top-p = 0.95 的效果。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 01 Tokenizers](../../01-tokenizers/docs/zh.md)、[阶段 10 · 02 从头开始构建 Tokenizer](../../02-building-a-tokenizer/docs/zh.md)：词表大小决定 embedding 与输出层的形状。
- [阶段 10 · 03 用于预训练的数据管道](../../03-data-pipelines/docs/zh.md)：训练数据的打包与加载。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)、[阶段 07 · 03 多头注意力](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：注意力与多头机制。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：自回归目标与因果 mask。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：理解本节手写反向传播。

### 本节被哪些后续内容用到
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：把同样的训练循环扩展到多卡。
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：在预训练模型上继续训练。
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：KV cache、prefill/decode 的深入优化。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的实现细节。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../34-gradient-checkpointing/docs/zh.md)：训练大模型时的显存优化。
- [阶段 19 · 35 GPT 模型组装](../../../19-capstone-projects/35-gpt-model-assembly/docs/zh.md)、[阶段 19 · 36 训练循环与评估](../../../19-capstone-projects/36-training-loop-eval/docs/zh.md)：综合项目中完整实现 GPT 与训练循环。

### 延伸关键词
`pre-norm / post-norm` · `RMSNorm` · `GELU` · `weight tying` · `causal mask` · `KV cache` · `GQA / MQA` · `prefill / decode` · `AdamW` · `warmup + cosine` · `gradient clipping` · `top-k / top-p` · `autograd`
