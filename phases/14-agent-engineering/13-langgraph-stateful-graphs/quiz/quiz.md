# 测验 · 有状态图 Orchestration：Durable Execution 与 Checkpoints（Stateful Graph Orchestration — Durable Execution and Checkpoints）

> **阶段 14 · Agent 工程 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有等价的 [code/main.ts](../code/main.ts)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：中文讲义为机器翻译，部分术语译错（如把 state machine 译成"州级机器"、把 checkpoint 译成"检查站"、把 concurrency 译成"货币"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Agent = 状态机 | 节点是函数、边是转移、状态是带类型的对象；**每个节点执行完都做 checkpoint** |
| 2 | 图的四个组成 | State 类型（TypedDict / Pydantic）、节点 `(state) -> state_update`、边（直接 / 条件）、`START` 与 `END` 哨兵 |
| 3 | Reducer | 把节点返回的 update 合并进当前 state 的函数；本节代码只有"覆盖式合并" `{**state, **update}` |
| 4 | Durable execution | 节点返回后序列化 state 写入 checkpointer（SQLite / Postgres / Redis / 自定义）；第 N 步失败后从第 N+1 步、用精确的 state 恢复 |
| 5 | 四项能力 | 讲义列出 LangGraph 文档强调的：durable execution、streaming、human-in-the-loop、comprehensive memory |
| 6 | Human-in-the-loop | 在关键节点前暂停 → 把 state 展示给人 → 接受修改 → 恢复；state 已序列化，所以很便宜 |
| 7 | 三种拓扑 | Supervisor（中心路由）、Swarm / P2P（通过共享工具直接 handoff）、Hierarchical（嵌套 subgraph） |
| 8 | 三个失败模式 | checkpoint 太小（只存对话）；节点不确定（随机数、时钟、外部 API 未捕获）；条件边滥用 |
| 9 | 确定性与幂等 | 恢复的前提是"同样输入得到同样 update"；会重复执行的节点要幂等，否则副作用会发生两次 |
| 10 | 本节代码的简化 | `InMemoryCheckpointer` 用 `deepcopy` 而非真正序列化；恢复点 `resume_from="send"` 是**手写**的；暂停靠异常实现 |

### 核心技能（能动手做到）

- [ ] 用 `StateGraph` 的 `add_node / add_edge / add_conditional_edges / set_entry` 搭一个路由图，并推演每一步的 state 与 checkpoint
- [ ] 解释 `Runner.run` 中"执行节点 → 合并 → 保存 checkpoint → 检查暂停 → 求下一节点"的顺序为什么重要
- [ ] 写一个根据 checkpoint **自动计算恢复点**的 `resume(session_id)`，同时处理"暂停"和"节点崩溃"两种情况
- [ ] 找出 `load_latest` 返回内部引用导致 checkpoint 被意外修改的问题，并写出基于 SQLite + JSON 的 checkpointer
- [ ] 为 `messages` 字段实现"追加式" reducer，说明覆盖式合并在并行分支下为什么会丢数据
- [ ] 判断一个节点是否幂等，并为有副作用的节点设计幂等键

---

## 二、基础自测（选择题）

**Q1.** 讲义对 LangGraph 核心模型的描述，最准确的是：

- A. 一个无状态的 prompt 模板库，每次调用都从头开始
- B. 带类型 state 的状态机：节点是函数、边（含条件边）是转移，每个节点执行后 state 被 checkpoint
- C. 一组彼此异步发消息的 actor
- D. 一组按角色分工、按顺序执行任务的 agent 团队

**Q2.** 讲义说 LangGraph 文档重点强调的四项能力是：

- A. 微调、量化、蒸馏、部署
- B. 路由、并行、投票、反思
- C. 检索、工具、记忆、规划
- D. Durable execution、streaming、human-in-the-loop、comprehensive memory

**Q3.** 下列哪一项**不是**讲义提到的 LangGraph 支持的三种编排拓扑之一？

- A. 环形流水线（ring pipeline）：每个 agent 只把结果传给下一个，最后一个再传回第一个
- B. Supervisor：中心路由 LLM 分派给专家 subagent
- C. Swarm / peer-to-peer：通过共享工具面直接 handoff，没有中心路由
- D. Hierarchical：supervisor 管理 sub-supervisor，以嵌套 subgraph 实现

**Q4.** 为什么讲义要求节点中的随机种子、系统时钟、外部 API 结果"must be captured"？

- A. 为了让图可以并行执行
- B. 为了减少 checkpoint 的体积
- C. 恢复时假设"同样的输入 state 产生同样的 update"；不捕获这些不确定来源，恢复后的执行可能与原执行不一致
- D. 因为 LangGraph 不允许节点调用外部 API

**Q5.** 运行 `main.py`，第一次运行在 `human_gate` 暂停时，打印的 state 中 `step` 和 `ticket` 分别是：

- A. `step=3`，`ticket="BUG-the CLI cras"`
- B. `step=2`，`ticket="BUG-the CLI crashes on ctrl-c, please fix"`
- C. `step=3`，`ticket="SAL-the CLI cras"`
- D. `step=4`，`ticket="BUG-the CLI cras"`

**Q6.** `Runner.run` 用 `state = {**state, **update}` 合并节点返回值。若 state 中已有 `"messages": ["hi"]`，某节点返回 `{"messages": ["hello"]}`，合并后 `messages` 是：

- A. `["hi", "hello"]`，因为字典合并会自动拼接列表
- B. 抛出 `KeyError`，因为键重复
- C. `["hi"]`，因为已有的键不会被覆盖
- D. `["hello"]`，后者覆盖前者；要追加需要自定义 reducer

**Q7.** 在本节的 `StateGraph` 中，若某个条件边的 router 返回了一个**不在 `targets` 里**的值（且该节点没有其他边），会发生什么？

- A. 抛出 `KeyError`
- B. `_next` 返回 `None`，`run` 的 while 循环结束，**静默地**返回当前 state，既没到 `END` 也没有报错
- C. 自动跳到 `END`，并打印警告
- D. 自动回到入口节点重新执行

**Q8.** 假设审批人**拒绝**了（`human_approval` 仍为 `False`），但运维照搬 `main()` 的写法，用 `resume_from="send"` 和该 state 恢复运行。结果是：

- A. `human_gate` 再次暂停，等待审批
- B. 抛出 `PausedAtNode`
- C. 工单照样被发送：恢复点直接跳过了 `human_gate`，审批检查被绕过
- D. 抛出 `RuntimeError("unknown node")`

---

## 三、动手 / 代码题

**Q9.**（补全函数）讲义说"Resume is a `load_state(session_id)` call"，但本节 `main()` 里的恢复是手写的：

```python
    latest = ckpt.load_latest(session)
    last_node, last_state = latest
    approved_state = {**last_state, "human_approval": True}
    approved_state.pop("_pause_reason", None)
    ckpt.save(session, f"{last_node}_reviewed", approved_state)

    final = runner.run(session_id=session, initial_state=initial,
                       resume_from="send", state_override=approved_state)
```

请写一个 `resume(runner, session_id, patch=None)`：只根据 checkpoint 决定从哪里继续。要求同时处理两种情况：① 上一次因为 `human_gate` **暂停**；② 上一次因为某节点**抛异常崩溃**（例如 `send` 调用外部 API 失败）。说明两种情况下恢复点分别应是什么。

**Q10.**（读代码找问题 + 改造）阅读 `InMemoryCheckpointer`：

```python
class InMemoryCheckpointer:
    def __init__(self) -> None:
        self._store: dict[str, list[tuple[str, State]]] = {}

    def save(self, session_id, step_name, state):
        self._store.setdefault(session_id, []).append((step_name, copy.deepcopy(state)))

    def load_latest(self, session_id):
        history = self._store.get(session_id, [])
        if not history:
            return None
        return history[-1]
```

1. 下面的代码会不会改变已保存的 checkpoint？为什么？
   ```python
   node, st = ckpt.load_latest("s001"); st["hacked"] = True
   print(ckpt.history("s001")[-1][1].get("hacked"))
   ```
2. 讲义说 checkpointer "serializes the state"。`deepcopy` 和序列化有什么区别？如果 state 里放了 `datetime` 或 `set`，换成真正的 SQLite checkpointer 时会发生什么？
3. 写一个 `SQLiteCheckpointer`（讲义练习 2），接口与 `InMemoryCheckpointer` 相同。

**Q11.**（改造代码）讲义 Key Terms 把 reducer 定义为"Function that combines current state with a node's update"，并在练习 3 中要求"two nodes run concurrently, merge by a custom reducer"。

1. 给 `StateGraph` 增加 `reducers: dict[str, Callable[[Any, Any], Any]]`，让 `messages` 字段用"追加"合并，其他字段仍覆盖。写出合并函数。
2. 两个并行节点分别返回 `{"messages": ["a"], "ticket": "T1"}` 和 `{"messages": ["b"], "ticket": "T2"}`，用你的 reducer 合并后结果是什么？`ticket` 的冲突应如何处理？
3. "不可变 state"（节点只返回 update、不原地修改 state）在并行时带来什么好处？

**Q12.**（改造代码）完成讲义练习 1，并修掉两个隐患：

1. `_classify` 增加 `confidence` 字段；置信度低于 0.6 时从 `classify` 走条件边到 `END`，由人手动设置 `route` 后恢复。
2. 让 `_next` 在"非 END 节点没有任何边匹配"时抛出异常，而不是静默结束（见 Q7）。
3. 实测：若暂停后**不审批**就从 `human_gate` 重新恢复，`step` 会从 3 变成 4；审批后再恢复变成 5。这说明了节点的什么问题？在真实系统中会造成什么后果？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 durable execution？LangGraph 是怎么实现的？为什么说它的价值"不在图的形状，而在图 + checkpoint 让恢复变得便宜"？

**Q14.**（原理深挖）从 checkpoint 恢复时，为什么节点必须是确定的、最好是幂等的？如果一个节点会发邮件或扣款，你如何保证恢复后不会重复执行副作用？

**Q15.**（工程实践）请设计一个 human-in-the-loop 的审批流程：在哪里暂停、如何展示 state、人修改 state 后如何恢复、如何审计。对比本节代码的实现，指出它的不足。

**Q16.**（场景设计）一个需要 40 步、运行数小时的研究型 agent 经常在第 30 多步因为外部 API 超时而失败。请设计它的 state schema、checkpointer 后端、恢复策略和监控。

**Q17.**（追问型）Supervisor、Swarm、Hierarchical 三种拓扑各适合什么场景？图有 30 多个节点时该怎么办？讲义提到 2026 年 LangChain 团队对 supervisor 的实现给出了什么建议？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义开篇："Agent is a state machine; nodes are functions; edges are transitions; state is checkpointed after each node." A 恰好相反；C 是第 14 节 AutoGen 的 actor 模型；D 是第 15 节 CrewAI 的角色团队。

### Q2 — 答案：D

讲义学习目标："Name the four capabilities the docs highlight: durable execution, streaming, human-in-the-loop, comprehensive memory." C 是第 12 节 augmented LLM 的三项能力加上规划，不是 LangGraph 的四项能力；A、B 与本节无关。

### Q3 — 答案：A

讲义的三种拓扑是 supervisor、swarm / peer-to-peer、hierarchical（嵌套 subgraph），即 B、C、D。A 是编造的干扰项。补充：讲义提到 supervisor 可以用 `langgraph-supervisor` 的 `create_supervisor()`，但"the LangChain team in 2026 recommends doing this through tool calls directly for more context control"。

### Q4 — 答案：C

讲义："Resume assumes node inputs produce the same state update. Random seeds, wall-clock, external APIs must be captured." 也就是说要把这些不确定的值作为 state 的一部分记录下来，恢复时重放记录的值而不是重新生成。A、B 与确定性无关；D 错，节点当然可以调用外部 API，只是结果要被记录。

### Q5 — 答案：A

`_classify` 发现输入里有 "crash"，路由到 `bug`；`_bug` 生成 `"BUG-" + input[:12]`，前 12 个字符是 `"the CLI cras"`；`classify`、`bug`、`human_gate` 各给 `step` 加 1，暂停时 `step=3`（`human_gate` 在返回 `_pause_reason` 的同时也增加了 step）。实际输出：`"step": 3, ... "ticket": "BUG-the CLI cras"`。D 是恢复后 `send` 执行完的值。

### Q6 — 答案：D

`{**a, **b}` 是"后者覆盖前者"的浅合并，不会拼接列表。这正是讲义 Key Terms 里 reducer 的意义：LangGraph 允许为字段声明 reducer（例如对消息列表做追加），否则就是覆盖。A 是许多人的错误直觉；B、C 都不是 Python 字典解包的行为。见 Q11。

### Q7 — 答案：B

```python
    def _next(self, current, state):
        for edge in self.edges.get(current, []):
            if edge.router is None or edge.router(state):
                return edge.dst
        return None
```

没有边匹配时返回 `None`，`run` 的循环条件 `current is not None and current != END` 不成立，直接返回 state。实测：router 返回 `"zzz"` 时 `run` 静默返回 `{'route': 'zzz'}`。调用方无法区分"正常结束"和"图走丢了"。另外，每条条件边都会**重新调用一次** router（实测 3 个目标时 router 被调用 3 次），若 router 有副作用或不确定，结果会出错。

### Q8 — 答案：C

实测：用 `human_approval=False` 的 state、`resume_from="send"` 恢复，得到 `'output': 'sent BUG-the CLI cras'`——工单照样发出。暂停逻辑在 `human_gate` 节点内部，跳过这个节点就跳过了检查，`send` 本身不检查审批状态。A 只有当恢复点是 `human_gate` 时才会发生（实测会再次暂停）。教训：**关键动作节点自身也应校验前置条件**（纵深防御），恢复点应由运行时根据 checkpoint 计算，而不是由人手写。

### Q9 — 参考答案

```python
import copy

def resume(runner, session_id, patch=None):
    latest = runner.checkpointer.load_latest(session_id)
    if latest is None:
        raise RuntimeError(f"no checkpoint for {session_id!r}")
    node, state = latest
    state = copy.deepcopy(state)                          # 不要改动 checkpoint 本身
    paused = state.pop("_pause_reason", None) is not None
    state.update(patch or {})                              # 人工修改（如审批）
    nxt = node if paused else runner.graph._next(node, state)
    if nxt is None or nxt == END:
        return state
    return runner.run(session_id, state, resume_from=nxt)
```

- **暂停**：checkpoint 里保存的是 `human_gate` 执行后的 state，并且带着 `_pause_reason`（`run` 在 pop 之前就保存了）。恢复点应是**暂停的节点本身**，让 `human_gate` 用新 state 重新检查审批；不审批就再次暂停。这与 LangGraph `interrupt()` 恢复时重新执行该节点的语义一致。
- **崩溃**：节点抛异常时 `run` 不会为它保存 checkpoint，最新 checkpoint 是"上一个成功的节点"，恢复点是用 `_next(上一个节点, state)` 算出的下一个节点，也就是崩溃的那个节点，重新执行它。
- 已实测：暂停后不带 patch 恢复会再次暂停；带 `{"human_approval": True}` 恢复成功发送；`send` 第一次抛 `ConnectionError` 时 checkpoint 历史为 `['classify', 'refund', 'human_gate']`，`resume` 后补上 `send` 并得到输出。
- 注意：`run` 的第二个参数 `initial_state` 在 `state_override` 为空时才使用，这里直接把恢复的 state 当作 `initial_state` 传入即可。

### Q10 — 参考答案

1. **会**。`load_latest` 直接返回列表中的元组，元组里的 dict 就是 checkpoint 内部保存的那个对象；`st["hacked"] = True` 修改的是同一个对象，实测 `history()` 打印 `True`。`history()` 用 `list(...)` 只复制了外层列表，同样不保护内部 dict。修复：`load_latest` / `history` 返回 `copy.deepcopy(...)`。（`main()` 里用 `{**last_state, ...}` 新建了字典，所以没有触发这个问题，但只要嵌套字段被原地修改就会中招。）
2. `deepcopy` 在**内存中**复制 Python 对象，任何对象都能复制，进程退出就没了；序列化是把 state 转成字节 / 文本（JSON、pickle）写到外部存储，进程崩溃后可以在另一台机器上恢复。JSON 只支持 dict / list / str / 数字 / bool / None，`datetime`、`set` 会报 `TypeError: Object of type datetime is not JSON serializable`（已实测）。`main()` 里 `json.dumps(..., default=str)` 会把这类值悄悄转成字符串，恢复后类型就变了。所以 state schema 要从一开始就设计成可序列化的。
3. 参考实现：

```python
import json, sqlite3

class SQLiteCheckpointer:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS ckpt ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " session_id TEXT, step_name TEXT, state TEXT)")

    def save(self, session_id, step_name, state):
        with self.conn:                                   # 每次保存是一个事务
            self.conn.execute(
                "INSERT INTO ckpt (session_id, step_name, state) VALUES (?, ?, ?)",
                (session_id, step_name, json.dumps(state)))   # 不可序列化就立刻报错

    def load_latest(self, session_id):
        row = self.conn.execute(
            "SELECT step_name, state FROM ckpt WHERE session_id = ? "
            "ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
        return None if row is None else (row[0], json.loads(row[1]))

    def history(self, session_id):
        rows = self.conn.execute(
            "SELECT step_name, state FROM ckpt WHERE session_id = ? ORDER BY id",
            (session_id,)).fetchall()
        return [(n, json.loads(s)) for n, s in rows]
```

  `json.loads` 每次返回新对象，天然避免了第 1 问的引用泄漏。用参数化查询（`?`）避免 SQL 注入。测量序列化开销时，可以用 `time.perf_counter()` 包住 `save`，对比 state 大小（例如消息列表增长到上千条）时每步的耗时。

### Q11 — 参考答案

1. 合并函数：

```python
def append_reducer(old, new):
    return (old or []) + list(new)

def merge(state, update, reducers):
    merged = dict(state)
    for key, value in update.items():
        if key in reducers and key in merged:
            merged[key] = reducers[key](merged[key], value)
        else:
            merged[key] = value                       # 默认：覆盖
    return merged

# 在 Runner.run 中把 state = {**state, **update} 换成
# state = merge(state, update, self.graph.reducers)
```

2. 依次合并两个 update：`messages` 得到 `[..., "a", "b"]`（顺序取决于合并顺序，若要确定需按节点名排序后合并）；`ticket` 是覆盖语义，后合并的 `"T2"` 胜出、`"T1"` 被静默丢弃。对冲突字段应：要么让两个并行节点写**不同的键**；要么为它声明 reducer（如合并成列表）；要么检测到同一 super-step 内多个节点写同一个无 reducer 的键时直接报错。
3. 不可变 state 的好处：每个并行节点读到的是同一份快照，互不干扰，没有竞态；合并发生在一个确定的位置（节点全部返回之后），可以对 update 排序后合并，结果可复现；每个节点的 update 可以单独记录，用于 streaming 输出 delta 和调试。

### Q12 — 参考答案

1. 修改 `_classify` 与边：

```python
def _classify(state):
    text = state["input"].lower()
    route, conf = "sales", 0.3                    # 默认：低置信度
    if "refund" in text or "money back" in text:
        route, conf = "refund", 0.9
    elif "crash" in text or "bug" in text or "error" in text:
        route, conf = "bug", 0.9
    elif "pricing" in text or "quote" in text:
        route, conf = "sales", 0.8
    return {"route": route, "confidence": conf, "step": state.get("step", 0) + 1}

graph.add_conditional_edges(
    "classify",
    router=lambda s: "low" if s["confidence"] < 0.6 else s["route"],
    targets={"refund": "refund", "bug": "bug", "sales": "sales", "low": END},
)
```

  原代码的 `else: route = "sales"` 把所有无法识别的输入都送去销售（例如 "hello there" 被路由到 sales，已实测），这正是需要置信度兜底的原因。低置信度时图走到 `END`，最后一个 checkpoint 是 `classify`；人手动设置 `route` 后，用 Q9 的 `resume(runner, sid, {"route": "bug", "confidence": 1.0})` 恢复，`_next("classify", state)` 会选出 `bug`。

2. 让 `_next` 报错：

```python
    def _next(self, current, state):
        edges = self.edges.get(current, [])
        for edge in edges:
            if edge.router is None or edge.router(state):
                return edge.dst
        raise RuntimeError(f"no edge matched from {current!r}; state keys={list(state)}")
```

  `send → END` 有一条直接边，所以正常结束不受影响。

3. `human_gate` 每执行一次就给 `step` 加 1，与是否真正推进无关：它**不是幂等的**。这里只是计数器偏大，但同样的模式放到"扣款""发送邮件""创建工单"的节点上，恢复时就会重复扣款、重复发信。对策：会被重复执行的节点要么无副作用，要么用幂等键（如 `session_id + 节点名 + 尝试序号`）去重，要么把副作用放到恢复点之后、由专门节点只执行一次并把结果写入 state。

### Q13 — 参考回答要点

- **定义**：长任务执行到中途失败（进程崩溃、API 超时、机器重启）后，能从最后一个成功的步骤、用完全一致的 state 继续，而不是从头再来。讲义："when a 40-step run fails at step 38, you want to resume from step 38, not start over."
- **LangGraph 的实现**：state 是一等公民的带类型对象；节点只返回 update，修改是显式的；每个节点返回后，运行时序列化 state 写入 checkpointer（SQLite / Postgres / Redis / 自定义）；恢复时按 session（thread）加载最新 checkpoint 继续。
- **价值所在**：讲义说"The claim isn't the graph shape; it's that the graph shape plus checkpointing makes recovery cheap." 图让"下一步是什么"可以从 state 计算出来；checkpoint 让 state 随时可得。两者结合，恢复、人工审批、时间回溯（从历史 checkpoint 重放）都变成廉价操作。讲义提到 Klarna、Uber、J.P. Morgan 等生产用户。
- 加分点：说明 checkpoint 也是调试资产（skill 文件："Failures need state too — that's where debugging starts"）。

### Q14 — 参考回答要点

- **确定性**：恢复时会重新执行"崩溃的节点"或"暂停的节点"。如果节点内部读时钟、随机数或外部 API，重新执行的结果可能与第一次不同，导致后续路径不同、无法复现。做法：把这些值作为 state 记录（或在节点内先查 state 里有没有已记录的值）。
- **幂等**：同一个节点执行多次和执行一次效果相同。本节 `human_gate` 每次执行都让 `step` 加 1，就是不幂等的例子。
- **防重复副作用**：
  - 幂等键：调用支付 / 邮件 API 时带上 `session_id + node + attempt` 生成的唯一键，由下游去重；
  - 先记录、后执行：先把"要执行的动作"写入 state 并 checkpoint，执行成功后再写"已完成"标记，恢复时检查标记；
  - 把副作用节点放在 human gate 之后，并在节点内部再次校验前置条件（见 Q8）；
  - 对不能撤销的动作使用 outbox 模式或事务。
- 常见误区：以为"有 checkpoint 就能安全重放"——checkpoint 保存的是 state，不能撤销外部世界的变化。

### Q15 — 参考回答要点

- **暂停点**：在不可逆或高风险节点（发送、付款、部署）**之前**暂停；暂停原因、待审批的具体内容写入 state。
- **展示**：从 checkpoint 读出 state，渲染成人能看懂的摘要（将要执行的动作、关键字段、依据）。
- **修改与恢复**：允许人修改 state 中的特定字段（白名单），修改本身作为一个新的 checkpoint 记录（谁、何时、改了什么）；恢复时重新执行 gate 节点让它再次校验。
- **审计**：每个 checkpoint 带时间戳、节点名、操作者；保留完整历史，支持回放。
- **本节代码的不足**：
  - 暂停靠节点返回 `_pause_reason` + 抛异常，checkpoint 里留着 `_pause_reason`，而异常里的 state 已被 pop，两者不一致；
  - 恢复点 `"send"` 是手写的，会绕过 gate（Q8）；
  - 审批记录用 `f"{last_node}_reviewed"` 这种伪节点名写入历史，没有记录审批人；
  - `send` 自身不校验审批状态。
- 加分点：提到 LangGraph 有 `interrupt_before` / `interrupt()` 这类内置机制，恢复时通过命令传入人的输入（具体 API 以官方文档为准）。

### Q16 — 参考回答要点

- **state schema**：任务目标、计划（步骤列表与状态）、已完成步骤的结果引用（大对象存对象存储，state 里只存 key）、消息历史（追加 reducer）、外部调用的请求 / 响应记录（保证可重放）、重试计数、预算消耗；全部可 JSON 序列化。讲义警告"Checkpoints too small"：只存对话会让工具状态和记忆写入无法恢复。
- **checkpointer 后端**：单机原型用 SQLite；多实例生产用 Postgres（事务、查询历史）；Redis 适合低延迟但要配置持久化。
- **恢复策略**：外部 API 调用加超时与指数退避重试；节点失败超过阈值则暂停并通知人；恢复时用 Q9 的逻辑自动计算恢复点；外部调用带幂等键。
- **图结构**：主干线性、少量分支（讲义："Prefer linear chains with occasional branches"）；把可独立的子流程封装成 subgraph。
- **监控**：每个节点的耗时、失败率、重试次数；会话卡在暂停状态的时长；checkpoint 大小增长；用 OpenTelemetry span 记录每一步（skill 文件建议阅读第 23 节）。
- 加分点：设置总步数上限，防止条件边构成的循环无限运行；定期清理过期会话的 checkpoint。

### Q17 — 参考回答要点

- **Supervisor**：一个中心路由 LLM 把任务分派给专家 subagent，适合"有明确分工、需要统一把控"的场景；缺点是中心节点成为瓶颈和单点。
- **Swarm / P2P**：agent 之间通过共享工具直接 handoff，没有中心路由，适合对话式、按话题流转的场景；缺点是全局状态难以把握。
- **Hierarchical**：supervisor 管理 sub-supervisor，用嵌套 subgraph 实现，适合大型系统按领域分层。
- **30+ 节点**：skill 文件规定"more than ~30 nodes, refuse flat layout and require nested subgraphs. Flat 30-node graphs are unreviewable"。把子流程封装为 subgraph，每层保持可读。
- **2026 年的建议**：讲义称 LangChain 团队建议 supervisor "through tool calls directly for more context control"，即把子 agent 包装成工具由主 agent 调用，而不是依赖 `create_supervisor()` 的封装。
- 加分点：说明拓扑选择要和 checkpoint 粒度一起考虑：subgraph 内部的 state 是否需要单独持久化、恢复时从哪一层恢复。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：本节的先修课；agent loop 本身就是一个隐式的状态机。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：本节的先修课；本节 demo 就是"routing 模式 + 持久化"。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：从 LLM 工程角度介绍同一套概念。

### 本节被哪些后续内容用到
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../14-autogen-actor-model/docs/zh.md)：高并发场景下的另一种运行时模型。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：handoff 与 guardrail 层。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：内置会话存储的托管 harness。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为图的每一步打 span。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：durable execution 的深入展开。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：检查点与回滚。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：多 agent 系统中的持久化。

### 延伸关键词
`StateGraph` · `TypedDict / Pydantic state` · `reducer / add_messages` · `conditional edges` · `checkpointer（SQLite / Postgres / Redis）` · `thread_id` · `interrupt / human-in-the-loop` · `time travel` · `subgraph` · `idempotency key` · `outbox pattern` · `durable execution`
