# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 07 节 构建 MCP 服务端：无状态 Python 与 TypeScript ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py --demo`（演示 8 个请求）；`python3 main.py`（作为 stdio server，从 stdin 逐行读 JSON-RPC）；测试 `python3 -m unittest discover tests -v`（均在 `code/` 下） ｜ **依赖**：仅标准库（`json`、`sys`、`uuid`、`copy`、`typing`）；同目录 `main.ts` 是 TypeScript 移植版，可用 Node.js 22.6+ 的 `node --experimental-strip-types main.ts --demo` 或讲义中的 `npx tsx main.ts --demo` 运行

---

## 1. 这份代码在考察什么

第 06 节把"一个请求的生命周期"讲清楚了；这一节把它做成一个**真正能被客户端拉起的 stdio MCP server**——一个笔记服务，暴露全部三种 server primitive：

1. **强制的 `server/discover`**：声明支持的版本、tools/resources/prompts 三类能力、使用说明、缓存提示和 server 身份。
2. **每请求校验**：信封、id 类型、`_meta` 中的版本 / capabilities / clientInfo，每个请求从零开始。
3. **三种 primitive 的 handler**：`tools/list` + `tools/call`、`resources/list` + `resources/read`、`prompts/list` + `prompts/get`，列表一律确定排序。
4. **两类错误**：`RpcProblem` 异常 → JSON-RPC 协议错误；executor 中的业务异常 → `isError: true` 的工具结果；其它异常 → `-32603`。
5. **集中的结果包装**：`complete()` 统一加 `resultType`、`serverInfo`，可缓存结果再加 `ttlMs` / `cacheScope`。
6. **stdio 传输纪律**：一行一条消息、只往 stdout 写 JSON-RPC、每条 flush、EOF 退出。
7. **应用状态 ≠ 协议状态**：`NOTES` 是合法的应用状态（可被 `notes_create` 修改），但没有任何"会话"或"连接上声明过的能力"。

> 一句话：**用一张 `HANDLERS` 路由表 + 一个 `complete()` 包装器 + 一个"校验—分发—异常归类"的 `dispatch`，就能写出无状态的 MCP server**。同时要看到它与讲义、与 TS 移植版之间的几处不一致（未知工具的归类、校验顺序、浅拷贝、跨语言的参数校验差异）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 版本 / `_meta` 键常量 | 模块常量 | 与第 06 节相同 | 每请求元数据 |
| `SERVER_CAPABILITIES` | 模块常量 | 声明 tools / resources / prompts 三类能力，全部 `listChanged: False` | 能力声明 |
| `_BASE_NOTES` / `NOTES` / `reset_notes` | 常量 + 可变全局 + 函数 | 初始笔记、运行时笔记库、测试用重置 | 应用状态 |
| `TOOLS` / `PROMPTS` | 模块常量 | 3 个工具描述符（含 annotations）、1 个 prompt 描述符 | Tools / Prompts primitive |
| `RpcProblem` | 异常类 | 携带 `code` 与 `data` 的协议错误 | 协议错误 |
| `request_meta` / `make_request` / `rpc_error` | 函数 | 构造请求与错误响应 | JSON-RPC 信封 |
| `complete` | 函数 | 统一成功结果包装 | `resultType` + 身份 + 缓存提示 |
| `validate_request` | 函数 | 校验信封、id、`_meta`，失败抛 `RpcProblem` | 每请求校验 |
| `exec_notes_list/search/create` + `TOOL_EXECUTORS` | 函数 + 路由表 | 工具的业务逻辑 | 工具执行 |
| `handle_*` + `HANDLERS` | 函数 + 路由表 | 7 个 MCP 方法的 handler | 方法路由 |
| `dispatch` | 函数 | 通知判断 → 校验 → 路由 → 异常归类 | dispatch loop |
| `serve_stdio` | 函数 | 逐行读 stdin，处理解析错误，写 stdout | stdio 传输 |
| `demo` / `main` | 函数 | `--demo` 演示或进入 stdio 服务 | 入口 |

数据流（stdio 模式）：stdin 一行 → `json.loads`（失败 `-32700`）→ 是否对象（否 `-32600`）→ `dispatch` →（无 id）不回复 /（有 id）`validate_request` → `HANDLERS[method]` → `handle_*` →（tools/call）`TOOL_EXECUTORS[name]` → `complete(...)` → `json.dumps(紧凑) + "\n"` → stdout + flush。

---

## 3. 逐段精讲

### 3.1 能力声明与应用状态

```python
SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
    "resources": {"listChanged": False, "subscribe": False},
    "prompts": {"listChanged": False},
}

_BASE_NOTES: dict[str, dict[str, str]] = {
    "note-1": {"title": "MCP overview", "body": "Stateless requests and JSON-RPC.", "tag": "mcp"},
    ...
}
NOTES = deepcopy(_BASE_NOTES)
```

- 三个 primitive 都声明了，且都**不**推送变更（`listChanged: False`、`subscribe: False`）。讲义："Modern change delivery does not use `resources/subscribe`"——变更推送在第 10 节通过客户端打开的 `subscriptions/listen` 实现。
- `NOTES` 是**应用状态**：`notes_create` 会往里写。这是讲义允许的（"Your application can still keep durable notes"），它和"协议状态"无关——无论哪个客户端、带什么 capabilities，看到的都是同一个笔记库，处理方式不依赖历史请求。
- `NOTES = deepcopy(_BASE_NOTES)` + `reset_notes()`：保留一份不可变的初始数据，测试的 `setUp` 每次调用 `reset_notes()`，保证测试之间互不影响。`reset_notes` 用 `clear()` + `update()` 原地修改而不是重新赋值，因为其它函数引用的是同一个 `NOTES` 对象。

### 3.2 工具与 prompt 描述符

```python
    {
        "name": "notes_search",
        "description": "Search note titles and bodies by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True},
    },
```

- `inputSchema` 是 JSON Schema，模型和 host 据此构造参数；`limit` 的 `minimum` / `maximum` 在 executor 中被**再次**手工校验——schema 只是声明，server 端必须自己执行。
- `annotations`：`notes_search` / `notes_list` 只读且幂等；`notes_create` 非破坏、非幂等（每次调用都新建一条）。讲义强调这些只是提示："The host should use them for confirmation and presentation. The server must still enforce real authorization."
- `TOOLS` 的定义顺序是 search、create、list，故意不按字母序，用来验证排序（讲义练习 2）。
- `PROMPTS` 只有 `review_note`，声明一个必填参数 `note_id`。

### 3.3 `RpcProblem`：用异常表达协议错误

```python
class RpcProblem(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
```

- 与第 06 节"返回错误或 None"的风格不同，这里用**异常**：任何深层 handler 都可以 `raise RpcProblem(-32602, ...)`，由 `dispatch` 统一捕获并转成错误响应，handler 本身只需关心正常路径。
- `super().__init__(message)` 让 `str(exc)` 返回 message，`dispatch` 里正是用 `str(exc)` 填错误消息。

### 3.4 `complete`：集中的成功结果包装

```python
def complete(payload, *, ttl_ms=None, cache_scope="private"):
    result = {
        "resultType": "complete",
        **payload,
        "_meta": {SERVER_INFO_KEY: SERVER_INFO.copy()},
    }
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope
    return result
```

- 讲义："Centralizing this wrapper prevents one handler from silently omitting modern result fields."
- `cache_scope` 默认 `"private"`：调用者只传 `ttl_ms` 时自动落到安全的作用域。
- 各 handler 的缓存策略：

| 方法 | `ttlMs` | `cacheScope` | 理由 |
|------|--------|-------------|------|
| `server/discover` | 3,600,000（1 小时） | public | 版本 / 能力只随部署变化 |
| `tools/list` | 60,000 | public | 工具定义对所有人相同 |
| `prompts/list` | 60,000 | public | 同上 |
| `resources/list` | 10,000 | private | 笔记是数据，可能因人而异，且会被 `notes_create` 改变 |
| `resources/read` | 5,000 | private | 同上，内容更细 |
| `tools/call`、`prompts/get` | 无 | 无 | 讲义：不属于需要缓存提示的结果 |

（具体 TTL 数值是代码的选择，讲义只规定了"哪些结果必须带"和"安全默认是 0 + private"。）

### 3.5 `validate_request`：每请求校验

```python
def validate_request(message):
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        raise RpcProblem(-32600, "Invalid Request")
    if "id" in message and type(message["id"]) not in (int, str):
        raise RpcProblem(-32600, "id must be a string or integer")
    params = message.get("params")
    if not isinstance(params, dict):
        raise RpcProblem(-32602, "params must be an object")
    meta = params.get("_meta")
    ...
    if requested not in SUPPORTED_VERSIONS:
        raise RpcProblem(-32022, "Unsupported protocol version",
                         {"requested": requested, "supported": SUPPORTED_VERSIONS.copy()})
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        raise RpcProblem(-32602, f"{CAPABILITIES_KEY} is required")
    ...
```

- 相比第 06 节新增了 **id 类型检查**：`type(x) not in (int, str)` 而不是 `isinstance`——因为 `bool` 是 `int` 的子类，`isinstance(True, int)` 为 `True`，用 `type` 才能把 `True` 拒之门外。`None`、`1.5`、dict 也都会被拒绝。
- ⚠️ **校验顺序与第 06 节讲义一致性问题依旧**：版本支持性检查仍在 capabilities 检查之前。实测"版本 `2027-01-01` + 缺 capabilities"返回 `-32022`，按第 06 节讲义生命周期应为 `-32602`。
- ⚠️ Python 的 `int` 没有上限，`id = 2**53` 会被接受并原样回显；TS 版用 `Number.isSafeInteger` 拒绝了它（见 3.10）。

### 3.6 三个工具 executor

```python
def exec_notes_list(arguments):
    tag = arguments.get("tag")
    items = [
        {"id": note_id, "title": note["title"], "tag": note.get("tag", "")}
        for note_id, note in sorted(NOTES.items())
        if not tag or note.get("tag") == tag
    ]
    return [{"type": "text", "text": json.dumps(items, sort_keys=True)}]


def exec_notes_search(arguments):
    query = arguments.get("query")
    if not isinstance(query, str) or not query:
        raise ValueError("query must be a non-empty string")
    limit = arguments.get("limit", 10)
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 through 50")
    needle = query.lower()
    hits = [... for note_id, note in sorted(NOTES.items())
            if needle in note["title"].lower() or needle in note["body"].lower()]
    return [{"type": "text", "text": json.dumps(hits[:limit], sort_keys=True)}]
```

- executor 只做业务逻辑，返回 **content 块列表**；包装成结果由 `handle_tools_call` 负责。
- `sorted(NOTES.items())` 按 note id 排序，保证**工具输出**也是确定的（不止 list 方法）。`json.dumps(..., sort_keys=True)` 让 JSON 文本的键顺序也确定。
- 搜索是大小写不敏感的子串匹配；`hits[:limit]` 截断。
- 参数不合法抛 `ValueError`，被上层转成 `isError` 结果，模型能看到具体原因。
- `1 <= limit <= 50` 是 Python 的**链式比较**。
- ⚠️ `isinstance(limit, int)` 会接受 `True`（实测 `limit: true` 被当作 1，返回 1 条结果），与 3.5 中刻意用 `type()` 拒绝布尔 id 的做法不一致；TS 版 `Number.isInteger(true)` 为假，会报错。

```python
def exec_notes_create(arguments):
    title = arguments.get("title")
    body = arguments.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("title and body must be strings")
    note_id = f"note-{uuid.uuid4().hex[:6]}"
    NOTES[note_id] = {"title": title, "body": body, "tag": str(arguments.get("tag", ""))}
    return [
        {"type": "text", "text": f"Created {note_id}"},
        {"type": "resource", "resource": {"uri": f"notes://{note_id}", "text": body}},
    ]
```

- 返回**两个** content 块：一段文本 + 一个**嵌入资源**（`type: "resource"`），把新笔记的 URI 和正文直接带回，客户端可以立刻用这个 URI 调 `resources/read`（测试 `test_create_then_read_returns_private_cacheable_resource` 就是这么做的）。
- ID 用 `uuid4().hex[:6]`（6 位十六进制、约 1677 万种），随机而不是自增，避免被枚举；但 6 位在大量创建时存在碰撞可能，且代码没有检查碰撞，会静默覆盖已有笔记。
- ⚠️ `str(arguments.get("tag", ""))`：`tag` 为 `None` 时存入字符串 `"None"`（已实测，之后 `notes_list` 显示 `"tag": "None"`），`tag: 123` 存入 `"123"`；TS 版则对非字符串一律存空串。

### 3.7 handlers 与 `tools/call` 的错误归类

```python
def handle_tools_call(params):
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise RpcProblem(-32602, "tools/call requires string name and object arguments")
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return complete(
            {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        )
    try:
        return complete({"content": executor(arguments), "isError": False})
    except (KeyError, TypeError, ValueError) as exc:
        return complete(
            {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        )
```

三层错误：

| 情况 | 结果 | 例子（实测） |
|------|------|------------|
| `name` 非字符串或 `arguments` 非对象 | JSON-RPC `-32602` | `arguments: []` |
| 工具名未知 | 成功结果 + `isError: true` | `Unknown tool: missing` |
| executor 抛 `KeyError/TypeError/ValueError` | 成功结果 + `isError: true` | `query must be a non-empty string` |
| executor 抛其它异常 | 冒泡到 `dispatch` → `-32603` | — |

- ⚠️ **未知工具的归类与讲义不一致**：讲义"Use a JSON-RPC error when the protocol envelope or method parameters are invalid. Use `isError: true` when a valid tool invocation runs but the tool itself fails." 未知工具并不是"合法调用"，按讲义更应是协议错误；代码和测试 `test_unknown_tool_is_tool_level_error` 选择了 `isError`（好处是模型能看到并改正工具名）。
- `params.get("arguments", {})`：不传 `arguments` 时默认空对象，所以 `{"name": "notes_list"}` 可以正常调用。

资源与 prompt 的 handler：

```python
def handle_resources_read(params):
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri.startswith("notes://"):
        raise RpcProblem(-32602, "resources/read requires a notes:// URI")
    note_id = uri.removeprefix("notes://")
    note = NOTES.get(note_id)
    if note is None:
        raise RpcProblem(-32602, "Resource not found", {"uri": uri})
    text = f"# {note['title']}\n\n{note['body']}\n\ntag: {note.get('tag', '')}"
    return complete({"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]},
                    ttl_ms=5_000, cache_scope="private")
```

- 资源用自定义 URI scheme `notes://<id>` 寻址；`str.removeprefix`（Python 3.9+）去掉前缀得到 id。
- `contents` 是列表（一次 read 可以返回多个内容块），每块带 `uri`、`mimeType`、`text`。
- 资源不存在用 `-32602` + `data.uri`。
- `handle_prompts_get` 校验 prompt 名和 `note_id`，渲染出一条 `role: "user"` 的消息。它的 `messages` 结构与 chat API 类似，host 会把它插入对话。
- 所有 handler 签名一致：`(params: dict) -> dict`，即使不需要 `params`（如 `handle_discover`）也接收它，这样 `HANDLERS` 表才能统一调用。

### 3.8 `dispatch`：通知、校验、路由、异常归类

```python
def dispatch(message):
    if "id" not in message:
        return None
    request_id = message.get("id")
    error_id = request_id if type(request_id) in (int, str) else None
    try:
        validate_request(message)
        handler = HANDLERS.get(message["method"])
        if handler is None:
            raise RpcProblem(-32601, f"Method not found: {message['method']}")
        result = handler(message["params"])
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except RpcProblem as exc:
        return rpc_error(error_id, exc.code, str(exc), exc.data)
    except Exception as exc:
        return rpc_error(error_id, -32603, "Internal error", {"detail": str(exc)})
```

- **路由表**代替 if/elif 链：新增方法只需注册一个函数。`HANDLERS` 中没有 `initialize`，所以带现代 `_meta` 的 `initialize` 得到 `-32601`；不带 `_meta` 的真正 legacy `initialize` 会在校验阶段得到 `-32602`。
- `error_id`：id 非法时错误响应用 `null`，不回显可疑的值。
- 两层 `except`：先捕获已知的协议错误，再兜底所有其它异常为 `-32603`，保证一个坏请求不会让进程崩溃——这比第 06 节健壮。
- ⚠️ 兜底把 `str(exc)` 放进 `data.detail` 返回给客户端。实测：若 executor 抛 `RuntimeError("db password=hunter2 at 10.0.0.5")`，客户端会原样收到这段文字。生产应只返回通用信息 / 关联 ID，把详情写到 stderr。

### 3.9 `serve_stdio`：stdio 传输纪律

```python
def serve_stdio():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            response = rpc_error(None, -32700, "Parse error", {"detail": str(exc)})
        else:
            response = (
                dispatch(parsed)
                if isinstance(parsed, dict)
                else rpc_error(None, -32600, "Invalid Request")
            )
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
```

- `for raw_line in sys.stdin`：逐行迭代，stdin 关闭（EOF）时循环自然结束、函数返回、进程退出——讲义"Exit promptly when stdin reaches EOF"。
- `try / except / else`：`else` 分支只在没有异常时执行，把"解析"和"处理"分开，避免 `dispatch` 内部的异常被误当成解析错误。
- 顶层是数组（JSON-RPC batch）→ `-32600`：本 server 不支持批量。
- `separators=(",", ":")` 输出紧凑 JSON，保证一条消息恰好一行（`json.dumps` 默认会把字符串中的换行转义为 `\n`，不会产生真正的换行）。
- 每条响应后 `flush()`：stdout 接管道时是块缓冲，不 flush 的话客户端可能一直等不到响应。
- 全程不 `print` 任何诊断到 stdout；`demo()` 用 `print` 是因为它不作为 server 运行。

### 3.10 TypeScript 移植版 `main.ts` 的差异

讲义说两个版本"expose the same methods and enforce the same wire contract"。结构上确实一一对应（`RpcProblem`、`complete`、`validateRequest`、`TOOL_EXECUTORS`、`HANDLERS`、`dispatch`、`serveStdio`），`structuredClone` 对应 `deepcopy`，`readline` 的 `line` 事件对应逐行读取。但用同一份输入实测，有以下差异：

| 输入 | Python | TypeScript |
|------|--------|-----------|
| `tools/call` 不带 `arguments` | 正常执行（默认 `{}`） | `-32602`（要求 `params.arguments` 为真值对象） |
| `arguments: []` | `-32602` | 放行（`typeof [] === "object"`），executor 报 `isError` |
| `limit: true` | 当作 1 | `isError`（`Number.isInteger(true)` 为假） |
| `id = 2**53` | 接受 | `-32600`（`Number.isSafeInteger`） |
| `tag: null` | 存 `"None"` | 存 `""` |
| 工具输出文本 | `json.dumps` 带空格、键排序 | `JSON.stringify` 紧凑、插入顺序 |
| 列表排序 | 按码点（`sorted`） | `localeCompare`（区域敏感，对大小写/符号的排序可能与码点不同） |

测试 `test_typescript_ids_are_limited_to_safe_integer_bounds` 是唯一的跨语言测试，它只覆盖了 id 边界。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库实现协议核心 | 讲义要求，协议细节完全可见 | 生产用官方 SDK；但理解手写版有助于排查 SDK 行为 |
| `HANDLERS` / `TOOL_EXECUTORS` 路由表 | 新增方法 / 工具只需注册 | 需要配合"所有 handler 都经过 `complete`"的测试 |
| 协议错误用异常，`dispatch` 统一归类 | handler 只写正常路径 | 兜底异常把内部消息回传给客户端，有信息泄露风险 |
| 集中的 `complete()` | 防止漏 `resultType` / 身份 / 缓存提示 | — |
| 资源 `private`、定义类 `public` | 数据可能因人而异 | 多租户时工具列表若按权限过滤也要改 `private` |
| 未知工具返回 `isError` | 让模型能自我纠正 | 与讲义的错误分类规则不一致 |
| 手写 `isinstance` 校验参数 | 无第三方依赖 | 与 `inputSchema` 双份维护、跨语言不一致；生产用 JSON Schema 校验器 |
| `NOTES` 为进程内全局字典 | 演示应用状态 | 多副本部署需改为数据库；ID 碰撞未处理 |
| 只做 modern，不含 legacy 适配器 | 让不变量清晰 | 老客户端无法连接；讲义练习 5 要求另建隔离的适配器 |
| 浅拷贝 `sorted(TOOLS)` | 写法简短 | 返回对象与全局共享，可被下游就地修改（第 06 节同类问题） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from copy import deepcopy` | `deepcopy(_BASE_NOTES)`、`deepcopy(SERVER_CAPABILITIES)` | 递归复制所有层级，修改副本不影响原对象 |
| 类型别名式注解 | `dict[str, Callable[[dict[str, Any]], dict[str, Any]]]` | `Callable[[参数类型], 返回类型]` 描述"函数"类型 |
| 自定义异常 | `class RpcProblem(Exception)` + `super().__init__(message)` | 继承 `Exception`，可携带额外属性 |
| `raise` / `try...except...` | `raise RpcProblem(-32602, ...)`、`except RpcProblem as exc` | 抛出与捕获；`as exc` 绑定异常对象 |
| 捕获多种异常 | `except (KeyError, TypeError, ValueError) as exc` | 元组列出多个异常类型 |
| `try...except...else` | `serve_stdio` 中解析 JSON | `else` 仅在没有异常时执行 |
| `type(x) in (...)` vs `isinstance` | `type(message["id"]) not in (int, str)` | `type` 精确匹配，不认子类；`bool` 是 `int` 的子类 |
| 链式比较 | `1 <= limit <= 50` | 等价于 `1 <= limit and limit <= 50` |
| 带条件的列表推导式 | `[... for note_id, note in sorted(NOTES.items()) if not tag or ...]` | 遍历、过滤、构造一步完成；`.items()` 返回 (键, 值) 对 |
| `sorted(dict.items())` | `sorted(NOTES.items())` | 按键排序得到确定顺序 |
| 切片 | `hits[:limit]`、`uuid.uuid4().hex[:6]` | 取前 N 个元素 / 字符 |
| `str.removeprefix` / `startswith` | `uri.removeprefix("notes://")` | Python 3.9+ 去前缀 |
| `uuid` | `uuid.uuid4().hex` | 生成随机 UUID 的 32 位十六进制串 |
| dict 作为函数路由表 | `HANDLERS.get(message["method"])` | 找不到返回 `None` |
| `dict.clear()` / `update()` | `reset_notes` | 原地清空 / 合并，保持对象身份不变 |
| 条件表达式 | `dispatch(parsed) if isinstance(parsed, dict) else rpc_error(...)` | 一行 if/else |
| `sys.stdin` 迭代 | `for raw_line in sys.stdin` | 逐行读取，EOF 时结束 |
| `sys.stdout.write` / `flush` | `serve_stdio` | 写入不自动换行；flush 立即推送缓冲 |
| `json.dumps(separators=...)` | `separators=(",", ":")` | 去掉多余空格，输出紧凑 JSON |
| 多行 f-string 与转义 | `f"# {note['title']}\n\n{note['body']}"` | f-string 内用不同引号访问字典键 |
| `"--demo" in sys.argv` | `main()` | 最简单的命令行开关 |

---

## 6. 运行结果解读

`python3 main.py --demo` 实际输出（每个响应只打印前 700 个字符，所以 `tools/list` 被截断；以下为摘要）：

```text
MCP 2026-07-28 stateless notes server

server/discover id=1
  result: capabilities {prompts, resources{listChanged,subscribe}, tools}, instructions "...",
          resultType complete, supportedVersions ["2026-07-28"], ttlMs 3600000, cacheScope public,
          _meta.serverInfo {"name": "notes-lesson-07", "version": "2.0.0"}

tools/list id=2
  result: tools[0] = notes_create（annotations destructiveHint false, idempotentHint false）... （被截断）

resources/list id=3
  result: resources = notes://note-1 "MCP overview", notes://note-2 "Function calling", notes://note-3 "Tool schemas"
          cacheScope private, ttlMs 10000

prompts/list id=4
  result: prompts = [review_note（arguments: note_id required）], cacheScope public, ttlMs 60000

tools/call id=5
  result: content[0].text = "[{\"id\": \"note-1\", \"title\": \"MCP overview\"}]", isError false

resources/read id=6
  result: contents[0].text = "# MCP overview\n\nStateless requests and JSON-RPC.\n\ntag: mcp",
          mimeType text/markdown, cacheScope private, ttlMs 5000

prompts/get id=7
  result: messages[0] = {role: user, content.text: "Review this note and propose improvements:\n\nStateless requests and JSON-RPC."}
          （无 ttlMs / cacheScope）

tools/list id=8
  error: code -32022, data {requested "2027-01-01", supported ["2026-07-28"]}
```

逐项解读：

- **discover**：三类能力都在，TTL 1 小时、public；身份在结果 `_meta` 中。
- **tools/list**：第一个是 `notes_create`——定义顺序是 search / create / list，排序后变成 create / list / search（实测名字列表 `['notes_create', 'notes_list', 'notes_search']`）。
- **resources/list**：按 note id 排序，`private` + 10 秒。
- **tools/call `notes_search("MCP")`**：只命中 note-1（标题 "MCP overview"），工具输出是 JSON 字符串放进 text 块。
- **resources/read**：Markdown 渲染的笔记，`private` + 5 秒。
- **prompts/get**：complete 但没有缓存提示，符合讲义。
- **版本 2027-01-01**：`-32022`，告诉客户端改用 `2026-07-28`。
- 8 个请求互相独立，第 8 个即使紧跟在 7 个成功请求之后，也不会因为"之前协商过"而被放行。

测试：`python3 -m unittest discover tests -v` 实测 **10 个测试全部通过**（`Ran 10 tests in 0.321s, OK`）；本环境有 Node.js v22.22.0，所以 TS 跨语言测试真正执行了而不是被跳过。TS 版 demo（`node --experimental-strip-types main.ts --demo`）也能运行，7 个成功结果均为 `resultType: "complete"`。

---

## 7. 动手改一改

1. **讲义练习 1**：写一个测试，先发一个 `capabilities={"extensions": {}}` 的 `tools/list`，再发一个删掉 capabilities 的 `tools/list`，断言第二个得到 `-32602`。顺便把 `validate_request` 的版本检查移到 capabilities 和 clientInfo 检查之后，并补测"版本错误 + 缺 capabilities → `-32602`"。
2. **讲义练习 2**：把 `TOOLS`、`PROMPTS` 反转、把 `_BASE_NOTES` 的插入顺序打乱，确认三个 list 结果不变；再用 `deepcopy` 修复 `sorted(TOOLS)` / `sorted(PROMPTS)` 的共享引用问题，并加一个"修改返回结果不影响下次结果"的测试。
3. **讲义练习 3**：增加 `notes_delete`，`destructiveHint: True`；给 `dispatch` → handler → executor 增加一个 `principal` 参数（从传输层得到，本练习中可从环境变量模拟），在 executor 内检查权限（参考测验 Q12）。
4. **讲义练习 4**：实现 `resources/templates/list`，返回 `[{"uriTemplate": "notes://{note_id}", "name": "Note by id", "mimeType": "text/markdown"}]`，带 `ttlMs` 与 `cacheScope`，并加入"所有 list 都有序且可缓存"的参数化测试。
5. **统一错误策略**：把未知工具改为 `-32602`；`dispatch` 的兜底只返回 `{"incident": <随机 ID>}`，把异常写到 stderr；`limit` 校验改为 `type(limit) is int`；`tag` 非字符串时报错。
6. **讲义练习 5（进阶）**：写一个独立的 `legacy_adapter.py`，实现 `2025-11-25` 的 `initialize` / `notifications/initialized`，在 `serve_stdio` 中根据"是否有现代 `_meta`"选择分支；测试证明现代请求从不进入适配器。再写一个 JSONL 一致性语料，同时驱动 `main.py` 和 `main.ts`，让测验 Q10 中的差异全部变成失败的测试，再逐个修复。

---

## 8. 常见坑

- **往 stdout 打印调试信息**：会破坏客户端的 JSON 解析；诊断一律写 stderr。
- **忘记 flush**：管道模式下 stdout 是块缓冲，客户端会"卡住"。
- **一条 JSON 跨多行**：用 `indent` 美化输出会产生多行，stdio 传输必须一行一条。
- **用 `isinstance(x, int)` 校验整数**：会放过 `True` / `False`。
- **把 annotations 当授权**：`readOnlyHint: True` 不会阻止任何事情，权限必须在 executor 中检查。
- **用 `clientInfo` 识别用户**：它是自报的，不是凭证。
- **所有异常都返回 `isError`**：内部错误细节进入模型上下文，既无用又可能泄密；反之所有异常都返回协议错误，模型失去自我纠正的机会。
- **给 `prompts/get` / `tools/call` 加缓存提示**：它们不是可缓存结果。
- **以为两种语言写"同样的逻辑"就会有同样的行为**：数组是不是对象、布尔是不是整数、大整数精度、字符串排序规则，在 Python 和 JavaScript 中都不一样。
- **在全局变量里偷偷存"上次请求的 capabilities"**：这就是讲义开篇所说的"easy to build and hard to operate"的 server。

---

## 9. 测试在验证什么

`tests/test_main.py` 使用 `unittest`，`setUp` 中调用 `main.reset_notes()` 保证每个测试从同一份笔记开始。在 `code/` 目录运行 `python3 -m unittest discover tests -v`，实测 **10 个测试全部通过**。

| 测试 | 验证的性质 | 对应讲义 |
|------|-----------|---------|
| `test_discover_is_mandatory_modern_shape` | discover 为 complete、版本列表正确、`cacheScope == "public"` | 强制的 `server/discover` |
| `test_missing_request_meta_is_invalid_params` | `params: {}`（无 `_meta`）→ `-32602` | 每请求校验 |
| `test_invalid_request_ids_are_rejected_at_the_boundary` | 用 `subTest` 对 `None / True / 1.5 / dict` 四种 id 逐一断言 `-32600` 且响应 `id` 为 `null` | 信封边界校验 |
| `test_typescript_ids_are_limited_to_safe_integer_bounds` | 用 `subprocess` 启动 `node --experimental-strip-types main.ts`，通过 stdin 发送 6 个请求：±(2⁵³−1) 被接受，±2⁵³、1.5、`true` 得到 `-32600`。Node 不存在或版本低于 22.6.0 时 `skipTest` | 跨语言 wire contract（JS 数字精度） |
| `test_unsupported_version_is_modern_error` | `2027-01-01` → `-32022`，`data.supported` 正确 | 版本协商 |
| `test_all_list_results_are_sorted_and_cacheable` | 三个 list 方法的排序键（name 或 uri）已排序，且带 `ttlMs` 与合法 `cacheScope` | 确定顺序 + 可缓存结果 |
| `test_every_success_has_server_identity` | 三个 list 结果都是 complete 且带 `serverInfo` | 集中的结果包装 |
| `test_create_then_read_returns_private_cacheable_resource` | `notes_create` 返回嵌入资源的 URI，`resources/read` 能读到正文且为 `private` | 应用状态 + 资源缓存作用域 |
| `test_unknown_tool_is_tool_level_error` | 未知工具得到 `isError: true` 的 complete 结果 | 工具错误（与讲义规则有分歧，见 3.7） |
| `test_initialize_is_not_a_modern_handler` | `initialize` → `-32601` | modern-only，legacy 需隔离 |

值得补充的测试：

- 校验顺序（版本错误 + 缺 capabilities）；
- 先后两个请求、第二个缺 capabilities，证明没有继承（讲义练习 1 的原意）；
- `tools/call` 的参数边界：`arguments` 缺省 / 为数组、`limit: true`、`tag: null`；
- 修改返回结果后全局 `TOOLS` 不变；
- `serve_stdio` 的黑盒测试：解析错误、数组输入、通知不回复、EOF 后进程退出码为 0；
- 把 TS 跨语言测试扩展成通用的一致性语料（测验 Q10）。
