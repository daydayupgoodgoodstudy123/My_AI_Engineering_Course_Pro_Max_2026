# 测验 · 生成式 Agents 与涌现模拟（Generative Agents and Emergent Simulation）

> **阶段 16 · 多智能体与集群 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机器翻译（如 Park 被译成"朴"或"公园"、arXiv 编号 2304.03442 被误写为"2304.0442"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Smallville | Park et al. 2023（UIST '23，arXiv:2304.03442）：25 个 agent 的沙盒，三组件架构 memory stream + reflection + plan |
| 2 | Memory stream | append-only 的自然语言日志（观察、行动、反思、计划），每条带时间戳、类型、描述，以及 recency、importance（写入时 agent 自评 1–10）、relevance（与当前查询的余弦相似度） |
| 3 | 检索打分 | `score = w_recency·e^(−decay·age) + w_importance·importance + w_relevance·cos_sim`，取 top-k 放进当前 prompt；讲义规则："Retrieval is ranked, not filtered" |
| 4 | Reflection | 周期性（每 N 条记忆或重要事件时）从近期记忆生成更高层的综合判断，写回 stream、可被检索；讲义规则：未处理记忆的 importance 之和超过阈值（如 150）时触发 |
| 5 | Plan | 自顶向下分解：日计划 → 小时计划 → 动作计划；观察与计划冲突时只重规划受影响片段 |
| 6 | 消融结论 | 讲义：去掉 observation、reflection、plan 中任一项，人类评分的 believability 都会下降；三者缺一不可 |
| 7 | 情人节派对涌现 | 只给 Isabella 一个"办派对"的种子目标，邀请通过双边对话在人群中传播，多个 agent 按时到达 Hobbs Cafe——系统级行为来自局部交互，没有中央编排者 |
| 8 | 已记录的失效 | 空间规范错误（进入已关门的商店、多人共用单人卫生间）、记忆膨胀（检索成本随 stream 增长）、反思幻觉（编造不存在的关系） |
| 9 | 五条实现规则 | 记忆 append-only；importance 写入时打分并缓存；检索排序而非过滤；反思按阈值周期触发；计划可局部修订 |
| 10 | 适用边界 | 需要**涌现的社会行为**（社会模拟、游戏 NPC、政策演练）用 Smallville 结构；需要**紧凑的任务执行**用 supervisor / 角色 / 原语模式 |

### 核心技能（能动手做到）

- [ ] 实现带 recency / importance / relevance 三项打分的 `retrieve_top_k`，并能手算排序
- [ ] 实现"importance 累加超过阈值才触发"的反思，并给反思记录来源记忆 id
- [ ] 把"邀请如何传播"从主循环的硬编码改为由 agent 自身信念和计划驱动，验证涌现在更大 N 下仍然成立
- [ ] 做一次消融实验（去掉 reflection），并解释为什么本节代码的消融结论是"构造出来的"
- [ ] 为模拟加入显式的空间/社会规范（如容量上限），观察溢出时的行为
- [ ] 为一个真实场景写出生成式 agent 模拟的设计：记忆 schema、反思节奏、计划层级、世界模型、预算与评估指标

---

## 二、基础自测（选择题）

**Q1.** Park et al. 2023 生成式 agent 架构的三个核心组件是：

- A. planner、coder、reviewer
- B. tokenizer、transformer、sampler
- C. memory stream、reflection、plan
- D. observation、tool calling、guardrail

**Q2.** 讲义给出的记忆检索打分公式中，三个分量分别是：

- A. recency（按时间指数衰减）、importance（写入时自评 1–10）、relevance（与查询的余弦相似度）
- B. 长度、频率、情感倾向
- C. recency、importance、作者身份
- D. 只用 relevance，其余作为硬过滤条件

**Q3.** 按讲义的实现规则，reflection 应该在什么时候触发？

- A. 每个 tick 都触发，保证信念最新
- B. 只在模拟结束时触发一次
- C. 由人工手动触发
- D. 未处理记忆的 importance 之和超过阈值（讲义举例 150）时触发

**Q4.** Park et al. 明确记录的失效模式中，属于"spatial norm errors"的是：

- A. agent 在对话中重复同一句话
- B. agent 走进已经关门的商店、多个 agent 同时使用单人卫生间
- C. agent 忘记了自己的名字
- D. agent 拒绝回答问题

**Q5.** 本节 `demo_retrieval` 中，tick = 4、查询 `"party cafe"`，代码打分为 `exp(−0.3·age) + importance/10 + relevance`（relevance 命中为 0.6，否则 0.1）。排第一的记忆及其分数是：

- A. `[t=1] Isabella said she is planning a party`，约 1.707
- B. `[t=2] I would enjoy a party at the cafe`，约 1.749
- C. `[t=3] Klaus mentioned he is writing a paper`，约 1.141
- D. `[t=0] saw Isabella at the cafe`，约 1.301

**Q6.** 讲义练习 1 要求把 agent 数增加到 10。直接调用 `run_simulation(n_agents=10)` 的结果是：

- A. 10/10 到达，涌现规模随人数扩大
- B. 程序报 `IndexError`
- C. 0/10 到达
- D. 5/10 到达——邀请传播是主循环里写死的（只给 agent-1～4 发邀请），agent-5～9 从未被邀请

**Q7.** 把 `Agent.reflect` 替换为空函数（去掉反思）后运行，结果是：

- A. 只有 agent-0 到达（1/5），因为 `update_plan` 只看 `beliefs`，而 belief 只能由 `reflect` 写入
- B. 仍然 5/5 到达，因为邀请已经写进了记忆
- C. 0/5 到达
- D. 程序崩溃

**Q8.** 调用 `run_simulation(n_agents=5, ticks=5)`，结果是 0/5 到达。原因是：

- A. 5 个 tick 不够邀请传播完
- B. 反思窗口只有 5 个 tick
- C. 计划的执行时刻被写死为 `tick=5`，而 `range(5)` 只到 tick 4，连 host 也不会出发
- D. HobbsCafe 有容量限制

---

## 三、动手 / 代码题

**Q9.** 代码结尾打印 "No orchestrator. One seed. The rest is memory + reflection + plan."，但邀请传播是这样写的：

```python
        if tick == 0:
            for i in (1, 2):
                agents[i].observe(tick, f"agent-0 invited me to a party at HobbsCafe at tick 5", importance=8)
        if tick == 1:
            agents[3].observe(tick, f"agent-1 invited me to a party at HobbsCafe at tick 5", importance=7)
        if tick == 2:
            agents[4].observe(tick, f"agent-2 invited me to a party at HobbsCafe at tick 5", importance=7)
```

1. 这段代码与"没有编排者"的说法矛盾在哪里？它还会导致哪两个可复现的问题？
2. 改写传播逻辑：在派对之前的每个 tick，**持有派对信念的 agent 自己**随机邀请 1 个尚未知情的 agent。给出代码，并报告 N = 5、10、20 时的到达人数。

**Q10.** 当前 `reflect` 的实现：

```python
    def reflect(self, tick: int) -> None:
        recent_important = [m for m in self.stream if m.importance >= 6 and tick - m.ts <= 5]
        for m in recent_important:
            if "invited" in m.content and "party at" in m.content:
                ...
```

1. 指出它违反了讲义五条实现规则中的哪两条，以及 skill 文件中的哪条硬拒绝。
2. 实现一个阈值触发、基于 `retrieve_top_k` 排序检索、并记录来源记忆 id 的反思，验证低重要度记忆不会触发反思、邀请会触发。
3. 如果把二度邀请的 importance 从 7 改成 5，会发生什么？这暴露了什么问题？

**Q11.** 审视 `retrieve_top_k`：

```python
    def score(m: Memory) -> float:
        recency = math.exp(-0.3 * (tick - m.ts))
        importance = m.importance / 10.0
        relevance = 0.6 if any(w in m.content.lower() for w in query.lower().split()) else 0.1
        return recency + importance + relevance
```

1. relevance 的实现与讲义的定义有哪些差距？举一个误判的例子。
2. 三个分量的取值范围分别是多少？这对排序意味着什么？
3. 这个函数在模拟主流程中被调用了吗？

**Q12.** 讲义练习 4：HobbsCafe 最多容纳 4 个 agent。

1. 在现有代码里加入容量约束，10 个 agent（配合 Q9 的传播改写）时有多少人进入？被挡在门外的 agent 应该如何处理？
2. 讲义说该架构"does not infer social-physical norms from the environment alone"。结合本题解释：为什么空间/社会规范必须显式编码？

---

## 四、面试高频题

**Q13.**（基础必考）介绍 Generative Agents（Smallville）的架构，以及每个组件解决什么问题。

**Q14.**（原理深挖）记忆检索为什么要同时用 recency、importance、relevance 三个分量？只用 embedding 相似度会出什么问题？

**Q15.**（工程实践）你要做一个 200 个 agent、模拟 30 天的用户行为仿真来评估一个新功能。请估算成本并给出控制成本与保证质量的设计。

**Q16.**（原理深挖）什么叫"涌现"？如何判断一个多 agent 模拟里的群体行为是真正的涌现，而不是被脚本写出来的？

**Q17.**（追问型）反思会产生"幻觉的关系"（reflection hallucination），而反思结果又会写回记忆、被后续检索使用。这和阶段 16 · 13 的 memory poisoning 有什么关系？如何缓解？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："a three-part architecture: memory stream (natural-language log), reflection (higher-level syntheses ...), and plan (day-level behavior, then sub-plans)." A 是脚本化任务团队（讲义说 Smallville 正是要超越这种模式）；B 是 LLM 内部结构；D 混入了无关组件。注意消融部分讲义说的是 "observation, reflection, and plan" 三项。

### Q2 — 答案：A

讲义：recency 是按年龄指数衰减，importance 由 agent 在写入时自评 1–10 并缓存，relevance 是与当前查询的余弦相似度（基于 embedding）。D 违背了讲义规则 "Retrieval is ranked, not filtered ... do not use hard filters (which lose context)"。

### Q3 — 答案：D

讲义规则 4："Trigger when the sum of importance of unprocessed memories exceeds a threshold (e.g., 150)." A 是 skill 文件明确的硬拒绝："Designs that run reflection every tick. This is budget-inefficient"——而本节代码恰恰每个 tick 对每个 agent 都调用 `reflect`。

### Q4 — 答案：B

讲义："Agents walk into closed stores. Agents try to use the same single-person bathroom. Agents eat in rooms not intended for eating." 另外两类已记录的失效是记忆膨胀和反思幻觉。A、C、D 讲义没有提及。

### Q5 — 答案：B

实算（tick = 4）：

| 记忆 | recency | importance | relevance | 合计 |
|------|---------|-----------|-----------|------|
| t=0 saw Isabella at the cafe | e^−1.2 ≈ 0.301 | 0.4 | 0.6 | 1.301 |
| t=1 Isabella ... planning a party | e^−0.9 ≈ 0.407 | 0.7 | 0.6 | 1.707 |
| t=2 I would enjoy a party at the cafe | e^−0.6 ≈ 0.549 | 0.6 | 0.6 | 1.749 |
| t=3 Klaus ... writing a paper | e^−0.3 ≈ 0.741 | 0.3 | 0.1 | 1.141 |

输出顺序 t=2、t=1、t=0，与实际运行一致。t=2 的 importance 比 t=1 低，但更新，recency 弥补了差距；t=3 最新但不相关，被排除在 top-3 之外。

### Q6 — 答案：D

实测 `run_simulation(n_agents=10)` 输出 `5/10 agents converged`。邀请只在 tick 0、1、2 硬编码发给 agent-1～4，agent-5～9 永远收不到。反过来，`n_agents=3` 会因 `agents[3]` 越界抛 `IndexError`——所以 B 描述的是 N < 5 的情况。讲义练习 1 问"增加到 10 个 agent，涌现是否仍然发生"，在原代码下这个问题无法被检验，必须先把传播改成由 agent 驱动（见 Q9）。

### Q7 — 答案：A

实测 1/5。`update_plan` 只检查 `self.beliefs`，而唯一能往 `beliefs` 里写入派对信念的就是 `reflect`（agent-0 在初始化时直接被写入信念，所以它仍会出发）。代码 Takeaway "reflection is load-bearing: dropping it stops belief formation" 因此在代码里成立，但这是**构造出来的**：邀请记忆本身已经包含全部信息（谁、哪里、何时），所谓"反思"只是把它复制成一句固定字符串。这与 Park 消融实验中"没有反思就无法形成高阶信念、交互流于表面"的含义并不相同。

### Q8 — 答案：C

`update_plan` 写死 `Plan(tick=5, ...)`，`act` 只在 `p.tick == tick` 时移动；`range(5)` 产生 0–4，tick 5 永远不会到来。实测 `ticks=5` 输出 0/5，`ticks=7` 输出 5/5。同时，邀请里的 "at tick 5" 并没有被解析——即使邀请写 "at tick 3"，计划仍是 tick 5（已实测）。

### Q9 — 参考答案

1. 矛盾在于：传播路径（谁、在哪一 tick、邀请谁）完全由主循环这个"上帝视角"决定，agent-0 的计划里并没有"去邀请别人"的步骤，被邀请的 agent 也从不主动转告。主循环本身就是编排者。可复现的问题：
   - `n_agents=10` 时只有 5/10 到达（Q6）；
   - `n_agents < 5` 时 `IndexError`（`agents[3]` / `agents[4]` 越界）。
2. 参考改写（已运行验证）：

```python
PARTY_BELIEF = "there is a party I was invited to"

def run_emergent(n_agents=10, ticks=8, fanout=1, capacity=None, seed=0):
    rng = random.Random(seed)
    agents = [Agent(f"agent-{i}", location="home") for i in range(n_agents)]
    host = agents[0]
    host.stream.append(Memory(0, "goal", "host a Valentine's party at HobbsCafe at tick 5", 10))
    host.plans.append(Plan(tick=5, where="HobbsCafe", note="host the party"))
    host.beliefs.append(PARTY_BELIEF)
    for tick in range(ticks):
        if tick < 5:                                     # 派对前：知情者自己决定邀请谁
            speakers = [a for a in agents if PARTY_BELIEF in a.beliefs]
            for a in speakers:
                others = [b for b in agents if b is not a and PARTY_BELIEF not in b.beliefs]
                for b in rng.sample(others, min(fanout, len(others))):
                    b.observe(tick, f"{a.name} invited me to a party at HobbsCafe at tick 5", importance=7)
        for a in agents:
            a.reflect(tick); a.update_plan(tick); a.act(tick)
    return sum(1 for a in agents if a.location == "HobbsCafe")
```

   实测：N = 5、10、20 分别 5/5、10/10、20/20 到达。原因是每个知情者每 tick 邀请 1 人，知情人数每 tick 大致翻倍，tick 0–4 共 5 轮足以覆盖 32 人。这才符合讲义"Neighbors tell other neighbors. The invitation spreads without central coordination."的描述。进一步的真实化：邀请应作为 agent 计划中的一个动作（"告诉朋友"），邀请对象来自社交关系图而非全局随机。

### Q10 — 参考答案

1. 违反的规则：
   - 规则 3 "Retrieval is ranked, not filtered"：用 `importance >= 6 and tick - m.ts <= 5` 做硬过滤；
   - 规则 4 "Reflection runs periodically ... when the sum of importance of unprocessed memories exceeds a threshold"：这里每个 tick 都跑，没有阈值；
   - skill 文件硬拒绝："Designs that run reflection every tick."
   - 另外，反思结果不记录来源记忆 id，违背讲义对反思幻觉的缓解建议（"include source memory ids in reflection prompts and verify at retrieval time"）。
2. 参考实现（已运行验证）：

```python
@dataclass
class ThresholdAgent(Agent):
    THRESHOLD = 7                 # 微缩版阈值；讲义示例为 150
    unprocessed: int = 0
    reflections_run: int = 0

    def observe(self, tick, content, importance=3):
        super().observe(tick, content, importance)
        self.unprocessed += importance

    def reflect(self, tick):
        if self.unprocessed < self.THRESHOLD:
            return                                        # 未达阈值，不花预算
        self.unprocessed = 0
        self.reflections_run += 1
        top = retrieve_top_k(self.stream, "invited party", tick, k=3)   # 排序检索
        sources = [i for i, mem in enumerate(self.stream) if mem in top]
        if any("invited" in mem.content and "party at" in mem.content for mem in top):
            belief = "there is a party I was invited to"
            if belief not in self.beliefs:
                self.beliefs.append(belief)
                self.stream.append(Memory(tick, "reflection", f"{belief} (sources={sources})", 8))
```

   验证：只观察到 importance 2 的 "saw a cat" 时，`reflections_run == 0`；再观察到 importance 7 的邀请后触发一次，写入 `there is a party I was invited to (sources=[0, 1])`；把 `run_simulation` 中的 `Agent` 换成 `ThresholdAgent` 后仍是 5/5 到达。注意子类必须同样加 `@dataclass`，否则基类生成的 `__init__` 不会初始化新字段（我们第一次尝试用 `__post_init__` 就因此报了 `AttributeError`）。
3. 实测：importance 为 5 的邀请不满足 `>= 6`，不会形成信念，`plans` 为空——收到邀请也不会去。这说明"是否赴约"被一个与语义无关的硬阈值卡死，importance 的轻微变化会让涌现整体消失或出现，结果非常脆弱；排序检索 + 阈值触发的设计更平滑。

### Q11 — 参考答案

1. 讲义的 relevance 是"Cosine similarity (embedding-based)"，代码是**子串匹配**的二值打分（命中 0.6、否则 0.1）：
   - 子串误判：查询 "cafe" 会命中 "the cafeteria was closed"（`'cafe' in 'the cafeteria was closed'` 为 True，已验证）；
   - 同义词漏判："coffee shop" 与 "cafe" 语义相同却得 0.1；
   - 没有程度区分：只命中一个词和命中全部词同分。
2. recency ∈ (0, 1]，importance ∈ [0.1, 1.0]，relevance ∈ {0.1, 0.6}，三者直接相加、权重都是 1。relevance 的最大差距只有 0.5，而 recency 在 0–1 之间连续变化——一条刚写入但不相关的记忆（recency 1.0）可以压过一条稍旧但相关的记忆。讲义公式里有 `w_recency / w_importance / w_relevance` 三个权重，生产实现通常先把各分量归一化到同一范围再加权。
3. 没有。`retrieve_top_k` 只在 `demo_retrieval` 中演示，`run_simulation` 里的 agent 从不检索记忆，`reflect` 直接遍历全部 stream。讲义 Build It 中"MemoryStream — append-only log with recency/importance/relevance retrieval"作为模拟组件，在代码里其实是孤立的。

### Q12 — 参考答案

1. 在 Q9 的 `run_emergent` 中加入容量检查（已运行验证）：

```python
            for p in a.plans:
                if p.tick == tick:
                    if capacity is not None and p.where == "HobbsCafe" and at_cafe >= capacity:
                        a.observe(tick, "HobbsCafe is full", importance=6)   # 被拒也是一条观察
                        continue
                    a.location = p.where
            at_cafe = sum(1 for x in agents if x.location == "HobbsCafe")
```

   `capacity=4`、10 个 agent 时实测 4 人进入。被挡在门外的 agent 应：把"满员"作为一条观察写入记忆 → 触发局部重规划（讲义规则 5："regenerate the affected segment only"），例如改去附近地点、或稍后再试 → 宿主也应能观察到满员并调整（分批、换场地）。否则就会出现 Park 记录的"多人共用单人卫生间"式失效：所有人都按原计划执行，与物理约束冲突。
2. 原因：LLM 只"知道"文本里写了什么。agent 的计划是"5 点去 Hobbs Cafe"，环境里"容量 4"如果没有以观察或硬约束的形式进入它的上下文，它没有理由推断出来。Park 的系统里商店营业时间、卫生间单人使用这些规范在环境中存在，但模型没能从环境中推断出来。因此讲义 Ship It 要求"Detect spatial / social norm violations explicitly. The architecture does not learn them."；skill 文件也把"没有显式空间/社会规范编码的设计"列为硬拒绝。工程做法：环境层做硬约束检查（拒绝动作并返回原因），同时把规范写进可检索的记忆或世界描述。

### Q13 — 参考回答要点

- **Memory stream**：append-only 的自然语言日志，记录观察、行动、反思、计划；检索时按 recency + importance + relevance 加权取 top-k。解决"LLM 上下文有限，长期经历怎么记"的问题。
- **Reflection**：importance 累积到阈值时，从近期记忆生成高层结论（"我喜欢和人聊音乐"），写回记忆。解决"只有零散观察、没有长期信念"的问题——讲义称之为架构里的"长期信念"。
- **Plan**：日 → 小时 → 动作的分层计划，观察冲突时局部重规划。解决"行为变成对刺激的随机反应、目标消散"的问题。
- **消融**：去掉任一组件，人类评分的 believability 都下降。
- **代表结果**：情人节派对——一个种子目标，经由双边邀请与个体计划，演化出多人按时聚会。
- 加分点：说出已知失效（空间规范、记忆膨胀、反思幻觉）以及适用边界（社会模拟 vs 任务执行）。

### Q14 — 参考回答要点

- **只用 relevance（embedding 相似度）的问题**：
  - 会反复取回很久以前、但与当前查询字面相似的记忆，忽略刚刚发生的事（缺 recency）；
  - 琐碎但相似的记忆（"吃了早饭"）与重大事件（"被邀请参加派对"）同权，重要事件被淹没（缺 importance）；
  - 对"我今天该干什么"这类宽泛查询，相似度区分度很低。
- **三个分量各自的作用**：recency 模拟遗忘、保证对当下情境的响应；importance 让"重大事件"长期可被想起；relevance 保证与当前任务相关。
- **工程要点**：各分量归一化到同一量纲再加权（本节代码直接相加，量纲不一致，见 Q11）；importance 在写入时由 LLM 打分并缓存，不在检索时重复计算；记录每次行动的检索轨迹（讲义 Ship It："Log the retrieval trace"）。
- 加分点：讲义规则 3 强调"排序而非过滤"——硬过滤（如只取 importance ≥ 6）会丢上下文，本节 `reflect` 就是反例。

### Q15 — 参考回答要点

- **成本估算框架**（讲义 Ship It："N agents × T ticks × calls-per-tick can dwarf your budget"）：假设每 agent 每 tick 有 importance 打分、检索后的计划/行动各 1 次调用，反思按阈值平均每 10 tick 一次；若 1 tick = 1 小时、每天活跃 16 tick，则 `200 × 16 × 30 × 约 2.1 次 ≈ 20 万次`调用，按每次数千 token 计可达数亿 token。具体数字取决于模型价格，必须先小规模实测每 tick 调用数和 token 数再外推。
- **控制成本**：
  - 事件驱动而非固定 tick：agent 没有新观察时跳过规划；
  - 反思阈值触发，不要每 tick 反思（skill 文件硬拒绝）；
  - 分层模型：importance 打分、简单动作用小模型，反思与日计划用大模型；
  - 记忆压缩：定期 summarize-and-prune 低重要度记忆，控制检索与上下文成本（skill 文件：N > 50 必须有压缩策略）；
  - 可缓存的 prompt 前缀（人设、世界描述）。
- **保证质量**：
  - 记忆落到真实存储（向量库 / Postgres），记录检索轨迹便于调试；
  - 显式编码空间与社会规范，并统计违规次数作为失效信号；
  - 评估指标：believability（人工抽样评分）、目标达成率、协调事件次数、规范违规率；
  - 先跑 N = 10–20 的小规模试验校准，再扩到 200。
- 常见误区：用模拟结果直接替代 A/B 测试——讲义："Faster than A/B tests; accuracy is contested."

### Q16 — 参考回答要点

- **定义**：讲义："system-level behavior (a party) arose from local interactions (bilateral invitations + individual planning) without a central orchestrator."
- **判断标准**：
  - 群体行为没有在任何单个 agent 的指令或主循环中被直接写出；
  - 信息传播路径由 agent 的决策产生（谁告诉谁、何时告诉），而非预先指定；
  - 改变初始条件（人数、社交图、种子目标）后，群体行为会以可解释但非预设的方式变化（例如 N 增大后仍能扩散，或出现竞争目标的分流）；
  - 能通过消融定位到产生该行为的局部机制。
- **反例**：本节代码——邀请路径由主循环写死，N = 10 时一半人永远收不到；它演示的是"三组件如何把一条邀请转成计划"，而不是涌现本身（见 Q9）。
- 加分点：讲义练习 3（竞争的种子目标："Klaus wants to give a research talk at 5pm"）是检验涌现的好实验——观察人群如何分流、由什么决定。

### Q17 — 参考回答要点

- **关系**：反思幻觉是**单个 agent 内部**的记忆投毒——反思编造的关系写回 memory stream，之后被检索、被当作事实用于计划和新的反思，错误自我强化。若这些记忆再通过对话传给其他 agent，就变成阶段 16 · 13 所说的跨 agent 投毒。
- **缓解**：
  - 讲义："include source memory ids in reflection prompts and verify at retrieval time"——每条反思带来源 id，检索时检查来源是否存在、是否支持该结论；
  - append-only：发现错误时写入更正记录（supersede），不修改原条目；
  - 反思与观察在检索时区别对待（如给反思单独的置信度或较低的默认权重）；
  - 对高影响信念（关系、承诺）要求多条独立观察支持；
  - 定期压缩时只保留有来源支撑的反思。
- 常见误区：直接删除错误反思——会丢失审计轨迹，也无法分析幻觉是怎么产生的。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：讲义列出的先修课，agent 的状态、消息与行动抽象。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：讲义列出的先修课，append-only、provenance 与记忆投毒。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)：单 agent 长期记忆的分层管理，对应 memory stream 的工程实现。
- [阶段 14 · 08 记忆块与休眠时计算](../../../14-agent-engineering/08-memory-blocks-sleep-time-compute/docs/zh.md)：离线整理记忆，与"反思"思路相近。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md)：另一种"把自我总结写回记忆"的范式。

### 本节被哪些后续内容用到
- [阶段 16 · 18 心智理论与涌现协调](../../18-theory-of-mind-coordination/docs/zh.md)：在生成式 agent 的基础上推断他人信念、实现涌现协调。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：模拟中信息级联与同质化的失效分析。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：believability、协调事件等模拟评估指标。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：长时模拟的持久化与断点续跑。

### 延伸关键词
`Generative Agents` · `Smallville` · `memory stream` · `recency / importance / relevance` · `reflection` · `hierarchical planning` · `believability` · `emergent behavior` · `spatial norm errors` · `memory compaction` · `reflection hallucination` · `agent-based modeling` · `NPC AI`
