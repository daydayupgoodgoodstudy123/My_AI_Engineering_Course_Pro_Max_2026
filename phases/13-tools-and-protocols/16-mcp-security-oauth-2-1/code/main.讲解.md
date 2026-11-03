# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 16 节 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`base64`、`binascii`、`hashlib`、`secrets`、`threading`、`time`、`dataclasses`、`urllib.parse`；测试另用 `unittest.mock`、`concurrent.futures`），无需网络、无需真实 OAuth 服务器

---

## 1. 这份代码在考察什么

这是一个**进程内的协议与授权模拟器**：授权服务器（AS）、MCP 资源服务器（RS）、客户端三个角色都是普通 Python 对象，"HTTP 请求"就是方法调用。它覆盖了讲义的完整链路：

1. **发现**：RS 发布 RFC 9728 受保护资源元数据（`resource`、`authorization_servers`、`scopes_supported`），AS 发布 RFC 8414 风格的元数据（S256、`iss` 支持、CIMD 支持、可选的 `registration_endpoint`）。
2. **注册**：CIMD 优先（`enroll_cimd` 做大量 URL 与文档校验），DCR 只在 AS 不支持 CIMD 时作为兼容路径（`dynamic_register` 强制 `application_type`）。
3. **授权码 + PKCE**：`pkce_pair` 生成 S256 对；`authorize` 记录 client、redirect_uri、scope、challenge、resource、过期时间；`exchange` 在锁内逐项核对并一次性消费授权码。
4. **签发者绑定**：客户端校验授权响应中的 `iss`；client id 按 issuer 存，token 按 `(issuer, resource)` 存。
5. **RS 侧校验**：线协议（头 body 一致、版本）→ token 有效期、issuer、audience → 工具所需 scope；401/403/404 等全部包装成带原始 id 的 JSON-RPC 错误，`WWW-Authenticate` 作为 HTTP 头返回。
6. **升级认证（step-up）**：403 `insufficient_scope` → 客户端用合并后的 scope 重新授权 → 新 JSON-RPC id 重试。
7. **附加**：`Mcp-Name` 头对非 ASCII 工具名使用 `=?base64?...?=` 哨兵编码（讲义正文没有讲到这一点）。

> 一句话：**无状态请求的授权不是匿名的——每个凭证绑定到签发它的 issuer，每个 token 绑定到接收它的资源**。这份代码把每条绑定都写成了一个可以被测试击中的 `if`。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `RESOURCE` / `RESOURCE_METADATA_URI` / `ISSUER` / `CLIENT_METADATA_URL` | 常量 | 资源 URI、保留路径的 RFC 9728 URL、AS issuer、CIMD URL | 标识符 |
| `FORBIDDEN_CIMD_SECRET_FIELDS` / `PRIVATE_JWK_FIELDS` | 常量 | CIMD 中禁止出现的密钥字段与私钥 JWK 成分 | CIMD 不含秘密 |
| `TOOL_DESCRIPTORS` | 常量 | 三个工具（create / delete / list），对象根 schema | `tools/list` |
| `Token` | frozen dataclass | value、issuer、audience、subject、client_id、scopes、expires_at | access token |
| `ProtocolError` | frozen dataclass 异常 | 额外带 `http_status` 与 `headers` | JSON-RPC 错误 + HTTP 映射 |
| `pkce_pair` | 函数 | 生成 (verifier, S256 challenge) | PKCE |
| `encode_mcp_header_value` / `decode_mcp_header_value` | 函数 | `Mcp-Name` 的安全编码与解码 | 头部编码 |
| `make_mcp_request` / `make_discover_request` / `make_tools_list_request` | 函数 | 构造三类请求 | 无状态信封 |
| `AuthorizationServer` | dataclass | 元数据、应用类型与重定向校验、CIMD、DCR、authorize、exchange | AS |
| `ResourceServer` | dataclass | RFC 9728 元数据、线协议校验、discover/list/call、401/403 | RS |
| `Client` | 类 | 注册、授权（含 `iss` 校验）、按 issuer/resource 存储、升级认证 | MCP 客户端 |
| `demo` | 函数 | discover → list → 元数据 → CIMD 注册 → 三次工具调用 | 端到端 |

数据流（以 `notes.delete` 首次调用为例）：

`Client.call_with_step_up` → 无 token → `Client.authorize` → (`enroll` → `AuthorizationServer.enroll_cimd`) → `pkce_pair` → `AuthorizationServer.authorize` 返回 `{code, iss}` → 校验 `iss` → `AuthorizationServer.exchange` 得 `Token{notes:read}` → `make_mcp_request(id=1)` → `ResourceServer.call` → 403 + scope 挑战 → `Client.authorize({read, delete})` → `make_mcp_request(id=2)` → 200。

---

## 3. 逐段精讲

### 3.1 常量：标识符必须"逐字"一致

```python
RESOURCE = "https://notes.example.com/mcp"
RESOURCE_METADATA_URI = "https://notes.example.com/.well-known/oauth-protected-resource/mcp"
ISSUER = "https://auth.example.com"
CLIENT_METADATA_URL = "https://client.example.com/oauth/metadata.json"
```

- `RESOURCE_METADATA_URI` 演示 RFC 9728 的构造规则：把 `/.well-known/oauth-protected-resource` 插在主机与路径之间，**保留**原路径 `/mcp`。丢掉它可能拿到同一源上另一个受保护资源的元数据。
- `ISSUER` 是之后所有字典键（`client_ids_by_issuer`、`tokens_by_issuer_resource`）与 `iss` 比较的基准，后面的代码一律做纯字符串比较。
- `CLIENT_METADATA_URL` 既是 CIMD 文档的地址，也是 `client_id` 本身。

```python
FORBIDDEN_CIMD_SECRET_FIELDS = {"client_secret", "client_secret_expires_at", "private_key", "private_key_jwk", "private_key_pem"}
PRIVATE_JWK_FIELDS = {"d", "p", "q", "dp", "dq", "qi", "oth", "k"}
```

CIMD 文档是公开托管的，任何秘密放进去都等于公开。`PRIVATE_JWK_FIELDS` 是 RSA/EC 私钥成分（`d`、`p`、`q` 等）和对称密钥 `k`：公开 JWK 只应有 `kty`、`n`、`e`、`x`、`y` 之类。

### 3.2 `Token` 与 `ProtocolError`

```python
@dataclass(frozen=True)
class Token:
    value: str
    issuer: str
    audience: str
    subject: str
    client_id: str
    scopes: frozenset[str]
    expires_at: float
```

- `frozen=True` + `frozenset`：token 一经签发不可修改，scope 集合也不可变、可哈希。
- 模拟器把**整个 `Token` 对象**交给 RS，相当于"RS 已经通过签名验证或 introspection 得到了这些声明"。⚠️ 真实 RS 收到的是 `Authorization: Bearer <字符串>`，必须验证 JWT 签名或调用 AS 的 introspection；本模型中测试可以直接构造任意 `Token`，这只说明模拟器省略了验签步骤。

```python
@dataclass(frozen=True)
class ProtocolError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None
    http_status: int = 400
    headers: dict[str, str] | None = None
```

比第 14、15 节多了 `http_status` 与 `headers`：同一个异常同时决定 JSON-RPC 错误体、HTTP 状态码和 `WWW-Authenticate` 头。（frozen dataclass 做异常的隐患同前两节，见测验/讲解中的说明。）

### 3.3 `pkce_pair`

```python
def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge
```

- `token_urlsafe(32)`：32 字节随机数 → base64url 43 个字符，落在 RFC 7636 要求的 43–128 字符范围内（实测 verifier 与 challenge 都是 43 个字符）。
- S256：`challenge = BASE64URL(SHA256(ASCII(verifier)))`，去掉 `=` 填充。
- 客户端在授权请求中只发送 challenge，兑换时才发送 verifier；截获授权码的攻击者没有 verifier。

### 3.4 `Mcp-Name` 头的哨兵编码

```python
def encode_mcp_header_value(value: str) -> str:
    is_safe = (
        value.isascii()
        and value == value.strip()
        and all(0x20 <= ord(character) <= 0x7E for character in value)
        and not (value.startswith(BASE64_SENTINEL_PREFIX) and value.endswith(BASE64_SENTINEL_SUFFIX))
    )
    if is_safe:
        return value
    payload = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"{BASE64_SENTINEL_PREFIX}{payload}{BASE64_SENTINEL_SUFFIX}"
```

- HTTP 头值只能安全地携带可打印 ASCII（`0x20`–`0x7E`），且首尾空白可能被中间件剥掉。
- 不安全的值（非 ASCII、首尾空白、控制字符）整体 UTF-8 → Base64，包在 `=?base64?` 和 `?=` 之间。实测：`notes.検索` → `=?base64?bm90ZXMu5qSc57Si?=`；`" padded"` → `=?base64?IHBhZGRlZA==?=`。
- **歧义防护**：如果原值本身就长得像哨兵（`=?base64?x?=`），也强制编码（实测得到 `=?base64?PT9iYXNlNjQ/eD89?=`），否则服务端会把它误解码。
- 解码端 `base64.b64decode(payload, validate=True)` 拒绝非 Base64 字符；`binascii.Error`、`UnicodeDecodeError` 统一转成 `-32020`。未编码的值若含不安全字符同样 `-32020`。
- 讲义正文没有讲这个机制；它是代码在"头 body 一致性"上的补充，使非 ASCII 工具名也能参与比较（测试 `test_unicode_mcp_name_uses_and_decodes_base64_sentinel`、`test_malformed_base64_mcp_name_is_rejected`）。

### 3.5 请求构造

三个 `make_*` 函数都生成完整的 `_meta`（`clientCapabilities` 为 `{}`）。`make_mcp_request` 额外设置 `Mcp-Name`（经过编码）。没有任何地方出现 `Mcp-Session-Id`（测试 `test_mcp_request_has_no_session_identifier`）。注意：模拟器里**没有** `Authorization` 头——token 是作为 `handle` 的第三个参数传入的。

### 3.6 `AuthorizationServer`：元数据

```python
@dataclass
class AuthorizationServer:
    issuer: str = ISSUER
    supports_cimd: bool = True
    supports_dcr: bool = True
    clients: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    _pending_codes_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
```

- `field(default_factory=dict)`：可变默认值必须用工厂，否则所有实例共享同一个字典。
- `init=False, repr=False`：锁不出现在构造参数与 `repr` 中。
- `metadata()` 根据开关决定是否给出 `registration_endpoint`、`client_id_metadata_document_supported`，便于测试"只有 DCR 的老 AS"。

### 3.7 `_validate_application`：应用类型与重定向 URI

```python
        if require_application_type and application_type not in {"native", "web"}:
            raise ValueError("application_type must be native or web")
        if application_type is not None and application_type not in {"native", "web"}:
            raise ValueError("application_type must be native or web")
```

- DCR 路径 `require_application_type=True`：缺失或非法都拒绝；CIMD 路径为 `False`：可以没有，但有就必须合法。

每个重定向 URI 必须：是非空字符串、无首尾空白、内部无空白、能被 `urlparse` 解析、有 scheme、无 fragment；http/https 还必须有主机名。测试覆盖了 `123`、`"not-a-uri"`、`"https:///callback"`、`""` 与带 `#fragment` 的情况。

```python
        if application_type == "web":
            for parsed in parsed_redirects:
                if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1"}:
                    raise ValueError("web redirect URIs must use remote HTTPS")
```

⚠️ loopback 黑名单不完整：实测 `https://[::1]/cb`、`https://localhost./cb`、`https://127.0.0.2/cb` 都被接受为 `web` 重定向。应使用 `ipaddress.ip_address(host).is_loopback` 并处理 `localhost` 变体（测验 Q10）。`native` 客户端不做额外限制（实测 `https://evil.example/cb` 可被注册），因为 native 应用可以使用 claimed HTTPS 重定向；真正的保护是"只能回到已注册的 URI"+ PKCE。

### 3.8 `enroll_cimd`：CIMD 注册

按顺序校验：

| 检查 | 失败信息 |
|------|---------|
| AS 支持 CIMD | `CIMD is not supported` |
| `https`、有主机、路径不是 `""` 或 `/` | `...must be an HTTPS URL with a path` |
| 无 `user:pass@` | `...must not contain userinfo` |
| 无 `#fragment` | `...must not contain a fragment` |
| 路径段中没有 `.` / `..` | `...must not contain dot path segments` |
| 文档 `client_id` 与 URL 完全相等 | `CIMD client_id must equal its metadata URL` |
| `client_name` 是非空字符串 | `client_name is required` |
| `token_endpoint_auth_method` 不以 `client_secret` 开头 | `...must not use shared-secret client authentication` |
| 不含禁止的密钥字段 | `...must not contain client secrets or private keys` |
| `jwks.keys` 中没有私钥成分 | `CIMD jwks must contain public keys only` |
| 应用类型与重定向 URI 合法 | 见 3.7 |

- `FORBIDDEN_CIMD_SECRET_FIELDS.intersection(document)`：对字典求交集时，参与运算的是它的**键**。
- `any(isinstance(key, dict) and PRIVATE_JWK_FIELDS.intersection(key) for key in keys)`：生成器表达式 + 短路，发现一个含私钥成分的 JWK 即为真。
- ⚠️ 讲义强调获取 CIMD 文档是 **SSRF 敏感操作**（解析并校验地址、拒绝 loopback/私有/链路本地、限制重定向与大小与时间、要求 JSON）。模拟器中文档是直接作为参数传入的，没有网络获取，这部分防护没有体现。
- 成功后记录 `{**document, "enrollment": "cimd"}`，返回 URL 本身作为 client id。

### 3.9 `dynamic_register`：DCR 兼容路径

```python
    def dynamic_register(self, metadata: dict[str, Any]) -> str:
        if not self.supports_dcr:
            raise ValueError("DCR is not supported")
        self._validate_application(metadata, require_application_type=True)
        client_id = f"dcr_{secrets.token_hex(6)}"
        self.clients[client_id] = {**metadata, "enrollment": "dcr-compatibility"}
        return client_id
```

- client id 由 AS **铸造**（`dcr_` + 12 位十六进制），这正是"issuer-minted credential"——不能带到别的 issuer。
- 记录 `"enrollment": "dcr-compatibility"`，让审计能看出这是兼容路径。

### 3.10 `authorize` 与 `exchange`：授权码 + PKCE

```python
    def authorize(self, *, client_id, redirect_uri, subject, scopes, challenge, resource):
        client = self.clients.get(client_id)
        if client is None or redirect_uri not in client["redirect_uris"]:
            raise ValueError("unknown client or redirect URI")
        code = f"code_{secrets.token_hex(8)}"
        self.pending_codes[code] = {..., "scopes": frozenset(scopes), "challenge": challenge,
                                    "resource": resource, "expires_at": time.time() + 300}
        return {"code": code, "iss": self.issuer}
```

- 重定向 URI 必须**精确**在注册列表中。
- 授权码有效期 300 秒；响应带 `iss`（RFC 9207）。
- ⚠️ 模拟器省略了：用户认证与同意界面；对 `scopes` 是否在 `scopes_supported` 内、`resource` 是否为已知资源的校验——实测申请 `{"admin:everything"}` 或 `resource="https://evil.example/mcp"` 都会照常签发。真实 AS 必须基于策略决定授予哪些 scope、为哪些 audience 签发。

```python
        with self._pending_codes_lock:
            record = self.pending_codes.get(code)
            if record is None:
                raise ValueError("invalid authorization code")
            if record["expires_at"] <= time.time():
                self.pending_codes.pop(code, None)
                raise ValueError("invalid authorization code")
            if record["client_id"] != client_id: raise ValueError("client_id mismatch")
            if record["redirect_uri"] != redirect_uri: raise ValueError("redirect_uri mismatch")
            if record["resource"] != resource: raise ValueError("resource mismatch")
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if not secrets.compare_digest(challenge, record["challenge"]):
                raise ValueError("PKCE mismatch")
            self.pending_codes.pop(code)
```

- **整段在锁内**：并发的两次合法兑换只有一个能 `pop` 成功（测试用 `Barrier` 让两个线程同时兑换，结果恰好 1 个 `Token`、1 个 `ValueError`）。
- **过期边界**：`<=`，到期那一刻就失效，并顺手清掉记录（测试用 `patch.object(main.time, "time", return_value=expires_at)` 精确卡在边界）。
- **错误的 client / redirect / resource / verifier 不消费授权码**（测试逐一验证后，最后用正确参数仍能兑换）。这是一种设计选择：好处是攻击者拿着错误参数无法"烧掉"用户的授权码；代价是给了多次尝试的机会——由于 verifier 有 256 位熵，暴力猜测不可行。也有 AS 选择"任何失败兑换都作废授权码"。
- `secrets.compare_digest`：常数时间比较（与 `hmac.compare_digest` 等价）。
- 返回的 `Token` 有效期 3600 秒，`audience=resource`、`issuer=self.issuer`、`scopes` 来自授权时的记录。

### 3.11 `ResourceServer`：元数据与线协议

```python
    scopes: dict[str, str] = field(default_factory=lambda: {
        "notes.list": "notes:read",
        "notes.create": "notes:write",
        "notes.delete": "notes:delete",
    })

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {"resource": self.resource, "authorization_servers": [self.issuer],
                "scopes_supported": sorted(set(self.scopes.values()))}
```

- 工具 → 最小 scope 的映射；`scopes_supported` 由映射推导并排序，保证确定性。
- `default_factory=lambda: {...}`：用 lambda 返回一个新字典。

`_validate_wire` 与前两节相同的顺序（`-32600` / `-32602` → `-32020` → `-32022`），区别是 `Mcp-Name` 先经过 `decode_mcp_header_value` 再与 body 比较。它是 `@staticmethod`，测试可以直接调用 `main.ResourceServer._validate_wire(body, headers)`。

### 3.12 `ResourceServer.handle`：认证 → 工具 → scope

```python
            elif method == "tools/call":
                challenge_base = f'Bearer resource_metadata="{RESOURCE_METADATA_URI}"'
                challenge_headers = {"WWW-Authenticate": challenge_base}
                if token is None or token.expires_at < time.time():
                    raise ProtocolError(-32001, "Unauthorized", {"reason": "invalid_token"}, 401, challenge_headers)
                if token.issuer != self.issuer or token.audience != self.resource:
                    raise ProtocolError(-32001, "Unauthorized", {"reason": "invalid_token"}, 401, challenge_headers)
                required = self.scopes.get(params.get("name"))
                if required is None:
                    raise ProtocolError(-32602, "Unknown tool", {"name": params.get("name")}, 404)
                if required not in token.scopes:
                    challenge = f'{challenge_base}, error="insufficient_scope", scope="{required}"'
                    raise ProtocolError(-32003, "Insufficient scope", {"requiredScope": required}, 403,
                                        {"WWW-Authenticate": challenge})
```

| 顺序 | 检查 | 结果 |
|------|------|------|
| 1 | 无 token 或已过期 | 401、`-32001`、`WWW-Authenticate: Bearer resource_metadata="..."` |
| 2 | issuer 或 audience 不匹配 | 同上 |
| 3 | 工具不存在 | 404、`-32602`、`data.name` |
| 4 | scope 不足 | 403、`-32003`、`data.requiredScope`，头中 `error="insufficient_scope", scope="..."` |
| 5 | 通过 | 200，文本 `"<tool> allowed for <subject>"` |

讨论：

- **先认证再查工具**：实测无 token 调用不存在的 `notes.purge` 得到 401 而不是 404，未认证者无法探测工具列表之外的名字。
- `server/discover` 与 `tools/list` **不需要 token**（讲义："Discovery and a user-independent tool list can be available before authorization"），所以它们的 `cacheScope` 可以是 `public`。
- ⚠️ 有效期检查用 `expires_at < time.time()`，到期那一刻 token 仍然有效（实测 200）；授权码用 `<=`。两处边界语义不一致。
- ⚠️ "未知工具"在这里是 **404** + `-32602`，而第 14、15 节是 **400** + `-32602`；讲义只规定"未知**方法**"返回 404 + `-32601`。`-32001`、`-32003` 也是本代码自选的错误码，讲义未规定数值。
- ⚠️ 401 的 `WWW-Authenticate` 没有带 `error="invalid_token"`（RFC 6750 推荐携带），原因只放在 JSON-RPC `data.reason` 里。

```python
            if is_notification:
                return 202, None, {}
            return 200, self._success(body["id"], result), {}
        except ProtocolError as error:
            if is_notification:
                return error.http_status, None, dict(error.headers or {})
            return (error.http_status, self._error(body.get("id"), error), dict(error.headers or {}))
```

- 返回三元组 `(状态, 响应体, 响应头)`。
- 通知出错：没有 body，但**仍返回 HTTP 状态和头**（实测 scope 不足的通知得到 `(403, None, {"WWW-Authenticate": ...})`）。
- `dict(error.headers or {})`：复制一份，避免调用方修改异常里的字典。
- ⚠️ 非 POST 在这里是 `ProtocolError(-32600, "HTTP method not allowed", http_status=405)`，即 405 **也带 JSON-RPC 错误信封**（测试 `test_modern_http_entrypoint_error_is_json_rpc_envelope`），而第 14、15 节返回 `(405, None)`。本节讲义强调"Every request error ... is a JSON-RPC error envelope with the original request id"，但真实的 GET 请求通常没有 JSON-RPC body，可带的 id 有限。

### 3.13 `Client`：注册、授权与按 issuer 存储

```python
        self.redirect_uri = "http://127.0.0.1:8765/callback" if application_type == "native" else "https://client.example.com/callback"
        self.client_ids_by_issuer: dict[str, str] = {}
        self.tokens_by_issuer_resource: dict[tuple[str, str], Token] = {}
        self.next_request_id = 1
```

`native` 客户端用 loopback 回调，`web` 客户端用远程 HTTPS 回调。两个字典的键体现了讲义的存储规则。

```python
    def enroll(self, auth: AuthorizationServer) -> str:
        metadata = auth.metadata()
        if metadata.get("issuer") != auth.issuer:
            raise ValueError("authorization metadata issuer mismatch")
        if metadata.get("client_id_metadata_document_supported"):
            client_id = auth.enroll_cimd(CLIENT_METADATA_URL, self._client_document())
        elif metadata.get("registration_endpoint"):
            fallback = self._client_document()
            fallback.pop("client_id")
            client_id = auth.dynamic_register(fallback)
        else:
            raise ValueError("authorization server offers no supported client enrollment")
        self.client_ids_by_issuer[auth.issuer] = client_id
        return client_id
```

- 降级条件是"AS **没有宣告** CIMD 支持"，而不是"CIMD 失败"：`enroll_cimd` 抛出的异常会直接向上传播，不会被吞掉后改走 DCR——符合讲义"Do not silently fall back after an arbitrary CIMD validation failure"。
- DCR 文档去掉 `client_id`（由 AS 分配），保留 `application_type`。
- 没有实现"预注册"分支（讲义优先级第一位）。
- ⚠️ `metadata.get("issuer") != auth.issuer` 在模拟器中恒为假（元数据就是用 `auth.issuer` 生成的）；真实客户端应把元数据中的 `issuer` 与**发现时使用的 issuer URL** 比较。

```python
        response = auth.authorize(client_id=client_id, redirect_uri=self.redirect_uri, subject=self.subject,
                                  scopes=scopes, challenge=challenge, resource=resource)
        if response.get("iss") != auth.issuer:
            raise ValueError("authorization response issuer mismatch")
        token = auth.exchange(code=response["code"], client_id=client_id, verifier=verifier,
                              redirect_uri=self.redirect_uri, resource=resource)
        self.tokens_by_issuer_resource[(auth.issuer, resource)] = token
```

- **先校验 `iss`，再用 `code`**。纯字符串比较：实测尾斜杠、大写主机、缺少 `iss` 都被拒绝，授权码留在 AS 中未被兑换。缺少 `iss` 也拒绝比讲义"when provided"更严格，但因为 AS 元数据宣告了 `authorization_response_iss_parameter_supported: true`，这正是 RFC 9207 对客户端的要求。
- 授权请求和 token 请求使用**同一个** `resource`。

### 3.14 `call_with_step_up`：升级认证

```python
        if server.issuer != auth.issuer:
            raise ValueError("protected resource selected a different issuer")
        key = (auth.issuer, server.resource)
        token = self.tokens_by_issuer_resource.get(key)
        if token is None:
            token = self.authorize(auth, server.resource, {"notes:read"})
        body, headers = make_mcp_request(self.next_request_id, tool)
        self.next_request_id += 1
        status, response, response_headers = server.call(body, headers, token)
        if status == 403 and response is not None and response.get("error", {}).get("code") == -32003:
            required = response_headers["WWW-Authenticate"].split('scope="', 1)[1].split('"', 1)[0]
            token = self.authorize(auth, server.resource, set(token.scopes) | {required})
            body, headers = make_mcp_request(self.next_request_id, tool)
            self.next_request_id += 1
            status, response, response_headers = server.call(body, headers, token)
        return status, response, response_headers
```

- 首次只申请 `notes:read`（最小 scope）。
- 403 + `-32003` 时从头部取出挑战 scope，与已有 scope 取并集重新授权，**用新 id 重试**，且只重试一次。
- `response.get("error", {}).get("code")`：链式 `get` 防止 `KeyError`。
- ⚠️ 解析只取引号内的整串：挑战若是 `scope="notes:read notes:delete"`，`required` 会变成一个含空格的字符串，被当成**单个** scope 申请，实测最终仍 403（测验 Q9）。应按空白切分。
- ⚠️ 模拟器跳过了"向用户解释并征得同意"这一步——讲义把它作为升级认证的必要环节。

### 3.15 `demo`

打印：discover 结果 → `tools/list` 的名字 → 受保护资源元数据 → CIMD client id → 三次工具调用 → 按 issuer 存储的键。最后一行名为 "effective client ids by issuer"，但打印的是 `sorted(client.client_ids_by_issuer)`，即**issuer 列表**，不是 client id 本身。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 三个角色都是进程内对象 | 每一步校验都可见、可测试 | 没有 HTTP、浏览器跳转、TLS；生产接第 09 节的 Streamable HTTP 适配器与真实 AS |
| RS 直接接收 `Token` 对象 | 跳过 JWT/introspection 细节 | 真实 RS 必须从 `Authorization` 头解析并验证签名或做 introspection |
| CIMD 优先，仅在未宣告支持时走 DCR | 符合讲义优先级，避免安全失败后的降级 | 没有预注册分支；没有 SSRF 防护（文档直接传入） |
| DCR 强制 `application_type` | 防止 OIDC 默认 `web` 导致 loopback 失败 | web 的 loopback 黑名单不全（`[::1]`、`127.0.0.2`、`localhost.`） |
| 授权码在锁内一次性消费，错误参数不消费 | 并发安全；防止恶意参数烧掉授权码 | 允许多次尝试（靠 verifier 熵兜底）；跨进程需数据库原子操作 |
| AS 不校验 scope 与 resource | 聚焦客户端与 RS 的逻辑 | 真实 AS 需基于策略、用户同意决定授予范围 |
| 精确字符串比较 `iss` | 符合 RFC 9207 与讲义 | 任何规范化差异都会失败——这正是想要的 |
| token 按 `(issuer, resource)` 存 | 签发者与受众隔离 | 需加密存储；未实现 refresh token 与轮换（练习 1） |
| 先认证后查工具，401/403/404 都是 JSON-RPC 信封 | 不泄露工具存在性；错误可被 JSON-RPC 客户端统一处理 | 未知工具 404 与第 14、15 节的 400 不一致；405 也带信封 |
| 单次升级认证，取挑战中的 scope 并集 | 最小权限、避免授权风暴 | 多 scope 挑战解析错误；未模拟用户同意 |
| `Mcp-Name` 的 Base64 哨兵编码 | 非 ASCII 工具名也能放进 HTTP 头并参与一致性比较 | 讲义未说明；客户端与服务端必须使用相同约定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 与 `field` | `clients: dict[...] = field(default_factory=dict)` | 可变默认值必须用 `default_factory`，否则所有实例共享一个对象 |
| `field(init=False, repr=False)` | `_pending_codes_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)` | 不进构造参数、不显示在 `repr` 中 |
| `default_factory=lambda: {...}` | `ResourceServer.scopes` | 每个实例得到一个新的默认字典 |
| `@dataclass(frozen=True)` | `Token` | 不可变对象 |
| `frozenset` | `scopes: frozenset[str]`、`frozenset(scopes)` | 不可变集合，可哈希 |
| 元组作字典键 | `tokens_by_issuer_resource[(auth.issuer, resource)]` | 复合键 |
| 集合运算 | `set(token.scopes) \| {required}`、`FORBIDDEN_CIMD_SECRET_FIELDS.intersection(document)` | 并集；与字典求交集时使用其键 |
| `str` 方法 | `value.isascii()`、`value.strip()`、`startswith`/`endswith`、`split('scope="', 1)` | 字符串检查与切分；`split` 的第二个参数是最多切几次 |
| `ord` 与链式比较 | `0x20 <= ord(character) <= 0x7E` | 字符码点；Python 支持 `a <= x <= b` |
| `all` / `any` + 生成器 | `all(0x20 <= ord(c) <= 0x7E for c in value)` | 惰性求值、短路 |
| 切片去掉前后缀 | `value[len(PREFIX):-len(SUFFIX)]` | 负索引从末尾计 |
| `base64` 家族 | `b64encode`、`b64decode(payload, validate=True)`、`urlsafe_b64encode(...).rstrip(b"=")` | 标准与 URL 安全编码；`validate=True` 拒绝非法字符 |
| `secrets` | `token_urlsafe(32)`、`token_hex(8)`、`compare_digest` | 安全随机数与常数时间比较 |
| `urllib.parse.urlparse` | `parsed.scheme`、`.netloc`、`.hostname`、`.path`、`.fragment`、`.username` | 解析 URL 各部分；`hostname` 会小写化并去掉 IPv6 方括号 |
| `with lock:` | `with self._pending_codes_lock:` | 临界区 |
| 多异常捕获 + 异常链 | `except (binascii.Error, UnicodeDecodeError, ValueError) as exc: raise ... from exc` | 统一转换为协议错误 |
| 仅限关键字参数 | `def authorize(self, *, client_id, redirect_uri, ...)` | 参数多时防止位置错位 |
| 返回三元组 | `return 202, None, {}` | `status, response, headers = ...` |
| 链式 `dict.get` | `response.get("error", {}).get("code")` | 安全地取嵌套字段 |
| 字典解包 | `{**document, "enrollment": "cimd"}`、`auth.exchange(**{**exchange, "client_id": "other"})`（测试） | 合并/覆盖字典；`**` 把字典展开成关键字参数 |
| f-string 中的引号 | `f'Bearer resource_metadata="{RESOURCE_METADATA_URI}"'` | 外层单引号，内部可直接写双引号 |
| 条件表达式 | `"http://127.0.0.1:8765/callback" if application_type == "native" else "https://..."` | 一行 if/else |
| 测试：`unittest.mock.patch.object` | `patch.object(main.time, "time", return_value=expires_at)` | 临时替换 `time.time`，精确测试边界 |
| 测试：猴子补丁 | `auth.authorize = wrong_issuer` | 运行时替换实例方法，模拟恶意 AS |

---

## 6. 运行结果解读

实际运行 `python3 main.py`：

```text
server discovery: {'supportedVersions': ['2026-07-28'], 'capabilities': {'tools': {'listChanged': False}}, 'ttlMs': 60000, 'cacheScope': 'public', 'resultType': 'complete', '_meta': {'io.modelcontextprotocol/serverInfo': {'name': 'notes-server', 'version': '2.0.0'}}}
tools: ['notes.create', 'notes.delete', 'notes.list']
protected resource metadata: {'resource': 'https://notes.example.com/mcp', 'authorization_servers': ['https://auth.example.com'], 'scopes_supported': ['notes:delete', 'notes:read', 'notes:write']}
CIMD client_id: https://client.example.com/oauth/metadata.json
notes.list 200 [{'type': 'text', 'text': 'notes.list allowed for alice'}]
notes.create 200 [{'type': 'text', 'text': 'notes.create allowed for alice'}]
notes.delete 200 [{'type': 'text', 'text': 'notes.delete allowed for alice'}]
effective client ids by issuer: ['https://auth.example.com']
```

逐项解读：

- **discovery 与 tools/list 不需要 token**：两者都是 `public` 缓存；工具按名字排序。
- **受保护资源元数据**：`scopes_supported` 由工具映射推导并排序。
- **CIMD client_id** 就是元数据 URL 本身——没有 AS 铸造的任何东西。
- **三次 200 背后隐藏了两次升级认证**（讲义："two separate scope step-ups"）。实际过程：`notes.list` 首次授权得 `{read}`，id 1 成功；`notes.create` id 2 得 403 → 授权 `{read, write}` → id 3 成功；`notes.delete` id 4 得 403 → 授权 `{read, write, delete}` → id 5 成功。实测：共 3 次授权流程，`next_request_id` 最终为 6，最终 token scope 为 `['notes:delete', 'notes:read', 'notes:write']`，`auth.pending_codes` 为空（每个授权码都被一次性消费），`auth.clients` 只有 1 个客户端。
- **最后一行**打印的是 issuer 列表（字典的键），不是 client id；它表明客户端只与一个 issuer 建立了关系。

---

## 7. 动手改一改

1. **修复 scope 解析**：用测验 Q9 的 `parse_scope_challenge`（正则 + `split()`）替换 `split('scope="', 1)` 写法；写一个子类让 RS 返回多 scope 挑战，断言升级后得到 200。
2. **修复 web 回调检查**：用 `ipaddress` 实现 `is_loopback_host`，让 `https://[::1]/cb`、`https://127.0.0.2/cb`、`https://localhost./cb` 都被拒绝；再考虑是否拒绝私有地址。
3. **讲义练习 3 + 5**：授权码已有过期；给 token 增加"到期即失效"的统一边界（改成 `<=`）。再创建第二个资源 `https://issues.example.com/mcp`（同一 AS），证明它的 token 在 notes 资源上得到 401。
4. **讲义练习 2**：给 `Client` 增加 issuer 白名单；issuer 变化时只复用 CIMD URL，拒绝使用任何旧 issuer 的 DCR client id 与 token；写测试覆盖"从 auth-one 切到 auth-two"。
5. **讲义练习 1**：让 `exchange` 同时签发 refresh token，实现 `refresh()`：每次刷新返回新 refresh token 并作废旧的；检测到旧 refresh token 被重用时吊销整个 token 家族。
6. **进阶**：给 AS 的 `authorize` 增加策略——`scopes` 必须是该资源 `scopes_supported` 的子集（但注意讲义说客户端不应假设挑战 scope 一定在其中），`resource` 必须是登记过的资源；并模拟一个"用户同意"回调，拒绝时返回 `access_denied`。

---

## 8. 常见坑

- **构造 RFC 9728 URL 时丢掉资源路径**：`/.well-known/oauth-protected-resource` 后面要接 `/mcp`。
- **从主机名猜 AS，或相信错误响应里的 issuer**：issuer 只能来自经过校验的受保护资源元数据，并符合本地信任策略。
- **规范化后比较 `iss`**：尾斜杠、大小写、默认端口、百分号编码都不能规范化，必须逐字相等。
- **CIMD 失败后静默改走 DCR**：会把安全失败变成一条更弱的注册路径。
- **DCR 不写 `application_type`**：可能被默认成 `web`，loopback 回调随即失败。
- **跨 issuer 复用凭证**：DCR client id、client secret、refresh/access token 都绑定签发它的 issuer；只有自托管的 CIMD URL 可移植。
- **token 放进 URL 查询参数**：会进入日志与 Referer；只能放 `Authorization` 头。
- **RS 不校验 audience，或把 MCP token 转发给下游**：受众体系整体失效（token passthrough）。
- **把 scope 挑战当成单个字符串**：RFC 6750 的 scope 是空格分隔列表。
- **升级认证后复用旧的 JSON-RPC id**：每次重试都是一个新请求。
- **只拦 `localhost` 和 `127.0.0.1`**：`[::1]`、`127.0.0.0/8` 其他地址、`localhost.` 都是 loopback。
- **为 stdio 本地服务端硬加浏览器 OAuth**：讲义明确不需要，信任边界是进程与操作系统。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover tests -v`。

实际运行结果：**28 个测试全部通过**（`Ran 28 tests in 0.005s`，`OK`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_discover_uses_current_result_shape` | discover 200、id 保留、`resultType`、`supportedVersions`、serverInfo |
| `test_tools_list_is_advertised_complete_and_deterministic` | discover 宣告 `tools`；两次 list 相同、已排序、对象根 schema、`ttlMs > 0`、`public` |
| `test_protected_resource_metadata_selects_issuer_and_path` | 元数据的 resource 与 AS；RFC 9728 URL 保留 `/mcp` |
| `test_cimd_client_id_is_metadata_url` | CIMD 注册后 client id 等于 URL，记录为 `cimd` |
| `test_cimd_requires_path_but_not_application_type` | 无 `application_type` 可以注册；无路径的 URL 被拒 |
| `test_cimd_rejects_forbidden_identifier_url_components` | userinfo、fragment、`.`、`..` 四种 URL 被拒（subTest） |
| `test_cimd_rejects_secret_bearing_metadata` | `client_secret_basic`、`client_secret`、`client_secret_expires_at`、`private_key`、含 `d` 的 JWK 被拒 |
| `test_dcr_fallback_declares_application_type` | AS 不支持 CIMD 时走 DCR，记录 `native` 与 `dcr-compatibility` |
| `test_dcr_rejects_missing_application_type` | DCR 缺 `application_type` 被拒 |
| `test_web_client_rejects_loopback_redirect` | `web` + `http://127.0.0.1/callback` 被拒 |
| `test_redirect_entries_must_be_valid_uri_strings` | 非字符串、无 scheme、无主机、空串被拒 |
| `test_redirect_uri_fragments_are_rejected_before_web_policy` | 带 fragment 的 URI 先于 web 策略被拒（错误信息含 "without fragments"） |
| `test_authorization_response_issuer_is_validated` | 猴子补丁让 AS 返回攻击者的 `iss`，客户端抛 "issuer mismatch" |
| `test_wrong_client_and_verifier_do_not_consume_authorization_code` | 错误的 client_id / redirect_uri / resource / verifier 各自报错且不消费授权码；最后正确兑换成功并消费 |
| `test_concurrent_valid_redemption_has_exactly_one_success` | 两线程同时兑换，恰好一个成功 |
| `test_authorization_code_is_invalid_at_expiry_boundary` | 时间恰为 `expires_at` 时兑换失败，记录被清除 |
| `test_credentials_are_keyed_by_issuer` | 对两个仅支持 DCR 的 AS 注册，得到两个不同 client id，按 issuer 分开存 |
| `test_resource_rejects_other_audience_with_json_rpc_error` | 他人 audience 的 token → 401、`-32001`、id 21、头中含元数据 URL |
| `test_step_up_requests_only_missing_scope` | 直接调 `notes.delete`：升级后 200，token 只有 `{read, delete}` |
| `test_routing_header_mismatch_is_json_rpc_400` | `Mcp-Name` 不一致 → 400、`-32020`，id 保留（在 token 检查之前） |
| `test_unicode_mcp_name_uses_and_decodes_base64_sentinel` | `notes.検索` 编码为哨兵格式且能被正确解码比较 |
| `test_malformed_base64_mcp_name_is_rejected` | `=?base64?%%%?=` → 400、`-32020` |
| `test_header_version_mismatch_precedes_support_check` | 只改 body 版本 → `-32020` |
| `test_unsupported_version_has_exact_error_data` | 头 body 一致的旧版本 → `-32022`，`data` 精确 |
| `test_unknown_method_is_json_rpc_404` | 未知方法 → 404、`-32601` |
| `test_accepted_notification_returns_empty_202` | 无 id 的 `tools/list` → `(202, None, {})` |
| `test_mcp_request_has_no_session_identifier` | 请求头不含 `Mcp-Session-Id`，`_meta` 完整 |
| `test_modern_http_entrypoint_error_is_json_rpc_envelope` | GET → 405，且带 JSON-RPC 错误信封与原 id |

测试没有覆盖、但已在本讲解中实测的点：

- 多 scope 挑战解析错误导致升级失败；
- `web` 回调接受 `[::1]`、`127.0.0.2`、`localhost.`；
- token 在 `expires_at` 那一刻仍被接受（与授权码边界不一致）；
- AS 对任意 scope、任意 resource 照常签发；
- 无 token 调用未知工具得到 401（认证先于工具查找）；
- scope 不足的 notification 返回 `(403, None, WWW-Authenticate 头)`。
