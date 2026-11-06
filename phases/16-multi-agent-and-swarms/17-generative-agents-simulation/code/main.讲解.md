# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 17 节 生成式 Agents 与涌现模拟 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数；`run_simulation(n_agents, ticks)` 可在交互环境中改参调用） ｜ **依赖**：仅标准库（`math`、`dataclasses`；`time` 被导入但未使用），无需 LLM、无需网络

---

## 1. 这份代码在考察什么

讲义介绍 Park et al. 2023 的 Smallville：25 个 agent，每个都有 **memory stream**（记忆流）、**reflection**（反思）、**plan**（计划）三个组件；只给一个 agent 种下"办情人节派对"的目标，邀请便在人群中传播，最后多人按时聚到 Hobbs Cafe。这份代码是一个"无 LLM 的微缩版"：

1. **Agent 的三件套**：`stream`（记忆列表）、`reflect`（从高重要度记忆形成信念）、`update_plan` + `act`（按信念制定计划并在指定 tick 执行）；
2. **派对场景**：5 个 agent、6 个 tick，agent-0 是 host，邀请按预设路径传到其他 4 人，最终统计有多少人到达 HobbsCafe；
3. **检索演示**：`retrieve_top_k` 用 recency + importance + relevance 给 4 条记忆打分，取 top-3。

> 一句话：**用最少的代码把"观察 → 反思成信念 → 信念变计划 → 按时行动"这条链跑通**。但要看清它离真正的"涌现"有多远：邀请传播是主循环硬编码的（主循环本身就是编排者）、反思是固定字符串匹配、计划时刻写死为 tick 5、检索函数在模拟中从未被调用。这些简化正好对应讲义的五条实现规则，逐一对照是本节最好的学习方式。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Memory` | `@dataclass` | 时间戳、类型（observation / reflection / goal）、内容、importance | memory stream 的一条记录 |
| `Plan` | `@dataclass` | 执行 tick、地点、备注 | 计划（只有一层） |
| `Agent` | `@dataclass` + 方法 | `stream / plans / beliefs / location`；`observe`、`reflect`、`update_plan`、`act` | 生成式 agent |
| `retrieve_top_k` | 函数 | 按 recency + importance + relevance 排序取前 k | 记忆检索 |
| `run_simulation` | 函数 | 创建 agent、种下目标、逐 tick 注入邀请、调用三件套、统计到达人数 | 派对场景 + 主循环 |
| `demo_retrieval` | 函数 | 4 条记忆、查询 "party cafe"、打印 top-3 | 检索演示 |
| `TICK_DURATION_S` | 常量 | 定义了但从未使用 | — |

数据流：`main()` → `run_simulation()`：初始化 → `for tick in range(6)`：（主循环按 tick 注入邀请观察）→ 每个 agent `reflect → update_plan → act` → 打印移动 → 统计 → `demo_retrieval()`。

讲义 Build It 中列出的是 `MemoryStream` 类、`reflect(stream)` 与 `plan(agent_state)` 函数，以及"day-level and hour-level plans"；实际代码没有 `MemoryStream` 类（记忆就是 `Agent.stream` 列表），`reflect` 和 `update_plan` 是 `Agent` 的方法，计划只有一层、只有一个固定时刻。

---

## 3. 逐段精讲

### 3.1 数据结构：`Memory`、`Plan`、`Agent`

```python
@dataclass
class Memory:
    ts: int
    kind: str
    content: str
    importance: int

@dataclass
class Agent:
    name: str
    location: str
    stream: list[Memory] = field(default_factory=list)
    plans: list[Plan] = field(default_factory=list)
    beliefs: list[str] = field(default_factory=list)

    def observe(self, tick: int, content: str, importance: int = 3) -> None:
        self.stream.append(Memory(tick, "observation", content, importance))
```

- `Memory` 对应讲义的记忆条目（时间戳、类型、自然语言描述、importance）。讲义提到的 relevance 需要 embedding，这里没有存向量；也没有 `source_ids` 字段（skill 文件建议的 schema 是 `(ts, kind, content, importance, embedding_ref, source_ids)`）。
- `observe` 只做 `append`，没有修改操作——符合讲义规则 1 "Memory is append-only"。
- importance 由**调用方**传入（邀请为 8 或 7，默认 3），对应讲义"写入时打分并缓存"；真实系统中这一步由 LLM 对内容自评 1–10。
- `beliefs` 是一个独立的字符串列表——讲义里信念就是写回 stream 的 reflection 记忆，这里额外维护了一个列表，计划只看这个列表（见 3.3）。
- 可变默认值（列表）必须用 `field(default_factory=list)`。

### 3.2 `reflect`：硬过滤 + 字符串匹配

```python
    def reflect(self, tick: int) -> None:
        recent_important = [m for m in self.stream if m.importance >= 6 and tick - m.ts <= 5]
        for m in recent_important:
            if "invited" in m.content and "party at" in m.content:
                belief = f"there is a party I was invited to"
                if belief not in self.beliefs:
                    self.beliefs.append(belief)
                    self.stream.append(Memory(tick, "reflection", belief, 8))
```

- 选材：importance ≥ 6 **且** 5 个 tick 内的记忆——这是**硬过滤**，违背讲义规则 3 "Retrieval is ranked, not filtered"。把二度邀请的 importance 改成 5，该 agent 就永远不会形成信念、不会赴约（已实测 `plans` 为空）。
- 综合：只认识一种模式——内容同时包含 "invited" 和 "party at"——生成一句固定信念。真实的反思是 LLM 针对一组记忆提出"高层问题"并给出带依据的回答。
- 触发：`run_simulation` 每个 tick 对每个 agent 都调用 `reflect`，违背讲义规则 4（按未处理 importance 之和超过阈值触发），也是 skill 文件的硬拒绝项"run reflection every tick"。
- 写回：信念同时写入 `beliefs` 和 `stream`（kind="reflection", importance=8），后者让反思"可被检索"，与讲义一致；但没有记录依据了哪些记忆（讲义针对反思幻觉的缓解措施是"include source memory ids"）。
- `f"there is a party I was invited to"` 是一个没有占位符的 f-string，加不加 `f` 结果一样。

### 3.3 `update_plan` 与 `act`：写死的 tick 5

```python
    def update_plan(self, tick: int) -> None:
        if "there is a party I was invited to" in self.beliefs:
            if not any(p.where == "HobbsCafe" for p in self.plans):
                self.plans.append(Plan(tick=5, where="HobbsCafe", note="attend the party"))

    def act(self, tick: int) -> str:
        for p in self.plans:
            if p.tick == tick:
                self.location = p.where
                return f"{self.name} moves to {p.where} ({p.note})"
        return f"{self.name} remains at {self.location}"
```

- 计划只有一层、一个动作。讲义的"日 → 小时 → 动作"分解和"观察冲突时局部重规划"都没有实现。
- `Plan(tick=5, ...)` 是写死的：邀请内容里虽然写着 "at tick 5"，但并没有被解析。实测把邀请改成 "at tick 3"，计划仍是 tick 5。
- `act` 只在 `p.tick == tick` 时移动，而模拟默认 `ticks=6`（`range(6)` 包含 5）。实测 `run_simulation(5, ticks=5)` 输出 **0/5**——连 host 都不出发；`ticks=7` 恢复为 5/5。
- `any(... for p in self.plans)` 防止重复添加同一个计划，是一种幂等写法。
- 到达后 agent 永远停在 HobbsCafe，没有"派对结束回家"的计划。

### 3.4 `retrieve_top_k`：三分量打分

```python
def retrieve_top_k(stream, query, tick, k=3):
    def score(m: Memory) -> float:
        recency = math.exp(-0.3 * (tick - m.ts))
        importance = m.importance / 10.0
        relevance = 0.6 if any(w in m.content.lower() for w in query.lower().split()) else 0.1
        return recency + importance + relevance
    return sorted(stream, key=score, reverse=True)[:k]
```

- 对应讲义公式 `w_recency·e^(−decay·age) + w_importance·importance + w_relevance·cos_sim`，这里 decay = 0.3、三个权重都是 1。
- **recency**：`e^(−0.3·age)`，age = 0 时为 1，age = 3 时约 0.41，age = 10 时约 0.05。
- **importance**：除以 10 归一到 0.1–1.0。
- **relevance**：讲义是 embedding 余弦相似度，代码是**子串匹配的二值分**：查询中任一词是记忆内容的子串就得 0.6，否则 0.1。问题：
  - 子串误判："cafe" 命中 "cafeteria"（已验证 `'cafe' in 'the cafeteria was closed'` 为 True）；
  - 同义词漏判："coffee shop" 不会命中 "cafe"；
  - 命中一个词与命中全部词同分。
- 量纲不一致：recency 连续分布在 (0, 1]，relevance 只有 0.5 的差距，三者直接相加，一条刚写入的无关记忆可以压过一条稍旧的相关记忆。生产中会先各自归一化再按权重相加。
- `sorted(..., key=score, reverse=True)[:k]`：对全部记忆排序后切片，复杂度 O(n log n)。记忆很多时可用 `heapq.nlargest(k, stream, key=score)`；更大规模要靠向量索引先召回候选。
- **最关键的一点**：这个函数只在 `demo_retrieval` 里被调用，`run_simulation` 中的 agent 从不检索记忆。讲义说检索是三件套的核心机制，代码里它和模拟是脱节的。

### 3.5 `run_simulation`：主循环就是编排者

```python
    agents[0].stream.append(Memory(0, "goal", "host a Valentine's party at HobbsCafe at tick 5", 10))
    agents[0].plans.append(Plan(tick=5, where="HobbsCafe", note="host the party"))
    agents[0].beliefs.append("there is a party I was invited to")

    for tick in range(ticks):
        if tick == 0:
            for i in (1, 2):
                agents[i].observe(tick, f"agent-0 invited me to a party at HobbsCafe at tick 5", importance=8)
        if tick == 1:
            agents[3].observe(tick, f"agent-1 invited me to a party at HobbsCafe at tick 5", importance=7)
        if tick == 2:
            agents[4].observe(tick, f"agent-2 invited me to a party at HobbsCafe at tick 5", importance=7)

        for a in agents:
            a.reflect(tick)
            a.update_plan(tick)
            action = a.act(tick)
```

- **种子**：host 拿到目标记忆（kind="goal"，importance 10）、一个计划，以及一条"我被邀请参加派对"的信念——给主人写"被邀请"有些别扭，但它保证了 host 也有计划（实际上计划已经直接加了）。
- **传播**：谁在哪个 tick 邀请谁，全部由主循环决定。agent-0 的计划里没有"邀请"这个动作，agent-1 / agent-2 也不会自己转告——"agent-1 → agent-3"只是主循环替它写进 agent-3 的记忆。代码最后打印的 "No orchestrator" 与此矛盾：**主循环本身就是编排者**。
- 由此导致两个可复现的问题（已实测）：
  - `run_simulation(n_agents=10)` → **5/10**，agent-5～9 永远收不到邀请（讲义练习 1 问"10 个 agent 时涌现是否仍发生"，在原代码下无法检验）；
  - `run_simulation(n_agents=3)` → `IndexError: list index out of range`（`agents[3]` 越界）。
- 每个 tick 对所有 agent 依次 `reflect → update_plan → act`：同一 tick 内收到的邀请会立刻被反思、立刻形成计划，没有任何延迟或遗漏的可能。
- 最终统计 `sum(1 for a in agents if a.location == "HobbsCafe")`：生成器表达式计数。讲义预期"at least 3 of the 5"，实际 5/5——因为路径是写死的，结果必然全员到达。

### 3.6 `demo_retrieval`

```python
    stream = [
        Memory(0, "observation", "saw Isabella at the cafe", importance=4),
        Memory(1, "observation", "Isabella said she is planning a party", importance=7),
        Memory(2, "reflection", "I would enjoy a party at the cafe", importance=6),
        Memory(3, "observation", "Klaus mentioned he is writing a paper", importance=3),
    ]
    top = retrieve_top_k(stream, query="party cafe", tick=4, k=3)
```

逐条打分（tick = 4，已用代码复算）：

| 记忆 | recency | importance | relevance | 合计 | 名次 |
|------|---------|-----------|-----------|------|------|
| t=2 I would enjoy a party at the cafe | 0.549 | 0.6 | 0.6 | 1.749 | 1 |
| t=1 Isabella said she is planning a party | 0.407 | 0.7 | 0.6 | 1.707 | 2 |
| t=0 saw Isabella at the cafe | 0.301 | 0.4 | 0.6 | 1.301 | 3 |
| t=3 Klaus mentioned he is writing a paper | 0.741 | 0.3 | 0.1 | 1.141 | 4 |

- t=2 的 importance（6）低于 t=1（7），但更新，recency 多出 0.14，反超 0.04。
- t=3 最新（recency 最高），但不相关、重要度低，落选。这说明三项需要共同作用——对应 Takeaway "no single score is enough"：只看 recency 会选 t=3，只看 importance 会把 t=1 排第一。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不调用 LLM，用字符串规则模拟 | 零成本、确定性、秒级运行 | 反思、计划都退化成模式匹配；真实系统中每一步都是 LLM 调用 |
| 邀请路径由主循环硬编码 | 让输出稳定可读 | 主循环成为编排者，不是涌现；N ≠ 5 时出错或覆盖不全；应改为由 agent 信念驱动的转告 |
| 反思用 importance ≥ 6 + 5 tick 窗口过滤 | 简单 | 违背"排序而非过滤"；importance 稍低就整条链断掉；应排序检索 |
| 每 tick 都反思 | 实现最简单 | 违背阈值触发规则，真实 LLM 下成本极高；应按未处理 importance 累加触发 |
| 计划时刻写死 tick 5 | 让演示对齐 | 不解析邀请内容；`ticks ≤ 5` 时无人出发；应从观察中抽取时间地点 |
| 计划只有一层 | 聚焦机制 | 没有日/小时/动作分解与局部重规划 |
| 检索用子串匹配、权重全为 1 | 不需要 embedding | 子串误判、同义词漏判、量纲不一致；生产用 embedding + 归一化加权 |
| 检索只在 demo 中调用 | 分开演示 | 模拟中的 agent 从不检索，三件套之间缺了关键连接 |
| 没有空间/容量约束 | 场景简单 | 复现不了 Park 记录的空间规范错误；讲义要求显式编码规范 |
| 信念单独存一个列表 | 方便 `update_plan` 查询 | 与 stream 中的反思记录形成两份状态，可能不一致 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 方法 | `class Agent: ... def observe(self, ...)` | 数据类可以带行为方法 |
| `field(default_factory=list)` | `stream: list[Memory] = field(default_factory=list)` | 每个实例一份新列表，避免共享可变默认值 |
| 带默认值的参数 | `def observe(self, tick, content, importance: int = 3)` | 调用时可省略 |
| 列表推导式 + 复合条件 | `[m for m in self.stream if m.importance >= 6 and tick - m.ts <= 5]` | 过滤记忆 |
| `in` 判断子串 / 成员 | `"invited" in m.content`、`belief not in self.beliefs` | 字符串子串、列表成员 |
| `any` + 生成器 | `any(p.where == "HobbsCafe" for p in self.plans)` | 任一满足即为 True，短路求值 |
| 嵌套函数 | `retrieve_top_k` 内的 `def score(m)` | 闭包读取外层的 `tick`、`query` |
| `math.exp` | `math.exp(-0.3 * (tick - m.ts))` | 指数衰减 |
| `sorted` + `key` + `reverse` + 切片 | `sorted(stream, key=score, reverse=True)[:k]` | 降序排序后取前 k |
| `str.lower` / `str.split` | `query.lower().split()` | 小写化、按空白切词 |
| 元组字面量遍历 | `for i in (1, 2):` | 遍历固定集合 |
| `str.startswith` | `action.startswith(a.name + " moves")` | 判断前缀，用来只打印移动的动作 |
| 生成器表达式计数 | `sum(1 for a in agents if a.location == "HobbsCafe")` | 统计满足条件的元素个数 |
| f-string 宽度 | `{a.name:10s}`、`{m.kind:11s}` | 左对齐 |
| 子类化 dataclass | （测验 Q10）`@dataclass class ThresholdAgent(Agent)` | 子类新增字段时必须同样加 `@dataclass`，否则不会被 `__init__` 初始化 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，瞬间完成，结果确定）：

```text
GENERATIVE AGENTS (miniature) — 5 agents, 6 ticks

--- tick 0 ---
  agent-0 -> agent-1: invitation
  agent-0 -> agent-2: invitation
--- tick 1 ---
  agent-1 -> agent-3: second-degree invitation
--- tick 2 ---
  agent-2 -> agent-4: second-degree invitation
--- tick 3 ---
--- tick 4 ---
--- tick 5 ---
  agent-0 moves to HobbsCafe (host the party)
  agent-1 moves to HobbsCafe (attend the party)
  agent-2 moves to HobbsCafe (attend the party)
  agent-3 moves to HobbsCafe (attend the party)
  agent-4 moves to HobbsCafe (attend the party)

5/5 agents converged at HobbsCafe for the party.
No orchestrator. One seed. The rest is memory + reflection + plan.

RETRIEVAL DEMO — top-k by recency + importance + relevance
  query: 'party cafe' at tick 4
  [t=2] reflection  imp=6 :: I would enjoy a party at the cafe
  [t=1] observation imp=7 :: Isabella said she is planning a party
  [t=0] observation imp=4 :: saw Isabella at the cafe
```

逐项解读：

- **tick 0–2**：打印的"agent-0 -> agent-1: invitation"等是主循环的 `print`，不是 agent 的行为；收到邀请的 agent 在同一 tick 内就完成反思与计划（没有输出，因为 `act` 只打印移动）。
- **tick 3–4**：空白——没有任何事情发生，agent 没有日程、没有其他计划。
- **tick 5**：所有人同时移动，结果 5/5（讲义预期"至少 3/5"）。因为传播路径写死、每个被邀请者的 importance 都 ≥ 6，结果没有任何不确定性。
- **检索演示**：排序与第 3.6 节手算一致。
- **我们额外做的实验**（均已实测）：

| 改动 | 结果 | 说明 |
|------|------|------|
| `n_agents=10` | 5/10 | 后 5 个 agent 从未被邀请 |
| `n_agents=3` | `IndexError` | 硬编码访问 `agents[3]` |
| `ticks=5` | 0/5 | tick 5 永远不会到来 |
| 去掉 `reflect` | 1/5 | 只有 host 出发（Takeaway "reflection is load-bearing" 成立，但是构造出来的） |
| 二度邀请 importance 改为 5 | 该 agent 不赴约 | 硬阈值 ≥ 6 |
| 改为"知情者每 tick 自己邀请 1 人" | N = 5/10/20 全部到达 | 真正由 agent 驱动的传播 |

---

## 7. 动手改一改

1. **让传播真正涌现（讲义练习 1）**：删掉主循环中按 tick 写死的三段邀请，改为"持有派对信念的 agent 在派对前每个 tick 随机邀请 1 个未知情者"（参考测验 Q9），测 N = 5、10、20 的到达人数；再把随机邀请改为基于一张预设社交关系图。
2. **消融反思（讲义练习 2）**：去掉 `reflect`，确认只剩 host 到达；然后思考：如果 `update_plan` 直接读取邀请记忆（不经过信念），结果会怎样？这说明本代码中"反思必不可少"的结论来自什么？
3. **阈值触发 + 排序检索的反思**：实现 `ThresholdAgent`——`observe` 时累加 importance，超过阈值才反思；反思时用 `retrieve_top_k` 取证据，并把来源记忆下标写进反思内容（参考测验 Q10）。
4. **解析邀请内容**：用正则从邀请中抽取地点和时间（`at (\w+) at tick (\d+)`），据此生成计划；再加一个"派对时间改了"的新观察，实现局部重规划（讲义规则 5）。
5. **竞争目标（讲义练习 3）**：再给 agent-3 种下 "Klaus wants to give a research talk at 5pm"（地点 Library），两个目标同时传播；规定冲突时按"先收到 / 重要度高"选择，观察人群如何分流、由什么决定。
6. **空间约束（讲义练习 4）**：HobbsCafe 容量设为 4，满员时把"HobbsCafe is full"作为观察写入被拒者记忆并触发重规划（去附近地点）；统计违规次数作为评估指标。

---

## 8. 常见坑

- **把编排写在主循环里还称作涌现**：涌现要求群体行为由 agent 的局部决策产生；主循环按 tick 写死"谁邀请谁"就是中央编排。
- **硬编码索引**：`agents[3]`、`agents[4]` 让任何 N < 5 的配置崩溃，N > 5 的配置覆盖不全。
- **魔法数字耦合**：计划 tick 5 与模拟总 tick 数耦合，`ticks=5` 时整个模拟"静默失败"（0/5，无报错）。
- **硬过滤代替排序**：`importance >= 6` 这类阈值让结果对参数极其敏感，讲义明确要求排序检索。
- **每 tick 反思**：在真实 LLM 下成本 = N × T 次反思调用，skill 文件把它列为硬拒绝。
- **子串匹配当相关性**："cafe" 命中 "cafeteria"；应使用 embedding 余弦相似度。
- **分量不归一化**：recency、importance、relevance 量纲不同直接相加，权重失去意义。
- **信念与记忆两份状态**：`beliefs` 列表与 stream 中的 reflection 记录可能不一致，排查时要两处都看。
- **子类化 dataclass 忘加装饰器**：子类新增字段却不加 `@dataclass`，基类的 `__init__` 不会初始化它们；在基类没有 `__post_init__` 时，子类定义的 `__post_init__` 也不会被调用。
