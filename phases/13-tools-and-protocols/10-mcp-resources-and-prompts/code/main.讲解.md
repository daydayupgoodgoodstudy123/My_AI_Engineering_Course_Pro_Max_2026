# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 10 节 MCP Resources 与 Prompts：无状态服务端的可寻址上下文 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`typing`），无需网络、无需 MCP SDK

---

## 1. 这份代码在考察什么

这是一个**不走真实网络**的 MCP 服务端模拟器，按 2026-07-28 修订版的"无状态"契约，用纯 Python 字典表示 JSON-RPC 消息。它考察：

1. **三种 primitive 中的两种**：resources（`NOTES` 字典，URI 可寻址）与 prompts（`PROMPTS` 字典，用户选择的模板）。
2. **无状态信封**：每个请求都由 `validate_request_meta` 独立检查 `_meta` 中的协议版本与客户端能力；版本不对返回 `-32022`，缺字段返回 `-32602`。
3. **`server/discover`**：一次性声明支持的版本与 resources/prompts 能力。
4. **确定性列表与缓存提示**：`resources/list`、`prompts/list` 都排序；list 用 `public`，正文 read 用 `private`。
5. **错误语义**：未知 URI → `-32602`；未知方法 → `-32601`；JSON-RPC 通知（无 `id`）→ 不回响应。
6. **新式订阅**：`subscriptions/listen` 生成一个 `SubscriptionStream` 对象，按允许列表过滤通知，所有消息用请求 `id` 作为 subscription ID 关联。

> 一句话：**把"无状态服务端如何暴露可寻址上下文"压缩成 300 行可读的消息构造代码**，重点在线上（wire）不变量，而不是传输。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` / `SERVER_INFO` | 常量 | 当前修订版与服务端身份 | 版本协商、诊断信息 |
| `NOTES` / `PROMPTS` | 字典 | 两篇笔记（resource）与两个 prompt 定义 | 数据源 |
| `RpcError` | 异常类 | 带 `code/message/data` 的 JSON-RPC 错误，`as_json()` 序列化 | 结构化错误 |
| `request_meta` / `response_meta` / `complete` | 函数 | 构造请求 `_meta`、响应 `_meta`、带 `resultType` 的结果 | 无状态信封 |
| `validate_request_meta` | 函数 | 每个请求的版本与能力校验 | `-32602` / `-32022` |
| `server_discover` | handler | 返回版本、能力、instructions、缓存提示 | `server/discover` |
| `resources_list` / `resources_read` | handler | 排序列出资源；按 URI 读取 | 确定性列表、未知 URI |
| `prompts_list` / `prompts_get` | handler | 排序列出 prompt；解析参数生成消息 | prompt 模板 |
| `SUPPORTED_NOTIFICATION_FIELDS` | 集合 | 服务端支持的三种订阅字段 | 允许列表 |
| `SubscriptionStream` | 冻结 dataclass | 生成 ack、各种通知、收尾结果 | 订阅流 |
| `subscriptions_listen` | 函数 | 把请求过滤器收敛成"已接受子集" | `subscriptions/listen` |
| `HANDLERS` / `handle` | 字典 + 分派函数 | 统一入口：校验 → 分派 → 包装响应/错误 | JSON-RPC 分派 |
| `rpc_request` / `demo` | 函数 | 构造请求；跑一遍完整对话并收集 transcript | 演示 |

数据流：`demo()` 用 `rpc_request` 构造请求 → `handle()` 校验 `_meta` → 查 `HANDLERS` 调用 handler → handler 用 `complete()` 包装结果 → `handle()` 包成 `{"jsonrpc","id","result"}`；订阅分支返回 `SubscriptionStream`，由 `demo()` 依次取 `acknowledged()`、`resource_updated()`、`close()` → `json.dumps` 打印。

---

## 3. 逐段精讲

### 3.1 数据：故意乱序的 `NOTES`

```python
NOTES = {
    "notes://note-2": {...},
    "notes://note-1": {...},
}
```

- 字典里 `note-2` 写在 `note-1` 前面——这是**有意为之**：Python 3.7+ 字典保持插入顺序，如果 `resources_list` 不排序，输出就会是 2、1。测试 `test_resource_list_is_deterministic` 断言输出等于 `sorted(main.NOTES)`，从而证明排序真的生效。
- URI 使用 `notes://` 命名空间（讲义："`notes://note-1` is better than `note-1` because its namespace is explicit"）。
- `PROMPTS` 同理，`review_note` 写在 `release_brief` 后面，排序后 `release_brief` 在前。

### 3.2 `RpcError`：把错误当作数据

```python
class RpcError(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}

    def as_json(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data:
            error["data"] = self.data
        return error
```

- handler 内部只需 `raise RpcError(...)`，由 `handle()` 统一捕获并转成 JSON-RPC `error` 对象——"抛异常 + 统一出口"是服务端常见写法。
- `data or {}`：`None` 时换成空字典；`as_json` 只在 `data` 非空时才输出 `data` 字段。

本文件用到的错误码：

| 码 | 含义 | 触发位置 |
|----|------|---------|
| `-32602` | Invalid params | 缺 `_meta`、缺版本、缺能力、未知 URI、prompt 参数错误、listen 缺过滤器 |
| `-32022` | 不支持的协议版本 | `validate_request_meta` |
| `-32601` | Method not found | `handle()` 找不到 handler |

### 3.3 无状态信封：`request_meta` 与 `validate_request_meta`

```python
def validate_request_meta(params: dict[str, Any]) -> None:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise RpcError(-32602, "Missing request metadata")
    requested = meta.get("io.modelcontextprotocol/protocolVersion")
    if not isinstance(requested, str):
        raise RpcError(-32602, "Missing or invalid protocol version")
    if requested != PROTOCOL_VERSION:
        raise RpcError(
            -32022,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    if not isinstance(meta.get("io.modelcontextprotocol/clientCapabilities"), dict):
        raise RpcError(-32602, "Missing client capabilities")
```

- **每个请求都要过一遍**，没有"握手后免检"的概念——这就是"无状态"。
- 区分两种错误：版本字段**缺失或类型错** → `-32602`；**存在但不支持** → `-32022`，并告诉客户端 `supported` 与 `requested`，便于客户端降级或报错。
- ⚠️ 简化：`clientInfo` 没有被检查（实测删掉它请求照样成功）。讲义的请求示例三项都有，但只把版本与能力写成必需。
- `clientCapabilities` 为 `{}` 也能通过（`isinstance({}, dict)` 为真）：空能力是合法的"什么都不支持"。

### 3.4 `complete()` 与 `server_discover`

```python
def complete(**payload: Any) -> dict[str, Any]:
    return {"resultType": "complete", **payload, "_meta": response_meta()}
```

- 所有正常结果都通过它包装：开头放 `resultType: "complete"`，结尾放带 `serverInfo` 的 `_meta`。测试 `test_every_complete_result_identifies_server` 验证这一点。
- `response_meta()` 用 `SERVER_INFO.copy()`，避免调用方修改返回值时污染全局常量。
- `serverInfo` 只是诊断信息，讲义强调"It is not an authentication identity"。

`server_discover` 返回 `supportedVersions`、`capabilities`（`resources.listChanged/subscribe`、`prompts.listChanged`）、一段 `instructions`，以及 `ttlMs=3_600_000`（1 小时）+ `public`——能力快照对所有人相同、变化很慢，适合长时间公共缓存。

### 3.5 Resources：排序的列表与严格的读取

```python
def resources_list(_: dict[str, Any]) -> dict[str, Any]:
    resources = [
        {key: value[key] for key in ("name", "description", "mimeType")} | {"uri": uri}
        for uri, value in sorted(NOTES.items())
    ]
    return complete(resources=resources, ttlMs=300_000, cacheScope="public")
```

- `sorted(NOTES.items())` 按键（URI）排序，保证确定性。
- 内层**字典推导式**只挑出三个元数据字段——**正文 `text` 不出现在列表里**，列表只给"目录"，正文必须单独 `read`。
- `| {"uri": uri}` 是 Python 3.9+ 的字典合并运算符，`uri` 被放在最后（所以输出里 `uri` 是每项的最后一个键）。
- 参数名写成 `_`，表示这个 handler 不使用 `params`（但签名要与其他 handler 一致，才能放进 `HANDLERS`）。

```python
def resources_read(params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str) or uri not in NOTES:
        raise RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri})
    note = NOTES[uri]
    return complete(
        contents=[{"uri": uri, "mimeType": note["mimeType"], "text": note["text"]}],
        ttlMs=60_000,
        cacheScope="private",
    )
```

- 先 `isinstance(uri, str)` 再 `in`：既拦住非字符串，也避免列表这类不可哈希值引发 `TypeError`（对比 3.6 中 `prompts_get` 没这样做）。
- 未知 URI 是**错误**而不是 `contents: []`：讲义"An unknown URI is not a successful empty read"，让客户端能区分"不存在"与"合法的空文档"。
- `contents` 是列表：规范允许一个 read 返回多个内容项。
- `private` + 60 秒：正文视为用户所有。
- ⚠️ 简化：没有授权主体、没有大小限制、没有字段脱敏（讲义要求服务端"限制内容大小……按调用者权限脱敏"）。

### 3.6 Prompts：模板解析与参数校验

```python
def prompts_get(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments", {})
    if name not in PROMPTS or not isinstance(arguments, dict):
        raise RpcError(-32602, "Unknown prompt or invalid arguments", {"name": name})
    if name == "review_note":
        uri = arguments.get("uri")
        if uri not in NOTES:
            raise RpcError(-32602, "review_note requires a known resource URI", {"uri": uri})
        focus = arguments.get("focus", "correctness")
        text = f"Review the resource {uri} for {focus}. Cite the URI in every finding."
    else:
        audience = arguments.get("audience")
        if not isinstance(audience, str) or not audience.strip():
            raise RpcError(-32602, "release_brief requires audience")
        text = f"Draft a release brief for {audience}. Separate verified facts from open questions."
    return complete(
        description=PROMPTS[name]["description"],
        messages=[{"role": "user", "content": {"type": "text", "text": text}}],
    )
```

- `prompts/get` 把参数解析成 `messages`，角色是 `user`——它**不替代** host 的系统指令（讲义）。
- `review_note` 要求 `uri` 是已知资源，体现"prompt 的 URI 应与直接读取走同样的检查"——但这里只检查了存在性，没有授权。
- `release_brief` 用 `audience.strip()` 拒绝纯空白字符串（实测 `"  "` 返回 `-32602`）。
- `focus` 是可选参数，默认 `"correctness"`。
- ⚠️ **Bug 1**：`name` 或 `uri` 为列表等不可哈希类型时，`in` 运算抛 `TypeError`，`handle()` 只捕获 `RpcError`，异常直接冒出（实测：`name=["x"]` → `TypeError: unhashable type: 'list'`）。应先 `isinstance(..., str)`。
- ⚠️ **Bug 2 / 安全提示**：`focus` 不做任何校验，任意文本被拼进消息（实测 `focus="Ignore previous instructions"` 被原样嵌入）。见测验 Q9。
- prompt 结果没有缓存提示（`ttlMs`/`cacheScope` 是可选的）。

### 3.7 订阅：允许列表与 `SubscriptionStream`

```python
def subscriptions_listen(request_id: int | str, params: dict[str, Any]) -> SubscriptionStream:
    requested = params.get("notifications")
    if not isinstance(requested, dict):
        raise RpcError(-32602, "subscriptions/listen requires a notifications filter")
    agreed: dict[str, Any] = {}
    for key in sorted(SUPPORTED_NOTIFICATION_FIELDS):
        value = requested.get(key)
        if key == "resourceSubscriptions" and value is not None:
            if not isinstance(value, list) or not all(isinstance(uri, str) for uri in value):
                raise RpcError(-32602, "resourceSubscriptions must be an array of URIs")
            agreed[key] = sorted(set(value))
        elif key != "resourceSubscriptions" and value is True:
            agreed[key] = True
    return SubscriptionStream(request_id, agreed)
```

- 循环的是**服务端支持的字段**而不是客户端发来的字段——客户端多发的未知键（如 `foo`）自然被忽略，这就是"已接受子集"。
- 布尔字段必须 `is True`：`"yes"`、`1` 都不算。
- URI 列表 `sorted(set(...))`：去重 + 排序，保证 ack 内容确定。
- `sorted(SUPPORTED_NOTIFICATION_FIELDS)` 的结果是 `['promptsListChanged', 'resourceSubscriptions', 'resourcesListChanged']`（大写 `S` 的 ASCII 码小于小写 `s`），所以 ack 里 `resourceSubscriptions` 排在 `resourcesListChanged` 前面——和讲义示例的键顺序相反，但 JSON 对象本身无序，不影响语义。
- ⚠️ 简化：URI 既不检查存在性也不做授权，`notes://missing` 会被"接受"（见测验 Q10）。

```python
@dataclass(frozen=True)
class SubscriptionStream:
    subscription_id: int | str
    notifications: dict[str, Any]

    def _meta(self) -> dict[str, Any]:
        return {"io.modelcontextprotocol/subscriptionId": self.subscription_id}

    def resource_updated(self, uri: str) -> dict[str, Any] | None:
        if uri not in self.notifications.get("resourceSubscriptions", []):
            return None
        return {..."method": "notifications/resources/updated",
                "params": {"_meta": self._meta(), "uri": uri}}
    ...
    def close(self) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": self.subscription_id,
                "result": {"resultType": "complete", "_meta": self._meta() | response_meta()}}
```

- `frozen=True`：subscription ID 一旦确定就不能被改（实测赋值抛 `FrozenInstanceError`）。注意 `notifications` 字典本身仍是可变的，冻结只是"浅冻结"。
- 每个"发通知"的方法先查过滤器，没请求就返回 `None`——"服务端不得推送未请求的通知类型"。
- 通知没有 `id`（JSON-RPC 通知不需要响应），只有 `close()` 带 `id`，与原 listen 请求配对。
- `resource_updated` 的 `params` 只有 URI，没有内容：客户端必须重新 `resources/read`。
- 这个类**不维护任何连接**：它只是"应该往响应流里写哪些消息"的工厂，讲义："The Python model does not open a real HTTP connection."

### 3.8 统一入口 `handle()`

```python
def handle(request: dict[str, Any]) -> dict[str, Any] | SubscriptionStream | None:
    is_notification = "id" not in request
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})
    if not isinstance(params, dict):
        if is_notification:
            return None
        error = RpcError(-32602, "params must be an object")
        return {"jsonrpc": "2.0", "id": request_id, "error": error.as_json()}
    try:
        validate_request_meta(params)
        if is_notification:
            handler = HANDLERS.get(method)
            if handler is not None:
                handler(params)
            return None
        if method == "subscriptions/listen":
            ...
            return subscriptions_listen(request_id, params)
        handler = HANDLERS.get(method)
        if handler is None:
            raise RpcError(-32601, "Method not found", {"method": method})
        return {"jsonrpc": "2.0", "id": request_id, "result": handler(params)}
    except RpcError as exc:
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "error": exc.as_json()}
```

- **通知判定用 `"id" not in request`**，而不是 `request.get("id") is None`：`"id": null` 在 JSON-RPC 中仍是请求。
- 通知永远不回响应（哪怕出错），这是 JSON-RPC 2.0 规则；测试 `test_json_rpc_notification_receives_no_response` 覆盖。
- `subscriptions/listen` 不在 `HANDLERS` 里，单独分支——因为它的返回值不是一个结果，而是一条"流"。
- 返回类型是三选一的联合类型：响应字典、`SubscriptionStream`、`None`。
- `HANDLERS` 中没有 `resources/subscribe` / `resources/unsubscribe`，调用会得到 `-32601`（实测）。
- ⚠️ 只捕获 `RpcError`；handler 内的其他异常（如 3.6 的 `TypeError`）会让整个服务端调用崩溃。生产中应再加一层 `except Exception` 转成 `-32603 Internal error`，并且不在 `data` 中泄露堆栈。

### 3.9 `demo()`：一条完整对话

按顺序发送 id 0–5：discover → resources/list → resources/read(note-1) → prompts/list → prompts/get(review_note) → subscriptions/listen；最后把 stream 的 `acknowledged()`、`resource_updated("notes://note-1")`、`close()` 依次追加，并过滤掉 `None`。消息的先后顺序完全由 `demo()` 的调用顺序决定——真实 SDK 需要保证 ack 一定先写入流。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字典模拟消息，不开真实连接 | 让线上不变量一目了然 | 没有 framing、SSE、背压；生产用官方 SDK |
| 每个请求都校验 `_meta` | 无状态：不依赖握手 | 每次多一点开销；SDK 通常在中间件统一做 |
| 异常 + 统一出口 | handler 简洁 | 只捕获 `RpcError`，其他异常会崩溃；应加兜底 `-32603` |
| list 排序、只给元数据 | 确定性、目录与正文分离 | 大量资源需要分页游标（讲义练习 2） |
| list `public` / read `private` | 示范按数据归属选缓存范围 | 一旦多用户，list 也可能需要 `private`；缓存键要含 subject |
| 未知 URI 返回 `-32602` | 区分"不存在"与"空文档" | 有授权后，"无权"也应返回同样的错误以免泄露存在性 |
| 订阅用冻结 dataclass 生成消息 | ID 不可变、逻辑可测 | 不管理真实流生命周期、不做 URI 授权 |
| prompt 参数只做最少校验 | 代码短 | `focus` 可注入、非字符串参数会崩；应白名单 + 类型检查 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在旧版本里写 `int \| str` 这样的新式注解 |
| 类型注解 | `def handle(request: dict[str, Any]) -> dict[str, Any] \| SubscriptionStream \| None` | 标注参数与返回类型；`X \| Y` 表示"二者之一"，`Any` 表示任意类型 |
| 自定义异常 | `class RpcError(Exception)`、`super().__init__(message)` | 继承 `Exception` 并附带额外字段 |
| `raise` / `try...except` | `raise RpcError(-32602, ...)`、`except RpcError as exc` | 抛出与捕获指定类型的异常 |
| `dataclass(frozen=True)` | `class SubscriptionStream` | 自动生成 `__init__`；`frozen` 让实例字段不可重新赋值 |
| `**kwargs` 收集关键字参数 | `def complete(**payload)`、`def rpc_request(request_id, method, **params)` | 把任意关键字参数收成字典 |
| 字典解包 `**` | `{"resultType": "complete", **payload, "_meta": ...}` | 把一个字典的键值展开到新字典中 |
| 字典合并 `\|` | `{...} \| {"uri": uri}`、`self._meta() \| response_meta()` | Python 3.9+，右侧同名键覆盖左侧 |
| 字典推导式 | `{key: value[key] for key in ("name", "description", "mimeType")}` | 从元组中挑字段构造新字典 |
| 列表推导式 | `[{"name": name, **definition} for name, definition in sorted(PROMPTS.items())]` | 遍历 + 构造一步完成 |
| `sorted()` 与 `set()` | `sorted(set(value))` | 去重后排序，得到确定的列表 |
| `all()` + 生成器表达式 | `all(isinstance(uri, str) for uri in value)` | 检查每个元素都满足条件 |
| `isinstance` | `isinstance(meta, dict)` | 运行时类型检查，校验外部输入必备 |
| `dict.get(key, default)` | `params.get("arguments", {})` | 键不存在时返回默认值，不抛 `KeyError` |
| `or` 提供默认值 | `self.data = data or {}` | `None`/空值时使用右侧 |
| 数字下划线 | `3_600_000`、`300_000` | 只为可读性，等于 3600000 |
| 字典作为分派表 | `HANDLERS = {"resources/list": resources_list, ...}` | 函数是一等对象，可以存进字典按名调用 |
| f-string | `f"Review the resource {uri} for {focus}. ..."` | 字符串插值 |
| `assert` | `assert isinstance(stream, SubscriptionStream)` | 开发期断言（用 `-O` 运行时会被去掉，不要用于输入校验） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo，被 `import` 时不执行 |
| `json.dumps(..., indent=2)` | `print(json.dumps(demo(), indent=2))` | 带缩进的 JSON 输出；Python 的 `True` 变成 `true` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3，标准库，瞬间完成），输出 8 条 JSON 消息，节选如下：

```text
{"id": 0, "result": {"resultType": "complete", "supportedVersions": ["2026-07-28"],
   "capabilities": {"resources": {"listChanged": true, "subscribe": true}, "prompts": {"listChanged": true}},
   "instructions": "...", "ttlMs": 3600000, "cacheScope": "public", "_meta": {serverInfo...}}}
{"id": 1, "result": {"resources": [ {... "uri": "notes://note-1"}, {... "uri": "notes://note-2"} ],
   "ttlMs": 300000, "cacheScope": "public"}}            ← 已排序：1 在 2 前（源字典是 2 在前）
{"id": 2, "result": {"contents": [{"uri": "notes://note-1", "mimeType": "text/markdown",
   "text": "# Decision\n\nKeep protocol requests self-contained."}], "ttlMs": 60000, "cacheScope": "private"}}
{"id": 3, "result": {"prompts": [{"name": "release_brief", ...}, {"name": "review_note", ...}],
   "ttlMs": 600000, "cacheScope": "public"}}            ← 同样排序
{"id": 4, "result": {"messages": [{"role": "user", "content": {"type": "text",
   "text": "Review the resource notes://note-1 for operational risk. Cite the URI in every finding."}}]}}
{"method": "notifications/subscriptions/acknowledged",
   "params": {"_meta": {"io.modelcontextprotocol/subscriptionId": 5},
              "notifications": {"resourceSubscriptions": ["notes://note-1"], "resourcesListChanged": true}}}
{"method": "notifications/resources/updated",
   "params": {"_meta": {"io.modelcontextprotocol/subscriptionId": 5}, "uri": "notes://note-1"}}
{"id": 5, "result": {"resultType": "complete",
   "_meta": {"io.modelcontextprotocol/subscriptionId": 5, "io.modelcontextprotocol/serverInfo": {...}}}}
```

对照讲义"Practice Lab"的检查清单：

1. **discover**：声明 `2026-07-28` 与 resources/prompts 两种能力。
2. **两个 list 都排序**，都带 `resultType: "complete"`。
3. **缓存提示**：discover 1 小时 public、resources/list 5 分钟 public、read 1 分钟 private、prompts/list 10 分钟 public；prompts/get 没有缓存提示。
4. 把 read 的 URI 改成 `notes://missing`：实测返回 `{"code": -32602, "message": "Unknown or invalid resource URI", "data": {"uri": "notes://missing"}}`。
5. **ack 在事件之前**：ack 是第 6 条，updated 是第 7 条。
6. **ID 5 贯穿**：ack、事件、收尾结果都带 `subscriptionId: 5`，收尾结果的 JSON-RPC `id` 也是 5。

额外观察：输出中 `resources` 的每一项 `uri` 都排在最后，这是 `| {"uri": uri}` 合并顺序造成的，与讲义示例的键顺序不同，但不影响语义。

---

## 7. 动手改一改

1. **（入门）** 往 `NOTES` 里加一条 `notes://note-0`，确认 `resources/list` 输出中它排第一，所有测试仍通过。
2. **（入门）** 修复 `prompts_get`：对 `name`、`uri`、`focus` 先做 `isinstance(..., str)` 检查，并把 `focus` 限制为白名单；补一个测试证明 `name=["x"]` 返回 `-32602` 而不是崩溃。
3. **（讲义练习 4）** 用 `promptsListChanged` 写一个测试：过滤器缺省时 `prompts_list_changed()` 返回 `None`，包含时返回带 subscription ID 的通知。
4. **（讲义练习 5）** 同时创建 `id=5` 与 `id=6` 两个订阅，对同一 URI 触发更新，断言两条事件分别带 5 和 6，并且只订阅了 note-2 的那一条返回 `None`。
5. **（讲义练习 2）** 给 `resources/list` 加 `cursor` 与 `pageSize`：游标编码"上一页最后一个 URI"，下一页从严格大于它的 URI 开始；证明翻页结果拼起来等于全量排序结果。
6. **（进阶，讲义练习 6）** 给 `handle()` 增加 `subject` 参数，给每条笔记加 `owner`；`resources_read`、`review_note`、`subscriptions_listen` 都执行同一个 `authorize(subject, uri)`；写一个简单的 host 缓存（键含 subject），证明 bob 命中不了 alice 的缓存项。

---

## 8. 常见坑

- **把未知 URI 当成空结果**：返回 `contents: []` 会让客户端误以为文档存在但为空，也可能触发"更宽泛的回退查询"。
- **列表不排序**：字典/数据库的自然顺序可能随插入或执行计划变化，导致缓存抖动、UI 跳动。
- **把 `no-store` 写进 `cacheScope`**：协议只有 `public`/`private`；no-store 是 host 策略。
- **以为 `public` 能代替授权**：缓存提示只描述"谁能共享"，不负责"谁能看"。
- **用 `serverInfo` / `clientInfo` 做身份认证**：它们只是自报的诊断信息。
- **通知也回响应**：JSON-RPC 通知（无 `id`）不应得到任何响应，哪怕处理出错。
- **认为订阅事件携带新内容**：事件只说"变了"，必须重新 `read`，并接受当前授权。
- **只捕获自定义异常**：类型错误、键错误会让服务端崩溃；对外部输入先做类型检查。
- **订阅 URI 不校验**：会把不存在或无权访问的 URI 写进 ack，误导客户端。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest discover tests -v`。实际结果：**Ran 14 tests ... OK**（讲义要求"至少 12 个"）。

`tests/test_main.py` 通过 `sys.path.insert(0, ...parents[1])` 把 `code/` 加到导入路径后 `import main`。辅助方法 `result()` 断言响应是字典、没有 `error`，再取出 `result`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_resource_list_is_deterministic` | 两次调用结果相同，且 URI 顺序等于 `sorted(NOTES)` |
| `test_server_discover_advertises_current_capabilities` | `supportedVersions` 为当前版本；能力恰好是 resources、prompts；`resources.subscribe` 为真 |
| `test_missing_protocol_version_is_invalid_params` | 删掉版本字段 → `-32602` |
| `test_unsupported_version_uses_current_protocol_error` | 版本 `2025-11-25` → `-32022`，`data` 中 `supported`、`requested` 正确 |
| `test_resource_list_has_public_cache_hints` | list 结果 `resultType=complete`、`ttlMs=300000`、`public` |
| `test_resource_read_has_private_cache_hints` | read 结果 `ttlMs=60000`、`private` |
| `test_unknown_resource_uses_invalid_params` | `notes://missing` → `-32602` |
| `test_prompt_list_is_deterministic_and_cacheable` | prompt 名称排序，`(600000, "public")` |
| `test_prompt_get_validates_required_argument` | `release_brief` 缺 `audience` → `-32602` |
| `test_subscription_acknowledgment_is_first_message` | listen 返回 `SubscriptionStream`；ack 的 method 与 subscription ID 正确 |
| `test_subscription_filters_and_correlates_updates` | 未订阅的 note-2 不产生事件；note-1 事件带 ID 22 |
| `test_legacy_subscription_methods_are_not_exposed` | `HANDLERS` 中没有 `resources/subscribe`/`unsubscribe` |
| `test_every_complete_result_identifies_server` | 结果 `_meta.serverInfo` 等于 `SERVER_INFO` |
| `test_json_rpc_notification_receives_no_response` | 删掉 `id` 的请求返回 `None` |

测试的盲区：

- `test_subscription_acknowledgment_is_first_message` 名为"ack 是第一条消息"，但只检查了 ack 的内容，**没有检查顺序**——顺序其实由调用者（`demo()`）决定。
- 没有测试不可哈希参数（会崩溃）、`focus` 注入、订阅不存在的 URI、`clientInfo` 缺失、`-32601` 未知方法、`close()` 的 ID 关联。
- 没有任何授权或多用户缓存隔离的测试——这正是讲义练习 6 要你补的。
