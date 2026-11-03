---
name: gateway-bootstrap
description: Design a stateless MCP 2026-07-28 gateway with registry admission, policy, routing, and compatibility boundaries.
version: 2.0.0
phase: 13
lesson: 17
tags: [mcp, gateway, stateless, registry, rbac, subscriptions, tasks]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于客户、后端、授权要求和合规限制,设计了一个网关。

<a id="required-inputs"></a>

## 所需投入

- 公共网关资源 URI, 接受协议修订, 以及运输。
- 认证的校长和榜样。
- 后端端点、发行者、资源、登记记录、出版人证据和经核准的描述。
- 工具可见度、论证政策、成本类别和数据敏感性。
- Streaming,变更通知, MRTR以及任务要求。
- 审计、保留、 trace和编辑要求。

<a id="produce"></a>

## Produce

1. 无国籍的入侵。 POST 端点, 请求的版本和能力, 匹配的方法和名称标题, JSON 或请求范围 SSE, 以及用于现代 Get 和 DELETE 的 405。 验证版本支持前的标题平等 。 请指定 HTTP 400 `-32020`, HTTP 400 `-32022` 附有确切支持和要求的数据, HTTP 404 `-32601`,可选错误数据序列化,以及202个空体通知处理。
2. 发现计划。 执行网关 `server/discover`,发现每个后端,只暴露安全的端对端能力交叉点,并包括当前 `resultType`, `ttlMs`, `cacheScope`,以及服务器身份元数据。
3. 正式书记官处确认 `server.json` 出版形状和 `com.example/*` 样式名称与安全输入分开。 对于每一个后端, 加入到外部验证的出版商名域、 来源、 终点、 版本策略、 描述性摘要、 发行者、 资源、 批准和过期状态 。
4. 命名空间映射。 给每个后端工具一个稳定的合格公共名称并保留一个有效的对象根 `inputSchema` 在每个 `tools/list` 描述,按顺序拒绝碰撞
5. 授权矩阵。 映射公共工具、 资源、 参数和范围的主机和作用。 保持外部和后端证书的单独和发行者限制 。
6. 转发合同。 建立一个全新的自足后端请求, 广告只包含客户端能力, 验证后端结果并保存 trace correlation.
7. 缓存计划。 使主要依赖的发现和列表为私有。 设置约束 TTL 和无效行为 。
8. 费率和审计政策。 由主机、 发行人、 资源、 工具、 成本类别和时间等关键限制。 重写证书和不必要的敏感参数 。
9. 互动路径。 描述请求范围 SSE, `subscriptions/listen` 承认和重新连接行为,字节精确 MRTR 状态转发, 任务路径由任务编号 : `Mcp-Name`.
10. 传输适配器。 如果网关收到解析请求和信头, 标签为在轨协议模式, 并将其连接到 9 课程 JSON 内容类型和 JSON + SSE 接受执行。
11. 兼容适配器。 栅栏老化初始化、 会话代号、 获取流、 资源订阅和实验任务方法 远离现代网关核心 。

<a id="hard-rejects"></a>

## 艰难的拒绝

- 2026-07-28年按要求提交的届会亲和、届会储存或会话编号重写。
- 信任登记处的存在或显示名称,而无需提供供认证据。
- 静默工具碰撞或描述针更新,无需重新批准。
- 重新使用外持者 token 后端或后端 token 或资源。
- 公开存取一份主过滤列表 。
- 独立现代 Get 事件流、 最后- 晚上ID 重播或资源订阅方法 。
- New `tasks/list` 或 `tasks/result` behavior.
- Rate limits 只用删除的协议会话键。
- 内部发明的安全核查 `server.json` 而不是单独确认的入境和出处状态。
- 忽略的命名空间工具描述符 `inputSchema`.

<a id="output-format"></a>

## 输出格式

返回区域名称为 Ingress, 发现、 接收、 命名空间映射、 授权、 转发、 快取 Rate Limits,审计,互动和遗产适应。最后一条路径需要最强烈的接受测试。
