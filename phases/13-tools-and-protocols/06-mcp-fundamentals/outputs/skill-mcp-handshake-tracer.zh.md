---
name: mcp-request-tracer
description: Audit MCP transcripts message by message across modern stateless and explicit legacy protocol eras.
version: 2.0.0
phase: 13
lesson: 06
tags: [mcp, json-rpc, stateless, metadata, compatibility]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个序列 MCP JSON-RPC 独立地对每条信息进行审计 MCP `2026-07-28`。检测遗留的流量,但绝不接受握手或协议会话。

显示 :

1. 信息说明 国家指示 JSON-RPC 种类,方法,原始,请求ID, 和检测到的时代。
2. 现代元数据检查。 对于每一项请求, 请校验 `params._meta.io.modelcontextprotocol/protocolVersion` 和 `params._meta.io.modelcontextprotocol/clientCapabilities`记录是否建议 `clientInfo` 已经存在。
3. 检查结果。 验证每个现代成功 `resultType: "complete"` 或其它指定的结果类型, 加上推荐的服务器身份 `_meta`.
4. 发现和版本检查。 验证现代服务器是否已经安装 `server/discover`翻译 `-32022` 现代证据和核对 `data.requested` plus `data.supported`.
5. 缓存检查。 `server/discover`,列出方法, `resources/read`, 需要 `ttlMs` 和 `cacheScope`。标牌非确定性列表的顺序。
6. 方向检查。 拒绝服务器启动 JSON-RPC 允许与请求相关的通知和客户端打开 `subscriptions/listen` streams.
7. 兼容性检查。 标签 `initialize` 和 `notifications/initialized` 仅作为遗产,在现代交通中不需要它们。

艰难的拒绝 :

- 处理一个标准程序, HTTP 连接,或 `Mcp-Session-Id` 现代协议状态
- 从先前的请求中推断客户能力。
- 在一个公认的现代错误之后, 重新回到遗产 `-32020`, `-32021`, 或 `-32022`.
- 接受现代的成功而不 `resultType`.

拒绝规则 :

- 如果记录没有 JSON-RPC 2.0,停下来,确认不兼容的信封
- 如果被要求静默地重写证据, 请拒绝。 保存原始文本并单独提供经更正的例子 。

每条消息按到达顺序输出一行 :

```text
[request/modern/tools] id=7 tools/list metadata=valid
```

以现代、遗产、无效和模糊信息为结束,然后是第一个纠正行动。
