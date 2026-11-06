---
name: mcp-server-platform
description: Design a stateless MCP 2026-07-28 server with registry metadata, live discovery, authorization, policy, audit, and scale evidence.
version: 2.0.0
phase: 19
lesson: 13
tags: [capstone, mcp, stateless, streamable-http, oauth, registry, governance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设计一个 stateless MCP 服务器和管理边界目标协议修订 `2026-07-28`.

构建计划 :

1. 一种计划性有效 `server.json` 其反向 DNS 名称与出版商的认证命名空间相符。
2. Mandatory `server/discover` 用于实时版本、能力、扩展和服务器身份。
3. 每项请求的版本和客户能力 `_meta`; `resultType` 和服务器身份
4. Deterministic `tools/list` 与 `ttlMs` 和 `cacheScope`.
5. 仅 POST 流 HTTP 具有所需的版本、方法和名称标题; 没有协议会话、 Get slow、 会话 DELETE 或重放页眉 。
6. 授权验证每次通话的发行人、观众、过期和范围。
7. 政策结束 actor,工具、目标以及正常参数。将高风险批准绑在精确动作和过期时间上,然后证明改变一个参数是拒绝重放的。
8. 重订审计和 trace 证据不在模型外
9. 验证登记册的调整器 `server.json`,探测器 `server/discover`,并报告元数据/运行时间流。
10. 两个可互换复制品和一个同时装载的探测器,没有会话的亲和性。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 协议正确性 | 无国籍信封、发现、结果、信头和负面案例 |
| 20 | Authorization | 发放者、受众、过期、范围和准确行动核准情况 |
| 15 | 书记官处的完整性 | 有效 `server.json`,现场探测,和漂流报告 |
| 15 | 政策与安全 | 允许、拒绝、错误的认可和敏感数据案例 |
| 15 | 规模 | 两个无亲和依赖性的复制品加上注销和收回 |
| 10 | Auditability | 重订的接收方审计和 trace evidence |

艰难的拒绝 :

- 流体 MCP 设计 `initialize`, `notifications/initialized`, 或 `Mcp-Session-Id`.
- Treating `server.json` 即是现场能力发现或发明 `.well-known/mcp-capabilities` 以 an 为单位 MCP requirement.
- 在为该出版商认证的命名空间外发布服务器名称。
- 接受a token 未经发行人和受众或资源验证。
- 将工具注释或聊天批准视为授权。
- 长期存在秘密或原始敏感数据的审计记录。

拒绝规则 :

- 拒绝要求只从当地模拟中进行生产准备。
- 拒绝披露一种改变国家的工具,而没有政策和有行动约束的核准证据。
- 拒绝发布指向无法校验其现场发现端点的元数据。

产出:构建一个包含出版物元数据、现场发现、无国籍运输、工具图案、授权、政策、批准、审计和规模的计划和证据矩阵。 结尾处为最高风险边界和证明失败的精确故障测试。
