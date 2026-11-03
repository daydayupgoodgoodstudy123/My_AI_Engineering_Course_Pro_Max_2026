# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 08 节 构建 MCP 客户端：发现、路由与新旧协议兼容回退 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v`（均在 `code/` 下） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），无网络、无子进程——所有 server 都是进程内的可调用对象

---

## 1. 这份代码在考察什么

第 07 节写了 server，这一节站到另一边：一个 agent host 往往同时连多个 MCP server，它的客户端要做四件事——

1. **为每个请求盖章**：版本、capabilities、clientInfo 写进每个现代请求的 `params._meta`。
2. **判断对方是哪一代协议（era）**：先发 `server/discover`；成功或收到可识别的现代错误 → 现代；收到含糊信号 → 只有被运维显式 allowlist 的 peer 才能做**一次有时限的** `initialize` 探测，并且必须拿到结构完整的正面证据才认定为 legacy；否则 fail closed。
3. **合并工具目录**：多个 server 的工具排序后合并，同名时加前缀或拒绝，绝不静默覆盖。
4. **路由调用**：canonical 名 → 哪个 peer 的哪个 local 名 → 新 id → 按 era 构造请求 → 严格校验响应 id。

为了让这些判断"看得见"，代码不用真实的子进程或 HTTP，而是把 server 写成接收 `(message, timeout_ms)`、返回响应 dict 的可调用对象（`ModernFakeServer`、`LegacyFakeServer`），测试中还用各种小函数模拟超时、断开、空响应、畸形结果。

> 一句话：**客户端最难的不是发请求，而是在"对方是老 server"与"对方是出了错的新 server"之间不犯错——宁可失败，也不要在证据不足时降级**。同时要看到本节在碰撞拒绝、故障隔离、缓存与恢复上的简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 版本常量、`RECOGNIZED_MODERN_ERRORS` | 模块常量 | 现代 / legacy 版本号；`{-32020, -32021, -32022}` | 可识别的现代错误 |
| `Transport` | 类型别名 | `Callable[[dict, int \| None], dict \| None]` | 传输适配器接口 |
| `RpcFault` | 异常类 | fake server 内部的协议错误 | 协议错误 |
| `request_meta` / `modern_request` / `legacy_request` | 函数 | 构造两代请求（legacy 不带 `_meta`） | 每请求盖章 |
| `rpc_error` / `complete` | 函数 | fake server 用来构造响应 | 结果形状 |
| `decode_rpc_response` | 函数 | 严格校验响应信封：id 类型与值、result/error 二选一、错误码类型 | 响应关联 |
| `validate_modern_request` | 函数 | fake server 的请求校验 | 每请求校验 |
| `ModernFakeServer` | 可调用类 | 现代 server：discover / tools/list / tools/call | 测试替身 |
| `LegacyFakeServer` | 可调用类 | legacy server：不认识 discover，需要 initialize | 测试替身 |
| `Peer` | dataclass | 每个 server 的客户端簿记 | peer 而非会话 |
| `MergedTool` | 冻结 dataclass | canonical 名 → peer + local 名 | 合并后的命名空间 |
| `MultiServerClient` | 类 | 连接、era 协商、发现工具、合并、路由 | 客户端主体 |
| `tool` / `main` | 函数 | 构造工具描述符；演示三个 peer | 演示 |

数据流：`main` → `add_server`（notes、files 为现代，archive 为 legacy 且 `allow_legacy=True`）→ `connect_all`（每个 peer：discover →〔现代〕`_activate_modern` /〔含糊 + allowlist〕`_probe_legacy` → `initialize` → `notifications/initialized`）→ `discover_tools`（每个可用 peer 发 `tools/list`）→ `merge`（排序、处理碰撞）→ `call`（查注册表 → `_request` → 按 era 构造 → `decode_rpc_response`）。

---

## 3. 逐段精讲

### 3.1 两代请求的构造

```python
def request_meta(version, capabilities=None):
    return {
        VERSION_KEY: version,
        CAPABILITIES_KEY: CLIENT_CAPABILITIES.copy() if capabilities is None else capabilities,
        CLIENT_INFO_KEY: CLIENT_INFO.copy(),
    }


def modern_request(request_id, method, params, version, capabilities=None):
    body_params = dict(params or {})
    body_params["_meta"] = request_meta(version, capabilities)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body_params}


def legacy_request(request_id, method, params=None):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params or {})}
```

- 现代请求：每次调用都重新生成 `_meta`。讲义："Do not attach metadata once to a connection object and assume it reached the wire. Stamp and inspect the final serialized request."
- legacy 请求：**没有** `_meta`，版本和能力已经在 `initialize` 时按连接协商过——这是两代协议在线上最直观的区别。
- `CLIENT_CAPABILITIES = {"extensions": {}}`：客户端声明的能力，本节没有实际使用任何能力，只是演示"必须携带"。

### 3.2 `decode_rpc_response`：严格的响应关联

```python
def decode_rpc_response(response, expected_id):
    response_id = response.get("id")
    if (
        response.get("jsonrpc") != "2.0"
        or type(response_id) not in (int, str)
        or type(response_id) is not type(expected_id)
        or response_id != expected_id
    ):
        raise RuntimeError("invalid JSON-RPC response envelope")
    has_result = "result" in response
    has_error = "error" in response
    if has_result == has_error:
        raise RuntimeError("JSON-RPC response must contain exactly one of result or error")
    ...
    code = error.get("code")
    if not isinstance(code, int) or isinstance(code, bool) or not isinstance(error.get("message"), str):
        raise RuntimeError("JSON-RPC error requires an integer code and string message")
    return "error", error
```

- 返回 `("result", dict)` 或 `("error", dict)` 的二元组，调用方用元组解包 `kind, payload = ...`。
- **id 要类型和值都相等**：Python 中 `True == 1`、而 JSON 里 `true` 与 `1` 是不同类型；`type(a) is not type(b)` 把这种"看起来相等"的情况挡掉（测试 `test_discovery_rejects_a_boolean_response_id_for_an_integer_request`）。
- `has_result == has_error`：两个布尔值相等意味着"都有"或"都没有"，一个判断覆盖两种非法情况。
- 错误码检查 `isinstance(code, int) and not isinstance(code, bool)`：与第 07 节用 `type()` 的思路相同，排除布尔值。
- 这是客户端的"信任边界"：所有来自 server 的数据都先经过它。

### 3.3 两个 fake server

```python
class ModernFakeServer:
    def __init__(self, name, tools, capabilities=None, supported_versions=None):
        self.server_info = {"name": name, "version": "2.0.0"}
        self.tools = sorted(tools, key=lambda tool: tool["name"])
        ...
        self.received = []
        self.timeouts_ms = []

    def __call__(self, message, timeout_ms=None):
        self.received.append(message)
        self.timeouts_ms.append(timeout_ms)
        if "id" not in message:
            return None
        ...
```

- 实现了 `__call__`，所以**实例本身就是一个函数**，可以直接作为 `Transport` 传给 `add_server`。
- `received` 与 `timeouts_ms` 记录收到的每条消息和超时参数，测试据此断言"只发了 discover""从未发 initialize""超时预算是多少"。这是测试替身（test double）中的 **spy** 模式。
- `ModernFakeServer` 是第 07 节 server 的精简版：同样的 `validate_modern_request`（同样把版本检查放在 capabilities 检查之前）、`complete` 包装、未知工具返回 `isError`。

```python
class LegacyFakeServer:
    def __call__(self, message, timeout_ms=None):
        ...
        if method == "server/discover":
            return rpc_error(message.get("id"), -32601, "Method not found")
        if method == "initialize":
            self.initialized = True
            return {"jsonrpc": "2.0", "id": message["id"], "result": {
                "protocolVersion": LEGACY_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": "1.0.0"},
            }}
        if method == "notifications/initialized":
            return None
        if not self.initialized:
            return rpc_error(message.get("id"), -32002, "Server not initialized")
        ...
```

- 模拟老 server 的典型行为：不认识 `server/discover`（`-32601`），必须先 `initialize`，否则拒绝操作。
- `self.initialized` 是**连接级状态**——legacy 协议本来就有状态，这正是两代协议的根本差别。
- legacy 结果没有 `resultType`、`ttlMs`、`cacheScope`。

### 3.4 `Peer` 与 `MergedTool`：dataclass 的两种用法

```python
@dataclass
class Peer:
    name: str
    transport: Transport
    allow_legacy: bool = False
    era: str = "unknown"
    protocol_version: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    server_info: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    available: bool = False


@dataclass(frozen=True)
class MergedTool:
    canonical_name: str
    peer_name: str
    local_name: str
    description: str
```

- `Peer` 可变：连接过程中逐步填入 era、版本、能力、工具。`era` 初始为 `"unknown"`，只有两条成功路径会把它改成 `"modern"` 或 `"legacy"`。
- `field(default_factory=dict)`：dataclass 中可变默认值必须用工厂函数，每个实例得到独立的 dict / list（直接写 `= {}` 会报错）。
- `MergedTool` 冻结：注册表条目一旦生成就不应被修改。
- 讲义列出的 peer 字段还有"pending request ids""transport health"，本节代码没有实现（同步调用不需要待配对 id 表；健康状态只有 `available` 一个布尔值）。

### 3.5 `MultiServerClient` 的配置

```python
    def __init__(self, *, supported_modern=(PROTOCOL_VERSION,), supported_legacy=(LEGACY_VERSION,),
                 probe_version=None, discovery_timeout_ms=1_000, legacy_probe_timeout_ms=1_000):
        if not supported_modern or not supported_legacy:
            raise ValueError("at least one modern and legacy version must be configured")
        if discovery_timeout_ms <= 0 or legacy_probe_timeout_ms <= 0:
            raise ValueError("probe timeouts must be positive")
        ...
        self._next_request_id = 1

    def _new_id(self):
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id
```

- 构造函数全是**仅限关键字参数**（开头的 `*`），并在一开始做参数校验（fail fast）：超时必须为正，否则"有时限的探测"就失去意义。
- `_new_id` 是客户端级的单调计数器，所有 peer、所有请求（包括重试）都拿新 id——讲义多次强调"retry with a new request id"。
- `_mutual_version` 取双方都支持的版本中**最大**的一个：`sorted(common, reverse=True)[0]`。版本是 `YYYY-MM-DD` 格式，字符串字典序与日期顺序一致，所以可以直接比较。

### 3.6 `_connect_peer`：era 协商状态机

```python
    def _connect_peer(self, peer):
        if peer.available and peer.era in {"modern", "legacy"}:
            return                                        # era 缓存
        request_id = self._new_id()
        probe = modern_request(request_id, "server/discover", {}, self.probe_version, self.client_capabilities)
        try:
            response = self._send(peer, probe, self.discovery_timeout_ms)
        except (TimeoutError, ConnectionError) as exc:
            self._probe_legacy(peer, type(exc).__name__)  # 含糊：超时 / 断开
            return
        if response is None:
            self._probe_legacy(peer, "empty discovery response")   # 含糊：空响应
            return
        ...
        kind, payload = decode_rpc_response(response, request_id)
        if kind == "result":
            ...                                           # DiscoverResult → 现代
            self._activate_modern(peer, payload, selected)
            return
        code = payload["code"]
        if code in RECOGNIZED_MODERN_ERRORS:
            if code != -32022:
                raise RuntimeError(f"{peer.name}: correct modern request error {code} before retrying")
            ...                                           # -32022 → 换版本、新 id 重试 discover
            self._activate_modern(peer, retry_payload, selected)
            return
        self._probe_legacy(peer, f"unrecognized discovery error {code}")   # 含糊：未识别错误
```

把它画成决策表：

| discover 的结果 | 判断 | 后续 |
|----------------|------|------|
| 合法 DiscoverResult，且有共同版本 | 现代 | `_activate_modern` |
| 合法 DiscoverResult，但无共同版本 | 现代 | 抛错（不降级） |
| `-32022`，`data.supported` 中有共同版本 | 现代 | 新 id、新版本重试 discover |
| `-32022`，无共同版本 | 现代 | 抛错（不降级） |
| `-32020` / `-32021` | 现代 | 抛错："先修正请求再重试" |
| 其它错误码（如 `-32601`）、超时、断开、空响应 | 含糊 | `_probe_legacy`：未 allowlist 直接抛错 |
| 响应不是 dict、信封非法 | 非法 | 抛错 |

- 关键原则："Recognized modern errors remain modern even when the peer is on the legacy allowlist."——`-32020/-32021/-32022` 分支根本不看 `allow_legacy`。
- `_activate_modern` 还要求 `resultType == "complete"`，现代结果缺判别字段同样拒绝。
- ⚠️ `_activate_modern` 中 `result.get("_meta", {}).get(SERVER_INFO_KEY, {})` 假定 `_meta` 是 dict；若 server 返回 `"_meta": "x"` 会抛 `AttributeError`（不是 `RuntimeError`），capabilities 也没有校验类型。

### 3.7 `_probe_legacy`：allowlist + 正面证据

```python
    def _probe_legacy(self, peer, trigger):
        if not peer.allow_legacy:
            raise RuntimeError(f"{peer.name}: {trigger}; legacy compatibility is not allowlisted")
        request_id = self._new_id()
        initialize = legacy_request(request_id, "initialize", {
            "protocolVersion": self.supported_legacy[0],
            "capabilities": self.client_capabilities.copy(),
            "clientInfo": CLIENT_INFO.copy(),
        })
        try:
            response = self._send(peer, initialize, self.legacy_probe_timeout_ms)
        except (TimeoutError, ConnectionError) as exc:
            raise RuntimeError(f"{peer.name}: bounded legacy probe failed closed") from exc
        ...
        if version not in self.supported_legacy:
            raise RuntimeError(f"{peer.name}: unsupported legacy protocol revision")
        if not isinstance(capabilities, dict) or not valid_server_info:
            raise RuntimeError(f"{peer.name}: malformed legacy initialize result")
        peer.era = "legacy"
        ...
        peer.available = True
        self._send(peer, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
```

- 第一道闸：没有 allowlist 立刻失败，**连 initialize 都不发**。
- 只发**一次**，带 `legacy_probe_timeout_ms`；超时或断开 → fail closed。`raise ... from exc` 保留原始异常链，便于排查。
- 正面证据的 5 项检查与讲义逐条对应：`decode_rpc_response` 负责信封与 id、result/error 二选一；`kind != "result"` → 失败；版本必须在 legacy 集合；capabilities 必须是 dict；`serverInfo` 的 name/version 必须是非空字符串（`bool(server_info["name"])` 排除空串）。
- 只有全部通过才修改 `peer` 并发送 `notifications/initialized`。任何一步失败时 `peer.era` 仍是 `"unknown"`、`available` 仍是 `False`（测试 `test_allowlisted_malformed_legacy_response_fails_closed` 验证了这一点）——这就是"fail closed"。
- 讲义提醒："The code passes `legacy_probe_timeout_ms` to the transport adapter; a real stdio or HTTP adapter must enforce that deadline rather than merely record it." 本节 fake server 只是把它记进 `timeouts_ms`。

### 3.8 `_request` 与 `discover_tools`：按 era 发请求

```python
    def _request(self, peer, method, params):
        request_id = self._new_id()
        if peer.era == "modern":
            message = modern_request(request_id, method, params,
                                     peer.protocol_version or PROTOCOL_VERSION, self.client_capabilities)
        elif peer.era == "legacy":
            message = legacy_request(request_id, method, params)
        else:
            raise RuntimeError(f"{peer.name}: protocol era not selected")
        response = self._send(peer, message)
        ...
        result = dict(payload)
        if peer.era == "modern" and "resultType" not in result:
            raise RuntimeError(f"{peer.name}: modern result omitted resultType")
        if peer.era == "legacy":
            result.setdefault("resultType", "complete")
        return result
```

- 现代 peer 每次都重新盖章，legacy peer 用无 `_meta` 的旧形状——同一个客户端同时说两种"方言"。
- legacy 结果缺 `resultType` 时补成 `"complete"`：讲义 "Clients must treat a missing `resultType` from a legacy server as `"complete"`."；`dict(payload)` 先复制再 `setdefault`，不修改 server 返回的原对象。
- `discover_tools` 对每个 `available` 的 peer 发 `tools/list`，再在客户端**再排序一次**（讲义："The client should also sort before merging so local registry order does not depend on process startup timing."）。
- ⚠️ `_send(peer, message)` 没有传超时，普通请求无界等待。
- ⚠️ `TimeoutError` / `ConnectionError` 没有被捕获，直接冒泡给调用方，`peer.available` 也不会被置为 `False`（实测）。讲义描述的"传输恢复"（重连、重新 discover、重新 list、按安全策略用新 id 重试）没有实现。
- ⚠️ 只检查 `resultType` **存在**，不检查值。`input_required` 结果会被原样交还给调用方（实测），没有 MRTR 处理。
- ⚠️ 结果中的 `ttlMs` / `cacheScope` 被完全忽略，每次 `discover_tools` 都会重新拉取，也没有按授权上下文区分缓存（讲义练习 3）。

### 3.9 `merge`：确定性的命名空间合并

```python
    def merge(self, policy="prefix-on-collision"):
        if policy not in {"prefix-on-collision", "reject"}:
            raise ValueError("policy must be prefix-on-collision or reject")
        self.registry.clear()
        for peer_name in sorted(self.peers):
            peer = self.peers[peer_name]
            for tool in peer.tools:
                local_name = tool["name"]
                canonical_name = local_name
                if canonical_name in self.registry:
                    if policy == "reject":
                        continue
                    canonical_name = f"{peer.name}/{local_name}"
                    if canonical_name in self.registry:
                        raise ValueError(f"canonical collision: {canonical_name}")
                self.registry[canonical_name] = MergedTool(...)
        self.registry = dict(sorted(self.registry.items()))
```

- **确定性**来自两层排序：peer 按名字排序、每个 peer 的工具按名字排序；最后注册表按 canonical 名排序。无论 `add_server` 的顺序如何，结果都一样（测试 `test_merge_is_deterministic_and_prefixes_collisions` 故意先加 beta 再加 alpha）。
- **谁拿到无前缀名**：字母序最靠前的 peer。demo 中是 `archive`（legacy server），所以 `search` → `archive:search`。
- 前缀后仍碰撞（例如某个 server 的工具本身就叫 `notes/search`）→ `ValueError`。我们实测：一个名为 `evil` 的 peer 注册工具 `notes/search`，会让 notes 的 `search` 无法加前缀，整个 `merge` 抛出 `canonical collision: notes/search`——一个 server 可以借此让合并失败。
- ⚠️ **`reject` 策略实际上是静默丢弃**：`continue` 跳过重复工具，不报错、不记录。实测 alpha / beta 都有 `search` 时，`merge("reject")` 得到 `['read', 'search']`，beta 的 `search` 悄悄消失。讲义要求"surface a clear configuration error"，讲义练习 4 要求"make startup fail with both peer names in the error"。
- ⚠️ 先 `self.registry.clear()`，中途抛异常会留下合并了一半的注册表。
- `self.registry = dict(sorted(self.registry.items()))`：Python 3.7+ 的 dict 保持插入顺序，用排序后的键值对重建 dict 即得到有序注册表。

### 3.10 `call`：纯查表路由

```python
    def call(self, canonical_name, arguments):
        merged = self.registry.get(canonical_name)
        if merged is None:
            return {"resultType": "complete",
                    "content": [{"type": "text", "text": f"Unknown tool: {canonical_name}"}], "isError": True}
        peer = self.peers[merged.peer_name]
        if not peer.available:
            return {... f"Transport unavailable: {peer.name}" ..., "isError": True}
        return self._request(peer, "tools/call", {"name": merged.local_name, "arguments": arguments})
```

- 讲义："Routing is a pure lookup"。模型看到的是 canonical 名（如 `notes/search`），发给 server 的是 local 名（`search`）——server 永远不知道自己的工具在客户端被改了名。
- 未知工具和传输不可用由客户端本地生成 `isError` 结果，不发任何网络请求（讲义："Do not send a call when its owning transport is unavailable."）。

### 3.11 `connect_all` 与 `main`

```python
    def connect_all(self):
        for peer_name in sorted(self.peers):
            self._connect_peer(self.peers[peer_name])
```

- ⚠️ 任何一个 peer 抛出 `RuntimeError`，循环就中断，后面的 peer 都不会被连接。实测：名为 `aaa` 的坏 peer 会让正常的 `zzz` 也停留在 `('unknown', False)`。多 server host 应该隔离每个 peer 的失败（测验 Q10）。

`main` 构造了三个 peer：两个现代（notes、files），一个 legacy（archive，`allow_legacy=True`），走完连接 → 发现 → 合并 → 调用的全流程。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 传输抽象为可调用对象 | 协议判断与 I/O 解耦，测试可注入各种失败 | 真实适配器需实现超时、子进程管理、并发读取 |
| 先发 `server/discover` | 给 era 划清边界，避免 legacy server 对 `tools/list` 的含糊成功 | 多一个往返（可被 `ttlMs` 缓存摊薄） |
| 可识别现代错误永不降级 | 防止把出错的现代 server 当成老 server | 需要运维修正请求 / 版本配置 |
| legacy 需要 allowlist + 正面证据 | 防止任意 server 把自己降级到弱语义 | 新接入老 server 需要显式配置 |
| 严格的响应解码（id 类型 + 值） | 防止错配响应 | — |
| era 按 peer 缓存 | 不在每次调用前重新探测 | 传输重启时必须作废（本节未实现重启） |
| 字母序 peer 先到先得 | 确定、可复现 | 无前缀名的归属取决于配置名，可能被新 server 抢走 |
| `reject` 用 `continue` | 实现简单 | 与讲义不符：应报错并列出双方 peer |
| `connect_all` 不隔离失败 | 代码短 | 一个坏 server 拖垮全部；应逐个捕获并汇报 |
| 忽略 `ttlMs` / `cacheScope` | 聚焦 era 协商 | 每次都重新拉取；多授权上下文时需按上下文缓存 |
| 普通请求无超时、无恢复 | 演示同步流程 | 生产需超时、断线检测、重连与安全重试 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类型别名 | `Transport = Callable[[dict[str, Any], int \| None], dict[str, Any] \| None]` | 给复杂类型起名字，提高可读性 |
| `__call__` | `class ModernFakeServer: def __call__(self, message, timeout_ms=None)` | 让实例像函数一样被调用 |
| `@dataclass` + `field(default_factory=...)` | `capabilities: dict = field(default_factory=dict)` | 可变默认值必须用工厂函数，保证每个实例独立 |
| `@dataclass(frozen=True)` | `class MergedTool` | 不可变的记录 |
| `@staticmethod` | `def _send(peer, message, timeout_ms=None)` | 不需要 `self` 的方法 |
| 下划线前缀 | `_new_id`、`_probe_legacy`、`_next_request_id` | 约定为内部实现，不供外部调用 |
| 仅限关键字参数 | `def __init__(self, *, supported_modern=...)`、`add_server(..., *, allow_legacy=False)` | `*` 后的参数必须写名字，防止布尔参数传错位置 |
| 元组返回与解包 | `return "result", result`；`kind, payload = decode_rpc_response(...)` | 一次返回多个值 |
| `type(a) is not type(b)` | `decode_rpc_response` | 精确类型比较，区分 `True` 与 `1` |
| 布尔比较技巧 | `if has_result == has_error:` | 两者同真或同假都非法 |
| 异常链 | `raise RuntimeError(...) from exc` | 新异常的 `__cause__` 指向原异常，回溯时两者都显示 |
| 捕获多种异常 | `except (TimeoutError, ConnectionError) as exc` | `type(exc).__name__` 取异常类名字符串 |
| 集合字面量与成员判断 | `RECOGNIZED_MODERN_ERRORS = {-32020, -32021, -32022}`、`code in ...` | 集合的 `in` 是 O(1) |
| 推导式 + `sorted(reverse=True)` | `sorted(common, reverse=True)[0] if common else None` | 降序取最大；空列表时返回 `None` |
| `all(...)` | `all(isinstance(version, str) for version in advertised)` | 生成器表达式配合 `all` 做批量校验 |
| `dict.setdefault` | `result.setdefault("resultType", "complete")` | 键不存在时才设置 |
| `dict(sorted(d.items()))` | `self.registry = dict(sorted(self.registry.items()))` | 得到按键排序的新 dict |
| f-string 宽度 | `f"{peer_name:8s} era={peer.era:6s}"`、`f"{canonical_name:20s}"` | 左对齐、固定宽度，用于表格式输出 |
| 测试中的默认参数绑定 | `def unavailable(message, timeout_ms=None, *, sink=received, current_signal=signal)` | 在循环里定义闭包时，用默认参数"冻结"当前循环变量的值 |

---

## 6. 运行结果解读

`python3 main.py` 实际输出：

```text
MCP client peers
  archive  era=legacy version=2025-11-25
  files    era=modern version=2026-07-28
  notes    era=modern version=2026-07-28

Merged tools
  create               -> notes:create
  files/search         -> files:search
  notes/search         -> notes:search
  read                 -> files:read
  restore              -> archive:restore
  search               -> archive:search

Calls
  create               -> [notes] create ran
  read                 -> [files] read ran
  notes/search         -> [notes] search ran
  search               -> [archive/legacy] search ran
  restore              -> [archive/legacy] restore ran

No modern protocol sessions were created.
```

逐项解读：

- **Peers**：archive 对 discover 返回 `-32601`（含糊信号），因为它在 allowlist 上，客户端做了一次 initialize 探测，结果合格，被认定为 legacy `2025-11-25`；files、notes 的 discover 直接成功，选定 `2026-07-28`。
- **Merged tools**：三个 peer 都有 `search`。按字母序 archive 先处理，拿到无前缀的 `search`；files、notes 的变成 `files/search`、`notes/search`。`create`、`read`、`restore` 没有碰撞，保持原名。注册表按 canonical 名排序输出。
- **Calls**：
  - `create`、`read`、`notes/search` 路由到现代 peer，请求带完整 `_meta`，响应带 `resultType`；
  - `notes/search` 发给 notes 的是 local 名 `search`，server 回显 `[notes] search ran`；
  - `search`、`restore` 路由到 legacy peer，请求没有 `_meta`，响应没有 `resultType`，客户端内部补成 `complete`；
  - 回显中的 `[archive/legacy]` 说明走的是 legacy 分支。
- **最后一行**：客户端维护的只是 peer 簿记；对现代 peer 而言没有任何协议会话。注意 legacy peer 确实有连接级状态（`LegacyFakeServer.initialized`），这是旧协议的本性。

测试：`python3 -m unittest discover tests -v` 实测 **16 个测试全部通过**（`Ran 16 tests in 0.002s, OK`）。

此外我们实测了几条测试未覆盖的行为：`merge("reject")` 静默丢弃重复工具；一个坏 peer 让 `connect_all` 中断、后续 peer 未连接；`_request` 遇到 `ConnectionError` 直接冒泡且 `available` 仍为 `True`；`input_required` 结果被原样返回。

---

## 7. 动手改一改

1. **讲义练习 1、2**：写一个返回 `-32022`、`supported` 为空列表的 fake server，确认客户端失败且未发 `initialize`；再写一个 allowlisted 的 fake legacy server，让它在收到 `initialize` 时抛 `TimeoutError`，确认 peer 保持 `unknown` 且不可用（错误信息为 "bounded legacy probe failed closed"）。
2. **讲义练习 4**：把 `reject` 改成收集所有碰撞后抛出带双方 peer 名的错误，并保证失败时不留下半成品注册表（参考测验 Q9）。
3. **故障隔离**：让 `connect_all` 返回 `{peer: 错误信息}`，一个 peer 失败不影响其它 peer；打印一份启动报告（peer、era、版本、工具数、失败原因）。
4. **讲义练习 3**：实现按 `ttlMs` + `cacheScope` + 授权上下文的工具缓存（参考测验 Q12），让 `discover_tools` 先查缓存。
5. **传输恢复**：在 `_request` 中捕获 `TimeoutError` / `ConnectionError`，把 peer 标为不可用并重置 era；提供 `reconnect(peer_name, new_transport)`，重新 discover、list、merge；对只读工具自动用新 id 重试一次，对其它工具返回 `isError` 让上层决定。
6. **讲义练习 5（进阶）**：写一个有限的 `subscriptions/listen` 模拟器：先返回 `notifications/subscriptions/acknowledged`，再推送一条 `notifications/tools/list_changed`，然后模拟断流；客户端收到断流后用新 id 重新 listen 并重新拉取工具。

---

## 8. 常见坑

- **把任何 discover 失败都当成 legacy**：超时、断开、`-32601` 都只是含糊信号。
- **收到 `-32022` 后发 `initialize`**：对方已经证明自己是现代 server，这是降级。
- **用通配符开启 legacy 兼容**：allowlist 必须绑定到具体的 peer（固定命令 / 端点）。
- **只看 initialize 有没有返回 result**：版本、capabilities、serverInfo 都要校验，否则畸形响应也能让你进入 legacy。
- **用 `==` 比较响应 id**：`True == 1`，要连类型一起比。
- **重试时复用旧 id**：每次重试都要新 id。
- **在连接对象上存一次 `_meta`**：现代请求必须在每次序列化前重新盖章。
- **静默覆盖或静默丢弃同名工具**：模型选择的动作会落到意想不到的 server，或者某些工具"消失"却没人知道。
- **合并顺序依赖启动时序**：先排序再合并；也要意识到"字母序先到先得"本身是一种需要被审查的策略。
- **把 private 缓存跨授权上下文共享**。
- **在等待用户输入（elicitation）时阻塞读取循环**：其它在途请求的响应会堆积甚至超时。

---

## 9. 测试在验证什么

`tests/test_main.py` 使用 `unittest`，大量用小函数作为 transport 替身，并通过 `received` 列表断言"客户端到底发了什么"。在 `code/` 下运行 `python3 -m unittest discover tests -v`，实测 **16 个测试全部通过**。

| 测试 | 验证的性质 | 对应讲义 |
|------|-----------|---------|
| `test_modern_request_contains_current_metadata` | `modern_request` 的 `_meta` 含版本、capabilities、clientInfo | 每个请求盖章 |
| `test_modern_discovery_never_initializes` | 现代 server 只收到一条 `server/discover`，era 为 modern | discover 成功即现代 |
| `test_unsupported_version_retries_modern` | 客户端先用 `2027-01-01` 探测，收到 `-32022` 后用 `2026-07-28` 重试，且从未发 `initialize` | `-32022` 换版本重试 |
| `test_recognized_modern_errors_never_fall_back` | 用 `subTest` 覆盖 `-32020/-32021/-32022`（后者无共同版本），即使 `allow_legacy=True` 也只发了 discover 并抛错 | 可识别现代错误不降级 |
| `test_timeout_without_allowlist_fails_without_initialize` | 超时 + 无 allowlist → 抛 "not allowlisted"，未发 initialize | 超时是含糊信号 |
| `test_unrecognized_error_without_allowlist_fails_without_initialize` | `-32601` + 无 allowlist → 同上 | `-32601` 不是正面证据 |
| `test_empty_response_and_connection_close_do_not_prove_legacy` | 空响应、连接关闭两种信号 → 同上 | 含糊信号 fail closed |
| `test_allowlisted_legacy_with_valid_initialize_succeeds` | allowlisted legacy server：消息序列为 discover → initialize → initialized，超时预算为 `[1000, 275, None]` | 有时限的单次探测 + 正面证据 |
| `test_allowlisted_malformed_legacy_response_fails_closed` | initialize 结果缺 `serverInfo` → "malformed legacy initialize result"，peer 保持 unknown / 不可用，未发 initialized | 正面证据必须完整 |
| `test_allowlisted_unsupported_legacy_revision_fails_closed` | initialize 返回 `2024-11-05` → "unsupported legacy protocol revision"，未发 initialized | 只接受配置的 legacy 修订 |
| `test_selected_peer_era_is_cached_for_transport_lifetime` | 两次 `connect_all` 只发一次 discover | era 缓存 |
| `test_request_rejects_a_response_without_result_or_error` | 连接成功后替换 transport，返回既无 result 也无 error 的响应 → 抛错 | 严格的响应信封 |
| `test_discovery_rejects_a_boolean_response_id_for_an_integer_request` | 包装真实 fake server，把响应 id 改成 `True` → "invalid JSON-RPC response envelope" | id 类型 + 值匹配 |
| `test_merge_is_deterministic_and_prefixes_collisions` | 先加 beta 后加 alpha，注册表仍为 `["beta/search", "read", "search", "write"]`，`search` 属于 alpha | 确定性合并 + 前缀策略 |
| `test_modern_tool_call_repeats_metadata` | `tools/call` 请求同样带版本 `_meta`，结果为 complete | 每个请求盖章 |
| `test_legacy_result_is_normalized_internally` | legacy 的 `tools/call` 结果被补上 `resultType: "complete"` | legacy 结果规范化 |

测试中一个值得学习的技巧：在 `for` 循环里定义替身函数时，用**仅限关键字的默认参数**（`*, sink=received, error_code=code`）把当前循环变量的值固定下来，避免所有闭包都引用循环结束时的最后一个值（Python 闭包的"后期绑定"陷阱）。

没有覆盖、值得补充的测试：`merge("reject")` 应报错；一个坏 peer 不影响其它 peer；普通请求超时 / 断开后 peer 被标为不可用；`input_required` 的处理；`private` 缓存不跨授权上下文；`-32022` 重试仍返回错误时的行为。
