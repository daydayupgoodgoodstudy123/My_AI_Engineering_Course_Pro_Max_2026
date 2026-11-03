# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 09 节 MCP 传输：stdio 与无状态 Streamable HTTP ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（或讲义写的 `python3 main.py --probe`，效果相同：在随机端口起 server 并跑一遍有限探针）；`python3 main.py --serve`（在 `127.0.0.1:8017/mcp` 常驻，Ctrl+C 退出）；测试 `python3 -m unittest discover tests -v`（均在 `code/` 下） ｜ **依赖**：仅标准库（`http.server`、`urllib`、`base64`、`threading` 等），只监听本机回环地址，不访问外网

---

## 1. 这份代码在考察什么

第 07 节的 server 跑在 stdio 上；这一节把同样的无状态契约搬到 **Streamable HTTP** 上，并且只用标准库实现，让 HTTP 层的每一个决定都看得见：

1. **POST-only 单端点**：只有 `/mcp`，只接受 POST；GET / DELETE 返回 `405`；`Mcp-Session-Id`、`Last-Event-ID` 被忽略。
2. **入口防线**：路径、重复 Origin、Origin 允许列表、Content-Type、Accept、Content-Length（必须、纯 ASCII 数字、上限、无重复、无 Transfer-Encoding）、读取超时。
3. **镜像头校验**：`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 与 body 比较，`Mcp-Name` 支持 Base64 哨兵；校验顺序严格遵循第 06 节讲义的生命周期。
4. **响应形态**：普通请求返回 `application/json`；通知返回 `202` 无 body；`subscriptions/listen` 返回 `text/event-stream`，其中每条消息都带 `subscriptionId`。
5. **状态码与 JSON-RPC 错误码的映射**：`400 + -32020/-32022/-32602/-32700`、`404 + -32601`、`403`、`405`、`406`、`415`。

文件里同时包含一个用 `urllib` 写的小客户端（`post`、`http_headers_for`）和一个 `probe()`，把讲义"Use It"列出的 8 项检查依次跑一遍。

> 一句话：**HTTP 只是搬运自描述的请求；server 在执行前要确认"头里说的"和"body 里写的"是同一件事，并且不从连接里推断任何协议状态**。同时请注意代码在订阅过滤、无 id 请求和请求头读取超时上的简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 常量（版本、`_meta` 键、`SUBSCRIPTION_ID_KEY`、`ORIGIN_ALLOWLIST`、`MAX_REQUEST_BYTES`、`READ_TIMEOUT_SECONDS`、`ROUTING_HEADERS`） | 模块常量 | 协议与安全配置 | — |
| `RpcFault` / `rpc_error` / `complete` / `make_request` | 类 + 函数 | 与前几节相同的协议基础件；`complete` 新增 `result_meta` | 结果包装 |
| `origin_allowed` | 函数 | Origin 精确匹配，缺失放行 | DNS rebinding 防护 |
| `encode_header_value` / `decode_header_value` | 函数 | Base64 哨兵编解码与字符集检查 | `Mcp-Name` 编码 |
| `body_name` / `http_headers_for` | 函数 | 从 body 推出 `Mcp-Name`；客户端生成全部镜像头 | 镜像头 |
| `validate_request_structure` / `validate_supported_version` / `validate_http_headers` | 函数 | 结构（`-32602`）、版本（`-32022`）、头一致性（`-32020`） | 请求生命周期 |
| `reject_duplicate_routing_headers` / `reject_duplicate_origin` / `reject_ambiguous_body_framing` | 函数 | 拒绝重复头与歧义的 body 定界 | 解释一致性 |
| `dispatch` | 函数 | discover / tools/list / tools/call / subscriptions/listen | 方法路由 |
| `accepted_filter` / `subscription_messages` | 函数 | 计算接受的订阅过滤器，生成有限的 SSE 消息序列 | `subscriptions/listen` |
| `Handler` | `BaseHTTPRequestHandler` 子类 | `do_POST` / `do_GET` / `do_DELETE` 及写响应的辅助方法 | HTTP 传输 |
| `serve` | 函数 | 在后台线程启动 `ThreadingHTTPServer` | — |
| `post` / `probe` / `main` | 函数 | 小客户端、8 项探针、入口 | 演示 |

数据流（一次 POST）：`do_POST` → 路径 / 重复 Origin / Origin 允许列表 → Content-Type → Accept → body 定界检查 → 读 body（带超时）→ `json.loads` → 结构校验 → 重复路由头 → 头 / body 一致性 → 版本支持性 →（无 id）`202` /（listen）SSE 流 /（其它）`dispatch` → `200` 或 `404` + JSON。

---

## 3. 逐段精讲

### 3.1 `complete` 的新参数与订阅 id 键

```python
SUBSCRIPTION_ID_KEY = "io.modelcontextprotocol/subscriptionId"

def complete(payload, *, ttl_ms=None, cache_scope="private", result_meta=None):
    metadata = {SERVER_INFO_KEY: SERVER_INFO.copy()}
    if result_meta:
        metadata.update(result_meta)
    result = {"resultType": "complete", **payload, "_meta": metadata}
    ...
```

- 相比前两节，`complete` 多了 `result_meta`，用来把 `subscriptionId` 合并进结果的 `_meta`——讲义要求 listen 的**最终结果**也要带这个键。
- `SERVER_CAPABILITIES = {"tools": {"listChanged": True}}`：本 server 声明工具列表**会**变化，所以客户端可以订阅 `toolsListChanged`。

### 3.2 Origin 校验

```python
ORIGIN_ALLOWLIST = {"http://localhost", "http://127.0.0.1", "https://client.example"}

def origin_allowed(origin):
    return origin is None or origin in ORIGIN_ALLOWLIST
```

- 集合的 `in` 是**精确匹配**。讲义特意警告不要用 `startswith`：`https://client.example.attacker.net` 会通过前缀检查。
- `origin is None` 放行：浏览器在跨源请求中一定会带 `Origin`，非浏览器客户端（CLI、服务端 SDK）可以不带。DNS rebinding 攻击依赖受害者的浏览器，所以只要浏览器请求必须通过允许列表即可。
- 精确匹配意味着带端口的 `http://localhost:5173` 不在列表里（实测返回 `403`）；真实配置要把端口写全。
- `reject_duplicate_origin`：两个 `Origin` 头时直接 `400 + -32020`，因为 `self.headers.get("Origin")` 只会取其中一个，不同组件可能取到不同的那个（测试 `test_duplicate_origin_is_rejected_before_allowlist_evaluation`）。

### 3.3 Base64 哨兵

```python
def encode_header_value(value):
    safe = all(0x20 <= ord(character) <= 0x7E for character in value)
    sentinel = value.startswith("=?base64?") and value.endswith("?=")
    if safe and value == value.strip() and not sentinel:
        return value
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"=?base64?{encoded}?="


def decode_header_value(value):
    if value.startswith("=?base64?") and value.endswith("?="):
        encoded = value[len("=?base64?") : -2]
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise RpcFault(-32020, "Malformed Base64 MCP header value") from exc
    if any(ord(character) < 0x20 or ord(character) > 0x7E for character in value):
        raise RpcFault(-32020, "Malformed MCP header value")
    return value
```

- **什么时候编码**：含 0x20–0x7E（可见 ASCII + 空格）以外的字符、首尾有空白（HTTP 会裁掉首尾空白，导致比较失败）、或原值本身"长得像哨兵"（否则 server 会误解码）。
- 例：`notes://笔记-1` → `=?base64?bm90ZXM6Ly/nrJTorrAtMQ==?=`（实测）。
- `b64decode(..., validate=True)`：遇到非 Base64 字母表字符直接抛错，而不是悄悄忽略；解码后的字节还必须是合法 UTF-8。两种失败都归为 `-32020`。
- 非哨兵值若含控制字符或非 ASCII，同样 `-32020`。

### 3.4 客户端侧的镜像头生成

```python
def body_name(message):
    params = message.get("params", {})
    if message.get("method") == "resources/read":
        value = params.get("uri")
    elif message.get("method") in {"tools/call", "prompts/get"}:
        value = params.get("name")
    else:
        return None
    return value if isinstance(value, str) else None


def http_headers_for(message, *, origin="http://localhost", extra=None):
    meta = message["params"]["_meta"]
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Origin": origin,
        "MCP-Protocol-Version": str(meta[VERSION_KEY]),
        "Mcp-Method": str(message["method"]),
    }
    name = body_name(message)
    if name is not None:
        headers["Mcp-Name"] = encode_header_value(name)
    ...
```

- `body_name` 被客户端（生成头）和 server（校验头）**共用**——同一个函数定义"名称是什么"，两端不可能对规则理解不同。
- 头值全部**从 body 推导**而不是另行传入：讲义第 08 节说"Stamp and inspect the final serialized request"，镜像头也应该从最终的 body 生成。
- `extra` 用于探针和测试注入额外头（如已移除的 `Mcp-Session-Id`）。

### 3.5 三个校验函数与它们的顺序

```python
def validate_request_structure(message) -> str:      # -32600 / -32602，返回 body 版本
    ...
def validate_supported_version(version) -> None:      # -32022，data 键为 supported、requested
    ...
def validate_http_headers(headers, message, body_version) -> None:   # -32020
    header_version = headers.get("MCP-Protocol-Version")
    if header_version is None or header_version != body_version:
        raise RpcFault(-32020, "Header mismatch: MCP-Protocol-Version")
    header_method = headers.get("Mcp-Method")
    if header_method is None or header_method != message["method"]:
        raise RpcFault(-32020, "Header mismatch: Mcp-Method")
    expected_name = body_name(message)
    if message["method"] in {"tools/call", "resources/read", "prompts/get"}:
        header_name = headers.get("Mcp-Name")
        if header_name is None or expected_name is None:
            raise RpcFault(-32020, "Header mismatch: Mcp-Name")
        if decode_header_value(header_name) != expected_name:
            raise RpcFault(-32020, "Header mismatch: Mcp-Name")
```

`do_POST` 中的调用顺序：

```python
            body_version = validate_request_structure(message)
            reject_duplicate_routing_headers(self.headers)
            validate_http_headers(self.headers, message, body_version)
            validate_supported_version(body_version)
```

- 这正是第 06 节讲义的第 2–5 步：结构 → 头与 body 一致 → 版本支持性。与第 06、07 节代码不同，**本节的顺序与讲义完全一致**：实测"头与 body 都是 2027 但缺 capabilities"返回 `-32602`；"头 2027、body 2026"返回 `-32020`；"都是 2027"返回 `-32022`。
- `-32022` 的 `data` 键顺序是 `{"supported": ..., "requested": ...}`，与讲义练习 2 给出的"exact data"一致（JSON 对象本身无序，测试比较的是 dict 相等）。
- `self.headers` 是 `email.message.Message`，`get` 对头**名**大小写不敏感（实测全小写头名可以通过），头**值**按原样比较（实测 `Mcp-Method: TOOLS/LIST` 被拒绝）。
- `reject_duplicate_routing_headers`：用 `get_all` 检查三个路由头是否出现多次。`getattr(headers, "get_all", None)` + `callable` 是一种"鸭子类型"写法，传入普通 dict 时直接跳过。
- ⚠️ `tools/call` 若 body 中缺 `params.name`，报的是 `-32020 Header mismatch: Mcp-Name`，严格说更像参数错误；这是"头校验在参数校验之前"的副作用。

### 3.6 `do_POST`：入口防线

```python
    def do_POST(self):
        if not self._valid_path_and_origin():
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._write_json(415, {"error": "Content-Type must be application/json"})
            return
        accept = self.headers.get("Accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            self._write_json(406, {"error": "Accept must include JSON and SSE"})
            return
        try:
            reject_ambiguous_body_framing(self.headers)
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            if not raw_length.isascii() or not raw_length.isdigit():
                raise ValueError("Content-Length must contain ASCII decimal digits")
            length = int(raw_length)
            if not 1 <= length <= MAX_REQUEST_BYTES:
                raise ValueError(...)
            self.connection.settimeout(READ_TIMEOUT_SECONDS)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("request body ended before Content-Length bytes arrived")
            message = json.loads(body)
            if not isinstance(message, dict):
                raise ValueError("message must be an object")
        except (ValueError, json.JSONDecodeError, TimeoutError) as exc:
            self._write_json(400, rpc_error(None, -32700, "Parse error", {"detail": str(exc)}))
            return
```

| 检查 | 失败时 | 防的是什么 |
|------|-------|-----------|
| 路径必须是 `/mcp` | `404` | 单端点 |
| 重复 Origin / Origin 不在允许列表 | `400 -32020` / `403` | 解释分歧 / DNS rebinding |
| `Content-Type` 主类型为 `application/json` | `415` | `split(";")` 去掉 `; charset=utf-8` 等参数 |
| `Accept` 同时含 JSON 与 SSE | `406` | 讲义要求客户端声明两种响应类型（实测 `*/*` 也被拒绝，较严格） |
| 重复 Content-Length、存在 Transfer-Encoding | `400 -32700` | HTTP 请求走私 |
| Content-Length 必须存在、纯 ASCII 数字 | `400 -32700` | `"²".isdigit()` 为 `True`、`int("+1")` 能成功，先 `isascii()` 堵住 |
| 长度 1～1 MiB | `400 -32700` | 内存耗尽 |
| 读取超时 5 秒、读满长度 | `400 -32700` | 慢速 body、半截 body |
| body 是 JSON 对象 | `400 -32700` | 不支持 batch 数组 |

- `json.JSONDecodeError` 是 `ValueError` 的子类，这里并列写出是为了可读性。
- ⚠️ 读取超时只在 body 阶段生效：`BaseHTTPRequestHandler.timeout` 默认是 `None`，读取请求行和请求头时没有超时（实测 `Handler.timeout` 为 `None`），存在 slowloris 风险。设置 `Handler.timeout = READ_TIMEOUT_SECONDS` 即可让 `setup()` 对套接字统一设置超时。
- ⚠️ 入口层面的错误（404 路径、403、405、406、415）返回的是 `{"error": "..."}` 这种**非 JSON-RPC** body；`-32xxx` 只出现在 400 / 404 的 JSON-RPC 错误中。这与讲义"双时代客户端检查 body 是否为可识别的现代错误"相配合：只有 JSON-RPC 错误才算现代证据。

### 3.7 通知、listen 与普通请求的分支

```python
        if "id" not in message:
            self.send_response(202)
            self.end_headers()
            return

        if message["method"] == "subscriptions/listen":
            ...
            self._write_subscription_stream(message)
            return

        response = dispatch(message)
        status = 404 if response and response.get("error", {}).get("code") == -32601 else 200
        if response is not None:
            self._write_json(status, response)
```

- **通知**：通过全部校验后返回 `202`、无 body（讲义要求）。⚠️ 代码不区分方法名：一个忘了带 `id` 的 `tools/call` 也会得到 `202`，工具不会执行，客户端也收不到任何错误（实测）。
- **listen**：单独走 SSE 分支，不经过 `dispatch`（`dispatch` 里的 listen 分支只在直接调用 `dispatch` 时用到）。
- **普通请求**：`dispatch` 会**再次**执行结构与版本校验（冗余但无害）；`-32601` 映射为 HTTP `404`（讲义："An unknown modern method returns HTTP `404` with JSON-RPC `-32601`"），其它结果（包括 `isError` 的工具结果）都是 `200`。
- `dispatch` 中 `tools/call` 对未知工具返回 `isError`（测试 `test_base64_name_is_decoded_before_comparison` 用 `ping-世界` 验证了"头通过 Base64 解码匹配后，进入 dispatch 得到 isError"）；`SERVER_CAPABILITIES.copy()` 仍是浅拷贝（与第 06 节同类问题）。

### 3.8 `subscriptions/listen` 的有限 SSE 流

```python
def subscription_messages(message):
    request_id = message["id"]
    requested = message["params"]["notifications"]
    accepted = accepted_filter(requested)
    subscription_meta = {SUBSCRIPTION_ID_KEY: request_id}
    messages = [{
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {"notifications": accepted, "_meta": subscription_meta.copy()},
    }]
    if accepted.get("toolsListChanged"):
        messages.append({... "notifications/tools/list_changed" ...})
    resources = accepted.get("resourceSubscriptions", [])
    if resources:
        messages.append({... "notifications/resources/updated", "uri": resources[0] ...})
    messages.append({"jsonrpc": "2.0", "id": request_id,
                     "result": complete({}, result_meta=subscription_meta)})
    return messages
```

```python
    def _write_subscription_stream(self, message):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        for payload in subscription_messages(message):
            self.wfile.write(f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode("utf-8"))
            self.wfile.flush()
```

- **SSE 格式**：每个事件是 `data: <JSON>` 加一个空行；**不写 `id:` 行**（测试断言流中没有 `\nid:`），因为现代流不可续传。
- **打标**：确认、每条通知、最终结果都带 `subscriptionId = listen 请求 id`，客户端据此把通知归属到哪个 listen 请求。
- **确认中返回"实际接受的过滤器"**：客户端可以对比自己请求的过滤器，知道哪些没被接受。
- `Cache-Control: no-cache` 防止中间缓存；`X-Accel-Buffering: no` 是常见反向代理（如 Nginx）识别的头，用于关闭代理缓冲，让事件即时下发。
- 这是一个**有限**的演示流：立即推送一条模拟的变更，然后发最终结果、关闭连接。真实实现会长期保持连接，在真实变更发生时推送，并可发 SSE 注释（以 `:` 开头的行）作为 keepalive。
- `BaseHTTPRequestHandler` 默认 `protocol_version = "HTTP/1.0"`，响应没有 `Content-Length`，连接关闭即流结束。
- ⚠️ `accepted_filter` 只检查请求里写了什么，不检查 server 能力和调用者授权：实测请求 `{"promptsListChanged": true, "resourceSubscriptions": ["file:///etc/passwd"]}` 时，确认消息"接受"了 prompts 列表变更（server 根本没有 prompts 能力）和 `file:///etc/passwd`，随后还推送了一条针对它的 `notifications/resources/updated`。应与 `SERVER_CAPABILITIES` 和主体可访问的资源集合取交集（测验 Q10）。

### 3.9 GET / DELETE 与 `serve`

```python
    def _method_not_allowed(self):
        ...
        self.send_response(405)
        self.send_header("Allow", "POST")
        ...

    def do_GET(self):
        if self._valid_path_and_origin():
            self._method_not_allowed()


def serve(host="127.0.0.1", port=0):
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
```

- GET / DELETE 也先过路径和 Origin 校验，再返回 `405` + `Allow: POST`（HTTP 规范要求 405 响应带 `Allow` 头）。
- 默认绑定 `127.0.0.1`（讲义："Local servers should bind to `127.0.0.1`, not every interface"），`port=0` 让操作系统分配空闲端口，测试和探针因此不会端口冲突。
- `ThreadingHTTPServer` 每个连接一个线程；`daemon=True` 让后台线程不阻止进程退出。
- `log_message` 被重写为写 **stderr**（带 `[mcp-http]` 前缀），所以运行时看到的访问日志与 stdout 的探针输出交织在一起。

### 3.10 小客户端 `post` 与探针 `probe`

```python
def post(url, message, headers):
    request = urllib.request.Request(url, data=json.dumps(message).encode("utf-8"),
                                     headers=dict(headers), method="POST")
    try:
        response = urllib.request.urlopen(request, timeout=3)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        ...
        return status, response_headers, json.loads(body) if body else None
    with response:
        body = response.read().decode("utf-8")
        if response.headers.get_content_type() == "application/json":
            payload = json.loads(body)
        else:
            payload = body
        return response.status, response.headers, payload
```

- `urlopen` 对 4xx/5xx 抛 `HTTPError`，但这个异常对象本身也是一个响应，可以 `read()` 出 body——这是读取 `400 + -32020` 等错误 body 的方法。
- `urllib` 会根据 `data` 自动设置 `Content-Length`，所以探针不必手写。
- SSE 响应作为整段文本返回（有限流，连接关闭后读完）。真实客户端需要逐行流式解析。
- `probe` 依次检查：非法 Origin、discover（无会话头）、带 `Mcp-Session-Id` / `Last-Event-ID` 的 `tools/list`（被忽略、不回显）、`Mcp-Method` 不一致、版本 2027、无 id 通知、GET、DELETE、`subscriptions/listen`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用 `http.server` 标准库 | 每个 HTTP 决策可见 | 生产用成熟的 ASGI/WSGI 框架或官方 SDK，放在反向代理之后 |
| 单端点、只接受 POST | 现代协议要求；任何副本都能处理任何请求 | 长期通知改由 `subscriptions/listen` 承载 |
| Origin 精确匹配、缺失放行 | 防 DNS rebinding，又不妨碍非浏览器客户端 | 允许列表需写全端口；Origin 不是认证，仍需 OAuth 等 |
| 严格的 Content-Length 规则 | 防请求走私、内存耗尽、半截 body | 不支持分块上传；超过 1 MiB 的请求被拒绝 |
| 结构 → 头一致 → 版本的顺序 | 与讲义生命周期一致，错误证据可区分 | — |
| `body_name` 两端共用 | 头的生成与校验规则只有一份 | — |
| 重复路由头 / Origin 直接拒绝 | 防止不同组件取到不同值 | — |
| 入口错误用非 JSON-RPC body | 让"可识别的现代错误"只出现在协议层 | 客户端需按状态码 + body 两步判断 |
| SSE 不写 event id | 现代流不可续传 | 断流后客户端需重新 listen 并重新拉取 |
| 有限的演示 listen 流 | 便于测试 | 真实实现需长连接、keepalive、真实变更源 |
| `accepted_filter` 照单全收 | 代码短 | 应与能力和授权取交集 |
| 无 id 即 `202` | 讲义对通知的规定 | 对"忘了带 id 的请求"不友好，可对已知请求方法报错 |
| 只在 body 阶段设置超时 | 简化 | 请求头阶段无超时；应设置 `Handler.timeout` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 继承标准库类并覆写方法 | `class Handler(BaseHTTPRequestHandler)`、`do_POST`、`log_message` | `http.server` 按 HTTP 方法名调用 `do_<METHOD>` |
| `%` 格式化 | `format_string % args` | 旧式字符串格式化，`log_message` 的接口约定 |
| `threading.Thread(daemon=True)` | `serve()` | 后台线程运行 `serve_forever`，守护线程随主线程退出 |
| `with` 语句 | `with response:` | 退出时自动关闭响应，释放连接 |
| `try / except ... as exc` / `raise ... from exc` | `decode_header_value` | 捕获并转换异常，保留异常链 |
| 多异常捕获 | `except (ValueError, json.JSONDecodeError, TimeoutError) as exc` | 一处处理多种失败 |
| `getattr(obj, name, default)` + `callable` | `get_all = getattr(headers, "get_all", None)` | 鸭子类型：有这个方法就用，没有就跳过 |
| 生成器表达式 + `all` / `any` | `all(0x20 <= ord(c) <= 0x7E for c in value)` | 逐字符检查，短路求值 |
| `ord()` 与十六进制字面量 | `ord(character) <= 0x7E` | 字符的码点；`0x7E` 是 `~` |
| 切片去前后缀 | `value[len("=?base64?") : -2]` | 去掉 `=?base64?` 前缀和 `?=` 后缀 |
| `str.isascii()` / `isdigit()` | `raw_length.isascii() and raw_length.isdigit()` | 两者组合才等于"纯 ASCII 数字" |
| `str.split(";", 1)[0].strip().lower()` | 解析 Content-Type | 只拆一次，取主类型并规范化 |
| `base64.b64encode` / `b64decode(validate=True)` | 哨兵编解码 | 字节 ↔ Base64 文本；`validate` 拒绝非法字符 |
| `bytes` 与 `str` 转换 | `.encode("utf-8")`、`.decode("ascii")` | 网络上传的是字节 |
| `typing.Mapping` | `headers: Mapping[str, str]` | 只读映射类型注解，dict 和 `email.message.Message` 都可传 |
| 集合 | `ORIGIN_ALLOWLIST = {...}`、`in {"tools/call", "resources/read", "prompts/get"}` | 精确的成员判断 |
| 数字分隔符 | `MAX_REQUEST_BYTES = 1_048_576` | 1 MiB |
| f-string 中的嵌套引号 | `f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"` | 外层双引号、内层单引号 |
| `str.removeprefix` | 测试中 `line.removeprefix("data: ")` | 去掉 SSE 行前缀后解析 JSON |
| 条件表达式 | `json.loads(body) if body else None` | 空 body 时返回 `None` |

---

## 6. 运行结果解读

`python3 main.py` 实际输出（`[mcp-http]` 开头的行是写到 stderr 的访问日志）：

```text
MCP 2026-07-28 Streamable HTTP probe
[mcp-http] "POST /mcp HTTP/1.1" 403 -
  invalid Origin: HTTP 403
[mcp-http] "POST /mcp HTTP/1.1" 200 -
  discovery: HTTP 200, version=2026-07-28, session-header=None
[mcp-http] "POST /mcp HTTP/1.1" 200 -
  removed headers ignored: HTTP 200, tool=ping, echo=None
[mcp-http] "POST /mcp HTTP/1.1" 400 -
  header mismatch: HTTP 400, code=-32020
[mcp-http] "POST /mcp HTTP/1.1" 400 -
  unsupported version: HTTP 400, code=-32022
[mcp-http] "POST /mcp HTTP/1.1" 202 -
  accepted notification: HTTP 202, empty-body=True
[mcp-http] "GET /mcp HTTP/1.1" 405 -
  GET: HTTP 405
[mcp-http] "DELETE /mcp HTTP/1.1" 405 -
  DELETE: HTTP 405
[mcp-http] "POST /mcp HTTP/1.1" 200 -
  subscriptions/listen: HTTP 200, SSE=True, tagged=True
```

逐项解读：

- **invalid Origin → 403**：`http://evil.example` 不在允许列表。
- **discovery → 200，`session-header=None`**：server 没有签发 `Mcp-Session-Id`。
- **removed headers ignored**：请求带了 `Mcp-Session-Id: ignored` 和 `Last-Event-ID: ignored`，server 正常处理 `tools/list`，也没有回显会话头。
- **header mismatch → 400 / -32020**：body 是 `tools/list`，头写成 `tools/call`。
- **unsupported version → 400 / -32022**：头和 body 一致为 2027，进入版本检查。
- **notification → 202，空 body**：探针把一个 `tools/list` 去掉 id 当作通知发送——只为演示 `202`，真实通知方法应是 `notifications/...`（见 3.7 的提醒）。
- **GET / DELETE → 405**。
- **listen → 200、SSE、带 subscriptionId**：响应是 `text/event-stream`，流中有确认消息且带订阅 id。用 `toolsListChanged: true` 请求时，流中依次是确认、`notifications/tools/list_changed`、最终结果。

测试：`python3 -m unittest discover tests -v` 实测 **18 个测试全部通过**（`Ran 18 tests in 1.218s, OK`）。

我们另外实测了讲义练习 1 和 3：删除 `Mcp-Method` → `400 -32020 Header mismatch: Mcp-Method`；`resources/read` 的 `uri` 为 `notes://笔记-1`，Base64 哨兵头匹配通过后得到 `404 -32601`（本 server 未实现 `resources/read`），把头换成另一个 URI 的哨兵则得到 `400 -32020`——说明解码后的值确实与 `params.uri` 做了比较。

---

## 7. 动手改一改

1. **讲义练习 1、2**：用 `http_headers_for` 生成头后删掉 `Mcp-Method`，确认 `400 / -32020`；发送头与 body 都是 `2027-01-01` 的请求，确认 `400 / -32022` 且 `data == {"supported": ["2026-07-28"], "requested": "2027-01-01"}`。
2. **讲义练习 3**：实现一个最小的 `resources/read`（返回固定内容），用 `notes://笔记-1` 测试 Base64 哨兵；再构造一个"原值恰好是 `=?base64?abc?=`"的名称，确认 `encode_header_value` 会把它编码而不是原样发送。
3. **修复订阅过滤**：让 `accepted_filter` 与 `SERVER_CAPABILITIES` 以及当前主体可访问的资源集合取交集，并只在真实变更时推送通知（参考测验 Q10）。
4. **讲义练习 4**：把 listen 流改成"推送确认后，在发送最终结果前断开连接"；写一个客户端循环：检测到流在最终结果前结束，就用**新的** JSON-RPC id 重新发起 `subscriptions/listen`，并重新拉取 `tools/list`。
5. **讲义练习 5**：给 `ping` 增加 `draft_start` / `draft_append`，用不可猜测的 handle + 共享存储 + 主体绑定实现跨副本草稿（参考测验 Q12）；用两个 `serve()` 实例共享同一个 dict 模拟两个副本，交替发请求验证。
6. **加固**：设置 `Handler.timeout = READ_TIMEOUT_SECONDS`；对缺少 `id` 的已知请求方法（`tools/*`、`resources/*`、`prompts/*`、`server/discover`）返回 `400 / -32600`；把 `SERVER_CAPABILITIES.copy()` 换成 `deepcopy`；为这些行为补测试。

---

## 8. 常见坑

- **把 2025 版的 GET 流 / 会话 id 当作现代行为**：现代端点只有 POST，GET / DELETE 都是 `405`。
- **只看头不看 body（或反之）**：两者必须一致，否则网关和源站可能在处理不同的操作。
- **先报 `-32022` 再查头一致性**：会掩盖头被篡改或构造错误的问题。
- **Origin 用前缀匹配**：`startswith` 会放过攻击者控制的域名。
- **以为 Origin 校验等于认证**：它只防 DNS rebinding。
- **直接把非 ASCII 名称放进头里**：用 Base64 哨兵。
- **给 SSE 事件加 id、支持 `Last-Event-ID`**：现代流不可续传，断流就重新请求。
- **listen 流中的通知不打 `subscriptionId`**：客户端无法把通知归属到对应的订阅请求。
- **`str.isdigit()` 校验数字**：会接受 `²` 等 Unicode 数字字符。
- **同时接受 Content-Length 与 Transfer-Encoding**：请求走私的经典条件。
- **用 sticky session 解决有状态工作流**：重启、发布、故障转移时就会失效；用显式 handle + 共享存储。
- **用 301/302 把 POST 重定向到新端点**：方法和 body 不一定被保留。

---

## 9. 测试在验证什么

`tests/test_main.py` 在 `setUpClass` 中用 `main.serve()` 启动一个真实的本地 HTTP server（随机端口），所有测试共用它，`tearDownClass` 中关闭。普通请求用 `main.post`（`urllib`），需要发送重复头或畸形 Content-Length 的测试用 `raw_post`（`http.client` 的 `putrequest` / `putheader` 手工构造请求，`urllib` 做不到发送重复头）。在 `code/` 下运行 `python3 -m unittest discover tests -v`，实测 **18 个测试全部通过**。

| 测试 | 验证的性质 | 对应讲义 |
|------|-----------|---------|
| `test_invalid_origin_is_rejected` | 非允许 Origin → `403`，body 为 `{"error": "Origin not allowed"}` | Origin 校验 |
| `test_duplicate_origin_is_rejected_before_allowlist_evaluation` | 两个 Origin（一个合法一个非法）→ `400 -32020 Duplicate Origin header` | 解释一致性 |
| `test_discovery_has_no_protocol_session` | discover `200`，响应无 `Mcp-Session-Id`，结果 complete 且带 serverInfo | 无协议会话 |
| `test_removed_session_and_replay_headers_are_ignored` | 带 `Mcp-Session-Id` 与 `Last-Event-ID` 仍正常返回，且不回显会话头 | 已移除的头被忽略 |
| `test_header_mismatch_is_modern_error` | `Mcp-Method` 与 body 不一致 → `400 -32020` | 镜像头校验 |
| `test_conflicting_duplicate_name_headers_are_rejected` | 两个不同的 `Mcp-Name` → `400 -32020` | 重复路由头 |
| `test_invalid_and_oversized_content_lengths_are_rejected` | 缺失、非数字、`-1`、超过 1 MiB → `400 -32700`（`subTest` 逐个） | body 定界 |
| `test_content_length_accepts_only_ascii_decimal_digits` | `+1`、`1.0`、`²` → `400 -32700`，detail 为 "Content-Length must contain ASCII decimal digits" | 纯 ASCII 数字 |
| `test_conflicting_content_lengths_are_rejected_before_body_read` | 两个不同的 Content-Length → `400`，detail 含 "duplicate Content-Length" | 请求走私防护 |
| `test_content_length_with_transfer_encoding_is_rejected_before_body_read` | Content-Length + `Transfer-Encoding: chunked` → `400`，detail 含 "Transfer-Encoding" | 请求走私防护 |
| `test_unsupported_matching_version_advertises_supported` | 头与 body 都是 2027 → `400 -32022`，`data` 精确等于 `{"supported": [...], "requested": "2027-01-01"}` | 版本协商（讲义练习 2） |
| `test_accepted_notification_returns_202_without_a_body` | 无 id 消息 → `202`，body 为空字符串 | 通知的 HTTP 语义 |
| `test_non_string_protocol_version_is_invalid_params` | body 版本为 `null` → `400 -32602` | 结构校验先于头校验 |
| `test_get_and_delete_return_405` | GET、DELETE → `405`，`Allow: POST` | POST-only |
| `test_tool_list_is_cacheable_and_deterministic` | 工具名有序，`ttlMs == 30000`、`cacheScope == "public"` | 可缓存结果 |
| `test_base64_name_is_decoded_before_comparison` | `ping-世界` 走 Base64 哨兵，头校验通过、得到 `200` + `isError` | Base64 哨兵（讲义练习 3 的 tools 版） |
| `test_subscriptions_listen_is_post_scoped_sse` | listen 返回 `text/event-stream`，含确认与 subscriptionId，没有 `id:` 行，最后一条是 complete 结果且 `_meta.subscriptionId == "listen-8"` | `subscriptions/listen` |
| `test_default_command_runs_the_finite_probe` | 以子进程运行 `python main.py`，退出码 0 且输出探针标题 | 默认入口是有限探针 |

值得补充的测试：`accepted_filter` 不应接受 server 未声明的能力和未授权的资源；缺 `id` 的 `tools/call` 的处理策略；请求头阶段的超时；带端口的 Origin 配置；listen 流在最终结果前断开后的客户端重试（讲义练习 4）。
