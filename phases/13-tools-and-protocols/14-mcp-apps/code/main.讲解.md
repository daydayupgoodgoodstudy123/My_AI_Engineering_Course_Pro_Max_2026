# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 14 节 无状态协议上的 MCP Apps ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`html`、`json`、`dataclasses`、`typing`；测试用 `unittest`、`importlib`），无需网络、无需 MCP SDK

---

## 1. 这份代码在考察什么

这是一个**进程内的协议模型**（in-process protocol model）：它不开 HTTP 端口，而是把"已经解析好的 JSON body + 路由头"直接交给 `McpAppServer.handle`，返回 `(HTTP 状态码, JSON-RPC 响应或 None)`。用它演示 2026-07-28 无状态 MCP 核心上的 MCP Apps：

1. **无状态请求信封**：每个请求在 `params._meta` 中自带 `protocolVersion`、`clientCapabilities`、`clientInfo`，没有 `initialize`、没有会话 ID。
2. **路由头与 body 的一致性**：`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 必须与 body 一致，否则 `-32020`；校验顺序是讲义"Reject wire ambiguity before feature policy"的直接实现。
3. **扩展协商**：`server/discover` 宣告 `io.modelcontextprotocol/ui`；客户端每个请求都要声明，服务端据此决定 `tools/list` 是否附带 `_meta.ui.resourceUri`、`resources/read` 是否放行。
4. **App 资源**：一段自包含 HTML，`text/html;profile=mcp-app`，带空的 CSP 域名列表与空 `permissions`，并演示 bridge 的最小安全写法（固定 `hostOrigin`、校验 `event.origin`、`ui/initialize` → `ui/notifications/initialized`）。
5. **文本回退**与**通知语义**（202 空 body）、非 POST 返回 405。

> 一句话：**用不到 300 行标准库代码，把"交互式 UI 也只是一次自包含的工具 + 资源交换"讲清楚，并把每一条线协议规则落到一个可测试的分支上**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` 等常量 | 模块常量 | 协议版本、扩展 ID、`_meta` 键名、资源 URI 与 MIME、host origin | 线协议标识符 |
| `NOTES` / `APP_CSP` | 模块常量 | 演示数据；四个全空的 CSP 域名列表 | 工具数据、deny-first CSP |
| `ProtocolError` | frozen dataclass 异常 | 携带 JSON-RPC 错误 `code` / `message` / `data` | 协议错误 |
| `request_meta` | 函数 | 生成每个请求的 `_meta`（可选是否声明 Apps） | 每请求能力声明 |
| `make_request` | 函数 | 生成 `(body, headers)`，自动填写三个路由头 | Streamable HTTP 路由头 |
| `timeline_html` | 函数 | 渲染 App HTML（转义数据 + bridge 脚本） | MCP App View、postMessage bridge |
| `McpAppServer._validate` | 方法 | 形状 → `_meta` 类型 → 头 body 一致 → 版本 | 校验顺序 |
| `McpAppServer._apps_enabled` | 静态方法 | 严格判断 Apps 扩展是否被声明 | 扩展 opt-in |
| `_success` / `_error` / `_error_status` | 静态方法 | 拼成功/错误响应，错误码映射 HTTP 状态 | `resultType`、serverInfo、404/400 |
| `McpAppServer.handle` | 方法 | 405 检查 → 校验 → 按方法分派 → 通知 202 | 服务端路由 |
| `demo` | 函数 | 依次调用 discover / tools/list / tools/call / resources/read 并打印 | 端到端演示 |
| `tests/test_main.py` | 测试 | 14 个 `unittest` 用例 | 见第 9 节 |

数据流：`make_request(method, id, params)` → `(body, headers)` → `McpAppServer.handle` → `_validate` → 方法分支生成 `result` → `_success` 补 `resultType` 与 `serverInfo` → `(200, response)`；任何 `ProtocolError` → `_error_status` + `_error` → `(400/404, error 或 None)`。

---

## 3. 逐段精讲

### 3.1 常量：把线协议里的"魔法字符串"集中起来

```python
PROTOCOL_VERSION = "2026-07-28"
APPS_EXTENSION = "io.modelcontextprotocol/ui"
PROTOCOL_META = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META = "io.modelcontextprotocol/serverInfo"
RESOURCE_URI = "ui://notes/timeline.html"
RESOURCE_MIME = "text/html;profile=mcp-app"
HOST_ORIGIN = "https://host.example"
```

- `_meta` 的键都带 `io.modelcontextprotocol/` 反向域名前缀，避免与业务字段冲突。
- `ui://` 是 App UI 模板专用的 URI scheme；`profile=mcp-app` 让 host 一眼识别"这是要放进 sandbox 的 App HTML"，而不是普通文档。
- `HOST_ORIGIN` 被写死进 HTML，用于 `postMessage` 的 target origin 和 `event.origin` 校验（见 3.4 的讨论）。

```python
APP_CSP = {
    "connectDomains": [],
    "resourceDomains": [],
    "frameDomains": [],
    "baseUriDomains": [],
}
```

四个列表全空 = deny-first：不允许任何外部 fetch/XHR/WebSocket、不允许加载外部脚本/样式/图片/字体、不允许嵌套外部 frame、不允许改 `<base>`。这个 App 能工作，是因为脚本和样式全部内联（讲义"Bundle code and data when practical"）。

### 3.2 `ProtocolError`：用 dataclass 定义异常

```python
@dataclass(frozen=True)
class ProtocolError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None
```

- `code` 是 JSON-RPC 错误码：`-32600` 无效请求、`-32602` 参数错误、`-32601` 方法不存在、`-32020/-32021/-32022` 是讲义里 MCP 定义的路由不一致 / 缺扩展能力 / 版本不支持。
- `data` 可选，用于 `-32022` 的 `{"supported": [...], "requested": "..."}` 与 `-32021` 的 `requiredCapabilities`。
- ⚠️ **frozen dataclass 做异常有两个隐患**（已实际复现）：
  1. 在 `contextlib.contextmanager` 包裹的 `with` 块中抛出时，`contextmanager` 会在 Python 层执行 `exc.__traceback__ = ...`，触发 `FrozenInstanceError: cannot assign to field '__traceback__'`，原异常被吞掉。
  2. dataclass 的 `__init__` 不调用 `Exception.__init__`；用关键字参数构造时 `args == ()`，`str(err)` 为空字符串。
  本文件只用位置参数、只做普通 `raise/except`，所以没有暴露问题。修复见测验 Q11。

### 3.3 构造请求：`request_meta` 与 `make_request`

```python
def request_meta(*, apps: bool = True) -> dict[str, Any]:
    extensions = {APPS_EXTENSION: {}} if apps else {}
    return {
        PROTOCOL_META: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META: {"extensions": extensions},
        CLIENT_INFO_META: {"name": "lesson-client", "version": "1.0.0"},
    }
```

- 每个请求都重新带上完整能力——这就是"无状态"：服务端不记得你上次说过什么。
- `apps=False` 时 `extensions` 是空字典（讲义练习 1 的场景）。
- `clientInfo` 仅用于诊断，讲义强调它"is self-reported data, not an authorization identity"。

```python
    body_params = dict(params or {})
    body_params["_meta"] = request_meta(apps=apps)
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}
    headers = {"MCP-Protocol-Version": PROTOCOL_VERSION, "Mcp-Method": method}
    if method in {"tools/call", "resources/read", "prompts/get"}:
        headers["Mcp-Name"] = str(body_params.get("name") or body_params.get("uri") or "")
    return body, headers
```

- `dict(params or {})` 复制一份，避免修改调用者传入的字典。
- 三个"有目标名"的方法才带 `Mcp-Name`：工具名、资源 URI 或 prompt 名。代理可以只看头部就做路由、限流、授权，而不必解析 body。
- ⚠️ 当 `name` 和 `uri` 都缺失时头部被写成 `""`，而服务端的 `expected_name` 是 `None`，两者不相等，于是"漏传 `name`"会被报成 `-32020` 路由不一致，而不是更准确的 `-32602` 参数错误（测验 Q9 第 3 问）。

### 3.4 App HTML：数据转义 + 最小安全 bridge

```python
    items = "".join(
        "<li><button data-note='{}'>{}</button><time>{}</time></li>".format(
            html.escape(note["id"]),
            html.escape(note["title"]),
            html.escape(note["created"]),
        )
        for note in notes
    )
```

- 每个字段都经过 `html.escape`（默认 `quote=True`，会把 `'` 转成 `&#x27;`），所以即便数据里有 `<script>` 或单引号也无法跳出属性/标签。实测：标题 `<script>x</script>` 被渲染为 `&lt;script&gt;x&lt;/script&gt;`，id `a'b` 变成 `a&#x27;b`。这对应讲义"Treat tool arguments, tool results, resource text ... as untrusted input"。
- `"".join(生成器表达式)` 一次性拼出所有 `<li>`。

HTML 主体用 f-string 写成，因此 CSS 和 JS 里的花括号都写成了 `{{ }}`。脚本部分：

```javascript
const hostOrigin = "https://host.example";
let nextId = 0;
function callTool(name, args) {
  const id = ++nextId;
  window.parent.postMessage({
    jsonrpc: "2.0", id, method: "tools/call",
    params: {name, arguments: args}
  }, hostOrigin);
}
window.addEventListener("message", (event) => {
  if (event.origin !== hostOrigin || !event.data || event.data.jsonrpc !== "2.0") return;
  if (event.data.id === 0 && event.data.result) {
    document.body.dataset.bridgeReady = "true";
    window.parent.postMessage({
      jsonrpc: "2.0", method: "ui/notifications/initialized"
    }, hostOrigin);
  }
});
...
window.parent.postMessage({
  jsonrpc: "2.0", id: 0, method: "ui/initialize",
  params: {
    appInfo: {name: "notes-timeline", version: "1.0.0"},
    appCapabilities: {}
  }
}, hostOrigin);
```

- `const hostOrigin = {json.dumps(HOST_ORIGIN)}`：用 `json.dumps` 生成带引号、已转义的 JS 字符串字面量，是把 Python 值安全嵌入 JS 的惯用法。
- **发送方向**：所有 `postMessage` 的第二个参数都是 `hostOrigin`，而不是 `'*'`。测试用 `assertNotIn("}, '*')", ...)` 确认这一点。若用 `'*'`，一旦 iframe 被嵌到别的页面，消息（可能含工具参数）就会发给任何父页面。
- **接收方向**：`event.origin !== hostOrigin` 直接丢弃，防止任意页面伪造 host 的响应。
- **握手顺序**：脚本加载时发出 `ui/initialize`（id 0）；只有收到 id 为 0 且带 `result` 的响应后，才发 `ui/notifications/initialized`——与讲义"Only after that response does the View send `ui/notifications/initialized`"一致。`nextId` 从 0 开始、`++nextId` 先加后用，所以工具调用 id 从 1 起，不会与握手的 id 0 冲突。
- ⚠️ 按钮调用的是 `notes_open`，但服务端只实现了 `notes_timeline`，所以按钮被点击后经 host 转成的 `tools/call` 会得到 `-32602 Unknown tool`。这是讲义练习 5 留的空，实现见测验 Q10。
- ⚠️ 消息处理器只处理握手响应，不处理工具结果、错误或 host 推送的上下文（主题、尺寸），是一个最小骨架。
- 设计讨论：把 host origin **写死在服务端返回的资源里**，意味着这份 HTML 只能在 `https://host.example` 下工作；`cacheScope: "public"` 的同一资源若要服务多个 host，host origin 就需要由 host 侧注入或由 bridge 握手确定。教学代码这样写是为了让"不用通配符"一目了然。

### 3.5 `_validate`：校验顺序就是安全策略

```python
        if body.get("jsonrpc") != "2.0":
            raise ProtocolError(-32600, "Invalid Request")
        method = body.get("method")
        params = body.get("params")
        if not isinstance(method, str) or not isinstance(params, dict):
            raise ProtocolError(-32600, "Invalid Request")
        meta = params.get("_meta")
        if not isinstance(meta, dict):
            raise ProtocolError(-32602, "request params._meta is required")
        requested_version = meta.get(PROTOCOL_META)
        if not isinstance(requested_version, str):
            raise ProtocolError(-32602, "protocolVersion must be a string")
        if not isinstance(meta.get(CLIENT_CAPABILITIES_META), dict):
            raise ProtocolError(-32602, "clientCapabilities is required on every request")
```

第一层：JSON-RPC 形状与 `_meta` 类型。注意 `params` 也必须存在——无状态核心下每个请求都要带 `_meta`，所以连 `server/discover` 都必须有 `params`。

```python
        if headers.get("MCP-Protocol-Version") != requested_version:
            raise ProtocolError(-32020, "MCP-Protocol-Version header does not match body")
        if headers.get("Mcp-Method") != method:
            raise ProtocolError(-32020, "Mcp-Method header does not match body")
        expected_name = params.get("name") or params.get("uri")
        if method in {"tools/call", "resources/read", "prompts/get"}:
            if headers.get("Mcp-Name") != expected_name:
                raise ProtocolError(-32020, "Mcp-Name header does not match body")
```

第二层：路由头与 body 一致。网关按头部做决定，服务端按 body 执行；两者必须描述同一个请求。

```python
        if requested_version != PROTOCOL_VERSION:
            raise ProtocolError(
                -32022,
                "Unsupported protocol version",
                {"supported": [PROTOCOL_VERSION], "requested": requested_version},
            )
        return meta
```

第三层：版本是否支持。`data` 的结构与讲义表格完全一致（测试做了精确比较）。

| 输入 | 实测结果 |
|------|---------|
| 缺 `params` | 400，`-32600` |
| `params` 无 `_meta` | 400，`-32602 request params._meta is required` |
| `protocolVersion` 是整数 | 400，`-32602 protocolVersion must be a string` |
| `clientCapabilities` 是列表 | 400，`-32602 clientCapabilities is required on every request` |
| 头版本与 body 不同 | 400，`-32020` |
| 两者都是 `2025-11-25` | 400，`-32022`，带精确 `data` |

### 3.6 `_apps_enabled`：严格的 opt-in 判断

```python
    @staticmethod
    def _apps_enabled(meta: dict[str, Any]) -> bool:
        caps = meta[CLIENT_CAPABILITIES_META]
        extensions = caps.get("extensions", {})
        return (
            isinstance(extensions, dict)
            and isinstance(extensions.get(APPS_EXTENSION), dict)
        )
```

- 只有 `extensions` 是字典、且其中 Apps 扩展对应的值也是字典时才算启用。`["io.modelcontextprotocol/ui"]`（列表）或 `{APPS_EXTENSION: True}` 都不算——实测两者下 `tools/list` 都不带 `_meta`。
- 原则：**宁可误判为"不支持"，也不要把畸形输入当成能力授予**。前者最多让用户看到文本回退，后者可能把可执行 UI 发给不该收到的客户端。

### 3.7 成功与错误响应

```python
    @staticmethod
    def _success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        result = dict(result)
        result.setdefault("resultType", "complete")
        result.setdefault("_meta", {})[SERVER_INFO_META] = SERVER_INFO
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
```

- 每个成功结果都补上 `resultType: "complete"` 与 `_meta.serverInfo`——讲义要检查的第 4 点。
- `setdefault("_meta", {})` 返回已有或新建的字典，再往里写键，一行完成"没有就建、有就复用"。
- `dict(result)` 是**浅拷贝**：如果某个分支的 `result` 自带 `_meta` 字典，这里会就地修改它；而 `SERVER_INFO` 被直接引用（实测 `result["_meta"][...] is SERVER_INFO` 为 `True`），若调用方修改返回值，会改坏全局常量。生产代码可用 `copy.deepcopy` 或不可变结构。

```python
    @staticmethod
    def _error_status(error: ProtocolError) -> int:
        return 404 if error.code == -32601 else 400
```

只有"方法不存在"映射 404，其余协议错误都是 400——与讲义表格一致。

### 3.8 `handle`：方法分派

```python
        if http_method != "POST":
            return 405, None
        is_notification = "id" not in body
```

- 讲义："Streamable HTTP uses one POST per request. Modern GET and DELETE entrypoints return 405." 这里对**所有**非 POST 都返回 405（实测 `PUT` 也是）。
- 用 `"id" not in body` 而不是 `body.get("id") is None` 判断通知——`id: null` 和"没有 id"在 JSON-RPC 里是两回事。

各分支要点：

| 方法 | 关键行为 |
|------|---------|
| `server/discover` | `supportedVersions`、`capabilities`（含 `extensions`）、`ttlMs: 300_000`、`cacheScope: "public"` |
| `tools/list` | 只有一个工具 `notes_timeline`；Apps 启用时才附 `_meta.ui.resourceUri`；`ttlMs: 60_000`、`public` |
| `tools/call` | 只认 `notes_timeline`；返回 `content`（文本 "Timeline ready."）+ `structuredContent.notes` + `isError: False` |
| `resources/list` | 一个稳定描述：URI、`name`、`description`、`mimeType` |
| `resources/read` | 先校验 URI（未知 → `-32602`），再校验 Apps 能力（缺 → `-32021` + `requiredCapabilities`），最后返回 HTML 与 `_meta.ui.csp/permissions` |
| 其他 | `-32601 Method not found` → 404 |

```python
            if is_notification:
                return 202, None
            return 200, self._success(body["id"], result)
        except ProtocolError as error:
            if is_notification:
                return self._error_status(error), None
            return self._error_status(error), self._error(body.get("id"), error)
```

- 通知成功：202 空 body；通知失败：只改状态码（实测未知方法通知 → `(404, None)`，头不一致通知 → `(400, None)`），绝不生成 JSON-RPC 错误体。
- `body.get("id")` 用于错误响应：若 id 本身缺失（通知）已在上一行返回，所以这里总能拿到 id。

值得注意的三个简化：

- ⚠️ **文本回退不够"有用"**：无 Apps 时 `tools/call` 的文本只有 "Timeline ready."，笔记内容只在 `structuredContent` 里。讲义要求"Keep a useful text result for `tools/call`"，更好的做法是在 `content` 里也给出一个可读列表（例如三行 "日期 标题"）。
- ⚠️ **`tools/list` 标 `public` 但内容随能力变化**：共享缓存若不把客户端扩展集合放进缓存键，就会把带 UI 绑定的列表发给非 Apps 客户端，或反之（测验 Q12）。
- ⚠️ 分派时没有校验 `tools/call` 的 `arguments`，也没有校验 notification 的方法是否本应是 `notifications/*`；作为协议模型这是合理的省略。

### 3.9 `demo`：端到端演示

```python
    for request_id, (method, params) in enumerate(
        [
            ("server/discover", {}),
            ("tools/list", {}),
            ("tools/call", {"name": "notes_timeline", "arguments": {}}),
            ("resources/read", {"uri": RESOURCE_URI}),
        ],
        start=1,
    ):
        body, headers = make_request(method, request_id, params)
        status, response = server.handle(body, headers)
        summary = response.get("result", response.get("error"))
        print(f"{status} {method}: {json.dumps(summary)[:220]}")
```

- `enumerate(..., start=1)` 让 JSON-RPC id 从 1 开始；`(method, params)` 在 for 头部直接解包元组。
- 每次都 `make_request` 一个全新的请求：四次调用之间没有任何共享状态，这就是讲义要检查的第 1 点"Every call is independent"。
- `json.dumps(...)[:220]` 只截取前 220 个字符打印，所以输出看起来"被截断"是故意的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 进程内协议模型，输入是已解析的 body 与头 | 聚焦协议规则，不被 HTTP 细节淹没 | 不检查 `Content-Type`、`Accept`；生产用第 09 节的完整 Streamable HTTP 适配器 |
| 严格的校验顺序（形状 → 头 body → 版本 → 方法 → 能力） | 防止代理与服务端"看到不同的请求" | 实现稍啰嗦；但顺序一旦定下必须写测试锁住 |
| UI 绑定放在 `tools/list`，并按能力开关 | 调用前即可预取与审查；无 Apps 时自然回退 | `tools/list` 结果随能力变化，缓存键必须包含扩展集合 |
| App 资源全部内联、CSP 全空 | 最小攻击面，无需任何外部域 | 资源变大；一旦要引外部脚本需加 `resourceDomains`，引入供应链风险（练习 4） |
| HTML 中写死 `HOST_ORIGIN` | 演示"不用 `'*'`"最直观 | 资源与单一 host 耦合；多 host 场景需要 host 注入 origin |
| `html.escape` 所有数据 | 工具数据不可信 | 若要富文本需引入有明确边界的 sanitizer |
| `frozen=True` 的 dataclass 异常 | 写法简洁、字段不可变 | 与 `contextlib.contextmanager` 冲突、关键字构造时 `str()` 为空；生产用普通异常类 |
| `_success` 浅拷贝并引用全局 `SERVER_INFO` | 简单 | 返回值被修改会污染全局；可用深拷贝 |
| 未实现 `notes_open` | 留作练习 5 | 示例 UI 的按钮当前会得到 `-32602` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可在老版本 Python 上写 `dict[str, Any] \| None` |
| 类型注解与 `Any` | `def request_meta(*, apps: bool = True) -> dict[str, Any]` | 标注参数与返回类型，`Any` 表示任意类型；运行时不强制检查 |
| `X \| None` 联合类型 | `data: dict[str, Any] \| None = None` | "可以是字典也可以是 None" |
| 仅限关键字参数 `*` | `def request_meta(*, apps=True)`、`handle(..., *, http_method="POST")` | `*` 之后的参数必须用 `apps=False` 这种关键字形式传入，防止位置传错 |
| `@dataclass(frozen=True)` 继承 `Exception` | `class ProtocolError(Exception)` | 自动生成 `__init__`；`frozen` 禁止赋值（但会带来 3.2 所述隐患） |
| `@staticmethod` | `_apps_enabled`、`_success` | 不需要 `self` 的方法；仍可通过 `self._success(...)` 调用 |
| 条件表达式 | `{APPS_EXTENSION: {}} if apps else {}` | 一行 if/else |
| `or` 短路取值 | `params.get("name") or params.get("uri")`、`dict(params or {})` | 返回第一个"真值"；空字符串、`None`、空字典都算假 |
| 集合字面量与 `in` | `method in {"tools/call", "resources/read", "prompts/get"}` | 集合成员判断是 O(1) |
| `dict.get` / `setdefault` | `result.setdefault("_meta", {})[...] = ...` | 取不到给默认值 / 没有就插入并返回 |
| `isinstance` 类型检查 | `isinstance(params, dict)` | 防御畸形输入 |
| `raise` / `try ... except ... as` | `raise ProtocolError(-32020, ...)`、`except ProtocolError as error` | 用异常把错误从深层校验直接带到统一出口 |
| 生成器表达式 + `str.join` | `"".join("<li>...".format(...) for note in notes)` | 惰性生成每一项并拼接 |
| `str.format` | `"<li><button data-note='{}'>..."` | 位置占位符；这里不用 f-string 是因为模板里有很多引号 |
| f-string 与 `{{ }}` 转义 | `f"""...body{{font:16px system-ui}}..."""` | f-string 中字面量花括号要写两次 |
| 三引号多行字符串 | `return f"""<!doctype html>..."""` | 保留换行，适合写 HTML 模板 |
| 数字下划线 | `300_000`、`60_000` | 只是可读性分隔，等于 300000 |
| `enumerate(..., start=1)` + 元组解包 | `for request_id, (method, params) in enumerate(...)` | 同时拿到序号和元素，并就地拆开元组 |
| 切片 | `json.dumps(summary)[:220]` | 取前 220 个字符 |
| 返回元组 | `return 405, None` | 调用方 `status, response = ...` 解包 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `demo()`，被测试导入时不执行 |
| `importlib.util.spec_from_file_location`（测试） | `SPEC.loader.exec_module(main)` | 按文件路径导入模块，不依赖 `sys.path` |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`）：

```text
200 server/discover: {"supportedVersions": ["2026-07-28"], "capabilities": {"tools": {}, "resources": {}, "extensions": {"io.modelcontextprotocol/ui": {}}}, "ttlMs": 300000, "cacheScope": "public", "resultType": "complete", "_meta": {"io.mod
200 tools/list: {"tools": [{"name": "notes_timeline", "description": "Render a timeline of notes.", "inputSchema": {"type": "object", "properties": {}}, "_meta": {"ui": {"resourceUri": "ui://notes/timeline.html"}}}], "ttlMs": 60000, "ca
200 tools/call: {"content": [{"type": "text", "text": "Timeline ready."}], "structuredContent": {"notes": [{"id": "note-1", "title": "Discover", "created": "2026-07-28"}, {"id": "note-2", "title": "Per-request metadata", "created": "202
200 resources/read: {"contents": [{"uri": "ui://notes/timeline.html", "mimeType": "text/html;profile=mcp-app", "text": "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Notes timeline</title>\n<style>body{font:16px sy
```

逐项解读：

- **四个 200**：每个请求都独立生成、独立校验，全部成功。没有任何地方出现 `initialize` 或会话 ID（讲义检查点 1、5）。
- **`server/discover`**：`extensions` 中有 `io.modelcontextprotocol/ui`；`resultType` 与 `_meta` 是 `_success` 后补的，所以出现在字典末尾。
- **`tools/list`**：因为 `make_request` 默认 `apps=True`，工具带 `_meta.ui.resourceUri`。用 `apps=False` 调用（讲义练习 1）实测结果中工具只剩 `name`、`description`、`inputSchema` 三个键。
- **`tools/call`**：文本只有 "Timeline ready."，三条笔记在 `structuredContent`。
- **`resources/read`**：MIME 为 `text/html;profile=mcp-app`。完整 HTML 实测长度为 1535 个字符，被 demo 截断。
- **未演示但已验证的分支**：练习 2（`Mcp-Name: ui://notes/other.html`）→ `(400, -32020 "Mcp-Name header does not match body")`；按钮的 `notes_open` → `(400, -32602 "Unknown tool")`。

---

## 7. 动手改一改

1. **讲义练习 1**：在 `demo` 里追加 `make_request("tools/list", 5, apps=False)`，打印工具字典的键，确认 `_meta` 消失；再用 `apps=False` 调 `resources/read`，确认得到 `-32021` 和 `requiredCapabilities`。
2. **讲义练习 2**：构造 `resources/read` 请求后把 `headers["Mcp-Name"]` 改成 `ui://notes/other.html`，确认 `-32020`。再思考：如果服务端"以 body 为准"继续处理，网关按头部做的授权会出什么问题？
3. **改进文本回退**：让 `tools/call` 的 `content` 文本包含每条笔记的日期与标题（例如 `"2026-07-28 Discover\n..."`），使非 Apps host 也能得到有用结果。
4. **讲义练习 5**：实现 `notes_open` 工具（`inputSchema` 要求 `id`，`additionalProperties: false`），未知 id 返回 `isError: true`；在 `tools/list` 中声明它，并为它写两个测试。参考测验 Q10。
5. **讲义练习 3 + 4**：把 `NOTES` 改为"按 `clientInfo` 或授权上下文选择不同用户的笔记"，把资源和 `tools/list` 的 `cacheScope` 改为 `private`；再把脚本移到 `https://static.example.com/app.js`，在 `resourceDomains` 中加入该 origin，写出你对供应链风险（CDN 被篡改、版本漂移、无 SRI）的缓解措施。
6. **进阶**：修复 `ProtocolError`（去掉 `frozen=True`，在 `__post_init__` 调 `super().__init__`），并写一个测试：在 `contextlib.contextmanager` 包裹下抛出 `ProtocolError`，断言能被正常捕获。

---

## 8. 常见坑

- **把 `ui/initialize` 当成核心 `initialize`**：它只属于 iframe↔host 的 `postMessage` 方言，不协商协议版本、不创建会话；核心 `notifications/initialized` 已移除，而 Apps 的 `ui/notifications/initialized` 仍存在——注意前缀。
- **`postMessage(msg, '*')`**：发送方向用通配符会把消息发给任意父页面；接收方向不校验 `event.origin` 会接受任意页面伪造的消息。两个方向都要固定 origin。
- **宽松解析能力声明**：把列表、`True` 之类的畸形扩展值当作"支持"，会把可执行 UI 发给不该收的客户端。
- **头部与 body 不一致时"挑一个信"**：必须拒绝（`-32020`），且要在版本检查之前。
- **给 notification 回 JSON-RPC 错误体**：没有 `id` 就没有响应对象，出错也只能改 HTTP 状态码。
- **缓存键只用 URI 或只用方法名**：`tools/list` 随能力变化、私有 App 资源随用户变化，缓存键必须包含这些维度。
- **把 `connectDomains` 当成安全白名单**：它只决定"能发往哪里"，不判断"发了什么"；允许的域就是外泄通道。
- **以为按钮点击就是用户授权**：iframe 发来的请求只是意图，批准必须由 host 完成，并在动作时检查能力是否已被撤销。
- **用 frozen dataclass 定义异常**：遇到 `contextlib.contextmanager` 会抛 `FrozenInstanceError`，关键字构造时 `str()` 为空。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover tests -v`。测试通过 `importlib` 按文件路径加载 `main.py`，所以不依赖当前工作目录是否在 `sys.path` 中。

实际运行结果：**14 个测试全部通过**（`Ran 14 tests in 0.001s`，`OK`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_discover_advertises_apps_extension` | discover 返回 200，`extensions` 含 Apps，`resultType == "complete"`，`supportedVersions == ["2026-07-28"]` |
| `test_tools_list_declares_ui_before_call` | 调用前的 `tools/list` 就带 `_meta.ui.resourceUri`，`inputSchema.type == "object"` |
| `test_resources_list_is_complete_cacheable_and_deterministic` | 两次 `resources/list` 结果相同（确定性），URI/MIME 正确，`ttlMs > 0`、`cacheScope == "public"`、带 serverInfo |
| `test_non_apps_client_gets_text_tool_fallback` | 无 Apps 时工具不带 `_meta` |
| `test_resource_requires_apps_capability` | 无 Apps 读 UI 资源 → 400、`-32021`，`data` 与讲义要求逐字一致 |
| `test_malformed_extension_map_does_not_grant_apps_capability` | `extensions` 写成列表 → 不算启用，`-32021` |
| `test_resource_has_mime_cache_and_safe_bridge_origin` | MIME 正确、`public` 缓存；HTML 含固定 `hostOrigin`、`event.origin` 守卫、`appCapabilities: {}`、`ui/notifications/initialized`，且不含 `}, '*')` |
| `test_header_body_mismatch_is_protocol_error` | `Mcp-Name` 与 body 工具名不一致 → 400、`-32020` |
| `test_header_version_mismatch_precedes_version_support_check` | 只改 body 版本 → `-32020` 而不是 `-32022`，锁住校验顺序 |
| `test_unsupported_version_has_exact_error_data` | 头 body 一致的旧版本 → `-32022`，`data` 精确等于 `{"supported": [...], "requested": ...}` |
| `test_unknown_method_is_json_rpc_404` | 未知方法 → 404，完整响应逐字段比较（不带 `data`） |
| `test_accepted_notification_returns_202_with_empty_body` | 删掉 `id` 的合法请求 → `(202, None)` |
| `test_get_and_delete_are_not_transport_entrypoints` | GET、DELETE → `(405, None)` |
| `test_tool_result_has_server_identity` | `tools/call` 结果带 `resultType` 与 serverInfo |

测试没有覆盖的点（可作为练习补充）：

- 通知出错时的状态码与空 body（实测 `(404, None)` / `(400, None)`）；
- `resources/read` 未知 URI 与缺能力同时出现时的优先级（实测先报 `-32602`）；
- `tools/call` 无 Apps 时的结果是否仍可用；
- `html.escape` 对恶意笔记数据的转义；
- 示例 HTML 中按钮调用的 `notes_open` 在服务端并不存在。
