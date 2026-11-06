# 测验 · OpenTelemetry GenAI 语义约定（OpenTelemetry GenAI Semantic Conventions）

> **阶段 14 · Agent 工程 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要语义约定 | 各厂商各起 span 名，运维只能按框架做看板；OTel GenAI SIG（讲义：2024 年 4 月成立）定义统一 schema，让同一条 agent trace 在 Datadog、Grafana、Jaeger、Honeycomb 中含义一致 |
| 2 | 三类 span | model/client span（原始 LLM 调用，由 provider SDK 或框架适配器产生）、agent span（`create_agent` 构造时、`invoke_agent` 运行时）、tool span（每次工具调用一个，以父子关系挂在 agent span 下） |
| 3 | agent span 命名 | 有名字时 `invoke_agent {gen_ai.agent.name}`，否则就叫 `invoke_agent` |
| 4 | CLIENT vs INTERNAL | 远程 agent 服务（OpenAI Assistants API、Bedrock Agents）用 CLIENT；进程内框架（LangChain、CrewAI、本地 ReAct）用 INTERNAL |
| 5 | 关键属性 | `gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.response.model`（路由后实际使用的模型）、`gen_ai.agent.name`、`gen_ai.operation.name`、`gen_ai.data_source.id`（RAG 查了哪个库） |
| 6 | 内容捕获默认关闭 | instrumentation SHOULD NOT 默认记录输入输出；opt-in 字段为 `gen_ai.system_instructions`、`gen_ai.input.messages`、`gen_ai.output.messages` |
| 7 | 生产推荐：外存 + 引用 | 内容写到 S3/日志库，span 上只记引用 ID（指针而非正文），兼顾调试与 PII/密钥安全 |
| 8 | 稳定性 opt-in | 讲义：截至 2026 年 3 月多数约定仍是 experimental；通过 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 选择最新实验版约定 |
| 9 | 四种常见错误 | span 里存完整 prompt、缺 `gen_ai.provider.name`、span 没有父链接（孤儿 tool span）、不设稳定性 opt-in |
| 10 | 后端支持 | 讲义：Datadog v1.37+ 原生映射 GenAI 属性；Grafana、Honeycomb、Jaeger 支持原始属性；Langfuse/Phoenix/Opik 见第 24 节 |

### 核心技能（能动手做到）

- [ ] 为一个 ReAct 风格 agent 画出 span 树：`invoke_agent` → `chat` / tool span，并标出每个 span 的 kind 与关键属性
- [ ] 判断任意 agent 框架的 `invoke_agent` 应该用 CLIENT 还是 INTERNAL
- [ ] 读懂本节 `Tracer` 的栈式父子关系实现，并指出它在异常、重复 `end_span` 时的问题
- [ ] 发现本节演示**根本没有产生 tool span** 的原因，并修好脚本
- [ ] 实现"关闭 / 仅引用 / 内联"三档内容捕获策略，默认关闭
- [ ] 解释 W3C trace context（`traceparent`）为什么是跨进程拼接 trace 的前提

---

## 二、基础自测（选择题）

**Q1.** 讲义把 GenAI span 分成哪三类？

- A. HTTP span、数据库 span、消息队列 span
- B. model/client span、agent span（`create_agent` / `invoke_agent`）、tool span
- C. prompt span、completion span、embedding span
- D. CLIENT span、SERVER span、PRODUCER span

**Q2.** 下列关于 `invoke_agent` span kind 的说法，正确的是：

- A. 所有 agent span 一律用 SERVER
- B. LangChain、CrewAI 这类进程内框架用 CLIENT；OpenAI Assistants API 用 INTERNAL
- C. kind 只影响颜色显示，可以随便填
- D. 调用远程 agent 服务（OpenAI Assistants API、Bedrock Agents）用 CLIENT；进程内框架（LangChain、CrewAI、本地 ReAct）用 INTERNAL

**Q3.** 关于 prompt/回复内容的捕获，讲义的规则是：

- A. 默认不捕获，需显式 opt-in；生产中推荐把内容存到外部存储，span 上只记录引用 ID
- B. 默认全部内联捕获，便于调试
- C. 只捕获 system prompt，不捕获用户消息
- D. 内容捕获由后端（如 Datadog）决定，与 instrumentation 无关

**Q4.** 某请求发往 `gpt-x`，被网关路由到了 `gpt-x-2026-01` 实际执行。应在哪个属性中记录"实际使用的模型"？

- A. `gen_ai.request.model`
- B. `gen_ai.agent.name`
- C. `gen_ai.response.model`
- D. `gen_ai.provider.name`

**Q5.** 运行本节 `main.py`，输出的 span 树中一共有几个 `tool_call search_tool` span？

- A. 0 个
- B. 1 个
- C. 3 个
- D. 6 个

**Q6.** `main.py` 中 `Tracer(capture_inline=False)`，第一个 `chat` span 的属性里与输入内容有关的是：

- A. `gen_ai.input.messages = 'turn 0: next action please'`
- B. 没有任何与输入相关的属性
- C. `gen_ai.input.messages = '[REDACTED]'`
- D. `gen_ai.input.messages.reference_id = 'content_001'`，正文在外部存储里

**Q7.** 在 trace 后端里看到大量没有父 span 的 tool span（"孤儿 span"），最可能的原因是：

- A. 没有设置 `gen_ai.provider.name`
- B. 创建 tool span 时没有使用/传播当前的活动上下文（父 span），跨线程或跨进程时尤其常见
- C. 内容捕获开得太多
- D. 采样率设置为 100%

**Q8.** 讲义建议设置哪个环境变量来选用最新的（实验性）GenAI 约定，避免后端升级时属性名发生变化带来的意外？

- A. `OTEL_TRACES_SAMPLER=always_on`
- B. `OTEL_GENAI_CAPTURE_CONTENT=false`
- C. `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`
- D. `OTEL_EXPORTER_OTLP_ENDPOINT=gen_ai`

---

## 三、动手 / 代码题

**Q9.** 讲义说本节脚本会产生"per-tool spans"，但实际输出只有 3 个 `chat` span。相关代码：

```python
def _scripted_llm(prompt: str) -> str:
    if "search" in prompt.lower():
        return "search_tool(\"agent engineering\")"
    if "result" in prompt.lower():
        return "found 3 sources; drafting answer"
    return "final answer: agents in 2026"
...
    for turn in range(3):
        ...
        prompt = f"turn {turn}: next action please"
        ...
        output = _scripted_llm(prompt)
        ...
        if "search_tool" in output:
            tool_span = tracer.start_span("tool_call search_tool", ...)
```

1. 解释为什么 tool span 一次都没有出现。
2. 这个循环还有什么不像真实 agent loop 的地方？
3. 修改驱动部分，使 span 树变成 `invoke_agent → [chat, tool_call search_tool, chat, chat]`。

**Q10.** 文件开头的 docstring 写着"Content capture is opt-in"。
1. 对照 `Tracer.add_content`，说明代码里实际有几种捕获模式，"opt-in"是否成立。
2. 实现一个三档策略：`off`（默认，什么正文都不记）、`reference`（外存 + 引用 ID）、`inline`（内联，仅限开发环境），并通过环境变量选择。

**Q11.** `Tracer` 用一个栈维护父子关系：

```python
    def start_span(self, name, kind="INTERNAL", attributes=None) -> Span:
        span = Span(name=name, kind=kind, attributes=dict(attributes or {}),
                    start_ns=time.perf_counter_ns())
        self.stack[-1].children.append(span)
        self.stack.append(span)
        return span

    def end_span(self) -> None:
        span = self.stack.pop()
        span.end_ns = time.perf_counter_ns()
```

1. 若 tool 执行中抛出异常、`end_span` 没被调用，接下来新开的 span 会挂在哪里？
2. 若 `end_span` 被多调用一次，会发生什么？
3. 用上下文管理器改写，保证异常时也能正确结束 span，并记录错误信息；再生成一个 W3C `traceparent` 字符串用于跨进程传播。

**Q12.** 对照讲义（以及 OTel GenAI 规范），审阅 `main.py` 产生的 span，列出至少四处与约定不符或不利于生产使用的地方，并说明怎么改。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 OpenTelemetry GenAI 语义约定？它解决了什么问题？一个 agent 运行的标准 span 树长什么样？

**Q14.**（原理深挖）为什么规范要求"默认不捕获 prompt/回复内容"？"外存 + 引用"模式具体怎么做，它和 prompt injection 防御有什么关系？

**Q15.**（工程实践）你的 agent 由 Python 编排进程调用一个 CLI 子进程（例如 Claude Agent SDK 启动的 CLI），子进程里又调用工具。如何让整条链路出现在**同一个** trace 中？

**Q16.**（场景设计）团队同时使用 Anthropic、OpenAI 与 Bedrock 三家模型，老板想要一个看板回答"哪些工具错误和哪些模型相关、每个 agent 的成本和延迟分布"。你会怎样设计 span 与属性？

**Q17.**（追问型）规范大部分还是 experimental，你怎么保证升级 SDK 或 collector 之后看板不坏？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 Span categories：1) Model/client spans（raw LLM calls，由 provider SDK 与框架模型适配器产生）；2) Agent spans（`create_agent`、`invoke_agent`）；3) Tool spans（one per tool invocation，以父子关系连到 agent span）。A 是通用后端 span 的分类；C 是凭空的划分；D 是 OTel 的 span kind，而不是 GenAI 的 span 类别——kind 与类别是两个正交的维度。

### Q2 — 答案：D

讲义："CLIENT — for remote agent services (OpenAI Assistants API, Bedrock Agents). INTERNAL — for in-process agent frameworks (LangChain, CrewAI, local ReAct)." B 恰好说反；A 中 SERVER 是"服务端收到请求"的视角，不适用于调用方记录的 agent span；C 错，kind 决定了后端如何理解调用关系（是否跨进程、是否计入服务依赖图）。

### Q3 — 答案：A

讲义："instrumentations SHOULD NOT capture inputs/outputs by default. Capture is opt-in"；"Recommended production pattern: store content externally (S3, your log store), record references on spans (pointer IDs, not prose)." B 违反默认规则，也是讲义"Capturing full prompts in spans"失败模式；C 无依据（`gen_ai.system_instructions` 同样是 opt-in）；D 错，是否采集发生在 instrumentation 侧，数据一旦发出，后端只能被动接收。

### Q4 — 答案：C

讲义："`gen_ai.response.model` — the resolved model (may differ from request due to routing)." A 记录的是请求时指定的模型；B 是 agent 名；D 是 provider（如 `openai`）。两个都记录才能回答"请求的是什么、实际跑的是什么"，排查路由/降级问题时非常关键。

### Q5 — 答案：A

实际运行输出中没有任何 tool span。三轮的 prompt 都是 `"turn N: next action please"`，既不含 `search` 也不含 `result`，`_scripted_llm` 三次都返回 `"final answer: agents in 2026"`，`if "search_tool" in output` 永远为假。详见 Q9。

### Q6 — 答案：D

`capture_inline=False` 时 `add_content` 把正文 `put` 进 `ExternalContentStore`，在 span 上写 `f"{key}.reference_id"`。实际输出：`gen_ai.input.messages.reference_id = 'content_001'`，正文 `turn 0: next action please` 出现在"external content store"部分。A 是 `capture_inline=True` 时的行为；B、C 都不是本代码会产生的结果（本代码没有"完全不捕获"模式，见 Q10）。

### Q7 — 答案：B

讲义："Spans without parent links. Orphaned tool spans. Always propagate context." 父子关系依赖"当前活动上下文"：在线程池、异步任务或子进程里执行工具时，若没有把上下文带过去，新 span 就会成为新 trace 的根。A 导致的是多 provider 看板归属错误；C 是隐私问题；D 只影响数据量。

### Q8 — 答案：C

讲义："Opt in ... with `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`"，并把"Not setting stability opt-in. Your attributes may get renamed on backend upgrade"列为失败模式。A 是采样器配置；B、D 不是讲义提到的变量。补充说明：从该变量的名字看，它的含义是让 instrumentation 发出"最新的实验版"约定，而不是把属性名永久冻结；规范演进时仍需关注变更（见 Q17）。

### Q9 — 参考答案

1. **原因**：`_scripted_llm` 只根据 prompt 中是否含 `search` / `result` 决定输出，而驱动循环生成的 prompt 固定是 `"turn {turn}: next action please"`，与上一轮输出无关。三轮都落到默认分支 `"final answer: agents in 2026"`，所以从未触发工具调用。这是一个"演示脚本自己没跑到想展示的路径"的 bug，讲义的"per-tool spans"和代码中 `gen_ai.data_source.id` 的用法都没有出现在输出里。
2. **不像真实 agent loop 的地方**：
   - prompt 不包含历史（上一轮输出、工具结果），模型"看不到"任何上下文；
   - 拿到 `final answer` 之后不会停止，还会继续跑满 3 轮；
   - 工具调用的参数是写死的 `"agent engineering"`，没有从模型输出中解析。
3. 修改后的驱动（已运行验证）：

```python
prompts = ["please search for sources", "tool result: 3 sources", "write the final answer"]
for p in prompts:
    chat = tracer.start_span("chat", attributes={...})
    tracer.add_content(chat, "gen_ai.input.messages", p)
    out = _scripted_llm(p)
    tracer.add_content(chat, "gen_ai.output.messages", out)
    tracer.end_span()
    if "search_tool" in out:
        ts = tracer.start_span("tool_call search_tool", attributes={...})
        tracer.add_content(ts, "gen_ai.tool.result", _search_tool("agent engineering"))
        tracer.end_span()
```

三轮输出依次为 `search_tool("agent engineering")`、`found 3 sources; drafting answer`、`final answer: agents in 2026`，`invoke_agent` 的子 span 为 `['chat', 'tool_call search_tool', 'chat', 'chat']`。更真实的写法是把上一轮输出/工具结果拼进下一轮 prompt，并在出现 `final answer` 时 `break`。

### Q10 — 参考答案

1. 代码只有**两种**模式：`capture_inline=True` 内联（截断到 200 字符），`capture_inline=False` 外存 + 引用。**两种模式都会记录正文**——只是位置不同。没有"不捕获"选项，所以"opt-in"并不成立：默认构造的 `Tracer()` 就会把每一条 prompt 和回复存进外部存储。外存比内联安全（访问控制可以分开），但规范说的是"默认不捕获"，应该是三档。
2. 参考实现（已运行验证）：

```python
import os

class PolicyTracer(Tracer):
    MODES = ("off", "reference", "inline")

    def __init__(self, mode=None, **kw):
        mode = mode or os.environ.get("GENAI_CAPTURE_MODE", "off")   # 默认关闭
        if mode not in self.MODES:
            raise ValueError(f"bad capture mode {mode!r}")
        super().__init__(capture_inline=(mode == "inline"), **kw)
        self.mode = mode

    def add_content(self, span, key, content):
        if self.mode == "off":
            span.attributes[f"{key}.length"] = len(content)   # 只留非敏感的元数据
            return
        super().add_content(span, key, content)
```

对内容 `"my SSN is 123-45-6789"` 的实测结果：

| 模式 | span 属性 | 外部存储 |
|------|----------|---------|
| `off` | `gen_ai.input.messages.length = 21` | 空 |
| `reference` | `gen_ai.input.messages.reference_id = 'content_001'` | 有正文 |
| `inline` | `gen_ai.input.messages = 'my SSN is ...'` | 空 |

说明：`*.length` 是为演示自定义的属性，不是规范字段；环境变量名 `GENAI_CAPTURE_MODE` 也是自定义的，实际 SDK 各有自己的开关。skill 文件要求：有 HIPAA/GDPR 约束的产品**拒绝**内联捕获，只允许带访问控制的外部存储；未知模式要报错而不是悄悄回退到某个模式。

### Q11 — 参考答案

1. **异常导致栈失衡**：span `x` 没有出栈，之后开的 `y` 会被当成 `x` 的子 span（实测 `root.children == ['x']`，`x.children == ['y']`），而且 `x` 的 `end_ns` 永远是 0，渲染时显示 `...`。整棵树从此错位。
2. **多调用一次 `end_span`**：会把哨兵 `__root__` 也弹出，栈变空；下一次 `start_span` 访问 `self.stack[-1]` 抛 `IndexError: list index out of range`（已实测）。
3. 用 `contextlib.contextmanager` + `try/finally`（已运行验证）：

```python
import secrets
from contextlib import contextmanager

class SafeTracer(Tracer):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.trace_id = secrets.token_hex(16)            # 32 位十六进制

    @contextmanager
    def span(self, name, kind="INTERNAL", attributes=None):
        s = self.start_span(name, kind, attributes)
        s.attributes["span_id"] = secrets.token_hex(8)   # 16 位十六进制
        try:
            yield s
        except Exception as e:
            s.attributes["error.type"] = type(e).__name__
            s.attributes["status"] = "ERROR"
            raise                                        # 记录后继续抛出
        finally:
            self.end_span()                              # 无论如何都出栈

    def traceparent(self, span):
        return f"00-{self.trace_id}-{span.attributes['span_id']}-01"
```

测试：在 `with t.span("invoke_agent bot")` 内部的工具 span 抛出 `TimeoutError`，之后新开的 `invoke_agent bot2` 正确成为根的第二个孩子，栈深度回到 1；工具 span 上有 `error.type = 'TimeoutError'`。`traceparent` 形如 `00-378ede16...54ff-a205e8edaac6b63c-01`（版本-trace id-父 span id-flags），通过 HTTP 头或环境变量传给子进程，子进程用它作为父上下文。真实 OTel SDK 的 `tracer.start_as_current_span(...)` 就是这样的上下文管理器，并用 contextvars 保存"当前 span"，在 asyncio 任务间也能正确传递。

### Q12 — 参考答案

| # | 问题 | 怎么改 |
|---|------|-------|
| 1 | 演示里没有 tool span（Q9） | 修驱动脚本，让工具路径真正被执行 |
| 2 | 没有"关闭"捕获模式，默认就记录正文（Q10） | 三档策略，默认 `off` |
| 3 | span 没有 trace id / span id / parent id，无法导出、无法跨进程拼接 | 使用 OTel SDK，或至少生成 W3C trace context（Q11） |
| 4 | `chat` span 用默认 kind `INTERNAL`，但它代表对 Anthropic API 的**远程**调用 | 远程模型调用应标 `CLIENT`（与讲义"远程服务用 CLIENT"的原则一致） |
| 5 | 异常时栈失衡、无错误状态（Q11） | 上下文管理器 + `error.type` / 状态 |
| 6 | tool span 没有 `gen_ai.provider.name` 等归属信息，`create_agent` 与 `invoke_agent` 是两个互不相关的根 span | 在 agent span 上设置必需属性，tool span 通过父链继承归属；按需用 span link 关联"创建"与"运行" |
| 7 | `ExternalContentStore.items()` 按字符串排序，超过 999 条后 `content_1000` 会排在 `content_100` 与 `content_101` 之间（实测） | 按插入顺序或数值排序；生产中用 UUID 作为引用 ID |
| 8 | 内联模式静默截断到 200 字符 | 截断时显式标注（如加 `*.truncated = True`），或干脆只用外存 |

补充（以 OTel 官方规范为准，规范仍在演进）：据笔者了解，规范中工具执行 span 的 `gen_ai.operation.name` 是 `execute_tool`、span 名为 `execute_tool {gen_ai.tool.name}`，推理 span 名一般为 `{operation} {model}`（如 `chat claude-...`）；讲义与代码使用的 `tool_call` 与之不同。落地时请对照你所用 SDK 版本对应的规范页面。

### Q13 — 参考回答要点

- **定义**：OTel 的 GenAI SIG 制定的一组 span 名、属性名与内容捕获规则，让 LLM/agent 遥测在不同框架和不同后端之间语义一致。
- **解决的问题**：此前每个框架自定义 span 名和字段，换框架或多框架并存时必须为每个框架单独做看板；有了标准，Datadog、Grafana、Jaeger、Honeycomb 等后端可以直接理解这些属性（讲义：Datadog v1.37+ 原生映射）。
- **标准 span 树**：

```text
invoke_agent research_bot   [INTERNAL，进程内框架]
├── chat <model>            [CLIENT，远程模型调用]  provider / request.model / response.model
├── <tool span> search      [INTERNAL]            tool.name / data_source.id
└── chat <model>
```

- **关键属性**：`gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.agent.name`、`gen_ai.operation.name`、`gen_ai.data_source.id`。
- 加分点：说明 kind（CLIENT/INTERNAL）与类别是两个维度；说明 `create_agent` 与 `invoke_agent` 的区别。

### Q14 — 参考回答要点

- **为什么默认不捕获**：prompt 和回复里经常有 PII、密钥、客户数据；trace 系统的访问权限通常比业务数据库宽得多（"traces that ops can read"），保留期和复制范围也不受业务控制；一旦写进 span 就很难删除（合规上的"被遗忘权"）。
- **外存 + 引用怎么做**：
  1. 正文写入有访问控制、有保留策略、可删除的存储（S3、日志库、数据库），得到一个 ID；
  2. span 上只写 `*.reference_id`（或 URI）；
  3. 有权限的人在调试时按 ID 取回正文；
  4. 可以对外存内容单独做脱敏、加密和审计。
- **与 prompt injection 的关系**：讲义称之为"the Lesson 27 content-poisoning defense wired into observability"。检索内容、工具输出可能含恶意载荷，若直接内联进 trace，会被下游读取 trace 的系统（如自动分析 trace 的 LLM、看板渲染）当作数据处理，造成二次注入或泄露；外存后，trace 中只有不可执行的指针，内容的读取路径单独受控。
- 常见误区：以为"截断到 200 字符"就安全了——前 200 字符里照样可以有身份证号。

### Q15 — 参考回答要点

- **核心**：W3C trace context。父进程在调用子进程前，把当前 span 的上下文序列化为 `traceparent`（`00-<trace_id>-<span_id>-<flags>`，必要时加 `tracestate`），通过环境变量、命令行参数或 HTTP 头传给子进程；子进程用 propagator 解析出父上下文，以它为父创建自己的 span。
- 讲义 Further Reading 提到 Claude Agent SDK 支持 W3C trace context propagation；skill 文件把"运行时无法跨进程传播上下文"列为拒绝上线的条件。
- **同进程内**：使用 SDK 的"当前 span"机制（contextvars），在线程池/异步任务中显式传递上下文，避免孤儿 span。
- **验证**：在后端按 trace id 查询，确认编排进程的 `invoke_agent`、子进程中的 `chat` 与工具 span 在一棵树上，时间轴连续。
- 加分点：说明采样决策（flags）也要一起传递，否则父子采样不一致会出现"断树"。

### Q16 — 参考回答要点

- **span 设计**：每次 agent 运行一个 `invoke_agent {agent.name}`；每次模型调用一个推理 span；每次工具调用一个 tool span，挂在对应 agent span 下（必要时也可挂在触发它的推理 span 之后）。
- **必需属性**：
  - 推理 span：`gen_ai.provider.name`（`anthropic` / `openai` / `aws.bedrock`）、`gen_ai.request.model`、`gen_ai.response.model`、token 用量；
  - tool span：`gen_ai.tool.name`、错误类型（`error.type`）、RAG 时的 `gen_ai.data_source.id`；
  - agent span：`gen_ai.agent.name`。
- **看板查询**：
  - "工具错误 × 模型"：以 tool span 为行，沿父链关联到同一 agent 运行中的推理 span，按 `response.model` × `tool.name` 统计错误率（讲义练习 5）；
  - 成本：按 provider/model 汇总 token 用量 × 单价；
  - 延迟：按 agent.name 统计 `invoke_agent` 的 P50/P95，并拆分到推理与工具耗时。
- 关键前提：讲义强调"No `gen_ai.provider.name`. Multi-provider dashboards break."；父子链接必须完整，否则无法关联。
- 加分点：内容默认不捕获，看板只依赖属性；把 provider/model 作为低基数维度，避免把 prompt 文本当维度。

### Q17 — 参考回答要点

- **固定约定版本**：在 instrumentation 侧显式设置 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`（讲义建议），并锁定 SDK/instrumentation 版本，升级作为有计划的变更。
- **在 collector 层做映射**：用 collector 的属性处理器把新旧属性名互相映射（例如过渡期同时保留两套名字），看板只依赖映射后的稳定字段。
- **契约测试**：在 CI 中跑一个固定的 agent 场景，断言导出的 span 名与属性集合（类似本节代码的 render 输出做快照测试），升级后若变化立即报警。
- **看板引用集中定义**：属性名集中在一个常量模块/查询模板里，改名时只改一处。
- **关注变更日志**：规范仍在演进，讲义自身的属性列表也可能与最新规范不同（见 Q12），升级前对照官方 changelog。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：span 树的骨架就是 agent loop 的每一轮。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：tool span 对应的工具调用。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：讲义列出的前置课。
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../../13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md)：从工具/协议角度看同一套约定。

### 本节被哪些后续内容用到
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：把 GenAI span 送进可观测平台。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：内容外存与 content poisoning 防御。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：跨进程 trace context 传播。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：生产可观测栈。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../../19-capstone-projects/28-observability-otel-traces/docs/zh.md)：综合项目中的完整实现。

### 延伸关键词
`OpenTelemetry` · `semantic conventions` · `GenAI SIG` · `invoke_agent` · `span kind CLIENT / INTERNAL` · `gen_ai.provider.name` · `gen_ai.response.model` · `content capture opt-in` · `OTEL_SEMCONV_STABILITY_OPT_IN` · `W3C traceparent` · `context propagation` · `OTel Collector`
