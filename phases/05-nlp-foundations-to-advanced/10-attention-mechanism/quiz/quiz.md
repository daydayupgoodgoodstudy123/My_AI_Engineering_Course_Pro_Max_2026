# 测验 · Attention 机制——突破（Attention Mechanism — The Breakthrough）

> **阶段 05 · NLP 基础到进阶 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | attention 解决了什么 | 不再只给 decoder 最终的 encoder 状态，而是保留**所有** encoder 状态，每个 decoder 步重新计算一个加权平均作为上下文 |
| 2 | 五步流程 | 以 `s_{t-1}` 为 query → 与每个 `h_i` 打分 → softmax 得 `α_{t,i}`（和为 1）→ `c_t = Σ α_{t,i}·h_i` → decoder 用 `c_t` 和上一个 token 生成下一个 token |
| 3 | 形状 | `H: (T_enc, d_h)`，`s: (d_s,)`，打分与权重：每个 encoder 位置一个标量，`c_t: (d_h,)`；BiLSTM 时 `d_h = 2·d_hidden` |
| 4 | Bahdanau（加性）打分 | `e_{t,i} = v_aᵀ · tanh(W_a·s_{t-1} + U_a·h_i)`，`W_a: (d_attn, d_s)`、`U_a: (d_attn, d_h)`；`v_a` 负责把 `d_attn` 维向量压成标量 |
| 5 | Luong（乘性）打分 | `dot: sᵀh`（要求 `d_s == d_h`）；`general: sᵀWh`（`W: (d_s, d_h)` 去掉维度约束）；`concat` 基本等同 Bahdanau |
| 6 | `s_{t-1}` vs `s_t` | Bahdanau 用生成当前词**之前**的状态，Luong 用**之后**的状态；混用会产生极难调试的错误 |
| 7 | 通往 Transformer 的桥 | Query = decoder 状态，Key = Value = encoder 状态；self-attention 让序列查询自身并分开学习 K、V 投影，multi-head 并行多组 |
| 8 | 解释性陷阱 | Jain & Wallace（2019）：某些任务上注意力分布可被置换/替换而预测不变；不做消融或反事实检验就不能把权重当作"推理证据" |

### 核心技能（能动手做到）

- [ ] 不用 NumPy，从零实现数值稳定的 `softmax`、Luong dot attention 和 Bahdanau additive attention
- [ ] 手算一个 3×3 例子的 dot attention 权重和上下文向量，并与代码输出对齐
- [ ] 给定 `d_s、d_h、d_attn、T_enc、T_dec、batch`，写出每个中间张量的形状，并写出断言测试 `weights.sum(-1) ≈ 1`
- [ ] 为 attention 加上 padding mask，使 pad 位置权重严格为 0，并处理"全被 mask"的边界情况
- [ ] 解释为什么未经训练的加性 attention 权重接近均匀，以及 `W_a·s` 若没有 tanh 会在 softmax 中被抵消
- [ ] 能把 Bahdanau 的术语翻译成 Q/K/V，并说清它与 self-attention、multi-head attention 的差别

---

## 二、基础自测（选择题）

**Q1.** 与第 09 节的经典 seq2seq 相比，Bahdanau attention 的核心改动是：

- A. 把 encoder 从 RNN 换成 CNN
- B. 在每个 decoder 步，用当前 decoder 状态对所有 encoder 状态打分，加权平均得到**随步变化**的上下文向量
- C. 把最终 encoder 状态复制多份送给 decoder
- D. 用 beam search 代替贪心解码

**Q2.** encoder 是每个方向 256 维的 BiLSTM，源句长度 `T_enc = 20`，decoder 状态 `d_s = 256`。某一个 decoder 步的注意力权重向量和上下文向量的形状分别是：

- A. `(20,)` 和 `(512,)`
- B. `(20,)` 和 `(256,)`
- C. `(512,)` 和 `(20,)`
- D. `(20, 512)` 和 `(512,)`

**Q3.** 在加性打分 `e = v_aᵀ · tanh(W_a·s + U_a·h_i)` 中，`v_a` 的作用是：

- A. 编码位置信息
- B. 对 softmax 做温度缩放
- C. 把 `d_attn` 维的中间向量投影成一个标量分数
- D. 控制 dropout 比例

**Q4.** 沿用 Q2 的设定（`d_s = 256`，`d_h = 512`），想用乘性 attention，应该：

- A. 直接用 Luong `dot`
- B. 用 Luong `general`，`W` 形状为 `(256, 512)`
- C. 用 Luong `general`，`W` 形状为 `(512, 512)`
- D. 乘性 attention 无法处理不同维度，只能用加性

**Q5.** 关于 Bahdanau 与 Luong 两种约定，正确的是：

- A. 两者都用当前步生成**之后**的 decoder 状态 `s_t`
- B. Bahdanau 用 `s_{t-1}`（生成当前词之前），Luong 用 `s_t`（之后），实现时应选定一篇论文的约定并坚持
- C. Bahdanau 用 `s_t`，Luong 用 `s_{t-1}`
- D. 两种约定的结果完全相同，可以随意混用

**Q6.** 用 Q/K/V 语言描述经典（Bahdanau/Luong）attention，正确的是：

- A. Q 来自 encoder，K、V 来自 decoder
- B. Q、K、V 是源序列的三个独立学习投影
- C. Q = decoder 状态；K 和 V 都是 encoder 状态（同一个张量）
- D. Q 随机初始化，K、V 可学习

**Q7.** 同事在汇报里放了一张注意力热力图，说"模型因为看了这个词才做出判断"。根据讲义，最合适的回应是：

- A. 注意力权重和为 1，所以它就是严格的解释
- B. Jain & Wallace（2019）显示某些任务上注意力分布可以被置换或替换而预测不变；需要做消融或反事实检验才能下结论
- C. 注意力权重不可微，无法用于分析
- D. 只有多头注意力的权重才有解释意义

---

## 三、动手 / 代码题

**Q8.** 本节 `main.py` 的数据：

```python
    H = [
        [1.0, 0.0, 0.2],
        [0.5, 0.5, 0.1],
        [0.1, 0.9, 0.3],
    ]
    positions = ["cat", "sat", "mat"]
```

(a) 对 decoder 状态 `s = [0.1, 0.9, 0.3]`（"close to 'mat'"），手算 dot attention 的三个分数、权重（保留 3 位小数）和上下文向量。
(b) 代码中的 `softmax` 为什么先减去 `max(scores)`？不减会怎样？
(c) 如果把 `s` 整体乘以 10 再算，权重会变成什么样？这与 Transformer 里 `QKᵀ/√d` 的缩放有什么联系？

**Q9.** 运行 `main.py`，加性 attention 部分的真实输出是：

```text
=== Bahdanau additive attention (d_attn=2) ===
  decoder state close to 'cat'       -> weights {'cat': 0.322, 'sat': 0.33, 'mat': 0.348}
  decoder state close to 'mat'       -> weights {'cat': 0.338, 'sat': 0.329, 'mat': 0.333}
```

"close to 'cat'" 的状态反而给 `mat` 最高权重，而且两组权重都接近均匀。相关代码：

```python
def additive_attention(decoder_state, encoder_states, W_a, U_a, v_a):
    projected_dec = matvec(W_a, decoder_state)
    scores = []
    for h in encoder_states:
        projected_enc = matvec(U_a, h)
        combined = tanh_vec([projected_enc[i] + projected_dec[i] for i in range(len(v_a))])
        scores.append(dot(v_a, combined))
```

(a) 解释为什么会这样（提示：这些参数是训练出来的吗？`projected_dec` 对每个 encoder 位置是否相同？）
(b) 证明：如果把 `tanh` 去掉（换成恒等函数），无论 decoder 状态是什么，注意力权重都完全一样。

**Q10.** 讲义练习 1 要求给 attention 加 padding mask。请以 `main.py` 的风格（纯 Python）实现：
(a) `masked_dot_attention(decoder_state, encoder_states, mask)`：`mask[i] == False` 的位置权重严格为 0；全部被 mask 时给出明确报错。
(b) `general_attention(decoder_state, encoder_states, W)`：`W` 形状为 `(d_s, d_h)`，允许 `d_s != d_h`。并说明当 `W` 为单位矩阵时它退化为什么。

---

## 四、面试高频题

**Q11.**（基础必考）用你自己的话讲讲 seq2seq 里的 attention：它解决了什么问题、怎么计算、计算复杂度是多少？

**Q12.**（原理深挖）加性 attention 和乘性（点积）attention 有什么区别？为什么 Transformer 选择了点积并且要除以 `√d`？

**Q13.**（原理深挖）从 Bahdanau attention 到 Transformer 的 self-attention，中间到底多了什么？讲义说"主要是记号的变化"，你同意吗？

**Q14.**（工程实践）你接手一个 attention 实现，训练能跑但效果莫名其妙地差。你会怎么排查？要写哪些测试？

**Q15.**（追问型）注意力权重能当模型解释吗？如果业务方一定要"可解释性"，你会怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义原话：保留每一个 encoder 状态，在每个 decoder 步计算一个加权平均，权重表示"此刻 decoder 需要多大程度上看 encoder 位置 i"，这个加权平均就是上下文，并且**每一步都在变**。A、D 与 attention 无关；C 仍然只有一个定长向量的信息量。

### Q2 — 答案：A

权重是"每个 encoder 位置一个标量"，所以是 `(T_enc,) = (20,)`；上下文是 encoder 状态的加权平均，形状与单个 encoder 状态相同。BiLSTM 的 `d_h = 2 × 256 = 512`（讲义形状表的注释），所以 `c_t` 是 `(512,)`。B 忘了双向拼接；D 是整个 `H` 的形状。

### Q3 — 答案：C

`W_a·s + U_a·h_i` 是 `d_attn` 维向量，过 tanh 后仍是 `d_attn` 维；与 `v_a`（`d_attn` 维）做内积才得到一个标量分数。讲义特别强调："This is what `v_α` does. It is not magic."

### Q4 — 答案：B

`dot` 要求 `d_s == d_h`，这里 256 ≠ 512，不能用（讲义："Skip if your encoder is bidirectional"）。`general` 的打分 `sᵀ W h` 中 `s` 是 256 维、`h` 是 512 维，所以 `W` 必须是 `(d_s, d_h) = (256, 512)`。C 的形状对不上 `s`；D 错在 `general` 正是为了去掉维度约束。

### Q5 — 答案：B

讲义的"gotcha"：Bahdanau 用生成当前词之前的 `s_{t-1}`，Luong 用之后的 `s_t`；混用会产生"极难调试的细微错误梯度"。两者在 decoder 的数据流上是不同的结构（Bahdanau 先算上下文再更新 RNN；Luong 先更新 RNN 再算上下文并与 `s_t` 组合输出），D 错。

### Q6 — 答案：C

经典 attention 中 query 是 decoder 状态，key 和 value 是同一组 encoder 状态——打分用它、加权求和也用它。B 描述的是 Transformer 的做法：对输入分别做三个学习投影 `W_Q、W_K、W_V`。

### Q7 — 答案：B

讲义"attention-weight-as-explanation trap"：权重看起来可解释（和为 1、可画图），但 Jain & Wallace（2019）证明在某些任务上可以置换或换成别的分布而预测不变。结论："Never report attention weights as evidence of reasoning without an ablation or counterfactual check." C 错，注意力权重是可微的；D 没有依据。

### Q8 — 参考答案

(a) 分数：
- `cat`: `0.1×1.0 + 0.9×0.0 + 0.3×0.2 = 0.16`
- `sat`: `0.1×0.5 + 0.9×0.5 + 0.3×0.1 = 0.53`
- `mat`: `0.1×0.1 + 0.9×0.9 + 0.3×0.3 = 0.91`

softmax（先减最大值 0.91）：`exp(-0.75) ≈ 0.472`、`exp(-0.38) ≈ 0.684`、`exp(0) = 1`，总和 ≈ 2.156，权重 ≈ `[0.219, 0.317, 0.464]`——与程序输出 `{'cat': 0.219, 'sat': 0.317, 'mat': 0.464}` 一致。

上下文向量 = `0.219×[1.0,0.0,0.2] + 0.317×[0.5,0.5,0.1] + 0.464×[0.1,0.9,0.3]` ≈ `[0.424, 0.576, 0.215]`（已运行验证）。注意它被"拉向" `mat` 的方向，但不是 `mat` 本身——上下文是**软**选择。

(b) softmax 对所有分数同时加减一个常数结果不变（分子分母同乘 `e^(-m)`）。减去最大值后最大的指数是 `e⁰ = 1`，不会上溢；不减时，若分数是 1000，`math.exp(1000)` 直接抛 `OverflowError`（NumPy 则得到 `inf`，再相除得到 `nan`）。这是数值稳定 softmax 的标准写法。

(c) 分数整体放大 10 倍，softmax 变得极其尖锐：实测 `s×10` 时权重 ≈ `[0.001, 0.022, 0.978]`，几乎 one-hot。点积的数值范围随维度 d 增大而增大（若各分量独立、方差为 1，点积方差为 d），softmax 会进入饱和区、梯度接近 0。Transformer 用 `QKᵀ/√d` 把分数方差拉回 1 左右，就是为了避免这种"过尖"。

### Q9 — 参考答案

(a) 三个原因叠加：
1. `W_a`、`U_a`、`v_a` 是**手写的任意参数**，不是训练得到的。加性 attention 的"对齐能力"完全来自学习，未训练时分数没有"相似度"的含义。
2. `projected_dec = W_a·s` 对**所有** encoder 位置都是同一个向量，只是统一加到每个位置上。位置之间的差异几乎全部来自 `U_a·h_i`：实测 `U_a·h` 分别为 `[0.56, 0.24]`、`[0.38, 0.42]`、`[0.32, 0.62]`，`v_a = [0.8, 0.6]` 全为正，于是 `mat` 那一行的分数最大（0.988 vs 0.938 vs 0.912），与 decoder 状态"像谁"无关。
3. 分数之间只差 0.03–0.08，softmax 后自然接近均匀。

讲义 Step 3 的"对齐"演示用的是 dot attention；dot 的分数直接是相似度，不需要训练就能体现对齐。加性 attention 要在训练中学出 `W_a、U_a、v_a` 才会表现出对齐。

(b) 去掉 tanh 后：

```text
e_i = v_aᵀ (W_a s + U_a h_i) = v_aᵀ W_a s + v_aᵀ U_a h_i = C(s) + g(h_i)
```

`C(s)` 与位置 i 无关，是所有分数共同的常数项；而 softmax 对加常数不变，于是 `α_i = softmax(g(h_i))`，**与 s 完全无关**。用代码实测，两种 decoder 状态下的"线性版"权重都是 `[0.3332, 0.3214, 0.3454]`。结论：decoder 状态只能**通过非线性（tanh）**影响不同位置的相对分数——这也是加性 attention 必须有 tanh 的原因。

### Q10 — 参考答案

```python
import math

def softmax(scores):
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def masked_dot_attention(decoder_state, encoder_states, mask):
    if not any(mask):
        raise ValueError("mask must keep at least one position")
    scores = [dot(decoder_state, h) if keep else float("-inf")
              for h, keep in zip(encoder_states, mask)]
    weights = softmax(scores)              # exp(-inf - m) = 0.0
    dim = len(encoder_states[0])
    context = [0.0] * dim
    for w, h in zip(weights, encoder_states):
        for d in range(dim):
            context[d] += w * h[d]
    return context, weights

def general_attention(decoder_state, encoder_states, W):
    # W: (d_s, d_h)；score_i = sᵀ W h_i = (Wᵀ s) · h_i
    d_h = len(encoder_states[0])
    projected = [sum(W[r][c] * decoder_state[r] for r in range(len(decoder_state)))
                 for c in range(d_h)]
    scores = [dot(projected, h) for h in encoder_states]
    weights = softmax(scores)
    context = [0.0] * d_h
    for w, h in zip(weights, encoder_states):
        for d in range(d_h):
            context[d] += w * h[d]
    return context, weights
```

验证（已运行）：
- 在 `H` 后补两行全 0 的 padding，`mask = [True, True, True, False, False]`，权重为 `[0.464, 0.305, 0.231, 0.0, 0.0]`，与无 padding 时完全一致；若不 mask，权重变成 `[0.341, 0.224, 0.169, 0.133, 0.133]`——pad 位置分数为 0，仍然"抢走"了约 27% 的权重，上下文被稀释。这就是讲义技能卡说的"silent accuracy degradation"。
- 全部 mask 时，所有分数都是 `-inf`，`max` 也是 `-inf`，`-inf - (-inf) = nan`，权重全是 `nan`——所以要显式报错（或像一些框架那样把全 mask 行的输出置 0）。
- `general_attention` 中 `W` 为单位矩阵时 `Wᵀ s = s`，退化为 Luong `dot`，权重同为 `[0.464, 0.305, 0.231]`。`d_s = 3`、`d_h = 6`（模拟双向 encoder）时 `W` 取 `3×6` 也能正常运行，而 `main.py` 的 `dot_attention` 会抛 `ValueError: ... length 6 != decoder_state length 3`。

### Q11 — 参考回答要点

- **问题**：经典 seq2seq 把整句压进一个定长向量，长句信息丢失（第 09 节的瓶颈）。
- **计算**（每个 decoder 步 t）：
  1. query = decoder 状态（Bahdanau 用 `s_{t-1}`）；
  2. 与每个 encoder 状态 `h_i` 打分 `e_{t,i}`（加性或点积）；
  3. `α_t = softmax(e_t)`；
  4. `c_t = Σ α_{t,i}·h_i`；
  5. decoder 用 `c_t` + 上一个 token 生成下一个 token。
- **为什么有效**：信息不再必须穿过一个向量，decoder 可以按需直接"回看"源句的任意位置；梯度也有了从输出直达各个 encoder 位置的短路径。
- **复杂度**：每个 decoder 步对 `T_enc` 个位置打分，总计 `O(T_dec · T_enc · d)`；存储 `(T_dec, T_enc)` 的对齐矩阵。
- **加分点**：对齐矩阵在机器翻译中会自动学出近似单调、局部有交叉（语序调整）的对齐，是"软对齐"；讲义说这是"explicit alignment"。

### Q12 — 参考回答要点

- **加性（Bahdanau）**：`vᵀ tanh(W q + U k)`，一个单隐层前馈网络打分；可处理 `d_q ≠ d_k`，表达能力强，但每对 (q, k) 都要过一次 tanh，难以用一次矩阵乘法批量完成。
- **乘性（Luong）**：`qᵀk` 或 `qᵀWk`；整组分数就是一次矩阵乘法 `Q Kᵀ`，在 GPU 上极快；讲义："Same accuracy on most tasks, a lot less code."
- **Transformer 选点积**：可以把所有 query 对所有 key 的分数写成一次 `QKᵀ`，高度并行。
- **除以 `√d`**：若 q、k 各分量独立、均值 0、方差 1，点积方差为 d；d 大时分数尺度大，softmax 饱和、梯度消失。除以 `√d` 把方差拉回 1（Q8(c) 的实验直观展示了分数放大 10 倍后 softmax 变成 one-hot）。
- **加分点**：原 Transformer 论文提到，d 较小时两者效果接近，d 较大时不缩放的点积不如加性——缩放就是为了修复这一点。

### Q13 — 参考回答要点

- **同意的部分**：打分 → softmax → 加权求和的数学完全相同；讲义："The math is the same. The shapes are the same."
- **真正新增的东西**：
  1. **self-attention**：query、key、value 来自**同一个**序列，每个位置都能直接看到其他所有位置，彻底替代 RNN 的循环；
  2. **K、V 分离**：用不同的学习投影 `W_Q、W_K、W_V`，"拿什么匹配"和"返回什么内容"解耦；
  3. **multi-head**：并行多组投影，各自关注不同的关系；
  4. **缩放点积**（`/√d`）；
  5. 因为没有循环，需要**位置编码**提供顺序信息；还要加残差、LayerNorm、前馈层等，堆叠多层；
  6. decoder 侧用**因果 mask** 防止看到未来 token，而 encoder-decoder 之间的 cross-attention 正是 Bahdanau attention 的直系后代。
- **结论**：概念上的突破在 2014 年已经完成，之后是"attention + 工程"——但这些工程（去掉循环带来的并行化）恰恰是规模化的关键。

### Q14 — 参考回答要点

- **先查形状**（讲义："the thing that bites everyone"）：逐个打印 `H、s、W_a·s、U_a·h、scores、weights、context` 的形状，对照 `(d_s, d_h, d_attn, T_enc, T_dec, batch)` 推导期望形状。
- **警惕静默广播**：讲义技能卡拒绝"静默广播"式修复，因为这种 bug 的表现是"精度悄悄下降"，是最糟糕的一类。例如 softmax 在错误的维度上做（对 batch 维或特征维归一化）不会报错。
- **必须写的测试**（技能卡原文）：`assert output.shape == (batch, T_dec, d_h)`、`assert weights.shape == (batch, T_dec, T_enc)`、`weights.sum(dim=-1)` 接近 1。
- **mask 检查**：pad 位置权重是否为 0；全 pad 行是否产生 NaN；decoder 侧是否需要因果 mask。
- **约定检查**：Bahdanau 应使用 `s_{t-1}`，Luong 使用 `s_t`，不要混用。
- **可视化**：画对齐矩阵——翻译任务应接近对角线；若全均匀或全集中在第一个/最后一个位置，多半有 bug。
- **加分点**：用一个只有 2–3 个位置、手算得出答案的单元测试（如 Q8）锁定数值正确性；对 dot attention，最常见的首错是 query 与 key 维度不一致（技能卡）。

### Q15 — 参考回答要点

- **不能直接当解释**：注意力权重反映"混合了哪些位置的表示"，不等于"哪些输入对预测负责"。Jain & Wallace（2019）显示某些任务上可以置换或替换注意力分布而预测不变；多层多头模型中，单层单头的权重更难解读。
- **可以怎么用**：作为探索性的可视化和假设来源（讲义也承认原始注意力权重在 MT 对齐分析中是有用工具），但必须配合验证。
- **更可靠的做法**：
  1. **消融**：mask 掉高权重的 token，看预测是否改变；
  2. **反事实**：替换关键词（如把"不"去掉），看输出变化；
  3. 基于梯度的归因方法（如积分梯度）作为补充；
  4. 业务上提供"证据片段 + 置信度"，而不是一张热力图。
- **常见误区**：在论文/汇报中把热力图直接写成"模型的推理过程"——讲义明确反对。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 09 序列到序列模型](../../09-sequence-to-sequence/docs/zh.md)：上下文向量瓶颈，本节要解决的问题。
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：点积 = 对齐程度，attention 打分的数学本质。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：softmax 减最大值、`-inf` 与 NaN。

### 本节被哪些后续内容用到
- [阶段 05 · 11 机器翻译](../../11-machine-translation/docs/zh.md)：attention 首先在 NMT 中落地，对齐矩阵用于分析翻译质量。
- [阶段 05 · 12 文本摘要](../../12-text-summarization/docs/zh.md)：抽象式摘要的 encoder-decoder 依赖 cross-attention。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：序列查询自身，K、V 分离。
- [阶段 07 · 03 多头注意力](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：讲义练习 2 的完整版本。
- [阶段 07 · 04 位置编码](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：去掉循环后如何提供顺序信息。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：attention 的工程优化。
- [阶段 07 · 15 Attention 变体](../../../07-transformers-deep-dive/15-attention-variants/docs/zh.md)：稀疏、线性、分组查询等变体。

### 延伸关键词
`alignment matrix` · `cross-attention` · `scaled dot-product attention` · `causal mask` · `padding mask` · `multi-head attention` · `pointer network` · `coverage` · `attention rollout` · `积分梯度 (Integrated Gradients)`
