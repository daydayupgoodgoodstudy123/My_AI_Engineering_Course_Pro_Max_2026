# 测验 · 原生稀疏 Attention（DeepSeek NSA）（Native Sparse Attention (DeepSeek NSA)）

> **阶段 10 · 从零构建 LLM · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 长上下文的瓶颈 | 全注意力每层 `O(N²)` 计算、`O(N)` KV cache；讲义引 NSA 论文估计，64k 时注意力占 decode 延迟的 70–80% |
| 2 | 两类旧方案的缺陷 | 固定模式稀疏（滑动窗口、strided、block-local）丢信息、长程召回差；推理期稀疏（H2O、StreamingLLM 等 KV 剪枝）作用在稠密训练的模型上，收益有限 |
| 3 | 三个并行分支 | **压缩分支**：每 `l` 个 token 压成一个摘要 token，看全局粗粒度；**选择分支**：按压缩分支分数取 top-k 块，读原始 token 做细粒度注意力；**滑动窗口分支**：最近 `W` 个 token 的局部注意力 |
| 4 | 门控融合 | `out = g_cmp·out_cmp + g_sel·out_sel + g_win·out_win`，门控来自 query 上的小 MLP，三者不必和为 1 |
| 5 | 原生可训练 | 选择直接复用压缩分支的注意力分数，不需要单独训练路由器；压缩分支本身是可微的全局注意力，选中块上的注意力也可微；top-k 只决定"加载哪些块" |
| 6 | 硬件对齐 | kernel 以 GQA 组为外循环、稀疏 KV 块为内循环，同组 query 头共享选中的块，KV 读取被摊薄，算术强度保持高 |
| 7 | 每 query 的 key 数 | `N/l + k·b + W`；N = 64k、l = 64、k = 16、b = 64、W = 512 时约 2,560 个 key，约为全注意力的 1/25 |
| 8 | 收益随长度增长但有上限 | 节省倍数 `N / (N/l + k·b + W)` 随 N 增大而增大，但当 N → ∞ 时趋于 `l`（压缩分支本身仍是 `O(N/l)`） |
| 9 | 适用边界 | 适合 64k+ 的预训练/继续训练、以及 NSA 原生权重的推理；不能直接改造已稠密训练的模型；16k 以下三分支开销抵消收益 |
| 10 | 同期与后继 | MoBA（Moonshot）把 MoE 的思想用到注意力块上；讲义称 DeepSeek 后续有 DSA（DeepSeek Sparse Attention） |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现压缩（mean-pool）、top-k 块选择、滑动窗口、门控融合四个部件，说清每一步的输入输出形状
- [ ] 给定 `(N, l, k, W)` 计算每 query 的 key 数和相对全注意力的节省倍数，并推出节省倍数的上限
- [ ] 指出 `main.py` 在 key 计数上的两处不精确（选中块与滑动窗口重叠被重复计数、`N // l` 与实际块数不一致）
- [ ] 用"单个 needle"实验说明 mean-pool 压缩会稀释信号，从而理解为什么 NSA 用可学习的压缩 MLP
- [ ] 解释 NSA 节省的是"每步加载与计算的 KV"，而不是 KV cache 的存储容量
- [ ] 讲清 NSA 与推理期 KV 剪枝、MoBA、差分注意力、MLA 分别在优化什么

---

## 二、基础自测（选择题）

**Q1.** NSA 对每个 query 并行运行的三个注意力分支是：

- A. 局部窗口、全局 token、随机 token（类似 BigBird）
- B. 压缩分支（块摘要 token）、选择分支（top-k 块的原始 token）、滑动窗口分支（最近 W 个 token）
- C. 两张 softmax 图相减再加一个滑动窗口
- D. 按 head 分成三组，每组用不同的 RoPE 频率

**Q2.** 按 `main.py` 中 `count_nsa` 的公式，N = 65,536、l = 64、k = 16、W = 512 时，每个 query 需要看的 key 数为：

- A. 1,024
- B. 2,048
- C. 2,560
- D. 65,536

**Q3.** 关于 NSA "原生可训练（natively trainable）"，下列说法最准确的是：

- A. 稀疏模式在预训练阶段就启用；选择直接复用压缩分支的注意力分数，压缩分支和选中块上的注意力都可微，top-k 本身不可微，但只决定加载哪些块，因此无需单独的路由器或连续松弛
- B. NSA 用 Gumbel-softmax 把 top-k 变成可微操作
- C. NSA 先用稠密注意力训练完，再在推理时剪掉不重要的 KV
- D. NSA 为 top-k 选择单独训练了一个路由网络，并加了负载均衡损失

**Q4.** 固定 l = 64、k = 16、W = 512，让上下文长度 N 无限增大，NSA 相对全注意力的"每 query key 数节省倍数"会：

- A. 随 N 线性增长，没有上限
- B. 稳定在 25.6 倍
- C. 稳定在 36.6 倍
- D. 单调增大并趋于 l = 64 倍，因为压缩分支仍需看 `N/l` 个 key

**Q5.** `main.py` Step 1 打印 `total keys attended : 288`，选中的块是 `[3, 6, 17, 28]`，滑动窗口是最后 128 个 token（位置 896–1023）。关于 288 这个数字，正确的是：

- A. 完全准确，三个分支的 key 互不重叠
- B. 有重复计数：块 28（位置 896–927）同时在选择分支和滑动窗口中，32 个 key 被算了两次；去重后细粒度 key 为 224 个，加上 32 个压缩 key 共 256 个
- C. 少算了，应该是 288 + 32
- D. 应该只算压缩分支的 32 个

**Q6.** 关于 NSA 与 KV cache **存储容量**，正确的说法是：

- A. NSA 只缓存 top-k 块，KV cache 降为原来的 `k·l / N`
- B. NSA 只缓存压缩 token，KV cache 降为原来的 `1/l`
- C. NSA 只缓存滑动窗口内的 token
- D. NSA 仍需保存全部原始 KV（任何块都可能在之后被选中），另外还要保存压缩 token；它节省的是每步需要读取和计算的 KV，而不是存储容量

**Q7.** 根据讲义，下列哪种情况**不应**采用 NSA？

- A. 给一个已经用稠密注意力预训练好的模型直接换成 NSA 提供服务，不做继续训练
- B. 规划一次目标 64k+ 上下文的预训练
- C. 推理 DeepSeek 原生 NSA 权重的长上下文 checkpoint
- D. 一次有充足算力的长上下文继续训练

**Q8.** NSA 的 kernel 为什么要求"同一 GQA 组内的 query 头共享同一组选中的块"？

- A. 为了让每个头选到不同的块，增加多样性
- B. 为了减少门控 MLP 的参数
- C. 共享选择后，同组所有 query 头可以复用一次从 HBM 加载到 SRAM 的 KV 块，KV 读取被摊薄、算术强度保持在高位；kernel 以 GQA 组为外循环、稀疏 KV 块为内循环
- D. 因为 GQA 不支持每头不同的 mask

---

## 三、动手 / 代码题

**Q9.** `main.py` 的合成数据把信号**整块**放进 3 个块（每块 32 个 token 的 key 全部等于 pattern），因此 top-4 选择轻松命中全部信号块。现在改成"needle-in-a-haystack"：每次只有**一个** token 的 key 等于 pattern，位置随机（0–799），其余不变，l = 32、k = 4。

```python
  cw, _ = attention(pattern, compress_mean(K, l), compress_mean(K, l))
  hit = (pos // l) in top_k_blocks(cw, 4)
```

1. 预测并解释：mean-pool 压缩下，top-4 命中 needle 所在块的概率大约是多少？（随机猜的命中率是 4/32 = 12.5%）
2. 如果用"块内每个 key 与 query 的最大点积"作为块分数（一个理想化的 oracle），命中率是多少？
3. 这说明 NSA 为什么要用**可学习**的压缩 MLP，而不是均值？（讲义练习 2）

**Q10.** 阅读：

```python
def compress_mean(K, l):
    n_blocks = (n + l - 1) // l
    ...

def count_nsa(N: int, l: int, k: int, W: int) -> int:
    return (N // l) + (k * l) + W
```

1. 当 N = 1000、l = 32、k = 4、W = 128 时，`count_nsa` 与 `nsa_step` 实际的压缩 key 数分别是多少？
2. 写一个 `count_nsa_unique(N, l, picks, W)`，对给定的选中块列表去掉与滑动窗口重叠的部分，并用 Step 1 的数据验证结果。
3. 证明当 N → ∞ 时 `N / count_nsa(N, l, k, W) → l`，并用 N = 2¹⁸、2²⁰、2²⁴ 验证（l = 64、k = 16、W = 512）。

**Q11.** 讲义练习 4 的变体：一个 70B 级模型（80 层、8 个 KV 头、head_dim 128、BF16）使用 NSA（l = 64、k = 16、W = 512）。

1. 128k 上下文下，全注意力与 NSA 的 KV cache **存储**分别是多少？
2. 每生成一个 token，每层每个 KV 头需要**读取**的 key 数分别是多少？
3. 序列长度为多少时，NSA 每步需要读取的 key 数与全注意力相同？这和讲义"Context under 16k. The three-branch overhead dominates the savings"有什么关系？

**Q12.** 讲义写道："Gradients flow through the compressed-branch scores (which influence both the compressed output AND the selection logic)... The non-differentiable `top_k` operation is a no-op on the forward computational graph — it only controls which blocks get loaded from memory."

结合 `nsa_step` 的前向过程回答：

```python
    cmp_w, cmp_out = attention(q, K_cmp, V_cmp)
    picks = top_k_blocks(cmp_w, cfg.k)
    K_sel, V_sel = fine_grained_keys(K, V, cfg.l, picks)
    _, sel_out = attention(q, K_sel, V_sel)
    ...
    combined = [g[0] * cmp_out[i] + g[1] * sel_out[i] + g[2] * win_out[i] ...]
```

1. 若对 `combined` 的某个损失求梯度，压缩 key `K_cmp`（以及生成它的压缩 MLP）的梯度来自哪里？选择分支的损失能否通过 `picks` 传回压缩分支？
2. "top_k is a no-op on the forward computational graph"这句话准确吗？
3. 既然选择本身得不到梯度，为什么 NSA 仍能学到好的选择？

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 DeepSeek NSA 的结构：三个分支各自负责什么？为什么需要三个而不是一个？

**Q14.**（原理深挖）NSA 和 H2O、StreamingLLM 这类推理期 KV 剪枝方法有什么本质区别？为什么说"原生可训练"是它能拿到真实加速的关键？

**Q15.**（原理深挖）NSA 的计算复杂度是多少？为什么"理论 FLOPs 减少"不一定等于"实际变快"？NSA 在 kernel 层面做了什么设计？

**Q16.**（工程实践）你要为一个 128k 上下文的新模型预训练选择 NSA 的 `(l, k, W)`。你会怎么权衡？用什么评测来证明选择是对的？

**Q17.**（追问型）NSA、MoBA、差分注意力、MLA 都和"长上下文注意力"有关。它们分别在优化什么？能否组合使用？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义"Three parallel branches"：Compressed branch（块压缩成摘要 token，粗粒度全局视图）、Selected branch（用压缩分支分数选 top-k 块，读原始 token）、Sliding-window branch（最近 W 个 token，捕捉语法、局部指代等短程模式）。A 是 BigBird 式固定稀疏；C 混入了差分注意力；D 与 NSA 无关。

### Q2 — 答案：C

`65536 // 64 + 16 × 64 + 512 = 1024 + 1024 + 512 = 2,560`，全注意力 65,536，节省 25.6 倍，与代码 Step 2 输出一致。讲义正文用 N = 64,000 近似，得到 `1000 + 1024 + 512 = 2536`、约 25 倍。A 只算了压缩分支；B 是 `l = 64, k = 8` 或 `l = 128, k = 8` 的结果（Step 3 中两者恰好都是 2,048）；D 是全注意力。

### Q3 — 答案：A

讲义："the compressed-branch attention IS a differentiable coarse-grained attention on the whole sequence. The top-k operation just reuses the top attention scores from the compressed branch to pick which fine-grained blocks to load"，因此 NSA "can be used in pre-training end to end"。B 是另一类做法（连续松弛），讲义说这类方法"did not give real sparsity at inference"；C 是推理期稀疏；D 是 MoE 式路由，NSA 恰恰避免了单独的路由器。关于梯度如何流动的精确说法，见 Q12。

### Q4 — 答案：D

`N / (N/l + k·l + W)`：N 小时常数项 `k·l + W = 1536` 占主导，节省随 N 增长；N 很大时 `N/l` 占主导，比值趋于 `l`。实测：N = 2¹⁸ 时 46.5 倍，2²⁰ 时 58.5 倍，2²⁴ 时 63.6 倍，逼近 64。讲义"The benefit grows with sequence length, which is the whole point"是对的，但收益有上限；要突破这个上限需要更大的 l 或多级压缩。B、C 只是 64k、128k 两个点上的值。

### Q5 — 答案：B

滑动窗口覆盖位置 896–1023，即块 28、29、30、31；选择分支选中了块 28，所以位置 896–927 的 32 个 key 在两个分支中都被注意。`total_keys = len(K_cmp) + len(K_sel) + len(K_win)` 直接相加，没有去重（已用代码验证：重叠 32 个，去重后细粒度 key 224 个）。在"计算量"的意义上，两个分支确实各算了一遍，288 也可以理解为"注意力打分次数"；但若用来衡量"需要从显存读取的不同 KV"，应该去重。真实实现通常会避免选择分支与窗口重复读取同一块。

### Q6 — 答案：D

选择分支在每一步都可能挑中任何一个历史块，所以全部原始 KV 都必须保留；压缩 token 是额外的（l = 64 时多约 1/64）。NSA 减少的是"每生成一个 token 要从 HBM 读取并参与计算的 KV 数量"——decode 是带宽瓶颈，这正是它变快的原因。A、B、C 描述的分别是"只保留选中块""只保留压缩表示""只保留窗口"（StreamingLLM 式），都会永久丢失信息。若要降低存储容量，需要 GQA/MLA、KV 量化等手段（见 Q11、Q17）。

### Q7 — 答案：A

讲义"When not to"："Serving an existing dense-attention pre-trained model. You cannot retrofit NSA without continued training." 稠密训练的模型从未学会通过稀疏模式路由信息，直接替换会严重掉点。B、C、D 都在讲义"When to reach for NSA"中。

### Q8 — 答案：C

讲义："The kernel loads queries by GQA groups (outer loop), fetches the corresponding sparse KV blocks per group (inner loop), and runs attention on SRAM. Because each query group sees the same selected blocks (selection is per-query-group, not per-query-head), the KV loads are amortized across the group. Arithmetic intensity stays high." 若每个头选不同的块（A），同一组的 KV 要分别加载，稀疏带来的不规则访存会吃掉理论收益。B、D 与此无关。

### Q9 — 参考答案

1. 我们用 200 个随机种子实测：mean-pool 压缩下 top-4 命中率约 **32%**，只比随机猜（12.5%）好一些。原因：needle 所在块的均值 key 为 `pattern/32 + 噪声均值`，信号被稀释为 1/32，`q·k̄ ≈ 0.031`；而噪声块均值的点积标准差约 `0.3/√32 ≈ 0.053`，信号淹没在块间噪声里。（代码原始设置中信号占满整块，块均值就是 pattern 本身，所以轻松命中；压缩分支的权重也很平——信号块约 0.039，平均 1/32 ≈ 0.031。）
2. 用块内最大点积作为分数，200 次实测命中率 **100%**。但这需要读取全部原始 key，等于没有省计算，只能作为上限参考。
3. 压缩函数决定了"路由信号"的质量。均值会把少数关键 token 稀释掉；可学习的压缩 MLP 可以学到"保留块内最突出的特征"之类的摘要方式，而且它通过压缩分支的输出损失与整个模型联合训练，学到的正是"对后续注意力有用"的摘要。讲义练习 2 让你用 2 层 MLP 替换 mean-pool 并比较困惑度，就是在验证这一点。这也说明为什么"原生训练"重要：路由质量要靠端到端训练获得。

### Q10 — 参考答案

1. `count_nsa(1000, 32, 4, 128)` 中压缩项为 `1000 // 32 = 31`，总计 287；而 `compress_mean` 用向上取整，实际产生 `ceil(1000/32) = 32` 个压缩 key（最后一块只有 8 个 token）。两者不一致，N 不是 l 的整数倍时计数偏小 1。
2. 参考实现：

```python
def count_nsa_unique(N, l, picks, W):
    n_cmp = (N + l - 1) // l
    sel = set()
    for b in picks:
        sel.update(range(b * l, min((b + 1) * l, N)))
    win = set(range(max(0, N - W), N))
    return n_cmp + len(sel | win)

# Step 1: count_nsa_unique(1024, 32, [3, 6, 17, 28], 128) -> 32 + 224 = 256
```

   与代码打印的 288 相比少 32，正是块 28 的重叠。
3. `N / (N/l + c)`，其中 `c = k·l + W` 为常数；分子分母同除以 N 得 `1 / (1/l + c/N) → l`。实测（l = 64）：2¹⁸ → 46.5 倍，2²⁰ → 58.5 倍，2²⁴ → 63.6 倍。

### Q11 — 参考答案

1. **存储**：每 token KV 为 `2 × 80 层 × 8 × 128 × 2 字节 = 327,680 字节`；128k 时全注意力约 **42.9 GB**。NSA 仍需全部原始 KV（42.9 GB），外加压缩 token（K、V 都压缩时约 `42.9 / 64 ≈ 0.67 GB`），合计约 43.6 GB——存储不降反略增。
2. **每步读取**（每层每个 KV 头）：全注意力 131,072 个 key；NSA `131072/64 + 16×64 + 512 = 3,584` 个，约 1/36.6。decode 是带宽瓶颈，读取量的减少直接转化为速度。
3. 令 `N = N/l + k·l + W`，得 `N = (k·l + W) / (1 − 1/l) = 1536 / (63/64) ≈ 1,560`。也就是说，**约 1.56k 个 token 以下**，NSA 每步要读的 key 不比全注意力少（N = 1024 时 NSA 需 1,552 个，反而更多）。再加上三个分支各自的 softmax、门控、压缩 MLP 和不规则访存的开销，实际"打平点"会远高于 1.56k——这与讲义"16k 以下三分支开销抵消收益"的判断方向一致。讲义练习 4 还要求与 MLA 比较：MLA 减少的是**存储**（DeepSeek-V3 每层每 token 576 个值，对比 8 个 KV 头的 2,048 个），NSA 减少的是**每步读取**，两者正交。

### Q12 — 参考答案

1. `K_cmp` 的梯度只来自 `cmp_out` 这一路：`combined → g[0]·cmp_out → attention(q, K_cmp, V_cmp)`。选择分支的输出 `sel_out` 依赖的是原始 `K_sel`、`V_sel`（来自原始 K、V）和 `q`，`picks` 是一组整数下标，对 `cmp_w` 的导数处处为 0（或不存在）。所以选择分支的损失**不会**通过 `picks` 传回压缩分支或压缩 MLP。讲义说压缩分数"influence both the compressed output AND the selection logic"在前向上正确，但"梯度流经选择逻辑"的暗示不准确。
2. 不准确。top-k 决定了 `sel_out` 是在哪些 token 上计算的，改变 `picks` 会改变前向输出，所以它不是前向图上的 no-op。更准确的说法是：top-k 在**反向**图上是一个"不传梯度的离散门"，它只决定"选中块上的可微注意力"作用在哪些 token 上。
3. 因为选择**复用**了压缩分支的分数，而压缩分支本身要为最终损失服务：它的注意力分数会被训练成"哪个块与当前 query 相关"的好估计（否则 `cmp_out` 就没用）。于是选择"搭便车"获得了一个随训练不断变好的路由信号，不需要单独的路由器、辅助损失或连续松弛；同时选中块上的细粒度注意力与 query、原始 K/V 一起端到端训练，模型会学会把需要精确检索的信息放在"容易被压缩分支识别"的形式里。这正是讲义练习 5 要你用梯度流来解释的"为什么复用压缩分数而不另算路由分数"。

### Q13 — 参考回答要点

- **压缩分支**：每 `l` 个 token（讲义：通常 32 或 64）用小 MLP 压成一个摘要 token，query 对所有摘要做注意力，得到整个序列的粗粒度视图，也为选择提供路由分数。
- **选择分支**：用压缩分支的分数挑 top-k 块（讲义：通常 16），读取这些块的原始 token 做细粒度注意力，负责精确的长程检索。
- **滑动窗口分支**：最近 W 个 token（讲义：通常 512），负责语法、局部指代等短程模式，防止局部模式"抢占"另外两个分支的学习。
- **门控**：query 上的小 MLP 输出三个权重，逐位置加权求和，不要求和为 1。
- **为什么三个**：只有压缩会丢细节；只有选择需要路由信号且可能漏掉局部；只有窗口无法长程召回。三者互补，且压缩分支同时充当选择的路由器。
- 讲义数据：ACL 2025 最佳论文；64k 时 key 数约为全注意力的 1/25，论文报告的 Triton kernel 在 64k 上比 FlashAttention 快约 9 倍（讲义原话）。

### Q14 — 参考回答要点

- **推理期剪枝**（H2O 按累计注意力保留"重要" token、StreamingLLM 保留开头的 attention sink 加最近窗口）：作用在稠密训练的模型上，模型从未被要求只依赖稀疏子集来路由信息；剪枝要么丢掉之后会用到的信息（长程召回变差），要么为保质量只能剪得很保守，加速有限（讲义："recovers only a fraction of the potential speedup"）。
- **NSA**：稀疏模式在预训练时就打开，模型学会"把信息组织成可被压缩分支识别、可被选择分支读回"的形式；推理时的稀疏模式与训练时完全一致，没有分布偏移。
- **为什么需要原生**：离散选择不可微，以往要么不对选择反传（训练受限），要么用连续松弛（推理时得不到真正的稀疏）。NSA 用压缩分支的分数做选择，绕开了这个问题（见 Q12）。
- **加速的落地**：只有训练时就采用"块级、GQA 组共享"的稀疏模式，推理 kernel 才能高效加载；推理期剪枝往往是 token 级、每头不同，访存不规则。
- 加分点：NSA 并不丢弃 KV（存储不变），所以不会像 KV 剪枝那样永久丢失信息。

### Q15 — 参考回答要点

- **复杂度**：每 query `O(N/l + k·b + W)`，全序列 `O(N·(N/l + k·b + W))`（讲义）。仍是 `O(N²)`，常数降为 `1/l`；N 很大时节省倍数趋于 l。
- **为何 FLOPs 少不等于快**：
  - 稀疏访存不连续，GPU 读取效率低，可能被带宽和延迟吃掉；
  - 每个头选择不同块会让同一 KV 被重复加载；
  - 小块导致 kernel 调度和 softmax 归约开销占比上升；
  - 三个分支 + 门控 + 压缩 MLP 有固定开销，短序列下得不偿失。
- **NSA 的硬件对齐设计**：块级选择（连续内存，适合 tensor core）；同一 GQA 组共享选择，以组为外循环、稀疏 KV 块为内循环，在 SRAM 中完成注意力；提供前向与反向 kernel，使训练也能受益。
- 加分点：说明 decode 是 memory-bound，NSA 减少每步读取的 KV 正好击中瓶颈。

### Q16 — 参考回答要点

- **l（压缩块）**：越大压缩分支越便宜、渐近节省上限越高，但摘要越粗，路由越难（Q9 的稀释问题）；同时若选择块大小等于 l，`k·l` 会变大。Step 3 表显示 N = 64k、W = 512 时 `(64, 8)` 与 `(128, 8)` 都是 2,048 个 key，`(128, 32)` 反而到 5,120。
- **k（top-k）**：越大召回越稳，代价线性增长；需要按"一个 query 通常要同时引用几个远处片段"来定，讲义典型值 16。
- **W（窗口）**：讲义："Typically 512; shorter hurts local coherence, longer wastes compute"。
- **流程**：先用小模型在 32k–128k 上扫 2–3 组预设（讲义练习 1），以"相对全注意力达到 95% needle 召回"为门槛，选 key 数最少的那组；再在目标规模验证。
- **评测**：needle-in-haystack（按深度分桶）、多 needle 检索、长文档 QA、代码仓库级补全；短上下文基准确认无回退；同时测训练吞吐、decode 延迟、显存。
- 加分点：真实 NSA 的压缩块、选择块大小可以不同，压缩也可以带步长重叠，outputs 技能文件也要求给出 kernel 选择与具体长上下文评测。

### Q17 — 参考回答要点

| 方法 | 优化什么 | 主要手段 |
|------|---------|---------|
| NSA | 每步计算量与 KV 读取量（compute/带宽） | 压缩 + 块选择 + 滑动窗口，原生训练 |
| MoBA | 同上 | 把 MoE 思想用到注意力块上，query 按门控选块（讲义：同期工作） |
| 差分注意力 | 注意力质量（噪声底） | 两个 softmax 相减，抵消共模噪声 |
| MLA | KV cache 存储容量 | K/V 压缩成低秩潜变量缓存 |

- **组合**：它们作用在不同的轴上，原则上可以叠加，例如 MLA 的潜变量缓存配合块级选择，或在选中块上做差分注意力；但组合需要重新设计 kernel 与训练，讲义只把 NSA 与 MoBA 并列为"2026 长上下文预训练要知道的两种架构"，并未给出组合方案的证据。
- 常见误区：以为 NSA 能降低 KV cache 存储；以为差分注意力能降低计算量。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：FlashAttention 的分块与 SRAM 计算，是 NSA kernel 的基础。
- [阶段 07 · 15 Attention 变体 — 滑动窗口、稀疏、差分](../../../07-transformers-deep-dive/15-attention-variants/docs/zh.md)：固定模式稀疏与滑动窗口。
- [阶段 10 · 16 Differential Attention（V2）](../../16-differential-attention-v2/docs/zh.md)：另一条改进长上下文注意力的路线。
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：GQA、MLA 与 KV cache 计算（讲义练习 4 要求对比 MLA）。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：理解 MoBA 的"按块路由"与 top-k 选择。

### 本节被哪些后续内容用到
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：NSA 所针对的模型家族。
- [阶段 10 · 21 Jamba——混合 SSM-Transformer](../../21-jamba-hybrid-ssm-transformer/docs/zh.md)：另一种降低长序列成本的混合架构。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：推理引擎如何管理 KV 块。
- [阶段 17 · 17 Prefill 与 Decode 分离](../../../17-infrastructure-and-production/17-disaggregated-prefill-decode/docs/zh.md)：长上下文下 prefill/decode 的成本结构。

### 延伸关键词
`Native Sparse Attention` · `compressed / selected / sliding branches` · `block top-k selection` · `hardware-aligned sparsity` · `GQA group sharing` · `Triton kernel` · `MoBA` · `DSA` · `H2O` · `StreamingLLM / attention sink` · `needle in a haystack` · `arithmetic intensity` · `memory-bound decode`
