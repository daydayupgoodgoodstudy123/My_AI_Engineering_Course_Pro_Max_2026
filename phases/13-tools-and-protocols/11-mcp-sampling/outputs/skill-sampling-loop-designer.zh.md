---
name: sampling-loop-designer
description: Migrate model-assisted MCP tools to direct inference or stateless 2026-07-28 MRTR with bounded compatibility sampling.
version: 2.0.0
phase: 13
lesson: 11
tags: [mcp, mrtr, sampling, stateless, migration]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设计模型辅助行为 MCP 服务器目标协议修订 `2026-07-28`.

以一个决定开始:服务器能否直接与模型提供者整合? Sampling 更倾向于直接整合,除非使用客户的模型和证书是明确的产品要求。

显示 :

1. 结构决定。 选择直接 inference 兼容性 Sampling 并说为什么。
2. 发现合同。 显示 `server/discover` 准确 `supportedVersions`、 广告能力, `ttlMs`, 和 `cacheScope`。如果工具被公布,则包括强制性的确定性 `tools/list` 带有有效对象的描述符 `inputSchema`, `resultType: "complete"`,服务器身份元数据,以及缓存提示。
3. 请求信封。 包含协议版本和客户端能力 `_meta` 使用 `-32602` 用于缺少或非字符串版本的, `-32022` 准确 `supported` 和 `requested` 不支持版本的数据, 并且 `-32021` 以 a 为单位 `requiredCapabilities` 对象 Sampling 。 将客户身份元数据作为信息处理。 永远不要发布 JSON-RPC 一份无ID-通知的答复; 一份已接受的 HTTP 收到通知 `202` 没有尸体
4. 圆桌会议。 MRTR 圆, 命名 `inputRequests` 关键、嵌入式请求方法、预期响应方案、验证和预算。
5. 重试合同。 需要原始的方法和参数, 新的 JSON-RPC ID, 当前轮 `inputResponses`字节精确 `requestState`.
6. 国家保护:将HMAC或经认证的加密程序绑在经认证的本金、方法、论据摘要、阶段和短时间失效上。
7. 安全政策 定义批准,最高轮 token 字节限制, 反应验证, 记录和拒绝行为。
8. 清除计划。 Sampling 将它改为直接整合的条件和日期。

艰难的拒绝 :

- 采用折旧的新设计 Sampling 没有任何书面要求。
- 发送的2026-07-28服务器 `sampling/createMessage` 是一个对客户的实时服务器请求 。
- 任何用途 `initialize`, `notifications/initialized`, `Mcp-Session-Id`,或隐藏的协议会话状态。
- Unsigned `requestState` 影响授权、资源获取或商业逻辑。
- 重试, 重新使用原始的 JSON-RPC id 或更改原始参数。
- 客户模式循环,没有能力检查、批准政策、验证和硬圆限制。
- `includeContext: "allServers"` 或隐含的跨服务器上下文。

拒绝规则 :

- 拒绝隐藏模式电话或隐藏服务器意图的任何设计,让用户知道。
- 拒绝将模型输出作为身份、授权或用户同意的证明。
- 拒绝多轮设计 tool call 足够了
- 拒绝将客户端和服务器元数据调用为经认证的身份 。

输出一页结构,包括决定、电路流通、圆桌会议、签署的国家内容、安全预算、故障案例和迁移计划。 `direct inference`, `temporary MRTR compatibility`, 或 `no model required`.
