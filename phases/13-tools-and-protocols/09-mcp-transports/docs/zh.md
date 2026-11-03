<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-transports-stdio-and-stateless-streamable-http"></a>

# MCP 传输：stdio 与无状态 Streamable HTTP

> 运输 MCP 信件。 它不提供缺少的协议状态。 in `2026-07-28`,本地平坦和远程流 HTTP 两者都含有自我描述的请求。

**类型:** 学习
**语言:** Python
**先修要求:** 第13阶段,第07和08期
**时间:** ~65分钟

<a id="learning-objectives"></a>

## 学习目标

- 选择本地儿童进程和可流的 stdio HTTP 网络服务。
- 执行现代单端点, 仅POST 流 HTTP contract.
- 镜像和验证 MCP 版本、方法和名称标题 JSON-RPC body.
- 交付请求范围广的SSE和长寿 `subscriptions/listen` 流正确 。
- 迁移会议和遗产 HTTP+SSE部署,没有将遗留行为作为现代。

<a id="the-problem"></a>

## 问题

早期可流 HTTP 修改连接和会话行为协议的合并谈判。 服务器可以最小化 `Mcp-Session-Id`,并使用 SSE 恢复 `Last-Event-ID`.

MCP `2026-07-28` 每一个请求都可以降落在任何健康的工人身上,因为其协议版本和客户能力都出现在请求机构。 HTTP 页眉反射选择的路线和政策字段,但服务器在执行前验证页眉对正文。

其结果是更容易测量和解释的。 这也意味着一个服务器在教授2025年的交通时,当它流传时,它正在教授错误的故障和安全模式。

<a id="the-concept"></a>

## 概念

<a id="stdio"></a>

### stdio

标准装订是客户端发射的子进程:

- 客户端写一个 UTF-8 JSON-RPC 每行消息到标准输入 。
- 服务器写入一个 UTF-8 JSON-RPC 一条线到 stdout 。
- 服务器将诊断书写给Stderr。
- 服务器在标准 EOF 上迅速退出 。
- 每一个现代请求都包含版本和客户能力 `params._meta`.

程序可能存在许多电话, 但这不是一个现代协议会话。 如果它意外退出, 则丢失飞行中的请求 。 重新启动进程、 重新发现、 重新列表、 重开订阅, 并用新的请求代号重新尝试安全操作 。

<a id="streamable-http-in-2026-07-28"></a>

### Streamable HTTP 2026-07-28年 内

现代服务器曝光 MCP 终点,例如 `/mcp`,这接受POST。

每个 JSON-RPC 请求或通知是新的 HTTP 胸腔,身体里有一个 JSON-RPC 消息。 客户端不发送 JSON-RPC 对服务器的反应 。

请求时, 服务器返回 :

- `Content-Type: application/json` 以一个 JSON-RPC 反应;或
- `Content-Type: text/event-stream` 之后是最后通知, JSON-RPC response.

对于被接受的通知, 服务器返回 `202 Accepted` 没有尸体

客户在广告中刊登两种反应类型:

```http
Accept: application/json, text/event-stream
```

<a id="post-only-means-post-only"></a>

### 仅 POST 表示仅 POST

现代流 HTTP 没有独立的 Get slow 和 DELETE 会话的终点 。

- `GET /mcp` 返回 `405 Method Not Allowed`.
- `DELETE /mcp` 返回 `405 Method Not Allowed`.
- `Mcp-Session-Id` 被忽略,从不拆卸或回响。
- `Last-Event-ID` 被忽略,因为现代流是不可恢复的。

如果在请求范围过宽的流流最后回复之前中断,客户端已丢失该飞行请求。 它可能发布新的请求并使用新 JSON-RPC 重试安全时的id。 它不能尝试恢复流。

<a id="origin-validation"></a>

### 来源验证

服务器验证 `Origin` 连接到的连接,以防止 DNS 重新绑定。如果信头存在,且没有明确允许,则返回 `403 Forbidden`。非浏览客户端可以省略 `Origin`,官方运输规则允许。

本地服务器应绑定到 `127.0.0.1`,而不是每个接口。网络服务仍然需要对每一个请求进行认证和授权。源代码验证不是认证。

使用精密源匹配的语法配置。 前缀检查, 如 `origin.startswith("https://trusted.example")` 因为他们可以接受攻击者控制的后缀。

<a id="required-http-metadata-headers"></a>

### 必需 HTTP 元数据标题

现代科技局的每一项要求包括:

```http
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: notes_search
```

页眉规则 :

- `MCP-Protocol-Version` 要求而且必须平等 `params._meta.io.modelcontextprotocol/protocolVersion`.
- `Mcp-Method` 要求而且必须等同 JSON-RPC `method`.
- `Mcp-Name` 需要 `tools/call`, `resources/read`, 和 `prompts/get`.
- `Mcp-Name` equals `params.name`, 或 `params.uri` 用于 `resources/read`.
- 标题值对大小写不敏感,即使标题名称对大小写不敏感。

不安全或无安全 -ASCII `Mcp-Name` 值使用精确的 UTF-8 Base64 哨点 :

```text
=?base64?{Base64EncodedValue}?=
```

服务器在与身体比较之前解码该值 。

丢失、格式错误或不匹配的镜像信头返回 HTTP `400` 与 JSON-RPC code `-32020`。如果信头和正文同意服务器不支持的版本,则返回 HTTP `400` 与 `-32022` 和精确错误数据,例如 `{"supported":["2026-07-28"],"requested":"2027-01-01"}`.

未知的现代方法返回 HTTP `404` 与 JSON-RPC `-32601`. 该 JSON-RPC 物体很重要,因为一个双时代的客户使用它来区分现代错误和遗留端点误差。

<a id="request-scoped-sse"></a>

### 请求范围 SSE

服务器可选择一个长期请求的 SSE :

```text
POST tools/call id=41
  <- notifications/progress related to id=41
  <- notifications/progress related to id=41
  <- JSON-RPC response id=41
stream closes
```

服务器不能独立发送 JSON-RPC 请求在此流中 。 Sampling, elicitation, 和 roots 互动使用 Multi Round-Trip Request 结果。 关闭响应流会取消此请求 。

不添加 SSE 事件代号用于重播 。 `Last-Event-ID` 恢复不是现代修订的一部分。

<a id="long-lived-changes-use-subscriptionslisten"></a>

### 使用订阅/听

更改通知使用客户端打开的请求, 而不是独立获取 :

```json
{
  "jsonrpc": "2.0",
  "id": "listen-1",
  "method": "subscriptions/listen",
  "params": {
    "notifications": {
      "toolsListChanged": true,
      "resourceSubscriptions": ["notes://note-1"]
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {},
      "io.modelcontextprotocol/clientInfo": {
        "name": "course-client",
        "version": "1.0.0"
      }
    }
  }
}
```

POST 响应是一个长寿命 SSE 流。 它的第一个协议消息是 `notifications/subscriptions/acknowledged`。确认、每次更改通知和最后结果 `io.modelcontextprotocol/subscriptionId` 在 `_meta`,等于监听请求代号。服务器可以作为保存器发布 SSE 批注。当流下降时,客户端会重新发布 `subscriptions/listen` 新的请求代号 和重置 影响的数据。

`resources/subscribe` 和 `resources/unsubscribe` 属于传统时代,不要用它们来连接现代。

<a id="explicit-application-state"></a>

### 明确应用状态

删除协议会话并不禁止使用状态的工作流程。 服务器可以将不透明的状态处理器复制为普通工具结果。 客户端会通过该程序作为以后电话的明确参数处理 。

将控件绑在被认证的委托人身上, 使其可以互不相干, 过期并授权使用。 这样就可以在应用层看到状态, 而不是隐藏在运输上的亲和中 。

隐藏复制状态造成的失败是机械性的:

1. 请求 A 到达复制品 1 并在该过程中生成草稿。
2. 答复没有回复一个处理程序,因为执行假设连接确定草案。
3. 请求B是一个新的POST, 并达到复制品2。
4. 复制 2 具有有效的协议元数据, 但无法给草稿命名或装入, 因此工作流程失败或读取错误的本地对象 。
5. 粘着的路线似乎可以修复症状 直到重新开始 rollout中,更改时间或更改错误后,将下一个请求移到别处。

正确的边界有两个部分。 协议上下文将保存在每次请求中。 持久应用程序状态位于一个共享的仓库, 由服务器管理控件返回客户。 下一份调用用品、 任何复制品都装入相同的记录, 授权将记录绑在被认证的主机和租户之间。 复制记忆可能隐藏记录, 但不能成为正确性所需的唯一副本 。

使用寿命选择状态机制。 请求本地变量可以使用一个调用 。 MRTR 连续使用受完整性保护的 `requestState`。草案或长期任务需要明确的处理方式,加上共同的持久性、过期性、货币管制和 idempotency。这些对象没有一个是 MCP 礼宾会议。

<a id="http-dual-era-compatibility"></a>

### HTTP 双年兼容性

支持现代和遗留服务器的客户端首先尝试使用现代 POST。 如果收到的话 HTTP `400`, `404`, 或 `405`检查尸体

- 公认的现代 JSON-RPC 错误证明服务器是现代的。 校正请求或重试已公布版本。 不要降级 。
- 空体或未经确认的答复可能表明遗产 HTTP+SSE 服务器。 只有尝试旧的端点, 并期望其遗产 `endpoint` event.

服务器可以在迁移过程中支持两个时代, 将现代元数据引入现代 POST 执行程序, 并为旧客户保留单独的遗留端点。 永远不要描述遗留端点 Get、 DELETE、 会话代号或重放行为作为 `2026-07-28`.

```figure
tp-transport-handshake
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行一个有限的、现代的流体 HTTP 服务器 Python 标准库。 它验证源代码和镜像信头, 忽略删除的会话信头, 返回 JSON 以显示一个定期的 `subscriptions/listen` SSE溪流。

```bash
cd code
python3 main.py --probe
python3 -m unittest discover tests -v
```

探测器检查:

- 拒绝无效的起源;
- 发现成功,没有会话代号;
- `Mcp-Session-Id` 和 `Last-Event-ID` 被忽略;
- 头不匹配返回 `-32020`;
- 不支持的版本返回 `-32022` 准确 `supported` 和 `requested` data;
- 被接受的无ID- 通知返回 HTTP `202` 无尸体;
- 回来,然后离开 `405`;
- `subscriptions/listen` 是一个POST响应流,其确认、通知和最终结果带有其订阅编号。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-transport-migrator.md`。它删除现代协议会话,添加页眉体验证,替换独立获取 `subscriptions/listen`并保持任何遗留的桥梁 明显分离。

<a id="exercises"></a>

## 练习

1. Remove `Mcp-Method` 发自邮局。 HTTP `400` 错误 `-32020`.
2. 发送匹配的页眉和正文版本 `2027-01-01`确认 HTTP `400`, 错误 `-32022`数据 `{"supported":["2026-07-28"],"requested":"2027-01-01"}`.
3. 发送一个 Base64 哨兵 `Mcp-Name` 用于非-ASCII 资源 URI。 确认解码值与 `params.uri`.
4. 在最后响应前打破有限的听器流。 以新版本重新发布 JSON-RPC 识别和再牵引工具。
5. 在 ping 工具中添加一个明确的工作流程控件。 将其绑在授权对象上, 不使用连接亲和 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| stdio | Newline-delimited JSON-RPC 客户端启动子进程 |
| Streamable HTTP | 每一个现代信息都是新 POST 的单一端点 |
| 请求范围 SSE | 包含相关通知和最后答复的POST响应流 |
| `subscriptions/listen` | 长期的POST 选择入选更改通知请求 |
| 页眉不匹配 | HTTP `400` 和 JSON-RPC `-32020` 当镜像头与身体不相容时 |
| 来源验证 | DNS 约束性防御连接,而非认证 |
| 明确状态控件 | Application token 以普通参数而不是隐藏会话状态通过 |
| 遗留桥 | 分开的早期行为只保留为兼容性 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 运输概览](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
- [MCP 平方英尺运输](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
- [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [MCP Subscriptions](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions)
- [MCP 2026-07-28变化](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
