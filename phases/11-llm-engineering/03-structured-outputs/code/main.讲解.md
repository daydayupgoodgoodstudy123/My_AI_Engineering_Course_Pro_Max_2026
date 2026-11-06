# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 03 节 Structured Outputs：JSON、Schema 校验与约束解码 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库 `json`（无需 API key、无需网络）。同目录的 `main.ts` 是 TypeScript 移植版（仿 Zod 的 schema DSL），本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

这份代码不调用任何真实 LLM，而是把"结构化输出"链路上**模型之外**的几个部件用纯 Python 写出来：

1. **JSON Schema 校验器**（`validate_schema`）：递归检查一个 Python 对象是否符合 schema，返回带路径的错误列表。这是应用侧"最后一道防线"。
2. **类 → schema 生成**（`SchemaField` + `model_to_schema`）：模仿 Pydantic，用 Python 声明字段，自动生成 JSON Schema。
3. **约束解码的模拟**（`next_valid_tokens`）：给定已生成的部分 JSON，列出下一个 token 允许的类别——这就是约束解码中"mask"的来源。
4. **抽取 + 重试管道**（`simulate_llm_extraction` + `extract_with_retry`）：用规则模拟 LLM，演示"解析 → 校验 → 重试"。
5. **嵌套 schema**：订单（对象里套对象、数组里套对象）的校验与错误路径。

对应讲义的核心概念：四级可靠性光谱、JSON Schema 作为契约、Pydantic 模式、约束解码、校验 + 重试、常见失败模式。

> 一句话：**把"让 LLM 输出类型化数据"拆成"定义契约 → 生成时约束 → 生成后校验 → 失败重试"四步，每步都用几十行可读代码演示**。同时它的每一步都有值得指出的简化，正好是理解生产级实现的入口。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `validate_schema` / `_validate` | 函数（递归） | 按 `type` 分派检查，收集错误到列表 | JSON Schema 校验 |
| `SchemaField` | 类 | 保存字段类型、是否必填、enum、范围 | Pydantic 的字段声明 |
| `python_type_to_schema` | 函数 | 把单个 `SchemaField` 映射为 schema 片段 | 类型 → JSON Schema |
| `model_to_schema` | 函数 | 组装 `properties` 与 `required` | Pydantic `model_json_schema()` |
| `next_valid_tokens` | 函数 | 由部分 JSON 的最后一个字符推出合法的下一类 token | 约束解码（token mask） |
| `demonstrate_constrained_decoding` | 函数 | 打印 9 个部分状态的合法 token | 约束解码演示 |
| `simulate_llm_extraction` | 函数 | 关键字匹配返回固定 JSON 字符串 | 模拟 LLM |
| `extract_with_retry` | 函数 | 解析 + 校验 + 最多 3 次重试 | 校验重试循环 |
| `PRODUCT_SCHEMA` | 模块级常量 | 产品 schema：4 个属性，3 个必填 | 契约 |
| `run_*_demo` × 5 | 函数 | 五个演示步骤 | — |

数据流：`__main__` → STEP 1 用 `PRODUCT_SCHEMA` 校验 8 个用例 → STEP 2 由 `SchemaField` 生成 Product / Event 两个 schema 并校验 → STEP 3 打印约束解码表 → STEP 4 四段文本 → `simulate_llm_extraction` → `json.loads` → `validate_schema` → 输出 → STEP 5 嵌套订单校验。

---

## 3. 逐段精讲

### 3.1 递归校验器：按类型分派、按路径报错

```python
def validate_schema(data, schema):
    errors = []
    _validate(data, schema, "", errors)
    return errors


def _validate(data, schema, path, errors):
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(data, dict):
            errors.append(f"{path}: expected object, got {type(data).__name__}")
            return
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}.{key}: required field missing")
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                _validate(value, properties[key], f"{path}.{key}", errors)
```

- **对外接口 + 内部递归**：`validate_schema` 只负责创建空列表并返回；真正的工作在 `_validate`，它把同一个 `errors` 列表一路传下去，各层把错误 `append` 进去。列表是可变对象，所以子调用的追加对上层可见。
- **路径拼接**：顶层 `path=""`，进入字段时变成 `".price"`，进入嵌套对象变成 `".customer.email"`，进入数组元素变成 `".items[0]"`。这让错误信息可以直接回传给模型（"`.customer.email` 缺失"比"校验失败"有用得多）。
- **类型不符就 `return`**：如果连类型都不对，继续检查子字段没有意义，提前返回避免连锁错误或异常。
- **`schema.get("type")` 返回 `None` 时**：没有任何分支匹配，函数什么也不做——即"没写 type 的 schema 接受任何值"。这与 JSON Schema 规范的宽松默认一致，但也意味着 `{"properties": {...}}` 这种漏写 `"type": "object"` 的 schema 会**完全不校验**（已实测返回 `[]`）。
- ⚠️ **多余字段不检查**：`if key in properties` 只校验已声明的键，其它键被静默放行。讲义 Key Terms 把 "no extra disallowed fields" 当作 schema compliance 的一部分，但代码没有实现 `additionalProperties: false`。

### 3.2 数组、字符串、数值、布尔、整数

```python
    elif schema_type == "array":
        ...
        min_items = schema.get("minItems", 0)
        max_items = schema.get("maxItems", float("inf"))
        ...
        items_schema = schema.get("items", {})
        for i, item in enumerate(data):
            _validate(item, items_schema, f"{path}[{i}]", errors)

    elif schema_type == "string":
        ...
        enum_values = schema.get("enum")
        if enum_values and data not in enum_values:
            errors.append(f"{path}: '{data}' not in allowed values {enum_values}")

    elif schema_type == "number":
        if not isinstance(data, (int, float)):
            errors.append(f"{path}: expected number, got {type(data).__name__}")
            return
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and data < minimum:
            ...

    elif schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            errors.append(f"{path}: expected integer, got {type(data).__name__}")
```

- **数组**：`maxItems` 缺省用 `float("inf")`，这样 `len(data) > inf` 永远为假，不需要额外的 `if`。`items` 缺省为 `{}`，即元素不受约束。用 `enumerate` 拿到下标拼进路径 `[i]`。
- **字符串 enum**：只在 `string` 分支检查 enum。讲义"Enum confusion"一节说的正是模型输出 `"available"` 而不是 `"in_stock"` 的情况，校验器能发现它（STEP 2 的 `'urgent'` 例子）。
- **`minimum is not None`**：必须写 `is not None` 而不是 `if minimum:`，否则 `minimum = 0` 会被当作假值跳过——`PRODUCT_SCHEMA` 的 `"minimum": 0` 恰好就是这种情况。
- ⚠️ **bool 被当成 number**：Python 中 `bool` 是 `int` 的子类，`isinstance(True, (int, float))` 为真，于是 `{"price": True}` 能通过（已实测返回 `[]`）。作者在 `integer` 分支意识到了这个问题（`or isinstance(data, bool)`），却没在 `number` 分支同样处理。
- ⚠️ **NaN 能通过**：`float("nan")` 是 float，且任何与 NaN 的比较都为 False，范围检查失效；而 Python 的 `json.loads` 默认能解析非标准的 `NaN`（已实测）。
- ⚠️ **整数的严格程度**：`3.0` 会被判为 "expected integer, got float"。JSON Schema 规范中 `3.0` 是合法的 integer（值为整数即可），这里比规范更严格。
- 不支持 `null` 类型、`oneOf/anyOf/allOf`（讲义练习 1）、`pattern`、`minLength` 等。

### 3.3 `SchemaField` 与类 → schema 生成

```python
class SchemaField:
    def __init__(self, field_type, required=True, default=None, enum=None, minimum=None, maximum=None):
        ...

def python_type_to_schema(field):
    type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
    schema = {}
    if field.field_type in type_map:
        schema["type"] = type_map[field.field_type]
    elif field.field_type == list:
        schema["type"] = "array"
        schema["items"] = {"type": "string"}
    elif isinstance(field.field_type, dict):
        schema = field.field_type
    if field.enum:
        schema["enum"] = field.enum
    ...

def model_to_schema(name, fields):
    properties = {}
    required = []
    for field_name, field in fields.items():
        properties[field_name] = python_type_to_schema(field)
        if field.required:
            required.append(field_name)
    return {"type": "object", "properties": properties, "required": required}
```

- **类型对象作字典键**：`type_map` 的键是 `str`、`int` 这些**类型对象本身**，`field.field_type in type_map` 用的是哈希查找。
- **`required` 列表**：`required=True` 是默认值，所以只有显式写 `required=False` 的字段（`categories`、`rating`、`is_recurring`）不进入 `required`。
- ⚠️ **dict 分支不可达**：`field.field_type in type_map` 需要对 `field_type` 求哈希，dict 不可哈希，传入 dict 会直接抛 `TypeError: unhashable type: 'dict'`（已实测），根本到不了 `isinstance(..., dict)`。即使修好顺序，`schema = field.field_type` 也是**别名**而非复制，后续 `schema["enum"] = ...` 会改掉调用者的原 dict。
- ⚠️ **其它简化**：`list` 的元素类型写死为 string；`default` 被保存但从未使用；`name` 参数没用到。作为对照，Pydantic 2 对 `class Product(BaseModel): product: str; price: float; in_stock: bool; categories: list[str] = []` 生成的 schema 会额外带 `"title"`、`"default": []`，`items` 由 `list[str]` 推出（已实际运行 `Product.model_json_schema()` 验证）。

### 3.4 约束解码模拟：`next_valid_tokens`

```python
def next_valid_tokens(partial_json, schema):
    stripped = partial_json.strip()
    if not stripped:
        return ["{"]
    try:
        json.loads(stripped)
        return ["<EOS>"]
    except json.JSONDecodeError:
        pass

    last_char = stripped[-1] if stripped else ""

    if last_char == "{":
        return ['"', "}"]
    elif last_char == '"':
        if stripped.endswith('":'):
            return ['"', "0-9", "true", "false", "null", "[", "{"]
        return ["a-z", '"']
    elif last_char == ":":
        return [" ", '"', "0-9", "true", "false", "null", "[", "{"]
    elif last_char == ",":
        return [" ", '"', "{", "["]
    elif last_char in "0123456789":
        return ["0-9", ".", ",", "}", "]"]
    elif last_char == "}":
        return [",", "}", "]", "<EOS>"]
    elif last_char == "]":
        return [",", "}", "<EOS>"]
    elif last_char == "[":
        return ['"', "0-9", "true", "false", "null", "{", "[", "]"]
    else:
        return ["any"]
```

**思想**：真实的约束解码在每一步都要回答"在当前语法状态下，词表里哪些 token 合法？"，然后把其余 token 的 logit 置为 −∞。这个函数用"token 类别"（`"0-9"`、`'"'`、`"true"`）代替真实词表，演示这个问题的形状。

- **空串 → 只能 `{`**：隐含假设顶层必须是对象。
- **能完整解析 → 只能 `<EOS>`**：用 `json.loads` 判断"已经是完整 JSON"，此时唯一合法的是结束符。巧妙但有副作用：`'"hi"'`、`'42'` 这样的顶层标量也会被判为完成（已实测返回 `['<EOS>']`）。
- **其余情况只看最后一个字符**——这是最大的简化，也带来了多个 bug（均已实测）：

| 输入 | 代码返回 | 正确答案 | 原因 |
|------|---------|---------|------|
| `{"product"` | `['a-z', '"']` | `[':']` | 分不清 `"` 是键的结束还是字符串的开始 |
| `{"product": "Sony"` | `['a-z', '"']` | `[',', '}']` | 同上，且不知道这是值 |
| `[1,` | `[' ', '"', '{', '[']` | 任意值（含 `0-9`、`true`…） | 逗号分支没区分数组/对象，漏了数字和字面量 |
| `{"a": 1,` | `[' ', '"', '{', '[']` | `['"']` | 对象里逗号后只能是键，`{`、`[` 非法 |
| `{"a": [1]` | `[',', '}', '<EOS>']` | `[',', '}']` | 对象未闭合，不能 EOS |
| `{"a": -` | `['any']` | `0-9` | 负号没处理 |

- ⚠️ **死代码**：`if stripped.endswith('":')` 位于 `last_char == '"'` 分支内，而以 `":` 结尾意味着最后一个字符是 `:`，二者不可能同时成立。
- ⚠️ **`schema` 参数从未使用**：所以它只约束 JSON 语法，不约束 schema（键名、值类型）。讲义描述的 OpenAI 结构化输出、Outlines、XGrammar 都是**按 schema** 约束的。
- 修复思路：维护"容器栈 + 是否在字符串内 + 下一步期望（键/冒号/值/逗号或闭合）"的状态机，见测验 Q9 的参考实现。那个"栈"正是 XGrammar 所用下推自动机（pushdown automaton）的雏形。

### 3.5 模拟 LLM 与重试循环

```python
def simulate_llm_extraction(text, schema, attempt=0):
    if "headphones" in text.lower() or "sony" in text.lower():
        if attempt == 0:
            return '{"product": "Sony WH-1000XM5", "price": 348.00, "in_stock": true, "categories": ["audio", "headphones"]}'
        return '{"product": "Sony WH-1000XM5", "price": 348.00, "in_stock": true}'
    ...
    return '{"product": "Unknown", "price": 0, "in_stock": false}'


def extract_with_retry(text, schema, max_retries=3):
    for attempt in range(max_retries):
        raw = simulate_llm_extraction(text, schema, attempt)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"    Attempt {attempt + 1}: JSON parse error -- {e}")
            continue
        errors = validate_schema(data, schema)
        if not errors:
            return data
        print(f"    Attempt {attempt + 1}: Schema validation errors -- {errors}")
    return None
```

- **两层失败**：先 `json.loads`（语法层，失败用 `continue` 进入下一次），再 `validate_schema`（schema 层）。这对应讲义光谱的前两级失败。
- **`348.00` → `348.0`**：JSON 字符串里的 `348.00` 解析成 Python float `348.0`，再 `json.dumps` 时输出 `348.0`；而 `"price": 0` 保持为 int `0`。
- ⚠️ **重试从未被触发**：模拟器在 `attempt == 0` 时对所有输入都返回能通过校验的 JSON，运行输出中没有任何 `Attempt N:` 行；Sony 的第二个分支永远走不到。
- ⚠️ **重试不反馈错误**：第二次调用只多传了 `attempt`，没有把上一次的输出和错误信息带给模型。对真实 LLM 这只是"再采样一次"；讲义说的 Instructor 会"send the errors back to the model as context"。参考改写见测验 Q11。
- ⚠️ **失败返回 `None`**：调用方只能看到 "FAILED after retries"，丢失了失败原因。
- ⚠️ **"Unknown" 也能通过**：没有产品信息的句子得到 `{"product": "Unknown", "price": 0, "in_stock": false}`，类型全对——这正是讲义的 "Hallucinated values" 失败模式，也与讲义"让模型显式输出 null"的建议相悖。

### 3.6 五个演示步骤

- **STEP 1** 8 个用例覆盖：合法、带可选数组、负价格、缺必填、字符串当数字、数字当字符串、顶层不是对象、字符串当布尔。
- **STEP 2** 生成 Product（5 个字段、3 个必填，`rating` 带 0–5 范围）与 Event（`priority` 带 enum）schema，并校验 `'urgent'` 不在 enum 中。
- **STEP 3** 打印约束解码表。
- **STEP 4** 四段文本走抽取管道。
- **STEP 5** 订单 schema：`customer` 是嵌套对象、`items` 是对象数组且 `minItems: 1`、`quantity` 是 integer。非法订单一次收集到 3 个错误（缺 email、空数组、负总价），展示了"收集全部错误而不是遇错即停"的好处——全部错误可以一次性回传给模型修正。
- 注意：合法订单的 `total = 54.96` 恰好等于 `3 × 9.99 + 24.99`，但校验器并不检查这种**跨字段一致性**，把 `total` 改成 `1.0` 也能通过——这类业务规则必须在 schema 之外校验。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写递归校验器 | 看清 JSON Schema 的语义与错误路径 | 只支持子集；生产用 `jsonschema` 库或 Pydantic |
| 收集全部错误而非遇错即停 | 错误可一次性回传给模型 | 输出可能较长；可限制条数 |
| 错误信息带路径 | 便于定位与回传 | — |
| `SchemaField` 模仿 Pydantic | 不依赖第三方库 | 不支持嵌套模型、可空、list 元素类型、description；生产直接用 Pydantic |
| 约束解码只看最后一个字符 | 代码极短，突出"mask"概念 | 结果多处错误；真实实现需状态机/下推自动机并结合真实词表 |
| 用 `json.loads` 判断完成 | 省去自己写完成判定 | 顶层标量也被判为完成 |
| 规则模拟 LLM | 无需 API key，可复现 | 无法展示真实失败与重试；可构造"首次失败"的模拟 |
| 重试只递增 `attempt` | 简单 | 不反馈错误；生产应带上原输出与错误（Instructor 方式） |
| 缺失信息返回 "Unknown"/0 | 让流程"不失败" | 制造了合规但虚假的数据；应使用 `null` 或判别字段 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 递归函数 | `_validate(value, properties[key], f"{path}.{key}", errors)` | 函数调用自身处理嵌套结构 |
| 可变参数共享 | `errors` 列表在各层 `_validate` 间传递 | 列表是可变对象，被调用方的 `append` 对调用方可见 |
| 前导下划线命名 | `_validate` | 约定为"内部函数"，不建议外部直接调用 |
| `dict.get(key, default)` | `schema.get("required", [])`、`schema.get("maxItems", float("inf"))` | 键不存在时返回默认值，不抛 `KeyError` |
| `float("inf")` | `max_items = ... float("inf")` | 正无穷，任何有限数都小于它 |
| `isinstance` 多类型 | `isinstance(data, (int, float))` | 传入元组表示"任一类型"；注意 `bool` 是 `int` 的子类 |
| `type(x).__name__` | `got {type(data).__name__}` | 取类型名字符串，如 `'str'`、`'NoneType'` |
| `is not None` | `if minimum is not None and data < minimum` | 区分 `None` 与 `0` 等假值 |
| `enumerate` | `for i, item in enumerate(data)` | 同时拿下标和元素 |
| 类与 `__init__` | `class SchemaField: def __init__(self, field_type, required=True, ...)` | 用实例属性保存配置；默认参数让调用简洁 |
| 类型对象作字典键 | `type_map = {str: "string", int: "integer", ...}` | 类型本身是可哈希对象；dict 不可哈希，`dict in type_map` 会抛 `TypeError` |
| `dict.items()` | `for field_name, field in fields.items()` | 遍历键值对 |
| `try / except / pass` | `try: json.loads(stripped) ... except json.JSONDecodeError: pass` | 用异常判断"是否已是完整 JSON" |
| `except ... as e` | `except json.JSONDecodeError as e:` | 捕获异常对象以打印错误信息 |
| `continue` | 解析失败后进入下一次循环 | 跳过本轮剩余代码 |
| 条件表达式 | `display = state if state else "(empty)"` | 一行内的 if/else |
| `str.endswith` / 负索引 | `stripped.endswith('":')`、`stripped[-1]` | 判断后缀；取最后一个字符 |
| `in` 判断字符集合 | `last_char in "0123456789"` | 在字符串中查子串 |
| `json.dumps(..., indent=2)` | `json.dumps(schema, indent=2)` | 格式化缩进输出 |
| `repr` | `repr(data)` | 输出带引号的表示，区分字符串与其他类型 |
| f-string 格式符 | `f"{display:<45}"`、`f"{'=' * 60}"`、`f"{text[:70]}..."` | 左对齐宽度 45；表达式内可做运算与切片 |
| 字符串乘法 | `"-" * 70` | 重复字符串画分隔线 |
| 模块级常量 | `PRODUCT_SCHEMA = {...}` | 全大写表示常量（约定，非强制） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示；被 import 时不执行（测验中的验证脚本正是 `from main import ...`） |

---

## 6. 运行结果解读

实际运行（Python 3.13，仅标准库，瞬间完成），关键片段：

```text
  STEP 1: JSON Schema Validation
  Valid complete object:            Result: PASS
  Valid with optional array:        Result: PASS
  Negative price:                   Result: FAIL: ['.price: -5.0 is less than minimum 0']
  Missing required field (price):   Result: FAIL: ['.price: required field missing']
  String as price:                  Result: FAIL: ['.price: expected number, got str']
  Number as product name:           Result: FAIL: ['.product: expected string, got int']
  String instead of object:         Result: FAIL: [': expected object, got str']   ← 顶层路径为空串
  String as boolean:                Result: FAIL: ['.in_stock: expected boolean, got str']
```

（为便于阅读，上面把每个用例的 Data/Result 两行合成了一行。）8 个用例两过六败，每个错误都精确到字段路径。顶层错误的路径是空串，所以以 `: ` 开头。

```text
  STEP 2: ...
  "required": ["product", "price", "in_stock"]          ← categories、rating 设了 required=False
  "priority": {"type": "string", "enum": ["low", "medium", "high"]}
    Valid event: PASS
    Invalid priority enum: FAIL: [".priority: 'urgent' not in allowed values ['low', 'medium', 'high']"]
```

```text
  STEP 3: Constrained Decoding Simulation
  (empty)                                       ['{']
  {                                             ['"', '}']
  {"product"                                    ['a-z', '"']          ← 错：应为 [':']
  {"product":                                   [' ', '"', '0-9', 'true', 'false', 'null', '[', '{']
  {"product": "Sony"                            ['a-z', '"']          ← 错：应为 [',', '}']
  {"product": "Sony",                           [' ', '"', '{', '[']  ← 对象内逗号后只能是 '"'
  {"product": "Sony", "price":                  [' ', '"', '0-9', 'true', 'false', 'null', '[', '{']
  {"product": "Sony", "price": 348              ['0-9', '.', ',', '}', ']']   ← ']' 在对象中非法
  {"product": "Sony", "price": 348}             ['<EOS>']
```

9 行中有 4 行不完全正确，原因都是"只看最后一个字符"。冒号之后的一行是对的，也是讲义 The Problem 一节举的例子（`{"price":` 之后只能是数字、引号、`null`、`true`、`false` 或负号——但代码的列表恰恰漏了负号）。

```text
  STEP 4: Extraction Pipeline with Retry
  Input: The Sony WH-1000XM5 headphones are priced at $348 ...
  Output: {"product": "Sony WH-1000XM5", "price": 348.0, "in_stock": true, "categories": ["audio", "headphones"]}
  ...
  Input: This sentence contains no product information at all....
  Output: {"product": "Unknown", "price": 0, "in_stock": false}
```

- 四条全部首次成功，**没有出现任何 `Attempt N:` 行**——重试逻辑在本次运行中从未执行。
- 第四条"无产品信息"也产出了合规 JSON，`in_stock: false` 把"没提到"写成了"缺货"。
- 输入行末尾的 `....`：`text[:70]` 截断后固定拼 `...`，原句恰好以句号结尾且不足 70 字符时就出现了四个点。

```text
  STEP 5: Nested Schema Validation
    Valid order: PASS
    Invalid order: FAIL
      - .customer.email: required field missing
      - .items: array has 0 items, minimum is 1
      - .total: -10 is less than minimum 0
```

嵌套路径 `.customer.email` 展示了递归时路径的拼接。三个错误被一次性收集，而不是遇到第一个就停止。

---

## 7. 动手改一改

1. **修 bool 与 NaN**：在 `number` 分支排除 `bool`、拒绝非有限数；加 `additionalProperties: false` 支持（参考测验 Q10）。用 `{"price": True}`、`{"price": float("nan")}`、`{"color": "red"}` 验证。
2. **加 `null` 与可空类型**：支持 `"type": ["number", "null"]`，把 `PRODUCT_SCHEMA` 的 `price` 改为可空，并让模拟器对"无产品信息"返回 `{"product": null, "price": null, "in_stock": null}`。
3. **讲义练习 1**：实现 `oneOf`——数据必须**恰好**匹配一个子 schema，用 Product / Service 两种形状测试。
4. **带错误反馈的重试**：改写 `simulate_llm_extraction`，让它接收 `messages`，首次返回带 markdown 围栏或 `"price": "$348"` 的坏输出，看到错误后返回正确结果；再实现 `extract_with_feedback`（参考测验 Q11），确认运行时出现 `Attempt 1` 的错误行。
5. **讲义练习 3**：重写 `next_valid_tokens` 为状态机（参考测验 Q9），再定义一个 100 个 token 的词表（字母、数字、标点、`true/false/null`、`":"`、`", "` 等多字符 token），逐步生成 `{"product": "Sony", "price": 348}`，统计每一步合法 token 占词表的百分比。
6. **讲义练习 2（进阶）**：写 `schema_diff(old, new)`，识别删除必填字段、修改类型、收紧 enum（破坏性）与新增可选字段、放宽范围（非破坏性）。

---

## 8. 常见坑

- **`isinstance(True, int)` 为真**：校验 number/integer 时必须先排除 `bool`。
- **用 `if minimum:` 判断约束是否存在**：`minimum = 0` 会被跳过，应写 `is not None`。
- **漏写 `"type"`**：本校验器对没有 `type` 的 schema 什么都不查，`{"properties": {...}}` 会让任何数据通过。
- **以为 JSON mode = schema 合规**：JSON mode 只保证能解析。
- **以为 schema 合规 = 内容正确**：幻觉值、"Unknown"/0 这样的占位值都能通过校验。
- **缺失信息用 0 / false 填充**：把"未知"伪装成"已知"，下游无法区分；应使用 `null`。
- **重试时不带错误信息**：对真实模型只是重新采样，修正效果差。
- **只看最后一个字符做约束**：JSON 是嵌套语法，判断合法性必须维护状态（是否在字符串内、当前容器类型、期望键还是值）。
- **在 dict 上做 `in type_map`**：dict 不可哈希，会抛 `TypeError`；同时注意别名问题，复用子 schema 时要复制。
- **Python `json` 接受 `NaN`/`Infinity`**：它们不是标准 JSON，跨语言传输会出问题。
