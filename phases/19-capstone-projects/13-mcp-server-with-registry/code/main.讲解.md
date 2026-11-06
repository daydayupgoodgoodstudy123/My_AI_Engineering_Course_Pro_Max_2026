# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 13 节 综合项目 13：带注册表与治理机制的 Stateless MCP 服务端 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节根目录执行 `python3 code/main.py`；测试 `python3 -m unittest discover -s code/tests -v` ｜ **依赖**：仅标准库（`hashlib`、`json`、`re`、`time`、`copy`、`dataclasses`、`typing`），不开网络端口、不验证真实 OAuth、不调用 OPA、不发布到 Registry

---

## 1. 这份代码在考察什么

讲义开篇一句话："Production MCP is not one server process. It is a chain of contracts"。这份代码用纯标准库把这条"合约链"中**不需要网络**的部分做成可执行模型：

1. **两层发现**：`registry_document()` 生成 `server.json`（发布元数据），`discover()` 返回运行时能力，二者分开存储、分开校验。
2. **Stateless 请求/结果信封**：每个请求都要带 `_meta`（协议版本 + 客户端能力），每个结果都带 `resultType: "complete"` 和 `serverInfo`；版本错误区分 `-32602` 与 `-32022`。
3. **可缓存的工具列表**：`tools_list()` 按名字排序，带 `ttlMs` 与 `cacheScope`。
4. **授权 + 策略**：`policy_decide` 依次检查 issuer、audience、过期、工具存在、scope、负载大小，destructive 工具还要 action-bound approval。
5. **审批记录**：`ApprovalRecord` 把 actor、tool、参数摘要、目标服务器、过期时间绑在一起，改一个参数就不能重放。
6. **Registry 准入**：`validate_registry_document`（部分 schema 校验）、`validate_publisher_namespace`（反向 DNS 归属）、`validate_runtime_alignment`（发布 vs 运行时漂移）。
7. **审计**：放行、拒绝、handler 出错都记录，参数和结果先脱敏再落盘。

讲义自己也划清了边界："These models prove local contract logic. They do not prove HTTP headers, OAuth exchange, Registry publication, OPA integration, load balancing, or collector receipt."

> 一句话：**把"谁能在什么条件下调用哪个工具、留下什么证据"写成一串可单元测试的纯函数**。读代码时要同时留意它省略了什么——参数 schema 校验、一次性审批、完整审计字段——这些正是面试和评审中最常被追问的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROTOCOL_VERSION` 等常量 | 常量 + 预编译正则 | 协议版本、Registry schema URI、发布域名、名称/域名标签/URL/版本范围的正则 | 合约常量 |
| `request_meta` | 函数 | 生成每个请求必带的 `_meta` | Stateless 请求信封 |
| `error` | 函数 | 构造 `{"error": {code, message, data?}}` | JSON-RPC 错误对象 |
| `validate_meta` | 函数 | 校验 `_meta`：对象、版本字符串、版本受支持、能力是对象 | `-32602` / `-32022` |
| `ToolSchema` | frozen dataclass | 工具名、所需 scope、是否 destructive、描述、输入 schema | 工具契约 |
| `MCPServer` | dataclass | 注册工具；`result` / `discover` / `tools_list` / `registry_document` | 服务端 + 两层发现 |
| `Token` | frozen dataclass | user、issuer、audience、scopes、过期时间 | 已验证的访问令牌（模拟） |
| `arguments_digest` | 函数 | sorted-keys 紧凑 JSON 的 SHA-256 | 参数规范化摘要 |
| `ApprovalRecord` | frozen dataclass | `for_action` 生成、`authorize` 校验 | Action-bound approval |
| `policy_decide` | 函数 | 授权 + 策略的全部检查 | 第二层策略决策 |
| `redact` | 函数 | 正则替换邮箱、SSN | 审计脱敏 |
| `AuditEntry` | frozen dataclass | 一条审计记录 | 审计证据 |
| `dispatch` | 函数 | `tools/call` 的完整流程：meta → 策略 → handler → 审计 → 结果 | 调用管线 |
| `validate_registry_document` | 函数 | `server.json` 的部分形状校验（remote 子集） | Registry 形状契约 |
| `reverse_dns_namespace` / `validate_publisher_namespace` | 函数 | 域名 → 反向 DNS；检查名字是否在已验证命名空间内 | 命名空间归属 |
| `validate_runtime_alignment` | 函数 | 比较 `server.json` 与 `serverInfo` 的 name/version | 漂移检测 |
| `Registry` | dataclass | `register` 串起全部校验并保存两层数据；`search` 简单搜索 | Registry 准入 |
| `build_readonly_server` / `build_destructive_server` | 工厂函数 | 构造两个示例服务器及其工具 | 只读 / 状态变更面分离 |
| `main` | 函数 | 注册、打印两层发现、两次放行的调用、审计日志 | 演示 |

数据流：`build_*_server()` → `Registry.register()`（形状校验 → 命名空间 → `discover` → 身份对齐 → 存储）→ 签发 `Token` 与 `ApprovalRecord` → `dispatch()`（`validate_meta` → `policy_decide` → handler → `redact` → `AuditEntry`）→ 打印结果与审计。

---

## 3. 逐段精讲

### 3.1 常量与正则

```python
PROTOCOL_VERSION = "2026-07-28"
REGISTRY_SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
PUBLISHER_DOMAIN = "example.com"
SERVER_NAME_RE = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
REMOTE_URL_RE = re.compile(r"^https?://\S+$")
VERSION_RANGE_RE = re.compile(r"(?:^[~^<>=]|[*]|(?:^|\.)x(?:$|\.))", re.IGNORECASE)
```

- 两个日期互相独立：协议版本 `2026-07-28` 与 Registry schema 版本 `2025-12-11`。讲义："Do not rewrite one date to match the other."
- `SERVER_NAME_RE`：`命名空间/服务器名`，斜杠前允许字母数字点横线，斜杠后还允许下划线。
- `DOMAIN_LABEL_RE`：一个 DNS 标签，1～63 个字符，首尾必须是字母或数字（中间可以有 `-`）。
- `REMOTE_URL_RE`：只检查 `http(s)://` 开头且无空白，很宽松——`http://` 也能过，生产中远程端点应要求 https。
- `VERSION_RANGE_RE`：三个分支——以 `~ ^ < > =` 开头（范围运算符）、含 `*`、以 `x` 作为一个点分段（如 `1.x`）。实测 `^1.2`、`1.x`、`1.2.*`、`>=1`、`x.1` 被拒；`1.0.0-rc.1`、`v1`、`2024.01.01` 通过。

### 3.2 请求信封与 `validate_meta`

```python
def request_meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {
            "name": "registry-capstone-client",
            "version": "1.0.0",
        },
    }
```

- 讲义："The version and capabilities are request facts, not connection facts." 每次调用都重新生成一份，任何副本拿到消息都能独立校验。
- 键名用 `io.modelcontextprotocol/` 前缀，是 `_meta` 中保留给协议本身的命名空间。

```python
def validate_meta(meta: object) -> dict | None:
    if not isinstance(meta, dict):
        return error(-32602, "params._meta must be an object")
    requested = meta.get("io.modelcontextprotocol/protocolVersion")
    if not isinstance(requested, str):
        return error(-32602, "protocolVersion must be a string")
    if requested != PROTOCOL_VERSION:
        return error(
            -32022,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
    if not isinstance(meta.get("io.modelcontextprotocol/clientCapabilities"), dict):
        return error(-32602, "clientCapabilities must be an object")
    return None
```

- 返回 `None` 表示通过，返回错误字典表示失败——调用方统一写 `invalid = validate_meta(meta); if invalid: return invalid`。
- 错误码严格区分：缺失或非字符串 → `-32602`（invalid params）；是字符串但不支持 → `-32022`，data 恰为 `{"supported": [...], "requested": "..."}`，与讲义逐字一致。
- 校验顺序有意义：先确认是对象，再看版本，最后看能力。版本错时不再检查能力，避免返回多个混杂错误。
- 没有校验 `clientInfo`（TS 模型会检查它若存在则必须有字符串 `name`/`version`），Python 更宽松。
- `error()` 只返回 `{"error": ...}`，没有 `jsonrpc`、`id` 字段——这是"去掉传输外壳"的模型，真实服务器要把 id 回填。

### 3.3 `ToolSchema` 与 `MCPServer`

```python
@dataclass(frozen=True)
class ToolSchema:
    name: str
    required_scope: str
    destructive: bool
    description: str
    input_schema: dict
```

- `frozen=True`：创建后不可修改，工具契约一旦注册就不该被悄悄改动。
- 每个工具声明自己需要的 **scope**（如 `postgres:query:readonly`），授权检查按工具粒度进行。
- `destructive` 是唯一的风险布尔值，它同时决定注解和"是否需要 approval"。⚠️ MCP 注解里 `readOnlyHint=false, destructiveHint=false` 可以表示"会写但只是新增"（如创建 issue），本模型把 `jira.create` 标成 destructive，是出于"状态变更都要审批"的保守策略，但两个 hint 被绑定成互斥，表达力有所损失。

```python
    def result(self, **fields: object) -> dict:
        return {
            "resultType": "complete",
            **fields,
            "_meta": {"io.modelcontextprotocol/serverInfo": self.server_info},
        }
```

- 所有成功结果都经过这里：保证 `resultType: "complete"` 与 `serverInfo` 一定存在（讲义："Ordinary results include `resultType: "complete"`. Servers should place their identity in `_meta.io.modelcontextprotocol/serverInfo` on each result."）。
- `**fields` 展开调用方传入的关键字参数；`_meta` 写在最后，即使调用方传了 `_meta` 也会被覆盖。

```python
    def discover(self, meta: dict) -> dict:
        invalid = validate_meta(meta)
        if invalid:
            return invalid
        return self.result(
            supportedVersions=[PROTOCOL_VERSION],
            capabilities={"tools": {"listChanged": False}},
            ttlMs=3_600_000,
            cacheScope="public",
        )
```

- `server/discover` 本身也要求 `_meta`——它是"普通的必需 RPC"，不是会话初始化（Key Terms："not a session initializer"）。
- `ttlMs=3_600_000` 即 1 小时，`public`：能力对所有调用者相同，可共享缓存。
- `listChanged: False`：本服务器不会推送工具列表变化通知。

```python
    def tools_list(self, meta: dict) -> dict:
        ...
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "annotations": {
                    "readOnlyHint": not tool.destructive,
                    "destructiveHint": tool.destructive,
                },
            }
            for tool in sorted(self.tools.values(), key=lambda item: item.name)
        ]
        return self.result(tools=tools, ttlMs=60_000, cacheScope="private")
```

- **按名字排序**：讲义要求"a stable tool order so identical lists can reuse prompt caches"。字典本身按插入顺序，排序后与注册顺序无关。
- `ttlMs=60_000`（60 秒）+ `private`：工具可见性在生产中随用户授权变化。⚠️ 但这里返回的是**全部**工具，并没有按 token 过滤；`tools_list` 甚至不接收 token 参数。
- `required_scope` 不出现在列表里——权限模型不暴露给客户端。

```python
    def registry_document(self) -> dict:
        return {
            "$schema": REGISTRY_SCHEMA,
            "name": self.name,
            ...
            "remotes": [{"type": "streamable-http", "url": self.url}],
        }
```

- `server.json` 里**没有工具列表、没有能力**，只有身份与连接方式，体现两层分离。

### 3.4 `Token`、参数摘要与 `ApprovalRecord`

```python
@dataclass(frozen=True)
class Token:
    user: str
    issuer: str
    audience: str
    scopes: frozenset[str]
    expires_at: float
```

- 这是"已经通过签名校验后的 token 声明"的模拟：`user` 对应 `sub`，`issuer` 对应 `iss`，`audience` 对应 `aud`/resource。
- `frozenset`：不可变集合，可以放进 frozen dataclass，`in` 判断 O(1)。
- `is_expired` 用 `now >= expires_at`：恰好到期的那一刻就算过期（fail closed）。

```python
def arguments_digest(args: dict) -> str:
    normalized = json.dumps(
        args,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

- **规范化**：`sort_keys=True` 让 `{"b":1,"a":2}` 与 `{"a":2,"b":1}` 得到同一字符串；`separators=(",", ":")` 去掉空白；`ensure_ascii=False` 保留原始 Unicode。实测两种键顺序的摘要完全相同。
- 输出 64 位十六进制（SHA-256 = 256 bit）。
- ⚠️ 数字表示没有规范化：`{"n": 1}` 与 `{"n": 1.0}` 摘要不同（实测）。更严格可用 RFC 8785（JCS）规范化。

```python
    @classmethod
    def for_action(cls, actor, tool, args, target, expires_at) -> ApprovalRecord:
        return cls(actor, tool, arguments_digest(args), target, expires_at)

    def authorize(self, actor, tool, args, target, now) -> tuple[bool, str]:
        if self.actor != actor:
            return False, "approval actor does not match token subject"
        if self.tool != tool:
            return False, "approval tool does not match requested tool"
        if self.target != target:
            return False, "approval target does not match this server"
        if self.arguments_digest != arguments_digest(args):
            return False, "approval arguments do not match requested action"
        if now >= self.expires_at:
            return False, "approval has expired"
        return True, "ok"
```

- `@classmethod` 工厂：调用方传原始参数，记录里只存**摘要**，审批记录本身不含敏感参数原文。
- 五个绑定维度：谁（actor = token 的 user）、做什么（tool）、对哪里（target = 服务器 URL）、具体参数（digest）、何时之前（expiry）。
- 返回 `(bool, reason)` 元组，拒绝原因会原样进入错误消息和审计。
- ⚠️ **没有一次性使用**：同一条 approval 在过期前可以无限次使用（实测连续 3 次都成功）。讲义要求的 "one-time or repeat-use policy" 只实现了 repeat-use。一次性需要 approval id + 共享存储中的原子消费（见测验 Q10）。
- 讲义强调"Approval is separate evidence, not a scope added to the access token"——代码里 approval 是 `dispatch` 的独立参数，不在 `Token` 里。

### 3.5 `policy_decide`：授权与策略

```python
def policy_decide(server, tool, token, args, now, approval=None) -> tuple[bool, str]:
    if token.issuer != server.trusted_issuer:
        return False, "token issuer is not trusted by this server"
    if token.audience != server.url:
        return False, "token audience does not match this server"
    if token.is_expired(now):
        return False, "token has expired"
    schema = server.tools.get(tool)
    if schema is None:
        return False, f"no such tool: {tool}"
    if not token.has_scope(schema.required_scope):
        return False, f"missing scope: {schema.required_scope}"
    if len(json.dumps(args)) > 8192:
        return False, "payload too large"
    if schema.destructive:
        if approval is None:
            return False, "destructive tool requires an action-bound approval"
        approved, reason = approval.authorize(token.user, tool, args, server.url, now)
        if not approved:
            return False, reason
    return True, "ok"
```

检查顺序与意义：

| 顺序 | 检查 | 拒绝消息 | 对应讲义 |
|-----|------|---------|---------|
| 1 | issuer 是否受信任 | `token issuer is not trusted...` | "Validate token issuer" |
| 2 | audience 是否等于本服务器 URL | `token audience does not match...` | "audience or resource"；练习 4 |
| 3 | 是否过期 | `token has expired` | "expiry" |
| 4 | 工具是否存在 | `no such tool: ...` | — |
| 5 | 是否有该工具所需 scope | `missing scope: ...` | "scopes" |
| 6 | 参数 JSON 长度 ≤ 8192 | `payload too large` | 有界输入 |
| 7 | destructive → approval 校验 | `...requires an action-bound approval` 等 | "Bind approvals to exact high-risk actions" |

- 身份类检查放在最前：未认证的调用者连"工具是否存在""需要什么 scope"都不应得知。
- 一律"先拒绝再执行"，handler 只在全部通过后才运行（讲义练习 4、5 的要求）。
- ⚠️ `len(json.dumps(args))` 默认 `ensure_ascii=True`，非 ASCII 字符被转义成 `\uXXXX`（6 个字符）。实测 1400 个汉字：转义后 8411 个字符被拒，但 UTF-8 实际只有 4211 字节。应改为按 UTF-8 字节计算。
- ⚠️ **没有参数 schema 校验**：`inputSchema` 只在 `tools_list` 里展示，`dispatch` 从不检查。讲义说 TS 模型会校验，Python 模型不会（见 3.7 与测验 Q9）。
- `approval.authorize` 的 target 传的是 `server.url`，所以给 A 服务器的审批不能用在 B 服务器上。

### 3.6 脱敏与审计记录

```python
def redact(payload: dict) -> dict:
    text = json.dumps(payload)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[ssn]", text)
    return json.loads(text)
```

- 思路：序列化成字符串 → 正则替换 → 再解析回字典，一次处理任意嵌套结构。
- 邮箱正则：`本地部分@域名.后缀`；SSN 正则：`\b` 单词边界 + `3-2-4` 位数字。
- 实测：`"mail a.b+c@x-y.co.uk ssn 123-45-6789 phone 555-123-4567"` → `"mail [email] ssn [ssn] phone 555-123-4567"`，电话号码没被处理。
- ⚠️ 正则脱敏只能覆盖已知模式；token、密钥、SQL 里的客户数据都会漏掉。讲义建议"Redact **or digest**"——对敏感字段只存摘要。

```python
@dataclass(frozen=True)
class AuditEntry:
    ts: float
    user: str
    issuer: str
    tool: str
    outcome: str
    args_redacted: dict
    response_redacted: dict
```

- ⚠️ 与讲义第 8 步对照，缺少 resource/audience、request id、trace context、latency；policy decision 只是拼进了 `outcome` 字符串（`denied:<reason>`）。

### 3.7 `dispatch`：一次 `tools/call` 的全流程

```python
def dispatch(server, token, tool, args, meta, audit, approval=None) -> dict:
    invalid = validate_meta(meta)
    if invalid:
        return invalid
    now = time.time()
    allowed, reason = policy_decide(server, tool, token, args, now, approval)
    if not allowed:
        audit.append(
            AuditEntry(now, token.user, token.issuer, tool, f"denied:{reason}", redact(args), {})
        )
        return error(-32000, reason)
    try:
        response = server.handlers[tool](args)
    except Exception as exc:
        audit.append(
            AuditEntry(now, token.user, token.issuer, tool, "handler_error", redact(args), {})
        )
        return server.result(
            content=[{"type": "text", "text": str(exc)}],
            isError=True,
        )
    audit.append(AuditEntry(now, token.user, token.issuer, tool, "allowed", redact(args), redact(response)))
    return server.result(
        content=[{"type": "text", "text": json.dumps(response)}],
        structuredContent=response,
        isError=False,
    )
```

三种结局，对应三种**不同层次**的错误表达：

| 结局 | 返回形态 | 审计 outcome | 含义 |
|-----|---------|-------------|------|
| `_meta` 非法 | `{"error": {-32602/-32022}}` | **不记录** | 协议层错误，请求还没"进入"服务器 |
| 策略拒绝 | `{"error": {-32000, reason}}` | `denied:<reason>` | 授权/策略层拒绝 |
| handler 异常 | `result(isError=True)` | `handler_error` | 工具执行失败，属于**工具结果**而不是协议错误 |
| 成功 | `result(content, structuredContent, isError=False)` | `allowed` | — |

- 协议错误不写审计：单元测试 `test_dispatch_requires_metadata_on_every_call` 明确断言 `audit == []`。
- 工具执行失败用 `isError: True` 的**结果**表达，这是 MCP 的约定：让模型看到失败原因并自行调整，而不是当作 JSON-RPC 协议错误。
- `content` 是给模型看的文本（`json.dumps(response)`），`structuredContent` 是给程序用的结构化结果，两者并存。
- `time.time()` 在函数内部取，无法注入时钟；测试过期逻辑只能用"过去的时间戳"。
- ⚠️ `-32000` 是 JSON-RPC 保留给"服务器自定义错误"的区间，代码把所有策略拒绝（含未知工具）都归为它。客户端只能靠 message 字符串区分原因，最好用不同错误码或结构化 `data`。
- ⚠️ handler 异常时 `str(exc)` 直接返回给调用方：`KeyError('sql')` 变成文本 `'sql'`，既没帮助又可能泄露内部细节；审计里也没记录异常类型。

### 3.8 Registry 文档校验

```python
def validate_registry_document(document: object) -> list[str]:
    if not isinstance(document, dict):
        return ["server.json must be an object"]
    issues: list[str] = []
    for key in ("name", "description", "version"):
        if key not in document:
            issues.append(f"missing {key}")
    ...
```

- **收集全部问题而不是遇错即停**：返回问题列表，便于一次性修复（单元测试 `test_invalid_registry_document_is_rejected` 一次断言 4 条问题）。
- 逐项规则：`$schema` 若存在必须等于固定 URI（可选字段）；`name` 3～200 字符且匹配 `namespace/server`；`description`、`title`（若存在）1～100 字符；`version` 1～255 字符、不是范围、不是 `latest`；`remotes` 必须非空，每项 `type` 为 `streamable-http` 或 `sse`、`url` 为 http(s)。
- 注意写法 `if "title" in document and (...)`：字段**存在**才检查，所以缺 `title` 不报错，但 `title: None` 会报错（测试覆盖了这一点）。
- docstring 明确声明这只是"remote-only profile 的子集"，讲义："do not present this dependency-free subset as full schema validation"。发布前必须用固定版本的官方 JSON Schema 或 `mcp-publisher` 完整校验。
- "要求 `remotes` 非空"是本课程的额外约束（官方 schema 也允许只有 `packages` 的记录），因为本综合项目总要对 remote 做在线探测。

### 3.9 命名空间与漂移

```python
def reverse_dns_namespace(domain: str) -> str:
    normalized = domain.casefold().rstrip(".")
    labels = normalized.split(".")
    if len(labels) < 2 or any(DOMAIN_LABEL_RE.fullmatch(label) is None for label in labels):
        raise ValueError("publisher domain must be a valid multi-label DNS name")
    return ".".join(reversed(labels))
```

- `casefold()` 小写化、`rstrip(".")` 去掉 FQDN 末尾的点：实测 `"Sub.Example.COM."` → `com.example.sub`。
- 至少两个标签：`localhost` 会抛 `ValueError`。
- `reversed(labels)` 反转后用点拼回：`example.com` → `com.example`。

```python
def validate_publisher_namespace(document, verified_domain) -> list[str]:
    if not isinstance(document, dict) or not isinstance(document.get("name"), str):
        return []
    namespace = document["name"].partition("/")[0]
    expected = reverse_dns_namespace(verified_domain)
    if namespace != expected and not namespace.startswith(f"{expected}."):
        return [f"name namespace must be {expected} or its child for verified domain {verified_domain}"]
    return []
```

- `partition("/")[0]` 取斜杠前的命名空间。
- 允许"等于"或"以 `expected.` 开头"（子命名空间）。末尾带点很关键：`com.examplefoo` 不会被误认为 `com.example` 的子空间（实测被拒）。
- 名字不是字符串时返回空列表——形状问题交给 `validate_registry_document` 报告，职责不重叠。
- 比较区分大小写：`COM.EXAMPLE/x` 能通过 `SERVER_NAME_RE`，但会被这里拒绝（fail closed）。

```python
def validate_runtime_alignment(document: dict, discovery: object) -> list[str]:
    ...
    if server_info.get("name") != document.get("name"):
        issues.append("runtime serverInfo.name does not match server.json name")
    if server_info.get("version") != document.get("version"):
        issues.append("runtime serverInfo.version does not match server.json version")
    return issues
```

- 这就是讲义第 7 步的"drift report"核心：发布说的身份必须与活进程报告的身份一致。
- 只比 name 和 version；讲义还要求比较 remote URL 与所需能力（练习 1）——本模型直接调用对象方法，没有"按发布 URL 去探测"这一步，因此无法发现 URL 漂移。

### 3.10 `Registry`：准入流程

```python
    def register(self, server: MCPServer) -> None:
        document = server.registry_document()
        issues = validate_registry_document(document)
        issues.extend(validate_publisher_namespace(document, self.publisher_domain))
        if issues:
            raise ValueError("; ".join(issues))
        discovery = server.discover(request_meta())
        if "error" in discovery:
            raise ValueError("runtime discovery failed")
        alignment_issues = validate_runtime_alignment(document, discovery)
        if alignment_issues:
            raise ValueError("; ".join(alignment_issues))
        self.entries[server.name] = deepcopy(document)
        self.runtime_discovery[server.name] = deepcopy(discovery)
```

- 准入顺序：静态形状 + 命名空间 → 在线探测 → 身份对齐 → 存储。任何一步失败都抛异常，不会留下半注册状态。
- 两层数据分别存进 `entries` 与 `runtime_discovery`，用 `deepcopy` 防止之后修改服务器对象影响已存档的证据。
- 讲义交付物拒绝规则："Refuse to publish metadata that points to an endpoint whose live discovery cannot be verified"——对应 `"error" in discovery` 分支。

```python
    def search(self, query: str) -> list[str]:
        needle = query.casefold()
        return sorted(
            name
            for name, entry in self.entries.items()
            if needle in name.casefold()
            or needle in entry["title"].casefold()
            or needle in entry["description"].casefold()
        )
```

- 大小写不敏感的子串搜索，结果排序保证确定性。实测 `search("read")` → `['com.example/internal-readonly']`，`search("tools")` 两个都命中（标题里都有 "Tools"）。
- ⚠️ `entry["title"]`：`title` 是可选字段，缺失时会 `KeyError`；应写 `entry.get("title", "")`。此方法在 `main` 与测试中都没有被调用。

### 3.11 两个示例服务器与 `main`

```python
    server.register(
        ToolSchema(
            "postgres.readonly",
            "postgres:query:readonly",
            False,
            "Run an approved read-only query.",
            {"type": "object", "properties": {"sql": {"type": "string"}},
             "required": ["sql"], "additionalProperties": False},
        ),
        lambda args: {"rows": [[1]], "sql": args["sql"]},
    )
```

- 只读服务器有 `postgres.readonly`、`s3.list` 两个工具；状态变更服务器单独部署，只有 `jira.create`（destructive）。对应讲义"Start with two read-only tools and one state-changing tool"以及"Keep high-risk tools on a separately reviewable surface"。
- handler 用 `lambda` 返回固定数据；`postgres.readonly` 不解析 SQL，传 `DROP TABLE users` 也返回成功——"只读"完全靠名字和注解，真实系统要靠只读数据库账号。
- 两个服务器的 `url` 不同、`trusted_issuer` 相同：同一个授权服务器，为不同资源签发不同 audience 的 token。
- `MCPServer.register` 重名时抛 `ValueError`，防止工具被静默覆盖。

`main()` 中：

- `readonly_token` 的 audience 是只读服务器 URL、scopes 为两个只读 scope；`approved_token` 的 audience 是 destructive 服务器 URL、scope 为 `jira:write`。
- `ApprovalRecord.for_action(..., time.time() + 900)`：审批 15 分钟有效，token 1 小时有效——审批应比 token 更短命。
- 只演示了两次**成功**调用；拒绝路径全部在单元测试里。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯函数 + dataclass，不开网络端口 | 每条合约都能单元测试 | 证明不了 HTTP header（`-32020`）、SSE 取消、负载均衡；讲义要求 Wire/Proxy 证据 |
| `server.json` 与 `discover` 分两份存储 | 发布事实 ≠ 运行事实 | 需要真正按发布 URL 探测才能发现 URL 漂移 |
| `validate_meta` 区分 `-32602` / `-32022` | 与讲义规定一致，客户端可据此降级 | — |
| `tools_list` 排序 + `ttlMs` + `cacheScope` | 确定性、可缓存、利于 prompt cache | 未按用户过滤；生产中按 token 过滤并标 `private` |
| 身份检查先于工具查找 | 不向未认证者泄露工具与权限模型 | — |
| approval 只存参数摘要 | 绑定精确动作且不存原文 | 无一次性消费；数字表示未规范化；生产用共享存储原子消费 + JCS |
| 只读与状态变更拆成两个服务器 | 缩小爆炸半径，独立 audience | 讲义提醒：凭据、策略、部署身份、审计也必须分离才有意义 |
| 正则脱敏 | 零依赖演示 | 覆盖面窄；生产对敏感字段存摘要或用专门的 DLP |
| 策略拒绝统一 `-32000` | 简单 | 客户端无法程序化区分原因；可用不同码或结构化 data |
| 参数 schema 只展示不校验 | 代码短 | 与 TS 模型、讲义描述不一致；应在 handler 前校验并返回 `isError` |
| `Registry.register` 一次走完准入 | 失败即拒绝、无半注册 | 讲义 Admission 证据还要求记录 digest、descriptor pin、ledger 事件 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，使 `-> ApprovalRecord`（类内引用自身）和 `dict \| None` 写法可用 |
| 联合类型 `X \| None` | `def validate_meta(meta: object) -> dict \| None` | 返回字典或 `None` |
| `typing.Callable` 类型别名 | `Handler = Callable[[dict], dict]` | "接收 dict、返回 dict 的函数"类型，提高可读性 |
| `re.compile` 预编译 | `SERVER_NAME_RE = re.compile(r"...")` | 模块加载时编译一次，后续 `fullmatch`/`search` 复用 |
| `fullmatch` vs `search` | `SERVER_NAME_RE.fullmatch(name)`、`VERSION_RANGE_RE.search(version)` | 整串匹配 vs 任意位置匹配 |
| 正则标志 | `re.IGNORECASE` | 忽略大小写 |
| 非捕获组 | `(?:^\|\.)x(?:$\|\.)` | 分组但不保存匹配结果 |
| `@dataclass(frozen=True)` | `ToolSchema`、`Token`、`ApprovalRecord`、`AuditEntry` | 实例不可变、可哈希，适合"证据"类对象 |
| `field(default_factory=dict)` | `tools: dict[str, ToolSchema] = field(default_factory=dict)` | 每个实例一个新字典 |
| `@property` | `def server_info(self) -> dict` | 像属性一样访问计算值：`self.server_info` |
| `@classmethod` 工厂 | `ApprovalRecord.for_action(...)` | 用 `cls(...)` 构造实例，封装"先算摘要再建对象" |
| `**kwargs` 收集与 `**` 展开 | `def result(self, **fields)`、`{"resultType": "complete", **fields, ...}` | 收集任意关键字参数；在字典字面量中展开 |
| 数字下划线 | `3_600_000`、`60_000` | 可读性分隔 |
| `frozenset` | `frozenset({"jira:write"})` | 不可变集合 |
| 元组返回 + 解包 | `allowed, reason = policy_decide(...)` | 同时返回结果与原因 |
| f-string | `f"missing scope: {schema.required_scope}"`、`f"remotes[{index}].type ..."` | 拼接错误消息 |
| `json.dumps` 参数 | `ensure_ascii=False, separators=(",", ":"), sort_keys=True`、`indent=2` | 规范化 / 紧凑 / 美化输出 |
| `hashlib` | `hashlib.sha256(b).hexdigest()` | 计算 SHA-256 十六进制摘要 |
| `re.sub` | `re.sub(pattern, "[email]", text)` | 正则替换 |
| `try / except Exception as exc` | `dispatch` 中包住 handler | 捕获任何异常，转成 `isError` 结果 |
| `isinstance` 类型守卫 | `if not isinstance(meta, dict)` | 处理来自外部、类型不可信的输入 |
| 链式比较 | `not 3 <= len(name) <= 200` | 等价于 `3 <= len and len <= 200` |
| `enumerate` | `for index, remote in enumerate(remotes)` | 错误消息里带下标 |
| 生成器 + `any` | `any(DOMAIN_LABEL_RE.fullmatch(l) is None for l in labels)` | 任一标签非法即为真，短路求值 |
| `str.partition` | `document["name"].partition("/")[0]` | 按第一个分隔符切成三段 |
| `casefold` | `domain.casefold()` | 比 `lower()` 更彻底的大小写折叠 |
| `reversed` + `join` | `".".join(reversed(labels))` | 反转标签顺序 |
| `deepcopy` | `self.entries[server.name] = deepcopy(document)` | 深拷贝，切断与原对象的引用 |
| `dataclasses.asdict` | `json.dumps(asdict(entry), sort_keys=True)` | dataclass 转字典以便序列化 |
| `lambda` 作 handler | `lambda args: {"rows": [[1]], "sql": args["sql"]}` | 匿名函数作为工具实现 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试 `import main` 时不执行演示 |

---

## 6. 运行结果解读

在小节根目录执行 `python3 code/main.py`（实际运行，瞬间完成）。输出分三段，以下为截取：

```text
=== registry metadata and runtime discovery ===
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "com.example/internal-readonly",
  "title": "Internal Read-Only Tools",
  "description": "Read-only incident and data lookup tools.",
  "version": "1.0.0",
  "remotes": [ { "type": "streamable-http", "url": "https://mcp.internal.example.com/readonly" } ]
}
{
  "resultType": "complete",
  "supportedVersions": [ "2026-07-28" ],
  "capabilities": { "tools": { "listChanged": false } },
  "ttlMs": 3600000,
  "cacheScope": "public",
  "_meta": { "io.modelcontextprotocol/serverInfo": { "name": "com.example/internal-readonly", "version": "1.0.0" } }
}
tools: {
  "resultType": "complete",
  "tools": [ { "name": "postgres.readonly", ... "annotations": { "readOnlyHint": true, "destructiveHint": false } },
             { "name": "s3.list", ... } ],
  "ttlMs": 60000,
  "cacheScope": "private",
  "_meta": { ... }
}

=== policy-gated calls ===
{'resultType': 'complete', 'content': [{'type': 'text', 'text': '{"rows": [[1]], "sql": "SELECT 1"}'}], 'structuredContent': {'rows': [[1]], 'sql': 'SELECT 1'}, 'isError': False, '_meta': {...}}
{'resultType': 'complete', 'content': [{'type': 'text', 'text': '{"id": "PROJ-99", "title": "new bug", "created": true}'}], 'structuredContent': {'id': 'PROJ-99', 'title': 'new bug', 'created': True}, 'isError': False, '_meta': {...}}

=== audit log ===
{"args_redacted": {"sql": "SELECT 1"}, "issuer": "https://auth.internal.example.com", "outcome": "allowed", "response_redacted": {"rows": [[1]], "sql": "SELECT 1"}, "tool": "postgres.readonly", "ts": 1791834616.895219, "user": "u42"}
{"args_redacted": {"title": "new bug"}, "issuer": "https://auth.internal.example.com", "outcome": "allowed", "response_redacted": {"created": true, "id": "PROJ-99", "title": "new bug"}, "tool": "jira.create", "ts": 1791834616.8953822, "user": "u42"}
```

逐项解读：

- **第一段两个 JSON**：同一个服务器的两层事实。`server.json` 只有身份与远程端点；`server/discover` 有版本、能力、缓存提示和 `serverInfo`。两者的 name/version 一致，所以 `Registry.register` 通过了漂移检查。
- **工具列表**：按名字排序（`postgres.readonly` < `s3.list`），`readOnlyHint: true`；`required_scope` 没有暴露。
- **第二段两次调用**：都是 `resultType: "complete"`、`isError: False`，`content` 是文本、`structuredContent` 是对象。第二次是 destructive 工具，因为带了参数完全一致、未过期、目标正确的 approval 才被放行。第一行打印的是 Python `dict` 的 repr（单引号、`False`），不是 JSON。
- **第三段审计**：两条 `allowed`。`ts` 是 Unix 时间戳，每次运行都会变；示例参数里没有邮箱/SSN，所以脱敏前后相同。注意审计里**没有** audience、请求 id、trace、耗时。
- `asdict` + `sort_keys=True` 让审计行的键按字母排序，便于 diff。

额外探测（自写脚本调用本模块，非 `main` 输出）：

| 探测 | 实际结果 |
|-----|---------|
| `postgres.readonly` 参数 `{"sql": 1, "extra": "x"}` | 放行，`isError: False`，审计 `allowed` |
| `postgres.readonly` 参数 `{}` | `isError: True`，文本 `'sql'`，审计 `handler_error` |
| 同一 approval 连续调用 3 次 | 3 次都成功 |
| 未知工具 `nope` | `{'error': {'code': -32000, 'message': 'no such tool: nope'}}` |
| 不可信 issuer + 未知工具 | 返回 issuer 错误，不泄露工具不存在 |
| 1400 个汉字的 `sql` | `payload too large`（转义后 8411 字符，UTF-8 实际 4211 字节） |

---

## 7. 动手改一改

1. **补参数校验**（必做）：实现测验 Q9 中的 `validate_args`，在 `dispatch` 中策略通过后、handler 之前调用；非法参数返回 `server.result(..., isError=True)` 且 handler 不被调用。补两条测试：类型错误、多余字段。
2. **讲义练习 5 的加强版——一次性审批**：给 `ApprovalRecord` 加 `approval_id` 与 `use_policy`，用一个可注入的 `ApprovalStore`（先用字典模拟共享存储）原子消费；写测试证明第二次使用被拒。
3. **修正大小限制**：改为按 UTF-8 字节计算，并补一条"1400 个汉字应放行"的测试。
4. **讲义练习 1——URL 漂移**：给 `Registry.register` 增加一个 `probe(url) -> discovery` 回调，按 `server.json` 里的 remote URL 探测；修改发布 URL 而不改服务器，报告精确的漂移项。
5. **补审计字段**：给 `AuditEntry` 加 `resource`、`request_id`、`traceparent`、`latency_ms`、`decision`（结构化）；把 `time.time()` 改成可注入的 `clock` 参数，并为 handler 错误记录异常类型。
6. **进阶——讲义练习 3**：写一个最小的 HTTP 包装层（`http.server`），校验 `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 与 body 一致，不一致返回 `-32020` 且不进入 `policy_decide`；用 `curl` 抓取原始 header 和 body 作为 Wire 证据。

---

## 8. 常见坑

- **把 `server.json` 当成能力声明**：发布元数据里写工具和能力，迟早与活进程不一致；能力只从 `server/discover` 取。
- **混用 `-32602` 与 `-32022`**：缺失或类型错误是 invalid params；只有"给了字符串但不支持"才用 `-32022`，而且 data 格式固定。
- **以为 annotations 是权限**：`readOnlyHint` 只是提示，本节 `postgres.readonly` 收到 `DROP TABLE` 照样"成功"。
- **audience 不校验**：为只读服务器签发的 token 被拿去调用写服务器（讲义练习 4）；本节在 `policy_decide` 第二步拦截。
- **审批变成可无限重放的通行证**：只绑定参数却不记录使用次数；一次性审批必须在共享存储中原子消费。
- **用进程内存保存跨调用状态**：两个副本之间不共享，负载均衡一换副本就丢；讲义要求显式 handle + 共享持久存储。
- **`json.dumps` 默认转义非 ASCII**：既影响大小限制，也会让摘要/日志与其他语言实现的结果不一致；涉及规范化时显式设置 `ensure_ascii`。
- **工具列表按用户变化却标 `public`**：共享缓存会把一个用户可见的工具泄露给另一个用户。
- **工具失败当协议错误返回**：handler 失败应是 `isError: True` 的结果，让模型能读到并调整；协议错误留给 envelope、版本、header 问题。
- **只靠正则脱敏**：遗漏电话、密钥等；敏感参数存摘要。
- **把本地模型当生产证明**：交付物拒绝规则第一条："Refuse to claim production readiness from the local simulations alone."

---

## 9. 测试在验证什么

测试文件 `code/tests/test_main.py`，用标准库 `unittest`。它通过 `Path(__file__).resolve().parents[2]` 找到小节根目录，把 `code/` 加入 `sys.path` 后 `import main`。`setUp` 每个测试新建两个服务器；辅助方法 `token(...)` 和 `approval(...)` 用关键字参数覆盖默认值，方便构造"只差一个字段"的负例。

运行方式（在小节根目录）：

```bash
python3 -m unittest discover -s code/tests -v
```

实际运行结果：**Ran 21 tests in 0.002s — OK**，全部通过。

| 测试 | 验证的性质 | 对应讲义 |
|-----|-----------|---------|
| `test_discover_advertises_current_revision_without_session_state` | `discover` 返回 `["2026-07-28"]`、1 小时 TTL、`public`、`complete`，没有 session 字段，`serverInfo.name` 正确 | 运行时发现、无 session |
| `test_unsupported_version_uses_reserved_error_and_exact_data` | 版本 `2025-11-25` → `-32022`，data 恰为 `{"supported": [...], "requested": "2025-11-25"}` | `-32022` 的精确格式 |
| `test_missing_or_non_string_version_is_invalid_params` | 缺失、整数、列表三种 → `-32602` 且无 data（`subTest` 分别报告） | 版本类型错误 |
| `test_tools_list_is_deterministic_cacheable_and_typed` | 名字已排序、`ttlMs=60000`、`private`、每个工具有 `inputSchema` | 可缓存发现 |
| `test_registry_document_and_runtime_discovery_remain_separate` | Registry 条目有 `$schema` 与 `streamable-http` remote，**没有** `tools`；运行时有 `capabilities` | 两层发现分离 |
| `test_example_domain_identity_uses_reverse_dns_in_both_layers` | `example.com` → `com.example`；两个服务器的发布名与 `serverInfo` 一致且命名空间合法 | 反向 DNS + 身份一致 |
| `test_registry_rejects_name_outside_verified_domain_namespace` | 名字改为 `io.example/...` 后 `register` 抛错（测试用 `".".join(("io", "example"))` 拼出该字符串） | 命名空间归属 |
| `test_registry_rejects_publication_runtime_identity_drift` | 用 `patch.object` 把 `discover` 换成返回篡改 name / version 的结果，`register` 抛出对应漂移错误 | 漂移检测 |
| `test_invalid_registry_document_is_rejected` | 只有 `name` 的文档一次报出缺 description、缺 version、缺 remotes、name 格式错 | 形状校验收集全部问题 |
| `test_registry_subset_validates_official_field_shapes` | name 无斜杠、空 description、101 字符 title、`None` title、`^1.2.3` 版本、`stdio` 类型、`file://` URL、缺 url 都被拒 | 字段约束 |
| `test_registry_subset_accepts_schema_optional_and_official_sse_remote` | 删掉 `$schema`、remote 改成 `sse` 仍然合法 | 可选字段与 SSE remote |
| `test_dispatch_requires_metadata_on_every_call` | `_meta` 为空字典 → `-32602`，**审计为空** | 每个请求都要 meta；协议错误不入审计 |
| `test_token_audience_is_bound_to_one_server` | audience 为只读服务器的 token 调 destructive 服务器 → 错误信息含 "audience"，审计 1 条 | 讲义练习 4 |
| `test_token_issuer_must_be_trusted` | issuer 为 attacker → 错误含 "issuer"，审计 1 条 | issuer 校验 |
| `test_expired_token_is_rejected` | 过期 token → 错误含 "expired" | 过期校验 |
| `test_destructive_tool_requires_an_approval_record` | 有 `jira:write` scope 但无 approval → 拒绝 | scope 不等于审批 |
| `test_approval_is_bound_to_actor_tool_target_and_expiry` | 四种 approval 分别只错 actor / tool / target / 过期，各自被拒且信息含对应关键词 | approval 绑定维度 |
| `test_approval_cannot_be_replayed_with_changed_arguments` | 审批 `"approved change"`，调用 `"different change"` → 错误含 "arguments" | 讲义练习 5 |
| `test_exact_action_approval_allows_destructive_call_without_magic_scope` | 精确匹配的 approval + 普通 `jira:write` scope → 成功，`created: True` | approval 是独立证据而非 scope |
| `test_allowed_call_returns_complete_result_and_audit_record` | 成功调用返回 `complete`、`isError: False`、`rows: [[1]]`，审计 outcome 为 `allowed` | 结果信封 + 审计 |
| `test_redaction_happens_before_audit_persistence` | `redact` 把邮箱与 SSN 字段替换成 `[email]` / `[ssn]` | 脱敏 |

测试**没有覆盖**、值得补上的负例：

- 参数不符合 `inputSchema`（类型错、多余字段、缺字段）时 handler 不应被调用——当前代码会失败；
- 同一 approval 第二次使用（一次性策略）——当前代码会放行；
- 未知工具、缺 scope 的拒绝路径（代码已实现但无测试）；
- 非 ASCII 负载的大小限制；
- `Registry.search` 在缺 `title` 时的行为。
