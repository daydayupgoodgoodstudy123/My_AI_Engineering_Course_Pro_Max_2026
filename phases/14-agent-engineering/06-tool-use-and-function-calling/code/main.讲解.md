# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 06 节 工具使用与 Function Calling ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；不调用任何 LLM，不需要 API key 和网络

> 同目录下的 `main.ts` 是同一逻辑的 TypeScript 移植（`npx tsx main.ts` 可运行，输出与 Python 版一致），本讲解以 `main.py` 为主，在第 8 节提一处 TS 版特有的坑。

---

## 1. 这份代码在考察什么

这份代码实现了一个"生产形状"的**工具注册表（tool registry）**——也就是 agent 运行时里位于"模型输出的 tool call"与"真正执行的函数"之间的那一层：

1. **工具定义**：每个工具 = `name` + `description` + `input_schema`（JSON Schema）+ 执行函数，对应讲义"Tool schema"一节。
2. **参数校验**：一个只用标准库的 JSON Schema 子集校验器，覆盖必填字段、六种基本类型、enum、minimum/maximum，对应讲义"Argument validation"。
3. **类型强制转换（coercion）**：模型常把整数写成字符串 `"4"`，能无歧义转换的就转换。
4. **结构化错误 observation**：未知工具、校验失败、执行异常，统统变成 `ToolResult(ok=False, content="...")`，**绝不把异常抛给 agent loop**。
5. **按 `tool_use_id` 关联的批量调用**：模拟"一个 assistant turn 里发出 5 个调用"。

> 一句话：**模型只会"说"要调用什么，这份代码演示的是运行时如何"不信任地"接住这些调用，并把每一种失败都变成模型能读懂、能重试的文字。**

需要提前知道的简化：没有真实模型（5 个调用是硬编码的）；`timeout_s` 只声明不生效；`dispatch_many` 是串行而非并行；没有任何 sandbox。这些都在下文标出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ToolDef` | dataclass | 工具定义：名字、描述、schema、执行器、超时 | Tool schema |
| `ToolCall` | dataclass | 模型发出的一次调用：`tool_use_id`、工具名、参数 | `tool_use` 块 |
| `ToolResult` | dataclass | 回传给模型的结果：`tool_use_id`、成功与否、内容 | `tool_result` 块 |
| `_coerce` | 函数 | 按 schema 的 `type` 做类型检查与有限的转换 | Type coercion |
| `validate` | 函数 | 必填、未知字段、类型、enum、范围，汇总所有错误 | Argument validation |
| `ToolRegistry` | 类 | 注册工具、输出 catalog、dispatch 单个/多个调用 | Tool registry / runtime |
| `add` / `multiply` / `classify` | 函数 | 三个演示工具，返回字符串 | 工具执行器 |
| `main` | 函数 | 注册工具 → 打印 catalog → 批量 dispatch 5 个调用 | 演示 trace |

数据流：`main` 注册 3 个工具 → `catalog()` 打印"模型看到的工具列表" → 构造 5 个 `ToolCall` → `dispatch_many` → 每个调用经过"查工具 → `validate`（内部调 `_coerce`）→ 执行器"→ 打印 `ToolResult`。

---

## 3. 逐段精讲

### 3.1 三个 dataclass：调用与结果的"协议形状"

```python
@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    executor: Callable[..., str]
    timeout_s: float = 5.0


@dataclass
class ToolCall:
    tool_use_id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    tool_use_id: str
    ok: bool
    content: str
```

- `ToolDef` 的前三个字段正是讲义里所有 provider 共有的形状：`name`、`description`、`input_schema`。字段名直接用了 Anthropic 的 `input_schema`（OpenAI 对应 `function.parameters`）。
- `executor: Callable[..., str]`：执行器返回**字符串**。工具结果最终要作为文本塞回对话，所以统一成 `str` 是合理的简化；真实系统里也可能返回 JSON 或多模态内容块。
- `ToolCall` 与 `ToolResult` 都带 `tool_use_id`，这就是讲义说的"correlation ID"：结果通过 ID 而不是顺序与调用对应。
- `ToolResult.ok` 对应 Anthropic `tool_result` 的 `is_error` 语义（取反）。
- ⚠️ `timeout_s` 在整个文件中**从未被读取**，详见 3.4。

### 3.2 `_coerce`：按类型检查，能转则转

```python
def _coerce(value: Any, schema: dict[str, Any]) -> tuple[Any, str | None]:
    t = schema.get("type")
    if t == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        if isinstance(value, str):
            try:
                return int(value), None
            except ValueError:
                return value, f"cannot coerce string {value!r} to integer"
        return value, f"expected integer, got {type(value).__name__}"
    if t == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value), None
        ...
```

- 返回值是 `(新值, 错误信息或 None)` 的二元组——用返回值而不是异常传递错误，调用方可以继续检查其他字段、**一次收集所有错误**。
- `not isinstance(value, bool)`：Python 中 `bool` 是 `int` 的子类，`isinstance(True, int)` 为 `True`。不排除的话，`True` 会被当成整数 1 通过校验。
- 字符串 → 整数：`int(value)`。这正是讲义"Model may return a string '5' where the schema says int. Coerce if unambiguous"。但 `int()` 比想象中宽松，实测：

| 输入 | 结果 |
|------|------|
| `"4"` | 4 |
| `" 7 "` | 7（忽略首尾空白） |
| `"1_0"` | 10（接受数字分隔下划线） |
| `"٤"`（阿拉伯-印度数字） | 4（接受任何 Unicode 十进制数字） |
| `"3.0"` | 报错 `cannot coerce string '3.0' to integer` |
| `5.0`（float） | 报错 `expected integer, got float` |
| `True` | 报错 `expected integer, got bool` |

  这就是讲义练习 2 问的"coercion 从哪里开始掩盖真正的 bug"（见测验 Q12）。
- `number` 分支：整数也会被 `float()` 转成浮点，`2` 变 `2.0`。
- ⚠️ `float("nan")`、`float("inf")` 都合法，`"nan"` 会一路通过（见 3.3）。
- `boolean`、`string`、`array`、`object` 只做类型检查，**不做转换**（`"true"` 不会变成 `True`）。`array` 不检查 `items`，`object` 不递归校验嵌套属性。
- 最后的 `return value, None`：schema 没写 `type` 或写了不认识的类型（如 `"null"`），一律放行。

### 3.3 `validate`：汇总所有错误

```python
def validate(args, schema):
    errors: list[str] = []
    props = schema.get("properties", {})
    required = schema.get("required", [])
    out: dict[str, Any] = {}

    for name in required:
        if name not in args:
            errors.append(f"missing required: {name}")

    for name, value in args.items():
        prop = props.get(name)
        if prop is None:
            errors.append(f"unknown field: {name}")
            continue
        coerced, err = _coerce(value, prop)
        if err:
            errors.append(f"{name}: {err}")
            continue
        if "enum" in prop and coerced not in prop["enum"]:
            errors.append(f"{name}: {coerced!r} not in {prop['enum']}")
            continue
        if prop.get("type") in ("number", "integer"):
            if "minimum" in prop and coerced < prop["minimum"]:
                ...
            if "maximum" in prop and coerced > prop["maximum"]:
                ...
        out[name] = coerced

    return out, errors
```

- 两轮检查：先查**必填字段是否缺失**，再逐个检查**模型给出的字段**。
- `unknown field`：schema 里没有的字段一律报错，相当于 JSON Schema 的 `additionalProperties: false`。这能抓住"模型把参数名写错"（如 `stauts`）的情况。
- 每个字段的检查顺序：类型/coercion → enum → 范围；任何一步失败就 `continue`，该字段不进入 `out`。
- **所有错误汇总后一起返回**：模型一次就能看到全部问题。实测 `validate({"a": -1, "s": "x"}, ...)` 返回 `['a: -1 < minimum 0', "s: 'x' not in ['open', 'closed']"]`。
- enum 检查在 coercion **之后**做，所以 `{"type": "integer", "enum": [1, 2]}` 能接受字符串 `"1"`。
- ⚠️ NaN 漏洞：`nan < 0` 与 `nan > 100` 都为 `False`，所以 `"nan"` 会绕过 minimum/maximum。实测 `validate({"p": "nan"}, {"properties": {"p": {"type": "number", "minimum": 0, "maximum": 100}}})` 返回 `({'p': nan}, [])`。修复见测验 Q9。
- 校验器忽略了顶层的 `"type": "object"`，只看 `properties` 和 `required`——它是一个"子集"实现，讲义开头也说明了范围。

### 3.4 `ToolRegistry`：注册、catalog、dispatch

```python
    def dispatch(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.tool_use_id, False,
                              f"error: unknown tool {call.name!r}")
        validated, errors = validate(call.args, tool.input_schema)
        if errors:
            return ToolResult(call.tool_use_id, False,
                              "validation error: " + "; ".join(errors))
        try:
            return ToolResult(call.tool_use_id, True, tool.executor(**validated))
        except Exception as e:
            return ToolResult(call.tool_use_id, False,
                              f"execution error: {type(e).__name__}: {e}")

    def dispatch_many(self, calls: list[ToolCall]) -> list[ToolResult]:
        return [self.dispatch(c) for c in calls]
```

- **三层防线**，每层都返回 `ToolResult` 而非抛异常：
  1. 工具不存在 → `error: unknown tool 'subtract'`（模型"幻觉"出不存在的工具）；
  2. 参数不合法 → `validation error: ...`；
  3. 执行器抛异常 → `execution error: ZeroDivisionError: division by zero`。
- 三种前缀不同，模型和日志都能区分"我调错了工具""我参数写错了""工具本身坏了"。
- `tool.executor(**validated)`：把校验后的字典解包成关键字参数。因为 `validate` 拒绝未知字段，不会传入执行器不认识的参数；但如果 schema 里某个字段**不是必填**而执行器又没有默认值，缺失时会变成 `execution error: TypeError: ... missing 1 required positional argument`（实测）——schema 与函数签名需要保持一致。
- `register` 用 `dict` 存储，同名工具会**静默覆盖**。
- `catalog()` 返回"发给模型的工具列表"，只包含 `name`、`description`、`input_schema`，不包含执行器——模型只需要知道"有什么、怎么调"。
- ⚠️ **超时没有实现**：`timeout_s` 存在 `ToolDef` 里，`dispatch` 却直接同步调用 `tool.executor`。实测一个 `timeout_s=0.1`、内部 `sleep(1)` 的工具会在 1.0 秒后返回 `ok=True`。
- ⚠️ **"parallel dispatch" 实际是串行**：`dispatch_many` 只是一个列表推导式。它展示了"一个 turn 多个调用、按 ID 回填"的**数据形状**，但没有并发执行。真正并发与超时的写法见测验 Q10、Q11。
- ⚠️ 没有 sandbox：执行器就在当前进程里运行，拥有进程的全部权限。讲义"Sandboxing"一节的读写面、网络、内存上限都没有体现。

### 3.5 演示工具与 `main`

```python
    reg.register(ToolDef(
        name="classify",
        description="Classify a status as one of the allowed labels.",
        input_schema={
            "type": "object",
            "properties": {"status": {"type": "string",
                                       "enum": ["open", "closed", "pending"]}},
            "required": ["status"],
        },
        executor=classify,
    ))
    ...
    calls = [
        ToolCall("u01", "add", {"a": 2, "b": 3}),
        ToolCall("u02", "multiply", {"a": "4", "b": 5}),
        ToolCall("u03", "classify", {"status": "in_progress"}),
        ToolCall("u04", "classify", {"status": "open"}),
        ToolCall("u05", "subtract", {"a": 1, "b": 2}),
    ]
```

五个调用各演示一种情况：

| ID | 场景 | 演示的机制 |
|----|------|-----------|
| u01 | 完全正确 | 正常路径 |
| u02 | 整数写成字符串 `"4"` | coercion 修复 |
| u03 | enum 外的值 `"in_progress"` | enum 校验（讲义原例） |
| u04 | 合法 enum 值 | 正常路径 |
| u05 | 不存在的工具 `subtract` | unknown tool / 幻觉工具 |

- 两个算术工具的 description 示范了讲义的要求：不只说"做什么"，还说"何时用"——`multiply` 写了 "Prefer multiplication over looped addition"，提示模型不要用多次 `add` 代替乘法。`classify` 的描述则比较弱，只说了做什么，配套 skill 文件把这类"只命名工具"的描述列为 hard reject。
- 讲义 Build It 说"a mini agent calling three tools in one turn, with one deliberately malformed call"，实际代码是 **5 个调用、2 个失败**（u03、u05），且没有任何 agent/模型参与，调用是写死的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库写 JSON Schema 子集 | 每条规则都看得见 | 不支持嵌套、`items`、`format`、`oneOf` 等；生产用 `jsonschema`、Pydantic、Zod（讲义练习 5） |
| 错误用返回值 `(value, err)` 传递 | 能一次收集所有字段的错误 | 需要调用方逐个检查；Pydantic 用 `ValidationError` 一次性带回全部错误 |
| 未知字段直接报错 | 抓住参数名拼写错误 | 与某些 provider 的宽松模式不同；可以按工具配置 |
| 字符串 → 数值的 coercion | 模型常见的无歧义错误自动修复 | `int()` 太宽松（空白、下划线、Unicode 数字）；`"nan"` 绕过范围检查；生产应限定格式并记录每次修复 |
| 三类错误统一成 `ToolResult(ok=False)` | 模型可读、可重试，循环不中断 | 需要配合重试上限、熔断，否则模型可能反复撞同一个错误 |
| `timeout_s` 只声明 | 保持演示简单 | 实际不生效；生产用子进程/容器做硬超时 |
| `dispatch_many` 串行 | 结果顺序天然与输入一致 | 不是真并行；生产用线程池/asyncio，并按 `tool_use_id` 回填 |
| 执行器在本进程运行 | 无需任何隔离设施 | 无 sandbox；生产要限定读写面、网络、内存，避免通用 shell 工具 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以在旧版本 Python 中使用 `str \| None`、`dict[str, Any]` 等写法 |
| `@dataclass` | `class ToolDef:` | 根据字段注解自动生成 `__init__`、`__repr__`、`__eq__` |
| dataclass 默认值 | `timeout_s: float = 5.0` | 有默认值的字段必须放在无默认值字段之后 |
| 位置参数构造 dataclass | `ToolCall("u01", "add", {...})` | 按字段声明顺序传参 |
| 类型注解 | `dict[str, Any]`、`Callable[..., str]`、`tuple[Any, str \| None]` | `Callable[..., str]` 表示"任意参数、返回 str 的可调用对象"；`X \| None` 表示可能为 None |
| `isinstance` 与元组 | `isinstance(value, (int, float))` | 判断是否属于其中任一类型 |
| `bool` 是 `int` 的子类 | `not isinstance(value, bool)` | `isinstance(True, int)` 为真，需要显式排除 |
| `try / except ValueError` | `int(value)` 转换失败 | 只捕获预期的异常类型 |
| `except Exception as e` | `dispatch` 中包住执行器 | 捕获所有常规异常；`type(e).__name__` 取异常类名 |
| 元组返回与解包 | `coerced, err = _coerce(value, prop)` | 一次返回多个值 |
| `!r` 格式符 | `f"{value!r}"`、`f"{call.name!r}"` | 用 `repr()` 显示，字符串会带引号，空白和特殊字符一目了然 |
| `dict.get` 默认值 | `schema.get("properties", {})` | 键不存在时返回默认值而不报错 |
| `**` 解包关键字参数 | `tool.executor(**validated)` | 把 `{"a": 2, "b": 3}` 变成 `executor(a=2, b=3)` |
| `str.join` | `"; ".join(errors)` | 用分隔符拼接列表 |
| 列表推导式 | `[self.dispatch(c) for c in calls]`、`catalog()` | 一行生成列表 |
| 私有约定 | `self._tools`、`_coerce` | 前导下划线表示"内部使用"，Python 不强制 |
| 条件表达式 | `tag = "OK " if result.ok else "ERR"` | 三元表达式 |
| 字符串乘法 | `"=" * 70` | 重复字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成）：

```text
======================================================================
TOOL USE and FUNCTION CALLING — Phase 14, Lesson 06
======================================================================

catalog (as presented to the model)
  - add: Add two integers a and b. Use for any integer addition.
  - multiply: Multiply two integers a and b. Prefer multiplication over looped addition.
  - classify: Classify a status as one of the allowed labels.

parallel dispatch (5 calls in one turn)
  u01 OK : 5
  u02 OK : 20
  u03 ERR: validation error: status: 'in_progress' not in ['open', 'closed', 'pending']
  u04 OK : classified as open
  u05 ERR: error: unknown tool 'subtract'

observation shape: every validation failure is a structured error
string the agent can read and retry against. never raise to the loop.
```

逐项解读：

- **catalog**：只打印了 name 和 description；真正发给模型的还包括 `input_schema`。description 是模型选工具的主要依据。
- **u01 → 5**：正常路径。
- **u02 → 20**：`"4"` 被 `_coerce` 转成整数 4。如果没有校验层，`"4" * 5` 在 Python 中会得到 `"44444"`——不报错但结果错误，比报错更危险。
- **u03 → ERR**：错误信息里列出了全部合法值 `['open', 'closed', 'pending']`，模型下一轮可以直接改成其中之一。这就是"structured observation"的价值。
- **u04 → OK**：同一工具的合法调用不受 u03 失败的影响——每个调用独立处理。
- **u05 → ERR**：模型调用了 catalog 中不存在的工具。错误前缀是 `error:` 而不是 `validation error:`，可区分。生产中可以在这里附上可用工具名列表，帮助模型改正。
- 输出顺序与输入顺序相同，是因为 `dispatch_many` 串行执行；如果真并发，必须靠 `tool_use_id` 而不是顺序来对应。

---

## 7. 动手改一改

1. **严格 coercion**：把 integer 的字符串转换改成只接受 `^-?[0-9]+$`，验证 `" 7 "`、`"1_0"`、`"٤"` 都被拒绝；给每次成功的 coercion 打一行日志（测验 Q12）。
2. **修 NaN 漏洞**：在 number 分支加 `math.isfinite` 检查，验证 `"nan"`、`"inf"` 被拒绝（测验 Q9）。
3. **讲义练习 1**：注册一个 `no_tool_applies(reason: str)` 工具，description 写明"当没有其他工具适用时调用"，设计 5 条"不该调用任何工具"的请求，思考如何统计误调用率。
4. **讲义练习 3**：用 `concurrent.futures` 让 `timeout_s` 生效，并加上"连续 3 次失败熔断 60 秒"的 circuit breaker（测验 Q10 有参考实现）。
5. **真并行**：把 `dispatch_many` 改成线程池并发，检测重复 `tool_use_id`，用 3 个 `sleep` 不同时长的工具验证总耗时约等于最慢那个（测验 Q11）。
6. **讲义练习 5**：用 Pydantic 为 `add` 定义参数模型（`a: int`、`b: int`），对比它对 `"4"`、`"3.0"`、`True`、`5.0` 的处理与本文件 `_coerce` 的差异，并用 `model_json_schema()` 生成可直接发给模型的 schema。

---

## 8. 常见坑

- **以为 `timeout_s` 会生效**：它只是字段。没有实际超时机制时，一个卡住的工具会卡住整个 agent。
- **忘了排除 bool**：`isinstance(True, int)` 为真；不加 `not isinstance(value, bool)`，`True` 会被当成 1。
- **`int()` 太宽松**：空白、下划线、非 ASCII 数字都能转；coercion 越宽松，越难发现模型真正的输出问题。
- **NaN 绕过范围检查**：任何与 NaN 的比较都为 `False`，min/max 检查必须先排除非有限值。
- **按返回顺序而非 `tool_use_id` 回填结果**：串行时碰巧正确，一改成并发就会把结果送错调用。
- **把异常抛给 agent loop**：循环中断，模型也没有机会修正。正确做法是像本文件一样把失败转成 observation。
- **错误信息只写 "error"**：模型无从修正，往往原样重试；要写清楚哪个字段、期望什么、合法值有哪些。
- **schema 与执行器签名不一致**：可选字段缺失时执行器可能因缺参数抛 `TypeError`；schema 应由函数签名或 Pydantic 模型生成，避免两处手写。
- **TS 版的空串陷阱**：`main.ts` 用 `Number(value)` 做转换，而 `Number("")`、`Number(" ")` 都等于 `0` 且是整数，所以空字符串会被当作合法整数 0 通过校验；Python 版的 `int("")` 则会报错。移植校验逻辑时要逐一核对语言差异。
