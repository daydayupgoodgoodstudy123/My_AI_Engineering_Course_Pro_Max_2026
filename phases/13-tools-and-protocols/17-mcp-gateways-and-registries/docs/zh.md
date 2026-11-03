<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="stateless-mcp-gateways-and-registry-admission"></a>

# Stateless MCP 网关与注册表准入

> 网关应该让每一条路线都清晰。 2026-07- 28 协议给出了方法、 名称、 版本、 能力、 身份、 缓存 和 trace 无需运输会话的边界。

**类型:** 学习
**语言:** Python
**先修要求:** 阶段13 15(安全),阶段13 16(授权)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 合计数 MCP 服务器位于一个2026-07-28终点后,没有会话的亲和性。
- 在政策或转发前验证每个请求的元数据和路径标头。
- 将工具与稳定的名称空间、确定顺序、描述针、RBAC和私人缓存合并。
- 将登记记录作为仍然需要入场保单的发现证据。
- 路线请求范围 `subscriptions/listen`, MRTR 重试, 任务扩展调用正确 。
- 与现代道路隔离的遗产握手和会话支持。

<a id="the-problem"></a>

## 问题

直接连接一个客户端到一个服务器是简单的。 更大的部署需要一致的答案来回答更困难的问题 :

- 哪些服务器是允许的?
- 哪个校长能看见和调用每个工具?
- 当两个后端揭开同一个名字时会怎样?
- 如何审查说明性改动?
- 哪里没有 rate limits 以及审计事件是否适用?
- 任何实例能处理下个请求吗?

客户端和后端之间的网关 MCP 服务器。 它显示一个 MCP 终点,适用交叉政策,并转发经批准的请求。

旧网关设计通常将一个客户端会话多路传到多个后端会话中并重写 `Mcp-Session-Id`2026-07-28核心没有协议会议。

<a id="the-concept"></a>

## 概念

<a id="the-modern-gateway-path"></a>

### 现代门户

对于每项请求:

1. 认证委托人 由运输授权。
2. Validate `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`, 和 `params._meta`.
3. 授权主控、资源、方法、工具和参数。
4. 应用描述符、登记、费率和数据政策。
5. 为选中的后端创建新的自足请求 。
6. 校验后端结果并返回网关结果 。
7. 记录一次没有记录秘密的审计事件。

不需要隐藏协议会话。 应用程序状态仍然可以存在于数据库、 明确控件、 任务或受完整性保护的 MRTR state.

<a id="runtime-policy-is-the-primary-gateway-decision"></a>

### 运行时间政策是主要网关决定

接收决定了哪个后端版本可以输入网关。 它不授权实时呼叫。 对于每一项请求, 网关都从认证的首席、 发行人和资源、 租户、 匹配的方法和名称、 正常参数、 被认可描述符针、 当前后端健康、 能力交叉处重新计算政策 。 data classification,费率状态,和任何行动许可。

命令很重要。 注册记录可以在用户作用被撤销时保持活跃。 目的地参数在跨越租户边界时可以继续固定。 事故政策隔离状态改变电话时,后端可以保持批准。 因此运行时间政策是允许或拒绝决定的主要办法, 登记处和描述证据作为输入。

不在连接或删除会话标识符下缓存允许的决定。 如果政策不可用, 则按操作类执行已宣布的失败政策 。 安全默认是关闭状态更改并读取敏感读取, 而明确批准的公开读取路径只有在风险模式允许时才能使用短时间最后已知的政策 。 记录哪个政策版本和失败路径做出了决定, 然后在返回后端结果之前验证 。

<a id="one-post-endpoint"></a>

### 邮政和电信部一个终点

现代流 HTTP 发送 JSON-RPC 通过 POST 发送消息 :

```text
POST /mcp
Authorization: Bearer <gateway-token>
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: notes.search
Accept: application/json, text/event-stream
```

大门可以回来 JSON 或请求范围为该 PST 的 SSE。 获取并指定返回 405 个现代请求 。 `Mcp-Session-Id` 和 `Last-Event-ID` 不得创造权威、亲和或重现行为。

页眉和体积值必须一致。 拒绝不匹配 `-32020` 之后再查找后端。 这样可以让负载平衡器、网关和计价限制线在保持端到端完整性的同时不解析整体。

以一个精确的顺序校验 : JSON-RPC 和元数据类型、标题和体等同,然后支持匹配版本。 HTTP 4 000 计 `-32020`。如果页眉和正文同意一个不支持的版本,则返回 HTTP 4 000 计 `-32022` 和 `data` exactly `{"supported":["2026-07-28"],"requested":"<actual>"}`返回未知的方法 HTTP 404 计 `-32601`.

`ProtocolError` 带有可选 `data`,而网关 连成 JSON-RPC 错误对象。通知中没有 `id`,所以它从来没有得到 JSON-RPC 成功或错误。 HTTP 通知返回空体202。

<a id="implement-discovery-at-every-layer"></a>

### 在每个层次都进行发现

网关执行 `server/discover` 用户。 它也发现每一个后端, 这样它就能了解协议版本、 能力和扩展 。

示例网关结果 :

```json
{
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {
    "tools": {"listChanged": true}
  },
  "ttlMs": 30000,
  "cacheScope": "private",
  "_meta": {
    "io.modelcontextprotocol/serverInfo": {
      "name": "enterprise-gateway",
      "version": "2.0.0"
    }
  }
}
```

广告只刊登连接网关的能力 才能结束 feature 自动暴露不安全。 feature 没有后端路径对广告没有用处 。

`serverInfo` 是指自报显示和诊断数据。不使用它作为注册或出版的证明。

<a id="per-request-client-capabilities"></a>

### 客户能力

每项请求都需要时事 `_meta` envelope:

```json
{
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientCapabilities": {},
  "io.modelcontextprotocol/clientInfo": {
    "name": "enterprise-gateway",
    "version": "1.0.0"
  }
}
```

不要盲目复制外部客户端能力到后端。 网关是后端的客户端。 只发布广告 features 网关将正确调节 。

<a id="deterministic-namespacing"></a>

### 确定性名称的间隔

将后端工具合并到稳定的公共名称下:

```text
notes.search
notes.create
issues.list
issues.open
```

保留从公共名称到后端和原始工具名称的映射。 永远不要选择第一次或最后一次碰撞。 公共名称是批准和审计合同的一部分, 因此更改它就是迁移 。

`tools/list` 必须是决定性的。 当按主控方的可见度不同时, 返回 `cacheScope: private`。 `ttlMs` 减少后端发现负载, 不允许用户特定列表在授权范围内泄漏 。

每个曝光的工具描述符都包含一个稳定的名称、描述和对象根 `inputSchema`。名称间隔不能删除所需的描述字段。完整的列表结果还包括 `resultType`,服务器身份元数据,以及缓存提示。

<a id="pin-approved-descriptors"></a>

### 平方公尺

注册时, 将完整描述符进行加固, 并将其摘要保存在合格的公开名称下。 在列表和呼叫时间上, 请比较活描述符与核准的摘要 。

如果改变的话:

- 把它从 `tools/list`.
- 拒绝直接通话
- 开始审计活动
- 更新插针前需要政策或人重新批准。

网关是一个有用的中央执行点,但它并不将第一眼描述符变成安全。 初步审查仍然有必要。

<a id="registries-help-discover-not-decide"></a>

### 登记员帮助发现,而不是决定

A 书记官处 `server.json` 提供出版元数据。 包支持的记录可以像这样 :

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "com.example/notes",
  "description": "Example notes MCP server.",
  "version": "1.0.0",
  "packages": [
    {
      "registryType": "npm",
      "identifier": "@example/notes-mcp",
      "version": "1.0.0",
      "transport": {"type": "stdio"}
    }
  ]
}
```

发布元数据并不包含网关的安全决定。 将经核实的出版商和来源证据保存在单独的接收状态 :

```json
{
  "registryName": "com.example/notes",
  "registryVersion": "1.0.0",
  "publisher": {"namespace": "com.example", "status": "verified"},
  "provenance": {
    "source": "registry.modelcontextprotocol.io",
    "recordId": "com.example/notes@1.0.0"
  },
  "admission": {"status": "approved", "reviewedBy": "gateway-policy"}
}
```

网关检查 `server.json` 设置并加入到外部状态。 门户仍然需要一个接纳政策 。

每一个入门后端记录:

- 准确的登记册和记录标识符。
- 经验证的出版商名称空间或域名证据。
- 允许运输及终点。
- 粘贴版或已核准的升级政策。
- 人工或描述性摘要。
- 授权发放者和资金。
- 审核员,批准时间和过期

不接受服务器, 因为显示的名称类似于熟悉的产品 。 不要将注册处作为操作安全审查对待 。 私人服务器即使从未出现在公共登记处也可以通过同样的证据模式被接受 。

课程内容是连接网关:在后端变成可循的路径之前,将出版物证据加入本地录取。 [30课: MCP 登记供应链、录用、漂流和 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md) 建立完整的控制平面, 用于准确的命名空间证明、 人工制品来源、 永恒的针线、 实时描述符漂移、 注册状态对账、 明显篡改的入场分类账以及证据支持 rollback保持供应链状态与上述每项请求的运行时间决定分开。

<a id="credential-mediation"></a>

### 身份调解

网关验证其调用者, 并单独验证后端。 后端证书不会交给客户端 。

明确这些约束性:

```text
outer principal -> gateway role and policy
backend issuer + resource -> backend registration and token
```

永远不要经过外门 token 后端。 永远不要重复后端 token 如果工具代表最终用户行事,请保留该工具 delegation 使用设计好的交换或索赔模式,而不是以共享的服务证书冒充用户。

<a id="rate-limits-without-sessions"></a>

### Rate limits 没有会议

由认证的校长、发行人、资源、公共工具、成本类别和时间窗口设定的关键限制。 会话id 不存在,即使存在,也很容易旋转。

使用廉价的验证后再消费昂贵的工作。 决定拒绝的电话是否算作滥用限制、商业配额或两者兼有。

<a id="audit-the-decision-chain"></a>

### 审计决策链

记录足够重建一个电话:

- 请求和 trace identifiers.
- 认证的校长和发行人。
- 公共工具和后端路径 。
- 描述符针版本 。
- 政策决定和理由。
- 延迟和结果类。
- MRTR 酌情使用圆形或任务标识符。

重记器 tokens,授权代码,更新 tokens,原始的秘密, 和不必要的敏感论点。

<a id="request-scoped-sse"></a>

### 请求范围 SSE

正常的 PST 可以在请求期间返回请求范围 SSE 。 关闭响应流会取消在飞行中的现代 HTTP request.

不要创建单独的 Get 流, 也不承诺要重播 Last- vent- ID 。 这些是旧的运输假设 。

<a id="long-lived-change-notifications"></a>

### 长寿命变更通知

对于列表和资源更改通知, 当前客户端发送 `subscriptions/listen` 通过 POST 接收 SSE 响应。 通知过滤器使用精确的平面字段 `toolsListChanged`, `promptsListChanged`, `resourcesListChanged`, 和 `resourceSubscriptions`:

```json
{
  "jsonrpc": "2.0",
  "id": "listen-tools",
  "method": "subscriptions/listen",
  "params": {
    "notifications": {
      "toolsListChanged": true
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```

第一个事件确认支持子集。 其订阅标识符是 JSON-RPC 打开流的请求的代号 :

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/subscriptions/acknowledged",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/subscriptionId": "listen-tools"
    },
    "notifications": {
      "toolsListChanged": true
    }
  }
}
```

网关然后只转发确认的更改类型。 该流上的每份通知都含有相同的类型 `io.modelcontextprotocol/subscriptionId` 在 `params._meta`。没有自动重放或自动重听。重新连接后,客户端会重新订阅并刷新它所依赖的清单。服务器启动的优雅近距离返回一个带有相同订阅标识的最终完整结果。

现代道路取代 `resources/subscribe`, `resources/unsubscribe`,而未请求的独立获得 streaming。只将这些保存在版本化旧路径中。

<a id="mrtr-through-a-gateway"></a>

### MRTR 穿过一个网关

当后端返回时 `resultType: input_required`,网关只有在外部客户支持所需的输入请求时才能将结果向前推进。 `requestState` 字节表示字节,除非网关故意终止并重新发布互动。

客户用新工具重试原始公共工具 JSON-RPC 编号和 `inputResponses`。网关重新授权重试,检查相同的公共路径,然后转发新的后端请求。它不能假定早先的回合获得无限批准。

<a id="tasks-extension-routing"></a>

### 任务扩展路径

任务是官方指定的延伸 `io.modelcontextprotocol/tasks`。它们不是一个核心会话替换器。

客户在每请求客户能力中声明扩展, 网关只在能够保存生命周期结束时发布发现信息。 对于支持的用户来说, `tools/call`,后端单独决定是否返回普通结果或 `resultType: task`任务结果 `taskId`, `status`时间戳, `ttlMs`,并且是一个可选 `pollIntervalMs` 直接在结果中。 任务在发送结果之前必须已经可以持久地读取 。

网关记录了不透明任务标识符的认证主机和后端路径。 `tasks/get`, `tasks/update`, 和 `tasks/cancel` 调用 `params.taskId` 作为 `Mcp-Name`,它给中间人一个路径键。 `tasks/get` 返回 `resultType: complete` 并插入终端状态中的最后结果或协议错误。 `tasks/update` 发送密钥 `inputResponses` 返回空的完整确认。 `tasks/cancel` 是一种合作意图,完全承认,而不是保证工作停止。

不执行新 `tasks/list` 或 `tasks/result` 方法。它们属于旧的实验模式。需要输入的任务通过 `tasks/get`;客户通过 `tasks/update`,而不是重试原始 tool call。客户仍然在建议的间隔进行民意调查;任务创建仍然以服务器为方向。

持久任务路径状态是任务处理所输入的应用数据,而不是协议会话。

<a id="compatibility-boundary"></a>

### 兼容边界

如果网关必须服务于旧客户端或后端 :

- 明确探查这个时代
- 保持初始化、 传输会话、 Get group、 资源订阅和旧任务 vocabulary 在一个遗留的适应器内。
- 永远不要把遗留的会话 泄露给现代路径或授权
- 最好用一个接缝的发现探测器 和明确的后退政策来代替沉默的降级

```figure
t3-gateway-funnel
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个进程内协议网关和两个后端服务器。 每个后端都收到新的当前程序请求。 此网关提供发现、用户过滤的确定性 `tools/list`,名称间距,登记 `server.json` 外加输入状态、描述针、RBAC、主控 rate limits审计决定和模拟 `subscriptions/listen` SSE承认。

该模型接收已解析的请求机构、路标头和经认证的无记名身份。 HTTP 适配器, 不分析 `Content-Type` 或满 `Accept` 合同 连接到9号课流 HTTP 适配器, 需要 `Content-Type: application/json` 和一个 `Accept` 包含两个值的数值 `application/json` 和 `text/event-stream`.

运行：

```bash
cd phases/13-tools-and-protocols/17-mcp-gateways-and-registries
python3 code/main.py
python3 -m unittest discover code/tests -v
```

演示打印外部请求代号, 和新鲜后端请求代号, 这样无国籍跳就可以看见 。

<a id="use-it"></a>

## 实际应用

将进程后端对象替换为真实的当前程序客户端。 保持相同的接缝 :

- 连接前的录取记录 。
- 后端发现之前,能力暴露。
- 未经批准,须有合格的公共名称。
- 列表或呼叫前的描述符针 。
- 转发前,每个请求都更新元数据。
- 返回前对结果进行验证。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-gateway-bootstrap.md`。它产生现代网关设计,包括入侵、发现、进入、命名空间、授权、缓存、 streaming订阅 MRTR任务, observability和遗留的孤立。

<a id="exercises"></a>

## 练习

1. Add trace 将数据输入外部,并记录审计活动中的关联性。
2. 添加任务能力后端和路径 `tasks/get` 任务编号 `Mcp-Name`.
3. 更改一个后端描述符, 并证明发现和直接通话都被屏蔽 。
4. 添加一个主服务器能力,并解释为什么发现必须保持私人藏匿。
5. 写入一个遗留的适应器接口, 不给现代添加任何遗留状态 `Gateway` class.

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| MCP gateway | 客户端和后端之间的策略和路径服务器 MCP servers |
| 录取记录 | 允许一个后端进入网关的证据和政策决定 |
| 合格的工具名称 | 稳定的公共路线,例如 `notes.search` |
| 描述符针 | 发现和发送时核对了核定摘要 |
| 私密缓存范围 | 缓存结果限于一个授权背景 |
| 请求范围 SSE | Streaming 与科技会议一项请求所附的答复 |
| `subscriptions/listen` | 客户端打开的 SSE 流, 用于选中的长期更改通知 |
| 任务路线 | 应用程序映射, 从不透明的任务 ID 到其后端 |
| 遗留适应器 | 旧握手和会话行为明确版本的界限 |

<a id="further-reading"></a>

## 进一步阅读

- [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [官方登记服务器。json requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md)
- [MCP 任务扩展](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
