# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 23 节 OpenTelemetry GenAI 语义约定 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`time`、`dataclasses`、`typing`）；不需要安装 `opentelemetry-sdk`，不导出到任何后端

---

## 1. 这份代码在考察什么

这份代码用几十行标准库代码"手搓"了一个迷你 tracer，用来展示 OTel GenAI 语义约定的三个核心思想：

1. **span 树**：`create_agent`、`invoke_agent`、`chat`、tool span 之间的父子关系，用一个栈来维护"当前活动 span"。
2. **标准属性**：`gen_ai.agent.name`、`gen_ai.operation.name`、`gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.data_source.id` 等。
3. **内容捕获策略**：prompt/回复默认**不内联**进 span，而是写入外部存储，span 上只记 `*.reference_id`。

> 一句话：**让一次 agent 运行变成一棵带标准属性的 span 树，同时把敏感正文挪出 trace**。阅读时要注意三个"演示与讲义不符"的地方：脚本根本没有产生 tool span；所谓"opt-in"其实没有关闭选项；tracer 缺少 trace id 与异常安全。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Span` | dataclass | 名字、kind、属性字典、子 span 列表、起止时间；`duration_ms` 属性 | OTel span |
| `ExternalContentStore` | 类 | 自增 ID → 正文的字典；`put` / `get` / `items` | 外部内容存储（S3/日志库） |
| `Tracer` | 类 | 哨兵根 span + 栈；`start_span` / `end_span` / `add_content` | OTel tracer + 上下文 |
| `_scripted_llm` | 函数 | 按 prompt 关键词返回固定回复 | 假的 LLM |
| `_search_tool` | 函数 | 返回固定的检索结果字符串 | 假的工具 |
| `main` | 函数 | 发出 create_agent、invoke_agent、3 个 chat（及可能的 tool span），渲染树与外部存储 | 演示 |
| `render` | `main` 内部的递归函数 | 缩进打印 span 树与属性 | trace 可视化 |

数据流：`main` → `Tracer.start_span("create_agent ...")` / `end_span` → `start_span("invoke_agent ...")` → 循环 3 次：`chat` span + `add_content`（输入、输出各一次）→（若输出含 `search_tool`）tool span → `end_span` 关闭 invoke_agent → `render(tracer.root)` → 打印 `content_store.items()`。

---

## 3. 逐段精讲

### 3.1 `Span`：一个 span 的全部信息

```python
@dataclass
class Span:
    name: str
    kind: str = "INTERNAL"
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)
    start_ns: int = 0
    end_ns: int = 0

    @property
    def duration_ms(self) -> float:
        return (self.end_ns - self.start_ns) / 1_000_000
```

- `kind` 默认 `"INTERNAL"`，对应讲义"进程内 agent 框架用 INTERNAL"。
- `field(default_factory=dict)`：可变默认值必须用工厂函数，否则所有 span 会共享同一个字典（dataclass 直接写 `= {}` 会报错）。
- `children` 用"父持有子列表"表示树。真实 OTel 是**反过来**的：每个 span 记录自己的 `trace_id`、`span_id` 和 `parent_span_id`，各自独立导出，由后端按 id 重建树——这样跨进程、跨服务的 span 才能拼起来。
- 时间用 `time.perf_counter_ns()`（单调时钟，适合测时长）；真实 span 用的是墙上时钟时间戳，便于跨机器对齐。
- `1_000_000`：数字里的下划线只为可读，纳秒 → 毫秒。

### 3.2 `ExternalContentStore`：外存 + 引用

```python
class ExternalContentStore:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._counter = 0

    def put(self, content: str) -> str:
        self._counter += 1
        cid = f"content_{self._counter:03d}"
        self._store[cid] = content
        return cid
    ...
    def items(self) -> list[tuple[str, str]]:
        return sorted(self._store.items())
```

- `put` 返回一个引用 ID（`content_001` …），span 上只记这个 ID。对应讲义"record references on spans (pointer IDs, not prose)"。
- `f"{n:03d}"`：至少 3 位、不足补 0。
- ⚠️ `items()` 按**字符串**排序：超过 999 条后，`content_1000` 会排到 `content_100` 与 `content_101` 之间（实测第 1000 条出现在下标 100 处）。用插入顺序（Python 3.7+ 字典本身有序）或 UUID 即可。
- 生产中这一层应是有访问控制、保留期、可删除、可审计的存储（S3、日志库），并且引用 ID 不应可被猜测（自增 ID 可以被枚举）。

### 3.3 `Tracer`：栈式上下文

```python
class Tracer:
    def __init__(self, capture_inline: bool = False,
                 content_store: ExternalContentStore | None = None) -> None:
        self.root = Span(name="__root__")
        self.stack: list[Span] = [self.root]
        self.capture_inline = capture_inline
        self.content_store = content_store or ExternalContentStore()

    def start_span(self, name: str, kind: str = "INTERNAL",
                   attributes: dict[str, Any] | None = None) -> Span:
        span = Span(name=name, kind=kind, attributes=dict(attributes or {}),
                    start_ns=time.perf_counter_ns())
        self.stack[-1].children.append(span)
        self.stack.append(span)
        return span

    def end_span(self) -> None:
        span = self.stack.pop()
        span.end_ns = time.perf_counter_ns()
```

- **栈顶 = 当前活动 span**。`start_span` 把新 span 挂到栈顶之下并入栈；`end_span` 出栈并记结束时间。这就是 OTel"current context"的最简模型：后开的 span 自动成为先开的 span 的孩子，**父子关系不需要手动传**——讲义"Spans without parent links. Orphaned tool spans. Always propagate context."说的正是这个上下文。
- `__root__` 是哨兵节点，保证 `self.stack[-1]` 总是存在，渲染时被跳过。
- `dict(attributes or {})`：`attributes` 为 `None` 时用空字典；并且**复制**一份，避免调用方后续修改传入的字典影响 span。
- `content_store or ExternalContentStore()`：没传就新建。
- ⚠️ **不是异常安全的**：如果在 `start_span` 和 `end_span` 之间抛异常，span 永远不出栈，之后所有 span 都挂错地方（实测：异常后新开的 `y` 成了未结束的 `x` 的孩子）。
- ⚠️ **没有防护**：多调用一次 `end_span` 会把哨兵也弹出，下一次 `start_span` 抛 `IndexError`（已实测）。
- ⚠️ 单一栈只适用于单线程、同步代码。多线程或 asyncio 下多个任务交错开关 span，会互相串台；OTel SDK 用 `contextvars` 为每个任务维护独立上下文。
- 测验 Q11 给出了 `@contextmanager` + `try/finally` 的改写，并演示生成 W3C `traceparent`。

### 3.4 `add_content`：两种模式，没有"关闭"

```python
    def add_content(self, span: Span, key: str, content: str) -> None:
        if self.capture_inline:
            span.attributes[key] = content[:200]
            return
        cid = self.content_store.put(content)
        span.attributes[f"{key}.reference_id"] = cid
```

| 模式 | span 上的属性 | 正文去向 |
|------|-------------|---------|
| `capture_inline=True` | `gen_ai.input.messages = '前 200 字符'` | 留在 trace 里 |
| `capture_inline=False`（默认） | `gen_ai.input.messages.reference_id = 'content_001'` | 外部存储 |

- 讲义："instrumentations SHOULD NOT capture inputs/outputs by default. Capture is opt-in"。
- ⚠️ 代码默认模式**仍然捕获了全部正文**（只是放在外部存储），并不存在"不捕获"的选项，所以 docstring 中"Content capture is opt-in"并不成立。正确设计应是三档：`off`（默认）/ `reference` / `inline`（测验 Q10）。
- ⚠️ 内联模式静默截断到 200 字符：截断既不能保证安全（前 200 字符里照样有身份证号），又会让调试信息不完整，而且没有任何标记说明被截断过。
- 规范里的 `gen_ai.input.messages` 等是结构化的消息数组（角色 + 内容片段），这里简化成一个字符串。

### 3.5 假的 LLM 与工具

```python
def _scripted_llm(prompt: str) -> str:
    if "search" in prompt.lower():
        return "search_tool(\"agent engineering\")"
    if "result" in prompt.lower():
        return "found 3 sources; drafting answer"
    return "final answer: agents in 2026"


def _search_tool(query: str) -> str:
    return f"[3 sources for {query!r}]"
```

- 设计意图是演示 ReAct 的三步：模型要求搜索 → 拿到结果后起草 → 给出最终答案。
- 下划线前缀 `_` 表示"模块内部使用"，是约定而非强制。
- `"search_tool(\"agent engineering\")"`：字符串内的双引号用 `\"` 转义。

### 3.6 `main`：发出 span（以及没发出的 tool span）

```python
    create_agent = tracer.start_span(
        "create_agent research_bot",
        attributes={
            "gen_ai.agent.name": "research_bot",
            "gen_ai.operation.name": "create_agent",
            "gen_ai.provider.name": "anthropic",
        },
    )
    tracer.end_span()

    invoke = tracer.start_span(
        "invoke_agent research_bot",
        attributes={ ... "gen_ai.request.model": "claude-opus-4-6", },
    )
```

- span 名遵循讲义"`invoke_agent {gen_ai.agent.name}`"；`create_agent` 立刻结束，表示构造阶段。
- `create_agent` 与 `invoke_agent` 都直接挂在哨兵根下，是**两个互不相关的根 span**（相当于两条 trace）。变量 `create_agent`、`invoke` 赋值后从未使用。

```python
    for turn in range(3):
        chat = tracer.start_span("chat", attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "anthropic",
                "gen_ai.request.model": "claude-opus-4-6",
                "gen_ai.response.model": "claude-opus-4-6",
            },
        )
        prompt = f"turn {turn}: next action please"
        tracer.add_content(chat, "gen_ai.input.messages", prompt)
        output = _scripted_llm(prompt)
        tracer.add_content(chat, "gen_ai.output.messages", output)
        tracer.end_span()

        if "search_tool" in output:
            tool_span = tracer.start_span(
                "tool_call search_tool",
                attributes={
                    "gen_ai.operation.name": "tool_call",
                    "gen_ai.tool.name": "search_tool",
                    "gen_ai.data_source.id": "corpus://mem0/default",
                },
            )
            ...
```

- 每次模型调用一个 `chat` span，属性包含 provider、请求模型、响应模型。
- ⚠️ **tool span 永远不会出现**：prompt 固定为 `"turn N: next action please"`，不含 `search` 或 `result`，`_scripted_llm` 三次都返回 `final answer`，`if "search_tool" in output` 永远为假。讲义说的"per-tool spans"以及 `gen_ai.data_source.id` 的示范都没有出现在输出中（测验 Q5、Q9）。
- ⚠️ 拿到 `final answer` 后循环不会停止；prompt 也不包含历史——这不是一个真正的 agent loop。
- ⚠️ `chat` span 用默认 kind `INTERNAL`，但它代表对 Anthropic API 的远程调用，按"远程用 CLIENT"的原则应为 `CLIENT`。
- 关于 `tool_call` 这个名字：讲义列出的 `gen_ai.operation.name` 取值包括 `tool_call`；据笔者了解，OTel 官方规范中工具执行使用 `execute_tool`（span 名 `execute_tool {gen_ai.tool.name}`）。规范仍在变化，落地时以官方页面为准。

### 3.7 `render`：递归打印 span 树

```python
    def render(span: Span, indent: int = 0) -> None:
        if span.name == "__root__":
            for child in span.children:
                render(child, indent)
            return
        pad = "  " * indent
        dur = f"{span.duration_ms:.2f}ms" if span.end_ns else "..."
        print(f"{pad}{span.name}  [{span.kind}]  {dur}")
        for key in sorted(span.attributes):
            val = span.attributes[key]
            if isinstance(val, str) and len(val) > 50:
                val = val[:50] + "..."
            print(f"{pad}  {key} = {val!r}")
        for child in span.children:
            render(child, indent + 1)
```

- 经典的**先序遍历**：先打印自己，再递归打印孩子，缩进层数 +1。
- `if span.end_ns else "..."`：没结束的 span 显示 `...`，可用来发现"忘了 end_span"。
- 属性按 key 排序打印，长字符串截到 50 字符。
- `render` 定义在 `main` 内部，是一个只在本地使用的嵌套函数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不依赖 OTel SDK，手写 tracer | 零依赖，看清原理 | 不能导出到 Jaeger/Datadog；生产用 `opentelemetry-sdk` + OTLP exporter |
| 父持有 children 列表 | 渲染方便 | 无 trace/span/parent id，无法跨进程拼接；真实 span 各自记录 parent id |
| 单一栈表示当前上下文 | 最简单的"自动父子关系" | 不支持多线程/异步、非异常安全；生产用 contextvars + 上下文管理器 |
| 哨兵根 span | 避免空栈判断 | 多调用一次 `end_span` 仍会弹掉它 |
| 默认外存 + 引用 | 正文不进 trace | 没有"不捕获"选项，与"默认不捕获"不符；生产三档、默认 off |
| 自增引用 ID | 可读 | 可被枚举、字符串排序在 999 后错乱；生产用 UUID + 访问控制 |
| 脚本化 LLM | 可复现 | 驱动写错导致 tool span 从未出现 |
| chat span 用 INTERNAL | 沿用默认值 | 远程模型调用应标 CLIENT |
| 稳定性 opt-in 只是打印一句话 | 提示概念 | 代码并不读取该环境变量 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `ExternalContentStore \| None` 等新式注解 |
| `@dataclass` + `field(default_factory=...)` | `attributes: dict[str, Any] = field(default_factory=dict)` | 可变默认值必须用工厂函数，每个实例得到独立的新字典/列表 |
| 字符串形式的前向引用 | `children: list["Span"]` | 类还没定义完时用字符串引用自身 |
| `@property` | `def duration_ms(self) -> float` | 像属性一样访问：`span.duration_ms`，不用加括号 |
| 数字下划线 | `1_000_000` | 只为可读，等于 1000000 |
| 私有约定 | `self._store`、`_scripted_llm` | 单下划线表示"内部使用"，不强制 |
| f-string 补零 | `f"content_{self._counter:03d}"` | 至少 3 位整数，不足补 0 |
| f-string 小数位 | `f"{span.duration_ms:.2f}ms"` | 保留两位小数 |
| `or` 提供默认值 | `content_store or ExternalContentStore()`、`attributes or {}` | 左边为假（None、空）时取右边 |
| `dict(...)` 复制 | `dict(attributes or {})` | 浅拷贝，避免共享调用方的字典 |
| 列表当栈 | `self.stack.append(span)`、`self.stack.pop()`、`self.stack[-1]` | 尾部入栈、出栈、取栈顶 |
| `sorted(dict.items())` | `sorted(self._store.items())` | 按 key 排序（字符串字典序） |
| `dict.get(k, default)` | `self._store.get(cid, "")` | 不存在时返回默认值 |
| 条件表达式 | `f"..." if span.end_ns else "..."` | 一行写 if/else |
| `isinstance` | `isinstance(val, str) and len(val) > 50` | 类型判断，配合短路求值 |
| 嵌套函数 + 递归 | `def render(span, indent=0): ... render(child, indent + 1)` | 函数内定义函数，并调用自身遍历树 |
| 转义引号 | `"search_tool(\"agent engineering\")"` | 字符串里包含双引号 |
| `time.perf_counter_ns()` | `start_ns=time.perf_counter_ns()` | 单调高精度计时，返回整数纳秒 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成；耗时数字每次略有不同）：

```text
span tree (GenAI-shaped)
create_agent research_bot  [INTERNAL]  0.00ms
  gen_ai.agent.name = 'research_bot'
  gen_ai.operation.name = 'create_agent'
  gen_ai.provider.name = 'anthropic'
invoke_agent research_bot  [INTERNAL]  0.02ms
  gen_ai.agent.name = 'research_bot'
  gen_ai.operation.name = 'invoke_agent'
  gen_ai.provider.name = 'anthropic'
  gen_ai.request.model = 'claude-opus-4-6'
  chat  [INTERNAL]  0.01ms
    gen_ai.input.messages.reference_id = 'content_001'
    gen_ai.operation.name = 'chat'
    gen_ai.output.messages.reference_id = 'content_002'
    gen_ai.provider.name = 'anthropic'
    gen_ai.request.model = 'claude-opus-4-6'
    gen_ai.response.model = 'claude-opus-4-6'
  chat  [INTERNAL]  0.00ms
    ...（同上，content_003 / content_004）
  chat  [INTERNAL]  0.00ms
    ...（同上，content_005 / content_006）

external content store (opt-in references, not inline)
  content_001: turn 0: next action please
  content_002: final answer: agents in 2026
  content_003: turn 1: next action please
  content_004: final answer: agents in 2026
  content_005: turn 2: next action please
  content_006: final answer: agents in 2026
```

逐项解读：

- **树结构**：`create_agent` 与 `invoke_agent` 是两个并列的顶层 span；3 个 `chat` 是 `invoke_agent` 的孩子（缩进一级）——栈式上下文自动建立了父子关系。
- **属性**：每个 `chat` 都带 provider、请求模型、响应模型，符合讲义"关键属性"；正文没有出现在 span 上，只有 `*.reference_id`。
- **没有 tool span**：三轮输出都是 `final answer: agents in 2026`（外部存储里看得很清楚），说明工具分支从未执行。讲义"Output: a span tree with all required GenAI attributes"中预期的 tool span 和 `gen_ai.data_source.id` 都没有出现。修好驱动后（测验 Q9），`invoke_agent` 的孩子变为 `['chat', 'tool_call search_tool', 'chat', 'chat']`。
- **耗时接近 0**：没有真实的网络调用，只是在测 Python 函数调用的开销；真实 trace 中 `chat` span 会是几百毫秒到几秒。
- **外部存储**：6 条正文对应 3 轮 × （输入 + 输出）。注意它们**被完整保存了**——默认模式并没有"不捕获"。
- 最后三行提到 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`：这只是提示，代码没有读取该变量。

---

## 7. 动手改一改

1. 修好驱动：让三轮 prompt 依次触发"搜索 → 起草 → 最终答案"，并在拿到 `final answer` 时 `break`，确认 tool span 和 `gen_ai.data_source.id` 出现在树中（测验 Q9）。
2. （讲义练习 2）把 `ExternalContentStore` 换成 SQLite（标准库 `sqlite3`）：正文写入表中，span 上只记行 ID；加一个"三档捕获"开关，默认 `off`（测验 Q10）。
3. 用 `@contextmanager` 写 `with tracer.span(...)`，异常时记录 `error.type` 并保证出栈；给每个 span 生成 `trace_id` / `span_id` / `parent_span_id`（测验 Q11）。
4. 把 `chat` span 的 kind 改成 `CLIENT`，span 名改成 `chat claude-opus-4-6` 形式，并给 `chat` span 加上 token 用量属性（输入/输出 token 数）。
5. （讲义练习 1）安装 `opentelemetry-sdk`，用 `ConsoleSpanExporter` 重写本文件，对比手写版与 SDK 输出的字段差异；有条件的话导出到本地 Jaeger。
6. （讲义练习 5）在 span 树上写一个聚合函数：遍历所有 tool span，按"所在 agent 运行使用的 `gen_ai.response.model` × `gen_ai.tool.name`"统计错误次数。

---

## 8. 常见坑

- **演示没跑到要演示的路径**：写脚本化的 LLM 时，要确认每个分支都被覆盖到——本文件的 tool 分支就从未执行。
- **把"外存"当成"不捕获"**：外存只是换了位置，正文仍被收集；规范的默认是不捕获。
- **非异常安全的 span 管理**：手动 `start/end` 配对，一旦中间抛异常整棵树就错位；用上下文管理器。
- **单一全局栈 + 并发**：多线程/asyncio 下 span 会挂到别人的父 span 下。
- **只有父持有子、没有 id**：无法跨进程传播上下文，子进程的 span 成为孤儿。
- **远程调用标成 INTERNAL**：后端无法正确识别跨服务调用关系。
- **截断当脱敏**：`content[:200]` 不能去除敏感信息。
- **缺 `gen_ai.provider.name`**：多 provider 看板会归属错误（本代码的 tool span 就没有这个属性，只能靠父 span 推断）。
