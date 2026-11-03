---
name: mcp-server-scaffolder
description: Design a stateless MCP 2026-07-28 server with discovery, request validation, and deterministic primitives.
version: 2.0.0
phase: 13
lesson: 07
tags: [mcp, server, stateless, discovery, scaffold]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了域,就生产出现代的 MCP 服务器计划。 保持应用程序的清晰状态, 并保持协议行为无国籍 。

显示 :

1. 原始分割。 定义原子工具、 磁共振处理的资源和有用 prompts。当域没有真正用途时,就抛弃原始的域。
2. 发现结果。 提供 `supportedVersions`,服务器能力,可选指令, `resultType: "complete"`、缓存提示和服务器身份 `_meta`.
3. 请求验证。 需要协议版本和客户能力 `params._meta`。在客户身份出现时验证推荐客户身份。 `-32022` 与请求和支持的版本不匹配。
4. 结果包装。 添加 `resultType: "complete"` 和服务器身份,以取得所有成功。 `ttlMs` 和 `cacheScope` ,查找,列表,模板和资源读取。
5. 排序政策。 为每个列表响应定义一个稳定排序键 。
6. 国家政策。 在数据库中输入耐久状态, 或者返回一个清晰的、不透明的处理器作为正常的工具参数。 永远不要在协议会话中隐藏状态 。
7. 兼容边界。 如果需要遗留支持, 请将 `2025-11-25` 初始化适配器。 仅选择用于遗留的流量, 独立测试两个时代 。

艰难的拒绝 :

- 现代服务器,其第一个有效方法必须是 `initialize`.
- 恢复先前请求中的能力、身份或版本。
- Returning `Mcp-Session-Id` 现代 HTTP traffic.
- 返回列表或资源读取结果,不包含缓存提示 。
- 将说明作为授权控制。
- 发送独立 JSON-RPC 服务器请求 。

拒绝规则 :

- 如果请求的资源未经批准会暴露秘密,请停止并要求发布访问政策。
- 如果一个域没有只读数据,请省略资源而不是发明资源。
- 如果域没有可重复使用的模板, 请略去 prompts 而不是运输填充器。

输出一页的架构、 方法表、 验证伪代码、 结果示例、 确定性排序规则, 以及至少六种符合性测试。 结尾处为应用程序状态和协议状态之间的界限 。
