# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 04 节 Structured Output：JSON Schema、Pydantic、Zod 与约束解码 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`json`、`re`、`dataclasses`、`typing`）；需要 Python 3.9+（用到 `str.removeprefix`）。无 LLM、无网络

---

## 1. 这份代码在考察什么

这份代码不调用任何模型，而是站在"模型输出已经拿到手"的位置，演示宿主如何把一段原始字符串变成可信的结构化数据：

1. **一个 strict 风格的 schema**：`INVOICE_SCHEMA` 用 `minLength/maxLength`、`pattern`、`integer + minimum`、`enum`、`required`、`additionalProperties: false` 描述发票。
2. **一个比第 01 节完整得多的校验器**：支持 object / array / string / number / integer / boolean、范围、长度、pattern、enum、额外字段，并返回**带路径**的 `ValidationError` 列表。
3. **讲义的三种失败模式**：`process_model_output` 把输入分成 `refusal` / `parse_error` / `violation` / `ok` 四个结果。
4. **五个测试用例**：成功、尾逗号、额外字段 + 坏 sku、缺必填字段、拒绝。

> 一句话：**受约束解码在 provider 端消灭了 parse_error 和 violation，但宿主代码仍要能识别这三种结果——尤其是 refusal——并在非 strict 场景下自己兜底。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `INVOICE_SCHEMA` | 常量 dict | 发票的 JSON Schema（嵌套对象 + 数组） | JSON Schema 2020-12 / strict 风格 |
| `ValidationError` | dataclass | `path` + `message`，`__str__` 输出 `"$.a.b: msg"` | 带路径的错误，便于反馈重试 |
| `validate` | 递归函数 | 按 `type` 分派检查，收集所有错误 | schema violation 检测 |
| `ParsedResult` | dataclass | `kind` / `payload` / `errors` | 带类型的处理结果 |
| `process_model_output` | 函数 | 先判拒绝 → 再 `json.loads` → 再校验 | 三种失败模式 |
| `TEST_CASES` | 列表 | 5 个 `(名称, 原始字符串)` | 各分支的测试输入 |
| `main` | 函数 | 逐个处理并打印结果 | 演示入口 |

数据流：原始字符串 `raw` → `process_model_output` →（`__REFUSAL__` 前缀？→ refusal）→ `json.loads`（失败 → parse_error）→ `validate`（有错 → violation）→ ok。

---

## 3. 逐段精讲

### 3.1 `INVOICE_SCHEMA`

```python
INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "customer": {"type": "string", "minLength": 1, "maxLength": 200},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
                    "qty": {"type": "integer", "minimum": 1},
                    "unit_usd": {"type": "number", "minimum": 0},
                },
                "required": ["sku", "qty", "unit_usd"],
                "additionalProperties": False,
            },
        },
        "total_usd": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["USD", "EUR", "INR"]},
    },
    "required": ["customer", "line_items", "total_usd", "currency"],
    "additionalProperties": False,
}
```

- 这个 schema 满足 OpenAI strict 的三条要求：每个对象的全部属性都在 `required` 中、每个对象都有 `additionalProperties: False`、没有 `$ref`。
- 每个约束对应一种真实的抽取错误：`minLength: 1` 防空客户名；`pattern` 规定 sku 只能是大写字母、数字和连字符；`qty` 必须是 ≥ 1 的整数；`currency` 用 `enum` 限定封闭集合。
- 没有约束 `line_items` 的长度（可以是空数组），也无法表达"total 等于明细之和"这种跨字段约束（见 3.6）。
- ⚠️ 讲义 Pydantic 示例用 `total_usd: Decimal`，而这里是 `number`——JSON 本身没有十进制类型，金额在代码中应转成 `Decimal` 处理。

### 3.2 `ValidationError`：带路径的错误

```python
@dataclass
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"
```

- 路径用类 JSONPath 的写法：`$` 是根，`.key` 是对象字段，`[i]` 是数组下标，例如 `$.line_items[0].sku`。
- 讲义："The validator returns a typed `[ValidationError]` list with path and message. That is the shape you want surfaced to the retry prompt." 带路径的错误能让模型精确知道改哪里。
- 重写 `__str__` 后，`print(e)` 和 f-string `{e}` 都会显示 `"$.x: msg"`；`repr` 仍是 dataclass 自动生成的形式。
- 注意它与 Python 内置的异常不同：这是一个**普通数据类**，不是 `Exception` 子类，不会被 `raise`。

### 3.3 `validate`：object 与 array 分支

```python
    if t == "object":
        if not isinstance(value, dict):
            return [ValidationError(path, f"expected object, got {type(value).__name__}")]
        required = schema.get("required", [])
        props = schema.get("properties", {})
        for field in required:
            if field not in value:
                errors.append(ValidationError(f"{path}.{field}", "missing required field"))
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(props)
            for extra in extras:
                errors.append(ValidationError(f"{path}.{extra}", "additional property not allowed"))
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(sub, value[key], f"{path}.{key}"))
        return errors
    if t == "array":
        if not isinstance(value, list):
            return [ValidationError(path, f"expected array, got {type(value).__name__}")]
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                errors.extend(validate(item_schema, item, f"{path}[{i}]"))
        return errors
```

- **类型不符立即返回**：不是 dict 就没法检查字段，直接返回一条错误，避免后续代码在错误类型上崩溃。
- **收集所有错误**：缺字段、额外字段、子字段错误全部累积到 `errors`，一次报全。
- `schema.get("additionalProperties") is False`：用 `is False` 而不是 `== False` 或 `not ...`，确保只有显式写了 `False` 才禁止额外字段；缺省（`None`）时允许。这与 JSON Schema 规范一致（默认允许额外属性）。
- `set(value) - set(props)`：对 dict 调 `set()` 得到键的集合，集合差就是"多出来的键"。
- ⚠️ 集合迭代顺序与字符串哈希有关，每个进程不同，所以多个额外字段的报错顺序不稳定（实测三个额外字段 x、y、z 按 z、y、x 报出，换个进程可能不同）。需要稳定输出时用 `sorted(...)`。
- array 分支用 `enumerate` 拿到下标拼进路径，`$.line_items[0]`。
- 与第 01 节相比，这里补上了 array、`additionalProperties`、路径。

### 3.4 `validate`：标量分支与通用约束

```python
    if t == "string":
        if not isinstance(value, str):
            errors.append(...); return errors
        if "minLength" in schema and len(value) < schema["minLength"]: ...
        if "maxLength" in schema and len(value) > schema["maxLength"]: ...
        if "pattern" in schema and not re.match(schema["pattern"], value): ...
    elif t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            ...; return errors
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            ...; return errors
    elif t == "boolean":
        if not isinstance(value, bool):
            ...; return errors
    if "minimum" in schema and isinstance(value, (int, float)) and value < schema["minimum"]: ...
    if "maximum" in schema and isinstance(value, (int, float)) and value > schema["maximum"]: ...
    if "enum" in schema and value not in schema["enum"]: ...
    return errors
```

- **修复了第 01 节的 bool 漏洞**：`isinstance(value, bool)` 被显式排除，`True` 不再能冒充 number/integer。
- 范围和 enum 放在类型分支之后，作为"通用约束"；类型不对时提前 `return`，不会对字符串做 `<` 比较。
- 实测：`total_usd = -5` → `$.total_usd: below minimum 0`（讲义练习 1）；`qty = 0` → `below minimum 1`；`qty = 1.5` → `expected integer, got float`。
- ⚠️ 与 JSON Schema 2020-12 的差异（均已实测）：

| 情况 | 本代码 | 规范 |
|------|-------|------|
| `pattern: "[0-9]+"`，值 `"abc123"` | 报错（`re.match` 从开头匹配） | 通过（非锚定搜索） |
| `pattern: "^[A-Z0-9-]+$"`，值 `"ABC-123\n"` | 通过（Python 的 `$` 匹配末尾换行前） | 报错 |
| `type: "integer"`，值 `2.0` | 报错 `expected integer, got float` | 通过（按数学值判断） |
| `type: ["string", "null"]`，值 `5` | 通过（列表不等于任何分支，所有检查被跳过） | 报错 |
| `type: "null"`，值 `5` | 通过（没有 null 分支） | 报错 |
| `enum: [1]`，值 `True` | 通过（Python 中 `True == 1`） | 报错 |

  其中"类型数组被静默放行"最危险：第 02 节的 strict 风格 schema 正是用 `["string", "null"]` 表达可选字段。讲义说这个校验器支持 "types, required, enum, min/max, pattern, items, additionalProperties"，这些关键字确实都有，但 `null` 类型、类型数组、`oneOf`（讲义练习 2）都不支持。

### 3.5 `process_model_output`：三分支处理

```python
def process_model_output(raw: str, schema: dict) -> ParsedResult:
    if raw.startswith("__REFUSAL__"):
        return ParsedResult("refusal", raw.removeprefix("__REFUSAL__").strip(), [])
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        return ParsedResult("parse_error", None, [ValidationError("$", str(e))])
    errs = validate(schema, parsed)
    if errs:
        return ParsedResult("violation", parsed, errs)
    return ParsedResult("ok", parsed, [])
```

- 判断顺序是 refusal → parse → validate，对应讲义的三种失败模式。
- `json.JSONDecodeError` 的消息带行列号（`line 1 column 73 (char 72)`），对重试反馈很有用。
- `violation` 时仍返回 `parsed`，方便记录日志或做部分修复。
- ⚠️ `__REFUSAL__` 前缀是本节**自己约定**的模拟方式。真实 OpenAI strict 响应中，拒绝出现在消息的 `refusal` 字段里（与 `content` 并列）；讲义还说 Anthropic 没有 refusal 停止原因，"`end_turn` with no tool call is the signal"。生产代码应按 provider 的结构判断，而不是匹配字符串前缀。
- ⚠️ `startswith` 对前导空白敏感：实测 `"  __REFUSAL__ no"` 被归为 `parse_error`。
- ⚠️ 讲义说 prompt JSON 的失败之一是"leaked prose like 'Here is your JSON:'"：实测 `'Here is your JSON: {"a":1}'` 直接 `parse_error`，代码没有尝试提取 JSON 片段（这是合理的保守选择，但说明非 strict 场景需要重试）。
- ⚠️ 讲义"Use It"说"The refusal branch does NOT retry. It logs and returns a typed refusal"——代码确实不重试，但**没有日志**；而且整个文件也**没有实现讲义的重试循环**（测验 Q11 给出了实现）。

### 3.6 `TEST_CASES` 与 `main`

```python
TEST_CASES = [
    ("happy path", json.dumps({... "total_usd": 219.98, "currency": "USD"})),
    ("parse error (trailing comma)", '{"customer": "Acme", ..., "currency": "USD",}'),
    ("schema violation (extra field, bad sku)", json.dumps({... "sku": "abc_123", ..., "discount": 0.1 ...})),
    ("schema violation (missing required)", json.dumps({"customer": "Acme", "line_items": []})),
    ("refusal (model declined)", "__REFUSAL__ The provided text is a song lyric, not an invoice."),
]
```

- 用 `json.dumps` 构造合法 JSON，手写字符串构造非法 JSON（尾逗号）——两种方式都模拟"模型的原始输出字符串"。
- 每个用例只覆盖一个分支，`main` 根据 `result.kind` 分别打印 payload、拒绝原因或错误列表。
- `raw[:80]` 截断显示，但无论长短都追加 `...`，所以 refusal 那一行出现了 `not an invoice....`。
- **schema 之外的语义问题**：happy path 的总额是 `2 × 49.99 + 120.00`。如果用浮点直接比较 `sum(...) == 219.98`，结果是 `False`——实测 `2*49.99 + 120.00 = 219.98000000000002`。用 `Decimal(str(x))` 计算得到精确的 `219.98`。schema 和受约束解码都管不了这种跨字段一致性，需要单独的语义校验（测验 Q10）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写校验器 | 不依赖第三方库，每个关键字都看得见 | `pattern`、`integer`、类型数组、`null`、`oneOf` 与规范不一致；生产用 `jsonschema` 或 Pydantic |
| 收集全部错误、带路径 | 一次反馈给模型就能改完 | 错误多时 prompt 变长；可截断为前 N 条 |
| 类型不符立即返回 | 避免在错误类型上做比较而崩溃 | 同一字段只报一个错误 |
| `additionalProperties is False` 才禁止额外字段 | 与规范默认值一致 | 需要在 schema 中显式声明（strict 模式本来就要求） |
| 用字符串前缀模拟 refusal | 离线可演示 | 真实场景按 provider 的 `refusal` 字段或"无工具调用的 end_turn"判断 |
| 结果用 `ParsedResult(kind, ...)` 表达 | 让调用方用分支处理，而不是 try/except | `kind` 是自由字符串，可改用 `Literal` 或 `Enum` |
| 没有重试循环 | 本文件聚焦"分类" | 讲义要求最多 3 次带错误反馈的重试，refusal 不重试 |
| 金额用 JSON number | JSON 没有 decimal | 代码中转 `Decimal(str(x))`，语义校验带容差 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 自定义 `__str__` | `class ValidationError: ... def __str__(self)` | 自动生成构造函数；`__str__` 决定 `print` 时的显示 |
| 默认参数做递归状态 | `def validate(schema, value, path: str = "$")` | 顶层调用不传 path，递归时传入拼接好的路径 |
| `is False` | `schema.get("additionalProperties") is False` | 只匹配真正的 `False` 对象，`None`、`0` 都不算 |
| 集合运算 | `set(value) - set(props)` | dict 转 set 得到键集合，差集即多余字段 |
| `enumerate` | `for i, item in enumerate(value)` | 同时得到下标与元素 |
| `isinstance` 组合 | `not isinstance(value, (int, float)) or isinstance(value, bool)` | 排除 bool（`bool` 是 `int` 子类） |
| `if / elif` 分派 | `if t == "string": ... elif t == "number": ...` | 按类型走不同检查 |
| `in` 判断键 | `if "minLength" in schema` | 只在 schema 声明了该约束时才检查 |
| 正则 | `re.match(schema["pattern"], value)` | `match` 只从开头匹配；`search` 任意位置；`fullmatch` 要求整体匹配 |
| f-string `!r` | `f"value {value!r} not in enum ..."`、`f"... pattern {schema['pattern']!r}"` | 用 `repr` 显示，字符串带引号 |
| f-string 中的不同引号 | `f"{schema['minLength']}"` | 外层双引号、内层单引号（3.12 起也可同种引号） |
| `try / except ... as e` | `except json.JSONDecodeError as e:` | 捕获特定异常并取得异常对象 |
| `str.removeprefix` | `raw.removeprefix("__REFUSAL__")` | Python 3.9+；去掉前缀（不存在则原样返回） |
| `str.strip` | `.strip()` | 去掉首尾空白 |
| 切片 | `raw[:80]` | 取前 80 个字符，越界不报错 |
| 元组列表 + 解包 | `for name, raw in TEST_CASES:` | 每个元素是 `(名称, 字符串)` |
| `json.dumps` 构造测试数据 | `json.dumps({...})` | 确保生成合法 JSON；`False` → `false` |
| 类型注解 | `-> list[ValidationError]`、`payload: Any` | 只做提示 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，输出确定；只有多个额外字段时报错顺序可能变化，本例只有一个）：

```text
Invoice schema keys: ['customer', 'line_items', 'total_usd', 'currency']

TEST : happy path
  kind: ok
  payload customer = Acme Corp
  total_usd        = 219.98

TEST : parse error (trailing comma)
  kind: parse_error
  error: $: Illegal trailing comma before end of object: line 1 column 73 (char 72)

TEST : schema violation (extra field, bad sku)
  kind: violation
  error: $.line_items[0].discount: additional property not allowed
  error: $.line_items[0].sku: does not match pattern '^[A-Z0-9-]+$'

TEST : schema violation (missing required)
  kind: violation
  error: $.total_usd: missing required field
  error: $.currency: missing required field

TEST : refusal (model declined)
  kind: refusal
  reason: The provided text is a song lyric, not an invoice.

summary: strict-mode eliminates parse_error and violation branches
at the provider level; your code still handles refusal as typed outcome.
```

逐项解读：

- **happy path**：所有约束满足。注意 schema 只检查了形状，`219.98` 是否等于明细之和并没有被检查。
- **parse error**：Python 3.13 的 `json` 模块给出了 "Illegal trailing comma" 的精确提示和位置（第 73 列）；旧版本 Python 的提示文字不同（如 "Expecting property name enclosed in double quotes"）。
- **extra field + bad sku**：两个错误都报出——`discount` 是讲义所说的"幻觉字段"，被 `additionalProperties: false` 拦下（讲义 "The `additionalProperties: false` check fires on the adversarial test input"）；`abc_123` 含小写字母和下划线，不匹配 pattern。
- **missing required**：`customer` 和 `line_items`（空数组）都合法，只报缺失的 `total_usd` 和 `currency`；顺序与 `required` 列表一致。
- **refusal**：直接返回原因，不进入解析和校验。
- **summary**：两行总结了本节结论：strict 消灭前两种失败，refusal 永远需要自己处理。

---

## 7. 动手改一改

1. **讲义练习 1**：加一个 `total_usd` 为负数的用例，确认输出 `$.total_usd: below minimum 0`。
2. **修正规范差异**：`pattern` 改用 `re.search` 并处理 `$` 与结尾换行；`integer` 接受 `2.0`；支持 `"null"` 类型和类型数组（参考测验 Q9）。
3. **讲义练习 2**：支持带 discriminator 的 `oneOf`——`line_item` 是 `{"kind": "product", "sku", "qty", ...}` 或 `{"kind": "service", "hours", "rate"}`，先按 `kind` 选子 schema 再校验，错误路径中带上分支名。
4. **实现重试**：写 `extract_with_retry(generate, schema, max_retries=3)`，refusal 不重试，parse_error / violation 带错误反馈重试（参考测验 Q11）。
5. **语义校验**：用 `Decimal` 检查 `total_usd` 是否等于明细之和（允许 0.01 误差），把结果并入 violation 分支（参考测验 Q10）。
6. **讲义练习 3**：用 Pydantic 写同一个模型（`ConfigDict(extra="forbid")`、`Field(pattern=..., ge=...)`、`Literal[...]`），对比 `model_json_schema()` 与手写 schema（会多出 `title`、`$defs`/`$ref`），并用 `model_validate` 跑一遍五个测试用例，比较错误信息与 lax 模式的类型转换。

---

## 8. 常见坑

- **以为 strict 下什么都不用管**：refusal 必须处理；语义正确性（金额、日期、客户是否存在）仍要自己校验。
- **refusal 也重试**：拒绝是模型的判断，重试只会浪费钱或逼出幻觉。
- **`re.match` 当作 JSON Schema 的 pattern 语义**：规范是非锚定搜索；Python 的 `$` 还会放过末尾换行。
- **类型数组被静默跳过**：手写校验器最容易漏掉 `["string", "null"]`。
- **`True` 冒充数字**：`bool` 是 `int` 的子类，必须显式排除（本节已修复）。
- **金额用浮点比较**：`2 * 49.99 + 120.00 != 219.98`，要用 `Decimal` 或容差。
- **Pydantic 默认不禁止额外字段**：需要 `extra="forbid"` 才会生成 `additionalProperties: false`。
- **用字符串前缀识别拒绝**：只是本节的模拟手段，真实响应要按 provider 的字段判断。
- **错误信息不带路径**：模型无法知道该改哪个字段，重试成功率下降。
