# 测验 · Agent State Machines——图、节点与 Checkpoints（Agent State Machines — Graphs, Nodes, Checkpoints）

> **阶段 11 · LLM 工程 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节代码需要 `ANTHROPIC_API_KEY`。下文的"实际运行结果"是用一个返回固定 tool call 的假 LLM 替换 `ChatAnthropic` 后，在 langgraph 1.2.14（另在 0.2.50 上对照）中真实跑出的，图、checkpointer、interrupt、time-travel 的行为都是 LangGraph 的真实行为。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 从 `while True` 到显式图 | agent 本来就是状态机（system prompt + 消息历史 + 待执行 tool call + 下一步动作）；画成图后 harness 免费获得 checkpoint、interrupt、streaming、time-travel 四种能力 |
| 2 | StateGraph 三要素 | State（TypedDict/Pydantic）、Nodes（`state -> 部分更新`）、Edges（静态边 / 条件边 + router 函数） |
| 3 | Reducer | 每个 state 字段的合并函数 `(old, new) -> merged`；默认覆盖；消息列表用 `add_messages`（追加，且按消息 id 替换/删除） |
| 4 | 忘记 reducer 的后果 | 顺序执行的节点：后写覆盖先写、静默丢历史；并行节点同一步写同一字段：LangGraph 直接抛 `InvalidUpdateError`（实测） |
| 5 | ReAct 图 | 2 个节点（`agent`、`tools`）+ 1 条条件边（`agent` → `tools` / `END`）+ 1 条静态边（`tools` → `agent`） |
| 6 | Checkpointer 与 thread | `compile(checkpointer=...)` 后每个 super-step 存一个快照，键为 `(thread_id, checkpoint_id)`；`MemorySaver` 只用于测试，生产用 Postgres/SQLite/Redis |
| 7 | Interrupt | `interrupt_before=["tools"]` 在副作用发生**之前**暂停；审批放在进入副作用节点的边上，校验放在模型节点出口 |
| 8 | Streaming 三模式 | `stream_mode="updates"`（每个节点的增量）、`"messages"`（模型 token）、`"values"`（完整快照） |
| 9 | Time-travel | `get_state_history(config)` 取快照列表；用带旧 `checkpoint_id` 的 config 调用即从该点分叉，输入 `None` 表示原样重放 |
| 10 | `Send` 与子图 | `Send(node, state)` 动态并行派发 N 个执行，结果经 reducer 合并；已编译的图可以作为另一个图的节点（supervisor-worker） |

### 核心技能（能动手做到）

- [ ] 用 `StateGraph` 写出 ReAct 图：`State`、`agent_node`、`should_continue`、`ToolNode`、条件边与回边，并挂上 `MemorySaver`
- [ ] 解释并演示 reducer：分别在"无 reducer / `operator.add` / `add_messages`"下观察顺序与并行写入的结果
- [ ] 在 `tools` 前加 interrupt，读出待执行的 tool call，完成"批准继续"和"拒绝并告诉模型"两条路径
- [ ] 读懂 `get_state_history` 的输出（`next`、`source`、`step`），从任意快照分叉，并用**不带** `checkpoint_id` 的 config 继续最新分支
- [ ] 不依赖 API key，用假 LLM 替换模型对图做确定性测试
- [ ] 指出本节代码在新旧 LangGraph 版本下的不兼容点（`__interrupt__` 事件、静态断点的恢复方式）

---

## 二、基础自测（选择题）

**Q1.** `State` 中写成 `messages: Annotated[list[AnyMessage], add_messages]`。关于 `add_messages` 的作用，下列说法**最准确**的是：

- A. 把消息列表压缩后再写入 checkpoint
- B. 节点返回的新消息追加到旧列表末尾；若新消息的 id 与已有消息相同则替换那一条（也支持 `RemoveMessage` 删除）
- C. 把模型输出的 token 逐个推送给前端
- D. 与默认行为相同，新值覆盖旧值，只是多了类型检查

**Q2.** State 为 `class S(TypedDict): items: list`（**没有** reducer）。图为 `START → a → b → END`，`a` 返回 `{"items": ["from_a"]}`，`b` 返回 `{"items": ["from_b"]}`，以 `{"items": ["init"]}` 调用 `invoke`，结果是：

- A. `{"items": ["init", "from_a", "from_b"]}`
- B. 抛出 `InvalidUpdateError`
- C. `{"items": ["from_a"]}`
- D. `{"items": ["from_b"]}`

**Q3.** 同样没有 reducer，但图改为 `START → a`、`START → b`（`a`、`b` 在同一步**并行**执行），结果是：

- A. 抛出 `InvalidUpdateError`：同一步内同一个 key 只能接收一个值
- B. 后完成的节点静默覆盖先完成的节点
- C. 两个更新自动拼接成 `["init", "from_a", "from_b"]`
- D. 随机保留其中一个

**Q4.** 一个 agent 有 `issue_refund` 工具，要求人工审批后才能真正退款。interrupt 应该怎么放？

- A. `interrupt_after=["tools"]`，退款执行完后再让人确认
- B. 不需要 interrupt，在 system prompt 里写"退款前先询问用户"即可
- C. `interrupt_before=["tools"]`（或只对退款节点 `interrupt_before`），在副作用发生前暂停，审批通过再恢复
- D. `interrupt_before=["agent"]`，在模型思考前暂停

**Q5.** 本节的图（`interrupt_before=["tools"]`），用户问一个问题，模型调用一次工具后给出最终答案（中间批准一次）。这一轮结束后 `get_state_history(config)` 共有几个快照？

- A. 2 个
- B. 3 个
- C. 5 个
- D. 8 个

**Q6.** 想从 thread 的**最早**快照分叉、问一个新问题。正确的做法是：

- A. `earliest = list(app.get_state_history(config))[-1].config`，然后 `app.stream({"messages": [新问题]}, earliest)`
- B. `app.get_state_history(config)[0]` 是最早的快照
- C. 删掉 `MemorySaver` 再用同一个 `thread_id` 重新调用
- D. 调用 `app.reset(thread_id)` 后再 `invoke`

**Q7.** 关于 `stream_mode`，对应关系正确的是：

- A. `"values"` 推送模型 token；`"messages"` 推送完整快照
- B. `"updates"` 只在图结束时推送一次
- C. 三种模式输出完全相同，只是格式不同
- D. `"updates"` 推送 `{节点名: 该节点的增量}`；`"messages"` 推送模型节点内的 LLM token；`"values"` 推送每一步后的完整状态

**Q8.** 关于 checkpointer 的选择，下列说法正确的是：

- A. 生产环境用 `MemorySaver` 就够了，它会自动写盘
- B. `MemorySaver` 只适合测试；需要跨进程/重启恢复、跨请求 interrupt 的服务应使用 Postgres、SQLite 或 Redis 等持久化 checkpointer
- C. 不挂 checkpointer 也能使用 `interrupt_before` 和 time-travel
- D. checkpointer 只在出错时才写入快照

---

## 三、动手 / 代码题

**Q9.** 用假 LLM 替换 `ChatAnthropic` 运行 `main.py`（langgraph 1.2.14 与 0.2.50 结果相同），输出如下后程序崩溃：

```text
<<agent>>
    [AIMessage]  -> web_lookup({'query': 'anthropic headquarters'})
<<__interrupt__>>
Traceback (most recent call last):
  ...
    for m in update.get("messages", []):
             ^^^^^^^^^^
AttributeError: 'tuple' object has no attribute 'get'
```

相关代码：

```python
    for event in app.stream({"messages": [user]}, config, stream_mode="updates"):
        for node, update in event.items():
            print(f"<<{node}>>")
            for m in update.get("messages", []):
                print("   ", pretty(m))
```

1. 解释崩溃原因。
2. 给出最小修复。修复后这段代码一共有几处要改？

**Q10.** 修好 Q9 后继续运行，time-travel 部分输出如下：

```text
Time-travel: forking from earliest checkpoint and asking a math question.
<<agent>>
    [AIMessage]  -> calculator({'expression': '17 * 23'})
<<__interrupt__>>
<<agent>>
    [AIMessage]  -> web_lookup({'query': 'anthropic headquarters'})
<<__interrupt__>>
```

代码：

```python
        earliest = history[-1].config
        fork = {"messages": [HumanMessage("What is 17 * 23?")]}
        for event in app.stream(fork, earliest, stream_mode="updates"):
            ...
        # Resume past the interrupt for the math tool.
        for event in app.stream(Command(resume=True), earliest, stream_mode="updates"):
            ...
```

1. 为什么"批准计算器"之后，计算器没有执行，反而又冒出一次 `web_lookup`？
2. 怎样修改才能让计算器执行并得到 391？

**Q11.** 讲义 Step 3 演示了"批准"路径（`Command(resume=True)`），本节代码也用它恢复。

1. 实测发现：在 langgraph 1.2.14 中 `Command(resume=True)` 能越过 `interrupt_before` 的静态断点；但在代码注释要求的最低版本 0.2.50 中，它只会再次触发 `__interrupt__`，工具从不执行。哪种恢复写法在两个版本中都可用？
2. 写出"人工**拒绝**"路径：不执行工具，但让模型知道被拒绝了，并继续生成回复。

**Q12.** `calculator` 工具的实现：

```python
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "ERROR: only digits and + - * / ( ) are allowed"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
```

1. 这个白名单能挡住 `__import__('os')` 吗？它还有什么漏洞？
2. 用 `ast` 写一个只支持 `+ - * /`、括号和数字的安全求值函数。

---

## 四、面试高频题

**Q13.**（基础必考）为什么要把 agent 从 `while True` 循环改写成显式的状态图？显式图带来了哪些能力？代价是什么？

**Q14.**（原理深挖）LangGraph 的 reducer 是什么？`add_messages` 和 `operator.add` 有什么区别？并行分支（包括 `Send`）的结果是怎么合并的？

**Q15.**（工程实践）你要上线一个"退款客服 agent"：退款金额 > 100 美元需人工审批，服务可能随时重启。请说明 interrupt 放在哪、checkpointer 怎么选、`thread_id` 怎么设计，以及恢复执行时要注意什么。

**Q16.**（场景设计）设计一个"研究 → 写作 → 审稿"的多 agent 系统：研究阶段要并行查三个来源，写作前需要人工批准研究摘要。用 LangGraph 的概念画出你的图。

**Q17.**（追问型）time-travel 分叉时，分叉点之后的节点会重新执行吗？如果其中有真实的副作用（发邮件、扣款）会怎样？如何安全地用 time-travel 做回归测试？

---

## 五、参考答案与解析

### Q1 — 答案：B

实测（`langgraph.graph.message.add_messages`）：已有 `[Human(id=1), AI("v1", id=2)]`，合并 `[AI("v2", id=2)]` 后得到 `[Human(1), AI("v2", 2)]`——同 id 被**替换**而不是追加；合并 `RemoveMessage(id="1")` 后只剩 id=2 那条；合并一个 `{"role": "user", ...}` 字典会被转成 `HumanMessage`。这正是它比 `operator.add`（纯拼接，同 id 会重复出现）更适合消息列表的原因。A、C 与 reducer 无关（C 是 `stream_mode="messages"`）；D 描述的是没有 reducer 的默认行为。

### Q2 — 答案：D

无 reducer 的字段是"最后一次写入为准"（实测输出 `{'items': ['from_b']}`）。`a` 先把 `["init"]` 覆盖成 `["from_a"]`，`b` 再覆盖成 `["from_b"]`，没有任何报错——这就是讲义所说的"静默丢失"。A 是加了 `operator.add` 的结果；B 只在并行写入时出现（Q3）；C 是中间状态。

### Q3 — 答案：A

实测：`InvalidUpdateError: At key 'items': Can receive only one value per step. Use an Annotated key to handle multiple values.`（1.2.14 与 0.2.50 一致）。讲义写"If two nodes both update `messages` and you forgot the reducer, the second wins silently"，这只对**顺序**执行成立；**并行**执行时 LangGraph 会直接报错。加上 `Annotated[list, operator.add]` 后结果为 `['init', 'from_a', 'from_b']`（C 是有 reducer 时的行为）。B、D 都不是 LangGraph 的行为。

### Q4 — 答案：C

讲义："Decide interrupts before tools run, not after. Approvals go on the edge into a side-effecting node so you can cancel before harm"；skill 文件也要求"Refuse to ship one that interrupts *after* the side effect"。A 的问题是退款已经发生；B 把安全寄托在模型自觉上，不可靠；D 拦在模型之前，审批人看不到模型想调什么工具。

### Q5 — 答案：C

实测历史（从新到旧）：

| # | 最后一条消息 | `next` | `metadata.source / step` |
|---|------------|--------|------------------------|
| 0 | AIMessage（最终回答） | `()` | loop / 3 |
| 1 | ToolMessage | `('agent',)` | loop / 2 |
| 2 | AIMessage（含 tool_calls） | `('tools',)` | loop / 1 ← interrupt 停在这里 |
| 3 | HumanMessage | `('agent',)` | loop / 0 |
| 4 | （空） | `('__start__',)` | input / -1 |

每个 super-step 结束时写一个快照，再加上最初的输入快照，共 5 个。讲义练习 1 要求"两轮对话至少 4 个快照"。

### Q6 — 答案：A

`get_state_history` 返回的是**从新到旧**的迭代器，最早的在列表最后，所以要 `list(...)[-1]`（B 错，而且它返回的是迭代器，不能直接下标）。这个 `config` 里带有 `checkpoint_id`，用它调用就从该点分叉。C、D 不是 LangGraph 的 API。注意：分叉之后要继续最新分支，应改用**不带** `checkpoint_id` 的 thread config（见 Q10）。

### Q7 — 答案：D

讲义 Streaming 一节：`updates` 产出状态增量，`messages` 产出模型节点内的 LLM token，`values` 产出完整快照；讲义建议 UI 用 `updates`、评测用 `values`。实际 API 参数名是 `stream_mode=`（讲义概念部分写的 `graph.stream(state, mode="updates")` 参数名不对，Build It 部分的 `stream_mode=` 才是正确写法）。

### Q8 — 答案：B

讲义："`MemorySaver` is for tests. Anything that persists across restarts wants a real store"、"Refuse to ship a LangGraph agent that has no checkpointer"。interrupt 需要把暂停时的状态保存下来、等下一个请求再恢复；进程重启或请求被路由到另一台实例时，内存里的状态就没了。C 错：没有 checkpointer 就没有 resume、interrupt 和 time-travel。D 错：每个 super-step 都会写。

### Q9 — 参考答案

1. 图在 `interrupt_before=["tools"]` 处暂停时，`stream_mode="updates"` 会额外产出一个事件 `{"__interrupt__": ()}`。它的值是**元组**而不是 dict，于是 `update.get(...)` 抛出 `AttributeError`。代码作者假设每个事件都是"节点名 → 状态增量 dict"，但 `__interrupt__` 不是节点。实测在代码注释要求的最低版本 0.2.50 和当前的 1.2.14 中都会出现，所以即便填上 API key，`main.py` 也会在第一次暂停时崩溃（前提是模型确实调用了工具——对这个问题它几乎一定会调用）。
2. 最小修复：跳过非 dict 的更新。

```python
for event in app.stream(..., stream_mode="updates"):
    for node, update in event.items():
        print(f"<<{node}>>")
        if not isinstance(update, dict):      # 例如 {"__interrupt__": ()}
            continue
        for m in update.get("messages", []):
            print("   ", pretty(m))
```

`run()` 里有 **4 处**完全相同的打印循环（首轮、批准恢复、分叉、分叉后恢复），都要改。更好的做法是抽成一个 `print_events(stream)` 辅助函数，消除重复代码。

### Q10 — 参考答案

1. `earliest` 是一个**固定指向最早快照**的 config（包含 `checkpoint_id`）。第一次 `stream(fork, earliest)` 从最早快照分叉，生成了新分支并停在计算器之前——这一步是对的。但第二次 `stream(Command(resume=True), earliest)` 仍然指向**最早快照**而不是新分支的末端；最早快照是 `source=input` 的输入快照，它保存的待处理输入是原来那句"Where is Anthropic headquartered?"，于是图从头又跑了一遍原始问题，模型再次调用 `web_lookup`，又停在 interrupt。计算器分支从未被恢复。
2. 分叉之后用**只含 `thread_id`** 的 config 继续，LangGraph 会自动找到该 thread 最新的快照（也就是新分支的末端）：

```python
for event in app.stream(Command(resume=True), config, stream_mode="updates"):   # 用 config，不用 earliest
    ...
```

实测输出：`<<tools>> [ToolMessage] 391`、`<<agent>> ... 391`；最终该 thread 的历史有 10 个快照，两条分支共享同一个输入快照作为根。也可以保存第一次分叉后 `app.get_state(config).config` 的返回值作为后续调用的 config。

### Q11 — 参考答案

1. 用 `None` 作为输入：`app.stream(None, config)` / `app.invoke(None, config)`。它的含义是"没有新输入，从当前快照继续"，对 `interrupt_before` 这类**静态断点**在两个版本中都有效（实测两个版本都得到最终回答）。`Command(resume=...)` 原本是为节点内部调用 `interrupt()` 的**动态中断**设计的，用来把审批值传回 `interrupt()` 的返回值；新版本才让它也能越过静态断点。代码注释写 `langgraph>=0.2.50`，因此应改用 `None`，或把版本下限提高并注明。
2. 拒绝路径（实测可用）：以 `tools` 节点的身份写入"被拒绝"的 ToolMessage，再继续：

```python
from langchain_core.messages import ToolMessage

state = app.get_state(config)
calls = state.values["messages"][-1].tool_calls
app.update_state(
    config,
    {"messages": [ToolMessage(content="Rejected by human reviewer.", tool_call_id=c["id"]) for c in calls]},
    as_node="tools",               # 假装 tools 节点已执行，下一步按 tools → agent 的边走
)
print(app.get_state(config).next)   # ('agent',)
app.invoke(None, config)            # 模型读到拒绝结果，自己组织回复
```

要点：每个 `tool_call_id` 都要有对应的 ToolMessage，否则多数模型 API 会因为"tool_use 没有对应 tool_result"而报错。讲义 Step 3 的拒绝写法 `update_state(config, {"messages": [AIMessage("Blocked by human reviewer.")]})` 没有给出 `as_node`，也没有为待处理的 tool call 补上结果，消息序列里会留下一个"悬空"的 tool_use，实际接入真实 API 时容易出错。

### Q12 — 参考答案

1. 能挡住 `__import__('os')`（实测返回 `ERROR: only digits and + - * / ( ) are allowed`），加上 `{"__builtins__": {}}` 双保险。漏洞在于白名单字符可以组合出 `**`（幂运算）：`2**10` 实测返回 `1024`，而 `9**9**9` 等于 9 的 387,420,489 次方，约 3.7 亿位十进制数（按位数估算，未实际执行），会长时间占满 CPU 和内存——模型或被注入的用户输入可以借此拖垮服务。另外 `1/0` 会被捕获并返回 `ERROR: ZeroDivisionError(...)`，这一点处理得不错。
2. 基于 `ast` 的安全求值（已运行验证）：

```python
import ast, operator as op

OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
       ast.USub: op.neg, ast.UAdd: op.pos}

def safe_eval(expr: str) -> float:
    if len(expr) > 200:
        raise ValueError("too long")
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.operand))
        raise ValueError("unsupported expression")
    return ev(ast.parse(expr, mode="eval"))
```

验证：`"2 + 2 * 3" → 8`，`"17 * 23" → 391`，`"(1+2)/4" → 0.75`，`"9**9**9" → ValueError`（`Pow` 不在白名单），`"1/0" → ZeroDivisionError`（交给外层 `try` 转成错误字符串）。

### Q13 — 参考回答要点

- **问题**：`while True` 循环没有钩子——不能暂停等人审批、不能在崩溃后恢复、不能回到某一步换个分支重试，出了问题只能看到"成功/失败"（讲义："the agent becomes a black box"）。
- **显式图的四种能力**：
  - checkpointing：每一步状态落盘，可恢复；
  - interrupts：在节点边界暂停，等人审批后继续；
  - streaming：按节点推送增量或 token，UI 可显示"正在调用 search_web…"；
  - time-travel：从历史任意快照分叉，复现和调试坏的运行。
- **代价**：多了一层抽象和依赖（框架版本变化会带来不兼容，本节代码就碰到了）；状态必须可序列化；要学 reducer 等概念；简单的单步任务不值得上图。
- 加分点：agent 本身没变，变的是 harness（讲义开篇："The agent hasn't changed. The harness around it has."）；先做 60 秒设计：列节点、定状态、画边、选 checkpointer、定 interrupt 位置。

### Q14 — 参考回答要点

- **reducer**：每个状态字段一个合并函数 `(old, new) -> merged`，节点只返回"部分更新"，由 reducer 决定怎么合并进全局状态。默认是覆盖。
- **`operator.add`**：纯列表拼接，适合"只追加、不去重"的字段（如 `retrieved_docs`）。
- **`add_messages`**：追加 + 按消息 id 更新/删除；能把 dict 形式的消息转换成消息对象。这让"修改某条已有消息"（如人工编辑模型的 tool call）和"删除旧消息做压缩"成为可能。
- **并行合并**：同一 super-step 中多个节点（或多个 `Send` 派发的执行）写同一字段时，reducer 把它们依次合并；没有 reducer 时直接报 `InvalidUpdateError`（实测），所以并行写入的字段**必须**有 reducer。
- 加分点：讲义建议把 `plan`、`budget`、`retrieved_docs` 等字段从 `messages` 中提出来作为顶层字段，各配合适的 reducer；常见误区：以为并行时"后写赢"。

### Q15 — 参考回答要点

- **节点与 interrupt**：`agent`、`lookup_order`、`issue_refund`、`send_email`、`human_review`；在 `issue_refund` 之前暂停（`interrupt_before`，或在节点内用条件判断金额 > 100 时调用 `interrupt()`）；查询类工具不需要审批。
- **checkpointer**：`PostgresSaver`（或 SQLite/Redis），确保重启后能从暂停点恢复；`MemorySaver` 只用于测试。
- **thread_id**：按业务实体设计，如 `user:{user_id}:case:{case_id}`（skill 文件示例），并设定 checkpoint 保留期限。
- **恢复时注意**：
  - 恢复后节点会从头执行，退款工具必须**幂等**（用订单号 + 金额作为幂等键），防止重启或重复审批导致重复退款；
  - 审批结果写入状态（如 `reviewer_decision` 字段）以便审计；
  - 拒绝时要给模型补上对应的 tool result（Q11）；
  - 注意框架版本的恢复 API 差异（`None` vs `Command(resume=...)`）。
- 加分点：审批请求要带上模型提议的完整参数（金额、订单号），审批人可以修改参数后再放行（`update_state` 修改最后一条 AI 消息的 tool_calls）。

### Q16 — 参考回答要点

- **外层 supervisor 图**：`plan` → 用 `Send` 向 `researcher` 子图派发 3 个并行任务（每个来源一个）→ 结果通过 `Annotated[list, operator.add]` 的 `findings` 字段合并 → `summarize` 生成研究摘要 → **`interrupt_before=["writer"]`** 等人工批准 → `writer` 子图 → `reviewer` 子图 → 条件边：通过则 `END`，不通过则回到 `writer`（设最大轮数）。
- **子图**：`researcher`、`writer`、`reviewer` 各自是已编译的图，有自己的状态；外层只看到一个节点（讲义："the outer graph sees a single node"）。
- **状态设计**：`messages`（`add_messages`）、`plan`（覆盖）、`findings`（`operator.add`）、`draft`（覆盖）、`review_round`（计数）。
- **持久化**：Postgres checkpointer；人工批准可以跨天。
- 加分点：讲义练习 3 要求验证"从旧快照 time-travel 只重跑分叉的分支"；给 reviewer 循环加上限，避免无限打回。

### Q17 — 参考回答要点

- **会重新执行**：从某个快照分叉后，该快照之后的节点会真正重新运行（本节实测：从最早快照分叉后 `agent` 节点被重新调用）。LangGraph 只保存状态，不会"录制并回放"节点里的外部调用。
- **副作用风险**：如果分叉后的路径包含发邮件、扣款等工具，它们会再执行一次。
- **安全做法**：
  - 回归测试时把有副作用的工具替换成 mock（本节就是用假 LLM 和玩具工具做的确定性测试）；
  - 在有副作用的节点前保留 `interrupt_before`，分叉重放也会停下来等人确认；
  - 工具实现幂等；
  - 用生产 trace 的状态快照作为测试输入，断言新版本的路由/输出。
- 加分点：分叉后继续执行要用不带 `checkpoint_id` 的 thread config，否则会回到旧点（Q10 的 bug）；`invoke(None, old_config)` 是"原样重放"，`invoke(value, old_config)` 是"在旧状态上追加输入后继续"。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：`agent` 节点产生的 tool_calls 与 `ToolNode` 的执行都建立在 function calling 之上。
- [阶段 11 · 14 Model Context Protocol (MCP)](../../14-model-context-protocol/docs/zh.md)：外部工具可以通过 MCP 适配器接入 `ToolNode`。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：本节要"图化"的正是这个循环。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../15-prompt-caching/docs/zh.md)：ReAct 每一步都重发完整消息历史，配合 prompt caching 降成本。

### 本节被哪些后续内容用到
- [阶段 11 · 17 Agent 框架权衡——图、角色与 Actor Orchestration](../../17-agent-framework-tradeoffs/docs/zh.md)：何时选 LangGraph、何时选 CrewAI / AutoGen 等。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：对 durable execution 的深入展开。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md)：chain、router、orchestrator-workers 等图形状的选择。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../../14-agent-engineering/28-orchestration-patterns/docs/zh.md)：supervisor-worker 子图结构。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：自主系统中的检查点与回滚。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：跨重启的持久执行。

### 延伸关键词
`StateGraph` · `reducer` · `add_messages` · `operator.add` · `MemorySaver / PostgresSaver` · `thread_id / checkpoint_id` · `interrupt_before / interrupt_after` · `interrupt()` · `Command(resume=...)` · `update_state(as_node=...)` · `get_state_history` · `Send` · `subgraph` · `InvalidUpdateError` · `idempotency`
