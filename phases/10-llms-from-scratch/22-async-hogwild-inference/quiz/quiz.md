# 测验 · 异步与 Hogwild! Inference（Async and Hogwild! Inference）

> **阶段 10 · 从零构建 LLM · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 问题背景 | 推理模型动辄生成上万 token；讲义：70B 模型 35 token/s 时 5 万 token 需要约 24 分钟。自回归的串行依赖是硬上限 |
| 2 | 三种并行拓扑 | 投票集成（跑 N 次取多数）、子任务拆分（多 Agent + 协调者）、Hogwild!（N 个 worker 共享一个 KV cache） |
| 3 | Hogwild! 的核心设置 | 同一模型的 N 个实例并发生成，共享**同一个** KV cache，每个 worker 立刻看到其他 worker 写下的 token |
| 4 | 涌现式协作 | 不需要微调：靠一段"你是 N 个实例之一，避免重复劳动"的提示 + 共享 cache，推理模型会自行分工、指出彼此错误、调整计划 |
| 5 | 命名来源 | 来自 Hogwild! SGD（Recht 等，2011）：多个异步 worker 无锁写同一份参数，依赖经验上的收敛而非同步保证 |
| 6 | RoPE 的作用 | RoPE 让注意力只依赖相对位置，已缓存的 K 可以通过旋转（而不是重算整段前向）"挪到"新的相对位置，共享 cache 才可行 |
| 7 | 加速比模型 | Amdahl 形式：`T_serial · ((1 − p) + p/N)` 加协调开销；p 是可并行比例，c 是协调开销 |
| 8 | 与 speculative decoding 的关系 | spec decode 在**单条序列内**并行（草稿 + 验证），Hogwild! 在**多个 worker 之间**并行，二者正交、可叠加 |
| 9 | 适用与不适用 | 适合长推理、可拆成独立子目标、推理型模型、单节点；不适合短对话、不可并行的线性任务、非推理模型、跨节点 |
| 10 | 研究状态 | 讲义：截至 2026 年 4 月仍是研究方法，有开源 PyTorch 实现但尚未进入生产；三个障碍是共享 cache 工程、任务相关性、收益不够大 |

### 核心技能（能动手做到）

- [ ] 说清投票、子任务拆分、Hogwild! 三种并行方式的协调机制与适用问题
- [ ] 用 Amdahl 公式计算给定 `T_serial`、p、c、N 下的理论加速比，并指出加速上限 `1 / (1 − p)`
- [ ] 读懂本节模拟器的"unique progress"度量，识别其中的不公平比较与未使用参数
- [ ] 解释 RoPE 的相对位置性质为什么让"共享并重排 KV cache"成为可能
- [ ] 判断一个推理工作负载是否值得尝试 Hogwild!，并设计两 worker 的实验与判停标准
- [ ] 描述 Hogwild! 与 speculative decoding 组合时的工程难点（共享前缀的扩展与回滚）

---

## 二、基础自测（选择题）

**Q1.** 下列哪项最准确地描述了 Hogwild! Inference？

- A. 用一个小模型起草 token，大模型并行验证
- B. 同一个 LLM 的 N 个实例并发生成，共享同一个 KV cache，彼此即时可见；不需要微调，协作从模型已有的推理能力中涌现
- C. 把一个问题拆成子任务，由协调者分配给不同的专用模型，最后汇总
- D. 跑 N 次独立采样，取多数答案

**Q2.** "Hogwild!" 这个名字来源于：

- A. 一种 GPU 显存分配算法
- B. Mamba 的选择性扫描
- C. 一个多 Agent 框架的商标
- D. Hogwild! SGD：多个异步 worker 无锁地写同一份共享参数，依赖经验收敛而不是同步保证

**Q3.** 按本节代码的公式 `T_serial · ((1 − p) + p/N) + c · N`，`T_serial = 10,000`、p = 0.7、c = 200、N = 4 时的加速比是：

- A. 约 1.80×
- B. 约 2.11×
- C. 约 2.80×
- D. 约 4.00×

**Q4.** 讲义认为 RoPE 让共享 KV cache "变得可行"。背后的关键性质是：

- A. RoPE 没有任何参数，所以不占显存
- B. RoPE 把位置信息加在 embedding 上，只影响第一层
- C. 注意力分数只依赖 query 与 key 的相对位置，因此一段已缓存的 K 可以通过旋转（例如改为旋转 query）来对应新的相对位置，而无需对这些 token 重新做整段前向
- D. RoPE 让所有 token 的位置都相同

**Q5.** 下列哪种场景**最不适合**使用 Hogwild!？

- A. 需要 3 万 token 推理、可以同时尝试多种证明思路的数学题
- B. 需要分情况讨论（case analysis）的长推理任务
- C. 单节点、显存足够放下共享 cache 与多个 worker 激活的部署
- D. 平均 500 token、实时交互的短对话

**Q6.** 忽略协调开销，可并行比例 p = 0.7、N = 4 时 Amdahl 定律给出的加速比上限约为：

- A. 1.43×
- B. 2.11×
- C. 2.80×
- D. 3.33×

**Q7.** 关于 Hogwild! 与 speculative decoding 的关系，正确的是：

- A. 两者是同一种技术的不同名字
- B. Hogwild! 需要先训练一个草稿模型
- C. spec decode 在单条序列内部并行（起草 + 验证），Hogwild! 在多个 worker 之间并行；二者正交，可以叠加，但共享前缀的扩展与回滚需要额外的簿记
- D. 使用 Hogwild! 后就不能再使用 speculative decoding

**Q8.** 本节模拟器中，把 `coordination_weight` 设为 0（两个 worker 都固定写 A），程序仍报告 `speedup vs N=1: 1.04x`，而不是讲义所说的"跌破 1"。原因是：

- A. "unique progress" 只统计同一步内不重复的类别，冗余 token 只是不计数而不会受罚；两个 worker 都在写 A 时，"至少一个写出 A"的概率比单 worker 更高
- B. 两个 worker 用了不同的模型
- C. 模拟器有 bug，导致 coordination_weight 实际不为 0
- D. 冗余 token 会被自动删除并返还步数

---

## 三、动手 / 代码题

**Q9.** 程序 Step 3 的扫描结果：

```text
    coord weight    progress   speedup vs N=1
            0.00         197             1.04x
            0.20         238             1.26x
            0.50         292             1.54x
            0.80         341             1.80x
            1.00         385             2.04x
```

2 个 worker 得到 2.04× 的加速，超过了 worker 数量（"超线性"）。请结合下面的代码解释原因，并给出一个公平的比较方式及其结果。

```python
def decide_next_category(worker, cache, target_per_category):
    if worker.rng.random() < 0.05:
        return "noise"
    counts = cache.counts()
    base = worker.intended
    if worker.rng.random() < worker.coordination_weight:
        candidates = sorted(("A", "B"), key=lambda c: counts[c])
        return candidates[0]
    if worker.rng.random() < 0.1:
        return "coord"
    return base
```

（基线 `r_1` 是 `n_workers=1, coordination_weight=0.8` 的结果，progress = 189。）

**Q10.** 阅读 `decide_next_category` 与 `run_hogwild`，找出至少四处"代码与其文档/讲义描述不一致"或"建模不合理"的地方。提示：看看 `target_per_category` 参数、`coord` token 何时出现、trace 中 `noise` 的标签、以及 N = 4 时会发生什么（N = 4、coordination_weight = 0.8 实测 progress = 397）。

**Q11.** 关于协调开销的公式：

- 讲义写：`T_serial · ((1 − p) + p/N) + c · steps_per_worker`；
- 讲义的例子写：`10000 × (0.3 + 0.7/4) + 200 × 4 = 5550`；
- 代码写：`parallel = T_serial * ((1 - p) + p / N) + c * N`，参数 `steps_per_worker` 传入但未使用。

1. 若按讲义第一个公式、`steps_per_worker = 10000 / 4`，结果是多少？说明什么？
2. 用代码公式完成讲义练习 3：50k token 推理任务（p = 0.8、c = 500、N = 4）与 1k token 对话任务（p = 0.3、c = 200、N = 4）。
3. 讲义称"在 5 万 token 的更长推理问题上，协调开销被摊薄，加速可达 2.5–3×"。若 p = 0.7、N = 4，这个说法成立吗？
4. 如果 N 个 worker 的协调是**并行**发生的，`+ c · N` 是否合理？你会怎么建模？

**Q12.** 讲义练习 5：让每个 Hogwild! worker 内部再做 2-token 的 speculative decoding。请说明：

1. 讲义"3× spec decode × 1.8× Hogwild! ≈ 5.4×"这种直接相乘的估计在什么假设下成立，为什么现实中通常达不到？
2. 两个 worker 都想扩展共享 cache 的同一个前缀时，会出现什么簿记（bookkeeping）问题？草稿被拒绝时又要怎么处理？

---

## 四、面试高频题

**Q13.**（基础必考）有哪些让 LLM 推理"跨序列并行"的方法？请比较投票集成、Tree of Thoughts / 多 Agent 子任务拆分、Hogwild! 三种方式。

**Q14.**（原理深挖）Hogwild! 的多个 worker 共享一个 KV cache 时，每个 worker 看到的 token 顺序可能不同。RoPE 在这里起什么作用？如果模型用的是可学习的绝对位置 embedding，会遇到什么问题？

**Q15.**（工程实践）你要评估"在我们的数学推理服务上上线 Hogwild!"是否值得，请设计实验方案、指标和决策标准。

**Q16.**（场景设计）一个 70B 推理模型，平均每题生成 2 万 token，用户抱怨等待太久。请列出你会考虑的加速手段（单序列内、跨序列、系统层面），并说明 Hogwild! 在其中的位置。

**Q17.**（追问型）Hogwild! 的协作是"涌现"的、没有同步保证。它可能以哪些方式失败？你会如何通过提示词或系统设计来缓解？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："N workers share a single KV cache. Each worker sees every other worker's generated tokens immediately ... The workers — without any training or fine-tuning — figure out how to divide the work." A 是 speculative decoding；C 是多 Agent 子任务拆分；D 是投票集成。

### Q2 — 答案：D

讲义 "The naming"：名字致敬 Recht 等（2011）的 Hogwild! SGD——异步 worker 无锁写共享参数向量；Hogwild! Inference 则是多个 worker 写共享 KV cache，"Both rely on empirical convergence rather than synchronization guarantees"。A、B、C 均为捏造。

### Q3 — 答案：A

`10000 × (0.3 + 0.7/4) + 200 × 4 = 4750 + 800 = 5550`，`10000 / 5550 = 1.80×`（与程序 Step 4 中 p = 0.70、N = 4 一格一致，也与讲义的 "Concrete example" 一致）。B 是不计协调开销的 Amdahl 上限；C、D 是把 p 当成 1 或忽略了串行部分。

### Q4 — 答案：C

RoPE 把位置编码成 Q、K 上的旋转，注意力分数 `q_mᵀ k_n` 只依赖 `m − n`。因此一段已缓存的 K 在别的 worker 眼中处于不同的相对位置时，只要对 query（或 key）做相应旋转即可，不必对这些 token 重新跑一遍前向。可学习的绝对位置 embedding 在输入处就把位置"写进"了每一层的隐藏状态，位置一变，所有层的 K、V 都失效。A 不是关键；B 描述的是绝对位置编码；D 错误。

注意讲义的表述"a token's position can shift without recomputing the KV cache entry ... no re-rotation needed"略有简化：K 在缓存时已按其绝对位置旋转，若要换位置仍需要一次旋转，只是旋转远比重算前向便宜，且可以等价地转移到 query 上做。

### Q5 — 答案：D

讲义 "When not to"："Short interactive chat. Coordination overhead dominates." 500 token 的任务里，几百 token 的协调开销就会吃掉全部收益（见 Q11 中 1k token 任务的 0.63×）。A、B、C 都是 "When to reach for Hogwild!" 列出的有利条件。

### Q6 — 答案：B

`1 / ((1 − 0.7) + 0.7/4) = 1 / 0.475 = 2.105×`（已计算）。N → ∞ 时上限是 `1 / 0.3 = 3.33×`（D）；A 是 `1 / 0.7`；C 无依据。由此可知讲义"5 万 token 时加速可达 2.5–3×"在 p = 0.7、N = 4 下不可能（见 Q11）。

### Q7 — 答案：C

讲义开篇："Speculative decoding parallelizes tokens within one sequence"；"Use It"："each Hogwild! worker can independently use spec decode"；练习 5 也指出共享前缀扩展的簿记问题。A、D 错；B 是 EAGLE/MTP 类方法的要求，Hogwild! 不需要任何额外训练。

### Q8 — 答案：A

coordination_weight = 0 时，每个 worker 每步约 85.5% 的概率写 A（5% noise，剩下的 10% 写 coord）。"unique progress" 每步最多计 1 个 A，所以 N = 2 时每步得分概率是 `1 − (1 − 0.855)² ≈ 0.979`，200 步约 197；而基线是 189。冗余 token 只是"不计分"，没有任何惩罚（不占额外时间、不降低进度），所以加速比恒 ≥ 1。实测 50 个随机种子下 cw = 0 的加速比在 1.005–1.124 之间，从未低于 1。讲义 "Step 5: stress the coordination" 中"speedup drops below 1"在此模拟器里无法复现。B、C、D 都不符合代码。

### Q9 — 参考答案

**原因**：基线与对比组的"协调权重"不同，基线承担了对比组没有的 coord token。

- 在 `decide_next_category` 中，只有**没有**进入协调分支时，才有 10% 的概率写 `coord`。cw = 1.0 时永远走协调分支，**从不**写 coord token；而基线 cw = 0.8，有 `0.95 × 0.2 × 0.1 ≈ 1.9%` 的步数浪费在 coord 上。
- 估算：基线每步有效概率约 `0.95 × (0.8 + 0.2 × 0.9) = 0.931`；cw = 1 时两个 worker 都写工作 token 且类别不同的期望约 `2 × 0.95 = 1.9`（第二个 worker 在同一步内能看到第一个 worker 的写入，按最少填充原则必然选另一个类别）。`1.9 / 0.931 ≈ 2.04`。

**公平比较**：用相同的 coordination_weight 跑 N = 1 与 N = 2。实测 cw = 1.0 时 N = 1 为 193、N = 2 为 385，加速 **1.99×**（不超过 2）；cw = 0 时 N = 1 为 171、N = 2 为 197，加速 **1.15×**。

**启示**：比较并行方案时，基线必须与实验组只差"并行"这一个变量；另外，代码里"协调"本身不花任何 token，这与讲义中"协调开销 c"的设定恰恰相反。

### Q10 — 参考答案

1. **`target_per_category` 从未使用**：docstring 说"if the other worker already produced enough tokens in a category, switch"，但函数里没有任何阈值判断；"切换"只是选当前计数最少的类别。
2. **coord token 的语义颠倒**：coord token 只在"不协调"的分支里出现，协调权重越高 coord token 越少（cw = 1 时为 0，cw = 0 时为 39），与"协调要付出开销"的讲义设定相反；协调本身完全免费。
3. **noise 被标记为 "redundant"**：trace 中 `(1, 'noise', 'redundant')`——noise 不是重复劳动，只是无效 token，标签误导。
4. **"冗余"只在同一步内判定**：两个 worker 在不同步写同一类别都算 "unique"；类别 A/B 没有"做完"的概念，于是并不存在真正的重复劳动。
5. **进度上限等于类别数**：每步最多 2 个 unique（只有 A、B 两类），所以 N = 4、cw = 0.8 实测 progress = 397，相对基线只有 2.10×；增加 worker 毫无意义——这其实是"可并行度 p 有上限"的一个粗糙体现，但代码与讲义都没有说明。
6. **"同时"并不同时**：同一步内 worker 按顺序决策，worker 1 已经能看到 worker 0 本步的写入；真实并发中两者读到的是同一个快照，可能做出相同选择。
7. **单 worker 也在"协调"**：N = 1、cw = 0.8 时 worker 会在 A、B 之间来回切换（类别计数几乎相等：95 / 94），"自己和自己协调"没有意义，只是因为免费才没有代价。我们改写了一个版本（同一步读快照、切换计划要花一个 coord token），N = 1 基线的 progress 从 189 降到 115，说明结论对建模假设非常敏感。
8. 另外 `expected_speedup` 的 `steps_per_worker` 参数也没有被使用（见 Q11）。

### Q11 — 参考答案

1. `10000 × 0.475 + 200 × 2500 = 504,750`，加速比约 0.02×——荒谬。说明讲义第一个公式中的 `c · steps_per_worker` 若把 c 理解成"每步开销"，单位就与例子中"每个 worker 的总开销 200 token"不一致。讲义例子与代码实际用的是 `c · N`。
2. 按代码公式（已计算）：
   - 50k 任务：`50000 × (0.2 + 0.8/4) + 500 × 4 = 20000 + 2000 = 22000`，加速 **2.27×**——划算；
   - 1k 对话：`1000 × (0.7 + 0.3/4) + 200 × 4 = 775 + 800 = 1575`，加速 **0.63×**——比串行还慢。
   原因：协调开销是近似固定的绝对量，长任务中被摊薄；短任务中它与 `T_serial` 同量级，再加上可并行比例低，收益为负。
3. 不成立。p = 0.7、N = 4 时，无论任务多长，加速比都不会超过 Amdahl 上限 2.105×（T = 50k、c = 200 时为 2.04×）。2.5–3× 需要更高的 p（例如 p = 0.9 时 Step 4 中 N = 4 为 2.47×、N = 8 为 2.68×）或更多 worker。
4. 不太合理。如果每个 worker 各自花 c 个 token "读 cache、定计划"，这些工作是**并行**发生的，墙钟时间上更接近 `+ c`（或 `+ c × 协调轮数`），而不是 `+ c · N`。`c · N` 相当于把所有协调串行化，是偏保守的估计。更合理的建模是：每个 worker 的 token 预算 = 自己负责的工作量 + 自身的协调 token，墙钟时间取所有 worker 中最慢的那个；如果协调随 N 增加（要读更多别人的输出），再让 c 随 N 增长。例如只加一次 c 时，讲义例子变为 `10000 / (4750 + 200) ≈ 2.02×`。

### Q12 — 参考答案

1. **直接相乘的前提**：两种加速互不争夺资源、互不影响。现实中：
   - 两者都消耗同一块 GPU 的算力与显存带宽：N 个 worker 并发已经提高了 batch 内的并行度，spec decode 的"空闲算力"红利变小；
   - Hogwild! 的 worker 在同一个共享 cache 上工作，单个 worker 的注意力上下文更长（包含他人的输出），每步更贵；
   - 草稿模型对"混杂了多个 worker 输出"的上下文预测更难，接受率可能下降；
   - 讲义自己也把"组合工程复杂"列为生产化障碍之一。所以 5.4× 只能看作理想上限。
2. **簿记问题**：
   - 两个 worker 若在同一位置之后各自追加 draft token，会出现**写冲突**：共享 cache 中同一"下一个位置"被两份草稿争用；必须为每个 worker 的草稿划分私有的暂存区，验证通过后再提交到共享区。
   - **可见性**：未验证的草稿不应被其他 worker 读到，否则别人会基于可能被拒绝的 token 推理；需要区分"已提交"与"暂存"的 KV。
   - **回滚**：草稿被拒绝时，要截断该 worker 暂存区中对应的 KV；若其他 worker 已经读到过（例如没有做隔离），它们的后续推理也被"污染"，只能接受或回滚，代价很高。
   - **位置**：提交顺序决定其他 worker 看到的相对位置，提交时可能需要利用 RoPE 调整位置。

### Q13 — 参考回答要点

| 方式 | 协调机制 | 适合 | 代价 |
|------|---------|------|------|
| 投票集成（self-consistency） | 无协调，最后多数投票 | 有明确答案的分类/短答案 | N 倍算力，不缩短单条推理时间 |
| ToT / 多 Agent 子任务 | 显式的分支剪枝或协调者 + 消息协议 | 可明确拆分的复杂任务 | 协议开销大，需要设计角色与流程 |
| Hogwild! | 共享 KV cache + 提示词，协作涌现 | 长推理、可拆成独立子目标、推理型模型 | 实验性；需要共享 cache 工程；任务依赖性强 |

- 讲义："These all also introduce explicit coordination machinery" vs Hogwild!"takes a different approach"。
- 加分点：这三者都与 speculative decoding（单序列内并行）正交。

### Q14 — 参考回答要点

- 共享 cache 中，每个 worker 需要把"别人的进度"和"自己的进度"放进自己的上下文；不同 worker 看到的拼接顺序不同，于是同一个缓存 token 在不同 worker 眼中处于不同的相对位置。
- **RoPE**：注意力分数只依赖相对位置差 `m − n`。缓存的 K 不必重算，只要对 query（或 K）施加对应位移的旋转，就能让同一份缓存以不同的相对位置参与注意力——一次旋转远比重跑整段前向便宜。
- **绝对位置 embedding**：位置在输入层被加到 token embedding 上，之后每一层的隐藏状态、K、V 都依赖这个绝对位置。位置一变，整段 token 在所有层的 K、V 都要重算；讲义："In a learned-position or absolute-position model, Hogwild! would need cache invalidation on every concurrent write."
- 加分点：这与"位置插值 / 上下文扩展"依赖 RoPE 相对性质的原理相同；也说明论文实现细节（如何组织各 worker 的 cache 块）应以论文与参考实现为准。

### Q15 — 参考回答要点

- **先画像**：统计历史推理轨迹中"探索性"token（多种思路、分情况讨论、搜索）的比例，作为 p 的粗估（讲义 "Pragmatic adoption path" 第 1 步）。
- **两 worker 实验**：同一批题目，比较单 worker 与 2 个 Hogwild! worker 的墙钟时间、正确率、总 token 数（总算力）。
- **决策标准**（讲义）：提升 < 1.3× → 处于协调主导区，回退单 worker；> 1.5× → 尝试 N = 4 再测，收益递减通常出现在 N = 4–8。
- **还要看**：正确率是否下降（worker 互相干扰）、尾延迟、GPU 显存（每个 worker 的激活 + 共享 cache）、单节点限制。
- 常见误区：只看平均加速，不看正确率与总算力；用非推理模型做实验（讲义：不会涌现协作）。

### Q16 — 参考回答要点

- **单序列内**：speculative decoding（EAGLE/MTP 草稿，讲义称约 3–5×）；KV cache 量化与 GQA/MLA 降低带宽压力；更快的 kernel（FlashAttention 等）。
- **跨序列**：Hogwild! 多 worker 共享 cache（实验性，适合可拆分的长推理，按 Amdahl 估算收益）；投票类方法不降低延迟。
- **系统层面**：更高带宽的硬件、张量并行降低单 token 延迟、FP8 权重；控制推理长度（预算提示、提前停止）；对简单题路由到小模型。
- **Hogwild! 的位置**：在 spec decode 等成熟手段之后、作为"把串行推理拆成并行子目标"的探索方向；先做两 worker 小实验验证。
- 常见误区：把吞吐优化（大 batch）当成延迟优化。

### Q17 — 参考回答要点

- **可能的失败方式**：
  - 重复劳动：多个 worker 同时选了同一子问题（尤其在彼此还没写出计划时）；
  - 互相干扰：一个 worker 的错误推理被其他 worker 采信，错误传播；
  - 计划冲突 / 无人收尾：各做各的，没有人汇总出最终答案；
  - 协调过度：大量 token 花在"读别人、写计划"上，c 变大，收益消失；
  - 非推理模型或任务不可拆分时根本不出现分工。
- **缓解**：
  - 提示词要求先写出简短计划并声明负责的部分，定期检查重复（讲义：被提示检查冗余时 worker 能发现并转向）；
  - 要求对他人结论进行复核后再引用；
  - 指定一个 worker 负责最终汇总，或设定"达成一致后停止"的规则；
  - 系统层面限制 worker 数量（N = 2–4），监控重复度与协调 token 占比，超过阈值回退单 worker。
- 讲义练习 4 要求阅读论文第 4 节，找出作者报告的两种失败模式并设计缓解，答题时以论文原文为准。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：KV cache、prefill/decode 与推理瓶颈。
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../15-speculative-decoding-eagle3/docs/zh.md)：单序列内并行，与 Hogwild! 正交。
- [阶段 07 · 04 位置编码 — 正弦、RoPE、ALiBi](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：理解 RoPE 的相对位置性质。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：共享 KV cache 的基础。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：思维链与思维树。

### 本节被哪些后续内容用到
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：显式分支搜索，与 Hogwild! 的隐式协作对照。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../../16-multi-agent-and-swarms/09-parallel-swarm-networks/docs/zh.md)：多 Agent 层面的并行拓扑。
- [阶段 16 · 13 共享记忆与黑板模式](../../../16-multi-agent-and-swarms/13-shared-memory-blackboard/docs/zh.md)：共享 KV cache 可以看作"黑板"在模型内部的版本。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../../16-multi-agent-and-swarms/15-voting-debate-topology/docs/zh.md)：投票集成与自洽性。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../../17-infrastructure-and-production/06-sglang-radixattention/docs/zh.md)：多请求共享 KV 的工程实现。

### 延伸关键词
`Hogwild! Inference` · `shared KV cache` · `emergent coordination` · `Hogwild! SGD` · `Amdahl's law` · `RoPE relative position` · `self-consistency` · `Tree of Thoughts` · `multi-agent` · `speculative decoding` · `parallel reasoning`
