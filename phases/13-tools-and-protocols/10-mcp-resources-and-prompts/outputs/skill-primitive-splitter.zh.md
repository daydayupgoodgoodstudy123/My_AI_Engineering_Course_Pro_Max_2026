---
name: primitive-splitter
description: Review an MCP server design and separate tools, resources, prompts, caching, and subscriptions using the 2026-07-28 contract.
version: 2.0.0
phase: 13
lesson: 10
tags: [mcp, resources, prompts, subscriptions, caching]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


审查拟议 MCP 从消费者的角度服务器 。

显示 :

1. 一个 `server/discover` 输出广告版本 `2026-07-28` 以及确切的资源和 prompt capabilities.
2. 表格用 `name`, `chooser`, `primitive`, 和 `reason`.
3. 稳定的资源 URI 计划和任何封闭的资源模板。
4. Prompt 名称、描述和要求或任择参数。
5. 每一个列表方法的确定性排序规则。
6. 缓存策略 `ttlMs` 和 `cacheScope` 用于每个可缓存结果。
7. 一个 `subscriptions/listen` 用于过滤需要更新的资源或列表更改 。
8. 一个返回的无效资源示例 JSON-RPC `-32602`,加上一个返回的无支持的校正示例 `-32022` 与 `supported` 和 `requested`.

使用这些决定规则:

- 模型选择操作是一个工具。
- 主机可读 URI 地址内容是一个资源 。
- 用户选择的信件工作流程是 prompt.
- 客户端打开更新流 `subscriptions/listen`.
- 听请求的ID变成 `io.modelcontextprotocol/subscriptionId`.
- 必须在签署协议的所有事件之前予以承认。
- 通知从不绕过授权,以后阅读。
- `server/discover` 即使客户选择先调用另一种方法, 也强制使用。

拒绝设计时:

- 列表因连接历史而不同 。
- 私家产品被放置在公共缓存中。
- 接受资源 URI, 不进行解析、 授权和边界检查 。
- 设计用途 `resources/subscribe` 或将订阅视为礼宾会议。
- 一个 prompt 允许推翻信任的主机指令。

返回一页的合同审查。 以风险最高的原始、 缓存或订阅错误和最小的更正结束 。
