# 测验 · Differential Attention（V2）（Differential Attention (V2)）

> **阶段 10 · 从零构建 LLM · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | softmax 的噪声底（noise floor） | softmax 永远不会给出精确的 0，每个无关 token 约分到 `O(1/N)` 的权重，N 个加起来是 `O(1)`，上下文越长问题越明显 |
| 2 | 差分注意力公式 | `DiffAttn = (softmax(Q₁K₁ᵀ/√d) − λ·softmax(Q₂K₂ᵀ/√d))·V`：两张注意力图相减，抵消两者共有的噪声成分 |
| 3 | 降噪耳机类比 | 两个麦克风录到同一声音 + 相关的背景噪声，相减后共模噪声消失，信号因两路幅度不同而保留 |
| 4 | λ 的参数化 | 每头一个可学习标量 `λ = exp(λ_q1·λ_k1) − exp(λ_q2·λ_k2) + λ_init`，可以为负；讲义称 `λ_init` 默认约 0.8 |
| 5 | 负权重与总质量 | 差分后的权重可以为负，每行之和为 `1 − λ`；V 投影吸收符号 |
| 6 | DIFF V1 的三个问题 | 为保持参数量而减半 head dim，decode 时 value cache 要读两遍；需要自定义 CUDA kernel、不兼容 FlashAttention；每头 RMSNorm 在 70B 级长训练中不稳定 |
| 7 | DIFF V2 的改动 | Q 头数翻倍、KV 头数与 head dim 不变（参数从 MLP up-projection 借来）；相减后再投影回基线的 O_W；decode 速度与基线持平、FlashAttention 不改、去掉每头 RMSNorm |
| 8 | 算术强度 | V2 每读一次 KV 做两倍的 Q 计算，decode 时"每字节的 FLOPs"上升，对 memory-bound 的 decode 有利 |
| 9 | 适用场景 | 收益随上下文增长：64k+ RAG、needle-in-haystack（32k 以后）、多文档 QA 明显；<4k 对话几乎无差别 |
| 10 | 与其它旋钮兼容 | 与 GQA、MoE、RoPE、YaRN、FlashAttention（V2）、speculative decoding 兼容；与 MLA 理论可行但无公开论文 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 写出 softmax、标准注意力与差分注意力，并解释每行权重之和为什么是 `1 − λ`
- [ ] 跑通 `main.py`，读懂 SNR（信号权重 / 平均噪声权重绝对值）的定义，并扫描 λ 找到 SNR 最大的点
- [ ] 指出代码玩具中"两个分支的噪声相互独立"这一设定只能抵消噪声的**均值**，并构造"相关噪声"实验验证真正的共模抵消
- [ ] 正确计算基线、DIFF V1、DIFF V2 的注意力参数量与 KV cache（在同一 MHA/GQA 口径下比较）
- [ ] 解释 V1 → V2 每一项改动对应解决了哪个生产问题
- [ ] 判断一个具体业务（上下文长度、幻觉类型、是否从头训练）是否值得引入差分注意力

---

## 二、基础自测（选择题）

**Q1.** 讲义认为标准 softmax 注意力存在"噪声底"，其根本原因是：

- A. 注意力分数没有除以 `√d`
- B. 因果 mask 把未来位置设成了 −∞
- C. Value 向量中混入了噪声
- D. softmax 不会输出精确的 0，每个无关 token 都分到约 `O(1/N)` 的正权重，合计是 `O(1)` 量级

**Q2.** 差分注意力的输出是：

- A. `softmax((Q₁K₁ᵀ − Q₂K₂ᵀ)/√d)·V`
- B. `(softmax(Q₁K₁ᵀ/√d) − λ·softmax(Q₂K₂ᵀ/√d))·V`
- C. `softmax(Q₁K₁ᵀ/√d)·V − softmax(Q₂K₂ᵀ/√d)·V`，λ 固定为 1
- D. `softmax(Q₁K₁ᵀ/√d) ⊙ softmax(Q₂K₂ᵀ/√d)·V`（逐元素相乘）

**Q3.** 关于 DIFF V1 与 DIFF V2，正确的是：

- A. V2 把 head dim 减半以保持参数量，V1 则把 Q 头翻倍
- B. V2 仍需要自定义 CUDA kernel，但 decode 更快
- C. V2 把 Q 头数翻倍、KV 头数与 head dim 保持不变，decode 速度与基线持平，可直接用 FlashAttention，并去掉了 V1 的每头 RMSNorm
- D. V2 增加了 KV 头数，所以 KV cache 翻倍

**Q4.** 某一行差分注意力权重由 `a − λ·b` 得到，a、b 分别是两张 softmax 图的同一行，λ = 0.8。这一行权重之和为：

- A. 0.2
- B. 1.0
- C. 1.8
- D. 0

**Q5.** `main.py` Step 2 的噪声扫描输出如下（λ = 0.8）：

```text
   noise_std    std SNR    diff SNR (lam=0.8)
        0.25      52.09                173.19
        0.50      48.69                 88.46
        1.00      34.62                 35.14
        1.50      15.93                 11.80
        2.00       8.46                  5.42
```

据此最合理的结论是：

- A. 差分注意力在任何噪声水平下都"reliably"提高 SNR，与代码结尾的 takeaway 一致
- B. 噪声越大，差分注意力的优势越大
- C. 在这个玩具里，噪声较大时差分注意力反而更差；因为两个分支的噪声相互独立，相减只抵消了噪声的均值，却叠加了两路的随机波动
- D. 结果说明 λ = 0.8 时差分注意力等价于标准注意力

**Q6.** 讲义写道："At 128k tokens, even if each non-matching token gets only 0.001% of the probability, 127,999 of them combined contribute about 12% of the total." 对这句话的判断正确的是：

- A. 算术不对：`0.001% × 127,999 ≈ 1.28`，即 128%，不可能；约 12% 对应的是每个 token 0.0001%
- B. 完全正确
- C. 应为约 1.2%
- D. 应为约 0.12%

**Q7.** 根据讲义的"When to reach for it"表，差分注意力收益**最小**的是：

- A. 64k 以上的长上下文 RAG
- B. 32k 以上的 needle-in-haystack 基准
- C. 多文档问答
- D. 4k 以内的短对话

**Q8.** `main.py` Step 3 打印 `DIFF V2 attention : 75.5M (delta 8.4M)`，相对 `baseline attention : 67.1M`。这个 8.4M 的含义是：

- A. 正好等于讲义所说的"roughly `hidden * hidden` extra"
- B. 口径不一致的产物：基线按 MHA（`4h²`）算，V2 却按 GQA（8 个 KV 头）算，且 V2 把 Q 和 O 都按 `2h²` 计；`+2h²`（Q、O 翻倍，约 33.6M）减去 GQA 节省的约 25.2M，恰好得到 8.4M
- C. 是 λ 参数的数量
- D. 是 V2 比 V1 节省的参数量

---

## 三、动手 / 代码题

**Q9.** 讲义练习 4：在 Step 1 的玩具上扫描 λ。

```python
    for lam in (0.0, 0.3, 0.6, 0.8, 1.0):
        diff = [a1 - lam * a2 for a1, a2 in zip(A1, A2)]
        dsnr = snr(diff, signal_pos)
```

1. 把 λ 改成从 0 到 2、步长 0.01 扫描，SNR 最大值出现在哪里？
2. 为什么 SNR 先升后降？λ = 1 时这一行权重之和是多少？λ > 1 意味着什么？
3. 输出中"weight on signal position"随 λ 增大略微下降（0.044569 → 0.044227），为什么？

**Q10.** Step 1 的两个分支的 logits 是这样生成的：

```python
    logits_trained = [rng.gauss(0, noise_std) for _ in range(n_tokens)]
    logits_trained[signal_pos] = signal_logit
    logits_untrained = [rng.gauss(0, noise_std) for _ in range(n_tokens)]
```

1. 两个分支的噪声是"共有的"吗？在这种设定下，差分到底抵消了什么？
2. 改一行代码，让分支 2 与分支 1 **共享**同一份噪声（但分支 2 在信号位置没有尖峰），再测 λ = 0.8 和 λ = 1.0 的 SNR。
3. 这个对比说明了训练后的差分注意力需要学到什么？

**Q11.** 修正参数量计算（讲义练习 2、5）：

```python
def attention_params_baseline(hidden: int) -> int:
    return 4 * hidden * hidden

def attention_params_diff_v2(hidden, n_heads, d_head, kv_heads):
    q_params = hidden * (2 * n_heads * d_head)
    k_params = hidden * (kv_heads * d_head)
    v_params = hidden * (kv_heads * d_head)
    o_params = (2 * n_heads * d_head) * hidden
    lam_params = 4 * n_heads * d_head
    return q_params + k_params + v_params + o_params + lam_params
```

1. 按讲义的描述（"After the subtraction, the extra dimension is projected back down to match baseline Transformer's O_W projection"），`o_params` 应该是多少？
2. 在 hidden = 4096、32 个 Q 头、head_dim = 128 下，分别在 **MHA（32 个 KV 头）** 和 **GQA（8 个 KV 头）** 两种口径下，给出基线与 V2 的注意力参数量和差值（忽略 λ）。32 层模型一共多出多少参数？
3. 讲义练习 5：证明 GQA + DIFF V2（8 个 KV 头、32 个基线 Q 头）的 KV cache 与同配置 GQA 基线完全相同，写出每 token 每层的 KV 字节数（BF16）。

**Q12.** 代码里定义了 `standard_attention`、`diff_attention`、`random_projection`、`matmul`、`build_signal_plus_noise` 五个函数，docstring 还写着"The Q, K projections are applied AFTER this build step so that both differential branches see the same underlying sequence but project it through different matrices — the faithful simulation of DIFF attention"。

1. `main()` 实际调用了其中哪些？
2. 请用这些函数写一个"真正经过 Q/K 投影"的实验：构造 1024 个 token 的输入序列，分支 1 用同一个矩阵投影 q 与 X（保持对齐），分支 2 用两个不同的随机矩阵；比较标准注意力与 λ = 0.8 的差分注意力的 SNR。
3. 讲义 Step 4 称"DIFF attention reliably produces a higher signal-to-noise ratio by a factor of 3x-10x"，Step 1 实际提升了多少倍？

---

## 四、面试高频题

**Q13.**（基础必考）什么是差分注意力（Differential Attention）？它想解决标准注意力的什么问题？为什么说它对长上下文更有价值？

**Q14.**（原理深挖）请从数学上说明 softmax 噪声底的来源，以及"两个 softmax 相减"为什么能抵消噪声而保留信号。差分后权重可能为负，这有问题吗？

**Q15.**（原理深挖）DIFF V1 为什么没有进入前沿预训练？V2 分别怎么解决？为什么"Q 头翻倍、KV 头不变"能让 decode 速度与基线持平？

**Q16.**（场景设计）你们的 128k 长上下文 RAG 产品经常出现"引用了不存在的段落"和"中间位置文档被忽略"。有人提议换成差分注意力。你会怎么评估和推进？

**Q17.**（追问型）除了差分注意力，还有哪些思路可以缓解长上下文下的注意力稀释？它们和差分注意力是什么关系？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Softmax can never produce exact zeros — every non-matching token gets some positive mass... each unrelated token still contributes `O(1/N)` to the weighted sum. The total contribution of unrelated tokens is `O((N-1)/N) = O(1)`." A 是数值尺度问题，缩放与否 softmax 都不会给出 0；B 处理的是未来位置，与噪声底无关；C 混淆了权重与 value。

### Q2 — 答案：B

讲义公式：`A_1 = softmax(Q_1 K_1^T / sqrt(d))`，`A_2 = softmax(Q_2 K_2^T / sqrt(d))`，`DiffAttn = (A_1 - lambda * A_2) V`。A 是"先相减再 softmax"，结果仍是非负、和为 1 的分布，无法抵消噪声底；C 把 λ 固定为 1，而 λ 是每头可学习的；D 是乘法门控，不是差分。

### Q3 — 答案：C

讲义 V2 部分："doubles the number of query heads and keeps the KV heads the same... The head dimension stays the same as baseline"，带来 decode 与基线持平、FlashAttention 不变、算术强度上升三项好处；"V2 also removes the per-head RMSNorm"。A 把 V1、V2 说反了（V1 才减半 head dim）；B 错，V2 不需要自定义 kernel；D 错，KV 头不变，KV cache 与基线相同。

### Q4 — 答案：A

`Σ(a − λb) = Σa − λΣb = 1 − 0.8 × 1 = 0.2`。代码实测 λ = 0.8 时该行之和为 0.2，λ = 1.0 时约为 0（3.2e-17 的浮点误差）。这意味着差分输出的整体幅度被缩小到约 `1 − λ`，实际实现需要后续的归一化或缩放来补偿（讲义提到 V1 用每头 RMSNorm 稳定相减后的输出）。

### Q5 — 答案：C

噪声 0.25、0.5 时差分明显更好（约 3.3 倍、1.8 倍），噪声 1.0 时基本持平，1.5、2.0 时差分反而更差。原因：代码中两个分支的噪声 logits 是**两次独立抽样**，并不"共有"。相减能去掉两路共同的**均值**（约 `1/N` 的均匀底），但两路各自的随机波动是独立的，相减后方差相加；噪声越大，波动部分占比越高，差分越吃亏。A 与这张表矛盾（代码结尾 takeaway 的"reliably improves"并不成立）；B 正好说反；D 错，只有 λ = 0 时才等价。

### Q6 — 答案：A

`0.001% = 1e-5`，`1e-5 × 127,999 ≈ 1.28`，超过 1，概率不可能这样分配；若每个无关 token 分到 0.0001%（1e-6），合计约 0.128，即讲义说的约 12%（已用 Python 计算）。讲义想表达的观点（大量微小权重累加不可忽略）没错，只是数字差了 10 倍。

### Q7 — 答案：D

讲义表格："Short chat (< 4k) — Essentially indistinguishable from baseline"；"The value grows with context length. At 4k tokens the noise floor is small enough that standard attention is fine." A、B、C 都是讲义列出的收益显著场景（8k 代码补全被列为"Marginal"）。

### Q8 — 答案：B

`compute_param_diff(hidden=4096, n_heads=32, kv_heads=8)`：基线 `4h² = 67,108,864`（MHA）；V2 = Q `2h²`（33.55M）+ K、V 各 `4096 × 1024`（4.19M × 2）+ O `2h²`（33.55M）+ λ 16,384 = 75,513,856。差值 8,404,992 = `+2h²`（Q 与 O 各多出 `h²`）− `25,165,824`（GQA 的 K/V 比 MHA 少的部分）+ λ。这是把两种不同口径相减得到的数字，既不是讲义说的"约 `h²`"（A 错），也不是 λ（C）；V2 的差值远大于 V1 的 8.2K，D 也错。同时代码结尾"V2 brings the parameter cost down"的说法与自己的输出矛盾。

### Q9 — 参考答案

1. 以 0.01 为步长扫描（已运行），SNR 在 **λ ≈ 0.77** 处最大，约 92.44；λ = 0.8 时 92.31，λ = 1.0 时 85.25，λ = 1.2 时 73.42。
2. 分支 1 的无关 token 权重 ≈ `1/N + 波动₁`，分支 2 ≈ `1/N + 波动₂`。λ 从 0 增大时，`a − λb` 的均值部分 `(1 − λ)/N` 逐渐减小，平均绝对值下降，SNR 上升；但同时 `λ·波动₂` 被引入，λ 越大这部分越大，超过某点后平均绝对值反而上升，SNR 下降。λ = 1 时整行之和为 0（均值完全抵消，只剩两路波动之差）；λ > 1 时整行之和为负（λ = 1.2 时为 −0.2），等于从输出中"倒扣"value 的平均，会把无关 token 推向负权重而非零。最优 λ 略小于 1，正是"均值抵消"与"波动叠加"的折中。
3. 信号位置的差分权重是 `a_sig − λ·b_sig`。分支 2 在信号位置只是普通噪声（实测 `b_sig ≈ 0.00034`），λ 增大会从信号上扣掉 `λ × 0.00034`，所以略有下降。对真实模型而言，这就是讲义所说"信号只有在两张图里幅度相同时才会被抵消"——分支 2 在信号处越小，信号保留越多。

### Q10 — 参考答案

1. 不是共有的，两份 `rng.gauss` 是独立抽样。差分只能抵消两者**期望相同**的部分（均匀的 `1/N` 底），而各自的随机波动不能抵消、反而叠加——这也是 Q5 中高噪声下差分变差的原因。
2. 改法：

```python
    logits_untrained = list(logits_trained)
    logits_untrained[signal_pos] = 0.0     # 分支 2 看到同样的噪声，但没有信号尖峰
```

   实测（已运行）：λ = 0.8 时 SNR ≈ **287.6**，λ = 1.0 时 ≈ **1023**，对比独立噪声时的 92.3 / 85.3 以及标准注意力的 47.7。λ = 1 时并非完全为 0，因为两个分支的归一化常数不同（分支 1 的分母含 `e⁴` 的信号项），残余很小。
3. 说明差分注意力的收益取决于"两个分支的噪声有多相关"。训练要让分支 2 学成一个"噪声估计器"：在无关 token 上与分支 1 给出相似的分布，在真正相关的 token 上不跟随分支 1 的尖峰。λ 与两组 Q/K 是一起学的，所以模型可以同时调整"噪声对齐程度"与"抵消比例"。代码中的"untrained head = 独立噪声"其实是最不利于差分的情形。

### Q11 — 参考答案

1. 相减时两路 Q 头配对成一路输出，输出头数回到基线的 32 个、维度 `32 × 128 = h`，所以 O_W 应为 `h × h`，即 `o_params = (n_heads * d_head) * hidden`，而不是 `2h²`。讲义 Step 5 也写 V2 额外参数是"roughly `hidden * hidden`"。
2. 统一口径后（已用 Python 计算，忽略 λ）：

| 口径 | 基线 | DIFF V2（Q 为 `2h²`，O 为 `h²`） | 差值 |
|------|------|-------------------------------|------|
| MHA（32 KV 头） | `4h² = 67.1M` | `2h² + h² + h² + h² = 5h² = 83.9M` | `+h² = 16.8M` |
| GQA（8 KV 头） | `2h² + 2·h·1024 = 41.9M` | `2h² + 2·h·1024 + h² = 58.7M` | `+h² = 16.8M` |

   两种口径下差值都是 `h² = 16,777,216`；32 层共多出约 **537M**（536,870,912）。讲义说 V2 的这部分参数"borrowing parameters from the up-projection"——实际模型会相应缩小 MLP 的 `intermediate_size`，使总参数不变，这一点代码没有体现。
3. KV cache 只取决于 KV 头数、head_dim 和层数。DIFF V2 只增加 Q 头，K、V 投影与基线 GQA 完全相同（各 `h × 8 × 128`），所以每 token 每层缓存 `2(K,V) × 8 × 128 × 2 字节 = 4,096 字节`，与基线 GQA 一致。V1 则不同：它把 head 拆小，同一份 value 在两个 softmax 分支中各读一次，讲义称"Decode had to load the value cache twice per step"。

### Q12 — 参考答案

1. `main()` 只用到了 `softmax_row`、`snr`、`compute_param_diff`（及其调用的三个 `attention_params_*`）和 `fmt_m`。`standard_attention`、`diff_attention`、`random_projection`、`matmul`、`build_signal_plus_noise` **全部未被调用**——Step 1 标题写的是"direct-logit toy"，直接在 logits 层面生成数据，没有经过任何 Q/K 投影。docstring 所说的"faithful simulation"并没有执行。
2. 参考实验（已运行一次，结果供参考）：

```python
import random
from main import (build_signal_plus_noise, random_projection, matmul,
                  standard_attention, diff_attention, snr)

rng = random.Random(0)
N, sp, d = 1024, 500, 64
X, q = build_signal_plus_noise(N, sp, d, noise_scale=0.3, rng=rng)
W1 = random_projection(d, d, rng)            # 分支 1：q 与 X 用同一矩阵，保持对齐
Wq2 = random_projection(d, d, rng)           # 分支 2：Q、K 用不同的随机矩阵
Wk2 = random_projection(d, d, rng)
qs = [[x * 8 for x in q]]                    # 放大 query，让信号能从噪声中显现
Q1, K1 = matmul(qs, W1), matmul(X, W1)
Q2, K2 = matmul(qs, Wq2), matmul(X, Wk2)
V = [[1.0] for _ in range(N)]
w, _ = standard_attention(Q1, K1, V)
dw, _ = diff_attention(Q1, K1, Q2, K2, V, lam=0.8)
print(snr(w[0], sp), snr(dw[0], sp))
```

   上面这段代码实际运行输出标准注意力 SNR ≈ 2.15、差分 ≈ 3.80；换用另外几组随机矩阵，标准注意力约 2.2–2.5，差分约 3.8–4.3。数值依赖于噪声幅度、query 缩放和随机种子，重点是让 `diff_attention` 真正跑起来并观察：随机初始化的分支 2 同样只能抵消均值部分。
3. Step 1 中 λ = 0.8 时 SNR 从 47.72 提升到 92.31，约 **1.9 倍**；最好的 λ = 0.77 也只有约 1.94 倍。只有在噪声很小（Step 2 的 0.25）时达到约 3.3 倍，噪声大时还不如标准注意力。讲义"3x-10x"与"reliably"在这个玩具里都不成立；这个倍数在真实模型中取决于两个分支被训练成多大程度的"相关噪声"（见 Q10）。

### Q13 — 参考回答要点

- **定义**：把每个头的 Q、K 分成两组，各算一张 softmax 注意力图，用第一张减去 λ 倍的第二张，再乘 V：`(A₁ − λA₂)V`。λ 是每头可学习标量。
- **问题**：softmax 的"噪声底"——每个无关 token 都拿到一点正权重，长上下文下累计成可观的质量，稀释真正相关的 token。讲义列举的表现：长上下文 RAG 的引用幻觉、lost-in-the-middle、32k 以后 needle-in-haystack 精度下降。
- **为什么对长上下文更有价值**：噪声总量随 N 增长而不消失，N 越大信号占比越低；差分抵消共模噪声，使注意力更"尖"。讲义称原论文中 DIFF Transformer 在同尺寸下困惑度更低、长上下文更准、幻觉更少。
- 加分点：说出它与降噪耳机/差分放大器的共模抑制原理相同。

### Q14 — 参考回答要点

- **噪声底**：`w_i = exp(s_i)/Σexp(s_j)`。对无关 key，`s_i = q·k_i/√d` 围绕 0 波动（讲义：方差约 `‖q‖²/d`），`exp(s_i) > 0`，所以 `w_i ≈ O(1/N)`；`N − 1` 个无关 token 合计 `O(1)`。softmax 无法输出 hard top-k。
- **为何相减能抵消**：设 `A₁ = 信号₁ + 噪声₁`、`A₂ = 信号₂ + 噪声₂`。若两路噪声相关（尤其是共有的均匀底），`噪声₁ − λ·噪声₂` 接近 0；信号只出现在 A₁（或在 A₂ 中幅度小），相减后保留。关键在"噪声相关、信号不相关"——代码玩具中两路噪声独立，只能抵消均值（见 Q10）。
- **负权重**：差分后权重可为负，行和为 `1 − λ`。讲义："the output weights can be negative. That is fine — the value cache still handles signed contributions. The subsequent V projection absorbs the sign." 但输出幅度随 λ 变化，需要归一化（V1 用每头 RMSNorm）或初始化策略（V2）来保持稳定。
- 加分点：λ 用 `exp(λq1·λk1) − exp(λq2·λk2) + λ_init` 参数化，便于学习并允许为负；据原论文，`λ_init` 还按层深设置不同初值（讲义简化为默认约 0.8）。

### Q15 — 参考回答要点

- **V1 的三个问题**（讲义）：
  1. 为保持参数量，把 head dim 减半，每个头表达力下降；value cache 每步要按两个分支各读一次，decode 比基线慢；
  2. 需要自定义 CUDA kernel，与 FlashAttention 不兼容；
  3. 每头 RMSNorm 在 70B 级长时间预训练中引发后期不稳定。
- **V2 的对应修复**：
  1. Q 头数翻倍、KV 头数与 head dim 不变，参数从 MLP up-projection 借；相减后再投影回基线大小的 O_W；
  2. 每个分支都是标准的 softmax attention，可以直接调用 FlashAttention；
  3. 去掉每头 RMSNorm，用更简单的初始化方案保持稳定。
- **为何 decode 速度持平**：decode 是 memory-bound，耗时主要在从 HBM 读 KV cache。V2 的 KV 头数不变，每步读取的 KV 字节数与基线相同；多出的 Q 头只是在读进来的 KV 上多做一倍计算，提高了算术强度（讲义："more compute per byte loaded from HBM"），在带宽瓶颈下几乎"免费"。
- 加分点：与 GQA 兼容的原因相同——V2 增加的是 Q 头，不是 KV 头。

### Q16 — 参考回答要点

- **先诊断**：用 needle-in-haystack（按插入位置分桶）、lost-in-the-middle 曲线、引用正确率/引用幻觉率量化问题；确认失败确实与上下文长度相关，而不是检索质量或 prompt 问题。
- **成本评估**：差分注意力是架构改动，讲义："Add differential attention from the start; retraining later is expensive"；对已稳定服务的预训练模型"retraining cost rarely pays back"。
- **可选路径**：
  - 若正在规划新的长上下文预训练（64k+）：从一开始采用 DIFF V2（FlashAttention 兼容、decode 不变慢）；
  - 若只能微调：讲义提到"A LoRA on the Q projections can approximate the DIFF structure"，可小规模试验；
  - 并行推进低成本手段：重排检索结果、把关键文档放在首尾、压缩上下文、要求逐句引用并校验。
- **验收标准**：长上下文评测提升显著、短上下文能力无回退、decode 延迟与吞吐不变、训练稳定性。
- 常见误区：在 <16k 的场景引入（讲义："Noise floor is negligible"）。

### Q17 — 参考回答要点

- **稀疏注意力**：只对少数 token 计算注意力（top-k、块选择、滑动窗口），从结构上让无关 token 权重为 0，例如下一节的 NSA；代价是选择机制的设计与训练。
- **滑动窗口 / 局部 + 全局混合**：限制每个 token 的可见范围，噪声底随窗口而非全文增长（Gemma 2、混合架构）。讲义也提到"Hybrid architectures that combine DIFF attention with sliding-window attention on alternate layers"。
- **调整 softmax 温度/缩放**：随上下文长度放大 logits，使分布更尖（属于研究中的一类做法）。
- **检索与上下文工程**：减少放进上下文的无关内容，从源头降低 N。
- **关系**：差分注意力保留"全连接 + softmax"，通过相减抵消共模噪声；稀疏/窗口方法直接把无关项置零。两类方法可以叠加（讲义的兼容性表）。
- 加分点：指出所有方法都要在长上下文专项评测上验证，并关注短上下文能力是否回退。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 02 Self-Attention 从头开始](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：softmax 注意力本身。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：头数、head dim 与 O 投影。
- [阶段 07 · 15 Attention 变体 — 滑动窗口、稀疏、差分](../../../07-transformers-deep-dive/15-attention-variants/docs/zh.md)：差分注意力在变体谱系中的位置。
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：GQA、参数量与 KV cache 的计算方法。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：FlashAttention 与 decode 的带宽瓶颈。

### 本节被哪些后续内容用到
- [阶段 10 · 17 原生稀疏 Attention（DeepSeek NSA）](../../17-native-sparse-attention/docs/zh.md)：另一条解决长上下文注意力问题的路线。
- [阶段 10 · 21 Jamba——混合 SSM-Transformer](../../21-jamba-hybrid-ssm-transformer/docs/zh.md)：混合架构中的注意力层设计。
- [阶段 11 · 07 Advanced RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：长上下文 RAG 的引用与检索质量。
- [阶段 11 · 05 Context Engineering](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：在不改架构时降低上下文噪声。

### 延伸关键词
`Differential Transformer` · `DIFF V2` · `noise floor` · `common-mode rejection` · `lambda reparameterization` · `per-head RMSNorm` · `FlashAttention compatibility` · `arithmetic intensity` · `lost in the middle` · `needle in a haystack` · `GQA` · `sliding-window attention`
