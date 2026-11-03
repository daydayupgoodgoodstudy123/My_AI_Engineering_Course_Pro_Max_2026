# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 31 节 MCP 一致性工程：版本管理、证据与运维 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（演示）；`python3 -m unittest discover -s tests -v`（测试） ｜ **依赖**：仅标准库（`base64`、`hashlib`、`hmac`、`json`、`dataclasses`、`typing`），无需网络

---

## 1. 这份代码在考察什么

这是一个**一致性（conformance）测试 harness + 发布门（release gate）**。它不连真实服务端，而是对"录下来的线路证据"（transcript）做判定，覆盖讲义的六个学习目标：

1. **规范 → transcript**：把协议规则写成 golden（应接受）与 negative（应拒绝）用例（`transcript_suite`、`run_transcript`）。
2. **版本时代分离**：现代 `2026-07-28` 与旧版 `2025-11-25` 走两条分支，严格/回退策略由 `select_era` 决定。
3. **未知字段 vs 未知 `resultType`**：`validate_result` 保留附加字段、拒绝未知判别符；`validate_method_result` 再校验方法级载荷。
4. **SDK 差分**：`compare_sdk_view` 对比原始结果和 SDK 归一化视图。
5. **代理证据**：`inspect_proxy` 对比 ingress / origin / egress 三个视图。
6. **发布门**：`ReleaseGate.evaluate` 把 transcript、SDK、代理、健康、经 HMAC 认证的回滚证据合在一起，给出 promote / rollback / hold，并对证据先脱敏再哈希（`redact`、`digest`）。

> 一句话：**测你发出的字节、每个中间层转发的字节、每个 SDK 暴露的语义，以及运维在压力下要用的证据；兼容是显式分支，回滚是有证据的发布动作。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MODERN_VERSION` / `LEGACY_VERSION` 等常量 | 常量 | 两个协议版本、三个 `_meta` 命名空间键、现代错误码集合、核心与扩展 `resultType`、脱敏黑名单 | 契约常量 |
| `canonical_json` / `digest` / `is_sha256_digest` | 函数 | 规范化 JSON 的 SHA-256；digest 格式校验 | 证据摘要 |
| `attach_rollback_attestation` / `rollback_evidence_ready` | 函数 | 给回滚证据加 HMAC-SHA-256 认证；严格校验字段、签名者与签名 | 回滚证据 |
| `canonical_field_name` / `redact` | 函数 | 键名 casefold + 去非字母数字；递归脱敏 | 证据脱敏 |
| `ProtocolViolation` | 异常类 | 带 JSON-RPC 错误码（默认 `-32600`） | 稳定错误码 |
| `routing_name` / `normalized_headers` | 函数 | 取 body 中的路由名；header 名小写化并拒绝冲突重复 | header 规则 |
| `encode_header_value` / `decode_header_value` | 函数 | `Mcp-Name` 的 `=?base64?...?=` 哨兵编解码 | 不安全值编码 |
| `validate_request` | 函数 | 按时代校验请求；现代分支校验元数据并比对 header | 请求一致性 |
| `allowed_result_types` / `validate_result` | 函数 | 按时代与能力校验 `resultType` | 判别符 |
| `validate_method_result` | 函数 | `tools/list`、`completion/complete`、`task` 的载荷校验 | 方法级校验 |
| `select_era` | 函数 | strict / fallback 时代选择 | 版本协商 |
| `notification_http_outcome` | 函数 | 通知应得到 `(202, None)` | 通知不变量 |
| `Transcript` / `CaseResult` | frozen dataclass | 一条用例 / 一条用例的结果 | transcript |
| `validate_response` / `validate_protocol_error_evidence` | 函数 | 响应信封、id、互斥、错误形状、HTTP 映射；header 不匹配时强制校验真实错误响应 | 响应一致性 |
| `run_transcript` | 函数 | 执行一条用例并给出 pass/fail 与脱敏证据摘要 | 用例执行 |
| `modern_request` / `transcript_suite` | 函数 | 构造现代请求；15 条用例 | 夹具 |
| `compare_sdk_view` | 函数 | SDK 差分 | SDK 差分 |
| `inspect_proxy` | 函数 | 三视图代理检查 | 代理证据 |
| `evaluate_health` | 函数 | 样本数、错误率、p95 | 健康窗口 |
| `ReleaseGate` | 类 | 汇总所有证据给出动作 | 发布门 |
| `healthy_window` / `demo` | 函数 | 演示数据与演示流程 | 演示 |

数据流：`demo()` → 15 条 `run_transcript` → `compare_sdk_view`（SDK 丢了 `futureHint`）→ `inspect_proxy`（origin 400 被折叠成 500）→ `attach_rollback_attestation`（1.0.0 回滚证据）→ `ReleaseGate.evaluate` → 打印摘要 JSON。

---

## 3. 逐段精讲

### 3.1 常量

```python
MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
MODERN_ERROR_CODES = {-32020, -32021, -32022}
CORE_RESULT_TYPES = {"complete", "input_required"}
EXTENSION_RESULT_TYPES = {"io.modelcontextprotocol/tasks": {"task"}}
```

- 三个现代错误码的含义（从代码用法得出）：`-32020` header 与 body 不匹配（以及 header 编码错误、冲突重复 header）；`-32021` 缺少 `clientCapabilities`；`-32022` 不支持的协议版本。
- `EXTENSION_RESULT_TYPES` 把"能力标识 → 该能力允许的额外 resultType"做成映射，便于扩展。
- `SECRET_KEYS` 里全是**规范化后的形式**（小写、无分隔符），如 `setcookie`、`xapikey`、`registrationaccesstoken`。讲义："Canonicalization and the denylist must use the same form."

### 3.2 摘要与回滚认证

```python
def attach_rollback_attestation(evidence, signer, signing_key):
    payload = dict(evidence)
    payload.pop("authenticator", None)
    signature = hmac.new(signing_key, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()
    return {**payload, "authenticator": {"algorithm": "hmac-sha256", "signer": signer, "signature": signature}}
```

- 签名覆盖的是**去掉 `authenticator` 之后的完整载荷**的规范化 JSON，任何字段（包括新增字段）变化都会让签名失效（实测加一个 `note` 字段后校验为 `False`）。
- `rollback_evidence_ready` 的检查是"精确类型"而非"真值"：
  - `version` 是非空字符串；
  - `healthy is True`（`"yes"` 不行）；`registryStatus == "active"`；
  - 三个 digest 都是 64 位十六进制；
  - `authenticator` 是 dict、算法是 `hmac-sha256`、`signer`/`signature` 是字符串、签名者在可信表中且密钥是 `bytes`；
  - 重新计算 HMAC，用 `hmac.compare_digest` 做常量时间比较（防计时攻击）。
- ⚠️ `hmac.compare_digest` 对含非 ASCII 字符的 `str` 会抛 `TypeError`（实测 `signature="é"` 时抛 "comparing strings with non-ASCII characters is not supported"），本应返回 `False`。可以先检查 `signature.isascii()` 或比较 `bytes`。
- ⚠️ 载荷里没有时间戳/有效期，也没有绑定到某个候选版本：一份旧的 "healthy: true" 证明可以被无限期重放。
- HMAC 是对称密钥：持有校验密钥的一方也能伪造签名。讲义明确说演示用的确定性密钥是非秘密夹具，生产应注入受保护密钥、KMS 校验结果或公钥签名校验器。

### 3.3 脱敏

```python
def canonical_field_name(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())

def redact(value):
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            normalized = canonical_field_name(key)
            output[key] = "[REDACTED]" if normalized in SECRET_KEYS else redact(item)
        return output
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
```

- `casefold()` 比 `lower()` 更彻底的大小写折叠；只保留字母数字，于是 `access-token`、`access_token`、`access.token`、`accessToken` 都变成 `accesstoken`。
- 递归处理 dict 和 list；**保留原键名**，只替换值，证据结构不变。
- 命中的键整个值被替换（即使值是嵌套对象）。
- ⚠️ 是**精确匹配**黑名单：实测 `X-Auth-Token`、`idToken`、`privateKey`、`sessionToken` 都不会被脱敏；如果 header 以 `[["Authorization", "Bearer z"]]` 这种"列表对"形式存储，也会漏过（键是列表元素而不是 dict 键）。讲义也提醒生产要加"方法级参数策略"，因为 `query` 这种无害键名也可能带个人数据。
- ⚠️ 键必须是字符串（`key.casefold()`）；JSON 解析出来的 dict 总满足这一点。

### 3.4 header 规则：路由名、规范化、Base64 哨兵

```python
def routing_name(body):
    params = body.get("params", {})
    if not isinstance(params, dict):
        return None
    for key in ("name", "taskId", "uri"):
        value = params.get(key)
        if isinstance(value, str):
            return value
    return None
```

- 依次尝试 `name`（tools/call、prompts/get）、`taskId`（任务方法）、`uri`（resources/read），第一个字符串即为路由名，对应 `Mcp-Name` header。

```python
def normalized_headers(headers):
    normalized = {}
    for name, value in headers.items():
        key = name.lower()
        if key in normalized and normalized[key] != value:
            raise ProtocolViolation(f"conflicting duplicate HTTP header: {name}", -32020)
        normalized[key] = value
    return normalized
```

- HTTP header **名**大小写不敏感 → 统一小写；**值**大小写敏感 → 原样比较。
- 同名（忽略大小写）但值不同 → `-32020`；同值重复则容忍。由于 Python dict 键唯一，"重复"只会以大小写变体的形式出现（测试中 `Mcp-Method` 与 `mcp-method` 同时存在）。

```python
def encode_header_value(value):
    safe = all(0x20 <= ord(character) <= 0x7E for character in value)
    sentinel = value.startswith("=?base64?") and value.endswith("?=")
    if safe and value == value.strip() and not sentinel:
        return value
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"=?base64?{encoded}?="
```

- 可打印 ASCII、无首尾空白、本身不像哨兵 → 原样发送；否则 UTF-8 → Base64 → 套上哨兵。例如 `"résumé_lookup"` → `"=?base64?csOpc3Vtw6lfbG9va3Vw?="`，`" inventory_get "` 也会被编码。
- `decode_header_value`：以 `=?base64?` 开头**或**以 `?=` 结尾就进入哨兵分支，两端必须都有；`b64decode(..., validate=True)` 拒绝非字母表字符；UTF-8 解码失败同样 `-32020`；非哨兵值若有首尾空白或非可打印 ASCII 则拒绝（"raw unsafe value"）。
- ⚠️ **编解码不对称**：编码器要求"两端都像哨兵"才编码，解码器"任一端像哨兵"就进入哨兵分支。实测 `"what?="`、`"=?base64?abc"` 被原样发送后在解码端报 "malformed Base64 MCP header sentinel"，这类合法名字永远无法通过。修复：编码器条件改为 `startswith(...) or endswith(...)`（见测验 Q10）。

### 3.5 `validate_request`：按时代校验请求

```python
    if body.get("jsonrpc") != "2.0" or not isinstance(body.get("method"), str):
        raise ProtocolViolation("invalid JSON-RPC request")
    params = body.get("params", {})
    if not isinstance(params, dict):
        raise ProtocolViolation("params must be an object", -32602)
    wire_headers = normalized_headers(headers)
    if era == "legacy":
        if body["method"] != "initialize" and wire_headers.get("mcp-protocol-version") == MODERN_VERSION:
            raise ProtocolViolation("modern metadata reached the legacy branch", -32020)
        return
```

- 先校验信封（`-32600`）和 params 类型（`-32602`），再规范化 header。
- **旧时代分支非常薄**：只拦截"非 initialize 请求却带着现代版本 header"——现代元数据误入旧分支。

现代分支的顺序（对应讲义 5 步）：

```python
    metadata = params.get("_meta")
    if not isinstance(metadata, dict):                       # 1. 元数据类型
        raise ProtocolViolation("modern request is missing params._meta", -32602)
    protocol_version = metadata.get(PROTOCOL_VERSION_KEY)
    capabilities = metadata.get(CLIENT_CAPABILITIES_KEY)
    if not isinstance(protocol_version, str):
        raise ProtocolViolation(..., -32602)
    if not isinstance(capabilities, dict):
        raise ProtocolViolation(..., -32021)

    mirrored = {"mcp-protocol-version": protocol_version, "mcp-method": body["method"]}
    name = routing_name(body)
    if name is not None:
        mirrored["mcp-name"] = name
    for header, body_value in mirrored.items():              # 2–4. 逐个比较
        header_value = wire_headers.get(header)
        if header == "mcp-name" and header_value is not None:
            header_value = decode_header_value(header_value)
        if header_value != body_value:
            raise ProtocolViolation(f"{header} does not match the JSON-RPC body", -32020)
    if protocol_version != MODERN_VERSION:                   # 5. 相等之后才判断支持
        raise ProtocolViolation(f"unsupported protocol version: {protocol_version}", -32022)
```

- 只认**精确的命名空间键**：`{"protocolVersion": ..., "clientCapabilities": ...}` 这种裸别名会因找不到 `PROTOCOL_VERSION_KEY` 而得到 `-32602`（测试 `test_bare_metadata_aliases_are_rejected`）。
- 缺 `clientCapabilities` 得到 `-32021`，而且它在 header 比较**之前**：实测"header 不匹配 + 缺能力"同时出现时报的是 `-32021`。
- 只有 `Mcp-Name` 会做哨兵解码；协议版本和方法名是普通 ASCII 值。
- **header 缺失也算不匹配**：`wire_headers.get(header)` 为 `None`，与 body 值不相等 → `-32020`（实测空 header 报 "mcp-protocol-version does not match"）。讲义说"When mirrored routing headers are present at the HTTP boundary"，代码则把这些 header 当作现代 HTTP 请求的必需项；如果要给 stdio 录 transcript，需要另一个不比较 header 的分支。
- 实测：body 写 2027、header 写 2026 → `-32020`；两者都写 2027 → `-32022`。这就是"先比较、后判断支持"带来的可区分性。

### 3.6 `validate_result` 与 `validate_method_result`

```python
def validate_result(result, era, capabilities=None):
    if not isinstance(result, dict):
        raise ProtocolViolation("result must be an object")
    preserved = dict(result)
    result_type = result.get("resultType")
    if era == "legacy":
        if result_type is None:
            return {"semanticType": "complete", "wire": preserved, "inferred": True}
    elif era == "modern":
        if result_type is None:
            raise ProtocolViolation("modern result is missing resultType")
    else:
        raise ValueError(f"unknown era: {era}")
    allowed = allowed_result_types(capabilities or set())
    if result_type not in allowed:
        raise ProtocolViolation(f"unknown or unadvertised resultType: {result_type}")
    return {"semanticType": result_type, "wire": preserved, "inferred": False}
```

- 返回值同时带"语义类型"和"原始 wire 副本"：附加字段（`futureHint`）完整保留在 `wire` 中。
- `inferred=True` 明确标记"这是推断出来的 complete"，供后续证据使用。
- 旧时代**如果带了** `resultType`，同样要在允许集合里。
- 未知 era 抛普通 `ValueError`（这是调用方编程错误，不是协议违规）。
- ⚠️ 若 `resultType` 是不可哈希的值（如列表 `["complete"]`），`result_type not in allowed` 会抛 `TypeError` 而不是 `ProtocolViolation`（实测），会让 `run_transcript` 直接崩溃。应先检查 `isinstance(result_type, str)`。

`validate_method_result` 对三类载荷做细校验：

| 方法 / 类型 | 检查 |
|------------|------|
| `tools/list` | `resultType` 必须是 `complete`；`tools` 是列表；每项是 dict、`name` 非空且**唯一**、`description` 非空、`inputSchema` 是 dict 且 `type == "object"` |
| `completion/complete` | `resultType` 必须是 `complete`；`completion` 是 dict；`values` 是字符串列表且 ≤ 100；`total`（可选）是非 bool 的 int 且 ≥ 值个数；`hasMore`（可选）是 bool |
| `task`（任何方法） | 方法必须是 `tools/call`；`taskId`、`status`、`createdAt`、`lastUpdatedAt` 是非空字符串；`status` ∈ {working, input_required, completed, cancelled, failed}；`ttlMs` 必须**存在**，值为 `null` 或非负 int；`pollIntervalMs`（可选）非负 int |

- `isinstance(total, bool)` 先排除：Python 中 `True` 是 `int` 的子类，不排除的话 `total=True` 会被当成 1。
- `ttlMs` 的"存在但为 null"与"不存在"被区别对待：`"ttlMs" not in result` 报缺失；`"ttlMs": "missing"` 这种字符串报类型错误（测试 `test_task_ttl_literal_missing_is_an_invalid_value_not_an_absent_field`）。
- ⚠️ 它读取的是传入结果里的 `resultType`。见 3.9：`validate_response` 传的是原始结果，旧时代被推断为 complete 的结果在这里会被判为"不是 complete"。

### 3.7 `select_era`：strict 与 fallback

```python
    kind = observation.get("kind")
    if kind == "discover_success":
        return "modern"
    if kind == "jsonrpc_error" and observation.get("code") in MODERN_ERROR_CODES:
        return "modern"
    if policy == "strict":
        raise ProtocolViolation("modern support was not proven; strict policy forbids fallback")
    if kind not in {"empty", "timeout", "connection_closed", "unrecognized"}:
        raise ProtocolViolation("probe outcome is not safe evidence for fallback")
    if not legacy_allowed:
        raise ProtocolViolation("legacy fallback is not allowlisted for this endpoint")
    if not isinstance(legacy_evidence, dict):
        raise ProtocolViolation("inconclusive modern probe is not positive legacy evidence")
    if legacy_evidence.get("kind") != "initialize_success" or legacy_evidence.get("protocolVersion") != LEGACY_VERSION:
        raise ProtocolViolation("legacy probe did not prove the configured legacy era")
    return "legacy"
```

一条"层层设卡"的决策链：

| 条件 | 结果 |
|------|------|
| `discover_success` | modern |
| 现代错误码 `-32020/-32021/-32022` | modern（**绝不降级**） |
| strict 且未证明现代 | 失败关闭 |
| 探测结果不是"无结论"四类之一（例如其他 JSON-RPC 错误） | 失败关闭 |
| 端点不在允许名单 | 失败关闭 |
| 没有旧版正面证据 | 失败关闭 |
| 旧版证据不是 `initialize_success` 或版本不是精确的 `2025-11-25` | 失败关闭 |
| 以上都通过 | legacy |

- 讲义 Lab A：`select_era({"kind": "timeout"}, "fallback")` 实测抛 "legacy fallback is not allowlisted for this endpoint"——沉默不是旧版证据。
- 旧版本只接受**精确的** `2025-11-25`（实测 `2025-06-18` 被拒），对应"pinned legacy revision"。
- ⚠️ 设计取舍：`-32601`（Method not found）这类非现代 JSON-RPC 错误被当作"不安全的回退证据"直接拒绝（实测）。而旧版服务端对 `server/discover` 最可能回的就是 `-32601`；要让这类端点走回退，调用方必须把它归类为 `unrecognized`，这个分类应写进端点策略。
- ⚠️ `observation.get("code")` 是列表时 `in MODERN_ERROR_CODES` 会抛 `TypeError`。

### 3.8 通知与数据类

```python
def notification_http_outcome(request):
    if "id" in request:
        raise ValueError("request has an id and is not a notification")
    return 202, None
```

- 用 `"id" in request` 判断（而不是 `request.get("id") is None`）：`{"id": null}` 仍是请求而不是通知。
- `Transcript` 与 `CaseResult` 都是 `frozen=True` 的 dataclass；`capabilities` 用 `frozenset`，与"冻结"语义一致（但 `headers`、`request` 是普通 dict，依然可变——冻结只阻止重新赋值字段）。

### 3.9 `validate_response` 与 header 不匹配的强制证据

```python
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
        raise ProtocolViolation("invalid JSON-RPC response envelope")
    request_id = request.get("id")
    response_id = response.get("id")
    if type(response_id) is not type(request_id) or response_id != request_id:
        raise ProtocolViolation("response id does not exactly match request id")
    has_result = "result" in response
    has_error = "error" in response
    if has_result == has_error:
        raise ProtocolViolation("response must contain exactly one of result or error")
```

- id 要求**值和 JSON 类型都相同**：请求 id `6`、响应 id `"6"` 被拒；`True` 与 `1` 也会被拒（Python 中 `True == 1`，所以必须再比类型）。
- `has_result == has_error` 一行同时覆盖"两者都有"和"两者都没有"。
- 成功结果要求 HTTP 200，然后 `validate_result` + `validate_method_result`。
- 错误要求 `code` 是非 bool 的 int、`message` 是字符串；并按映射表检查 HTTP 状态：`-32020/-32021/-32022 → 400`，`-32601 → 404`；其他码不约束状态。
- ⚠️ **旧时代 bug**：成功分支里 `validate_result(...)` 的返回值被丢弃，`validate_method_result` 收到原始结果（无 `resultType`），于是旧时代的 `tools/list` 与 `completion/complete` 结果全都会被判为 "must return a complete result"。实测讲义要求的 "legacy result without `resultType`" golden 用例无法通过（`compare_sdk_view` 的写法是正确的）。修复见测验 Q9。

```python
def validate_protocol_error_evidence(case, expected_code):
    if case.response_body is None:
        raise ProtocolViolation("expected JSON-RPC error response is missing")
    validate_response(case.request, case.response_status, case.response_body, case.era, set(case.capabilities))
    error = case.response_body.get("error")
    if not isinstance(error, dict) or error.get("code") != expected_code:
        raise ProtocolViolation(f"server did not return JSON-RPC error {expected_code}")
```

- 这是讲义强调的："A harness that stops after its own request validator throws has tested only itself, not the server's wire behavior." 本地校验器发现 header 不匹配后，还必须证明服务端**真的**回了结构正确的 HTTP 400 + `-32020`。

### 3.10 `run_transcript`：一条用例的判定

```python
    evidence = redact({...headers, request, responseStatus, responseBody...})
    try:
        validate_request(case.headers, case.request, case.era)
        if "id" not in case.request:
            expected_status, expected_body = notification_http_outcome(case.request)
            if (case.response_status, case.response_body) != (expected_status, expected_body):
                raise ProtocolViolation("notification received a response body")
        elif case.response_body is None:
            raise ProtocolViolation("JSON-RPC request has no response body")
        else:
            validate_response(...)
        if case.expected_error_code is not None:
            return CaseResult(case.name, False, "negative case was accepted", digest(evidence))
        return CaseResult(case.name, True, "accepted as expected", digest(evidence))
    except ProtocolViolation as error:
        passed = case.expected_error_code == error.code
        detail = f"rejected with {error.code}: {error}"
        if error.code == -32020:
            try:
                validate_protocol_error_evidence(case, -32020)
            except ProtocolViolation as response_error:
                passed = False
                detail = f"request rejection was correct, but response was invalid: {response_error}"
        return CaseResult(case.name, passed, detail, digest(evidence))
```

判定矩阵：

| 情况 | golden（无期望码） | negative（有期望码） |
|------|-------------------|---------------------|
| 全部校验通过 | 通过 | **失败**："negative case was accepted" |
| 抛出 ProtocolViolation | 失败（`None != code`） | 码相同则通过 |
| 抛出 `-32020` | 失败 | 还要额外验证服务端错误响应，不合格则失败 |

- 证据**先脱敏再哈希**：`evidence_digest` 不会因为 token 不同而泄露信息。
- 只有 `-32020` 有"强制响应证据"；`-32021`/`-32022` 在本地被拒后不检查服务端响应（讲义只对 HeaderMismatch 作此要求）。
- ⚠️ 负例只比较错误**码**：11 条负例中有 10 条期望 `-32600`，而 `validate_response` 的大多数失败都用默认码 `-32600`。实测把 `negative-malformed-tools-list` 的缺陷换成"缺 resultType"后它依然通过——用例名和实际触发的规则可以不一致。改进是给违规加稳定的规则标识（见测验 Q12）。
- ⚠️ 只捕获 `ProtocolViolation`；`validate_result` 中可能出现的 `TypeError`（见 3.6）会直接冒泡。

### 3.11 `modern_request` 与 `transcript_suite`

- `modern_request(method, request_id, name)` 生成一对 `(headers, body)`：`_meta` 含三个命名空间键；有 `name` 时放进 `params.name` 并生成编码后的 `Mcp-Name`；`request_id=None` 时生成通知（没有 `id` 键）。
- 15 条用例：

| # | 名称 | 类型 | 要点 |
|---|------|------|------|
| 1 | golden-modern-list | golden | 含附加字段 `futureHint`，仍应接受 |
| 2 | golden-notification-no-response | golden | 课程扩展通知 `notifications/course/progress`，期望 202 + 空 |
| 3 | negative-header-body-mismatch | negative `-32020` | `Mcp-Name: inventory_delete` vs body `inventory_get`；带真实 400 + `-32020` 响应 |
| 4 | negative-missing-result-type | negative | 现代结果缺 `resultType` |
| 5 | negative-unknown-result-type | negative | `resultType: "surprise"` |
| 6 | negative-response-jsonrpc-version | negative | 响应 `jsonrpc: "1.0"` |
| 7 | negative-response-id-mismatch | negative | 请求 id 6、响应 id `"6"` |
| 8 | negative-result-error-exclusivity | negative | 同时有 result 与 error |
| 9 | negative-malformed-error | negative | `code` 是字符串、缺 `message` |
| 10 | negative-error-http-mapping | negative | `-32020` 却用 HTTP 500 |
| 11 | negative-malformed-tools-list | negative | 工具缺 `inputSchema` |
| 12 | negative-task-required-fields | negative | task 结果缺 status 等 |
| 13 | golden-task-result | golden | 声明 Tasks 能力的完整 task 结果 |
| 14 | golden-completion-result | golden | 2 个值、`total=3`、`hasMore=true` |
| 15 | negative-malformed-completion-result | negative | values 里有整数 7 |

- 讲义列出但套件**没有**的用例：golden 的 `input_required` 结果、旧时代无 `resultType` 结果；negative 的缺能力（`-32021`）、不支持版本（`-32022`）、给通知发了响应、畸形请求信封、代理折叠（后者由 `inspect_proxy` 单独覆盖）。其中旧时代 golden 一旦补上就会暴露 3.9 的 bug。
- 讲义注明：课程扩展通知只用于测试"单向序列化"不变量，不是新的核心方法（2026-07-28 在 Streamable HTTP 上没有核心的客户端→服务端通知）。

### 3.12 `compare_sdk_view`：SDK 差分

```python
    validated = validate_result(raw_result, era, capabilities)
    method_result = dict(validated["wire"])
    method_result["resultType"] = validated["semanticType"]
    validate_method_result(method, method_result)
    bookkeeping = {"resultType", "_meta", "ttlMs", "cacheScope"}
    semantic_wire = {k: v for k, v in validated["wire"].items() if k not in bookkeeping}
    dropped = sorted(k for k in semantic_wire if k not in sdk_result)
    changed = sorted(k for k in semantic_wire if k in sdk_result and semantic_wire[k] != sdk_result[k])
```

- 先保证原始结果本身合法（含方法级校验），再做对比——畸形原始结果直接抛错（测试 `test_sdk_differential_rejects_malformed_advertised_task_result`）。
- 把推断出的 `semanticType` 写回再做方法级校验，所以旧时代结果在这里能通过（与 3.9 的 bug 形成对照）。
- 簿记字段允许被 SDK 去掉；其余字段若缺失记为 dropped、值不同记为 changed（如 SDK 把工具列表弄丢了一项，实测报 `changedFields: ["tools"]`）。
- 返回原始与 SDK 两个 digest，供发布门检查格式。
- ⚠️ 只看"原始有、SDK 没有/不同"，不看"SDK 多出来的"：实测 SDK 视图多了 `nextCursor: None` 和合成的 `resultType` 仍是 `semanticMatch=True`。讲义要求记录 "fields lifted, synthesized, stripped, or changed"，合成字段这一类没有覆盖。
- ⚠️ 只比较结果对象，没有采集原始状态码和 header（讲义第 1 条要求）。

### 3.13 `inspect_proxy`：三视图

```python
    try:
        validate_request(ingress.get("headers", {}), ingress.get("body", {}), "modern")
    except ProtocolViolation as error:
        issues.append(f"ingress:{error.code}")
    if (origin.get("status") in {400, 404} and isinstance(origin_body, dict)
            and "error" in origin_body and egress.get("status") == 500):
        issues.append("proxy collapsed a protocol error into HTTP 500")
    if origin.get("body") != egress.get("body"):
        issues.append("proxy changed the origin JSON-RPC body")
    redacted_exchange = redact(exchange)
```

- ingress 请求先按现代规则校验，违规记为 `ingress:<code>`。
- 两条检测：协议错误被折叠成 500；body 被改写。
- 证据整体脱敏后分别对三个视图求 digest，并把脱敏后的证据原样返回（演示中 `Authorization: Bearer do-not-store` 变成 `[REDACTED]`）。
- ⚠️ 折叠检测只认 500：实测 origin 400 → egress 502 或 200（body 不变）都 `passed=True`。更稳妥的是"egress 状态必须等于 origin 状态"。
- ⚠️ 不检查 header（content type、缓存头、trace 关联）、SSE、压缩；讲义说这些需要按部署补充。

### 3.14 `evaluate_health` 与 `ReleaseGate`

```python
def evaluate_health(health):
    reasons = []
    if health.get("sampleCount", 0) <= 0:
        reasons.append("health window has no samples")
    if health.get("errorRate", 1.0) > health.get("maxErrorRate", 0.01):
        reasons.append("error rate exceeds the release threshold")
    if health.get("p95Ms", float("inf")) > health.get("maxP95Ms", 500):
        reasons.append("p95 latency exceeds the release threshold")
    return not reasons, reasons
```

- 缺失时默认"最坏值"（错误率 1.0、p95 无穷大、样本 0），空 dict 会得到三条失败原因——这是"缺证据即失败"的好习惯。
- ⚠️ 阈值从**被评估的数据**里读取，证据提供方可以放宽阈值（实测 `errorRate=0.9, maxErrorRate=1.0` 通过）。
- ⚠️ 样本数只要求 > 0（实测 1 个样本通过），没有讲义说的"最小样本数"、观测时长、饱和度、基线对比。
- ⚠️ `float("nan") > 0.01` 为 `False`，NaN 错误率会通过（实测）；字符串数值会抛 `TypeError`。

`ReleaseGate.evaluate` 的原因收集：

1. transcript 为空 / digest 非法 / 有失败用例；
2. SDK 报告为空 / digest 非法 / `semanticMatch is not True`；
3. 代理报告为空 / 三个 digest 任一非法 / 每个 issue / `passed` 不为 True 却没有 issue；
4. 健康窗口原因；
5. 回滚证据未就绪。

```python
        if not reasons:      action = "promote"
        elif rollback_ready: action = "rollback"
        else:                action = "hold"
```

- 所有"是否通过"都用 `is not True` / `is True` 的精确判断，防止 `"yes"` 之类的真值混进来。
- 最终证据包（transcript 结果、SDK、代理、健康、回滚）再次脱敏后求 `evidenceDigest`：它证明"是哪一份脱敏证据驱动了这次决策"。
- ⚠️ 只要求"非空"，不要求覆盖**哪些**用例：实测只交 1 条通过的 golden 用例也会 promote。见测验 Q11 的加固实现。
- 注意语义：当候选失败而回滚就绪时，动作是 `rollback`——即便候选尚未上线，它也意味着"保持/恢复到已验证的前一版本"。

### 3.15 `demo()`

1. 跑 15 条 transcript；
2. SDK 差分：原始结果含 `futureHint` 与 `_meta`，SDK 视图只有 `tools`；
3. 代理：ingress 是合法的 `tools/call`（带 `Authorization`），origin 400 + `-32020`，egress 500 + `{"message": "upstream failed"}`；
4. 用固定的非秘密夹具密钥给 1.0.0 生成回滚证明；
5. 用同一密钥构造的发布门评估，打印摘要。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 对录制的 transcript 做判定 | 确定、可重复，能在单元测试层跑 | 需要在真实传输、网关、canary 层用同名用例再跑一遍 |
| 两条时代分支 | 不让畸形现代对端享受旧版宽松规则 | 旧版分支校验很薄，需要单独的旧版适配器 |
| 先比 header、后判支持 | 区分 `-32020` 与 `-32022`，防止"按 header 授权、按 body 执行" | header 缺失也被当作不匹配，stdio 需要另一分支 |
| Base64 哨兵 | 让任意 UTF-8 工具名能放进 header | 编解码判定必须对称（本代码不对称） |
| 现代错误绝不降级 | 防降级攻击、保留纠错信息 | `-32601` 等需要策略明确归类 |
| 负例比对错误码 | 比"失败了"更强 | 大量共用 `-32600`，需要规则级标识 |
| header 不匹配强制验证真实响应 | 测服务端而不是测自己 | 只覆盖 `-32020` |
| SDK 差分只报丢弃/改变 | 实现简单 | 漏掉合成/新增字段 |
| 代理只查 500 折叠和 body 改写 | 覆盖最常见问题 | 其他状态改写、header、SSE 需补充 |
| 键名规范化 + 精确黑名单 | 一次覆盖 camelCase / 分隔符变体 | 黑名单之外的敏感键与值内嵌密钥会漏 |
| HMAC 认证回滚证据 | 标准库即可演示"认证 + 精确字段" | 对称密钥、无有效期；生产用 KMS / 公钥签名 + 时间戳 |
| 健康阈值随数据传入 | 演示方便 | 阈值应属于策略；需最小样本、有限数校验 |
| promote / rollback / hold 三态 | 没有证据的回滚目标时宁可 hold | 需要人介入处理 hold |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 集合字面量与 `frozenset` | `MODERN_ERROR_CODES = {...}`、`capabilities: frozenset[str] = frozenset()` | 可变集合 / 不可变集合；frozen dataclass 的默认值必须不可变 |
| dict 嵌套常量 | `EXTENSION_RESULT_TYPES = {"io.modelcontextprotocol/tasks": {"task"}}` | 能力 → 允许类型的映射 |
| `hmac.new(key, msg, hashlib.sha256).hexdigest()` | `attach_rollback_attestation` | 计算 HMAC-SHA-256 |
| `hmac.compare_digest` | `rollback_evidence_ready` | 常量时间比较，防计时攻击；str 只支持 ASCII |
| `base64.b64encode` / `b64decode(validate=True)` | header 编解码 | `validate=True` 拒绝非 Base64 字符 |
| `str.casefold()` / `isalnum()` | `canonical_field_name` | 彻底的大小写折叠；只保留字母数字 |
| 字符串切片 | `value[len("=?base64?") : -2]` | 去掉前缀和末尾两个字符 |
| 递归函数 | `redact` | 遍历任意嵌套的 dict / list |
| 自定义异常带属性 | `class ProtocolViolation(ValueError)`，`self.code = code` | 异常携带错误码；`super().__init__(message)` 设置消息 |
| `raise ... from error` | `decode_header_value` | 保留原始异常链，便于调试 |
| 捕获多个异常 | `except (ValueError, UnicodeDecodeError)` | 元组形式 |
| 嵌套 try | `run_transcript` 中再 `try: validate_protocol_error_evidence` | 外层失败后做额外验证 |
| `type(a) is not type(b)` | id 比较 | 精确类型比较，区分 `1`/`True`/`"1"` |
| 布尔相等技巧 | `if has_result == has_error:` | 同时覆盖"都有"与"都没有" |
| `isinstance(x, bool)` 先判断 | `isinstance(total, bool) or not isinstance(total, int)` | `bool` 是 `int` 子类，需单独排除 |
| `dict.get(key, default)` | `health.get("errorRate", 1.0)` | 缺失时给出保守默认值 |
| `float("inf")` / NaN | `health.get("p95Ms", float("inf"))` | 无穷大；注意 NaN 与任何数比较都为 False |
| 元组比较 | `(case.response_status, case.response_body) != (expected_status, expected_body)` | 一次比较多个值 |
| 返回元组 + 解包 | `health_passed, health_reasons = evaluate_health(health)` | 多返回值 |
| 类型注解 `tuple[int, None]` | `notification_http_outcome` | 精确描述返回形状 |
| `@dataclass(frozen=True)` | `Transcript`、`CaseResult` | 不可变记录；`case.__dict__` 取字段字典 |
| 关键字参数调用 dataclass | `Transcript(..., expected_error_code=-32020)` | 跳过中间有默认值的字段 |
| 生成器表达式 + `any` / `all` / `sum` | `any(not is_sha256_digest(...) for ...)`、`sum(case.passed for case in cases)` | `True` 计为 1，`sum` 可数通过数 |
| 双重 for 的生成器 | `for report in proxy_reports for field in (...)` | 扁平化两层循环 |
| `list.extend(生成器)` | `reasons.extend(f"transcript failed: {case.name}" for case in transcripts if not case.passed)` | 批量追加 |
| 字典推导式 | `{key: value for key, value in validated["wire"].items() if key not in bookkeeping}` | 过滤字典 |
| `sorted(生成器)` | `sorted(key for key in semantic_wire if key not in sdk_result)` | 输出确定顺序 |
| `next(生成器)` | 测试里 `next(item for item in suite if item.name == ...)` | 取第一个匹配项 |
| 字典解包 | `{**payload, "authenticator": {...}}`、`{**headers, "Authorization": ...}` | 合并 / 覆盖键 |
| f-string | `f"=?base64?{encoded}?="`、`f"ingress:{error.code}"` | 字符串插值 |
| `json.dumps(indent=2)` | `demo()` | 美化输出 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `demo()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`python3 main.py`）：

```json
{
  "transcriptsPassed": 15,
  "transcriptsTotal": 15,
  "sdkDroppedFields": [
    "futureHint"
  ],
  "proxyIssues": [
    "proxy collapsed a protocol error into HTTP 500",
    "proxy changed the origin JSON-RPC body"
  ],
  "releaseAction": "rollback",
  "evidenceDigest": "ff1d4fe953070a57bf939636110d43caf441d1fa6fca8ff5df32d5c84a256897"
}
```

与讲义的 "Expected shape" 完全一致。逐项解读：

- **`transcriptsPassed: 15/15`**：我们逐条打印了 detail——4 条 golden 为 "accepted as expected"；header 不匹配为 "rejected with -32020: mcp-name does not match the JSON-RPC body"（服务端 400 + `-32020` 响应通过了强制验证）；其余 10 条负例都以 `-32600` 被拒，且各自命中了 3.11 表中描述的那条规则（例如 "JSON-RPC error -32020 requires HTTP 400"、"task result requires non-empty status"）。
- **`sdkDroppedFields: ["futureHint"]`**：`_meta` 和 `resultType` 是簿记字段，允许去掉；`futureHint` 是语义字段，被 SDK 丢了。
- **`proxyIssues`**：origin 400 → egress 500 触发折叠检测；egress body `{"message": "upstream failed"}` 与 origin 的 JSON-RPC 错误不同，触发改写检测。ingress 合法，没有 `ingress:` 前缀的问题；证据中 `Authorization` 已被替换为 `[REDACTED]`。
- **`releaseAction: "rollback"`**：我们打印了发布门的 reasons：`["SDK view lost or changed wire semantics", "proxy collapsed a protocol error into HTTP 500", "proxy changed the origin JSON-RPC body"]`；健康窗口通过；回滚证据经 HMAC 验证就绪，所以动作是 rollback 而不是 hold。
- **`evidenceDigest`**：脱敏证据包的 SHA-256，由于输入全部确定，每次运行都相同。

我们还按讲义 Lab D 实际验证：把 egress 改成与 origin 相同的 400 + 错误 body 后，代理问题消失，但动作仍是 `rollback`（原因只剩 "SDK view lost or changed wire semantics"）；再让 SDK 视图包含 `futureHint`，动作变为 `promote`，与讲义描述一致。

测试运行：**35 个测试全部通过，耗时约 0.006 秒**（见第 9 节）。

---

## 7. 动手改一改

1. **（入门）Lab A/B/C**：在 Python shell 里按讲义执行 `validate_result`、`select_era`、`compare_sdk_view` 的例子，并把 `-32601` 作为探测结果试一试，思考它应该被归为哪一类。
2. **（入门）补齐用例**：给 `transcript_suite()` 加入讲义列出但缺失的 `negative-missing-capabilities`（期望 `-32021`）、`negative-unsupported-version`（`-32022`）、`negative-notification-response`、`golden-input-required`；记得同步修改测试里的 `assertEqual(len(results), 15)`。
3. **（进阶）补旧时代 golden 并修 bug**：加入 `golden-legacy-list`，观察它失败；修改 `validate_response`，把推断出的 `semanticType` 写回后再做方法级校验（测验 Q9）。
4. **（进阶）修 `Mcp-Name` 编码器**：把哨兵判断改为 `or`，并写一个往返测试覆盖 `"what?="`、`"=?base64?abc"`、空字符串、emoji（测验 Q10）。
5. **（进阶）加固发布门**：必需用例集合、策略阈值、最小样本数、`math.isfinite` 检查；给回滚证明加 `observedAt` 与最大有效期；把 `inspect_proxy` 的折叠检测改成"egress 状态必须等于 origin 状态"；让 `compare_sdk_view` 报告 `addedFields`。
6. **（挑战）Practice Lab：请求级 SSE transcript**：记录状态、content type、有序事件与流终止；每个事件做时代相关的结果/错误校验；加入"代理缓冲整条流"和"事件 id 与请求不符"两个负例；事件数据脱敏；把首事件延迟、流时长、事件数纳入健康窗口。

---

## 8. 常见坑

- **用 SDK 的返回值证明一致性**：SDK 可能合成缺失字段、去掉未知字段；要采集解码前的原始字节。
- **一个"宽松验证器"同时接受新旧两种形状**：会奖励畸形的现代对端。
- **收到现代错误就降级**：掩盖真实问题，并给降级攻击开门。
- **把超时当作"对方是旧版"**：沉默不是证据。
- **先判断版本支持、后比较 header**：无法区分 `-32020` 与 `-32022`。
- **按 header 授权、按 body 执行**：每一跳都要比较 `Mcp-Name` 与 body。
- **header 值做大小写归一化**：只有名字大小写不敏感，值是敏感的。
- **编码器与解码器判定条件不对称**：合法值无法往返。
- **把未知 `resultType` 当 complete**：可能丢掉一个任务或输入请求的生命周期。
- **只测 handler 不测序列化器**：通知的 `None` 可能被中间件包成 `{result: null}`。
- **负例只断言"失败了"或只断言一个公共错误码**：无法证明是哪条规则在起作用。
- **本地校验器抛错就算 header 不匹配用例通过**：必须验证服务端真实响应。
- **证据先落盘再脱敏**：必须在序列化、哈希、日志、上传之前脱敏。
- **脱敏黑名单只写一种拼写**：要统一规范化；同时注意黑名单之外的敏感键。
- **健康阈值随证据提交、NaN 当成健康、零样本当成零错误**。
- **用真值判断代替精确类型**：`healthy: "yes"`、任意字符串当 digest。
- **没有已验证的回滚目标就发布**：应 hold。
- **`hmac.compare_digest` 传入非 ASCII 字符串**：会抛 `TypeError`。

---

## 9. 测试在验证什么

测试文件 `tests/test_main.py` 与前两节不同：它用 `sys.path.insert(0, <code 目录>)` 后直接 `import main`。因此在同一个 Python 进程里同时导入多个小节的 `main` 时可能互相覆盖（单独运行本节测试没有问题）。文件顶部定义了签名者 `release-controller` 和一个由固定字符串哈希得到的非秘密密钥，`rollback_evidence()` 生成经认证的回滚证据，`release_gate()` 创建信任该签名者的发布门。

运行：

```bash
cd phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations
python3 -m unittest discover -s code/tests -v
```

实际结果：`Ran 35 tests in 0.006s — OK`。

**transcript 与请求校验**

| 测试 | 验证的性质 |
|------|-----------|
| `test_golden_and_negative_transcript_suite_passes` | 15 条用例全部达到预期结果，数量恰为 15 |
| `test_header_mismatch_fixture_requires_valid_protocol_error_response` | header 不匹配夹具带 400 + `-32020` 响应且通过 |
| `test_header_mismatch_cannot_pass_without_actual_error_response` | 本地拒绝正确但服务端 500 无 body → 失败，detail 含 "expected JSON-RPC error response is missing" |
| `test_modern_request_uses_only_exact_namespaced_metadata_keys` | 夹具只用命名空间键，不含裸别名 |
| `test_bare_metadata_aliases_are_rejected` | 裸 `protocolVersion`/`clientCapabilities` → `-32602` |
| `test_header_body_mismatch_uses_modern_error_code` | `Mcp-Name` 不一致 → `-32020` |
| `test_http_header_names_are_case_insensitive` | 全小写 header 名照样通过 |
| `test_conflicting_duplicate_header_values_are_rejected` | `Mcp-Method` 与 `mcp-method` 值冲突 → `-32020` |
| `test_mcp_name_base64_sentinel_is_decoded_before_comparison` | `résumé_lookup` 被编码且能通过；非法 Base64 哨兵 → `-32020` |
| `test_raw_mcp_name_whitespace_requires_base64_sentinel` | 带首尾空格的名字：编码后通过，原样发送 → `-32020` |

**结果与时代**

| 测试 | 验证的性质 |
|------|-----------|
| `test_modern_result_requires_result_type_but_legacy_can_infer_complete` | 现代缺 `resultType` 抛错；旧版推断 complete 且 `inferred=True` |
| `test_unknown_additive_result_fields_are_preserved` | `futureHint` 保留在 `wire` 中 |
| `test_unknown_result_type_is_rejected` | `surprise` 被拒 |
| `test_extension_result_type_requires_advertised_capability` | 未声明能力的 `task` 被拒，声明后接受 |
| `test_task_ttl_literal_missing_is_an_invalid_value_not_an_absent_field` | `ttlMs: "missing"` 报类型错误 |
| `test_completion_complete_validates_its_method_payload` | 合法 completion 通过，含整数值的被拒 |
| `test_recognized_modern_error_never_triggers_legacy_fallback` | fallback 下 `-32021` → modern |
| `test_timeout_alone_never_proves_legacy_era` | 超时：无允许名单、有允许名单无证据、strict，三种都失败 |
| `test_legacy_requires_allowlist_and_positive_initialize_evidence` | 允许名单 + 正确旧版证据 → legacy；版本不符 → 失败 |
| `test_notification_has_empty_http_outcome_and_no_json_rpc_response` | 通知 → `(202, None)`；加了 id 就不是通知 |

**SDK、代理、发布门与脱敏**

| 测试 | 验证的性质 |
|------|-----------|
| `test_sdk_may_hide_bookkeeping_but_dropped_semantic_field_is_reported` | 只去掉 `_meta` 时匹配；丢 `futureHint` 时报告 |
| `test_sdk_differential_preserves_legacy_complete_inference` | 旧版 `{"tools": []}` 的差分能通过（注意：同样的结果走 `run_transcript` 会失败，见 3.9） |
| `test_sdk_differential_accepts_advertised_task_result` | 去掉 `resultType`、`ttlMs`、`cacheScope` 的 task 视图视为匹配 |
| `test_sdk_differential_rejects_malformed_advertised_task_result` | 原始 task 结果缺 status 时直接抛错 |
| `test_proxy_evidence_detects_error_collapse_and_redacts_credentials` | 400 → 500 被发现；`Authorization` 被脱敏 |
| `test_healthy_transcripts_and_proxy_promote_release` | 全部证据合格 → promote |
| `test_healthy_candidate_holds_without_verified_rollback_target` | 候选健康但无回滚证据 → hold |
| `test_failed_candidate_selects_only_evidenced_healthy_rollback` | 候选失败 + 回滚就绪 → rollback |
| `test_failed_candidate_holds_without_rollback_evidence` | 候选失败 + 无回滚证据 → hold |
| `test_empty_conformance_sdk_and_proxy_evidence_never_promotes` | 三类证据为空 → 不 promote，三条原因齐全 |
| `test_truthy_strings_do_not_authenticate_a_rollback_target` | `"yes"`、`"truthy"` 之类的真值字符串无法通过 |
| `test_tampered_authenticated_rollback_evidence_is_rejected` | 签名后把版本改成 9.9.9 → 校验失败 |
| `test_nested_sensitive_values_are_redacted_before_hashing` | `Cookie`、`Set-Cookie`、`X-Api-Key`、`api_key` 被脱敏，`q` 保留 |
| `test_camel_case_credentials_are_redacted_recursively` | camelCase 的 `accessToken`、`clientSecret`、`registrationAccessToken` 被脱敏 |
| `test_secret_key_separator_variants_share_one_redaction_policy` | 连字符、下划线、点号三种分隔变体都被脱敏 |

测试覆盖的空白（可作为练习补上）：

- 旧时代的 golden transcript（补上后会失败，暴露 `validate_response` 的 bug）。
- `Mcp-Name` 编码往返（`"what?="` 一类值）。
- 缺能力 `-32021`、不支持版本 `-32022` 的 transcript 级负例；"给通知发了响应"的负例。
- 负例的规则精确性（目前只比错误码）。
- 代理把 400 改成 502/200、SDK 合成新字段、健康窗口阈值被放宽 / NaN / 单样本、回滚证明的有效期与非 ASCII 签名。
- 发布门对必需用例集合的覆盖要求。
