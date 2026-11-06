# 测验 · 面向 Agents 的共识与拜占庭容错（Consensus and Byzantine Fault Tolerance for Agents）

> **阶段 16 · 多智能体与集群 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机器翻译，质量较差（如把 sycophantic conformity 译成"阳极合身"、monoculture 译成"与性关系严重的单一文化"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 经典 BFT（PBFT） | Castro & Liskov（OSDI 1999），三阶段（pre-prepare、prepare、commit）+ 签名消息 + quorum certificate；需要 `n ≥ 3f + 1`，即最多容忍 `f < n/3` 个拜占庭节点 |
| 2 | PBFT 的三个隐含假设 | ①故障相互独立；②诚实节点的输出本身是对的，协议只负责"对齐分歧"；③问题有客观正确答案。LLM agent 三条全都违反 |
| 3 | 三种 LLM 特有攻击 | **byzantine lie**（故意说谎）、**sycophantic conformity**（看别人答案后跟风）、**correlated-error monoculture**（同一基座模型犯同样的错，形成"虚假多数"） |
| 4 | CP-WBFT | 每票附带 confidence probe（自报概率或独立校准模型预测），按置信度加权；讲义："+85.71% BFT improvement on complete graphs"；主要缓解跟风（跟风者往往置信度低） |
| 5 | DecentLLMs | 无 leader：worker 并行提案、evaluator 打分，取打分位置的 geometric median；讲义称在 `f < n/2` 时稳健 |
| 6 | WBFT | 按回答质量 + 历史信任分加权；Hierarchical Structure Clustering 把 agent 分成 Core 与 Edge，Core 先达成共识，Edge 跟随，控制延迟 |
| 7 | "Can AI Agents Agree?" 的发现 | 讲义：无对手时标量问题分歧率在很多基准上超过 30%；一个欺骗性人设的 agent 可把 Mixture-of-Agents 共识拉离诚实基线 40+ 个百分点；异构集成分歧多但漂移慢 |
| 8 | 最小 LLM-BFT 轮次 | 各自作答 + 置信度 → 语义聚类 → 簇权重 `w(C) = Σ c_i` → 最大簇超过 `threshold × Σc` 才接受，否则重试/升级 → 少数簇连同 provenance 记日志 |
| 9 | 阈值与轮数 | 讲义经验：`n = 5–7` 时阈值 0.5–0.67，`n` 越小阈值越高；辩论轮数限 2–3 轮，"辩到一致为止"会奖励跟风 |
| 10 | 一致 ≠ 正确 | BFT 只负责对齐输出，不保证对齐后的输出正确；monoculture 只能靠**多样性**或**独立 verifier**解决 |

### 核心技能（能动手做到）

- [ ] 给定 `n` 算出 PBFT 能容忍的最大拜占庭数 `f = ⌊(n−1)/3⌋`，并解释 `3f + 1` 的由来
- [ ] 手算 plurality、CP-WBFT（含阈值判断）在任一投票场景下的结果
- [ ] 读懂本节 `decentllms` 的打分公式，指出它与"geometric median"的差距以及置信度大小被忽略的问题
- [ ] 构造能区分三种聚合器的投票场景（例如 3 个低置信度跟风者 vs 2 个高置信度独立者）
- [ ] 为聚合器加入"弃权（abstention）"处理，并说清弃权应如何计入分母
- [ ] 为一个真实多 agent 集成设计共识协议：聚类方法、加权、阈值、升级策略、多样性要求、独立 verifier

---

## 二、基础自测（选择题）

**Q1.** 一个 PBFT 集群有 `n = 7` 个节点，它最多能容忍多少个拜占庭节点？

- A. 1
- B. 3
- C. 2
- D. 6

**Q2.** "三个 agent 共用同一个基座模型，一起幻觉出同一个错误答案"——这种 monoculture 主要违反了 PBFT 的哪条假设？

- A. 故障相互独立（Byzantines do not coordinate / faults are independent）
- B. 消息必须签名
- C. 网络最终会把消息送达
- D. 节点数必须是奇数

**Q3.** 本节代码的 monoculture 场景：`42%` 三票，置信度 0.70、0.68、0.72；`4.2%` 两票，置信度 0.85、0.82；`threshold = 0.5`。`cp_wbft` 的结果是：

- A. 返回 `None`（低于阈值被拒绝），因为两簇权重接近
- B. 返回 `4.2%`，因为该簇平均置信度更高
- C. 返回 `4.2%`，因为置信度加权会自动惩罚大簇
- D. 返回 `42%`，权重 2.10 对 1.67，占比约 0.557 ≥ 0.5

**Q4.** 关于本节代码中 `decentllms` 的打分 `len(cluster) * max(0, 1 - Σ|c_i − median|)`，下列说法正确的是：

- A. 它在答案的 embedding 空间里计算 geometric median
- B. 它只看簇大小和簇内置信度的离散程度，置信度本身高低完全不影响分数
- C. 它等价于 CP-WBFT 的加权求和
- D. 它保证 `f < n/2` 时一定选对

**Q5.** 本节 `Vote.canonical()` 只保留字母数字、`.` 和 `%`。一个使用欧洲小数写法的 agent 回答 `"4,2%"`，它会被归入哪个簇？

- A. `42%` 簇——逗号被删除，正确答案被并进了错误答案
- B. `4.2%` 簇——逗号被自动转换为小数点
- C. 单独的 `4,2%` 簇
- D. 抛出异常

**Q6.** 讲义 Ship It 要求"Enforce bounded rounds"，不允许"一直辩论直到达成一致"，原因是：

- A. 多轮辩论会让 token 成本线性增长
- B. PBFT 协议规定最多 3 轮
- C. agent 能看到前几轮的答案并模仿，轮数越多越会趋同于"彼此"而不是"真相"，无界轮次等于奖励跟风
- D. 多轮后置信度会自动变成 1

**Q7.** 运行本节 `main.py`，在 "sycophantic conformity" 场景（2 个跟风者答 42%、置信度 0.35/0.30；3 个独立者答 4.2%、置信度 0.85/0.80/0.82）中，三个聚合器的表现是：

- A. 只有 CP-WBFT 正确
- B. 三者都正确——plurality 本来就 3:2 胜出，这个场景无法体现置信度加权的优势
- C. 只有 plurality 错误
- D. 三者都错误

**Q8.** 讲义引用的 "Can AI Agents Agree?"（arXiv:2603.01213）的结论**不包括**：

- A. 无对手时，LLM agent 在很多基准的标量问题上分歧率超过 30%
- B. 单个采用欺骗人设的 agent 能把 Mixture-of-Agents 共识拉偏 40+ 个百分点
- C. 异构集成比同构集成分歧更多，但漂移更慢
- D. 只要采用 CP-WBFT，欺骗性 agent 的影响就可以被完全消除

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1 写道："Confirm plurality fails the monoculture attack but CPWBFT partially mitigates it when the monoculture confidence is below 0.7."

保持 `4.2%` 两票（0.85、0.82）不变，把 `42%` 三票的置信度统一设为 `x`。

1. 推导 CP-WBFT 改判为 `4.2%` 的临界 `x`。
2. 讲义"below 0.7"的说法是否准确？用 `x = 0.6` 的结果说明。
3. 若 `x` 继续下降，会不会出现 `None`（拒绝）？在什么区间？

**Q10.** 下面这个场景中，5 个诚实 agent 都答对了，只有 1 个拜占庭说谎者：

```python
hon = [Vote('a','4.2%',0.9), Vote('b','4.2%',0.5), Vote('c','4.2%',0.9),
       Vote('d','4.2%',0.3), Vote('e','4.2%',0.8), Vote('z','42%',0.95)]
```

1. 手算 `decentllms(hon)` 两个簇的分数，它选谁？
2. 指出打分公式中的两个缺陷。
3. 给出修正后的打分函数，并说明它在本例和"3 个置信度 0.1 的跟风者"场景下的结果。

**Q11.** 讲义练习 2：加入"silent abstention"——agent 回答 "I don't know"。场景：

```python
vs = [Vote('a','4.2%',0.6), Vote('b','42%',0.55), Vote('c',"I don't know",0.0),
      Vote('d','4.2%',0.5), Vote('e',"I don't know",0.0)]
```

1. 用原代码运行，三个聚合器分别输出什么？哪个输出最离谱，为什么？
2. 写出一个 abstention-aware 的 `cp_wbft`，并说明你对"弃权是否计入分母"的选择。

**Q12.** 本节代码的四个场景中，三个聚合器的结论**完全相同**，没能体现讲义所说的"CPWBFT's confidence weighting mitigates sycophancy"。请设计一个新的 sycophancy 场景（5 票），使 plurality 和 DecentLLMs 选错、CP-WBFT 选对，并给出各自的计算过程。

---

## 四、面试高频题

**Q13.**（基础必考）什么是拜占庭容错？为什么 PBFT 需要 `n ≥ 3f + 1` 个节点？

**Q14.**（原理深挖）把经典 BFT 直接套在 LLM agent 集成上会有哪些问题？请结合 byzantine、sycophancy、monoculture 三种攻击说明。

**Q15.**（工程实践）你要为一个"5 个 agent 回答财务报表数值问题"的系统设计共识机制。请给出聚类、加权、阈值、升级、多样性和监控方案。

**Q16.**（原理深挖）用 agent 自报的置信度加权投票，有什么风险？如何缓解？

**Q17.**（追问型）既然 5 个 agent 达成了一致，为什么还需要 verifier？"一致"和"正确"的差别在工程上如何体现？

---

## 五、参考答案与解析

### Q1 — 答案：C

`n ≥ 3f + 1` ⇒ `f ≤ (n − 1)/3 = 2`。A 是 `n = 4 或 5` 的情况；B 需要 `n ≥ 10`；D 把"多数"和"拜占庭容错"混为一谈。

### Q2 — 答案：A

讲义列出的第一条假设："Independent faults. Byzantines do not coordinate." monoculture 中三个 agent 并非恶意协调，而是因为共享训练数据和基座模型而**相关地**犯错——对投票而言效果与"串通"一样。讲义："Two agents running the same base model share faults." B、C 是 PBFT 的机制而非这里被违反的假设；D 不存在。

### Q3 — 答案：D

实际运行：`cp_wbft(mono)` 返回 `('42%', {'42%': 2.10, '4.2%': 1.67})`。总权重 3.77，`2.10 / 3.77 ≈ 0.557`，不低于 0.5，接受。B 混淆了"平均置信度"与"权重之和"——CP-WBFT 累加的是总和，大簇天然占优；C 恰好相反；A 的拒绝只在占比 < 0.5 时发生。这也是代码 Takeaways 想说明的："no aggregator solves monoculture"。

### Q4 — 答案：B

`dist = Σ|c_i − median|` 只衡量簇内置信度的离散度；簇大小乘以 `1 − dist`。置信度整体平移不改变 dist，所以 3 个置信度都是 0.1 的跟风者得 `3 × 1.0 = 3.0`，比两个 0.85/0.82 的独立者（1.94）还高（已实测）。A 错：代码里没有任何"答案空间"，只是按字符串聚类；C 错：CP-WBFT 是置信度求和；D 错：讲义说 DecentLLMs 原论文在 `f < n/2` 时稳健，但这份简化实现并不具备该保证（见 Q10）。

### Q5 — 答案：A

已实测：`Vote('x','4,2%',1).canonical()` 返回 `'42%'`。逗号不是字母数字、也不是 `.` 或 `%`，被直接删掉。于是"正确答案的另一种写法"被并入了错误簇，给错误答案加票。这说明字符串规范化不是语义聚类：讲义自己的例子 `"the study reports 4.2%"` 与 `"4.2% improvement"` 也会被分成两簇（实测前者规范化为 `thestudyreports4.2%`）。B、C 都是想当然；D 不会发生。

### Q6 — 答案：C

讲义："If agents can observe prior rounds and mimic (Du 2023 debate), they start agreeing with each other regardless of truth. Bound the rounds (2-3 typically)." Ship It："No 'keep debating until agreement' — that rewards sycophancy." A 是事实但不是主要理由；B 错，PBFT 的三阶段与辩论轮数无关；D 无依据。

### Q7 — 答案：B

实际输出三者都是 `[CORRECT]`。plurality 3:2；CP-WBFT 2.47 对 0.65；DecentLLMs 4.2% 簇分数更高。讲义 Build It 说 "CPWBFT's confidence weighting mitigates sycophancy"，但这个场景下 plurality 本来就赢了，无法证明加权的作用。四个场景中三种聚合器的结论完全一致：前三个全对、monoculture 全错。能体现差异的场景见 Q12。

### Q8 — 答案：D

A、B、C 都是讲义对该论文的转述。D 与讲义结论相反：讲义强调"BFT is necessary but not sufficient"，并在 Takeaway 中说"BFT gives you machinery to align outputs, but it does not tell you whether the aligned output is right"。练习 5 也是让你去检验 CP-WBFT/DecentLLMs 能否抓住欺骗人设，而不是假定能。

### Q9 — 参考答案

1. CP-WBFT 比较簇权重之和：`42%` 为 `3x`，`4.2%` 为 `0.85 + 0.82 = 1.67`。改判条件 `3x < 1.67` ⇒ `x < 0.5567`。实测：`x = 0.56` 时仍是 `42%`（1.68 对 1.67），`x = 0.55` 时变为 `4.2%`（1.65 对 1.67）。
2. 不准确。`x = 0.6` 时权重 1.80 对 1.67，CP-WBFT 仍选 `42%`。在当前代码下，"低于 0.7"不足以缓解，需要低于约 0.557。即便 monoculture 的平均置信度（0.70）明显低于正确簇（0.835），只要人数多，总和照样赢——讲义和代码 Takeaways 中"when the wrong cluster is both larger AND more confident"的说法也不准确：本例中错误簇**个体置信度更低**，依然胜出。
3. 拒绝条件是"最大簇权重 / 总权重 < 0.5"。只有两个簇时，最大簇占比一定 ≥ 0.5，所以**永远不会返回 None**。要出现拒绝，必须有 3 个及以上簇且票数足够分散（实测 `A:0.5, B:0.5, C:0.6` 时 `0.6/1.6 = 0.375 < 0.5`，返回 None）。另外代码条件是 `< threshold` 才拒绝，恰好等于 0.5 的平局会被接受，平局时由 `max` 取先插入的键——结果依赖投票顺序。

### Q10 — 参考答案

1. `4.2%` 簇：置信度 `[0.9, 0.5, 0.9, 0.3, 0.8]`，中位数 0.8，`dist = 0.1 + 0.3 + 0.1 + 0.5 + 0 = 1.0`，分数 `5 × max(0, 1 − 1.0) = 0`。`42%` 簇：只有一票，dist = 0，分数 `1 × 1 = 1`。**拜占庭说谎者以 1.0 对 0.0 胜出**（已实测：`('42%', {'4.2%': 0.0, '42%': 1.0})`），而 plurality 和 CP-WBFT 都选对。
2. 两个缺陷：
   - **dist 没有按簇大小归一化**：绝对偏差之和随成员数增长，簇越大越容易被罚到 0——这与"geometric median 抗离群值、偏向稠密簇"的初衷正好相反；单成员簇 dist 恒为 0，反而得满分。
   - **完全忽略置信度大小**：只看离散度，不看高低，等于把评分退化成"人数 × 一致性"。
3. 修正示例：

```python
def decent_fixed(votes):
    clusters = {}
    for v in votes:
        clusters.setdefault(v.canonical(), []).append(v)
    scores = {}
    for k, c in clusters.items():
        confs = [v.confidence for v in c]
        med = median(confs)
        mad = sum(abs(x - med) for x in confs) / len(confs)   # 平均绝对偏差，已归一化
        scores[k] = sum(confs) * max(0.0, 1.0 - mad)          # 置信度总和 × 一致性
    w = max(scores, key=scores.get)
    return clusters[w][0].answer, scores
```

实测：本例 `4.2%` 得 2.72、`42%` 得 0.95，选对；"3 个 0.1 跟风者 vs 0.85/0.82"时 `42%` 得 0.30、`4.2%` 得 1.645，选对；原 monoculture 场景仍选 `42%`（2.072 对 1.645）——这符合讲义"monoculture 需要多样性或 verifier"的结论，聚合器本身救不了。真正的 DecentLLMs 还需要独立 evaluator 对提案打分，而不是复用自报置信度。

### Q11 — 参考答案

1. 实测结果：
   - plurality：`4.2%` 与 `idontknow` 各 2 票，平局，`max` 取先插入的 `4.2%`——**碰巧**正确，换个顺序就会输出 "I don't know"。
   - CP-WBFT：`4.2%` 权重 1.1、`42%` 0.55、`idontknow` 0.0，选 `4.2%`。
   - DecentLLMs：选 **"I don't know"**（2.0 对 1.8）。两个弃权者置信度都是 0、dist 为 0，拿到满分 `2 × 1 = 2.0`。这是最离谱的：弃权被当成了一个"答案"，并且赢了。
2. 参考实现（已运行验证）：

```python
ABSTAIN = {"idontknow", "unknown", ""}

def cp_wbft_abstain(votes, threshold=0.5):
    cast = [v for v in votes if v.canonical() not in ABSTAIN]
    n_abs = len(votes) - len(cast)
    weights, rep = {}, {}
    for v in cast:
        k = v.canonical()
        weights[k] = weights.get(k, 0.0) + v.confidence
        rep.setdefault(k, v.answer)
    if not weights:
        return None, weights                       # 全员弃权 → 升级
    total = sum(weights.values()) + 0.5 * n_abs    # 每个弃权计 0.5 的"未决质量"
    w = max(weights, key=weights.get)
    return (rep[w] if weights[w] / total >= threshold else None), weights
```

本例：总量 `1.65 + 2 × 0.5 = 2.65`，`1.1 / 2.65 ≈ 0.415 < 0.5`，返回 `None` → 升级给人或换一组 agent。

设计取舍：
- **弃权不计入分母**：只在表态者中求多数，容易在多数人弃权时让少数票"代表全体"；
- **弃权计入分母**（本实现）：弃权越多越难过阈值，倾向于升级，更保守；
- 无论哪种，弃权都**不能**成为一个可获胜的簇。讲义 Ship It 中"fail predictably, not silently"也支持把大量弃权当作升级信号。

### Q12 — 参考答案

把跟风者增加到 3 个、独立者 2 个：

```python
sy = [Vote('a','42%',0.35), Vote('b','42%',0.30), Vote('f','42%',0.30),
      Vote('c','4.2%',0.85), Vote('d','4.2%',0.80)]
```

实测：
- plurality：3:2 → `42%`（错）。
- CP-WBFT：`42%` 权重 `0.35 + 0.30 + 0.30 = 0.95`，`4.2%` 权重 `1.65`；`1.65 / 2.60 ≈ 0.635 ≥ 0.5` → `4.2%`（对）。
- DecentLLMs：`42%` 中位数 0.30，dist 0.05，分数 `3 × 0.95 = 2.85`；`4.2%` 中位数 0.825，dist 0.05，分数 `2 × 0.95 = 1.90` → `42%`（错）。

这才是能体现"跟风者置信度低 → 加权能救"的场景。前提是跟风者**如实**报告低置信度；如果跟风者也自报高置信度，CP-WBFT 同样失效（见 Q16）。

### Q13 — 参考回答要点

- **拜占庭故障**：节点可以任意出错——说谎、给不同节点发不同消息、不响应，而不只是"崩溃停机"。BFT 协议要让诚实节点在这种情况下仍对同一个值达成一致。
- **为什么 3f + 1**：系统必须在只等到 `n − f` 个回复时就能前进（另外 f 个可能永远不回）；而这 `n − f` 个回复里最坏可能有 f 个来自拜占庭节点。为保证诚实回复多于拜占庭回复，需要 `n − 2f > f`，即 `n > 3f`。等价地，任意两个大小为 `2f + 1` 的 quorum 至少交于 `f + 1` 个节点，其中必有一个诚实节点，保证不会提交冲突的值。
- **PBFT 流程**：pre-prepare（主节点分配序号）→ prepare（收集 2f 个一致的 prepare）→ commit（收集 2f + 1 个 commit 后执行），配合签名消息和 quorum certificate；讲义："Agreement on a single value among `n >= 3f + 1` honest-or-malicious nodes."
- 加分点：区分 crash fault（`n ≥ 2f + 1`，如 Raft/Paxos）与 Byzantine fault（`n ≥ 3f + 1`）。

### Q14 — 参考回答要点

- **byzantine lie**：经典 BFT 能处理，前提是 `f < n/3`。但 LLM 说谎者可以附带很高的自报置信度（本节场景 0.95），置信度加权反而放大它的影响。
- **sycophancy**：跟风 agent 能通过所有签名检查，它不是"恶意"节点，经典 BFT 根本不认为它有问题；但它让票数不再独立，相当于把最先/最响的声音复制了几份。
- **monoculture**：三个"诚实"agent 一起错，经典 BFT 只会忠实地对齐到错误答案上。讲义："Classical BFT does not help because all three 'honestly' agree."
- **更根本的差异**：讲义列出的三条假设——独立故障、诚实即正确、存在客观真值——LLM 都违反。LLM 节点"即使诚实也是随机的、跨模型相关的、相互影响的"，不能当作独立的伯努利投票者。
- **应对**：CP-WBFT（置信度加权，针对跟风）、DecentLLMs（无 leader + 稳健聚合，针对离群说谎者）、WBFT（信任分 + Core/Edge，针对规模和部分多样性）；以及 BFT 之外的多样性和独立 verifier。
- 常见误区：认为"agent 数量够多就能投票投出正确答案"——相关错误下，增加同质 agent 只会放大虚假多数。

### Q15 — 参考回答要点

- **聚类**：数值题用结构化规范化——解析成数值 + 单位（统一百分比/小数、千分位、小数点与逗号），在容差内视为同簇；文本题用 embedding 相似度阈值聚类。避免本节 `canonical()` 那种删字符的做法。
- **加权**：CP-WBFT 风格的置信度加权，但置信度来自独立校准模型或历史准确率（WBFT 的 trust score），而不是只信自报。
- **阈值**：`n = 5` 取 0.6 左右（讲义 0.5–0.67，`n` 小取高）；低于阈值 → 重试一次（换温度/提示）→ 仍不过则升级给人。
- **多样性**：至少 2–3 个不同基座模型、不同提示族；讲义："Monoculture is the attack plurality cannot recover from; diversity is the structural mitigation."（skill 文件）
- **独立 verifier**：对数值类问题回到原始报表重新计算或取数；verifier 输出不回流到投票池。
- **轮次**：最多 2 轮，第二轮才允许看到他人答案。
- **监控**：记录每轮所有少数簇及 provenance；监控一致率——讲义："A sharp rise means conformity bias; a sharp fall means model drift."
- **上线前**：用 byzantine / sycophancy / monoculture 三种模式做攻击测试，要求"fail predictably, not silently"。

### Q16 — 参考回答要点

- **风险**：
  - 拜占庭 agent 可以随意报高置信度（本节 byzantine 场景报 0.95），加权会放大它；
  - LLM 自报置信度通常校准不佳，常见过度自信；
  - 跟风者如果被提示"表现得有把握"，也会报高置信度，CP-WBFT 的前提（跟风者低置信度）随之失效；
  - 同一基座模型的 monoculture 成员往往**同样自信**地犯错（本节 monoculture 场景 0.68–0.72）。
- **缓解**：
  - 讲义练习 4：用**独立校准模型**预测每个 agent 回答的置信度，而不是信自报；
  - 用历史准确率形成 trust score（WBFT 思路），对长期自报过高的 agent 降权；
  - 置信度上限截断（例如 0.9），限制单票影响；
  - 结合 token 级概率、自一致性（同一 agent 多次采样的一致率）等可观测信号代替口头置信度。
- 加分点：校准度可以用 ECE（expected calibration error）或 Brier score 评估。

### Q17 — 参考回答要点

- **一致不等于正确**：讲义原话："BFT gives you machinery to align outputs, but it does not tell you whether the aligned output is right." 本节 monoculture 场景中三种聚合器全部"一致"地选了错误的 42%。
- **工程体现**：
  - 共识输出交给**独立于集成的 verifier**（重新取源、执行代码、规则检查），verifier 输出不回流投票池（skill 文件把回流列为硬拒绝）；
  - 记录少数簇——它们往往是相关错误的早期预警；
  - 对无客观答案的问题（观点、创作），讲义要求明确称之为"意见"，共识只作建议，人来决策；
  - 复合问题拆开分别投票。
- **一致率监控**：一致率突然升高常意味着跟风/同质化，而不是"大家变准了"。
- 常见误区：把"高一致率"当作质量指标写进 KPI。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../07-society-of-mind-debate/docs/zh.md)：讲义列出的先修课，Du 2023 多 agent 辩论与跟风问题的来源。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：讲义列出的先修课，provenance、独立 verifier、"verifier 输出不回流"的原则在本节再次出现。
- [阶段 16 · 08 角色专业化](../../08-role-specialization/docs/zh.md)：讲义提到用 verifier 角色补足"一致 ≠ 正确"。
- [阶段 02 · 11 集成方法](../../../02-ml-fundamentals/11-ensemble-methods/docs/zh.md)：投票集成、误差相关性对集成收益的影响。

### 本节被哪些后续内容用到
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../15-voting-debate-topology/docs/zh.md)：讲义点名的"diversity (debate variants)"，从投票规则扩展到辩论拓扑。
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：WBFT 的历史信任分与声誉系统。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：sycophancy 与 monoculture 的系统化失效分类。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：讲义点名的 evaluator agents 与基准。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../../18-ethics-safety-alignment/04-sycophancy-rlhf-amplification/docs/zh.md)：sycophancy 的训练根源。

### 延伸关键词
`PBFT` · `3f+1` · `quorum certificate` · `crash fault vs Byzantine fault` · `CP-WBFT` · `DecentLLMs` · `geometric median` · `WBFT Core/Edge` · `confidence calibration` · `ECE` · `semantic clustering` · `monoculture` · `sycophancy` · `Mixture-of-Agents`
