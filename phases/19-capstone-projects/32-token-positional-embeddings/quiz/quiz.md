# 测验 · Token 与位置 Embeddings（Token and Positional Embeddings）

> **阶段 19 · 综合项目 · 第 32 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 形状契约 | embedding 阶段把 `(B, T)` 的 token id 变成 `(B, T, D)` 的浮点张量；之后整个网络都在 `D` 维上工作 |
| 2 | Token embedding = 查表 | 参数矩阵 `(V, D)`，前向就是"按 id 取行"（`nn.Embedding`），初始化为均值 0、std 0.02 的高斯 |
| 3 | 稀疏梯度 | 反向传播只给本批出现过的行累加梯度；没出现的行这一步梯度为 0；同一 id 出现 n 次，梯度累加 n 次 |
| 4 | Learned 位置 embedding | 第二张表 `(L, D)`，用位置 id `0..T-1` 查表；多 `L·D` 个参数，且**物理上**不存在第 `L` 行，超过就无法处理 |
| 5 | Sinusoidal 位置 embedding | `pe[p,2k]=sin(p/10000^(2k/D))`、`pe[p,2k+1]=cos(...)`，零参数；本节代码预先算好 `L` 行的表，超过 `L` 同样报错 |
| 6 | 频率分布 | 第 k 对的波长 `2π·10000^(2k/D)`：k=0 波长约 6.28（变化最快、编码精细位置），k 越大波长越长（编码粗略位置）——讲义把这一点说反了 |
| 7 | 相对位置的线性性 | 同一频率上 sin/cos 成对，`pe[p+k] = R_k · pe[p]`，`R_k` 是只依赖 k 的分块旋转矩阵，注意力可以通过线性投影学到"往回看 k 个" |
| 8 | 组合方式是相加 | `tok (B,T,D) + pos (T,D)→(1,T,D)` 广播相加，而不是拼接；`D` 在全网保持不变 |
| 9 | 邻近位置余弦相似度 | Sinusoidal：`cos(pe[p], pe[p+k]) = (2/D)·Σ cos(ω_i k)`，只依赖 k；Learned 初始化时各行独立，≈0 |
| 10 | 本节没做的 | RoPE、ALiBi 作用在 attention 的 Q/K 上而非输入；本节也不训练 embedding（没有 loss） |

### 核心技能（能动手做到）

- [ ] 用 `nn.Embedding` 写出 token embedding 与 learned 位置 embedding，并说清 `(B,T) → (B,T,D)` 和 `(T,) → (T,D)` 的形状
- [ ] 不看代码写出 sinusoidal 表的构造（`arange` + 广播 + `0::2/1::2` 交错赋值），并手算 `D=4` 时任意位置的向量
- [ ] 用 `register_buffer` 存放不参与训练的张量，并解释它与 `nn.Parameter` 在 `parameters()`、`.to(device)`、`state_dict` 上的区别
- [ ] 计算任意配置下 embedding 层的参数量（含/不含 learned 位置表），例如 GPT-2 Small 的 `50257×768` 与 `1024×768`
- [ ] 用 autograd 验证"只有被查到的行有梯度"，并能解释重复 id 的梯度累加
- [ ] 推导 sinusoidal 的"平移 = 旋转"性质，并用代码数值验证
- [ ] 改写 sinusoidal 模块，让它按需计算任意位置（真正"可外推"），并支持起始偏移 `start`（为 KV cache 生成做准备）

---

## 二、基础自测（选择题）

**Q1.** 本节 demo 中 `ids` 形状为 `(4, 32)`，`d_model = 64`。`EmbeddingComposer.forward(ids)` 的输出形状是：

- A. `(4, 32, 64)`
- B. `(4, 64)`
- C. `(4, 32, 320)`（320 为词表大小）
- D. `(32, 64)`

**Q2.** 用 demo 的配置（`vocab_size=320, d_model=64, max_context_length=128`），`count_parameters(learned_composer)` 的结果是：

- A. 20,480
- B. 8,192
- C. 40,960
- D. 28,672

**Q3.** `TokenEmbedding(vocab_size=10, d_model=4)`，输入 `ids = [[3, 3, 3]]`，对输出求和后 `backward()`。下列关于 `weight.grad` 的说法正确的是：

- A. 10 行都收到相同的梯度
- B. 只有第 3 行非零，且该行每个元素为 3（梯度被累加了 3 次）
- C. 只有第 3 行非零，且每个元素为 1（重复 id 只算一次）
- D. 所有行梯度都为 0，因为 embedding 查表不可导

**Q4.** 关于 sinusoidal 位置编码中不同维度的"频率/波长"，正确的说法是：

- A. 低维（k 小）波长长，编码粗略位置；高维波长短，编码精细位置
- B. 所有维度波长相同，只是相位不同
- C. 低维（k 小）波长短（k=0 时约 6.28 个位置），编码精细位置；高维波长越来越长，编码粗略位置
- D. 波长随维度线性增长

**Q5.** 在**本节代码**中，`max_context_length=128`，调用 `positional_embedding(129)` 会怎样？

- A. Learned 报错；Sinusoidal 正常返回 129 行（公式可以外推）
- B. 两者都静默截断成 128 行
- C. Learned 返回随机初始化的新行；Sinusoidal 报错
- D. 两者都抛出 `ValueError`

**Q6.** Sinusoidal 编码在同一频率上同时使用 sin 和 cos，最主要的好处是：

- A. 位置 `p+k` 的向量可以写成位置 `p` 向量的线性变换（一个只依赖 k 的旋转），便于注意力学习相对偏移
- B. sin 单独使用无法反向传播
- C. 让参数量翻倍，提高表达能力
- D. 保证每个位置向量的范数为 1

**Q7.** `SinusoidalPositionalEmbedding` 用 `self.register_buffer("pe", pe, persistent=False)` 保存表。下列说法正确的是：

- A. `pe` 会出现在 `module.parameters()` 里，但 `requires_grad=False`
- B. `pe` 会被优化器更新
- C. `pe` 不在 `parameters()` 里、会随 `.to(device)` 移动，但不会写进 `state_dict()`
- D. `pe` 不会随 `.to(device)` 移动，需要手动搬到 GPU

**Q8.** demo 打印的"邻近位置余弦相似度"中，learned 列在 ±0.02 附近、sinusoidal 列在 k=1 时为 +0.9662。下列解释正确的是：

- A. learned 表已经训练过，学到了"位置无关"的结构
- B. learned 表各行独立采样，随机向量两两近似正交；sinusoidal 的 `cos(pe[p], pe[p+k])` 恰好等于 `(2/D)·Σ cos(ω_i k)`，与 p 无关，只依赖偏移 k
- C. sinusoidal 的相似度高是因为所有行都相同
- D. 两列差异来自 learned 用了 float16

---

## 三、动手 / 代码题

**Q9.** 手算题。`D = 4`、`base = 10000`：

1. 写出 `pe[0]` 和 `pe[1]`（保留 4 位小数）。
2. 证明对 sinusoidal 表，`pe[p]·pe[p+k] = Σ_i cos(ω_i k)`，从而 `‖pe[p]‖ = √(D/2)`、余弦相似度只依赖 k。
3. 据此计算 `D = 4` 时 k = 1 的邻近余弦相似度。

**Q10.** 阅读 demo 的最后两段：

```python
    _print_section("Sinusoidal property: smooth decay")
    monotone_count = sum(
        sinusoidal_curve[i] >= sinusoidal_curve[i + 1] - 1e-3
        for i in range(len(sinusoidal_curve) - 1)
    )
    ...
    _print_section("Length extrapolation")
    short = cfg.max_context_length // 2
    long = cfg.max_context_length
    print(f"sinusoidal at len {short:>3} : ok")
    _ = sinusoidal_pos(short)
    print(f"sinusoidal at len {long:>3} : ok")
    _ = sinusoidal_pos(long)
    print("learned bounded by max_context_length: must error past max")
    try:
        _ = learned_pos(long + 1)
    except ValueError as e:
        print(f"  caught: {e}")
```

1. 实际输出为 `monotone steps: 4/5`，sinusoidal 曲线在 k=5→6 时从 0.7345 升到 0.7362。为什么"平滑衰减"并不严格单调？
2. "Length extrapolation"这一段想说明什么？它真的证明了 sinusoidal 能外推吗？指出代码里两处让人误解的写法。

**Q11.** 改造题：写一个 `SinusoidalAny(d_model)` 模块，不预先建表，`forward(seq_len, start=0)` 按需计算位置 `start .. start+seq_len-1` 的编码。要求：①与原模块在前 128 行数值一致；②能返回第 5000 个位置；③说明 `start` 参数在什么场景下必需。

**Q12.** 规模估算：GPT-2 Small 的 `V = 50257`、`D = 768`、最大上下文 1024，使用 learned 位置 embedding。

1. token embedding 与位置 embedding 各有多少参数？
2. 若改用 sinusoidal，省下多少参数？占 124M 的比例约多少？
3. 如果输出层与 token embedding 做 weight tying，反向传播时 token embedding 的梯度还是"稀疏的"吗？

---

## 四、面试高频题

**Q13.**（基础必考）为什么 Transformer 把 token embedding 和位置 embedding **相加**而不是**拼接**？相加不会把两种信息"混在一起"分不开吗？

**Q14.**（原理深挖）请推导 sinusoidal 位置编码的"相对位置可线性表示"性质，并说明它为什么对注意力有用。它和 RoPE 的思想有什么联系？

**Q15.**（工程实践）Learned 绝对位置、sinusoidal、RoPE、ALiBi 四种方案在参数量、作用位置、长度外推方面各有什么特点？如果今天从零训练一个 decoder-only LLM，你会选哪种？

**Q16.**（追问型）Embedding 的梯度是稀疏的，这会给优化器（尤其是 Adam 与 weight decay）带来什么影响？词表里训练中几乎从未出现的 token 会怎样？

**Q17.**（场景设计）一个用 learned 绝对位置 embedding、在 1024 长度上训练好的模型，业务要求它处理 4096 长度的输入。你有哪些方案？各自的代价是什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

`TokenEmbedding` 把 `(4, 32)` 变成 `(4, 32, 64)`；位置部分返回 `(32, 64)`，`unsqueeze(0)` 成 `(1, 32, 64)` 后广播相加，结果仍是 `(4, 32, 64)`。实际运行输出 `learned composer : (4, 32, 64)`。B 丢了序列维；C 是 LM head 输出 logits 的形状（`V` 维），不是 embedding；D 是位置表本身的形状。

### Q2 — 答案：D

`token 320×64 = 20,480` + `learned 128×64 = 8,192` = **28,672**（已实际运行验证）。`EmbeddingComposer` 把两个子模块注册为属性，`parameters()` 会递归收集。A 是只有 token embedding（即 `sinusoidal_composer` 的参数量）；B 是位置表本身；C 是把 token 表算了两次。注意 demo 里两个 composer **共享同一个 `token_emb` 对象**，所以它们的 token 表是同一份参数。

### Q3 — 答案：B

`nn.Embedding` 的反向是"按 id 把上游梯度 scatter-add 回对应行"。输出求和后每个位置的上游梯度都是全 1 向量，id=3 出现了 3 次，于是第 3 行梯度为 `[3, 3, 3, 3]`（实际运行结果），其余行为 0。C 忽略了累加；A 把查表当成了全连接；D 错在查表对**被查到的行**是可导的（它对行的导数就是单位映射），只是对 id（整数）不可导。

### Q4 — 答案：C

角度 `p / 10000^(2k/D)`：k=0 时分母为 1，角度就是 p，波长 `2π ≈ 6.28` 个位置——变化最快；`D=64` 时 k=16 的波长约 628，k=31 约 47,117（实际计算）。所以低维是"秒针"（精细位置），高维是"时针"（粗略位置）。讲义写"the lower dimensions encode coarse position and the higher dimensions encode fine position"，**恰好说反了**，A 就是讲义的说法。B、D 都与公式不符（波长随 k 几何增长，而非线性）。

### Q5 — 答案：D

两个类的 `forward` 都有同样的检查：

```python
        if seq_len > self.max_context_length:
            raise ValueError(...)
```

Sinusoidal 的公式理论上能算任意位置，但本节实现预先只算了 `max_context_length` 行（讲义也明确说明了这一点），所以同样受限。实际验证：`sinusoidal_pos(129)` 抛出 `seq_len 129 exceeds max_context_length 128`。A 是"公式层面"的理解，却不是本节代码的行为；B、C 都不存在。

### Q6 — 答案：A

`sin(a+b) = sin a·cos b + cos a·sin b`，`cos(a+b) = cos a·cos b − sin a·sin b`。对每一对 `(sin ωp, cos ωp)`，平移 k 等价于乘一个 2×2 旋转矩阵，整个向量就是分块对角矩阵 `R_k` 乘 `pe[p]`，`R_k` 只与 k 有关。我们用代码验证过：`R_3 @ pe[7]` 与 `pe[10]` 的最大误差约 1.5e-7。B 错，sin 可导；C 错，sinusoidal 零参数；D 错，每行范数是 `√(D/2)`（D=64 时约 5.657），不是 1。

### Q7 — 答案：C

buffer 是"模块状态的一部分但不是参数"：不出现在 `parameters()` 中（因此 `count_parameters` 为 0，优化器也看不到），但会随 `.to(device)`/`.cuda()`/`.half()` 一起移动。`persistent=False` 进一步让它**不写入 `state_dict()`**——实际运行 `list(pos.state_dict().keys())` 为 `[]`，`named_buffers()` 里有 `pe`。这样做合理：表可以随时由公式重建，没必要存进 checkpoint。A 描述的是 `nn.Parameter(requires_grad=False)`；B 错；D 恰好是 buffer 要解决的问题。

### Q8 — 答案：B

- Learned 表用 `N(0, 0.02²)` 独立采样，两行之间的余弦相似度均值为 0、标准差约 `1/√D = 0.125`；`neighbour_cosine_curve` 再对 `128−k` 对取平均，所以落在 ±0.02 附近（实测 −0.0210 ~ +0.0078）。
- Sinusoidal：`pe[p]·pe[p+k] = Σ_i [sin(ω_i p)sin(ω_i(p+k)) + cos(ω_i p)cos(ω_i(p+k))] = Σ_i cos(ω_i k)`，范数恒为 `√(D/2)`，所以余弦相似度 `= (2/D)·Σ cos(ω_i k)`，与 p 无关。按公式算 k=1..6 为 `0.9662, 0.8845, 0.7996, 0.7479, 0.7345, 0.7362`，与 demo 输出逐位一致。

A 错，本节没有训练；C 错，各行不同（只是相似）；D 错，全程 float32。

### Q9 — 参考答案

1. `D=4` 有两对频率：`ω_0 = 1`，`ω_1 = 1/10000^(2/4) = 0.01`。
   - `pe[0] = [sin0, cos0, sin0, cos0] = [0, 1, 0, 1]`
   - `pe[1] = [sin1, cos1, sin0.01, cos0.01] = [0.8415, 0.5403, 0.0100, 0.99995]`（代码打印为 `[0.8415, 0.5403, 0.0100, 0.9999]`，float32 舍入）
2. 对每一对：`sin(ωp)sin(ω(p+k)) + cos(ωp)cos(ω(p+k)) = cos(ω(p+k) − ωp) = cos(ωk)`。对 D/2 对求和得 `Σ_i cos(ω_i k)`。令 k=0 得 `‖pe[p]‖² = D/2`。因此余弦相似度 `= Σ cos(ω_i k) / (D/2)`，与 p 无关——这正是"只依赖相对距离"的数学根源。
3. `(cos 1 + cos 0.01) / 2 = (0.5403 + 0.99995) / 2 ≈ 0.7701`（已用 Python 计算验证）。

### Q10 — 参考答案

1. 相似度是 32 个 `cos(ω_i k)` 的平均。高维（低频）对的 `cos(ω_i k)` 都接近 1，构成约 0.73 的"平台"；最高频的那一对（ω=1）贡献 `cos(k)`：`cos 5 ≈ 0.284`、`cos 6 ≈ 0.960`，从 k=5 到 6 它**上升**了约 0.68，除以 32 约 +0.021，盖过了其他对的下降，于是整体从 0.7345 升到 0.7362。代码给比较加了 `1e-3` 的容差，但差值 0.0017 超过容差，所以只有 4/5 步单调。换成 `D=32`（讲义建议的实验），曲线为 `0.9571, 0.8581, 0.7670, 0.7288, 0.7361, 0.7432`，只有 3/5 步单调——高频对占比更大，振荡更明显。结论：sinusoidal 的相似度"总体随距离下降"，但**不是单调函数**，讲义说的"smooth and predictable decay"是对短距离的近似描述。
2. 这一段只证明了"两个模块都能在 `≤ max_context_length` 时工作、learned 超过就报错"，**并没有对 sinusoidal 做超长测试**；如果对 sinusoidal 也调用 `sinusoidal_pos(long + 1)`，同样会报错（见 Q5）。误导之处：
   - 标题叫 "Length extrapolation"，打印内容又只给 learned 加了"must error past max"的说明，读者容易得出"sinusoidal 能外推"的错误印象；
   - `print("... : ok")` 写在实际调用**之前**，即使调用失败也已经打出了 "ok"——检查结果应该在调用成功之后再打印。

### Q11 — 参考答案

```python
import torch
import torch.nn as nn

class SinusoidalAny(nn.Module):
    def __init__(self, d_model: int, base: float = 10000.0) -> None:
        super().__init__()
        if d_model % 2 != 0:
            raise ValueError("d_model must be even")
        self.d_model = d_model
        inv_freq = 1.0 / (base ** (torch.arange(0, d_model, 2, dtype=torch.float32) / d_model))
        self.register_buffer("inv_freq", inv_freq, persistent=False)   # (D/2,)

    def forward(self, seq_len: int, start: int = 0) -> torch.Tensor:
        pos = torch.arange(start, start + seq_len, dtype=torch.float32,
                           device=self.inv_freq.device)                 # (T,)
        angle = pos[:, None] * self.inv_freq[None, :]                   # (T, D/2)
        pe = torch.empty(seq_len, self.d_model, device=angle.device)
        pe[:, 0::2] = torch.sin(angle)
        pe[:, 1::2] = torch.cos(angle)
        return pe
```

已实际验证：`torch.allclose(SinusoidalAny(64)(128), SinusoidalPositionalEmbedding(128, 64).pe, atol=1e-5)` 为 `True`；`forward(200)` 返回 `(200, 64)`；`forward(3, start=10)` 等于原表第 10–12 行；`forward(1, start=5000)` 正常返回。

`start` 的用途：自回归生成配合 KV cache 时，每步只输入 1 个新 token，它的位置是"已生成长度"而不是 0。如果仍从 0 开始编码，每个新 token 都会被当作位置 0，模型的位置信息全乱。注意：这样的模块"能算"任意位置，但模型在训练长度之外**未必用得好**（讲义："The model may still struggle past its training length even when the table is large enough to index"）。另外 float32 下位置很大时 `pos * inv_freq` 的精度会下降，生产实现常用 float64 或分段计算。

### Q12 — 参考答案

1. token embedding：`50,257 × 768 = 38,597,376`；learned 位置：`1,024 × 768 = 786,432`。
2. 省下 786,432 个参数，约占 124M 的 **0.63%**——参数量上几乎可以忽略。选择 learned 还是 sinusoidal，真正的差别在**长度行为与归纳偏置**，而不是参数量。
3. 不再稀疏。weight tying 时输出层 `logits = h @ Eᵀ` 对**整个词表**算 softmax，每个位置的梯度 `(p − onehot)ᵀ h` 会落到 E 的每一行（讲义："every backward pass touches every row of the embedding through the output side"）。输入侧仍然只是被查到的行有梯度，两侧梯度相加。

### Q13 — 参考回答要点

- **保持维度**：相加让 `D` 在整个网络中不变，残差连接、LayerNorm、注意力投影都按 `D` 设计；拼接会让输入变成 `D_tok + D_pos`，要么额外加投影，要么让每层都更宽。
- **相加并不会"不可分"**：在高维空间里，随机初始化/训练得到的 token 子空间与位置子空间近似正交，后续的线性投影（`W_q`、`W_k`）可以学会分别"读出"语义和位置。讲义原话："lets the model decide on a per-feature basis whether the token meaning or the position dominates"。
- **等价性视角**：拼接后再乘一个线性矩阵 `W[e_tok; e_pos] = W_1 e_tok + W_2 e_pos`，本质上也是两个投影的和；直接相加相当于把 `W_1、W_2` 固定为单位阵，后面的层再做投影。
- 加分点：RoPE 走了另一条路——不往输入里"加"位置，而是在 Q/K 上"乘"旋转，让注意力分数天然只依赖相对位置。
- 常见误区：认为位置信息只存在于第一层，实际上通过残差流会一直传到上层。

### Q14 — 参考回答要点

- **推导**：对频率 ω，`[sin ω(p+k), cos ω(p+k)]ᵀ = [[cos ωk, sin ωk], [−sin ωk, cos ωk]] · [sin ωp, cos ωp]ᵀ`。把 D/2 个 2×2 块放到对角线上得到 `R_k`，有 `pe[p+k] = R_k · pe[p]`，`R_k` 与 p 无关。
- **为什么有用**：注意力分数是 `(x_p W_q)·(x_{p'} W_k)`。如果模型想表达"关注前面第 k 个位置"，它需要一种在任意绝对位置 p 都一样的方式来比较位置向量；`R_k` 只依赖 k，线性投影就能近似实现"按相对距离打分"。同时点积 `pe[p]·pe[p+k] = Σ cos(ω_i k)` 只依赖 k（Q9）。
- **与 RoPE 的联系**：RoPE 把同样的"按频率成对旋转"直接作用在 Q、K 向量上：`q_p' = R_p q_p`、`k_{p'}' = R_{p'} k_{p'}`，于是 `q_p'·k_{p'}' = q_pᵀ R_{p'−p} k_{p'}`，注意力分数**精确地**只依赖相对位置，而不是"可以学出来"。频率设置（`base^(−2i/D)`）与 sinusoidal 完全相同。
- 加分点：多尺度波长让编码在短距离分辨率高、长距离也不重复（最长波长 `2π·10000`）。

### Q15 — 参考回答要点

| 方案 | 参数 | 作用位置 | 长度外推 |
|------|------|---------|---------|
| Learned 绝对位置 | `L × D` | 输入（与 token embedding 相加） | 不能超过 L，表里没有那一行 |
| Sinusoidal | 0 | 输入 | 公式可算任意位置，但模型没见过的位置效果常常下降；本节实现还被预建表限制 |
| RoPE | 0 | 每层注意力的 Q/K | 天然相对位置；超出训练长度会退化，但可以用插值/调整 base 等方法扩展 |
| ALiBi | 0（每头一个固定斜率） | 注意力分数上加与距离成比例的线性偏置 | 外推性较好，但对长距离信息有"天然衰减"偏好 |

- 选择：今天从零训练 decoder-only LLM，主流选择是 RoPE（讲义："Those are the modern choices in production transformers"），因为它零参数、相对位置精确、与 KV cache 兼容、有成熟的长度扩展方法。
- 加分点：位置信息作用在 Q/K 上，意味着 V 不带位置偏置，残差流里也不会有"位置向量"一直占用维度。
- 常见误区：认为"sinusoidal 零参数所以一定能外推"——能算出向量不等于模型能正确使用它。

### Q16 — 参考回答要点

- **稀疏梯度**：每步只有本批出现的 token 行有梯度（输入侧）；词表 50K、一批几千 token 时，大部分行这一步梯度为 0。
- **对 Adam 的影响**：PyTorch 默认的稠密 Adam 对梯度为 0 的行依然会更新一阶/二阶矩（指数衰减）并用旧的动量继续移动参数，所以"没出现的行"也会动；稀疏 Adam（`SparseAdam` + `nn.Embedding(sparse=True)`）只更新出现的行。
- **weight decay**：AdamW 的解耦 weight decay 会让每一步都把所有行往 0 拉，从未出现的 token 行会逐渐衰减——很多实现会对 embedding 关闭 weight decay。
- **罕见 token**：长尾 token 的行几乎得不到训练信号，停留在初始化附近；推理时遇到它们会产生异常输出（阶段 10 第 01 节提到的 glitch token 现象）。
- **weight tying 的缓解**：共享输出层后，每一步每一行都会从输出侧收到梯度（Q12），罕见 token 至少能学到"不该被预测"。
- 加分点：多卡训练时 embedding 很大，常用词表并行（vocab parallel）把 `(V, D)` 按行切分到不同卡上。

### Q17 — 参考回答要点

- **直接输入 4096**：不可行——位置表只有 1024 行，代码层面就会报错（本节代码同样如此）。
- **方案一：扩表 + 继续训练**：新增 1024–4095 行，用已有行的插值（如把旧表线性插值到 4096 行）初始化，再在长文本上继续预训练/微调。代价：需要长文本数据和一定训练量；注意力计算量随长度平方增长。
- **方案二：滑动窗口/分块**：把长输入切成 ≤1024 的块分别处理，或做层级摘要（map-reduce）。代价：跨块依赖丢失。
- **方案三：检索替代长上下文**：只把相关片段放进 1024 窗口（RAG）。代价：检索质量决定效果。
- **方案四：换架构重训**：改成 RoPE 等相对位置方案，再用长度扩展技术。代价最大，但长期最灵活。
- 评估：用"长文中埋入事实再提问"的测试检查不同位置的召回，并监控短文本任务是否退化。
- 常见误区：以为把 `max_context_length` 改大、新行随机初始化就能用——新行没有训练过，模型完全不认识这些位置。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../30-bpe-tokenizer-from-scratch/docs/zh.md)：token id 从哪里来，词表大小 V 如何确定。
- [阶段 19 · 31 使用滑动窗口构建分词后的数据集](../../31-tokenized-dataset-sliding-window/docs/zh.md)：产生本节输入的 `(B, T)` 批次。
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../../05-nlp-foundations-to-advanced/03-word-embeddings-word2vec/docs/zh.md)：embedding 查表与"方向编码相似性"的直觉。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：更系统的位置编码对比。
- [阶段 03 · 11 PyTorch简介](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`nn.Module`、`nn.Embedding`、autograd 基础。

### 本节被哪些后续内容用到
- [阶段 19 · 33 多头 Self-Attention](../../33-multihead-self-attention/docs/zh.md)：本节输出的 `(B, T, D)` 直接作为注意力输入；可选扩展是在 Q/K 上加入 RoPE。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：把 token + 位置 embedding、Transformer block 和 LM head 组装成完整模型，并讨论 weight tying。
- [阶段 19 · 37 加载预训练 Weights](../../37-loading-pretrained-weights/docs/zh.md)：GPT-2 的 `wte`/`wpe` 两张表就是本节的 token 与 learned 位置 embedding。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：NumPy 版本的同一结构。

### 延伸关键词
`nn.Embedding` · `register_buffer` · `weight tying` · `sinusoidal positional encoding` · `RoPE` · `ALiBi` · `position interpolation` · `length extrapolation` · `sparse gradient` · `SparseAdam`
