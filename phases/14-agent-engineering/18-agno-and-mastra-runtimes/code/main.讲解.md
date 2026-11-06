# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 18 节 生产级 Agent 运行时：快速实例化与类型化工作流 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`time`、`dataclasses`、`typing`），无需安装 Agno 或 Mastra。同目录还有 TypeScript 对照版 `main.ts`（可用 `tsx main.ts` 运行），本文第 3.6 节一并对照讲解。

---

## 1. 这份代码在考察什么

讲义本节以"比较"为主（Type: Learn），代码是一份 142 行的并排玩具，用同一种语言（Python 标准库）模仿两种运行时的**结构差异**：

1. **Agno 形状**：一个极薄的 agent（名字 + 一个函数）、一个会话存储、一个类似 FastAPI 路由函数的 `agno_request_handler`，并用 `time.perf_counter_ns()` 测量 handler 耗时——对应讲义的"无状态、会话作用域的 FastAPI 后端"和"微秒级开销"。
2. **Mastra 形状**：三个原语——带 `input_schema` 的 `MastraTool`、持有 instructions 与 tools 的 `MastraAgent`、按顺序串联步骤的 `MastraWorkflow`——对应讲义的 "Agents, Tools (Zod-typed), Workflows"。

> 一句话：**Agno 形状 = "一个函数 + 外置会话"，Mastra 形状 = "agent / tool / workflow 三种积木"**。但它离讲义的描述有距离：没有流式输出、Agno 实际复用同一个 agent、agent 不读取会话历史、Mastra 的 schema 从不校验，两条路径也并非"功能等价"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `AgnoAgent` | dataclass | `name` + `fn`；`run(prompt)` 直接调用 `fn` | 轻量 agent（"just pure python"） |
| `AgnoSession` | 类 | `append` / `history`，内存 dict 模拟数据库 | 会话状态外置到 DB |
| `agno_request_handler` | 函数 | 写入 user 轮 → 调 agent → 写入 assistant 轮 → 返回带耗时的字符串 | 无状态 FastAPI 路由 |
| `MastraTool` | dataclass | `name`、`input_schema`（JSON Schema 风格字典）、`fn` | Tools（真实 Mastra 用 Zod） |
| `MastraAgent` | dataclass | `name`、`instructions`、`tools`；`run` 依次执行给定的工具调用 | Agents |
| `MastraWorkflow` | dataclass | `steps: list[(name, fn)]`；`run` 把上一步输出喂给下一步 | Workflows |
| `_agno_agent_fn` / `_mastra_tool_fn` | 函数 | 模拟回复与模拟搜索结果 | LLM / 工具替身 |
| `main` | 函数 | Agno 3 次请求 → Mastra agent 2 次工具调用 → workflow 3 步 | 演示 |

数据流：

- Agno：`prompt` → `session.append("user: ...")` → `agent.run(prompt)` → `session.append("assistant: ...")` → 返回 `"<reply>  (handler X us)"`。
- Mastra agent：`[(tool_name, args), ...]` → 逐个查找工具并执行 → `(output, trace)`。
- Mastra workflow：`payload` → `normalize` → `search` → `summarize`，每步结果进 trace。

---

## 3. 逐段精讲

### 3.1 Agno 形状：极薄的 agent 与外置会话

```python
@dataclass
class AgnoAgent:
    name: str
    fn: Callable[[str], str]

    def run(self, prompt: str) -> str:
        return self.fn(prompt)


class AgnoSession:
    def __init__(self) -> None:
        self._turns: dict[str, list[str]] = {}

    def append(self, session_id: str, turn: str) -> None:
        self._turns.setdefault(session_id, []).append(turn)

    def history(self, session_id: str) -> list[str]:
        return list(self._turns.get(session_id, []))
```

- `AgnoAgent` 只有两个字段，`run` 只是转调 `fn`。这在形式上呼应讲义引用的 Agno 口号 "No graphs, chains, or convoluted patterns — just pure python"，也解释了为什么"实例化可以很便宜"：对象里几乎什么都没有。
- `AgnoSession` 用 `dict[str, list[str]]` 模拟数据库：键是会话 ID，值是按顺序追加的轮次字符串。
- `history` 返回 `list(...)` 副本，调用方修改不会影响存储。
- ⚠️ 真实场景中会话在 DB 中（讲义："session state lives in a DB"），这里是进程内存，进程重启即丢失——这恰恰是"有状态进程"的反面教材，只是为了演示方便。

### 3.2 `agno_request_handler`：模拟一个 FastAPI 路由

```python
def agno_request_handler(session: AgnoSession,
                         agent: AgnoAgent,
                         session_id: str,
                         prompt: str) -> str:
    start = time.perf_counter_ns()
    session.append(session_id, f"user: {prompt}")
    output = agent.run(prompt)
    session.append(session_id, f"assistant: {output}")
    elapsed_us = (time.perf_counter_ns() - start) / 1000
    return f"{output}  (handler {elapsed_us:.1f} us)"
```

- `time.perf_counter_ns()` 返回单调递增的高精度计时（纳秒整数），适合测量短时间间隔；除以 1000 换算为微秒，`:.1f` 保留一位小数。
- 测量的是**整个 handler**（两次写会话 + 一次 agent 调用），**不是 agent 实例化**。讲义的 "~2μs agent instantiation" 指的是创建 agent 对象的开销，二者不能直接比较。
- ⚠️ 与打印的 pattern "a fresh agent per request" 不一致：`agent` 作为参数传入，`main` 在循环外只创建了一次，三次请求复用同一个对象。
- ⚠️ agent 只拿到 `prompt`，**从不读取 `session.history(...)`**。会话被写入却没有被用来恢复上下文，因此这不是真正的"会话状态驱动的无状态 agent"——测验 Q9 给出了"每请求新建 agent + 加载历史"的改写。
- 先写 `user` 轮再调用 agent：如果 agent 抛异常，会话里会留下"只有问、没有答"的半截记录。

### 3.3 Mastra 形状：Tool 与 Agent

```python
@dataclass
class MastraTool:
    name: str
    input_schema: dict[str, Any]
    fn: Callable[..., str]


@dataclass
class MastraAgent:
    name: str
    instructions: str
    tools: list[MastraTool] = field(default_factory=list)

    def run(self, prompt: str, tool_calls: list[tuple[str, dict[str, Any]]]
            ) -> tuple[str, list[tuple[str, str]]]:
        trace: list[tuple[str, str]] = []
        for tool_name, args in tool_calls:
            tool = next((t for t in self.tools if t.name == tool_name), None)
            if tool is None:
                trace.append((tool_name, "error: unknown"))
                continue
            result = tool.fn(**args)
            trace.append((tool_name, result))
        output = f"{self.name} processed {len(tool_calls)} tools"
        return output, trace
```

- `MastraTool.input_schema` 是一个 JSON Schema 风格的字典（`{"type": "object", "properties": {"query": {"type": "string"}}}`），对应真实 Mastra 中的 Zod schema。
- ⚠️ **schema 只是被存储，从未校验**。我们实测：`{"query": 123}` 被照常执行得到 `[mastra search result for 123]`；`{"q": "x"}` 则在 `tool.fn(**args)` 处抛出 `TypeError: _mastra_tool_fn() got an unexpected keyword argument 'q'`，由于没有 `try`，整个 `run` 直接失败。`main.ts` 里有 `checkSchema`，Python 版缺失（测验 Q10）。
- 工具查找用 `next(生成器, None)`，未知工具记入 trace 后 `continue`，不会中断。
- 与第 17 节一样，工具调用序列是**调用方事先给定的**（`tool_calls` 参数），没有模型做决策。
- ⚠️ `prompt` 与 `instructions` 都没有被使用，最终输出只是 `"mastra_a processed 2 tools"`，没有 LLM 把工具结果组织成回答（`main.ts` 用 `mockLLM` 补上了这一步）。
- 返回类型 `tuple[str, list[tuple[str, str]]]`：调用方用 `output, trace = ...` 解包。

### 3.4 Mastra 形状：Workflow

```python
@dataclass
class MastraWorkflow:
    steps: list[tuple[str, Callable[[Any], Any]]]

    def run(self, payload: Any) -> list[tuple[str, Any]]:
        trace: list[tuple[str, Any]] = []
        current = payload
        for name, fn in self.steps:
            current = fn(current)
            trace.append((name, current))
        return trace
```

- 最朴素的**管道（pipeline）**：每一步的输出是下一步的输入，`trace` 记录每一步的中间结果。
- 与 agent 的区别：workflow 的步骤顺序是**确定的、由开发者写死的**，agent 的工具调用顺序（在真实系统里）由模型决定。这对应第 12 节"优先用简单的 workflow"的思想。
- 没有分支、并行、错误重试、挂起/恢复；真实 Mastra 的 Workflows 会提供这些能力并持久化状态（讲义提到 composite storage 中 workflows 可以单独存储）。

### 3.5 `main()`：两段演示

```python
    session = AgnoSession()
    agent = AgnoAgent(name="agno_a", fn=_agno_agent_fn)
    for i in range(3):
        out = agno_request_handler(session, agent, "s001",
                                   f"query {i}: how do I ship an agent")
        print(f"  turn {i}: {out}")
    print(f"  session history length: {len(session.history('s001'))}")
```

- 3 次请求共用会话 `s001`，每次追加 2 条，所以历史长度为 6。
- `_agno_agent_fn` 返回 `"[agno reply] " + prompt[:40]`。

```python
    workflow = MastraWorkflow(steps=[
        ("normalize", lambda p: p.strip().lower()),
        ("search", lambda p: f"found 3 results for {p}"),
        ("summarize", lambda p: f"summary: {p}"),
    ])
    for name, out in workflow.run("  Agent Engineering 2026  "):
        print(f"    {name}: {out}")
```

- 用 `lambda` 定义三个步骤：去首尾空格并转小写 → 模拟搜索 → 模拟摘要。
- 注意这里的 "search" 步骤是一个新的 lambda，**没有复用**上面定义的 `search_tool`；`main.ts` 的 workflow 则直接调用 `searchTool.execute`，更能体现"workflow 编排 tools"。
- 最后一行 `"pick by stack: python+fastapi  Agno; ..."` 中间是两个空格，对照 `main.ts` 可知原本应是箭头 `→`（字符在移植时丢失了）。

### 3.6 对照 `main.ts`：TypeScript 版多了什么

`main.ts`（209 行）是同一个演示的 TypeScript 版本，我们用 `tsx main.ts` 实际运行过。主要差异：

| 方面 | `main.py` | `main.ts` |
|------|-----------|-----------|
| 工具参数校验 | 无 | `checkSchema` 检查缺字段与 `typeof` 类型，错误写入 trace |
| 未知工具演示 | 无 | 故意调用 `unknown_tool`，trace 中出现 `error: unknown tool` |
| 最终 LLM 步骤 | 无，输出固定字符串 | `mockLLM(this.instructions, 用户消息 + 工具结果)`，并按"字符数/4"估算 token（运行输出 `~78 tokens`） |
| workflow 与 tools | workflow 用独立 lambda | workflow 步骤直接调用 `searchTool.execute` / `summariseTool.execute` |
| 异步 | 同步 | `async/await`，`mockLLM` 用 `setTimeout(5ms)` 模拟网络延迟 |
| 计时 | `perf_counter_ns` | `process.hrtime.bigint()`，整数微秒 |
| 流式输出 | 无 | 无 |

TS 版的一个小瑕疵：`mockLLM` 返回 `userMessage.slice(0, 60)`，截断点落在多行文本中间，所以输出里出现了换行和半截的 `search: 3 results ]`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用一种语言模仿两种运行时 | 便于并排比较结构 | 体现不出 Python/TS 生态差异；`main.ts` 补了 TS 视角 |
| Agno agent 只有 `name` + `fn` | 体现"纯 Python、极低开销" | 不代表真实 Agno agent（模型、工具、记忆配置）的实例化成本 |
| 会话存在内存 dict | 零依赖 | 进程重启丢失；生产放 DB，按会话串行化写入 |
| handler 复用 agent、不读历史 | 代码最短 | 与"每请求新建 agent、状态从 DB 恢复"不符；应传入工厂并加载历史 |
| 计时测 handler 而非实例化 | 演示 μs 级计时 | 不能用来验证"2μs 实例化"；应单独基准测试构造函数 |
| Mastra schema 只存不验 | 篇幅 | 错误参数被放过或导致崩溃；用 Zod / jsonschema / Pydantic 校验 |
| 工具调用由调用方给定 | 无需模型 | 看不到 agent 决策；真实 agent 由 LLM 选择工具 |
| workflow 线性串联 | 最直观 | 无分支、重试、持久化、人工审批挂起 |
| 不实现流式输出 | 简化 | 讲义 "Build It" 提到 "stream the output"；可用生成器 / SSE 实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值 |
| `@dataclass` 带方法 | `AgnoAgent.run`、`MastraAgent.run` | dataclass 也可以定义普通方法 |
| `field(default_factory=list)` | `MastraAgent.tools` | 可变默认值必须用工厂 |
| 类型注解 | `Callable[[str], str]`、`list[tuple[str, Callable[[Any], Any]]]` | 描述函数签名与嵌套容器 |
| 返回元组并解包 | `return output, trace` / `output, trace = mastra_agent.run(...)` | 一次返回多个值 |
| `time.perf_counter_ns()` | `start = time.perf_counter_ns()` | 高精度单调时钟，返回纳秒整数 |
| `dict.setdefault` | `self._turns.setdefault(session_id, []).append(turn)` | 不存在则插入默认值并返回 |
| `next(生成器, 默认值)` | `next((t for t in self.tools if t.name == tool_name), None)` | 找第一个匹配元素 |
| `**args` 解包 | `tool.fn(**args)` | 字典展开为关键字参数 |
| `lambda` | `("normalize", lambda p: p.strip().lower())` | 匿名小函数，作为 workflow 步骤 |
| 字符串方法 | `p.strip().lower()` | 去首尾空白、转小写，可链式调用 |
| f-string 格式符 | `{elapsed_us:.1f}`、`{query!r}`、`{prompt[:40]}` | 保留 1 位小数、repr 加引号、切片 |
| 隐式字符串拼接 | `print("  pattern: a fresh agent per request; session holds state; " "FastAPI is stateless.")` | 相邻字面量自动连接 |
| `for ... in` 解包 | `for name, fn in self.steps:`、`for tool, result in trace:` | 遍历元组列表 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16）。handler 耗时每次运行都会略有不同，下面是其中一次：

```text
======================================================================
AGNO vs MASTRA — Phase 14, Lesson 18
======================================================================

1. AGNO-shaped (stateless session-scoped FastAPI handler)
  turn 0: [agno reply] query 0: how do I ship an agent  (handler 4.9 us)
  turn 1: [agno reply] query 1: how do I ship an agent  (handler 1.7 us)
  turn 2: [agno reply] query 2: how do I ship an agent  (handler 1.2 us)
  session history length: 6
  pattern: a fresh agent per request; session holds state; FastAPI is stateless.

2. MASTRA-shaped (Agents + Tools + Workflows)
  agent output: mastra_a processed 2 tools
    tool search: [mastra search result for 'agent engineering 2026']
    tool search: [mastra search result for 'BFCL V4 benchmarks']

  workflow run
    normalize: agent engineering 2026
    search: found 3 results for agent engineering 2026
    summarize: summary: found 3 results for agent engineering 2026

pick by stack: python+fastapi  Agno; typescript+next/vercel  Mastra.
```

逐项解读：

- **handler 耗时**：第二次运行得到 3.1 / 1.5 / 0.7 us。第一次调用通常最慢（首次执行路径上的缓存、内存分配等预热效应），之后降到 1μs 左右。这只是"两次 dict 追加 + 一次字符串格式化"的耗时，与讲义的"2μs 实例化"不是同一件事。我们另外用 `timeit` 测得：构造一个 `AgnoAgent` 约 0.07μs、约 142 字节（含名字字符串）——玩具对象太简单，既不能证明也不能反驳 Agno 的数字（测验 Q11）。
- **history length 6**：3 次请求 × (user + assistant)。
- **Mastra agent**：两次 `search` 调用的结果被记入 trace；输出只是计数字符串。`{query!r}` 使结果中的查询带单引号。
- **workflow**：`"  Agent Engineering 2026  "` 经 `strip().lower()` 变成 `agent engineering 2026`，再依次被"搜索""摘要"包装。trace 展示了每一步的中间结果，这是 workflow 易于调试的原因。
- **最后一行**：双空格处原本应是 `→`。
- **对照 TS 版**：`tsx main.ts` 的 handler 耗时为 103 / 18 / 4 us（含 `await` 的异步开销与 JIT 预热），Mastra agent 额外显示 `tool unknown_tool: error: unknown tool` 与 `(~78 tokens)`。

---

## 7. 动手改一改

1. **（入门）** 给 `main()` 再加一个会话 `s002`，交替发送请求，确认两个会话的历史互不干扰；把最后一行的双空格改回 `→`。
2. **（对齐讲义）** 把 `agno_request_handler` 改成接收 `make_agent` 工厂：每个请求新建 agent，并把 `session.history(...)` 传给 agent（测验 Q9）。思考同一会话并发请求时的竞态。
3. **（补齐校验）** 参照 `main.ts` 的 `checkSchema`，为 Python 版实现 JSON Schema 风格的参数校验，并给 `tool.fn(**args)` 加上异常捕获（测验 Q10）。
4. **（讲义练习 3）** 写一个基准：用 `timeit` 分别测量"构造 `AgnoAgent`"和"`agno_request_handler` 一次调用"的平均耗时；再用 `time.sleep(1.5)` 模拟一次 LLM 调用，计算实例化开销的占比，判断 2μs 是否对你的工作负载重要（测验 Q11）。
5. **（流式输出）** 让 agent 的 `fn` 变成生成器，handler 逐块 `yield`，流结束后再把完整回复写入会话（测验 Q12）；可以进一步用 FastAPI 的 `StreamingResponse` 包装。
6. **（进阶，讲义练习 1、2）** 安装 Agno（Python）与 Mastra（TypeScript），把第 01 节的 ReAct 循环分别移植过去，记录"哪些代码消失了、工具类型定义（Zod vs 无）有什么变化"。

---

## 8. 常见坑

- **把 handler 耗时当成实例化耗时**：本代码测的是整个 handler；比较框架时必须单独测构造开销，并放到真实请求链路里看占比。
- **为性能而性能**：一次 LLM 调用动辄秒级，微秒级的实例化差异几乎不可见；只有大量短命 agent（聊天汇聚、评测流水线）时才值得为它选型。
- **"无状态"却把状态放在进程内存**：本代码的 `AgnoSession` 只是演示；生产中会话必须放在外部存储，否则水平扩展和故障恢复都会出问题。
- **写了会话却不读**：agent 看不到历史，多轮对话就失去了意义。
- **只定义 schema 不校验**：模型生成的错误参数会被静默放过或导致崩溃；Python 中还要注意 `bool` 是 `int` 的子类。
- **以为两段演示"功能等价"**：讲义如此描述，但两条路径的输入、步骤与输出都不同，只能说明"结构不同"。
- **忽视许可证**：照抄 Mastra 的 `ee/` 功能前先读许可证，它不是 Apache 2.0。
