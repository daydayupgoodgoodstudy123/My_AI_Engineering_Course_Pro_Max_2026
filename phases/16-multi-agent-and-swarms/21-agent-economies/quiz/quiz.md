# 测验 · Agent 经济体系、Token 激励与声誉（Agent Economies, Token Incentives, Reputation）

> **阶段 16 · 多智能体与集群 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五层 agent 经济栈 | DePIN（物理算力）→ Identity（W3C DID + 声誉）→ Cognition（LLM + RAG + MCP）→ Settlement（账户抽象 ERC-4337）→ Governance（Agentic DAO）；讲义："是参考地图，不是必选项" |
| 2 | 三个生产网络 | Bittensor（子网验证者按输出质量排名、按 stake 加权分配 TAO）、Fetch.ai/ASI（ASI-1 Mini，用 FET 付推理费）、Gonka（以 transformer 前向计算为"工作量证明"） |
| 3 | 信用分配问题 | 多个 agent 共同产出价值，但要分别奖励；平分、"最后贡献者全拿"不公平或可被操纵 |
| 4 | Shapley value | 满足效率、对称、线性、零贡献者（null）四条公理的唯一分配；= 所有排列中边际贡献的平均；精确计算 O(N!)，需要采样近似 |
| 5 | 第二价格拍卖（Vickrey） | 出价最高者赢，支付第二高出价；单物品、私有价值下如实报价是占优策略；讲义：Google Research 在"单调聚合"条件下用于 LLM token 拍卖 |
| 6 | 声誉资本 | `rep(t+1) = α·rep(t) + (1 − α)·quality(t)`，α 接近 1；读取便宜、伪造昂贵（随时间积累并绑定 DID）、可被 slashing（罚没） |
| 7 | AAMAS 2025 去中心化 LaMAS | DID 身份 + Shapley 信用分配 + 简单拍卖；讲义："去中心化信用分配让系统可审计、不易被单点操纵" |
| 8 | 经济机制的失效点 | 价格预言机被操纵、Sybil 攻击（一人造 N 个假 agent）、验证成本（便宜的验证可被利用，昂贵的不可扩展）、监管灰区 |
| 9 | 什么时候值得用 | 异构运营方的开放网络、输出可验证、长程工作流、token 支付在当地合法；封闭企业系统用简单分配即可 |
| 10 | 本节代码的真实情况 | Shapley 计算正确（0.5083 / 0.3333 / 0.1583）；拍卖只打印"truthful"，没演示；声誉路由只提升 +3.6%（讲义预期 10–20%），且没有实现 slashing |

### 核心技能（能动手做到）

- [ ] 用 3 人公式手算 Shapley 值，并验证效率公理（总和等于大联盟价值）
- [ ] 写出 Shapley 的精确枚举与 Monte Carlo 采样版本，估算采样次数 K 与误差、N 与耗时的关系
- [ ] 对第二价格拍卖逐一枚举"多报/少报"的收益，证明如实报价是占优策略，并说出破坏这一性质的条件
- [ ] 读懂 EMA 声誉更新，解释初始值、α 和路由策略（按比例 vs 贪心）对路由收益的影响
- [ ] 给声誉系统补上 slashing、时间衰减、上下限，并指出"新身份初始声誉过高"的 Sybil 漏洞
- [ ] 针对一个开放的多 agent 网络，按"身份—信用—支付—声誉—验证—防 Sybil—合规"七步给出经济层设计

---

## 二、基础自测（选择题）

**Q1.** 讲义中五层 agent 经济栈从底到顶的顺序是：

- A. Identity → DePIN → Settlement → Cognition → Governance
- B. Cognition → Identity → DePIN → Governance → Settlement
- C. DePIN → Cognition → Identity → Governance → Settlement
- D. DePIN → Identity → Cognition → Settlement → Governance

**Q2.** Shapley value 是唯一同时满足哪四条公理的分配方式？

- A. 效率（efficiency）、对称（symmetry）、线性（linearity）、零贡献者（null）
- B. 单调性、凸性、个体理性、预算平衡
- C. 效率、激励相容、个体理性、匿名性
- D. 对称、帕累托最优、无嫉妒、预算平衡

**Q3.** 代码 `demo_auction` 中的出价为 a = 0.82、b = 0.60、c = 0.95、d = 0.45、e = 0.77。第二价格拍卖的结果是：

- A. agent-c 获胜，支付 0.95
- B. agent-a 获胜，支付 0.77
- C. agent-c 获胜，支付 0.82
- D. agent-c 获胜，支付五个出价的平均值 0.718

**Q4.** 讲义总结 Bittensor 带来的"经济学教训"是：

- A. 按消耗的算力付费
- B. 按特定任务的输出质量付费（由子网验证者排名、按 stake 加权分配），而不是按算力付费
- C. 按调用次数付费
- D. 按 agent 的注册时长付费

**Q5.** 代码中三人合作的价值函数为：单人 coder 0.5、researcher 0.3、reviewer 0.1；两两组合 0.85 / 0.70 / 0.55；三人 1.00。精确 Shapley 值是：

- A. coder 0.5083、researcher 0.3333、reviewer 0.1583
- B. coder 0.5556、researcher 0.3333、reviewer 0.1111
- C. 每人 0.3333
- D. coder 0.5000、researcher 0.3000、reviewer 0.2000

**Q6.** 关于 Sybil 攻击，下列说法正确的是：

- A. 指价格预言机被篡改
- B. 指验证者与被验证者串通
- C. 只要用了 DID 就能彻底杜绝
- D. 指一个运营方创建大量假 agent 来放大自己的份额；DID 只能减缓，主要靠"伪造声誉的成本"来缓解

**Q7.** 代码的声誉路由只比随机路由提升 +3.6%，远低于讲义预期的 10–20%。下列哪一项是**最主要**的原因组合？

- A. 随机数种子选得不好，换个种子就能达到 15%
- B. 初始声誉为 1.0 且 α = 0.95，50 次预热后声誉几乎没离开 1.0；路由按声誉**比例**抽样，差 agent 仍常被选中；而且提升是在包含 50 个完全相同的预热任务的 100 个任务上计算的
- C. 质量噪声 ±0.1 太大，声誉无法区分 agent
- D. `weighted_choice` 有 bug，总是返回最后一个 agent

**Q8.** 按讲义，下列哪种场景**最适合**引入 agent 经济机制？

- A. 一家公司内部，由一个团队维护的 5 个 agent 流水线
- B. 一次性的问答任务
- C. 多个互不隶属的运营方提供 agent、输出可以被独立验证、任务长期反复出现、且 token 支付在当地合法
- D. 输出无法验证，但希望用 token 激励提升积极性

---

## 三、动手 / 代码题

**Q9.** Shapley 手算与公理。

1. 用三人公式 `φ_i = (1/3)·v({i}) + (1/6)·[v({i,j}) − v({j})] + (1/6)·[v({i,k}) − v({k})] + (1/3)·[v(N) − v({j,k})]` 手算 coder 的 Shapley 值，并说明这四项的权重为什么是 1/3、1/6、1/6、1/3。
2. 验证效率公理。与"平分"（各 0.333）和"按单人能力成比例"（0.556 / 0.333 / 0.111）相比，Shapley 给 reviewer 的份额是更多还是更少？为什么？
3. 讲义练习 1：如果把 reviewer 改成"完全无用"（任何联盟加入它价值都不变），它的 Shapley 值是多少？对应哪条公理？

**Q10.** 第二价格拍卖的激励。沿用 Q3 的出价，假设每个人的出价就是他的真实价值，赢家收益 = 真实价值 − 支付，输家收益 = 0。

1. agent-a（真实价值 0.82）若改报 0.90 或 0.96，结果和收益分别是什么？
2. agent-c（真实价值 0.95）若改报 0.85、0.83、0.80，结果和收益分别是什么？
3. 从 1 中你还能看出一个"输家也能影响结果"的现象吗？它在什么情况下会成为问题？
4. `second_price` 在只有 1 个出价时返回 `None`。生产中通常怎么处理？

**Q11.** 声誉路由分析。实测（同一种子下的 50 次随机预热后）声誉为：alpha 0.963、beta 0.793、gamma 0.852、delta 0.693（真实质量 0.9 / 0.5 / 0.75 / 0.3）。200 个种子平均、**只看后 50 个任务**的结果：

| 路由策略 | α | 初始声誉 | 随机路由 | 声誉路由 | 提升 |
|---------|---|--------|--------|--------|-----|
| 按声誉比例抽样（原代码） | 0.95 | 1.0 | 0.611 | 0.654 | +7.0% |
| 按声誉比例抽样 | 0.8 | 1.0 | 0.611 | 0.695 | +13.7% |
| 按声誉比例抽样 | 0.95 | 0.5 | 0.611 | 0.671 | +9.9% |
| 贪心（选声誉最高者） | 0.95 | 1.0 | 0.611 | 0.897 | +46.9% |

1. 解释为什么 50 次预热后 delta 的声誉仍有 0.693。
2. 为什么"按比例抽样"即使声誉准确，收益也有限？贪心的风险是什么？
3. 代码的 `Reputation.init` 把所有新 agent 设为 1.0。从 Sybil 和 slashing 的角度看，这有什么问题？

**Q12.** 讲义要求"slashing"和"Shapley 采样"，代码只完成了一半。

1. 给 `Reputation` 补上 `slash(agent, penalty)` 和"按时间衰减向先验回归"的 `tick()`，并加一个上限 `ceiling`。
2. Shapley 采样精度与成本（实测）：三人例子中，K = 10 / 50 / 200 / 1000 / 10000 时最大绝对误差平均为 0.0202 / 0.0092 / 0.0044 / 0.0020 / 0.0006；用一个 10 人价值函数，精确枚举 N = 8、9、10 分别耗时 0.26 s、3.06 s、37.6 s，而 K = 100 采样只需约 1.4 ms，但最大绝对误差平均 0.033（各人 Shapley 值在 0.062–0.392 之间）。请据此说明：误差随 K 大致怎样变化？讲义"Sample 100-1000 orderings"在 N = 10 时够不够？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Shapley value？为什么说它"公平"？精确计算的复杂度是多少，生产中怎么近似？

**Q14.**（原理深挖）为什么第二价格拍卖是 truthful 的？哪些条件被破坏后会失效？放到 LLM 场景（多个 agent 竞标一个任务槽或一段输出）会出现什么具体问题？

**Q15.**（工程实践）设计一个可上线的 agent 声誉系统：更新规则、衰减、上下限、slashing、冷启动、验证分别怎么做？

**Q16.**（场景设计）一个开放平台允许第三方提交"代码修复 agent"，多个 agent 协作完成一个 PR（检索、修改、测试）。平台要按贡献奖励它们。请给出经济层设计，并说明怎样防刷。

**Q17.**（追问型）面试官问："既然 Shapley 是唯一满足四条公理的分配，为什么讲义还说'Verify before you reward'？Shapley 不就已经公平了吗？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义顺序：1 DePIN（物理算力）、2 Identity（DID + 声誉）、3 Cognition（LLM + RAG + MCP）、4 Settlement（ERC-4337 账户抽象）、5 Governance（Agentic DAO）。A、B、C 打乱了层次。讲义还强调并非每个系统都用满五层：例如 Bittensor 用了第 1、2 层，部分用了第 3、4 层，没有第 5 层；OpenAI 的 agent 只用第 3 层。

### Q2 — 答案：A

讲义："the unique credit allocation satisfying four axioms (efficiency, symmetry, linearity, null)"。
- 效率：分配总和等于大联盟价值；
- 对称：贡献完全相同的两人分得相同；
- 线性：两个游戏相加，分配也相加；
- 零贡献者：对任何联盟都不带来增量的人分得 0。
B、C、D 混入了合作博弈/机制设计中的其它概念（个体理性、激励相容、无嫉妒等），不是 Shapley 的公理化定义。

### Q3 — 答案：C

出价排序：c 0.95 > a 0.82 > e 0.77 > b 0.60 > d 0.45。最高者 c 获胜，支付第二高出价 0.82。实际输出：`winner: agent-c  payment: 0.82`。
- A 是第一价格拍卖；
- B 把赢家搞错了；
- D 不是任何标准拍卖规则。

### Q4 — 答案：B

讲义："Miners submit model outputs. Validators rank them; stake-weighted scoring distributes the TAO rewards... The economic lesson: pay for task-specific output quality, not compute used." A、C、D 都不是讲义给出的结论。

### Q5 — 答案：A

代码输出：coder 0.5083、researcher 0.3333、reviewer 0.1583，总和 1.0000。
- B 是"按单人能力成比例"（0.5 : 0.3 : 0.1）；
- C 是平分；
- D 只是随手拼的数字，总和虽为 1，但不满足 Shapley 定义。

### Q6 — 答案：D

讲义："One operator spins up N fake agents to inflate their own contribution. DIDs slow but do not stop this; reputation cost-to-forge is the mitigation."
- A 是"价格预言机操纵"，讲义单独列出；
- B 是串通，不是 Sybil 的定义；
- C 与讲义"DIDs slow but do not stop this"相反。

### Q7 — 答案：B

三个原因叠加：
1. 声誉初始为 1.0、`α = 0.95`，每个 agent 预热期只被选中约 12 次，初始值仍占约 `0.95^12 ≈ 0.54` 的权重，所以声誉普遍偏高、彼此接近；
2. `weighted_choice` 按声誉**比例**抽样，即使声誉准确，delta 仍有约 19% 的概率被选中；
3. 两次运行都用 `random.Random(0)`，预热阶段的随机抽取完全相同（已验证前 50 个质量值逐个相等），提升只来自后 50 个任务，却按 100 个任务平均，被稀释了一半。只看后 50 个任务，本种子是 0.622 → 0.667（约 +7%）。

- A：200 个种子平均（按 100 个任务计）也只有 +3.5%；
- C：±0.1 的噪声相对于 0.3–0.9 的质量差距很小；
- D：`weighted_choice` 实现正确。

### Q8 — 答案：C

讲义 "When agent economies make sense"：开放网络、异构运营方、可验证输出、长程工作流、token 支付合法。
- A：封闭的企业系统，讲义说"economics gives way to simpler allocation"；
- B：一次性任务无法从声誉积累中受益；
- D：讲义与技能文件都强调"Without verification, credit attribution is a guess"。

### Q9 — 参考答案

1. coder 的计算：
   - `(1/3) × 0.5 = 0.16667`（coder 排第一）
   - `(1/6) × (0.85 − 0.30) = 0.09167`（排第二，前面是 researcher）
   - `(1/6) × (0.70 − 0.10) = 0.10000`（排第二，前面是 reviewer）
   - `(1/3) × (1.00 − 0.55) = 0.15000`（排最后）
   - 合计 **0.50833**，与输出一致。

   权重来源：3! = 6 种排列中，coder 排第一的有 2 种（2/6 = 1/3）；排第二且前面是某个特定的人的各 1 种（1/6）；排最后的有 2 种（1/3）。同理 researcher = 0.1 + 0.05833 + 0.075 + 0.1 = 0.33333，reviewer = 0.03333 + 0.03333 + 0.04167 + 0.05 = 0.15833。

2. 效率：0.50833 + 0.33333 + 0.15833 = 1.00000 = v(N)。reviewer 的份额：Shapley 0.158，比"按单人能力成比例"的 0.111 **多**，比平分的 0.333 少。原因：reviewer 单独只值 0.1，但它与别人组合时有协同（例如 coder + reviewer = 0.70 > 0.5 + 0.1；最后加入时让 0.85 → 1.00），Shapley 会把这部分协同的边际贡献算给它；按单人能力分配则完全忽略协同。

3. 若 reviewer 对任何联盟都不带来增量，所有排列中它的边际贡献都是 0，Shapley 值为 **0**，对应**零贡献者（null）公理**；同时由于效率公理，coder 与 researcher 的份额之和会等于新的 v(N)。

### Q10 — 参考答案

实测（用代码中的 `second_price` 逐一计算）：

| 情形 | 结果 | 收益 |
|------|------|------|
| a 如实报 0.82 | c 赢，付 0.82 | a：0 |
| a 改报 0.90 | c 赢，付 **0.90** | a：0 |
| a 改报 0.96 | **a 赢，付 0.95** | a：0.82 − 0.95 = **−0.13** |
| c 如实报 0.95 | c 赢，付 0.82 | c：0.13 |
| c 改报 0.85 或 0.83 | c 赢，付 0.82 | c：0.13（不变） |
| c 改报 0.80 | **a 赢**，付 0.80 | c：0（损失 0.13） |

1. a 多报到 0.90 时没有好处；多报到 0.96 以上会赢，但要付 0.95 > 真实价值，收益为负。
2. c 少报只要仍是最高，支付不变（支付由别人的出价决定）；少报到低于第二高出价就会输掉本应赢的 0.13。所以**如实报价是占优策略**：支付与自己的出价无关，自己的出价只决定"赢不赢"，而如实报价恰好让你在"赢了有正收益"时赢。
3. 输家 a 把出价从 0.82 提到 0.90，赢家 c 的支付从 0.82 变成 0.90——**输家可以抬高赢家的价格**。单次拍卖中这对 a 无损，但在重复拍卖、竞争对手之间、或 a 与拍卖方串通（"托"）时，会被用来抽取赢家的剩余；这也是 Vickrey 拍卖对串通和 shill bidding 脆弱的原因之一。
4. 生产中通常设置**保留价（reserve price）**：只有一个出价时以保留价成交（或不成交）；也可以把平台方的保留价当作一个"虚拟出价"参与排序。此外还要定义平局规则（代码中 `sorted` 是稳定排序，平局时先出现在列表里的人赢）。

### Q11 — 参考答案

1. EMA 更新 `rep ← 0.95·rep + 0.05·q`。delta 在预热期被选中约 11 次，初始值 1.0 的残留权重约 `0.95^11 ≈ 0.57`，所以 `rep ≈ 0.57 × 1.0 + 0.43 × 0.3 ≈ 0.70`，与实测 0.693 吻合。**α 越接近 1，越"记得"初始值**；样本少时初始值主导了声誉。
2. 按比例抽样：选中概率 = 声誉 / 声誉总和。即使声誉完全准确（0.9 / 0.5 / 0.75 / 0.3），alpha 也只有 `0.9 / 2.45 ≈ 37%` 的概率被选中，期望质量约 `(0.81 + 0.25 + 0.5625 + 0.09) / 2.45 ≈ 0.70`，离"总选 alpha"的 0.9 还很远。贪心能拿到接近 0.9，但风险是：完全不探索，alpha 若退化（模型更新、被攻击）而其它 agent 不再被选中，声誉不会更新，系统发现得很慢；所有流量集中到一个 agent 也会造成负载和单点风险。折中：softmax（带温度）、ε-greedy、或把声誉作为 bandit 的先验（Thompson sampling）。
3. 新 agent 一注册就拥有 1.0——**高于任何真实 agent 能稳定达到的水平**（质量上限是 1，均值更低）。后果：
   - 被 slash 到低声誉的运营方只需换一个 DID 重新注册，就能"洗白"成最高声誉；
   - Sybil 攻击者批量注册新身份，会立刻在比例路由中分走大量流量；
   - 与讲义"reputation is expensive to forge"直接矛盾。

   修复：新身份从**低先验**（如 0.3）或"全网中位数以下"起步；新身份流量配额受限；需要 stake 或验证后才能提高上限。

### Q12 — 参考答案

1. 参考实现：

```python
class Reputation:
    def __init__(self, alpha=0.95, floor=0.1, ceiling=0.95, prior=0.3, time_decay=0.99):
        self.alpha, self.floor, self.ceiling = alpha, floor, ceiling
        self.prior, self.time_decay = prior, time_decay
        self.scores: dict[str, float] = {}

    def init(self, agents):
        for a in agents:
            self.scores.setdefault(a, self.prior)       # 新身份从低先验起步

    def _clip(self, x):
        return max(self.floor, min(self.ceiling, x))

    def update(self, agent, quality):                   # 只在通过验证后调用
        cur = self.scores.get(agent, self.prior)
        self.scores[agent] = self._clip(self.alpha * cur + (1 - self.alpha) * quality)

    def slash(self, agent, penalty=0.3):                # 验证失败直接扣分
        cur = self.scores.get(agent, self.prior)
        self.scores[agent] = self._clip(cur - penalty)

    def tick(self):                                     # 按时间（而非按使用）向先验回归
        for a, s in self.scores.items():
            self.scores[a] = self._clip(self.prior + self.time_decay * (s - self.prior))
```

要点：`update` 只在验证通过后调用；`slash` 用于验证失败；`tick` 由定时任务调用，解决"不被选中的 agent 声誉永远不变"的问题（技能文件把"没有衰减的声誉"列为硬拒绝）；ceiling 防止早期幸运者垄断。

2. 误差大致按 `1/√K` 下降：K 从 10 到 1000 扩大 100 倍，误差从 0.0202 降到 0.0020，约 10 倍。N = 10 时 K = 100 的平均最大误差 0.033，对 Shapley 值只有 0.062 的 agent 来说相对误差约 50%，不够用；要把误差压到 0.003 左右，按 `1/√K` 估算需要 K ≈ 100 × (0.033 / 0.003)² ≈ 1.2 万，仍远快于精确枚举（每次排列 N 次 value 调用，约 12 万次，对比精确的 3,628,800 × 10 次）。讲义"100–1000 次"更适合作为起点，实际应根据份额大小和可接受误差决定。另外：精确枚举每增加 1 人耗时约乘以 N（0.26 → 3.06 → 37.6 秒），技能文件"N > 6 不做精确计算"的规则有道理。真实系统中 value_fn 每次可能是一次 LLM 评测，成本更高，常用缓存联盟价值（只有 2^N 个不同联盟）来减少调用。

### Q13 — 参考回答要点

- **定义**：对所有 N! 个加入顺序，计算 agent i 加入时带来的边际贡献 `v(S ∪ {i}) − v(S)`，取平均。
- **为什么公平**：它是唯一同时满足效率（分完）、对称（同等贡献同等回报）、线性（可分解）、零贡献者得 0 的分配；考虑了协同效应，不像"按单独能力分"那样忽略合作。
- **复杂度**：O(N!) 个排列，或等价地 O(2^N) 个联盟价值；每个联盟价值可能需要一次真实评测。
- **近似**：
  - Monte Carlo 排列采样（讲义 Ship It："Sample 100-1000 orderings"），误差约 `1/√K`；
  - 缓存联盟价值；
  - 分层采样、按联盟大小采样；
  - 对结构化的价值函数用近似模型（如 KernelSHAP 思路）。
- 加分点：说明效率公理保证总额正好分完；说出 N=10 精确枚举需 3,628,800 个排列。

### Q14 — 参考回答要点

- **为什么 truthful**：赢家的支付由**别人**的最高出价决定，与自己的出价无关；自己的出价只决定是否赢。如实报价时：当真实价值高于其他最高出价，就赢且收益为正；低于时就输、收益为 0。任何偏离只会导致"本该赢的输了"或"不该赢的赢了且亏钱"（见 Q10）。
- **失效条件**：
  - 讲义：聚合函数不满足单调性（技能文件："Second-price auctions where the aggregation function is not monotone. Truthfulness does not hold."）；
  - 串通 / 虚假出价（shill bidding）：输家可以抬高赢家价格；
  - 多物品、组合拍卖（需要 VCG 等更一般的机制）；
  - 预算约束、风险偏好、重复博弈中的声誉考量；
  - 拍卖方不可信（可插入假出价）。
- **LLM 场景的具体问题**：agent 的"价值"难以客观定义，报价可能与真实质量脱钩；同一运营方的多个 agent 串通；若平台按出价选输出、但最终质量由 LLM 聚合决定，聚合方式不单调时，agent 有动机虚报以影响聚合结果。
- 加分点：区分"拍卖决定谁做"与"质量验证决定是否付款"——后者仍需要托管（escrow）与验证（技能文件第 3、5 步）。

### Q15 — 参考回答要点

- **更新**：EMA `rep ← α·rep + (1 − α)·q`，q 必须来自独立验证（讲义 "Verify before you reward"），不接受自报质量。
- **α 的取舍**：α 大 → 稳定但反应慢、初始值影响大；α 小 → 反应快但噪声大。可按样本数自适应（前期 α 小，后期 α 大），或用贝叶斯（Beta 分布）表示并带不确定性。
- **时间衰减**：按时间向先验回归，避免"多年前表现好、现在已坏"的 agent 一直高声誉（技能文件硬拒绝）。
- **上下限**：floor 防止合法贡献者被永久清零（讲义 Ship It），ceiling 防止垄断。
- **slashing**：验证失败时扣分，严重违规直接冻结；保留审计日志。
- **冷启动**：新身份从低先验开始、限流、要求 stake；给少量探索流量。
- **路由使用**：不要只按比例抽样或纯贪心；用 softmax/ε-greedy/Thompson sampling 平衡探索与利用（见 Q11）。
- **验证**：独立验证 agent 或人工抽检；验证器本身也要被审计（讲义"Verification cost"）。

### Q16 — 参考回答要点

按技能文件的七步：
1. **身份**：开放平台、多运营方 → 每个 agent 一个 DID，声誉绑定 DID。
2. **信用分配**：PR 合并后，用 Shapley 采样分配奖励。价值函数 v(S) = 用联盟 S 的产出（例如去掉某 agent 的修改或替换为基线实现）重跑测试套件得到的通过率/质量分；联盟价值缓存。
3. **支付**：任务槽用第二价格拍卖或固定价格；奖励进入托管，等合并且回归测试通过后结算。
4. **声誉**：EMA + 时间衰减 + 上下限 + 验证失败 slashing；新 DID 低先验。
5. **验证**：独立 CI 测试 + reviewer agent + 人工抽检；验证器轮换，防止被针对性利用。
6. **防刷（Sybil）**：注册需 stake 或身份证明；每个运营方的 DID 数量与流量上限；检测"同一运营方的多个 agent 总在同一联盟里出现"的模式；Shapley 的价值函数只认可通过测试的真实增量。
7. **合规**：若奖励是 token，涉及金融监管，需法律评审；不确定时先只做声誉（讲义 "Start with reputation, not tokens"）。
- 试点：30 天内先跑预热、建立验证管线、再启用按声誉路由，并安排定期审计（技能文件的输出要求）。

### Q17 — 参考回答要点

- **Shapley 的公平是"相对于价值函数 v 的公平"**：它保证在给定 v 的前提下按边际贡献分配，但 v 本身从哪里来？如果 v 来自 agent 自报或一个容易被欺骗的评审器，Shapley 只会把"被操纵的价值"公平地分下去。
- **讲义原话**：Credit attribution is only as fair as the verifier；"Self-reported quality accrues sybil games"。
- **具体攻击**：
  - 刷分：针对便宜的 LLM 评审器优化输出，让 v 虚高；
  - Sybil：同一运营方注册多个 agent，若 v 把它们视为独立贡献者，可能分走更多份额；
  - 价格/预言机操纵：若 v 依赖外部价格或指标，攻击指标即可。
- **因此**：先验证（独立、昂贵程度与风险匹配）、再分配；对机制做红队测试（讲义 "Audit mechanisms adversarially"）。
- 加分点：指出 Shapley 的计算成本也会诱导"用便宜但可被操纵的评审器"，这正是讲义所说的验证成本两难。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 16 协商与议价](../../16-negotiation-bargaining/docs/zh.md)：讲义列出的先修课，agent 之间的博弈与议价。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：讲义列出的先修课。
- [阶段 16 · 19 面向 LLMs 的 Swarm 优化（PSO、ACO）](../../19-swarm-optimization-pso-aco/docs/zh.md)：信息素路由与声誉路由同属"按历史质量加权选择 agent"。
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../14-consensus-and-bft/docs/zh.md)：开放网络中的恶意节点与 Sybil 问题。

### 本节被哪些后续内容用到
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：经济结算与验证需要持久化、幂等的执行。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：激励失配导致的系统性失效。
- [阶段 16 · 25 案例研究与 2026 年前沿进展](../../25-case-studies-2026-sota/docs/zh.md)：真实多 agent 系统案例。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：当信用函数可被操纵时，agent 会去操纵它。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：token 支付与监管合规。

### 延伸关键词
`Shapley value` · `Monte Carlo Shapley` · `Vickrey auction` · `VCG mechanism` · `reserve price` · `shill bidding` · `mechanism design` · `reputation system` · `EMA` · `slashing` · `Sybil attack` · `W3C DID` · `ERC-4337` · `DePIN` · `Bittensor` · `escrow`
