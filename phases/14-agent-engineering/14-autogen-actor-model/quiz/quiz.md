# 测验 · 用于 Agents 的 Actor 模型：异步消息与类型化运行时（The Actor Model for Agents — Async Messages and Typed Runtimes）

> **阶段 14 · Agent 工程 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：中文讲义为机器翻译，部分术语译错（如把 concurrency 译成"同值货币 / 同价货币"、把 fault isolation 译成"断层隔离"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Actor 的三要素 | 私有状态（外部不能直接碰）+ 收件箱（消息队列）+ 处理函数 `receive(message) -> effects`；actor 之间**不共享内存**，只能发消息 |
| 2 | Handler 能产生的效果 | 回复、发消息给其他 actor、创建新 actor、更新自身状态、停止自己 |
| 3 | AutoGen v0.4 三层 API | Core（底层 actor 框架：`AgentRuntime`、`Agent`、`Message`、`Topic`）、AgentChat（任务驱动的高层 API，替代 v0.2 的 `ConversableAgent`）、Extensions（OpenAI / Anthropic / Azure、工具、记忆等集成） |
| 4 | 投递与处理解耦 | v0.2 的 `agent_a.chat(agent_b)` 同步阻塞；v0.4 的 `send(agent_b, msg)` 只把消息放进收件箱就返回，由 runtime 稍后投递 |
| 5 | 解耦的三个后果 | 故障隔离（B 崩溃不会带崩 A）、天然并发（多条消息同时在途）、易于分布式（收件箱 + 传输层在进程内外是同一抽象） |
| 6 | 团队拓扑 | `RoundRobinGroupChat`（固定轮转）、`SelectorGroupChat`（选择器按上下文挑下一个发言者）、Magentic-One（网页浏览 + 代码执行 + 文件处理的参考团队） |
| 7 | 可观测性 | 内置 OpenTelemetry：每条消息一个 span，工具调用带 `gen_ai.*` 属性（第 23 节） |
| 8 | 项目状态 | 讲义：AutoGen 已进入维护模式，v0.7.x 适合研究与原型；Microsoft Agent Framework 是生产继任者（2025 年 10 月 1 日公开预览） |
| 9 | Dead-letter queue | handler 抛出的异常不向外传播，失败消息进入 DLQ 供人检查，其余 actor 继续运行 |
| 10 | 本节代码的简化 | 一个**全局共享 FIFO 队列**而非每个 actor 一个收件箱；单线程顺序处理，没有真正并发；topic 只是字符串字段，没有发布订阅 |

### 核心技能（能动手做到）

- [ ] 读懂 `Runtime.send` / `run_until_idle`，能按 FIFO 顺序推演任意一段消息 trace
- [ ] 解释 trace 中 `[send]` 行为什么出现在对应的 `[recv]` 行之前
- [ ] 找出 `ChecklistAgent` 共识逻辑的三个问题（过早置 True、写死 3、失败消息导致永远等不齐），并修复
- [ ] 用 `asyncio.Queue` 为每个 actor 实现独立收件箱，测出真正的并发收益
- [ ] 设计 DLQ 策略：何时重试、何时通知发送方、如何处理"发出消息后才抛异常"的部分副作用
- [ ] 用一个 selector actor 实现 `SelectorGroupChat` 风格的发言者选择，并设置终止条件

---

## 二、基础自测（选择题）

**Q1.** 按讲义，actor 模型中两个 actor 之间**唯一**合法的交互方式是：

- A. 读写一个共享的全局字典
- B. 直接调用对方的方法并等待返回值
- C. 共享同一个 LLM 会话上下文
- D. 通过收件箱异步交换消息

**Q2.** AutoGen v0.4 把 API 分成三层。下列对应关系正确的是：

- A. Core：底层 actor 框架；AgentChat：任务驱动的高层 API；Extensions：模型与工具集成
- B. Core：模型集成；AgentChat：actor 运行时；Extensions：群聊拓扑
- C. Core：提示词模板；AgentChat：向量数据库；Extensions：微调
- D. Core：GPU 调度；AgentChat：前端 UI；Extensions：计费

**Q3.** 为什么"投递与处理解耦"能带来故障隔离？

- A. 因为每个 actor 都运行在独立的 GPU 上
- B. 因为 actor 的代码不会抛异常
- C. 发送方的 `send()` 只是把消息放进收件箱就返回，不等待接收方；接收方 handler 的异常由 runtime 捕获处理（记录、重试、进 DLQ），不会沿调用栈传回发送方
- D. 因为消息都会被持久化到数据库

**Q4.** 关于 AgentChat 的团队拓扑，说法正确的是：

- A. `RoundRobinGroupChat` 由一个 LLM 决定下一个发言者
- B. `SelectorGroupChat` 由一个 selector agent 根据对话上下文挑选下一个发言者
- C. Magentic-One 是 AutoGen 的底层消息传输协议
- D. 两种 GroupChat 都要求所有 agent 同时发言

**Q5.** 运行 `main.py`，trace 中 `[FAIL m002]` 出现在 `[recv m003]` 之前。原因是：

- A. runtime 会优先处理会失败的消息
- B. `crash_me` 消息的优先级更高
- C. 全局队列是 FIFO：m002 由 `main()` 在调用 `run_until_idle()` 之前就入队了，而 m003～m005 是处理 m001 时才产生的，排在 m002 之后
- D. 两条消息是并发处理的，顺序是随机的

**Q6.** `ReviewerAgent` 用 `if "eval(" in code` 检测危险调用。对代码片段 `"import ast; ast.literal_eval('1')"`，它的判定是：

- A. `ok=False, issues=['uses eval']`——子串匹配把安全的 `literal_eval(` 也当成了 `eval(`
- B. `ok=True`，因为 `literal_eval` 是安全函数
- C. 抛出异常进入 DLQ
- D. `ok=False, issues=['bare except']`

**Q7.** 若把 `main()` 中 `start` 消息的 body 换成只有两个片段 `["x=1", "eval(1)"]`，最终 `checklist.consensus` 是：

- A. `False`，因为第二个片段用了 eval
- B. `None`，因为还没收齐 3 个结果
- C. 抛出 `KeyError`
- D. `True`——第一个结果 ok 时就被置为 True，第二个结果失败时既不满足"全部 ok"也不满足"恰好 3 个"，于是 True 一直保留

**Q8.** 按讲义，AutoGen 在 2026 年初的状态是：

- A. 已被完全删除，不能再安装
- B. 进入维护模式，v0.7.x 适合研究与原型；Microsoft Agent Framework 是生产继任者
- C. 刚刚发布 v0.2，开始支持 actor 模型
- D. 被并入 LangGraph

---

## 三、动手 / 代码题

**Q9.**（读代码找 bug）阅读 `ChecklistAgent.receive`：

```python
        elif message.topic == "review_result":
            self.results.append(dict(message.body))
            if all(r["ok"] for r in self.results):
                self.consensus = True
            if len(self.results) == 3:
                self.consensus = all(r["ok"] for r in self.results)
```

已知实测结果：

| 片段 | `consensus` |
|------|------------|
| `["x=1", "eval(1)"]` | `True` |
| `["x=1", "y=2", "z=3", "eval(1)"]` | `True` |
| `["a=1", "boom", "b=2"]`，reviewer 处理 `"boom"` 时抛异常 | `True` |
| 原 demo 设 `max_messages=5` 中途停止，只收到 1 个结果 | `True` |

1. 逐一解释每一行为什么是 `True`。
2. 第 3 行说明了 actor 模型中"故障隔离"的什么代价？
3. 修复 `ChecklistAgent`，并让 runtime 在 handler 失败时通知发送方。

**Q10.**（改造代码）讲义说"Each agent is an actor with a private inbox"，Key Terms 也把 Inbox 定义为"Per-actor queue"，并强调"actors process their inbox concurrently"。但本节代码是：

```python
@dataclass
class Runtime:
    queue: deque[Message] = field(default_factory=deque)
    ...
    def run_until_idle(self) -> None:
        processed = 0
        while self.queue and processed < self.max_messages:
            msg = self.queue.popleft()
            ...
```

1. 这与"每个 actor 一个收件箱、并发处理"有什么差别？单线程全局队列会在什么情况下成为问题？
2. 用 `asyncio` 写一个每个 actor 一个 `asyncio.Queue` 的 runtime：`send` 只入队立即返回；每个 actor 一个处理协程；handler 异常进 DLQ；能判断"整个系统空闲"。
3. 两个 actor `a`、`b` 的 handler 都 `await asyncio.sleep(0.5)`，给 `a` 发 1 条、给 `b` 发 2 条消息，总耗时大约多少？顺序处理呢？

**Q11.**（读代码 + 设计）围绕讲义练习 1（dead-letter queue）回答：

1. 两个 actor 互相回复 `ping`，`max_messages=100`。`run_until_idle()` 返回后 `runtime.counter` 是多少、队列里还剩几条？这时调用方能知道系统"并没有空闲"吗？
2. 某个 handler 先 `runtime.send(...)` 再抛异常。实测 trace 为：
   ```text
   [send m002] h -> sink topic=x body=1
   [FAIL m001] h raised RuntimeError: after send
   [recv m002] sink handled topic=x
   ```
   这说明了什么问题？生产中如何处理？
3. 发往不存在的 actor 的消息会进 DLQ，但不计入 `processed`。这会有什么影响？
4. 给出一个完整的 DLQ 策略（哪些错误重试、重试几次、何时进 DLQ、谁来处理 DLQ）。

**Q12.**（补全函数）讲义练习 2：实现 `SelectorGroupChat`——一个 selector actor 根据对话状态挑选下一个处理消息的 actor。要求：selector 保存对话历史；用一个 `pick(history, participants)` 函数（真实系统中是一次 LLM 调用）选择下一位；遇到 `"APPROVE"` 或超过 `max_turns` 时终止；pick 返回未知名字时报错。用 coder / reviewer 两个 actor 演示"写补丁 → 要求修改 → 再写 → 通过"。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 actor 模型？把 agent 建模成 actor 有什么好处？和"agent A 直接调用 agent B 的函数"相比有什么本质区别？

**Q14.**（原理深挖）异步消息带来了故障隔离，但也带来了哪些新问题？（提示：发送方怎么知道请求失败了？消息顺序？重复投递？）

**Q15.**（工程实践）对比 LangGraph 的有状态图（第 13 节）和 AutoGen 的 actor 模型：各自适合什么场景？如果要做到"崩溃后可恢复"，actor runtime 还需要补什么？

**Q16.**（场景设计）设计一个多 agent 代码评审系统：一个 coordinator、若干专项 reviewer（安全、性能、风格），要求支持并发评审、单个 reviewer 故障不影响整体、全链路可追踪。请给出 actor 划分、消息类型、超时与 DLQ 策略、OTel 埋点。

**Q17.**（追问型）skill 文件说"如果只有两个 actor 固定来回，就拒绝 actor 框架，改用 prompt chain"。为什么？什么时候 actor 模型才"值回成本"？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Two actors cannot share memory. They can only send messages." A 违反"不共享内存"；B 是 v0.2 的同步调用方式，正是 v0.4 要摆脱的；C 也是一种共享状态。

### Q2 — 答案：A

讲义：Core 是"Low-level actor framework. `AgentRuntime`, `Agent`, `Message`, `Topic`"；AgentChat 是"Task-driven high-level API (replacement for v0.2's ConversableAgent)"，包括 `AssistantAgent`、`RoundRobinGroupChat`、`SelectorGroupChat` 等；Extensions 是"Integrations — OpenAI, Anthropic, Azure, tools, memory"。B 把三层的职责打乱了；C、D 是编造的。

### Q3 — 答案：C

讲义："Agent B crashing does not crash Agent A — the runtime catches the failure in B's handler and decides what to do (log, retry, dead-letter)." 关键是发送方不在接收方的调用栈上。本节代码里 `run_until_idle` 的 `try/except` 就是这个"runtime 捕获"。A、D 与故障隔离无关；B 显然不成立，demo 里 reviewer 就故意抛了异常。

### Q4 — 答案：B

讲义："SelectorGroupChat. A selector agent picks who goes next based on conversation context." A 描述的其实是 Selector，RoundRobin 是固定轮转；C 错，Magentic-One 是"Reference multi-agent team for web browsing, code execution, file handling. Built on AgentChat"；D 错，两种都是轮流发言。

### Q5 — 答案：C

`main()` 先 `send` 了 m001（start）和 m002（crash_me），然后才 `run_until_idle()`。处理 m001 时 checklist 发出 m003～m005，它们排在队尾，也就是 m002 之后。所以顺序是 m001 → m002（失败）→ m003～m005 → m006～m008。代码是单线程顺序处理，不存在 D 所说的并发与随机；A、B 中的优先级机制代码里并不存在。

### Q6 — 答案：A

`"ast.literal_eval('1')"` 包含子串 `"eval("`，实测得到 `{'ok': False, 'issues': ['uses eval']}`。反过来，`"eval (x)"`（中间有空格）不包含 `"eval("`，实测被判为 ok。这说明子串匹配既有误报也有漏报；真实的代码检查应基于 AST（例如用 `ast` 模块遍历 `Call` 节点并检查函数名是否为 `eval`）。B 是"应该的"结果，但代码做不到；C、D 不符合代码逻辑。

### Q7 — 答案：D

第一个结果 `ok=True` 进来时，`all(...)` 为真，`consensus = True`；第二个结果 `ok=False` 进来时，`all(...)` 为假（不改动），`len == 3` 也不成立（不改动），于是 True 被保留。实测 `consensus=True`。A 是正确答案应有的样子；B 是合理设计应有的"未完成"状态，但代码没有这个状态。详见 Q9。

### Q8 — 答案：B

讲义"Status: maintenance mode"：AutoGen v0.7.x 适合研究与原型（"stable for research and prototyping"）；微软已把主动开发转向 Microsoft Agent Framework，即生产继任者（讲义："public preview Oct 1 2025; 1.0 GA was targeted for end of Q1 2026"）。讲义同时强调"AutoGen patterns port forward cleanly — the actor model is the durable idea"。A 错，仍可使用；C 把版本说反了，v0.2 是旧的同步模型，v0.4 才引入 actor 模型；D 是编造的。

### Q9 — 参考答案

1. 逐行解释：
   - `["x=1", "eval(1)"]`：同 Q7。第一个 ok 结果就把 consensus 置为 True，之后既没有"全部 ok"也没有"恰好 3 个"，True 被保留。
   - `["x=1","y=2","z=3","eval(1)"]`：第 3 个结果时三个都 ok，`consensus = True`；第 4 个 `eval` 结果失败，但 `len == 4` 不再触发重算，True 被保留。根源是**把期望数量写死为 3**。
   - `["a=1","boom","b=2"]`：reviewer 处理 `"boom"` 抛异常，消息进 DLQ，checklist 只收到 2 个 ok 结果，第一个结果时就置为 True，永远等不到第 3 个。
   - `max_messages=5`：runtime 处理完 5 条消息就停下，队列里还剩 2 条；此时 checklist 只收到 1 个 ok 结果，consensus 已经是 True。
2. 故障隔离的代价：**失败被隔离了，但也被"藏起来"了**。reviewer 的异常没有传回 checklist，checklist 不知道有一个请求失败，只会无限期等待（或像这里一样基于不完整数据得出结论）。actor 系统必须显式设计"失败通知 / 超时"，否则就是静默的部分失败。
3. 修复（已实测：上述 4 种情况依次得到 `False`、`False`、`None`（有 1 个失败）、全部 ok 时 `True`）：

```python
class FixedChecklist(Actor):
    def __init__(self, name, partner):
        super().__init__(name)
        self.partner = partner
        self.expected, self.results, self.failed, self.consensus = 0, [], 0, None

    def receive(self, message, runtime):
        if message.topic == "start":
            self.expected = len(message.body)              # 不写死数量
            self.results.clear(); self.failed = 0; self.consensus = None
            for snippet in message.body:
                runtime.send(self.name, self.partner, "review", snippet)
        elif message.topic == "review_result":
            self.results.append(dict(message.body)); self._maybe_decide()
        elif message.topic == "delivery_failed":           # runtime 发来的失败通知
            self.failed += 1; self._maybe_decide()

    def _maybe_decide(self):
        if len(self.results) + self.failed < self.expected:
            return                                          # 没收齐之前不下结论
        self.consensus = None if self.failed else all(r["ok"] for r in self.results)


class NotifyingRuntime(Runtime):
    def run_until_idle(self):
        processed = 0
        while self.queue and processed < self.max_messages:
            msg = self.queue.popleft()
            actor = self.actors.get(msg.recipient)
            try:
                if actor is None:
                    raise LookupError(f"no actor {msg.recipient!r}")
                actor.receive(msg, self)
            except Exception as e:
                self.dead_letters.append((msg, f"{type(e).__name__}: {e}"))
                if msg.sender in self.actors and msg.topic != "delivery_failed":
                    self.send("__runtime__", msg.sender, "delivery_failed",
                              {"mid": msg.mid, "error": str(e)})
            processed += 1
```

  要点：结论只在"结果数 + 失败数 = 期望数"时给出；有失败时给出 `None`（"无法判定"）而不是 True；`delivery_failed` 自己失败时不再递归通知，避免消息风暴。生产中还应加超时（定时消息），防止接收方"没报错但一直不回复"。

### Q10 — 参考答案

1. 差别：
   - 代码里所有 actor 共用一个 `deque`，按全局 FIFO 一条一条处理；"收件箱"并不属于某个 actor。
   - 没有并发：一个慢 handler（例如等待 LLM 回复 10 秒）会阻塞**所有** actor 的消息。
   - 没有每个 actor 的背压、优先级、容量上限；也无法把某个 actor 单独迁到另一台机器。
   - 讲义说"Distribution is just different transport"，前提正是"每个 actor 有自己的收件箱"。
2. 参考实现（已实测运行）：

```python
import asyncio

class AsyncRuntime:
    def __init__(self):
        self.inboxes, self.handlers, self.dead_letters = {}, {}, []
        self.in_flight = 0
        self.idle = asyncio.Event(); self.idle.set()

    def register(self, name, handler):
        self.inboxes[name] = asyncio.Queue()
        self.handlers[name] = handler

    def send(self, sender, recipient, topic, body):
        inbox = self.inboxes.get(recipient)
        if inbox is None:
            self.dead_letters.append(((sender, recipient, topic), "no actor"))
            return
        self.in_flight += 1; self.idle.clear()
        inbox.put_nowait((sender, topic, body))       # 只入队，立即返回

    async def _loop(self, name):
        inbox, handler = self.inboxes[name], self.handlers[name]
        while True:
            sender, topic, body = await inbox.get()
            try:
                await handler(sender, topic, body, self)
            except Exception as e:                     # 故障隔离
                self.dead_letters.append(((sender, name, topic), repr(e)))
            finally:
                self.in_flight -= 1
                if self.in_flight == 0:
                    self.idle.set()

    async def run_until_idle(self):
        tasks = [asyncio.create_task(self._loop(n)) for n in self.inboxes]
        await self.idle.wait()                         # 所有在途消息处理完
        for t in tasks:
            t.cancel()
```

  "系统空闲"用在途消息计数判断：`send` 时 +1，处理完（无论成功失败）−1，归零时置位 `idle` 事件。只看"所有队列都为空"是不够的，因为消息可能已被取出但还在处理中。
3. 实测约 **1.0 秒**：`a` 的 1 条与 `b` 的第 1 条并发（0.5 秒），`b` 的第 2 条在 `b` 自己的收件箱里排队（再 0.5 秒）。顺序处理需要 1.5 秒。同一个 actor 内部仍然是**串行**的——这正是 actor 模型的特点：actor 之间并发，actor 内部一次只处理一条消息，因此私有状态不需要加锁。

### Q11 — 参考答案

1. 实测 `counter=101`、队列剩 1 条。`run_until_idle()` 处理满 100 条就返回，但两个 actor 还在互相发消息。函数名叫"until idle"，返回时却并不空闲，调用方没有任何信号（不报错、不返回状态）。应返回是否真正空闲，或在达到上限时记录告警 / 抛出异常；这个上限本身是防止消息风暴的重要保护。
2. handler 的效果不是原子的：消息已经发出（下游已处理），handler 却失败了，发送的消息不会被"撤回"。如果之后重试这条失败消息，下游会收到第二次。生产中的做法：
   - handler 先做完所有可能失败的计算，最后再发送消息（"先算后发"）；
   - 或者把要发送的消息先收集在本地，handler 成功后由 runtime 统一提交（类似事务性 outbox）；
   - 接收方按消息 ID 去重，保证重复投递是幂等的。
3. 未知 recipient 的消息走 `continue`，跳过了 `processed += 1`，因此不受 `max_messages` 限制；如果某个 bug 不断向不存在的 actor 发消息，这些消息不会触发上限保护（每条都会进 DLQ，DLQ 无限增长）。另外 trace 里这类消息的格式（`[DLQ ...]`）也和 handler 失败（`[FAIL ...]`）不同，统计时要注意。
4. DLQ 策略示例：
   - **分类**：可重试错误（超时、限流、网络）与不可重试错误（参数错误、业务校验失败、代码 bug）；
   - **重试**：可重试错误按指数退避重试 3 次，带上原消息 ID 便于下游去重；
   - **进 DLQ**：不可重试错误立即进入，可重试错误重试耗尽后进入；记录原消息、错误、堆栈、重试次数、时间；
   - **通知**：向发送方发 `delivery_failed`（见 Q9），让业务逻辑能做出"无法判定"之类的决策；
   - **处理**：DLQ 有告警阈值和负责人；提供"修复后重放"工具；定期统计 DLQ 命中率（讲义练习 1："How often does DLQ get hit"）。

### Q12 — 参考答案

```python
class Selector(Actor):
    def __init__(self, name, participants, pick, max_turns=6):
        super().__init__(name)
        self.participants, self.pick, self.max_turns = participants, pick, max_turns
        self.history = []

    def receive(self, message, runtime):
        if message.topic in ("task", "said"):
            self.history.append((message.sender, message.body))
            if "APPROVE" in str(message.body) or len(self.history) > self.max_turns:
                return                                        # 终止条件
            nxt = self.pick(self.history, self.participants)  # 真实系统：一次 LLM 调用
            if nxt not in self.participants:
                raise ValueError(f"selector picked unknown speaker {nxt!r}")
            runtime.send(self.name, nxt, "speak", list(self.history))


class Speaker(Actor):
    def __init__(self, name, reply):
        super().__init__(name)
        self.reply = reply

    def receive(self, message, runtime):
        if message.topic == "speak":
            runtime.send(self.name, message.sender, "said", self.reply(message.body))


def pick(history, participants):
    last_sender, last_body = history[-1]
    if last_sender == "__user__":
        return "coder"
    if last_sender == "coder":
        return "reviewer"
    return "coder" if "FIX" in last_body else "reviewer"
```

实测（coder 依次返回 `patch v1`、`patch v2`；reviewer 对 v1 回复 `FIX: missing test`、对 v2 回复 `APPROVE`）得到对话历史：

```text
[('__user__', 'add retry to http client'), ('coder', 'patch v1'),
 ('reviewer', 'FIX: missing test'), ('coder', 'patch v2'), ('reviewer', 'APPROVE')]
```

要点：
- selector 是唯一持有对话历史的 actor；发言者只通过消息拿到历史的**副本**（`list(self.history)`），不共享可变状态。
- 终止条件有两个：显式的 `APPROVE` 与 `max_turns` 上限，防止两个 agent 无限来回。
- pick 的输出必须校验，LLM 可能输出不存在的名字；校验失败抛异常会进 DLQ，可以再加"回落到轮转（round robin）"的兜底。
- `RoundRobinGroupChat` 只需把 `pick` 换成"按固定顺序取下一个"。

### Q13 — 参考回答要点

- **定义**：每个 actor 有私有状态、收件箱和处理函数；actor 之间只通过异步消息交互，不共享内存；处理函数可以回复、给其他 actor 发消息、创建新 actor、更新自身状态、停止自己。
- **好处**（讲义）：故障隔离（一个 actor 崩溃不影响其他）；天然并发（多条消息同时在途，各 actor 并发处理收件箱）；易于分布式（收件箱 + 传输层，进程内外同一抽象）；actor 内部一次处理一条消息，私有状态不需要锁。
- **与直接调用的本质区别**：直接调用是同步的调用栈，调用方被阻塞、被调用方的异常会沿栈传回、并发需要额外设计、跨进程需要重写；actor 的 `send` 立即返回，由 runtime 负责投递和失败处理。讲义："In the v0.2 model, calling `agent_a.chat(agent_b)` synchronously blocks agent_a until agent_b returns."
- 加分点：提到 Erlang/OTP 的 "let it crash" 理念（讲义 Key Terms 中 Fault isolation 的俗称）——让出错的 actor 失败，由监督者决定重启，而不是在每个函数里防御所有错误。

### Q14 — 参考回答要点

- **失败不可见**：发送方不在接收方的调用栈上，异常不会传回；必须设计失败通知（`delivery_failed`）或超时，否则会静默地等待或基于不完整结果做决策（本节 `ChecklistAgent` 就是例子）。
- **顺序问题**：单个收件箱内通常 FIFO，但不同发送方发来的消息之间、跨 actor 的因果顺序没有保证；需要在消息中携带关联 ID、序号。
- **重复投递**：重试、网络分区会导致同一消息被处理两次；handler 要幂等、按消息 ID 去重。
- **部分副作用**：handler 中途失败时已发出的消息不会撤回（Q11 第 2 问）。
- **调试困难**：调用栈被打散成消息流，需要 trace ID 把一次请求的所有消息串起来（讲义：每条消息一个 OTel span）。
- **背压与消息风暴**：快的生产者会淹没慢的消费者；循环回复会无限增长，需要上限（本节的 `max_messages`）。
- 加分点：skill 文件拒绝"为了好调试而用同步模式"，建议用日志 + tracing 代替。

### Q15 — 参考回答要点

| 维度 | LangGraph 有状态图 | AutoGen actor 模型 |
|------|-------------------|-------------------|
| 控制流 | 显式的图，下一步由边和 state 决定 | 隐式，由消息流决定 |
| 状态 | 一个共享的、带类型的 state，每步 checkpoint | 分散在各 actor 的私有状态中 |
| 强项 | 可审计、可恢复、human-in-the-loop | 高并发、故障隔离、分布式 |
| 适合 | 流程清晰的业务流程、审批 | 多个长期运行、彼此异步协作的 agent |

- 讲义（第 13 节）把 AutoGen v0.4 定位为"actor model alternative for high-concurrency scenarios"。
- **actor runtime 要做到可恢复需要补**：消息持久化（队列落盘 / 消息中间件如 NATS、RabbitMQ）；每个 actor 状态的快照或事件溯源（重放消息重建状态）；至少一次投递 + 幂等处理；actor 的监督与重启策略。
- 加分点：两者可以组合，例如图中的某个节点内部是一个 actor 团队，或者 actor 的状态用 checkpointer 持久化。

### Q16 — 参考回答要点

- **actor 划分**：`coordinator`（接收 PR、拆分任务、汇总结论）；`security_reviewer`、`perf_reviewer`、`style_reviewer`（各自专项）；可选 `selector`（动态决定还需要哪些 reviewer）；`reporter`（生成最终报告）。
- **消息类型**：`review_request{pr_id, diff_chunk, correlation_id}`、`review_result{correlation_id, reviewer, findings, ok}`、`delivery_failed{correlation_id, error}`、`timeout{correlation_id}`，用 dataclass 定义（讲义："Typed payload"）。
- **并发**：每个 reviewer 一个收件箱，coordinator 一次性 fan-out，reviewer 并发处理；同一 reviewer 内部串行，避免状态竞争。
- **超时与 DLQ**：coordinator 为每个请求设定时器（定时向自己发 `timeout` 消息）；超时或失败的 reviewer 结果记为"未完成"，结论标为"部分评审"而不是"通过"；可重试错误重试 2–3 次，耗尽后进 DLQ 并告警。
- **可观测性**：每条消息一个 span，`correlation_id` 作为 trace 关联；属性 `gen_ai.agent.name`、`gen_ai.operation.name`（第 23 节）；统计各 reviewer 的延迟、失败率、DLQ 命中率。
- 常见误区：coordinator 用"收到 N 个结果就下结论"却不处理失败，导致与本节 `ChecklistAgent` 一样的"过早共识"。

### Q17 — 参考回答要点

- 两个 actor 固定来回，本质是一条预先确定的流程：A 产出 → B 处理 → A 收尾。用 prompt chain（第 12 节）几行就能写完，控制流一目了然；套上 actor 框架会带来消息路由、DLQ、异步调试等额外复杂度，却换不来任何收益。
- skill 文件："Actors earn cost when there are >=3 actors or async concurrency."
- **值回成本的场景**：三个及以上 agent、需要并发、需要故障隔离（一个 agent 挂了其他继续）、需要跨进程或跨机器部署、agent 长期运行并响应外部事件。
- 加分点：本节 demo 本身就是两个 actor 的固定来回，按 skill 文件的规则它其实"不该"用 actor 框架——它的价值在于教学（展示消息、DLQ 与故障隔离），面试时能指出这一点很加分。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：本节的先修课；单个 agent 的循环是 actor 内部的处理逻辑。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：本节的先修课；判断何时不需要 actor 框架。
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../../11-llm-engineering/17-agent-framework-tradeoffs/docs/zh.md)：从框架选型角度比较图、角色与 actor。

### 本节被哪些后续内容用到
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：图模型与 actor 模型的对照（swarm 拓扑与 actor 相似）。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../15-crewai-role-based-crews/docs/zh.md)：另一种多 agent 抽象：角色与任务。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为每条消息埋点（讲义练习 4）。
- [阶段 14 · 25 多 Agent 辩论与协作](../../25-multi-agent-debate/docs/zh.md)：actor 之间的协商与辩论。
- [阶段 16 · 03 通信协议](../../../16-multi-agent-and-swarms/03-communication-protocols/docs/zh.md)：多 agent 消息格式与协议。
- [阶段 16 · 10 群聊与发言者选择](../../../16-multi-agent-and-swarms/10-group-chat-speaker-selection/docs/zh.md)：RoundRobin / Selector 的深入讨论。
- [阶段 16 · 12 A2A：Agent 与 Agent 之间的通信协议](../../../16-multi-agent-and-swarms/12-a2a-protocol/docs/zh.md)：跨进程、跨厂商的 agent 通信。

### 延伸关键词
`actor model` · `mailbox / inbox` · `let it crash` · `Erlang/OTP supervisor` · `AutoGen Core / AgentChat / Extensions` · `RoundRobinGroupChat` · `SelectorGroupChat` · `Magentic-One` · `Microsoft Agent Framework` · `dead-letter queue` · `at-least-once delivery` · `idempotency` · `correlation ID` · `backpressure`
