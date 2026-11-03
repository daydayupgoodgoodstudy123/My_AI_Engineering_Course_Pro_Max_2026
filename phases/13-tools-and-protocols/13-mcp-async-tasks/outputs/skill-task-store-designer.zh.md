---
name: task-store-designer
description: Design durable MCP work with the current Tasks extension, stateless requests, explicit ownership, polling, input updates, and cancellation.
version: 2.0.0
phase: 13
lesson: 13
tags: [mcp, tasks, extension, durable-state, stateless]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设计长期 MCP 工作权 `io.modelcontextprotocol/tasks` extension.

显示 :

1. 资格决定。 解释为什么操作需要任务而不是同步 `tools/call`.
2. 能力合同。 显示准确 `supportedVersions`能力, 能力, `ttlMs`, 和 `cacheScope` 在 `server/discover`,加上按要求客户能力分列的任务扩展。如果工具被公布,则包括强制性的确定性 `tools/list` 带有有效对象的描述符 `inputSchema`,服务器身份元数据,以及缓存提示。 `-32021` 以 a 为单位 `requiredCapabilities` 对象,当扩展名不存在时,并且 `-32022` 准确 `supported` 和 `requested` 不支持版本的数据 。
3. 创建交易。 任务持续到 `tasks/get` 能够解决它,然后返回服务器方向 `resultType: "task"`.
4. 状态形状。 包含 `taskId`, `status`, `statusMessage`,ISO 时间戳, `ttlMs`, `pollIntervalMs`,权威所有人,原始操作参考,结果或错误,未完成的输入请求,以及所有已发输入键。 `CallToolResult` 需要的 `resultType: "complete"` 并应该包括它自己的 `io.modelcontextprotocol/serverInfo` metadata.
5. 当前方法。 定义 `tasks/get`, `tasks/update`, 和 `tasks/cancel`. 供流用 HTTP,每套请求 `Mcp-Name` 以 `params.taskId`。不介绍 `tasks/status`, `tasks/result`, 或 `tasks/list`.
6. 输入继续。 MRTR 创建后 `tasks/get` plus `tasks/update`需要使用寿命单一输入键和部分响应处理。
7. 易变计划。 选择原子文件系统存储、 交易数据库或共享队列和存储。 包括工人租赁和重新启动行为 。
8. 所有权政策: 授权使用每一种任务方法和租户与委托人订户, 绝不将任务身份知识视为许可。
9. 取消合同:承认是合作性的,不得导致 `cancelled`.
10. 通知选项。 使用 `subscriptions/listen` 和 SSE 流 `notifications/tasks`,以投票作为基准。 `io.modelcontextprotocol/subscriptionId`,等于在确认和每项任务通知中倾听请求的代号。 JSON-RPC 回复; 已接受 HTTP 收到通知 `202` 没有尸体
11. 过期政策。 解释 `ttlMs` 来定义清洗行为 避免泄露另一个租户的任务是否存在
12. 迁移图。 用当前扩展流替换客户端要求的任务标记和删除的实验方法 。

艰难的拒绝 :

- 返回任务处理,然后才能持久阅读可见度。
- Returning `resultType: "task"` 请求中未公布延期内容。
- 使用 `params._meta.task.required`, `tasks/status`, `tasks/result`, 或 `tasks/list` 作为当前 API.
- 使用 `initialize`, `Mcp-Session-Id`,粘贴路径,或隐藏的运输会话状态作为任务商店。
- Treating `tasks/cancel` 承认为工人停止工作的证据。
- 重用一个 `inputRequests` 键在一个任务寿命期内。
- 将任务归还给一个不是其权威主人的打电话者。
- 通过独立获取、会话 SSE 或 `Last-Event-ID` replay.

拒绝规则 :

- 拒绝快速检查任务,除非打电话者给出具体持久性要求。
- 当工作必须生存时拒绝只使用模拟生产仓库, 重新启动 。
- 拒绝无约束结果有效载荷; 将大型文物储存在外部, 并归还授权的资源处理器 。
- 拒绝没有明确的房客所有权的历史终点、过滤、页数和保留政策。

输出一页的设计,包括生命周期表、电线方法、持久性交易、所有权规则、输入流、投票顺序、取消语义、订阅选项、过期清理、故障模型和遗留的迁移图。
