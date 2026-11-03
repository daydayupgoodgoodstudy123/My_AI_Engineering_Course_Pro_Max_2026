# 测验 · 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens（MCP Auth in Production: Issuer-Bound Enrollment and Tokens）

> **阶段 13 · 工具与协议 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/tests/test_main.py](../code/tests/test_main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个角色各管各的检查 | 授权服务器（AS）签发 token、轮换签名密钥；资源服务器（RS，即 MCP server）缓存 JWKS 并逐请求校验；客户端负责发现、注册（enrollment）与 RFC 9207 `iss` 校验 |
| 2 | 两级发现链 | RFC 9728 protected-resource metadata 指出信任哪些 `authorization_servers` → RFC 8414 `/.well-known/oauth-authorization-server` 给出全部端点；带路径的资源要把 well-known 段**插在路径之前** |
| 3 | 部署前的硬门槛 | `code_challenge_methods_supported` 必须含 `S256`（缺失即拒绝，PKCE 没有降级模式）；至少有一条注册路径；`response_types_supported` 为 `["code"]` |
| 4 | 注册路径的优先级 | 已有的签发者级 pre-registration → CIMD（Client ID Metadata Document，推荐）→ RFC 7591 DCR（2026-07-28 起已弃用，仅作兼容，且必须声明正确的 `application_type`） |
| 5 | CIMD 的约束 | `client_id` 是带路径的绝对 HTTPS URL，且必须等于文档自身 URL；必填 `client_id`、`client_name`、非空 `redirect_uris`；`application_type` 可选；AS 需防 SSRF 与 localhost 冒充 |
| 6 | 凭据按签发者隔离 | 注册信息按 issuer 存，access token 按 `(issuer, resource)` 存；issuer 变了就重新注册，resource 不同就单独申请受众绑定的 token |
| 7 | Rotate 与 Refresh 是两个动词 | rotate 是 AS 生成/退役签名密钥；refresh 是 RS 重新拉取已发布的 JWKS。缓存未命中的回退只能是**一次幂等的 re-fetch**，绝不能是 rotate-and-mint |
| 8 | 逐请求校验顺序 | 解码 → `iss` 白名单 → 按 `kid` 取 key（未命中则 refresh 一次）→ 验签 → `aud` 等于本服务器 canonical resource → `exp` → 所需 scope；失败返回带 `resource_metadata` 的 `WWW-Authenticate` |
| 9 | 三种攻击三种防线 | audience replay 靠 RS 校验 `aud`（spec 称 access-token privilege restriction）；mix-up 靠客户端校验 RFC 9207 `iss`；confused deputy 靠逐客户端同意 + 禁止 token passthrough |
| 10 | 运维契约 | opaque token 走 RFC 7662 introspection；撤销是"新鲜度契约"（最大撤销延迟）；依赖故障要有预先声明的策略，introspection 不可用时 fail closed |

### 核心技能（能动手做到）

- [ ] 给定任意 MCP 资源 URL，写出它的 protected-resource metadata URL，并说出 401/403 的 `WWW-Authenticate` 应带哪些参数
- [ ] 读懂 `ResourceServer.validate` 的每一步，说出每个分支返回的状态码与 `error_description`
- [ ] 解释为什么 JWKS 缓存未命中时只能 re-fetch，并能测出"随机 `kid` 喷射"会触发多少次 refresh、AS 的 key 数是否增长
- [ ] 根据 key 轮换间隔、保留的 key 个数和 token 有效期，算出旧 token 最坏情况下还能用多久
- [ ] 按 CIMD / pre-registration / DCR 的规则判断一个注册请求（含 `redirect_uris` 与 `application_type`）会被接受还是拒绝
- [ ] 跑通 30 个单元测试，并能说出 PKCE、授权码一次性、按签发者隔离凭据分别由哪个测试保护
- [ ] 为 opaque token 设计 introspection 缓存键与撤销窗口，为每种依赖故障写出声明式处置

---

## 二、基础自测（选择题）

**Q1.** 某 MCP server 的 canonical resource 是 `https://mcp.example.com/team/server`。按本节代码 `protected_resource_metadata_url`（也是讲义的规则），它的 protected-resource metadata URL 是：

- A. `https://mcp.example.com/.well-known/oauth-protected-resource/team/server`
- B. `https://mcp.example.com/team/server/.well-known/oauth-protected-resource`
- C. `https://mcp.example.com/.well-known/oauth-authorization-server/team/server`
- D. `https://mcp.example.com/.well-known/oauth-protected-resource`

**Q2.** 资源服务器收到一个 `kid` 不在 JWKS 缓存中的 token。正确的处理是：

- A. 调用 AS 的 `rotate_key()` 生成新 key，再用新 key 验签
- B. 直接拒绝，绝不访问网络
- C. 跳过签名校验，只检查 `aud` 和 `exp`
- D. 同步 re-fetch 一次已发布的 JWKS，再查一次；仍找不到就以 `unknown kid` 返回 401

**Q3.** Server A（`notes.example.com`）被攻破，攻击者拿 A 的用户 token 去调用 Server B（`tasks.example.com`），两者信任同一个 AS。本节代码中 Server B 的返回是：

- A. 403，`error="insufficient_scope"`
- B. 401，`error="invalid_token", error_description="audience mismatch"`，并带 `resource_metadata="https://tasks.example.com/.well-known/oauth-protected-resource"`
- C. 401，`error_description="iss not allowed"`
- D. 200，因为签名和签发者都合法

**Q4.** 一个只含 `mcp:tools.invoke` 的 token 调用 `notes.delete`（需要 `mcp:tools.delete`）。代码返回：

- A. 401，`error="invalid_token"`
- B. 200，因为 `notes.delete` 不在 `scopes_supported` 中，默认放行
- C. 403，`WWW-Authenticate: Bearer error="insufficient_scope", scope="mcp:tools.delete", resource_metadata="..."`
- D. 400，`invalid_request`

**Q5.** `Client.enroll()` 在 AS 同时支持 CIMD 和 DCR、且客户端配置了该 issuer 的 pre-registered `client_id` 时，会选择哪条路径？

- A. CIMD，因为它是 2026-07-28 推荐的默认方式
- B. DCR，因为它能拿到 `registration_access_token`
- C. pre-registered `client_id`（前提是 AS 确实认识它）；若该 issuer 已在 `client_ids_by_issuer` 里，则直接复用已有记录
- D. 三条路径都走一遍，取最后一个结果

**Q6.** 关于 mix-up attack，下列说法正确的是：

- A. 它发生在任何 token 存在之前，防线在客户端：重定向前记录期望的 issuer，收到授权响应后把 RFC 9207 的 `iss` 与之做精确字符串比较
- B. PKCE 足以防御 mix-up，因为 `code_verifier` 只有客户端知道
- C. 资源服务器校验 `aud` 就能防御 mix-up
- D. 只要 AS 元数据里有 `jwks_uri` 就不会发生 mix-up

**Q7.** 下列 CIMD 文档，哪一个会被本节 `register_cimd` **接受**？（文档 URL 均为 `https://app.example.com/oauth/client.json`，未列出的字段视为缺失）

- A. `client_id` 为 `https://app.example.com`，其余字段齐全
- B. `client_id` 正确、`client_name` 为 `"   "`、`redirect_uris` 为 `["http://127.0.0.1:7333/callback"]`
- C. `client_id` 正确、`client_name` 正确、`application_type: "web"`、`redirect_uris: ["http://app.example.com/callback"]`
- D. `client_id` 正确、`client_name` 正确、不写 `application_type`、`redirect_uris: ["com.example.app:/oauth2redirect"]`

**Q8.** 部署使用 opaque token，资源服务器调用 RFC 7662 introspection 端点时网络超时。讲义要求的安全行为是：

- A. 视为 `active: true`，避免误伤用户
- B. 对受保护调用 fail closed，并把它归类为运维错误（走健康检查与重试策略），而不是授权拒绝
- C. 退回到解码 token 自身内容来判断
- D. 无限延长上一次 introspection 结果的缓存

---

## 三、动手 / 代码题

**Q9.** 讲义练习 2 要求"给 `authorization_servers` 加一个新 IdP，并确认验证器接受它签发的 token"。直接这样改：

```python
partner = AuthorizationServer(issuer="https://partners.example.com"); partner.rotate_key()
rs = ResourceServer(resource=MCP_RESOURCE, auth_server=auth,
                    allowed_issuers=[auth.issuer, partner.issuer])
rs.validate(partner_token)   # partner_token 由 partner 正常签发，aud 正确
```

相关源码：

```python
    def refresh_jwks(self) -> dict:
        keys = self.auth_server.jwks()["keys"]
        self.jwks_cache[self.auth_server.issuer] = {"keys": keys, "fetched_at": time.time()}
        ...
    def validate(self, token, required_scope=None):
        ...
        cache = self.jwks_cache.get(iss)
        if cache is None:
            self.refresh_jwks()
            cache = self.jwks_cache.get(iss)
```

1. 实际返回什么？为什么？
2. 给出一个最小改法，让 `ResourceServer` 真正支持多个签发者。

**Q10.** `AuthorizationServer.rotate_key()` 只保留最近 **2** 个 key，`issue_token` 的有效期是 **3600 秒**。

1. 假设 AS 每 15 分钟轮换一次。一个 token 在最坏情况下签发后多久就会因为 `unknown kid` 被拒？最好情况呢？
2. 若想保证任何 token 在 60 分钟有效期内始终可验，按"保留个数"的思路至少要保留几个 key？更合理的工程做法是什么？
3. 用代码验证：签发 token → 轮换一次并 refresh → 再轮换一次并 refresh，第二次之后旧 token 的返回是什么？

**Q11.** `validate` 只用 `try` 包住了 `jwt_decode`。下面三个"格式坏掉"的 token（前两段都是合法的 base64url JSON，签名 key 也存在）分别会发生什么？请改写 `validate` 的开头，让所有格式问题都统一返回 401 `malformed`。

- (a) payload 是 JSON 数组 `[]`
- (b) 签名段只有一个字符 `a`
- (c) 由合法 key 签名、但 `exp` 是字符串 `"soon"`

**Q12.** 讲义练习 6："发送带随机 `kid` 的 token，确认 `refresh_jwks` 最多运行一次，AS 的 key 数不增长。"

1. 连续发送 5 个各带不同随机 `kid` 的 token，`refresh_jwks` 一共被调用几次？AS 的 key 数是多少？"最多一次"说的是什么范围？
2. 为 `refresh_jwks` 的回退路径加一个冷却（例如 30 秒内最多 re-fetch 一次），写出代码。
3. 如果把回退改成 `self.auth_server.rotate_key()`，会有哪两个后果？

---

## 四、面试高频题

**Q13.**（基础必考）一个 MCP 资源服务器在把请求交给 tool handler 之前，必须对 bearer token 做哪些检查？401 和 403 分别在什么情况下返回，`WWW-Authenticate` 要带什么？

**Q14.**（原理深挖）audience replay、mix-up attack、confused deputy 三者有什么区别？各自的防线在哪个角色上？为什么 PKCE 防不住 mix-up？

**Q15.**（工程实践）设计一个生产级 JWKS 缓存：刷新周期、缓存未命中策略、key 轮换重叠、刷新失败时怎么办？要防哪些 DoS？

**Q16.**（场景设计）你的 IdP 签发的是 opaque token，且法务要求"用户注销后 60 秒内所有副本都必须拒绝该 token"。请设计 introspection 缓存与撤销策略，并说明如何验证这条承诺。

**Q17.**（追问型）MCP 2026-07-28 为什么把 DCR 降为弃用、改推 CIMD？CIMD 自身有哪些安全风险？什么时候仍然要用 pre-registration 或 DCR？

---

## 五、参考答案与解析

### Q1 — 答案：A

`protected_resource_metadata_url` 取出路径 `/team/server`，拼成 `scheme://netloc/.well-known/oauth-protected-resource` + 路径。实际运行输出就是 `https://mcp.example.com/.well-known/oauth-protected-resource/team/server`（测试 `test_protected_resource_metadata_inserts_well_known_before_resource_path` 也锁定了它）。讲义："Appending `/.well-known/...` after the resource path is incorrect"，所以 B 错；C 是 AS 元数据（RFC 8414）的 well-known 名，不是 RS 的；D 丢掉了路径，同一 origin 下多个 MCP server 会撞在一起——只有路径为空或 `/` 时才是 D。

### Q2 — 答案：D

`validate` 中：缓存里找不到匹配 `kid` → 调一次 `refresh_jwks()` → 再找；仍为 `None` 就返回 401 `unknown kid`。A 是讲义点名的"Rotate-as-fall-back"bug：新铸的 key 的 `kid` 依然不等于 token 的 `kid`，而且攻击者可以用随机 `kid` 逼 AS 无限造 key；更根本的是 RS 根本不持有 AS 的私钥，不能 rotate。B 会让"签名 key 比缓存新"的合法 token 在下次定时刷新前全部失败（key 重叠窗口问题）。C 等于放弃签名，任何人都能伪造。

### Q3 — 答案：B

验证顺序：`iss` 在白名单内（同一个 AS，通过）→ `kid` 找得到 → 签名正确 → `aud` 是 `https://notes.example.com`，不等于 `https://tasks.example.com` → 401。实际运行 step 9 的输出：

```text
other server response: {'status': 401, 'WWW-Authenticate': 'Bearer error="invalid_token", error_description="audience mismatch", resource_metadata="https://tasks.example.com/.well-known/oauth-protected-resource"'}
```

注意 `resource_metadata` 指向的是 **Server B 自己的** PRM 文档 URL（不是裸资源 URL），让客户端去重新发现。A 是 scope 不足；C 只在签发者不在白名单时出现；D 恰恰是不校验 `aud` 时会发生的事，讲义称其为"最常见的生产错误"。

### Q4 — 答案：C

`TOOL_SCOPES["notes.delete"] = "mcp:tools.delete"`，token 的 `scope` 只有 `mcp:tools.invoke`，走到最后一步返回 `challenge(403, 'error="insufficient_scope", scope="mcp:tools.delete", resource_metadata="..."')`。测试 `test_scope_is_checked_on_each_tool_call` 断言了 403 且头里包含 `mcp:tools.delete`。A 的 401 用于 token 本身无效；B 混淆了 AS 的 `scopes_supported`（AS 对外宣称支持的 scope）与 RS 的工具授权——RS 不看那个列表；D 不是本节的返回码。`scope="..."` 参数就是客户端发起 step-up 授权时要申请的 scope。

### Q5 — 答案：C

`enroll()` 的顺序是：①该 issuer 已在 `client_ids_by_issuer` → 直接返回；②有 `pre_registered_client_ids_by_issuer[issuer]` 且 AS 的 `clients` 里有它 → 使用；③AS 宣称 `client_id_metadata_document_supported` → CIMD；④否则 DCR。讲义："If the authorization server operator has already provisioned a client identifier, use that issuer-scoped registration before trying automatic enrollment. Otherwise prefer CIMD." 测试 `test_pre_registered_client_is_used_before_cimd_or_dcr` 验证了这一点。A 忽略了 pre-registration 优先；B 把已弃用的 DCR 当首选；D 不存在。

### Q6 — 答案：A

讲义："The client (not the server) defends against mix-up attacks"。攻击发生在换取 token 之前：恶意 AS 让客户端把诚实 AS 的授权码送到攻击者的 token 端点。代码里 `Client.discover()` 记下 `expected_issuer`，`authorize()` 在 `redeem_code` 之前调用 `validate_authorization_response_issuer(resp.get("iss"))`；AS 宣称支持 `iss` 参数但响应缺失时也拒绝。B 错：客户端会把 `code_verifier` 交给它被引导去的任何 token 端点，PKCE 只证明"兑换者 = 发起者"，不证明"兑换地点正确"。C 错：此时还没有 token，`aud` 无从谈起。D 无关。

### Q7 — 答案：D

- A：`client_id` 不等于文档 URL（且 `https://app.example.com` 没有路径），报 "must equal its document URL"。
- B：`client_name` 去掉空白后为空，报 "CIMD requires a non-empty client_name"。
- C：`web` 客户端要求 HTTPS 重定向，`http://app.example.com` 被拒（测试 `test_web_cimd_rejects_insecure_redirect`）。
- D：不写 `application_type` 时代码按 `native` 规则检查重定向；`com.example.app` 是"基于域名的私有 scheme"（至少两段、每段字母数字开头结尾），通过 `valid_private_use_scheme`。测试 `test_native_redirect_policy_accepts_domain_based_private_use_scheme` 正是这个用例。注意讲义强调 `application_type` 对 CIMD 是可选的，"Do not copy the DCR requirement for `application_type` into the preferred CIMD path"。

### Q8 — 答案：B

讲义的依赖故障表："Introspection is unavailable → Fail closed for protected calls; do not convert network failure into `active: true`"，并且"Classify failures separately from invalid credentials"：依赖故障是运维错误（有健康和重试策略），坏签名/坏 aud 才是授权拒绝。A 是最危险的错误；C 违反"opaque token 无法解码成可信 claim"的前提；D 违反撤销新鲜度契约——正向缓存必须以 token 过期、签发者缓存指引、撤销 SLO 三者中最早者为界。

### Q9 — 参考答案

1. **实际返回 401 `unknown kid`**（已实际运行验证）。过程：`iss` 在白名单内 → `jwks_cache.get("https://partners.example.com")` 为 `None` → 调 `refresh_jwks()`，但它永远只拉 `self.auth_server`（主 AS）的 JWKS 并写到主 AS 的 issuer 键下 → partner 的缓存仍是 `None` → `matching = None` → 再 refresh 一次（同样无效）→ 401 `unknown kid`。也就是说，`allowed_issuers` 看起来是列表，实际 RS 只能验证一个签发者，错误信息还会误导排查（看起来像 key 轮换问题）。

2. 最小改法：让 RS 持有"issuer → JWKS 来源"的映射，并按 token 的 `iss` 刷新对应的那个：

```python
@dataclass
class ResourceServer:
    resource: str
    jwks_sources: dict[str, AuthorizationServer]   # issuer -> AS（线上是 issuer -> jwks_uri）
    jwks_cache: dict[str, dict] = field(default_factory=dict)

    @property
    def allowed_issuers(self):
        return list(self.jwks_sources)               # 白名单与 JWKS 来源同源，不会不一致

    def refresh_jwks(self, issuer: str) -> dict:
        keys = self.jwks_sources[issuer].jwks()["keys"]
        self.jwks_cache[issuer] = {"keys": keys, "fetched_at": time.time()}
        return {"refreshed": True, "kids": [k["kid"] for k in keys]}
```

`validate` 中两处 `self.refresh_jwks()` 改为 `self.refresh_jwks(iss)`。要点：`jwks_uri` 必须来自**已验证的签发者元数据和部署配置**，不能来自 token 头（讲义："never follow a key URL or algorithm selected only by the token header"）。

### Q10 — 参考答案

1. key K 在第 i 次轮换时成为 current，在第 i+2 次轮换（新增第 i+2 个 key、只保留最后 2 个）时被移出。轮换间隔 R = 15 分钟：
   - 最坏：token 在下次轮换前一刻签发，约 **15 分钟**后被拒；
   - 最好：token 在轮换后立即签发，**30 分钟**后被拒。
   两者都远小于 token 的 60 分钟有效期（已用小脚本模拟验证：保留 2 个 key 时最坏约 15 分钟、最好 30 分钟）。
2. 按"保留个数"推：最坏存活时间 = (N − 1) × R，要求 ≥ 60 分钟 → N − 1 ≥ 4 → **至少保留 5 个 key**（模拟：N = 5 时最坏约 60 分钟）。更合理的做法是**按时间退役**而不是按个数：一个 key 停止签名后，至少再保留"最长 token 有效期 + 时钟偏差"才从 JWKS 中删除；讲义的稳态是"两个 key 重叠"，前提正是轮换间隔不短于 token 寿命。
3. 运行结果：第一次轮换 + refresh 后旧 token 仍返回 200（demo step 7 的"overlap window"）；第二次轮换 + refresh 后返回
   `{'status': 401, 'WWW-Authenticate': 'Bearer error="invalid_token", error_description="unknown kid", ...'}`——此时 token 的 `exp` 还远没到。

### Q11 — 参考答案

实际运行结果（RS 只信任主 AS，签名 key 存在）：

| 输入 | 结果 | 原因 |
|------|------|------|
| (a) payload `[]` | 抛 `AttributeError: 'list' object has no attribute 'get'` | `jwt_decode` 成功，但 `claims.get("iss")` 假定是 dict |
| (b) 签名段 `a` | 抛 `binascii.Error: ... cannot be 1 more than a multiple of 4` | 异常发生在 `jwt_verify` 的 `b64url_decode`，不在 `try` 范围内 |
| (c) `exp: "soon"` | 抛 `TypeError: '<' not supported between instances of 'str' and 'float'` | 比较前没检查类型 |

在 HTTP 服务里这些会变成 500，而不是规范要求的 401 + `WWW-Authenticate`；(b) 甚至不需要任何合法凭据就能触发。改写思路：把"解码 + 形状校验"集中到一处，任何异常都映射为 `malformed`：

```python
def _parse(token: str):
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("parts")
    header = json.loads(b64url_decode(parts[0]))
    claims = json.loads(b64url_decode(parts[1]))
    sig = b64url_decode(parts[2])                 # 提前解码签名，坏 base64 在这里暴露
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise ValueError("shape")
    for name in ("exp", "iat"):
        if name in claims and (not isinstance(claims[name], int) or isinstance(claims[name], bool)):
            raise ValueError(f"{name} type")
    return header, claims, sig

# validate 开头
try:
    header, claims, _sig = _parse(token)
except Exception:
    return challenge(401, f'error="invalid_token", error_description="malformed", resource_metadata="{rm}"')
```

讲义的依赖故障表也写了："Clock source or claim type is invalid → Reject rather than widening skew until the token passes"。

### Q12 — 参考答案

1. 实测：5 个随机 `kid` 的 token → `refresh_jwks` 被调用 **5 次**，AS 的 key 数始终是 **1**，每个都返回 401 `unknown kid`。所以"最多一次"指的是**每个请求**最多一次 re-fetch；它保证了 key 数不增长（无 key 创建 DoS），但并没有限制跨请求的总 fetch 次数——攻击者每发一个请求，RS 就会向 IdP 发一次 JWKS 请求（线上是一次 HTTP GET），可以被放大成对 IdP 的流量攻击。
2. 加冷却（按 issuer 记录上次"因未命中触发"的刷新时间）：

```python
MISS_REFRESH_COOLDOWN = 30.0

@dataclass
class ResourceServer:
    ...
    last_miss_refresh: dict[str, float] = field(default_factory=dict)

    def refresh_on_miss(self, issuer: str) -> bool:
        now = time.time()
        if now - self.last_miss_refresh.get(issuer, 0.0) < MISS_REFRESH_COOLDOWN:
            return False                      # 冷却中：不 fetch，直接按 unknown kid 拒绝
        self.last_miss_refresh[issuer] = now
        self.refresh_jwks()
        return True
```

`validate` 中未命中分支改为 `if self.refresh_on_miss(iss): cache = ...; matching = ...`。代价：真正的新 key 在冷却期内到达时会被误拒最多 30 秒，因此定时刷新要足够频繁，AS 也应**先发布新 key、过一段时间再开始用它签名**。
3. 后果（讲义 "Rotate-as-fall-back"）：①新铸 key 的 `kid` 依然不匹配 token，查找照样失败，修不好任何问题；②攻击者用随机 `kid` 每发一个请求就让 AS 新增一个 key——在本代码里，由于只保留 2 个 key，还会把正在使用的合法 key 挤出 JWKS，导致所有合法用户的 token 立刻 `unknown kid`，DoS 效果更直接。

### Q13 — 参考回答要点

- **入口**：只接受 `Authorization: Bearer ...`；不接受 query string；MCP 2026-07-28 传输无状态，**每个请求**都校验，不能只在"会话开始"时校验。
- **检查项与顺序**（对应 `validate`）：格式解码 → `iss` 在 PRM 的 `authorization_servers` 白名单中 → 按 `kid` 取 key（未命中 re-fetch 一次）→ 验签（算法与 `jwks_uri` 由配置固定，不听 token 头的）→ `aud` 精确等于本服务器 canonical resource（缺失也拒，不当通配符）→ `exp`（以及 `nbf`/`iat` 合理性）→ 当前工具所需 scope。
- **401**：token 无效（格式、签发者、`kid`、签名、受众、过期），`WWW-Authenticate: Bearer error="invalid_token", error_description="...", resource_metadata="<PRM URL>"`。
- **403**：token 有效但 scope 不够，`error="insufficient_scope", scope="<所需 scope>", resource_metadata="..."`，客户端据此 step-up。
- 加分点：`resource_metadata` 是 PRM 文档的 URL，不存在 `resource` 参数；SEP-985 之后该头可选，但 well-known URI 必须可用；用"token 上携带的 scope"判断，不去查"用户当前 scope"，避免 TOCTOU（讲义 Scope upgrade race）。
- 常见误区：先查 scope 再验签；把 `aud` 缺失当作"适用所有服务器"。

### Q14 — 参考回答要点

| 攻击 | 发生时机 | 场景 | 防线（角色） |
|------|---------|------|------------|
| audience replay | token 已签发后 | 发给 A 的 token 被拿去调用 B | RS 校验 `aud`（RFC 8707 + 逐请求校验）；spec 称 access-token privilege restriction |
| mix-up | 兑换授权码之前 | 恶意 AS 诱导客户端把诚实 AS 的 code 送到攻击者的 token 端点 | 客户端：重定向前记录 issuer，校验 RFC 9207 `iss`（精确字符串比较） |
| confused deputy | MCP server 作为 OAuth 代理调用第三方 API 时 | 代理用静态 client ID，未逐客户端取得用户同意就转发 | 逐客户端同意 + 禁止 token passthrough，MCP server 必须为上游单独取 token |

- **PKCE 为什么不够**：PKCE 证明"来兑换的人 = 发起授权的人"，但客户端会把 `code_verifier` 一并交给它被引导去的任何 token 端点；攻击者在自己的端点拿到 code + verifier，就能去诚实 AS 兑换。
- 加分点：讲义特别区分了术语——spec 把 confused deputy 保留给"代理"场景，audience replay 不应叫 confused deputy。

### Q15 — 参考回答要点

- **两个动词分开**：AS rotate，RS 只 refresh。
- **定时刷新**：cron/定时器按固定间隔拉 `jwks_uri`，覆盖 `cache[issuer] = {keys, fetched_at}`（技能文件给的默认 `0 */6 * * *`，高频轮换的 IdP 收紧到 `*/15 * * * *`）。
- **未命中回退**：同步 re-fetch 一次再查，幂等；加按 issuer 的冷却/单飞（singleflight），防止随机 `kid` 喷射把流量放大到 IdP（见 Q12）。
- **重叠窗口**：AS 先发布下一个 key 再退役旧 key；退役以"最长 token 寿命 + 偏差"为界（见 Q10）。
- **刷新失败**：已知 `kid` 且缓存仍在声明的 stale-on-error 窗口内 → 继续服务并上报降级健康状态；未知 `kid` 且唯一一次刷新失败 → 拒绝，绝不接受无法验证的签名。
- **其他**：固定接受的算法（防 `alg` 混淆），`jwks_uri` 来自配置而非 token 头；`fetched_at` 要真正参与过期判断（本节代码只存不用）。
- **必须指出的简化**：本节为只用标准库，用 HS256 并把对称密钥以 `"kty": "oct", "k": ...` 放进 JWKS——实际运行 `auth.jwks()` 可以直接看到 `k` 的值。真实部署中 JWKS 是公开文档，公开对称密钥等于让任何人都能签发 token；生产必须用 RS256/ES256/EdDSA，JWKS 里只放公钥。

### Q16 — 参考回答要点

- **校验路径**：opaque token 不能解码，必须走 RFC 7662 introspection，经认证的后端通道；要求 `active: true`、签发者上下文正确、`aud`/resource 精确匹配本 MCP 资源、未过期、有所需 scope。
- **缓存键**：`(issuer, sha256(token), resource)`——绝不用明文 token 当日志或缓存键；同一 token 字符串对不同 resource 的结果不能复用。
- **正向缓存 TTL** = min(token 过期, 签发者缓存指引, 撤销窗口) → 这里不超过 60 秒；高风险工具（删除、转账）每次都 introspect。
- **负向缓存**要短，避免新签发的 token 被误判为 inactive。
- **故障**：introspection 不可用 → 受保护调用 fail closed；revocation 端点不可用 → 报告"撤销未完成"，不要声称全局撤销成功。
- **验证承诺**：讲义要求"Test that statement through the load balancer, not only against one warm process"——注销后在 60 秒边界通过负载均衡对所有副本发请求，断言全部拒绝。
- 加分点：若改用 JWT，则要靠短 token 寿命 + refresh token 撤销 + 可选的 sub/jti denylist，因为签名过的 JWT 在过期前一直密码学有效。

### Q17 — 参考回答要点

- **DCR 的问题**：AS 要为每个客户端保存状态、铸造 `client_id`；注册端点可被脚本刷爆（`client_id` 命名空间耗尽，需要按源 IP 限流）；`registration_access_token` 被盗可改写 redirect URI；讲义提到有些企业 IdP 还要求 `software_statement`。
- **CIMD 的思路**：把注册从 push 变成 pull——客户端用自己控制的 HTTPS URL 作为 `client_id`，AS 在授权流程中拉取 JSON；信任根在 DNS，AS 不需保存注册状态。
- **CIMD 的风险**：①SSRF：AS 要去抓攻击者提供的 URL，必须禁止访问内网/管理端点；②localhost 冒充：本地攻击者可以声称是合法客户端的元数据 URL 并绑定 `localhost` 回调，AS **必须**在同意页清楚展示重定向主机名，并**应当**对仅 localhost 的重定向给出警告。
- **何时用其他路径**：AS 运营方已经为该 issuer 预置了 `client_id` → 优先 pre-registration；AS 既不支持 CIMD 又无法预注册 → 才用 DCR，并且必须声明正确的 `application_type`（loopback 桌面客户端 `native`，服务端托管 `web` 且只用 HTTPS 回调）。
- 加分点：本节代码中的 CIMD 是"客户端把 URL 和文档一起交给 AS"，并没有真正 fetch，也就演示不了 SSRF 防护——面试时能指出这是模拟简化。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)：本节直接建立在其 OAuth 2.1 状态机、PKCE、资源指示器之上。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关场景下多个 MCP server 共享一个信任网，正是 audience replay 的温床。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：理解"无协议会话，所以每个请求都要校验"。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：MCP 的威胁模型全景。

### 本节被哪些后续内容用到
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../19-a2a-protocol/docs/zh.md)：Agent Card 中声明的 auth scheme 复用同样的 OAuth 模式。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把认证、网关、追踪组装成完整工具生态。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：部署证据与运维门禁。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：密钥轮换与审计日志的通用工程实践。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：scope 与 step-up 在 Agent 权限设计中的对应物。

### 延伸关键词
`RFC 8414` · `RFC 9728` · `RFC 8707 resource indicator` · `RFC 9207 iss` · `RFC 7636 PKCE` · `RFC 7591 DCR` · `CIMD` · `JWKS / kid` · `key rotation overlap` · `RFC 7662 introspection` · `RFC 7009 revocation` · `token passthrough` · `step-up authorization` · `singleflight`
