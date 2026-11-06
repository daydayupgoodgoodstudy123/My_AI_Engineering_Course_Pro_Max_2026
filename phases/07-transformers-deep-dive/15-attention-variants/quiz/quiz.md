# 测验 · Attention 变体 — 滑动窗口、稀疏、差分（Attention Variants — Sliding Window, Sparse, Differential）

> **阶段 07 · Transformers 深入 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 全注意力的账单 | 计算 `O(N²)`，KV cache 每层 `O(N)`；Flash Attention 省掉了 `N×N` 激活的显存，但**没有减少运算量** |
| 2 | 滑动窗口（SWA） | 因果 SWA 中位置 i 只看 `[i−W+1, i]`；计算降到 `O(N·W)`，KV cache 每层只需保留最近 W 个 token |
| 3 | 有效感受野 | L 层 SWA 叠起来，信息可以逐层"接力"，最多回看约 `L × W` 个 token（Mistral 7B 的思路） |
| 4 | SWA + 全局层混合 | Gemma 3：5 层 SWA（W=1024）配 1 层全局；全局层负责长程检索，KV cache 总量约降到 1/5.8 |
| 5 | 稀疏 / 块注意力 | 局部 + 跨步（Child et al. 2019，`O(N·√N)`）、Longformer/BigBird（局部 + 全局 token + 随机）、DeepSeek 的 Native Sparse Attention（学习块级稀疏） |
| 6 | 稀疏是"内核工程" | 在稠密矩阵上填 `-inf` 只改变结果、不省计算；真正的收益来自内核层面跳过整块零值（FlashAttention-3、FlexAttention） |
| 7 | Attention sink | softmax 强制每行权重和为 1，"没什么可看"的 query 只能把权重倒给开头几个 token |
| 8 | 差分注意力（DIFF） | `(A1 − λ·A2)·V`：两张 attention 图相减，抵消共同的"汇点/噪声"分量；权重可以为负，每行和变成 `1 − λ` |
| 9 | KV cache 公式 | `2 × 层数 × KV 头数 × d_head × 序列长度 × 每元素字节数`；Llama-3-70B 形状、128K、fp16 约 42.9 GB |
| 10 | FlexAttention | PyTorch 2.5+：把 mask 写成 Python 函数 `(b, h, q_idx, kv_idx) → bool`，编译成定制内核 |

### 核心技能（能动手做到）

- [ ] 从零写出 `causal_mask`、`swa_mask`、`strided_mask`，并验证 8 个 token 上分别覆盖 36、26、24 个格子
- [ ] 推导 SWA 掩码的格子数闭式公式 `W(W+1)/2 + (n−W)·W`，并用代码验证
- [ ] 实现"带掩码的 softmax"，正确处理整行都被遮住的情况（不产生 NaN）
- [ ] 实现差分注意力的一行计算，验证权重和为 `1 − λ`，并能构造一个"汇点被抵消"的玩具例子
- [ ] 用公式算出任意配置下 full / SWA / 5:1 混合 / 差分注意力的 KV cache 大小
- [ ] 能按"上下文长度 × 检索需求 × 显存预算"为新模型选择 attention 拓扑

---

## 二、基础自测（选择题）

**Q1.** 序列长度 n = 10、因果滑动窗口 W = 3，`swa_mask(10, 3)` 中值为 0.0（被关注）的格子共有几个？

- A. 24
- B. 27
- C. 30
- D. 55

**Q2.** Flash Attention 与滑动窗口 attention 的区别，说法正确的是：

- A. 两者都把 attention 的运算量从 `O(N²)` 降到了 `O(N·W)`
- B. Flash Attention 不物化 `N×N` 分数矩阵、节省激活显存，但每个 token 仍与所有 token 计算分数；SWA 直接改变了"谁看谁"，运算量和 KV cache 都随之下降
- C. Flash Attention 会降低模型质量，SWA 不会
- D. SWA 只能用于训练，不能用于推理

**Q3.** Mistral 7B 风格的纯因果 SWA 堆叠，32 层、窗口 W = 4096。按讲义的说法，顶层理论上最远能"间接看到"多少个 token 之前的信息？

- A. 4096
- B. 8192
- C. 约 131K（32 × 4096）
- D. 无限远

**Q4.** 在本节代码的 Gemma-3 5:1 混合配置（W=1024，N=128K）中，KV cache 主要由什么构成？

- A. 5 个 SWA 层，约占 83%
- B. 1 个全局层，约占 96%
- C. 两者各占一半
- D. 位置编码

**Q5.** 关于 "attention sink"，下列解释最准确的是：

- A. 第 0 个 token 的 embedding 学坏了
- B. softmax 要求每行权重和为 1，没有明确关注目标的 query 也必须把权重分出去，往往集中到开头几个 token 上
- C. 是 KV cache 溢出造成的
- D. 只在使用 RoPE 时出现

**Q6.** 差分注意力中，`A1`、`A2` 都是因果 softmax 权重矩阵，`λ = 0.6`。`A1 − λ·A2` 的每一行之和等于：

- A. 1
- B. 0
- C. 0.4
- D. 不确定，取决于输入

**Q7.** 讲义说 "Sparse attention is a kernel-engineering story"。它的意思是：

- A. 稀疏 attention 的数学非常复杂
- B. 只要在稠密分数矩阵上把不需要的位置填 `-inf`，就能获得同比例的加速
- C. 掩码本身很简单；真正的加速来自内核根本不把零值块加载进 SRAM、不去计算它们
- D. 稀疏 attention 只能在 CPU 上实现

**Q8.** 你的模型目标上下文 8K，主要做闲聊，团队里没有内核工程师。按讲义与 skill 文件的选型规则，最合理的选择是：

- A. 全注意力 + FlashAttention
- B. 纯 SWA，窗口 256
- C. 差分注意力 + Native Sparse Attention
- D. BigBird 随机稀疏

---

## 三、动手 / 代码题

**Q9.** 不运行代码，回答：

```python
def swa_mask(n, window):
    M = [[NEG_INF] * n for _ in range(n)]
    for i in range(n):
        lo = max(0, i - window + 1)
        for j in range(lo, i + 1):
            M[i][j] = 0.0
    return M
```

(a) `swa_mask(8, 8) == causal_mask(8)` 的结果？`swa_mask(8, 1)` 是什么形状的掩码？(b) 写一个 O(1) 的函数 `swa_cells(n, W)`，返回被关注格子数，并用 `count_nonmasked` 验证。(c) 为什么第一行用列表推导 `[[NEG_INF] * n for _ in range(n)]`，而不是 `[[NEG_INF] * n] * n`？

**Q10.** 代码的"attention sink"演示实际输出为：

```text
single attn weights: 0.018 0.068 0.335 0.031 0.054 0.112 0.156 0.227
  (notice the weight bleeding to position 0 — the attention sink)
diff   attn weights: +0.008 +0.030 +0.169 +0.013 +0.033 +0.039 +0.097 +0.112
```

(a) 这个输出真的展示了 attention sink 吗？差分注意力"抵消汇点"的效果体现出来了吗？为什么？（提示：看 `q2`、`K2` 是怎么构造的。）(b) 修改输入，构造一个真正有汇点、并能被差分注意力抵消的玩具例子。

**Q11.** 代码中差分注意力的 KV cache 是按 `diff = full * 2` 计算的。

```python
def diff_attention_row(q1, q2, K1, K2, V, mask_row, lam):
    _, w1 = attention_row(q1, K1, V, mask_row)
    _, w2 = attention_row(q2, K2, V, mask_row)
    # ...
```

(a) 按这个函数本身的结构（两组 K、一组 V），在头数、d_head 不变的前提下，推理时 KV cache 应是全注意力的几倍？(b) 解释为什么 Gemma-3 5:1 混合只缩小 5.8 倍，而纯 SWA（W=1024）能缩小 128 倍，并写出混合比例的通用公式。

**Q12.** `attention_row` 里有这样一段：

```python
    finite = [s for s in scores if s != NEG_INF]
    if not finite:
        return [0.0] * len(Vs[0]), [0.0] * len(scores)
    shifted = softmax(finite)
```

(a) 为什么不直接对含 `-inf` 的整行调用 `softmax(scores)`？什么情况下整行都会是 `-inf`？(b) 如果真的对一整行 `-inf` 调用本文件的 `softmax`，会发生什么？

---

## 四、面试高频题

**Q13.**（基础必考）长上下文场景下 full attention 的瓶颈是什么？Flash Attention、SWA、稀疏 attention、GQA 各自解决了哪一部分？

**Q14.**（原理深挖）解释 attention sink 的成因。差分注意力为什么能缓解它？它带来了哪些新问题、代价是什么？

**Q15.**（场景设计）你要把一个 7B 模型的上下文从 8K 扩到 128K，主要用于长文档 RAG。你会怎么设计 attention 拓扑？要算哪些账、做哪些评测？

**Q16.**（工程实践）只在稠密 attention 上加一个滑动窗口 mask，训练会变快吗？怎样才能真正拿到稀疏带来的收益？

**Q17.**（追问型）纯 SWA 模型理论上有 `L × W` 的感受野，为什么长程检索还是不好？Gemma 3 为什么还要保留全局层？

---

## 五、参考答案与解析

### Q1 — 答案：B

前 W 行还没"装满"窗口：第 0、1、2 行分别关注 1、2、3 个位置，合计 6；之后 7 行每行都恰好关注 3 个位置，合计 21。总数 27。一般公式 `W(W+1)/2 + (n−W)·W`。D 是全因果（`n(n+1)/2 = 55`）。

### Q2 — 答案：B

讲义原话："Flash Attention hides the O(N²) activation memory but does not change the arithmetic cost." Flash Attention 是 IO 层面的优化（分块、在 SRAM 里完成 softmax），数学结果与标准 attention 完全相同。SWA 改的是 attention 矩阵的拓扑。A 把两者混为一谈；C 错，Flash Attention 是精确计算；D 错，SWA 在推理时还能省 KV cache。

### Q3 — 答案：C

每过一层，位置 i 能拿到 `[i−W+1, i]` 的信息，而这些位置在上一层又汇总了各自窗口内的信息，所以每层把感受野向前延伸约 W，L 层后约 `L × W = 32 × 4096 = 131072`。但这是"信息可能传到"的上限，不代表能精确检索（见 Q17）。

### Q4 — 答案：B

相对全注意力，SWA 层的 KV 只有 `W/N = 1/128`。总量 = `5/6 × 1/128 + 1/6 ≈ 0.0065 + 0.1667 = 0.1732`，其中全局层占 `0.1667 / 0.1732 ≈ 96%`。所以想进一步省显存，要动的是全局层（例如更大的混合比、对全局层用 GQA/MQA 或 KV 量化），而不是继续缩小窗口。

### Q5 — 答案：B

softmax 输出必须是概率分布。当一个 query 在上下文里找不到真正相关的内容，它也不能输出"全 0"，只好把权重放在某个"无害"的位置——实践中常是 BOS / 第一个 token。讲义的说法是这"偷走了本该给真实内容的容量"。A、C、D 都不是根本原因。

### Q6 — 答案：C

`A1`、`A2` 每行和都为 1，所以 `A1 − λ·A2` 每行和为 `1 − λ = 0.4`。这意味着输出的整体幅度被缩小了，而且个别权重可以为负。代码的实际输出也能印证：λ = 0.5 时差分权重之和约为 0.5。DIFF Transformer 论文因此在每个头的输出后加了归一化，并乘以 `(1 − λ_init)` 来稳定幅度。

### Q7 — 答案：C

数学上，稀疏 attention 就是"给分数矩阵加一个掩码"。但如果内核仍然计算完整的 `N×N` 再把一部分置为 `-inf`，计算量和访存一分没少（B 错）。收益来自块稀疏内核：提前知道哪些 `(Q块, K块)` 全为零，直接跳过它们的加载和计算。这就是 FlexAttention 的 `create_block_mask`、NSA 的块选择在做的事。

### Q8 — 答案：A

skill 文件的第一条规则："Context ≤ 16K and retrieval ≤ 3: full attention with FlashAttention. Don't optimize prematurely." 讲义也说全注意力适用于约 16K 以内。B 的窗口过小（skill 文件指出窗口 < 512 几乎从来不对）；C、D 需要定制内核，收益在 8K 场景下也不明显。

### Q9 — 参考答案

**(a)** `swa_mask(8, 8) == causal_mask(8)` 为 `True`：`lo = max(0, i − 7) = 0` 对所有 i ≤ 7 成立，正好是全因果。只要 `window ≥ n` 都与全因果逐位相同（讲义练习 1）。`swa_mask(8, 1)` 只有对角线为 0，每个 token 只看自己。

**(b)**

```python
def swa_cells(n, W):
    W = min(W, n)
    return W * (W + 1) // 2 + (n - W) * W

for n, W in [(8, 4), (8, 1), (8, 8), (10, 3), (8, 100)]:
    print(n, W, count_nonmasked(swa_mask(n, W)), swa_cells(n, W))
```

实际输出（两列一致）：

```text
8 4 26 26
8 1 8 8
8 8 36 36
10 3 27 27
8 100 36 36
```

`min(W, n)` 处理窗口大于序列的情况。n 很大时格子数约为 `n·W`，与全因果的约 `n²/2` 相比，比例约为 `2W/n`。

**(c)** `[[NEG_INF] * n] * n` 会生成 n 个指向**同一个**列表对象的引用，改 `M[0][0]` 会同时改掉每一行的第 0 列，掩码全乱。列表推导每次循环都新建一行，互不影响。

### Q10 — 参考答案

**(a)** 都没有体现。

- 位置 0 的权重是 0.018，是 8 个位置里**最小**的，打印的注释"weight bleeding to position 0"与输出矛盾。原因：`K`、`V`、`q` 全是独立的高斯随机数，没有任何机制让第 0 个 token 特殊。Attention sink 是训练出来的现象（模型学会把 BOS 的 key 做成"谁都能对上"的方向），随机向量不会自发出现。
- `q2 = q + 0.2·噪声`、`K2 = K + 0.2·噪声`，A2 几乎就是 A1 的拷贝，于是 `A1 − 0.5·A2 ≈ 0.5·A1`：输出的差分权重基本是单注意力权重减半（0.335 → 0.169，0.227 → 0.112），既没有出现负权重，也没有"抵消"任何特定分量。真正的差分注意力依赖两组投影学到**不同**的东西：一组带内容 + 共模噪声，另一组主要是共模噪声。

**(b)** 让第 0 个 token 的 key 带一个强"汇点"方向，q1 = 内容分量 + 汇点分量，q2 = 只有汇点分量：

```python
import random
from main import causal_mask, attention_row, diff_attention_row

rng = random.Random(0)
d, n = 8, 8
K = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(n)]
V = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(n)]
K[0][0] += 2.5                              # 第 0 个 token 的 key 带一个很强的"汇点"分量
sink = [2.5] + [0.0] * (d - 1)
q1 = [x + s for x, s in zip(K[5], sink)]    # q1 = 想找第 5 个 token 的内容分量 + 汇点分量
q2 = sink[:]                                # q2 = 只有汇点分量
mask = causal_mask(n)[n - 1]

_, w1 = attention_row(q1, K, V, mask)
_, w2 = attention_row(q2, K, V, mask)
_, wd = diff_attention_row(q1, q2, K, K, V, mask, lam=0.6)
print("A1  :", " ".join(f"{w:.3f}" for w in w1))
print("A2  :", " ".join(f"{w:.3f}" for w in w2))
print("diff:", " ".join(f"{w:+.3f}" for w in wd), f" sum={sum(wd):.3f}")
```

实际输出：

```text
A1  : 0.317 0.003 0.468 0.000 0.001 0.197 0.005 0.009
A2  : 0.558 0.008 0.223 0.018 0.024 0.075 0.031 0.063
diff: -0.018 -0.002 +0.334 -0.010 -0.013 +0.152 -0.014 -0.029  sum=0.400
```

解读：A1 把 0.317 的权重倒给了位置 0（汇点）；A2 主要盯着位置 0。相减后位置 0 降到约 0，内容相关的位置（2 和 5；在这个随机种子下 K[2] 恰好与 K[5] 方向相近）保留了下来，一些无关位置出现小的负权重，行和为 `1 − 0.6 = 0.4`。

### Q11 — 参考答案

**(a)** 推理时要为每个历史 token 缓存 K1、K2、V 三份张量，而全注意力只缓存 K、V 两份，所以是 **1.5 倍**，不是 2 倍。只有当 V 也复制一份时才是 2 倍。补充：DIFF Transformer 论文为了与基线对齐参数量和计算量，把头数减半（每个头的 Q/K 拆成两组），在这种配置下 KV cache 与基线大体持平。所以"差分注意力 KV 翻倍"是**固定头数、简单复制**时的上界，不是必然代价。

**(b)** 设全注意力层的 KV 为 1，SWA 层为 `W/N`。混合比例为 `s:g`（s 层 SWA、g 层全局）时：

`相对大小 = (s/(s+g))·(W/N) + g/(s+g)`

代入 `s=5, g=1, W/N=1/128`：`0.0065 + 0.1667 = 0.1732`，即缩小 `1/0.1732 ≈ 5.8` 倍。N 越大，SWA 层的贡献越趋近 0，混合配置的缩小倍数会趋近 `(s+g)/g = 6`。这就是全局层的"保底成本"。

```python
def mixed_kv_ratio(swa_layers, global_layers, window, n):
    total = swa_layers + global_layers
    return swa_layers / total * (window / n) + global_layers / total

print(1 / mixed_kv_ratio(5, 1, 1024, 131072))   # 5.774...
```

### Q12 — 参考答案

**(a)** 本文件的 `softmax` 先算 `m = max(xs)` 再 `exp(x − m)`。只过滤出有限值来做 softmax，再把权重放回原位置、被遮住的位置填 0，可以避免 `-inf` 参与运算。整行都是 `-inf` 的情况：理论上因果掩码的每一行至少有对角线可看；但在 padding 掩码、或某些稀疏模式与 padding 叠加时，可能出现一整行没有任何可看的位置。代码对此返回全 0 输出和全 0 权重。

**(b)** `m = max(xs) = -inf`，`x − m = -inf − (-inf) = nan`，`math.exp(nan) = nan`，最终所有权重都是 `nan`，并会沿着后续计算传染。这正是 PyTorch 里"整行被 mask 导致 NaN"问题的纯 Python 版本。

### Q13 — 参考回答要点

- **瓶颈**：①计算 `O(N²)`（每个 token 对所有 token 打分）；②训练时 `N×N` 激活显存；③推理时 KV cache 随 N 线性增长，长上下文 + 大 batch 时常是显存第一杀手。
- **各方案对应**：
  - Flash Attention：解决②（不物化 `N×N`），不改①、③；
  - SWA：①降到 `O(N·W)`，③降到每层 `O(W)`；
  - 稀疏 attention：①按稀疏度下降，需要专用内核才能兑现；
  - GQA/MQA：减少 KV 头数，直接缩小③（本节代码的"8 KV heads"就是 GQA 配置）。
- **加分点**：这些手段可以叠加，例如 Gemma 3 = SWA/全局混合 + GQA + Flash 类内核；KV cache 公式能脱口而出。
- **常见误区**：认为 Flash Attention 让 attention 变成了线性复杂度。

### Q14 — 参考回答要点

- **成因**：softmax 归一化让每行和为 1；许多 query 其实"不需要"关注特定内容，权重只能被倾倒到一个固定位置（常为第一个 token），形成汇点，占用了本可分配给真实内容的注意力。
- **差分注意力**：用两组 Q/K 算出 A1、A2，输出 `(A1 − λ·A2)·V`。两张图共有的部分（汇点、对无关 token 的均匀噪声）被相减抵消，类似差分放大器消除共模噪声；λ 可学习，讲义称典型值 0.5–0.8。
- **新问题与代价**：
  - 权重可以为负，每行和变为 `1 − λ`，输出幅度变化，需要每头归一化来稳定（论文做法）；
  - 要算两张 attention 图，计算更多；若不减头数，K 的缓存也要两份；
  - 需要从预训练阶段就采用，难以改造已训练好的模型（skill 文件："retrofitting differential attention into a pretrained model is expensive"）；
  - skill 文件提醒：论文证据主要来自中小规模模型，大规模证据有限。
- **加分点**：提到另一类做法是显式提供"汇点"（例如保留开头几个 token 的 KV），说明汇点本身是模型在利用 softmax 的约束，不一定都是坏事。

### Q15 — 参考回答要点

- **算 KV 账**：先用 `2 × L × n_kv × d_head × N × bytes` 算出 128K 下全注意力 KV，评估单卡能撑多大 batch。
- **拓扑选择**：按 skill 文件，16–128K 且检索需求中等 → Gemma-3 式 5:1 SWA/全局混合，W=1024；RAG 检索需求高 → 可以提高全局层比例，或只在顶部少数层用差分注意力。
- **位置编码**：任何变体都要配合 RoPE 扩展方案（位置插值 / YaRN，见第 04 节），并明确写出位置方案。
- **训练**：已有 8K 模型做长上下文继续训练；SWA 可以通过掩码直接改造，差分注意力和学习式稀疏不能直接改造。
- **评测**：needle-in-a-haystack（不同深度、不同长度）、长文档 QA、短上下文基准不回退（防止长上下文训练损伤常规能力），以及显存/吞吐/首 token 延迟。
- **常见误区**：只看 KV 缩小倍数，不测长程检索；7B 以下做纯 SWA（skill 文件明确建议避免）。

### Q16 — 参考回答要点

- **不会变快**：在稠密 attention 里加一个 `-inf` mask，内核仍然计算完整的 `N×N` 分数再屏蔽掉，FLOPs 和访存都不变，甚至因为多了构造 mask 的开销更慢。
- **拿到收益的方法**：
  - 使用支持块稀疏的内核：FlexAttention（`create_block_mask` 预先算出哪些块全为零，生成的内核直接跳过；讲义称常见模式下与 FlashAttention-3 速度相差 10% 以内）；
  - FlashAttention 原生支持的局部窗口参数；
  - 推理时用环形缓冲区实现 SWA 的 KV cache，只保留最近 W 个 token，才能真正省显存。
- **加分点**：块大小（如 128）决定了稀疏的粒度，掩码模式要尽量"块对齐"，否则大量块是部分非零，无法跳过。
- **常见误区**：在 profile 之前就宣称 SWA 带来了加速。

### Q17 — 参考回答要点

- **感受野 ≠ 检索能力**：信息要经过多层"接力"才能从远处传到当前位置，每一层都要在有限维度里压缩窗口内的所有内容，远处的精确细节（比如一个具体的数字、一个 needle）在传递中被稀释、覆盖。`L × W` 是上限，不是保证。
- **讲义观点**：纯 SWA 模型在长程检索上吃力，修复办法就是插入全注意力层；Gemma 3 用 5:1 的混合保住检索能力，同时把 KV 缩小约 6 倍。
- **为什么不是更少的全局层**：全局层越少，检索越依赖层间接力；skill 文件也提示 7B 以下纯 SWA 模型在推理类基准上会有可测量的退化。
- **加分点**：把 Q4/Q11 的计算带进来——全局层占了混合配置 96% 的 KV，这是"检索能力的显存保费"。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../02-self-attention-from-scratch/docs/zh.md)：分数矩阵、softmax、加权求和。
- [阶段 07 · 03 多头 Attention](../../03-multi-head-attention/docs/zh.md)：多头与 KV 头数的概念。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：因果 mask 是本节所有变体的起点。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：KV cache 公式与 Flash Attention 的 IO 视角。

### 本节被哪些后续内容用到
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：长上下文变体都要搭配 RoPE 扩展（位置插值 / YaRN）。
- [阶段 07 · 14 从零构建 Transformer](../../14-build-a-transformer-capstone/docs/zh.md)：讲义练习 2、3 在这个综合项目上实现 SWA 和 5:1 混合。
- [阶段 10 · 16 差分注意力 V2](../../../10-llms-from-scratch/16-differential-attention-v2/docs/zh.md)：差分注意力的深入版本。
- [阶段 10 · 17 Native Sparse Attention](../../../10-llms-from-scratch/17-native-sparse-attention/docs/zh.md)：学习式块稀疏的完整实现。
- [阶段 10 · 21 Jamba 混合 SSM-Transformer](../../../10-llms-from-scratch/21-jamba-hybrid-ssm-transformer/docs/zh.md)：另一种"混合层"思路，用 SSM 层替代部分 attention 层。
- [阶段 05 · 28 长上下文评测](../../../05-nlp-foundations-to-advanced/28-long-context-evaluation/docs/zh.md)：needle-in-a-haystack 等评测方法。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：KV cache 显存管理在服务端的落地。

### 延伸关键词
`Sliding Window Attention` · `Longformer / BigBird` · `Sparse Transformer (local + strided)` · `Native Sparse Attention` · `Differential Transformer` · `attention sink` · `FlexAttention / create_block_mask` · `GQA / MQA` · `YaRN` · `ring buffer KV cache`
