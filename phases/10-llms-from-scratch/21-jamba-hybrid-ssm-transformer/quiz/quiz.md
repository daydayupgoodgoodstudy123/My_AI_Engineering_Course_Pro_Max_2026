# 测验 · Jamba——混合 SSM-Transformer（Jamba — Hybrid SSM-Transformer）

> **阶段 10 · 从零构建 LLM · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | SSM 递推 | `h_t = A h_{t-1} + B x_t`，`y_t = C h_t`；算 `y_t` 只需 `h_{t-1}` 和 `x_t`，每 token O(1)、状态大小固定 |
| 2 | 演进 | S4（结构化 A，可当长卷积训练）→ Mamba（A/B/C 依赖输入，即 selective）→ Mamba-2（结构进一步简化）→ Mamba-3（讲义：复数状态、MIMO） |
| 3 | 纯 SSM 的短板 | 把全部历史压进固定大小的状态，长历史会"漏信息"；在状态追踪、上下文精确检索上落后于注意力 |
| 4 | Jamba 配方 | `l = 8`：每 8 层 1 层注意力 + 7 层 Mamba；`e = 2`：每隔一层用 MoE。32 层 = 4 注意力 + 28 Mamba，16 层 MoE |
| 5 | 为什么是 1:7 | 讲义：1:1 质量好但显存/速度差；1:15 显存极省但上下文检索失败；1:7～1:8 是甜点 |
| 6 | KV cache 只来自注意力层 | 混合模型的 KV cache ∝ 注意力层数；Mamba 层只有固定大小的状态，与上下文长度无关 |
| 7 | 位置编码 | Mamba 层通过递推天然感知顺序，原始 Jamba 的注意力层不用 RoPE；讲义称 Jamba 1.5 为长上下文加入了 RoPE |
| 8 | 规模 | Jamba：52B 总参数 / 12B 激活，256K 上下文；Jamba 1.5 Large：398B / 94B |
| 9 | 适用边界 | 64K 以上长上下文、单卡显存受限时混合架构占优；16K 以下短上下文或前沿能力竞赛中，纯 Transformer（+MoE/MLA）更常见 |
| 10 | 本节计算器的口径 | 注意力层按 32 个 KV 头（MHA）计、SSM 状态按 `hidden × 16` 计；与讲义正文、程序结尾的 takeaway 数字互相不一致 |

### 核心技能（能动手做到）

- [ ] 写出 SSM 递推式，解释为什么它的推理显存与上下文长度无关
- [ ] 给定总层数、`l`、`e`，数出注意力层、Mamba 层、MoE 层各有多少
- [ ] 计算任意混合配置在给定上下文下的 KV cache 与 SSM 状态大小（含 GQA 与 BF16/FP8）
- [ ] 识别讲义与代码中的单位、上下文长度和头数口径错误，并给出正确数字
- [ ] 判断一个具体工作负载（上下文长度分布、任务类型、显存预算）该选纯 Transformer、混合还是纯 SSM
- [ ] 估算在单张 80GB GPU 上，混合模型与纯 Transformer 在长上下文下各能并发多少条请求

---

## 二、基础自测（选择题）

**Q1.** SSM 层在推理时显存不随上下文长度增长，最直接的原因是：

- A. SSM 使用了 FlashAttention
- B. SSM 只处理最近 4,096 个 token
- C. 计算 `y_t` 只需要上一步的固定大小状态 `h_{t-1}` 和当前输入 `x_t`，不需要访问更早的任何 token
- D. SSM 把 KV cache 量化到了 1 bit

**Q2.** 按 Jamba 的 `l = 8`、`e = 2`，一个 32 层的模型有：

- A. 4 层注意力、28 层 Mamba、16 层 MoE
- B. 8 层注意力、24 层 Mamba、16 层 MoE
- C. 4 层注意力、28 层 Mamba、8 层 MoE
- D. 1 层注意力、31 层 Mamba、16 层 MoE

**Q3.** 按本节代码中 "Jamba 1:7 hybrid 32L" 的配置（4 层注意力，每层 32 个 KV 头、head_dim 128，BF16），262,144 token 的 KV cache 是：

- A. 8.4 GB
- B. 128 GB
- C. 4 GB
- D. 16 GiB

**Q4.** Mamba 相对 S4 的关键改进 "selective"（选择性）指的是：

- A. 只在部分层使用 SSM
- B. 让 A、B、C（以及离散化步长）依赖于输入，从而具备类似门控的"选择记住什么"的能力
- C. 只选择最重要的 token 计算注意力
- D. 选择性地关闭 MoE 专家

**Q5.** 根据讲义对注意力:Mamba 比例的描述，把比例从 1:7 降到 1:15（注意力更少）最可能出现的问题是：

- A. 显存占用大幅上升
- B. 显存很省，但上下文内的精确检索（in-context retrieval）能力失效
- C. 训练无法收敛
- D. 模型无法处理位置信息

**Q6.** 讲义列出的 Mamba-3 三项创新是：

- A. MLA、MTP、DualPipe
- B. 稀疏注意力、滑动窗口、ALiBi
- C. LayerNorm、GELU、weight tying
- D. 指数-梯形离散化、复数值状态更新、MIMO（多输入多输出）投影

**Q7.** 下列哪种场景下，混合 SSM-Transformer **最不占优势**？

- A. 平均上下文 4K 的高并发聊天服务
- B. 单张 80GB GPU 上处理 200K token 的合同文档
- C. 输入是很长的日志，需要一边做局部结构分析、一边偶尔回查远处的关键字段
- D. 希望在同样显存下并发更多长上下文请求

**Q8.** Jamba 1.5 Large（398B 总参数 / 94B 激活）的激活比例约为多少？与 DeepSeek-V3（37B / 671B）相比如何？

- A. 约 5.5%，与 DeepSeek-V3 相同
- B. 约 2.3%，比 DeepSeek-V3 更稀疏
- C. 约 23.6%，比 DeepSeek-V3 的约 5.5% 稠密得多
- D. 100%，Jamba 1.5 没有 MoE

---

## 三、动手 / 代码题

**Q9.** 讲义正文与程序结尾的 takeaway 中出现了以下数字：

```text
讲义：KV cache (attention layers only): 2 * 4 * 32 * 128 * 256k * 2 = 8.4 GB at 256k BF16
讲义：Even against the GQA(8) baseline ... (32 GB), Jamba's 1:7 hybrid at 16 GB is still 2x smaller.
代码 takeaway：Pure Transformer at 256k = 67 GB just for KV cache
代码 takeaway：Jamba 1:7 = 8.4 GB KV cache + ~4 MB SSM state
```

而程序表格打印的是 Jamba 1:7 在 262k 为 `16.00GB`、纯 Transformer 为 `128.00GB`。

1. 用 Python 算出 `2 * 4 * 32 * 128 * 262144 * 2`，并判断 8.4 GB、67 GB 这两个数字实际对应的是什么上下文长度和单位。
2. 讲义的这几句话之间有什么自相矛盾之处？

**Q10.** 真实的 Jamba（v0.1）在注意力层使用 GQA：32 个 query 头、8 个 KV 头。

1. 把代码中 Jamba 1:7 的 `n_kv_heads` 改为 8，256K 上下文的 KV cache 是多少？与"32 层、GQA 8"的纯 Transformer（如 Mixtral 形状）相比是几倍？
2. 讲义说 Jamba 能"在单张 80GB GPU 上跑 256K 上下文"。52B 参数的权重用 BF16 存需要多少显存？这句话要成立，还需要什么前提？

**Q11.** 代码中 SSM 状态的计算：

```python
def ssm_state_bytes(cfg, bytes_per_elem):
    ssm_layers = cfg.total_layers - cfg.attn_layers
    return ssm_layers * cfg.hidden * cfg.ssm_state_size * bytes_per_elem
```

1. Jamba 1:7（28 层 Mamba、hidden 4096、state 16、BF16）的 SSM 状态是多少？
2. 在 Mamba 中，状态的宽度是扩展后的内部维度 `d_inner = expand × hidden`（常用 expand = 2），每层还要缓存一个短卷积的状态（`d_inner × (d_conv − 1)`，常用 d_conv = 4）。按此重算。
3. 讲义练习 2 问"在哪个比例下 KV cache 等于 SSM 状态"。对 Jamba 1:7（按代码口径），上下文多长时两者相等？由此解释程序第三张表里所有混合配置的 `kv_frac_of_total_cache` 都显示 `1.000` 的原因。

**Q12.** 一张 80GB GPU，假设模型权重用 8-bit 存储（52B → 52 GB），激活与其它开销预留 4 GB，剩余显存全部给 KV cache 和 SSM 状态。请分别计算在 256K 上下文下能并发多少条请求：

- 真实 Jamba（4 层注意力、8 个 KV 头、28 层 Mamba，SSM 状态按 Q11 第 2 问的结果）；
- 一个同样 52B、32 层全注意力、GQA 8 的纯 Transformer。

---

## 四、面试高频题

**Q13.**（基础必考）对比 Transformer 注意力与 SSM（如 Mamba）在训练复杂度、推理复杂度、推理显存、能力上的差异。

**Q14.**（原理深挖）为什么混合架构只需要很少的注意力层就能"补上" SSM 的短板？Jamba 的注意力层为什么可以不用 RoPE？

**Q15.**（工程实践）在 vLLM/SGLang 这类推理引擎中服务 Jamba 这类混合模型，与服务纯 Transformer 相比，在缓存管理、prefix caching、speculative decoding 等方面会遇到哪些新问题？

**Q16.**（场景设计）公司有三条业务：①平均 2K token 的客服对话，QPS 很高；②单次 200K token 的法律卷宗问答，只有单张 80GB 卡；③需要多文档交叉推理的复杂分析报告。请分别给出架构选择与理由。

**Q17.**（追问型）讲义说 Mamba-3 用复数值状态更新"恢复"了状态追踪能力，并称它等价于对状态做数据相关的 rotary embedding。请解释这句话的直觉，以及为什么实数对角/标量状态矩阵会损失状态追踪能力。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："computing `y_t` needs only `h_{t-1}` and `x_t`, not any earlier `x`. Memory is constant. Inference is O(1) per token." 历史信息全部被压缩进固定大小的 `h`。A 是注意力的 IO 优化；B 是滑动窗口注意力；D 是捏造的。

### Q2 — 答案：A

32 / 8 = 4 个 Jamba block，每个 block 1 层注意力 + 7 层 Mamba，合计 4 + 28；`e = 2` 表示每隔一层 MoE，32 / 2 = 16 层。讲义："At 4 blocks deep (32 layers total), you get 28 Mamba and 4 Attention layers. 16 of those use MoE." B 把 l 理解成"每 4 层一个注意力"；C 的 MoE 数错误；D 混淆了 block 数。

### Q3 — 答案：D

`2 × 4 × 32 × 128 × 262144 × 2 = 17,179,869,184 字节 = 16 GiB`（程序表格输出 `16.00GB`，用的是 1024 进制）。A（8.4 GB）是讲义正文的错误数字，实际对应 128K（见 Q9）；B 是 32 层纯 MHA Transformer；C 是真实 Jamba 用 GQA 8 个 KV 头时的值（见 Q10）。

### Q4 — 答案：B

讲义："Mamba (Gu, Dao 2023) replaced the fixed `A, B, C` with data-dependent ones (the 'selective' part)"；Key Terms："Data-dependent A, B, C parameters that give the model gating-like selectivity at linear time"。A 描述的是混合架构；C 是稀疏注意力；D 与 SSM 无关。

### Q5 — 答案：B

讲义消融结论："Too little attention (1:15): memory is great but in-context retrieval fails." 注意力层负责"精确回忆与状态追踪"，太少就补不上 SSM 的短板。A 方向反了；C、D 没有依据（Mamba 层本身就能提供位置信息）。

### Q6 — 答案：D

讲义 "Mamba-3: the pure-SSM baseline in 2026" 列出：exponential-trapezoidal discretization、complex-valued state update、MIMO projections。A 是 DeepSeek-V3 的创新；B 是注意力变体；C 是 Transformer 基础组件。

### Q7 — 答案：A

讲义 "Hybrids lose when: Context is short (under 16k). The SSM overhead is wasted; pure Transformer is fine." 4K 上下文时 KV cache 本来就小，混合架构的显存优势体现不出来，而 SSM 层的递推实现和生态成熟度反而是负担。B、C、D 正是讲义列出的 "Hybrids win when" 场景（长上下文、短程结构 + 长程回查、单卡显存受限、同显存更多并发）。

### Q8 — 答案：C

`94 / 398 = 23.6%`；DeepSeek-V3 `37 / 671 = 5.5%`（已计算）。Jamba 只在一半的层用 MoE（`e = 2`），另一半层的 MLP 全部激活，注意力/Mamba 层也全部激活，因此激活比例天然更高；DeepSeek-V3 除前 3 层外全部是 256 选 8 的细粒度 MoE。这正是讲义练习 4 要你解释的现象。（Jamba v0.1 的 12B / 52B 也约为 23%。）

### Q9 — 参考答案

1. `2 × 4 × 32 × 128 × 262144 × 2 = 17,179,869,184 字节`，即 17.2 GB（十进制）或 16 GiB。8.4 GB 对应的是**128K** 上下文：`2 × 4 × 32 × 128 × 131072 × 2 = 8.59e9 字节 ≈ 8.6 GB`。同理 takeaway 中纯 Transformer 的"67 GB"对应 128K 下的 `68.7e9 字节`（=64 GiB），而 256K 时是 128 GiB。也就是说这两个数字都把上下文长度算成了 128K（并混用了十进制/二进制单位），与"256k"的标注不符。
2. 自相矛盾：讲义先说 Jamba 1:7 在 256K 时 KV cache 是 8.4 GB，几段之后又说"Jamba's 1:7 hybrid at 16 GB is still 2x smaller"；takeaway 说纯 Transformer 256K 需 67 GB，而同一个程序的表格打印 128 GB。正确的同口径（256K、BF16、每层 32 个 KV 头）数字是：纯 MHA 128 GiB、纯 GQA 8 为 32 GiB、Jamba 1:7（MHA）16 GiB。另外"8x reduction"只在"同头数、32 层 vs 4 层注意力"时成立。

### Q10 — 参考答案

1. `2 × 4 × 8 × 128 × 262144 × 2 = 4 GiB`（已计算）。32 层 GQA 8 的纯 Transformer 是 `2 × 32 × 8 × 128 × 262144 × 2 = 32 GiB`，正好 **8 倍**——"1:7 混合把 KV cache 降为 1/8"指的是与同头数配置相比。代码把 Jamba 写成 32 个 KV 头，结果 16 GiB，与"GQA 8 纯 Transformer 只差 2 倍"的结论就是这么来的；把真实 GQA 计入后，优势是 8 倍而不是 2 倍。
2. `52e9 × 2 字节 = 104 GB`，BF16 权重本身就放不下 80GB。要在单卡 80GB 上运行，权重至少要量化到 8-bit（约 52 GB），再加 4 GiB 左右的 KV cache、MB 级的 SSM 状态和激活，才可能装下。所以"单卡 80GB 跑 256K"隐含了"权重量化"和"单条/少量请求"的前提。（AI21 发布时给出的说法是单张 80GB GPU 可容纳约 140K 上下文，可自行查阅 Jamba 论文核对。）

### Q11 — 参考答案

1. `28 × 4096 × 16 × 2 = 3,670,016 字节 ≈ 3.5 MiB`（讲义"3.7 MB"是十进制）。纯 Mamba 32 层为 4 MiB（程序打印 `4.00MB`）。
2. `d_inner = 2 × 4096 = 8192`：SSM 状态 `28 × 8192 × 16 × 2 = 7.0 MiB`；卷积状态 `28 × 8192 × 3 × 2 ≈ 1.3 MiB`；合计约 8.3 MiB。仍然是 MB 级、与上下文长度无关，结论不变，但代码低估了约 2.4 倍。（实际实现中 SSM 状态常以 FP32 保存，还会再翻倍。）
3. KV cache 每 token：`2 × 4 × 32 × 128 × 2 = 65,536 字节`；SSM 状态 3,670,016 字节；`3,670,016 / 65,536 = 56`——**上下文只需 56 个 token**，KV cache 就追平 SSM 状态（已计算）。在 256K 时 KV cache 是 SSM 状态的约 4,700 倍，所以 `kv / (kv + ss + 1)` 约为 0.9998，三位小数显示成 `1.000`。结论：只要还有一层注意力，长上下文下的缓存显存几乎全部来自注意力层；混合比例的意义就在于"减少注意力层数"。

### Q12 — 参考答案

可用显存：`80 − 52 − 4 = 24 GB`（按十进制 24e9 字节）。

- **真实 Jamba**：每条请求 KV cache `4 GiB = 4.295e9 字节` + SSM/卷积状态约 8.3 MiB ≈ `4.30e9 字节`；`24e9 / 4.30e9 ≈ 5.6`，可并发 **5 条** 256K 请求。
- **纯 Transformer（32 层、GQA 8）**：每条 `32 GiB ≈ 34.4e9 字节`，超过 24 GB，**一条都放不下**。

这就是混合架构在长上下文下的核心价值：同样显存下并发数（吞吐）的差距是数量级的。讲义："At 256k context, Jamba's memory advantage shows up in concurrent-request throughput."

### Q13 — 参考回答要点

| 维度 | 注意力 | SSM（Mamba） |
|------|-------|-------------|
| 训练复杂度 | O(N²)（FlashAttention 降低 IO 但不改复杂度） | O(N)（并行扫描 / 分块算法） |
| 推理每 token | O(N)（要读全部 KV） | O(1) |
| 推理显存 | KV cache ∝ N | 固定大小状态 |
| 能力 | 精确回忆任意位置、上下文检索强 | 历史被压缩，长距离精确检索、状态追踪较弱 |

- 讲义："SSMs compress history into a fixed state, and when history is long, information leaks. Attention remembers everything exactly but pays quadratic cost."
- 加分点：说明 S4 → Mamba → Mamba-2 的演进，以及 Mamba 选择性机制让模型能根据输入决定"记住/遗忘"。

### Q14 — 参考回答要点

- **少量注意力就够**：多数层的工作是局部/短程的特征加工，SSM 足以胜任；需要"按内容精确查找"的能力（如复制、检索、归纳头式的模式匹配）只要在网络中出现若干次全局注意力就能提供。讲义："The Transformer layers handle exact recall and state tracking. The Mamba layers handle the cheap bulk of processing."
- **比例由消融决定**：1:7～1:8 在困惑度与检索能力之间取得平衡。
- **不需要 RoPE**：Mamba 的递推是按顺序进行的，输出天然带有位置信息；注意力层的输入已经过前面的 Mamba 层，已经"知道"顺序。讲义称 Jamba 1.5 后来在注意力层加入了 RoPE，用于更长上下文的泛化。
- 加分点：说明纯 SSM 在"多查询联想回忆（MQAR）"一类合成任务上会随序列变长迅速退化，而少量注意力层可以修复。

### Q15 — 参考回答要点

- **两类缓存**：注意力层的分页 KV cache（随长度增长）+ Mamba 层的固定大小状态（每请求一份，不分页）。引擎需要两套内存管理，并在调度时同时考虑两者。
- **prefix caching 更难**：KV cache 可以按 token 块复用；SSM 状态只代表"处理到某个位置为止的整段历史"，要复用前缀必须在特定位置保存状态快照，不能任意截断复用。
- **speculative decoding 的回滚**：注意力层拒绝 draft 时截断 KV 即可；SSM 状态已被 draft token "污染"，需要保存检查点或重算。
- **chunked prefill**：SSM 需要把上一块的末状态传给下一块，状态管理要严格按序。
- **算子与生态**：需要专门的选择性扫描 kernel；讲义提醒"Check the specific version"，引擎对 Jamba/Mamba 的支持程度随版本变化。
- **吞吐收益**：长上下文下单卡能并发更多请求（见 Q12）。

### Q16 — 参考回答要点

- **①短对话高 QPS**：纯 Transformer（GQA/MLA，可选 MoE）。短上下文下 KV cache 不是瓶颈，混合架构优势小；纯 Transformer 推理生态最成熟（连续批处理、prefix caching、speculative decoding）。
- **②200K 卷宗、单卡 80GB**：混合架构（Jamba 类）+ 8-bit 权重。KV cache 只有纯 Transformer 的约 1/8，单卡能放下并留出并发余量；纯 Transformer 的 KV cache 在 200K 时就可能超过可用显存。
- **③多文档交叉推理**：纯 Transformer（前沿 MoE + MLA 类）。讲义："Tasks need everywhere-to-everywhere attention ... The sparsity of attention layers in the hybrid hurts." 前沿能力仍由纯 Transformer MoE 主导。
- 加分点：给出评测方式——用目标长度下的检索类评测（如 needle-in-a-haystack、RULER）和真实业务集比较，而不是只看困惑度。

### Q17 — 参考回答要点

- **直觉**：复数对角状态矩阵的每个元素 `λ = r·e^{iθ}`，每一步把状态乘以 λ，相当于在复平面上**旋转** θ 角（同时按 r 衰减）。RoPE 也是按位置对向量做旋转。若 θ 由输入决定（数据相关），状态每一步旋转的角度由内容控制，所以讲义说它等价于"对状态做数据相关的 rotary embedding"。
- **为什么实数会损失状态追踪**：实数对角元素只能做缩放（以及正负号翻转，且常被约束为正的衰减），无法表达"循环/计数取模"一类需要周期性旋转的状态变化，例如奇偶性（parity）、模 n 计数、有限状态机的循环转移。Mamba 到 Mamba-2 进一步把状态矩阵简化为标量乘单位阵，表达力更受限。复数旋转恢复了表示周期性变化的能力。
- **讲义原话**：Mamba-3 "re-adds complex values — equivalent to a data-dependent rotary embedding on the state. This restores state-tracking capabilities that previous real-valued simplifications cost."
- 讲义给出的效果数字（1.5B 规模，平均下游准确率比 Gated DeltaNet 高 0.6 分，MIMO 变体再加 1.2 分；同等效果下状态大小减半）照实引用即可，面试中不要自行夸大。
- 加分点：联系第 7 阶段第 04 节 RoPE 的推导——二维旋转等价于乘以单位复数 `e^{iθ}`。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：GQA、MoE、读 config 的方法。
- [阶段 10 · 17 原生稀疏 Attention（DeepSeek NSA）](../../17-native-sparse-attention/docs/zh.md)：另一条降低长上下文注意力成本的路线。
- [阶段 07 · 01 为什么选择 Transformers — RNNs 的问题](../../../07-transformers-deep-dive/01-why-transformers/docs/zh.md)：SSM 本质上是一种可并行训练的线性 RNN。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：理解 Mamba-3 复数状态与 RoPE 的关系。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的计算方法。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：Jamba 隔层 MoE 的基础。

### 本节被哪些后续内容用到
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：MLA 是另一种压缩 KV cache 的思路，可与混合架构对比。
- [阶段 05 · 28 长上下文 Evaluation — NIAH、RULER、LongBench、MRCR](../../../05-nlp-foundations-to-advanced/28-long-context-evaluation/docs/zh.md)：评估混合模型长上下文检索能力。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：混合模型的缓存管理问题。
- [阶段 12 · 18 百万 Token 上下文中的长视频理解](../../../12-multimodal-ai/18-long-video-million-token/docs/zh.md)：超长上下文的实际应用。

### 延伸关键词
`state space model` · `S4` · `Mamba / selective scan` · `Mamba-2 / SSD` · `Mamba-3` · `hybrid architecture` · `attention-to-Mamba ratio` · `Gated DeltaNet` · `linear attention` · `MQAR` · `state tracking` · `KV cache` · `GQA`
