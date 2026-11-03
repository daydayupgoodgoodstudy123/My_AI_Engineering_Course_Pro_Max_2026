<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-authorization-cimd-issuer-binding-pkce-and-step-up"></a>

# MCP 授权：CIMD、签发者绑定、PKCE 与升级认证

> 远程 MCP 申请是无国籍的,但授权不是匿名的。 token 来接收它的资源

**类型：** 构建
**语言:** Python
**先修要求:** 阶段13 · 0 9(运输),阶段13 · 15(安全)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 通过保护资源元数据发现授权服务器 。
- 更喜欢客户身份元数据文档,而不是已折旧的动态客户登记。
- 声明正确 `application_type` 当 DCR 兼容性路径不可避免时 。
- 验证授权回复 `iss` 并按发行人分列证书。
- 使用 PKCE、资源指标、受众验证和递增范围。
- 发送授权 MCP 2026-07-28项请求没有举行礼宾会议。

<a id="the-problem"></a>

## 问题

远程 MCP 服务器可以读取私人记录, 写入外部系统, 或者触发昂贵的工作。 验证会告诉谁提交了证书 。 授权也必须回答 :

- 哪个授权服务器签发了证书?
- Which MCP 资源为 token 用于?
- 哪个客户端和重新定位的URI完成了流程?
- 用户批准哪些操作?
- 这份申请是否仍然符合批准条件?

2026-07-28授权配置使客户注册和发行处理更加严格。 它更喜欢客户身份元数据文档, 并会破坏动态客户注册, 需要右侧 `application_type` 并禁止发行者重新使用证书。

这些规则补充了无国籍的核心,不能恢复核心握手或恢复核心握手。 `Mcp-Session-Id`.

<a id="the-concept"></a>

## 概念

<a id="know-the-three-roles"></a>

### 认识三个角色

- **MCP client:** 代表资源所有者发送请求 。
- **MCP 资源服务器 :** 接受访问 token 服务于 MCP endpoint.
- **授权服务器 :** 认证资源所有者, 收集同意并发布 tokens.

资源服务器和授权服务器可以同时运行,但将其识别资料和验证责任分开。

<a id="authorization-applies-to-http"></a>

### 授权适用于 HTTP

该 MCP 授权规格适用于 HTTP本地的平板服务器在流程和操作系统下运行 trust boundary。不添加一个假浏览器 OAuth 流到平坦的状态只是为了对称

用于远程流 HTTP,发送持证人 token 在 `Authorization` 每个请求都标头。 永远不要把它放在 URL 中 。

<a id="start-with-protected-resource-metadata"></a>

### 以受保护资源元数据开始

资源服务器发布 RFC 9728 元数据:

```json
{
  "resource": "https://notes.example.com/mcp",
  "authorization_servers": ["https://auth.example.com"],
  "scopes_supported": ["notes:delete", "notes:read", "notes:write"]
}
```

客户端从 MCP 资源 URL, 获取此文档, 选择一个已公布的授权服务器, 然后获取该服务器的 OAuth 或 OpenID 连接元数据。

构建 RFC 9728 著名 URL 时保存资源路径。 对于此资源 `https://notes.example.com/mcp`,该课使用 `https://notes.example.com/.well-known/oauth-protected-resource/mcp`。 `/mcp` 后缀可以选择同一来源的不同受保护资源的元数据。

不要从主机名中猜想授权服务器。 不要跟随从未验证错误体中发现的发行者。 保留客户端愿意信任的发行者的政策 。

<a id="verify-authorization-server-metadata"></a>

### 校验授权服务器元数据

元数据应披露终点和辅助控制:

```json
{
  "issuer": "https://auth.example.com",
  "authorization_endpoint": "https://auth.example.com/authorize",
  "token_endpoint": "https://auth.example.com/token",
  "code_challenge_methods_supported": ["S256"],
  "authorization_response_iss_parameter_supported": true,
  "client_id_metadata_document_supported": true
}
```

需要S256 PKCE。记录确切的发行人字符串。该精确值成为注册和 token storage.

<a id="follow-the-registration-priority"></a>

### 遵循登记优先权

当客户与所选发行者已有明确关系时, 使用预先登记的客户端信息。 否则, 当授权服务器广告支持时, 更喜欢使用客户端 ID 元数据文档 。 仅使用 DCR 作为已折旧的兼容性退缩, 然后 prompt 如果没有这些机制,则提供客户信息。

<a id="prefer-client-id-metadata-documents"></a>

### 更可取的客户身份元数据文档

客户端 ID 元数据文档给授权服务器一个 HTTPS 既是客户端标识符又是元数据位置的 URL :

```json
{
  "client_id": "https://client.example.com/oauth/metadata.json",
  "client_name": "Notes desktop client",
  "application_type": "native",
  "redirect_uris": ["http://127.0.0.1:8765/callback"],
  "grant_types": ["authorization_code"],
  "response_types": ["code"]
}
```

授权服务器获取并验证文档。 `client_id` 一定是个 HTTPS 带有路径的 URL,文档中的值必须完全等于该 URL。所需要的文档字段是 `client_id`, `client_name`, 和 `redirect_uris`. `application_type` 此处出现,但不是CIMD要求。 其新的强制使用是具体DCR路径。

将获取文档作为具有SERF 敏感性的操作处理。 确定并验证目的地, 拒绝回滚、 私人、 链接本地或其它被否决的地址, 在重定向和 DNS 更改后重新检查, 限制重定向、 字节和时间要求 JSON,并且只能根据验证的缓存 HTTP 缓存控制。 处理 `client_name` 和作为不可信文本的其他显示字段。

CIMD 取消了每次第一次接触时需要的最小化动态标识符。 它不会取消重定向 URI 验证、 发行策略或用户同意 。

<a id="dcr-is-a-compatibility-path"></a>

### DCR 是兼容路径

旧授权服务器仍然可以进行动态客户登记,但用于新的 MCP implementations.

使用 DCR 时, 声明 `application_type`:

```json
{
  "client_name": "Notes desktop client",
  "application_type": "native",
  "redirect_uris": ["http://127.0.0.1:8765/callback"],
  "grant_types": ["authorization_code"],
  "response_types": ["code"]
}
```

- 使用桌面、移动、命令行和回溯客户端 `native`.
- 远程主机浏览器应用程序使用 `web` 远程 HTTPS redirects.

默认字段 `web` 并让合法的回路重置失败。

保持 DCR 代码在明确后退决定后面。 在任意的 CIMD 验证失败后不要静静地退缩。 这样可以将安全故障变成较弱的注册路径 。

<a id="bind-credentials-to-the-issuer"></a>

### 将全权证书附于发行者

保存发行者记号的注册材料,

```text
issuer_credentials[issuer] = pre_registered_or_dcr_client
tokens[(issuer, resource)] = access_token
```

如果保护资源发现从 `https://auth-one.example` 以 `https://auth-two.example`重新评价信任,不要把第一位发行人客户的秘密 DCR客户身份,注册权限 token,以刷新 token,或访问 token 预先登记和记录管理客户必须使用新发行人签发的证书。

CIMD 客户端id 不同, 因为它是自托管的 HTTPS URL, 不是授权服务器的认证。 相同的 CIMD URL 是可移植的: 新的可信任发行者在不重新注册 DCR 的情况下获取并验证文档。 授权回复和 tokens 仍在新的发行者之下验证和储存。

<a id="authorization-code-with-pkce"></a>

### 授权代码 PKCE

互动流程是:

1. 生成高密度的 `code_verifier`.
2. 引出S256号 `code_challenge`.
3. 准确发送授权请求 `client_id`, `redirect_uri`, `scope`, `code_challenge`, 和 `resource`.
4. 接收授权回复, 包含 `code` 并且,如果提供了, `iss`.
5. Validate `iss` 使用任何响应字段前,与确切记录的发行者相对照。
6. 交换代码 `code_verifier`,相同的调整 URI,同样的 `resource`.
7. 保存结果 token under `(issuer, resource)`.

该 `resource` parameter 皇家空军8707号 出现在批准和批准中 token 标注了 MCP 服务器 URI 。

<a id="validate-iss-exactly"></a>

### Validate `iss` exactly

RFC 9207防止一个发行人的授权答复与另一个发行人的答复混淆。

当 `iss` 存在, 比较它与已记录的发行者, 不折叠、 尾随冲击变化、 默认端口清除或% 编码 normalization。在不匹配时,不要对代码采取行动,甚至不要显示该响应中攻击者控制的错误细节。

授权服务器,包括 `iss` advertises `authorization_response_iss_parameter_supported: true`。当前客户仍然验证一份礼物 `iss` 即使广告没写

<a id="validate-audience-at-the-mcp-server"></a>

### 校验观众 MCP server

仅接受资源服务器 tokens 特此印发:

```text
token.issuer == configured_authorization_server
token.audience == canonical_mcp_resource
```

无效、过期、错误签发者或错误的观众 tokens 401. 家庭补助 MCP 服务器不可接受或中转 a token 本来是给另一个服务

<a id="request-the-smallest-current-scope"></a>

### 要求最小的当前范围

以当前需要的范围开始。 如果后一个工具需要更多的, 服务器返回403 , 并带有权威范围挑战 :

```text
WWW-Authenticate: Bearer error="insufficient_scope",
  scope="notes:delete",
  resource_metadata="https://notes.example.com/.well-known/oauth-protected-resource/mcp"
```

客户对新权限的解释, 获得同意, 执行新的授权流程 与合并范围集, 并重试 MCP 带有新 JSON-RPC id.

假设被质疑的范围是 `scopes_supported`. 挑战对目前行动具有权威性。

<a id="authorization-and-the-stateless-mcp-wire"></a>

### 授权和 stateless MCP wire

授权 tool call 仍然携带完整当前请求信封:

```text
POST /mcp
Authorization: Bearer <access-token>
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: notes.delete
```

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "method": "tools/call",
  "params": {
    "name": "notes.delete",
    "arguments": {"id": "note-7"},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {},
      "io.modelcontextprotocol/clientInfo": {
        "name": "oauth-lesson-client",
        "version": "1.0.0"
      }
    }
  }
}
```

该 token 请求元数据会谈判协议行为, 无法替代对方 。

以固定顺序验证电线: JSON-RPC 和元数据类型、标题和体等同,然后支持协议。 HTTP 4 000 计 `-32020`。如果页眉和正文同意一个不支持的版本,则返回 HTTP 4 000 计 `-32022` 和 `data` exactly `{"supported":["2026-07-28"],"requested":"<actual>"}`返回未知的方法 HTTP 404 计 `-32601`.

每个请求错误, 包括 401 无效 token 范围不足的403个 JSON-RPC 原始请求的错误信封 `id`。结构化的回收信息属于可选错误 `data`; `WWW-Authenticate` 继续 HTTP 回复信头。 通知没有 `id`,所以它没有得到 JSON-RPC 接受的 HTTP 通知返回空体202。

服务器执行器 `server/discover` 并公布工具,因此它也执行强制性 `tools/list` 方法。其工具描述符具有稳定的名称、描述和对象根 `inputSchema` 值。列表是确定性和返回 `resultType`服务器身份元数据,一个连接 `ttlMs`, 和 `cacheScope`。在授权之前,可以提供发现和用户独立的工具列表。如果按主机不同,则应用正常政策和私人缓存。

<a id="no-token-passthrough"></a>

### 否 token passthrough

一个 MCP 服务器不能转发客户端的 MCP access token 下游的 API获得单独的下游 token 使用明确的 token只有在服务拒绝时才能进行观众验证 tokens 给别人装了

<a id="refresh-tokens"></a>

### Refresh tokens

Refresh tokens 。当发布时,要保密地将其存储,并用发行人和资源键入。不要假设它们存在。当授权服务器支持旋转并检测无效值的再利用时,要旋转它们。

```figure
t3-scope-stepup
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 是一个在程序内的协议和授权模拟器。 它执行受保护的资源发现、授权服务器元数据、 CIMD 输入、版本化 DCR 备份、 应用程序类型检查, PKCE发行人验证,有资源 tokens,范围提升, `server/discover`, `tools/list`,以及无国籍工具请求。

该模型接收解析请求的机构和路由信头。 HTTP 适配器, 不分析 `Content-Type` 或 `Accept`连接到 9 节流课程 HTTP 适配器, 需要 `Content-Type: application/json` 和一个 `Accept` 包含两个值的数值 `application/json` 和 `text/event-stream`.

运行：

```bash
cd phases/13-tools-and-protocols/16-mcp-security-oauth-2-1
python3 code/main.py
python3 -m unittest discover code/tests -v
```

输出显示发现第一,CIMD 注册,普通读, 两个单独的范围提升, 和发行人 以证书为主的存储。

<a id="use-it"></a>

## 实际应用

将模拟器对象映射为生产部件:

- `ResourceServer.protected_resource_metadata` 成为RFC 9728终点。
- `AuthorizationServer.metadata` 成为 RFC 8414 或 OpenID 连接发现。
- `Client.enroll` 成为 CIMD 分辨率加上明确的 DCR 兼容性 branch.
- 客户证书和 `tokens_by_issuer_resource` 成为加密记录。 CIMD URL 仍然可以被移动, 而授权结果仍然在发行者权限之内 。
- `ResourceServer.handle` 成为验证当前状态的中间软件 MCP headers, token,在发送前将每个请求错误保留在匹配中 JSON-RPC envelope.

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-oauth-scope-planner.md`。它现在设计注册优先级,发行人限制的证书存储,应用类型, PKCE、资源指标、范围挑战和目前无国籍者要求的界限。

<a id="exercises"></a>

## 练习

1. 添加刷新 -token 旋转并拒绝重复使用上一个刷新 token.
2. 添加发行者允许列表。 在发行者更改时, 只重新使用可移植的 CIMD URL; 拒绝所有先前签发者记号证书并 tokens.
3. 在授权代码中添加过期失效通知, 并确认延迟交换失败 。
4. 使用远程创建网络客户端变量 HTTPS 重新定位并比较 DCR 元数据与本地客户端 。
5. 在同一发行者之下添加第二个资源。 确认访问权限 token 无法在第一个资源中使用。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| 保护资源元数据 | RFC 9728号文件,其中标明资源和授权服务器 |
| CIMD | HTTPS 元数据文档的 URL 是 OAuth 客户端标识符 |
| DCR | 保留了已折旧的动态客户端注册,以保持兼容性 |
| `application_type` | `native` 或 `web`,用于验证重置 URI 规则 |
| PKCE | 保护被拦截授权代码的验证和 S256 质疑 |
| `iss` | RFC 9207 授权应答器标识符 |
| 资源指标 | RFC 8707号 parameter 中,该词将 token 请求 MCP resource |
| Audience | 用于 a 源 token 有效 |
| Step-up | 新同意和 token 额外当前操作范围 |
| 受签发人限制的全权证书 | 登记和 token 由授权服务器发行者隔开记录 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28 授权说明](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [RFC 9728: OAuth 2.0 受保护资源元数据](https://www.rfc-editor.org/rfc/rfc9728)
- [RFC 8707: 资源指标 OAuth 2.0](https://www.rfc-editor.org/rfc/rfc8707)
- [RFC 9207: OAuth 2.0 授权服务器发行者标识](https://www.rfc-editor.org/rfc/rfc9207)
- [OAuth 客户 ID 元数据文档草稿](https://datatracker.ietf.org/doc/draft-ietf-oauth-client-id-metadata-document/)
