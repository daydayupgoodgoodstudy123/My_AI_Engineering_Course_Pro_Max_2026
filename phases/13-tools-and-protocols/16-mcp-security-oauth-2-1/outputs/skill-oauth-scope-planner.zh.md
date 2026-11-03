---
name: oauth-scope-planner
description: Design MCP 2026-07-28 authorization with CIMD, issuer isolation, resource indicators, and step-up scopes.
version: 2.0.0
phase: 13
lesson: 16
tags: [mcp, oauth, cimd, pkce, issuer, resource-indicators]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给远程 HTTP MCP 服务器及其工具列表,设计完整的授权边界。

<a id="required-inputs"></a>

## 所需投入

- Canonical MCP 资源 URI 和 保护资源元数据位置 。
- 允许授权服务器发行器 。
- 客户运行时间: 本地或网络, 精确重定向 URI 。
- 工具到范围绘图和相应操作。
- Token和证明文件的保存限制
- 缺少CIMD的遗留授权服务器

<a id="produce"></a>

## Produce

1. 资源元数据。 `resource`, `authorization_servers`, 和 `scopes_supported`。保存在已知段之后的资源路径,例如 `https://notes.example.com/.well-known/oauth-protected-resource/mcp` 用于 `https://notes.example.com/mcp`.
2. 发行政策. 国家允许的发行者、元数据验证、变更处理和RFC 9207 `iss` comparison.
3. 输入。 使用备查的预登记, 否则更喜欢客户名 ID 元数据文档 。 HTTPS 路径为 URL `client_id`;要求精确重定向 URI ,并将显示的元数据作为不信任处理。 `application_type` 这里可选 。
4. DCR 后退。 如果需要, 标签它会贬值, 声明 `application_type`,并定义允许退缩的确切条件。在通用 CIMD 安全故障后,不要降级。
5. 预先登记和记录管理证书,在签发人和 tokens under `(issuer, resource)`。声明自托管的 CIMD URL 是可移动的,当受信任的发行者更改时不需要重新注册。
6. PKCE 需要 S256 精确重定向 URI、授权响应发布器验证以及相同资源 token requests.
7. 范围模型,将每个工具都绘制到最小范围。 `WWW-Authenticate` 具有权威性的范围挑战。
8. 逐步增加的经验。 确定额外范围、 用户解释、 同意点、 新授权, 并重新尝试 MCP 请求编号。
9. 资源服务器检查。 执行已公布 `tools/list` 具有有效的对象根图、 确定顺序、 结果类型、 服务器身份和缓存提示。 校验发行者、 观众、 过期时间、 范围、 当前 MCP 页眉, 并请求元数据后再发送工具 。
10. Token 卫生。 只用小标题, 没有查询 token, 否 token 过关,秘密的更新存储, 和旋转计划。
11. 错误合同。 保存所有请求代号 JSON-RPC 错误信封, 包括 OAuth 失败。 需要 HTTP 400 `-32020` 格式化 HTTP 400 `-32022` 版本支持检查, 精确支持和请求数据, HTTP 404 `-32601` 以及202个空体,供接受通知。
12. 传输边界。 标签解析体示例作为进程内协议模型, 并附加到 9 课的完整流流 HTTP 适配器 JSON 内容类型和 JSON + SSE 接受验证。

<a id="hard-rejects"></a>

## 艰难的拒绝

- 儿童康复中心被作为首选的新入学机制提出。
- 没有 DCR `application_type`.
- 重新使用签发人记号登记证书,查阅 tokens,或刷新 tokens 发行者更改后。 自定义的 CIMD URL 是可移动的例外, 而不是发行者记号的秘密 。
- 授权回复的正常化 `iss` 比较之前。
- Missing PKCE S256或失踪 `resource` 授权和 token requests.
- 接受a token 或转发 MCP token downstream.
- 使用 `clientInfo`, `serverInfo`,能力,或删除的协议会话作为认证。
- Adding OAuth 仅用于模仿远程 HTTP.
- 构建 RFC 9728 元数据 URL 时丢弃受保护的资源路径 。
- 将一个简单的文字或特定对象还给 MCP 请求错误, 而不是 JSON-RPC 信封上写着相同的ID

<a id="output-format"></a>

## 输出格式

返回区域名称为资源、发行者、注册、证书存储处 PKCE 流程、 范围矩阵、 跳跃、 服务器验证 Token 卫生,和兼容性。结束精确的事件 强制发行者审查, 对于发行者客户, 重新加入。
