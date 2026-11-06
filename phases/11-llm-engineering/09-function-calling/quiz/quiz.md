# 测验 · Function Calling 与工具使用（Function Calling & Tool Use）

> **阶段 11 · LLM 工程 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/function_calling.py](../code/function_calling.py)、[code/tests/test_main.py](../code/tests/test_main.py)、[code/main.ts](../code/main.ts)（TypeScript 对照版） ｜ 代码讲解：[code/function_calling.讲解.md](../code/function_calling.讲解.md)（测试说明见其第 9 节）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 模型不执行任何东西 | 模型只输出"调用哪个函数、带什么参数"的结构化 JSON；真正执行的是你的应用代码 |
| 2 | 五步循环 | 用户消息 → 模型收到消息 + 工具定义 → 模型返回 tool call → 代码执行 → 结果回传给模型生成最终回答 |
| 3 | 工具定义 = JSON Schema 契约 | `name`、`description`、`parameters`（类型、`enum`、`required`）；description 本身就是"工具选择的 prompt" |
| 4 | 供应商差异 | OpenAI 用 `tools[].function.parameters`、返回 `tool_calls`；Anthropic 用 `input_schema`、返回 `tool_use` 内容块、结果放在 user 消息的 `tool_result` 里；Gemini 用 `function_declarations` |
| 5 | tool choice | auto（模型自己决定）、required / any（必须调用至少一个）、指定函数（强制调用某个工具，用于路由） |
| 6 | 并行调用 | 一轮输出多个 tool call，把多次往返合并成一次；每个结果要用 call id 对应回去 |
| 7 | Structured outputs vs function calling | 前者的 JSON 是最终产物（抽取数据），后者的 JSON 是中间步骤（请求执行动作） |
| 8 | 五条安全规则 | 不直接执行模型生成的 SQL；函数白名单；校验参数；清洗工具结果；限制调用次数 |
| 9 | 结构化错误 | 失败时返回 `{"error": true, "message": ..., "code": ...}` 这样的工具结果而不是抛异常，模型能据此自我修正 |
| 10 | MCP | 把工具做成可被任何兼容客户端发现和调用的服务；工具跨多个宿主共享时，从内联 function calling 升级到 MCP |

### 核心技能（能动手做到）

- [ ] 写出工具注册表：一份给模型看的 JSON Schema 定义 + 一个真正执行的 Python 函数
- [ ] 实现 `execute_tool_call`，保证任何参数错误、工具异常都转成结构化错误结果，而不是让循环崩溃
- [ ] 按 JSON Schema 校验参数（必填、未知字段、类型、enum），并知道 Python 中 `bool` 是 `int` 子类带来的坑
- [ ] 把"只跑一轮"的循环改造成真正的多步 agent loop：传入对话历史、带 `tool_call_id`、设置迭代上限
- [ ] 识别 `eval` / `exec` 类工具的风险（DoS、过滤绕过），说出进程/容器级隔离的必要性
- [ ] 用一组标注好的查询评估工具选择准确率，定位路由错误

---

## 二、基础自测（选择题）

**Q1.** 用户问"东京现在天气如何"，模型返回 `get_weather(city="Tokyo")`。关于这一步，说法正确的是：

- A. 模型在服务端调用了天气 API，并把结果写进了回复
- B. 模型只输出了"想调用什么函数、带什么参数"的结构化描述，由应用代码去执行函数并把结果回传
- C. 模型执行了函数，但需要应用代码来格式化结果
- D. 只有在 `tool_choice="required"` 时模型才会自己执行函数

**Q2.** 把一个 OpenAI 格式的工具定义迁移到 Anthropic Messages API 时，最常见的必改项是：

- A. 把 `description` 改名为 `summary`
- B. Anthropic 不支持 `enum`，需要删掉
- C. 把工具结果放在 `role: "tool"` 的消息里
- D. 参数 schema 字段从 `parameters` 改为 `input_schema`；工具结果以 `type: "tool_result"` 内容块放在 user 消息中返回

**Q3.** 上游路由已经判定"这个问题必须查实时数据"，你希望模型**至少调用一个工具**而不是凭记忆回答。按讲义的表格，OpenAI 与 Anthropic 分别应设置：

- A. OpenAI `tool_choice="required"`；Anthropic `tool_choice={"type": "any"}`
- B. 两者都设 `tool_choice="auto"`
- C. OpenAI `tool_choice="none"`；Anthropic `tool_choice={"type": "auto"}`
- D. 两者都需要在 system prompt 里写"必须调用工具"，没有 API 参数可用

**Q4.** 下列场景中，更适合用 structured outputs 而不是 function calling 的是：

- A. 查询订单数据库里某个订单的状态
- B. 给用户发送一封确认邮件
- C. 从一段商品描述中抽取 `{name, price, in_stock}`，抽取结果就是最终产物
- D. 根据用户意图在 5 个内部 API 中选一个去调用

**Q5.** 工具执行失败（例如城市名拼错）时，讲义推荐的做法是：

- A. 返回结构化的错误结果，如 `{"error": true, "message": "City 'Toky' not found. Did you mean 'Tokyo'?", "code": "CITY_NOT_FOUND"}`，让模型据此调整参数重试
- B. 直接抛出异常，中止整个对话
- C. 返回空字符串，让模型自己判断
- D. 返回 "something went wrong"，避免泄露内部信息

**Q6.** 实际运行本节代码，`"Search for MCP protocol"` 这条查询调用了 `web_search`，但结果是 `{"query": "mcp protocol", "results": [], "total": 0}`，尽管 `SEARCH_DB` 里明明有 `"MCP protocol"` 这一条。原因是：

- A. `simulate_model_decision` 选错了工具
- B. `max_results` 默认值是 0
- C. `web_search` 只支持完全相等的匹配
- D. `web_search` 把查询转成了小写，却没有把 `SEARCH_DB` 的键转成小写，`"MCP protocol"` 与 `"mcp protocol"` 互不为子串

**Q7.** `validate_tool_arguments("calculator", {"expression": "1+1", "precision": True})` 的返回值是：

- A. `["Argument 'precision': expected integer, got bool"]`
- B. `[]`，因为 Python 中 `bool` 是 `int` 的子类，`isinstance(True, int)` 为真
- C. `["Unknown argument: precision"]`
- D. 抛出 `TypeError`

**Q8.** 运行 `"What's the weather in tokyo and london?"` 时，代码输出 `Tool calls made: 2`。关于这次"并行调用"，说法正确的是：

- A. 两个调用分别在两轮对话中完成，共 2 次模型往返
- B. 代码用线程并发执行了两个 `get_weather`
- C. 模型（这里是模拟函数）在**一轮**里返回了两个 tool call，代码按顺序执行后一起回传；真正的收益是减少模型往返次数，并发执行需要另外实现
- D. 并行调用只有 OpenAI 支持，所以这只是 OpenAI 格式的演示

---

## 三、动手 / 代码题

**Q9.** 阅读 `execute_tool_call`：

```python
def execute_tool_call(tool_call):
    name = tool_call["name"]
    args = tool_call["arguments"]

    if name not in TOOL_REGISTRY:
        return {"tool": name, "result": {"error": True, "message": f"Unknown tool: {name}", "code": "UNKNOWN_TOOL"}, "execution_time_ms": 0}

    tool = TOOL_REGISTRY[name]
    func = tool["function"]
    start = time.time()

    try:
        result = func(**args)
    except TypeError as e:
        result = {"error": True, "message": f"Invalid arguments: {e}"}

    elapsed_ms = round((time.time() - start) * 1000, 2)
    return {"tool": name, "result": result, "execution_time_ms": elapsed_ms}
```

1. 模型生成 `{"name": "get_weather", "arguments": {"city": 123}}` 时会发生什么？`{"city": "Tokyo", "units": "kelvin"}` 呢？
2. 代码里已经有 `validate_tool_arguments`，它在哪里被调用了？
3. 写一个 `safe_execute_tool_call`：先校验参数，再执行；任何异常都转成结构化错误；计时改用更合适的时钟。

**Q10.** `simulate_model_decision` 是用关键词规则模拟"模型选工具"。以下是实际运行结果：

| 用户输入 | 模拟出的 tool call |
|---------|------------------|
| `Weather in Paris` | `get_weather(city="Tokyo")` |
| `Find the weather API docs` | `get_weather(city="Tokyo")` |
| `What is the capital of France?` | `calculator(expression="0")` |
| `What's 2+2?` | （不调用工具） |
| `Is it going to rain in Sydney?` | （不调用工具） |
| `Run 2+2 in python` | `run_code(code="result = 'Hello from the sandbox!'")` |

1. 逐条说明出错的原因（对应到代码中的哪条规则）。
2. 其中哪一条在真实系统中危害最大？为什么？
3. 讲义练习 4 要求"30 条查询测工具选择准确率"。请设计这个评测：数据怎么标、指标怎么算、除了"选对工具"还应该检查什么？

**Q11.** 关于两个"会执行代码"的工具：

```python
def calculator(expression, precision=2):
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return {"error": True, "message": f"Invalid characters in expression: {expression}"}
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        ...
```

```python
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)): ...
        if isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"): ...
        if isinstance(node, ast.Name) and node.id in unsafe_names: ...
    exec(code, {"__builtins__": {...受限内置函数...}}, local_vars)
```

1. 字符白名单能挡住 `__import__('os')`，那 `calculator("9**9**8")` 会怎样？
2. `run_code("result = '{0.__class__.__mro__}'.format(())")` 能通过 AST 检查吗？结果是什么？说明了什么？
3. `run_code("while True: pass")` 会怎样？
4. 用 `ast` 写一个只允许数字和 `+ - * /`（含一元正负号）的安全计算器，并限制结果大小。

**Q12.** 阅读 `run_function_calling_loop`：

```python
    for iteration in range(max_iterations):
        tool_calls = simulate_model_decision(user_message, tool_definitions, conversation)
        if not tool_calls:
            break
        results = [execute_tool_call(call) for call in tool_calls]   # 原代码为显式 for 循环
        conversation.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        for result in results:
            conversation.append({"role": "tool", "content": json.dumps(result["result"]), "tool_name": result["tool"]})
        all_tool_results.extend(results)
        break
```

1. `max_iterations=5` 实际起作用吗？`iterations` 最多可能是几？
2. 与 OpenAI / Anthropic 的真实消息格式相比，这里的 `tool` 消息缺了什么关键字段？在并行调用时会造成什么问题？
3. 讲义练习 3："读取 config 文件得知模型名，再搜索该模型的定价"。请改写成真正的多步循环：决策函数接收**对话历史**，每个调用带 id，达到上限时报告原因。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一次 function calling 的交互流程，并说明模型、应用代码、工具三者各自负责什么。

**Q14.**（原理深挖）模型是如何"学会"调用工具的？tool 定义是怎么进入模型的？为什么 description 写得好坏会显著影响工具选择？工具数量多了会怎样？

**Q15.**（工程实践）你要上线一个可以查询订单数据库、发退款邮件的客服 agent。请列出你会加的安全措施。

**Q16.**（场景设计）一个查询需要依次调用 5–10 个工具，端到端延迟太高。你会从哪些方面优化？

**Q17.**（追问型）什么时候应该把内联的 function calling 升级为 MCP server？MCP 解决了什么问题，又带来了哪些新的风险？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The model never executes anything. It only decides what to call and with what arguments. Your code is the executor." 模型输出的只是结构化的调用意图；A、C 都错把执行归给了模型；D 混淆了 tool choice 的含义——`required` 只是强制模型**输出**工具调用，执行仍由应用负责。

### Q2 — 答案：D

讲义："Anthropic uses `input_schema` for tool parameter definitions, while OpenAI uses `parameters`." 并且 "The tool result goes in a user message with `type: "tool_result"`." A、B 都是虚构的差异；C 是 OpenAI 的做法（`role: "tool"` + `tool_call_id`）。outputs 里的 skill 文件也把 `input_schema` 列为"常见迁移 bug"。

### Q3 — 答案：A

讲义的供应商对比表："Forced Calling" 一列中，OpenAI 为 `tool_choice="required"`，Anthropic 为 `tool_choice={"type":"any"}`。B 的 auto 允许模型不调工具直接作答；C 中 `"none"` 是禁止调用；D 错，两家都有 API 级别的控制。如果要强制调用**某一个**工具，则用指定函数的写法（讲义："Use this for routing"）。

### Q4 — 答案：C

讲义："Structured outputs: force the model to produce data in a specific shape. The output is the final product." 抽取 `{name, price, in_stock}` 正是讲义举的例子。A、B、D 都需要与外部系统交互（查库、发邮件、调用 API），属于 function calling。

### Q5 — 答案：A

讲义："Return errors as structured tool results, not exceptions ... Models are good at self-correcting from structured error messages. They are bad at recovering from empty responses or generic 'something went wrong' errors." B 会中断对话；C、D 让模型无从修正。本节 `get_weather` 对 `"Tok"` 返回 `"suggestions": ["tokyo"]`，就是这种设计（但对 `"Mars"` 建议列表为空）。注意结构化错误中不要带内部堆栈、密钥等敏感信息（安全规则 4）。

### Q6 — 答案：D

`web_search` 中 `key = query.lower().strip()` 得到 `"mcp protocol"`，再判断 `db_key in key or key in db_key`。`SEARCH_DB` 的键 `"MCP protocol"` 含大写字母，与小写的 `key` 互不为子串，所以返回空。同样的问题也会让 `"weather API"` 永远无法通过完整短语匹配（`"weather"` 这样的短查询能命中，是因为 `"weather" in "weather API"`）。A 错：工具选对了（`simulate_model_decision` 返回了 `web_search`）；B、C 与代码不符。修复：比较前把 `db_key` 也 `.lower()`。这个 bug 的教训：**demo 打印了 Tool: web_search，看起来"成功了"，但结果为空**——评估工具调用时不能只看"有没有调用"。

### Q7 — 答案：B

`type_checks["integer"]` 是 `int`，而 `bool` 是 `int` 的子类，所以 `True` 通过检查，返回 `[]`（已实际运行）。反过来，`precision=2.0` 会被判为错误（`expected integer, got float`），尽管很多 JSON 库会把 `2.0` 当作合法的整数值。严格的实现应先排除 `bool`：`isinstance(v, int) and not isinstance(v, bool)`；生产中可以直接用 `jsonschema` 库或 Pydantic 校验。

### Q8 — 答案：C

`simulate_model_decision` 在**一次**调用中返回了两个 `get_weather`，循环随后**顺序**执行它们（普通 `for` 循环），把两个结果一并追加进对话。讲义："Your code executes both (ideally concurrently)... This cuts round trips from 2 to 1." A 错，只有一轮；B 错，代码里没有线程或 asyncio；D 错，讲义的表格中 OpenAI、Anthropic、Gemini 都支持并行调用。

### Q9 — 参考答案

1. 实际运行结果：
   - `{"city": 123}`：`get_weather` 内部执行 `city.lower()`，抛出 `AttributeError: 'int' object has no attribute 'lower'`。`execute_tool_call` 只捕获 `TypeError`，于是异常向上传播，**整个调用循环崩溃**。
   - `{"city": "Tokyo", "units": "kelvin"}`：不会报错，`get_weather` 只在 `units == "fahrenheit"` 时转换，否则默认返回摄氏度。模型以为拿到了开尔文温度，实际是 18（摄氏），属于"静默错误"。
   - 另外，`{"cty": "Tokyo"}` 这种拼错的参数名会触发 `TypeError`，被转成 `Invalid arguments: ... unexpected keyword argument 'cty'. Did you mean 'city'?`——这一类倒是处理得不错。
2. 没有被调用。`validate_tool_arguments` 只在 `run_demo` 的"Argument Validation"一节单独演示，真正的执行路径 `run_function_calling_loop → execute_tool_call` 完全绕过了它。讲义安全规则 3 "Validate arguments" 在执行路径上并未落实。
3. 参考实现（已运行验证：`city=123` 与 `units="kelvin"` 都返回 `INVALID_ARGUMENTS`，未知工具返回错误，正常调用不受影响）：

```python
def safe_execute_tool_call(tool_call):
    name = tool_call.get("name")
    args = tool_call.get("arguments", {})
    errors = validate_tool_arguments(name, args)          # 未知工具也会在这里报错
    if errors:
        return {"tool": name,
                "result": {"error": True, "code": "INVALID_ARGUMENTS", "message": "; ".join(errors)},
                "execution_time_ms": 0}
    func = TOOL_REGISTRY[name]["function"]
    start = time.perf_counter()                           # 单调时钟，适合测耗时
    try:
        result = func(**args)
    except Exception as e:                                # 工具内部任何异常都不能打断 agent 循环
        result = {"error": True, "code": "TOOL_EXCEPTION", "message": f"{type(e).__name__}: {e}"}
    return {"tool": name, "result": result,
            "execution_time_ms": round((time.perf_counter() - start) * 1000, 2)}
```

   要点：`time.time()` 是墙钟时间，可能被系统校时调整，测耗时应使用 `time.perf_counter()`；捕获宽泛异常后要**记录日志**，但返回给模型的 message 应去掉堆栈和内部路径。

### Q10 — 参考答案

1. 逐条分析：
   - `Weather in Paris → Tokyo`：命中 "weather" 分支，`WEATHER_DB` 里没有 paris，最后执行 `if not cities: cities = ["tokyo"]`，用一个**默认城市**顶替。
   - `Find the weather API docs → get_weather`：规则按顺序匹配，"weather" 分支排在 "find/search" 分支之前，先到先得。
   - `What is the capital of France? → calculator("0")`：计算分支的触发词包含 `"what is"`，找不到表达式时兜底返回 `calculator("0")`。
   - `What's 2+2? → 不调用`：触发词是 `"what is"`，而输入是 `"what's"`；其他分支也不匹配，于是返回空列表，相当于让模型"直接回答"。
   - `Is it going to rain in Sydney? → 不调用`：天气分支只认 `weather / temperature / forecast`，不认 "rain"。
   - `Run 2+2 in python → 固定代码`：`run_code` 分支总是执行写死的 `result = 'Hello from the sandbox!'`，完全忽略用户要跑的代码。
2. 危害最大的是 **`Weather in Paris → Tokyo`**：它不是"不知道"，而是**编造了参数**并返回了一个看似真实的答案（东京的 18°C），用户无从察觉。真实系统中，参数无法从用户输入得到时应该追问或返回错误，而不是填默认值。讲义开头批评的"hallucination dressed in a disclaimer"在这里换了个形式出现在工具参数上。
3. 评测设计要点：
   - **数据**：30+ 条查询，每条标注期望的工具名（或"不应调用工具"）和期望参数；覆盖每个工具的正例、近义说法（rain / 降雨）、多意图（"查天气并换算华氏度"）、负例（闲聊、常识问题）、易混淆对（"find weather API docs" 应该是 `web_search`）。
   - **指标**：工具选择准确率；"该调不调 / 不该调却调"分别统计（类似 recall / precision）；参数准确率（精确匹配或按字段比对）；混淆矩阵，找出最常互相混淆的工具对。
   - **还要检查**：参数是否来自用户输入而非编造；调用次数是否在预算内；多工具查询是否全部覆盖。
   - 对真实 LLM 要多次采样看稳定性，并在修改 description 后回归测试（加分点：Berkeley Function Calling Leaderboard 就是这类评测的公开版本，讲义 Further Reading 中列出）。

### Q11 — 参考答案

1. `9**9**8` 只含数字和 `*`，能通过字符白名单。`**` 是右结合的，等于 `9 ** 43,046,721`，Python 会老老实实算这个有约 4,100 万位的大整数。实际运行中 8 秒超时仍未返回——这就是**拒绝服务（DoS）**：单个工具调用就能把 worker 卡死。（`9**9**5` 能很快算完，但转 float 时报 `int too large to convert to float`。）
2. 能通过。AST 检查只看 `ast.Attribute` 节点，而 `__class__.__mro__` 写在**字符串里**，由 `str.format` 在运行时解析。实际返回 `"(<class 'tuple'>, <class 'object'>)"`。格式化字符串只能读取属性、不能调用函数，所以这里只是信息泄露，但它说明了讲义的结论："Any in-process guard shares the interpreter with the code it runs... treat this as a teaching filter, not a real boundary."
3. 死循环。`exec` 没有任何超时，整个进程会被永久占住（未实际运行此例，按代码推断）。同理 `result = [0] * 10**9` 可以耗尽内存。
4. 参考实现（已运行验证：`(10 + 5) * 3 / 2 → 22.5`、`(100 + 250) * 0.15 → 52.5`、`-3 + 2 → -1`；`9**9**8`、`()` 被拒绝；`1/0` 抛 ZeroDivisionError 由外层转为错误结果；连乘 61 个 2 时报 "Result too large"）：

```python
import ast, operator

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}

def safe_eval(expr, max_abs=1e15):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            val = OPS[type(node.op)](ev(node.left), ev(node.right))
        elif isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            val = OPS[type(node.op)](ev(node.operand))
        else:
            raise ValueError(f"Unsupported syntax: {type(node).__name__}")
        if abs(val) > max_abs:                 # 每一步都检查，防止中间结果爆炸
            raise ValueError("Result too large")
        return val
    return ev(ast.parse(expr, mode="eval"))
```

   核心思路：**白名单语法节点**而不是黑名单字符；不支持 `**`（或对指数设上限）；每一步都限制数值范围。对 `run_code` 这类必须执行任意代码的工具，进程内的过滤永远不够，必须放到独立进程/容器（讲义：subprocess with dropped privileges、gVisor、Firecracker 或托管 code runner），并设置 CPU 时间、内存、网络和文件系统限制。

### Q12 — 参考答案

1. 不起作用。循环体末尾无条件 `break`，所以最多执行一轮：有工具调用时 `iterations` 为 1，没有时为 0。`simulate_model_decision` 每次只看 `user_message`，根本不读 `conversation`，即使去掉 `break` 也会在每一轮返回相同的调用，直到 5 次上限——这正是讲义安全规则 5 所说的"模型在循环里反复调用工具"。另外，若传入 `max_iterations=0`，`for` 一次都不执行，最后的 `tool_calls` 未定义，会抛 `NameError`。
2. 缺少 **`tool_call_id`**。OpenAI 要求每条 `role: "tool"` 消息带上对应调用的 `tool_call_id`，Anthropic 要求 `tool_result` 带 `tool_use_id`（讲义 "Use It" 部分）。这里只记录了 `tool_name`：并行调用两个 `get_weather` 时，两条结果的 `tool_name` 相同，模型无法分辨哪个结果对应东京、哪个对应伦敦。
3. 参考实现（已用一个玩具决策函数运行验证：先 `read_file` 读出 `gpt-4o`，再 `web_search("gpt-4o pricing")`，2 轮后正常结束；一个永远要调工具的决策函数在 `max_iterations=3` 时以 `max_iterations` 原因停止）：

```python
import itertools, json
_ids = itertools.count(1)

def run_agent_loop(user_message, decide, max_iterations=10):
    conversation = [{"role": "user", "content": user_message}]
    tools = [t["definition"] for t in TOOL_REGISTRY.values()]
    for step in range(1, max_iterations + 1):
        calls = decide(conversation, tools)               # 决策函数看到完整历史
        if not calls:
            return {"conversation": conversation, "iterations": step - 1, "stopped": "final_answer"}
        for c in calls:
            c["id"] = f"call_{next(_ids)}"
        conversation.append({"role": "assistant", "content": None, "tool_calls": calls})
        for c in calls:
            out = execute_tool_call(c)                    # 建议换成 Q9 的 safe_execute_tool_call
            conversation.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": json.dumps(out["result"])})
    return {"conversation": conversation, "iterations": max_iterations, "stopped": "max_iterations"}
```

   注意：本节 `SEARCH_DB` 里没有 "gpt-4o pricing"，所以第二步返回空结果——在真实系统中，决策函数应读到 `total: 0` 并决定改写查询或如实告知。

### Q13 — 参考回答要点

- **流程**：① 用户提问；② 应用把对话 + 工具定义（JSON Schema）一起发给模型；③ 模型返回 tool call（函数名 + JSON 参数），而不是文本；④ 应用校验参数、执行函数、得到结果；⑤ 把结果作为 tool 消息（带 call id）追加到对话，再次调用模型；模型可能继续调用工具，也可能给出最终回答。
- **分工**：模型负责"决定调什么、填什么参数、怎么解读结果"；应用代码负责"白名单、校验、执行、错误处理、限流、结果清洗"；工具负责具体的外部能力（API、数据库、文件）。
- **加分点**：tool call 的参数是模型生成的**不可信输入**，要像处理用户输入一样校验；多轮工具调用就是 ReAct 式的 agent loop（讲义 Key Terms）。
- 常见误区：以为"模型调用了 API"。

### Q14 — 参考回答要点

- **怎么学会的**：前沿模型在训练中专门学习了"看到工具定义 → 输出符合 schema 的调用"这种格式（讲义 Further Reading 中的 Toolformer、Gorilla 是这一方向的研究）；开源模型的 fine-tune 常用 Hermes 等格式（讲义供应商表）。
- **定义怎么进入模型**：API 层把 tools 列表序列化后注入到模型上下文（通常在 system 部分），所以工具定义会**占用 token**，也会影响模型的注意力分配。
- **description 的作用**：讲义："The description is a prompt for tool selection." 写清楚"做什么、什么时候用、返回什么"，用 `enum` 约束取值，给出示例格式（如 `'Tokyo' or 'San Francisco'`）。
- **工具多了会怎样**：选择准确率下降、token 成本上升。outputs 中的 skill 文件给出经验值：5–10 个工具表现良好，20+ 个开始下降，50+ 个时预计 10–15% 的错误选择。对策：按场景分组、先路由再暴露子集、合并相似工具。
- 加分点：讲义规则 2——即使内部有 50 个函数，也只暴露用户需要的 5 个；不要做"按名字执行任意函数"的万能工具。

### Q15 — 参考回答要点

- **最小权限与白名单**：只暴露 `get_order_status(order_id)`、`request_refund(order_id, reason)` 这样的窄工具，不暴露通用 SQL；数据库账号只读或按表授权。
- **参数化与校验**：订单 ID 格式、金额范围、枚举值用 schema + 服务端二次校验；绝不拼接 SQL（讲义规则 1、3）。
- **权限绑定用户身份**：工具执行时用**当前登录用户**的身份做鉴权，模型无法通过参数查别人的订单。
- **高风险操作需确认**：退款、发邮件等有副作用的操作要人工确认或二次确认；设金额阈值。
- **结果清洗**：返回给模型前去掉 PII、内部字段、错误堆栈（规则 4）；同时把工具结果当作**不可信数据**，防范其中夹带的指令（讲义 Key Terms 中的 tool poisoning）。
- **限流与预算**：单会话工具调用上限（讲义：10–20 次），单工具频率限制，循环检测。
- **审计**：记录每次调用的参数、结果、耗时、用户 ID，便于追溯。
- 常见误区：只在 prompt 里写"不要删除数据"，而没有在代码与权限层面兜底。

### Q16 — 参考回答要点

- **并行调用**：互不依赖的工具在一轮里一起请求、并发执行。讲义："For agents with 5-10 tool calls per query, parallel calling reduces latency by 60-80%."
- **减少往返**：把常一起用的步骤合并成一个更高层的工具；能用确定性代码串起来的步骤不必每步都问模型。
- **缓存**：相同工具 + 相同参数在短时间内复用结果（讲义练习 5，用 `(tool_name, frozenset(args.items()))` 做键，注意嵌套参数不可哈希的问题）。
- **更快的模型做路由**：用小模型决定调什么工具，大模型只做最终整合。
- **工具本身提速**：超时、重试策略、连接池；对慢工具设置预算并提前返回部分结果。
- **流式输出**：最终回答边生成边返回，降低用户感知延迟。
- 加分点：给每次工具调用打点（耗时、是否命中缓存），先测量再优化。

### Q17 — 参考回答要点

- **何时升级**：同一组工具要被多个宿主（IDE、聊天客户端、自建 agent）复用时；讲义 Related："when a tool is shared across hosts, graduate from inline function-calling to an MCP server."
- **解决的问题**：工具定义和实现只写一次，任何兼容客户端都能发现（`list_tools`）和调用（`call_tool`）；讲义的比喻："MCP is to function calling what HTTP is to networking."
- **新风险**：引入第三方 MCP server 等于引入了你不控制的代码和工具描述——工具描述本身可能被投毒（tool poisoning），工具结果可能夹带注入指令；还涉及认证授权、凭据管理、版本漂移等问题（阶段 13 的 MCP 安全课程专门讨论）。
- **不变的原则**：无论内联还是 MCP，参数校验、最小权限、结果清洗、调用预算仍然是应用方的责任。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../03-structured-outputs/docs/zh.md)：讲义列为先修，function calling 复用同一套 JSON Schema 机制。
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)：工具 description 本质上就是 prompt。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../../05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding/docs/zh.md)：模型如何被约束输出合法 JSON。

### 本节被哪些后续内容用到
- [阶段 11 · 14 Model Context Protocol (MCP)](../../14-model-context-protocol/docs/zh.md)：讲义指明的下一步——把工具做成协议化服务。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../12-guardrails/docs/zh.md)：工具调用的输入/输出护栏。
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)、[阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)、[阶段 13 · 05 工具 Schema 设计](../../../13-tools-and-protocols/05-tool-schema-design/docs/zh.md)：各家 API 细节、并行与流式、schema 设计。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../../13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/zh.md)：tool poisoning 的深入讨论。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)、[阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：从单次工具调用走向完整的 agent 循环。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../../19-capstone-projects/21-tool-registry-schema-validation/docs/zh.md)、[阶段 19 · 23 函数调用分派器](../../../19-capstone-projects/23-function-call-dispatcher/docs/zh.md)：综合项目中实现生产级注册表与分派器。

### 延伸关键词
`tool_choice` · `parallel_tool_calls` · `tool_call_id / tool_use_id` · `input_schema` · `JSON Schema` · `jsonschema / Pydantic` · `ReAct` · `tool poisoning` · `prompt injection` · `least privilege` · `sandbox (gVisor / Firecracker)` · `Berkeley Function Calling Leaderboard` · `MCP`
