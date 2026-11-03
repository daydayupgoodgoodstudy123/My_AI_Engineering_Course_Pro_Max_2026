# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 02 节 深入理解 Function Calling：OpenAI、Anthropic、Gemini ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`typing`），无网络、无 API key、无需任何 SDK

---

## 1. 这份代码在考察什么

三家 provider 的 function calling 本质上是同一个循环，但字段名、嵌套方式、参数是字符串还是对象、id 怎么关联都不一样。这份代码用"**一份 canonical 定义 + 边缘翻译**"的方式把差异摊开：

1. **声明翻译**：一个 canonical `Tool` → OpenAI / Anthropic / Gemini 三种声明 JSON（含 Gemini 的 OpenAPI 方言转换）。
2. **tool_choice 翻译**：canonical `ToolChoice(mode)` 的 auto / none / required / force → 三家写法。
3. **响应解析**：三份手写的模拟响应 → 同一个 `Call(id, name, args)`。
4. **等价性检查**：证明三家"皮不同、骨相同"。

> 一句话：**业务代码只认 canonical 类型，provider 差异全部关在翻译函数里**——这是多 provider 工程（以及第 17 节网关）的基本模式。同时要看清：本节只覆盖了五个要素中的四个，"结果回填"没有实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Tool` | dataclass | name / description / input_schema / strict | canonical 工具声明 |
| `Call` | dataclass | id / name / args | canonical 调用 |
| `ToolChoice` | dataclass | mode / tool_name | canonical 工具选择策略 |
| `WEATHER` | 常量 | 一个按 OpenAI strict 规则写的天气工具 | strict 兼容的 schema |
| `to_openai` / `to_anthropic` / `to_gemini` | 函数 | 三种声明信封 | 声明差异 |
| `_gemini_schema` | 递归函数 | 删 `additionalProperties`、类型转大写 | OpenAPI 3.0 子集方言 |
| `tool_choice_openai/anthropic/gemini` | 函数 | 四种模式的三家写法 | tool_choice 差异 |
| `OPENAI_RESPONSE` / `ANTHROPIC_RESPONSE` / `GEMINI_RESPONSE` | 常量 | 手写的模拟响应 | 调用在响应中的位置 |
| `parse_openai` / `parse_anthropic` / `parse_gemini` | 函数 | 响应 → `list[Call]` | 响应解析 / id 关联 |
| `diff_line` / `main` | 函数 | 并排打印、等价性检查 | 演示 |

数据流：`WEATHER` → 三个 `to_*` → 打印声明；`ToolChoice` × 4 → 三个 `tool_choice_*` → 打印；三份模拟响应 → 三个 `parse_*` → `Call` → 比较 name 与 args 是否一致。

---

## 3. 逐段精讲

### 3.1 三个 canonical 数据类

```python
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    strict: bool = True

@dataclass
class Call:
    id: str
    name: str
    args: dict

@dataclass
class ToolChoice:
    mode: str
    tool_name: str | None = None
```

- `Tool` 比第 01 节少了 `executor`、多了 `strict`：本节只关心"发给 provider 的部分"。
- `Call.args` 统一是 **dict**——不管 provider 给的是字符串还是对象，进入业务层之前都要变成 dict。
- `ToolChoice.mode` 用字符串（`"auto"`/`"none"`/`"required"`/`"force"`）；生产代码可改用 `Literal[...]` 或 `Enum` 防止拼写错误。`tool_name` 只在 force 时需要，但代码没有校验：实测 `tool_choice_openai(ToolChoice("force"))` 会返回 `{"type": "function", "function": {"name": None}}`，错误被推迟到 provider 端。
- `str | None` 是 Python 3.10 的联合类型写法；文件开头的 `from __future__ import annotations` 让它在更早版本中作为注解也能用。

### 3.2 `WEATHER`：一个按 strict 规则写的 schema

```python
    input_schema={
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "units": {"type": ["string", "null"], "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city", "units"],
        "additionalProperties": False,
    },
```

- OpenAI strict mode 要求：所有属性都在 `required` 中、`additionalProperties: false`。于是"可选的 units"只能写成"必填但可为 null"：`"type": ["string", "null"]`。
- ⚠️ **但 `enum` 里没有 `null`**。JSON Schema 中 `type` 和 `enum` 同时生效，null 会被 enum 拒绝。我们用 `jsonschema` 4.26 实测：

| 实例 | 结果 |
|------|------|
| `{"city": "X", "units": "celsius"}` | 通过 |
| `{"city": "X", "units": None}` | `None is not one of ['celsius', 'fahrenheit']` |
| `{"city": "X"}` | `'units' is a required property` |
| `{"city": "X", "units": "kelvin"}` | `'kelvin' is not one of [...]` |

  所以这个字段其实是"必填、必须是两个值之一"，nullable 形同虚设。正确写法是 `"enum": ["celsius", "fahrenheit", None]`（JSON 中为 `null`）。

### 3.3 三种声明信封

```python
def to_openai(tool: Tool) -> dict:
    return {"type": "function",
            "function": {"name": tool.name, "description": tool.description,
                         "parameters": tool.input_schema, "strict": tool.strict}}

def to_anthropic(tool: Tool) -> dict:
    return {"name": tool.name, "description": tool.description,
            "input_schema": tool.input_schema}

def to_gemini(tool: Tool) -> dict:
    return {"functionDeclarations": [{"name": tool.name, "description": tool.description,
                                      "parameters": _gemini_schema(tool.input_schema)}]}
```

| 差异 | OpenAI | Anthropic | Gemini |
|------|--------|-----------|--------|
| 外层 | `type: "function"` + `function: {...}` | 扁平 | `functionDeclarations: [...]`（一个 tool 对象里可放多个函数） |
| schema 字段名 | `parameters` | `input_schema` | `parameters` |
| strict | 保留 | **静默丢弃** | **静默丢弃** |
| schema 方言 | JSON Schema | JSON Schema（原样） | 经 `_gemini_schema` 转换 |

- ⚠️ `strict` 在 Anthropic、Gemini 翻译中被直接丢弃，没有任何警告。移植时"校验强度下降"是静默发生的——宿主侧校验因此更重要。

### 3.4 `_gemini_schema`：方言转换及其缺陷

```python
def _gemini_schema(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict = {}
        for k, v in node.items():
            if k == "additionalProperties":
                continue
            if k == "type" and isinstance(v, str):
                out["type"] = v.upper()
                continue
            out[k] = _gemini_schema(v)
        return out
    if isinstance(node, list):
        return [_gemini_schema(x) for x in node]
    return node
```

- 递归遍历任意嵌套的 dict/list：删除 Gemini 不支持的 `additionalProperties`，把 `"object"` → `"OBJECT"`、`"string"` → `"STRING"`。
- ⚠️ **类型数组没处理**：`isinstance(v, str)` 只覆盖字符串，`["string", "null"]` 被当成普通列表原样保留。运行输出里 Gemini 的 `units` 仍是 `"type": ["string", "null"]`。OpenAPI 3.0 子集要求 `"type": "STRING", "nullable": true`。
- ⚠️ **把属性名当成关键字**：函数不区分"schema 关键字"和"`properties` 下的属性名"。实测一个名为 `additionalProperties` 的属性会被整个删掉：`{"properties": {"additionalProperties": {...}}}` → `{"properties": {}}`。
- 其它关键字（`anyOf`、`$ref`、`const`、`format` 等）全部原样透传，不保证 Gemini 支持。测验 Q9 给出了修正版。

### 3.5 tool_choice 翻译

```python
def tool_choice_anthropic(tc: ToolChoice) -> dict:
    if tc.mode == "auto":
        return {"type": "auto"}
    if tc.mode == "none":
        return {"type": "none"}
    if tc.mode == "required":
        return {"type": "any"}
    if tc.mode == "force":
        return {"type": "tool", "name": tc.tool_name}
    raise ValueError(tc.mode)

def tool_choice_gemini(tc: ToolChoice) -> dict:
    mode_map = {"auto": "AUTO", "none": "NONE", "required": "ANY"}
    if tc.mode in mode_map:
        return {"function_calling_config": {"mode": mode_map[tc.mode]}}
    if tc.mode == "force":
        return {"function_calling_config": {"mode": "ANY",
                                            "allowed_function_names": [tc.tool_name]}}
    raise ValueError(tc.mode)
```

| canonical | OpenAI | Anthropic | Gemini |
|-----------|--------|-----------|--------|
| auto | `"auto"` | `{"type": "auto"}` | `mode: "AUTO"` |
| none | `"none"` | `{"type": "none"}` | `mode: "NONE"` |
| required | `"required"` | `{"type": "any"}` | `mode: "ANY"` |
| force | `{"type": "function", "function": {"name": ...}}` | `{"type": "tool", "name": ...}` | `mode: "ANY"` + `allowed_function_names: [...]` |

- OpenAI 的 `tool_choice` 可以是字符串，也可以是对象，所以 `tool_choice_openai` 的返回类型是 `Any`。
- Gemini 的 force 是"ANY + 白名单只有一个"——这比讲义对比表中只写 `mode: "ANY"` 更准确（只写 ANY 不能指定是哪个工具）。
- Gemini 用 dict 查表 `mode_map` 处理三种简单模式，比连续 `if` 更紧凑。
- 不认识的模式统一 `raise ValueError(tc.mode)`：实测 `ToolChoice("any")` → `ValueError: any`。这是"快速失败"的好习惯。
- 讲义提到的各家独有选项（Anthropic `disable_parallel_tool_use`、Gemini `VALIDATED` 模式）没有在 canonical 中建模。

### 3.6 三份模拟响应：调用藏在哪里

```python
OPENAI_RESPONSE    = {"choices": [{"message": {..., "tool_calls": [
                        {"id": "call_abc123", "type": "function",
                         "function": {"name": "get_weather",
                                      "arguments": '{"city":"Bengaluru","units":"celsius"}'}}]},
                       "finish_reason": "tool_calls"}]}
ANTHROPIC_RESPONSE = {..., "content": [{"type": "text", "text": "Looking that up."},
                        {"type": "tool_use", "id": "toolu_xyz789", "name": "get_weather",
                         "input": {"city": "Bengaluru", "units": "celsius"}}],
                      "stop_reason": "tool_use"}
GEMINI_RESPONSE    = {"candidates": [{"content": {"role": "model", "parts": [
                        {"functionCall": {"id": "fc-9a3d", "name": "get_weather",
                                          "args": {"city": "Bengaluru", "units": "celsius"}}}]},
                       "finishReason": "STOP"}]}
```

（上面为节选压缩，结构与源码一致。）

- OpenAI 的 `arguments` 是**单引号包住的 JSON 字符串**；另两家是 dict。
- Anthropic 的 `content` 里 text 块和 tool_use 块可以并存——模型可以边说"Looking that up."边发起调用。
- Gemini 的 `finishReason` 是 `"STOP"`，并不像另两家那样明确表示"因工具调用而停止"，所以不能只凭结束原因判断。
- Gemini 示例 id 是 `fc-9a3d`，并不是讲义所说的 UUID 格式；这只是示例数据，说明不要假设 id 的格式。

### 3.7 三个 parser

```python
def parse_openai(resp: dict) -> list[Call]:
    msg = resp["choices"][0]["message"]
    calls = []
    for tc in msg.get("tool_calls", []):
        fn = tc["function"]
        calls.append(Call(id=tc["id"], name=fn["name"], args=json.loads(fn["arguments"])))
    return calls

def parse_anthropic(resp: dict) -> list[Call]:
    calls = []
    for block in resp.get("content", []):
        if block.get("type") == "tool_use":
            calls.append(Call(id=block["id"], name=block["name"], args=block["input"]))
    return calls

def parse_gemini(resp: dict) -> list[Call]:
    calls = []
    for part in resp["candidates"][0]["content"].get("parts", []):
        if "functionCall" in part:
            fc = part["functionCall"]
            calls.append(Call(id=fc.get("id", ""), name=fc["name"], args=fc["args"]))
    return calls
```

- 三个函数都返回**列表**，天然支持一轮多个（并行）调用。
- Anthropic parser 按 `type` 过滤，text 块被跳过（宿主写历史时应保留完整 content）。
- 边界情况的实测结果：

| 情况 | 结果 |
|------|------|
| OpenAI 消息里没有 `tool_calls` 键 | 返回 `[]`，正确 |
| OpenAI `tool_calls: None`（键存在、值为 null） | ⚠️ `TypeError: 'NoneType' object is not iterable`，因为 `.get(k, [])` 只在键缺失时用默认值 |
| OpenAI `arguments` 为非法 JSON（尾逗号） | ⚠️ `JSONDecodeError` 直接抛出，没有讲义说的"注入错误并重试" |
| Gemini 两个并行调用都没有 id | ⚠️ 返回两个 `id=''` 的 `Call`，结果无法区分 |

  健壮写法见测验 Q10：`msg.get("tool_calls") or []`、捕获 `JSONDecodeError` 转成结构化错误、缺 id 时本地生成。
- `parse_openai` 只取 `choices[0]`；请求 `n > 1` 时其他候选被忽略。

### 3.8 `main`：并排打印与等价性检查

```python
    all_names = {oa.name, an.name, gm.name}
    all_args = {json.dumps(oa.args, sort_keys=True),
                json.dumps(an.args, sort_keys=True),
                json.dumps(gm.args, sort_keys=True)}
    print(f"  same tool name across providers : {len(all_names) == 1}")
    print(f"  same args payload across providers : {len(all_args) == 1}")
```

- 用**集合去重**判断三者是否相同：集合长度为 1 就说明完全一致。
- dict 不能放进集合（不可哈希），所以先 `json.dumps(..., sort_keys=True)` 变成规范化字符串；`sort_keys` 保证键顺序不同的 dict 得到相同字符串。
- `asdict(WEATHER)` 把 dataclass 递归转成 dict，便于 `json.dumps` 打印。

### 3.9 本节缺失的第五要素：结果回填

讲义列出的五个共同要素里，"Result injection" 在代码里完全没有出现；讲义"Use It"说代码会"round-trips a fake tool call"，实际只做了"响应 → Call"这一半。补全方式见测验 Q11：OpenAI 是 `{"role": "tool", "tool_call_id", "content": <字符串>}`，Anthropic 是 `user` 消息中的 `tool_result` 块（可带 `is_error`），Gemini 是 `functionResponse`（`response` 为对象）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一份 canonical + 边缘翻译 | 业务逻辑与 provider 解耦，加一家只需加一组函数 | 抽象可能抹掉各家独有能力（`disable_parallel_tool_use`、`allowed_function_names` 的多元素用法等） |
| canonical schema 按 OpenAI strict 写 | 选"最严格"的作为基准，向下兼容其他家 | 必须处理 nullable+enum 陷阱；Gemini 需要方言转换 |
| `_gemini_schema` 用通用递归 | 代码短 | 不区分关键字与属性名；类型数组未转换；生产应按关键字白名单逐个转换并在构建期报错 |
| 手写模拟响应 | 离线、可复现 | 真实响应还有流式、多候选、refusal、安全拦截等形状；应录制真实样本做契约测试 |
| parser 不做错误处理 | 演示清晰 | 遇到 `null`、非法 JSON、缺 id 会崩溃或静默出错 |
| `strict` 在其他家被丢弃 | 其他家没有同名字段 | 应至少打日志/警告，并在宿主侧补校验 |
| 不实现结果回填 | 本节聚焦声明与调用 | 循环无法闭合；第 03 节开始处理并行结果 |
| tool_choice 未知模式抛 `ValueError` | 快速失败 | 但 force 缺少 `tool_name` 不报错，应在 `ToolChoice.__post_init__` 中校验 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Tool:`、`class Call:` | 自动生成构造函数和 `repr`；运行输出中的 `Call(id='call_abc123', ...)` 就是自动生成的 `__repr__` |
| `dataclasses.asdict` | `asdict(WEATHER)` | dataclass → dict（递归） |
| 联合类型 `X \| None` | `tool_name: str \| None = None` | "字符串或 None"；配合 `from __future__ import annotations` 使用 |
| `typing.Any` | `def _gemini_schema(node: Any) -> Any` | 任意类型 |
| 布尔字面量 | `"additionalProperties": False` | Python 的 `False` 经 `json.dumps` 变成 JSON 的 `false` |
| 递归处理嵌套结构 | `_gemini_schema` 对 dict、list 分别递归 | 处理任意深度的 JSON |
| `isinstance` 分派 | `isinstance(node, dict)`、`isinstance(v, str)` | 按类型走不同分支 |
| `continue` | `if k == "additionalProperties": continue` | 跳过本次循环剩余部分 |
| 字典查表代替 if 链 | `mode_map = {"auto": "AUTO", ...}`；`mode_map[tc.mode]` | 更紧凑、易扩展 |
| `in` 判断键 | `if tc.mode in mode_map`、`if "functionCall" in part` | 对 dict 判断的是键 |
| `raise ValueError(...)` | `raise ValueError(tc.mode)` | 遇到非法输入快速失败 |
| `dict.get(k, default)` 的陷阱 | `msg.get("tool_calls", [])` | 键存在且值为 `None` 时返回 `None`，不是默认值；用 `msg.get(k) or []` 更稳 |
| 单引号包 JSON 字符串 | `'{"city":"Bengaluru","units":"celsius"}'` | 外层单引号，内部双引号无需转义 |
| `json.loads` / `json.dumps` | `json.loads(fn["arguments"])`、`json.dumps(x, indent=2, sort_keys=True)` | 解析 / 序列化；`indent` 美化，`sort_keys` 规范化键顺序 |
| 集合推导与去重 | `{oa.name, an.name, gm.name}` | 集合自动去重，`len == 1` 表示全部相同 |
| 条件表达式 | `"get_weather" if mode == "force" else None` | 三元表达式 |
| f-string `!r` | `f"mode = {mode!r}"` | 用 `repr` 显示，字符串带引号：`mode = 'auto'` |
| `type(x).__name__` | `type(oa.args).__name__` | 取类型名字符串，如 `dict` |
| 列表下标链 | `resp["choices"][0]["message"]` | 逐层取值；任何一层缺失都会 `KeyError`/`IndexError` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，输出确定、无随机性）。节选：

```text
Gemini:
{
  "functionDeclarations": [
    {
      "name": "get_weather",
      ...
      "parameters": {
        "type": "OBJECT",
        "properties": {
          "city": {"type": "STRING"},
          "units": {
            "type": ["string", "null"],          ← 未转换（应为 STRING + nullable）
            "enum": ["celsius", "fahrenheit"]
          }
        },
        "required": ["city", "units"]            ← additionalProperties 已删除
      }
    }
  ]
}

--- tool_choice translation ---
mode = 'required'
  OpenAI    : "required"
  Anthropic : {"type": "any"}
  Gemini    : {"function_calling_config": {"mode": "ANY"}}

mode = 'force'
  OpenAI    : {"type": "function", "function": {"name": "get_weather"}}
  Anthropic : {"type": "tool", "name": "get_weather"}
  Gemini    : {"function_calling_config": {"mode": "ANY", "allowed_function_names": ["get_weather"]}}

--- parsing provider responses ---
OpenAI     : Call(id='call_abc123', name='get_weather', args={'city': 'Bengaluru', 'units': 'celsius'})
Anthropic  : Call(id='toolu_xyz789', name='get_weather', args={'city': 'Bengaluru', 'units': 'celsius'})
Gemini     : Call(id='fc-9a3d', name='get_weather', args={'city': 'Bengaluru', 'units': 'celsius'})

--- args type after parsing ---
  OpenAI raw args type : string -> dict
  Anthropic raw args   : object -> dict
  Gemini raw args      : object -> dict

--- equivalence check ---
  same tool name across providers : True
  same args payload across providers : True
```

逐项解读：

- **canonical 与 OpenAI 声明**：OpenAI 的 `parameters` 与 canonical `input_schema` 完全相同，外面多包一层 `function`，并带 `strict: true`。
- **Anthropic 声明**：最扁平，没有 `strict`。
- **Gemini 声明**：`OBJECT`、`STRING` 已大写，`additionalProperties` 已删除，但 `units` 的类型数组保持小写原样——这是翻译器的缺陷，真实请求中可能被拒绝。
- **tool_choice 四组**：同一语义三种写法；注意 required 在 Anthropic 叫 `any`。
- **三个 `Call`**：id 前缀不同（`call_` / `toolu_` / `fc-`），name 与 args 完全一致。
- **args 类型**：只有 OpenAI 的原始参数是字符串，解析后三者都是 dict。
- **等价性检查两个 True**：证明三家"语义相同、形状不同"。但要注意，这只是在"格式良好"的模拟数据上成立；边界情况见 3.7 的表格。

---

## 7. 动手改一改

1. **修复 nullable 陷阱**：给 `units` 的 enum 加上 `None`，用 `jsonschema` 验证 `{"city": "X", "units": None}` 现在能通过。
2. **修复 Gemini 翻译器**（讲义练习 1）：按测验 Q9 改写 `_gemini_schema`，输出 `{"type": "STRING", "nullable": true, ...}`；再加一个含 `["string", "integer"]` 的字段，确认翻译器在构建期抛错。
3. **补全结果回填**：实现 `result_openai / result_anthropic / result_gemini`（测验 Q11），并写一个函数把"一轮多个调用的结果"按各家规则打包（Anthropic 放进同一条 user 消息）。
4. **健壮 parser**：处理 `tool_calls: None`、非法 JSON、Gemini 缺 id；把解析错误转成 `ToolCallParseError` 并在循环中作为错误结果回填（测验 Q10）。
5. **扩展 tool_choice**（讲义练习 3）：给 `ToolChoice` 加 `parallel: bool` 字段，映射到 OpenAI 的 `parallel_tool_calls` 和 Anthropic 的 `disable_parallel_tool_use`；加 `__post_init__` 校验 force 模式必须有 `tool_name`。
6. **契约测试**（讲义练习 5）：构造一个违反 schema 的调用（缺 `city`、`units` 为 `"kelvin"`），用第 01 节的 `validate` 或 `jsonschema` 校验，写成 `unittest` 用例，确保三家 parser 解析后都能被同一校验器拦下。

---

## 8. 常见坑

- **在 Anthropic/Gemini 上对参数调用 `json.loads`**：它们已经是 dict，会直接 `TypeError`；反过来在 OpenAI 上忘了 parse，会把整个字符串当参数。
- **`dict.get(k, [])` 遇到 `null`**：键存在但值为 `None` 时不会用默认值。
- **可空字段与 enum**：`type` 允许 null 但 `enum` 不含 null，等于不允许 null。
- **只靠结束原因判断是否发起调用**：Gemini 示例的 `finishReason` 是 `STOP`。
- **Anthropic 结果回填角色写错**：是 `user` 消息里的 `tool_result` 块，不是 `role: "tool"`。
- **丢掉 Anthropic 响应里的 text 块**：解析调用时可以跳过，但写回历史时必须保留完整 content。
- **strict 被静默丢弃**：移植到不支持 strict 的 provider 后，校验强度下降却没人察觉。
- **假设 id 格式或必然存在**：不同 provider、不同版本的 id 前缀和有无都不同。
- **Gemini 的 force 只写 `mode: "ANY"`**：只能强制"调用某个工具"，不能指定是哪个，需要 `allowed_function_names`。
