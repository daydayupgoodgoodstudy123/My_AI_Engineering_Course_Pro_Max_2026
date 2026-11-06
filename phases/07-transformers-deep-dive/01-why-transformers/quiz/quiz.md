# 测验 · 为什么选择 Transformers — RNNs 的问题（Why Transformers — The Problems with RNNs）

> **阶段 07 · Transformers 深入 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 递归（recurrence）是串行瓶颈 | `h_t = f(h_{t-1}, x_t)`：第 t 步必须等第 t-1 步算完，时间轴上无法并行，N 个 token 就是 N 个串行步 |
| 2 | 串行深度（serial depth）决定 wall-clock | 两个算法可以做同样多的加法，但"必须按顺序完成的最长依赖链"不同；在 GPU 上决定耗时的是深度而不是总运算量 |
| 3 | 梯度消失与长程依赖 | 50 个 token 之前的信息要穿过 50 次非线性才能到达当前步；LSTM/GRU 的门控只是缓解，没有根除 |
| 4 | 固定宽度隐状态瓶颈 | 经典 seq2seq 的 encoder 把整个源序列压成一个固定形状的向量，源句 5 个 token 还是 500 个 token，瓶颈都一样大 |
| 5 | Self-attention 是"广播" | `output_i = Σ_j a_ij · v_j` 对所有 (i, j) 同时计算，整个 N×N 矩阵一次批量 matmul 填满，层内没有沿序列的依赖链 |
| 6 | Transformer 的代价：O(N²) | 全量 attention 的分数矩阵是 N×N；2K 上下文没问题，128K 就需要 Flash Attention、滑动窗口、线性 attention 等手段 |
| 7 | 归纳偏置（inductive bias）的转移 | RNN 预设"局部性 + 近因性"；Transformer 认为任意两个位置都可能相关 → 更吃数据，但数据够多时扩展得更远 |
| 8 | 循环没有消失，而是变成组件 | 流式推理、百万级长序列、无矩阵加速器的边缘设备上，RNN / SSM（Mamba、RWKV）仍有优势；Jamba、Samba 等是 SSM + attention 混合 |
| 9 | 并行前缀和（Hillis-Steele scan） | 深度 `⌈log₂N⌉`，但总加法数约 `N·log₂N`，用"更多总工作量"换"更浅的依赖图" |

### 核心技能（能动手做到）

- [ ] 运行 `code/main.py`，逐列解释三张输出表（深度对比、纯 Python 计时、前缀和一致性检查）
- [ ] 手算 `depth(n)` 在 n = 64、512、1000 时的返回值，并说出 `max(1, ...)` 和 `math.ceil` 各防了什么
- [ ] 手动追踪 `parallel_scan([1, 2, 3, 4])` 每一轮的中间结果，并解释为什么必须用 `new = list(out)` 做"双缓冲"
- [ ] 说清楚纯 Python 计时里 `attention_style` 更快的真正原因（C 实现的 `sum`），而不是误以为这是"并行"
- [ ] 证明 `rnn_style` 这种**线性**递归其实可以写成闭式或并行扫描，并说明真正无法并行的是哪一类递归
- [ ] 估算给定上下文长度下 N×N attention 分数矩阵的显存占用（例如 2K 与 128K、fp16）
- [ ] 针对"流式 / 超长序列 / 边缘设备 / 常规训练"四类场景给出架构选择和一句话理由

---

## 二、基础自测（选择题）

**Q1.** RNN 在 GPU 上训练长序列很慢，最根本的原因是：

- A. RNN 的参数量通常比 Transformer 大得多
- B. 每一步都依赖上一步的隐状态，沿时间轴的串行深度等于序列长度 N
- C. RNN 无法使用反向传播训练，只能用强化学习
- D. tanh 激活函数在 GPU 上的计算比矩阵乘法慢

**Q2.** 对 N 个数求和。假设处理器无限多，但每次操作只能把**两个**数相加，则最小串行深度是：

- A. 1
- B. `⌈log₂N⌉`
- C. N − 1
- D. `N·log₂N`

**Q3.** 关于经典 RNN encoder-decoder（不带 attention）中的"固定宽度隐状态瓶颈"，正确的说法是：

- A. 源序列越长，encoder 输出的上下文向量维度越大
- B. 不管源序列是 5 个还是 500 个 token，decoder 拿到的都是同一形状的单个向量
- C. LSTM 的遗忘门彻底解决了这个瓶颈
- D. 这个瓶颈只存在于 decoder 端，与 encoder 无关

**Q4.** 对一层全量 self-attention（序列长度 N），下列描述最准确的是：

- A. 串行深度 O(N)，分数矩阵内存 O(N)
- B. 串行深度 O(N)，分数矩阵内存 O(N²)
- C. 沿序列方向没有依赖链（层内深度与 N 无关，只剩归约求和的对数深度），分数矩阵内存 O(N²)
- D. 串行深度 O(log N)，内存 O(log N)

**Q5.** 讲义说"Transformer 需要更多数据才能训练好，但拿到数据后扩展得更远"，背后的原因是：

- A. Transformer 参数更少，所以需要更多数据补偿
- B. RNN 内置"局部性 + 近因性"先验，小数据时这是帮助、大数据时变成束缚；Transformer 几乎不做这类假设
- C. Transformer 无法处理 token 的顺序，所以要靠更多数据学习
- D. attention 是线性运算，表达能力弱于 RNN

**Q6.** 在本节代码的纯 Python 计时中，`attention_style` 比 `rnn_style` 快约 4–6 倍。最准确的解释是：

- A. Python 自动把 `sum()` 分配到多个 CPU 核上并行执行
- B. `sum()` 是 C 实现的循环，省掉了每一步的解释器开销；`rnn_style` 每步还要多做一次乘法——这和 GPU 并行无关
- C. `attention_style` 只做 `log N` 次加法
- D. CPython 会自动把 `for` 循环向量化成 SIMD 指令

**Q7.** 关于 Flash Attention 与 attention 的 O(N²) 代价，正确的是：

- A. Flash Attention 把 attention 的计算量降到了 O(N)
- B. Flash Attention 通过分块（tiling）避免把完整 N×N 分数矩阵写入显存，大幅降低显存占用和 IO，但 FLOPs 仍是 O(N²)
- C. Flash Attention 用低秩矩阵近似 attention，所以结果和标准 attention 不完全一样
- D. Flash Attention 只能用于推理，不能用于训练

---

## 三、动手 / 代码题

**Q8.** 阅读 `depth` 函数，写出下面三行的输出，并解释 `max(1, ...)` 与 `math.ceil` 各自的作用。

```python
def depth(n):
    """Serial-depth count for RNN vs attention-style reductions."""
    rnn_depth = n
    attn_depth = max(1, math.ceil(math.log2(n)))
    return rnn_depth, attn_depth

print(depth(64))
print(depth(1000))
print(depth(1))
```

**Q9.** 下面是代码中的 Hillis-Steele 并行前缀和：

```python
def parallel_scan(xs):
    out = list(xs)
    step = 1
    n = len(out)
    while step < n:
        new = list(out)
        for i in range(step, n):
            new[i] = out[i] + out[i - step]
        out = new
        step *= 2
    return out
```

(a) 写出 `parallel_scan([1, 2, 3, 4])` 每一轮结束后 `out` 的值，共几轮？
(b) 如果把 `new = list(out)` 删掉，直接 `out[i] = out[i] + out[i - step]` 原地更新，`[1, 2, 3, 4]` 会得到什么？为什么错？
(c) n = 16 时，串行前缀和做 15 次加法，Hillis-Steele 一共做多少次加法？这说明了什么取舍？

**Q10.** `rnn_style` 的 docstring 写着 "Cannot parallelize"：

```python
def rnn_style(xs, decay=0.9):
    """Sequential recurrence: h_t depends on h_{t-1}. Cannot parallelize."""
    h = 0.0
    for x in xs:
        h = decay * h + x
    return h
```

请 (a) 写出 `rnn_style` 返回值的闭式表达式；(b) 实现一个基于 Hillis-Steele 思路的 `rnn_parallel_scan(xs, decay)`，返回每一步的 `h_t`，并与逐步循环的结果对比；(c) 说明"真正无法这样并行"的是哪一类 RNN。

---

## 四、面试高频题

**Q11.**（基础必考）为什么 Transformer 能取代 RNN 成为序列建模的主流？请从计算、优化、信息流三个角度回答，并说出 Transformer 付出的代价。

**Q12.**（原理深挖）LSTM 是怎么缓解梯度消失的？为什么它仍然处理不好很长的依赖？

**Q13.**（工程实践）估算 128K 上下文下，单个 head、单层的 attention 分数矩阵（fp16）有多大？工程上有哪些手段应对？KV cache 的增长和分数矩阵的增长是一回事吗？

**Q14.**（追问型）"Transformer 推理也是一个 token 一个 token 生成的，那它相对 RNN 的并行优势体现在哪里？推理时它反而有什么劣势？"

**Q15.**（场景设计）分别为以下场景选择架构并说明理由：① 实时语音流，逐帧推理，内存必须恒定；② 基因组序列，长度 > 1M；③ 没有矩阵乘加速器的 MCU；④ 训练一个 7B 通用对话模型，上下文 32K。

---

## 五、参考答案与解析

### Q1 — 答案：B

RNN 的核心是 `h_t = f(h_{t-1}, x_t)`，`h_5` 必须等 `h_4` 算完，1024 个 token 就是 1024 个串行步，GPU 上成千上万的并行核心只能干等。A 错：参数量不是根因，同等参数下串行性依然存在；C 错：RNN 用 BPTT（随时间反向传播）训练；D 错：激活函数开销不是瓶颈，依赖链才是。

### Q2 — 答案：B

用二叉树归约：第一轮两两相加剩 N/2 个，第二轮剩 N/4 个……共 `⌈log₂N⌉` 轮。C 是串行累加的深度；D 是 Hillis-Steele 前缀和的总**工作量**量级而不是深度。A 只有在允许"一次操作把 N 个数加起来"（无界扇入）的理想模型下才成立。⚠️ 讲义 Step 2 写"or 1 with a parallel scan"并不严谨：并行扫描（包括本节代码里的 Hillis-Steele）的深度也是 `log₂N`，这一点 `depth()` 函数本身就体现了。

### Q3 — 答案：B

这正是讲义的第三个"致命弱点"：encoder 把整个源序列挤进一个向量，形状和长度无关。A 错在维度是固定超参数；C 错：门控缓解的是梯度流问题，不改变"一个向量装下整句"的容量限制；D 错：瓶颈恰恰出在 encoder→decoder 的交接处。Bahdanau attention（2014）就是为了让 decoder 能回看 encoder 的所有隐状态。

### Q4 — 答案：C

所有 (i, j) 对的分数可以同时算，没有"第 j 个位置等第 j-1 个位置"的依赖；层数固定，与 N 无关（讲义称之为 O(1) 串行深度）。严格地说，每个 `Σ_j` 归约在硬件上还有 `log N` 级的深度，但这和 RNN 的 O(N) 是数量级差别。分数矩阵是 N×N，所以朴素实现的内存是 O(N²)。

### Q5 — 答案：B

归纳偏置是"写进架构的先验"。RNN 假设相邻 token 更相关、近期信息更重要，这在数据少时能帮模型少走弯路；但当数据足够多时，这个先验限制了模型学习任意远距离关系的能力。Transformer 把"谁和谁相关"完全交给 attention 去学，所以数据饥渴但上限更高。C 错：Transformer 通过位置编码处理顺序（见第 04 节）。

### Q6 — 答案：B

两者都在单线程 CPU 上跑，没有任何并行。`sum()` 在 C 层面循环，每个元素的开销极小；`rnn_style` 的 `for` 循环每一步都要经过字节码解释，还多一次乘法。一个简单的验证：把 `attention_style` 改成纯 Python `for` 循环累加，它和 `rnn_style` 的差距会缩小到 1.x 倍（实测 100 万元素约 18 ms vs 23 ms）。所以这个表格说明的是"解释器开销"，**不是**"串行深度"——真正体现深度差距的是第一张表，以及讲义练习 3 在 GPU 上的实验。

### Q7 — 答案：B

Flash Attention 是 IO 感知的精确算法：把 Q、K、V 分块搬进片上 SRAM，用 online softmax 边算边归一化，从不把完整的 N×N 矩阵写回 HBM。因此额外显存从 O(N²) 降到 O(N)，速度也因 IO 减少而提升，但 FLOPs 仍是 O(N²)，结果与标准 attention 数学等价（C 错）。训练和推理都能用（D 错）。讲义 Key Terms 里"hides the constants, not the scaling"这句话对**计算量**成立，对**显存**并不准确。

### Q8 — 参考答案

```text
(64, 6)
(1000, 10)
(1, 1)
```

- `log2(64) = 6.0`，`ceil` 后为 6；`log2(1000) ≈ 9.97`，`ceil` 后为 10——树形归约 1000 个数需要 10 轮（2⁹ = 512 < 1000 ≤ 1024 = 2¹⁰）。
- `math.ceil`：轮数必须是整数，非 2 的幂时要向上取整，否则会低估深度。
- `max(1, ...)`：`log2(1) = 0`，深度为 0 会让 `main()` 里 `rd / ad` 除以零；同时"至少要做一步"在语义上也更合理。注意 `depth(0)` 仍会因为 `log2(0)` 抛 `ValueError`，代码没有处理，因为 `main()` 从不传 0。

### Q9 — 参考答案

(a) 共 2 轮（`step = 1, 2`，`step = 4` 时不满足 `4 < 4`）：

| 轮次 | step | 计算 | out |
|-----|------|------|-----|
| 初始 | — | — | `[1, 2, 3, 4]` |
| 1 | 1 | `new[i] = out[i] + out[i-1]`，i = 1..3 | `[1, 3, 5, 7]` |
| 2 | 2 | `new[i] = out[i] + out[i-2]`，i = 2..3 | `[1, 3, 6, 10]` |

结果与 `serial_scan` 相同。

(b) 原地更新得到 `[1, 3, 7, 13]`（错误）。原因：第 1 轮 i = 2 时读取的 `out[1]` 已经在本轮被改成 3（而不是原来的 2），于是同一轮里的数据"串了味"。Hillis-Steele 的每一轮在概念上是**同时**发生的，所有 `new[i]` 都只能读取**上一轮**的值，所以必须双缓冲。在 GPU kernel 里这对应"读一个 buffer、写另一个 buffer"，或者在两轮之间加同步屏障。

(c) 每轮做 `n - step` 次加法：`15 + 14 + 12 + 8 = 49` 次，是串行版 15 次的 3 倍多（量级 `N·log₂N`）。取舍：**用更多总工作量换更浅的依赖图**。在 GPU 上，只要并行宽度足够，4 轮就能完成，远快于 15 个串行步；在单核 CPU 上它反而更慢。这正是"深度而不是运算量决定 GPU 时间"。（更省工作量的 Blelloch 扫描能做到 O(N) 工作量、O(log N) 深度。）

### Q10 — 参考答案

(a) 展开递推：`h_N = x_N + 0.9·x_{N-1} + 0.9²·x_{N-2} + …`，即

```text
rnn_style(xs) = Σ_{t=0}^{N-1} decay^(N-1-t) · xs[t]
```

这是一个**加权求和**，每一项相互独立，可以直接并行计算。

(b) 把每一步看成仿射变换 `h ↦ a·h + b`（这里 `a = decay`、`b = x_t`），两个仿射变换的复合仍是仿射变换，且满足结合律，因此可以套用 Hillis-Steele：

```python
def combine(p, q):
    """先做 p 再做 q：q(p(h)) = a2*(a1*h + b1) + b2"""
    a1, b1 = p
    a2, b2 = q
    return (a1 * a2, a2 * b1 + b2)


def rnn_parallel_scan(xs, decay=0.9):
    out = [(decay, x) for x in xs]
    step, n = 1, len(out)
    while step < n:
        new = list(out)
        for i in range(step, n):
            new[i] = combine(out[i - step], out[i])
        out = new
        step *= 2
    return [b for _, b in out]   # 初始 h = 0，所以 h_t 就是复合后的 b


xs = [1.0, 2.0, 3.0, 4.0]
print(rnn_parallel_scan(xs))                      # [1.0, 2.9, 5.61, 9.049]（末位有浮点尾数）
print([rnn_style(xs[:k + 1]) for k in range(4)])  # 与上一行逐项相等
```

用 `benchmark` 里的输入（1000 个元素）实测，`rnn_style`、闭式求和、并行扫描三者的结果只在第 16 位小数上有浮点差异。

(c) 能这样并行的前提是"每一步的变换可以写成满足结合律的运算"，线性（仿射）递归正好满足——这正是 Mamba 等 SSM 能"像 RNN 一样推理、像 Transformer 一样并行训练"的关键（selective scan）。真正无法这样并行的是**非线性**递归，例如 `h_t = tanh(W·h_{t-1} + U·x_t)`：`tanh` 夹在中间，两步的复合不再是同一族的简单函数，只能一步一步算。所以 docstring 里的 "Cannot parallelize" 对这段线性代码并不准确，它想表达的是"经典非线性 RNN 不能并行"。

### Q11 — 参考回答要点

- **计算（并行性）**：RNN 的串行深度是 O(N)，训练时 GPU 利用率极低；self-attention 一层内所有位置对同时计算，一次批量 matmul 完成，训练时序列维度可完全并行（teacher forcing）。
- **优化（梯度流）**：RNN 中第 t 步的梯度要穿过 t 次非线性和权重乘法才能到达早期 token，容易消失或爆炸；attention 中任意两个位置之间的路径长度是 O(1)，加上残差连接，梯度可以直达。
- **信息流（容量）**：seq2seq 把整句压进一个固定向量；attention 让每个输出位置直接读取所有输入位置，容量随序列长度增长。
- **代价**：分数矩阵 O(N²) 的内存/计算；没有内置的顺序信息，需要位置编码；归纳偏置弱，更依赖大数据；自回归推理时 KV cache 随长度线性增长。
- **加分点**：能说出"深度而非运算量决定 GPU 时间"；提到 2026 年循环以 SSM 的形式回归、混合架构（Jamba、Samba）。
- **常见误区**：说"Transformer 计算量比 RNN 小"——错，长序列下 attention 的 FLOPs 更大，赢在并行。

### Q12 — 参考回答要点

- **原理**：LSTM 引入 cell state `c_t = f_t ⊙ c_{t-1} + i_t ⊙ c̃_t`。cell state 的更新以**加法**为主，当遗忘门 `f_t ≈ 1` 时，梯度沿 cell state 回传几乎不衰减（"常误差传送带"），从而缓解了 vanilla RNN 中反复乘以权重矩阵与 tanh 导数造成的指数衰减。
- **为什么仍不够**：
  1. 遗忘门通常小于 1，跨越几百步后乘积仍会衰减，长程信号仍然被稀释；
  2. 所有历史信息必须挤进一个固定维度的状态向量，存在容量上限（讲义的"fixed-width hidden state"）；
  3. 即便梯度能传过去，训练仍是 O(N) 串行，长序列训练成本高。
- **加分点**：指出 GRU 用更新门实现类似的加性路径；说明 attention 直接给出 O(1) 长度的路径，这才是根本改变。
- **常见误区**：说"LSTM 彻底解决了梯度消失"——讲义原话是 "softened the crush but never eliminated it"。

### Q13 — 参考回答要点

- **估算**：N = 128K = 131,072；N² ≈ 1.72 × 10¹⁰ 个元素；fp16 每个 2 字节 ≈ **34 GB**——这只是**一层、一个 head**。对比 2K 上下文：2048² × 2 B ≈ 8 MB。长度扩大 64 倍，分数矩阵扩大 4096 倍。
- **手段**：
  - Flash Attention：分块 + online softmax，不落地 N×N 矩阵，显存降到 O(N)，FLOPs 不变（第 12 节）；
  - 滑动窗口 / 稀疏 attention：每个 token 只看局部或特定位置，计算和显存都降到 O(N·w)（第 15 节）；
  - 位置编码外推（RoPE scaling 等）让短上下文训练的模型用于长上下文（第 04 节）；
  - 线性 attention、SSM、混合架构：从根本上把复杂度改成 O(N)。
- **KV cache 不是一回事**：KV cache 存的是每个已生成 token 的 K、V 向量，大小约 `2 × 层数 × N × d_model × 字节数`，随 N **线性**增长；分数矩阵在 N 上是**平方**增长。前者靠 GQA/MQA、KV 量化、PagedAttention 等优化，后者靠 Flash Attention、稀疏化。
- **加分点**：能区分"训练/prefill 阶段的 O(N²) 计算瓶颈"和"decode 阶段的 KV cache 显存/带宽瓶颈"。

### Q14 — 参考回答要点

- **优势在哪里**：
  - 训练：teacher forcing 下整条序列的所有位置同时计算，这是 Transformer 相对 RNN 最大的胜利；
  - 推理 prefill：prompt 的所有 token 一次并行处理，生成首 token 前的计算是并行的；
  - 层内每一步 decode 也是一次大 matmul，GPU 利用率比 RNN 的小向量运算高（尤其在 batch 推理时）。
- **劣势在哪里**：
  - decode 阶段依然是逐 token 串行；
  - 每生成一个 token 要对全部历史做 attention，单步代价随上下文长度增长，KV cache 线性膨胀；
  - RNN/SSM 的单步代价和状态大小是**常数**，所以在流式、超长上下文、内存受限的推理场景上有天然优势——这正是讲义"Use It"表格的第一行。
- **加分点**：提到 speculative decoding、KV cache 优化等都是为了缓解 decode 的串行性（第 12、16 节）。

### Q15 — 参考回答要点

| 场景 | 选择 | 理由 |
|------|------|------|
| ① 实时语音流，内存恒定 | RNN 或 SSM（Mamba、RWKV） | 每步代价与状态大小恒定，天然流式；Transformer 的 KV cache 会随时间无限增长 |
| ② 长度 > 1M 的序列 | 线性 attention / Mamba 2 / Hyena，或 SSM + attention 混合 | 全量 attention 的 N² 在 1M 时完全不可行 |
| ③ 无矩阵加速器的 MCU | 小型（如深度可分离）RNN | 讲义："Depthwise-separable RNN still wins on FLOPs/watt" |
| ④ 7B 通用对话模型，32K | Transformer（配合 Flash Attention、RoPE、GQA 等） | 训练并行、生态成熟、32K 在全量 attention + Flash Attention 可承受范围内 |

- **加分点**：对 ② 提到混合架构（Jamba、Samba）在"大部分层用 SSM、少数层用 attention"的折中；对 ④ 主动提出"如果后续要扩到 128K，需要 RoPE 缩放和长上下文继续训练"。
- **常见误区**：一律回答"用 Transformer"。讲义的配套 skill 也要求：推荐 >64K 的全量 attention 时必须说明 O(N²) 显存代价。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 03 Backpropagation 从头开始](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：理解梯度为什么会沿长链路消失/爆炸。
- [阶段 05 · 08 文本的 CNNs 和 RNNs](../../../05-nlp-foundations-to-advanced/08-cnns-rnns-for-text/docs/zh.md)：RNN/LSTM/GRU 的具体结构。
- [阶段 05 · 09 序列到序列模型](../../../05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/zh.md)：固定宽度隐状态瓶颈的来源。
- [阶段 05 · 10 Attention 机制——突破](../../../05-nlp-foundations-to-advanced/10-attention-mechanism/docs/zh.md)：Bahdanau attention 如何"嫁接"在 RNN 上。

### 本节被哪些后续内容用到
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：把本节的"广播"直觉落实成 `softmax(QKᵀ/√d)V`。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：去掉递归后顺序信息丢失，需要位置编码补回来。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：本节提到的 O(N²) 显存墙的解决方案。
- [阶段 07 · 13 Scaling Laws](../../13-scaling-laws/docs/zh.md)：数据量、参数量与架构扩展性的定量关系。
- [阶段 07 · 15 Attention 变体](../../15-attention-variants/docs/zh.md)：滑动窗口、稀疏 attention 等长上下文手段。
- [阶段 10 · 21 Jamba——混合 SSM-Transformer](../../../10-llms-from-scratch/21-jamba-hybrid-ssm-transformer/docs/zh.md)：本节"循环变成组件"的具体案例。

### 延伸关键词
`BPTT` · `LSTM 常误差传送带` · `Bahdanau / Luong attention` · `Blelloch scan` · `associative scan` · `Mamba selective scan` · `RWKV` · `linear attention` · `Flash Attention` · `KV cache`
