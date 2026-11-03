# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 06 节 MCP 基础：无状态请求与 JSON-RPC ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v`（均在 `code/` 目录下） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`typing`），无需网络、无需 MCP SDK

---

## 1. 这份代码在考察什么

这份代码不依赖任何 MCP 框架，用 250 行纯 Python 把 MCP `2026-07-28` 的"一个请求的生命周期"摊开给你看：

1. **JSON-RPC 2.0 信封**：请求、成功响应、错误响应、通知各长什么样，`id` 只是配对用的。
2. **每请求元数据**：`params._meta` 中的 `protocolVersion`（必填）、`clientCapabilities`（必填）、`clientInfo`（推荐）。
3. **无握手的版本协商**：`server/discover` 返回支持的版本；不支持的版本返回 `-32022` 并在 `data` 里列出 `supported`。
4. **现代结果的形状**：`resultType: "complete"`、结果 `_meta` 中的 `serverInfo`、可缓存结果的 `ttlMs` / `cacheScope`、确定性的列表顺序。
5. **协议时代识别**：`trace_message` 区分 modern / legacy / invalid 消息，对应 `outputs/` 中的请求追踪 skill。

> 一句话：**每个请求都要"自己说清楚自己是谁、要什么、说哪个版本的话"，server 处理完就忘**。同时请留意代码在校验顺序、参数校验和浅拷贝上的几处简化——它们正好是"无状态"这个主题最容易出错的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` / `*_KEY` 常量 | 模块常量 | 协议版本与 `_meta` 中的四个命名空间键 | 每请求元数据 |
| `CLIENT_INFO` / `SERVER_INFO` / `SERVER_CAPABILITIES` | 模块常量 | 客户端身份、server 身份、server 能力 | 身份与能力 |
| `TOOLS` | 模块常量 | 两个工具定义（故意按"非字母序"排列） | Tools primitive |
| `Trace` | 冻结 dataclass | 一条消息的追踪结果：kind / method / era / detail | 消息审计 |
| `request_meta` / `make_request` | 函数 | 构造带 `_meta` 的现代请求 | 自描述请求 |
| `rpc_error` | 函数 | 构造 JSON-RPC 错误响应 | 错误信封 |
| `complete_result` | 函数 | 构造 `resultType: "complete"` 的结果，附 server 身份与可选缓存提示 | 完整结果 |
| `validate_request` | 函数 | 按顺序校验信封与 `_meta`，返回错误或 `None` | 请求生命周期 2–5 步 |
| `dispatch` | 函数 | 校验后按 `method` 路由到 discover / list / call | 请求生命周期 6–8 步 |
| `trace_message` / `show` | 函数 | 识别消息种类与时代并打印 | 追踪器 |
| `main` | 函数 | 依次处理 4 个请求并打印请求与响应 | 演示 |

数据流：`main` → `make_request`（构造 4 个独立请求）→ `show(请求)` → `dispatch` → `validate_request` →（通过）按 method 生成 `complete_result` /（失败）`rpc_error` → `show(响应)` → 打印"传输关闭，没有协议会话"。

---

## 3. 逐段精讲

### 3.1 常量：命名空间键与"故意打乱"的工具表

```python
PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [PROTOCOL_VERSION]
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"
```

- `_meta` 中的键带反向域名前缀 `io.modelcontextprotocol/`，表示"这是协议保留的键"，与扩展或应用自定义的键区分开，避免冲突。
- 协议版本是**日期字符串**，比较时用 `in SUPPORTED_VERSIONS` 做精确匹配，不做大小比较。
- `TOOLS` 中 `notes_search` 在前、`notes_list` 在后——不是字母序。这样 `tools/list` 中的 `sorted` 才有可见效果（见 3.6），讲义练习 3"反转注册表后顺序不变"其实已经被这个定义顺序预先演示了。
- `SERVER_CAPABILITIES = {"tools": {"listChanged": False}}`：声明只支持 tools，且不会推送列表变更。

### 3.2 `Trace`：冻结的 dataclass

```python
@dataclass(frozen=True)
class Trace:
    kind: str
    method: str
    era: str
    detail: str
```

- `@dataclass` 根据类型注解自动生成 `__init__`、`__repr__`、`__eq__`；`frozen=True` 让实例不可修改（赋值会抛 `FrozenInstanceError`），适合表示"一次观测的结果"。
- `era` 取值为 `"modern"`、`"legacy"`、`"invalid"`、`"unknown"`，对应讲义"协议时代"的概念。

### 3.3 构造请求：每一个请求都重复 `_meta`

```python
def request_meta(version=PROTOCOL_VERSION, capabilities=None, include_client_info=True):
    meta = {
        VERSION_KEY: version,
        CAPABILITIES_KEY: {} if capabilities is None else capabilities,
    }
    if include_client_info:
        meta[CLIENT_INFO_KEY] = CLIENT_INFO.copy()
    return meta


def make_request(request_id, method, params=None, *, version=PROTOCOL_VERSION, capabilities=None):
    body_params = dict(params or {})
    body_params["_meta"] = request_meta(version, capabilities)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}
```

- **为什么 `capabilities=None` 而不是 `capabilities={}`**：可变对象作为默认参数会在所有调用之间共享（Python 经典陷阱）。用 `None` 作哨兵、函数体内再新建 `{}`，每次调用都得到新 dict。
- 空的 `{}` 也是合法的 capabilities——"我什么可选能力都不支持"。讲义的关键是**必须出现**，而不是必须非空。
- `dict(params or {})`：浅拷贝调用者传入的 params，再往里加 `_meta`，避免修改调用者的对象。
- `*` 之后的 `version`、`capabilities` 是**仅限关键字参数**，调用时必须写 `version="2027-01-01"`，防止位置参数传错。
- ⚠️ `make_request` 没有暴露 `include_client_info`，想构造"不带 clientInfo"的请求只能事后 `del`（测试里就是这么做的）。讲义练习 5 可以顺手把这个参数透传出来。

### 3.4 `rpc_error` 与 `complete_result`：两种响应形状

```python
def rpc_error(request_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def complete_result(payload, *, ttl_ms=None, cache_scope=None):
    result = {
        "resultType": "complete",
        **payload,
        "_meta": {SERVER_INFO_KEY: SERVER_INFO.copy()},
    }
    if ttl_ms is not None:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = cache_scope or "private"
    return result
```

- 错误响应用 `error`、成功响应用 `result`，两者互斥；`data` 可选，只有 `-32022` 这类需要附带结构化信息的错误才带。
- `{"resultType": ..., **payload, "_meta": ...}`：字典解包，**后写的键覆盖先写的**。所以即使 `payload` 里有 `_meta`，也会被 server 身份覆盖；`payload` 里若有 `resultType` 则会覆盖 `"complete"`。
- `if ttl_ms is not None`：用 `is not None` 而不是 `if ttl_ms`，这样 `ttl_ms=0`（讲义说的安全默认）也会被正确写出。
- `cache_scope or "private"`：调用方没指定作用域时退回安全默认 `"private"`，与讲义"A safe default is `ttlMs: 0` and `cacheScope: "private"`"一致。

### 3.5 `validate_request`：生命周期第 2–5 步

```python
def validate_request(message):
    request_id = message.get("id")
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return rpc_error(request_id, -32600, "Invalid Request")
    params = message.get("params")
    if not isinstance(params, dict):
        return rpc_error(request_id, -32602, "params must be an object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return rpc_error(request_id, -32602, "params._meta is required")
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        return rpc_error(request_id, -32602, f"{VERSION_KEY} is required")
    if version not in SUPPORTED_VERSIONS:
        return rpc_error(request_id, -32022, "Unsupported protocol version",
                         {"requested": version, "supported": SUPPORTED_VERSIONS.copy()})
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        return rpc_error(request_id, -32602, f"{CAPABILITIES_KEY} is required")
    client_info = meta.get(CLIENT_INFO_KEY)
    if client_info is not None and (...name/version 不是字符串...):
        return rpc_error(request_id, -32602, f"{CLIENT_INFO_KEY} is malformed")
    return None
```

错误码对照：

| 错误码 | 名称 | 本函数中的触发条件 |
|-------|------|------------------|
| `-32600` | Invalid Request | `jsonrpc` 不是 `"2.0"` 或 `method` 不是字符串 |
| `-32602` | Invalid params | `params` 非对象、缺 `_meta`、缺版本、缺 capabilities、clientInfo 格式错 |
| `-32022` | Unsupported protocol version | 版本是字符串但不在支持列表中 |

- 函数的约定是"**返回错误响应或 `None`**"——`None` 表示通过。调用方 `if invalid is not None: return invalid`，这是一种不用异常的"提前返回"风格。
- 每一步都用 `isinstance` 检查类型，而不只是检查"存在"：`_meta` 是字符串、capabilities 是列表都会被拒绝。网络输入不可信，类型检查是第一道防线。
- `clientInfo` 的处理正好体现"推荐但非必填"：缺失放行，存在但格式不对拒绝。
- ⚠️ **与讲义顺序不一致**：讲义第 3 步"要求版本字符串**和** capability 对象（`-32602`）"在第 5 步"拒绝不支持的版本（`-32022`）"之前；代码却在检查 capabilities 前就做了版本判断。实测：版本 `2027-01-01` 且缺 capabilities 的请求返回 `-32022`，按讲义应为 `-32602`。客户端会据此换版本重试，再失败一次。修正方法是把版本支持性判断移到所有结构校验之后（测验 Q9 给出了改写并验证）。
- ⚠️ 没有校验 `id` 的类型：`make_request(None, "tools/list")` 会被当作正常请求处理并返回 `id: null` 的结果。JSON-RPC 不鼓励 `null` id，因为它和"无法确定 id 的错误响应"混淆。
- ⚠️ 讲义第 4 步（HTTP 头与 body 一致性，`-32020`）在这里没有实现——本节没有传输层，第 09 节补上。

### 3.6 `dispatch`：路由与三个方法

```python
def dispatch(message):
    if "id" not in message:
        return None
    invalid = validate_request(message)
    if invalid is not None:
        return invalid
    request_id = message["id"]
    method = message["method"]
    params = message["params"]
    if method == "server/discover":
        result = complete_result({...}, ttl_ms=3_600_000, cache_scope="public")
    elif method == "tools/list":
        result = complete_result(
            {"tools": sorted(TOOLS, key=lambda tool: tool["name"])},
            ttl_ms=30_000, cache_scope="public",
        )
    elif method == "tools/call":
        ...
    else:
        return rpc_error(request_id, -32601, f"Method not found: {method}")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
```

- **没有 `id` 就是 notification**，不返回任何东西（返回 `None`，`main` 里也就不打印响应）。
- **`server/discover`**：返回 `supportedVersions`、`capabilities`、`instructions`（给模型/host 的使用说明），缓存 1 小时（`3_600_000` 毫秒）且 `public`——这些信息对所有调用者相同，适合共享缓存。
- **`tools/list`**：按 `name` 排序，`notes_list` 排在 `notes_search` 前（`'l' < 's'`）。缓存 30 秒、`public`。确定顺序的意义：等价响应得到相同的缓存键，进入模型上下文的工具顺序也稳定。
- **`tools/call`**：
  - `notes_list` 直接返回固定文本；
  - `notes_search` 要求 `arguments.query` 是字符串，返回 `Found notes matching 'JSON-RPC'`（`!r` 用 `repr` 给字符串加了引号）；
  - 其它情况返回 `isError: True` 的**成功结果**（注意：是 `result`，不是 `error`）；
  - `tools/call` 不传 `ttl_ms`，所以没有缓存提示——动作的结果不应被缓存。
- **未知方法**：`-32601 Method not found`。例如本 server 不支持 `resources/list`，实测返回 `{"code": -32601, "message": "Method not found: resources/list"}`。
- ⚠️ **`arguments` 不是 dict 时会崩溃**：`{"name": "notes_search", "arguments": "x"}` 触发 `AttributeError: 'str' object has no attribute 'get'`（已实测），`dispatch` 没有任何异常兜底。
- ⚠️ **未知工具与参数错误混为一谈**：都返回 `"Unknown or invalid tool: <name>"` + `isError: True`。工具名未知更适合作为协议错误；业务参数缺失则应给模型一个可执行的修正提示（测验 Q10）。
- ⚠️ **浅拷贝泄漏**：`SERVER_CAPABILITIES.copy()` 只复制外层，内层 `{"listChanged": False}` 与全局共享。实测：修改某次 discover 结果中的 `capabilities["tools"]["listChanged"] = True` 后，全局 `SERVER_CAPABILITIES` 也变成了 `True`，之后所有请求都会看到——这恰恰是本节要消灭的"跨请求状态"。`sorted(TOOLS, ...)` 同理只新建了列表，工具 dict 仍是全局对象。应使用 `copy.deepcopy`（测验 Q11）。
- ⚠️ 讲义第 7 步（鉴权）未实现；"检查所需 capabilities"也没有体现——本节的方法都不依赖任何客户端能力，所以收到的 capabilities 只被校验了类型，没有被使用。

### 3.7 `trace_message`：识别消息种类与协议时代

```python
def trace_message(message):
    if "method" in message and "id" in message:          # 请求
        method = str(message["method"])
        if method == "initialize":
            return Trace("request", method, "legacy", "connection-scoped handshake")
        params = message.get("params", {})
        meta = params.get("_meta", {}) if isinstance(params, dict) else {}
        if isinstance(meta, dict) and VERSION_KEY in meta and CAPABILITIES_KEY in meta:
            detail = f"version={meta[VERSION_KEY]} capabilities=current-request"
            return Trace("request", method, "modern", detail)
        return Trace("request", method, "invalid", "missing modern request metadata")
    if "result" in message or "error" in message:         # 响应
        if "error" in message:
            return Trace("response", "error", "unknown", f"code={message['error']['code']}")
        result = message["result"]
        era = "modern" if result.get("resultType") else "legacy"
        return Trace("response", "result", era, f"resultType={result.get('resultType', 'absent')}")
    if "method" in message:                               # 通知
        return Trace("notification", str(message["method"]), "unknown", "no response expected")
    return Trace("unknown", "", "invalid", "not a JSON-RPC message")
```

- 判断顺序：有 `method` 且有 `id` → 请求；有 `result`/`error` → 响应；只有 `method` → 通知；其余 → 非法。
- 请求的时代判断：`initialize` → legacy；`_meta` 同时含版本和 capabilities → modern；否则 invalid。只看"键在不在"，不看值是否合法——这是追踪器（观察者）而不是校验器。
- 响应的时代判断：有 `resultType` → modern，否则 legacy。
- ⚠️ 与 `outputs/skill-mcp-handshake-tracer.md` 的规则有两处不符：`notifications/initialized` 被标为 `unknown`（skill 要求标为 legacy）；`-32022` 被标为 `unknown`（skill 要求"Interpret `-32022` as modern evidence"）。
- ⚠️ 对不可信输入不够稳健：`result` 若不是 dict、`error` 若缺 `code`，会抛异常。

### 3.8 `show` 与 `main`

```python
def show(message):
    trace = trace_message(message)
    print(f"[{trace.kind}/{trace.era}] {trace.method}: {trace.detail}")
    print(json.dumps(message, indent=2, sort_keys=True))
```

- `json.dumps(..., indent=2, sort_keys=True)`：缩进 2 格、**按键排序**输出，所以你会看到 `_meta` 排在最前（`_` 的 ASCII 码 95 小于小写字母）、`resultType` 排在 `supportedVersions` 前。这只是打印顺序，与协议无关。
- `main` 构造 4 个**相互独立**的请求：discover、tools/list、tools/call、以及一个版本为 `2027-01-01` 的 tools/list。每个都完整携带 `_meta`，server 不依赖任何前序请求。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不用 MCP SDK，手写 dict | 让每个字段都可见 | 生产用官方 SDK，由框架处理信封、校验和序列化 |
| 校验函数返回"错误或 None" | 校验与分发解耦，便于单测 | 规模大时用 schema 校验库（如 Pydantic）生成一致的错误 |
| `capabilities=None` 哨兵 | 避免可变默认参数共享 | — |
| 缓存提示只给 discover 和 list | 动作结果不应缓存 | 按用户过滤的列表必须改为 `private` |
| 版本检查在 capabilities 检查之前 | 写法直观 | 与讲义顺序不一致，错误证据被掩盖；应先完成全部结构校验 |
| 未知工具 / 参数错误返回 `isError` | 简化分支 | 协议错误与执行错误混淆；生产应区分并给出可执行提示 |
| 浅拷贝全局常量 | 写起来短 | 内层对象共享，形成跨请求状态泄漏；用 `deepcopy` 或不可变结构 |
| 无异常兜底 | 演示代码 | 生产需要捕获 handler 异常并返回 `-32603`，保证单个坏请求不拖垮进程 |
| `trace_message` 只看键是否存在 | 追踪器应宽容地分类 | 需补 legacy 通知与现代错误码的识别，并对非 dict 输入做防护 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，可在旧版本 Python 中使用 `dict[str, Any] \| None` 等新写法 |
| 类型注解 | `def make_request(request_id: int \| str, ...) -> dict[str, Any]` | `X \| Y` 表示"X 或 Y"；`Any` 表示任意类型；注解不影响运行 |
| `@dataclass(frozen=True)` | `class Trace` | 自动生成构造函数等；`frozen` 使实例不可变 |
| 默认参数 + `None` 哨兵 | `capabilities: dict \| None = None` | 避免可变默认值（如 `{}`）在调用间共享 |
| 仅限关键字参数 `*` | `def make_request(request_id, method, params=None, *, version=...)` | `*` 之后的参数必须用 `名字=值` 传入 |
| 条件表达式 | `{} if capabilities is None else capabilities` | 一行内的 if/else |
| `or` 取默认值 | `params or {}`、`cache_scope or "private"` | 左边为假（`None`、空 dict、空串）时取右边 |
| 字典解包 `**` | `{"resultType": "complete", **payload, "_meta": ...}` | 把另一个 dict 的键值展开进来，后出现的键覆盖前面的 |
| `dict(...)` / `.copy()` | `dict(params or {})`、`SERVER_INFO.copy()` | 浅拷贝：只复制一层 |
| 数字下划线 | `3_600_000`、`30_000` | 下划线只为可读，等于 3600000 |
| `isinstance` | `isinstance(meta, dict)` | 运行时类型检查，校验不可信输入 |
| `dict.get(key, default)` | `params.get("arguments", {})` | 键不存在时返回默认值而不是抛 `KeyError` |
| `in` 判断键 | `"id" not in message` | 判断 dict 是否含某个键 |
| `sorted` + `lambda` | `sorted(TOOLS, key=lambda tool: tool["name"])` | 返回新列表，按 key 函数的结果排序 |
| f-string 与 `!r` | `f"Found notes matching {arguments['query']!r}"` | `!r` 调用 `repr()`，字符串会带引号 |
| `json.dumps` | `json.dumps(message, indent=2, sort_keys=True)` | 序列化为 JSON 文本，缩进并按键排序 |
| `del` | 测试中 `del message["params"]["_meta"][...]` | 删除 dict 中的键 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`；被测试 `import` 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，输出截取）：

```text
MCP 2026-07-28 stateless request trace

[request/modern] server/discover: version=2026-07-28 capabilities=current-request
{ "id": 1, "jsonrpc": "2.0", "method": "server/discover",
  "params": { "_meta": { ...clientCapabilities: {}, clientInfo: {...}, protocolVersion: "2026-07-28" } } }
[response/modern] result: resultType=complete
{ "id": 1, "jsonrpc": "2.0",
  "result": { "_meta": { "io.modelcontextprotocol/serverInfo": { "name": "lesson-06-notes", "version": "1.0.0" } },
              "cacheScope": "public",
              "capabilities": { "tools": { "listChanged": false } },
              "instructions": "Use notes_list for titles and notes_search for keywords.",
              "resultType": "complete",
              "supportedVersions": [ "2026-07-28" ],
              "ttlMs": 3600000 } }

[request/modern] tools/list: ...
[response/modern] result: resultType=complete
  "tools": [ { "name": "notes_list", ... }, { "name": "notes_search", ... } ], "ttlMs": 30000, "cacheScope": "public"

[request/modern] tools/call: ...  "arguments": { "query": "JSON-RPC" }, "name": "notes_search"
[response/modern] result: resultType=complete
  "content": [ { "text": "Found notes matching 'JSON-RPC'", "type": "text" } ], "isError": false

[request/modern] tools/list: version=2027-01-01 capabilities=current-request
[response/unknown] error: code=-32022
{ "error": { "code": -32022,
             "data": { "requested": "2027-01-01", "supported": [ "2026-07-28" ] },
             "message": "Unsupported protocol version" },
  "id": 4, "jsonrpc": "2.0" }

Transport closes. No protocol session was created or terminated.
```

逐项解读（对应讲义"Watch for three invariants"）：

- **每个请求都重复 `_meta`**：4 个请求的 `_meta` 完全相同（除第 4 个的版本），没有任何一个依赖前一个。
- **每个成功结果都是 complete 且带 server 身份**：3 个成功响应都有 `resultType: "complete"` 和 `serverInfo`。
- **列表结果有序且带缓存提示**：`notes_list` 排在 `notes_search` 前，尽管定义顺序相反；`ttlMs: 30000`、`cacheScope: "public"`。
- **discover 的缓存时间更长**：1 小时，因为版本与能力很少变化。
- **`tools/call` 没有 `ttlMs`**：动作结果不可缓存。
- **第 4 个请求**：追踪器把请求标成 `modern`（它确实带了现代元数据，只是版本不受支持），server 返回 `-32022` 并在 `data.supported` 里告诉客户端应改用 `2026-07-28`；客户端应用**新的 id** 重试。响应被追踪器标为 `unknown`——见 3.7 的不足。
- **最后一行**：关闭传输不等于结束会话，因为根本没有会话。

此外我们额外验证了几条边界行为（均为实测）：缺 capabilities 且版本错误 → `-32022`（应为 `-32602`）；`arguments` 为字符串 → `AttributeError` 崩溃；请求 `resources/list` → `-32601`；修改 discover 结果的内层 dict 会改动全局 `SERVER_CAPABILITIES`。

---

## 7. 动手改一改

1. **讲义练习 1、2**：把第 2 个请求的版本改成 `2027-01-01`，确认 `-32022`；再删掉第 2 个请求的 `clientCapabilities`，确认得到 `-32602`、server 没有沿用第 1 个请求的能力。然后**同时**做这两个修改，观察返回的是哪个错误码，并按讲义顺序修正 `validate_request`（测验 Q9）。
2. **讲义练习 3、4**：把 `TOOLS` 反转后运行，确认输出顺序不变；把 `tools/list` 的 `cache_scope` 改成 `"private"`，写一段说明：如果将来按用户角色过滤工具列表，为什么必须是 `private`。
3. **讲义练习 5**：给 `make_request` 增加 `include_client_info: bool = True` 参数并透传给 `request_meta`，写测试验证不带 clientInfo 仍得到 complete 结果，以及 `clientInfo={"name": "x"}` 得到 `-32602`。
4. **修复 `tools/call`**：`arguments` 非对象和未知工具返回 JSON-RPC 错误；`notes_search` 缺 `query` 时返回带修正提示的 `isError` 结果；再给 `dispatch` 加一个 `try/except`，handler 抛异常时返回 `-32603`。
5. **修复浅拷贝**：用 `copy.deepcopy` 替换 discover 和 list 分支中的拷贝，写一个测试"修改返回结果后，再次 dispatch 得到的结果不变"。
6. **进阶**：让 `trace_message` 把 `notifications/initialized` 识别为 legacy、把 `-32020/-32021/-32022` 识别为 modern，并在 `main` 末尾输出 modern / legacy / invalid / ambiguous 的计数，向 `outputs/skill-mcp-handshake-tracer.md` 要求的输出格式靠拢。

---

## 8. 常见坑

- **把 `id` 当成会话**：`id` 只用于把响应配回请求；重试时要用**新的** id。
- **用可变对象作默认参数**：`def f(capabilities={})` 会让所有调用共享同一个 dict，正是"跨请求状态"的经典来源。
- **浅拷贝全局配置再返回**：调用方修改响应会改到全局（本节的 `SERVER_CAPABILITIES` 就有此问题）。
- **只检查键存在，不检查类型**：`_meta` 是字符串、capabilities 是列表都应拒绝。
- **校验顺序随意**：版本协商放在结构校验前，会让客户端用错误的方式"修复"请求。
- **把执行错误和协议错误混用**：`isError` 是给模型看的，协议错误是给客户端程序看的。
- **给按用户区分的结果标 `public`**：共享缓存会把一个用户的结果发给另一个用户。
- **`ttl_ms=0` 被当成"没设置"**：判断时要用 `is not None`，不要用真值判断。
- **以为 `json.dumps(sort_keys=True)` 的顺序是协议要求**：它只影响打印；协议要求确定的是**列表元素**的顺序。

---

## 9. 测试在验证什么

`tests/test_main.py` 用标准库 `unittest`，通过 `sys.path.insert(0, ...)` 把 `code/` 加入导入路径后 `import main`。在 `code/` 目录下运行 `python3 -m unittest discover tests -v`，实测 **7 个测试全部通过**（`Ran 7 tests in 0.000s, OK`）。

| 测试 | 验证的性质 | 对应讲义 |
|------|-----------|---------|
| `test_request_repeats_required_metadata` | `make_request` 生成的 `_meta` 含版本、传入的 capabilities 和 clientInfo | 每请求元数据 |
| `test_discover_is_complete_and_identifies_server` | discover 结果为 complete、`supportedVersions == ["2026-07-28"]`、带 `serverInfo` | `server/discover` 与 server 身份 |
| `test_list_is_cacheable_and_deterministic` | 工具名已排序、`ttlMs == 30000`、`cacheScope == "public"` | 可缓存结果与确定顺序 |
| `test_missing_capabilities_are_not_inferred` | 删除 capabilities 后返回 `-32602` | 不从前序请求推断能力 |
| `test_unsupported_version_advertises_supported_versions` | 版本 `2027-01-01` → `-32022`，`data` 含 requested 与 supported | 无握手的版本协商 |
| `test_client_info_is_recommended_not_required` | 删除 clientInfo 仍得到 complete 结果 | clientInfo 是推荐项（讲义练习 5） |
| `test_tracer_distinguishes_modern_and_legacy` | 现代请求标 modern，`initialize` 标 legacy | 协议时代识别 |

测试没有覆盖、但值得补充的：

- "版本错误 + 缺 capabilities"同时出现时的错误码（会暴露 3.5 的顺序问题）；
- `tools/call` 的非法 `arguments`（会暴露崩溃）；
- 修改返回结果不影响后续请求（会暴露浅拷贝问题）；
- `test_missing_capabilities_are_not_inferred` 名字说的是"不推断"，但它只发了一个请求。更有说服力的写法是先发一个带 capabilities 的请求、再发一个不带的，证明第二个没有继承第一个。
