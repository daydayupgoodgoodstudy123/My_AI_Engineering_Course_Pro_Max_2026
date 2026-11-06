# 测验 · 层级架构及其失效模式（Hierarchical Architecture and Its Failure Mode）

> **阶段 16 · 多智能体与集群 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 层级 = 嵌套的 supervisor | manager 管 sub-manager，sub-manager 管 worker；每个内部节点都要规划、分派、汇总，只有叶子干活 |
| 2 | 典型实现 | CrewAI `Process.hierarchical`（`manager_llm` 动态分派并验证输出）；LangGraph 嵌套 `create_supervisor`（内层图对外层是不透明节点） |
| 3 | 适用场景 | 任务确实对应组织结构（法务、财务、工程分别审查再汇总给高管）；局部汇总让顶层只看几个子摘要而非全部 worker 输出 |
| 4 | LLM manager ≠ 人类 manager | 人类对下属有稳定先验；LLM manager 每轮都从上下文重新推理组织结构，上下文的微小漂移就会让整棵树分错活 |
| 5 | 失效一：任务分配错误 | 顶层幻觉出错误分解并分给错的子 manager，子 manager 照做，错误要到顶层汇总才显现 |
| 6 | 失效二：输出误读 | 语义在每一层漂移，例如 "unable to verify claim X" 被总结成 "claim X not confirmed" |
| 7 | 失效三：共识循环 | 子 manager 互相矛盾 → 顶层要求协调 → 再下派 → worker 重跑 → 结果略有不同 → 循环；步数上限本身变成了超参数 |
| 8 | 关键判断 | 任务真的有独立子团队，还是一条线性流程伪装成树？后者用 sequential；前者用 hierarchical 并预设协调规则。讲义："Sequential often beats it." |
| 9 | 上线护栏 | 深度上限 2；协调预算（通常 2 轮）；每个汇总都带 provenance；记录分解并与用户问题 diff，发现漂移就告警；canary 问题 |
| 10 | 代码演示 | 顶层把 legal 误标为 finance：finance 尽职回答，legal 问题无人回答，汇总格式完美却答非所问 |

### 核心技能（能动手做到）

- [ ] 画出一个三层层级结构，说清每个内部节点做什么、信息在哪一层被压缩
- [ ] 区分"拼错成不存在的分支"（响亮）和"错成另一个存在的分支"（静默）两种分配错误
- [ ] 实现一个"必需领域 − 已覆盖领域"的漂移检测，并在汇总中输出告警
- [ ] 实现 canary worker：把原始用户问题原样下传，用来发现分解漂移
- [ ] 为分支间的分歧实现一个有轮数上限的协调循环，超限时带分歧提交
- [ ] 根据任务形状在 sequential、flat supervisor、hierarchical 之间做选择并说明理由

---

## 二、基础自测（选择题）

**Q1.** 讲义对层级架构的定义最准确的是：

- A. 所有 agent 平等地在群聊中轮流发言
- B. supervisor 的嵌套：manager 管 sub-manager，sub-manager 管 worker，内部节点规划、分派、汇总，只有叶子做实际工作
- C. 一条固定顺序的流水线，前一步的输出是后一步的输入
- D. 多个 worker 从同一个队列里抢任务

**Q2.** 子 manager 回报 "unable to verify claim X"，顶层 manager 在汇总中写成 "claim X not confirmed"。这属于讲义列出的哪一类失效？

- A. 输出误读（output misinterpretation）
- B. 任务分配错误（task assignment error）
- C. 共识循环（consensus loop）
- D. 拒绝服务（denial of service）

**Q3.** 讲义给出的"决定性问题"是：

- A. 团队里有多少个 LLM 可用
- B. manager 用的模型是否比 worker 更强
- C. 任务是真的有独立的子团队，还是一条线性流程伪装成了树
- D. 是否使用 CrewAI 而不是 LangGraph

**Q4.** 讲义 Ship It 对层级架构给出的默认数字是：

- A. 深度上限 5，协调轮数不设上限
- B. 深度上限 3，协调预算 10 轮
- C. 深度不设上限，但每层最多 2 个 worker
- D. 深度上限 2，协调预算通常为 2 轮

**Q5.** 本节代码中，顶层 manager 的分支标签出错有两种情况：拼成不存在的 `"legl"`，或错成另一个存在的 `"finance"`。下列说法正确的是：

- A. 两种情况都会抛出 `KeyError`，程序中止
- B. `"legl"` 会在汇总中产生 `MISSING[legl]` 和 "no such sub-manager"，错误响亮；`"finance"` 会产生格式正常、内容专业的汇总，错误静默
- C. 两种情况下 legal 分支都会被自动补上
- D. `"finance"` 会产生 `MISSING` 分支，`"legl"` 会被路由到 legal

**Q6.** 用 `build_hierarchy()` 构造的树执行 `top.run("Review GDPR compliance", ["legal"])`，lawyer 实际收到的问题是：

- A. `"Review GDPR compliance"`
- B. `"Review GDPR compliance -- branch: legal"`
- C. `"legal review of the feature"`
- D. 空字符串

**Q7.** 关于 LangGraph 嵌套 supervisor 与 CrewAI hierarchical 的对比，与讲义一致的是：

- A. LangGraph 的内层图对外层是不透明节点，可以分别单步调试每张图，更便于调试，但更难表达树结构的动态重组
- B. LangGraph 不支持嵌套，只能实现扁平 supervisor
- C. CrewAI hierarchical 没有 manager，由 worker 自行协商
- D. 两者完全等价，没有任何取舍

**Q8.** 讲义中的 canary question（金丝雀问题）指的是：

- A. 在生产流量中随机抽 1% 给新版本 manager
- B. 让 worker 回答一道已知答案的测试题来校准置信度
- C. 在 prompt 中埋入一个秘密 token 检测泄露
- D. 每一层都有一个 worker 始终收到**未经改写的原始用户问题**，用它的回答来检测分解漂移

---

## 三、动手 / 代码题

**Q9.** 讲义 Ship It："Alert on decomposition drift. Log the manager's decomposition per step; diff against the user query."

1. 写一个 `required_domains(user_query)`（基于关键字表）和 `drift_report(user_query, synth)`，输出 `missing`（问题需要但没有分支覆盖）与 `unrequested`（有分支但问题没要求）。
2. 对 `"Ship the premium tier feature to production after legal and engineering review."` 分别跑 happy 与 perturbed，写出报告结果。
3. 如果直接用代码里的原任务 `"Ship the premium tier feature to production."`，检测还能发现 legal 缺失吗？这说明了什么？

**Q10.** 讲义练习 3：实现 canary。要求给 `SubManager` 加一个 canary 判断函数，它读**原始用户问题**并判断问题属于哪个领域；若与本分支领域不符，就在本分支的汇总后追加 `CANARY ALERT`。写出代码，并讨论 manager 收到 canary 告警后应该怎么办。

**Q11.** 阅读 `SubManager.run`：

```python
def run(self, task: str) -> SubSummary:
    leaves = []
    for w in self.workers:
        sub_q = self.split.get(w.name, task)
        leaves.append(w.run(sub_q))
    summary = f"[{self.name}] aggregated: " + " | ".join(l.answer for l in leaves)
    return SubSummary(sub_manager=self.name, leaves=leaves, summary=summary)
```

1. 上游传下来的 `task` 在 `build_hierarchy()` 构造的树中被用到了吗？为什么？
2. 这对"在中间层发现漂移"意味着什么？
3. 请修改接口，让原始用户问题和上游任务都能一路下传，并在 `LeafOutput` 中记录完整的委托链（谁、在哪一层、把什么问题改写成了什么）。

**Q12.** 讲义的第三种失效是共识循环。请实现一个 `reconcile(branch_a, branch_b, max_rounds=2)`：两个分支每轮各给出结论，一致则返回；超过预算就"带着分歧提交"，并保留每一轮的历史。给出代码，并说明讲义为什么说"the limit itself is now a hyperparameter"。

---

## 四、面试高频题

**Q13.**（基础必考）层级多 agent 架构是什么？它和扁平 supervisor、sequential pipeline 分别适合什么任务？

**Q14.**（原理深挖）为什么讲义说"LLM manager 不同于人类 manager"？从上下文与推理方式的角度，解释为什么层级越深越容易出现分解漂移和语义漂移。

**Q15.**（工程实践）你接手一个三层层级的多 agent 系统，用户反馈"报告看起来很专业，但经常没回答我真正的问题"。你会怎么排查和改造？

**Q16.**（场景设计）为一个"新功能上线前的跨部门审查"设计多 agent 系统（工程、法务、财务、安全四个方面，最后给高管一页摘要）。你会用层级吗？深度多少？护栏有哪些？

**Q17.**（追问型）"人类公司都是层级结构，为什么不让 agent 系统也照搬公司的组织架构？深度为什么要限制在 2？"

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Hierarchical is supervisor nested. Manager agents over sub-managers over workers"，"Every internal node plans, delegates, and synthesizes. Only leaves do work." A 是群聊（阶段 16 · 10）；C 是 sequential pipeline；D 是队列驱动的 swarm。

### Q2 — 答案：A

讲义第二种失效的原例："Sub-manager returns 'unable to verify claim X.' Top manager summarizes as 'claim X not confirmed.' Meaning drifts at every level." "无法验证"（不知道）与"未被确认"（倾向于否定）语义不同。B 是分解/分派阶段的错误；C 是反复协调不收敛；D 不是讲义的概念。

### Q3 — 答案：C

讲义："does your task actually have independent sub-teams, or is it one linear flow pretending to be a tree? If the latter, use sequential. If the former, use hierarchical but budget explicit reconciliation rules." A、B、D 都不是选择架构的决定因素。

### Q4 — 答案：D

讲义 Ship It："Cap tree depth at 2. Three levels already hides most errors from observability."；"Explicit reconciliation budget. Set max rounds before the top manager must commit. Usually 2." 本节 `outputs/skill-hierarchy-fitness.md` 同样默认 2 轮，并要求深度 > 2 必须给出具体的审计或组织理由。

### Q5 — 答案：B

`TopManager.run` 中 `if label not in self.subs` 会构造一个 `MISSING[label]` 的 `SubSummary`，汇总里出现 "tried to delegate to 'legl' -- no such sub-manager"（已实测），不会抛异常，A 错。错成 `"finance"` 时，finance 子 manager 正常工作，返回 "Projected cost $42k/month; exceeds budget by 12%"，汇总格式与 happy path 毫无二致——这才是危险的静默错误。C、D 都没有对应的代码逻辑。

### Q6 — 答案：C

`SubManager.run` 用 `self.split.get(w.name, task)`：lawyer 在 split 中预设了 `"legal review of the feature"`，所以上游传来的 `"Review GDPR compliance -- branch: legal"`（B）被完全丢弃（已实测）。只有当 worker 在 split 中没有预设时才会收到 B。这意味着用户的真实问题（GDPR）从未到达叶子。

### Q7 — 答案：A

讲义："The inner supervisor has its own graph; the outer supervisor treats the inner graph as an opaque node. This is cleaner than CrewAI for debugging (you can step through each graph separately) but harder to express dynamic reshaping of the tree." B 错，嵌套正是 `create_supervisor(create_supervisor(...))`；C 错，CrewAI hierarchical 的核心就是 `manager_llm`；D 忽略了讲义指出的取舍。

### Q8 — 答案：D

讲义 Key Terms："Canary question — A worker that is always asked the original query unchanged, to detect drift." A 是金丝雀发布（canary release），名字相同但概念不同；B 是校准题；C 是金丝雀 token（用于检测泄露，见阶段 15 · 14）。

### Q9 — 参考答案

```python
DOMAIN_KEYWORDS = {
    "engineering": ["frontend", "backend", "api", "deploy", "ship"],
    "legal": ["legal", "contract", "gdpr", "compliance", "license"],
    "finance": ["cost", "budget", "pricing", "revenue"],
}

def required_domains(user_query):
    q = user_query.lower()
    return {d for d, kws in DOMAIN_KEYWORDS.items() if any(k in q for k in kws)}

def drift_report(user_query, synth):
    required = required_domains(user_query)
    covered = {b.sub_manager.split("-manager")[0].replace("eng", "engineering")
               for b in synth.branches if b.leaves}          # MISSING 分支没有 leaves，不算覆盖
    return {"missing": sorted(required - covered),
            "unrequested": sorted(covered - required)}
```

实测结果：

```text
required: {'legal', 'engineering'}
happy      {'missing': [], 'unrequested': []}
perturbed  {'missing': ['legal'], 'unrequested': ['finance']}
```

- 第 3 问：对原任务 `"Ship the premium tier feature to production."`，`required_domains` 只得到 `{'engineering'}`（"ship" 命中），**发现不了** legal 缺失。这说明代码末尾"User asked about legal/engineering review"只是旁白，用户意图并没有写进任务本身。漂移检测的前提是"用户要什么"被显式表达——生产中要么让用户/上游给出验收清单，要么先用一次独立的调用把问题解析成必需覆盖的方面，再与分解做 diff。
- 注意：从 `sub_manager` 名字反推领域（`split("-manager")`、`replace("eng", ...)`）很脆弱，正式实现应在 `SubSummary` 里显式记录 `domain` 字段。

### Q10 — 参考答案

```python
class CanarySubManager(SubManager):
    def __init__(self, name, workers, split, domain, canary):
        super().__init__(name, workers, split)
        self.domain = domain
        self.canary = canary                 # 读原始问题，返回它认为的领域

    def run(self, task, user_query=""):
        s = super().run(task)
        verdict = self.canary(user_query)    # 原始问题，未经任何改写
        if verdict != self.domain:
            s.summary += (f"  [CANARY ALERT: original query looks like "
                          f"'{verdict}', not '{self.domain}']")
        return s
```

用关键字版 canary 测试：finance 分支收到原始问题 "Check the contract clauses for GDPR compliance" 时，输出末尾出现 `[CANARY ALERT: original query looks like 'legal', not 'finance']`（已实测）。`TopManager.run` 需要相应地把 `user_query` 一起传给每个子 manager。

manager 收到告警后的处理（讲义练习 3 的问题）：

- 不要静默忽略，也不要直接用 canary 的答案替换分支结果（canary 也可能错）；
- 首选：在协调预算内**重新分解**——对比 canary 判断与当前分解，补上缺失分支（本例追加 legal），撤销或降权不相关的分支；
- 预算用尽仍有冲突：在最终汇总中显式标注"分解可能未覆盖问题的 X 方面"，必要时升级给人工；
- 记录告警次数作为指标，持续偏高说明顶层分解 prompt 需要修改。

### Q11 — 参考答案

1. **没有被用到**。四个 worker 在 `split` 里都有预设子问题，`self.split.get(w.name, task)` 永远返回预设值，`task` 只是默认值。实测顶层任务改为 "Review GDPR compliance" 后，lawyer 收到的仍是 "legal review of the feature"。
2. 中间层和叶子**完全看不到**上游意图，所以既不可能发现"我被分到的活和用户问题不相关"，也不可能纠正上游的错误标签——它们只能"obediently"执行。错误只能等到顶层汇总时才可能被发现，而顶层恰恰是犯错的那一层。
3. 改造思路：

```python
@dataclass
class Delegation:
    level: str            # "top" / "sub" / "leaf"
    actor: str            # 谁做的委托
    received: str         # 收到的任务
    sent: str             # 改写后下发的任务

@dataclass
class LeafOutput:
    worker: str
    question: str
    answer: str
    chain: list[Delegation]   # 从顶层到本叶子的完整委托链
    user_query: str           # 原始用户问题，一路原样下传

class SubManager:
    def run(self, task, user_query, chain):
        leaves = []
        for w in self.workers:
            sub_q = self.split.get(w.name, task)
            hop = Delegation("sub", self.name, received=task, sent=sub_q)
            leaves.append(w.run(sub_q, user_query, chain + [hop]))
        ...
```

  `TopManager.run` 在入口创建第一条 `Delegation("top", self.name, received=user_query, sent=f"{task} -- branch: {label}")`。这样每个叶子的输出都能回答三个问题：用户原本问了什么、中途被改写成了什么、谁改写的——这就是讲义的 provenance chain，也为漂移告警提供了数据。

### Q12 — 参考答案

```python
def reconcile(branch_a, branch_b, max_rounds=2):
    history = []
    for r in range(max_rounds + 1):          # 第 0 轮是初次回答，之后最多协调 max_rounds 轮
        a, b = branch_a(r), branch_b(r)
        history.append((r, a, b))
        if a == b:
            return {"status": "agreed", "answer": a, "rounds": r, "history": history}
    return {"status": "committed-without-consensus",
            "answer": f"A says {a}; B says {b}",
            "rounds": max_rounds, "history": history}
```

实测：两个分支始终分别回答 "ship" 和 "hold" 时，经过第 0、1、2 轮后返回 `committed-without-consensus`，答案为 `A says ship; B says hold`，历史中保留 3 轮记录。

为什么"上限本身成了超参数"：

- 上限太小，本可以通过再一轮澄清达成一致的分歧被过早提交；上限太大，系统在无法收敛的分歧上反复重跑 worker，成本线性增长，而且每轮结果"略有不同"（LLM 的随机性）会让循环看起来像是在进步；
- 合适的值取决于任务、模型和成本预算，只能通过评测调出来——它不再是一个"正确/错误"的设计问题，而是需要调参的数值；
- 讲义给的经验值是 2 轮；更重要的是超限时的**提交策略**：带着分歧提交并显式说明，而不是随机选一个或无限循环。

### Q13 — 参考回答要点

- **定义**：多层 supervisor 嵌套，内部节点规划、分派、汇总，叶子执行。
- **选择**：
  - **Sequential pipeline**：任务是一条线性流程，每步依赖上一步。
  - **Flat supervisor**：任务可拆成若干独立的子问题，一个 lead 足以管理。
  - **Hierarchical**：任务天然对应"部门的部门"——每个子团队内部还需要再分解和局部汇总；顶层只想看几个子摘要。
- **讲义观点**："Sequential often beats it."；Anthropic Research 系统刻意选择了扁平 supervisor 而非层级（讲义 Further Reading）。
- 加分点：说出层级的收益（局部汇总，顶层上下文更短）和代价（每层都可能引入分解漂移和语义漂移，错误离发生地更远才显现）。

### Q14 — 参考回答要点

- **人类 manager**：对下属的能力、职责有稳定的长期记忆和先验，分工方式相对固定，出错时能凭经验发现"这件事不该给他"。
- **LLM manager**：每一轮都只能从当前上下文重新推理"谁负责什么"，上下文中措辞的细微变化、信息的增减都会改变分解结果（讲义："Tiny drift in that context, and the whole tree misallocates work"）。
- **为什么越深越糟**：
  - 每一层都是一次"读入—压缩—改写—下发"，信息论意义上每次压缩都丢信息、每次改写都可能变义；误差在层与层之间累积（类似传话游戏）。
  - 每多一层，叶子离用户原始问题就远一层，叶子和中间层越来越难判断自己的工作是否切题。
  - 可观测性下降：错误显现的位置（顶层汇总）与发生的位置之间隔着更多层，排查成本上升。讲义："Three levels already hides most errors from observability."
- **缓解**：原始问题原样下传（canary）、每层保留 provenance、对分解做 diff 告警、限制深度。

### Q15 — 参考回答要点

- **复现与定位**：抽样问题，沿 provenance 链从顶层汇总追到叶子，逐层比对"收到的任务 vs 发出的任务 vs 用户原问题"，找出意图在哪一层丢失。若当前系统没有保存叶子输出和委托链，第一步就是补上这些记录。
- **常见根因**：
  - 顶层分解遗漏或错配（任务分配错误）；
  - 子 manager 改写任务时丢失约束（本节代码 `split` 覆盖 `task` 就是这种）；
  - 汇总时语义漂移（输出误读）；
  - 汇总只看"格式完整"，没有对照问题检查覆盖度。
- **改造**：
  - 先问"能否变浅"：把三层压成两层，或改为 flat supervisor / sequential；
  - 把用户问题解析成验收清单，汇总前做覆盖检查，缺失即告警或补派；
  - 每个子 manager 增加 canary；
  - 汇总必须引用叶子输出，禁止无来源的结论；
  - 设协调预算，超限带分歧提交；
  - 建立回归评测集：以"是否回答了问题"而非"报告是否专业"为指标。
- 常见误区：只调顶层 prompt 让报告"更全面"，结果是加入更多无关分支，掩盖问题。

### Q16 — 参考回答要点

- **任务形状**：工程、法务、财务、安全四个方面相互独立，最后汇总——本质是 fan-out + 汇总。若每个方面内部只需一个 agent，**扁平 supervisor（深度 1）就够了**；只有当某个方面内部还要再拆（如工程拆前端、后端、基础设施），才给它加一层，形成深度 2 的层级，且只在需要的分支加。
- **分解**：顶层分解固定为四个分支（可以用静态规则而非 LLM，避免分配错误）；每个分支的子 manager 拿到原始需求文档 + 本分支的检查清单。
- **护栏**：
  - 深度 ≤ 2；
  - 每个分支有 canary；
  - 汇总必须逐条引用叶子结论和证据；
  - 覆盖检查：四个方面都必须有结论，缺失则不允许出最终摘要；
  - 协调预算 2 轮（例如工程说"可以上线"、安全说"必须修复漏洞"时），超限则在摘要中并列呈现并标为"需高管决策"；
  - 高风险结论（法务不合规、安全高危）不得在汇总中被弱化——用结构化字段（严重级别）而非自由文本传递。
- **一页摘要模板**：结论（上线/有条件上线/不上线）、各方面一句话结论 + 严重级别、未决分歧、证据链接。
- 加分点：说明为什么不让 LLM 自由决定分支——这一步是最主要的错误来源，而这里分支集合是已知的。

### Q17 — 参考回答要点

- **人类层级有效的前提**：长期稳定的角色认知、非正式沟通渠道（同事之间可以直接对齐）、对上级意图的长期理解、能主动质疑任务。LLM agent 默认缺少这些：每轮重新推理、只能通过上级传话、倾向于"服从地"完成被分配的任务。
- **讲义观点**：本节 `outputs/skill-hierarchy-fitness.md` 的拒绝规则写道：如果用户为了"真实感"（因为人类组织很深）而要求层级，要指出人类层级并不能映射到 LLM 层级，并推荐更扁平的结构。
- **为什么限制在 2**：讲义 "Three levels already hides most errors from observability"；每多一层就多一次压缩与改写（漂移累积），多一轮潜在的协调循环，多一份成本与延迟。2 层能覆盖大多数"部门 + 小组"的需求。
- **何时可以更深**：有明确的审计或组织要求，并配套 provenance、canary、漂移告警（讲义 skill：depth > 2 必须给出具体理由）。
- 加分点：指出"深度"的口径——本节代码的"3-level hierarchy"是 3 层节点、2 级委托，讨论时要先统一口径。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：层级就是嵌套的 supervisor，先掌握扁平版本。
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：用四原语理解 manager（orchestrator）与委托（handoff）。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../../14-agent-engineering/15-crewai-role-based-crews/docs/zh.md)：CrewAI 的 Sequential 与 Hierarchical 流程。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 子图与嵌套的基础。

### 本节被哪些后续内容用到
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../08-role-specialization/docs/zh.md)：用验证者角色抓住层级中的错误。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：MAST 分类中的协调失效与级联错误。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：如何评测多 agent 系统是否真正回答了问题。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../../14-agent-engineering/28-orchestration-patterns/docs/zh.md)：几种编排模式的横向比较。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：另一种"金丝雀"思想在自主系统中的用法。

### 延伸关键词
`hierarchical multi-agent` · `CrewAI Process.hierarchical` · `manager_llm` · `nested create_supervisor` · `decomposition drift` · `output misinterpretation` · `reconciliation loop` · `reconciliation budget` · `canary question` · `provenance chain` · `depth-2 ceiling` · `MAST taxonomy`
