# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 01 节 工具接口：为什么 Agents 需要结构化输入输出 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`datetime`、`json`、`re`、`time`、`uuid`、`dataclasses`、`typing`），无需 LLM、无需 API key、无需网络

---

## 1. 这份代码在考察什么

这份代码用不到 250 行标准库 Python，把讲义的"四步循环"（describe → decide → execute → observe）完整跑了一遍，只是把 decide 这一步的 LLM 换成了一个关键词路由器 `fake_decide`。它考察的是：

1. **工具是怎么被"描述"的**：`Tool` dataclass = name + description + JSON Schema + executor（+ consequential 标志）。
2. **宿主在执行前做什么**：查工具名 → 按 schema 校验参数 → （有后果的工具）关卡 → 执行并计时。
3. **结果怎么回到模型**：把结果作为 `role: "tool"`、带匹配 `id` 的消息追加进 history，再调用一次 decide。
4. **循环怎么终止**：模型给出最终文本，或撞上 `MAX_TURNS = 5` 的 circuit breaker。
5. **pure 与 consequential 的区分**：注册表打印 `[pure]` / `[consequential]`，consequential 工具会打印 `GATE` 行。

> 一句话：**LLM 只负责"说要做什么"，宿主负责"检查、执行、汇报"——这份代码把宿主那一半写得清清楚楚，同时留下了不少值得改进的简化。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MAX_TURNS = 5` | 常量 | 每次对话最多 decide 5 轮 | circuit breaker |
| `Tool` | dataclass | name / description / input_schema / executor / consequential | 工具三要素 + 信任划分 |
| `tool_add` / `tool_get_time` / `tool_get_weather` | 函数 | 三个执行函数，输入 dict，输出可 JSON 序列化的 dict | executor |
| `REGISTRY` | 列表 | 三个 `Tool` 实例 | 工具注册表（describe） |
| `validate` | 递归函数 | JSON Schema 最小子集校验，返回错误列表 | execute 前的参数校验 |
| `fake_decide` | 函数 | 用正则模拟模型：返回 `{"content": ...}` 或 `{"tool_calls": [...]}` | decide |
| `run_loop` | 函数 | 四步循环本体，打印每一步 | 整个 tool loop |
| `describe_registry` | 函数 | 打印注册表与 pure/consequential 分类 | describe |
| `main` | 函数 | 依次跑四条演示查询 | 演示入口 |

数据流：`main` → `describe_registry` 打印注册表 → 对每条查询调用 `run_loop` → `fake_decide` 产生调用 → `validate` 校验 → `executor` 执行 → 结果写入 `history` → 再次 `fake_decide` → 最终答案。

---

## 3. 逐段精讲

### 3.1 `Tool`：一个工具 = 四个字段 + 一个标志

```python
@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    executor: Callable[[dict], Any]
    consequential: bool = False
```

- `name`、`description`、`input_schema` 是**发给模型**的部分（describe）；`executor` 是**只留在宿主**的部分——模型永远拿不到函数本身。
- `consequential` 默认 `False`。讲义练习 3 要求"加一个 `consequential: true` 标志"，其实代码已经预留了这个字段和对应的 `GATE` 打印，只是三个演示工具都没有设为 `True`。
- 讲义"需要关注的内容"里写"注册表为每个工具保存**三个**字段：名称、描述、schema，以及执行函数引用"——数出来其实是四个（加上 consequential 是五个），这是讲义的笔误。

### 3.2 三个执行函数

```python
def tool_add(args: dict) -> dict:
    return {"sum": args["a"] + args["b"]}

def tool_get_time(args: dict) -> dict:
    tz = args.get("timezone", "UTC")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {"now": now, "timezone": tz}

def tool_get_weather(args: dict) -> dict:
    fake = {"Bengaluru": 28, "Tokyo": 12, "Zurich": 4, "Lagos": 31}
    city = args["city"]
    units = args.get("units", "celsius")
    temp = fake.get(city, 20)
    return {"city": city, "temp": temp, "units": units}
```

- 统一签名 `(args: dict) -> dict`：宿主可以用同一种方式调用所有工具，返回值能被 `json.dumps` 序列化（讲义："The result must be serializable"）。
- ⚠️ `tool_get_time` **忽略了 timezone**：无论传什么都返回 UTC 时间，但把 `timezone` 字段原样回显。实测 `{"timezone": "Asia/Tokyo"}` 返回 `{"now": "...+00:00", "timezone": "Asia/Tokyo"}`——结果"自称"是东京时间，实际是 UTC，模型会被误导。正确做法是用 `zoneinfo.ZoneInfo(tz)` 转换，或在 schema 里只允许 `"UTC"`。
- ⚠️ `tool_get_weather` 对未知城市返回默认 20 度：实测 `{"city": "Atlantis"}` → `{"temp": 20}`。这是"编造数据"——真实工具应返回结构化错误（如 `{"error": "unknown city"}`），否则模型会把假数据当真话转述给用户。
- ⚠️ `units` 只是回显，没有做摄氏/华氏换算。
- 三者都是 pure（只读、无副作用），对应讲义的 pure 示例。

### 3.3 `REGISTRY`：describe 的具体样子

```python
    Tool(
        name="get_weather",
        description=(
            "Use when the user asks about current conditions in a named city. "
            "Do not use for forecasts or historical weather data."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "units": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
        executor=tool_get_weather,
    ),
```

- description 统一采用"**Use when X. Do not use for Y.**"两句式：前一句教模型何时选它，后一句排除易混淆的场景。这正是 `outputs/skill-tool-interface-reviewer.md` 里要求的形状。
- `units` 用 `enum` 表达封闭取值集合；`required` 只有 `city`，`units` 可选。
- 括号包住的相邻字符串字面量会被 Python 自动拼接成一个字符串（见第 5 节）。
- ⚠️ 没有声明 `"additionalProperties": false`，所以多余字段会被静默接受（见 3.4）。
- `get_time` 的 `"required": []` 表示所有字段可选。

### 3.4 `validate`：最小 JSON Schema 校验器

```python
def validate(schema: dict, value: Any) -> list[str]:
    errors: list[str] = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return [f"expected object, got {type(value).__name__}"]
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"missing required field '{field}'")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate(sub, value[key]))
        return errors
    if t == "number" and not isinstance(value, (int, float)):
        errors.append(f"expected number, got {type(value).__name__}")
    if t == "string" and not isinstance(value, str):
        errors.append(f"expected string, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"value {value!r} not in enum {schema['enum']}")
    return errors
```

- **返回错误列表而不是抛异常**：调用方可以一次看到所有问题，并且可以把列表原样回填给模型。
- **递归**：对 object 的每个已出现的属性，用子 schema 递归校验，错误用 `extend` 汇总。
- 实测行为：

| 调用 | 返回 | 评价 |
|------|------|------|
| `{"a": 1}`（add） | `["missing required field 'b'"]` | 正确 |
| `{"a": "7", "b": 2}` | `['expected number, got str']` | 正确 |
| `{"city": 5, "units": "kelvin"}` | `['expected string, got int', "value 'kelvin' not in enum [...]"]` | 正确，两个错误都报 |
| `[1, 2]`（add） | `['expected object, got list']` | 正确 |
| `{"a": True, "b": 2}` | `[]` | ⚠️ 错放：`bool` 是 `int` 的子类 |
| `{"a": 1, "b": 2, "c": "rm -rf"}` | `[]` | ⚠️ 多余字段被静默接受 |
| `validate({"type": "integer"}, 1.5)` | `[]` | ⚠️ 不认识的类型直接放行 |
| `validate({"type": "number", "minimum": 0}, -3)` | `[]` | ⚠️ 没有实现 minimum/maximum |

- ⚠️ **讲义与代码不一致**：讲义说校验器支持 "types, required, enum, min/max"，代码里没有任何 min/max 逻辑；`integer`、`boolean`、`array`、`additionalProperties` 也都不支持。
- ⚠️ 错误信息不带字段路径，嵌套对象出错时难以定位（测验 Q9 给出了带 `$.a` 路径的改写版）。

### 3.5 `fake_decide`：用正则冒充模型

```python
def fake_decide(user_msg: str, history: list[dict]) -> dict:
    last = history[-1] if history else {}
    if last.get("role") == "tool":
        return {"content": f"Final answer built from tool output: {last.get('content')}"}
    msg = user_msg.lower()
    if re.search(r"\b(add|sum|plus)\b", msg):
        nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", msg)]
        if len(nums) >= 2:
            return {"tool_calls": [{"id": f"call_{uuid.uuid4().hex[:8]}",
                                    "name": "add",
                                    "arguments": {"a": nums[0], "b": nums[1]}}]}
    if "time" in msg:
        ...
    match = re.search(r"weather in (\w+)", msg)
    ...
    return {"content": "I cannot route that query to any registered tool."}
```

- **返回值的两种形状**正好对应模型的两种决策：`{"content": ...}`（直接回答）或 `{"tool_calls": [...]}`（调用工具）。每个调用含 `id`、`name`、`arguments` 三个字段，与讲义的"三个稳定字段"一致。讲义提到的第三种决策"拒绝"没有模拟。
- **observe 后立即收尾**：只要 history 最后一条是 tool 消息，就把工具结果拼进最终答案。所以每条查询最多 2 轮。
- 路由顺序是 add → time → weather，先命中先返回。
- 实测的路由缺陷（都已运行验证）：

| 输入 | 实际结果 | 原因 |
|------|---------|------|
| `"add 1e3 and 2"` | `add(1.0, 3.0)` | 正则不认识科学计数法，`1e3` 被拆成 1 和 3 |
| `"weather in new york"` | `city="New"` | `(\w+)` 只抓一个单词 |
| `"I sometimes wonder"` | `get_time` | `"time" in msg` 是子串匹配，没有词边界 |
| `"weather in Tokyo at this time"` | `get_time` | time 分支排在 weather 前面 |
| `"add 10"` | 无法路由 | 数字不足两个，落到兜底回复 |

  这些对应真实模型的"选错工具"和"参数抽错"两类错误；后者的值类型合法，schema 校验也拦不住。
- ⚠️ docstring 里写 "swap this for provider.chat.completions.create with `tools=[t.input_schema for t in REGISTRY]`"——这不对。真实 API 需要的是包含 name、description、parameters 的完整工具声明（OpenAI 是 `{"type": "function", "function": {"name", "description", "parameters"}}`），只传 schema 的话模型连工具叫什么都不知道。下一节会看到三家 provider 的真实形状。
- `uuid.uuid4().hex[:8]` 每次运行都不同，所以输出里的 `id=call_xxxxxxxx` 不可复现。

### 3.6 `run_loop`：四步循环本体

```python
    tools_by_name = {t.name: t for t in REGISTRY}
    history: list[dict] = [{"role": "user", "content": user_msg}]
    for turn in range(1, MAX_TURNS + 1):
        decision = fake_decide(user_msg, history)            # decide
        if "content" in decision:
            print(f"TURN {turn} DECIDE : final answer")
            print(f"MODEL : {decision['content']}")
            return
        for call in decision["tool_calls"]:
            tool = tools_by_name.get(call["name"])
            ...
            if tool is None:
                print(f"           ERROR : unknown tool {call['name']}")
                return
            errs = validate(tool.input_schema, call["arguments"])  # 校验
            if errs:
                print(f"           VALIDATION ERRORS : {errs}")
                return
            if tool.consequential:
                print("           GATE : tool is consequential, would confirm")
            start = time.perf_counter()
            result = tool.executor(call["arguments"])               # execute
            ms = (time.perf_counter() - start) * 1000
            ...
            history.append({                                        # observe
                "role": "tool", "id": call["id"],
                "name": tool.name, "content": json.dumps(result),
            })
        print(f"TURN {turn} OBSERVE: history length = {len(history)}")
    print("LOOP TERMINATED : hit MAX_TURNS circuit breaker")
```

- `tools_by_name` 用字典推导式把列表变成"名字 → 工具"的查找表，O(1) 查找。
- `for turn in range(1, MAX_TURNS + 1)` 就是 circuit breaker：`for` 正常跑完（没有 `return`）才会走到最后一行的 `LOOP TERMINATED`。
- 一轮里可以有多个 `tool_calls`（内层 `for`），已经为并行调用（第 03 节）留好了结构，只是这里串行执行。
- `time.perf_counter()` 是高精度单调时钟，适合测量耗时。
- 关于设计上的简化（都会在后续小节修正）：
  - ⚠️ **未知工具 / 校验失败时直接 `return`**，错误没有回填给模型。讲义描述的是"fail fast **and surface the error to the model**"——模型应该看到错误并在下一轮修正。
  - ⚠️ **history 里没有 assistant 的 tool_calls 消息**，只有 user 和 tool 两类。真实的 OpenAI / Anthropic 协议要求 tool 结果必须跟在发起调用的 assistant 消息之后，否则请求会被拒绝。输出中 `history length = 2` 就是 user + tool。
  - ⚠️ **`GATE` 只打印、不阻断**：consequential 工具打印完 "would confirm" 照样执行。
  - ⚠️ **执行器异常没有捕获**：任何工具抛异常都会让整个宿主崩溃（`outputs/` 里的审查 skill 把这列为 hard reject）。
  - ⚠️ 在默认 `fake_decide` 下 circuit breaker 永远不会触发。我们用一个"永远调用 `get_time`"的替身 decider 实测，跑满 TURN 1–5 后打印 `LOOP TERMINATED : hit MAX_TURNS circuit breaker`，history 长度增至 6。

### 3.7 `describe_registry` 与 `main`

```python
        kind = "consequential" if t.consequential else "pure"
        print(f"  {t.name:14s} [{kind}] - {t.description}")
```

- `{t.name:14s}` 把名字左对齐填充到 14 个字符，让表格对齐。
- `main` 依次运行四条查询，覆盖三个工具各一次和"无法路由"一次。
- 同目录下还有一份 `main.ts`（TypeScript 版本，不在本讲解范围内），结构与 Python 版一一对应，同样有 `MAX_TURNS`、`validate`、`consequential` 和 `GATE` 打印。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用正则 `fake_decide` 代替 LLM | 离线可跑、输出可读，专注宿主逻辑 | 路由非常脆弱；生产换成真实 provider（第 02 节） |
| `Tool` dataclass 把描述与执行器放一起 | 一处注册，describe 和 execute 共用 | 发给模型时必须只序列化 name/description/schema，不能把函数对象发出去 |
| 手写最小校验器 | 不依赖第三方库，便于讲解 | bool 冒充 number、无 min/max、无 additionalProperties；生产用 `jsonschema` 或 Pydantic（第 04 节） |
| 校验失败直接 `return` | 演示"执行前拦截" | 应把结构化错误作为 tool 结果回填，让模型重试 |
| history 只记 user 和 tool 消息 | 简化 | 真实协议需要 assistant 的 tool_calls 消息在前 |
| `GATE` 只打印 | 展示关卡位置 | 真正的关卡要等用户确认、拒绝时不执行（fail closed） |
| `MAX_TURNS = 5` | 讲义：生产常设 5–20 | 还应加 token/费用预算、同错误重复计数熔断 |
| 执行器返回 dict 并 `json.dumps` | 保证可序列化 | 应捕获异常、限制结果大小、处理非 JSON 类型（如 datetime） |
| 演示工具全是 pure | 安全、易演示 | 无法展示 consequential 路径；练习 3 补上 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可以在旧版本 Python 中使用 `list[dict]` 等新写法 |
| `@dataclass` | `class Tool:` | 自动生成 `__init__`、`__repr__` 等；字段按类型注解声明 |
| 字段默认值 | `consequential: bool = False` | 有默认值的字段必须排在无默认值字段之后 |
| 类型注解 | `def validate(schema: dict, value: Any) -> list[str]` | 只是提示，运行时不检查 |
| `Callable[[dict], Any]` | `executor: Callable[[dict], Any]` | "接收一个 dict、返回任意值的可调用对象" |
| 函数是一等对象 | `executor=tool_add`，`tool.executor(call["arguments"])` | 函数可以存进字段、稍后调用 |
| 相邻字符串自动拼接 | `("Use when ... " "Do not use ...")` | 括号内相邻的字符串字面量在编译时合并 |
| `dict.get(key, default)` | `args.get("timezone", "UTC")`、`schema.get("required", [])` | 键不存在时返回默认值而不报错 |
| `isinstance` 与元组 | `isinstance(value, (int, float))` | 任一类型匹配即为真；注意 `bool` 是 `int` 子类 |
| 递归 | `validate` 内部调用 `validate(sub, value[key])` | 处理嵌套对象 |
| `list.extend` vs `append` | `errors.extend(...)`、`history.append({...})` | `extend` 合并列表元素，`append` 追加一个元素 |
| 正则 | `re.search(r"\b(add\|sum\|plus)\b", msg)`、`re.findall(...)`、`match.group(1)` | `\b` 词边界；`findall` 返回所有匹配；`group(1)` 取第一个捕获组 |
| 原始字符串 | `r"-?\d+\.?\d*"` | `r""` 中反斜杠不转义，写正则必备 |
| 列表推导式 | `[float(n) for n in re.findall(...)]` | 一行完成映射 |
| 字典推导式 | `{t.name: t for t in REGISTRY}` | 构建名字到对象的查找表 |
| 条件表达式 | `"consequential" if t.consequential else "pure"` | 三元运算 |
| f-string 格式符 | `{t.name:14s}`、`{ms:.2f}`、`{value!r}` | 宽度填充、两位小数、用 `repr()` 显示（字符串带引号） |
| `uuid` | `uuid.uuid4().hex[:8]` | 随机 UUID 的十六进制串取前 8 位 |
| `datetime` 时区 | `dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")` | 带时区的当前时间，ISO 8601 格式精确到秒 |
| `time.perf_counter()` | 计时 | 高精度单调时钟 |
| `json.dumps` | `json.dumps(result)` | Python 对象 → JSON 字符串；`True` 变 `true`，`7.0` 保持 `7.0` |
| `for` 与提前 `return` | `run_loop` | 循环中途 `return` 就不会执行循环后的"熔断"打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，Python 3，耗时 < 1 秒；id 和时间每次不同）：

```text
TOOL REGISTRY
------------------------------------------------------------------------
  add            [pure] - Use when the user asks for the sum of two numbers. Do not use for subtraction, product, or symbolic algebra.
  get_time       [pure] - Use when the user asks what time it is. Do not use for historical dates or future scheduling.
  get_weather    [pure] - Use when the user asks about current conditions in a named city. Do not use for forecasts or historical weather data.

USER : please add 7 and 35
TURN 1 DECIDE : call add id=call_541edd40
           args = {"a": 7.0, "b": 35.0}
TURN 1 EXECUTE: add -> {"sum": 42.0} [0.00 ms]
TURN 1 OBSERVE: history length = 2
TURN 2 DECIDE : final answer
MODEL : Final answer built from tool output: {"sum": 42.0}

USER : what time is it?
TURN 1 DECIDE : call get_time id=call_83b697dc
           args = {"timezone": "UTC"}
TURN 1 EXECUTE: get_time -> {"now": "2026-10-12T16:52:23+00:00", "timezone": "UTC"} [0.02 ms]
...
USER : tell me the weather in Bengaluru
TURN 1 DECIDE : call get_weather id=call_64554756
           args = {"city": "Bengaluru", "units": "celsius"}
TURN 1 EXECUTE: get_weather -> {"city": "Bengaluru", "temp": 28, "units": "celsius"} [0.00 ms]
...
USER : write me a haiku about tea
TURN 1 DECIDE : final answer
MODEL : I cannot route that query to any registered tool.
```

逐项解读：

- **注册表全是 `[pure]`**：三个工具都没有设 `consequential=True`，所以整个运行中不会出现 `GATE` 行。
- **加法结果是 `42.0` 而不是 `42`**：`fake_decide` 把正则抽到的数字都转成了 float。
- **`history length = 2`**：user 消息 + 1 条 tool 消息。真实协议中还应有一条 assistant 的 tool_calls 消息，长度应为 3。
- **每条查询 2 轮结束**：TURN 1 调用工具，TURN 2 因为 history 最后一条是 tool 而直接给出最终答案。"最终答案"只是把 JSON 原样拼进去，没有真正的语言组织——这正是真实 LLM 在 observe 之后要做的事。
- **耗时 `0.00 ms`**：执行器是内存运算，几乎不耗时；真实工具（网络请求、数据库）才是循环的主要延迟来源，这也是第 03 节要讲并行调用的原因。
- **haiku 查询**：没有任何分支命中，对应"模型直接回答、不调用工具"的决策；注意它是在 TURN 1 就结束的。
- **从未出现 `LOOP TERMINATED`**：默认 decider 下 circuit breaker 不可达（见 3.6 的替身验证）。

---

## 7. 动手改一改

1. **讲义练习 1**：加 `get_stock_price(ticker)`，description 用讲义原文。在 `fake_decide` 的已有分支**之前**加一条"含 price 且有 2–5 位大写代码"的路由（注意要匹配原始 `user_msg`，因为 `msg` 已经被转成小写）。验证 `"what is the price of NVDA"` 路由正确。
2. **讲义练习 2**：构造缺字段、多字段、bool 冒充 number 三种调用，观察 `validate` 的行为；然后给 schema 加 `"additionalProperties": false` 并扩展 `validate` 支持它，再补上 `minimum`/`maximum`/`integer`/`boolean`（参考测验 Q9）。
3. **讲义练习 3**：加一个 `send_message(to, text)` 并设 `consequential=True`；把 `GATE` 从"打印"改成真正调用 `confirm(call) -> bool`，用户拒绝时不执行，而是回填 `{"error": "user declined"}`。
4. **错误回填**：把 `run_loop` 中两处 `return`（未知工具、校验失败）改成"追加一条带 `is_error: True` 的 tool 消息再 `continue`"，同时给 `tool.executor(...)` 包上 `try/except`（参考测验 Q11）。
5. **补全协议**：在执行工具前追加 `{"role": "assistant", "tool_calls": decision["tool_calls"]}`，使 history 结构与 OpenAI Chat Completions 一致；再写一个函数把这个 history 转成 Anthropic 的 `tool_use` / `tool_result` 块（为第 02 节做准备）。
6. **修正 `get_time`**：用 `zoneinfo.ZoneInfo(tz)` 真正按时区返回时间，未知时区返回结构化错误；在 schema 中为 `timezone` 写一条 description，说明使用 IANA 名称（如 `Asia/Tokyo`）。

---

## 8. 常见坑

- **以为模型会执行工具**：模型只输出调用请求，执行永远在宿主。把执行器"发给模型"是概念错误。
- **只把 schema 发给模型**：没有 name 和 description，模型无法选择工具（本文件 docstring 中 `tools=[t.input_schema ...]` 的写法就是这个错误）。
- **`isinstance(True, int)` 为真**：校验 number/integer 时必须先排除 bool。
- **多余字段被静默接受**：不声明 `additionalProperties: false` 时，模型幻觉出的字段会一路进入执行器。
- **工具回显参数造成误导**：`get_time` 回显 timezone 但不转换，结果看似可信却是错的；工具要么真正处理参数，要么在 schema 中禁止它。
- **未知输入返回默认值**：`get_weather` 对未知城市返回 20 度，比报错更危险。
- **校验失败后静默终止**：模型看不到错误就无法修正，用户只会看到"没反应"。
- **漏掉 assistant 的 tool_calls 消息**：对接真实 API 时最常见的 400 错误来源之一。
- **没有 circuit breaker 或只有轮数上限**：还应限制 token/费用，并对"同一错误反复出现"单独熔断。
