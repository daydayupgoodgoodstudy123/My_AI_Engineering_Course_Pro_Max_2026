# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 16 节 Agent State Machines——图、节点与 Checkpoints ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`export ANTHROPIC_API_KEY=...; python main.py`（可用环境变量 `LLM_MODEL` 指定模型，默认 `claude-sonnet-4-5`） ｜ **依赖**：第三方 `langgraph>=0.2.50`、`langchain-anthropic>=0.3.0`（会连带安装 `langchain-core`、`anthropic`、`pydantic` 等）；需要网络与 Anthropic API key

---

## 1. 这份代码在考察什么

讲义的核心论点是"agent 本来就是状态机，把它画成显式的图，harness 就免费获得 checkpoint、interrupt、streaming、time-travel"。`main.py` 用不到 100 行有效代码把这四件事串成一个演示：

1. **State + reducer**：`messages` 字段用 `add_messages` 作为 reducer，保证每个节点的输出是"追加"而不是"覆盖"。
2. **ReAct 图**：`agent` 节点（调用 LLM）+ `tools` 节点（`ToolNode` 执行工具）+ 条件边（有 tool_calls 去 `tools`，否则 `END`）+ 回边（`tools` → `agent`）。
3. **Checkpointer + interrupt**：`MemorySaver` + `interrupt_before=["tools"]`，在任何工具执行前暂停，打印待执行的 tool call，再"批准"恢复。
4. **Streaming**：全部用 `stream_mode="updates"`，逐节点打印增量。
5. **Time-travel**：打印 checkpoint 历史，再从最早的快照分叉问一个数学题。

> 一句话：**agent 的"脑子"没变，变的是包着它的运行时**——暂停、恢复、回放都由图运行时提供。但这份代码在真实运行时有两处会出错（`__interrupt__` 事件导致崩溃、time-travel 恢复时用错了 config），读懂它们比读懂正常路径更能理解 LangGraph 的执行模型。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `State` | `TypedDict` | 唯一字段 `messages`，reducer 为 `add_messages` | State + reducer |
| `calculator` | `@tool` 函数 | 白名单字符 + 受限 `eval` 计算算术式 | 工具（无副作用） |
| `web_lookup` | `@tool` 函数 | 查一个两条记录的字典，假装是搜索 | 工具（检索替身） |
| `TOOLS` | 列表 | 绑定给模型、交给 `ToolNode` | 工具注册 |
| `build_app` | 函数 | 建 LLM、定义两个节点和 router、连边、编译 | StateGraph 构建与 compile |
| `agent_node`（内部函数） | 闭包 | `llm.invoke(messages)` → `{"messages": [response]}` | 模型节点 |
| `should_continue`（内部函数） | 闭包 | 最后一条消息有 tool_calls → `"tools"`，否则 `END` | 条件边的 router |
| `pretty` | 函数 | 把一条消息格式化成一行字符串 | 输出展示 |
| `run` | 函数 | 首轮流式运行 → 暂停检查 → 批准恢复 → 打印历史 → 分叉 | 驱动脚本 |

数据流：`HumanMessage` → `app.stream`（`agent` 产出带 tool_calls 的 AIMessage）→ 在 `tools` 前暂停 → `get_state` 读待执行调用 → `Command(resume=True)` 恢复（`tools` 产出 ToolMessage → `agent` 产出最终回答）→ `get_state_history` → 用最早快照的 config 分叉。

---

## 3. 逐段精讲

### 3.1 State：一个字段，一个 reducer

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

- `TypedDict` 只是给字典加上字段类型提示；LangGraph 读取它来知道有哪些"通道"（channel）。
- `Annotated[类型, 元数据]` 是标准库语法：第二个参数 `add_messages` 对 Python 没有意义，但 LangGraph 会把它当成这个字段的 reducer。
- `add_messages` 的语义（已实测）：
  - 新消息追加到末尾；
  - 新消息的 `id` 与已有消息相同 → **替换**那一条；
  - `RemoveMessage(id=...)` → 删除；
  - `{"role": "user", "content": ...}` 字典 → 自动转成 `HumanMessage`。
- 如果去掉 reducer（写成 `messages: list`）：`agent` 返回 `{"messages": [response]}` 会把整段历史覆盖成只剩这一条，下一步模型就看不到用户问题了。讲义："Forgetting it is the most common LangGraph bug."

### 3.2 两个玩具工具

```python
@tool
def calculator(expression: str) -> str:
    """Evaluate a Python arithmetic expression like '2 + 2 * 3'. Returns the
    result as a string."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "ERROR: only digits and + - * / ( ) are allowed"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:
        return f"ERROR: {exc!r}"
```

- `@tool`（来自 `langchain_core.tools`）把普通函数包装成 `StructuredTool`：函数名成为工具名，**docstring 成为工具描述**，类型注解生成参数 schema（实测 `calculator.args == {'expression': {'title': 'Expression', 'type': 'string'}}`）。模型就是靠这段描述决定何时调用它，所以 docstring 不是注释，而是 prompt 的一部分。
- 安全措施有两层：字符白名单（`set(expression) <= allowed` 判断子集）+ `eval` 时清空 `__builtins__`。实测 `__import__('os')` 被白名单挡下。
- ⚠️ 漏洞：`*` 在白名单里，`**`（幂运算）就能通过。`2**10` 实测返回 `1024`；`9**9**9` 是一个约 3.7 亿位的整数，会长时间占满 CPU 和内存。用 `ast` 只放行 `+ - * /` 节点才是可靠做法（测验 Q12 给出实现）。
- 错误不抛出而是**返回字符串** `"ERROR: ..."`：工具失败变成一条 ToolMessage 回到模型，模型可以自己纠正。实测 `1/0` 返回 `ERROR: ZeroDivisionError('division by zero')`。

```python
@tool
def web_lookup(query: str) -> str:
    facts = {
        "anthropic headquarters": "Anthropic is headquartered in San Francisco, California.",
        "python release year": "Python was first released in 1991.",
    }
    return facts.get(query.strip().lower(), "unknown")
```

- 只做了 `strip().lower()` 归一化，必须**完全匹配**键。实测 `"Anthropic Headquarters "` 能命中，`"Anthropic headquarters location"` 返回 `unknown`。真实模型生成的查询词千变万化，演示时很可能拿到 `unknown`——这是"假工具"的局限，不是图的问题。

### 3.3 `build_app`：连线与编译

```python
def build_app() -> tuple:
    llm = ChatAnthropic(model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5"), temperature=0).bind_tools(TOOLS)

    def agent_node(state: State) -> dict:
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: State) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END
```

- `bind_tools(TOOLS)` 把工具 schema 附在每次请求上，返回的仍是一个可 `invoke` 的模型对象；模型的回复是 `AIMessage`，若要调工具，`tool_calls` 字段是 `[{"name", "args", "id"}, ...]`。
- `temperature=0`：让演示尽量确定。
- `agent_node` 只返回**部分更新** `{"messages": [response]}`，由 `add_messages` 追加到历史。
- `should_continue` 是条件边的 router：用 `getattr(last, "tool_calls", None)` 安全地读属性（HumanMessage、ToolMessage 没有这个字段也不会报错），空列表和 `None` 都为假。
- `agent_node` 和 `should_continue` 定义在 `build_app` 内部，是**闭包**：它们捕获了外层的 `llm` 变量，因此不需要全局变量。

```python
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    app = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["tools"],
    )
    return app, llm
```

- `ToolNode`（预置节点）读取最后一条 AIMessage 的 `tool_calls`，逐个执行对应工具，为每个调用返回一条带 `tool_call_id` 的 `ToolMessage`。
- `set_entry_point("agent")` 等价于新写法 `add_edge(START, "agent")`。
- `add_conditional_edges` 的第三个参数是"router 返回值 → 目标节点"的映射，便于画图和校验。
- 最终的拓扑是 **2 个节点 + 1 条条件边 + 1 条静态边**。讲义和文件注释都称之为"four-node"图（讲义："A production ReAct agent is four nodes and two edges"，但随后列出的是 2 个节点和 2 条边），说法不严谨。
- `compile` 绑定拓扑，挂上 `MemorySaver`，并声明在 `tools` 节点执行前中断。每个 super-step 结束时写一个快照。
- 返回值注解为 `tuple`，第二个元素 `llm` 在 `run()` 里没有被使用（`app, _llm = build_app()`）。

### 3.4 `pretty`：消息的一行展示

```python
def pretty(msg: AnyMessage) -> str:
    kind = msg.__class__.__name__
    content = msg.content if isinstance(msg.content, str) else str(msg.content)[:200]
    tool_calls = getattr(msg, "tool_calls", None) or []
    tcs = " | ".join(f"{t['name']}({t['args']})" for t in tool_calls)
    return f"[{kind}] {content} {('-> ' + tcs) if tcs else ''}".strip()
```

- Anthropic 模型带工具调用时，`AIMessage.content` 往往是**内容块列表**（text 块 + tool_use 块），所以这里非字符串时转成 `str` 并截断到 200 字符。
- `x or []`：`tool_calls` 为 `None` 时退化成空列表，后面的生成器表达式就不用判空。

### 3.5 `run()` 第一段：流式运行到 interrupt

```python
    config = {"configurable": {"thread_id": "demo-42"}}

    user = HumanMessage("Where is Anthropic headquartered?")
    for event in app.stream({"messages": [user]}, config, stream_mode="updates"):
        for node, update in event.items():
            print(f"<<{node}>>")
            for m in update.get("messages", []):
                print("   ", pretty(m))
```

- `config["configurable"]["thread_id"]` 决定这次对话的所有快照归属哪个 thread。
- `stream_mode="updates"` 每次产出 `{节点名: 该节点返回的增量}`。
- ⚠️ **崩溃点**：图在 `tools` 前暂停时，stream 会额外产出 `{"__interrupt__": ()}`，它的值是元组，`update.get` 抛 `AttributeError: 'tuple' object has no attribute 'get'`。实测在 langgraph 0.2.50（代码要求的下限）和 1.2.14 中都如此，所以**即使有 API key，脚本也会在第一次暂停时崩溃**。修复：`if not isinstance(update, dict): continue`。`run()` 中有 4 段相同的循环，都要改（测验 Q9）。

### 3.6 第二段：读取待执行调用，批准恢复

```python
    pending = app.get_state(config)
    print("\nPAUSED. Pending tool calls:")
    for m in pending.values["messages"][-1:]:
        for tc in getattr(m, "tool_calls", []) or []:
            print(f"  - {tc['name']}({tc['args']})")

    for event in app.stream(Command(resume=True), config, stream_mode="updates"):
        ...
```

- `app.get_state(config)` 返回 `StateSnapshot`：`.values` 是状态字典，`.next` 是下一个要执行的节点（此时为 `('tools',)`），`.config` 带当前 `checkpoint_id`。
- `[-1:]` 用切片取"最后一条消息组成的列表"，列表为空也不会报错。
- 这里就是人工审批的位置：真实系统会把 `tc['name']` 和 `tc['args']` 发给审批人，而不是直接放行。
- ⚠️ **版本差异**：`Command(resume=...)` 原本用于恢复节点内部调用 `interrupt()` 的动态中断。实测在 langgraph 1.2.14 中它也能越过 `interrupt_before` 静态断点；但在 0.2.50 中它只会再次产出 `__interrupt__`，工具从不执行。两个版本都可用的写法是 `app.stream(None, config, ...)`——输入 `None` 表示"无新输入，从当前快照继续"。
- 拒绝路径（代码未演示）：`update_state(config, {"messages": [ToolMessage("Rejected...", tool_call_id=...)]}, as_node="tools")` 后再 `invoke(None, config)`，详见测验 Q11。

### 3.7 第三段：打印 checkpoint 历史

```python
    history = list(app.get_state_history(config))
    print(f"\nCheckpoint history: {len(history)} snapshots")
    for i, snap in enumerate(history):
        last = snap.values["messages"][-1] if snap.values.get("messages") else None
        tag = last.__class__.__name__ if last else "?"
        print(f"  {i:>2}  {tag:<15}  next={snap.next}")
```

- `get_state_history` 返回**从新到旧**的快照迭代器，用 `list()` 物化。
- 最早的输入快照里 `messages` 为空，`snap.values.get("messages")` 为假时打印 `?`。这一点比讲义 Step 4 的示例稳健：讲义直接写 `snapshot.values["messages"][-1].content[:80]`，实测会在空的输入快照上抛 `IndexError`。

### 3.8 第四段：time-travel 分叉

```python
    if len(history) >= 3:
        earliest = history[-1].config
        fork = {"messages": [HumanMessage("What is 17 * 23?")]}
        for event in app.stream(fork, earliest, stream_mode="updates"):
            ...
        for event in app.stream(Command(resume=True), earliest, stream_mode="updates"):
            ...
```

- `history[-1]` 是最早的快照（`source=input, step=-1`，状态为空）。它的 `config` 里带着 `checkpoint_id`，以它为起点 stream 一个新输入，就创建了一条**新分支**：新分支只有数学问题，没有之前的 Anthropic 对话。
- ⚠️ **逻辑错误**：第二个 `stream` 仍然传 `earliest`，即再次指向最早快照，而不是新分支的末端。实测结果：图从最早快照重新执行了**原始输入**（"Where is Anthropic headquartered?"），又调用了一次 `web_lookup` 并再次暂停，计算器从未执行。修复：恢复时用只含 `thread_id` 的 `config`，LangGraph 会自动取该 thread 最新的快照。修复后实测得到 `[ToolMessage] 391`，整个 thread 共 10 个快照、两条分支共享同一个根（测验 Q10）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 LangGraph 而非手写 `while True` | 免费获得 checkpoint、interrupt、streaming、time-travel | 引入框架依赖与版本漂移（本代码在新旧版本都踩到坑）；简单任务不值得 |
| 只有 `messages` 一个字段 | 最小可运行的 ReAct 状态 | 讲义建议把 `plan`、`budget`、`retrieved_docs` 等提升为顶层字段并各配 reducer |
| `MemorySaver` | 零配置、适合演示 | 进程退出即丢失；生产用 `PostgresSaver`/SQLite/Redis |
| 对**所有**工具 `interrupt_before` | 演示简单、绝对安全 | 只读工具也要人工批准，体验差；生产只对有副作用的节点中断，或在节点内按条件调用 `interrupt()` |
| `Command(resume=True)` 恢复静态断点 | 与讲义写法一致 | 旧版本无效；`None` 输入在两个版本都可用 |
| 玩具工具 + 硬编码事实 | 无外部依赖 | 查询词必须精确匹配；生产接真实检索 |
| 白名单 + `eval` | 实现短 | `**` 可造成资源耗尽；应用 `ast` 白名单 |
| 依赖真实 Claude | 展示真实 tool calling | 没有 key 无法运行、结果不确定；测试应注入假 LLM（见第 6 节） |
| 四段重复的打印循环 | 线性脚本易读 | 一个 bug 要改四处；应抽成 `print_events()` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可使用较新的类型语法 |
| `TypedDict` | `class State(TypedDict): messages: ...` | 带字段类型的字典"形状"声明，运行时仍是普通 dict |
| `Annotated` | `Annotated[list[AnyMessage], add_messages]` | 给类型附加元数据；LangGraph 从中读出 reducer |
| 装饰器 | `@tool` | 把函数替换成包装后的对象（这里是 `StructuredTool`），调用方式变为 `.invoke({...})` |
| docstring | 工具函数下的三引号字符串 | 被 `@tool` 读取为工具描述，直接影响模型行为 |
| 集合运算 | `set(expression) <= allowed` | `<=` 判断子集 |
| 受限 `eval` | `eval(expression, {"__builtins__": {}}, {})` | 第 2、3 个参数是全局/局部命名空间；清空 builtins 仍不等于安全 |
| `try / except Exception as exc` | 计算器里 | 捕获错误并转成字符串返回 |
| f-string 的 `!r` | `f"ERROR: {exc!r}"` | 用 `repr()` 展示对象，得到 `ZeroDivisionError('division by zero')` |
| `dict.get(key, default)` | `facts.get(..., "unknown")`、`os.environ.get("LLM_MODEL", ...)` | 键不存在时给默认值 |
| 方法链 | `query.strip().lower()`、`ChatAnthropic(...).bind_tools(TOOLS)` | 前一个调用的返回值继续调用方法 |
| 闭包 | `build_app` 内定义的 `agent_node` 使用外层 `llm` | 内部函数记住外层变量 |
| 条件表达式 | `"tools" if getattr(...) else END` | 一行 if/else |
| `getattr(obj, name, default)` | `getattr(last, "tool_calls", None)` | 属性不存在时返回默认值，不抛异常 |
| `or` 提供默认值 | `getattr(msg, "tool_calls", None) or []` | 左边为假（`None`、空列表）时取右边 |
| 生成器表达式 + `join` | `" | ".join(f"..." for t in tool_calls)` | 拼接字符串 |
| `isinstance` | `isinstance(msg.content, str)` | 类型判断（修复 Q9 也靠它） |
| `__class__.__name__` | `msg.__class__.__name__` | 取对象的类名，如 `AIMessage` |
| 元组解包与"丢弃"变量 | `app, _llm = build_app()` | 前缀下划线表示有意不用 |
| 嵌套 dict 配置 | `{"configurable": {"thread_id": "demo-42"}}` | LangGraph 约定的运行时配置格式 |
| 切片取尾 | `pending.values["messages"][-1:]`、`history[-1]` | `[-1:]` 得到列表，`[-1]` 得到元素 |
| `dict.items()` 双重循环 | `for node, update in event.items()` | 遍历键值对 |
| f-string 对齐 | `{i:>2}`、`{tag:<15}` | 右对齐宽 2、左对齐宽 15 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行（第 6 节的测试脚本就是 import 后替换 `ChatAnthropic` 再调用 `run()`） |

---

## 6. 运行结果解读

**未能用真实 Claude 运行**，原因：环境中没有 `ANTHROPIC_API_KEY`。直接运行的结果：

- 未安装依赖时：`ModuleNotFoundError: No module named 'langchain_anthropic'`；
- 安装 `langgraph`（1.2.14）和 `langchain-anthropic` 后：`TypeError: Anthropic authentication failed: no API key ...`，发生在 `agent` 节点第一次调用模型时。

为了观察图运行时的真实行为，我们在测试脚本中 `import main`，把 `main.ChatAnthropic` 替换成一个假 LLM：问题里有 "anthropic" 就返回 `web_lookup` 调用、有 "17" 就返回 `calculator` 调用、收到 ToolMessage 就回复 `"Answer based on tool: ..."`。图、`ToolNode`、`MemorySaver`、interrupt、history 全部是 LangGraph 的真实实现。

**原样运行（假 LLM，langgraph 1.2.14；0.2.50 结果相同）**：

```text
<<agent>>
    [AIMessage]  -> web_lookup({'query': 'anthropic headquarters'})
<<__interrupt__>>
Traceback (most recent call last):
  ...
AttributeError: 'tuple' object has no attribute 'get'
```

第一个节点正常，暂停时的 `__interrupt__` 事件让脚本崩溃（第 3.5 节）。

**只修复 `isinstance(update, dict)` 后的完整输出（langgraph 1.2.14）**：

```text
<<agent>>
    [AIMessage]  -> web_lookup({'query': 'anthropic headquarters'})
<<__interrupt__>>

PAUSED. Pending tool calls:
  - web_lookup({'query': 'anthropic headquarters'})
<<tools>>
    [ToolMessage] Anthropic is headquartered in San Francisco, California.
<<agent>>
    [AIMessage] Answer based on tool: Anthropic is headquartered in San Francisco, California.

Checkpoint history: 5 snapshots
   0  AIMessage        next=()
   1  ToolMessage      next=('agent',)
   2  AIMessage        next=('tools',)
   3  HumanMessage     next=('agent',)
   4  ?                next=('__start__',)

Time-travel: forking from earliest checkpoint and asking a math question.
<<agent>>
    [AIMessage]  -> calculator({'expression': '17 * 23'})
<<__interrupt__>>
<<agent>>
    [AIMessage]  -> web_lookup({'query': 'anthropic headquarters'})
<<__interrupt__>>
```

逐项解读：

- **暂停与批准**：`agent` 产出带 tool_calls 的 AIMessage 后，图在 `tools` 前停下；`get_state` 读出待执行调用；`Command(resume=True)` 恢复后 `tools` 产出 ToolMessage，`agent` 产出最终回答。
- **5 个快照**（从新到旧）：#4 是输入快照（`next=('__start__',)`，状态为空，打印 `?`）；#3 写入了用户消息、下一步 `agent`；#2 是暂停点（下一步 `tools`）；#1 工具结果已写入、下一步 `agent`；#0 是终态（`next=()`）。
- **分叉的前半段正确**：从最早快照带新输入运行，新分支只含数学问题，模型调用 `calculator` 并暂停。
- **分叉的后半段错误**：恢复时又传了 `earliest`，图回到最早快照重新执行**原始输入**，于是又出现 `web_lookup` 调用和暂停，`391` 从未出现（第 3.8 节）。把恢复用的 config 换成 `config` 后，实测输出 `<<tools>> [ToolMessage] 391` 和最终回答，thread 历史变为 10 个快照、两条分支。
- **在 langgraph 0.2.50 中**：除了同样的崩溃，`Command(resume=True)` 不会越过静态断点——首轮批准后只打印 `<<__interrupt__>>`，工具不执行，历史只有 3 个快照。改用 `app.stream(None, config)` 后两个版本行为一致。

---

## 7. 动手改一改

1. **修复两处 bug**：抽出 `print_events(stream)` 辅助函数并跳过非 dict 更新；time-travel 后用 thread config 恢复。确认最终能看到 `391`。
2. **去掉 reducer 做对照**：把 `messages` 改成 `messages: list[AnyMessage]`，用假 LLM 运行，打印每个快照的消息条数，观察历史如何被覆盖成 1 条。
3. **只对有副作用的工具中断**：新增一个 `send_email` 工具，拆成 `read_tools`（`calculator`、`web_lookup`）和 `write_tools`（`send_email`）两个 `ToolNode`，router 根据工具名分流，只对 `write_tools` 设置 `interrupt_before`。
4. **实现拒绝路径**：在暂停点用 `update_state(..., as_node="tools")` 写入"Rejected by human reviewer."的 ToolMessage，`invoke(None, config)` 后检查模型的回复。
5. **讲义练习 2**：加 `planner` 节点写入 `plan: list[str]`，`agent` 逐步标记完成；故意用错 reducer，写一个测试在"中断—恢复"后断言 `plan` 没丢。
6. **进阶**：换成 `SqliteSaver`（`langgraph-checkpoint-sqlite`），在暂停后**退出进程**，再启动一个新进程用同一个 `thread_id` 恢复，验证 checkpoint 真的持久化了；并用 `calculator` 的 `ast` 安全版替换 `eval`。

---

## 8. 常见坑

- **忘记 `add_messages`**：顺序节点静默覆盖历史；并行节点写同一字段则直接抛 `InvalidUpdateError`（讲义说"second wins silently"，只对顺序执行成立）。
- **把 `__interrupt__` 当成节点更新**：`stream_mode="updates"` 的事件不全是 `{节点: dict}`，要先判断类型。
- **time-travel 后继续用旧 config**：带 `checkpoint_id` 的 config 永远指向那个旧点；继续最新分支要用只含 `thread_id` 的 config。
- **混淆静态断点和动态中断**：`interrupt_before/after` 是编译期的静态断点，`interrupt()` 是节点内的动态中断；`Command(resume=...)` 对前者的支持取决于版本，`None` 输入最稳妥。
- **拒绝时只追加一条 AIMessage**：前一条 AIMessage 里的 tool_use 没有对应结果，真实模型 API 可能报错；应为每个 `tool_call_id` 补 ToolMessage。
- **interrupt 放在副作用之后**：`interrupt_after` 放在有副作用的节点上，审批时损害已经发生。
- **恢复后重复执行副作用**：恢复或分叉都会重新运行后续节点，有副作用的工具必须幂等。
- **生产环境用 `MemorySaver`**：重启即丢失所有暂停中的会话。
- **讲义 API 小错**：概念部分 `graph.stream(state, mode="updates")` 应为 `stream_mode=`；`graph.get_state_history(thread_id)` 实际接收的是 config 字典；Step 4 的历史打印循环会在空的输入快照上抛 `IndexError`。中文机翻版术语混乱（如把 state machine 译成"国家机器"、reducer 译成"缩放符"），以英文版为准。
