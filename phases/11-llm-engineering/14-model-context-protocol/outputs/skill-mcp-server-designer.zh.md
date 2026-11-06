---
name: mcp-server-designer
description: Design a stateless MCP 2026-07-28 server with explicit discovery, state, transport, and safety contracts.
version: 2.0.0
phase: 11
lesson: 14
tags: [llm-engineering, mcp, stateless, tool-use]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定域( 内部) API,数据库,文件源)和将挂载服务器的主机,输出:

1. 原始地图。 哪些能力成为 `tools` 行动),成为 `resources` (只读数据),成为 `prompts` (用户使用的模板) 原始文本一行
2. 发现合同。 `server/discover` 使用执行支持、能力、服务器身份、指令的准确版本, `ttlMs`, 和 `cacheScope`.
3. 请求合同。 需要字符串协议版本和对象客户端能力 `params._meta` 依要求, 建议客户身份 。 返回无效的参数 (Param)`-32602`),用于丢失或错误类型所需的元数据。 `UnsupportedProtocolVersionError` (`-32022`) 与 `data.supported` 和 `data.requested` 仅对服务器未执行的提供版本字符串 。
4. 结果合同。 `resultType`,服务器身份元数据,确定列表的排序,以及每个适用结果的缓存策略。
5. MRTR 计划。 `input_required` 仅用于 `tools/call`, `resources/read`, 或 `prompts/get`中至少包含一个 `inputRequests` 或不透明 `requestState`; 使用新 JSON-RPC ID, 请求时相应的输入回复, 以及准确的 state value 此时此刻
6. 状态计划。 对于每个多调工作流, 请定义一个以服务器为最小的不透明控点作为普通工具参数。 不要隐藏连接或协议会话背后的状态 。
7. 运输和认证计划。选择标准或2026-07-28流 HTTP POST 端点。 HTTP,定义源代码验证和每个请求授权。 `MCP-Protocol-Version` 要求, `Mcp-Method` 在 JSON-RPC 请求, `Mcp-Name` 仅用于 `tools/call`, `resources/read`, 和 `prompts/get`。一个被接受的通知 POST 返回 HTTP 202没有尸体
8. 书状草稿。 写 JSON 每个工具的图示 parameter,并配有用于选择模型的描述和用于不可信输入的清晰界限。
9. 破坏动作列表。 标记每个突变工具 `destructiveHint: true` 需要人的同意
10. 核查计划。 JSON-RPC 响应、错误的信封和请求标识、元数据拒绝、发现、确定列表、版本不匹配、缓存字段、信头对身体不匹配、授权、批准和1 prompt-注射病例

拒绝使用的设计 `initialize`, `notifications/initialized`, `Mcp-Session-Id`,独立 HTTP GET, HTTP 确定,或 `Last-Event-ID` 允许这些装置只进入一个清晰的适应器, 用于到2025-11-25年的协议版本。 Roots, Sampling,或登录到新的执行;兼容性支持必须标出并 Roots 或 Sampling 输入必须使用 MRTR。拒绝一个写入磁盘或调用外部服务器 API 未经批准,验证,批准路径。
