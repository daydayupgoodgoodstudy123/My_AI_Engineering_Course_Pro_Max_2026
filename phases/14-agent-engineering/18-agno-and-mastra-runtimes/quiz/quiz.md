# 测验 · 生产级 Agent 运行时：快速实例化与类型化工作流（Production Agent Runtimes — Fast Instantiation and Typed Workflows）

> **阶段 14 · Agent 工程 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（TypeScript 对照版：[code/main.ts](../code/main.ts)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生产运行时关心什么 | 原型框架忽略的东西：实例化成本、类型化的 workflow 接口、可直接上线的服务端 |
| 2 | Agno 定位 | Python 运行时（前身 Phi-data），"No graphs, chains, or convoluted patterns — just pure python." |
| 3 | Agno 性能目标 | 讲义引用其文档：约 2μs 实例化一个 agent、每个 agent 约 3.75 KiB 内存、约 23 个模型提供方 |
| 4 | Agno 生产路径 | 无状态、按会话作用域的 FastAPI 后端：每个请求新建 agent，会话状态存在数据库里 |
| 5 | 速度何时重要 | 每秒成千上万个短命 agent（聊天汇聚、评测流水线）时重要；一个 agent 跑 10 分钟时几乎无关 |
| 6 | Mastra 三原语 | TypeScript、基于 Vercel AI SDK；Agents、Tools（Zod 类型化）、Workflows |
| 7 | Mastra 周边 | Unified Model Router（讲义：2026 年 3 月 3,300+ 模型、94 家提供方）；composite storage（memory / workflows / observability 分存，可观测性大规模时推荐 ClickHouse）；Express/Hono/Fastify/Koa 适配器；Mastra Studio（localhost:4111） |
| 8 | Mastra 许可证 | 主体 Apache 2.0，`ee/` 目录是 source-available 的企业许可，不是开源许可 |
| 9 | 选型主轴 | 语言契合（Python-first 选 Agno，TypeScript-first 选 Mastra）、运行时人体工学、可观测性；要持久状态与显式图选 LangGraph |
| 10 | 三个坑 | perf-for-perf's-sake（瓶颈不在实例化）、生态锁定（Vercel 风格集成）、企业许可证混淆 |

### 核心技能（能动手做到）

- [ ] 复述 Agno 与 Mastra 的关键数字与定位，并对一个给定技术栈给出选型理由
- [ ] 解释"无状态、会话作用域"的后端为什么易于水平扩展，以及它把压力转移到了哪里
- [ ] 读懂 `main.py` 的 Agno 形状 handler 与 Mastra 形状 agent/workflow，指出它们与讲义描述不一致的地方
- [ ] 把 handler 改成"每请求新建 agent + 从会话加载历史"的真正无状态形状
- [ ] 为 Python 版 `MastraTool` 补上 schema 校验（参照 `main.ts` 的 `checkSchema`）
- [ ] 用一次 LLM 调用耗时估算"实例化开销占比"，判断 2μs 对你的工作负载是否重要

---

## 二、基础自测（选择题）

**Q1.** 讲义引用的 Agno 性能目标是：

- A. 约 2 ms 实例化、约 3.75 MiB 内存、约 94 个模型提供方
- B. 约 2μs 实例化、每个 agent 约 3.75 KiB 内存、约 23 个模型提供方
- C. 约 200 ms 实例化、约 100 MiB 内存
- D. 讲义没有给出任何数字

**Q2.** 讲义推荐的 Agno 生产部署形态是：

- A. 一个长期驻留、在内存中保存所有会话的有状态守护进程
- B. 只能以定时任务（cron）方式运行
- C. 只支持 WebSocket 的服务器
- D. 无状态、按会话作用域的 FastAPI 后端：每个请求新建 agent，会话状态存在数据库

**Q3.** Mastra 的三个原语是：

- A. Agents、Tools（Zod 类型化）、Workflows
- B. Node、Edge、State
- C. Actor、Message、Inbox
- D. Planner、Executor、Critic

**Q4.** 讲义对 Mastra Unified Model Router 的描述是：

- A. 一个向量数据库层
- B. 一个 graph checkpointer
- C. 一个统一客户端，覆盖 94 家提供方的 3,300+ 模型（2026 年 3 月）
- D. 一个工具调用队列

**Q5.** 关于 Mastra 的许可证，正确的是：

- A. 整个仓库都是 GPL
- B. 没有许可证文件，可以随意使用
- C. 整个仓库都是 Apache 2.0，包括 `ee/` 目录
- D. 主体是 Apache 2.0，但 `ee/` 目录采用 source-available 的企业许可，fork 前需要阅读条款

**Q6.** 运行 `code/main.py`，Agno 部分打印 `session history length: 6`。原因是：

- A. 3 次请求，每次 handler 都向会话追加 `user:` 和 `assistant:` 两条
- B. 每次请求新建一个 agent，共 6 个 agent
- C. FastAPI 自动记录了 6 条日志
- D. 会话里存了 3 条用户消息和 3 个 handler 耗时

**Q7.** 按讲义，Agno 的微秒级实例化在什么情况下最有意义？

- A. 每个请求只有一次耗时数秒的 LLM 调用
- B. 单个 agent 连续运行 10 分钟
- C. 每秒有成千上万个短命 agent，例如聊天汇聚或评测流水线
- D. 只在 GPU 推理时有意义

**Q8.** 关于 `main.py` 的 Python 实现，下列说法正确的是：

- A. `MastraAgent.run` 会调用一次模拟 LLM，把工具结果组合成最终回答
- B. `MastraTool.input_schema` 只是被存储，从未用于校验；传 `{"query": 123}` 也会被正常执行
- C. Agno handler 每次请求都新建一个 `AgnoAgent`
- D. 两种形状都实现了流式输出

---

## 三、动手 / 代码题

**Q9.** `main.py` 打印 `pattern: a fresh agent per request; session holds state; FastAPI is stateless.`，相关代码如下：

```python
    session = AgnoSession()
    agent = AgnoAgent(name="agno_a", fn=_agno_agent_fn)
    for i in range(3):
        out = agno_request_handler(session, agent, "s001",
                                   f"query {i}: how do I ship an agent")
```

```python
def agno_request_handler(session, agent, session_id, prompt):
    start = time.perf_counter_ns()
    session.append(session_id, f"user: {prompt}")
    output = agent.run(prompt)
    session.append(session_id, f"assistant: {output}")
    ...
```

1. 代码与打印的 pattern 有哪两处不一致？（提示：agent 在哪里创建？agent 看到了历史吗？）
2. 改写 `agno_request_handler`：每个请求内新建 agent，从 session 加载历史并交给 agent，再追加本轮。函数签名改为接收一个 `make_agent` 工厂。
3. 这样改之后，"同一会话的两个请求同时到达"会出现什么问题？生产中如何处理？

**Q10.** `main.ts` 中有一个 `checkSchema`，Python 版却没有：

```typescript
function checkSchema(schema: ToolInputSchema, input: ToolInput): string | null {
  for (const [key, expected] of Object.entries(schema)) {
    if (!(key in input)) return `missing field ${key}`;
    if (typeof input[key] !== expected) return `field ${key}: expected ${expected}, got ${typeof input[key]}`;
  }
  return null;
}
```

1. 在 Python 版中调用 `mastra_agent.run("p", [("search", {"q": "x"})])` 会发生什么？`[("search", {"query": 123})]` 呢？
2. 为 Python 版写一个 `check_schema(schema, args)`，支持 `main.py` 中 JSON Schema 风格的 `{"type": "object", "properties": {"query": {"type": "string"}}}`，并接入 `MastraAgent.run`，同时捕获工具异常。
3. 讲义说 Mastra 的 Tools 是 "Zod-typed"。相比运行时手写校验，Zod 多带来了什么？

**Q11.**（计算题，对应讲义练习 3）设一次 LLM 调用耗时 1.5 s。比较"实例化 2μs 的运行时"和"实例化 20 ms 的重型框架"：

1. 对"每请求一个 agent、一次 LLM 调用"的工作负载，实例化开销各占请求总耗时的百分之几？
2. 一个评测流水线要创建 100 万个 agent，其中绝大部分命中缓存、不调用 LLM。两种运行时仅实例化就分别要多少 CPU 时间？
3. 同时存活 10,000 个 agent，按讲义 3.75 KiB/agent，内存约多少 MiB？
4. 我们在本机测得 `main.py` 中 `AgnoAgent(...)` 的实例化约 0.07μs、约 142 字节。为什么这个数字不能用来"验证"或"反驳"Agno 的 2μs？

**Q12.** 讲义 "Build It" 说 `main.py` 是"a minimal 'run an agent, stream the output, persist session' flow implemented twice ... Two structurally different but functionally equivalent traces."

1. 对照 `main.py`，列出这段描述与代码不符之处（至少三处）。
2. `main.ts` 在哪些方面比 `main.py` 更接近讲义？
3. 给 Agno 形状的 handler 增加"流式输出"：用 Python 生成器逐块 `yield` 输出，流结束后才把完整回复写入 session。写出代码骨架，并说明为什么"流结束后才持久化"。

---

## 四、面试高频题

**Q13.**（基础必考）Agno 和 Mastra 分别是什么？各自适合什么团队与场景？和 LangGraph、OpenAI/Claude 的 Agent SDK 怎么取舍？

**Q14.**（原理深挖）为什么"无状态、会话作用域"的后端是 Agno 推荐的生产路径？它解决了什么问题，又把压力转移到了哪里？

**Q15.**（工程实践）团队有人主张"换 Agno，因为它实例化只要 2μs"。你如何用数据评估这个提议？

**Q16.**（场景设计）一个 Next.js + Vercel 部署的 SaaS 要接入多家模型提供方、做带审批步骤的多步流程，并要求可观测性。请给出运行时选型和存储架构。

**Q17.**（追问型）选择 Mastra 时，许可证和生态锁定要注意什么？如果你们是 Python 单仓，为什么不该随手引入一个 TypeScript 运行时？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Performance targets from their docs: ~2μs agent instantiation, ~3.75 KiB memory per agent, ~23 model providers." A 把单位放大了 1000 倍，并把 Mastra 的 "94 providers" 混了进来；C 是重型框架的量级；D 错。注意这些是**厂商文档中的目标值**，`outputs/skill-runtime-picker.md` 提醒："framework vendor benchmarks are directional."

### Q2 — 答案：D

讲义："Production path: stateless session-scoped FastAPI backend. Each request starts a fresh agent; session state lives in a DB." A 恰好相反——状态在进程内存里会让水平扩展和故障恢复变难；B、C 与讲义无关。

### Q3 — 答案：A

讲义："Three primitives: Agents, Tools (Zod-typed), Workflows." B 是 LangGraph 的概念（第 13 节），C 是 AutoGen 的 actor 模型（第 14 节），D 是 Plan-and-Execute / Reflexion 一类模式的角色。

### Q4 — 答案：C

讲义："Unified Model Router — 3,300+ models across 94 providers (March 2026)." Key Terms 解释为 "Single client for 3,300+ models across 94 providers"。A、B、D 都不是 Router 的职责；checkpointer 是 LangGraph 的概念。

### Q5 — 答案：D

讲义："Apache 2.0 with `ee/` directories under source-available enterprise license." 以及 "Mastra's `ee/` directories are source-available, not Apache 2.0. Read the licenses if you're planning to fork." Key Terms："License permits source reading but restricts commercial use." C 是最常见的误解。

### Q6 — 答案：A

`agno_request_handler` 每次调用两次 `session.append`：一次 `user: ...`，一次 `assistant: ...`。3 次请求 × 2 = 6。B 错：代码只创建了一个 `AgnoAgent` 并在循环中复用（见 Q9）；C 错：没有 FastAPI；D 错：耗时只拼进了返回字符串，没有写入 session。

### Q7 — 答案：C

讲义："The speed targets matter when you have thousands of short-lived agents per second (chat fan-in, evaluation pipelines). They matter less when one agent runs for 10 minutes." A 正是讲义说的 "Perf-for-perf's-sake" 反例；B 被讲义直接点名；D 无依据。

### Q8 — 答案：B

已实际验证：`ma.run("p", [("search", {"query": 123})])` （与一个未知工具 `nope` 一起调用）返回 `('m processed 2 tools', [('nope', 'error: unknown'), ('search', '[mastra search result for 123]')])`，`input_schema` 从未被读取。A 描述的是 `main.ts` 的行为（`mockLLM` 最终步骤），Python 版只返回固定的 `"mastra_a processed 2 tools"`；C 错（见 Q6）；D 错，两种形状都没有流式输出，尽管讲义 "Build It" 提到了 "stream the output"。

### Q9 — 参考答案

1. 两处不一致：
   - **agent 不是每请求新建**：`agent` 在循环外创建一次，三次请求复用同一个对象；
   - **会话状态没有被使用**：handler 把对话写进 session，但 `agent.run(prompt)` 只拿到当前 prompt，从不读取 `session.history(...)`。这只是"写日志"，不是"会话状态驱动 agent"。Agno 推荐路径的关键在于：agent 是无状态的，**每次请求都从 DB 恢复上下文**。
2. 参考实现（已在本地运行验证，第 3 次请求时 agent 能看到前 4 条历史）：

```python
def agno_request_handler(session, make_agent, session_id, prompt):
    start = time.perf_counter_ns()
    agent = make_agent()                         # 每个请求新建 agent（廉价）
    history = session.history(session_id)       # 从"数据库"加载状态
    output = agent.run(prompt, history)          # 状态显式传入
    session.append(session_id, f"user: {prompt}")
    session.append(session_id, f"assistant: {output}")
    elapsed_us = (time.perf_counter_ns() - start) / 1000
    return f"{output}  (handler {elapsed_us:.1f} us)"

# 调用方
make_agent = lambda: AgnoAgent(name="agno_a",
                               fn=lambda p, h: f"[agno reply, {len(h)} prior turns] {p[:40]}")
```

（需要把 `AgnoAgent.fn` 的签名改成 `Callable[[str, list[str]], str]`。）把 `user` 与 `assistant` 放在成功生成之后一起写入，可以避免生成失败时留下"只有问没有答"的半截记录。

3. 两个请求会读到同一份历史，各自生成回答后都追加，导致两轮交错、彼此看不到对方——典型的"读—改—写"竞态。处理方式：同一会话串行化（按 session_id 加分布式锁或单分区队列）；或者使用带版本号的乐观并发（写入时检查版本，冲突则重试）；在前端层面禁止同一会话并发提交。

### Q10 — 参考答案

1. 已验证：
   - `{"q": "x"}`：`tool.fn(**args)` 抛出 `TypeError: _mastra_tool_fn() got an unexpected keyword argument 'q'`，`MastraAgent.run` 没有 `try`，异常直接冒泡，整个 agent 运行失败；
   - `{"query": 123}`：被正常执行，结果是 `[mastra search result for 123]`——类型错误被静默放过。
2. 参考实现：

```python
_PY_TYPES = {"string": str, "number": (int, float), "boolean": bool, "integer": int}

def check_schema(schema: dict, args: dict) -> str | None:
    props = schema.get("properties", {})
    required = schema.get("required", list(props))      # 示例 schema 没写 required，默认全部必填
    for key in required:
        if key not in args:
            return f"missing field {key}"
    for key, value in args.items():
        if key not in props:
            return f"unexpected field {key}"
        expected = _PY_TYPES[props[key]["type"]]
        if isinstance(value, bool) and expected is not bool:   # bool 是 int 的子类
            return f"field {key}: expected {props[key]['type']}, got bool"
        if not isinstance(value, expected):
            return f"field {key}: expected {props[key]['type']}, got {type(value).__name__}"
    return None

# MastraAgent.run 中
            err = check_schema(tool.input_schema, args)
            if err:
                trace.append((tool_name, f"error: {err}"))
                continue
            try:
                result = tool.fn(**args)
            except Exception as e:
                result = f"error: {type(e).__name__}: {e}"
            trace.append((tool_name, result))
```

要点：缺字段、多字段、类型错误都返回结构化错误给模型（让它修正参数重试），而不是让运行崩溃；注意 Python 中 `bool` 是 `int` 的子类。生产中可直接用 `jsonschema` 或 Pydantic。

3. Zod 同时提供**运行时校验**与**编译期类型推导**：一份 schema 既能在运行时拒绝模型生成的错误参数，又能让 `execute(input)` 中的 `input` 自动获得精确的 TypeScript 类型，避免 schema 与类型定义两处维护不一致；它还能导出 JSON Schema 交给模型作为工具定义。讲义练习 2 正是让你对比 "Zod vs nothing"。

### Q11 — 参考答案

（已用 Python 计算）

1. 每请求一次 1.5 s 的 LLM 调用：
   - 2μs：`2e-6 / 1.5 ≈ 0.00013%`；
   - 20 ms：`0.02 / 1.5 ≈ 1.33%`。
   两者都远小于 LLM 调用本身——讲义的 "Overhead is not the bottleneck"。
2. 100 万个 agent：
   - 2μs × 1e6 = **2 s**；
   - 20 ms × 1e6 = 20,000 s ≈ **5.56 小时**。
   在评测流水线、聊天汇聚这类"大量短命 agent、LLM 调用被缓存或很少"的场景，差异是数量级的——这就是讲义说速度目标"matter"的场景。
3. `10,000 × 3.75 KiB = 37,500 KiB ≈ 36.6 MiB`。
4. 本机测得的 0.07μs、142 字节，测的是一个只有 `name` 和 `fn` 两个字段的玩具 dataclass；真实 Agno agent 还要初始化模型配置、工具、记忆、存储等组件，二者不是同一个对象。而且 2μs 是厂商在自己基准上的目标值，正确做法是讲义练习 3："measure agent instantiation latency on your stack"——在你的硬件、你的 agent 配置、你的请求路径上测量，并与 LLM 调用耗时放在一起看占比。

### Q12 — 参考答案

1. 与讲义不符之处：
   - **没有流式输出**：两种形状都是一次性返回字符串；
   - **Mastra 形状没有持久化会话**：只有 Agno 形状写了 `AgnoSession`；
   - **不是"功能等价"**：Agno 部分是回声式回复 3 个请求，Mastra 部分是执行 2 次工具 + 一个 workflow，输入、步骤、输出都不同；
   - Mastra agent 的 `prompt` 和 `instructions` 都没被使用，也没有 LLM 步骤；
   - 打印 "a fresh agent per request"，但实际复用一个 agent（Q9）；
   - 最后一行 `python+fastapi  Agno` 中间是两个空格——对照 `main.ts` 可知这里原本应是箭头 `→`。
2. `main.ts` 更完整：
   - 有 `checkSchema` 运行时校验，并演示了 `unknown_tool` 的错误路径；
   - `MastraAgent.run` 最后调用 `mockLLM(this.instructions, ...)`，把工具结果组合进最终回答，并估算 token（实际运行输出 `~78 tokens`）；
   - workflow 的 search/summarise 步骤直接复用 `searchTool.execute` / `summariseTool.execute`，体现"workflow 编排 tools"；
   - 用 `async/await` 与 `setTimeout` 模拟网络延迟。
   但它同样没有流式输出（我们用 `tsx main.ts` 实际运行过）。
3. 参考骨架：

```python
def agno_stream_handler(session, make_agent, session_id, prompt):
    agent = make_agent()
    history = session.history(session_id)
    chunks = []
    for chunk in agent.stream(prompt, history):   # agent.stream 是生成器
        chunks.append(chunk)
        yield chunk                               # 边生成边推给客户端（如 SSE）
    full = "".join(chunks)
    session.append(session_id, f"user: {prompt}")
    session.append(session_id, f"assistant: {full}")
```

流结束后才持久化，是因为：中途客户端断开、模型报错时，不应把半截回答当作完整的 assistant 轮次存进历史，否则下一轮会基于残缺上下文继续；如需保留，可单独标记为"未完成"。在 FastAPI 中可以用 `StreamingResponse` 包装这个生成器。

### Q13 — 参考回答要点

- **Agno**：Python 运行时（前身 Phi-data），主张"纯 Python、无图无链"，追求极低的实例化开销（讲义：~2μs、~3.75 KiB），生产路径是无状态 FastAPI + 数据库会话；原生多模态与 agentic RAG。适合 Python/FastAPI 团队、大量短命 agent、性能要求高的场景。
- **Mastra**：TypeScript，基于 Vercel AI SDK；Agents + Zod 类型化 Tools + Workflows；Unified Model Router、composite storage、多种服务端适配器、Next.js/Astro 一等集成、Mastra Studio。适合 TypeScript/Next.js/Vercel 团队、需要多提供方路由与类型化工具的场景。
- **其他选择**：需要持久状态、显式图、失败后恢复 → LangGraph（第 13 节）；想要提供方产品化的形状 → OpenAI Agents SDK / Claude Agent SDK（第 16、17 节）。
- 加分点：讲义强调"Neither is trying to be LangGraph"——它们竞争的是语言契合、运行时人体工学与可观测性；`outputs` 中的决策表还覆盖了 AutoGen、CrewAI 与"直接 API + 第 01 节的循环"。

### Q14 — 参考回答要点

- **做法**：每个请求新建 agent，所有跨请求状态（会话历史、记忆）放在外部数据库；进程本身不持有会话状态。
- **解决的问题**：
  - 水平扩展：任意实例都能处理任意会话的请求，负载均衡无需粘性会话；
  - 故障恢复：实例崩溃不丢会话，重启或换机即可继续；
  - 部署简单：滚动发布、自动扩缩容不需要迁移内存状态；
  - 这正是"实例化必须便宜"的原因——每请求都要新建一次。
- **压力转移到哪里**：
  - 数据库：每次请求读历史、写新轮次，读写放大与延迟增加；长会话需要截断/摘要；
  - 并发一致性：同一会话的并发请求需要串行化或乐观锁（见 Q9）；
  - 进程内缓存失效：不能依赖内存里的热数据，需要外部缓存。
- 常见误区：把"无状态"理解为"不需要会话"——状态依然存在，只是被外置了。

### Q15 — 参考回答要点

- **先测瓶颈**：用 trace 拆分请求耗时（实例化、检索、LLM 调用、工具调用、序列化），看实例化占比。
- **在自己的栈上测**：按讲义练习 3 写一个基准，测"按生产配置构造 agent"的 P50/P99 耗时与内存，而不是引用厂商数字。
- **估算收益**：实例化占比 × 请求量 = 可节省的 CPU/延迟；与 LLM 调用耗时比较（见 Q11：1.5 s 的调用下 20 ms 也只占 1.33%）。
- **考虑迁移成本**：现有框架的 primitives（如 CrewAI 的角色、流程）在新运行时里如何表达，哪些会丢失（讲义练习 4）。
- **结论模板**：若工作负载是"每请求一次慢调用"，否决；若是高并发短命 agent 或大规模评测，值得做 PoC。
- `outputs` 硬规则："Picking Agno or Mastra purely on 'performance' when the workload is one slow call per request. Performance is rarely the bottleneck."

### Q16 — 参考回答要点

- **选型**：TypeScript + Next.js + Vercel + 多提供方 → Mastra（`outputs` 决策第 2 条）。
- **模型接入**：Unified Model Router 统一多家提供方，便于按成本/能力切换和故障转移。
- **多步流程**：用 Workflows 表达"检索 → 起草 → 人工审批 → 发送"等步骤，tools 用 Zod 定义输入；审批这类可能等待很久的步骤需要持久化 workflow 状态（若要跨天的长流程，考虑队列架构或第 29 节的生产运行时）。
- **存储**：composite storage——会话记忆放主业务库，workflow 状态单独存，观测数据量大时放 ClickHouse（讲义建议）。
- **可观测性**：开发期用 Mastra Studio（localhost:4111）调试，线上接 Langfuse/Phoenix/Opik（第 24 节）。
- **风险**：Vercel 生态锁定（讲义："a plus on Vercel, a minus elsewhere"）；如需 `ee/` 功能先审许可证。

### Q17 — 参考回答要点

- **许可证**：主体 Apache 2.0，`ee/` 目录是 source-available 企业许可，"permits source reading but restricts commercial use"。fork 或自托管前要确认用到的功能是否位于 `ee/`；`outputs` 规则："If the user wants to self-host Mastra's `ee/` features, refuse and point to the license terms."（讲义练习 5 让你读条款。）
- **生态锁定**：Mastra 与 Vercel AI SDK、Next.js 的深度集成在 Vercel 上是加分项，在其他平台上可能变成额外负担；评估时把"迁出成本"算进去。
- **Python 单仓不该随手引入 TS 运行时**：`outputs` 硬规则："Picking a TypeScript runtime in a Python monorepo without a rationale. Mixed-language agent code is an operational tax." 双语言意味着两套依赖管理、构建、测试、部署、可观测性接入，以及工具/类型定义在两种语言之间重复维护。
- 加分点：真需要 TS 前端能力时，可以让 TS 只做 UI 与流式代理，agent 逻辑仍留在 Python 服务里，通过 HTTP/SSE 交互。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：讲义练习 1、2 要把这个循环分别移植到 Agno 与 Mastra。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：讲义的先修，Agno/Mastra 的对照对象。
- [阶段 14 · 15 基于角色的 Agent 团队：角色、任务与流程](../../15-crewai-role-based-crews/docs/zh.md)：讲义练习 4 的迁移起点（CrewAI → Agno）。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：理解 Zod 类型化工具。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：Unified Model Router 的通用背景。

### 本节被哪些后续内容用到
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)、[阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：选型表中的提供方 SDK。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：两种运行时都接入的观测后端。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：框架之上的运维层，`outputs` 指定的下一步阅读。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：composite storage 中观测数据的落地。

### 延伸关键词
`Agno` · `Phi-data` · `FastAPI` · `stateless session-scoped backend` · `Mastra` · `Vercel AI SDK` · `Zod` · `Unified Model Router` · `composite storage` · `ClickHouse` · `Mastra Studio` · `source-available` · `instantiation latency` · `StreamingResponse / SSE`
