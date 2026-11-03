---
name: mcp-transport-migrator
description: Migrate legacy MCP HTTP transports to the stateless, POST-only 2026-07-28 contract.
version: 2.0.0
phase: 13
lesson: 09
tags: [mcp, streamable-http, stateless, migration, headers]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以会议为基础流体 HTTP 或 HTTP+SSE 服务器,为 MCP `2026-07-28`.

显示 :

1. 终点地图。 定义一个现代 MCP 接受 PST 的终点。 JSON-RPC 请求或通知可接收新的函授通知。
2. 反应图。 `application/json` 答复或请求范围 `text/event-stream` 之后是最后答复。
3. 已经消除的行为。 `405` 现代的Get和Delet。 `Mcp-Session-Id` 和 `Last-Event-ID`; 永远不要薄荷, 反响, 撤销, 或者恢复它们 。
4. 请求元数据。 需要每个机构的协议版本和客户能力 `_meta`,建议客户身份。
5. 页眉验证。 需要 `MCP-Protocol-Version`, `Mcp-Method`,且有条件 `Mcp-Name`。解码 Base64 哨兵,并将信头与尸体进行比较。 `-32020` 返回时 `-32022` 在一个不支持的匹配版本中使用精确的数据键 `supported` 和 `requested`.
6. 订阅迁移。替换独立获取, `resources/subscribe`, 和 `resources/unsubscribe` 与 Post 连接 `subscriptions/listen`。标记确认、每份通知和最后结果 `io.modelcontextprotocol/subscriptionId` 等于倾听请求的代号。
7. 国家移民:用明确、不透明的应用程序取代连接关系,处理程序与经认证的委托人有关。
8. 兼容性窗口。 保持旧端点分开并清晰标记。 在任何遗留的后退之前必须检查现代 POST 错误。 不要将 POST 重新定向为 `301` 或 `302` 因为方法和身体保护不安全
9. 验证。 测试源拒绝, POST 媒体谈判, 机构元数据, 反射信头, JSON 答复、接受的通知 `202` 没有物体, 范围覆盖 SSE 订阅元数据, Get and DELETE `405`,忽略了删除的页眉,用新的ID进行断流重试。

艰难的拒绝 :

- 展示会话的ID, 独立获得, DELETE, 或者重播作为现代行为。
- 通过进程或连接内存共享每个请求的能力。
- 发送服务器启动中 JSON-RPC requests.
- 与 `Last-Event-ID`.
- 在一个公认的现代错误之后,又回到了遗产。
- 使用重定向移动 JSON-RPC 移民期间的POST。

拒绝规则 :

- 拒绝公开曝光,没有认证、授权和确切的原产地政策。
- 拒绝隐藏粘性路径, 以替代明确的工作流程状态 。
- 拒绝自动重试非全权操作,无需申请 idempotency control.

输出一个前后的终点表,已分阶段 rollout, rollback 边界, 以及可执行的符合性检查。 结束于要删除遗留路径的确切日期 。
