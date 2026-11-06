# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 13 节 有状态图 Orchestration：Durable Execution 与 Checkpoints ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`copy`、`json`、`dataclasses`、`typing`）；不需要 LangGraph、API key 或网络
>
> 同目录的 `main.ts` 是逐行对应的 TypeScript 版本（`npx tsx code/main.ts` 运行），结构与本文件一致，本讲解不单独展开。

---

## 1. 这份代码在考察什么

用不到 250 行标准库代码，复刻 LangGraph 的核心运行模型：

1. **图 = 状态机**：`StateGraph` 保存节点（函数）与边（直接边 / 条件边），`set_entry` 指定入口，`END` 是出口哨兵。
2. **节点只返回 update**：节点读 state、返回一个 dict，由运行时合并进 state（最简单的覆盖式 reducer）。
3. **每个节点之后做 checkpoint**：`Runner.run` 在每个节点执行后把 state 存进 `InMemoryCheckpointer`，形成完整的历史。
4. **Human-in-the-loop**：`human_gate` 节点在未审批时设置 `_pause_reason`，运行时保存 checkpoint 后抛 `PausedAtNode`；人审批后从 checkpoint 取出 state、修改、再恢复运行。

> 一句话：**把"下一步是什么"交给图、把"现在是什么状态"交给 checkpoint，于是中断后的恢复只是"读出 state、从下一个节点继续"**。同时要看清代码的简化：恢复点是手写的、checkpoint 只是内存里的 deepcopy、暂停靠异常。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `State` / `Update` / `NodeFn` / `Router` | 类型别名 | `dict[str, Any]` 与函数签名 | 带类型的 state（这里只是别名） |
| `START` / `END` | 字符串常量 | 入口 / 出口哨兵（`START` 未被使用） | 图的边界 |
| `Edge` | dataclass | `src`、`dst`、可选 `router`（布尔谓词） | 边 / 条件边 |
| `StateGraph` | 类 | `add_node`、`add_edge`、`add_conditional_edges`、`set_entry`、`_next` | 图定义 |
| `_make_router` | 函数 | 把"返回标签的 router"变成"判断标签是否等于某值的谓词" | 条件边实现 |
| `InMemoryCheckpointer` | 类 | 每个 session 一个 `(节点名, state 快照)` 列表 | checkpointer |
| `PausedAtNode` | 异常类 | 携带暂停节点名与 state | 中断信号 |
| `Runner` | 类 | `run`：执行 → 合并 → 保存 → 检查暂停 → 求下一节点 | 运行时 |
| `_classify` … `_send` | 6 个节点函数 | 关键字分类、生成工单、审批门、发送 | 业务节点 |
| `build_graph` | 函数 | classify →（条件）refund / bug / sales → human_gate → send → END | demo 图 |
| `main` | 函数 | 第一次运行（暂停）→ 打印历史 → 模拟审批 → 从 `send` 恢复 | 演示 |

数据流：`initial state` → `classify`（写 `route`）→ 条件边选 `bug` → `bug`（写 `ticket`）→ `human_gate`（未审批，写 `_pause_reason`）→ checkpoint → `PausedAtNode` → 人工把 `human_approval` 改为 True → `run(resume_from="send", state_override=...)` → `send`（写 `output`）→ `END`。

---

## 3. 逐段精讲

### 3.1 类型别名与哨兵

```python
State = dict[str, Any]
Update = dict[str, Any]
NodeFn = Callable[[State], Update]
Router = Callable[[State], str]

START = "__start__"
END = "__end__"
```

- 讲义说 State 是"A typed dict (or Pydantic model)"，并列出 `messages, step, route, output, human_approval` 等字段；代码里 `State` 只是 `dict[str, Any]` 的别名，**没有字段级的类型约束**，实际字段是 `input / step / human_approval / route / ticket / output`，没有 `messages`。
- 生产中会用 `TypedDict` 或 Pydantic 声明每个字段，配合类型检查器发现"节点写了不存在的键"之类的错误。
- `START` 定义了但没有使用：入口由 `set_entry` 指定。LangGraph 中通常写成"从 `START` 连一条边到第一个节点"，两者等价。

### 3.2 `StateGraph`：节点、边与条件边

```python
    def add_conditional_edges(self, src, router, targets):
        for value, dst in targets.items():
            self.edges.setdefault(src, []).append(
                Edge(src=src, dst=dst, router=_make_router(router, value))
            )

    def _next(self, current, state):
        for edge in self.edges.get(current, []):
            if edge.router is None or edge.router(state):
                return edge.dst
        return None


def _make_router(router, expected):
    def fn(state):
        return router(state) == expected
    return fn
```

- 条件边被展开成多条普通边，每条带一个谓词："router 的返回值是否等于这个标签"。`targets={"refund": "refund", "bug": "bug", "sales": "sales"}` 变成 3 条边。
- `_make_router` 是一个**闭包工厂**：每次调用都生成一个新的 `fn`，各自记住自己的 `expected`。如果直接在循环里写 `lambda s: router(s) == value`，所有 lambda 都会引用循环结束时的最后一个 `value`（Python 闭包的晚绑定陷阱）。用工厂函数正是为了避开它。
- `_next` 按**插入顺序**找第一条匹配的边。直接边（`router is None`）总是匹配。
- ⚠️ 每条条件边都会重新调用一次 router：3 个目标时 router 可能被调用 3 次（实测）。router 若有副作用或调用 LLM，就会重复执行、甚至前后不一致。更好的实现是调用一次 router，再查表。
- ⚠️ 没有边匹配时返回 `None`，`run` 静默结束（实测：router 返回 `"zzz"` 时直接返回当前 state）。调用方无法区分"正常走到 END"和"图走丢了"。
- `Edge.src` 字段存了但从未读取（边已经按 `src` 存在字典里）。

### 3.3 `InMemoryCheckpointer`

```python
class InMemoryCheckpointer:
    def __init__(self):
        self._store: dict[str, list[tuple[str, State]]] = {}

    def save(self, session_id, step_name, state):
        self._store.setdefault(session_id, []).append((step_name, copy.deepcopy(state)))

    def load_latest(self, session_id):
        history = self._store.get(session_id, [])
        if not history:
            return None
        return history[-1]

    def history(self, session_id):
        return list(self._store.get(session_id, []))
```

- 每个 session 保存**完整历史**（不是只保留最新），这使"回看任意一步的 state"（LangGraph 所谓 time travel）成为可能，也方便调试。
- `save` 用 `copy.deepcopy`，保证之后对 state 的修改不会影响已保存的快照。
- ⚠️ `load_latest` / `history` 返回的是**内部对象的引用**：调用方原地修改返回的 dict，会直接改掉已保存的 checkpoint（实测 `st["hacked"] = True` 后历史中也出现 `hacked`）。读取时也应 deepcopy。
- ⚠️ 讲义称它为"`SQLiteCheckpointer` (in-memory fake)"并说"serializes state"；实际类名是 `InMemoryCheckpointer`，`deepcopy` 不是序列化——它能复制 `datetime`、`set` 等任何对象，换成 SQLite + JSON 时这些值会直接报 `TypeError`。进程退出后数据也全部丢失，因此它**不能**真正实现"崩溃后恢复"。

### 3.4 `Runner.run`：执行循环

```python
    def run(self, session_id, initial_state, resume_from=None, state_override=None):
        if state_override is not None:
            state = copy.deepcopy(state_override)
        else:
            state = copy.deepcopy(initial_state)
        current = resume_from or self.graph.entry
        if current is None:
            raise RuntimeError("no entry node set")
        while current is not None and current != END:
            fn = self.graph.nodes.get(current)
            if fn is None:
                raise RuntimeError(f"unknown node {current!r}")
            update = fn(state)
            if update is None:
                update = {}
            state = {**state, **update}
            self.checkpointer.save(session_id, current, state)
            if state.get("_pause_reason"):
                reason = state.pop("_pause_reason")
                raise PausedAtNode(current, state)
            current = self.graph._next(current, state)
        return state
```

逐步看每轮循环的顺序：

| 顺序 | 动作 | 为什么 |
|------|------|-------|
| 1 | `fn(state)` 执行节点 | 节点只读 state、返回 update |
| 2 | `update is None` → `{}` | 容忍"什么都不改"的节点 |
| 3 | `state = {**state, **update}` | **覆盖式 reducer**，并且生成新 dict（不原地修改） |
| 4 | `checkpointer.save(...)` | 节点成功后立刻持久化——这就是"每个节点之后 checkpoint" |
| 5 | 检查 `_pause_reason` | 暂停前 state 已保存，恢复时有据可依 |
| 6 | `_next` 求下一节点 | 由图和 state 决定 |

- 若节点**抛异常**，第 4 步不会执行，最新 checkpoint 停留在上一个成功节点——这正是"从最后一个成功 checkpoint 恢复"的基础。`run` 本身不捕获异常，交给调用方。
- `resume_from` 让运行从任意节点开始；`state_override` 用给定 state 代替 `initial_state`（此时 `initial_state` 被忽略）。
- ⚠️ 覆盖式合并：节点返回 `{"messages": [...]}` 会**替换**原列表而不是追加。讲义 Key Terms 提到 reducer，LangGraph 允许为字段声明追加等合并方式（测验 Q11）。
- ⚠️ `_pause_reason` 的不一致：checkpoint 保存时 state 里**还有** `_pause_reason`，随后 `state.pop` 只影响异常里携带的那份。所以 `main()` 从 checkpoint 读出 state 后要再 `pop` 一次。`reason` 变量取出后没有使用。
- ⚠️ 没有最大步数限制：若条件边构成环且条件永远满足，会无限循环。
- 暂停靠异常实现：用异常做控制流简单直接，但调用方必须记得捕获 `PausedAtNode`。

### 3.5 节点函数

```python
def _classify(state):
    text = state["input"].lower()
    if "refund" in text or "money back" in text:
        route = "refund"
    elif "crash" in text or "bug" in text or "error" in text:
        route = "bug"
    elif "pricing" in text or "quote" in text:
        route = "sales"
    else:
        route = "sales"
    return {"route": route, "step": state.get("step", 0) + 1}


def _human_gate(state):
    if not state.get("human_approval"):
        return {"_pause_reason": "awaiting human approval",
                "step": state.get("step", 0) + 1}
    return {"step": state.get("step", 0) + 1}
```

- `_classify` 是关键字规则（真实系统中是一次 LLM 调用）。`else` 分支也路由到 `sales`：任何不认识的输入都会被送去销售（实测 "hello there" → sales）。讲义练习 1 要求低置信度时走到 `END`。
- 三个工单节点生成 `"REF-/BUG-/SAL-" + input[:12]`，切片 `[:12]` 取前 12 个字符。
- 所有节点都执行 `step + 1`，用来演示"每一步都被记录"。
- ⚠️ `_human_gate` 无论是否暂停都会加 1，**不幂等**：同一节点被恢复重跑一次，`step` 就多 1（实测 3 → 4 → 5）。在扣款、发邮件这类节点上，同样的模式意味着重复副作用。
- `_send` 不检查审批状态，审批只在 `human_gate` 中检查一次（见 3.7）。

### 3.6 `build_graph`：路由 workflow 的图形式

```python
    graph.add_conditional_edges(
        "classify",
        router=lambda s: s["route"],
        targets={"refund": "refund", "bug": "bug", "sales": "sales"},
    )
    graph.add_edge("refund", "human_gate")
    graph.add_edge("bug", "human_gate")
    graph.add_edge("sales", "human_gate")
    graph.add_edge("human_gate", "send")
    graph.add_edge("send", END)
```

```text
classify ──route──┬─> refund ─┐
                  ├─> bug    ─┼─> human_gate ─> send ─> END
                  └─> sales  ─┘
```

- 这就是第 12 节的 routing 模式，只不过现在每一步都有 checkpoint、并且能暂停等人。
- 只有一处条件边，其余都是直线——符合讲义"Prefer linear chains with occasional branches"。

### 3.7 `main`：暂停 → 审批 → 恢复

```python
    latest = ckpt.load_latest(session)
    last_node, last_state = latest
    approved_state = {**last_state, "human_approval": True}
    approved_state.pop("_pause_reason", None)
    ckpt.save(session, f"{last_node}_reviewed", approved_state)

    final = runner.run(session_id=session, initial_state=initial,
                       resume_from="send", state_override=approved_state)
```

- 从 checkpoint 读出 `human_gate` 之后的 state，模拟人工审批（`human_approval=True`），去掉 `_pause_reason`，把审批后的 state 作为一条名为 `human_gate_reviewed` 的伪 checkpoint 存档，然后从 `send` 继续。
- ⚠️ `resume_from="send"` 是**写死**的。讲义说"Resume is a `load_state(session_id)` call"，理想情况下应由运行时根据最新 checkpoint 和图自动算出恢复点。写死带来的问题：如果审批人拒绝（`human_approval=False`），照样从 `send` 恢复，工单仍会被发出——审批被绕过（实测）。测验 Q9 给出了自动计算恢复点的 `resume()`。
- ⚠️ 讲义说 trace 显示"the first run failing at the human gate"，实际是**暂停**而不是失败；demo 也没有演示真正的节点崩溃后恢复。
- `json.dumps(paused.state, default=str)`：`default=str` 让不可序列化的值以字符串形式打印，而不是报错。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| State 用 `dict[str, Any]` | 简单灵活 | 无字段类型约束；生产用 TypedDict / Pydantic |
| 节点返回 update、运行时合并 | state 修改集中、可追踪；为并行合并留出空间 | 只有覆盖式 reducer；需要按字段声明 reducer |
| 条件边展开成多条谓词边 | 复用"找第一条匹配边"的统一逻辑 | router 被重复调用；无匹配时静默结束 |
| 每个节点后保存完整快照 | 恢复点精确，历史可回放 | 存储随步数线性增长；生产会做增量存储与过期清理 |
| `deepcopy` 内存 checkpointer | 零依赖 | 不是真正的序列化，进程退出即丢失；`load_latest` 泄漏引用 |
| 暂停 = 特殊字段 + 异常 | 实现最短 | checkpoint 与异常中的 state 不一致；调用方必须捕获 |
| 恢复点手写为 `"send"` | demo 直观 | 可能绕过审批；应由运行时根据 checkpoint 计算 |
| 关键字分类 | 离线可复现 | 未知输入默认走 sales；真实系统用 LLM + 置信度 |
| 节点内 `step + 1` | 演示每步都被记录 | 节点不幂等，重跑会累加 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类型别名 | `State = dict[str, Any]`、`NodeFn = Callable[[State], Update]` | 给复杂类型起名，提高可读性 |
| `Any` | `dict[str, Any]` | 任意类型，类型检查器不做约束 |
| `X \| None` 可选类型 | `router: Router \| None = None`、`str \| None` | 可能为 None |
| `@dataclass` 默认值 | `Edge(src, dst, router=None)` | 未传时为 None |
| `dict.setdefault` | `self.edges.setdefault(src, []).append(...)` | 键不存在时先放入默认值再返回它，常用于"分组追加" |
| 闭包工厂 | `_make_router(router, expected)` 返回内部 `fn` | 每次调用生成独立闭包，避免循环中 lambda 的晚绑定问题 |
| `copy.deepcopy` | `copy.deepcopy(state)` | 递归复制所有嵌套对象；与 `dict(state)` 的浅复制不同 |
| 字典解包合并 | `{**state, **update}` | 生成新字典，后者覆盖前者 |
| `dict.pop(key, default)` | `approved_state.pop("_pause_reason", None)` | 删除并返回值；键不存在时返回默认值而不报错 |
| 自定义异常 | `class PausedAtNode(Exception)` + `super().__init__(node)` | 异常对象可以携带额外属性（`node`、`state`） |
| `raise` / `try ... except` | `raise PausedAtNode(...)`、`except PausedAtNode as paused` | 用异常传递"暂停"信号 |
| `!r` 格式符 | `f"unknown node {current!r}"` | 用 `repr()` 显示值（字符串会带引号） |
| `or` 取默认值 | `current = resume_from or self.graph.entry` | 前者为假值（None、空串）时取后者 |
| `assert` | `assert latest is not None` | 开发期断言；用 `python -O` 运行时会被跳过，不能用于生产校验 |
| 元组解包 | `last_node, last_state = latest`、`for node, snap in ckpt.history(...)` | 一次取出多个值 |
| 字符串切片 | `state.get('input', '')[:12]` | 取前 12 个字符，不足时取全部 |
| `json.dumps(default=str)` | `json.dumps(paused.state, default=str)` | 遇到不可序列化的对象时调用 `str()` 转换 |
| 关键字参数调用 | `runner.run(session_id=session, ..., resume_from="send")` | 参数多时提高可读性 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成）：

```text
first run (will pause at human_gate)
  PAUSED at human_gate
  state at pause: {"input": "the CLI crashes on ctrl-c, please fix", "step": 3,
                   "human_approval": false, "route": "bug", "ticket": "BUG-the CLI cras"}

checkpoint history
  classify  route=bug  ticket=None  step=1               ← classify 后
  bug  route=bug  ticket=BUG-the CLI cras  step=2        ← bug 节点写入 ticket
  human_gate  route=bug  ticket=BUG-the CLI cras  step=3 ← 暂停前已保存

human approves; resume from next node after human_gate
  final: {'input': 'the CLI crashes on ctrl-c, please fix', 'step': 4, 'human_approval': True,
          'route': 'bug', 'ticket': 'BUG-the CLI cras', 'output': 'sent BUG-the CLI cras'}
```

逐项解读：

- **路由**：输入含 "crash"，`_classify` 选 `bug`。
- **暂停时的 state**：`step=3`（classify、bug、human_gate 各 +1）；这里打印的 state 已去掉 `_pause_reason`，但 checkpoint 里保存的那份**仍然带着**它。
- **checkpoint 历史**三条，对应三个已执行的节点；恢复之后历史还会增加 `human_gate_reviewed` 与 `send` 两条（`main` 在恢复前就打印了历史，所以看不到）。
- **恢复**：从 `send` 开始，只执行了一个节点，`step` 从 3 到 4，`output` 写入。前三个节点没有重跑——这就是 durable execution 想要的效果。

额外的探针实验（导入模块后调用，不修改源码）：

| 实验 | 结果 |
|------|------|
| 读出最新 checkpoint 并原地修改 | 已保存的历史被同步修改（引用泄漏） |
| 不审批，照搬 `resume_from="send"` | 工单仍被发送（审批被绕过） |
| 不审批，从 `human_gate` 恢复 | 再次暂停，`step` 变成 4 |
| 审批后从 `human_gate` 恢复 | 发送成功，`step` 变成 5（节点不幂等） |
| 条件边 router 返回未知标签 | `run` 静默返回，未到 `END` |
| 3 个目标的条件边 | router 被调用 3 次 |
| state 中放 `datetime` 再 `json.dumps` | `TypeError`，内存 checkpointer 无法发现这个问题 |

---

## 7. 动手改一改

1. **自动恢复**：实现 `resume(runner, session_id, patch=None)`：暂停时重跑暂停节点，崩溃时从下一个节点继续；用一个第一次调用会抛 `ConnectionError` 的 `send` 验证（参考测验 Q9）。
2. **修复引用泄漏 + 真正持久化（讲义练习 2）**：`load_latest` / `history` 返回 deepcopy；再写一个基于 `sqlite3` + `json` 的 `SQLiteCheckpointer`，用 `time.perf_counter()` 测每步序列化开销（参考测验 Q10）。
3. **置信度兜底（讲义练习 1）**：`_classify` 输出 `confidence`，低于 0.6 走到 `END`；人工设置 `route` 后恢复（参考测验 Q12）。
4. **字段级 reducer（讲义练习 3 的前置）**：给 `StateGraph` 加 `reducers`，让 `messages` 追加；再实现"两个节点并行、合并 update"，对同一个无 reducer 的键被两个节点写入的情况报错（参考测验 Q11）。
5. **Streaming（讲义练习 5）**：把 `run` 改成生成器，每个节点执行后 `yield (node, update)`，调用方边运行边打印 delta。
6. **安全加固**：`_next` 无匹配时抛异常；加 `max_steps`；`send` 节点内部再次校验 `human_approval`；给 `human_gate` 的计数改成幂等写法（例如只在首次进入时记录）。

---

## 8. 常见坑

- **checkpoint 太小**：只存对话，不存工具状态和记忆写入，恢复后"世界状态"对不上。讲义："Full state must serialize."
- **用内存 checkpointer 冒充持久化**：进程一挂全部丢失；`deepcopy` 能复制的对象不一定能 JSON 序列化，迁移到数据库时才暴露问题。
- **读 checkpoint 后原地修改**：如果 checkpointer 返回引用，会悄悄篡改历史。
- **手写恢复点**：容易跳过关键节点（如审批），应由运行时根据 checkpoint 和图计算。
- **节点不确定 / 不幂等**：恢复会重跑节点；读时钟、随机数、外部 API 的值要记录进 state，有副作用的操作要带幂等键。
- **条件边滥用**：讲义："A graph with every edge conditional is a state machine that cannot be reasoned about."
- **循环里用 lambda 捕获循环变量**：所有 lambda 共享最后一个值；本文件用 `_make_router` 工厂函数避免了这个坑，自己改写时要注意。
- **覆盖式合并丢数据**：消息列表、并行分支的结果需要专门的 reducer。
- **只捕获 `PausedAtNode`，忘记其他异常**：真实运行中节点崩溃更常见，要区分"暂停"和"失败"两种恢复路径。
