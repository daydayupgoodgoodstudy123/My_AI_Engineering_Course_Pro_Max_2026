---
name: mcp-threat-model
description: Threat-model an MCP 2026-07-28 deployment across metadata, routing, authorization, MRTR, and compatibility boundaries.
version: 2.0.0
phase: 13
lesson: 15
tags: [mcp, security, stateless, tool-poisoning, mrtr]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 MCP 进行部署,提出证据 threat model。假设任何服务器、软件包、缓存、登记条目或网关路径都可能受损。

<a id="required-inputs"></a>

## 所需投入

- 客户、网关、服务器、授权服务器和登记册 trust boundaries.
- 完成工具的常规描述符和已核准的摘要。
- 认证主机、发行人、受众、范围以及工具政策。
- 接受目前和遗留的议定书修订。
- MRTR 操作,输入计划, 国家保护和重播政策。
- 缓存范围、TTL、订阅路线和审计保留。

<a id="produce"></a>

## Produce

1. 线性验证。 验证每个请求的版本和能力, 然后在版本支持之前对路由标题进行平等 。 HTTP 400 `-32020` 以不匹配为目的 HTTP 400 `-32022` 具有准确支持和请求的数据,用于不支持的匹配版本, HTTP 404 `-32601` 以及202个空体 用于接受的通知
2. 描述性审查。报告中毒指标、全描述性消化器变化、未知工具以及计划或注释变化。
3. 命名空间映射。 为每个后端工具提供一个合格的公共名称, 并拒绝静态碰撞分辨率 。
4. 授权矩阵。 地图已验证主机和资源、 工具、 参数限制和范围等的发行程序。 不使用 `clientInfo` 或 `serverInfo` 身份,你应该知道
5. MRTR 审查. 确认每个 `inputRequests` 条目是完整嵌入的请求, 由客户端声明的能力支持。 treat `elicitation: {}` 作为一种隐含形式支持和 `elicitation: {form: {}}` 格式支持。仅拒绝 URL elicitation 与 HTTP 400 `-32021` 和 `data.requiredCapabilities.elicitation.form`装订保护 `requestState` 来进行方法、工具、精确参数、主控、目的、过期和无。 `inputResponses` 键入后, 原子消耗每个处理器都共享的、 被绑定的 TTL 打印的重放仓库中的无环 。
6. 风险轴审查。 标记任何将不信任的输入、 敏感数据及相应动作结合起来的自动步骤 。
7. 缓存和订阅审查。 确保基于用户的结果是私有的,且使用长时期通知 `subscriptions/listen`.
8. 兼容边界 。 隔离任何旧的握手、 会话、 Get slow、 服务器回调或实验性任务行为 。
9. 运输边界. 确定执行是否完整 HTTP 适配器或进程内协议模型。 连接模式到 9 课 JSON 内容类型和 JSON + SSE 接受验证。
10. 补救令,给三个最高作用的解决方案 加上业主和验收证据

<a id="hard-rejects"></a>

## 艰难的拒绝

- 沉默工具根据发现命令覆盖或选择路径 。
- 更新说明摘要,不由人或政策重新批准。
- 将自报客户端或服务器信息作为认证处理 。
- 将申报的能力视为许可。
- 信任简洁文本或未签名 `requestState` 以采取相应行动。
- 将唯一的重放分类账保存在一个网关或服务器实例中 。
- Keying rate limits 或批准国 `Mcp-Session-Id`.
- 提出已折旧 Sampling, Roots、 记录或遗留问题 HTTP 加上SSE作为新的执行路径。

<a id="output-format"></a>

## 输出格式

返回区域名称 Trust Boundaries,电线调查,描述性调查,路线图,授权矩阵, MRTR 发现、兼容性发现和补救。 将证据与假设分开, 结束于目前跨越最大边界的单一攻击路径 。
