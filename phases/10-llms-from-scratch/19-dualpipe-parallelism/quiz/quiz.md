# 测验 · DualPipe 并行（DualPipe Parallelism）

> **阶段 10 · 从零构建 LLM · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提示**：本节中文讲义机翻质量很差（如把 micro-batch 译成"微型蓄水池"、把 EP 译成"欧洲议会"），建议以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 流水线并行（PP） | 把 N 层模型按层切到 P 个设备上；micro-batch 前向从 rank 0 流到 P−1，反向再流回来 |
| 2 | Pipeline bubble | 某个 stage 等输入或等梯度时 GPU 空转的时间；1F1B 的 bubble 约为 `(P−1)·(F+B)`，与 micro-batch 数 M 无关，占比约 `(P−1)/(M+P−1)` |
| 3 | 调度演进 | GPipe（一次一批）→ 1F1B（前反向交错）→ Zero Bubble（把反向拆成 B 输入梯度与 W 权重梯度去填空泡）→ DualPipe |
| 4 | MoE 的 all-to-all 瓶颈 | 跨节点专家并行（EP）每次前向要 dispatch 和 combine 两次 all-to-all；讲义：DeepSeek-V3 中计算与通信约 1:1 |
| 5 | Chunk 拆分 | 每个前向 chunk 拆成 attention、all-to-all dispatch、MLP（专家计算）、all-to-all combine 四段，以便与另一个 chunk 的计算互相遮盖 |
| 6 | 双向调度 | 从流水线**两端**同时注入 micro-batch；设备 i 同时持有第 i 段和第 `P−1−i` 段的层，因此参数是 2 份——这就是"Dual" |
| 7 | "bubble-free"的真实含义 | 技术含义是 bubble 不随 micro-batch 数增长、稳定阶段可被填满；warmup/cooldown 仍有固定 bubble |
| 8 | DualPipeV（Cut-in-half） | Sea AI Lab 2025 的 V 形调度，只保留 1 份参数，代价是 bubble 略大；DeepSeek 开源仓库已纳入 |
| 9 | 适用场景 | 千卡以上、EP 通信繁重的 MoE 预训练才值得；小规模/稠密模型用 1F1B 或 Zero Bubble 足够 |
| 10 | 本节代码的性质 | 不是逐时隙的调度模拟器，而是四个手写的闭式公式；DualPipeV 直接取 DualPipe 的 1.2 倍 |

### 核心技能（能动手做到）

- [ ] 画出 P = 4 的 1F1B 时序图，数出每个 rank 的 bubble，并推导 `(P−1)/(M+P−1)`
- [ ] 用本节代码的公式手算任意 (P, M) 下四种调度的 bubble 占比，并能指出各公式分母的假设
- [ ] 解释 DualPipe 如何把 all-to-all dispatch/combine 藏进另一个 micro-batch 的计算里
- [ ] 计算 DualPipe 2× 参数复制在稠密与 MoE 模型上的每卡显存代价，说明为何 MoE 下代价相对较小
- [ ] 把 bubble 占比换算成整个训练任务"可回收的 GPU 小时"，并对结论的假设保持警惕
- [ ] 针对给定集群（卡数、互联、模型形状）选择 PP 深度、micro-batch 数和调度算法

---

## 二、基础自测（选择题）

**Q1.** DualPipe 把一个前向 chunk 拆成哪四个部分？

- A. Embedding、Attention、MLP、输出头
- B. Q 投影、K 投影、V 投影、输出投影
- C. 前向输入梯度、前向权重梯度、反向输入梯度、反向权重梯度
- D. Attention、all-to-all dispatch、MLP（专家计算）、all-to-all combine

**Q2.** DualPipe 名字里的 "Dual" 指的是：

- A. 每个设备同时持有第 i 段和第 `P−1−i` 段的层，即参数保存两份，以支撑从两端注入的双向 micro-batch 流
- B. 每个 micro-batch 都要做两次前向
- C. 使用两张 GPU 组成一个 stage
- D. 同时使用数据并行与张量并行两种并行方式

**Q3.** 按本节代码 `bubble_1f1b` 的公式，P = 8、M = 16 时 1F1B 的 bubble 占比是：

- A. 约 12%
- B. 约 5.5%
- C. 约 30.4%
- D. 约 46.7%

**Q4.** Zero Bubble（Qi 等，2023）能进一步压缩 bubble 的关键做法是：

- A. 增加流水线深度 P
- B. 把反向传播拆成"对输入的梯度（B）"和"对权重的梯度（W）"两部分，W 不在关键路径上，可用来填补空泡
- C. 让每个 rank 保存两份参数
- D. 取消 warmup 阶段，直接进入稳定阶段

**Q5.** 讲义区分了"营销说法"和"技术说法"。DualPipe 所谓 "bubble-free" 在技术上准确的含义是：

- A. bubble 不随 micro-batch 数增长；稳定阶段可以没有空泡，但 warmup/cooldown 仍有固定 bubble
- B. 任何 P、M 下 bubble 都严格为 0
- C. 不再需要流水线并行
- D. 所有通信时间都变成了 0

**Q6.** 关于 DualPipeV，正确的是：

- A. 它保存 4 份参数以进一步减少 bubble
- B. 它只适用于稠密模型，不能用于 MoE
- C. 它取消了 chunk 拆分与计算-通信重叠
- D. 它用 V 形调度只保留 1 份参数，代价是 bubble 比 DualPipe 略大

**Q7.** DeepSeek-V3 技术报告用 F、B、W、`F&B`（互相重叠的一对前向与反向 chunk）对比了几种调度。下列哪项描述与报告一致？

- A. 1F1B 的 bubble 为 `(PP/2 − 1)(F + B)`，参数 2×
- B. DualPipe 的 bubble 为 `(PP/2 − 1)(F&B + B − 3W)`，参数 2×，激活显存 `PP + 1`
- C. ZB1P 的 bubble 为 0，参数 1×
- D. DualPipe 的 bubble 随 micro-batch 数线性增长

**Q8.** 下列哪个场景**最值得**使用 DualPipe？

- A. 在 64 张 A100 上训练一个 7B 稠密模型
- B. 模型能完整放进单张 GPU，只想加速训练
- C. 在 2,048 张 H800 上训练一个跨节点专家并行的 671B MoE 模型
- D. 在单机 8 卡上对 70B 稠密模型做 LoRA 微调

---

## 三、动手 / 代码题

**Q9.** 本节代码的四个 bubble 公式如下：

```python
def bubble_1f1b(P, M):
    total = 2 * M + 2 * (P - 1)
    bubble = 2 * (P - 1)
    return bubble / total

def bubble_zero_bubble(P, M):
    total = 3 * M + 2 * (P - 1)
    bubble = (P - 1)
    return bubble / total

def bubble_dualpipe(P, M):
    total = 3 * M + (P - 1)
    bubble = (P - 1) // 2
    return bubble / total

def bubble_dualpipev(P, M):
    return bubble_dualpipe(P, M) * 1.2
```

1. 手算 P = 4、M = 8 时四种调度的 bubble 占比。
2. 讲义的对比表说 1F1B、Zero Bubble 的 bubble "grows"（随 micro-batch 数增长），DualPipe 是 "constant"。请看这几个函数里**分子** `bubble` 的写法，判断这个说法在代码里是否成立，并给出正确的表述。
3. `bubble_dualpipe` 的分母为什么写成 `3 * M + (P - 1)` 而 1F1B 是 `2 * M + 2 * (P - 1)`？这种比较是否"同一口径"？

**Q10.** 讲义给出的手画时序图（P = 4，8 个 micro-batch，F5R～F8R 为反向流）：

```
           Time →
rank 0:  F1 F2 F3 F4  F5R F6R F7R F8R  B1 B2 B3 B4  ...
rank 1:     F1 F2 F3  F4/F5R F6R F7R   B1 B2 ...
rank 2:        F1 F2  F3/F5R F4/F6R    B1 ...
rank 3:           F1  F2/F5R F3/F6R    ...
```

请找出至少两处违反流水线数据依赖的地方，并说明真实 DualPipe 中反向流（从 rank 3 注入的 micro-batch）应该如何出现在时序图上。

**Q11.** Step 4 打印：

```text
  1F1B bubble     : 10.5%
  DualPipe bubble : 1.8%
  recovered       : 244,583 GPU-hours
  (that is roughly the cost of a full 70B dense pre-training run)
```

1. 用代码公式复现 244,583 这个数。
2. 讲义另一处说"At 8 stages, roughly 12% of GPU time can be bubble even with 1F1B"。按 1F1B 公式，P = 8 时需要多大的 M 才会是 12%？这与 Step 1 中 M = 16 的 30.4% 有什么关系？
3. 评价"245K GPU 小时约等于一次完整 70B 稠密预训练"这一说法（提示：用 `6·N·D` 估算 FLOPs，假设 H800 BF16 稠密峰值约 989 TFLOPS、MFU 40%）。

**Q12.** 讲义练习 4：分别计算 DualPipe 的 2× 参数复制对下面两种情况的每卡参数显存（BF16，每参数 2 字节）影响，并解释为什么 MoE 情况"相对代价更小"。

- 稠密 70B，P = 8，不用张量并行；
- 671B MoE，P = 16，EP = 64。为便于计算，**假设**其中非专家参数约 20B、专家参数约 651B，专家在 EP 组内均分。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 pipeline bubble？请比较 GPipe、1F1B、Zero Bubble 三种调度在 bubble 和激活显存上的差异。

**Q14.**（原理深挖）DualPipe 是如何把 MoE 的跨节点 all-to-all 通信"藏起来"的？为什么需要把 chunk 拆成四段、并且要双向注入？

**Q15.**（工程实践）给你 1,024 张 GPU（节点内 NVLink、节点间 400Gbps IB）训练一个 200B 级 MoE，你如何选择 PP 深度、micro-batch 数、PP 调度算法？上线后看哪些指标判断调度是否达标？

**Q16.**（追问型）DualPipe 要保存两份参数，为什么 DeepSeek 认为"这很便宜"？什么情况下应该改用 DualPipeV？

**Q17.**（场景设计）你把训练从 1F1B 切换到 DualPipe 后，整体 MFU 只提升了 1 个百分点，远低于预期。请列出排查思路。

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义 "Idea 1: chunk decomposition"：attention、all-to-all dispatch、MLP（MoE 专家计算）、all-to-all combine。反向 chunk 包含对应的梯度版本。拆成四段的目的，是让一个 chunk 的通信与另一个 chunk 的计算在时间上重叠。A 是模型的整体结构；B 是注意力内部的投影；C 混淆了 Zero Bubble 的 B/W 拆分。

### Q2 — 答案：A

讲义："device `i` must hold BOTH the early-pipeline layer `i` AND the late-pipeline layer `P - 1 - i`. That is the 'dual' part"。双向注入意味着同一台设备要为两个方向的流服务不同位置的层，所以参数是 2 份。B、C、D 都不是该设计的内容。

### Q3 — 答案：C

`bubble = 2 × 7 = 14`，`total = 2 × 16 + 14 = 46`，`14 / 46 = 30.4%`（与程序 Step 1 输出一致）。等价于经典公式 `(P−1)/(M+P−1) = 7/23`。A（12%）是讲义的说法，对应的是 M ≈ 51 的情形（见 Q11）；B 是 DualPipe 的值；D 是 M = 8 时的值。

### Q4 — 答案：B

讲义 Key Terms："Splits backward into B (input gradient) and W (weight gradient)"。B 必须尽快算出来传给上一个 stage（在关键路径上），W 只用于本 stage 的参数更新，可以推迟，用来填空泡。A 会让 bubble 更大；C 是 DualPipe 的做法；D 不可能，warmup 是流水线填充所必需的。

### Q5 — 答案：A

讲义："In marketing terms: 'bubble-free'. In technical terms: bubbles do not grow with micro-batch count." 稳定阶段可以填满，但 warmup/cooldown 的 bubble 依然存在（DeepSeek-V3 报告给出的 DualPipe bubble 为 `(PP/2−1)(F&B+B−3W)`，不为 0）。B 过度解读；C、D 显然错误——通信是被**重叠**而不是被消除。

### Q6 — 答案：D

讲义："Their DualPipeV schedule folds the bidirectional injection into a 'V-shape' schedule that runs on a single parameter copy. The bubble is slightly larger than DualPipe's"。A 反了；B 不对，讲义表格写的是"dense or EP-light"适用，不是"不能用于 MoE"；C 错，DualPipeV 仍保留部分计算-通信重叠（表格中为 partial）。

### Q7 — 答案：B

DeepSeek-V3 技术报告（Table 2）的对比：

| 方法 | Bubble | 参数 | 激活 |
|------|--------|------|------|
| 1F1B | `(PP−1)(F+B)` | 1× | PP |
| ZB1P | `(PP−1)(F+B−2W)` | 1× | PP |
| DualPipe | `(PP/2−1)(F&B+B−3W)` | 2× | PP+1 |

A 把 DualPipe 的系数安到了 1F1B 上；C 错，ZB1P 仍有 bubble；D 错，三者的 bubble 都与 micro-batch 数无关，DualPipe 的优势是系数小（约减半），并且大部分时间 `F&B` 是重叠执行的。

### Q8 — 答案：C

讲义："For frontier MoE training at multi-thousand GPU scale, it is effectively required"；"For smaller runs (under 1k GPUs), DualPipe is overkill"。A 规模小且是稠密模型，没有 all-to-all 瓶颈；B 能放进单卡就不需要流水线并行；D 是微调场景，通常用数据并行/ZeRO 就够了。

### Q9 — 参考答案

1. P = 4、M = 8（已用 Python 计算）：

| 调度 | 分子 | 分母 | 占比 |
|------|------|------|------|
| 1F1B | `2×3 = 6` | `16 + 6 = 22` | 27.3% |
| Zero Bubble | `3` | `24 + 6 = 30` | 10.0% |
| DualPipe | `3 // 2 = 1` | `24 + 3 = 27` | 3.7% |
| DualPipeV | `1.2 × 1/27` | — | 4.4% |

2. **不成立**。四个函数的分子都只依赖 P，不依赖 M——1F1B 的绝对 bubble `2(P−1)` 与 DualPipe 的 `(P−1)//2` 一样都是"constant"。随 M 增大，所有调度的 bubble **占比**都在下降（Step 2 表格里 1F1B 从 63.6% 降到 5.2%）。正确表述：在 1F1B、ZB1P、DualPipe 中，bubble 的绝对量都与 M 无关；DualPipe 的优势在于**系数更小**（约 `PP/2 − 1` 而非 `PP − 1`），并且把通信与计算重叠起来。DeepSeek-V3 报告强调的"不随 micro-batch 增长"是相对于 Chimera 这类双向调度而言的（报告原话还包括激活显存也不随 micro-batch 增长）。
3. 不是同一口径。1F1B 以"chunk"为单位（每个 micro-batch 前向 1 + 反向 1 = 2 个单位）；Zero Bubble 与 DualPipe 以"sub-chunk"为单位（F、B、W 各 1，共 3 个单位），这只是作者的近似。DualPipe 的 warmup 项写成 `P − 1` 而非 `2(P − 1)` 也没有推导依据。所以代码给出的数字只能看趋势，不能当作精确比较。另外 `(P−1)//2` 用了整除：P 为偶数时恰好等于报告中的 `PP/2 − 1`（P = 8 时为 3），但代码把它乘的单位当成 1 个 sub-chunk，而报告中是 `F&B + B − 3W`。

### Q10 — 参考答案

问题：

1. **F5R 在同一时隙出现在全部 4 个 rank 上**（第 5 个时隙：rank 0 的 `F5R`、rank 1 的 `F4/F5R`、rank 2 的 `F3/F5R`、rank 3 的 `F2/F5R`）。一个 micro-batch 必须先在 rank 3 算完第一段，才能把激活传给 rank 2，不可能同时在 4 个 rank 上执行同一个前向。F6R 也有同样问题（rank 0/1 在第 6 个时隙、rank 2/3 也在第 6 个时隙）。
2. **反向流注入太晚**：DualPipe 的要点是两端**同时**注入。rank 3 在第 1 个时隙就应该开始 F5R，而不是先空等 3 个时隙再处理 F1。
3. **B1 的顺序错误**：micro-batch 1 的反向必须先在 rank 3（最后一段）开始，再逐级传回 rank 0；图中 rank 0 的 B1 出现在 rank 2/3 之前或同时。

正确画法：正向流 F1、F2… 在 rank 0 第 1 个时隙开始、每个时隙往下游移动一格；反向流 F5R、F6R… 在 rank 3 第 1 个时隙开始、每个时隙往上游移动一格（呈"对角线"）。两条对角线在中间的 rank（1、2）最先相遇，此后这些 rank 把"一个方向的前向"与"另一个方向的反向"配对重叠执行（即报告中的 `F&B`）。讲义练习 2 要求手画的就是这张表，建议对照 DeepSeek-V3 报告的 Figure 5 或 DualPipe 仓库 README 的示意图。

### Q11 — 参考答案

1. `bubble_1f1b(16, 128) = 30 / (256 + 30) = 10.49%`；`bubble_dualpipe(16, 128) = 7 / (384 + 15) = 1.75%`；差值 `8.74% × 2,800,000 = 244,583` GPU 小时。
2. 由 `(P−1)/(M+P−1) = 0.12`、P = 8 得 `M = 7/0.12 − 7 ≈ 51`。也就是说讲义的"12%"隐含 M ≈ 51；Step 1 选 M = 16 时是 30.4%。bubble 占比强烈依赖 M，脱离 M 谈"8 级流水线 12% bubble"并不完整。讲义另一处"12–15% bubble → 340–420K GPU 小时"与代码 Step 4 在 P = 16、M = 128 下的 10.5%（换算约 294K，回收 245K）也不是同一组假设。
3. 估算（已计算）：`244,583 h × 3600 s × 989e12 × 0.4 ≈ 3.5e23 FLOPs`；按 `6·N·D`、N = 70B，可训练约 `0.83T` token。而一次"完整"的 70B 预训练按 15T token 计需要约 `6.3e24 FLOPs`，同样假设下约 4.4M GPU 小时。所以 245K GPU 小时只够一次小规模（不到 1T token）的 70B 训练，"roughly the cost of a full 70B run"严重高估了它。结论：回收的算力可观（约 9% 的总预算），但具体比喻要说明 token 数和 MFU 假设。另外，总预算 2.8M GPU 小时本身也包含了上下文扩展与后训练阶段，并非全部用于 PP 预训练。

### Q12 — 参考答案

**稠密 70B，P = 8**：单份每卡 `70B / 8 = 8.75B` 参数 → 17.5 GB；DualPipe 2 份 → 17.5B 参数 → **35 GB**，多出 17.5 GB，在 80 GB 卡上是很大的负担（还要放优化器状态、梯度和激活）。

**671B MoE，P = 16，EP = 64（按题设假设）**：

- 非专家：`20B / 16 = 1.25B`
- 专家：`651B / (16 × 64) ≈ 0.636B`
- 单份合计约 `1.886B` 参数 → 约 3.8 GB；2 份约 **7.5 GB**，多出约 3.8 GB。

结论：MoE 的绝大部分参数是专家，已被 EP 切成 64 份，每卡持有的参数本来就很少，复制一份的绝对代价只有几 GB；稠密模型没有 EP 分摊，复制的代价直接翻倍。这正是讲义所说"Expert Parallelism already spreads the MoE experts so thin that replicating ... is small potatoes"。实际系统中优化器状态（ZeRO 分片）与激活显存也要一起核算。

### Q13 — 参考回答要点

- **定义**：流水线中某个 stage 因等待上游激活或下游梯度而空转的时间。
- **GPipe**：先把 M 个 micro-batch 的前向全部做完再做反向；bubble 约 `(P−1)(F+B)`，但需要同时保存 M 个 micro-batch 的激活，显存大。
- **1F1B**：warmup 后每个 rank 交替做一个前向、一个反向；bubble 与 GPipe 相同量级，但每个 rank 最多只保存约 P 个 micro-batch 的激活，显存与 M 无关。
- **Zero Bubble**：把反向拆成 B 与 W，W 可延后填补空泡，bubble 降到 `(PP−1)(F+B−2W)`（ZB1P），更激进的变体（ZB-H2 等）以更多显存换接近 0 的 bubble。
- 公式：1F1B bubble 占比 `(P−1)/(M+P−1)`，增大 M 可以摊薄，但受全局 batch size 与显存限制。
- 加分点：提到 interleaved 1F1B（虚拟 stage）把 bubble 再除以虚拟 stage 数，代价是更多 P2P 通信。

### Q14 — 参考回答要点

- **问题**：跨节点 EP 下，每个 MoE 层前后各一次 all-to-all；讲义：计算与通信约 1:1，不重叠的话 GPU 一半时间在等通信。
- **chunk 拆分**：把前向/反向 chunk 拆成 attention、dispatch、MLP、combine；在一对重叠执行的"前向 chunk + 反向 chunk"中，一个 chunk 在通信时另一个在计算（例如前向的 dispatch 与反向的 attention/MLP 计算同时进行），交替排布让通信被计算覆盖。
- **为什么要双向**：单向流水线里，稳定阶段每个 rank 拿到的前向和反向来自同一方向，能配对重叠的机会少，warmup/cooldown 的空泡也大。从两端同时注入后，每个 rank 都能找到另一个方向的 chunk 来配对，形成 `F&B` 重叠执行，bubble 系数从 `PP − 1` 降到约 `PP/2 − 1`。
- **代价**：两份参数、激活显存 `PP + 1`，以及调度实现复杂。
- 加分点：DeepSeek-V3 报告还提到为通信专门分配少量 SM（约 20 个）并定制跨节点 all-to-all kernel，限制每个 token 最多发往 4 个节点，以控制 IB 流量。

### Q15 — 参考回答要点

- **PP 深度**：先用 TP/EP 确定单个 stage 能放下，再定 P；MoE 前沿训练讲义建议 16–32。P 越大 bubble 越大，不宜超过需要。
- **micro-batch 数**：DualPipe/DualPipeV 要求能被 2 整除（附带 skill 文件建议 M/P 在 8–16 之间）；M 越大 bubble 占比越低，但受全局 batch 和激活显存约束。
- **调度**：EP 通信重、节点间带宽是瓶颈 → DualPipe；参数显存紧张或 EP 较轻 → DualPipeV；没有定制 all-to-all kernel → 先用 Zero Bubble。
- **指标**：逐 rank 的 GPU 利用率 / MFU（讲义强调"Monitor GPU utilization per rank, not just aggregate"）、每步耗时与其中通信未被覆盖的部分（profiler 时间线）、各 rank 显存峰值、tokens/s。
- 常见误区：只看聚合利用率，掩盖了个别慢 rank（straggler）拖累整个流水线的情况。
- 加分点：讲义提醒"第一次实现预计要花一周调试调度"，应先在小规模上用 profiler 验证重叠效果。

### Q16 — 参考回答要点

- **便宜的原因**：MoE 中专家参数占绝大部分，已被 EP 分散到很多卡上，每卡实际持有的参数量很小，复制一份的绝对显存只是几 GB（见 Q12）；而换来的是 all-to-all 几乎完全被遮盖，对计算通信 1:1 的系统收益巨大。
- **改用 DualPipeV 的情形**：稠密模型或 EP 很轻、通信重叠不是主要矛盾；显存紧张；讲义表格"Use when: dense or EP-light"。
- 附带 skill 文件中的规则可作为参考：没有 EP 时不使用 DualPipe；互联不超过 200Gbps 时也推荐 DualPipeV。
- 加分点：说清"参数 2 份"不等于"优化器状态 2 份"的处理方式取决于实现（如与 ZeRO 分片配合），这是讲义提到的"bookkeeping 需要与 ZeRO 协作"。

### Q17 — 参考回答要点

1. **确认瓶颈是否真的是 bubble 与通信**：用 profiler 看时间线，如果原来 1F1B 的空转就不多（M/P 很大），DualPipe 能回收的本来就少。
2. **检查通信是否真的被覆盖**：all-to-all 是否与计算并行（是否占用了足够 SM、是否和计算争抢 SM 导致计算变慢）。
3. **检查 M 与 P 的配置**：M 是否满足调度要求（能被 2 整除、足够大）；warmup/cooldown 是否占了大头。
4. **逐 rank 看利用率**：是否存在 straggler（某些 rank 的专家负载不均，路由不平衡）。
5. **显存**：2 份参数是否导致激活重计算增加、micro-batch 变小，反而抵消收益。
6. **对比实验**：在小规模上固定其它变量，分别测 1F1B、ZB、DualPipe、DualPipeV 的步时。
- 加分点：指出 MoE 负载均衡（如 DeepSeek-V3 的无辅助损失负载均衡）对 all-to-all 时间的影响，以及节点限制路由对跨节点流量的影响。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../05-scaling-distributed/docs/zh.md)：数据并行、张量并行、流水线并行与 ZeRO 的基础。
- [阶段 10 · 14 开放模型：架构详解](../../14-open-models-architecture-walkthroughs/docs/zh.md)：MoE 架构与专家规模。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：理解 dispatch/combine 两次 all-to-all 的来源。
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../../19-capstone-projects/79-pipeline-parallel/docs/zh.md)：亲手实现 GPipe/1F1B 并测量 bubble。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../34-gradient-checkpointing/docs/zh.md)：流水线中激活显存的另一种处理手段。

### 本节被哪些后续内容用到
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：DualPipe 作为 V3 训练系统的一部分。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../18-multi-token-prediction/docs/zh.md)：MTP 模块与主模型共享 embedding/输出头，需要与流水线切分协同放置。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../../19-capstone-projects/48-distributed-fsdp-ddp/docs/zh.md)：与 PP 组合使用的数据并行维度。
- [阶段 19 · 81 端到端分布式训练](../../../19-capstone-projects/81-end-to-end-distributed-train/docs/zh.md)：把多种并行方式组合到一个训练任务中。

### 延伸关键词
`pipeline parallelism` · `GPipe` · `1F1B` · `interleaved 1F1B` · `Zero Bubble (ZB-H1/H2)` · `DualPipe` · `DualPipeV / Cut-in-half` · `Chimera` · `expert parallelism` · `all-to-all` · `computation-communication overlap` · `MFU`
