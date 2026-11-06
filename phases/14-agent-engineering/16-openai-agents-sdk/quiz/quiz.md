# 测验 · OpenAI Agents SDK：Handoffs、Guardrails 与追踪（OpenAI Agents SDK: Handoffs, Guardrails, Tracing）

> **阶段 14 · Agent 工程 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五个原语（primitives） | Agent、Handoff、Guardrail、Session、Tracing；Agent = LLM + instructions + tools + handoffs |
| 2 | Handoff 就是工具 | 模型在工具列表里看到 `transfer_to_<agent_name>`，调用它 = 把对话交给目标 agent；本质是把监督者（supervisor）模式产品化 |
| 3 | Handoff 时的上下文 | 默认复制整段对话给目标 agent；beta 选项 `nest_handoff_history` 先把历史折叠成摘要再转交 |
| 4 | 三类 guardrail | input（只对第一个 agent 的输入）、output（只对最后一个 agent 的输出）、tool（每个 function tool 的调用） |
| 5 | 并行 vs 阻塞模式 | 默认并行：与主 LLM 同时跑，尾延迟低，触发时主 LLM 的 token 白花；`run_in_parallel=False` 阻塞：先检查，不浪费 token 但多一段延迟 |
| 6 | Tripwire | guardrail 拒绝时抛结构化异常 `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered`，而不是让程序崩溃 |
| 7 | Tracing 默认开启 | LLM generation、tool call、handoff、guardrail 都发 span；`OPENAI_AGENTS_DISABLE_TRACING=1` 关闭；`add_trace_processor` 把 span 同时发到自建后端 |
| 8 | Session | 把对话历史存在 SQLite / Redis / 自定义后端，`Runner.run(..., session=session)` 自动加载并追加 |
| 9 | 三种典型失败 | handoff drift（A↔B 来回踢皮球，用 hop 计数器）、guardrail bypass（tool guardrail 管不到内置工具）、over-tracing（span 里有敏感内容） |
| 10 | 本节代码的简化 | 用 `policy` 函数代替 LLM；只实现 input/output guardrail、hop 上限与 span 树；**没有** tool guardrail、Session、并行模式 |

### 核心技能（能动手做到）

- [ ] 说出五个原语，并解释为什么把 handoff 建模成一个名为 `transfer_to_<agent>` 的工具
- [ ] 读懂 `Runner.run` 的主循环：input guardrail → 按 `kind` 分派 final / tool / handoff → output guardrail
- [ ] 根据代码手推任一输入的 span 树（哪些 span 是兄弟、哪些是子节点）
- [ ] 为代码补上 tool guardrail，并让 hop 耗尽时抛出明确错误而不是返回空字符串
- [ ] 对给定的延迟与触发率，定量比较并行与阻塞 guardrail 的延迟和 token 浪费
- [ ] 设计一个"triage + 若干专家 agent"的客服系统，说清 guardrail、hop 上限、Session、tracing 各放在哪里

---

## 二、基础自测（选择题）

**Q1.** 讲义列出的 OpenAI Agents SDK 五个原语是：

- A. Agent、Handoff、Guardrail、Session、Tracing
- B. Planner、Worker、Solver、Critic、Memory
- C. Node、Edge、Reducer、Checkpointer、Subgraph
- D. Tool、Prompt、Model、Memory、Trace

**Q2.** 在 SDK 里，模型是通过什么"看到"可以把对话转交给 billing agent 的？

- A. system prompt 里的一段说明文字
- B. 一个特殊的控制 token
- C. 一个独立的 HTTP 回调端点
- D. 工具列表中一个名为 `transfer_to_billing_agent` 这种形式的工具

**Q3.** 关于 guardrail 的并行（parallel，默认）与阻塞（`run_in_parallel=False`）模式，正确的是：

- A. 阻塞模式延迟更低，因为 guardrail 先跑完就不用再等
- B. 并行模式下 guardrail 与主 LLM 同时运行，尾延迟更低；一旦触发，主 LLM 已经生成的 token 被丢弃，造成浪费
- C. 并行模式只适用于 output guardrail
- D. 两种模式在 guardrail 触发时花费的 token 完全相同

**Q4.** 一个请求经过 triage → billing 两个 agent。按讲义，input guardrail 与 output guardrail 分别作用在：

- A. 两个 agent 的输入都检查；两个 agent 的输出都检查
- B. 只检查 billing 的输入；只检查 triage 的输出
- C. 只检查第一个 agent（triage）的输入；只检查最后一个 agent（billing）的输出
- D. 只在 handoff 发生时检查

**Q5.** 运行 `code/main.py`，第三个用例 `"share my ssn with the team"` 打印的 span 树中，`run` 节点下有哪些子 span？

- A. 只有一个 `input_guardrail.pii_block`（`passed=False`）
- B. `input_guardrail.pii_block` 和 `agent.triage`
- C. `input_guardrail.pii_block`、`agent.triage` 和 `output_guardrail.length_cap`
- D. 没有任何子 span，因为抛出了异常

**Q6.** 用本节的 `Runner`（`max_hops=3`）运行两个互相 handoff 的 agent：A 总是转给 B，B 总是转给 A，并配置 `length_cap` 输出 guardrail。实际结果是：

- A. 抛出 `GuardrailTripped("output", ...)`
- B. 抛出 `RecursionError`
- C. 无限循环，程序卡住
- D. 静默返回空字符串 `''`，`length_cap` 显示 `passed=True reason='output 0 chars'`

**Q7.** 关于 SDK 的 tracing，下列说法正确的是：

- A. 默认关闭，需要在每个 agent 上手动开启
- B. 只能通过 OpenTelemetry Collector 导出，不能接自定义后端
- C. 默认开启；设置 `OPENAI_AGENTS_DISABLE_TRACING=1` 可退出；`add_trace_processor` 可把 span 同时发往自己的后端
- D. 只记录 LLM generation，不记录 handoff 和 guardrail

**Q8.** 讲义说的 "guardrail bypass" 指的是：

- A. 模型可以通过改写提示词关闭 guardrail
- B. tool guardrail 只对 function tool 生效，文件读取、网页抓取这类内置工具需要单独的策略
- C. 阻塞模式下 guardrail 会被跳过
- D. handoff 之后所有 guardrail 都失效

---

## 三、动手 / 代码题

**Q9.** 阅读 `Runner.run` 的主循环（节选）：

```python
        current_agent = agent
        current_input = user_input
        final_output = ""
        for hop in range(self.max_hops):
            ...
            if kind == "final":
                final_output = policy_output["text"]
                ...
                break
            if kind == "tool":
                ...
                current_input = f"tool {tool_name} returned: {result}"
                continue
            if kind == "handoff":
                ...
                current_agent = handoff.target
                current_input = policy_output.get("input", current_input)
                continue
            ...

        for guard in self.output_guardrails:
            ok, reason = guard.check(final_output)
```

1. 当 `max_hops` 用完仍没有 `final` 时会发生什么？为什么这是一个危险的默认行为？
2. 工具调用也会消耗 hop。一个 agent 需要连续调用 3 次工具后才能回答，会出现什么问题？
3. 修改代码：hop 耗尽时抛出一个结构化异常（与 guardrail 一样"不是崩溃"），并让工具调用与 handoff 分开计数。

**Q10.** 讲义 "Build It" 说 `Runner` 带有 "input/output/tool guardrails"，但代码里只有 `input_guardrails` 和 `output_guardrails`。请：

1. 设计一个 `ToolGuardrail` 数据类，签名为 `check(tool_name: str, args: dict) -> tuple[bool, str]`；
2. 写出接入 `Runner.run` 中 `kind == "tool"` 分支的代码：在 `tool.fn(**args)` 之前检查，拒绝时抛 `GuardrailTripped("tool", reason)`，并在 trace 中记录 span；
3. 说明为什么 tool guardrail 不能替代 input guardrail。

**Q11.**（计算题）某客服系统：guardrail LLM 耗时 300 ms，主 LLM 耗时 2000 ms 并消耗 1500 token；guardrail 触发率 5%。假设并行模式下 guardrail 触发时主 LLM 已经跑完（token 全部浪费），阻塞模式下 guardrail 触发后不再调用主 LLM。请计算每 1000 个请求：

1. 两种模式的平均端到端延迟；
2. 并行模式浪费的 token 数；
3. 若主 LLM 每 1000 token 0.01 美元，guardrail 本身调用不计，并行模式每 1000 个请求多花多少钱？什么情况下你会改成阻塞模式？

**Q12.** `main()` 里每个用例开始前都执行 `runner.trace = Span(name="run", ...)`。

1. 如果删掉这一行，第二个用例打印的 span 树会怎样？
2. 当前 trace 的结构是"所有 agent span 都是 `run` 的直接子节点，handoff span 挂在发起方 agent 下"。真实 SDK 与 OTel 中，一个 trace 还需要哪些字段才能在后端被正确拼成树并计算耗时？
3. 如果同一个 `Runner` 实例被两个线程并发使用，会出现什么问题？给出改造方案。

---

## 四、面试高频题

**Q13.**（基础必考）介绍 OpenAI Agents SDK 的五个原语。为什么 handoff 被设计成一个工具，而不是单独的控制流 API？

**Q14.**（原理深挖）input / output / tool 三类 guardrail 各自拦截什么风险？并行模式和阻塞模式该如何选？

**Q15.**（工程实践）tracing 默认开启。在生产中你会如何处理 span 中的敏感内容、如何接入自有可观测性后端？

**Q16.**（场景设计）为一家 SaaS 公司设计客服多 agent 系统：triage + billing + support + account 三个专家。请说明 agent 划分、handoff、guardrail、Session、tracing 和失败处理的设计。

**Q17.**（追问型）handoff 时把完整对话复制给目标 agent，和用 `nest_handoff_history` 折叠成摘要，各有什么利弊？A↔B 来回 handoff 的问题除了 hop 计数器还能怎么治？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Five primitives: Agent, Handoff, Guardrail, Session, Tracing."
B 是 Plan-and-Execute / Reflexion 一类模式的角色名；C 是 LangGraph 的概念（第 13 节）；D 把 Handoff、Guardrail、Session 都换成了泛泛的组件名，Tool 在 SDK 中只是 Agent 的组成部分（`FunctionTool`），不是独立原语。

### Q2 — 答案：D

讲义："The model sees `transfer_to_billing_agent` in its tool list." 调用这个工具会让 runtime 复制上下文、用目标 agent 的 instructions 初始化它、并继续运行。好处是复用了模型已有的 tool calling 能力，无需新的协议。A、B、C 都不是 SDK 的机制。本节代码中 `Handoff.tool_name` 返回 `f"transfer_to_{self.target.name}"`，因为 agent 名叫 `billing`，所以 span 里显示的是 `transfer_to_billing`。

### Q3 — 答案：B

讲义："Parallel (default). Guardrail LLM runs alongside the main LLM. Lower tail latency. If tripped, the main LLM's work is discarded (token waste). Blocking ... If tripped, no tokens wasted on the main call."
A 说反了：阻塞模式是"先等 guardrail 再跑主 LLM"，延迟是两者之和；C 错，模式是 guardrail 的执行方式，讲义描述的是 input guardrail 的场景；D 错，并行模式触发时多花了主 LLM 的 token。

### Q4 — 答案：C

讲义："Input (first agent only), output (last agent only), or tool invocation (per function tool)." 原因：用户输入只在入口出现一次，中间 handoff 的输入是 agent 之间的内部消息；最终交付给用户的只有最后一个 agent 的输出。本节代码同样只在循环前检查 `user_input`、循环后检查 `final_output`。

### Q5 — 答案：A

实际运行输出：

```text
--- case: share my ssn with the team ---
GUARDRAIL: input: refuses to process social security numbers
span tree:
  run  user_input='share my ssn with the team'
    input_guardrail.pii_block  passed=False reason='refuses to process social security numbers'
```

input guardrail 在任何 agent 运行之前执行，`_pii_check` 发现 `"ssn"` 后立即 `raise GuardrailTripped("input", reason)`，所以没有 `agent.triage`（B 错），更不会走到 output guardrail（C 错）。span 是在 `raise` **之前** `append` 的，因此 trace 里保留了这次拒绝的记录（D 错）——这正是"guardrail 触发是结构化事件而不是崩溃"的含义。

### Q6 — 答案：D

已实际运行验证：

```text
loop out repr: ''
run
  agent.a  hop=0 instructions='x'
    handoff.transfer_to_b  from='a' to='b'
  agent.b  hop=1 instructions='y'
    handoff.transfer_to_a  from='b' to='a'
  agent.a  hop=2 instructions='x'
    handoff.transfer_to_b  from='a' to='b'
  output_guardrail.length_cap  passed=True reason='output 0 chars'
```

`for hop in range(self.max_hops)` 跑满 3 次后正常退出循环，`final_output` 仍是初始值 `""`，长度 0 < 200，`length_cap` 通过。所以 hop 上限确实阻止了死循环（C 错），没有递归（B 错），但它不报错（A 错）——调用方拿到一个空回复却不知道发生了 handoff drift。详见 Q9。

### Q7 — 答案：C

讲义："On by default. ... `OPENAI_AGENTS_DISABLE_TRACING=1` opts out. `add_trace_processor(processor)` fans spans to your own backend alongside OpenAI's." A 说反了；B 错，`add_trace_processor` 就是接自定义后端的入口；D 错，讲义明确列出 LLM generation、tool call、handoff、guardrail 四类 span。

### Q8 — 答案：B

讲义："Tool guardrails only fire on function tools; built-in tools (file reader, web fetch) need separate policy." A 描述的是 prompt injection，不是本节定义的 bypass；C 错，阻塞模式只是改变执行顺序；D 错，讲义没有这种说法——input/output guardrail 本来就只在首尾生效，这是设计而不是失效。

### Q9 — 参考答案

1. **hop 耗尽时**：循环自然结束，`final_output` 保持 `""`，接着 output guardrail 对空字符串做检查（`length_cap` 通过），`run` 返回 `""`。危险在于**静默失败**：调用方无法区分"agent 回答了空内容"和"agent 陷入了 handoff 循环"；trace 里也没有任何"超限"标记。讲义练习 1 要求的是 "refuse after N transfers"，即明确拒绝。
2. **工具调用占用 hop**：`kind == "tool"` 分支末尾 `continue`，同样消耗一次 `range(self.max_hops)`。需要连续 3 次工具调用的 agent 在第 3 次工具结果返回后已没有 hop 生成 final，结果同样是 `""`。另外 `current_input = f"tool {tool_name} returned: {result}"` 用工具结果**覆盖**了原始用户输入，agent 下一轮看不到用户原话——真实 SDK 是把工具结果追加到对话历史里，而不是替换。
3. 参考修改（已在本地运行验证：A↔B 循环抛出 `max_handoffs: 3 handoffs exceeded`）：

```python
class MaxHopsExceeded(Exception):
    pass

    # Runner 中
    max_handoffs: int = 3
    max_turns: int = 10          # 工具调用 + 生成的总轮数上限

    def run(self, agent, user_input):
        ...
        handoffs_done = 0
        for turn in range(self.max_turns):
            ...
            if kind == "handoff":
                if handoffs_done >= self.max_handoffs:
                    agent_span.children.append(
                        Span(name="handoff_refused",
                             attributes={"reason": "max handoffs"}))
                    raise MaxHopsExceeded(f"max_handoffs: {self.max_handoffs} handoffs exceeded")
                handoffs_done += 1
                ...
        else:                     # for-else：循环没有被 break
            raise MaxHopsExceeded(f"max_turns: {self.max_turns} turns without final output")
```

要点：handoff 次数与总轮数分开计数；超限写入 trace；用 `for ... else` 捕捉"没有 break 就结束"的情况。真实 SDK 也有类似的 `max_turns` 限制，超限时抛异常。

### Q10 — 参考答案

```python
@dataclass
class ToolGuardrail:
    name: str
    check: Callable[[str, dict], tuple[bool, str]]

# Runner 增加字段
#   tool_guardrails: list[ToolGuardrail] = field(default_factory=list)

            if kind == "tool":
                tool_name = policy_output["tool"]
                args = policy_output.get("args", {})
                tool = ...  # 原代码：查找工具
                for guard in self.tool_guardrails:
                    ok, reason = guard.check(tool_name, args)
                    agent_span.children.append(
                        Span(name=f"tool_guardrail.{guard.name}",
                             attributes={"tool": tool_name, "passed": ok, "reason": reason}))
                    if not ok:
                        raise GuardrailTripped("tool", reason)
                result = tool.fn(**args)
```

示例检查函数：

```python
def _no_rm(tool_name, args):
    if tool_name == "shell" and "rm -rf" in args.get("cmd", ""):
        return False, "destructive shell command"
    return True, "ok"
```

为什么不能替代 input guardrail：

- tool guardrail 只在模型**已经决定调用工具**之后才运行，此时主 LLM 已经读过（可能有害的）输入并消耗了 token；input guardrail 在任何 LLM 调用之前拒绝越界请求。
- 很多风险根本不经过工具（如直接让模型输出违规内容），只能由 input/output guardrail 拦截。
- 反过来 input guardrail 也替代不了 tool guardrail：工具参数是模型在运行中生成的（可能受 prompt injection 影响），只有在调用点才能看到。三者是分层防御。

### Q11 — 参考答案

（已用 Python 计算）

1. **平均延迟**：
   - 阻塞：通过的请求 `300 + 2000 = 2300 ms`，触发的请求只需 `300 ms`；平均 `0.95 × 2300 + 0.05 × 300 = 2200 ms`。
   - 并行：通过的请求 `max(300, 2000) = 2000 ms`；按题设触发时主 LLM 已跑完，也记 2000 ms（若能在 300 ms 时取消主调用，则触发请求可更快返回，但已生成的 token 仍然计费）。平均 `2000 ms`。
   - 并行比阻塞平均快 200 ms，而且对**通过的请求**（95%）每个都快 300 ms——这就是讲义说的 "lower tail latency"。
2. **浪费的 token**：`1000 × 5% × 1500 = 75,000` token。
3. **多花的钱**：`75,000 / 1000 × 0.01 = 0.75` 美元 / 1000 请求。
   改为阻塞模式的情形：触发率高（例如面向公网、垃圾请求多）；主模型很贵或输出很长（如长文生成、深度推理）；guardrail 很快、相对主调用延迟占比很小；或者主 LLM 会触发有副作用的工具调用（并行时可能在 guardrail 拒绝前就执行了动作）。`outputs/skill-agents-sdk-scaffold.md` 的规则是："Default to parallel mode unless the guardrail LLM is large relative to the main model — then use blocking."

### Q12 — 参考答案

1. `Runner.trace` 是 dataclass 字段，`run` 只往 `self.trace.children` 里 `append`，从不重置。删掉那一行后，第二个用例的 span 树会包含第一个用例的全部 span（已验证：同一 Runner 连续 run 两次，`run` 下有 4 个子 span），而且根节点的 `user_input` 属性仍是第一个用例的。
2. 需要：`trace_id`（同一次 run 的全部 span 共享）、`span_id` 与 `parent_span_id`（拼树）、开始/结束时间戳（算耗时）、状态（ok / error）以及 span 类型（generation、function、handoff、guardrail）。本节的 `Span` 只有 `name`、`attributes`、`children`，靠对象嵌套表达父子关系，没有时间信息，无法导出到 OTel 后端。讲义建议对齐 OTel GenAI 语义约定（第 23 节）。
3. 两个线程会把 span 写进同一个 `self.trace`，树会交错混杂，甚至因为 `main()` 那样重置 `runner.trace` 而互相覆盖。改造：让 `run` 在内部创建局部的 `trace = Span("run", ...)`，并返回一个 `RunResult(final_output, trace)`；`Runner` 只保存配置（guardrails、max_hops），不保存单次运行的状态。真实 SDK 的 `Runner.run` 也是返回一个结果对象，trace 由上下文管理。

### Q13 — 参考回答要点

- **五个原语**：Agent（LLM + instructions + tools + handoffs）、Handoff（委派给另一个 agent）、Guardrail（输入/输出/工具调用校验）、Session（跨轮对话历史持久化）、Tracing（LLM、工具、handoff、guardrail 的内置 span）。
- **为什么 handoff 是工具**：
  - 模型已经很擅长"从工具列表中选一个并调用"，handoff 复用这套能力，不需要新的训练或协议；
  - 工具描述天然告诉模型"什么时候该转给谁"，路由决策由模型做；
  - runtime 只需在识别到 `transfer_to_*` 时切换当前 agent、搬运上下文，实现简单；
  - 对 tracing 友好：handoff 和 tool call 一样有清晰的 span。
- 加分点：讲义说这是 "the supervisor pattern ... productized"；本节代码中 triage agent 只有 handoffs、没有领域工具，与 `outputs` 的硬规则 "Triage handoffs only; mixing dilutes the router's decision" 一致。
- 常见误区：以为 handoff 是"调用另一个 agent 然后拿回结果"——handoff 是**转移控制权**，后续由目标 agent 继续对话；"调用后拿回结果"是 agent-as-tool / 子 agent 模式。

### Q14 — 参考回答要点

- **input guardrail**：第一个 agent 的输入；拦截越界请求、PII、越狱、明显违规内容；越早拒绝越省钱。
- **output guardrail**：最后一个 agent 的输出；拦截 PII 泄露、违反政策、格式不合规（例如 JSON 不合法、过长）。
- **tool guardrail**：每次 function tool 调用；校验参数、检查权限、审计执行，防止有副作用的危险操作；注意它覆盖不到内置工具。
- **并行 vs 阻塞**：
  - 并行：延迟 ≈ `max(guardrail, main)`，触发时浪费主调用 token；适合触发率低、guardrail 便宜、对延迟敏感的场景。
  - 阻塞：延迟 ≈ `guardrail + main`，触发时零浪费；适合触发率高、主调用贵、主调用会产生副作用、或 guardrail 模型相对主模型较大的场景。
- 加分点：能给出定量估算（见 Q11）；指出 guardrail 应当只"批准或拒绝"而不改写内容（`outputs` 硬规则："Guardrails approve or reject — they do not rewrite."）。
- 常见误区：把 output guardrail 设为并行——输出 guardrail 必须在结果交给用户之前完成，生产中对安全关键输出应阻塞（`outputs`："Always blocking on prod for safety-critical outputs."）。

### Q15 — 参考回答要点

- **默认开启的意义**：多步 agent 的失败很难复现，没有 trace 几乎无法调试；`outputs` 甚至规定 "If tracing is disabled in prod, refuse to ship."
- **敏感内容**：讲义的 over-tracing 风险——span 里会记录 prompt、工具参数和输出。做法：
  - 对齐 OTel GenAI 的内容捕获规则：内容默认不进 span，而是存到受控存储，span 中只放引用 ID（讲义："store externally, reference by ID"）；
  - 对 PII 字段做脱敏或哈希；
  - 区分环境：开发环境全量，生产环境最小化。
- **接入后端**：用 `add_trace_processor(processor)` 把 span 同时发给自建后端（Langfuse、Phoenix、OTel collector 等），与 OpenAI 自带的 trace UI 并存；或者用环境变量完全关闭默认导出。
- 加分点：本节 `Span` 用 `[:40]`、`[:60]` 截断属性值，是最朴素的"限制内容"手段，但截断不等于脱敏——前 40 个字符里照样可能有 PII。

### Q16 — 参考回答要点

- **agent 划分**：triage 只有 handoffs（`transfer_to_billing` / `transfer_to_support` / `transfer_to_account`），没有领域工具；每个专家只拿自己领域的 function tool（退款查询、工单创建、账户修改）。
- **guardrail**：
  - input：PII/越界/越狱检测，默认并行；面向公网高触发率时改阻塞；
  - output：PII 泄露、承诺退款金额等政策检查，阻塞；
  - tool：退款、改账户等有副作用的工具加权限与金额上限检查，必要时转人工确认。
- **hop 上限**：handoff 上限 3 次，超限转人工并记 trace；专家之间如需互转，需在 instructions 里写清边界，防止 drift。
- **Session**：开发用 SQLite，生产用 Redis；以用户/会话 ID 为键，`Runner.run(agent, input, session=session)` 自动加载历史。
- **tracing**：默认开启，`add_trace_processor` 接入公司可观测性平台；内容外置、span 只存 ID。
- **失败处理**：guardrail tripwire 被捕获后返回友好提示；工具异常转为结构化错误交给模型或人工；监控 handoff 循环率、guardrail 触发率。
- 加分点：`outputs` 指出只有 2 个专家时可以用一个直接分类器路由（第 12 节的 routing 工作流）代替 triage + handoff，更省 token。

### Q17 — 参考回答要点

- **完整复制**：目标 agent 看到全部原始细节，不丢信息；代价是上下文变长、token 成本和延迟上升，且上一个 agent 的中间推理、工具噪声会干扰目标 agent。
- **`nest_handoff_history` 折叠**：先把历史压缩成一条摘要再转交，上下文短、焦点清晰；代价是摘要可能丢失关键细节（订单号、用户原话），而且多一次总结调用。讲义标注它为 beta。
- **治理 A↔B 来回**：
  - hop 计数器（讲义与本节代码的 `max_hops`），并在超限时**显式报错**；
  - 在 agent instructions 和 handoff 描述里写清职责边界，减少模糊地带；
  - 禁止"回退给刚刚转来的 agent"，或只允许专家 handoff 回 triage；
  - 监控 trace 中的 handoff 链路，发现循环模式后修 prompt。
- 常见误区：只设 hop 上限而不处理超限后的行为——就像本节代码那样返回空字符串，用户体验和可调试性都很差。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：`Runner.run` 的 for 循环就是一个带 hop 上限的 agent loop。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：handoff 被建模为工具，前提是理解 tool calling。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：routing 工作流与 triage handoff 的取舍。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：讲义把 handoff 称作监督者模式的产品化。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：guardrail 的基础概念。

### 本节被哪些后续内容用到
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：Claude 侧的对应 SDK，subagent 与 hook。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：span 的标准字段与内容捕获规则。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：`add_trace_processor` 接入的后端。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../28-orchestration-patterns/docs/zh.md)：handoff 所属的编排模式全景。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../../16-multi-agent-and-swarms/11-handoffs-and-routines/docs/zh.md)：handoff 思想在多智能体中的展开。
- [阶段 15 · 18 Llama Guard 与输入输出分类](../../../15-autonomous-systems/18-llama-guard/docs/zh.md)：用分类模型实现 input/output guardrail。

### 延伸关键词
`Responses API` · `transfer_to_<agent>` · `nest_handoff_history` · `InputGuardrailTripwireTriggered` · `run_in_parallel` · `add_trace_processor` · `max_turns` · `SQLiteSession` · `supervisor pattern` · `OTel GenAI` · `agent-as-tool`
