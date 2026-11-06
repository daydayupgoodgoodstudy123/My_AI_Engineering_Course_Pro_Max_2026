# 测验 · 规模定律（Scaling Laws）

> **阶段 07 · Transformers 深入 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两个旋钮 N 与 D | 固定训练算力 C 时，只能在"参数量 N"和"训练 token 数 D"之间分配；标准 Transformer 有 `C ≈ 6·N·D` |
| 2 | Hoffmann（Chinchilla）损失公式 | `L(N, D) = A/N^α + B/D^β + E`：参数项、数据项、不可约项三部分相加；本节常数 `A≈406.4, B≈410.7, α≈0.34, β≈0.28, E≈1.69` |
| 3 | Kaplan vs Chinchilla | Kaplan（2020）主张"猛加 N"，GPT-3 只有约 1.7 token/参数；Hoffmann（2022）发现应让 N、D 同步增长，计算最优约 **20 token/参数**，GPT-3 欠训练约 10 倍 |
| 4 | 计算最优解的形状 | 代入 `D = C/(6N)` 求导得 `N_opt ∝ C^(β/(α+β))`、`D_opt ∝ C^(α/(α+β))`；用本节常数时 α ≠ β，所以最优 D/N 会随 C 缓慢增大（≈ `C^0.097`） |
| 5 | 不可约损失 E | 数据本身的熵，无论多大模型、多少数据都压不下去的下限 |
| 6 | 过度训练（over-training） | 训练费用只付一次，推理费用按 N 永远在付；高推理量场景应"训更小、训更久"，如 Llama 3 8B 用 15T token（≈1875 token/参数） |
| 7 | 涌现 vs 平滑 | Schaeffer et al.（2023）：所谓"涌现"多是 exact match 等不连续指标造成的假象，连续指标（cross-entropy）是平滑的；做预算要看连续 loss |
| 8 | 有效算力（effective compute） | 更好的数据、Muon 优化器、MoE 等相当于给算力乘一个倍数——改变常数，不改变曲线形状 |

### 核心技能（能动手做到）

- [ ] 从零实现 `chinchilla_loss`，并用 log 网格搜索在 `6ND = C` 约束下求出 `(N*, D*)`
- [ ] 推导闭式最优解 `N_opt = G·(C/6)^(β/(α+β))`，并验证它与网格搜索结果的差距在一个网格步长以内
- [ ] 给定算力 C，用"20 token/参数"经验法则心算 `N ≈ √(C/120)`、`D ≈ 20N`
- [ ] 把任一模型的预测 loss 拆成参数项 `A/N^α` 和数据项 `B/D^β`，判断它是"参数瓶颈"还是"数据瓶颈"
- [ ] 量化一次过度训练的代价：loss 上升多少、推理 FLOPs 省多少倍
- [ ] 能根据推理流量、部署硬件，说清楚为什么选 Chinchilla-optimal 或 over-trained 方案

---

## 二、基础自测（选择题）

**Q1.** 训练算力近似公式 `C ≈ 6·N·D` 中的系数 6 主要来自：

- A. Transformer 默认有 6 层
- B. 每个参数每个 token：前向约 2 FLOPs（一次乘、一次加），反向约 4 FLOPs
- C. Adam 优化器为每个参数维护 6 个状态
- D. 经验拟合出来的常数，没有物理含义

**Q2.** 你有 `C = 1.2×10²³` FLOPs，按"20 token/参数"的 Chinchilla 经验法则，最接近的 `(N, D)` 是：

- A. N ≈ 3.2B，D ≈ 63B
- B. N ≈ 31.6B，D ≈ 632B
- C. N ≈ 100B，D ≈ 200B
- D. N ≈ 316B，D ≈ 63B

**Q3.** Kaplan（2020）与 Hoffmann（2022）两篇 scaling law 论文的核心分歧是：

- A. loss 是否随规模呈幂律下降
- B. 固定算力下 N 与 D 如何分配：前者偏向优先放大 N，后者发现 N、D 应大致同比增长
- C. 是否存在不可约损失
- D. 结论是否适用于 Transformer 架构

**Q4.** Llama 3 8B 用 15T token 训练，远超 Chinchilla 最优比例。最主要的理由是：

- A. Chinchilla 定律对 10B 以下的模型完全不适用
- B. 推理成本与 N 成正比、而且要一直付；对高流量部署，多花一次性训练算力换一个更小的模型更划算
- C. 数据足够多时 loss 会降到 E 以下
- D. 训练 token 越多，训练 FLOPs 反而越少

**Q5.** 关于"涌现能力"，Schaeffer et al.（2023）的主要观点是：

- A. 涌现是模型规模越过临界点后的真实相变，无法提前预测
- B. 涌现多是 exact match、阈值准确率等不连续评分造成的假象；换成 cross-entropy 等连续指标，改进是平滑的
- C. 涌现只在 MoE 模型中出现
- D. 涌现说明 scaling law 已经失效

**Q6.** 公式 `L(N, D) = A/N^α + B/D^β + E` 中的 `E` 代表：

- A. 优化器带来的随机噪声
- B. 数据本身的熵，即无论模型多大、数据多少都无法消除的下限
- C. 位置编码引入的误差
- D. embedding 层参数对 loss 的贡献

**Q7.** 讲义提到 Muon 优化器带来约 2 倍"有效算力"。这类改进对 scaling law 的影响通常是：

- A. 改变幂律指数，使曲线变得更陡
- B. 改变公式中的常数（相当于给算力乘了个倍数），不改变曲线形状和渐近线
- C. 把不可约损失 E 降到 0
- D. 让 `C ≈ 6ND` 不再成立

**Q8.** 用本节代码的常数（α=0.34，β=0.28），计算最优的 D/N 随算力 C 如何变化？

- A. 恒等于 20
- B. 约正比于 `C^((α−β)/(α+β)) ≈ C^0.097`，随 C 缓慢增大
- C. 正比于 `C^0.5`
- D. 随 C 增大而减小

---

## 三、动手 / 代码题

**Q9.** 运行 `code/main.py` 的第一张表，D/N 一列是：

```text
27.1  29.4  38.3  50.0  65.3  85.2  92.4  120.5     (对应 C = 1e18 … 1e25)
```

请回答：(a) 为什么不是讲义标题里的 20？(b) 为什么数字跳得不均匀（85.2 → 92.4 → 120.5）？可以对照下面这段源码：

```python
def compute_optimal(C_flops, n_grid=200):
    """Find (N, D) minimizing loss subject to 6ND = C by grid search over log N."""
    # 6ND = C => D = C / (6N)
    log_N_min = math.log10(1e5)
    log_N_max = math.log10(1e13)
    best = (None, None, float("inf"))
    for i in range(n_grid):
        log_N = log_N_min + (log_N_max - log_N_min) * i / (n_grid - 1)
        N = 10 ** log_N
        D = C_flops / (6 * N)
        if D < 1e6:
            continue
        loss = chinchilla_loss(N, D)
        if loss < best[2]:
            best = (N, D, loss)
    return best
```

**Q10.** 网格搜索只是数值近似。请推导并实现闭式解 `compute_optimal_closed(C)`，返回 `(N, D, loss)`，并与 `compute_optimal` 在 `C = 1e20, 1e22, 1e24` 上对比。

**Q11.** 代码的过度训练实验是这样写的：

```python
    C = 1e24
    N_opt, D_opt, L_opt = compute_optimal(C)
    N_under = N_opt / 10
    D_over = D_opt * 10
    L_over = chinchilla_loss(N_under, D_over)
```

(a) 这个小模型用的训练算力比最优方案多还是少？(b) 如果坚持用 `N_under` 这个小模型，想把 loss 训到和 `L_opt` 一样低，需要多少 token、多少倍算力？写一个函数 `tokens_to_match(N, target_loss)` 算出来，并解释结果。

**Q12.** 写几行代码，把 GPT-3 175B（300B token）、Chinchilla 70B（1.4T token）、Llama 3 8B（15T token）的预测 loss 拆成参数项 `A/N^α` 和数据项 `B/D^β`，判断每个模型主要卡在哪一项。

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 Chinchilla scaling law。"20 token/参数"是怎么来的？它和 Kaplan 2020 的结论有什么不同，GPT-3 为什么被称为"欠训练"？

**Q14.**（场景设计）你有约 `1e23` FLOPs 的预训练预算，模型上线后预计每月服务上万亿 token 的推理流量，需要能在单张消费级 / 中端 GPU 上部署。你会怎么定 N 和 D？要算哪些账？

**Q15.**（原理深挖）"大模型的能力会在某个规模突然涌现"——你怎么看？如果要提前预测一个更大模型的能力，应该怎么做？

**Q16.**（工程实践）你要在正式训练前用一批小模型拟合自己的 scaling law 再外推。实验怎么设计？哪些地方最容易翻车？

**Q17.**（追问型）高质量文本数据快用完了，scaling law 还有用吗？MoE 模型（例如 DeepSeek-V3 总参数很大、激活 37B）该怎么套用这条定律？

---

## 五、参考答案与解析

### Q1 — 答案：B

一次矩阵乘法里每个权重对每个 token 做一次乘法和一次加法，前向约 `2N` FLOPs/token；反向要分别对激活和权重求梯度，约为前向的 2 倍，即 `4N`。合计 `6N` FLOPs/token，乘以 token 数得 `6ND`。它忽略了 attention 中与序列长度相关的项，对大模型、普通上下文长度是很好的近似。A、C 是望文生义；D 错在这个 6 有清晰的计数来源。

### Q2 — 答案：B

`D = 20N` 代入 `C = 6ND` 得 `C = 120N²`，`N = √(C/120) = √(10²¹) ≈ 3.16×10¹⁰ = 31.6B`，`D = 20N ≈ 632B`。验算：`6 × 31.6e9 × 632e9 ≈ 1.2e23` ✔。A 的 N、D 各小 10 倍，算力小了 100 倍；C、D 的乘积对不上或比例严重失衡。

### Q3 — 答案：B

两篇论文都认为 loss 随规模呈幂律下降（A 错），Hoffmann 的公式里明确有不可约项 E（C 错），两者都是在 Transformer 上做的实验（D 错）。真正的分歧在**分配**：Kaplan 的结论导致业界"堆参数"，GPT-3 只有约 1.7 token/参数；Hoffmann 发现 N、D 应同步扩大，约 20 token/参数，于是 70B 的 Chinchilla 在更少参数下胜过了 175B 的 GPT-3，推理便宜约 2.5 倍。

### Q4 — 答案：B

Chinchilla-optimal 只优化"每个训练 FLOP 换来的 loss"，没算推理。推理每个 token 的 FLOPs 约 `2N`，一个高流量模型一生的推理 token 数可能远超训练 token 数，所以把 N 压小、用更多 token 补质量，总成本更低，还更容易部署。A 说反了（定律仍适用，只是优化目标变了）；C 错，E 是下限；D 错，固定 N 时 D 越多训练 FLOPs 越多。

### Q5 — 答案：B

如果评分是"整串答对才算 1 分"，底层每个 token 的正确概率平滑上升，乘起来的整体正确率就会在某个规模附近看似陡升。换成逐 token 的 cross-entropy 或编辑距离等连续指标，曲线是平滑的。讲义给出的结论：用连续 loss 做预测是可靠的，基准分数的跳变常是评分器造成的。

### Q6 — 答案：B

当 N → ∞、D → ∞ 时，前两项都趋于 0，loss 收敛到 E（≈1.69）。它对应自然语言本身的不确定性——同样的上文，下一个词本来就可能有多种合理写法。

### Q7 — 答案：B

讲义原话："Changes the absolute constant in the scaling law, not its shape." 更好的数据、优化器、MoE 都是"让一个 FLOP 走得更远"，相当于把 C 换成 `k·C`；曲线整体平移，幂律指数和渐近线 E 不变。

### Q8 — 答案：B

由 `N_opt ∝ C^(β/(α+β)) = C^0.452`、`D_opt ∝ C^(α/(α+β)) = C^0.548`，得 `D/N ∝ C^((α−β)/(α+β)) = C^0.097`，C 每增大 10 倍，D/N 约乘 1.25。只有 α = β 时 D/N 才是常数。代码的输出和闭式解（Q10）都印证了这一点。

### Q9 — 参考答案

**(a)** 20 是 Hoffmann 论文的"标题结论"，而代码用的是论文里参数化拟合给出的常数（α=0.34 ≠ β=0.28）。按 Q8，用这组常数算出的最优 D/N 会随 C 增大，在 1e22～1e23 区间已经是 60～80，而不是 20。代码自己的打印也承认"extrapolation drifts"。结论：**20 是经验法则，不是这组常数的精确推论**，具体数字取决于你拟合出的常数。

**(b)** 网格在 log₁₀N 上从 5 到 13 均匀取 200 个点，相邻两点之间 N 相差 `10^(8/199) ≈ 1.097` 倍，约 9.7%。真正的最优点落在两个格点之间，取到的 N* 会有最多约 ±5% 的误差，D* = C/(6N*) 随之反向变化，D/N 的误差就被放大到约 ±10%，所以序列不平滑。把 `n_grid` 改成 20000，D/N 变成 25.7、40.1、62.6、78.2、97.7、122.1，平滑递增。

另外注意：loss 那一列在 200 点网格下已经精确到小数点后 3～4 位，说明**最优点附近 loss 曲面非常平**，N 偏 10% 几乎不影响 loss。这也是工程上可以为了推理成本大幅偏离最优点的原因。

### Q10 — 参考答案

推导：把 `D = C/(6N)` 代入，`L(N) = A·N^(−α) + B·(C/6)^(−β)·N^β + E`，令 `dL/dN = 0`：

`α·A·N^(−α) = β·B·(C/6)^(−β)·N^β` ⇒ `N_opt = G·(C/6)^(β/(α+β))`，其中 `G = (αA / βB)^(1/(α+β))`。

```python
from main import chinchilla_loss, compute_optimal, pretty, A, B_CONST, ALPHA, BETA

def compute_optimal_closed(C, A=A, B=B_CONST, alpha=ALPHA, beta=BETA):
    G = (alpha * A / (beta * B)) ** (1 / (alpha + beta))
    N = G * (C / 6) ** (beta / (alpha + beta))
    D = C / (6 * N)
    return N, D, chinchilla_loss(N, D)

for C in [1e20, 1e22, 1e24]:
    Nc, Dc, Lc = compute_optimal_closed(C)
    Ng, Dg, Lg = compute_optimal(C)
    print(f"{C:.0e}  closed N={pretty(Nc)} D/N={Dc/Nc:5.1f} L={Lc:.4f} | grid N={pretty(Ng)} D/N={Dg/Ng:5.1f} L={Lg:.4f}")
```

实际输出：

```text
1e+20  closed N=644.9M D/N= 40.1 L=2.5998 | grid N=659.3M D/N= 38.3 L=2.5999
1e+22  closed N=5.2B D/N= 62.6 L=2.1386 | grid N=5.1B D/N= 65.3 L=2.1386
1e+24  closed N=41.3B D/N= 97.7 L=1.9112 | grid N=42.5B D/N= 92.4 L=1.9112
```

N 的差距都在一个网格步长（约 9.7%）以内，loss 几乎一致。闭式解是 O(1) 的，网格是 O(n_grid)；但网格搜索的好处是**换任何 loss 公式都能直接用**（例如加上推理成本项），闭式解要重新推导。

### Q11 — 参考答案

**(a)** 一样多。`6 × (N/10) × (10D) = 6ND = C`，这是**等算力**比较：同样 1e24 FLOPs，小 10 倍的模型 loss 从 1.911 升到 1.971（+0.059），换来推理便宜 10 倍。

**(b)**

```python
from main import compute_optimal, pretty, A, B_CONST, ALPHA, BETA, E_CONST

def tokens_to_match(N, target_loss):
    gap = target_loss - E_CONST - A / N ** ALPHA   # 留给数据项的余量
    if gap <= 0:
        return float("inf")                        # 小模型的下限都高于目标，不可能达到
    return (B_CONST / gap) ** (1 / BETA)

C = 1e24
N_opt, D_opt, L_opt = compute_optimal(C)
N_small = N_opt / 10
D_need = tokens_to_match(N_small, L_opt)
print(f"floor of small model: {E_CONST + A / N_small ** ALPHA:.4f}")
print(f"tokens needed: {pretty(D_need)}  compute: {6 * N_small * D_need:.2e}  = {6 * N_small * D_need / C:.0f}x budget")
```

输出：

```text
floor of small model: 1.9065
tokens needed: 431436.5T  compute: 1.10e+28  = 10995x budget
```

解释：4.25B 模型的参数项 `A/N^α ≈ 0.216`，所以它的"无限数据下限"是 `E + 0.216 ≈ 1.9065`，只比目标 1.9112 低 0.005。留给数据项的余量极小，而 `B/D^β` 衰减很慢（β 只有 0.28），于是需要约 43 万 T token、1.1 万倍算力——实际上不可能。**结论：过度训练能换来"接近"，换不来"相同"；模型太小会撞上自己的参数下限。** 这也是讲义所说"超过 1000 倍 Chinchilla 之后收益变成噪声"的直观来源。

### Q12 — 参考答案

```python
from main import A, B_CONST, ALPHA, BETA

for name, N, D in [("GPT-3 175B", 175e9, 300e9),
                   ("Chinchilla 70B", 70e9, 1400e9),
                   ("Llama 3 8B", 8e9, 15_000e9)]:
    p, d = A / N ** ALPHA, B_CONST / D ** BETA
    print(f"{name:<15} param={p:.3f} data={d:.3f} -> {'data-bound' if d > p else 'param-bound'}")
```

输出：

```text
GPT-3 175B      param=0.061 data=0.251 -> data-bound
Chinchilla 70B  param=0.083 data=0.163 -> data-bound
Llama 3 8B      param=0.175 data=0.084 -> param-bound
```

GPT-3 的数据项是参数项的 4 倍，说明再加参数几乎没用，该加数据——这就是"欠训练"的量化含义。Llama 3 8B 反过来：数据已经喂得很足，瓶颈在参数量。注意：计算最优点并不是"两项相等"，而是两项对 N 的**边际收益**相等（`α·参数项 = β·数据项`），所以 Chinchilla 的数据项仍大于参数项。

### Q13 — 参考回答要点

- **定义**：Hoffmann et al.（2022）拟合了 `L(N, D) = A/N^α + B/D^β + E`，在 `C ≈ 6ND` 约束下求最小 loss，发现计算最优时 N、D 大致同比增长，比例约 20 token/参数。
- **来历**：论文用 400 多个不同规模、不同 token 数的模型做实验（固定算力扫 N 的 IsoFLOP 曲线，加上参数化拟合），三种方法给出的结论相近；"20"是对这些结果的经验总结。
- **与 Kaplan 的不同**：Kaplan 认为算力增加时应把大部分投入参数；按 Hoffmann 的结论，GPT-3（175B / 300B token，约 1.7 token/参数）欠训练约 10 倍。Chinchilla（70B / 1.4T）以 2.5 倍更小的体量胜过 GPT-3。
- **取舍**：Chinchilla-optimal 只最小化**训练**成本下的 loss；考虑推理后最优点会往"小模型、多数据"移动。
- **加分点**：指出用论文参数化拟合的常数直接算，最优 D/N 会随 C 漂移（本节代码就能看到 25～120），因此"20"是经验法则；Kaplan 的偏差一个常被提到的原因是学习率余弦调度长度没有随训练 token 数调整，导致小数据量的实验点被低估。
- **常见误区**：把"20 token/参数"当成任何规模、任何数据都成立的常数；把 N 理解成包含 embedding 的总参数量（讲义定义 N 为非 embedding 参数）。

### Q14 — 参考回答要点

- **先算 Chinchilla 基线**：`N = √(1e23/120) ≈ 29B`，`D ≈ 580B`。记下基线 loss。
- **再算推理账**：推理每 token 约 `2N` FLOPs。每月 1e12 token，29B 模型每月推理约 `5.8e22` FLOPs，不到两个月推理算力就超过整个训练预算。模型越小，这笔持续开销越小。
- **部署约束**：单卡消费级 GPU 决定了 N 的上限（如 7B～8B 量级，配合量化）。在约束内选 N，用剩余算力换 D：`D = C/(6N)`，8B 时约 2T token，D/N ≈ 260，落在讲义所说"推理主导时 100–500 token/参数"的区间。
- **量化代价**：用 `chinchilla_loss` 比较两种方案的 loss 差（本节代码中 1e24 下缩小 10 倍只差约 0.06），再评估这个差距在下游任务上能否接受。
- **风险检查**：2T 高质量 token 是否拿得到（数据墙）；先用约 1% 预算做缩小版验证；确定 held-out 评测集再定目标 loss。
- **加分点**：提到真实决策要同时考虑 KV cache 显存、延迟 SLO、量化后精度损失，以及 MoE 作为"总参数大、激活参数小"的折中。

### Q15 — 参考回答要点

- **现象**：很多基准上，小模型准确率接近随机，过了某个规模后突然上升，被称为"涌现"。
- **主流解释**：Schaeffer et al.（2023）指出这多半是评分方式的产物。exact match、多选题阈值准确率是不连续的；底层每个 token 的对数概率是平滑改进的，多步任务的整体正确率是若干步正确率的乘积，在对数坐标下看就像突然跳起。用 cross-entropy、token 级编辑距离等连续指标，曲线平滑。
- **预测方法**：①在一系列小模型上拟合连续 loss（或目标任务的连续代理指标）随算力的幂律；②外推到目标规模；③再把 loss 映射到任务指标。讲义的结论：用连续 loss 做预算是可靠的。
- **加分点**：区分"指标不连续"与"能力不存在"——即使曲线平滑，跨过可用阈值对产品来说仍可能是质变；评测时尽量报告连续指标和多个随机种子。
- **常见误区**：看到某个基准跳变就宣称"涌现"，或据此认为 scaling law 不可预测。

### Q16 — 参考回答要点

- **实验设计**：选 5 个以上跨 1～2 个数量级的模型规模（讲义练习用 100K～10M 参数），同一份数据、同一 tokenizer、同一架构超参比例；每个规模扫几个 token 数（IsoFLOP 曲线），记录收敛后的验证 loss。
- **拟合**：对 `L = A/N^α + B/D^β + E` 做非线性最小二乘（在 log 空间拟合更稳），得到 α、β、E，再求最优 D/N 曲线；与已发表指数对比。
- **常见翻车点**：
  - 学习率调度没有按每次运行的 token 数设定（余弦周期过长会让短训练的点看起来更差，从而系统性偏向大模型）；
  - 小模型区间离目标规模太远，外推几个数量级时误差放大（本节代码打印的 "extrapolation drifts" 就是这个意思）；
  - 小模型数据重复多轮，与大模型的"一轮数据"不可比；
  - N 的定义混乱（是否计 embedding），小模型里 embedding 占比很高；
  - 只用单一随机种子，噪声被当成趋势。
- **加分点**：正式开训前先做约 1% 预算的放大验证（讲义 skill 文件里也要求这一步）。

### Q17 — 参考回答要点

- **数据墙**：讲义估计过滤后的高质量英文 web 文本约 5–10T token，前沿预训练已接近上限，进入"数据受限"区间。此时 Chinchilla 公式（假设数据不重复、无限供应）不再直接适用。下一步的杠杆：合成数据、多语言、多模态 token、用 SFT/RLHF 做规模化后训练。
- **有效算力仍然有用**：数据质量筛选（Phi 风格，讲义称可带来 >2 倍有效算力）、Muon 优化器、MoE 等，都是在改变常数，让同样的 FLOPs 换到更低 loss。
- **MoE 怎么套**：训练和推理的 FLOPs 由**激活参数**决定，讲义建议按 per-active-FLOP 来看 scaling law；本节代码把 DeepSeek-V3 按 37B 激活参数代入就是这个思路。但总参数决定了容量和显存，只用激活参数会低估 MoE 的"知识容量"，需要单独的 MoE scaling 曲线。
- **RL 的 scaling law**：讲义称仍是开放问题，早期证据显示也呈幂律，但指数与预训练很不一样。
- **常见误区**：把稠密模型的 20 token/参数直接套到 MoE 的总参数上，或认为数据墙意味着 scaling 已经结束。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：理解参数主要在哪些矩阵里，才能理解 `6ND`。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：scaling law 讨论的 loss 就是 next-token 的 cross-entropy。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵与交叉熵，理解不可约损失 E。
- [阶段 03 · 06 优化器](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：AdamW 等优化器，理解"优化器改变有效算力"。

### 本节被哪些后续内容用到
- [阶段 07 · 11 专家混合 (MoE)](../../11-mixture-of-experts/docs/zh.md)：总参数与激活参数分离，scaling law 按激活 FLOPs 计。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：推理成本的具体构成，是"过度训练"决策的另一半账。
- [阶段 10 · 03 数据管线](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：数据质量与去重，直接影响有效算力。
- [阶段 10 · 04 预训练 mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：亲手训练小模型，可用来做讲义的"拟合自己的 scaling law"练习。
- [阶段 10 · 05 规模化与分布式](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：把算出来的 FLOPs 预算落到 GPU 数和训练时长。
- [阶段 10 · 20 DeepSeek-V3 详解](../../../10-llms-from-scratch/20-deepseek-v3-walkthrough/docs/zh.md)：本节代码里 "DeepSeek-V3 (active)" 那一行的真实架构。
- [阶段 17 · 02 推理平台经济学](../../../17-infrastructure-and-production/02-inference-platform-economics/docs/zh.md)：推理成本如何反过来决定训练时的 N。
- [阶段 05 · 27 LLM 评测框架](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：连续指标 vs 不连续指标，与"涌现"讨论直接相关。

### 延伸关键词
`Kaplan scaling laws` · `Chinchilla / IsoFLOP` · `compute-optimal` · `inference-aware scaling（Sardana & Frankle 2024）` · `effective compute` · `data-constrained scaling` · `MoE scaling` · `Muon optimizer` · `emergent abilities mirage`
