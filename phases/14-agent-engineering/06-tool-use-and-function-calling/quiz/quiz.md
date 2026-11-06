# 测验 · 工具使用与 Function Calling（Tool Use and Function Calling）

> **阶段 14 · Agent 工程 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义是机器翻译，质量较差（例如把 Toolformer 译成"Toolex""工具前端"，把 BFCL 译成"英国联邦金融法系"）。遇到读不通的地方请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Toolformer 的自监督信号 | 让模型在预训练语料里自己插入候选 API 调用、真的执行，**只保留"插入工具结果后下一个 token 的 loss 下降"的标注**，再在过滤后的语料上微调；全程无人工标签 |
| 2 | 工具能力随规模涌现 | 讲义："Smaller models hurt from tool annotations; larger models gain"——所以 7B 级模型通常需要专门的 tool-use 微调才可靠 |
| 3 | BFCL V4 的五类权重 | Agentic 40%、Multi-Turn 30%、Live 10%、Non-Live 10%、Hallucination 10%（讲义口径） |
| 4 | 基于状态的评估（V3 起） | 不再比对 tool call 的 AST，而是检查调用序列结束后 API 的**真实状态**（如"文件真的创建了吗"） |
| 5 | 2026 年仍未解决的问题 | 单轮调用已接近解决；失败集中在 memory（跨轮记忆）、dynamic decision-making（依据前一步结果选工具）、long-horizon（20+ 步后漂移）、hallucination detection（没有合适工具时拒绝调用） |
| 6 | 工具 schema 三件套 | `name` + `description`（做什么、**何时用**）+ `input_schema`（JSON Schema）；Anthropic 叫 `input_schema`，OpenAI 叫 `function.parameters`；description 写得差是"选错工具"的头号原因 |
| 7 | 参数校验四件事 | 类型强制转换（无歧义才转）、enum 校验、必填字段、格式校验（用真正的解析器而不是正则）；**每个失败都返回结构化 observation，让模型重试，而不是让循环崩溃** |
| 8 | 并行 tool call 与 `tool_use_id` | 一个 assistant turn 可发出多个调用，每个结果按 `tool_use_id` 回填为 `tool_result`；ID 对错位 = 结果路由错位 |
| 9 | Sandboxing | 工具执行就是 sandbox 边界：每个工具声明读写面、网络、超时、内存上限；通用 `run_shell(cmd)` 是红旗，具体的 `git_status()` 更安全 |
| 10 | 本节代码的边界 | `timeout_s` 只声明未执行、`dispatch_many` 实为串行、`"nan"` 能绕过 min/max——"production-shape"只是形状，不是生产级 |

### 核心技能（能动手做到）

- [ ] 用标准库写出一个 JSON Schema 子集校验器（required / type / enum / minimum / maximum），并把所有错误汇总成一条可读的 observation
- [ ] 为每种类型制定"能转就转、有歧义就拒"的 coercion 规则，并说出 Python `int()` 会意外接受哪些字符串
- [ ] 实现按 `tool_use_id` 回填结果的并行 dispatch，并保证结果顺序与 ID 对应
- [ ] 给工具加上真正生效的 timeout 和 circuit breaker（连续失败 N 次后熔断一段时间）
- [ ] 写出"告诉模型何时用、何时不用"的工具 description，识别两个工具描述重叠的风险
- [ ] 解释 BFCL V4 各类别测什么，并为自己的 agent 设计一个 hallucination（该不调用时不调用）小测

---

## 二、基础自测（选择题）

**Q1.** Toolformer 用什么信号决定是否保留一条候选工具调用标注？

- A. 把工具执行结果插入文本后，后续 token 的预测 loss 是否下降
- B. 人工标注员是否认为这次调用有用
- C. 工具是否在 100 ms 内返回
- D. 工具返回的内容是否为合法 JSON

**Q2.** 按讲义，BFCL V4 中权重最大的类别是：

- A. Multi-Turn（多轮对话中的工具链）
- B. Live（用户提交的真实 prompt）
- C. Hallucination（检测不该调用工具的情况）
- D. Agentic（完整 agent 轨迹：记忆、多轮、动态决策）

**Q3.** 运行 `code/main.py`，调用 `ToolCall("u02", "multiply", {"a": "4", "b": 5})` 的结果是：

- A. `u02 ERR: validation error: a: expected integer, got str`
- B. `u02 OK : 20`
- C. `u02 OK : 44444`（字符串重复）
- D. `u02 ERR: execution error: TypeError: can't multiply sequence by non-int`

**Q4.** BFCL V3 引入的 state-based evaluation 主要想抓住哪类问题？

- A. 工具调用耗时过长
- B. 模型输出的 JSON 不合法
- C. 调用序列在语法（AST）上看起来正确，但执行后 API 的实际状态不对
- D. 工具 schema 版本漂移

**Q5.** 一个 assistant turn 里模型发出了 3 个并行 tool call。运行时把它们并发执行后，结果返回顺序是 2、3、1。正确的处理方式是：

- A. 按返回顺序依次作为 `tool_result` 发回，模型会自己猜对应关系
- B. 丢弃先返回的结果，等最慢的那个回来再统一重跑
- C. 把三个结果拼成一个字符串放进一条 user 消息里
- D. 每个结果都带上对应调用的 `tool_use_id` 作为 `tool_result` 块发回，由 ID 而不是顺序决定对应关系

**Q6.** 对 schema `{"type": "integer"}`，本节 `_coerce` 会**接受**下面哪个输入（返回无错误）？

- A. 字符串 `" 7 "`（前后有空格）
- B. 浮点数 `5.0`
- C. 布尔值 `True`
- D. 字符串 `"3.0"`

**Q7.** 讲义说通用的 `run_shell(cmd)` 工具是"red flag"，最主要的原因是：

- A. Shell 命令执行太慢
- B. 各家 provider 都会拒绝名为 `run_shell` 的工具
- C. 它把 sandbox 边界放大到整个主机：读写面、网络、破坏性操作都无法按工具粒度约束；`git_status()` 这类具体动词才能限定风险面
- D. 它不能并行调用

**Q8.** 本节 `ToolDef` 有字段 `timeout_s: float = 5.0`。如果注册一个会 `time.sleep(10)` 的工具并调用它，`ToolRegistry.dispatch` 会：

- A. 5 秒后抛出 `TimeoutError`，被捕获为 `execution error`
- B. 一直等到 10 秒后执行完毕，返回 `ok=True`——`timeout_s` 在代码里从未被读取
- C. 立即返回 `validation error`，因为 timeout 超出上限
- D. 由 `dispatch_many` 自动取消并返回 `ok=False`

---

## 三、动手 / 代码题

**Q9.** 阅读 `validate` 中数值范围检查的部分：

```python
        coerced, err = _coerce(value, prop)
        ...
        if prop.get("type") in ("number", "integer"):
            if "minimum" in prop and coerced < prop["minimum"]:
                errors.append(f"{name}: {coerced} < minimum {prop['minimum']}")
                continue
            if "maximum" in prop and coerced > prop["maximum"]:
                errors.append(f"{name}: {coerced} > maximum {prop['maximum']}")
                continue
        out[name] = coerced
```

对 schema `{"p": {"type": "number", "minimum": 0, "maximum": 100}}`，分别传入 `"nan"`、`"-inf"`、`"inf"`、`"50"`、`150`，`validate` 各返回什么？哪一个是漏洞？怎么修？

**Q10.** 讲义练习 3：给 registry 加上**真正生效的** per-tool timeout，以及 circuit breaker（同一工具连续失败 3 次后，60 秒内拒绝调用）。请写出改造后的 `dispatch`，并回答：熔断时返回给模型的 observation 应该怎么写，才能帮助模型恢复？Python 的线程超时有什么局限？

**Q11.** `dispatch_many` 的实现是：

```python
    def dispatch_many(self, calls: list[ToolCall]) -> list[ToolResult]:
        return [self.dispatch(c) for c in calls]
```

1. 它真的是"parallel dispatch"吗？三个分别耗时 0.3s、0.1s、0.2s 的调用，总耗时是多少？
2. 改成真正并发执行，同时保证返回列表的顺序与 `calls` 一一对应；顺便检测重复的 `tool_use_id`。
3. 什么情况下**不应该**并行执行同一 turn 的多个调用？

**Q12.** 讲义练习 2 问："Where does coercion start to hide real bugs?" 本节 `_coerce` 对 integer 直接调用 `int(value)`。实际运行发现以下字符串都会被接受：`" 7 "` → 7、`"1_0"` → 10、`"٤"`（阿拉伯-印度数字 4）→ 4，而 `"3.0"` 被拒绝。

1. 解释为什么这些看似"宽容"的转换可能掩盖真正的 bug。
2. 设计一个更严格的 integer coercion 策略，并说明哪些情况应该拒绝而不是转换。
3. 对 `type: "number"` 的 int 输入，`_coerce` 返回 `float(value)`。这会对工具输出产生什么可见影响？

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一次 function calling 的端到端流程：模型到底做了什么、运行时（runtime）做了什么？为什么说"模型从不真正执行工具"？

**Q14.**（原理深挖）Toolformer 是怎么在没有人工标签的情况下学会调用工具的？为什么讲义说小模型会被工具标注"伤害"、大模型才受益？这对今天选择开源模型做 agent 有什么启示？

**Q15.**（工程实践）你负责一个生产 agent 的工具层。请设计参数校验与错误回传策略：哪些错误自动修复、哪些拒绝、错误信息怎么写、如何避免模型陷入"重复同一个错误调用"的死循环？

**Q16.**（场景设计）一个客服 agent 挂了 45 个工具，线上日志显示"选错工具"占失败的大头。你会怎么排查和改进？

**Q17.**（追问型）BFCL 的 Hallucination 类别测"没有合适工具时不调用"。为什么这件事难？你会怎么在自己的 agent 上测量和改进它？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Keep the annotation only if including the tool result reduces loss on the next token." 这是纯自监督：信号来自"工具结果是否帮助预测文本"，不需要人工判断（B 错）。C、D 是工程层面的指标，与 Toolformer 的训练信号无关。

### Q2 — 答案：D

讲义口径：Agentic 40%、Multi-Turn 30%、Live 10%、Non-Live 10%、Hallucination 10%。Agentic 占比最大，体现出评测重心已从"单次调用对不对"转向"完整轨迹能否完成任务"。A 是第二大（30%）；B、C 各 10%。

### Q3 — 答案：B

实际运行输出为 `u02 OK : 20`。schema 规定 `a` 是 `integer`，`_coerce` 遇到字符串时尝试 `int("4")` 成功，于是 `a` 被转换为整数 4，执行 `multiply(4, 5)` 得 `"20"`。A 是"不做 coercion"的严格校验器会给出的结果；C 只有在跳过校验、直接把字符串传给 `a * b` 时才会出现（`"4" * 5` 在 Python 中得到 `"44444"`，不会报错，错得更隐蔽）；D 的报错要在 `"4" * "5"` 这类两个字符串相乘时才出现。这说明校验层把类型问题挡在了执行之前。

### Q4 — 答案：C

讲义："after a tool sequence, check the API's actual state (e.g. 'is the file created?') rather than match the AST of the tool calls." AST 匹配会误判两类情况：调用写法不同但效果相同（假阴性），以及调用看起来对、实际状态错（假阳性）。A、B、D 都不是 state-based evaluation 的目标。

### Q5 — 答案：D

讲义："Each result goes back as a `tool_result` block correlated by `tool_use_id`"，并强调"treat correlation IDs as load-bearing"。A 依赖顺序，并发时顺序不可靠，模型会把结果对错；B 浪费且没必要；C 丢失了结构化的对应关系，也不符合 provider 协议（Anthropic 要求每个 `tool_use` 都有对应 `tool_result`）。

### Q6 — 答案：A

实际测试：`validate({"a": " 7 "})` 返回 `a = 7`——Python 的 `int()` 会忽略首尾空白。B：`isinstance(5.0, int)` 为假，也不是字符串，报 `expected integer, got float`；C：代码特意用 `not isinstance(value, bool)` 排除布尔值（`bool` 是 `int` 的子类），报 `expected integer, got bool`；D：`int("3.0")` 抛 `ValueError`，报 `cannot coerce string '3.0' to integer`。

### Q7 — 答案：C

讲义："every tool should specify read/write surface, network access, timeout, memory cap. Generic `run_shell(cmd)` is a red flag; specific `git_status()` is safer." 问题在于权限面而不是速度（A）或并行（D）；provider 并不会按名字拒绝工具（B）。配套的 skill 文件也把"Generic shell/command-exec tool"列为 hard reject，要求拆成 `git_status`、`fs_read`、`npm_test` 等具体动词。

### Q8 — 答案：B

`ToolDef.timeout_s` 只是数据字段，`dispatch` 中直接 `tool.executor(**validated)` 同步调用，没有任何地方读取 `timeout_s`。实测：注册 `timeout_s=0.1`、内部 `sleep(1)` 的工具，`dispatch` 耗时 1.0 秒并返回 `ok=True, content='done'`。A 是"期望中的行为"，需要自己实现（见 Q10）；C、D 在代码里都不存在。这是讲义"Tool registration with ... timeout"与代码实现之间的落差。

### Q9 — 参考答案

实际运行结果：

| 输入 | `validate` 返回 |
|------|----------------|
| `"nan"` | `({'p': nan}, [])` ——**通过** |
| `"-inf"` | `({}, ['p: -inf < minimum 0'])` |
| `"inf"` | `({}, ['p: inf > maximum 100'])` |
| `"50"` | `({'p': 50.0}, [])` |
| `150` | `({}, ['p: 150.0 > maximum 100'])` |

漏洞是 `"nan"`：`float("nan")` 合法，而 NaN 与任何数比较都返回 `False`，所以 `nan < 0` 和 `nan > 100` 都不成立，范围检查被绕过，NaN 被交给执行器。`inf` 碰巧会被 min/max 拦住，但如果 schema 没写范围也会放行。

修复：在 number 的 coercion 之后拒绝非有限值。

```python
import math

    if t == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            v = float(value)
        elif isinstance(value, str):
            try:
                v = float(value)
            except ValueError:
                return value, f"cannot coerce string {value!r} to number"
        else:
            return value, f"expected number, got {type(value).__name__}"
        if not math.isfinite(v):
            return value, f"number must be finite, got {value!r}"
        return v, None
```

要点：JSON 标准本身不允许 NaN/Infinity，模型几乎不会合法地需要它们；校验器应该把它们当作错误而不是数值。

### Q10 — 参考答案

参考实现（已实际运行验证）：

```python
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout

class SafeRegistry(ToolRegistry):
    def __init__(self, max_fail=3, cooldown=60.0, clock=time.monotonic):
        super().__init__()
        self._fails, self._open_until = {}, {}
        self.max_fail, self.cooldown, self.clock = max_fail, cooldown, clock
        self._pool = ThreadPoolExecutor(max_workers=8)

    def dispatch(self, call):
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.tool_use_id, False, f"error: unknown tool {call.name!r}")
        now = self.clock()
        if self._open_until.get(call.name, 0) > now:          # 熔断中
            return ToolResult(call.tool_use_id, False,
                f"error: tool {call.name!r} temporarily disabled after repeated failures; "
                "try another approach")
        validated, errors = validate(call.args, tool.input_schema)
        if errors:
            return ToolResult(call.tool_use_id, False, "validation error: " + "; ".join(errors))
        fut = self._pool.submit(tool.executor, **validated)
        try:
            res = ToolResult(call.tool_use_id, True, fut.result(timeout=tool.timeout_s))
        except FTimeout:
            res = ToolResult(call.tool_use_id, False, f"timeout: {call.name} exceeded {tool.timeout_s}s")
        except Exception as e:
            res = ToolResult(call.tool_use_id, False, f"execution error: {type(e).__name__}: {e}")
        if res.ok:
            self._fails[call.name] = 0
        else:
            n = self._fails.get(call.name, 0) + 1
            self._fails[call.name] = n
            if n >= self.max_fail:                              # 打开熔断器
                self._open_until[call.name] = now + self.cooldown
                self._fails[call.name] = 0
        return res
```

实测：对一个总是抛 `RuntimeError` 的工具连续调用 5 次，前 3 次返回 `execution error: RuntimeError: upstream 503`，第 4、5 次返回 `temporarily disabled ...`；`timeout_s=0.1` 的 `sleep(0.5)` 工具返回 `timeout: slow exceeded 0.1s`。

- **observation 怎么写**：说清楚"发生了什么、持续多久、下一步可以做什么"，例如"工具 X 已因连续 3 次失败暂停 60 秒，请改用 Y 或向用户说明"。只说"error"会让模型原地重试，正好撞上熔断。
- **设计细节**：是否把 validation error 计入失败次数是一个取舍——计入可以阻止模型反复发同一个错误调用，但它反映的是模型的问题而不是工具的问题；上面的实现**不计入**（校验失败直接 return）。
- **Python 线程超时的局限**：`fut.result(timeout=...)` 只是**不再等待**，后台线程仍在运行，无法被强制杀掉；如果工具有副作用（写文件、发请求），超时后副作用仍可能发生。真正的硬超时需要子进程（`subprocess` + `timeout`）、容器或 asyncio 中可取消的 I/O。注入 `clock` 参数是为了让测试可以快进时间而不必真等 60 秒。

### Q11 — 参考答案

1. 不是。列表推导式按顺序逐个调用 `dispatch`，总耗时约为各调用之和 0.6s。注释和讲义说"parallel dispatch"，但它只演示了"一个 turn 里有多个调用"的**数据形状**，执行本身是串行的。
2. 参考实现（已运行，三个调用总耗时 0.3s，即最慢那个）：

```python
from concurrent.futures import ThreadPoolExecutor

def dispatch_many(self, calls):
    ids = [c.tool_use_id for c in calls]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate tool_use_id in one turn")
    with ThreadPoolExecutor(max_workers=len(calls) or 1) as ex:
        futs = {c.tool_use_id: ex.submit(self.dispatch, c) for c in calls}
        return [futs[i].result() for i in ids]      # 按原顺序取回，ID 与结果一一对应
```

   每个 `ToolResult` 本身也携带 `tool_use_id`，即使调用方按完成顺序消费，也能正确回填。
3. 不应并行的情况：调用之间有数据依赖（第二个调用需要第一个的结果，此时模型本就不该在同一 turn 发出）；多个调用写同一资源（两个 `fs_write` 同一文件、扣同一账户余额）会产生竞态；工具对外部服务有速率限制；存在需要人工确认的破坏性操作。工程上常见做法是给工具打标签（只读 / 写入 / 破坏性），只对只读工具并发。

### Q12 — 参考答案

1. **宽容转换掩盖 bug 的方式**：
   - `"1_0"` → 10：模型可能是想写 `"1.0"` 或 `"10"`，转换器替它"猜"了一个值；如果其实是 `"1_000"` 之类的格式错误，下游拿到的数字就是错的且没有任何告警。
   - `"٤"` → 4：Python `int()` 接受任何 Unicode 十进制数字。来自用户输入或网页内容的字符被悄悄解释成数字，日志里看起来又像一个普通的 4，很难追查。
   - `" 7 "` → 7：通常无害，但说明模型输出里混入了格式噪声，长期掩盖了 prompt 或 schema 的问题。
   - 更普遍的问题：coercion 让"模型输出类型错误"这一信号消失了，你无法统计模型到底多常出错，也就无法改进 description 或换模型。
2. **更严格的策略**：
   - 只接受匹配 `^-?[0-9]+$`（ASCII 数字、可选负号）的字符串，转换前不做 `strip`；
   - 拒绝 `"3.0"`、`"1e3"`、`"0x10"`、千分位 `"1,000"`、下划线、全角/非 ASCII 数字；
   - 对 bool、float 一律拒绝（即使 `5.0` 是整数值，也要求模型修正）；
   - 每次成功 coercion 记一条日志/指标，让"被修复的调用"可观测。
   - 与 skill 文件的建议一致："accept int-as-string, reject float-as-string"。
3. `add`/`multiply` 的 schema 是 integer，不受影响；但若某个工具的参数是 `number`，传入 `2` 会变成 `2.0`，执行器 `str(a + b)` 将输出 `"5.0"` 而不是 `"5"`。模型看到的结果格式随之变化，可能影响后续推理或与期望值的字符串比较。这是"coercion 不只改类型，也改语义表现"的例子。

### Q13 — 参考回答要点

- **定义工具**：开发者把每个工具的 `name`、`description`、`input_schema`（JSON Schema）随请求发给模型。
- **模型决策**：模型阅读用户消息和工具 catalog，输出一个或多个**结构化的调用意图**（Anthropic 的 `tool_use` 块 / OpenAI 的 `tool_calls`），包含工具名、参数 JSON 和 `tool_use_id`；也可以选择不调用、直接回答。
- **运行时执行**：你的代码解析调用、做参数校验（类型、enum、必填、格式）、在 sandbox 内执行、处理超时与异常。
- **结果回填**：每个结果作为 `tool_result`（带 `tool_use_id`）追加到对话，再次请求模型；模型据此决定继续调用还是给出最终回答。这就是 [阶段 14 · 01](../../01-the-agent-loop/docs/zh.md) 的 agent loop。
- **"模型不执行工具"**：模型只产出文本（结构化 token），所有副作用都发生在你的运行时里。所以安全、权限、超时、审计都必须由运行时负责，不能指望模型"自觉"。
- 加分点：错误也要作为 `tool_result` 回传（如本节 `ToolResult(ok=False, ...)`），而不是抛异常中断循环；`is_error` 之类的标志能帮助模型区分失败与正常结果。

### Q14 — 参考回答要点

- **方法**：
  1. 用少量示例 prompt 让模型在语料中插入候选 API 调用（计算器、QA 系统、搜索、翻译、日历）；
  2. 真正执行这些调用拿到结果；
  3. 比较"带调用+结果"与"不带"两种情况下后续 token 的 loss，只保留明显降低 loss 的标注；
  4. 在过滤后的语料上微调。信号完全来自"工具是否帮助预测文本"。
- **为什么小模型受损**：讲义："tool use emerges at scale. Smaller models hurt from tool annotations; larger models gain." 直观理解：小模型容量有限，插入的调用语法和结果会打断语言建模，且小模型难以学会"何时调用、如何利用结果"，净效果为负；大模型能把工具当作外部能力整合进推理。
- **对选型的启示**：讲义："2026 frontier models have strong tool use baked in while most 7B models need explicit tool-use fine-tuning to be reliable." 用小开源模型做 agent 时，应选做过 function calling 微调的版本，并在自己的工具集上测（如 BFCL 类别），不要假设"能聊天就能调工具"。
- 常见误区：把 Toolformer 理解成"人工标注工具调用数据再 SFT"——恰恰相反，它的卖点就是无需人工标签。

### Q15 — 参考回答要点

- **分层处理**：
  - 未知工具 → 返回"工具不存在 + 可用工具列表"；
  - 缺必填字段 / 未知字段 / enum 不符 → 直接拒绝，错误信息里列出合法值（本节输出 `status: 'in_progress' not in ['open', 'closed', 'pending']` 就是好例子）；
  - 无歧义的类型偏差（`"4"` → 4）→ 自动修复并记录指标；有歧义的（`"3.0"` → int、`"1,000"`）→ 拒绝；
  - NaN/Infinity、超范围 → 拒绝（见 Q9）；
  - 格式（日期、邮箱、URL）→ 用真正的解析器校验（讲义："with concrete parsers, not regex"）。
- **错误信息原则**：结构化、一次列出全部问题（本节 `validate` 会汇总所有错误再返回，模型一次就能改完）、说明期望的形状，永不 raise 到循环。
- **防死循环**：同一工具 + 相同参数连续失败 N 次则改变 observation（提示换思路）；circuit breaker（见 Q10）；全局步数/token 预算；把重复失败计入评估指标。
- **可观测性**：每个调用打 OpenTelemetry GenAI span（skill 文件提到 `gen_ai.tool.name`、`gen_ai.tool.call.id` 等属性），统计每个工具的校验失败率，反过来改 description 和 schema。
- 加分点：生产中用 Pydantic / Zod 或 provider 的 strict mode（约束解码）从源头减少格式错误，校验器作为最后一道防线。

### Q16 — 参考回答要点

- **先量化**：从 trace 中按"期望工具 vs 实际工具"做混淆矩阵，找出最常被混淆的工具对。
- **改 description**：讲义："Bad tool descriptions are the #1 root cause of wrong-tool-picked failures." 每个描述要写"做什么、何时用、何时不用、和相似工具的区别"；两个工具描述重叠时合并或重写（skill 文件："Same description for two different tools" 是 hard reject）。
- **收缩工具数**：skill 文件规定单个 agent 超过 30 个工具应拒绝并改为 subagent 委派。可以按领域拆成路由器 + 子 agent，或按对话阶段动态加载工具子集。
- **改 schema**：用 enum 约束封闭集合，减少"参数对但工具错"的歧义；命名用清晰的 snake_case 动词。
- **建评测**：构造覆盖每个工具及易混淆场景的回归集（含"不应调用任何工具"的样例），每次修改 description 都跑一遍，参考 BFCL 的类别设计。
- 常见误区：只加长 system prompt 叮嘱"请选择正确的工具"；问题通常在工具定义本身。

### Q17 — 参考回答要点

- **为什么难**：模型被训练成"乐于助人"，看到工具就倾向于调用；工具描述越宽泛越容易被硬套；用户请求与某个工具"表面相似"（例如问天气但只有日历工具）时，模型可能编造参数调用最接近的工具，甚至调用不存在的工具（本节 `u05` 调用 `subtract` 就是模拟这种情况）。
- **测量**：构造一组"没有合适工具"的请求和一组"有合适工具"的对照请求，分别统计误调用率和漏调用率；把"调用了不存在的工具"单独计数。
- **改进**：
  - 讲义练习 1：提供一个显式的 no-op / "refuse" 工具，让模型有一个合法的"不做"选项；
  - description 写明适用边界（"仅当……时使用"）；
  - system prompt 允许并鼓励"没有合适工具时直接说明"；
  - 运行时对未知工具返回明确错误，而不是静默忽略；
  - 对高风险工具加确认门（confirmation gate）。
- 加分点：说明 hallucination 与 multi-turn/memory 相关——前几轮调过某工具，后面模型更容易在不合适时也调用它。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：tool call 是 agent loop 中"行动"的具体形式，结果回填即"观察"。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)、[阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)：各家 provider 的工具 schema 与消息格式（讲义的先修写的是"Phase 13 · 01 (Function Calling Deep Dive)"，按索引该标题对应 13 · 02）。
- [阶段 11 · 09 Function Calling 与工具使用](../../../11-llm-engineering/09-function-calling/docs/zh.md)：应用层视角的 function calling 入门。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：JSON Schema 与约束解码，是参数校验的上游。

### 本节被哪些后续内容用到
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：真正的并行与流式工具调用。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../../13-tools-and-protocols/05-tool-schema-design/docs/zh.md)：如何写出"load-bearing"的 description。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：工具执行的权限与沙箱边界。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：讲义列出的未解决问题之一"memory"，下一节用工具调用实现记忆分页。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为每个 tool call 打 span。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)、[阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：工具失败的分类与评测驱动改进。

### 延伸关键词
`Toolformer` · `BFCL V4` · `state-based evaluation` · `tool_use / tool_result` · `tool_use_id` · `JSON Schema` · `strict mode` · `Pydantic / Zod` · `argument coercion` · `circuit breaker` · `sandboxing` · `hallucination detection` · `parallel tool calls`
