# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 14 节 Model Context Protocol (MCP) ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`；测试：`python -m unittest discover tests -v`（在 `code/` 目录下）或 `python -m pytest -q` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`typing`）；测试用标准库 `unittest`，pytest 可选。
>
> 本讲解同时覆盖 `tests/test_main.py`（见第 9 节）。协议细节以讲义（MCP 2026-07-28 修订版）为准。

---

## 1. 这份代码在考察什么

这份代码不用任何 MCP SDK，只用标准库实现了一个**无状态 MCP 服务端**和一个**进程内客户端**，把协议的每个信封都摆在明面上：

1. **请求契约**：每个请求在 `params._meta` 中携带协议版本、客户端能力、客户端身份；服务端逐项校验，返回规范的错误码（`-32602`、`-32022`）。
2. **JSON-RPC 2.0 信封**：request 与 notification 的区分、`id` 类型、`-32600`/`-32601`/`-32603`。
3. **三种服务端原语**：用装饰器注册 tool、resource、prompt，实现 `*/list`、`tools/call`、`resources/read`、`prompts/get`。
4. **显式结果**：每个成功结果都有 `resultType: "complete"` 和 `_meta.serverInfo`；列表结果排序并带 `ttlMs`/`cacheScope`。
5. **能力发现**：`server/discover` 返回支持的版本、能力、身份与使用说明。
6. **安全提示**：破坏性工具带 `destructiveHint`。

> 一句话：**MCP 的本质是"一份所有人都遵守的 JSON-RPC 信封约定"**——本文件用不到 400 行把这份约定写成了可测试的代码。它刻意省略了传输层（HTTP 头、SSE）、参数 schema 校验和 MRTR，这些正是讲义练习和测验代码题的扩展点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` / `SUPPORTED_VERSIONS` / `*_KEY` | 常量 | 协议版本与 `_meta` 键名 | 版本协商 |
| `Tool` / `Resource` / `Prompt` | dataclass | 三种原语的注册记录 | 服务端原语 |
| `request_metadata` | 函数 | 生成每个请求的 `_meta` | 无状态请求 |
| `MCPServer.tool/resource/prompt` | 装饰器工厂 | 把函数注册为原语 | 能力发布 |
| `MCPServer._complete` | 方法 | 包装成功结果：`resultType`、`_meta`、缓存提示 | 显式结果 |
| `MCPServer._error` | 静态方法 | 构造 JSON-RPC 错误响应 | 错误码 |
| `MCPServer._validate_metadata` | 方法 | 校验 `_meta` | `-32602` / `-32022` |
| `MCPServer.handle` | 方法 | 信封校验 → 元数据校验 → 方法分发 | JSON-RPC 服务端 |
| `MCPClient` | 类 | 自增 id、自动附加 `_meta`、解包结果 | 客户端 |
| `server` + `add` / `delete_user` / `app_config` / `code_review` | 模块级实例与注册函数 | 演示用服务端表面 | Tools / Resources / Prompts |
| `main` | 函数 | 发现 → 列工具 → 调用 → 读资源 → 取 prompt | 端到端流程 |

数据流：`MCPClient.request(method, params)` → 拼 `{"jsonrpc","id","method","params"+_meta}` → `server.handle(message)` → 信封校验 → `_validate_metadata` → 按 `method` 分发 → `_complete(...)` 或 `_error(...)` → 客户端返回 `result` 或抛 `RuntimeError`。

---

## 3. 逐段精讲

### 3.1 常量与三种原语的数据结构

```python
PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = (PROTOCOL_VERSION,)
PROTOCOL_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    destructive: bool = False
```

- `_meta` 的键用**反向域名前缀** `io.modelcontextprotocol/`，避免和其他扩展的键冲突。把键名定义成常量，代码和测试都引用同一份，拼写错误会变成 `NameError` 而不是静默失败。
- `SUPPORTED_VERSIONS` 用元组（不可变）：本服务端只支持一个版本，所以 `2025-11-25` 会被拒绝。
- `Tool` 记录名称、描述（写给模型看）、JSON Schema 输入、处理函数和是否破坏性；`Resource` 以 URI 为主键；`Prompt` 记录参数名列表。
- `Callable[..., Any]` 表示"任意参数、任意返回值的可调用对象"；`Callable[[], str]` 表示"无参数、返回字符串"。

### 3.2 `request_metadata`：每个请求都要带的上下文

```python
def request_metadata(
    *,
    client_name: str = "demo-client",
    client_version: str = "1.0.0",
    capabilities: dict[str, Any] | None = None,
    protocol_version: str = PROTOCOL_VERSION,
) -> dict[str, Any]:
    return {
        PROTOCOL_KEY: protocol_version,
        CLIENT_CAPABILITIES_KEY: capabilities or {},
        CLIENT_INFO_KEY: {"name": client_name, "version": client_version},
    }
```

- 参数列表开头的 `*` 表示后面的参数**只能用关键字传递**：`request_metadata(protocol_version="2025-11-25")`，防止位置参数传错。
- 讲义："The protocol version and client capabilities are required. Client identity is recommended." 这里三者都填上，能力默认是空对象 `{}`（"我没有声明任何可选能力"，但字段本身必须存在）。
- `capabilities or {}`：不能把默认值直接写成 `= {}`（可变默认参数陷阱），所以默认 `None`，在函数体内换成新字典。

### 3.3 装饰器注册：`@server.tool(...)`

```python
    def tool(self, name, description, schema, *, destructive=False):
        def decorator(fn):
            self.tools[name] = Tool(name, description, schema, fn, destructive)
            return fn

        return decorator
```

- 这是**带参数的装饰器**：`server.tool("add", ...)` 先被调用，返回真正的装饰器 `decorator`；`@` 再把下面的函数 `add` 传给 `decorator`。
- `decorator` 是闭包，能访问外层的 `self`、`name` 等变量；它把函数登记进 `self.tools` 后**原样返回函数**，所以 `add(1, 2)` 依然可以在 Python 里直接调用和单元测试。
- 用名字（或 URI）做字典键：重复注册同名工具会**静默覆盖**前一个，生产中最好检测并报错。
- 这和讲义 Build It 第 1 步的写法一致："Registration stays simple even though the request contract changed"。

### 3.4 `_complete` 与 `_error`：结果与错误的统一形状

```python
    def _complete(self, payload, *, cacheable=False):
        result = {
            "resultType": "complete",
            **payload,
            "_meta": {SERVER_INFO_KEY: self.server_info},
        }
        if cacheable:
            result.update({"ttlMs": 30_000, "cacheScope": "private"})
        return result

    @staticmethod
    def _error(request_id, code, message, data=None):
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}
```

- 讲义要求："Every core 2026-07-28 result has `resultType`"，"Servers should include `io.modelcontextprotocol/serverInfo` in every result's `_meta`"——所有成功路径都经过 `_complete`，保证不会漏。
- `**payload` 在字典字面量中**展开**另一个字典。顺序决定覆盖关系：`_meta` 写在最后，payload 里即使带了 `_meta` 也会被覆盖（目前没有原语需要自定义 `_meta`）。
- 列表与读取类结果 `cacheable=True`：`ttlMs=30000`（30 秒）、`cacheScope="private"`。讲义示例的 discover 用的是 `3600000` 和 `public`；本实现统一用短 TTL + private，是更保守的选择。`tools/call` 和 `prompts/get` 不带缓存提示（讲义："A tool call returns a complete, non-cacheable result because its output can depend on current state"）。
- `_error` 只有在 `data` 非空时才加 `data` 字段：测试 `test_missing_protocol_version_is_invalid_params` 专门断言 `-32602` 错误里**没有** `data`。
- `server_info` 是自报身份。讲义："This identity is self-reported and is for display, logging, and debugging, not for security decisions."

### 3.5 `_validate_metadata`：逐项检查 `_meta`

```python
    def _validate_metadata(self, params, request_id):
        metadata = params.get("_meta")
        if not isinstance(metadata, dict):
            return self._error(request_id, -32602, "params._meta is required")
        if PROTOCOL_KEY not in metadata:
            return self._error(request_id, -32602, f"{PROTOCOL_KEY} is required")
        version = metadata[PROTOCOL_KEY]
        if not isinstance(version, str):
            return self._error(request_id, -32602, f"{PROTOCOL_KEY} must be a string")
        if version not in SUPPORTED_VERSIONS:
            return self._error(request_id, -32022, "Unsupported protocol version",
                               {"supported": list(SUPPORTED_VERSIONS), "requested": version})
        if not isinstance(metadata.get(CLIENT_CAPABILITIES_KEY), dict):
            return self._error(request_id, -32602, "clientCapabilities must be an object")
        client_info = metadata.get(CLIENT_INFO_KEY)
        if client_info is not None and (
            not isinstance(client_info, dict)
            or not isinstance(client_info.get("name"), str)
            or not isinstance(client_info.get("version"), str)
        ):
            return self._error(request_id, -32602, "clientInfo must contain name and version")
        return None
```

- 返回约定："有问题返回错误响应，没问题返回 `None`"，调用方 `if metadata_error: return metadata_error`。
- **顺序与讲义一致**："missing `_meta`、missing required field、wrong type → `-32602`；well-formed but unsupported version → `-32022`"。先确认"格式正确"，再判断"是否支持"——只有对一个合法的版本字符串才谈得上"不支持"。
- `-32022` 的 `data` 带 `supported`（服务端支持的列表）和 `requested`（被拒绝的版本），客户端据此重新选择（讲义练习 2）。
- `clientInfo` 是可选的（`is not None` 才检查），但一旦提供就必须结构完整。实测 `{"name": "x"}`（缺 version）返回 `-32602`。
- `isinstance(..., dict)` 同时排除了 `None`、字符串、列表等，比 `if not metadata` 更严格。

### 3.6 `handle`：信封校验与分发

```python
    def handle(self, message):
        if not isinstance(message, dict):
            return self._error(None, -32600, "request must be an object")

        request_id = message.get("id")
        if "id" not in message:
            return None
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            error_id = request_id if type(request_id) in (str, int) else None
            return self._error(error_id, -32600, "invalid JSON-RPC request")
        if type(request_id) not in (str, int):
            return self._error(None, -32600, "id must be a string or integer")

        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "params must be an object")

        metadata_error = self._validate_metadata(params, request_id)
        if metadata_error:
            return metadata_error
```

校验顺序与理由：

| 步骤 | 条件 | 结果 | 理由 |
|------|------|------|------|
| 1 | 消息不是对象（如 `[1, 2]`） | `-32600`，`id: null` | 连 id 都取不到 |
| 2 | 没有 `id` 键 | `None`（不响应） | notification 不需要响应；即使它不合法也无人接收错误 |
| 3 | `jsonrpc != "2.0"` 或 `method` 不是字符串 | `-32600`，id 合法就回显 | 信封非法，但尽量让对方能对上号 |
| 4 | `id` 不是 str/int（如 `None`、`1.0`、`True`） | `-32600`，`id: null` | MCP 要求 id 为字符串或整数 |
| 5 | `params` 不是对象 | `-32602` | 参数非法 |
| 6 | `_meta` 校验失败 | `-32602` / `-32022` | 无状态契约 |
| 7 | 方法不存在 | `-32601` | 见下 |

- `type(request_id) in (str, int)` 用的是 `type()` 而不是 `isinstance`：`bool` 是 `int` 的子类，`isinstance(True, int)` 为真，但 `type(True)` 是 `bool`，所以 `id: True` 会被拒绝（实测返回 `-32600`）。这是刻意的严格。
- ⚠️ 元数据校验在方法分发**之前**：调用一个不存在的方法且缺 `_meta`，返回的是 `-32602` 而不是 `-32601`（实测 `{"id": "abc", "method": "nope/x", "params": {}}` 得到 `-32602`）。这符合"先校验请求契约"的思路，但调试时要知道。
- ⚠️ `message.get("params", {})`：若显式传 `"params": null`，得到 `None`，被第 5 步拒绝（实测 `-32602`）。

### 3.7 各方法的实现

```python
        if method == "server/discover":
            result = self._complete(
                {
                    "supportedVersions": list(SUPPORTED_VERSIONS),
                    "capabilities": self._capabilities(),
                    "instructions": "Use add for arithmetic and request approval before delete_user.",
                },
                cacheable=True,
            )
```

- 对应讲义 discover 结果的 `supportedVersions`、`capabilities`、`ttlMs`、`cacheScope`、`_meta.serverInfo`；代码额外加了 `instructions`（给 host/模型的使用说明，讲义的 skill 文件也要求 discover 包含 instructions）。
- `capabilities` 中 `tools`、`resources`、`prompts` 都是空对象——表示"支持该原语、没有额外子特性"。

```python
        elif method == "tools/list":
            result = self._complete(
                {"tools": [
                    {"name": tool.name, "description": tool.description,
                     "inputSchema": tool.input_schema,
                     "annotations": ({"destructiveHint": True} if tool.destructive else {})}
                    for tool in sorted(self.tools.values(), key=lambda item: item.name)
                ]},
                cacheable=True,
            )
```

- 按名字排序：讲义 "A deterministic `tools/list` order plus a freshness hint lets clients cache discovery safely and improves prompt-cache stability"。Python 内部字段名是 `input_schema`（PEP 8 蛇形），对外输出 `inputSchema`（协议的驼峰），映射发生在这里。
- 破坏性工具带 `annotations.destructiveHint: true`，非破坏性的带空对象。

```python
        elif method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name not in self.tools:
                return self._error(request_id, -32602, "missing or unknown tool name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                return self._error(request_id, -32602, "arguments must be an object")
            tool = self.tools[name]
            try:
                output = json.dumps(tool.handler(**arguments))
            except Exception:
                return self._error(request_id, -32603, "tool handler failed")
            result = self._complete({"content": [{"type": "text", "text": output}], "isError": False})
```

- 结果是 `content` 数组，每项带 `type`；这里把 handler 返回的字典 `json.dumps` 成一段文本。
- `try` 同时包住"调用 handler"和"序列化结果"，两类失败都返回 `-32603`，且错误信息是固定的 "tool handler failed"，**不把异常细节泄露给客户端**（好习惯），但也**没有记录到 stderr**，排障时看不到原因。
- ⚠️ **没有按 `inputSchema` 校验参数**：`{"a": "40", "b": "2"}` 返回 `{"sum": "402"}`；`{"a": 1.5, "b": True}` 返回 `{"sum": 2.5}`；缺参数或多参数变成 `-32603`。参数错误本应是 `-32602`（测验 Q8、Q9）。
- ⚠️ `isError` 恒为 `False`：业务层面的失败（例如删除不存在的用户）没有表达途径。
- ⚠️ `delete_user` 标了 `destructiveHint`，但服务端照样直接执行——hint 只是给 host 的提示，审批必须在 host 实现，服务端还应有自己的授权检查。

```python
        elif method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str) or uri not in self.resources:
                return self._error(request_id, -32602, "missing or unknown resource URI")
            resource = self.resources[uri]
            try:
                text = resource.handler()
                if not isinstance(text, str):
                    raise TypeError("resource handler must return text")
            except Exception:
                return self._error(request_id, -32603, "resource handler failed")
            result = self._complete(
                {"contents": [{"uri": resource.uri, "mimeType": "text/plain", "text": text}]},
                cacheable=True,
            )
```

- 资源按 URI 精确匹配（没有实现 URI 模板）；返回 `contents` 数组，每项带 `uri`、`mimeType`、`text`。
- 主动检查返回值类型，返回非字符串时**自己抛 `TypeError`**，统一走 `-32603`（测试 `test_non_text_resource_and_prompt_results_are_internal_errors`）。
- ⚠️ `mimeType` 写死为 `text/plain`，而演示资源 `config://app` 返回的是 JSON 文本，更准确的是 `application/json`。

```python
        elif method == "prompts/get":
            ...
            rendered = prompt.handler(**arguments)
            ...
            result = self._complete(
                {"messages": [{"role": "user", "content": {"type": "text", "text": rendered}}]}
            )
        else:
            return self._error(request_id, -32601, f"unknown method: {method}")

        return {"jsonrpc": "2.0", "id": request_id, "result": result}
```

- `prompts/get` 返回的是**消息列表**（这里一条 user 消息），host 可以直接放进对话。`prompts/list` 把所有参数都标为 `required: True`（实测输出），没有可选参数的表达方式。
- 未知方法 `-32601` Method not found（测试 `test_unknown_method_uses_json_rpc_method_not_found`）。
- 最后统一包上 `jsonrpc` 与回显的 `id`——成功响应的 `id` 必须与请求一致，客户端靠它把响应对应到请求。

### 3.8 `MCPClient`：每次请求都重建 `_meta`

```python
class MCPClient:
    def __init__(self, server):
        self.server = server
        self._id = 0

    def request(self, method, params=None):
        self._id += 1
        request_params = dict(params or {})
        request_params["_meta"] = request_metadata()
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": request_params}
        )
        if response is None:
            raise RuntimeError("request did not receive a response")
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return response["result"]
```

- `dict(params or {})` **复制**一份参数，再加 `_meta`，不修改调用方传入的字典（对比第 13 节 `handle_request` 原地修改 `variables` 的问题）。
- 自增 `_id` 保证同一客户端的请求 id 唯一。
- 讲义："Do not cache this metadata only in a connection object. The server validates it on each request." 这里每次调用都重新生成 `_meta`。
- ⚠️ 错误被转成 `RuntimeError(message)`，**丢掉了 `code` 与 `data`**，调用方无法识别 `-32022` 并从 `supported` 中选择版本；`request_metadata()` 也总用固定版本。测验 Q10 给出了保留错误码、支持版本协商的 `NegotiatingClient`。
- ⚠️ 没有校验响应的 `id` 是否等于请求的 `id`（进程内调用不会错位，但网络传输时需要）。

### 3.9 演示服务端与 `main`

```python
server = MCPServer("demo-server")

@server.tool("add", "Add two integers and return the sum.", {...})
def add(a: int, b: int) -> dict[str, int]:
    return {"sum": a + b}

@server.tool("delete_user", "Delete a user by id. Mutating; requires approval.", {...}, destructive=True)
def delete_user(user_id: int) -> dict[str, Any]:
    return {"deleted": user_id, "note": "simulated"}

@server.resource("config://app", "app-config", "Application config as JSON text.")
def app_config() -> str:
    return json.dumps({"env": "prod", "region": "us-east-1"})

@server.prompt("code_review", "Review code in a language.", ["language", "code"])
def code_review(language: str, code: str) -> str:
    return f"You are a senior {language} reviewer. Review for correctness and style:\n\n{code}"
```

- 模块级的 `server` 在 `import main` 时就完成注册，测试直接复用它。
- 两个工具覆盖"安全的计算"和"破坏性操作"两类；资源用自定义 URI 方案 `config://`；prompt 有两个参数。
- `main()` 依次演示：discover → `tools/list` → `tools/call` → `resources/list` → `resources/read` → `prompts/get`，即讲义 Build It 第 3 步"optionally discover before listing"的流程。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不用 SDK，标准库手写 | 每个信封都可见、可测试 | 生产用官方 SDK，自己的代码只写工具逻辑 |
| 进程内传输（直接调用 `handle`） | 去掉网络细节，聚焦协议 | 没有 stdio 分帧、HTTP 头校验（`-32020`）、SSE；见阶段 13 · 09 |
| 每个请求独立校验 `_meta` | 讲义的无状态契约 | 每请求少量开销；换来任意实例可处理任意请求 |
| 先格式校验，再判断版本是否支持 | 区分 `-32602` 与 `-32022` | — |
| 用 `type()` 严格限制 id | 排除 `bool`、`float` | 对宽松客户端不友好，但符合规范 |
| 无 id 一律不响应 | notification 语义 | 无效的无 id 消息被静默丢弃，只能靠日志发现 |
| 装饰器注册 + 字典存储 | 简洁、函数仍可直接调用 | 同名注册静默覆盖；可加重复检测 |
| 列表排序 + 30 秒 private 缓存提示 | 确定性、安全的缓存 | `public` 能让共享缓存命中更高，但只适用于与调用者无关的结果 |
| handler 异常统一 `-32603`、不暴露细节 | 不泄露内部信息 | 参数错误也被报成内部错误；未写 stderr 日志 |
| 不校验 `inputSchema` | 代码短 | 类型错误静默产生错误结果；生产必须校验 |
| `destructiveHint` 只做标注 | 审批是 host 的职责 | 服务端仍需授权检查；可用 MRTR 二次确认 |
| 客户端把错误转成 `RuntimeError` | 演示简单 | 丢失错误码，无法版本协商 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在注解里使用尚未定义的名字和新式写法 |
| 内置泛型注解 | `dict[str, Any]`、`list[str]` | Python 3.9+ 可直接用内置类型做泛型 |
| `X \| None` | `dict[str, Any] \| None` | 联合类型，等价于 `Optional[...]` |
| `Callable` | `Callable[..., Any]`、`Callable[[], str]` | 可调用对象的类型；`...` 表示任意参数 |
| `@dataclass` | `class Tool:` | 自动生成构造函数等；有默认值的字段（`destructive`）放最后 |
| 仅限关键字参数 | `def request_metadata(*, client_name=...)`、`def tool(self, ..., *, destructive=False)` | `*` 之后的参数必须写成 `name=value` |
| 带参数的装饰器 / 闭包 | `def tool(...): def decorator(fn): ...; return decorator` | 外层接收配置，内层接收函数；内层能访问外层变量 |
| `@staticmethod` | `def _error(request_id, code, message, data=None)` | 不需要 `self` 的方法 |
| 字典展开 | `{"resultType": "complete", **payload, "_meta": ...}`、`{**metadata, "name": "broken"}` | 合并字典，后写的键覆盖先写的 |
| `dict.update` | `result.update({"ttlMs": 30_000, ...})` | 原地合并 |
| 数字下划线 | `30_000` | 提高可读性 |
| `isinstance` vs `type()` | `isinstance(metadata, dict)`；`type(request_id) in (str, int)` | `isinstance` 认子类；`type()` 精确匹配，用来排除 `bool` |
| `in` 判断键 | `"id" not in message`、`PROTOCOL_KEY not in metadata` | 判断"键存在"与"值为 None"是两回事 |
| 列表推导式 + `sorted(key=lambda)` | `[... for tool in sorted(self.tools.values(), key=lambda item: item.name)]` | 排序后转换 |
| 条件表达式 | `{"destructiveHint": True} if tool.destructive else {}` | 三元运算 |
| `**kwargs` 调用 | `tool.handler(**arguments)` | 把字典展开成关键字参数；键不匹配会 `TypeError` |
| `try` / `except Exception` | handler 调用处 | 捕获所有普通异常，转成协议错误 |
| 主动 `raise` | `raise TypeError("resource handler must return text")` | 把"返回值类型不对"变成统一的异常路径 |
| `json.dumps` | `json.dumps(tool.handler(**arguments))` | 序列化；遇到 `set` 等不可序列化对象抛 `TypeError` |
| f-string | `f"{PROTOCOL_KEY} is required"`、`f"unknown method: {method}"` | 格式化错误信息 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被测试导入时不执行 |
| 测试中的 `sys.path.insert` | `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` | 把 `code/` 加入模块搜索路径，使 `from main import ...` 可用 |
| `unittest.TestCase.subTest` | `with self.subTest(method=method):` | 一个测试里循环多个子用例，某个失败不影响其他子用例报告 |

---

## 6. 运行结果解读

`python3 main.py` 实际输出（Python 3.13，确定性）：

```text
Discovered demo-server (protocol 2026-07-28)

2 tool(s) discovered:
  - add: Add two integers and return the sum.
  - delete_user [destructive]: Delete a user by id. Mutating; requires approval.

Call add(40, 2) -> {"sum": 42}

1 resource(s): config://app
Read config://app -> {"env": "prod", "region": "us-east-1"}

Render code_review prompt -> You are a senior Python reviewer. Review for correctness and style:

x = 1
```

逐项解读：

- **第一行**正是讲义 Use It 所说的 "The first line should report discovery of `demo-server` at protocol `2026-07-28`"：服务端名来自 `result._meta.serverInfo.name`，版本来自 `supportedVersions[0]`。
- **工具清单**按名字排序（`add` 在 `delete_user` 前）；`[destructive]` 来自 `annotations.destructiveHint`。
- **工具调用**的结果是 JSON 文本 `{"sum": 42}`，放在 `content[0].text` 中。
- **资源读取**返回配置的 JSON 文本；**prompt** 渲染为一条 user 消息（打印时截取前 80 个字符）。

为本讲解补充的实验（均已实际运行）：

| 输入 | 返回 |
|------|------|
| `add` 参数 `{"a": "40", "b": "2"}` | 成功，`{"sum": "402"}` ← 未做 schema 校验 |
| `add` 参数 `{"a": 1, "b": 2, "c": 3}` | `-32603 tool handler failed` |
| `id: True` 或 `id: 1.0` | `-32600 id must be a string or integer`，`id: null` |
| 未知方法 + 缺 `_meta` | `-32602 params._meta is required`（元数据先校验） |
| `params: null` | `-32602 params must be an object` |
| 消息是列表 `[1, 2]` | `-32600 request must be an object` |
| `clientInfo` 只有 name | `-32602 clientInfo must contain name and version` |
| `server/discover` 完整结果 | `resultType`、`supportedVersions`、`capabilities`、`instructions`、`_meta`、`ttlMs: 30000`、`cacheScope: "private"` |

---

## 7. 动手改一改

1. **讲义练习 1**：注册 `subtract` 工具，确认 `tools/list` 顺序变为 `add, delete_user, subtract`；在测试里补一个断言。
2. **讲义练习 2**：手工构造缺少版本键的请求确认 `-32602`；再发送 `2025-11-25` 确认 `-32022` 且 `data.requested` 回显该版本；实现测验 Q10 的 `NegotiatingClient`，让它根据 `supported` 自动切换版本。
3. **参数校验**：实现测验 Q9 的 `validate_arguments`，在 `tools/call` 和 `prompts/get` 调用 handler 前执行，参数错误返回 `-32602`；相应修改 `test_handler_key_and_type_errors_are_internal_errors`，并新增"字符串参数被拒绝"的测试。
4. **讲义练习 4（MRTR）**：按测验 Q11 让 `delete_user` 首次返回 `input_required`，用签名的 `requestState` 保持服务端无状态；补充"篡改 state""参数不一致""用户拒绝"三个负向测试，并思考如何防重放。
5. **HTTP 传输**：用标准库 `http.server` 包一层 POST 端点：校验 `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 与 body 一致，不一致返回 HTTP 400 和 `-32020`；notification 返回 202 无响应体；绑定 `127.0.0.1` 并校验 `Origin`。
6. **讲义练习 3（state handle）**：实现 `create_draft` / `update_draft`，`draftId` 用 `secrets.token_urlsafe` 生成，每次更新都校验归属。

---

## 8. 常见坑

- **只在第一次请求带版本**：这是旧版握手思维。无状态协议下每个请求都必须带完整 `_meta`。
- **把"缺字段"和"版本不支持"混为一谈**：前者 `-32602`，后者 `-32022` 且必须带 `supported`/`requested`。
- **用 `message.get("id") is None` 判断 notification**：`{"id": null}` 是带非法 id 的请求，不是 notification；要判断键是否存在。
- **用 `isinstance(x, int)` 校验整数**：`True` 也会通过；用 `type()` 或额外排除 `bool`。
- **信任 `inputSchema`**：schema 是发布给模型的说明，不是服务端的校验；模型生成的参数是不可信输入。
- **把客户端错误报成内部错误**：调用方无法区分"改参数重试"和"服务端故障"。
- **把 `destructiveHint` 当安全机制**：它只是提示，审批在 host，授权在服务端。
- **共享缓存用 `public` 缓存了因人而异的结果**：工具或资源按权限过滤时必须 `private`。
- **stdio 服务端往 stdout 打印调试信息**：会破坏 JSON-RPC 流；诊断写 stderr（讲义 Step 5）。
- **客户端吞掉错误码**：本节 `MCPClient` 只保留 message，版本协商和重试策略都无从实现。

---

## 9. 测试在验证什么

测试文件：`tests/test_main.py`，共 20 个测试（`unittest.TestCase`），其中两个用 `subTest` 包含 9 个子用例。

**运行方式**（在 `code/` 目录下）：

```bash
python3 -m unittest discover tests -v
python3 -m pytest -q          # 需先安装 pytest
```

**实际运行结果**：`unittest` 输出 `Ran 20 tests in 0.001s  OK`；`pytest`（为验证另行安装）输出 `20 passed, 9 subtests passed in 0.02s`。

测试文件开头用 `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` 把 `code/` 加入搜索路径，再 `from main import ...`；辅助函数 `envelope(method, params, request_id)` 生成**不带 `_meta`** 的基础信封，需要时由测试显式加入。

| 测试 | 验证的性质 | 对应讲义/规则 |
|------|-----------|--------------|
| `test_request_metadata_carries_version_capabilities_and_identity` | `request_metadata()` 包含版本、空能力对象、客户端名 | 每请求元数据 |
| `test_discover_returns_identity_capabilities_and_cache_policy` | discover 结果为 complete、版本列表正确、带服务端名、`ttlMs > 0`、`cacheScope` 合法 | `server/discover` |
| `test_missing_metadata_is_rejected` | 无 `_meta` → `-32602` | 缺 `_meta` 为畸形请求 |
| `test_missing_protocol_version_is_invalid_params` | 缺版本键 → `-32602`，且错误**不含** `data` | 区分 `-32602` 与 `-32022` |
| `test_non_string_protocol_version_is_invalid_params` | 版本是整数 `20260728` → `-32602` | 类型错误为畸形 |
| `test_missing_client_capabilities_is_invalid_params` | 缺能力键 → `-32602` | 能力为必需字段 |
| `test_unsupported_protocol_version_returns_spec_error` | `2025-11-25` → `-32022`，`supported` 与 `requested` 正确 | 版本不支持错误 |
| `test_tool_list_is_deterministic_and_cacheable` | 工具顺序为 `["add", "delete_user"]`，`cacheScope == "private"` | 确定性列表与缓存提示 |
| `test_tool_call_returns_typed_complete_result` | `add(20, 22)` 结果为 complete，文本 `{"sum": 42}`，带服务端身份 | 显式结果 |
| `test_resource_read_is_cacheable` | 资源读取为 complete 且 private | 读取结果带缓存提示 |
| `test_resource_list_includes_required_name` | 资源列表项包含 `name` | 资源元数据 |
| `test_every_success_result_is_typed_and_identifies_server` | 7 个方法（`subTest`）的成功结果都有 `resultType: complete` 和服务端名 | "Every core result has `resultType`" + 每个结果带 serverInfo |
| `test_notification_is_ignored_without_a_json_rpc_response` | 无 id 的 `notifications/cancelled` → `None` | notification 不响应 |
| `test_idless_invalid_envelopes_receive_no_response` | 无 id 且 `jsonrpc` 错误、或无 method 的消息 → `None`（2 个 `subTest`） | 无 id 即不响应，即使信封非法 |
| `test_handler_key_and_type_errors_are_internal_errors` | handler 内部 `KeyError`、缺参数导致的 `TypeError` → `-32603` | handler 失败映射为内部错误 |
| `test_non_serializable_tool_result_is_an_internal_error` | 返回含 `set` 的字典 → `-32603 tool handler failed` | 序列化失败也在 try 范围内 |
| `test_non_text_resource_and_prompt_results_are_internal_errors` | 资源与 prompt 返回非字符串 → `-32603`，信息分别为 "resource handler failed"、"prompt handler failed" | 返回值类型检查 |
| `test_null_request_id_is_invalid` | `id: None` → `-32600`，响应 `id` 为 `None` | id 必须是字符串或整数 |
| `test_wrong_json_rpc_version_is_invalid` | `jsonrpc: "1.0"`、`id: 12` → `-32600`，且回显 `id: 12` | 信封非法但 id 合法时回显 |
| `test_unknown_method_uses_json_rpc_method_not_found` | 未知方法 → `-32601`，回显 `id: 9` | Method not found |

测试设计的亮点与可补充之处：

- **负向测试占多数**（20 个中 13 个验证错误或无响应路径）——协议实现的正确性主要体现在"拒绝什么"。讲义 skill 文件的验证计划也要求覆盖 "notifications producing no JSON-RPC response, malformed envelopes and request IDs, metadata rejection..."。
- 多个测试在**局部新建** `MCPServer` 实例（`"handler-errors"`、`"serialization-errors"`）注册故意出错的原语，避免污染模块级的 `server`。
- `test_handler_key_and_type_errors_are_internal_errors` 把"缺少必需参数 → `-32603`"固化为预期行为。如果按测验 Q9 加入参数校验（缺参数改为 `-32602`），需要同步修改这个测试——这是一个"测试固化了有争议的行为"的例子。
- **尚未覆盖**：参数类型错误（`"40"` 被接受）、`id: True`/`1.0`、`params: null`、`clientInfo` 结构不完整、`destructiveHint` 注解输出、`prompts/list` 内容、`prompts/get` 缺参数。可按第 7 节练习逐一补上。
