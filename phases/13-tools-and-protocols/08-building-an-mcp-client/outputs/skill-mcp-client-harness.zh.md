---
name: mcp-client-harness
description: Scaffold a multi-server MCP client with modern metadata, safe era negotiation, deterministic merge, and routing.
version: 2.1.0
phase: 13
lesson: 08
tags: [mcp, client, stateless, compatibility, routing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给出了列表 MCP 服务器传输, 生成客户端 harness 喜欢 MCP `2026-07-28` 并分离出遗留的兼容性。

显示 :

1. 对等配置。 将稳定的服务器名称映射为固定的指令或端点、 参数、 环境允许列表、 授权背景、 运输类型和明确的 `allow_legacy` 标记默认为假的 。
2. 现代请求构建器。 印章协议版本、 当前客户能力以及推荐客户身份到每个 `params._meta` 紧接着连环化
3. 标准时代探测器。 发送 `server/discover` 首先,接受一个有效的发现Result, 重试 `-32022` 并治疗 `-32020` plus `-32021` 是一种现代错误
4. 遗留兼容性检测。 将一个未识别的错误、 超时、 连接关闭或空响应视为模糊 。 发送一个有时间限制的 `initialize` 只有当那个对等点 `allow_legacy: true`。仅在相关之后选择遗产 JSON-RPC 成功包含已配置的遗留版本、 对象能力和非空白服务器身份。 否则会关闭 。
5. 工具缓存。 荣誉 `ttlMs` 和 `cacheScope` 处理没有的遗产 `resultType` 作为 `"complete"`.
6. 命名空间合并。 排序对等方和工具。 前面或后面拒绝碰撞。 禁止沉默覆盖 。
7. 路由器。 地图卡通工具名称, 以对等点加本地名称, 创建一个新的请求代号, 发送时间校正请求, 并验证响应代号 。
8. 恢复:运输损失、飞行中故障、重新开始或重新连接、重复发现和列出、重新订阅,以及只重试安全政策允许的操作。

艰难的拒绝 :

- 发送不切实际的现代请求 `_meta`.
- 在一个公认的现代错误后又回到初始化。
- Sending `initialize` 给没有明确允许列出遗留兼容性的对等点。
- 将超时、连接关闭、空响应、未确认的错误、错误的结果或未经支持的修订作为遗产行为的证明。
- 处理过程、连接或 `Mcp-Session-Id` 现代协议状态
- 共享一个私人缓存列表, 跨越授权范围 。
- 静悄悄地覆盖一个重复的工具名 。
- 接受现代的成功而不 `resultType`.

拒绝规则 :

- 拒绝在固定的许可名单之外生成命令 。
- 当拥有者模棱两可时拒绝使用工具。
- 拒绝自动重试非全能的呼叫,无需应用程序 idempotency 键或用户决定。

输出完整 Python harness,至少6个符合性测试,以及一份启动报告,其中列出对等点、选定时代、选定版本、缓存范围以及卡通工具名称。
