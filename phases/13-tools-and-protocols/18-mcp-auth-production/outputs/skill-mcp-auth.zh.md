---
name: mcp-auth-wiring
description: Design MCP 2026-07-28 authorization with issuer-bound enrollment, CIMD, protected-resource metadata, JWKS refresh, audience pinning, and per-request validation.
version: 2.0.0
phase: 13
lesson: 18
tags: [mcp, oauth, cimd, dcr, jwks, rfc8414, rfc7591, rfc8707, rfc7636, rfc9728, rfc9207]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 MCP 服务器配置和 IdP 功能集, 发布构成生产的验证表面和拒绝规则 MCP 授权层。

输入:

- `mcp_resource_url` ─ 粗体资源 URL(最特定标识符;仅在区分共同托管服务器时保留路径),用作 `aud` 并用作受保护资源元数据 `resource` 值.
- `idp_metadata_url` - 党内警察 `/.well-known/oauth-authorization-server` URL( 或 OpenID 连接发现) URL 。
- `idp_capabilities`:观察到的数值 `issuer`, `code_challenge_methods_supported`, `grant_types_supported`, `client_id_metadata_document_supported`,折旧 `registration_endpoint`, `response_types_supported`, 和 `authorization_response_iss_parameter_supported`.
- `pre_registered_client_ids`:授权服务器操作员提供的可选发行者对客户识别图。在 CIMD 之前,最好使用此发行者范围的身份,然后只使用已折旧的 DCR 作为最终兼容路径。
- `application_type`: `native` 或 `web`,在选择折旧后 DCR 兼容性时必须使用。
- `credential_store`:客户身份和登记证书,由授权服务器签发人负责,并可以查阅 tokens 键入 `(issuer, mcp_resource_url)`.
- `tools`: 该 MCP 带有每个要求的范围的工具列表。

显示 :

1. **拒绝的大门** 拒绝接线,如果任何困难情况发生,停止:
   - `S256` 丢失的 `code_challenge_methods_supported` (PKCE 具有无退化模式)。
   - `authorization_code` 丢失的 `grant_types_supported`.
   - `response_types_supported` 绝对是 `["code"]`.
   - 没有注册路径: 没有预登记的路径 `client_id`, `client_id_metadata_document_supported: true`,或有一个已折旧的 DCR 兼容端点。
   - CIMD是被选中的,但 `client_id` 绝对不是 HTTPS 文档中带有路径的 URL, 与文档 URL 不匹配, 或者文档缺少非空白 `client_name` 或 `redirect_uris` array. `application_type` 可供 CIMD 选择。
   - 退回的RFC 9207 `iss` 与重定向前记录的发行者不同,或在服务器作为支持广告时被忽略。
   - 折旧的 DCR 缺乏 `application_type`或其调整的URI政策与 `native` 或 `web`.

2. **保护资源元数据文档** 财政年度(9728) MCP 服务器。对于带有路径的资源,请在该路径之前插入已知的段数 : `https://host/team/mcp` 地图 `https://host/.well-known/oauth-protected-resource/team/mcp`。包含 `resource`, `authorization_servers` (发行者许可清单) `scopes_supported`, 和 `bearer_methods_supported: ["header"]`.

3. **HTTP endpoints.**
   - `GET /.well-known/oauth-protected-resource` - 从(2)返回文件。
   - `POST /mcp` (该 stateless MCP 运输:验证持单人 token ,在任何工具发送前,请按此请求。
   - 只允许 DCR 兼容性 : `POST /register`,在前方进行程序类型检查和费率限制检查。

4. **背景工作+常规。**
   - 预定的 JWKS 刷新, 重新弹出 `jwks_uri` 进入缓存 `{keys, fetched_at}`。同上,请勿使用薄荷键。AS 旋转;资源服务器仅进行更新。 `0 */6 * * *`; 收紧到 `*/15 * * * *` 高旋转IDPs。
   - 一个 `validate` 例行检查 `iss` 允许列表, 与缓存的 JWKS 签名, `aud == mcp_resource_url`, `exp`,要求范围。
   - 逐步发放路径——只有当工具清单包含以用户最初不批准的范围为后盾的操作时。

5. **缓冲计划** 被接受的发行者中, `issuer`,按住键 `{keys, fetched_at}`文档显示读取模式:验证符读取缓存,然后返回到同步刷新 `kid` 小姐( 重新拉伸, 不旋转- 再拉伸是一等的, 不能变成一个关键创建 DoS ) 。

6. **范围图。** 将每个工具都映射到它所需的范围。输出一个表格 :
   `| tool | required_scope | rationale |`。在其自身范围内组装破坏性工具;不得再使用读写工具的镜像。

7. **运行时拒绝规则** (验证人必须编码这些):
   - 拒绝时间 `aud != mcp_resource_url` → 401 `Bearer error="invalid_token", error_description="audience mismatch", resource_metadata="<prm_url>"`.
   - 拒绝时间 `iss not in authorization_servers`.
   - 拒绝时间 `kid` 在一个重新拉伸后退后后,没有在缓存的 JWKS 中。
   - 拒绝要求的范围 `Bearer error="insufficient_scope", scope="<required>", resource_metadata="<prm_url>"`.
   - 未经S256批准而拒绝任何授权请求 `code_challenge`,并拒绝任何 token 请求 `code_verifier`,客户端, 重新定向 URI, 或 `resource` 与一次性授权代码记录不符。
   - 拒绝任何证书或 token 发行者不匹配其证书库密钥。 发行者更改需要新的注册 。

拒绝(绝不接受任何此类要求——拒绝请求和文件原因):

- Storing `client_secret` 公共客户使用 `token_endpoint_auth_method: none`; 用户使用保密信息 `private_key_jwt`。没有简洁的文本共享秘密 rest 或登记回复日志中。
- 跳过 `aud` 检查验证符。 观众约束( 访问- )token 限制特权)是RFC 8707+RFC 9728的全部理由。
- 将 JWKS 缓存错误的后退线连接到旋转和最小, 而不是再拉伸。 它从不生成缺失的 `kid` 并让攻击者控制 `kid` 值强制不锁定密钥创建。 返回必须是一流的刷新 。
- Allowing PKCE- 无需授权代码 OAuth 2.1 禁止;验证人必须拒绝任何 `/token` 缺少 `code_challenge`.
- 正在抓取 JWKS , 但没有刷新工作。 要么预定的刷新船, 要么 认证表面不部署 。
- 相信自己 `iss` 接受 a/ token 中选择 `iss` 让攻击者站起来 伪造自己的IP tokens.
- 向入境者前进 MCP token 向上游 API (token 。如果 MCP 服务器在上游调用 APIs 须获得自己的独立 token; 传递造成混乱的副作用问题。
- Storing `registration_access_token` 简洁的文字。rest;要求每次更新都提供明确文本。
- Treating MCP 2026-07-28运输为无国籍;验证并批准每一项请求。

输出: 带有受保护资源文件、 发行人键入的注册版式、 发行人和资源的一页计划 token 版式, 选择的注册路径, HTTP 端点, JWKS 刷新工作、 范围映射和运行时拒绝规则。 以授权服务器实际元数据中第一个未完成的部署门结束 。
