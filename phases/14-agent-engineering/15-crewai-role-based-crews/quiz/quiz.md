# 测验 · 基于角色的 Agent 团队：角色、任务与流程（Role-Based Agent Teams — Roles, Tasks, Processes）

> **阶段 14 · Agent 工程 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：中文讲义为机器翻译，Crew 被译成"船员"、Flow 被译成"流动"、prompt-bloat 被译成"prompt- 烟雾"，请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个原语 | Agent（role + goal + backstory + tools + 可选 llm）、Task（description + expected_output + agent + 可选 context / output_pydantic）、Crew（agents + tasks + process + 可选 memory / manager_llm）、Process（执行策略） |
| 2 | 心智模型 | Agent 之间不直接互相可见；Task 引用 Agent；Crew 编排 Task；Process 决定由谁选下一个 Task |
| 3 | 三种 Process | Sequential（按声明顺序，前一任务输出作为下一任务 context，最便宜最可预测）；Hierarchical（额外的 manager LLM 每轮选下一个专家，可拒绝或改派）；Consensus（**计划中、尚未实现**） |
| 4 | Crew vs Flow | Crew：LLM 驱动、运行时决定形状，适合研究 / 头脑风暴 / 初稿，难重放难测试；Flow：代码拥有的事件驱动图（`@start`、`@listen`），可观测、可测试、确定 |
| 5 | 生产建议 | 讲义引用文档原话："for any production-ready application, start with a Flow"；在 Flow 的步骤里调用 `Crew.kickoff()` 组合两者 |
| 6 | 三种接工具的方式 | `@tool` 装饰器（签名即 schema、docstring 即描述）、`BaseTool` 子类（显式 args schema、异步、重试、可持有状态）、内置工具包 |
| 7 | 结构化输出 | Task 上设 `output_pydantic=Model`，CrewAI 校验 LLM 输出并强制转换或重试；配合紧凑的 `expected_output` |
| 8 | 四种记忆 | Short-term（单次运行内的会话缓冲）、Long-term（跨运行，向量库，按相似度检索）、Entity（按实体键存事实）、Contextual（需要时即时组装检索） |
| 9 | 四个失败模式 | backstory 导致 prompt 膨胀（建议 < 200 词）、manager LLM 税、脆弱的 handoff（用 `output_pydantic` 修）、把 Crew 直接上生产（用 Flow 包住） |
| 10 | 本节代码的简化 | 所有 agent 都是固定字符串函数；manager 是规则函数；`expected_output` 从未被使用；记忆的"向量"是哈希随机向量，没有语义；没有 contextual 记忆 |

### 核心技能（能动手做到）

- [ ] 用 `Agent`、`Task`、`SequentialCrew` 搭出 researcher → writer → editor 三人团队，并说清 `prior` 与 `context` 如何传递
- [ ] 数清 Sequential 与 Hierarchical 两种 process 在同一任务上的 LLM 调用次数，解释 manager 税
- [ ] 用 `Flow` 的 `@start` / `@listen(topic)` 把同一流程改写成确定性的事件链，并指出该实现的两个隐患（同一 topic 只能有一个监听者、可能死循环）
- [ ] 识别本节 `Memory._embed` 的哈希向量没有语义，解释 `recall_long_term` 结果为何出现两条完全相同的记录
- [ ] 实现"writer 不足 3 段就不交给 editor"的 hierarchical 路由（讲义练习 3）
- [ ] 用标准库模拟 `output_pydantic`：解析 + 校验 + 带错误提示重试（讲义练习 5）

---

## 二、基础自测（选择题）

**Q1.** CrewAI 的四个原语是：

- A. Node、Edge、State、Checkpointer
- B. Actor、Message、Topic、Runtime
- C. Agent、Task、Crew、Process
- D. Router、Worker、Evaluator、Optimizer

**Q2.** 讲义引用的 CrewAI 文档对生产环境的建议是：

- A. 生产应用从 Flow 开始；需要自主性时在 Flow 步骤里调用 `Crew.kickoff()`
- B. 生产应用一律用 Hierarchical Crew，以便 manager 动态纠错
- C. 生产应用用 Consensus process 投票决策
- D. 生产应用不要用 CrewAI，改用 LangGraph

**Q3.** 关于 Consensus process，讲义的说法是：

- A. 它是默认的 process
- B. 它是成本最低的 process
- C. 它已经在 0.86 中稳定可用
- D. 它是计划中的投票式 process，目前公开 API 中尚未实现，不应依赖

**Q4.** 讲义所说的"脆弱的 handoff（brittle handoffs）"指上游任务输出了 4 个小节而下游按 3 个小节解析。推荐的修法是：

- A. 把下游 agent 的 backstory 写得更长，让它更聪明
- B. 给上游 Task 设置 `output_pydantic`，让下游读取类型化对象而不是自由文本
- C. 改用 Hierarchical process
- D. 打开 long-term memory

**Q5.** 在本节 `main()` 的 HierarchicalCrew 演示中，`manager.fn` 与各专家 `fn` 一共被调用了多少次？（把每次调用都当作一次"LLM 调用"）

- A. 3 次（只有 3 个专家）
- B. 7 次（manager 4 次，含最后返回 `"done"` 的那次，专家 3 次）
- C. 6 次（manager 3 次，专家 3 次）
- D. 10 次（每个专家调用前后各一次 manager）

**Q6.** 程序最后打印 `long_term entries: 9`。这 9 条的来源是：

- A. Sequential 3 + Hierarchical 3 + Flow 3
- B. Hierarchical 3 + Flow 3 + 第二次 Sequential 3
- C. 三次 Sequential 各 3 条
- D. 第一次 Sequential 3 + Flow 3 + 第二次 Sequential 3；Hierarchical 只写 short-term

**Q7.** `recall_long_term("brief")` 返回的两条记录**完全相同**（都是 editor、score 都是 +0.255）。原因是：

- A. Sequential 与 Flow 中 editor 产出了一模一样的字符串，被写入了两次；`_embed` 对相同文本给出相同向量，所以分数也相同——而且这个分数本身与语义无关
- B. `recall_long_term` 有 bug，把同一条记录返回了两次
- C. "brief" 与 editor 输出语义最相近，所以排第一
- D. long-term 记忆按角色去重失败

**Q8.** 讲义"Pitfalls"对 Crew 中带副作用的工具（POST、DELETE、支付）给出的建议是：

- A. 给这些工具加上更详细的 docstring
- B. 只在 Hierarchical Crew 中使用
- C. 放进 Flow 的步骤里，绝不作为 Crew 的工具——Crew 可能比预期更多次地调用工具
- D. 改用 `BaseTool` 子类就安全了

---

## 三、动手 / 代码题

**Q9.**（读代码找问题 + 改造）阅读 `HierarchicalCrew.kickoff` 与 `_manager`：

```python
        for _ in range(self.max_steps):
            pick = self.manager.fn(done, [], None)
            if pick == "done":
                outputs.append("[manager] done")
                break
            specialist = self.specialists.get(pick)
            ...
            out = specialist.fn(current, specialist.tools, self.memory)
            current = out
            done.add(pick)

def _manager(prior, tools, memory):
    done = prior if isinstance(prior, set) else set()
    if "researcher" not in done:
        return "researcher"
    ...
```

1. manager 做决定时能看到专家的输出吗？这与讲义描述的"The manager picks the next task each round and can refuse or re-route"有何差距？
2. 若把 `max_steps` 设为 3，输出会少什么？调用方能发现吗？
3. 完成讲义练习 3：manager 在 writer 的输出不足 3 段时拒绝交给 editor、把任务打回 writer。写出实现，并说明 writer 重做时应该拿什么作为输入。

**Q10.**（读代码找问题）阅读 `Memory`：

```python
    def _embed(self, text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v
```

已知实测：`recall_long_term("final brief")` 把 editor 的输出（内容以 `"final brief"` 开头）排在**最后**（score −0.071）；`"brief"` 与 `"brief."` 两个向量的余弦相似度只有 0.319；16 维随机单位向量之间余弦相似度的标准差约 0.24。

1. 这个"embedding"有语义吗？`recall_long_term` 的排序意味着什么？
2. 类的 docstring 说"Four-store memory matching CrewAI's short, long, entity, contextual"。实际实现了几种？哪种完全没被 demo 用到？agent 函数读过记忆吗？
3. 完成讲义练习 2：实现实体记忆的读取，使 writer 能根据客户的套餐调整语气；同时让 long-term 写入去重。

**Q11.**（读代码找问题）阅读 `Flow`：

```python
    def listen(self, topic):
        def decorator(fn):
            self.listeners[topic] = fn
            return fn
        return decorator

    def kickoff(self, payload):
        ...
        topic, out = self.start_step(payload)
        self.trace.append(("start", topic, out))
        while topic in self.listeners:
            step = self.listeners[topic]
            result = step(out)
            if result is None:
                break
            topic, out = result
            self.trace.append((step.__name__, topic, out))
        return self.trace
```

1. 两个函数都 `@flow.listen("a")` 时会怎样？（实测：trace 只出现后注册的 `l2`）
2. 如果某个步骤返回的 topic 指向前面已经执行过的步骤，会发生什么？
3. demo 中注册了 `on_edited`，它出现在 trace 里吗？为什么？
4. 修改 `Flow`：支持一个 topic 多个监听者（按注册顺序执行，形成扇出）、加入 `max_steps` 防止死循环、并让返回 `None` 的步骤也出现在 trace 中。

**Q12.**（补全函数）讲义练习 5：给 editor 任务加上"结构化输出"——输出必须是含 `title`、`summary`、`sections`（列表）三个字段的 JSON。请不用 pydantic，写一个 `run_structured(agent_fn, prior, parse, max_retries=2)`：解析失败时把错误信息附在下一次的输入里重试，超过次数后抛出异常。让 editor 第一次返回被截断的 JSON，验证重试过程。

---

## 四、面试高频题

**Q13.**（基础必考）介绍 CrewAI 的四个原语和 Crew / Flow 两种形态。为什么文档说生产应用应该"start with a Flow"？

**Q14.**（原理深挖）Sequential 与 Hierarchical process 的成本和适用场景有何不同？讲义里关于 manager 税的两种说法——"six LLM calls instead of five"和"adds a manager LLM call before every specialist call"——是否一致？请用本节代码的实测数据说明。

**Q15.**（工程实践）CrewAI 项目上线后常见哪些问题？请结合讲义的失败模式与 pitfalls，各给出可落地的修复办法。

**Q16.**（场景设计）设计一个"每周行业简报"自动生产系统：调研 → 写作 → 编辑 → 发布到 CMS 并邮件通知订阅者。哪些部分用 Crew，哪些用 Flow？工具、结构化输出、记忆分别怎么放？

**Q17.**（追问型）同样是多 agent，什么时候选 CrewAI，什么时候选 LangGraph（第 13 节）或 AutoGen（第 14 节）？什么时候三者都不该用？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Four primitives: Agent, Task, Crew, Process." A 是第 13 节 LangGraph 的概念；B 是第 14 节 actor 模型；D 是第 12 节 workflow 模式中的角色。

### Q2 — 答案：A

讲义："The docs' 2026 production recommendation: start with a Flow. Fold Crews in as `Crew.kickoff()` calls from inside Flow steps when autonomy earns its cost." 并总结为"Compose, do not pick"。B 恰好是讲义警告的"Crew-as-prod"与 manager 税；C 的 Consensus 尚未实现；D 讲义没有这样说，它把 LangGraph 定位为"严格顺序的确定性 DAG"的选择。

### Q3 — 答案：D

讲义："Consensus. Planned, not currently implemented in the public API. The docs reserve the name for a future voting-based process. Do not rely on it today." 本节代码也只实现了 Sequential 和 Hierarchical。

### Q4 — 答案：B

讲义："Fix with `output_pydantic` on Task N so Task N+1 reads a typed object, not free text." A 反而会加重 prompt 膨胀；C 加一个 manager 解决不了格式不一致；D 与格式无关。

### Q5 — 答案：B

`_manager` 依次返回 `researcher`、`writer`、`editor`、`done`，共 4 次；专家各 1 次，共 3 次；合计 7 次（已用包装计数器实测：`{'m': 4, 's': 3}`）。Sequential 只需 3 次。C 漏了最后那次判断"done"的 manager 调用；D 是"每个专家前后各一次"的错误理解。

### Q6 — 答案：D

`SequentialCrew.kickoff` 每个任务都调用 `write_short_term` 和 `write_long_term`；`HierarchicalCrew.kickoff` **只**调用 `write_short_term`；Flow 的三个步骤各自显式写 long-term。所以 9 = 3（第一次 Sequential）+ 3（Flow）+ 3（第二次 Sequential）。实测：只跑第一次 Sequential 和 Hierarchical 后 long-term 为 3、short-term 为 6。A、B 都误以为 Hierarchical 写了 long-term。

### Q7 — 答案：A

Sequential 与 Flow 用同样的函数、同样的输入，editor 产出完全相同的字符串，于是 long-term 中有两条重复记录；`_embed` 用文本的 SHA-256 作随机种子，相同文本得到相同向量，分数自然相同。更关键的是，这个分数本身没有语义含义（见 Q10）：C 的"语义最相近"是错的。B、D 中的 bug 不存在，但"没有去重"本身确实是讲义 pitfall"Memory always-on"所说的问题：每次运行都写、向量库越来越大、检索越来越嘈杂。

### Q8 — 答案：C

讲义 Pitfalls："A Crew can call a tool more times than expected. POST, DELETE, payment belong in a Flow step, never a Crew tool." 原因是 Crew 的执行路径由 LLM 决定，调用次数和时机不可控；放在 Flow 步骤里，调用位置与次数由代码决定，可审计、可加幂等保护。A、D 都不能限制调用次数；B 反而让路由更不可控。

### Q9 — 参考答案

1. 看不到。manager 只收到 `done`（已经派过的角色集合），专家的输出既不传给 manager，也不影响路由——它是"按缺失角色依次派活"的固定规则，本质上与 Sequential 等价。讲义描述的 manager 会基于先前输出选择、拒绝或改派任务。另外，`HierarchicalCrew` 完全不使用 `Task` 对象（没有 description / expected_output），而真实 CrewAI 的 hierarchical process 仍然是在任务列表上由 manager 委派。
2. `max_steps=3` 时 3 轮都用来派专家，第 4 次 manager 调用不会发生，输出里**没有** `"[manager] done"`（已实测）。循环正常结束，没有任何警告，调用方无法区分"正常完成"和"步数用尽"。本例只是碰巧三个专家都跑完了；如果有打回重做，就会在中途被截断。应在循环耗尽时追加 `"[manager] max_steps reached"` 或抛出异常。
3. 参考实现（已实测：writer 第一次只写 2 段被打回，第二次写 3 段后交给 editor，最后 `done`）：

```python
@dataclass
class GatedHierarchicalCrew:
    manager: Agent
    specialists: dict
    max_steps: int = 8
    log: list = field(default_factory=list)

    def kickoff(self, topic):
        outputs = {}
        upstream = {"researcher": None, "writer": "researcher", "editor": "writer"}
        for _ in range(self.max_steps):
            pick = self.manager.fn(outputs, [], None)     # manager 能看到全部输出
            if pick == "done":
                self.log.append("[manager] done")
                return outputs
            src = upstream[pick]
            agent_input = topic if src is None else outputs[src]
            out = self.specialists[pick].fn(agent_input, self.specialists[pick].tools, None)
            self.log.append(f"[manager -> {pick}] {out[:50]!r}")
            outputs[pick] = out
        self.log.append("[manager] max_steps reached")
        return outputs


def paragraphs(text):
    return len([p for p in text.split("\n\n") if p.strip()])

def gated_manager(outputs, tools, memory):
    if "researcher" not in outputs:
        return "researcher"
    if "writer" not in outputs or paragraphs(outputs["writer"]) < 3:
        return "writer"                    # 不足 3 段：不交给 editor，打回 writer
    if "editor" not in outputs:
        return "editor"
    return "done"
```

  writer 重做时的输入应该是 **researcher 的输出**（必要时再附上"上次只有 2 段，请写满 3 段"的反馈），而不是 writer 自己上一次的草稿——原代码的 `current = out` 会让重做的 writer 读到自己的旧稿，资料来源就丢了。用 `upstream` 映射明确每个角色读谁的输出，就是把 handoff 契约写进代码。`max_steps` 要留出重试余量（这里设为 8）。

### Q10 — 参考答案

1. 没有语义。哈希函数的特点是输入有一点点变化输出就完全不同，所以 `"brief"` 与 `"brief."` 的向量几乎无关（余弦 0.319）；不同文本的向量相当于随机向量，16 维时余弦相似度大致在 0 附近、标准差约 0.24 地随机波动。`recall_long_term` 的排序因此是**随机的**——editor 的输出明明以 "final brief" 开头，查询 "final brief" 时却排在最后。唯一有意义的情况是"查询与某条记录完全相同"（余弦 = 1.0，实测确实如此）。真实系统要用 embedding 模型（讲义：默认 OpenAI，可换成本地模型）。
2. 实现了 3 种：short-term、long-term、entity。contextual 完全没有实现；entity 有 `write_entity` 但没有读取方法，demo 也从未调用。所有 agent 函数（`_researcher`、`_writer`、`_editor`、`_manager`）都接收 `memory` 参数，但**没有一个读取它**——所以讲义说的"long-term memory surviving across two kickoffs"在代码里只体现为条目数从 6 变成 9，第二次运行的输出与第一次完全相同，记忆没有产生任何作用。
3. 参考实现（已实测：重复写 3 次同一内容后 long-term 只有 1 条；`acme` 是 enterprise 客户时 writer 用正式语气，`globex` 是 free 客户时用友好语气）：

```python
class BetterMemory(Memory):
    def write_long_term(self, role, value):
        if any(v == value for _, v, _ in self.long_term):
            return                                   # 去重
        super().write_long_term(role, value)

    def recall_entity(self, entity_id):
        return dict(self.entity.get(entity_id, {}))  # 按实体键精确查找，不靠相似度


def writer_with_entity(prior, tools, memory, customer="acme"):
    facts = memory.recall_entity(customer) if memory else {}
    tone = "formal, SLA-focused" if facts.get("plan") == "enterprise" else "friendly"
    return f"draft for {customer} ({tone}): {prior[:30]}"
```

  要点：entity 记忆是"按键查找"而非"按相似度查找"（讲义："Keyed by entity, not by similarity"）；返回副本避免调用方改坏存储；写入应只发生在"事实确实是持久的"任务上（讲义 Pitfalls："Scope writes to tasks where the fact is persistent"）。

### Q11 — 参考答案

1. `self.listeners[topic] = fn` 是字典赋值，后注册的覆盖先注册的，`l1` 被**静默丢弃**，实测 trace 为 `[('start', 'a', 'p'), ('l2', 'b', 'p2')]`。一个事件只能有一个监听者，无法扇出。
2. 无限循环。`while topic in self.listeners` 没有步数上限，A → B → A 会一直运行下去。skill 文件要求 Flow 的 `@listen` 步骤"forming a DAG"，但代码没有检查。
3. 不出现。`on_edited` 返回 `None`，循环在 `append` 之前就 `break` 了，所以 trace 只有 `start`、`on_researched`、`on_drafted` 三行。对审计来说，"执行了但没有输出"的步骤也应该被记录。
4. 参考实现：

```python
class Flow2:
    def __init__(self, max_steps=50):
        self.start_step = None
        self.listeners = {}                     # topic -> [fn, ...]
        self.trace = []
        self.max_steps = max_steps

    def start(self, fn):
        self.start_step = fn
        return fn

    def listen(self, topic):
        def decorator(fn):
            self.listeners.setdefault(topic, []).append(fn)
            return fn
        return decorator

    def kickoff(self, payload):
        self.trace = []
        topic, out = self.start_step(payload)
        self.trace.append(("start", topic, out))
        pending = [(topic, out)]                # 待分发的事件（FIFO）
        steps = 0
        while pending:
            topic, out = pending.pop(0)
            for step in self.listeners.get(topic, []):
                steps += 1
                if steps > self.max_steps:
                    raise RuntimeError("flow exceeded max_steps (cycle?)")
                result = step(out)
                if result is None:
                    self.trace.append((step.__name__, None, None))   # 终止步骤也记录
                    continue
                self.trace.append((step.__name__, *result))
                pending.append(result)
        return self.trace
```

  已实测：`a` 有 `l1`、`l2` 两个监听者、`b` 的监听者返回 `None` 时，trace 为 `[('start','a','p'), ('l1','b','p1'), ('l2','c','p2'), ('end', None, None)]`；`a → b → a` 的环在 `max_steps=10` 时抛出 `flow exceeded max_steps (cycle?)`。

  补充：也可以在注册时做静态检查（构建 topic 依赖图并检测环），这比运行时计数更早发现问题。

### Q12 — 参考答案

```python
import json
from dataclasses import dataclass

@dataclass
class Brief:
    title: str
    summary: str
    sections: list

def parse_brief(raw):
    data = json.loads(raw)
    missing = {"title", "summary", "sections"} - data.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if not isinstance(data["sections"], list):
        raise ValueError("sections must be a list")
    return Brief(**{k: data[k] for k in ("title", "summary", "sections")})

def run_structured(agent_fn, prior, parse, max_retries=2):
    errors = []
    for attempt in range(max_retries + 1):
        hint = f"\nprevious error: {errors[-1]}" if errors else ""
        raw = agent_fn(prior + hint)                     # 把上次的错误告诉模型
        try:
            return parse(raw), errors
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            errors.append(f"attempt {attempt + 1}: {exc}")
    raise RuntimeError(f"structured output failed: {errors}")
```

实测：editor 第一次返回截断的 `'{"title": "Agent engineering 2026", "summary": "x"'`，解析报 `Expecting ',' delimiter: line 1 column 51 (char 50)`；第二次返回完整 JSON，得到 `Brief(title='Agent engineering 2026', summary='loops, tools, memory', sections=['loop', 'tools', 'memory'])`，错误列表里留下第一次的记录。

要点：
- 解析与业务校验分开（JSON 语法错 vs 缺字段 / 类型错），两类错误都触发重试；
- 重试时附上错误信息，模型才有机会改对；
- 设置重试上限，失败要显式抛出，交给 Flow 层决定降级或转人工；
- 保留错误记录用于监控（结构化输出失败率是重要指标）。
- 讲义说 CrewAI 的 `output_pydantic` 会"either coerces or retries"，这里的实现就是其中"retries"一支的最小版本。

### Q13 — 参考回答要点

- **四个原语**：Agent（role、goal、backstory、tools、可选 llm；backstory 决定语气、判断、何时停止，是"load-bearing"的）；Task（description、expected_output 作为契约、agent、context 引用上游任务、output_pydantic 强制结构）；Crew（agents、tasks、process、memory、verbose、manager_llm 的容器）；Process（Sequential / Hierarchical / Consensus（计划中））。
- **两种形态**：Crew 由 LLM 驱动、运行时决定路径，适合探索性工作；Flow 是代码拥有的事件驱动图，`@start` 标记入口、`@listen` 标记响应某事件的步骤，每一步是普通 Python。
- **为什么从 Flow 开始**：生产需要确定性重放、成本可预估、出问题时能定位到哪一步——讲义"The Problem"列举了客户报 bug 需要重放、财务问每次运行成本、值班需要知道哪个 agent 卡住；自由形态的 Crew 都回答不好。Flow 提供审计边界，需要自主性的部分再在 Flow 步骤里调用 Crew。
- 加分点：讲义强调"Compose, do not pick"——不是二选一，而是 Flow 包 Crew。

### Q14 — 参考回答要点

- **Sequential**：按声明顺序执行，前一任务输出作为下一任务的 context；调用次数 = 任务数，最便宜、最可预测；适合顺序固定的协作。
- **Hierarchical**：额外的 manager LLM 每轮决定下一个任务，可以拒绝或改派；适合讲义所说"四个及以上专家、且顺序确实取决于前面的输出"的场景。skill 文件把"只有 2 个专家的 Hierarchical"列为 hard reject。
- **manager 税**：manager 的每次调用都带着完整任务列表和先前输出，prompt 越来越长；讲义说"Token cost can triple on a five-step run"。
- **两种说法不一致**：如果 manager 在**每个**专家调用之前都调用一次，5 个任务就是 5 + 5 = 10 次，加上判断结束的那一次是 11 次，而不是"six LLM calls instead of five"。本节代码实测：3 个任务时 manager 4 次 + 专家 3 次 = 7 次，Sequential 是 3 次，符合"每个专家前一次 + 收尾一次"，即 2n + 1。"六次而非五次"只有在 manager 一次性规划全部任务时才成立。面试中能指出这种不一致并给出自己的计数，是很好的加分点。
- 结论：除非路由确实依赖输出，否则用 Sequential（讲义："Switch to Sequential unless routing depends on output"）。

### Q15 — 参考回答要点

| 问题 | 表现 | 修复 |
|------|------|------|
| backstory 膨胀 | 5 个 agent 各 2000 词 backstory，第一次工具调用前就耗尽上下文 | backstory < 200 词；共享的风格说明只写一次（skill 文件把超过 200 词列为拒绝条件） |
| manager LLM 税 | Hierarchical 每轮多一次带完整上下文的调用 | 路由不依赖输出就用 Sequential |
| 脆弱的 handoff | 上游自由文本格式漂移，下游即兴发挥 | `output_pydantic` + 紧凑的 `expected_output` |
| Crew 直接上生产 | 输出方差大、无法重放、值班无法对比好坏运行 | 用 Flow 包住，Crew 只做其中需要探索的一步 |
| 跳过 `expected_output` | 下游拿到什么算什么，审计失败 | 每个任务写明契约（本节代码的 `expected_output` 甚至从未被传给 agent） |
| 记忆一直开着 | 每次都写 long-term，向量库膨胀、检索变吵 | 只在事实持久的任务上写；去重（本节 demo 中同一内容被写入 3 次） |
| manager prompt 漂移 | 路由变怪 | 用 verbose 模式导出 manager prompt 阅读 |
| 工具副作用 | Crew 多次调用 POST / 支付 | 副作用放进 Flow 步骤并加幂等键 |

- 加分点：backstory 会显著影响输出，讲义建议每个 agent 测 3 个变体后冻结一个；接入 AgentOps / Langfuse 做追踪（讲义练习 7）。

### Q16 — 参考回答要点

- **外层 Flow**（确定性、可审计）：`@start` 接收本周主题 → `@listen("researched")` 写作 → `@listen("drafted")` 编辑 → `@listen("edited")` 人工审核或自动质检 → `@listen("approved")` 发布 → `@listen("published")` 通知。
- **Crew 只放在调研步骤**：researcher + analyst 的 Sequential Crew（必要时 Hierarchical），在 Flow 步骤里 `Crew.kickoff()`；调研的路径本身是答案的一部分，适合 Crew。
- **工具**：搜索、抓取用 `@tool` 或 `BaseTool`（有客户端、缓存、重试时用 `BaseTool`）；**发布到 CMS、发送邮件**这类有副作用的操作放在 Flow 步骤里，带幂等键（按"主题 + 周次"），绝不作为 Crew 工具。
- **结构化输出**：调研结果 `output_pydantic=Sources`（来源 URL、摘要、日期）；编辑结果 `Brief(title, summary, sections)`，发布步骤只接受通过校验的对象。
- **记忆**：entity 记忆存订阅者偏好与往期覆盖过的公司；long-term 存往期简报摘要，用于避免重复选题，写入前去重；short-term 只在单次运行内使用。
- **观测与成本**：每一步记录耗时、token、重试次数；Flow 的 trace 用于回放与对比。
- 常见误区：整个流程做成一个 Hierarchical Crew，让 manager 决定何时发布——发布时机与次数变得不可控。

### Q17 — 参考回答要点

- **CrewAI**：3–6 个有明确角色的 agent 协作（起草、评审、规划、头脑风暴），团队更习惯读 `role + goal + backstory` 而不是图定义；内置四种记忆，比轻量框架省事（讲义："pure LangGraph requires you to wire each of these yourself"）。
- **LangGraph**：严格顺序的确定性 DAG、显式状态机、durable resume、human-in-the-loop；讲义："Deterministic DAGs with strict ordering. Use LangGraph."
- **AutoGen v0.4**：actor 模型并发与故障隔离、分布式。
- **都不该用**：单 agent 循环（用第 01 节的 agent loop + 工具注册表更短）；亚秒级延迟预算（Hierarchical 增加往返，Sequential 也要串行拼接包含 backstory 的 prompt）；两三步的固定流程（第 12 节的 prompt chain 足矣）。
- 加分点：讲义提到厂商基准声称 CrewAI 在某些 QA 负载上比 LangGraph 快很多，但方法（数据集、硬件、指标）未公开，只能作为方向性参考——面试中对厂商数字保持审慎是加分项。另外讲义说"Lesson 17 (Agent Framework Tradeoffs) lays this out in a matrix"，在本课程中对应的是阶段 11 · 17（阶段 14 的第 17 节是 Claude Agent SDK）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：本节的先修课；Sequential crew 就是 prompt chaining，Hierarchical 接近 orchestrator-workers。
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../14-autogen-actor-model/docs/zh.md)：本节的先修课；另一种多 agent 抽象。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：`@tool` 背后的 function calling 机制。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../09-hybrid-memory-mem0/docs/zh.md)：long-term / entity 记忆的实现方式。
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：讲义提到的框架对比矩阵。

### 本节被哪些后续内容用到
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：Flow 需要 durable resume 时的选择。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：另一种多 agent 产品化形态。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：Claude 优先产品的 subagent 方案。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：为 Crew / Flow 接入追踪（讲义练习 7）。
- [阶段 16 · 08 角色专业化：规划者、Critic、执行者与验证者](../../../16-multi-agent-and-swarms/08-role-specialization/docs/zh.md)：角色分工的系统性讨论。
- [阶段 16 · 05 监督者与编排者—工作者模式](../../../16-multi-agent-and-swarms/05-supervisor-orchestrator-pattern/docs/zh.md)：Hierarchical process 背后的监督者模式。
- [阶段 19 · 10 综合项目 10：多 Agent 软件工程团队](../../../19-capstone-projects/10-multi-agent-software-team/docs/zh.md)：综合项目中的角色化团队。

### 延伸关键词
`CrewAI` · `Agent / Task / Crew / Process` · `Sequential / Hierarchical process` · `manager_llm` · `Flow @start / @listen` · `Crew.kickoff()` · `@tool / BaseTool` · `output_pydantic` · `expected_output` · `short-term / long-term / entity / contextual memory` · `backstory bloat` · `brittle handoffs`
