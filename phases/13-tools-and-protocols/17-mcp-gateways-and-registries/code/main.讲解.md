# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 17 节 Stateless MCP 网关与注册表准入 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`hashlib`、`json`、`time`、`dataclasses`、`typing`），无需网络

---

## 1. 这份代码在考察什么

这是一个**进程内的网关协议模型**：一个 `Gateway` 对象站在两个进程内后端（`notes`、`issues`）前面，输入是"已认证的 bearer 字符串 + 已解析的 body + 路由头"，输出 `(HTTP 状态, 响应或 None)`。它把讲义"现代网关路径"中的大部分接缝写成了代码：

1. **入口校验**：只接受 POST；bearer 查表认证；`validate_wire` 校验 `_meta`、头 body 一致（`-32020`）、版本（`-32022`）。
2. **发现与列表**：网关自己的 `server/discover`（`private` 缓存）；`tools/list` 按 principal 的 RBAC 过滤、只含已准入且 descriptor pin 一致的工具、按公开名排序。
3. **注册表准入**：`server.json` 发布形状校验 + 外部"已验证准入状态"拼接（`registry_record_is_admissible`）。
4. **调用路径**：RBAC（403）→ 按 principal 的令牌桶限流（429）→ descriptor pin（409）→ 为后端构造全新的自包含请求（`gw-N` id）→ 去掉后端 `_meta` 后返回 → 审计。
5. **订阅**：`subscriptions/listen` 需要 SSE（否则 406），只确认 `toolsListChanged`，subscriptionId 等于请求 id。
6. **Tasks 路由键**：`tasks/get|update|cancel` 用 `taskId` 作 `Mcp-Name`（网关本身未实现这些方法）。

> 一句话：**网关让每一条路由都显式化——没有会话，每个请求都携带方法、名称、版本、能力与身份，网关据此独立做出决定并为后端重新构造请求**。同时要看清它省略或遗漏了什么（最重要的是：`tools/call` 没有复查准入），这些正是练习与测验的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NAMED_METHODS` | 常量集合 | 需要 `Mcp-Name` 的方法（含三个 tasks 方法） | 路由头 |
| `USERS` / `RBAC` | 常量 | bearer → principal/角色；principal → 允许的公开工具 | 认证与授权（模拟） |
| `REGISTRY_SERVER_JSON` | 常量 | 两条 Registry `server.json` 发布记录 | 注册表发现 |
| `VERIFIED_ADMISSION_STATE` | 常量 | 与发布记录分开的准入证据：发布者、来源、审批 | 准入记录 |
| `ProtocolError` | frozen dataclass 异常 | JSON-RPC 错误 | 协议错误 |
| `request_meta` / `request_name` / `make_request` | 函数 | 构造信封；tasks 方法取 `taskId` 作名称 | 无状态请求 |
| `descriptor_digest` | 函数 | 规范化 JSON → SHA-256 | descriptor pin |
| `registry_record_is_admissible` | 函数 | `server.json` 形状 + 外部准入状态 | 注册表 ≠ 决策 |
| `validate_wire` | 函数 | 网关与后端共用的线协议校验 | 校验顺序 |
| `BackendServer` | 类 | 极简后端：discover / list / call | 后端 MCP 服务端 |
| `TokenBucket` | dataclass | 令牌桶限流 | 无会话限流 |
| `Gateway` | 类 | pins、buckets、audit、forwarded ids；`handle` 主逻辑 | MCP 网关 |
| `demo` | 函数 | 依次 discover、list、call、listen，并打印转发 id 与审计 | 端到端 |

数据流（一次被允许的 `tools/call`）：

`handle(bearer, body, headers)` → POST? → `USERS[bearer]` → `validate_wire` → RBAC → `TokenBucket.consume` → 查后端工具 + `_is_pinned` → `_forward`（`make_request` 生成 `gw-N` 新请求 → `BackendServer.handle` → `validate_wire` → 执行）→ 去掉后端 `_meta` → 审计 `allow` → `_success`（补网关 serverInfo）→ `(200, response)`。

---

## 3. 逐段精讲

### 3.1 静态数据：身份、RBAC、注册表与准入

```python
USERS = {
    "bearer-alice": {"id": "alice", "role": "developer"},
    "bearer-bob": {"id": "bob", "role": "auditor"},
}
RBAC = {
    "alice": {"notes.search", "notes.create", "issues.list", "issues.open"},
    "bob": {"notes.search", "issues.list"},
}
```

- `USERS` 模拟"传输授权已经被验证"后的结果：bearer 字符串 → principal。真实网关会按第 16 节验证 token 的签名、issuer、audience。
- `RBAC` 直接以**公开名**（限定名）为单位授权——讲义 "Qualified public name before authorization"。注意 `role` 字段没有被使用，授权是按用户 ID 而不是按角色。

`REGISTRY_SERVER_JSON` 是两条发布记录：`$schema`、`name`（`com.example/notes`）、`description`、`version`、`packages`（npm 包、`stdio` 传输）。`VERIFIED_ADMISSION_STATE` 是**另一份**数据：`registryName`、`registryVersion`、`publisher`（命名空间与验证状态）、`provenance`（来源注册表与记录 ID）、`admission`（审批状态与审批者）。讲义："Publication metadata does not carry the gateway's security decision. Keep verified publisher and provenance evidence in separate admission state."

### 3.2 请求构造与 `request_name`

```python
def request_name(method: str, params: dict[str, Any]) -> Any:
    if method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        return params.get("taskId")
    return params.get("name") or params.get("uri")
```

- 工具调用、prompt 用 `name`，资源读取用 `uri`，Tasks 方法用 `taskId`——讲义："use `params.taskId` as `Mcp-Name`, which gives intermediaries a routing key."
- `make_request` 只为 `NAMED_METHODS` 设置 `Mcp-Name`；名称缺失时写成 `""`，与 body 中的 `None` 不等，会得到 `-32020`（与前几节相同的小瑕疵）。
- `client_name` 关键字参数让网关转发时以自己的身份（`enterprise-gateway`）出现在 `clientInfo` 中。

### 3.3 `descriptor_digest` 与 `registry_record_is_admissible`

`descriptor_digest` 与第 15 节完全相同：规范化 JSON 后 SHA-256。

```python
def registry_record_is_admissible(record, admission, namespace: str = "com.example/") -> bool:
    packages = record.get("packages")
    package_shapes_are_valid = isinstance(packages, list) and bool(packages) and all(
        isinstance(package, dict)
        and isinstance(package.get("registryType"), str)
        and isinstance(package.get("identifier"), str)
        and isinstance(package.get("version"), str)
        and isinstance(package.get("transport"), dict)
        and package["transport"].get("type") == "stdio"
        for package in packages
    )
    return bool(
        isinstance(record.get("name"), str)
        and record["name"].startswith(namespace)
        and isinstance(record.get("description"), str)
        and record.get("version") == admission.get("registryVersion")
        and record.get("name") == admission.get("registryName")
        and package_shapes_are_valid
        and admission.get("publisher", {}).get("namespace") == "com.example"
        and admission.get("publisher", {}).get("status") == "verified"
        and admission.get("provenance", {}).get("source") == "registry.modelcontextprotocol.io"
        and admission.get("admission", {}).get("status") == "approved"
    )
```

两段逻辑：

1. **发布形状**：`packages` 非空列表，每个包有字符串 `registryType`/`identifier`/`version` 和 `stdio` 传输。`bool(packages)` 排除空列表；`all(...)` 对空列表会返回 `True`，所以前面的 `bool(packages)` 是必要的。
2. **拼接准入状态**：记录名与版本必须与准入记录一致（版本 pin），发布者已验证，来源是官方注册表，审批状态为 `approved`。

`bool(a and b and ...)`：`and` 链返回最后一个被求值的操作数（可能是字符串、字典），外层 `bool` 把它规范成 `True`/`False`。

⚠️ 问题与简化：

- `namespace` 参数只用于名称前缀；发布者命名空间写死为 `"com.example"`，来源写死为官方注册表。实测 `namespace="org.acme/"` + 已验证的 `org.acme` 发布者仍返回 `False`。
- 未校验 `provenance.recordId` 与 `name@version` 一致，未校验 `$schema`。
- 讲义清单中的端点、descriptor/制品摘要、issuer/resource、审批时间与过期都不在准入记录中（讲义也说明完整控制面在第 30 节）。
- 只接受官方注册表来源，私有服务端无法用"同一证据模式"准入。

### 3.4 `validate_wire`：网关与后端共用

与前三节相同的顺序：形状（`-32600`）→ `_meta` 类型（`-32602`）→ 三个头与 body 一致（`-32020`）→ 版本（`-32022`）。区别是它是模块级函数，`BackendServer.handle` 也调用它——后端同样独立校验网关发来的请求，体现"每一跳都是自包含请求"。

### 3.5 `BackendServer`：最小后端

```python
    def handle(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        params = validate_wire(body, headers)
        if body["method"] == "server/discover":
            result = {..., "capabilities": {"tools": {"listChanged": True}}, "ttlMs": 60_000, "cacheScope": "public"}
        elif body["method"] == "tools/list":
            result = {"tools": sorted(self.tools, key=lambda tool: tool["name"]), "ttlMs": 30_000, "cacheScope": "public"}
        elif body["method"] == "tools/call":
            tool = next((item for item in self.tools if item["name"] == params.get("name")), None)
            if tool is None:
                raise ProtocolError(-32601, "Tool not found")
            result = {"content": [{"type": "text", "text": f"{self.name}.{tool['name']} completed"}], "isError": False}
        else:
            raise ProtocolError(-32601, "Method not found")
        return self._success(body.get("id"), result)
```

- `self.tools = json.loads(json.dumps(tools))`：深拷贝，测试可以直接修改某个后端的工具描述来模拟 rug pull。
- `next(生成器, None)`：找第一个匹配项，找不到返回 `None`——比写 for 循环 + break 更紧凑。
- 后端自己的 `tools/list` 是 `public`（与用户无关），网关的列表则是 `private`（因 RBAC 过滤而因人而异）。
- ⚠️ 后端只**抛出** `ProtocolError`，不返回 JSON-RPC 错误信封；网关的 `_forward` 直接取 `["result"]`。由于网关在转发前已经做了 pin 检查，正常路径下不会触发后端错误。
- ⚠️ 网关从不调用后端的 `server/discover`——讲义 "It also discovers each backend ... Advertise only the capability intersection" 在代码中没有体现，网关的能力是写死的。

### 3.6 `TokenBucket`：无会话的限流

```python
@dataclass
class TokenBucket:
    capacity: int = 5
    refill_per_second: float = 1.0
    tokens: float = 5.0
    updated_at: float = field(default_factory=time.monotonic)

    def consume(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        self.tokens = min(self.capacity, self.tokens + max(0.0, current - self.updated_at) * self.refill_per_second)
        self.updated_at = current
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True
```

- 经典令牌桶：容量 5，每秒补 1 个；按流逝时间**惰性补充**（不需要后台定时器）。
- `time.monotonic()`：单调时钟，不受系统时间调整影响，适合测量间隔；`field(default_factory=time.monotonic)` 在创建时取当前值。
- `max(0.0, ...)`：防止时钟回拨时令牌变负。`min(self.capacity, ...)`：封顶。
- `now` 参数可注入，方便测试。实测：`TokenBucket(tokens=0, updated_at=100.0)` 依次 `consume(100.5)` → `False`（0.5）、`consume(101.0)` → `True`（0.0）、`consume(110)` → `True`（4）。被拒绝的调用也会累积部分令牌。

### 3.7 `Gateway.__init__`：后端、pin、状态

```python
        self.pins = {
            f"{server_name}.{tool['name']}": descriptor_digest(tool)
            for server_name, backend in self.backends.items()
            for tool in backend.tools
        }
        self.buckets: dict[str, TokenBucket] = {}
        self.audit: list[dict[str, Any]] = []
        self.forwarded_request_ids: list[str] = []
```

- pin 在构造时由当前后端工具计算——模型中"启动即批准"；真实系统中 pin 来自审批记录。
- `buckets` 以用户 ID 为键；`audit` 是内存列表；`forwarded_request_ids` 用于演示"新的后端请求 id"。
- 没有任何会话字段（测试 `test_legacy_headers_do_not_create_gateway_state` 断言 `not hasattr(self.gateway, "sessions")`）。

### 3.8 `_visible_tools`：准入 + RBAC + pin 的三重过滤

```python
    def _visible_tools(self, user_id: str) -> list[dict[str, Any]]:
        visible = []
        for server_name, backend in self.backends.items():
            if not registry_record_is_admissible(REGISTRY_SERVER_JSON[server_name], VERIFIED_ADMISSION_STATE[server_name]):
                continue
            for tool in backend.tools:
                canonical = f"{server_name}.{tool['name']}"
                if canonical in RBAC.get(user_id, set()) and self._is_pinned(canonical, tool):
                    visible.append({**tool, "name": canonical})
        return sorted(visible, key=lambda tool: tool["name"])
```

- 后端未准入 → 整个后端跳过；工具不在用户 RBAC 中或 pin 不一致 → 跳过。
- `{**tool, "name": canonical}`：保留 description 与 `inputSchema`，只把名字换成公开名——讲义 "Namespacing cannot remove required descriptor fields."
- 结果排序：alice 看到 `issues.list, issues.open, notes.create, notes.search`；bob 看到 `issues.list, notes.search`（实测）。

### 3.9 `_forward`：为后端构造全新请求

```python
    def _forward(self, canonical_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        server_name, tool_name = canonical_name.split(".", 1)
        backend = self.backends[server_name]
        forwarded_id = f"gw-{len(self.forwarded_request_ids) + 1}"
        self.forwarded_request_ids.append(forwarded_id)
        body, headers = make_request("tools/call", forwarded_id, {"name": tool_name, "arguments": arguments},
                                     client_name="enterprise-gateway")
        return backend.handle(body, headers)["result"]
```

- 公开名 `notes.search` 拆成后端 `notes` 与原始工具名 `search`（`split(".", 1)` 只切一次，工具名中若再有点也不会出错）。
- 新的 JSON-RPC id、新的 `_meta`（网关自己的 `clientInfo`、能力 `{}`）、新的路由头：讲义 "Create a fresh self-contained request" 与 "Do not blindly copy the outer client capabilities"。
- 外层 bearer **没有**传给后端（后端 `handle` 根本不接收凭证）。真实网关会用为该后端 issuer/resource 单独获取的 token。
- ⚠️ `gw-N` 由网关实例内的计数生成，多实例部署会重复；且没有把外层 id 与 `gw-N` 的对应关系写入审计（讲义练习 1 要求加入 trace context 并在审计中关联）。

### 3.10 `handle`：入口与认证

```python
        if http_method != "POST":
            return 405, None
        is_notification = "id" not in body
        user = USERS.get(bearer)
        if user is None:
            if is_notification:
                return 401, None
            return 401, self._error(body.get("id"), ProtocolError(-32001, "Unauthenticated"))
```

- 先 405，再认证，**然后**才是线协议校验——对应讲义七步中"1. Authenticate"排在"2. Validate"之前。实测未知 bearer 即使头部不一致也是 401。
- 认证失败也用 JSON-RPC 错误信封（带原 id）；notification 只返回状态码。

### 3.11 `handle`：`server/discover` 与 `tools/list`

- 网关 discovery：`supportedVersions`、`capabilities: {"tools": {"listChanged": True}}`、`ttlMs: 30_000`、`cacheScope: "private"`——与讲义示例逐字一致。为什么 discovery 也是 private？练习 4：一旦能力因 principal 而不同（例如某些用户能用 Tasks），就不能共享缓存。
- `tools/list`：`_visible_tools(user["id"])`、`ttlMs: 10_000`、`private`。

### 3.12 `handle`：`tools/call` 的检查链

```python
                canonical = str(params.get("name", ""))
                if canonical not in RBAC.get(user["id"], set()):
                    self.audit.append({"principal": user["id"], "tool": canonical, "decision": "deny"})
                    raise ProtocolError(-32003, "Forbidden", {"tool": canonical})
                bucket = self.buckets.setdefault(user["id"], TokenBucket())
                if not bucket.consume():
                    self.audit.append({..., "decision": "rate_limit"})
                    if is_notification:
                        return 429, None
                    return 429, self._error(body.get("id"), ProtocolError(-32029, "Rate limited"))
                server_name, tool_name = canonical.split(".", 1)
                tool = next((item for item in self.backends[server_name].tools if item["name"] == tool_name), None)
                if tool is None or not self._is_pinned(canonical, tool):
                    self.audit.append({..., "decision": "pin_mismatch"})
                    ...
                    return 409, self._error(body.get("id"), ProtocolError(-32010, "Descriptor changed", {"tool": canonical}))
                backend_result = self._forward(canonical, params.get("arguments", {}))
                result = {key: value for key, value in backend_result.items() if key != "_meta"}
                self.audit.append({..., "decision": "allow"})
```

| 步骤 | 失败结果 | 审计 |
|------|---------|------|
| RBAC | 403、`-32003`、`data.tool` | `deny` |
| 令牌桶 | 429、`-32029` | `rate_limit` |
| 工具存在且 pin 一致 | 409、`-32010`、`data.tool` | `pin_mismatch` |
| 转发 | — | `allow` |

- `-32003`、`-32029`、`-32010` 及 403/429/409 映射都是本代码自定的，讲义只规定了 `-32020`、`-32022`、`-32601`。
- `{key: value for ... if key != "_meta"}`：丢弃后端的 `_meta`（后端的 serverInfo），由网关 `_success` 补上自己的身份——客户端看到的是网关，不是后端。讲义还要求"Validate the backend result"，这里只是剥离了 `_meta`，没有做结构校验。
- `self.buckets.setdefault(user["id"], TokenBucket())`：没有桶时创建并返回。

⚠️ 需要重点关注的问题（均已实测）：

1. **`tools/call` 不检查准入**：把 `notes` 的准入状态改为 `revoked` 后，`tools/list` 不再显示 `notes.*`，但直接调用 `notes.search` 仍得到 200 与 `allow` 审计。列表过滤不等于授权；讲义要求运行时策略以准入证据为输入。修复：让 list 与 call 共用同一个路由检查函数（测验 Q9）。
2. **便宜的 pin 检查放在限流之后**：已下架工具的调用也消耗配额，连续 6 次调用得到 `[409, 409, 409, 409, 409, 429]`。
3. **RBAC 拒绝不计入任何限额**：bob 连续 10 次无权调用后仍没有桶，可以无限探测工具名。讲义要求明确"被拒调用是否计入滥用限额"。
4. **限流键只有用户 ID**：讲义要求 principal + issuer + resource + 工具 + 成本类别 + 时间窗。
5. **不校验参数**：`arguments="DROP"` 被原样转发，返回 200。
6. **notification 会执行调用**：删掉 id 的 `tools/call` 返回 `(202, None)`，但已转发（`forwarded_request_ids == ['gw-1']`）并记录 `allow`。
7. **审计字段太少**：只有 principal、tool、decision；没有请求/追踪 ID、后端路由、pin 版本、原因、延迟。

### 3.13 `handle`：`subscriptions/listen`

```python
            elif method == "subscriptions/listen":
                if "text/event-stream" not in accept:
                    ...
                    return 406, self._error(body.get("id"), ProtocolError(-32602, "subscriptions/listen requires an SSE response"))
                requested = params.get("notifications", {})
                if not isinstance(requested, dict):
                    raise ProtocolError(-32602, "notifications must be an object")
                honored = {}
                if requested.get("toolsListChanged") is True:
                    honored["toolsListChanged"] = True
                ...
                return 200, {
                    "contentType": "text/event-stream",
                    "events": [{
                        "jsonrpc": "2.0",
                        "method": "notifications/subscriptions/acknowledged",
                        "params": {"_meta": {SUBSCRIPTION_ID_META: body.get("id")}, "notifications": honored},
                    }],
                }
```

- 客户端 `Accept` 不含 `text/event-stream` → 406（"Not Acceptable"）。用子串判断是简化；真实实现要解析媒体类型与 q 值。
- 只确认网关真正支持的 `toolsListChanged`，且值必须是 `True`（`is True`）；`resourcesListChanged` 等被静默丢弃——讲义 "The first event acknowledges the supported subset."
- subscriptionId 就是请求 id（demo 中是整数 4，测试中是字符串 `"listen-tools"`）。
- 返回值用一个字典**模拟** SSE 响应（`contentType` + `events` 列表），并不是 JSON-RPC 信封；之后的变化通知、优雅关闭时的最终结果都没有实现。

### 3.14 `handle`：异常出口

```python
        except (KeyError, ValueError):
            if is_notification:
                return 400, None
            return 400, self._error(body.get("id"), ProtocolError(-32602, "Invalid params"))
        except ProtocolError as error:
            status = 403 if error.code == -32003 else self._error_status(error)
            ...
```

- 第一个 `except` 兜底 `KeyError`/`ValueError`（例如公开名拆分或字典取值失败），统一成 `-32602`。在当前数据下几乎不可达（RBAC 已保证名字合法），但宽泛地捕获 `KeyError` 也可能掩盖真正的编程错误。
- `-32003` 特判为 403，`-32601` 为 404，其余 400。

### 3.15 `demo`

依次以 alice 身份调用 `server/discover`、`tools/list`、`tools/call notes.search`、`subscriptions/listen`，每个响应截取前 260 个字符打印，最后打印转发 id 与审计。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 进程内后端对象 | 聚焦网关逻辑 | 真实后端是远程 MCP 客户端连接；需要超时、重试、熔断 |
| bearer 查表认证 | 省略第 16 节的 token 验证 | 生产验证签名、issuer、audience，并区分外层与后端凭证 |
| RBAC 以公开名为单位 | 审批、审计、路由引用同一对象 | `role` 字段未使用；生产用角色/属性策略并校验参数 |
| `server.json` 与准入状态分离 | 发布元数据不承载安全决策 | 命名空间、来源写死；缺端点、摘要、issuer、过期；只在 list 上检查 |
| 启动时计算 descriptor pin | 简单 | pin 应来自审批记录，并与准入记录关联 |
| list 与 call 各自实现检查 | 代码直观 | 两条路径不一致（call 漏准入）；应共用一个路由函数 |
| 令牌桶以用户 ID 为键、内存保存 | 演示无会话限流 | 键维度不足；多实例需共享存储；pin 检查应在限流前 |
| 为后端构造 `gw-N` 新请求、剥离后端 `_meta` | 每一跳自包含，客户端只看到网关身份 | id 在多实例下重复；未做结果校验与追踪关联 |
| 自定义错误码（-32003/-32029/-32010）与状态（403/429/409） | 语义清晰 | 讲义未规定，客户端需按本网关约定处理 |
| `subscriptions/listen` 只建模确认事件 | 展示过滤与 subscriptionId 规则 | 没有后续通知、关闭语义与后端联动 |
| 网关能力写死、不做后端 discovery | 代码短 | 违背"只宣告能力交集"；生产需周期性探测后端 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 集合字面量常量 | `NAMED_METHODS = {"tools/call", ...}` | 成员判断 O(1) |
| 嵌套字典常量 | `REGISTRY_SERVER_JSON`、`VERIFIED_ADMISSION_STATE` | 以 JSON 形式描述配置 |
| `dict.get` 链 | `admission.get("publisher", {}).get("namespace")` | 缺失时给空字典，避免 `KeyError` |
| `all()` + 生成器 | `all(isinstance(package, dict) and ... for package in packages)` | 全部满足才为真；空序列返回 `True` |
| `bool(a and b and ...)` | `return bool(isinstance(...) and ...)` | `and` 链返回操作数本身，`bool` 规范化 |
| `str.startswith` | `record["name"].startswith(namespace)` | 前缀匹配 |
| `next(生成器, 默认值)` | `next((item for item in self.tools if ...), None)` | 取第一个匹配项 |
| `@dataclass` + `field(default_factory=...)` | `updated_at: float = field(default_factory=time.monotonic)` | 每个实例创建时调用一次工厂函数 |
| `time.monotonic()` | `TokenBucket.consume` | 单调时钟，测间隔用 |
| `min` / `max` 截断 | `min(self.capacity, ...)`、`max(0.0, ...)` | 上下限 |
| 条件表达式 | `time.monotonic() if now is None else now` | 可注入时间 |
| 双层字典推导式 | `self.pins = {f"{s}.{t['name']}": ... for s, b in ... for t in b.tools}` | 生成 pin 表 |
| 字典推导式过滤 | `{key: value for key, value in backend_result.items() if key != "_meta"}` | 去掉一个键 |
| `str.split(".", 1)` 解包 | `server_name, tool_name = canonical.split(".", 1)` | 最多切一次；段数不对会抛 `ValueError` |
| `str.partition` | （测验 Q9 的重构中）`canonical.partition(".")` | 总是返回三元组，不抛异常 |
| `dict.setdefault` | `self.buckets.setdefault(user["id"], TokenBucket())` | 注意：默认值表达式**每次都会求值**（即使键已存在也会创建一个被丢弃的 `TokenBucket`） |
| 字典解包 | `{**tool, "name": canonical}` | 复制并覆盖 |
| `json.loads(json.dumps(x))` | `BackendServer.__init__` | 简易深拷贝 |
| `enumerate(..., start=1)` + 解包 | `for request_id, (method, params) in enumerate([...], start=1)` | id 从 1 开始 |
| 多异常捕获 | `except (KeyError, ValueError):` | 元组 |
| `is True` | `requested.get("toolsListChanged") is True` | 只接受真正的布尔真 |
| 关键字参数默认值 | `handle(..., *, http_method="POST", accept="application/json, text/event-stream")` | 调用时可覆盖 |
| f-string 生成 id | `f"gw-{len(self.forwarded_request_ids) + 1}"` | 表达式可直接写在花括号里 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（每行截取前 260 个字符）：

```text
200 server/discover {"jsonrpc": "2.0", "id": 1, "result": {"supportedVersions": ["2026-07-28"], "capabilities": {"tools": {"listChanged": true}}, "ttlMs": 30000, "cacheScope": "private", "resultType": "complete", "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "enterpris
200 tools/list {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "issues.list", "description": "List tracked issues.", "inputSchema": {"type": "object", "properties": {}}}, {"name": "issues.open", "description": "Open an issue.", "inputSchema": {"type": "object", "pr
200 tools/call {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "notes.search completed"}], "isError": false, "resultType": "complete", "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "enterprise-gateway", "version": "2.0.0"}}}}
200 subscriptions/listen {"contentType": "text/event-stream", "events": [{"jsonrpc": "2.0", "method": "notifications/subscriptions/acknowledged", "params": {"_meta": {"io.modelcontextprotocol/subscriptionId": 4}, "notifications": {"toolsListChanged": true}}}]}
forwarded request ids: ['gw-1']
audit: [{'principal': 'alice', 'tool': 'notes.search', 'decision': 'allow'}]
```

逐项解读：

- **discover**：`cacheScope: "private"`、`ttlMs: 30000`，与讲义示例一致；serverInfo 是网关自己的 `enterprise-gateway`。
- **tools/list**：按公开名排序，第一个是 `issues.list`；alice 共 4 个工具（被截断）。每个工具保留了 `inputSchema`。
- **tools/call**：外层 id 3；文本 `notes.search completed` 来自 `notes` 后端（后端拼接 `f"{self.name}.{tool['name']} completed"`）；结果中的 serverInfo 是**网关**的——后端 `_meta` 已被剥离。
- **subscriptions/listen**：模拟的 SSE 响应，确认事件中 subscriptionId 是 4（打开流的请求 id），只确认了 `toolsListChanged`。
- **forwarded request ids: ['gw-1']**：讲义 "The demo prints the outer request id and fresh backend request id so the stateless hop is visible"——外层 id 3 对应后端 id `gw-1`，两跳 id 互不相同。
- **audit**：只有一条 `allow`；discover、list、listen 都不产生审计事件。

---

## 7. 动手改一改

1. **修复准入绕过**：实现测验 Q9 的 `_route`，让 `_visible_tools` 与 `tools/call` 共用；写测试"撤销准入后 list 与 call 都被拒绝"。
2. **讲义练习 3**：修改一个后端的 `inputSchema`（不改描述），证明 list 下架、call 得到 409；再把 pin 检查挪到限流之前，确认连续调用不再消耗配额。
3. **讲义练习 1**：在外层请求 `_meta` 中加入 trace context（如 W3C `traceparent`），转发时生成子 span，并在审计事件中记录外层 id、`gw-N`、后端路由、pin 摘要前 12 位、决策原因与耗时。
4. **限流键升级**：把桶的键改为 `(principal, issuer, resource, tool, cost_class)`，为写操作设置更小容量；另加一个"滥用桶"统计所有调用（含被拒绝的），写测试验证 bob 的无权探测会被限速。
5. **讲义练习 2**：加一个支持 Tasks 的后端：`tools/call` 返回 `resultType: "task"` 时，网关把 `taskId → (principal, backend)` 存入字典；实现 `tasks/get` 按 `Mcp-Name` 路由，并拒绝其他 principal 查询该任务。
6. **讲义练习 5**：写一个 `LegacyAdapter` 接口（`initialize`、会话 ID、GET 流都只存在于适配器内部），`Gateway` 在发现某后端只支持 `2025-11-25` 时通过适配器转发，且 `Gateway` 类本身不新增任何会话状态。

---

## 8. 常见坑

- **只在 `tools/list` 上做过滤**：列表隐藏 ≠ 授权；直接调用必须重新走全部检查（本节代码在准入上就犯了这个错）。
- **按发现顺序处理同名工具**：必须使用限定公开名并保留后端映射。
- **公开缓存因人而异的列表或 discovery**：会把一个用户能看到的工具泄露给另一个用户。
- **把注册表记录当安全审查**：`server.json` 只是发布元数据；准入证据要独立保存并在每次调用时作为策略输入。
- **转发时复制外层能力或外层 token**：网关是后端的客户端，只声明自己能中介的能力，使用为后端单独获取的凭证。
- **限流放在便宜的校验之前**：被下架或格式错误的调用白白消耗配额；同时要决定被拒调用是否计入滥用限额。
- **以会话 ID 或连接为键缓存允许决定或限流**：当前协议没有会话，且这类 ID 极易轮换。
- **为 `subscriptions/listen` 承诺重放**：没有 `Last-Event-ID` 重放，也没有自动重新订阅；断线后客户端重新订阅并刷新列表。
- **实现 `tasks/list`、`tasks/result`**：属于旧的实验模型。
- **notification 形式的 `tools/call` 照常执行**：后果性动作被执行却没有回执。
- **审计里写 bearer token 或授权码**：必须脱敏。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover tests -v`。

实际运行结果：**19 个测试全部通过**（`Ran 19 tests in 0.004s`，`OK`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_discover_advertises_current_protocol` | discover 200、版本、`resultType`、`cacheScope == "private"` |
| `test_tools_list_is_principal_filtered_and_sorted` | alice 列表已排序且含 `notes.create`；bob 不含；工具都是对象根 schema；`ttlMs > 0`；serverInfo 为网关 |
| `test_registry_server_json_requires_external_verified_admission` | 已验证时可准入；发布者改为 `unverified` 即拒绝；`server.json` 只有五个发布字段 |
| `test_registry_record_rejects_wrong_namespace_or_invalid_package` | 名字不在 `com.example/` 下、包缺字段都拒绝 |
| `test_allowed_call_is_forwarded_with_fresh_backend_id` | 外层 id 99 原样返回；后端收到 `gw-1`；`resultType` 为 complete |
| `test_denied_call_is_audited` | bob 调 `notes.create` → 403、`-32003`、审计 `deny` |
| `test_rate_limit_is_keyed_by_principal` | 把 alice 的桶清零 → 429，审计 principal 为 alice |
| `test_descriptor_change_is_blocked_at_list_and_call` | 改描述后 list 不含 `notes.search`，call 得 409 |
| `test_header_body_mismatch_is_rejected_before_route` | `Mcp-Name` 不一致 → 400、`-32020`，且没有任何转发 |
| `test_header_version_mismatch_precedes_support_check` | 只改 body 版本 → `-32020` |
| `test_unsupported_version_has_exact_error_data` | 头 body 一致的旧版本 → `-32022`，`data` 精确，id 42 |
| `test_unknown_method_is_json_rpc_404` | `widgets/list` → 404、`-32601`，id 43 |
| `test_task_methods_route_by_task_id_header_before_dispatch` | `tasks/get` 的 `Mcp-Name` 为 `task-7`，通过校验后因未实现得到 404 |
| `test_accepted_notification_returns_empty_202` | 无 id 的 `tools/list` → `(202, None)` |
| `test_modern_get_and_delete_return_405` | GET、DELETE → 405 |
| `test_subscriptions_listen_is_post_response_sse` | 200、`text/event-stream`、确认事件方法名、确认子集、subscriptionId 等于请求 id |
| `test_subscription_requires_sse_acceptance` | `Accept: application/json` → 406 |
| `test_subscription_acknowledges_only_supported_requested_types` | 同时请求 tools 与 resources 变化，只确认 tools |
| `test_legacy_headers_do_not_create_gateway_state` | 带 `Mcp-Session-Id`、`Last-Event-ID` 照常 200，网关无 `sessions` 属性 |

测试没有覆盖、但已在本讲解中实测的点：

- 撤销准入后 `tools/call` 仍被允许并转发；
- pin 不一致的调用消耗限流令牌；RBAC 拒绝不计入任何限额；
- `registry_record_is_admissible` 的 `namespace` 参数对发布者命名空间无效；
- 非对象 `arguments` 被原样转发；
- notification 形式的 `tools/call` 会被执行；
- 未知 bearer 时认证先于线协议校验（返回 401）。
