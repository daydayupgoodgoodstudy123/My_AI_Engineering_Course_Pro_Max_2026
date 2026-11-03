# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 18 节 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover -s code/tests -v` ｜ **依赖**：纯标准库（`base64`、`hashlib`、`hmac`、`json`、`secrets`、`threading`、`time`、`dataclasses`、`urllib.parse`），不开网络端口、不写文件

---

## 1. 这份代码在考察什么

这份代码用三个类在一个进程里模拟 MCP 2026-07-28 授权的**生产边界**：

1. **发现与部署门槛**：AS 发布 RFC 8414 元数据，客户端检查 `S256`、注册路径、`authorization_response_iss_parameter_supported`，RS 的 RFC 9728 元数据 URL 按"well-known 插在路径前"的规则生成。
2. **按签发者隔离的注册（enrollment）**：pre-registration → CIMD → 已弃用的 DCR；客户端凭据按 issuer 存，access token 按 `(issuer, resource)` 存。
3. **重定向 URI 策略**：`native` / `web` 两类客户端各自允许哪些 redirect URI（loopback HTTP、HTTPS、基于域名的私有 scheme）。
4. **授权码流程的硬化**：S256 PKCE、授权码 300 秒过期、一次性兑换（加锁保证原子性）、兑换时 client / redirect / resource 必须与发起时一致、RFC 9207 `iss` 校验防 mix-up。
5. **资源服务器的逐请求校验**：`iss` 白名单 → JWKS 缓存按 `kid` 取 key（未命中 re-fetch 一次）→ 验签 → `aud` → `exp` → 工具所需 scope，失败返回带 `resource_metadata` 的 `WWW-Authenticate`。
6. **Rotate 与 Refresh 的分工**：AS 轮换 key（保留 2 个重叠），RS 只重新拉取。

> 一句话：**把"token 到达真实 MCP 请求路径后仍然可信或被拒绝"拆成可以逐行验证的检查链**。同时要看清它在多签发者、key 保留策略、异常处理、scope 授予、对称密钥公开等处做了简化——这些是测验和面试追问的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `b64url` / `b64url_decode` | 函数 | 无填充的 base64url 编解码 | JWT 编码 |
| `jwt_sign` / `jwt_decode` / `jwt_verify` | 函数 | HS256 签名、拆解、常数时间验签 | JWT |
| `protected_resource_metadata_url` | 函数 | 由资源 URL 生成 RFC 9728 元数据 URL | PRM 发现 |
| `MCP_RESOURCE` 等常量 | 常量 | 两个 MCP 资源、工具→scope 映射、授权码 TTL=300 | audience、scope |
| `parsed_absolute_redirect_uri` 等 4 个函数 | 函数 | 重定向 URI 的语法与 native/web 策略校验 | RFC 8252 风格回调策略 |
| `IdPKey` | dataclass | 一个签名 key：`kid`、`secret`、`issued_at` | JWKS 条目 |
| `AuthorizationServer` | dataclass | 元数据、key 轮换、CIMD/DCR/预注册、发起授权、兑换授权码、签发 token | AS |
| `ResourceServer` | dataclass | JWKS 缓存与刷新、`validate`、`call_tool` | RS / MCP server |
| `Client` | dataclass | 发现、注册、`iss` 校验、切换 AS、完整授权 | OAuth 客户端 |
| `demo` | 函数 | 9 步 + bonus 的生产流程演示 | 整体流程 |
| `tests/test_main.py` | 测试 | 30 个单元测试 | 见第 9 节 |

数据流：`demo` 建 AS 并轮换两次 → `Client.discover` → `Client.enroll`（CIMD）→ `Client.authorize`（PKCE + `iss` 校验 + `resource`）→ `ResourceServer.call_tool` → `validate`（首次用时填充 JWKS 缓存）→ AS 轮换 + RS refresh → 旧/新 token 都通过 → 另一个 RS 拒绝 audience replay → step-up 拿到 delete scope。

---

## 3. 逐段精讲

### 3.1 JWT 工具函数：HS256 + 常数时间比较

```python
def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def jwt_sign(payload: dict, kid: str, secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64url(sig)}"
```

- JWT = `base64url(header).base64url(payload).base64url(signature)`，签名对象是前两段**编码后的字符串**，不是原始 JSON。
- base64url 去掉 `=` 填充；解码时 `-len(s) % 4` 算出要补几个 `=`（例如长度 43 → 补 1 个）。32 字节的 HMAC-SHA256 签名编码后正好 43 个字符（实测）。
- `separators=(",", ":")` 生成紧凑 JSON，避免空格导致同一内容出现多种编码。
- `jwt_verify` 用 `hmac.compare_digest` 做**常数时间比较**，防止通过响应时间逐字节猜签名。
- `jwt_verify` 从不读取 header 里的 `alg`，永远按 HS256 算——这在客观上"固定了算法"，`alg: none` 攻击无效（实测返回 `bad signature`）。生产应显式把接受的算法写进配置。
- ⚠️ `jwt_decode` / `jwt_verify` 都假设恰好三段、内容可解码；格式异常只有 `jwt_decode` 被 `try` 保护（见 3.8）。

### 3.2 `protected_resource_metadata_url`：well-known 插在路径前

```python
def protected_resource_metadata_url(resource: str) -> str:
    parsed = urlparse(resource)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("MCP resource must be an absolute HTTPS URL without query or fragment")
    suffix = "" if parsed.path in {"", "/"} else parsed.path
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{suffix}"
```

- `https://mcp.example.com/team/server` → `https://mcp.example.com/.well-known/oauth-protected-resource/team/server`（讲义原例，测试锁定）。
- 资源必须是 HTTPS、无 query、无 fragment——与讲义对 canonical URI 的要求一致（canonical URI 还要求小写 scheme/host，这里没做规范化）。
- 这个 URL 会出现在每个 401/403 的 `resource_metadata="..."` 参数里，是客户端重新发现 AS 的入口。

### 3.3 常量：工具 → scope 映射

```python
TOOL_SCOPES = {
    "notes.list": "mcp:tools.invoke",
    "notes.read": "mcp:tools.invoke",
    "notes.delete": "mcp:tools.delete",
    "tasks.list": "mcp:tools.invoke",
}
DEFAULT_TOOL_SCOPE = "mcp:tools.invoke"
AUTHORIZATION_CODE_TTL_SECONDS = 300
```

- 破坏性工具放在更强的 scope 后面，对应技能文件"Group destructive tools under their own scope"。
- 未列出的工具默认要求 `mcp:tools.invoke`（实测 `call_tool("whatever.drop", token)` 返回 200）——这是"默认允许"策略；更保守的做法是未知工具直接拒绝。
- 注释说 `mcp:tools.delete` "NOT in the IdP's minimal scopes_supported, so a client reaches it only via the step-up flow"，但 AS 并不检查请求的 scope（见 3.6），所以这个"门"在代码里并不存在。

### 3.4 重定向 URI 策略

```python
def parsed_absolute_redirect_uri(value: object):
    if (not isinstance(value, str) or not value or value != value.strip()
        or any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in value)):
        return None
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError:
        return None
    if not parsed.scheme or parsed.fragment or parsed.username is not None or parsed.password is not None:
        return None
    if parsed.scheme in {"http", "https"} and (not parsed.netloc or hostname is None):
        return None
    return parsed
```

逐条看它拒绝什么：

| 条件 | 拒绝的例子 | 为什么 |
|------|-----------|--------|
| 非字符串、空串、首尾空白、控制字符 | `""`、`" https://..."`、含 `\n` | 防止解析歧义与头注入 |
| `_ = parsed.port` 抛 `ValueError` | `https://a.b:65536/cb`、`:not-a-port` | 访问 `.port` 才会触发端口合法性检查，这一行是"故意求值" |
| 无 scheme | `/callback`、`callback` | 必须是绝对 URI |
| 有 fragment | `https://a.b/cb#x` | OAuth 规定重定向 URI 不能含 fragment |
| 带 userinfo | `https://user:pw@a.b/cb` | 防混淆主机名 |
| http(s) 但没主机 | `https:///callback` | 无效绝对 URL |

然后按客户端类型细分：

```python
def valid_native_redirect_uri(value: object) -> bool:
    parsed = parsed_absolute_redirect_uri(value)
    if parsed is None:
        return False
    if parsed.scheme == "https":
        return parsed.hostname is not None
    if parsed.scheme == "http":
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    return valid_private_use_scheme(parsed.scheme)
```

- **web**：只能 HTTPS。
- **native**：HTTPS；或只指向 loopback 的 HTTP（`127.0.0.1`、`::1`、`localhost`）；或"基于域名的私有 scheme"，如 `com.example.app:/oauth2redirect`。
- `valid_private_use_scheme` 要求 scheme 至少两段（以 `.` 分隔）、每段 ASCII 字母数字开头结尾、中间只含字母数字或 `-`。因此 `myapp:/cb`（一段）、`javascript:`、`data:`、`urn:` 都被拒（实测），`ftp://` 也被拒。
- 实测汇总：`http://127.0.0.1:7333/callback`、`http://localhost/cb`、`http://[::1]:80/cb`、`com.example.app:/cb` 对 native 合法；`http://app.example.com/cb` 对两类都不合法。
- ⚠️ 讲义提到 AS **应当**对 `localhost`-only 的重定向给出警告（localhost 冒充风险），代码直接接受 `localhost`，没有警告逻辑。

### 3.5 `AuthorizationServer`：key 轮换与元数据

```python
    def rotate_key(self) -> IdPKey:
        new_kid = f"k_{int(time.time())}_{secrets.token_hex(2)}"
        new = IdPKey(kid=new_kid, secret=secrets.token_bytes(32), issued_at=time.time())
        self.keys.append(new)
        if len(self.keys) > 2:
            self.keys = self.keys[-2:]
        return new

    def jwks(self) -> dict:
        return {"keys": [{"kid": k.kid, "kty": "oct", "alg": "HS256", "use": "sig", "k": b64url(k.secret)}
                         for k in self.keys]}
```

- `current_key()` 是 `keys[-1]`：总用最新 key 签名。
- 保留最近 2 个 key 实现讲义的"两个 key 重叠是稳态"。但保留是**按个数**而不是**按时间**：一个 token 在签发它的 key 之后又发生两次轮换就会 `unknown kid`，哪怕 `exp`（3600 秒）还没到。轮换间隔 15 分钟时最坏只能活约 15 分钟（测验 Q10 的计算）。
- `kid` = 秒级时间戳 + 2 字节随机（4 个十六进制字符）。同一秒内两次轮换的 `kid` 碰撞概率是 1/65536；碰撞时 `validate` 的 `next(...)` 会取到第一个同名 key，验签失败。
- ⚠️ **`jwks()` 把对称密钥 `k` 公开了**（实测输出 `'kty': 'oct', ..., 'k': 'O2Xl...'`）。在本进程模拟里无害，但真实 JWKS 是公开文档，公开 HS256 密钥 = 任何人都能伪造 token。讲义只说"Production uses RS256 or EdDSA"，没有点明这一层；生产 JWKS 只能放公钥。

`metadata()` 返回 RFC 8414 文档，字段与讲义 JSON 示例一致，包括 `client_id_metadata_document_supported: True`、`authorization_response_iss_parameter_supported: True`、`code_challenge_methods_supported: ["S256"]`。

### 3.6 三种注册方式

**CIMD**：

```python
    def register_cimd(self, document_url: str, document: dict) -> str:
        parsed = urlparse(document_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path in {"", "/"}:
            raise ValueError("CIMD client_id must be an absolute HTTPS URL with a path")
        if document.get("client_id") != document_url:
            raise ValueError("CIMD client_id must equal its document URL")
        client_name = document.get("client_name")
        if not isinstance(client_name, str) or not client_name.strip():
            raise ValueError("CIMD requires a non-empty client_name")
        application_type = document.get("application_type")
        ...
        redirect_application_type = application_type or "native"
```

- 三条硬规则：URL 必须 HTTPS 且有路径；文档里的 `client_id` 必须等于 URL；`client_name` 非空；`redirect_uris` 是非空列表且每项都是合法绝对 URI。
- `application_type` 可选；缺失时**按 native 的回调策略**检查（`redirect_application_type = application_type or "native"`），但记录里存的是原值 `None`（测试 `test_cimd_does_not_require_dcr_application_type`）。
- 返回值就是 `document_url`——CIMD 不铸造 `client_id`。
- ⚠️ 模拟简化：真实 CIMD 是 AS 在授权流程中**自己去抓**这个 URL；这里客户端把 URL 和文档一起交给 AS，AS 无从验证"文档真的托管在那个 URL"，也就演示不了讲义强调的 SSRF 防护。

**DCR（已弃用的兼容路径）**：

```python
        application_type = body.get("application_type")
        if application_type not in {"native", "web"}:
            return {"status": 400, "body": {"error": "invalid_client_metadata"}}
        ...
        cid = f"c_{secrets.token_hex(4)}"
        reg_token = secrets.token_urlsafe(24)
        self.clients[cid] = {
            ...
            "registration_access_token_hash": hashlib.sha256(reg_token.encode()).hexdigest(),
            ...
        }
```

- 与 CIMD 不同，DCR **必须**声明 `application_type`，否则 400 `invalid_client_metadata`。
- `token_endpoint_auth_method` 只允许 `none`（公开客户端）或 `private_key_jwt`。
- `registration_access_token` 只存 SHA-256 哈希，明文只在响应里出现一次——对应讲义三大陷阱之一。另外两个陷阱（按源 IP 限流、`software_statement` 校验）没有实现，是讲义练习 3、4。
- 返回 HTTP 风格的 `{"status": ..., "body": ...}`，而 CIMD 和预注册用抛 `ValueError`——同一个类里两种错误风格，是演示代码的折中。

**pre-registration**：`pre_register_client` 是 AS 运营方预置的客户端，同样执行 native/web 回调策略（测试 `test_pre_registered_redirects_follow_runtime_registration_policy` 确保预注册不能绕过运行时策略）。

### 3.7 授权码：发起与兑换

```python
        with self._authorization_codes_lock:
            now = time.time()
            expired_codes = [code for code, record in self.authorization_codes.items()
                             if record["expires_at"] <= now]
            for expired_code in expired_codes:
                self.authorization_codes.pop(expired_code, None)
            code = secrets.token_urlsafe(24)
            while code in self.authorization_codes:
                code = secrets.token_urlsafe(24)
            self.authorization_codes[code] = {..., "expires_at": now + AUTHORIZATION_CODE_TTL_SECONDS}
        return {"code": code, "iss": self.issuer}
```

- `begin_authorization` 前置检查：客户端已在本 issuer 注册、`redirect_uri` 在已注册列表中、`code_challenge` 非空且方法必须是 `S256`（拒绝 `plain`）、`resource` 是绝对 HTTPS URL。
- 每次发起新授权时**顺手清理过期授权码**，避免被放弃的授权码无限堆积（测试：1000 秒、1200 秒、1301 秒各发起一次，1301 时第一个——300 秒前到期于 1300——被清掉）。
- 响应带 `iss`，这就是 RFC 9207 的授权响应签发者参数。

```python
    def redeem_code(self, *, code, client_id, redirect_uri, code_verifier, resource) -> str:
        with self._authorization_codes_lock:
            record = self.authorization_codes.get(code)
            if record is None:
                raise ValueError("authorization code is invalid or already used")
            if record["expires_at"] <= time.time():
                self.authorization_codes.pop(code, None)
                raise ValueError("authorization code is expired")
            if record["client_id"] != client_id or record["redirect_uri"] != redirect_uri:
                raise ValueError("authorization code is not bound to this client redirect")
            if record["resource"] != resource:
                raise ValueError("token resource does not match the authorization request")
            supplied_challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())
            if not hmac.compare_digest(record["code_challenge"], supplied_challenge):
                raise ValueError("PKCE code_verifier does not match the stored challenge")
            self.authorization_codes.pop(code)
        return self.issue_token(client_id, record["user"], record["scopes"], record["resource"])
```

- **整段在锁内**：查找、校验、删除是一个原子操作。两个线程同时兑换同一个码，只有一个成功，另一个得到 "invalid or already used"（测试用 `threading.Barrier` 让两个线程同时冲）。如果没有锁，两个线程可能都通过 `get` 再各自 `pop`，签发两个 token。
- **S256**：`BASE64URL(SHA256(verifier))` 必须等于发起时存的 challenge。
- 过期判定是 `<=`：TTL 300 秒，1000 秒发起，1300 秒兑换就已过期。
- 设计细节：PKCE 不匹配时**不删除**授权码（测试 `test_pkce_verifier_is_checked_before_code_redemption` 断言码仍在）。这让错误的 verifier 不会烧掉合法用户的码；verifier 有 256 位熵，暴力猜测不可行。
- `issue_token` 用当前 key 签发，claims 包括 `iss`、`sub`、`aud=resource`、`azp=client_id`、空格分隔的 `scope`、`iat`、`exp=iat+3600`。
- ⚠️ AS **从不检查请求的 scope**：不对照 `scopes_supported`、不经过用户同意。实测请求 `{"mcp:tools.delete", "admin:everything"}`，token 的 scope 就是 `admin:everything mcp:tools.delete`。demo 的 "bonus: step-up" 因此只是"重新要一个更大的 scope"，并没有任何升级认证。

### 3.8 `ResourceServer.validate`：逐请求检查链

```python
    def validate(self, token: str, required_scope: str | None = None) -> dict:
        rm = self.resource_metadata

        def challenge(status: int, params: str) -> dict:
            return {"valid": False, "status": status, "www_authenticate": f"Bearer {params}"}

        try:
            header, claims, _ = jwt_decode(token)
        except Exception:
            return challenge(401, f'error="invalid_token", error_description="malformed", resource_metadata="{rm}"')

        iss = claims.get("iss", "")
        if iss not in self.allowed_issuers:
            return challenge(401, f'... error_description="iss not allowed" ...')
        cache = self.jwks_cache.get(iss)
        if cache is None:
            self.refresh_jwks()
            cache = self.jwks_cache.get(iss)

        matching = next((k for k in cache["keys"] if k["kid"] == header.get("kid")), None) if cache else None
        if matching is None:
            self.refresh_jwks()
            cache = self.jwks_cache.get(iss)
            matching = next((k for k in cache["keys"] if k["kid"] == header.get("kid")), None) if cache else None
        if matching is None:
            return challenge(401, f'... error_description="unknown kid" ...')

        if not jwt_verify(token, b64url_decode(matching["k"])):
            return challenge(401, '... "bad signature" ...')
        if claims.get("aud") != self.resource:
            return challenge(401, '... "audience mismatch" ...')
        if claims.get("exp", 0) < time.time():
            return challenge(401, '... "expired" ...')
        if required_scope and required_scope not in set(claims.get("scope", "").split()):
            return challenge(403, f'error="insufficient_scope", scope="{required_scope}", resource_metadata="{rm}"')
        return {"valid": True, "claims": claims}
```

检查顺序与返回：

| 步骤 | 失败时 | 说明 |
|------|--------|------|
| 解码 | 401 `malformed` | 只保护了这一步 |
| `iss` 白名单 | 401 `iss not allowed` | 放在 refresh 之前：不受信的签发者不值得一次 JWKS 拉取 |
| 首次使用填充缓存 | — | demo step 5 的 "JWKS cache primed on first use" |
| 按 `kid` 查 key，未命中 re-fetch 一次 | 401 `unknown kid` | 讲义的 cache-miss fall-back |
| 验签 | 401 `bad signature` | |
| `aud == self.resource` | 401 `audience mismatch` | 缺失 `aud` 时 `None != resource`，同样拒绝，不当通配符 |
| `exp` | 401 `expired` | 缺失 `exp` 时取 0，视为已过期（实测），fail closed |
| scope | 403 `insufficient_scope` + `scope="..."` | 客户端据此 step-up |

- `challenge` 是**嵌套函数**，闭包捕获了 `rm`，让每个分支只写差异部分。
- 先读未验签的 `iss`/`kid` 来**路由**（选白名单、选 key）是标准做法；真正的信任决定在验签之后。
- `aud` 用 `!=` 比较字符串：JWT 规范允许 `aud` 是数组，实测 `aud: ["https://notes.example.com"]` 会被判 `audience mismatch`——fail closed，但与某些 IdP 不兼容。
- 没有 `nbf`、`iat` 合理性检查，也没有时钟偏差容忍。

⚠️ 已实测的问题：

1. **多签发者不可用**：`refresh_jwks()` 永远只拉 `self.auth_server` 的 key，写到 `self.auth_server.issuer` 键下。白名单里第二个 issuer 签的合法 token 必然 `unknown kid`（测验 Q9）。
2. **异常没有全部转成 401**：payload 是 JSON 数组 → `AttributeError`；签名段长度模 4 余 1（如 `a`）→ `binascii.Error`；`exp` 是字符串 → `TypeError`。在 HTTP 服务里这些都会变成 500（测验 Q11）。
3. **"最多一次 refresh"是按请求计**：5 个随机 `kid` 的 token 触发 5 次 refresh，AS key 数不变（测验 Q12）。修好了 key 创建 DoS，但没有限制对 IdP 的拉取频率。

### 3.9 `refresh_jwks` 与 `call_tool`

```python
    def refresh_jwks(self) -> dict:
        keys = self.auth_server.jwks()["keys"]
        self.jwks_cache[self.auth_server.issuer] = {"keys": keys, "fetched_at": time.time()}
        return {"refreshed": True, "kids": [k["kid"] for k in keys]}
```

- 纯拉取、幂等：讲义"Resource servers only ever refresh"。线上是对 `jwks_uri` 的 HTTP GET，这里因为同进程直接读 AS 的列表。
- 缓存形状 `{issuer: {"keys": [...], "fetched_at": ...}}` 与讲义 JSON 一致；但 `fetched_at` 从未被读取——没有 TTL，也没有讲义所说的 stale-on-error 窗口。"定时刷新"在 demo 里是手动调用一次。

```python
    def call_tool(self, tool: str, bearer: str) -> dict:
        required_scope = TOOL_SCOPES.get(tool, DEFAULT_TOOL_SCOPE)
        result = self.validate(bearer, required_scope=required_scope)
        if not result["valid"]:
            return {"status": result["status"], "WWW-Authenticate": result["www_authenticate"]}
        return {"status": 200, "body": {"tool": tool, "user": result["claims"]["sub"], "ok": True}}
```

- 所有工具调用都经过同一个 `validate`：讲义"there is no path that reaches a tool without validating first"。
- scope 来自**这次请求的 token**，不去查"用户当前 scope"，避免讲义所说的 TOCTOU（scope upgrade race）。

### 3.10 `Client`：发现、注册、授权

```python
    def discover(self) -> dict:
        meta = self.auth_server.metadata()
        if meta.get("issuer") != self.auth_server.issuer:
            raise ValueError("authorization metadata issuer mismatch")
        if "S256" not in meta["code_challenge_methods_supported"]:
            raise ValueError("authorization server does not advertise S256 PKCE")
        if not (meta.get("client_id_metadata_document_supported") or "registration_endpoint" in meta):
            raise ValueError("authorization server advertises no client enrollment path")
        self.expected_issuer = meta["issuer"]
        self.require_response_issuer = bool(meta.get("authorization_response_iss_parameter_supported"))
        return meta
```

- 记录 `expected_issuer`，并根据 AS 是否宣称支持 `iss` 参数决定"缺 `iss` 是否拒绝"。
- ⚠️ `meta["issuer"] != self.auth_server.issuer` 比较的是同一个对象的两个属性，几乎恒为真；真实客户端应比较"元数据里的 issuer"与"构造 well-known URL 时用的 issuer"。`meta["code_challenge_methods_supported"]` 用 `[]` 取值，字段缺失时会抛 `KeyError` 而不是讲义所说的"字段缺失即拒绝"的清晰错误（效果上也是拒绝）。讲义清单里的 `grant_types_supported`、`response_types_supported` 检查没有实现。

```python
    def authorize(self, scopes: set[str], resource: str, user: str) -> str:
        issuer = self.auth_server.issuer
        client_id = self.client_ids_by_issuer.get(issuer)
        if client_id is None:
            raise ValueError("client must enroll separately with this issuer")
        ...
        verifier = secrets.token_urlsafe(32)
        challenge = b64url(hashlib.sha256(verifier.encode()).digest())
        authorization_response = self.auth_server.begin_authorization(...)
        self.validate_authorization_response_issuer(authorization_response.get("iss"))
        token = self.auth_server.redeem_code(..., code_verifier=verifier, resource=resource)
        self.access_tokens_by_issuer_resource[(issuer, resource)] = token
        return token
```

- `client_ids_by_issuer` 查不到就拒绝：换了 AS 必须重新注册（测试 `test_credentials_are_not_reused_across_issuers`）。
- `token_urlsafe(32)` 生成 43 字符的 verifier（32 字节熵），符合 RFC 7636 的 43–128 字符要求。
- **`iss` 校验发生在兑换之前**——顺序就是防线本身。
- token 按 `(issuer, resource)` 存入 `access_tokens_by_issuer_resource`，元组作为字典键。
- `use_authorization_server` 只换 AS、清空 `expected_issuer`，**不复制**任何 `client_id` 或 token。注意：CIMD 的 `client_id` 就是那个 URL，换 issuer 后再注册得到的字符串完全相同（测试里 `first_id == second_id`）；隔离的是"每个 issuer 各自的注册记录"，而不是 ID 字符串。

### 3.11 `demo`：9 步 + bonus

- step 1：AS 轮换两次 → 两个重叠 key。
- step 2–3：发现 + CIMD 注册（`client_metadata` 里没有 `application_type`，按 native 处理）。
- step 4：PKCE + `resource=https://notes.example.com` 拿 token。
- step 5：RS 首次验证时填充 JWKS 缓存。
- step 6：AS 再轮换，RS 定时 refresh；缓存从 `[k1, k2]` 变成 `[k2, k3]`。
- step 7：旧 token（`kid=k2`）仍通过——重叠窗口。
- step 8：新 token（`kid=k3`）通过。
- step 9：同一 token 打到 `tasks.example.com` → 401 audience mismatch。
- bonus：申请含 `mcp:tools.delete` 的 token 后调用 `notes.delete` 成功（但见 3.7：AS 没有任何把关）。
- `assert` 语句把关键期望写进 demo，任何回归会直接让脚本失败。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| HS256 + 共享密钥 | 只用标准库 | JWKS 公开了对称密钥；生产用 RS256/ES256/EdDSA，JWKS 只放公钥 |
| 三个角色同进程，方法调用代替 HTTP | 可单测、无网络 | 没有 `jwks_uri` GET、没有超时/失败，演示不了依赖故障策略 |
| AS 保留最近 2 个 key | 体现"两 key 重叠"稳态 | 按个数而非时间退役，轮换快于 token 寿命时旧 token 提前失效；生产按"最长 token 寿命 + 偏差"退役 |
| 未命中 re-fetch 一次 | 处理 key 重叠窗口，且幂等 | 跨请求无冷却，可被放大成对 IdP 的拉取风暴；生产加冷却 / singleflight |
| `iss` 白名单在 refresh 之前 | 不信任的签发者不消耗 JWKS 拉取 | 合理；但 `refresh_jwks` 只认单一 AS，多签发者形同虚设 |
| 授权码操作加锁、一次性、300 秒 TTL、惰性清理 | 防重放与并发重复兑换 | 单进程锁；多副本 AS 需要数据库原子删除（如 `DELETE ... RETURNING`） |
| CIMD 文档由客户端直接递交 | 无需 HTTP 抓取 | 演示不了 SSRF 防护与"文档确实托管在该 URL"的验证 |
| DCR 返回状态码字典，其余抛异常 | DCR 模拟 HTTP 端点 | 错误风格不统一 |
| AS 不校验请求的 scope | 让 step-up 演示简单 | 任何已注册客户端都能要到任意 scope；生产须对照策略与用户同意 |
| `validate` 只 try 住解码 | 代码简洁 | 畸形输入抛出 500；应统一映射为 401 `malformed` |
| `fetched_at` 只存不用 | 展示缓存形状 | 无 TTL、无 stale-on-error 判定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以写 `str \| None`、`tuple[str, str]` 而不受旧版本限制 |
| `@dataclass` | `class AuthorizationServer:` | 自动生成 `__init__`、`__repr__` 等 |
| `field(default_factory=...)` | `keys: list[IdPKey] = field(default_factory=list)` | 可变默认值必须用工厂，否则所有实例共享同一个列表 |
| `field(repr=False, compare=False)` | `_authorization_codes_lock` | 锁不参与打印和相等比较 |
| `@property` | `def resource_metadata(self)` | 像属性一样访问计算值 |
| 关键字专用参数 `*` | `def begin_authorization(self, *, client_id, ...)` | `*` 之后的参数必须按名字传，避免参数顺序搞错 |
| `**kwargs` 透传 | 测试中 `super().begin_authorization(**kwargs)`、`auth.begin_authorization(**request)` | 用字典展开为关键字参数 |
| 类型注解 | `-> tuple[dict, dict, str]`、`dict[tuple[str, str], str]` | 内置泛型写法（3.9+） |
| f-string 与嵌套引号 | `f'error="invalid_token", ... resource_metadata="{rm}"'` | 外层单引号、内层双引号 |
| `-len(s) % 4` | `b64url_decode` | Python 取模结果非负，正好算出补齐长度 |
| `bytes` 与 `str` 转换 | `.encode()`、`.decode()` | 哈希、HMAC 只接受 bytes |
| `hmac.compare_digest` | `jwt_verify`、`redeem_code` | 常数时间比较，防时序攻击 |
| `secrets` 模块 | `token_bytes(32)`、`token_urlsafe(24)`、`token_hex(4)` | 密码学安全随机数，不能用 `random` |
| 生成器 + `next(..., None)` | `next((k for k in cache["keys"] if k["kid"] == ...), None)` | 找第一个满足条件的元素，找不到返回默认值 |
| 条件表达式 | `... if cache else None`、`"" if parsed.path in {"", "/"} else parsed.path` | 一行 if/else |
| 集合字面量与成员测试 | `{"native", "web"}`、`in {"localhost", "127.0.0.1", "::1"}` | O(1) 查找 |
| `any` / `all` + 生成器 | `any(parsed_absolute_redirect_uri(uri) is None for uri in redirect_uris)` | 短路判断 |
| 嵌套函数 / 闭包 | `validate` 里的 `def challenge(...)` | 捕获外层变量 `rm` |
| `with` 锁 | `with self._authorization_codes_lock:` | 进入加锁、退出（含异常）自动释放 |
| `try/except ValueError` | `parsed.port` 访问 | 把解析失败转成 `None` |
| `_ = expr` | `_ = parsed.port` | 只为副作用（触发校验）求值，丢弃结果 |
| `raise ValueError(...)` | 多处 | 用异常表达拒绝 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不运行 demo |
| 元组作字典键 | `access_tokens_by_issuer_resource[(issuer, resource)]` | 元组可哈希 |

---

## 6. 运行结果解读

实际运行 `python3 code/main.py`（Python 3，耗时不到 0.1 秒；`kid` 含时间戳与随机数，每次不同）：

```text
--- step 1: stand up the authorization server (two overlapping keys) ---
  issuer=https://auth.example.com, keys=['k_1791823956_7e23', 'k_1791823956_9915']

--- step 2: client discovers the authorization server (RFC 8414) ---
  issuer=https://auth.example.com, S256 PKCE supported
  CIMD supported=True

--- step 3: client enrolls through CIMD without DCR ---
  client_id metadata URL: https://client.example.com/oauth/client.json
  credential cache issuer keys: ['https://auth.example.com']

--- step 4: client runs PKCE authorization flow with resource indicator ---
  bearer issued (kid=k_1791823956_9915, aud=https://notes.example.com)

--- step 5: MCP server validates the request, JWKS cache primed on first use ---
  server response: {'status': 200, 'body': {'tool': 'notes.list', 'user': 'alice@example.com', 'ok': True}}

--- step 6: IdP rotates a key, scheduled refresh re-pulls the JWKS ---
  cached kids before refresh: ['k_1791823956_7e23', 'k_1791823956_9915']
  cached kids after refresh:  ['k_1791823956_9915', 'k_1791823956_2fad']

--- step 7: existing token still validates (overlap window) ---
  server response: {'status': 200, ...}

--- step 8: new token signed with new key validates against refreshed JWKS ---
  fresh token kid: k_1791823956_2fad
  server response: {'status': 200, 'body': {'tool': 'notes.read', ...}}

--- step 9: audience-replay attempt against a different MCP resource ---
  other server response: {'status': 401, 'WWW-Authenticate': 'Bearer error="invalid_token", error_description="audience mismatch", resource_metadata="https://tasks.example.com/.well-known/oauth-protected-resource"'}

--- bonus: step-up flow for a higher-privilege scope ---
  server response: {'status': 200, 'body': {'tool': 'notes.delete', 'user': 'alice@example.com', 'ok': True}}
```

逐项解读：

- **step 1**：两个 `kid` 时间戳相同（同一秒内轮换），后缀随机。
- **step 3**：`client_id` 就是 CIMD 文档 URL；凭据缓存只有一个 issuer 键。
- **step 4**：token 用当前 key（第二个）签名，`aud` 被固定为 notes 资源。
- **step 6**：轮换后最老的 `7e23` 被挤出，`9915` 保留，新增 `2fad`——缓存始终是两个重叠 key。
- **step 7**：旧 token 的 `kid=9915` 仍在缓存中，所以通过。再轮换一次就不行了（测验 Q10 实测返回 `unknown kid`）。
- **step 9**：`resource_metadata` 指向 **tasks** 服务器自己的 PRM 文档 URL，客户端据此重新发现。
- **bonus**：直接拿到了 delete 权限——AS 没有对 scope 做任何把关；真正的 step-up 应该先收到 403 `insufficient_scope, scope="mcp:tools.delete"`（测试 `test_scope_is_checked_on_each_tool_call` 展示了这个 403），再走一次需要用户同意/更强认证的授权。
- 讲义说测试"reports eighteen passing checks"，实际是 **30 个**测试全部通过（见第 9 节）——讲义数字已过时。

---

## 7. 动手改一改

1. **（入门）** 在 demo 末尾再轮换两次并 refresh，用最早的 `bearer` 调用 `notes.list`，观察 `unknown kid`；然后把 `rotate_key` 改成"按时间退役"：只删除 `issued_at` 早于 `now - 3600 - 60` 的非当前 key。
2. **（练习 2）** 按测验 Q9 改造 `ResourceServer` 支持多签发者：加入 `https://partners.example.com`，确认它签的 token 通过，未列名 IdP 的 token 得到 `iss not allowed`。
3. **（练习 3）** 给 `register_client` 加按源 IP 的 token bucket（字典 `{ip: (tokens, last_ts)}`），超出时返回 429。
4. **（练习 6 进阶）** 给 cache-miss 回退加 30 秒冷却（测验 Q12），写测试：连续 100 个随机 `kid` token 只触发 1 次 re-fetch，AS key 数不变；再故意改成 `rotate_key()`，观察合法 token 也被挤出 JWKS 后失败。
5. **（健壮性）** 按测验 Q11 让 `validate` 对任何畸形输入都返回 401 `malformed`，并补上 `nbf` 与 60 秒时钟偏差的处理。
6. **（真实签名）** 安装 `cryptography` 后把 HS256 换成 Ed25519：AS 只在 JWKS 中发布 `{"kty": "OKP", "crv": "Ed25519", "x": ...}` 公钥，RS 用公钥验签；确认 `validate` 的检查链无需改动。

---

## 8. 常见坑

- **把 refresh 写成 rotate**：RS 不持有 AS 私钥；cache-miss 走 rotate 既修不好问题，又是 key 创建 DoS。
- **以为"每请求最多一次 refresh"就安全**：没有冷却时，攻击者仍能让 RS 对 IdP 疯狂拉取。
- **按个数保留 key**：轮换间隔短于 token 寿命时，合法 token 会在过期前就 `unknown kid`。
- **公开对称密钥**：HS256 的 JWKS 里放 `k` 只在教学中成立；任何能读 JWKS 的人都能签 token。
- **`aud` 缺失当通配符**：本代码 `None != resource` 正确拒绝；自己实现时别写成 `if claims.get("aud") and ...`。
- **只 try 住解码**：签名 base64 错误、claims 类型错误会变成 500。
- **以为 `allowed_issuers` 加一项就支持多 IdP**：还要有该 issuer 对应的 JWKS 来源。
- **CIMD 的 `client_id` 不变 ≠ 凭据复用**：换 issuer 后必须重新走该 issuer 的注册，测试里两个 ID 字符串相同是 CIMD 的特性。
- **把 `resource_metadata` 写成资源 URL**：它必须是 PRM 文档的 URL；也不存在 `resource=` 参数。
- **把 web 客户端的回调写成 http**：CIMD、DCR、预注册三条路径都会拒绝。

---

## 9. 测试在验证什么

运行方式（在小节目录下）：

```bash
python3 -m unittest discover -s code/tests -v
```

实际运行结果：`Ran 30 tests in 0.007s` / `OK`（讲义写的是 18 个，已过时）。测试文件开头用 `sys.path.insert(0, ...parents[1])` 把 `code/` 加入导入路径，再 `from main import ...`；两个辅助函数 `ready_authorization_server`（建 AS 并轮换一次）和 `cimd_client`（构造带合法 CIMD 文档的客户端）供各测试复用。

| 分组 | 测试 | 验证的性质 |
|------|------|-----------|
| CIMD 身份 | `test_cimd_uses_document_url_as_client_id` | `client_id` 就是文档 URL，记录 `enrollment="cimd"` |
| | `test_cimd_rejects_document_identity_mismatch` | 文档内 `client_id` ≠ URL → "must equal" |
| | `test_cimd_requires_a_document_path` | 无路径的 URL → "with a path" |
| | `test_cimd_requires_client_name_and_redirect_uris` | 空白 `client_name`；`[]`、`[""]`、字符串（非列表）三种 `redirect_uris` 都被拒 |
| | `test_cimd_does_not_require_dcr_application_type` | CIMD 不强制 `application_type`，记录为 `None` |
| DCR | `test_dcr_requires_application_type` | 缺 `application_type` → 400 |
| | `test_web_dcr_rejects_insecure_redirect` | web + http 回调 → `invalid_redirect_uri` |
| | `test_dcr_fallback_records_native_application_type` | `Client.register()` 声明 `native`，并按 issuer 存 `client_id` |
| 回调策略 | `test_web_cimd_rejects_insecure_redirect` | CIMD web + http 被拒 |
| | `test_web_redirects_require_absolute_https_host_without_fragment` | `https:///callback`、带 fragment，在 CIMD 与 DCR 下都被拒 |
| | `test_web_redirects_reject_malformed_and_out_of_range_ports` | 非数字端口、65536 端口被拒（依赖 `_ = parsed.port`） |
| | `test_every_cimd_and_dcr_redirect_is_absolute_and_fragment_free` | 相对路径、带 fragment 的 URI 在 `None/native/web` 三种类型下全被拒 |
| | `test_native_redirect_policy_rejects_remote_cleartext_http` | native 不允许非 loopback 的 http |
| | `test_native_redirect_policy_rejects_registered_and_generic_schemes` | `javascript:`、`data:`、`ftp://`、`urn:...:oob` 在 CIMD（含省略类型）、DCR、预注册四条路径下全被拒，且预注册失败不留下记录 |
| | `test_native_redirect_policy_accepts_domain_based_private_use_scheme` | `com.example.app:/oauth2redirect` 在三条路径下都被接受 |
| 预注册 | `test_pre_registered_client_is_used_before_cimd_or_dcr` | 优先使用预注册 ID |
| | `test_pre_registered_redirects_follow_runtime_registration_policy` | 预注册不能绕过 native/web 回调策略 |
| 发现 | `test_protected_resource_metadata_inserts_well_known_before_resource_path` | PRM URL 规则（有路径 / 无路径） |
| mix-up | `test_authorization_response_issuer_mismatch_is_rejected` | 返回的 `iss` 不同 → "issuer mismatch" |
| | `test_advertised_response_issuer_cannot_be_omitted` | AS 宣称支持却缺 `iss` → "omitted" |
| | `test_authorize_validates_the_issuer_from_the_actual_response` | 用子类 `MixupAuthorizationServer` 篡改**真实响应**的 `iss`，`authorize()` 在兑换前就失败 |
| PKCE 与授权码 | `test_pkce_verifier_is_checked_before_code_redemption` | 错误 verifier 被拒，且授权码**保留** |
| | `test_authorization_requires_s256_challenge_method` | `plain` 被拒 |
| | `test_authorization_code_expires_and_is_removed` | 用 `patch("main.time.time")` 冻结时间：1000 发起、1301 兑换 → "expired"，且码被删除 |
| | `test_authorization_code_redemption_is_atomic` | 两线程经 `Barrier` 同时兑换：恰好 1 成功、1 失败，错误信息是 "invalid or already used" |
| | `test_new_authorization_prunes_abandoned_expired_codes` | 新授权会清理已过期的码，未过期的保留 |
| | `test_authorization_code_is_single_use_and_token_cache_is_resource_bound` | 兑换后授权码表为空；token 缓存有两个 `(issuer, resource)` 键 |
| 签发者隔离 | `test_credentials_are_not_reused_across_issuers` | 换 AS 后未注册就授权 → "enroll separately"；再注册后两个 issuer 各有记录 |
| RS 校验 | `test_resource_server_rejects_cross_resource_token` | 跨资源 → 401 audience mismatch |
| | `test_scope_is_checked_on_each_tool_call` | 缺 delete scope → 403，头里含 `mcp:tools.delete` |

测试没有覆盖的点（正好对应第 3 节发现的问题，可作为练习补上）：多签发者 JWKS、key 两次轮换后的旧 token、畸形 token 不抛异常、随机 `kid` 的 refresh 次数与冷却、AS 对请求 scope 的把关。
