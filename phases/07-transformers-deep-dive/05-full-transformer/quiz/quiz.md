# 测验 · 完整的 Transformer — Encoder + Decoder（The Full Transformer — Encoder + Decoder）

> **阶段 07 · Transformers 深入 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 六个组件 | embedding + 位置信号、self-attention、FFN、残差、归一化、cross-attention（仅 decoder）；之后所有 Transformer 都继承这个骨架 |
| 2 | Encoder block | `x → Norm → 自注意力 → +残差 → Norm → FFN → +残差`；双向、无 mask，所有位置互相可见 |
| 3 | Decoder block | 三个子层：带因果 mask 的自注意力 → cross-attention → FFN；decoder-only（GPT）去掉中间的 cross-attention |
| 4 | Cross-attention | Q 来自 decoder，K/V 来自 encoder 输出；这是信息从 encoder 流向 decoder 的**唯一**通道 |
| 5 | 残差连接 | `x + sublayer(x)`：给梯度和信息一条"直通高速路"，深层堆叠的前提 |
| 6 | Pre-norm vs Post-norm | Pre-norm：`x + f(Norm(x))`（2026 默认，深层更好训）；Post-norm：`Norm(x + f(x))`（原论文，深层需小心 warmup） |
| 7 | RMSNorm | 只除以 RMS，不减均值；比 LayerNorm 少一步，经验上同样稳定 |
| 8 | FFN 与 SwiGLU | 逐位置两层 MLP，经典扩展比 4×；SwiGLU `(SiLU(xW₁) ⊙ xW₃)W₂` 用三个矩阵，扩展比取约 8/3（讲义写 2.6×）使参数量与 4× 的两矩阵版相当 |
| 9 | 参数量 | 每层约 `4d²`（attention）+ `3·d·d_ff`（SwiGLU FFN）；norm 可忽略；另加 embedding / 输出头 |
| 10 | 三大家族 | encoder-only（BERT：分类、embedding）、decoder-only（GPT/Llama：生成）、encoder-decoder（T5/BART/Whisper：有明确"源序列"的转换任务） |

### 核心技能（能动手做到）

- [ ] 不看讲义画出 encoder block 与 decoder block 的数据流，标出残差和 norm 的位置
- [ ] 读懂 `main.py` 的 `multi_head_attention(..., kv_source=...)`，说清同一个函数如何同时实现 self-attention 和 cross-attention
- [ ] 手算 `BlockParams` 的参数量，以及讲义练习 1（`d=512, 8 头, 扩展 4×, SwiGLU`）的参数量
- [ ] 写一个测试验证 decoder 的因果性：修改第 t 个目标 token，前 t 个位置的输出不变
- [ ] 实现 post-norm 版本的 block，比较 12 层堆叠后的激活范数，并能解释结果
- [ ] 把 RMSNorm 换成 LayerNorm、SwiGLU 换成 ReLU-FFN，确认形状不变（讲义 Step 4）
- [ ] 根据任务类型在 encoder-only / decoder-only / encoder-decoder 之间做出选择并说明理由

---

## 二、基础自测（选择题）

**Q1.** 在 encoder-decoder Transformer 的 cross-attention 中，Q、K、V 的来源是：

- A. Q、K、V 都来自 decoder
- B. Q 来自 decoder，K、V 来自 encoder 输出
- C. Q 来自 encoder 输出，K、V 来自 decoder
- D. Q、K、V 都来自 encoder 输出

**Q2.** 下列哪个公式是 **pre-norm** 残差子层？

- A. `y = Norm(x + f(x))`
- B. `y = x + f(Norm(x))`
- C. `y = Norm(f(x))`
- D. `y = f(x + Norm(x))`

**Q3.** 对行向量 `x = [1, 2, 3, 4]`（不带可学习缩放与偏置），LayerNorm 与 RMSNorm 的输出约为：

- A. 两者都是 `[-1.342, -0.447, 0.447, 1.342]`
- B. LayerNorm `[-1.342, -0.447, 0.447, 1.342]`，RMSNorm `[0.365, 0.730, 1.095, 1.461]`
- C. LayerNorm `[0.365, 0.730, 1.095, 1.461]`，RMSNorm `[-1.342, -0.447, 0.447, 1.342]`
- D. 两者都是 `[0.25, 0.5, 0.75, 1.0]`

**Q4.** 现代模型使用 SwiGLU 时，FFN 隐藏层扩展比通常取约 8/3（≈2.67×，讲义写作 2.6×）而不是 4×，主要原因是：

- A. SwiGLU 的激活函数输出范围更大，需要更窄的隐藏层
- B. SwiGLU 有三个矩阵（W₁、W₂、W₃），取 8/3 可以让参数量与"4× 两矩阵 FFN"基本相同
- C. 8/3 能让 GPU 计算更快
- D. 这是为了和注意力头数对齐

**Q5.** GPT 这类 decoder-only 模型的每个 block 包含：

- A. 双向自注意力 + FFN
- B. 带因果 mask 的自注意力 + cross-attention + FFN
- C. 带因果 mask 的自注意力 + FFN
- D. 只有 FFN

**Q6.** 在本节的 2 层 encoder + 2 层 decoder 中，decoder 的每一层 cross-attention 读取的是：

- A. 与其同层编号的 encoder 层输出（decoder 第 1 层读 encoder 第 1 层）
- B. encoder **最后一层**的输出 `enc_out`
- C. 原始源序列 `src`，不经过 encoder
- D. 上一层 decoder 的输出

**Q7.** 下列"任务 → 架构"的对应中，**最不合适**的是：

- A. 文本分类 / 句向量 → encoder-only（BERT、ModernBERT）
- B. 对话、代码生成 → decoder-only（GPT、Llama、Qwen）
- C. 语音识别 → encoder-decoder（Whisper）
- D. 开放域多轮对话生成 → encoder-only（BERT），因为它是双向的

---

## 三、动手 / 代码题

**Q8.** 阅读 `BlockParams`：

```python
class BlockParams:
    def __init__(self, d, n_heads, ffn_expansion, rng, use_swiglu=True):
        # ...
        self.Wq = randn(d, d, rng)
        self.Wk = randn(d, d, rng)
        self.Wv = randn(d, d, rng)
        self.Wo = randn(d, d, rng)
        h = int(d * ffn_expansion)
        if use_swiglu:
            self.W1 = randn(d, h, rng)
            self.W2 = randn(h, d, rng)
            self.W3 = randn(d, h, rng)
        else:
            self.W1 = randn(d, h, rng)
            self.W2 = randn(h, d, rng)
        # cross-attention (decoder)
        self.Wq_x = randn(d, d, rng)
        self.Wk_x = randn(d, d, rng)
        self.Wv_x = randn(d, d, rng)
        self.Wo_x = randn(d, d, rng)
```

(a) `main()` 中 `d = 8, ffn_expansion = 2.0`，一个 encoder block 和一个 decoder block 实际**用到**的参数各是多少？encoder block 有多少参数是"创建了但从没用过"的？
(b) 讲义练习 1：`d_model = 512, n_heads = 8, 扩展 4×, SwiGLU`，一个 encoder block 的参数量是多少？（不计 bias；如果 RMSNorm 带可学习缩放，再加多少？）
(c) 讲义用 `d = 4096, r = 2.6, 32 层` 估算参数量，写的是 "≈ 32 · (16 + 32) M = ~1.5B parameters per layer × 32 ≈ 7B"。请重新计算每层参数量，并指出原式的问题。

**Q9.** 关于 decoder 的掩码：

```python
def decoder_block(x, enc_out, p):
    h = rms_norm(x)
    a = multi_head_attention(h, p.Wq, p.Wk, p.Wv, p.Wo, p.n_heads, causal=True)
    x = add(x, a)
    h = rms_norm(x)
    a = multi_head_attention(h, p.Wq_x, p.Wk_x, p.Wv_x, p.Wo_x, p.n_heads, kv_source=enc_out)
    x = add(x, a)
    # ... FFN
```

(a) 设计一个实验验证"decoder 第 t 个位置的输出不依赖第 t 个之后的目标 token"，并预测结果。
(b) 为什么 cross-attention 不需要因果 mask？如果误把 cross-attention 也设为 `causal=True`，在 `tgt_len = 5, src_len = 6` 时会发生什么？
(c) `softmax_rows` 中 `m = max(v for v in row if v != float("-inf"))` 在什么情况下会抛异常？本程序为什么不会遇到？

**Q10.** 讲义练习 2 说："Post-norm's activations should explode; pre-norm's should stay bounded." 请用本文件的函数写一个 post-norm 版本的 encoder block，用 `d = 16` 随机初始化 12 层，分别堆叠 pre-norm 和 post-norm，打印每层输出的平均行范数。预测并解释结果——讲义的预期对吗？

---

## 四、面试高频题

**Q11.**（基础必考）请描述原始 Transformer 的 encoder 和 decoder 的结构，每个子层的作用是什么？训练时 decoder 的输入是什么？

**Q12.**（原理深挖）残差连接和 LayerNorm 各解决了什么问题？Pre-norm 和 post-norm 有什么区别？为什么现代大模型几乎都用 pre-norm？

**Q13.**（原理深挖）RMSNorm 相比 LayerNorm、SwiGLU 相比 ReLU-FFN，各自改了什么、好在哪？

**Q14.**（工程实践）请估算 Llama-3-8B 量级模型的参数量。公开配置大致为：`d_model = 4096`、32 层、32 个 Q 头 / 8 个 KV 头（`d_head = 128`）、FFN 中间维度 14336（SwiGLU）、词表 128256，输入 embedding 与输出头不共享。

**Q15.**（场景设计）为什么 decoder-only 在大语言模型上"赢了"？encoder-decoder 在什么场景下仍然更合适？请举例。

---

## 五、参考答案与解析

### Q1 — 答案：B

decoder 拿着"我现在需要什么"（Q）去 encoder 的输出里查找（K）并取回内容（V）。代码里就是 `multi_head_attention(h, ..., kv_source=enc_out)`：Q 由 decoder 的 `h` 投影，K、V 由 `enc_out` 投影。这也是 decoder 唯一能看到源序列的地方。

### Q2 — 答案：B

pre-norm 先对子层输入做归一化，再把子层输出加回**未归一化**的残差流：`x + f(Norm(x))`。A 是原论文的 post-norm。pre-norm 的好处是残差路径上没有任何变换，梯度可以从顶层无衰减地直达底层，深层训练更稳定。代码中的 `encoder_block` 就是这个写法：`h = rms_norm(x); a = ...(h); x = add(x, a)`。

### Q3 — 答案：B

- LayerNorm：均值 2.5，方差 1.25，`(x − 2.5)/√1.25` = `[-1.342, -0.447, 0.447, 1.342]`，均值 0、方差 1。
- RMSNorm：`RMS = √((1+4+9+16)/4) = √7.5 ≈ 2.739`，`x / 2.739` = `[0.365, 0.730, 1.095, 1.461]`，不居中，只统一了尺度。

（均用代码中的 `layer_norm` 和 `rms_norm` 验证，eps 影响可忽略。）

### Q4 — 答案：B

两矩阵 FFN 参数为 `2·d·4d = 8d²`；SwiGLU 三个矩阵，参数 `3·d·d_ff`，令其等于 `8d²` 得 `d_ff = 8d/3 ≈ 2.67d`。所以"2.6×"是为了在同等参数预算下公平替换（讲义："SwiGLU uses three matrices, total params match"）。实际模型常再取整到硬件友好的倍数，也有模型选择更大的比值。

### Q5 — 答案：C

decoder-only 没有 encoder，自然没有 cross-attention；剩下"因果自注意力 + FFN"两个子层（讲义："In a pure decoder-only architecture (GPT), cross-attention is omitted"）。A 是 encoder block；B 是 encoder-decoder 中的 decoder block。

### Q6 — 答案：B

`main()` 先把 encoder 全部跑完得到 `enc_out`，再在 decoder 的每一层都传入同一个 `enc_out`（讲义 Step 2："Pass the encoder output into every decoder cross-attention"）。这也是原始 Transformer 和 T5 的做法。

### Q7 — 答案：D

BERT 是双向 encoder，每个位置能看到未来 token，没有自回归生成的机制，不适合开放式生成。A、B、C 都与讲义的选型表一致：语音识别、翻译这类"有明确源序列"的任务适合 encoder-decoder（Whisper、T5、BART）。

### Q8 — 参考答案

(a) `d = 8`，`h = int(8 × 2.0) = 16`：

| 部分 | 参数量 |
|------|--------|
| 自注意力 `Wq/Wk/Wv/Wo` | `4 × 8 × 8 = 256` |
| SwiGLU `W1 (8×16)、W3 (8×16)、W2 (16×8)` | `3 × 8 × 16 = 384` |
| cross-attention `Wq_x/Wk_x/Wv_x/Wo_x` | `4 × 8 × 8 = 256` |

- encoder block 用到 `256 + 384 = 640`，但 `BlockParams` 还创建了 256 个 cross-attention 参数，**从未使用**（`encoder_block` 不读 `*_x`）。
- decoder block 用到 `256 + 256 + 384 = 896`。
- 代码中的 RMSNorm 没有可学习参数，所以不计。

(b) attention `4 × 512² = 1,048,576`；SwiGLU（`d_ff = 2048`）`3 × 512 × 2048 = 3,145,728`；合计 **4,194,304**。若两个 RMSNorm 各带一个长度 512 的可学习缩放向量，再加 1,024，得 4,195,328。注意这里按讲义要求用了 4× 扩展的 SwiGLU，所以 FFN 参数是 `12d²`，比"参数对齐"的 8/3× 版本多 50%。

(c) `d² = 4096² ≈ 16.78M`。每层 attention `4d² ≈ 67.1M`，FFN `3 × 2.6 × d² ≈ 130.9M`，合计约 **198M / 层**，32 层约 **6.34B**，再加 embedding 和输出头。原式有两处问题：
- 把 `4d²` 和 `7.8d²` 写成了 "16M" 和 "32M"（漏乘了系数，其实 16M 只是 `d²` 本身）；
- "~1.5B parameters per layer × 32 ≈ 7B" 自相矛盾（1.5B × 32 = 48B）；正确的说法是"约 0.2B / 层 × 32 ≈ 6.3B，加上 embedding 后接近公开的 8B 量级"。

### Q9 — 参考答案

(a) 实验：先用原始 `tgt` 跑一次 decoder，再把 `tgt` 的最后一行（位置 4）全部改成 9.0 再跑一次，比较两次输出：

```python
def run_decoder(t):
    o = t
    for p in dec_params:
        o = decoder_block(o, enc_out, p)
    return o

o1 = run_decoder(tgt)
t2 = tgt.copy()
for j in range(t2.cols):
    t2.set(4, j, 9.0)
o2 = run_decoder(t2)
same = all(abs(a - b) < 1e-12 for a, b in zip(o1.data[:4 * 8], o2.data[:4 * 8]))
print(same)                                                  # True：位置 0–3 完全不变
print(max(abs(a - b) for a, b in zip(o1.data[32:], o2.data[32:])))   # 位置 4 明显改变
```

实测：前 4 行逐位相同，第 5 行最大差约 11.1。原因：因果 mask 让位置 i 只能看到 `j ≤ i`；其余运算（RMSNorm、FFN、cross-attention）都是**逐位置**的，不会跨位置混合信息。这是检验 decoder 实现正确性的标准单测。

(b) cross-attention 的 K、V 是**完整的源序列**，在推理时源序列一开始就全部已知，不存在"偷看未来"的问题，所以 decoder 的每个位置都应能看到全部源 token。若误设 `causal=True`，代码会构造 `mask[i][j] = j > i` 的 5×6 矩阵，decoder 位置 i 只能看到源位置 `0..i`：位置 0 只能看第一个源 token，最后一个源 token（位置 5）对任何目标位置都不可见——翻译时后半句的信息就丢了。不会报错，但结果错误。

(c) 当某一行**全部**被 mask 时，生成器为空，`max()` 抛 `ValueError: max() arg is an empty sequence`。本程序只在自注意力中使用 `j > i` 的因果 mask，对角线 `j = i` 永远可见，每行至少有一个有效值，所以不会触发。（后面的 `e / s if s > 0 else 0.0` 是另一层防御。）

### Q10 — 参考答案

```python
def post_norm_block(x, p):
    a = multi_head_attention(x, p.Wq, p.Wk, p.Wv, p.Wo, p.n_heads)
    x = rms_norm(add(x, a))                       # 先加残差，再归一化
    f = ffn_swiglu(x, p.W1, p.W2, p.W3)
    return rms_norm(add(x, f))


def mean_row_norm(X):
    return sum(math.sqrt(sum(v * v for v in X.row(i))) for i in range(X.rows)) / X.rows


rng = random.Random(0)
params = [BlockParams(16, 2, 2.0, rng) for _ in range(12)]
x0 = randn(6, 16, random.Random(1), scale=1.0)
x_pre, x_post = x0, x0
for layer, p in enumerate(params, 1):
    x_pre = encoder_block(x_pre, p)
    x_post = post_norm_block(x_post, p)
    print(layer, round(mean_row_norm(x_pre), 3), round(mean_row_norm(x_post), 3))
```

实测（节选）：

| 层数 | pre-norm 平均行范数 | post-norm 平均行范数 |
|------|-------------------|--------------------|
| 1 | 4.695 | 4.0 |
| 3 | 5.912 | 4.0 |
| 6 | 8.490 | 4.0 |
| 12 | 9.749 | 4.0 |

**讲义的预期与实际相反**：post-norm 每层最后一步就是 RMSNorm，输出每行 RMS 恒为 1，范数恒为 `√16 = 4`；pre-norm 的残差流上没有任何归一化，每层都往上"加"东西，范数随深度增长（这也是 pre-norm 模型需要在最后加一个 final norm 的原因）。

post-norm 真正的问题在**梯度**而不是前向激活：Xiong et al.（2020，讲义"延伸阅读"中的论文）分析指出，post-norm 在初始化时靠近输出层的参数梯度很大，需要学习率 warmup 才能稳定训练；pre-norm 的残差路径是恒等映射，梯度分布更均匀，可以不用或少用 warmup。所以练习 2 若要体现 post-norm 的困难，应该比较**各层梯度范数**或"无 warmup 时的训练稳定性"，而不是激活范数。

### Q11 — 参考回答要点

- **Encoder（N 层）**：每层 = 多头自注意力（双向）+ FFN，每个子层外包残差和 LayerNorm（原论文为 post-norm）。输入是源序列 embedding + 位置编码，输出是每个源 token 的上下文表示。
- **Decoder（N 层）**：每层 = 带因果 mask 的多头自注意力 + cross-attention（Q 来自 decoder，K/V 来自 encoder 最终输出）+ FFN，同样有残差和 norm。最后经过线性层 + softmax 得到下一个 token 的分布。
- **子层作用**：自注意力负责"位置之间的信息交换"；FFN 负责"每个位置内部的非线性变换"（逐位置、参数共享）；残差保证信息与梯度通畅；norm 稳定数值尺度；cross-attention 把源序列信息注入目标端。
- **训练时 decoder 的输入**：teacher forcing——把目标序列右移一位（开头加 BOS）作为输入，一次性并行计算所有位置，因果 mask 保证位置 t 只看到 `< t+1` 的 token；推理时则自回归逐 token 生成。
- **加分点**：指出 decoder 的输入长度与 encoder 无关（本节 `tgt_len = 5`、`src_len = 6`），cross-attention 的分数矩阵是 `(tgt_len, src_len)` 而非方阵。

### Q12 — 参考回答要点

- **残差**：`x + f(x)` 让每一层只需学习"增量"；反向传播时 `∂(x + f(x))/∂x = I + ∂f/∂x`，恒等项给梯度提供直通路径，缓解深层网络的梯度消失与退化问题。
- **LayerNorm**：把每个 token 向量的尺度拉回稳定范围，避免激活在层间逐渐漂移，使优化对学习率更不敏感。
- **Post-norm（原论文）**：`Norm(x + f(x))`。残差流本身被反复归一化，前向数值稳定，但梯度必须穿过每一层的 norm；初始化时靠近输出层的梯度偏大，深层训练需要 warmup 和精细调参。
- **Pre-norm**：`x + f(Norm(x))`。残差主干是纯恒等路径，梯度可以直达底层，深层训练稳定，对 warmup 依赖小；代价是残差流范数随深度增长（见 Q10），需要在最后加一个 final norm，且有观点认为深层的表示利用率略低。
- **现代选择**：讲义："Pre-norm is the 2026 default: Llama, Qwen, GPT-3+, Mistral all use it"。
- **加分点**：提到 DeepNorm、sandwich norm 等折中方案；能指出"pre-norm 激活会长大、post-norm 激活不会"这一容易说反的事实。

### Q13 — 参考回答要点

- **RMSNorm**：`y = x / √(mean(x²) + ε) · g`，去掉了 LayerNorm 的"减均值"和偏置 β。假设是"缩放不变性比平移不变性更重要"。少一次归约运算，在大模型上节省可观的计算与访存，经验上稳定性不输 LayerNorm（讲义："one less op, same empirical stability"）。
- **SwiGLU**：`FFN(x) = (SiLU(xW₁) ⊙ xW₃) W₂`。相比 `ReLU(xW₁)W₂`：
  - 多了一条线性"门"分支 `xW₃`，与激活分支逐元素相乘，模型可以按输入动态地放大或抑制每个隐藏单元；
  - SiLU（Swish）平滑、在负区间有小的非零梯度，比 ReLU 更不容易出现"死神经元"；
  - 参数对齐（扩展比 ≈ 8/3）后，在多项语言模型实验中困惑度优于 ReLU/GELU FFN（Shazeer 2020，GLU Variants）。
- **一起使用的现代 block**：RMSNorm + SwiGLU + RoPE + GQA + 无 bias（讲义 2017 vs 2026 对照表）。
- **常见误区**：认为 SwiGLU 在参数量不变的情况下是"多了一个矩阵"——实际上是把隐藏层变窄来换一个门控矩阵。

### Q14 — 参考回答要点

逐项计算（不计 norm 参数，约几十万，可忽略）：

| 部分 | 公式 | 数值 |
|------|------|------|
| `W_q`、`W_o` | `2 × 4096 × 4096` | 33.6M |
| `W_k`、`W_v`（GQA，8 个 KV 头 × 128 = 1024） | `2 × 4096 × 1024` | 8.4M |
| SwiGLU FFN | `3 × 4096 × 14336` | 176.2M |
| **每层合计** | | **≈ 218M** |
| 32 层 | `32 × 218M` | ≈ 6.98B |
| 输入 embedding + 输出头（不共享） | `2 × 128256 × 4096` | ≈ 1.05B |
| **总计** | | **≈ 8.0B** |

- 与讲义简化公式（MHA、r = 2.6）相比：GQA 让 attention 从 `4d²` 降到 `2.5d²`，但 FFN 用了 3.5× 的扩展比，二者此消彼长；词表很大时 embedding 也是不可忽略的一部分（约 13%）。
- **加分点**：能顺手估算训练 FLOPs（约 `6 × 参数量 × token 数`）或推理时 fp16 权重显存（约 16 GB）；指出 embedding 与输出头是否共享（tied）会显著影响小模型的参数量。

### Q15 — 参考回答要点

- **decoder-only 胜出的原因**（讲义："it scales cleanest and handles both comprehension and generation"）：
  1. 结构单一：只有一种 block，一种训练目标（下一个 token 预测），工程栈最简单；
  2. 训练信号密集：每个位置都参与 loss，数据利用率高；
  3. 统一任务形式：理解类任务也能改写成"给 prompt 续写答案"，一个模型覆盖所有任务；
  4. 推理友好：KV cache、speculative decoding 等优化都围绕这一种结构展开。
- **encoder-decoder 仍更合适的场景**：输入有明确"源序列"身份、且输入与输出模态或长度差异很大时——机器翻译、摘要（T5、BART）、语音识别（Whisper：encoder 处理音频频谱，decoder 生成文本）。encoder 对源序列做一次双向编码，decoder 每步只需 cross-attend，源序列很长时比把源和目标拼成一个序列更省。
- **encoder-only**：分类、检索 embedding、抽取式问答（BERT、DeBERTa、ModernBERT），需要双向上下文且不需要生成。
- **加分点**：提到多模态模型常见"视觉 encoder + 语言 decoder"的组合（第 09 节、阶段 12），本质上也是 encoder-decoder 思想。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：缩放点积与因果 mask。
- [阶段 07 · 03 多头 Attention](../../03-multi-head-attention/docs/zh.md)：拆头、`W_o`、GQA。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：本节代码"minus RoPE"缺的那一块。
- [阶段 03 · 04 Activation Functions](../../../03-deep-learning-core/04-activation-functions/docs/zh.md)：ReLU、GELU、SiLU 的形状与梯度。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：残差、归一化与深层训练稳定性。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：post-norm 为什么依赖 warmup。

### 本节被哪些后续内容用到
- [阶段 07 · 06 BERT——掩码语言建模](../../06-bert-masked-language-modeling/docs/zh.md)：encoder-only 特化。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：decoder-only 特化。
- [阶段 07 · 08 T5、BART——Encoder-Decoder 模型](../../08-t5-bart-encoder-decoder/docs/zh.md)：encoder-decoder 特化。
- [阶段 07 · 14 从零构建 Transformer——综合项目](../../14-build-a-transformer-capstone/docs/zh.md)：把本节骨架训练起来。
- [阶段 10 · 14 开放模型：架构详解](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：真实模型的 block 配置。
- [阶段 19 · 34 从零实现 Transformer 模块](../../../19-capstone-projects/34-transformer-block/docs/zh.md)：综合项目中的 block 实现。

### 延伸关键词
`teacher forcing` · `pre-LN / post-LN` · `DeepNorm` · `final norm` · `RMSNorm` · `SwiGLU / GeGLU` · `tied embeddings` · `modeling_llama.py` · `参数量估算 4d² + 3d·d_ff`
