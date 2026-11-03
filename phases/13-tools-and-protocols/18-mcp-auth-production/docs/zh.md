<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-auth-in-production-issuer-bound-enrollment-and-tokens"></a>

# 生产环境中的 MCP 认证：绑定签发者的注册与 Tokens

> 16课是用来建造 OAuth 2.1 国家机器。 MCP 2026-07-28:客户身份元数据文件,仅限兼容性、授权-答复签发者验证、发行人对客户资格、JWKS更新和受众定位而提前动态登记 tokens 每一个无国籍者的要求。
>
> **标注(2026-07-28):** 动态客户注册被折旧, 偏向于客户身份元数据文档。 DCR 仍是一个兼容机制。 当使用时, 客户会声明正确 `application_type`客户验证 RFC 9207 `iss` 使用授权服务器,且不得再使用证书。

**类型:** Build
**语言:** Python (stdlib)
**先修要求:** 阶段13 16(OAuth 2.1 国家机器,第13阶段 17(门道)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 通过RFC 8414元数据发现授权服务器,并核查合同。
- 通过客户端 ID 元数据文档输入, 并分离已折旧的 DCR 作为后退 。
- 验证 RFC 9207 `iss`、由授权服务器签发人进行的关键登记和受资源约束的关键登记 tokens 以发行者加资源为单位。
- 缓存并刷新列表上的 JWKS 键, 这样签名验证才能在键滚转中成功 。
- Pin tokens 单 MCP 使用RFC 8707资源指标,拒绝混淆的副作用再利用。
- Choose JWT 审定或 token 反省,定义取消的新鲜性,当身份依赖性不存在时安全失效。
- 将授权服务器、资源服务器和客户端分开, 每一个用户只执行自己的检查 。
- 根据部署清单审计授权服务器,拒绝不安全的注册或 token reuse.

<a id="the-problem"></a>

## 问题

16课模拟器运行 OAuth 生产有三个操作缺口,只有记忆模拟器看不到。

第一个差距是入学和证书隔离。 MCP 服务器和千个 MCP 2026-07-28修订案倾向于 **客户名元数据文档**:客户使用 HTTPS URL 带有它控制路径作为标识符,授权服务器则拉动元数据。 RFC 7591 动态注册仅保留为折旧兼容路径。当 DCR 不可避免时,请求会声明正确 `application_type`客户商店登记由授权服务器签发和进入 tokens 下方的 `(issuer, resource)` 双对。 更改的发行者意味着新的注册, 而不同的资源则意味着一个单独的受众 token.

第二个差距是关键旋转。 JWT 验证取决于授权服务器的签名密钥, 以 a 格式发布 JSON Web 密钥集( JWKS) 。 授权服务器在计划下旋转这些密钥( 通常为小时, 有时更快) incident response). 一个 MCP 服务器, 只需在启动时一次获取 JWKS 即可验证精细, 直到旋转窗口 。 然后每次请求都失败直到重新启动 。 生产线条作为缓存值, 并进行刷新工作, 在前一个密钥过期之前覆盖缓存, 再加上在缓存错误上回抓一个 token 由比缓存到达日期更新的一个密钥签名 。

第三个差距是受众的束缚,第16课引入了RFC 8707资源指标,在生产中,该指标成为对每一项要求进行硬性索赔检查。 MCP 服务器比较 `token.aud` 与它自己的金刚资源 URL 相对,并拒绝不匹配 HTTP 401. 这是唯一防上游的防线 MCP 服务器( 或持有 token 用于一个服务器)重播 token 与同一信任网格中的另一个服务器对着。

此课程将每个空白映射为表面的混凝土块。 元数据文档是一个 HTTP 端点。 JWKS 缓存刷是一个预定任务, 加上一个密钥值缓存 。 JWT 验证是发送任何工具前资源服务器运行的例行程序。 保持三个角色的分隔, 每个角色只执行它所拥有的检查: 授权服务器发布和旋转密钥, 资源服务器缓存和验证, 客户端发现和注册 。

<a id="scope-production-enforcement-after-lesson-16"></a>

## 范围:生产在教训16之后的执行

[16课: MCP 警卫人员 OAuth 2.1](../../16-mcp-security-oauth-2-1/docs/zh.md) 拥有授权代码国家机器, PKCE, 保护资源发现、资源指标和范围决定。 OAuth 流程。 它从这些合同存在后开始, 询问一个已部署的资源服务器在关键旋转时如何持续执行它们, 且不透明 。token 验证、撤销、抚养能力丧失 rollout, 和 incident response.

生产界限较窄,更便于操作:

- 一个 JWT 路径验证被钉住的发行者、 算法、 签名键、 观众、 时间请求和范围, 同时安全地刷新 JWKS 。
- 隐蔽的...token 路径将使用发行人的经认证的反省终点, 并验证返回的当前状态、 受众或资源、 过期、 主题和范围 。
- 撤销政策规定了证书必须停止工作的速度,以及哪些缓存可以拖延这一事实。
- 失败政策决定了当发现、 JWKS、反省或撤销基础设施无法使用时会发生什么。
- 证据记录中哪些是发布元数据、钥匙集或反省反应, token 索赔、政策版本和拒绝理由导致结果,但没有储存 token.

16课证明了流量。 token 或被拒绝, MCP 请求路径 。

<a id="the-concept"></a>

## 概念

<a id="rfc-8414--oauth-authorization-server-metadata"></a>

### RFC 8414 - OAuth 授权服务器元数据

文档 `/.well-known/oauth-authorization-server` 描述客户需要的一切:

```json
{
  "issuer": "https://auth.example.com",
  "authorization_endpoint": "https://auth.example.com/authorize",
  "token_endpoint": "https://auth.example.com/token",
  "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
  "client_id_metadata_document_supported": true,
  "registration_endpoint": "https://auth.example.com/register",
  "authorization_response_iss_parameter_supported": true,
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "scopes_supported": ["mcp:tools.read", "mcp:tools.invoke"],
  "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"]
}
```

客户端给 MCP 资源 URL 链发现 : `oauth-protected-resource` 由 RFC 9728 (资源服务器的文档) 命名发行者, 然后 `oauth-authorization-server` (RFC) 命名每个端点。 客户从未硬编码授权 URL 。

对于带有路径的资源标识符,请在该路径之前插入已知的段。例如, `https://mcp.example.com/team/server` 解决保护资源元数据 `https://mcp.example.com/.well-known/oauth-protected-resource/team/server`。 `/.well-known/...` 资源路径错误后 。

信任IP之前你核查的合同 MCP:

- `code_challenge_methods_supported` includes `S256` (PKCE 说明是明确的:如果这个领域 **absent**,授权服务器不支持 PKCE 客户 **必须** 拒绝继续
- `grant_types_supported` includes `authorization_code` 拒绝 `password` 和 `implicit`.
- 至少有一个注册路径 : `client_id_metadata_document_supported: true` (首选CIMD),预先登记的客户,或 `registration_endpoint` (已折旧的RFC 7591兼容性)。
- 如果 `authorization_response_iss_parameter_supported` 是真的,客户要求回的RFC 9207 `iss` 并将其与重新定向前的发行者完全比较。
- `response_types_supported` 确实 `["code"]` 用于 OAuth 2.1.

如果 `S256` 失踪 MCP 服务器拒绝对这个 IdP 进行部署, 没有退化模式 PKCE. 如果 *neither* 注册路径已公布, 您没有预先注册 `client_id`,您也不能注册;部署表是错误的,而不是代码。

<a id="rfc-9728-recap--protected-resource-metadata"></a>

### RFC 9728(上限)-保护资源元数据

课程16涵盖RFC 9728。 三角洲正在生产: 此文档是客户唯一寻找 被信任的授权服务器的地方 *此* MCP 服务器。 MCP 服务器可以接受 tokens 由多个独立采购干事(一个工作人员,一个伙伴)提供。 RFC 9728 宣布该套;RFC 8414 记录每个独立采购干事所支持的内容。

```json
{
  "resource": "https://notes.example.com",
  "authorization_servers": ["https://auth.example.com", "https://partners.example.com"],
  "scopes_supported": ["mcp:tools.invoke"],
  "bearer_methods_supported": ["header"],
  "resource_documentation": "https://notes.example.com/docs"
}
```

<a id="client-id-metadata-documents-the-recommended-default"></a>

### 客户 ID 元数据文档(建议默认)

CIMD 转换注册 *push* 以 *pull*。而不是要求授权服务器 `client_id`,客户使用 HTTPS URL 它控制 **作为** 它的 `client_id`URL 解析为 JSON 元数据文档; 授权服务器在 OAuth 流程。 信任根植于 DNS: 如果服务器操作员信任 `app.example.com`客户服务对象 `https://app.example.com/client.json`。没有注册往返,没有 `client_id` 要排空的命名空间, 没有每个服务器状态可以同步 。

元数据文档客户端主机 :

```json
{
  "client_id": "https://app.example.com/oauth/client.json",
  "client_name": "Example MCP Client",
  "client_uri": "https://app.example.com",
  "application_type": "native",
  "redirect_uris": ["http://127.0.0.1:7333/callback", "http://localhost:7333/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

该 `client_id` 文档中的值 **必须** 等同它所服务的 URL (授权服务器验证此选项; 拒绝不匹配) 。 授权服务器以 `client_id_metadata_document_supported: true` 在其RFC 8414元数据中。

对于目前的CIMD合同, `client_id`, `client_name`,并且是一个非空的 `redirect_uris` 需要矩阵。客户端标识符是一个绝对 HTTPS 带有路径的 URL 。 `application_type` 可能包含,但这不是 CIMD 字段。 `application_type` 进入首选的 CIMD 路径。

安全事实有两个 细节是坦率的:

- **SSRF.** 授权服务器获取一个攻击者提供的 URL。 它必须保护服务器端请求的伪造( 没有内部/ 高级端点的提取) 。
- **本地主机仿真 。** 光靠CIMD无法阻止本地攻击者 要求合法的客户端元数据 URL 并约束任何 `localhost` 重定向。 授权服务器 **必须** 明确显示在同意时重定向 URI 主机名, **应当** 警告你们吧! `localhost`- 只能改变方向

由于 CIMD 不需要服务器端状态, 没有注册员可以按 DCR 的要求站立。 客户端是只读: 从静态中为您的元数据文档服务 HTTPS 端点,让授权服务器拉动它。

如果授权服务器操作员已经提供了客户身份标识, 请在尝试自动注册前先使用发行者范围登记。 否则会更喜欢 CIMD 。 只有在发行者不能使用预先注册或 CIMD 的情况下才使用已折旧的 DCR 。

<a id="rfc-7591-deprecated-compatibility-enrollment"></a>

### RFC 7591: 折旧兼容性入学率

DCR 在 2026-07-28 修订版中被折旧。 仅保留给不能使用 CIMD 的授权服务器, 且预登记不切实际 。 兼容客户端 :

```json
POST /register
Content-Type: application/json

{
  "application_type": "native",
  "redirect_uris": ["http://127.0.0.1:7333/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none",
  "scope": "mcp:tools.invoke",
  "client_name": "Cursor",
  "software_id": "com.cursor.cursor",
  "software_version": "0.42.0"
}
```

服务器响应 `client_id` 和一个 `registration_access_token` 供日后更新:

```json
{
  "client_id": "c_3e7f1a",
  "client_id_issued_at": 1769472000,
  "redirect_uris": ["http://127.0.0.1:7333/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "registration_access_token": "regt_b2...",
  "registration_client_uri": "https://auth.example.com/register/c_3e7f1a"
}
```

`application_type` 不装饰。 双回桌面客户端声明 `native`; 服务器托管客户端声明 `web` 使用 HTTPS 重新定位磁共振 `token_endpoint_auth_method: none` 是一个公共本地客户端的正确默认值。 它会得到一个 `client_id` 仅此而已,与 PKCE 提供拥有证明。

三个生产陷阱:

- 注册终点必须按来源IP进行标定。 没有此选项, 则会发生敌对状态 。 actor 数以百万计的假注册 耗尽了 `client_id` 命名空间,在登记员处理申请之前先进行费率限制检查。
- `software_statement` (a) 签署 JWT 验证客户名)是某些企业 IdP 的要求。 模拟课程跳过它; 生产线是一个校验步骤, 拒绝本地主机以外的任何单位的无签名注册 。
- 该 `registration_access_token` 必须作为散列而不是纯文本存储。 偷窃此文件 token 意思是攻击者可以重写客户的重置 URIs。

<a id="rfc-8707-recap--resource-indicators"></a>

### RFC 8707(摘要)——资源指标

16课确定了形状。 token 请求包括 `resource=<canonical-mcp-url>`, 以及该 MCP 服务器校验 `token.aud` 匹配每个调用时的自有资源 URL。 Canonical URI 是 *最具体的* 服务器的标识符: 它使用小写机和主机, 没有碎片, 通常没有尾部斜线。 路径组件是 **不** 被规则所剥夺——规定在需要确定个人身份时保留 MCP server. `https://mcp.example.com`, `https://mcp.example.com/mcp`, `https://mcp.example.com:8443`, 和 `https://mcp.example.com/server/mcp` 均为有效的卡通 URIs。 选择每个服务器和插针 `aud` (这堂课的模拟使用 空宿者观众喜欢 `https://notes.example.com` 简洁;部署,共同主办若干次 MCP 在一个来源下的服务器通过路径区分。 )

<a id="rfc-7636-recap--pkce"></a>

### RFC 7636(章次) - PKCE

PKCE 强制使用 OAuth 2.1. 课程授权代码的流向总是随时间推移 `code_challenge` 和 `code_verifier`服务器拒绝任何 token 请求时没有核实者,或没有仓促处理所储存的挑战的核查者。

<a id="mcp-2026-07-28-authorization-profile"></a>

### MCP 2026-07-28授权概况

当前 MCP 修改保留 OAuth 制作时的资源服务器边界 MCP 无需通过协议会议来隐藏身份决定。 因此,授权层可以独立验证每项请求:

- 实施 RFC 9728 保护资源元数据,并通过 `WWW-Authenticate: Bearer resource_metadata="..."` 401号机头 **或** 众所周知的 URI `/.well-known/oauth-protected-resource` (SEP-985) 以众所周知的后退方式选择了标题。元数据 `authorization_servers` field **必须** 名称至少是一个服务器 。
- Accept tokens 仅通过 `Authorization: Bearer ...` 在 **每个** 请求 - 从未在查询字符串中, 仅在会话开始时才生效 。
- Validate `aud`, `iss`, `exp`,并按请求设定范围。 **必须** 证实 token 专门为它(观众)发放的;丢失或不匹配 `aud` 被否决, 从未被作为通配符处理 。
- 401/403号,返回 `WWW-Authenticate: Bearer` carrying `error=...`, 该 `resource_metadata="<PRM-URL>"` parameter (元数据文档的 URL, *不* 以及(此处叩头!) `scope="..."` 在 `insufficient_scope` (403) 说明: parameter 是 `resource_metadata`发现指针 - 没有 `resource` parameter 挑战。
- 接受授权服务器的发现 **任一** RFC 8414号 OAuth metadata **或** OpenID 连接发现1.0; 客户必须按优先级尝试两个众所周知的后缀 。
- 客户( 不是服务器) 进行防御 **混杂攻击**:它记录了预期 `issuer` 和验证 `iss` 数值在实际批准回复(RCC 9207)中返回,然后才变现代码。 PKCE 单靠自己不能停止混淆 因为客户会手握 `code_verifier` 随便 token 终点是它被引导到的
- 客户端证书属于一个授权服务器发行人。 如果发现结果由另一个发行人解决, 客户端将重新注册, 而不是展示旧的 `client_id`,登记 token,或访问 token.
- CIMD 是首选的注册机制。 DCR 已被折旧; 兼容 DCR 请求仍然声明正确 `application_type`.

该 OAuth 2.1 草案为基础;RFC 8414/7591/8707/9728/9207+RFC 7636+CIMD为表面; MCP 特征就是特征

<a id="deployment-capability-checklist"></a>

### 部署能力清单

Vendor feature 表格迅速变淡。 请检查您实际将部署的授权服务器返回的元数据。 大门是机械的 :

| Check | 需要作出的决定 |
|---|---|
| 发现发行者 | Exact HTTPS 政策预期的发行者 |
| PKCE | `S256` 广告;否则停止 |
| 招生 | CIMD 倾向于,预先登记为接受,但DCR仅作为折旧兼容性 |
| 授权回复 | 验证 RFC 9207 `iss` 现职或广告 |
| 资源约束 | Token 请求随身携带 `resource`; 资源服务器需要匹配 `aud` |
| 证书储存 | 按发行人分列的关键客户身份和登记证书;关键访问 tokens 按发行者加资源 |
| 数据记录兼容性 | Declare `native` 或 `web`; 拒绝重定向不符合已申报应用程序类型的 URI |

不要从产品名称或定价层次推断支持。 在部署证据中捕获所发现的文档, 当强制字段不存在时失败 。

<a id="jwks-refresh-pattern-rotate-at-the-as-refresh-at-the-resource-server"></a>

### JWKS 刷新模式( 在 AS 旋转, 在资源服务器上刷新)

保持两个动词分开, 因为合并它们是一个真正的生产错误 :

- **Rotate** 是什么,这是 *授权服务器* : 将新的签名密钥刻录在 JWKS 中, 以后再将旧密钥留存。 资源服务器没有参与其中, 无法做到这一点 —— 它不持有 IdP 的私人密钥 。
- **Refresh** 是什么,这是 *资源服务器* 说:`GET` 将已公布的 JWKS 输入到缓存中。 这是资源服务器唯一能执行的 JWKS 动作 。

生产失败模式是一个老化的缓存。 以一个预定的刷新任务解决它, 加上一个密钥值缓存。 资源服务器运行一个在固定间隔内获取的工作( cron、 计时器、 不论您是否愿意运行) `<issuer>/.well-known/jwks.json` 被倾覆 `cache[issuer] = {keys, fetched_at}`。验证符读取的缓存。 token whose `kid` 丢失于缓存触发器 **one** 同步刷新作为回溯, 然后重新检查。 它同时处理两个案例: 预定的刷新, 和密钥重叠窗口 token 由新密钥签名, 在下次计划更新之前到达 。

后退的状态 **必须是再伸展, 绝不旋转**。如果您将缓存缺失路径连接到旋转和最小路径,则有两件中断:(1) 拆开新密钥生成 `kid` 该 *still* 与 token,所以搜索失败;(2) 喷雾攻击者 tokens 随机 `kid` 值强制生成一系列未设界的关键创造—— 自定义的 DoS。 重取是一等的, 所以是假的 `kid` 最多一个浪费的接货费。

缓存形状 :

```json
{
  "https://auth.example.com": {
    "keys": [
      {"kid": "k_2026_03", "kty": "RSA", "n": "...", "e": "AQAB", "alg": "RS256", "use": "sig"},
      {"kid": "k_2026_04", "kty": "RSA", "n": "...", "e": "AQAB", "alg": "RS256", "use": "sig"}
    ],
    "fetched_at": 1772668800
  }
}
```

同步两个密钥是稳定状态。 授权服务器通过引入下一个密钥旋转( NAME OF TRANSLATORS)`k_2026_04`)之前的(`k_2026_03`,这样 tokens 旧密钥下发布的,在过期前有效。缓存持有联盟;验证人选择 `kid`.

<a id="the-validation-routine"></a>

### 验证程序

该 MCP 服务器在发送任何工具之前运行验证。 形状 `code/main.py` 使用:

```python
result = server.validate(bearer_token, required_scope="mcp:tools.invoke")
if not result["valid"]:
    return {"status": result["status"], "WWW-Authenticate": result["www_authenticate"]}
```

`validate` 解码 JWT,从 JWKS 缓存中解决签名键(在错误时重新打开一次),核实签名,然后检查 `iss` 与允许名单相反 `aud` 与此服务器的金刚石资源相对, `exp`以及所需范围——返回a `WWW-Authenticate` 第一次失败时的挑战。 在资源服务器上保持它一个单一的例行程序意味着每个切入点( 每个 tool call,每个运输工具)都经过同样的检查;没有一条路径可以达到工具,而无需先验证。

<a id="opaque-tokens-use-introspection-not-guesswork"></a>

### Opaque tokens 使用内省, 不猜测

不是所有访问 token 是一个 JWT。如果发行者将不透明地 token,资源服务器无法将其解码为可信赖的债权。它发送 token 向发行者的RFC 7662反省端点 提供经过认证的后通道 `active: true`,预期发行人的背景,确切的 MCP 观众或资源,未完成的时间申报,以及具体工具要求的范围。

由发行人单向地进行缓存内省 token 文摘,和 MCP 资源。永远不要使用清除 token 以日志或缓存标签的形式。 token 过期、 发行者缓存指南和部署的取消新状态目标。 保持负缓存短到新发布 token 无法使用一个资源的结果,即使不透明 token 字符串相同 。

不从攻击者控制中选择验证模式 token 内容. 平 JWT 相对于反省行为, 以验证发行者元数据和部署配置。 关于 JWT 路径、 针被接受的算法和信任 `jwks_uri`; 永远不要遵循仅由 token header.

<a id="revocation-is-a-freshness-contract"></a>

### 免职是新鲜合同

RFC 7009 让客户请求授权服务器撤销 token。该请求不会删除每个资源服务器已经隐藏的复制件。定义最大可接受的撤销延迟,并让每个缓存都兑现它。

Opaque-token 部署可以通过对每次高风险呼叫进行反省或使用短时间正数缓存实现更严格的撤销。 JWT 部署通常结合了短途出入token 充满了活力token 撤销、对全发行者事件的关键退职以及选修科目、会话或 token- 当地紧急拒绝的拒绝名单。 JWT 除非资源服务器有当前外部撤销证据,否则在过期前仍具有加密有效。

注销、账户禁用、同意退出和 incident response 是一个不同的触发器,但必须在一个可测量的语句上求同:最多在声明的撤销窗口之后,每个复制器都拒绝认证。通过负载平衡器测试该语句,而不仅仅是对一个温暖的过程。

<a id="dependency-failure-needs-a-declared-decision"></a>

### 依赖性失灵需要宣布决定

绝不是即兴表演 availability 特殊处理器内的政策 。

| Failure | 安全生产行为 |
|---|---|
| 计划 JWKS 刷新失败, 已知道 `kid` 仍留在一个仍然有效的封存缓存中 | 仅在已宣布的悬浮窗口中继续,并发布退化的健康证据 |
| Token 未知的状态 `kid` 允许刷新失败的 | 拒绝; 不接受无法核实的签名 |
| 无法反省 | 保护电话不关闭; 不将网络故障转换为 `active: true` |
| 保护资源或发行者元数据意外变化 | 停止新注册 token 获取; 仅根据受约束事件政策保持明确锁定、未到期配置 |
| 无法取消终点 | 报告注销或撤销为不完整,保留在当地的证书,在可能的情况下不能使用,并且不声称全局撤销成功 |
| 时钟源或索赔类型无效 | 拒绝而不是扩大,直到 token passes |

将失败和无效的证书分开分类。 依赖性断开是带有健康和重试策略的操作错误。 错误的签名、 发行者、 观众、 过期或范围是拒绝授权。 工具处理者都无法接触到, 也不应该泄漏 token 内容纳入审计证据。

<a id="audience-replay-walkthrough-access-token-privilege-restriction"></a>

### 观众重播漫步token 特权限制)

服务器 A (`notes.example.com`和服务器 B (`tasks.example.com`) 都对同一个授权服务器注册。服务器 A 已损坏。 攻击者将使用用户的便笺 token 并重播它与服务器B。

服务器 B 的验证符 :

1. Decode JWT,从 `kid`,验证签名。
2. Check `iss` 相对于其保护资源元数据 `authorization_servers`.(通行证——同样的身份证)
3. Check `aud == "https://tasks.example.com"`. (失败 -) token的 `aud` 是 `https://notes.example.com`.)
4. 返回 401 和 `WWW-Authenticate: Bearer error="invalid_token", error_description="audience mismatch", resource_metadata="https://tasks.example.com/.well-known/oauth-protected-resource"`.

观众声称是对抗协议层攻击的唯一防御。 跳过它来表现最常见的错误; 验证人必须按每个请求运行, 而不是在会议开始时。 预览者称之为此 。 **access-token 特权限制**: 一个 MCP server `MUST` 拒绝任何 token 观众中不叫它名字

> **命名音符 。** 规格保留了术语 *混杂的副手* 是一个相关但明显的问题: MCP 服务器作为 OAuth **proxy** 给第三方的 API,使用静态客户端编号, token 未经每个客户用户同意。 观众约束会修正上述重播; 混杂的副作用修正会得到每个客户的同意 **plus** 从未经过入境 token 穿过上游 APIs (该 MCP server `MUST` 自己去上流地区 token).

<a id="mix-up-attacks-a-client-side-defense-the-server-cannot-provide"></a>

### 混合攻击( 服务器无法提供客户端防御)

客户在很多授权服务器上 都说到他们的生命。 token 结束点。 观众的束缚对这里毫无帮助,攻击发生在任何 token 被告的辩护生命(RCC 9207):

1. 在重新定向之前,客户记录了预期的 `issuer` 由已验证的AS元数据中生成。
2. 在授权回复中,客户比较了返回的 `iss` parameter 相对于已录制的发行者( 简单字符串比较, 无) normalization)之前,将代码发送到任何地方。
3. 错配( 或) `iss` 当AS广告时缺席 `authorization_response_iss_parameter_supported`拒绝,甚至不显示 `error` fields.

PKCE 单靠自己不能停止混淆 因为客户会手握 `code_verifier` 随便 token 最终点,它被引导到。 这就是为什么规格记录了每个要求的发行者 PKCE 核查员和 `state`.

<a id="failure-modes"></a>

### 失效模式

- **烂JWKS。** 验证人拒绝有效 tokens 自动交换键旋转后。 修正是上面的 cron- refresh + capse- miss- refach 模式。 不再在不进行刷新工作的情况下隐藏 JWKS 。
- **Rotate-as-fall-back.** 将缓存缺失路径与旋转和最小路径相连接, 而不是重新拉伸是一个真正的错误: 它从不生成缺失的路径 `kid`,它会变成攻击者控制 `kid` 值进入创建密钥 DoS。 后退必须是一流的 `refresh-jwks`.
- **Missing `aud` claim.** 某些要省略的 IdP 默认值 `aud` 除非 `resource` 位于 token 请求。 验证人必须拒绝 tokens 缺少 `aud`,而不是把缺席作为通配符。
- **通过丢失混音 `iss` check.** 一个客户没有验证 RFC 9207 `iss` authorization-response parameter 与发行者对抗 在重新定位前被记录 被引导去赎回一个诚实的AS代码 token 端点。 这是客户端的失败; 资源服务器无法补偿它 。
- **范围升级比赛。** 同一用户的两个同时的升级流程既可以成功,也可以产生两个接入 tokens 使用不同范围。 token 而不是去寻找“用户当前的范围”—— 从而创建了TOCTOU窗口。
- **Registration token theft.** 漏了个屁 `registration_access_token` 让攻击者重写 URIs 重置。 rest;要求客户在每次更新时提交明确文本;在怀疑情况下轮换。
- **`iss` 还没被钉住** 接受任何 `iss` 让攻击者自己站立授权服务器, 登记目标受众的客户端, 并发布 tokens。 `authorization_servers` 列表是允许列表; 强制执行它。
- **证书或 token 缓冲碰撞** 仅按资源键注册的客户可以向另一个用户显示一个授权服务器的身份。 tokens 只有发行者才能重播 token 由验证的发行人注册密钥, 密钥访问 tokens 通过 `(issuer, resource)`,并重新输入发行者改变的版本。

```figure
t3-jwks-rotate
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 以平滑的平滑行走 Python 和三个角色: `AuthorizationServer`, `ResourceServer`, 和 `Client`流动 :

从仓库根运行 :

```bash
cd phases/13-tools-and-protocols/18-mcp-auth-production
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

第一个命令打印发行者登录的注册 token-validation
记录。第二份报告 18 过关检查。 任何命令都无法打开
网络听众或写证书。

1. 授权服务器发布 RFC 8414 元数据 `/.well-known/oauth-authorization-server`.
2. MCP 客户端调用元数据端点并检查其注册选项( W)`client_id_metadata_document_supported` 给CIMD, `registration_endpoint` 和(d) 区域 `S256` PKCE support.
3. 客户检查发行人范围范围的预登记,否则注册为 HTTPS 客户端 ID 元数据文档。 过期的 DCR 仍然是一种可单独测试的兼容性方法 。
4. 客户记录了经验证的发行人 创建了S256质疑 收到一次性授权代码加 `iss`,验证该发货人的身份,并用原始核查人和RFC 8707来解码 `resource` indicator.
5. MCP 客户端在 MCP 服务器 `Authorization: Bearer ...`.
6. MCP 服务器运行 `validate`,从 JWKS 缓存中解开签名密钥。
7. IdP 旋转密钥; 计划进行的刷新将 JWKS 拖放到缓存中 。
8. 下一次调用对刷新键进行验证, 不重新启动, 以及上一个 token 仍然在重叠窗口中验证。
9. 一次针对不同对象的观众重播 MCP 资源获得 401 和 `audience mismatch` 和一个 `resource_metadata` pointer.

该 JWT 在此使用 HS256 共享秘密( 课程仅以标准lib 运行) 。 生产使用 RS256 或 EdDSA , 上面的 JWKS 模式; 验证逻辑是相同的 。 因为 IdP 和资源服务器生活在一个过程中, `refresh_jwks` 直接读取授权服务器的密钥列表; 在线上是 HTTP `GET` 以 `jwks_uri`.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-mcp-auth.md`。如果有的话 MCP 服务器配置和 IdP 功能集, 技能释放授权表面以站起来—— 保护资源元数据、 使用注册路径( CIMD、 预登记或 DCR 回溯)、 JWKS 更新计划、 范围映射以及当 IdP 不支持完整 RFC 配置时的拒绝规则 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`. Trace 注意 IdP 在计划的第6步中旋转键 `refresh_jwks` 重新拉动已出版的集,同时拉动旧的 token 和新鲜的 token 验证不重开 。

2. 在受保护资源元数据中添加新的 IdP `authorization_servers` 列表。 token 由新IP签署并确认验证人接受。 token 由未列名的 IdP 签名, 确认无效的验证者为 `WWW-Authenticate: Bearer error="invalid_token", error_description="iss not allowed"`.

3. 添加一个限制费率的检查到 `register_client` 使用 token- 每个源IP都用小插头按住

4. 阅读 RFC 7591 并识别两个课程字段 `/register` 处理器不验证。 添加验证 。 (提示 : `software_statement` 和 `redirect_uris` 反贪计划。 )

5. 添加第二个授权服务器。 确认客户端存储一个单独的发行人加密的注册, 并拒绝重新使用第一个发行人的 token 或 `client_id`.

6. 证明 DoS 修正。 发送验证符 a token 随机 `kid` 并确认 `refresh_jwks` 最多一次运行, 授权服务器的密钥数不会增加 。 然后故意将回溯线重新连接到旋转和最小上, 并观看键数在假的上移 token 之后再恢复再伸缩

7. 演习已折旧的DCR, 两者 `native` 和 `web` 确认一个网络客户端 HTTP 重新定位 URI 和一个本地客户端, 但没有精确回溯重定向, 被拒绝 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| ASM | "OAuth 元数据文档" | RFC 8414号 `/.well-known/oauth-authorization-server` JSON |
| CIMD | “ 用户元数据 URL ” | 客户名元数据文档: a HTTPS URL 用作 `client_id`; AS 调用 JSON中选择的注册 MCP 2026-07-28 |
| DCR | "自费客户登记" | RFC 7591号 `POST /register`; 在当前情况下折旧 MCP 仅保留为兼容性 |
| JWKS | "公共钥匙 JWT validation" | JSON Web 密钥集, 从 `jwks_uri`,由 `kid` |
| 旋转与刷新 | 更新钥匙 | *Rotate* = AS 薄荷糖/调味剂签名键; *refresh* = 资源服务器重新输入已公布的集。 资源服务器仅会刷新 |
| 资源指标 | "Audience parameter" | RFC 8707号 `resource` parameter 夹住 token 转到一个服务器 |
| `aud` claim | "Audience" | JWT 对比金刚石资源 URL 来要求验证符 |
| 观众重播 | "Token replay" | Token 向服务器 B 展示了服务器 A ; 由观众验证进行辩护( 请注明: 访问 - )token 特权限制) |
| 混杂的副手 | "Proxy token misuse" | 一个 MCP 代理服务器, 使用静态客户端 ID 转发 a token 未经每个客户同意; 不同于观众重播 |
| 混合攻击 | "Wrong token endpoint" | 客户在攻击者的终点 被引导去解码诚实的AS ; 通过RFC 9207为客户辩护 `iss` |
| `iss` allow-list | "信任授权服务器" | 保护资源元数据中命名的集 `authorization_servers` |
| `resource_metadata` | "在哪里找到PRM医生" | `WWW-Authenticate` parameter 以401/403命名 RFC 9728元数据 URL |
| 公共客户 | “ 原用户或浏览器客户端” | OAuth 无客户端 `client_secret`; PKCE compensates |
| `WWW-Authenticate` | "401/403 回应信头" | Carries `Bearer error=...` 促使客户收回指令 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 授权规格(2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) - 水流 MCP 授权配置
- [MCP 2026-07-28变化](https://modelcontextprotocol.io/specification/2026-07-28/changelog) - CIMD、发行人验证、DCR折旧和签发人保有的证书更改
- [OAuth 客户端 ID 元数据文档(草稿- ietf-)oauth-client-id-metadata-document-00)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-client-id-metadata-document-00) - CIMD(计算机通信中心)
- [RFC 8414 - OAuth 2.0 授权服务器元数据](https://datatracker.ietf.org/doc/html/rfc8414) 发现合同
- [RFC 7591 - OAuth 2.0 动态客户登记程序](https://datatracker.ietf.org/doc/html/rfc7591) - DCR(后退路径)
- [RFC 7636 - 代码交换的证明密钥(RFC 7636)PKCE)](https://datatracker.ietf.org/doc/html/rfc7636) 公客户的委托书
- [RFC 8707——用于 OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc8707) 观众针刺
- [RFC 9728 - OAuth 2.0 受保护资源元数据](https://datatracker.ietf.org/doc/html/rfc9728) 资源服务器发现
- [RFC 9207 - OAuth 2.0 授权服务器发行者标识](https://datatracker.ietf.org/doc/html/rfc9207) — 该 `iss` parameter 防混攻击
- [RFC 7662: OAuth 2.0 Token Introspection](https://datatracker.ietf.org/doc/html/rfc7662)
- [RFC 7009: 红宝石公司 OAuth 2.0 Token Revocation](https://datatracker.ietf.org/doc/html/rfc7009)
