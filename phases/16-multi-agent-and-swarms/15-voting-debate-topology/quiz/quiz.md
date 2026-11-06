# 测验 · 投票、自洽性与辩论拓扑（Voting, Self-Consistency, and Debate Topology）

> **阶段 16 · 多智能体与集群 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机器翻译（如 topology 被译成"地形"、rounds 被译成"发子弹"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Self-consistency | Wang et al. 2022：同一模型在 temperature > 0 下采样 N 次，对推理路径的最终答案多数投票；讲义：GSM8K 上 N = 40 比单次贪婪解码有显著提升 |
| 2 | Self-consistency 的天花板 | 只有一个基座模型，错误"by construction"相关；模型有系统性偏差时，N 个样本都共享 |
| 3 | 异构多 agent 投票 | 用不同基座模型、不同 prompt、不同工具/上下文的 N 个 agent 代替 N 次采样，换取"不相关的错误"；讲义称这类异构对抗辩论为 A-HMAD |
| 4 | 四种拓扑 | star（只与 hub 通信）、chain（每个 agent 看到前一个的输出）、tree（层级）、graph（任意对任意） |
| 5 | MultiAgentBench（MARBLE，ACL 2025） | 讲义：graph 在研究类任务最好；star 在快速事实类任务最好；chain 在分步流水线最好；graph 拓扑超过约 4 个 agent 出现 coordination tax |
| 6 | Coordination tax | agent 数增加后，时延和 token 成本比质量增长得更快；讲义认为 4-agent 上限是经验性的，反映了上下文被同伴输出填满 |
| 7 | "Should we be going MAD?" | 讲义：结构上与 self-consistency 类似的 MAD 变体，在**同等预算**下常常输给 self-consistency；MAD 只在 agent 真正异构且有对抗结构时最有帮助 |
| 8 | AgentVerse 的两种涌现行为 | volunteer（主动揽活）与 conformity（向 critic 妥协，即使 critic 错了）；conformity 是"辩到一致为止"奖励霸凌者的原因 |
| 9 | 异构性 > 数量 | 讲义：把 N 个 agent 中的一个换成不同基座模型，比 N + 1 更能提升准确率；"三个不同模型胜过同一模型的五个副本" |
| 10 | 何时用 / 不用投票 + 辩论 | 有客观答案、可获得异构性、轮数有界（2–3）且有独立 judge、预算 3–5 个 agent 时用；观点类问题、同一基座、轮数无界、任务简单时不用 |

### 核心技能（能动手做到）

- [ ] 写出 self-consistency 的最小实现，并用二项分布手算"N 个独立、准确率 p 的投票者多数投票"的准确率
- [ ] 用标准库模拟 star / chain / tree / graph 四种拓扑，统计准确率与 token 成本
- [ ] 识别模拟器中的建模缺陷：错误是否真的相关、平局如何处理、辩论轮是否真的改变结果
- [ ] 用"共享隐变量"模拟相关错误，复现"同质 agent 加多少都突破不了天花板"的现象
- [ ] 根据任务类型（研究 / 快速事实 / 分步精炼 / 观点）选择拓扑、N、异构配置和轮数上限
- [ ] 判断一份实验输出是否足以支持结论（样本量、标准误、对照组）

---

## 二、基础自测（选择题）

**Q1.** Wang et al. 2022 的 self-consistency 方法是：

- A. 让多个不同的模型各回答一次，再由 judge 选择最好的回答
- B. 同一个模型在 temperature > 0 下采样多条推理路径，对最终答案做多数投票
- C. 让同一个模型反复修改自己的答案直到不再变化
- D. 用 temperature = 0 贪婪解码 N 次，取最长的推理链

**Q2.** 根据讲义转述的 MultiAgentBench 结果，在"快速事实类"任务上表现最好的拓扑是：

- A. graph
- B. chain
- C. tree
- D. star

**Q3.** 讲义说"swapping one of your N agents for a different base model gives a bigger accuracy bump than increasing N by 1"，最根本的原因是：

- A. 每增加一个独立的错误来源，比再增加一个与已有成员相关的样本更有价值
- B. 不同的基座模型参数量更大
- C. 增加 N 会让 token 成本翻倍
- D. 不同模型的输出格式不同，更容易聚类

**Q4.** 讲义引用 "Should we be going MAD?"（arXiv:2311.17371）的主要发现是：

- A. 多 agent 辩论在任何预算下都优于 self-consistency
- B. 辩论轮数越多准确率越高
- C. 结构上类似 self-consistency 的 MAD 变体，在同等预算下常常不如 self-consistency
- D. 只要使用 graph 拓扑，MAD 就一定有效

**Q5.** 阅读本节代码的 `run_graph`：第一轮各自作答；之后每一轮中，与当前多数不同的 agent 以 0.4 的概率改投多数；最后取多数。关于它的最终答案，下列说法正确的是：

- A. 辩论轮让少数派有机会说服多数派，因此常常改变结果
- B. 由于 0.4 的随机性，最终答案与初始多数不同的概率约 40%
- C. 轮数越多，最终答案越可能是正确答案
- D. 最终答案总是等于第一轮的初始多数（已在 30,000 次对照中验证零例外），辩论轮从不改变结果

**Q6.** 本节代码中 chain 拓扑的准确率在 N = 3、5、7 时都停在约 0.72（20,000 次试验：0.720 / 0.721 / 0.724），原因是：

- A. 更新规则 `proposal != current and rng.random() < a.base_accuracy` 不看提案是否正确，链条最终只相当于"最后几个 agent 的随机接力"，没有任何聚合效果
- B. chain 的 token 成本太高
- C. 每个 agent 的准确率恰好都是 0.72，所以任何拓扑都只能达到 0.72
- D. chain 拓扑会把错误放大，所以 N 越大越差

**Q7.** 代码 Takeaways 写道 "graph/N=7 shows coordination tax: tokens inflate ~7x over star/N=3"。根据实际输出（graph N=7 平均 5600 tokens，star N=3 平均 1200 tokens），实际倍数约为：

- A. 7 倍
- B. 4.7 倍
- C. 2.3 倍
- D. 14 倍

**Q8.** 本节代码中 `run_tree` 在 N = 5 时（4 个叶子分成左右各 2 个，先组内多数、再对两个组结果多数），其最终答案等价于：

- A. 4 个叶子的严格多数
- B. root 自己的答案
- C. 第一个叶子 agent 的答案——因为 2 票平局时 `majority` 取先出现的那个，左组结果总是 `leaves[0]`，顶层 2 票平局又总取左组
- D. 随机选一个叶子的答案

---

## 三、动手 / 代码题

**Q9.** `majority` 的实现：

```python
def majority(items: list[str]) -> str:
    counts: dict[str, int] = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    return max(counts, key=counts.get)
```

1. 平局时返回什么？
2. 结合 `run_star`（hub 不投票，只统计 N − 1 个 worker）与 `run_tree`，解释为什么 star N = 3、tree N = 3、tree N = 5 的准确率都约等于单个 agent 的准确率（同质组 20,000 次试验：0.724、0.724、0.724）。
3. 给出两种修复思路。

**Q10.** 讲义说"Graph wins at N=3-5 on the research-style tasks"。在本节代码的同质组中，graph 的准确率（20,000 次试验）是 0.809 / 0.866 / 0.899，star 是 0.724 / 0.810 / 0.865。

1. 手算 N 个独立投票者（每人准确率 0.72，错误答案只有一种）的多数投票准确率，N = 3、5、7。与 graph 的数据比较，你发现了什么？
2. 于是 graph 比 star 好的真正原因是什么？它能证明"任意对任意的辩论更好"吗？
3. 代码里还有哪些讲义承诺的东西没有实现？

**Q11.** 本节代码的同质组（"HOMOGENEOUS (monoculture)"）和异质组只有两点区别：错误标签（全是 `WRONG-A` vs 轮流 `WRONG-A/B/C`）和准确率列表。每个 agent 每次都用 `rng.random()` **独立**抽签。

1. 这能模拟讲义所说的 monoculture（相关错误）吗？异质组准确率更高的真实机制是什么？
2. 写一个带相关系数 `rho` 的投票模拟：每次试验先抽一个"共享"结果，每个 agent 以概率 `rho` 直接采用共享结果，否则独立抽签。报告 `p = 0.72` 时 `rho = 0, 0.5, 0.8, 1.0` 下 N = 3、5、7、15 的多数投票准确率，并解释现象。

**Q12.** 检查代码 Takeaways 的四条结论与本次实际输出（每格 200 次试验）是否一致：

1. "heterogeneous ensembles outperform homogeneous at every topology/N."
2. "graph/N=7 shows coordination tax."
3. "chain underperforms on monoculture because one bias propagates along the chain."
4. 另外，200 次试验下准确率的标准误大约是多少？哪些"差异"根本不显著？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 self-consistency？它和多 agent 投票、多 agent 辩论有什么关系？

**Q14.**（原理深挖）为什么"跑 5 个 agent 然后投票"经常比单个 agent 还差？请从相关错误、拓扑、轮数、conformity 几个角度回答。

**Q15.**（场景设计）分别为以下三个任务选择拓扑、agent 数、异构配置和轮数：①客服知识库的事实问答；②写一份竞品调研报告；③把需求逐步转成代码再测试。

**Q16.**（工程实践）你要向老板证明"异构 3-agent 投票"值得比"单模型 self-consistency N=5"多花钱。你会怎么设计实验？

**Q17.**（追问型）讲义说 graph 拓扑超过约 4 个 agent 就有 coordination tax。这个 4 是从哪来的？换了更强的模型或更长的上下文，它会变吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："sampled the same model N times at temperature > 0 and majority-voted on reasoning-path answers"。A 是多模型 + judge；C 类似 Self-Refine；D 中 temperature = 0 的贪婪解码 N 次结果完全一样，投票没有意义。

### Q2 — 答案：D

讲义："Star wins on fast-answer factual tasks. Hub filters and consolidates." graph 赢在研究类，chain 赢在分步流水线，tree 讲义没有给出"最优任务"。

### Q3 — 答案：A

讲义："The intuition is monoculture — each new independent-error source is worth more than an additional correlated sample." 投票的收益来自"错误互相抵消"，相关的样本会一起错，抵消不了。B、D 与此无关；C 是成本问题，不是准确率提升的原因。

### Q4 — 答案：C

讲义："MAD variants that are *structurally similar* to self-consistency (independent sampling + aggregation) often underperform self-consistency when using the same budget. MAD helps most when agents are genuinely heterogeneous and the debate has adversarial structure." A、D 与该结论相反；B 与讲义"bounded rounds"的建议相反——轮数越多 conformity 越强。

### Q5 — 答案：D

更新规则只允许"少数派改投多数"，多数派的票只增不减，所以第一轮的多数永远保持多数。用同一随机种子对照 30,000 次（N ∈ {3, 5, 7} × 同质/异质 × 5,000 个种子），`run_graph` 的结果与"初始答案的多数"不一致的次数为 **0**。辩论轮在本模拟中只是"花 token"，A、B、C 都不成立。这也意味着代码没有模拟出 conformity 的危害（跟风错误的多数），也没有模拟出辩论的好处（被正确论证说服）。

### Q6 — 答案：A

`current = proposal if proposal != current and rng.random() < a.base_accuracy else current`：只要提案与当前不同，就以 `base_accuracy` 的概率换成提案——**不管提案对不对**。同质组中：当前正确 → 变错的概率 `0.28 × 0.72 ≈ 0.20`；当前错误 → 变对的概率 `0.72 × 0.72 ≈ 0.52`。这是一个两状态马尔可夫链，平稳分布中正确的概率 `0.52 / (0.52 + 0.20) = 0.72`，恰好等于单个 agent 的准确率。C 错，graph/star 能超过 0.72；D 错，200 次试验看到的"N=7 降到 0.71/0.69"只是噪声（标准误约 0.03）。

### Q7 — 答案：B

`5600 / 1200 ≈ 4.67`。graph 两轮共 `2 × N` 次调用：`2 × 7 × 400 = 5600`；star N = 3 是 `3 × 400 = 1200`。Takeaway 的 "~7x" 与输出不符。而且 graph 的准确率随 N 单调上升（同质 0.82 → 0.91 → 0.92，异质 0.89 → 0.95 → 0.99），token 只是线性增长，**并没有出现"成本比质量增长得更快"的拐点**——代码没有演示出 coordination tax。

### Q8 — 答案：C

N = 5 时 `leaves` 有 4 个，`mid = 2`。左组 `majority([l0, l1])`：若两者一致就是它，不一致时平局取先出现的 `l0`——总之等于 `l0`。右组同理等于 `r0`。顶层 `majority([L, R])` 不一致时平局取 `L`。所以结果恒等于第一个叶子的答案，准确率 = 单个 agent（20,000 次试验 0.724）。root 只计了 token，没有参与决策。

### Q9 — 参考答案

1. `max(counts, key=counts.get)` 遍历字典的键，字典保持插入顺序，平局时返回**最先出现**的答案。
2. 偶数个投票者时平局频繁，而平局总是倒向"列表里第一个人"：
   - star N = 3：hub 不投票，只有 2 个 worker；不一致时取 `workers[0]`，等价于单人。
   - tree N = 3：两个叶子各成一组，顶层 2 票平局取左，等价于 `leaves[0]`。
   - tree N = 5：见 Q8。
   所以这三种配置的准确率都约等于单个 agent 的 0.72。同理 star N = 5 只有 4 个 worker，实测 0.810，恰好等于"3 人多数"的 0.809。
3. 修复思路：
   - **让 hub/root 也投票或负责打破平局**：例如 star 中 `majority(answers + [hub.answer(...)])`，tree 中 root 在两组不一致时自己作答；
   - **平铺多数 + 显式平局策略**：tree 改为对全部叶子答案直接多数（实测同质组 N = 5、7 提升到 0.810、0.865），平局时随机选择或升级给 judge，并记录平局次数。
   - 原则：拓扑实验中，"谁投票、平局怎么破"必须一致，否则比较的是计票规则而不是拓扑。

### Q10 — 参考答案

1. 多数投票准确率 `P = Σ_{k > N/2} C(N, k) p^k (1−p)^{N−k}`，`p = 0.72`：
   - N = 3：`0.72³ + 3 × 0.72² × 0.28 ≈ 0.809`
   - N = 5：≈ 0.862
   - N = 7：≈ 0.898
   与 graph 的 0.809 / 0.866 / 0.899 几乎一致——**graph 就是"N 个人的一次性独立投票"**（见 Q5），辩论轮没有任何作用。
2. graph 比 star 好，是因为 graph 让**全部 N 个**agent 投票，而 star 的 hub 不投票，只有 N − 1 个 worker。star N = 5、7 的 0.810、0.865 恰好对应 3 人、5 人多数（偶数个 worker 的平局又损失了一票）。这只是"投票人数"差异，不能证明"任意对任意的辩论更好"。
3. 未实现的部分：
   - 讲义说会报告 `(accuracy, total_tokens, wallclock_simulated)`，代码只有 `steps`，且是写死的常数（star 2、tree 3、graph 4、chain N），没有时延模型；
   - 讲义说"研究类任务 graph 赢、快速事实类 star 赢"，代码只有一种任务，没有任务类型之分；
   - 没有 judge、没有对抗角色、没有 A-HMAD（这些留给练习 2、3）。

### Q11 — 参考答案

1. 不能。每个 agent 每次都独立抽签，同质组的错误**并不相关**，只是"错得一样"（都投 `WRONG-A`）。异质组更高的真实机制是**错误票被分散**：错的人分投 A/B/C 三个标签，正确答案只需要相对多数就能赢。例如 N = 5 中 2 对 3 错，同质组 3 张错票都投 `WRONG-A`，错误答案赢；异质组 3 张错票可能分成 A/B/C 各 1 张，正确答案以 2 票胜出。这是"vote splitting"，不是讲义所说的"不相关错误"。顺带一提，`make_agents` 里创建的 `rng = random.Random(seed)` 从未被使用。
2. 参考实现（已运行，每格 20,000 次试验）：

```python
def plurality_corr(n, rho, p, trials=20000, seed=0):
    rng = random.Random(seed); ok = 0
    for _ in range(trials):
        shared = rng.random() < p                      # 共享的"模型级"结果
        votes = []
        for _ in range(n):
            if rng.random() < rho:
                votes.append("RIGHT" if shared else "WRONG-A")
            else:
                votes.append("RIGHT" if rng.random() < p else "WRONG-A")
        ok += majority(votes) == "RIGHT"
    return ok / trials
```

| rho | N=3 | N=5 | N=7 | N=15 |
|-----|-----|-----|-----|------|
| 0.0 | 0.809 | 0.864 | 0.898 | 0.966 |
| 0.5 | 0.766 | 0.774 | 0.774 | 0.752 |
| 0.8 | 0.734 | 0.732 | 0.725 | 0.716 |
| 1.0 | 0.720 | 0.725 | 0.717 | 0.714 |

解释：独立时（rho = 0）增加 N 稳定提升；一旦错误相关，N 再大也停在约 `p` 附近的天花板——当共享结果出错时，大部分 agent 会一起错。这就是讲义"heterogeneity beats numerosity"和 self-consistency 天花板的定量版本：要提升准确率，应该降低 rho（换基座模型、换 prompt、换信息源），而不是加 N。

### Q12 — 参考答案

1. **不成立**。本次输出中：star N=3（异质 0.75 vs 同质 0.76）、chain N=5（0.73 vs 0.78）、chain N=7（0.69 vs 0.71）、tree N=3（0.75 vs 0.76）、tree N=5（0.75 vs 0.76）异质组都更低。20,000 次试验下 star N=3 与 tree N=3、5 异质组仍更低（0.705 vs 0.724），原因是异质组里 `agent-1` 的准确率是 0.70。
2. **不成立**。graph 的准确率随 N 单调上升，token 线性增长，没有"成本比质量增长更快"的拐点；倍数是 4.7 而非 7（见 Q7）。
3. **不成立**。chain 在异质组同样差（0.69），而且 chain 的问题与"偏差传播"无关，而是更新规则不看对错，链条准确率收敛到单人水平（见 Q6）。
4. 标准误 `sqrt(p(1−p)/n)`：p ≈ 0.8 时 `sqrt(0.16/200) ≈ 0.028`，p ≈ 0.72 时约 0.032。chain 的 0.75 → 0.71、同质 vs 异质的 ±0.01 差异都在 1 个标准误以内，不能据此下结论。应增加试验次数（例如 20,000 次）或报告置信区间。

### Q13 — 参考回答要点

- **self-consistency**：单模型、temperature > 0 采样 N 条推理路径、对最终答案多数投票（Wang 2022）；本质是"用采样多样性代替模型多样性"。
- **与多 agent 投票的关系**：多 agent 投票是它的异构扩展——把 N 次采样换成 N 个不同的 agent（不同基座、prompt、工具），目的是降低错误相关性。
- **与辩论的关系**：辩论（MAD）在投票之外加入多轮互相批评；讲义引用的综述指出，结构上与 self-consistency 相似的辩论在同等预算下常常不如 self-consistency。
- **工程建议（讲义 Ship It）**：先做 self-consistency N=5 基线 → 准确率重要时升级到异构 N=3 投票并测量增益 → 只有任务有结构（研究、多步）且轮数可控时才上辩论拓扑。
- 加分点：self-consistency 只适用于答案可比较/可聚类的任务；开放式生成需要 judge 或 universal self-consistency 之类的变体。

### Q14 — 参考回答要点

- **相关错误**：5 个 agent 同一基座，错误高度相关，投票只是把同一个偏差复制 5 次（见 Q11：rho = 0.8 时 N 从 3 加到 15，准确率反而从 0.734 降到 0.716）。
- **拓扑**：chain 中后面的 agent 可能覆盖前面正确的答案；star 若 hub 只是转述，hub 本身成为单点；graph 让每个 agent 上下文被同伴输出淹没，即 coordination tax。
- **轮数**：讲义："Rounds are unbounded. Conformity wins every time." 轮数越多，越趋同于最响亮/最自信的声音。
- **conformity**：AgentVerse 观察到 agent 会向 critic 妥协，即使 critic 是错的。
- **任务不适合**：观点类问题没有客观答案，投票只会收敛到"看起来最自信的答案"；简单任务上多 agent 只是增加成本。
- 加分点：计票细节也会导致退化——偶数票平局、hub 不投票等（本节代码 star N=3 就退化为单人）。

### Q15 — 参考回答要点

| 任务 | 拓扑 | N | 异构 | 轮数 / 聚合 |
|------|------|---|------|------------|
| ①客服事实问答 | star（或直接单 agent + self-consistency） | 3 | 至少 1 个不同基座；或单模型 N=5 采样 | 1 轮投票；低于阈值升级人工 |
| ②竞品调研报告 | graph | 3–5（graph 超过约 4 注意 coordination tax） | 3 个不同基座、不同检索源 | 最多 2–3 轮互评 + 独立 judge 打分，不让 judge 投票 |
| ③需求 → 代码 → 测试 | chain（或 tree 做分治） | 每个阶段 1 个，必要时阶段内投票 | 实现者与 reviewer 用不同模型 | 每个阶段有可执行的验证门（测试），而不是靠投票 |

- 依据：讲义与 skill 文件的映射——research → graph、fast-factual → star、stepwise-refinement → chain；观点类则不投票，单 agent + 人决策。
- 常见误区：给研究任务用 star（丢失任意对任意的批评，skill 文件列为硬拒绝）；在 graph 上堆 10 个以上 agent。

### Q16 — 参考回答要点

- **基线**：单模型 self-consistency N=5（讲义 Ship It 推荐的"cheap baseline"）。
- **实验组**：异构 3-agent 投票（3 个不同基座），保持同样的 prompt 与评测集。
- **评测集**：有客观答案的真实业务题，数量足够（几百到上千题），并按难度/类别分层。
- **指标**：准确率（附置信区间或配对检验，如 McNemar）、每题 token 成本、P50/P95 时延；以及少数簇中"少数派其实是对的"的比例（讲义："When a minority is persistently right, you have a diversity signal."）。
- **错误相关性分析**：统计两两 agent 同时出错的比例；异构组的共错率应显著更低，这是收益的来源。
- **结论表述**：讲义——"'Better accuracy at 10x cost' is a business decision."，给出"每提升 1 个百分点的成本"，由业务方决策。
- 常见误区：只跑几十道题、只报一个准确率数字（本节代码 200 次试验的 ±0.03 噪声就足以制造假结论）。

### Q17 — 参考回答要点

- **来源**：讲义转述 MultiAgentBench 的经验结果，并明确说 "The 4-agent ceiling is empirical, not fundamental. It reflects 2026 LLM context capacity"。
- **机制**：graph 中每个 agent 都要读其他所有 agent 的输出，消息量随 N² 增长；上下文被同伴输出填满，边际 agent 带来的新信息越来越少，而 token 与时延持续增加。
- **会不会变**：会。上下文更长、长上下文利用能力更强、或改用摘要/黑板式路由（只推送相关内容，见阶段 16 · 13）都会推高这个上限；但只要信息流是全连接，N² 的成本结构不变，拐点只是后移。
- **工程做法**：不要迷信"4"，在自己的任务上画"准确率 vs N、token vs N"曲线找拐点（讲义练习 1）；超过拐点就改用层级（tree）或分组 graph。
- 加分点：指出本节代码的模拟并没有复现 coordination tax——graph 准确率随 N 单调上升、token 线性增长——要复现它，需要建模"上下文过载导致单个 agent 准确率随 N 下降"。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../07-society-of-mind-debate/docs/zh.md)：讲义列出的先修课，Du 2023 多 agent 辩论的基本形式。
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../14-consensus-and-bft/docs/zh.md)：讲义列出的先修课，monoculture 与 sycophancy 攻击、置信度加权聚合。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：star 拓扑就是没有回传通道的 supervisor-worker。
- [阶段 16 · 06 层级架构及其失效模式](../../06-hierarchical-architecture/docs/zh.md)：讲义说 tree 拓扑用于层级 agent 系统（"Lesson 06"）。
- [阶段 14 · 25 多 Agent 辩论与协作](../../../14-agent-engineering/25-multi-agent-debate/docs/zh.md)：单 agent 工程视角下的辩论实现。
- [阶段 02 · 11 集成方法](../../../02-ml-fundamentals/11-ensemble-methods/docs/zh.md)：投票集成与基学习器多样性。

### 本节被哪些后续内容用到
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：conformity 与 groupthink 的系统化分析（讲义正文写作"Lesson 24"，按索引实际是第 23 节）。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：MultiAgentBench 等协调基准的评测方法。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：graph 拓扑在 swarm 中的扩展。
- [阶段 16 · 25 案例研究与 2026 年前沿进展](../../25-case-studies-2026-sota/docs/zh.md)：生产系统中的拓扑选择案例。

### 延伸关键词
`self-consistency` · `universal self-consistency` · `MAD` · `A-HMAD` · `MultiAgentBench / MARBLE` · `coordination tax` · `star / chain / tree / graph` · `AgentVerse volunteer / conformity` · `jury (Sibyl)` · `vote splitting` · `error correlation` · `Condorcet jury theorem`
