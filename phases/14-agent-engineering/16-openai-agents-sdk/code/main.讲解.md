# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 16 节 OpenAI Agents SDK：Handoffs、Guardrails 与追踪 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），无需 API key、无需网络、无需安装 `openai-agents`

---

## 1. 这份代码在考察什么

这份代码用 226 行标准库 Python 模仿 OpenAI Agents SDK 的"形状"，让你在不调用任何 LLM 的情况下看清 SDK 的运行时在做什么：

1. **Agent 与 Handoff**：Agent 持有 instructions、tools、handoffs；handoff 的工具名是 `transfer_to_<agent>`。
2. **Runner 主循环**：每一"跳"（hop）让当前 agent 做一次决策，结果分为 `final`（给出答案）、`tool`（调用工具）、`handoff`（转交控制权）三类。
3. **Guardrail 与 tripwire**：input guardrail 在任何 agent 运行前检查用户输入，output guardrail 在结束后检查最终输出，拒绝时抛结构化异常 `GuardrailTripped`。
4. **Tracing**：每个 guardrail、agent、handoff、工具调用、生成都被记录成一个 `Span`，组成一棵可打印的 span 树。
5. **hop 上限**：`max_hops` 防止 handoff 无限循环（讲义的 handoff drift）。

为了能离线运行，"LLM"被替换成了确定性的 `policy` 函数（关键词路由），这既是本代码的教学巧思，也是它和真实 SDK 最大的差异。

> 一句话：**用一个 `for hop in range(max_hops)` 循环 + 三种决策分支 + 首尾两道检查，把 Agents SDK 的运行时骨架摊开给你看**；同时要注意它省略了 tool guardrail、Session、并行模式，并且 hop 耗尽时会静默返回空字符串。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GuardrailTripped` | 异常类 | 携带 `which`（input/output）与 `reason` | Tripwire（SDK 中是两个独立异常类） |
| `FunctionTool` | dataclass | 名称 + 描述 + 可调用对象 | Function tool |
| `Handoff` | dataclass | 指向目标 agent；`tool_name` 属性生成 `transfer_to_<name>` | Handoff 即工具 |
| `Agent` | dataclass | name、instructions、`policy`（代替 LLM）、tools、handoffs | Agent 原语 |
| `InputGuardrail` / `OutputGuardrail` | dataclass | 名称 + `check(text) -> (ok, reason)` | Guardrail 原语 |
| `Span` | dataclass | name、attributes、children，嵌套成树 | Tracing 原语 |
| `Runner` | dataclass | 持有 guardrail 列表、`max_hops`、当前 `trace`；`run()` 是运行时主循环 | Runner |
| `_print_span` | 递归函数 | 缩进打印 span 树 | trace 可视化 |
| `_triage_policy` / `_billing_policy` / `_support_policy` | 函数 | 关键词路由与专家回复 | 用规则模拟 LLM 决策 |
| `_pii_check` / `_length_check` | 函数 | 输入含 "ssn" 拒绝；输出长度 < 200 | 示例 guardrail |
| `main` | 函数 | 组装 3 个 agent 和 Runner，跑 3 个用例并打印 trace | 演示入口 |

数据流：`user_input` → input guardrails（任一失败即抛异常）→ `for hop`：`agent.policy(input)` → `final` 结束 / `tool` 执行后把结果当作新输入 / `handoff` 切换 agent → output guardrails → 返回 `final_output`；全程把 `Span` 追加到 `runner.trace`。

---

## 3. 逐段精讲

### 3.1 结构化异常：`GuardrailTripped`

```python
class GuardrailTripped(Exception):
    def __init__(self, which: str, reason: str) -> None:
        super().__init__(f"{which}: {reason}")
        self.which = which
        self.reason = reason
```

- 继承 `Exception`，调用 `super().__init__` 设置异常消息（`str(e)` 得到 `"input: refuses ..."`）。
- 额外保存 `which` 和 `reason` 两个字段，让调用方可以按类型分支处理，而不是解析字符串——这就是讲义说的 "every guardrail trip is a structured exception, not a crash"。
- ⚠️ 与真实 SDK 的差异：SDK 用两个不同的异常类 `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered`，可以用不同的 `except` 子句捕获；这里用一个类加 `which` 字段区分。

### 3.2 数据类：Tool、Handoff、Agent、Guardrail

```python
@dataclass
class Handoff:
    target: "Agent"

    @property
    def tool_name(self) -> str:
        return f"transfer_to_{self.target.name}"


@dataclass
class Agent:
    name: str
    instructions: str
    policy: Callable[[str], dict[str, Any]]
    tools: list[FunctionTool] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
```

- `target: "Agent"` 是**前向引用**：`Agent` 类定义在 `Handoff` 之后，用字符串注解；文件顶部的 `from __future__ import annotations` 让所有注解都延迟求值，因此其实不加引号也可以。
- `tool_name` 用 `@property` 动态生成，这正是讲义的核心点："Handoff ... Represented to the model as a tool named `transfer_to_<agent_name>`"。本例 agent 名为 `billing`，所以工具名是 `transfer_to_billing`（讲义举例用的是 `transfer_to_billing_agent`，取决于 agent 的 name）。
- `policy: Callable[[str], dict]` 代替了真实的 LLM：输入一段文本，输出一个决策字典 `{"kind": ...}`。
- `field(default_factory=list)`：dataclass 的可变默认值必须用工厂函数，否则所有实例会共享同一个列表。
- ⚠️ `instructions` 在代码里**只被写入 span 属性**，从未传给 `policy`。真实 SDK 会把 instructions 作为 system prompt 发给模型。
- ⚠️ `tool_name` 也只用于 span 名称：`policy` 返回的是 `{"to": "billing"}`，runtime 用 `h.target.name == target_name` 匹配，而不是"模型调用了名为 `transfer_to_billing` 的工具"。真实 SDK 中，handoff 会和 function tool 一起出现在发给模型的工具列表里。

`InputGuardrail` 与 `OutputGuardrail` 结构完全相同，都是 `name + check(text) -> (bool, str)`。分成两个类是为了类型上区分用途。

### 3.3 `Span`：最小 trace 节点

```python
@dataclass
class Span:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Span"] = field(default_factory=list)
```

- 通过 `children` 嵌套表达父子关系，整个 trace 就是一棵树。
- ⚠️ 与真实 tracing（以及 OTel）相比，缺少 `trace_id` / `span_id` / `parent_id`、开始与结束时间、状态码。没有时间戳就无法从 trace 里看出"哪一步慢"。

### 3.4 `Runner.run` 第一段：input guardrail

```python
@dataclass
class Runner:
    input_guardrails: list[InputGuardrail] = field(default_factory=list)
    output_guardrails: list[OutputGuardrail] = field(default_factory=list)
    max_hops: int = 3
    trace: Span = field(default_factory=lambda: Span(name="run"))

    def run(self, agent: Agent, user_input: str) -> str:
        for guard in self.input_guardrails:
            ok, reason = guard.check(user_input)
            span = Span(name=f"input_guardrail.{guard.name}",
                        attributes={"passed": ok, "reason": reason})
            self.trace.children.append(span)
            if not ok:
                raise GuardrailTripped("input", reason)
```

- `Runner` 本身也是 dataclass；`trace` 的默认值用 `lambda` 作为工厂，每个 Runner 实例一棵新树。
- 依次运行每个 input guardrail：**先记 span 再判断**，所以即使拒绝，trace 里也保留了 `passed=False` 的记录（见第 6 节第 3 个用例）。
- 只检查最初的 `user_input`，对应讲义"Input guardrails. Run on the first agent's input"。
- 这是**阻塞模式**：guardrail 全部通过后才运行任何 agent。代码没有实现讲义中默认的并行模式（并行需要并发执行 guardrail 与主调用，例如 `asyncio.gather`）。
- ⚠️ `trace` 是 Runner 的实例状态，`run` 从不重置它，只会 `append`；如果复用同一个 Runner 而不手动重置，span 会跨请求累积（见第 8 节）。

### 3.5 `Runner.run` 第二段：hop 循环与三种决策

```python
        current_agent = agent
        current_input = user_input
        final_output = ""
        for hop in range(self.max_hops):
            agent_span = Span(name=f"agent.{current_agent.name}",
                              attributes={"hop": hop,
                                          "instructions": current_agent.instructions[:40]})
            self.trace.children.append(agent_span)

            policy_output = current_agent.policy(current_input)
            kind = policy_output["kind"]
```

每一跳先为当前 agent 建一个 span（**直接挂在 `run` 下**，所以多个 agent 在树里是兄弟节点），再调用 `policy` 得到决策。`instructions[:40]` 用切片截断，避免 span 过大。

**分支 1：`final`**

```python
            if kind == "final":
                final_output = policy_output["text"]
                agent_span.children.append(
                    Span(name="llm_generation",
                         attributes={"output": final_output[:60]})
                )
                break
```

记录一个 `llm_generation` 子 span，`break` 跳出循环。

**分支 2：`tool`**

```python
            if kind == "tool":
                tool_name = policy_output["tool"]
                args = policy_output.get("args", {})
                tool = next((t for t in current_agent.tools if t.name == tool_name),
                            None)
                if tool is None:
                    ...
                    final_output = f"error: unknown tool {tool_name}"
                    break
                result = tool.fn(**args)
                agent_span.children.append(
                    Span(name=f"tool.{tool_name}",
                         attributes={"args": args, "result": result[:40]})
                )
                current_input = f"tool {tool_name} returned: {result}"
                continue
```

- `next((... for ...), None)`：在生成器里找第一个匹配的工具，找不到返回默认值 `None`——这是 Python 中"查找第一个满足条件元素"的惯用写法。
- `tool.fn(**args)`：把字典解包成关键字参数。
- 工具结果被拼成字符串**替换** `current_input`，同一个 agent 在下一跳读到它。
- ⚠️ 这里没有 tool guardrail，尽管讲义 "Build It" 写着 `Runner` 带 "input/output/tool guardrails"（测验 Q10 给出补全方案）。
- ⚠️ `tool.fn` 抛出的异常不会被捕获，会直接让 `run` 崩溃；`result[:40]` 也假设返回值是字符串。
- ⚠️ 原始用户输入被覆盖：agent 下一跳只看到 `"tool X returned: ..."`。真实 SDK 是把工具结果**追加**到对话历史。
- ⚠️ 工具调用也消耗一个 hop。演示用例里没有 agent 带工具，所以这条分支在 `main()` 中没有被执行到（第 6 节之外我们用额外脚本验证过：一次工具调用后再生成 final，共占 2 个 hop）。

**分支 3：`handoff`**

```python
            if kind == "handoff":
                target_name = policy_output["to"]
                handoff = next((h for h in current_agent.handoffs
                                if h.target.name == target_name), None)
                if handoff is None:
                    final_output = f"error: no handoff to {target_name}"
                    break
                agent_span.children.append(
                    Span(name=f"handoff.{handoff.tool_name}",
                         attributes={"from": current_agent.name,
                                     "to": target_name})
                )
                current_agent = handoff.target
                current_input = policy_output.get("input", current_input)
                continue
```

- 只允许转交给**当前 agent 声明过的** handoff 目标——这是一种白名单，模型不能凭空转给任意 agent。
- 切换 `current_agent`，`policy_output.get("input", current_input)` 允许发起方改写要传过去的输入，否则沿用原输入。这对应讲义里"复制对话上下文"的第 1 步（这里只传了一条字符串，没有完整历史）。
- handoff span 挂在**发起方** agent 的 span 下面，目标 agent 在下一跳得到自己的 span。

**兜底**

```python
            final_output = f"error: unknown policy kind {kind}"
            break
```

未知的 `kind` 被转成错误字符串，而不是抛异常。注意这些 `error: ...` 字符串会被当作正常的 `final_output` 返回给调用方。

### 3.6 `Runner.run` 第三段：output guardrail 与 hop 耗尽

```python
        for guard in self.output_guardrails:
            ok, reason = guard.check(final_output)
            span = Span(name=f"output_guardrail.{guard.name}",
                        attributes={"passed": ok, "reason": reason})
            self.trace.children.append(span)
            if not ok:
                raise GuardrailTripped("output", reason)

        return final_output
```

- 只检查最后的 `final_output`，对应讲义 "Output guardrails. Run on the last agent's output"。
- ⚠️ **hop 耗尽是静默的**：如果 `range(self.max_hops)` 跑完都没有 `break`，`final_output` 仍是 `""`，`length_cap` 对空串通过，`run` 返回 `""`。我们实际构造了 A↔B 互相 handoff 的情形，得到 `''` 和 `output_guardrail.length_cap passed=True reason='output 0 chars'`。讲义练习 1 要求 "refuse after N transfers"——应当抛出类似 `MaxHopsExceeded` 的异常（测验 Q9）。

### 3.7 打印与示例策略

```python
def _print_span(span: Span, indent: int = 0) -> None:
    prefix = "  " * indent
    attrs = " ".join(f"{k}={v!r}" for k, v in span.attributes.items())
    print(f"{prefix}{span.name}  {attrs}")
    for child in span.children:
        _print_span(child, indent + 1)
```

- 递归先序遍历：先打印自己，再缩进打印孩子。
- `{v!r}` 用 `repr()` 格式化，字符串会带引号（如 `reason='ok'`），布尔值显示为 `True`。

```python
def _triage_policy(user_input: str) -> dict[str, Any]:
    t = user_input.lower()
    if "refund" in t or "billing" in t or "invoice" in t:
        return {"kind": "handoff", "to": "billing", "input": user_input}
    if "error" in t or "crash" in t or "bug" in t:
        return {"kind": "handoff", "to": "support", "input": user_input}
    return {"kind": "final", "text": "i'm not sure how to help with that"}
```

- triage 只做路由，**没有领域工具**，与 `outputs/skill-agents-sdk-scaffold.md` 的硬规则 "Triage handoffs only" 一致。
- 子串匹配有误报：我们实测 `"terrorist?"` 和 `"rebuggy"` 都会被转给 support；`_pii_check` 对 `"Mississippi assn meeting"` 也会因为 `"assn"` 里含 `"ssn"` 而拒绝。真实系统中路由由 LLM 完成、PII 检测用专门的分类器或正则 + 校验。

```python
def _length_check(text: str) -> tuple[bool, str]:
    return len(text) < 200, f"output {len(text)} chars"
```

无论通过与否都返回描述性 reason，所以 trace 里能看到 `reason='output 49 chars'`。

### 3.8 `main()`：组装与三个用例

```python
    triage = Agent(
        name="triage", instructions="route queries to the right specialist",
        policy=_triage_policy,
        handoffs=[Handoff(target=billing), Handoff(target=support)],
    )
    runner = Runner(
        input_guardrails=[InputGuardrail("pii_block", _pii_check)],
        output_guardrails=[OutputGuardrail("length_cap", _length_check)],
    )
    ...
    for case in cases:
        runner.trace = Span(name="run", attributes={"user_input": case[:40]})
        try:
            out = runner.run(triage, case)
            print(f"final: {out}")
        except GuardrailTripped as e:
            print(f"GUARDRAIL: {e}")
```

- 必须先创建 `billing`、`support`，triage 才能引用它们。
- 每个用例前手动重置 `runner.trace`——这一行是在弥补 `Runner` 把单次运行状态存在实例上的设计。
- `try/except GuardrailTripped` 演示了"tripwire 是可预期的控制流"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `policy` 函数代替 LLM | 离线、确定、可复现 | 看不到模型如何"选择工具"；真实 SDK 把 instructions 与工具列表发给模型 |
| handoff 用 `{"kind": "handoff", "to": ...}` 表达 | 代码简单 | 没有真正把 `transfer_to_*` 放进工具列表；真实 SDK 中 handoff 就是工具调用 |
| 一个 `GuardrailTripped` 类 + `which` 字段 | 少写类 | SDK 用两个异常类，便于分别捕获 |
| input guardrail 在循环前同步执行 | 演示阻塞语义最直观 | 没有默认的并行模式；并行需 async 并发与取消 |
| 不实现 tool guardrail、Session | 控制篇幅 | 与讲义 "Build It" 描述不一致；生产中工具调用必须有参数/权限检查 |
| `max_hops` 简单计数 | 防止死循环 | 工具调用也计入；耗尽时返回 `""` 而不报错；应分开计数并抛异常 |
| span 用嵌套对象，属性截断 | 打印直观 | 无 ID、无时间戳，无法导出到 OTel；截断不等于脱敏 |
| trace 存在 Runner 实例上 | 演示方便 | 不可并发、需手动重置；应让 `run` 返回包含 trace 的结果对象 |
| 关键词路由 / 子串 PII 检测 | 易读 | 误报（"assn"、"terrorist"）；生产用 LLM 路由与专用 PII 检测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 让类型注解延迟求值，可以在注解中引用尚未定义的类 |
| `@dataclass` | `@dataclass class Agent: ...` | 自动生成 `__init__`、`__repr__` 等，适合"只装数据"的类 |
| `field(default_factory=...)` | `field(default_factory=list)`、`field(default_factory=lambda: Span(name="run"))` | 可变默认值必须用工厂，避免多个实例共享同一个对象 |
| 前向引用注解 | `target: "Agent"`、`list["Span"]` | 用字符串引用后面才定义（或自身）的类型 |
| `@property` | `def tool_name(self) -> str` | 像访问属性一样调用方法：`handoff.tool_name` |
| 类型注解 | `Callable[[str], tuple[bool, str]]`、`dict[str, Any]` | 描述函数签名和容器元素类型，运行时不强制检查 |
| 自定义异常 | `class GuardrailTripped(Exception)` + `super().__init__(...)` | 继承 `Exception`，附加字段便于结构化处理 |
| `raise` / `try...except` | `raise GuardrailTripped("input", reason)`、`except GuardrailTripped as e:` | 抛出与捕获异常；`as e` 拿到异常对象 |
| `next(生成器, 默认值)` | `next((t for t in tools if t.name == tool_name), None)` | 取第一个满足条件的元素，找不到返回默认值 |
| `**kwargs` 解包 | `tool.fn(**args)` | 把字典展开成关键字参数 |
| `dict.get(key, default)` | `policy_output.get("args", {})` | 键不存在时返回默认值而不报 `KeyError` |
| 元组解包 | `ok, reason = guard.check(user_input)` | 一次接收多个返回值 |
| `for` + `break` / `continue` | hop 循环 | `break` 结束循环，`continue` 进入下一跳 |
| 字符串切片 | `instructions[:40]`、`final_output[:60]` | 取前 N 个字符，超出长度也不会报错 |
| f-string 与 `!r` | `f"{k}={v!r}"`、`f"transfer_to_{self.target.name}"` | `!r` 使用 `repr()`，字符串会带引号 |
| 生成器表达式 + `join` | `" ".join(f"..." for k, v in span.attributes.items())` | 拼接多个片段 |
| 递归 | `_print_span(child, indent + 1)` | 遍历树结构 |
| 字符串乘法 | `"  " * indent`、`"=" * 70` | 重复字符串生成缩进或分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，耗时不到 1 秒，输出完全确定）：

```text
======================================================================
OPENAI AGENTS SDK SHAPE — Phase 14, Lesson 16
======================================================================

--- case: I need a refund for invoice 4711 ---
final: billing handled: I need a refund for invoice 4711
span tree:
  run  user_input='I need a refund for invoice 4711'
    input_guardrail.pii_block  passed=True reason='ok'
    agent.triage  hop=0 instructions='route queries to the right specialist'
      handoff.transfer_to_billing  from='triage' to='billing'
    agent.billing  hop=1 instructions='handle refunds and invoices'
      llm_generation  output='billing handled: I need a refund for invoice 4711'
    output_guardrail.length_cap  passed=True reason='output 49 chars'

--- case: the CLI crashes on ctrl-c ---
final: support handled: the CLI crashes on ctrl-c
span tree:
  run  user_input='the CLI crashes on ctrl-c'
    input_guardrail.pii_block  passed=True reason='ok'
    agent.triage  hop=0 instructions='route queries to the right specialist'
      handoff.transfer_to_support  from='triage' to='support'
    agent.support  hop=1 instructions='handle bugs and errors'
      llm_generation  output='support handled: the CLI crashes on ctrl-c'
    output_guardrail.length_cap  passed=True reason='output 42 chars'

--- case: share my ssn with the team ---
GUARDRAIL: input: refuses to process social security numbers
span tree:
  run  user_input='share my ssn with the team'
    input_guardrail.pii_block  passed=False reason='refuses to process social security numbers'

every handoff is a tool named transfer_to_<agent>.
every guardrail trip is a structured exception, not a crash.
```

逐项解读：

- **用例 1**：输入含 `refund`，triage 在 hop 0 决定 handoff 到 billing；billing 在 hop 1 直接给出 final。共用 2 个 hop（上限 3）。输出 `"billing handled: " + 输入前 40 字符`，长度 49 < 200，output guardrail 通过。
- **用例 2**：`crashes` 包含子串 `crash`，路由到 support，结构与用例 1 相同，输出 42 字符。
- **用例 3**：输入含 `ssn`，input guardrail 在任何 agent 运行前就拒绝，span 树里只有一个 `passed=False` 的 guardrail span，没有任何 agent span——对应讲义 "reject unsafe or out-of-scope requests before any LLM call"。
- **span 树形状**：guardrail span 与 agent span 都是 `run` 的直接子节点；handoff span 是发起方 agent 的子节点；`llm_generation` 是生成答案的 agent 的子节点。这与讲义"two successful handoffs, one input guardrail trip"的描述一致。
- **没出现的路径**：演示用例没有覆盖 `tool` 分支、未知工具、未知 handoff、hop 耗尽、output guardrail 触发。我们用额外脚本验证了：A↔B 循环在 3 跳后返回 `''`；一个 250 字符的输出会触发 `GuardrailTripped('output', 'output 250 chars')`。

---

## 7. 动手改一改

1. **（入门）** 给 `main()` 加第 4 个用例 `"how is the weather"`，预测并验证 span 树（triage 直接 final，hop 只用 1 个）。再加一个会触发 `length_cap` 的 agent，观察 output guardrail 的 span。
2. **（讲义练习 1）** 把 hop 上限改成"超限即拒绝"：handoff 次数与总轮数分开计数，超限抛 `MaxHopsExceeded` 并写入 trace（参考测验 Q9）。
3. **（补齐讲义承诺）** 实现 `ToolGuardrail(name, check(tool_name, args))` 并接入 `kind == "tool"` 分支；给 support agent 加一个 `lookup_logs` 工具来验证（参考测验 Q10）。
4. **（讲义练习 2）** 实现 `nest_handoff_history` 选项：让 `run` 维护一个 `history: list[str]`，handoff 时可选择"完整传递"或"折叠成一行摘要"（可以先用"拼接前 N 条 + 截断"模拟摘要）。
5. **（讲义练习 3、4）** 用 `asyncio` 把 input guardrail 改成并行模式：`asyncio.gather` 同时跑 guardrail 与第一个 agent 的 `policy`（各用 `asyncio.sleep` 模拟延迟），比较阻塞/并行的耗时；再给 `Span` 加上 `start`/`end` 时间戳和 `span_id`/`parent_id`，写一个 `add_trace_processor` 风格的回调，把每个 span 输出成一行 JSON。
6. **（进阶，讲义练习 5）** 安装 `openai-agents` 并把这个玩具移植过去（需要 API key）：对比真实 SDK 中 handoff 如何出现在工具列表、guardrail 挂在哪里、trace 长什么样，列出本代码"建模错了"的地方。

---

## 8. 常见坑

- **把 hop 上限当作错误处理**：本代码 hop 耗尽时返回空字符串，output guardrail 还会显示通过。上线时务必让超限变成显式错误并告警。
- **复用 Runner 却不重置 trace**：`run` 只追加不清空，同一个 Runner 连续跑两次，trace 里有两次的 span；多线程共享 Runner 时 trace 会交错。
- **以为 tool guardrail 能兜住一切**：讲义提醒 tool guardrail 只对 function tool 生效，内置工具（文件读取、网页抓取）要另配策略；本代码甚至连 tool guardrail 都没有。
- **子串匹配误报**：`"ssn" in text` 会误伤 "assn"，`"bug" in text` 会命中 "rebuggy"。演示可以，生产不行。
- **把 `error: ...` 当正常答案**：未知工具、未知 handoff、未知 kind 都只是把错误文本写进 `final_output` 正常返回，调用方需要额外判断。
- **工具结果覆盖用户输入**：多步工具调用后 agent 会忘记用户最初的问题；正确做法是维护消息历史并追加。
- **dataclass 可变默认值**：如果把 `tools: list = []` 写成普通默认值，dataclass 会直接报错（`ValueError: mutable default`），必须用 `field(default_factory=list)`。
- **span 里放敏感内容**：截断（`[:40]`）不是脱敏，讲义建议内容外置存储、span 只存引用 ID。
