# 测验 · GPT — 因果语言建模（GPT — Causal Language Modeling）

> **阶段 07 · Transformers 深入 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 因果语言建模目标 | 学 `P(x_t \| x_<t)`：给定前 t-1 个 token，预测第 t 个 token 的分布；能生成文本全靠这个目标 |
| 2 | 因果掩码（causal mask） | `M[i,j] = 0 (j ≤ i)`、`-inf (j > i)`，在 softmax **之前**加到分数上；`exp(-inf)=0`，未来位置权重为 0 |
| 3 | 掩码从哪里来 | 前缀平均 `tril(ones)/行和` → 学习的静态分数 + softmax → 内容相关分数 `QKᵀ/√d_k`；三阶段共享"下三角、行和为 1"的不变量 |
| 4 | 训练并行、推理串行 | 训练一次前向就得到 N 个位置的 next-token 预测；推理逐 token 生成，串行深度 = 输出长度（自回归税） |
| 5 | 错位一位的损失（shift-by-one） | 输入 `[t1,t2,t3]`、目标 `[t2,t3,t4]`，对每个位置算 `-log P(target_i)` 再求和/平均；预训练、SFT 都是同一个 loss |
| 6 | Teacher forcing | 训练时喂真实的前缀而不是模型自己的预测；推理时只能喂自己的输出 |
| 7 | 解码策略 | greedy / temperature / top-k / top-p / min-p / speculative decoding 各有适用场景；采样选择对输出质量影响很大 |
| 8 | Temperature 与截断 | `logits / T`：T→0 趋近 greedy、T→∞ 趋近均匀；top-p 取累计概率 ≥ p 的最小集合，min-p 保留 `p ≥ min_p × max_p` 的 token |
| 9 | GPT 配方 | decoder-only + 扩规模 + in-context learning + RLHF + Pre-norm/RoPE/SwiGLU；核心架构自 GPT-2 以来变化不大 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 写出 `causal_mask(n)`，把它加到随机分数上做逐行 softmax，验证结果是下三角且每行和为 1
- [ ] 用 NumPy 写出讲义的"三阶段"推导：`tril(ones)` 前缀平均、加 `-inf` 的 softmax、`QKᵀ/√d_k`，并验证改动未来 token 不影响过去位置的输出
- [ ] 写出 shift-by-one 的交叉熵 `cross_entropy_shifted`，并能解释为什么随机 logits 的 loss 往往**高于** `ln V`
- [ ] 从零实现 greedy、temperature、top-k、top-p、min-p 五种采样，并能手算给定分布下 top-p / min-p 保留了哪些 token
- [ ] 给定任务（代码补全、闲聊、结构化输出、评测复现）能说出合适的采样参数和停止条件
- [ ] 能用 Hugging Face `AutoModelForCausalLM` + `generate()` 跑一次带 `temperature`/`top_p` 的生成，并说出 `generate()` 内部的循环在做什么

---

## 二、基础自测（选择题）

**Q1.** 对长度为 N 的序列施加因果掩码并做 softmax 之后，attention 权重矩阵具有什么性质？

- A. 上三角，且每列和为 1
- B. 下三角（含对角线），且每行和为 1
- C. 对角矩阵，每个 token 只关注自己
- D. 对称矩阵，因为 `QKᵀ` 本身对称

**Q2.** 一个训练样本的 token 序列是 `[t1, t2, t3, t4]`，按讲义的 shift-by-one 方式，模型的输入和目标分别是：

- A. 输入 `[t1, t2, t3, t4]`，目标 `[t1, t2, t3, t4]`
- B. 输入 `[t2, t3, t4]`，目标 `[t1, t2, t3]`
- C. 输入 `[t1, t2, t3]`，目标 `[t2, t3, t4]`
- D. 输入 `[t1, t3]`，目标 `[t2, t4]`

**Q3.** 关于"训练并行、推理串行"，下列说法**正确**的是：

- A. 训练时也必须逐 token 前向，只是 GPU 足够快
- B. 因果掩码让一次前向同时得到 N 个位置的 next-token 预测，所以训练可以沿序列并行；推理时第 t+1 个 token 依赖第 t 个 token 的采样结果，只能串行
- C. 有了 KV cache 以后，推理也能像训练一样一次性并行生成全部 token
- D. 推理串行是因为推理时不使用因果掩码

**Q4.** 把 logits 除以温度 T=2.0 再做 softmax，相比 T=1.0：

- A. 分布更尖锐，argmax 可能改变
- B. 分布更平坦，但 argmax 不变
- C. 分布不变，只是采样速度更快
- D. 所有 token 概率变成相等

**Q5.** 某一步的 next-token 概率（已排序）为：`0.380, 0.255, 0.127, 0.069, 0.047, 0.038, 0.031, 0.023, 0.017, 0.013`。用 top-p=0.9，会保留几个 token？

- A. 3 个
- B. 4 个
- C. 6 个
- D. 10 个

**Q6.** 关于 min-p 采样（`min_p = 0.1`），下列说法**错误**的是：

- A. 阈值是 `0.1 × 当前最大概率`，所以阈值随分布的尖锐程度自适应变化
- B. 当模型非常确定（最大概率 0.95）时，几乎只保留头部 token
- C. 当分布很平坦时，会保留更多候选 token
- D. min-p 总是保留固定数量的 token，与分布形状无关

**Q7.** 为什么因果掩码要在 softmax **之前**加 `-inf`，而不是在 softmax **之后**把未来位置的权重直接置 0？

- A. 两者完全等价，只是写法习惯不同
- B. softmax 之后直接置 0 会让每行权重之和小于 1，不再是概率分布；在 softmax 之前加 `-inf`，`exp(-inf)=0`，归一化只在可见位置之间进行
- C. 因为 softmax 之后的矩阵无法修改
- D. 因为 `-inf` 能让梯度变大，训练更快

---

## 三、动手 / 代码题

**Q8.** `code/main.py` 的 `demo_ce_loss()` 运行输出如下：

```text
loss with biased logits (trained-ish):  1.145
loss with random logits:                2.418
random-baseline loss (ln V = ln 10):      2.303
```

请回答：(1) `cross_entropy_shifted` 中第 i 个位置的 logits 是和哪个 token 比较的？对长度为 6 的 `seq`，一共平均了几个位置？(2) 为什么"完全随机"的 logits 得到的 loss（2.418）反而**高于** `ln 10 = 2.303`？什么样的 logits 会精确得到 `ln 10`？

```python
def cross_entropy_shifted(logits_per_pos, target_ids):
    """Next-token CE: logit_i vs target_{i+1}."""
    total = 0.0
    count = 0
    for i in range(len(target_ids) - 1):
        probs = softmax(logits_per_pos[i])
        p = probs[target_ids[i + 1]]
        total += -math.log(max(p, 1e-12))
        count += 1
    return total / count
```

**Q9.** 代码里已经有一个 `softmax(logits)`，为什么还要单独写 `apply_softmax_row`？如果把 `demo_causal_mask` 里的 `apply_softmax_row(row)` 换成 `softmax(row)`，在因果掩码下结果会变吗？在什么样的掩码下会出问题？

```python
def apply_softmax_row(row):
    finite = [x for x in row if x != float("-inf")]
    if not finite:
        return [0.0] * len(row)
    m = max(finite)
    exps = [math.exp(x - m) if x != float("-inf") else 0.0 for x in row]
    s = sum(exps)
    return [e / s if s > 0 else 0.0 for e in exps]
```

**Q10.** 用 NumPy 实现讲义"Stage 3"的单头因果自注意力 `causal_attention(X, Wq, Wk, Wv)`，并写一个测试：随机修改序列最后一个 token 的输入向量，验证前 N-1 个位置的输出**完全不变**（这就是"不能偷看答案"的可验证定义）。

---

## 四、面试高频题

**Q11.**（基础必考）GPT 和 BERT 的训练目标有什么区别？为什么说"loss 决定了模型能不能生成"？为什么今天主流大模型几乎都是 decoder-only？

**Q12.**（原理深挖）请不用"打补丁"的说法，从"前缀平均"出发推导出因果掩码，并解释 `-inf` 的作用。

**Q13.**（原理深挖）什么是 teacher forcing？它带来了什么问题（exposure bias）？为什么即使有这个问题，LLM 预训练仍然只用 teacher forcing？

**Q14.**（工程实践）你要为以下四个场景配置解码参数：代码补全、开放式闲聊、JSON 结构化输出、需要可复现的离线评测。分别怎么配？为什么开放式对话不能用纯 greedy？

**Q15.**（追问型）为什么说解码是所有 LLM 的延迟瓶颈？KV cache 和 speculative decoding 分别解决了它的哪一部分问题？

**Q16.**（追问型）GPT-2 起常见的"输入 embedding 与输出 unembedding 权重共享（weight tying）"是什么？有什么好处和代价？

---

## 五、参考答案与解析

### Q1 — 答案：B

`M[i,j] = -inf (j > i)` 让对角线以上的位置在 softmax 后变成 0，所以矩阵是**下三角（含对角线）**；softmax 是按行做的，所以每**行**和为 1——第 i 行是"位置 i 对位置 0…i 的概率分布"。A 把行列搞反了；C 只是 n=1 的特例；D 错在 `QKᵀ` 一般不对称（Q、K 投影矩阵不同），加了掩码更不可能对称。代码 `demo_causal_mask` 的输出可以直接验证：第 0 行是 `1.000 0.000 …`，第 3 行只有前 4 列非零。

### Q2 — 答案：C

位置 i 的输出要预测位置 i+1 的 token。输入去掉最后一个、目标去掉第一个，正好错开一位。A 是"复制输入"，在因果掩码下位置 i 能看到自己，会学成恒等映射；B 方向反了；D 是无意义的切分。

### Q3 — 答案：B

训练时整段真实序列是已知的（teacher forcing），掩码保证每个位置只看过去，一次前向就得到 N 个预测和 N 个 loss。推理时下一个 token 要等上一个 token 被采样出来才知道，所以串行深度 = 输出长度。C 错：KV cache 只省掉对历史 token 的重复计算，**不能**消除串行依赖。D 错：推理同样使用因果掩码（尤其是 prefill 阶段）。

### Q4 — 答案：B

`softmax(z/T)`：T > 1 时 logits 之间的差距被缩小，分布变平坦；T < 1 时差距被放大，分布更尖锐。但除以一个正数不改变大小顺序，所以 **argmax 不变**——这也是 greedy 不受温度影响的原因。D 只在 T→∞ 时才成立。用本节代码的 logits 算：T=1 时 "the" 概率 0.380，T=2 时降为 0.226，T=0.7 时升到 0.497。

### Q5 — 答案：C

累计概率：0.380 → 0.635 → 0.762 → 0.831 → 0.878 → **0.916**。第 6 个 token 加进来后首次 ≥ 0.9，所以保留 6 个（`the, dog, mat, jumped, cat, ran`），然后重新归一化再采样。这就是 `sample_top_p` 里 `cutoff = i + 1` 的含义。注意 top-p 保留的是"累计概率首次达到 p 的最小集合"，包括让累计值越过 p 的那一个。

### Q6 — 答案：D

min-p 的阈值 `min_p × max_p` 依赖当前分布：模型很确定时（max_p 大）阈值高、候选少；分布平坦时阈值低、候选多。这正是它"自适应"的地方，所以 A、B、C 都对，D 描述的是 top-k（固定 k 个）。顺带：Q5 的分布上 min-p=0.1 的阈值是 `0.1 × 0.380 = 0.038`，保留 `the, dog, mat, jumped, cat, ran` 六个（ran 的 0.0381 刚好压线）。

### Q7 — 答案：B

softmax 的分母包含整行所有位置。如果先 softmax 再把未来位置置 0，可见位置的权重已经被"未来"分走了一部分，行和小于 1，而且未来 token 的分数仍然通过分母影响了过去位置的输出——**信息泄漏依然存在**。在 softmax 之前加 `-inf`，`exp(-inf)=0`，分母里根本不含未来位置。讲义的说法是：`-inf` 掩码就是第一阶段前缀平均里那些"0 系数"在 softmax 输入域里的翻译。

### Q8 — 参考答案

(1) 第 i 个位置的 logits 和 `target_ids[i + 1]` 比较——这就是 shift-by-one。循环 `range(len(target_ids) - 1)`，长度为 6 的序列有 5 个预测位置，最后一个位置的 logits 没有"下一个 token"可比，被丢弃；`count = 5`，返回 5 个位置的平均 loss。

(2) 当所有 logits 都相等（例如全 0）时，softmax 是严格均匀分布，每个位置的 loss 恰好是 `-log(1/10) = ln 10 = 2.303`。随机 logits 并不是"不偏不倚"：它们服从 `N(0,1)`，每个位置都会随机地"自信地偏向"某些 token，而正确 token 平均来说并不在其中，于是被分到的概率经常小于 1/10。数学上 `CE = logsumexp(z) - z_target`，`E[logsumexp(z)]` 大于 `ln V`（对 V=10、σ=1，期望 CE 约为 2.73；本次只有 5 个位置，样本噪声大，得到 2.418）。

工程启示：这也是语言模型初始化时会把输出层/embedding 初始化得比较小的原因之一——训练第 0 步的 loss 应该接近 `ln V`，如果远高于 `ln V`，说明初始 logits 尺度过大，是一个值得排查的信号。而 "trained-ish" 那组把正确 token 的 logit 加了 2.0，loss 降到 1.145，明显低于基线。

### Q9 — 参考答案

在因果掩码下**结果不变**。因果掩码的对角线永远是 0，每一行至少有一个有限值，`softmax` 里 `m = max(logits)` 是有限数，`math.exp(-inf - m) = 0.0`，计算完全正常。

`apply_softmax_row` 防的是**整行全是 `-inf`** 的情况：此时 `max(row) = -inf`，`-inf - (-inf) = nan`，`math.exp(nan) = nan`，整行变成 NaN 并传染给后续所有计算。这种情况在因果掩码里不会出现，但在 **padding 掩码**（左 padding 的 pad 位置作为 query 时可能整行都被屏蔽）、或因果掩码与 padding 掩码叠加时可能出现。`apply_softmax_row` 只对有限值求 max，并在全被屏蔽时返回全 0 行。

PyTorch 的 `F.scaled_dot_product_attention` 等实现里，全屏蔽行产生 NaN 也是真实存在的坑，工程上常见做法是用一个很大的有限负数（如 `torch.finfo(dtype).min`）代替 `-inf`，或者显式处理全屏蔽行。

### Q10 — 参考答案

```python
import numpy as np

def softmax(x, axis=-1):
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)

def causal_attention(X, Wq, Wk, Wv):
    n = X.shape[0]
    Q, K, V = X @ Wq, X @ Wk, X @ Wv
    d_k = Q.shape[-1]
    S = Q @ K.T / np.sqrt(d_k)
    S = S + np.triu(np.full((n, n), -np.inf), k=1)   # 未来位置 -> -inf
    A = softmax(S, axis=1)                            # 每行是概率分布
    return A @ V, A

rng = np.random.default_rng(0)
n, d, dk = 6, 8, 4
X = rng.normal(size=(n, d))
Wq, Wk, Wv = (rng.normal(size=(d, dk)) for _ in range(3))

out1, A = causal_attention(X, Wq, Wk, Wv)
X2 = X.copy()
X2[-1] = rng.normal(size=d) * 10        # 大幅改动最后一个 token
out2, _ = causal_attention(X2, Wq, Wk, Wv)

assert np.allclose(np.triu(A, k=1), 0)          # 下三角
assert np.allclose(A.sum(axis=1), 1)            # 行和为 1
assert np.allclose(out1[:-1], out2[:-1])        # 前 n-1 个位置完全不受影响
assert not np.allclose(out1[-1], out2[-1])      # 最后一个位置当然会变
print("causality verified")
```

要点：①`np.triu(..., k=1)` 只屏蔽严格上三角，对角线保留（位置 i 能看自己）；②`softmax` 先减行最大值，`-inf - 有限数` 仍是 `-inf`，`exp` 后为 0，不会出 NaN；③"改未来、不改过去"是比肉眼看矩阵更严格的因果性测试，在实现多层 GPT 时同样适用（多层堆叠后依然成立，因为每层都只从过去聚合信息）。

### Q11 — 参考回答要点

- **目标不同**：GPT 学 `P(x_t | x_<t)`（因果 LM），BERT 学 `P(x_masked | x_unmasked)`（掩码 LM，双向看上下文）。
- **为什么 loss 决定能否生成**：GPT 的目标本身就是一个可以链式展开的序列概率 `P(x) = Π P(x_t | x_<t)`，可以一个 token 一个 token 地采样；BERT 训练时依赖两侧上下文，没有定义"从左到右"的生成过程，所以天然适合理解/分类/抽取，而不适合生成。
- **为什么 decoder-only 胜出**：①一个目标同时覆盖理解和生成，任何任务都能写成"续写"；②每个 token 都提供训练信号（BERT 只有约 15% 被掩码的 token 有 loss），数据效率高；③架构简单（无 encoder、无 cross-attention），扩规模和推理优化（KV cache）都很顺；④规模上去后出现 in-context learning，few-shot 不用微调。
- **常见误区**：说"GPT 用 decoder 所以不能理解"——decoder-only 照样能做分类，只是信息只从左往右流动。

### Q12 — 参考回答要点

- **第 1 阶段（前缀平均）**：位置 i 的输出 = 位置 0…i 的平均。矩阵写法 `A = tril(ones(n,n))`，每行除以行和，`out = A @ X`。对角线以上本来就是 0——未来从未进入求和，不存在"屏蔽"。
- **第 2 阶段（学习的静态权重）**：把 1 换成可学习分数 `S`，行和不再为 1，改用 softmax 归一化。但 softmax 永远不输出精确的 0，会破坏因果性——除非未来位置的分数是 `-inf`，因为 `exp(-inf) = 0`。
- **第 3 阶段（内容相关权重）**：`S = QKᵀ/√d_k`，分数取决于 token 内容，掩码、softmax、矩阵乘完全不变。
- **结论**：三个阶段的不变量是"下三角、行随机（row-stochastic）矩阵 × 序列"。`-inf` 掩码不是新机制，它是前缀平均里那些 0 系数在 softmax 输入域的翻译。
- **加分点**：指出实现上常用 `torch.tril` 生成掩码，代价几乎为零；FlashAttention 等 kernel 有专门的 causal 模式，可以直接跳过整个上三角块的计算。

### Q13 — 参考回答要点

- **定义**：训练时每个位置的输入都是**真实**的历史 token，而不是模型上一步自己的预测（讲义 Key Terms：feed the true previous token）。
- **好处**：配合因果掩码，整段序列一次前向即可并行训练；梯度信号稳定。
- **问题（exposure bias）**：训练时模型从未见过"自己犯错后的前缀"，推理时一旦生成了一个不太对的 token，后续条件分布就偏离训练分布，错误可能累积（重复、跑题）。
- **为什么仍只用 teacher forcing**：并行性带来的训练效率无可替代；规模足够大、数据足够多时，模型的预测分布本身就很接近真实分布；后训练阶段（RLHF / DPO 等）在模型**自己生成**的样本上优化，部分弥补了这个缺口；解码端还可以用采样截断（top-p、min-p）等方式减轻长尾错误。
- **常见误区**：把 teacher forcing 当成只有 seq2seq 才有的技巧——讲义明确说它是每个 seq2seq LM 的标准做法，GPT 的预训练本质上就是 teacher forcing。

### Q14 — 参考回答要点

| 场景 | 建议配置 | 理由 |
|------|---------|------|
| 代码补全 | greedy 或低温度（如 0.2）+ top-p 1.0 | 正确答案往往唯一，多样性收益小；高温度会引入语法/逻辑错误 |
| 开放式闲聊 | temperature ≈ 0.7 + min-p ≈ 0.1（或 top-p 0.9） | 需要多样性；min-p 能自适应地砍掉长尾 |
| JSON 结构化输出 | 低温度，**绝不 > 1.0**；配合停止符和格式校验（或约束解码） | 格式错误的代价远大于多样性收益 |
| 可复现评测 | greedy 或固定 seed；记录全部采样参数 | 结果要能复现、能对比 |

- **为什么闲聊不能用纯 greedy**：greedy 每步都取局部最优，很容易陷入高概率的循环片段（重复同一句话），输出也单调。讲义配套的 skill 明确"拒绝为开放式对话推荐纯 greedy——模型会循环"。
- **加分点**：提到停止条件（`max_new_tokens`、停止 token 列表、像 `</tool_call>` 这样的模式停止）和重复惩罚；说明 temperature 应先于 top-p 应用（top-p 的截断集合依赖温度后的分布）。

### Q15 — 参考回答要点

- **瓶颈来源**：推理是自回归的，生成 L 个 token 就要做 L 次串行前向，串行深度 = 输出长度（讲义称为 autoregressive tax）。每次只产出 1 个 token，GPU 的并行能力在 decode 阶段很难被用满。
- **KV cache**：缓存历史 token 每层的 K、V，新 token 只需算自己的 Q/K/V 并与缓存做 attention，避免每步重算整个前缀。它降低的是**每一步**的计算量，但**不改变步数**。
- **Speculative decoding**：用小的 draft 模型一次提议 N 个 token，大模型一次前向**并行验证**，接受其中正确的前缀。它减少的是**大模型的串行调用次数**，讲义给出的量级是同等质量下 2–3× 的延迟降低。
- **加分点**：区分 prefill（并行、计算密集）与 decode（串行、访存密集）；提到生产推理栈（vLLM、TensorRT-LLM、llama.cpp 等）还会做 continuous batching、KV cache 分页。具体机制见第 12 节和第 16 节。

### Q16 — 参考回答要点

- **做法**：输出层（LM head，把 `d_model` 维隐状态映射到词表 logits）直接复用 token embedding 矩阵的转置，`logits = h @ Eᵀ`。
- **好处**：①省参数：词表 V × d_model 的矩阵只存一份（小模型里词表矩阵占比很大，省得明显）；②输入和输出共享同一个"词向量空间"，起到正则作用，对小数据/小模型往往有帮助。
- **代价**：输入端（"这个 token 是什么"）和输出端（"下一个 token 可能是什么"）被迫用同一组向量表示，限制了表达能力；规模很大时省下的参数占比变小，因此并非所有大模型都共享。
- **常见误区**：以为 tying 会影响因果性或 loss 定义——它只是参数共享，和掩码、目标函数都无关。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：`softmax(QKᵀ/√d_k)V` 的计算过程。
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：decoder block 中的 masked self-attention。
- [阶段 07 · 06 BERT——掩码语言建模](../../06-bert-masked-language-modeling/docs/zh.md)：双向编码器，与本节的单向目标形成对照。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：交叉熵与 `ln V` 基线。

### 本节被哪些后续内容用到
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：解决本节提出的"自回归税"。
- [阶段 07 · 13 Scaling Laws](../../13-scaling-laws/docs/zh.md)：GPT 配方中"怎么花算力"。
- [阶段 07 · 14 从零构建 Transformer——综合项目](../../14-build-a-transformer-capstone/docs/zh.md)：把因果掩码、shift-by-one loss、采样组装成完整模型。
- [阶段 07 · 16 Speculative Decoding](../../16-speculative-decoding/docs/zh.md)：本节解码策略表中最后一行的完整展开。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：在真实数据上用同一个 next-token loss 训练。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：GPT 配方中把预训练模型变成助手的后训练环节。
- [阶段 05 · 20 结构化输出与约束解码](../../../05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding/docs/zh.md)：在采样阶段对 logits 加约束。

### 延伸关键词
`beam search` · `repetition penalty` · `exposure bias` · `perplexity` · `weight tying` · `continuous batching` · `typical sampling` · `contrastive decoding`
