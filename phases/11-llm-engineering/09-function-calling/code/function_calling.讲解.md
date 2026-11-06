# 代码讲解 · function_calling.py

> **所属小节**：阶段 11 · LLM 工程 · 第 09 节 Function Calling 与工具使用 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python function_calling.py`（无参数）；测试：`python -m unittest discover -s tests -v` ｜ **依赖**：仅标准库（`ast`、`json`、`math`、`re`、`time`；测试用 `unittest`、`pathlib`），无需网络、无需 API key
>
> 同目录下的 `main.ts` 是同一套逻辑的 TypeScript 版本（类型化的注册表、校验器、分派器），本文不单独讲解。

---

## 1. 这份代码在考察什么

这份代码不调用任何真实的 LLM，而是用纯 Python 把 function calling 的"应用侧"完整搭出来：

1. **工具注册表**：每个工具 = 一份给模型看的 JSON Schema 定义 + 一个真正执行的 Python 函数。
2. **五个工具**：计算器、天气查询、网页搜索（模拟）、文件读取（内存文件系统）、代码执行（带 AST 过滤）。
3. **"模型决策"的替身**：`simulate_model_decision` 用关键词规则模拟模型输出 tool call，包括一次返回多个调用（并行调用）。
4. **执行与回传**：`execute_tool_call` 按名字分派、计时、把异常转成结构化错误；`run_function_calling_loop` 把调用和结果写进对话。
5. **参数校验**：按 schema 检查必填、未知字段、类型、enum。
6. **安全护栏**：文件路径限制、计算器字符白名单、代码执行工具的静态分析过滤。

> 一句话：**模型只负责"说要调什么"，这份代码演示的是"应用如何把它变成真实执行"**。它同时也是一份很好的反面教材：校验器写了却没接入执行路径、路由规则会编造参数、搜索有大小写 bug、计算器能被超大指数拖垮——这些都是生产中真实会遇到的问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOOL_REGISTRY` / `register_tool` | 全局字典 + 函数 | `name → {definition, function}` | 工具白名单与 schema 契约 |
| `calculator` | 工具 | 字符白名单 + `eval`（空 builtins） | 受限求值 |
| `WEATHER_DB` / `get_weather` | 数据 + 工具 | 查表返回天气，缺城市时给 suggestions | 结构化错误 |
| `SEARCH_DB` / `web_search` | 数据 + 工具 | 子串匹配返回搜索结果 | 模拟检索 |
| `FILE_SYSTEM` / `read_file` | 数据 + 工具 | 内存文件系统，拦截路径穿越 | 受限文件访问 |
| `run_code` | 工具 | AST 静态检查 + 受限 `exec` | 代码执行护栏 |
| `register_all_tools` | 函数 | 注册上述 5 个工具及其 schema | 工具定义 |
| `simulate_model_decision` | 函数 | 关键词规则模拟模型选工具 | "模型决策"替身 |
| `execute_tool_call` | 函数 | 按名字分派、计时、捕获 TypeError | 执行工具 |
| `validate_tool_arguments` | 函数 | 按 schema 校验必填/未知/类型/enum | 参数校验 |
| `run_function_calling_loop` | 函数 | 决策 → 执行 → 写进对话（只跑一轮） | function calling 循环 |
| `run_demo` | 函数 | Step by step 打印 8 个环节 | 演示 |

数据流：`register_all_tools` 填好注册表 → `simulate_model_decision` 产出 tool call 列表 → `execute_tool_call` 逐个执行 → 结果以 `assistant`(tool_calls) + `tool`(content) 两类消息写回 `conversation`。

---

## 3. 逐段精讲

### 3.1 工具注册表

```python
TOOL_REGISTRY = {}

def register_tool(name, description, parameters, function):
    TOOL_REGISTRY[name] = {
        "definition": {
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        },
        "function": function,
    }
```

- 每个工具存两份东西：`definition` 是**给模型看**的 JSON Schema（OpenAI 的 `tools[].function` 形状），`function` 是**给代码执行**的 Python 可调用对象。这正是讲义反复强调的分工——模型读 schema 决定调什么，代码用函数真正执行。
- 注册表天然是一个**白名单**：`execute_tool_call` 只会调用注册表里有的名字，对应讲义安全规则 2"Allowlist functions"。
- `description` 会随 `definition` 一起进入模型上下文，讲义："The description is a prompt for tool selection."

### 3.2 `calculator`：字符白名单 + 空 builtins 的 eval

```python
def calculator(expression, precision=2):
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return {"error": True, "message": f"Invalid characters in expression: {expression}"}
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return {"result": round(float(result), precision), "expression": expression}
    except Exception as e:
        return {"error": True, "message": str(e)}
```

- 先做字符白名单：只允许数字、四则运算符、小数点、括号、空格。`__import__('os')` 这类含字母和引号的串会被直接挡掉。
- `eval(expr, {"__builtins__": {}}, {"math": math})`：把全局内置清空，只留 `math`。
- ⚠️ **白名单里有 `*`，于是 `**` 合法**：`calculator("9**9**8")` 全是数字和 `*`，能通过检查，但 `**` 右结合、指数极大，Python 会去计算一个有数千万位的大整数，单次调用就能把 worker 卡死（DoS）。实际测试中它会长时间无法返回；`9**9**5` 能算完但转 `float` 时报 "int too large to convert to float"。
- ⚠️ `round(float(result), ...)` 要求结果能转成浮点，`calculator("()")`（空元组）会报 "float() argument must be a string or a real number"。
- 对比：安全的做法是用 `ast` 白名单**语法节点**、禁用 `**` 或限制指数、限制数值范围，而不是过滤字符（见测验 Q11）。

### 3.3 `get_weather`：查表 + 结构化错误

```python
def get_weather(city, units="celsius"):
    key = city.lower().strip()
    if key not in WEATHER_DB:
        suggestions = [c for c in WEATHER_DB if c.startswith(key[:3])]
        return {"error": True, "message": f"City '{city}' not found.", "suggestions": suggestions, "code": "CITY_NOT_FOUND"}
    data = WEATHER_DB[key].copy()
    if units == "fahrenheit":
        data["temp_f"] = round(data["temp_c"] * 9 / 5 + 32, 1)
        del data["temp_c"]
    data["city"] = city
    return data
```

- 返回**结构化错误**（带 `message`、`suggestions`、`code`），模型可据此改参数重试——讲义："Models are good at self-correcting from structured error messages."
- `.copy()` 很关键：不加会直接修改 `WEATHER_DB` 里的字典，华氏度转换会污染全局数据（下次查同一城市就错了）。
- ⚠️ `suggestions` 用 `key[:3]` 前缀匹配：`"Tok"` 能给出 `["tokyo"]`，但 `"Mars"` 的前缀匹配不到任何城市，返回空列表——错误提示对真正的拼写错误才有用。
- ⚠️ `units` 只认 `"fahrenheit"`，传 `"kelvin"` 不会报错，默默返回摄氏度，属于"静默错误"（见测验 Q9）。

### 3.4 `web_search` 与 `read_file`

```python
def web_search(query, max_results=3):
    key = query.lower().strip()
    for db_key, results in SEARCH_DB.items():
        if db_key in key or key in db_key:
            return {"query": query, "results": results[:max_results], "total": len(results)}
    return {"query": query, "results": [], "total": 0}
```

- 用"互为子串"做模糊匹配。⚠️ **大小写 bug**：`key` 被转成小写，但 `SEARCH_DB` 的键 `"MCP protocol"`、`"weather API"` 含大写字母，与小写 `key` 互不为子串。所以 `"MCP protocol"` 查询返回空（见测验 Q6）；修复只需比较前对 `db_key` 也 `.lower()`。
- ⚠️ `total` 返回的是**匹配到的那一条 DB 记录里的结果总数**，不是全局命中数，语义有点含糊。

```python
def read_file(path):
    if ".." in path or path.startswith("/"):
        return {"error": True, "message": "Path traversal not allowed.", "code": "FORBIDDEN"}
    if path not in FILE_SYSTEM:
        return {"error": True, "message": f"File '{path}' not found.", "available_files": list(FILE_SYSTEM.keys()), "code": "NOT_FOUND"}
    content = FILE_SYSTEM[path]
    return {"path": path, "content": content, "size_bytes": len(content), "lines": content.count("\n") + 1}
```

- 两道防线：含 `..` 或以 `/` 开头的路径直接拒绝（拦路径穿越），其余必须精确命中内存文件系统的键。
- 因为用的是内存字典而非真实磁盘，这里的"文件系统"本身就是一个白名单，相对安全。真实场景下 `".." in path` 这种字符串检查并不够（可能被 URL 编码、符号链接绕过），应当用 `os.path.realpath` 规范化后判断是否在允许目录内。
- ⚠️ `read_file("./README.md")` 会因为不等于键 `"README.md"` 而返回 NOT_FOUND——精确匹配对合法路径也可能"误伤"。

### 3.5 `run_code`：AST 静态检查 + 受限 exec

```python
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"error": True, "message": f"SyntaxError: {e}", "code": "SYNTAX_ERROR"}
    unsafe_names = {"exec", "eval", "compile", "__import__", "open", "globals", "locals", "vars", "getattr", "setattr", "delattr"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return {"error": True, "message": "Forbidden operation: import is not allowed", "code": "SECURITY_VIOLATION"}
        if isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            return {"error": True, "message": "Forbidden operation: dunder attribute access is not allowed", "code": "SECURITY_VIOLATION"}
        if isinstance(node, ast.Name) and node.id in unsafe_names:
            return {"error": True, "message": f"Forbidden operation: {node.id} is not allowed", "code": "SECURITY_VIOLATION"}
    # ... 受限 __builtins__ 下 exec(code, ...)，取 local_vars["result"]
```

- 这是比字符黑名单更进一步的做法：先把代码解析成**语法树**，再遍历节点，按**结构**拒绝三类风险——`import` 语句、以双下划线开头结尾的属性访问（阻断通过内置对象链回到真实解释器的那类手法）、以及危险的内置函数名。
- 执行时把 `__builtins__` 换成一份只含安全函数（`print`、`range`、`len`、`sum`、`math` 等）的白名单，并约定把输出写进 `result` 变量。
- ⚠️ 讲义和注册描述都明确说这是**教学用的过滤器，不是真正的隔离边界**。几个已验证的漏洞：
  1. **字符串里的属性链**：`str.format` 在运行时解析属性，`"{0.__class__.__mro__}".format(())` 这类写法不出现在 `ast.Attribute` 节点上，能通过检查并泄露类型信息——说明静态检查看不到运行时才拼出来的访问。
  2. **没有超时/资源限制**：`while True: pass` 会把进程永久占住；构造超大对象可耗尽内存。
  3. 任何进程内的过滤都与被执行代码共享同一个解释器，有经验的攻击者仍可能找到可达对象。
- 正确做法（讲义 Build It 末尾）：把不可信代码放到**独立进程或容器**里跑（降权子进程、gVisor、Firecracker 或托管 code runner），即使被突破也只是一次性沙箱，而不是你的服务本体。

### 3.6 `register_all_tools`：工具定义的样子

```python
    register_tool(
        "get_weather",
        "Get current weather for a city. Returns temperature, condition, humidity, and wind speed.",
        {"type": "object",
         "properties": {
             "city": {"type": "string", "description": "City name, e.g. 'Tokyo' or 'San Francisco'"},
             "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Temperature units, defaults to celsius"}},
         "required": ["city"]},
        get_weather,
    )
```

- 每个 schema 都给了类型、`enum`（约束取值，避免模型发明 "C"、"metric" 之类的字符串）、`description`（举例子）、`required`。这正是 outputs 中 skill 文件总结的"描述即 prompt、用 enum 约束、required 慎用"。
- 五个工具的 description 都写明了"返回什么"，不只是"做什么"——这对模型解读结果很重要。

### 3.7 `simulate_model_decision`：关键词规则替身

```python
    if any(word in msg for word in ["weather", "temperature", "forecast"]):
        cities = [city for city in WEATHER_DB if city in msg]
        if not cities:
            cities = ["tokyo"]                       # ⚠️ 兜底填默认城市
        return [{"name": "get_weather", "arguments": {"city": c.title()}} for c in cities]

    if any(word in msg for word in ["calculate", "compute", "math", "what is", "how much"]):
        for run in re.findall(r"[0-9.+\-*/()\s]{3,}", msg):
            expr = run.strip()
            if any(c.isdigit() for c in expr) and any(c in expr for c in "+-*/") and "error" not in calculator(expr):
                return [{"name": "calculator", "arguments": {"expression": expr}}]
        ...
        return [{"name": "calculator", "arguments": {"expression": "0"}}]   # ⚠️ 兜底
```

- 这是用关键词 if/elif 模拟"模型路由"，并不是真的调用 LLM。它的价值是让整条链路可以离线跑通。
- 代码版比讲义版多了一步：用正则 `[0-9.+\-*/()\s]{3,}` 抽取表达式片段，并用 `calculator(expr)` **先验证能否算通**再决定调用——这让 `"Calculate (100 + 250) * 0.15"` 能正确抽出 `"(100 + 250) * 0.15"`。
- ⚠️ 它的几个典型错误（实际运行验证，见测验 Q10）：
  - 多个天气分支会**编造默认城市**：`"Weather in Paris"` → `get_weather(city="Tokyo")`；
  - 规则按顺序匹配，`"Find the weather API docs"` 先命中 weather 分支而不是 search；
  - `"What is the capital of France?"` 命中 `"what is"` 触发词，兜底成 `calculator("0")`；
  - `run_code` 分支永远执行写死的 `result = 'Hello from the sandbox!'`，忽略用户真正想跑的代码。
- 最危险的是"编造参数"：它不是"不知道"，而是给出一个看似可信的错误答案。真实系统应在参数无法从输入得出时追问或报错。

### 3.8 `execute_tool_call`：分派、计时、异常

```python
def execute_tool_call(tool_call):
    name, args = tool_call["name"], tool_call["arguments"]
    if name not in TOOL_REGISTRY:
        return {"tool": name, "result": {"error": True, "message": f"Unknown tool: {name}", "code": "UNKNOWN_TOOL"}, "execution_time_ms": 0}
    func = TOOL_REGISTRY[name]["function"]
    start = time.time()
    try:
        result = func(**args)
    except TypeError as e:
        result = {"error": True, "message": f"Invalid arguments: {e}"}
    elapsed_ms = round((time.time() - start) * 1000, 2)
    return {"tool": name, "result": result, "execution_time_ms": elapsed_ms}
```

- 未知工具返回结构化错误（白名单在这里生效）。
- `func(**args)`：把参数字典展开成关键字参数。拼错的参数名（如 `cty`）会抛 `TypeError`，被转成友好的 "Invalid arguments: ... Did you mean 'city'?"。
- ⚠️ **只捕获 `TypeError`**：`get_weather(city=123)` 在函数内部执行 `city.lower()` 抛的是 `AttributeError`，不会被捕获，**整个循环崩溃**。而且这里**从不调用** `validate_tool_arguments`——校验器写了却没接到执行路径上，讲义安全规则 3 形同虚设（修复见测验 Q9）。
- ⚠️ `time.time()` 是墙钟时间，测耗时应用 `time.perf_counter()`。

### 3.9 `validate_tool_arguments`：参数校验

```python
    for required_field in schema.get("required", []):
        if required_field not in arguments:
            errors.append(f"Missing required argument: {required_field}")
    for arg_name, arg_value in arguments.items():
        if arg_name not in properties:
            errors.append(f"Unknown argument: {arg_name}"); continue
        expected_type = properties[arg_name].get("type")
        type_checks = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
        if expected_type in type_checks and not isinstance(arg_value, type_checks[expected_type]):
            errors.append(f"Argument '{arg_name}': expected {expected_type}, got {type(arg_value).__name__}")
        if "enum" in prop_schema and arg_value not in prop_schema["enum"]:
            errors.append(...)
```

- 检查四类问题：缺必填、未知字段、类型不符、不在 enum 中。
- ⚠️ **`bool` 是 `int` 的子类**：`precision=True` 会通过 `integer` 检查（`isinstance(True, int)` 为真）；而 `precision=2.0` 反而被判错（float 不是 int）。严格实现应 `isinstance(v, int) and not isinstance(v, bool)`。
- 它是正确方向的实现，但如 3.8 所说，没有接到执行路径上。生产中更常直接用 `jsonschema` 或 Pydantic。

### 3.10 `run_function_calling_loop`：只跑一轮的"循环"

```python
    for iteration in range(max_iterations):
        tool_calls = simulate_model_decision(user_message, tool_definitions, conversation)
        if not tool_calls:
            break
        results = [execute_tool_call(call) for call in tool_calls]
        conversation.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        for result in results:
            conversation.append({"role": "tool", "content": json.dumps(result["result"]), "tool_name": result["tool"]})
        all_tool_results.extend(results)
        break                                    # ⚠️ 无条件退出
    return {"conversation": conversation, "tool_results": all_tool_results,
            "iterations": iteration + 1 if tool_calls else 0}
```

- 把一轮的调用和结果按两类消息写进对话：`assistant` 消息带 `tool_calls`，每个结果一条 `tool` 消息。这对应讲义五步循环的第 4、5 步。
- ⚠️ **末尾无条件 `break`**，所以 `max_iterations` 从不生效，最多只跑一轮。而且 `simulate_model_decision` 只看 `user_message`、不读 `conversation`，即便去掉 `break` 也会每轮返回相同调用直到上限——这正是安全规则 5 要防的"模型在循环里反复调用工具"。
- ⚠️ `tool` 消息只记了 `tool_name`，**缺少 `tool_call_id`**。OpenAI 的 `role:"tool"` 要带 `tool_call_id`、Anthropic 的 `tool_result` 要带 `tool_use_id`；并行调用两个 `get_weather` 时，模型无法把结果对应回东京/伦敦。
- 真正的多步 agent loop 应让决策函数接收对话历史、每个调用带 id、达到上限时报告停止原因（见测验 Q12）。

### 3.11 `run_demo`：八个演示环节

`run_demo` 依次打印：注册的工具、参数校验、直接执行 8 个工具调用、完整循环跑 6 条查询、并行调用、三项安全检查。它是整份代码的"自测台"——既展示正常路径，也故意喂进越权路径（路径穿越、含危险调用的代码片段、`__import__` 表达式）看护栏是否拦住。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字典当工具注册表 | 天然是白名单，查找 O(1) | 真实系统还要带版本、权限、超时等元数据 |
| 定义与实现分开存 | 对应"模型看 schema / 代码执行函数" | 两者容易不同步，需要测试保证一致 |
| 关键词规则模拟模型 | 离线、可复现、零成本 | 会编造参数、顺序敏感、不读历史；真实靠 LLM |
| 计算器用字符白名单 + eval | 代码短 | `**` 导致 DoS；应改用 AST 白名单 + 数值/指数限制 |
| `run_code` 用 AST 过滤 + 受限 exec | 展示比黑名单更结构化的思路 | 进程内过滤不是边界；应放独立进程/容器并限资源 |
| 结构化错误而非抛异常 | 模型能自我修正 | 要记得过滤掉堆栈、密钥等敏感信息 |
| 校验器单独写 | 便于演示 | 没接到执行路径，等于没做校验——应在 `execute_tool_call` 里先校验 |
| 循环写死 `break` | 演示单轮足够 | 多步任务无法完成；需要真正的迭代 + 上限 |
| `tool` 消息只带 name | demo 够用 | 并行时无法对应结果；必须带 `tool_call_id` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 全局可变状态 | `TOOL_REGISTRY = {}` 后在函数里改它 | 模块级字典，被多个函数共享 |
| `**kwargs` 展开调用 | `func(**args)` | 把字典按键名展开成关键字参数 |
| `all` / `any` + 生成器 | `all(c in allowed for c in expression)`、`any(word in msg for word in [...])` | 全真 / 存在判断 |
| 集合字面量 | `allowed = set("0123...")`、`unsafe_names = {"exec", ...}` | 用 `set` 做 O(1) 成员判断 |
| `eval` 的三参数形式 | `eval(expr, {"__builtins__": {}}, {"math": math})` | 第二参是全局、第三参是局部命名空间 |
| `exec` + 受限命名空间 | `exec(code, {"__builtins__": {...}}, local_vars)` | 执行语句块，变量落在 `local_vars` |
| `ast.parse` / `ast.walk` | `tree = ast.parse(code)`；`for node in ast.walk(tree)` | 把源码解析成语法树并遍历每个节点 |
| `isinstance` 判节点类型 | `isinstance(node, (ast.Import, ast.ImportFrom))` | 元组表示"属于其中任一类型" |
| 字典 `.get(k, default)` | `schema.get("required", [])`、`prop_schema.get("type")` | 键缺失时给默认值 |
| 字典 `.copy()` | `WEATHER_DB[key].copy()` | 浅拷贝，避免改到共享数据 |
| 列表 / 字典推导式 | `[c for c in WEATHER_DB if c in msg]`、`{k: str(v) for k, v in local_vars.items() if not k.startswith("_")}` | 一行构造 |
| 条件表达式 | `iterations = iteration + 1 if tool_calls else 0` | 一行 if/else |
| 正则 `re.findall` | `re.findall(r"[0-9.+\-*/()\s]{3,}", msg)` | 抽取连续 3 个及以上的"类表达式"片段；`\-` 在字符类里转义连字符 |
| 字符串方法 | `.lower()`、`.strip()`、`.startswith("/")`、`.title()`、`.capitalize()`、`.split("/")[-1].split(".")[0]` | 规范化与切分 |
| f-string | `f"City '{city}' not found."`、`f"{type(e).__name__}: {e}"` | 插值；`type(e).__name__` 取异常类名 |
| `json.dumps` | `json.dumps(result["result"])` | 把 Python 对象序列化成 JSON 字符串 |
| `try/except` 指定异常 | `except TypeError as e:`、`except SyntaxError as e:` | 只捕获特定异常（本文件的坑之一） |
| `time.time()` | 计时 | 墙钟时间；测耗时更应该用 `time.perf_counter()` |
| `if __name__ == "__main__":` | 文件末尾 `run_demo()` | 直接运行才执行 demo |

---

## 6. 运行结果解读

实际运行 `python function_calling.py`（已运行，输出确定、无随机性），节选并解读：

```text
--- Argument Validation ---
  Valid call: VALID
  Missing required arg: ERRORS: ['Missing required argument: city']
  Invalid enum value: ERRORS: ["Argument 'units': 'kelvin' not in ['celsius', 'fahrenheit']"]
  Wrong type (int for string): ERRORS: ["Argument 'expression': expected string, got int"]
  Unknown tool: ERRORS: ['Unknown tool: unknown_tool']
```

校验器四类检查都工作正常——但注意它只在这一节被单独调用，并不在真正的执行路径上。

```text
--- Tool Execution ---
  calculator({"expression": "(10 + 5) * 3 / 2"}) -> {"result": 22.5, ...}
  get_weather({"city": "Mars"}) -> {"error": true, "message": "City 'Mars' not found.", "suggestions": [], ...}
  read_file({"path": "../etc/passwd"}) -> {"error": true, "message": "Path traversal not allowed.", ...}
  run_code({"code": "import os; ..."}) -> {"error": true, "message": "Forbidden operation: import is not allowed", ...}
```

- 计算器正常；缺城市时返回结构化错误，但 `Mars` 的 suggestions 为空。
- 路径穿越、`import` 语句都被护栏拦下（返回 error）。

```text
--- Full Function Calling Loop ---
  User: Search for MCP protocol
    Tool: web_search (0.04ms)
    Result: {"query": "mcp protocol", "results": [], "total": 0}      ← 工具调用了，但结果为空（大小写 bug）
  User: Tell me a joke
    [No tool called -- direct response]
    Iterations: 0
```

- `Search for MCP protocol` 看似"成功调用了 web_search"，实际结果为空——因为 `SEARCH_DB` 的键大写、查询小写，互不为子串（见测验 Q6）。**这说明评估工具调用时不能只看"有没有调用"，还要看结果是否真的有用。**
- `Tell me a joke` 不匹配任何规则，返回空调用、`iterations=0`，相当于"模型直接作答"。

```text
--- Parallel Tool Calls ---
  User: What's the weather in tokyo and london?
  Tool calls made: 2
    Tokyo: 18C, cloudy
    London: 12C, rainy
```

- 一轮里返回两个 `get_weather` 并顺序执行，演示并行调用的形状（但未真正并发，也缺 call id）。

```text
--- Security Checks ---
  read_file(../../etc/passwd): BLOCKED
  run_code(...subprocess...): BLOCKED
  calculator(__import__('os')...): BLOCKED
```

- 三项越权尝试都被对应护栏拦住。但正如第 3.5 节所述，`run_code` 的护栏只是教学过滤器，仍存在字符串属性链、无超时等绕过/风险。

---

## 7. 动手改一改

1. **把校验接入执行路径**：在 `execute_tool_call` 开头调用 `validate_tool_arguments`，有错就直接返回结构化错误；并把 `except TypeError` 放宽为 `except Exception`，实现测验 Q9 的 `safe_execute_tool_call`。
2. **修 `web_search` 大小写 bug**：比较前对 `db_key` 也 `.lower()`，验证 `"Search for MCP protocol"` 能返回真实结果。
3. **安全计算器**：用 `ast` 只放行数字和 `+ - * /`（含一元正负），禁用 `**`，限制数值大小，替换 `eval`（参考测验 Q11）。
4. **真正的多步循环**（讲义练习 3）：让决策函数接收 `conversation`，每个调用带 `tool_call_id`，去掉写死的 `break`，达到 `max_iterations` 时报告停止原因；跑通"读 config → 搜该模型定价"。
5. **工具选择评测**（讲义练习 4）：准备 30 条标注查询，统计工具选择准确率、"该调不调/不该调却调"、参数准确率，画混淆矩阵。
6. **加第 6 个工具**（讲义练习 1）：一个只接受表名 + 受限过滤条件（`= > < >= <=`）的数据库查询工具，表名走白名单，演示讲义安全规则 1"绝不执行模型生成的原始 SQL"。
7. **工具结果缓存**（讲义练习 5）：对 `(tool_name, frozenset(args.items()))` 做键缓存 60 秒，注意嵌套/不可哈希参数的处理。

---

## 8. 常见坑

- **以为模型执行了函数**：模型只输出调用意图，执行与安全全在应用侧。
- **校验器写了不接入**：本文件最大的坑——`validate_tool_arguments` 从未在执行路径被调用，参数全靠工具内部兜底。
- **只捕获一种异常**：`except TypeError` 挡不住 `get_weather(city=123)` 的 `AttributeError`，循环会崩。
- **字符白名单挡不住 `**`**：计算器可被超大指数拖垮，用 AST + 数值限制才稳。
- **进程内过滤当成沙箱**：`run_code` 的 AST 检查是教学过滤器，真正的不可信代码必须进独立进程/容器并限资源。
- **大小写/标点敏感的匹配**：`web_search` 的大小写 bug、`read_file` 对 `./README.md` 的误伤，都是"看似成功实则没命中"。
- **循环缺上限和 call id**：没有迭代上限会被模型拖进死循环；`tool` 消息缺 `tool_call_id` 时并行结果无法对应。
- **只看"是否调用工具"**：Search 那条调用了工具却返回空结果，评估必须看结果有效性而不只是调用动作。

---

## 9. 测试在验证什么

`tests/test_main.py` 用标准库 `unittest` 覆盖三个工具的护栏。运行：`python -m unittest discover -s tests -v`（已实际运行，**9 个用例全部通过**）。它先用 `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` 把上一级目录加入模块搜索路径，再 `from function_calling import run_code, calculator, read_file`。

| 测试 | 验证的性质 | 实际结果 |
|------|-----------|---------|
| `test_benign_code_runs` | 正常代码能跑：`result = sum(range(1, 101))` | 返回 `success=True`、`result == 5050` |
| `test_math_helper_available` | 受限环境里保留了 `math`：`round(math.sqrt(2), 3)` | 返回 `1.414` |
| `test_import_statement_blocked` | `import os` 被静态分析拦下 | `code == "SECURITY_VIOLATION"` |
| `test_from_import_blocked` | `from os import getpid` 同样被拦 | `SECURITY_VIOLATION` |
| `test_dunder_attribute_chain_blocked` | 通过双下划线属性链回溯解释器的写法被拦 | `SECURITY_VIOLATION` |
| `test_unsafe_builtin_name_blocked` | 危险内置名 `eval` 被拦 | `SECURITY_VIOLATION` |
| `test_syntax_error_reported` | 语法错误能被捕获并报告 | `code == "SYNTAX_ERROR"` |
| `test_calculator_rejects_non_math_characters` | 计算器字符白名单挡住含字母/引号的表达式 | `error == True` |
| `test_read_file_rejects_traversal` | 路径穿越被拒 | `code == "FORBIDDEN"` |

这些测试验证的是**护栏的正向与反向行为**：正常输入应成功、越权输入应被特定错误码拦截。值得注意的是，它们只覆盖了"能被静态分析识别的攻击形态"，并没有测试第 3.5 / 第 8 节提到的绕过方式（运行时才拼出的属性访问、无超时的死循环、计算器的超大指数 DoS）——也就是说，**测试全绿不代表护栏安全**，只代表它拦住了测试里列出的那几类。要真正验证隔离，需要在独立进程/容器中做超时、内存、网络的端到端测试。
