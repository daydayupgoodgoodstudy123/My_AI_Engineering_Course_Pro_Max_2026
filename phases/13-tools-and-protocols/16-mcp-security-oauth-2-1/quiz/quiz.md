# 测验 · MCP 授权：CIMD、签发者绑定、PKCE 与升级认证（MCP Authorization: CIMD, Issuer Binding, PKCE, and Step-Up）

> **阶段 13 · 工具与协议 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个角色 | MCP client 代表资源所有者发请求；MCP resource server 接收 access token 并提供 MCP 端点；authorization server（AS）认证用户、收集同意、签发 token。可以同一方运营，但标识与校验职责要分开 |
| 2 | 授权只适用于 HTTP | 授权规范针对 HTTP 传输；本地 stdio 服务端在进程/操作系统信任边界内，不要为了"对称"硬加浏览器 OAuth。远程请求每次都在 `Authorization` 头里带 bearer token，绝不放在 URL 里 |
| 3 | 从受保护资源元数据开始 | RFC 9728：`resource`、`authorization_servers`、`scopes_supported`；well-known URL 要保留资源路径：`https://notes.example.com/.well-known/oauth-protected-resource/mcp` |
| 4 | AS 元数据 | RFC 8414 / OIDC discovery：`issuer`、端点、`code_challenge_methods_supported: ["S256"]`、`authorization_response_iss_parameter_supported`、`client_id_metadata_document_supported`；记录**精确**的 issuer 字符串作为存储键 |
| 5 | 注册优先级 | 预注册 > CIMD（Client ID Metadata Document）> DCR（已弃用的兼容路径）> 提示用户提供；不要在 CIMD 安全校验失败后静默降级到 DCR |
| 6 | CIMD 规则 | `client_id` 是带路径的 HTTPS URL，文档内 `client_id` 必须与之完全相等；必填 `client_id`、`client_name`、`redirect_uris`；`application_type` 对 CIMD 不是必填；获取文档是 SSRF 敏感操作 |
| 7 | DCR 的 `application_type` | 桌面/移动/命令行/loopback 用 `native`，远程托管的浏览器应用用 `web` 且只能用远程 HTTPS 重定向；省略时 OIDC 实现可能默认 `web`，导致合法的 loopback 重定向失败 |
| 8 | 签发者绑定 | 签发者铸造的材料按 `issuer` 存，token 按 `(issuer, resource)` 存；issuer 变化时绝不把旧 issuer 的 secret、DCR client id、refresh/access token 发给新 issuer；CIMD URL 是自托管的，可移植 |
| 9 | PKCE + `resource` + `iss` | S256 challenge；授权请求和 token 请求都带同一个 `resource`（RFC 8707）；RFC 9207 的 `iss` 必须与记录值**逐字**比较（不做大小写、尾斜杠、默认端口、百分号编码规范化） |
| 10 | 受众校验与升级认证 | resource server 只接受 `issuer` 与 `audience` 都匹配自己的 token，否则 401；权限不足返回 403 + `WWW-Authenticate: Bearer error="insufficient_scope", scope="..."`，客户端征得同意后用合并的 scope 重新授权，并用**新的 JSON-RPC id** 重试；禁止 token passthrough |

### 核心技能（能动手做到）

- [ ] 由 MCP 资源 URL 推出 RFC 9728 元数据 URL，并解释为什么不能丢掉路径
- [ ] 手写 `pkce_pair`：`token_urlsafe(32)` → SHA-256 → base64url 去填充，说出 verifier 与 challenge 的长度
- [ ] 按"CIMD 优先、DCR 兼容"写出客户端注册逻辑，并为 DCR 正确设置 `application_type`
- [ ] 实现授权码兑换的全部校验：存在、未过期、client_id、redirect_uri、resource、PKCE，以及并发下"恰好一次兑换"
- [ ] 在 resource server 上按"线协议 → token 有效期/签发者/受众 → 工具 scope"的顺序校验，并把 401/403 包装成带原始 id 的 JSON-RPC 错误
- [ ] 正确解析 `WWW-Authenticate` 中的 scope 挑战（可能包含多个空格分隔的 scope），完成一次升级认证

---

## 二、基础自测（选择题）

**Q1.** 授权服务器同时宣告支持 CIMD 和 DCR，客户端与该 issuer **没有**预注册关系。按讲义，客户端应该：

- A. 使用 Client ID Metadata Document，以自己托管的 HTTPS 元数据 URL 作为 `client_id`
- B. 使用 DCR，因为它能为每个 issuer 生成独立的 client id，更安全
- C. 直接弹窗让用户手工输入 client id
- D. 复用之前在另一个 issuer 上通过 DCR 拿到的 client id

**Q2.** MCP 资源是 `https://notes.example.com/mcp`。本节使用的 RFC 9728 受保护资源元数据 URL 是：

- A. `https://notes.example.com/.well-known/oauth-protected-resource`
- B. `https://notes.example.com/mcp/.well-known/oauth-protected-resource`
- C. `https://notes.example.com/.well-known/oauth-protected-resource/mcp`
- D. `https://auth.example.com/.well-known/oauth-authorization-server`

**Q3.** 客户端记录的 issuer 是 `https://auth.example.com`，授权响应里的 `iss` 是 `https://auth.example.com/`（多了尾斜杠）。正确的处理是：

- A. 去掉尾斜杠后比较，相等就继续兑换授权码
- B. 主机名相同，可以接受
- C. 接受，但在日志里记录一个警告
- D. 判定为不匹配：不使用其中的 `code`，也不展示该响应中攻击者可控的错误详情

**Q4.** 一个使用 `http://127.0.0.1:8765/callback` 回调的桌面客户端，在走 DCR 兼容路径时应声明：

- A. `"application_type": "web"`
- B. `"application_type": "native"`
- C. 省略 `application_type`，让服务器用默认值
- D. `"application_type": "desktop"`

**Q5.** 关于 CIMD 文档，下列说法正确的是：

- A. 文档必须包含 `application_type`，否则 AS 应拒绝
- B. `client_id` 可以是 `https://client.example.com`（没有路径）
- C. `client_id` 必须是带路径的 HTTPS URL，且文档内的 `client_id` 与该 URL 完全相等；必填字段是 `client_id`、`client_name`、`redirect_uris`
- D. 可以在文档里放 `client_secret`，方便 AS 做客户端认证

**Q6.** 受保护资源元数据里的 issuer 从 `https://auth-one.example` 变成了 `https://auth-two.example`。下列做法正确的是：

- A. 继续用 auth-one 签发的 refresh token 去 auth-two 换新 token
- B. 把 auth-one 通过 DCR 分配的 client id 发给 auth-two，省去重新注册
- C. 资源没变，所以 auth-one 签发的 access token 可以继续使用
- D. 重新评估是否信任 auth-two；不向它发送任何 auth-one 铸造的凭证或 token；自托管的 CIMD URL 可以继续使用，但新的授权结果和 token 要存到 auth-two 名下

**Q7.** MCP 服务端 `https://notes.example.com/mcp` 收到一个 `issuer` 正确、但 `audience` 为 `https://other.example/mcp` 的 token。本节代码的行为是：

- A. HTTP 401，返回带原始请求 id 的 JSON-RPC 错误（`-32001`），并附 `WWW-Authenticate: Bearer resource_metadata="..."`
- B. 把这个 token 转发给下游的 `other.example`，由它判断
- C. HTTP 403 `insufficient_scope`
- D. HTTP 200，因为 issuer 是可信的

**Q8.** 调用 `notes.delete` 时服务端返回 403，`WWW-Authenticate` 带 `error="insufficient_scope", scope="notes:delete"`。客户端正确的下一步是：

- A. 用同一个 token 和同一个 JSON-RPC id 立即重试
- B. 向用户解释新权限、征得同意，用"已有 scope + `notes:delete`"重新走授权流程，然后用一个**新的** JSON-RPC id 重试
- C. 先检查 `notes:delete` 是否在 `scopes_supported` 中，不在就忽略这个挑战
- D. 以后首次授权就一次性申请所有 scope，避免再遇到 403

---

## 三、动手 / 代码题

**Q9.** `Client.call_with_step_up` 这样解析 scope 挑战：

```python
        if status == 403 and response is not None and response.get("error", {}).get("code") == -32003:
            required = response_headers["WWW-Authenticate"].split('scope="', 1)[1].split('"', 1)[0]
            token = self.authorize(auth, server.resource, set(token.scopes) | {required})
```

1. 如果服务端返回的挑战是 `scope="notes:read notes:delete"`（RFC 6750 中 scope 是空格分隔的列表），会发生什么？写出最终 token 的 scope 集合和最终 HTTP 状态。
2. 写一个更健壮的 `parse_scope_challenge(header) -> set[str]`。
3. 这段代码只做**一次**升级尝试。为什么不应该写成"一直重试直到成功"？

**Q10.** `_validate_application` 对 `web` 客户端的检查是：

```python
        if application_type == "web":
            for parsed in parsed_redirects:
                if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1"}:
                    raise ValueError("web redirect URIs must use remote HTTPS")
```

1. 实测下列重定向 URI 中哪些被**接受**了：`https://[::1]/cb`、`https://localhost./cb`、`https://127.0.0.2/cb`、`http://example.com/cb`？
2. 用 `ipaddress` 模块写一个 `is_loopback_host(hostname)`，修复这个检查。
3. 反过来，`native` 客户端注册 `https://evil.example/cb` 被接受了。这一定是 bug 吗？

**Q11.** 阅读 `demo()` 与 `call_with_step_up`，**不运行代码**回答：依次调用 `notes.list`、`notes.create`、`notes.delete` 之后，

1. 一共发起了几次授权流程（`Client.authorize`）？
2. `client.next_request_id` 的最终值是多少？哪几个 JSON-RPC id 收到了 403？
3. 最终保存在 `tokens_by_issuer_resource[(ISSUER, RESOURCE)]` 中的 token 有哪些 scope？
4. `auth.pending_codes` 里还剩几个授权码？为什么？

**Q12.** 在 `ResourceServer.handle` 上，写出下列调用的 `(HTTP 状态, JSON-RPC 错误码或"无 body", 是否有 WWW-Authenticate)`：

1. `notes.list`，`token=None`
2. 有效 token（只有 `notes:read`），调用不存在的工具 `notes.purge`
3. `token=None`，调用不存在的工具 `notes.purge`
4. 只有 `notes:read` 的 token 以 notification 形式调用 `notes.delete`
5. `server/discover` 用 `http_method="GET"`
6. token 的 `expires_at` 恰好等于当前时间

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述一个 MCP 客户端第一次访问远程 MCP 服务端时的授权流程：从拿到 MCP URL 开始，到第一次 `tools/call` 成功为止。

**Q14.**（原理深挖）PKCE、`resource` 参数（RFC 8707）、`iss` 参数（RFC 9207）分别防的是什么攻击？少了任何一个会怎样？

**Q15.**（原理深挖）为什么 MCP 2026-07-28 优先 CIMD、把 DCR 降为兼容路径？CIMD 带来了什么新风险，AS 侧要怎么防？

**Q16.**（工程实践）你的 MCP 服务端需要调用公司内部的 Jira API。同事建议"直接把客户端发来的 MCP access token 转发给 Jira"。你怎么评价？正确做法是什么？

**Q17.**（追问型）"MCP 已经是无状态协议了，没有会话，那授权状态放在哪里？`clientInfo` 能不能当身份？token 和 `clientCapabilities` 是什么关系？"

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义注册优先级："Use pre-registered client information when the client already has an explicit relationship ... Otherwise prefer Client ID Metadata Documents when the authorization server advertises support. Use DCR only as the deprecated compatibility fallback, then prompt for client information if none of those mechanisms is available." 代码 `Client.enroll` 也是先看 `client_id_metadata_document_supported`，再看 `registration_endpoint`。B 错，DCR 已被弃用；C 是所有机制都不可用时的最后手段；D 违反签发者绑定——DCR client id 是 auth 服务器铸造的，不能跨 issuer 使用。

### Q2 — 答案：C

讲义："Preserve the resource path when constructing the RFC 9728 well-known URL ... Dropping the `/mcp` suffix can select metadata for a different protected resource on the same origin." 代码常量 `RESOURCE_METADATA_URI` 就是 C，测试 `test_protected_resource_metadata_selects_issuer_and_path` 断言了它。A 丢了路径，同一个源上的另一个受保护资源可能有不同的 AS；B 把 well-known 放在路径后面，不符合 RFC 9728 的插入规则；D 是 AS 自己的元数据，应在拿到受保护资源元数据**之后**再获取。

### Q3 — 答案：D

讲义："compare it to the recorded issuer without case folding, trailing-slash changes, default-port removal, or percent-encoding normalization. On mismatch, do not act on the code or even display attacker-controlled error details from that response." 代码 `if response.get("iss") != auth.issuer: raise ValueError("authorization response issuer mismatch")` 是纯字符串比较；实测尾斜杠、大写主机名、缺少 `iss` 三种情况都被拒绝，而且授权码仍留在 AS 的 `pending_codes` 里未被兑换。A、B、C 都在做"规范化后宽松比较"，这正是 mix-up 攻击利用的缝隙。

### Q4 — 答案：B

讲义："Desktop, mobile, command-line, and loopback clients use `native`." 并且 "Omitting the field can default to `web` in an OpenID Connect registration implementation and make a legitimate loopback redirect fail." 代码中 DCR 路径 `require_application_type=True`，缺失或取值不在 `{"native", "web"}` 都会抛 `application_type must be native or web`（测试 `test_dcr_rejects_missing_application_type`）。A 会让 loopback 重定向被 `web` 规则拒绝；C 即讲义警告的情形；D 不是合法取值。

### Q5 — 答案：C

讲义："The `client_id` must be an HTTPS URL with a path, and the value inside the document must equal that URL exactly. The required document fields are `client_id`, `client_name`, and `redirect_uris`. `application_type` appears in this example but is not a CIMD requirement." 代码 `enroll_cimd` 还额外拒绝了 userinfo、fragment、`.`/`..` 路径段、`client_secret*` 认证方式、`client_secret`/私钥字段、含私钥成分（`d`、`p`、`q` 等）的 JWK。A 错（测试 `test_cimd_requires_path_but_not_application_type` 用不含 `application_type` 的文档注册成功）；B 会得到 "CIMD client_id must be an HTTPS URL with a path"；D 错，CIMD 文档是公开托管的，放密钥等于公开密钥。

### Q6 — 答案：D

讲义："If protected-resource discovery changes ... re-evaluate trust. Never send the first issuer's client secret, DCR client id, registration access token, refresh token, or access token to the second." 以及 "A CIMD client id is different because it is a self-hosted HTTPS URL ... The same CIMD URL is portable ... Authorization responses and tokens are still validated and stored under the new issuer." A、B、C 都是把旧 issuer 铸造的东西带给新 issuer。注意 C：即使资源相同，token 的 `issuer` 也不匹配新的配置——本节 resource server 对 `issuer` 不同的 token 返回 401（实测）。

### Q7 — 答案：A

代码：

```python
                if token.issuer != self.issuer or token.audience != self.resource:
                    raise ProtocolError(-32001, "Unauthorized", {"reason": "invalid_token"}, 401, challenge_headers)
```

`challenge_headers` 是 `{"WWW-Authenticate": 'Bearer resource_metadata="https://notes.example.com/.well-known/oauth-protected-resource/mcp"'}`。测试 `test_resource_rejects_other_audience_with_json_rpc_error` 断言 401、`id == 21`、`-32001`、头中含元数据 URL。B 是讲义明令禁止的 token passthrough；C 的 403 用于"token 有效但 scope 不够"；D 忽略了受众校验——讲义："The MCP server must not accept or transit a token meant for another service." 注：`-32001`、`-32003` 是本代码选用的错误码，讲义正文没有规定具体数值。

### Q8 — 答案：B

讲义："The client explains the new permission, obtains consent, performs a new authorization flow with the combined scope set, and retries the MCP request with a new JSON-RPC id." 以及 "Do not assume the challenged scope is a subset of `scopes_supported`. The challenge is authoritative for the current operation." A 错：token 没变，结果必然还是 403，而且 id 应当是新的；C 恰好违背"挑战是权威的"；D 违反最小权限原则（"Start with the scope needed now"）。测试 `test_step_up_requests_only_missing_scope` 证明直接调用 `notes.delete` 时最终 token 只有 `{"notes:read", "notes:delete"}`，没有多余的 `notes:write`。

### Q9 — 参考答案

1. 实测（用一个把挑战改为 `scope="notes:read notes:delete"` 的子类）：`required` 被解析成**一个**字符串 `"notes:read notes:delete"`，新 token 的 scope 是 `{"notes:read", "notes:read notes:delete"}`；resource server 检查 `"notes:delete" in token.scopes` 为假，最终仍是 **403 `-32003`**。即：多 scope 挑战让升级认证失效，而且还向 AS 申请了一个奇怪的"合成 scope"（本节 AS 不校验 scope，照单全发）。
2. 参考实现（已实测：多 scope 解析为 `{"notes:read", "notes:delete"}`，单 scope 解析为 `{"notes:delete"}`）：

```python
import re

def parse_scope_challenge(header: str) -> set[str]:
    match = re.search(r'(?:^|[\s,])scope="([^"]*)"', header)
    return set(match.group(1).split()) if match else set()

# 使用：token = self.authorize(auth, server.resource, set(token.scopes) | parse_scope_challenge(h))
```

   要点：匹配时要求 `scope=` 前面是开头、空白或逗号，避免误匹配 `error="insufficient_scope"` 这类包含 `scope` 字样的参数；值按空白切分成集合。生产中应使用完整的 `WWW-Authenticate` 解析器（参数可能以 token 而非引号字符串出现，可能有多个 challenge）。
3. 只重试一次：如果新 token 仍不够（AS 降级了授权、用户拒绝了部分 scope、服务端策略还要求别的条件），无限重试会造成授权风暴、反复打扰用户，甚至被恶意服务端利用来诱导用户不断授予更多权限。正确做法是失败后把 403 交给上层，向用户说明原因。

### Q10 — 参考答案

1. 实测：`https://[::1]/cb`、`https://localhost./cb`（末尾带点的 FQDN 形式）、`https://127.0.0.2/cb`（整个 `127.0.0.0/8` 都是 loopback）**全部被接受**；只有 `http://example.com/cb` 因为不是 https 被拒绝。黑名单只列了两个字面量，覆盖不全。
2. 参考实现（已实测：上面三个 loopback 形式与 `LOCALHOST`、`app.localhost` 都返回 `True`，`client.example.com` 返回 `False`）：

```python
import ipaddress

def is_loopback_host(hostname: str | None) -> bool:
    if hostname is None:
        return True                      # 没有主机名，按不安全处理
    host = hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False                     # 普通域名

# web 检查改为：
if parsed.scheme != "https" or is_loopback_host(parsed.hostname):
    raise ValueError("web redirect URIs must use remote HTTPS")
```

   `urlparse("https://[::1]/cb").hostname` 返回去掉方括号的 `"::1"`，所以可以直接交给 `ipaddress`。更严格的实现还会拒绝私有地址（`is_private`）、链路本地地址（`is_link_local`）。
3. 不一定。`native` 应用可以使用"claimed HTTPS"重定向（例如移动端的 App Links / Universal Links），所以 `native` 的规则本来就比 `web` 宽松。本节只对 `web` 做了额外限制，`native` 只检查 URI 格式。真正的保护来自：AS 只允许把授权码发回**注册时登记**的重定向 URI（`authorize` 中 `redirect_uri not in client["redirect_uris"]` 即拒绝），兑换时 redirect_uri 必须一致，并且有 PKCE。

### Q11 — 参考答案

已用实际运行验证（最终 token scope `['notes:delete', 'notes:read', 'notes:write']`，`next_request_id == 6`，`pending_codes` 为空）：

| 步骤 | 发生了什么 | JSON-RPC id |
|------|-----------|-------------|
| `notes.list` | 无 token → `authorize({"notes:read"})`（第 1 次）→ 调用成功 | 1（200） |
| `notes.create` | 已有 `{read}` token → 调用得 403 → `authorize({read, write})`（第 2 次）→ 新 id 重试 | 2（403）、3（200） |
| `notes.delete` | 已有 `{read, write}` → 403 → `authorize({read, write, delete})`（第 3 次）→ 重试 | 4（403）、5（200） |

1. 共 **3 次**授权流程（`demo` 里 `client.enroll(auth)` 只做了注册，不算授权流程；之后 `authorize` 发现已注册，不再重复注册，`auth.clients` 中只有 1 个客户端）。
2. `next_request_id` 最终为 **6**；id 2 和 4 收到 403。每次重试都用新 id——讲义："retries the MCP request with a new JSON-RPC id"。
3. `{"notes:read", "notes:write", "notes:delete"}`：每次升级都是"已有 scope ∪ 缺的 scope"。
4. **0 个**：每个授权码都在 `exchange` 成功后被 `pop`，一次性使用。

### Q12 — 参考答案

已逐一实际运行验证：

| 调用 | 结果 | 说明 |
|------|------|------|
| 1. `token=None` | `(401, -32001, 有)` | `data = {"reason": "invalid_token"}`，头为 `Bearer resource_metadata="..."` |
| 2. 有效 token + 未知工具 | `(404, -32602 "Unknown tool", 无)` | `data = {"name": "notes.purge"}` |
| 3. 无 token + 未知工具 | `(401, -32001, 有)` | 先认证再查工具：未认证的调用者无法探测工具是否存在 |
| 4. notification 且 scope 不足 | `(403, 无 body, 有)` | 通知没有 JSON-RPC 响应，但 HTTP 状态与 `WWW-Authenticate` 头照常返回 |
| 5. `GET` | `(405, -32600 "HTTP method not allowed", 无)` | 本节把 405 也包成 JSON-RPC 错误信封（第 14、15 节返回 `(405, None)`） |
| 6. `expires_at == now` | `(200, ...)` | token 检查用 `expires_at < time.time()`，边界时刻仍有效；而授权码用 `<=`，边界时刻已失效（测试 `test_authorization_code_is_invalid_at_expiry_boundary`）。两处边界语义不一致 |

延伸讨论：

- 第 2 题的未知工具返回 **404 + `-32602`**，而第 14、15 节对未知工具都返回 **400 + `-32602`**；讲义只规定了"未知**方法**返回 404 + `-32601`"。同一课程中的三个模型对"未知工具"的 HTTP 状态不一致，学习时注意区分"方法不存在"与"工具不存在"。
- 第 1 题：RFC 6750 建议对无效 token 在 `WWW-Authenticate` 中带 `error="invalid_token"`；本节的 401 头只有 `resource_metadata`，信息在 JSON-RPC `data.reason` 里。

### Q13 — 参考回答要点

1. 客户端对 MCP URL 发请求，收到 401 + `WWW-Authenticate: Bearer resource_metadata="..."`（或直接按规则构造 RFC 9728 URL，保留 `/mcp` 路径）。
2. 获取受保护资源元数据：`resource`、`authorization_servers`、`scopes_supported`；按本地策略从中选一个**可信**的 issuer（不从错误体里"发现" issuer，不靠主机名猜）。
3. 获取该 AS 的 RFC 8414 / OIDC 元数据，核对 `issuer` 精确相等，要求支持 S256，记录 `authorization_response_iss_parameter_supported` 与 CIMD 支持情况。
4. 注册：预注册 > CIMD > DCR（带 `application_type`）> 提示用户。
5. 生成 PKCE（高熵 verifier、S256 challenge），发授权请求：`client_id`、`redirect_uri`、最小 `scope`、`code_challenge`、`resource`。
6. 收到 `code` 与 `iss`：先**逐字**校验 `iss`，再使用 `code`。
7. 兑换：`code` + `code_verifier` + 相同的 `redirect_uri` + 相同的 `resource`；得到 token，存到 `(issuer, resource)` 名下。
8. 发 MCP 请求：`Authorization: Bearer ...` + 完整的无状态信封（`_meta`、`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name`）。
9. 服务端：校验线协议 → token 有效期、issuer、audience → 工具 scope；不足则 403 + scope 挑战，进入升级认证。
- 加分点：说出 stdio 不走这套流程；`server/discover` 和与用户无关的 `tools/list` 可以在授权前访问。

### Q14 — 参考回答要点

- **PKCE（S256）**：防授权码被截获后被兑换。攻击者拿到 `code`（恶意应用注册了同一个自定义 scheme、日志泄露、Referer 泄露）也没有 `code_verifier`，兑换失败。对没有 client secret 的公共客户端（桌面、移动、CLI）尤为关键。本节 `exchange` 用 `secrets.compare_digest` 比较重算的 challenge。
- **`resource`（RFC 8707）**：把 token 绑定到具体的 MCP 资源，使 token 的 audience 明确。没有它，一个 AS 为多个资源签发的 token 可能是"通用"的，被某个恶意或被攻破的 MCP 服务端拿去调用其他服务（token 重放 / confused deputy）。本节授权码记录了 `resource`，兑换时 `resource mismatch` 即拒绝；token 的 `audience` 就是它。
- **`iss`（RFC 9207）**：防 mix-up 攻击。客户端同时对接多个 AS 时，攻击者控制的 AS 可以诱导客户端把从诚实 AS 拿到的授权码发到攻击者的 token 端点，或反之。逐字校验 `iss` 后，客户端能确定"这个响应来自我发起请求的那个 AS"。
- 三者缺一的后果：没有 PKCE → 截获码可兑换；没有 `resource` → token 可跨服务滥用；没有 `iss` → 多 AS 场景下码与 token 被混淆。
- 加分点：refresh token 同样按 `(issuer, resource)` 存储并启用轮换与重用检测（讲义练习 1）。

### Q15 — 参考回答要点

- **为什么优先 CIMD**：
  - DCR 让每个首次接触的客户端都在 AS 上"铸造"一个新身份，AS 无法知道这个客户端是谁、开放注册容易被滥用（大量垃圾客户端、钓鱼客户端冒用名字）；
  - CIMD 的 `client_id` 是客户端自己托管的 HTTPS URL，域名本身就是一种可验证的身份锚点，AS 可以对域名做信任策略；
  - 同一个 CIMD URL 可以跨 issuer 复用，不必为每个 AS 注册；
  - 讲义："CIMD removes the need to mint a fresh dynamic identifier for every first contact."
- **CIMD 的新风险**：AS 要**主动去获取**客户端提供的 URL——典型的 SSRF 面。还有展示字段（`client_name`、logo）可被用来伪装。
- **AS 侧防护**（讲义原文要点）：解析并校验目标地址，拒绝 loopback、私有、链路本地等地址；重定向后与 DNS 变化后重新检查；限制重定向次数、字节数、时间；要求 JSON；只按经过校验的 HTTP 缓存头缓存；把 `client_name` 等展示字段当作不可信文本。本节代码额外校验 URL 形态（https、有路径、无 userinfo/fragment/点段）和不得包含密钥（`client_secret*`、私钥、含私钥成分的 JWK）。
- 加分点：CIMD 不取消重定向 URI 校验、issuer 策略与用户同意；DCR 仍要放在显式的降级分支里，不能因为 CIMD 校验失败就静默降级。

### Q16 — 参考回答要点

- **评价**：这是讲义明令禁止的 **token passthrough**。理由：
  - 该 token 的 audience 是 MCP 服务端，不是 Jira；如果 Jira 接受了它，说明 Jira 没做受众校验，整个 audience 体系失效；
  - MCP 服务端变成了"拿着用户 token 到处使用"的 confused deputy，任何一处被攻破都会扩大影响面；
  - 审计与限流无法区分"用户直接调用 Jira"与"经 MCP 服务端调用"；
  - scope 语义不同：`notes:delete` 对 Jira 毫无意义。
- **正确做法**：
  - 为 Jira 单独获取一个 audience 为 Jira 的下游 token：服务端自己的 client credentials（以服务身份访问），或显式的 token exchange（RFC 8693，以"代表用户"的委托身份访问）；
  - 下游 token 的 scope 最小化；
  - 记录"哪个 MCP 请求、哪个 principal 导致了哪个下游调用"。
- 讲义："Obtain a separate downstream token with the right audience or use an explicit token-exchange design. Audience validation only works when services refuse tokens minted for someone else."

### Q17 — 参考回答要点

- **授权状态放在哪**：放在**每个请求携带的 bearer token** 里（以及 AS 侧的授权记录），而不是协议会话里。resource server 对每个请求独立校验 token 的签名/有效期、issuer、audience、scope；客户端按 `(issuer, resource)` 保存 token。讲义："These rules complement the stateless core. They do not restore a core handshake or `Mcp-Session-Id`."
- **`clientInfo` 不能当身份**：它是自报数据，只用于诊断；身份来自 token 中经过 AS 认证的 subject 与 client_id。
- **token 与 `clientCapabilities` 的关系**：讲义："The token authorizes the principal. The request metadata negotiates protocol behavior. Neither substitutes for the other." 能力声明决定"服务端可以用什么形状回复"，token 决定"这个人能不能做这件事"。
- **一致的校验顺序**：先线协议（头 body 一致、版本），再 token，再 scope；所有请求错误（包括 401/403）都用带原始 id 的 JSON-RPC 错误信封，恢复信息放 `data`，`WWW-Authenticate` 仍是 HTTP 头。
- 加分点：指出本节模拟器把 `Token` 对象直接传给 `handle`，真实服务端需要从 `Authorization` 头解析 bearer 字符串并验证签名或调用 introspection。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：授权只作用于 HTTP 传输；完整的 HTTP 适配器在这里。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：上一节缺失的"已认证 principal"在本节补上。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：`_meta`、JSON-RPC 错误信封。
- [阶段 00 · 04 APIs 与密钥](../../../00-setup-and-tooling/04-apis-and-keys/docs/zh.md)：API 凭证的基本保管方式。

### 本节被哪些后续内容用到
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关在入口处校验 token 并为后端单独换取凭证（不 passthrough）。
- [阶段 13 · 18 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens](../../18-mcp-auth-production/docs/zh.md)：本节模型的生产化版本。
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../19-a2a-protocol/docs/zh.md)：跨 Agent 调用同样面临受众与委托问题。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：最小权限与升级授权的另一种形态。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：refresh token 与密钥的保管、轮换与审计。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：用户同意与权限升级在 Agent 产品中的体现。

### 延伸关键词
`OAuth 2.1` · `RFC 9728 Protected Resource Metadata` · `RFC 8414` · `RFC 8707 Resource Indicators` · `RFC 9207 iss` · `RFC 7636 PKCE` · `RFC 6750 WWW-Authenticate` · `Client ID Metadata Document` · `Dynamic Client Registration` · `mix-up attack` · `token passthrough` · `confused deputy` · `token exchange (RFC 8693)` · `refresh token rotation` · `SSRF`
