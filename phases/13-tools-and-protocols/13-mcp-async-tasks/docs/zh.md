<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-tasks-extension-durable-work-on-a-stateless-core"></a>

# MCP Tasks 扩展：在无状态核心上运行持久任务

> Stateless MCP 并不表示每个操作必须同时完成。 正式任务扩展给长期工作一个明确的耐用控件。 服务器可以返回 `tools/call`,任何实例都可以回答 `tasks/get`用户输入 `tasks/update` 但不恢复礼宾会议。

**类型:** Build
**语言:** Python
**先修要求:** 阶段13 · 0 9(运输),阶段13 · 11(无 MRTR13阶段 12(a)elicitation)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 将无国籍人的礼宾运输与持久适用任务区分开来。
- 谈判 `io.modelcontextprotocol/tasks` 请求能力 `server/discover`.
- 返回服务器方向 `CreateTaskResult` 与 `resultType: "task"` 只有在持久的创造之后
- 与 `tasks/get`,完成任务输入 `tasks/update`,并要求合作取消 `tasks/cancel`.
- 删除旧的 `tasks/status`, `tasks/result`, 和 `tasks/list` assumptions.
- 订阅可选任务通知 `subscriptions/listen` 后一反应 SSE 流。
- 模式任务过期、 重新启动恢复、 输入键重复和执行错误正确 。

<a id="why-tasks-are-an-extension"></a>

## 任务为何是一个扩展

任务首先作为实验核心出现 feature 2026年7月的重新设计把他们带到了官方 `io.modelcontextprotocol/tasks` 扩展,客户和服务器可以选择使用寿命周期,而不扩大每个人的核心程序。

扩展规格仍然是一个草稿, 即使它是当前任务的官方主页。 pin the extraction 版本由您支持 SDK,运行符合的场景,并将电线调适器与您的工人和存储域隔开。

当操作具有一个或多个这些属性时使用任务 :

- 可能比普通请求暂停时间还久
- 工人排队或外部工作系统已经拥有执行权。
- 客户在重新开始后需要恢复。
- 操作在执行过程中暂停用户或模型输入 。
- 产品要求是取消和持久结果检索。

不要为廉价的决定性的检查创建任务。 手柄、耐力、投票、过期和取消都是真正的复杂。

<a id="stateless-core-stateful-application"></a>

## 核心、国家适用

MCP 2026-07-28删除 `initialize`, `notifications/initialized`、礼宾会议,以及 `Mcp-Session-Id`这并不禁止有价物品。

任务id是明确的适用性说明:

- 服务器在返回前一直维持着它。
- 客户端可以在重新启动后再次存储和民意测验。
- ID可以通往同一耐久商店支持的任何复制品。
- 检查每个任务方法的核准 。
- 过期和删除由任务领域而不是运输寿命来界定。

这在操作上不同于连接的隐藏状态。

保持四个生命期的分开:

| 状态 | Lifetime | 属于哪里 |
|---|---|---|
| 协议元数据 | 一项请求 | `params._meta`,再次验证在每次呼叫 |
| 运输工作 | 一项标准要求或 HTTP response | 飞行协调员,有截止期限 |
| MRTR continuation | 重试一个序列 | Integrity-protected `requestState`,必要时再播放控件 |
| 持久任务 | 在所有请求中,复制、重新启动和重新连接 | 共享应用程序存储器, 由授权的 `taskId` |

将任务记录移至进程内存时没有 MCP 程序没有被确定,但后来 `tasks/get` 被转到另一个复制处无法恢复记录。 在返回控件前先保存, 然后让每个任务方法在租户和主检查下解决相同的共享记录 。

<a id="capability-negotiation"></a>

## 能力谈判

客户在每次符合条件的请求中都公布支持:

```json
{
  "_meta": {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {
      "extensions": {
        "io.modelcontextprotocol/tasks": {}
      }
    },
    "io.modelcontextprotocol/clientInfo": {
      "name": "lesson-client",
      "version": "1.0.0"
    }
  }
}
```

服务器返回精确 `supportedVersions`能力, 能力, `ttlMs`, 和 `cacheScope` 来自 `server/discover`,在能力下,它也使用相同的扩展功能。由于它发布工具广告,它也强制实施 `tools/list`。结果返回一个确定因素 `generate_report` 描述符, 有效对象 `inputSchema`, `resultType: "complete"`,服务器身份元数据,以及公共缓存提示。

客户端未声明扩展返回的任务方法 `-32021`,缺少客户能力 `data.requiredCapabilities` 设置为 `{"extensions":{"io.modelcontextprotocol/tasks":{}}}`。不支持的协议字符串返回 `-32022` 准确 `supported` 和 `requested` 数据; 缺少或非字符串版本返回 `-32602`.

信封没有 JSON-RPC `id` 是一个通知。 接收者可以处理它, 但它释放不 JSON-RPC 结果或错误。 HTTP 适配器返回 `202 Accepted` 没有接受通知的机构。

目前只有 `tools/call` 支持任务增强的执行。设计您的内部抽象,以便未来的请求类型不需要重新写入存储。

<a id="server-directed-task-creation"></a>

## 服务器已拆分任务创建

旧客户端的旗帜 `params._meta.task.required` 。客户端声明扩展支持,然后服务器决定特定 `tools/call` 成为任务

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "generate_report",
    "arguments": {"size": "large"},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "task",
    "taskId": "tsk_786512e29e0d",
    "status": "working",
    "statusMessage": "Preparing report outline.",
    "createdAt": "2026-08-21T10:30:00Z",
    "lastUpdatedAt": "2026-08-21T10:30:00Z",
    "ttlMs": 900000,
    "pollIntervalMs": 1000
  }
}
```

服务器不能返回此控点, 直到 `tasks/get` 以确认身份。 在最终一致的商店中, 等待阅读可见度后才能回答。 否则客户可以收到有效的身份识别码, 并立即找到“ 找不到 ” 。

任务响应是未经请求的, 即客户端不要求任务模式。 它不是未经谈判的: 当前的请求仍然必须发布扩展名 。

<a id="the-task-shape"></a>

## 任务形状

每项任务都包含:

- `taskId`:稳定的服务器生成标识符;
- `status`: `working`, `input_required`, `completed`, `cancelled`, 或 `failed`;
- `createdAt` 和 `lastUpdatedAt`:ISO 8601 时间戳;
- `ttlMs`: 创建后的终止期,或 `null` 不得以广告方式限制;
- 可选 `pollIntervalMs`:服务器目前建议的最低投票率;
- 可选 `statusMessage`:用户直观或模型直观的上下文。

特定地位领域仅在相关时出现:

- `input_required` includes `inputRequests`.
- `completed` 包括原始请求 `result` shape.
- `failed` 包括 a JSON-RPC `error` object.

客户应该尊重 `pollIntervalMs`。服务器的评分限制可能更具有攻击性,并可能改变任务寿命的间隔。

<a id="poll-with-tasksget"></a>

## 与 `tasks/get`

客户要求当前快照:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tasks/get
Mcp-Name: tsk_786512e29e0d
```

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tasks/get",
  "params": {
    "taskId": "tsk_786512e29e0d",
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

`tasks/get` 本身完成,所以它的结果总是 `resultType: "complete"`。嵌套的任务仍然可以 `status: "working"` 或 `status: "input_required"`.

此区分防止了常见的解析器错误 :

```text
result.resultType = complete    means the tasks/get RPC finished
result.status = working        means the represented job is still running
```

没有 `tasks/result` 调用。 当任务完成后, 下一个 `tasks/get` 回复嵌入原始 `CallToolResult` under `result`:

```json
{
  "resultType": "complete",
  "taskId": "tsk_786512e29e0d",
  "status": "completed",
  "createdAt": "2026-08-21T10:30:00Z",
  "lastUpdatedAt": "2026-08-21T10:34:12Z",
  "ttlMs": 900000,
  "result": {
    "resultType": "complete",
    "content": [
      {"type": "text", "text": "Generated large report with approved outline."}
    ],
    "structuredContent": {"size": "large", "approved": true},
    "isError": false,
    "_meta": {
      "io.modelcontextprotocol/serverInfo": {
        "name": "tasks-demo",
        "version": "1.0.0"
      }
    }
  },
  "_meta": {
    "io.modelcontextprotocol/serverInfo": {
      "name": "tasks-demo",
      "version": "1.0.0"
    }
  }
}
```

外边 `resultType` 说 `tasks/get` RPC 完成。 嵌套 `result.resultType` 原版写着 tool call 已完成。 需要嵌入的导师。 已嵌入 `CallToolResult` 也该自己带 `io.modelcontextprotocol/serverInfo`;这一课包括它而不是储存未输入的有效载荷。

没有 `tasks/list`。无会话服务器无法安全地推断哪些任务属于连接范围列表。需要历史的应用程序应该暴露一个拥有明确过滤器和所有权规则的授权域工具。

<a id="input-during-task-execution"></a>

## 任务执行期间输入

任务投入和核心 MRTR 看上去相似,但使用不同的延续。

<a id="input-needed-before-task-creation"></a>

### 任务创建前需要的投入

返回核心 `resultType: "input_required"` 原页 `tools/call`。客户端完成并重试原始呼叫。只有在同步后创建任务 MRTR 子弹打完

<a id="input-needed-after-task-creation"></a>

### 任务创建后需要的投入

设定任务为 `input_required`. `tasks/get` 暴露了未清的 `inputRequests`,客户通过 `tasks/update`。客户端不重试原始 `tools/call`.

Snapshot:

```json
{
  "resultType": "complete",
  "taskId": "tsk_786512e29e0d",
  "status": "input_required",
  "createdAt": "2026-08-21T10:30:00Z",
  "lastUpdatedAt": "2026-08-21T10:31:00Z",
  "ttlMs": 900000,
  "inputRequests": {
    "approve_outline": {
      "method": "elicitation/create",
      "params": {
        "mode": "form",
        "message": "Approve the generated report outline?",
        "requestedSchema": {
          "type": "object",
          "properties": {"approved": {"type": "boolean"}},
          "required": ["approved"]
        }
      }
    }
  }
}
```

Update:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tasks/update
Mcp-Name: tsk_786512e29e0d
```

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tasks/update",
  "params": {
    "taskId": "tsk_786512e29e0d",
    "inputResponses": {
      "approve_outline": {
        "action": "accept",
        "content": {"approved": true}
      }
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

成功的反应是空洞的确认加 `resultType: "complete"`国家的变化最终可能是一致的,因此客户继续投票或倾听。

每个 `inputRequests` 键必须在整个任务寿命期间独有。 `tasks/get` 快速显示可能显示相同的未执行密钥; 客户对 UI 进行复制, 服务器忽略未知、 被取代或已经完成的密钥。 部分更新可以让任务留在 `input_required` 直到所有所需的密钥都得到回答。

<a id="cancellation-is-cooperative"></a>

## 取消为合作

`tasks/cancel` 信号意图并返回空的完整确认。 此项确认并不能保证工人停止工作。 工作可以先完成, 忽略取消或稍后过渡 。

```http
POST /mcp HTTP/1.1
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tasks/cancel
Mcp-Name: tsk_786512e29e0d
```

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tasks/cancel",
  "params": {
    "taskId": "tsk_786512e29e0d",
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {}
        }
      }
    }
  }
}
```

三种任务方法 `Mcp-Name` mirrors `params.taskId`。它不重复 JSON-RPC 方法名称。 `code/main.py` 将这条规则集中到 `make_http_request`.

教育工作者立即表彰取消,反复致电“无能 ” 。 生产客户仍必须将取消视为合作性,而不是从确认中推断出最终任务地位。

不使用 `notifications/cancelled` 来取消任务。该通知属于请求取消任务,而非持久任务。

区分在航线边界很重要。 请求取消飞行目标 1 JSON-RPC 或请求范围 HTTP 回应。 如果 `tools/call` 已经返回 `resultType: "task"`,该请求已经完成,而其运输的关闭无法命名或停止持久工作。 `tasks/cancel` 是一个新的授权RPC。 `params.taskId`,镜子的ID英寸 `Mcp-Name`,解决任务拥有后端,记录合作取消意向,并返回确认,但工人没有要求停止。

因此,网关必须把请求协调员和任务路径保存在不同表格中。 请求表在回复完成时可以消失。 任务路径必须持续到终端状态和留存期限结束。 [第29课: MCP 可靠性、取消和流程控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md) 造出赛跑,暂停, idempotency, backpressure,并重试两条路径的规则。

<a id="optional-notifications"></a>

## 可选通知

投票是基线。 客户端想要按更新发送 `subscriptions/listen` 任务编号。 HTTP,这是一个POST,其响应是请求范围 SSE 流。没有独立的 Get 事件流和没有协议会话可以维持生命。

服务器确认已接受的代号 `notifications/subscriptions/acknowledged` 然后可以发送完整的快照通过 `notifications/tasks`。确认和每项任务通知都包含 `io.modelcontextprotocol/subscriptionId` 在 `_meta`,等于 `subscriptions/listen` 每项任务通知在其他方面相当于 `tasks/get` 那时会回来

客户仍必须声明任务扩展。 他们应该从耐久的任务代号重新连接并恢复, 而不是依赖事件重放或重播 。 `Last-Event-ID`.

<a id="failure-semantics"></a>

## 失败语义

正确使用两个错误层 。

<a id="protocol-error"></a>

### 协议错误

无效的方法 parameters 或未知任务id 返回 a JSON-RPC 常见错误 `-32602`缺少扩展支持返回 `-32021` 具有所需的能力对象。

<a id="task-execution-outcome"></a>

### 任务执行结果

- 普通工具结果 `isError: true` 仍然是 `completed` 任务 tool call 产生了它确定的结果。
- 一个 JSON-RPC 推迟执行时出错导致任务 `failed` 并储存 JSON-RPC 错误 `error`.
- 用户拒绝可以产生 `cancelled`,或一个完整的拒绝结果,或另一个特定域的安全结果。

<a id="durability-expiry-and-ownership"></a>

## 易腐性、过期和所有权

保存任务编号、 状态、 时间戳、 ttl、 民意测验间隔、 原始操作所有权、 结果或错误、 未解决的输入请求, 以及所有已发的输入键 。

存储密钥必须包含或解决权威的租户和委托人。 了解任务id 不得允许访问。 `tasks/get`, `tasks/update`, `tasks/cancel`,以及订阅。

`ttlMs` , 并且可能更改。 当任务停止生成可观测更新时, 客户端可以将其作为支持。 服务器可能失败, 以后删除过期的任务。 不要把它描述为在完成后保留完成的多毫秒结果的承诺 。

使用原子写作或交易。 课程会写入一个临时文件, 并用原子重命名它。 多复制服务应该使用共享的耐久商店和工人租赁或等效货币控制 。

```figure
tp-task-lifecycle
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行确定性任务服务:

- `server/discover` 返回 `supportedVersions`,缓存提示,以及任务扩展。
- `tools/list` 返回可缓存的确定性 `generate_report` 带有有效输入图的描述符 。
- `tools/call` 创建并持续任务后返回 `resultType: "task"`.
- 一个新的服务实例重新装入相同的任务, 以证明恢复恢复 。
- `tasks/get` 返回任务完整快照。
- 工人从 `working` 以 `input_required`.
- `tasks/update` 接受窗体响应,返回空的完整确认。
- 工人养了个巢穴 `CallToolResult` 与自己的 `resultType` 和服务器身份,然后转换为 `completed`.
- `tasks/cancel` 在执行过程中是无能的。
- 该 HTTP 建筑工件 `Mcp-Name` 以 `params.taskId` 用于 `tasks/get`, `tasks/update`, 和 `tasks/cancel`.
- 通知助手使用 `notifications/subscriptions/acknowledged` 和 `notifications/tasks`,两个标记 听请求的ID。
- 无日期通知产生无 JSON-RPC response.

工人明显地进步,而不是沉睡在背景线上。 这让每一个州都决定了过渡,并且让协议的范例与排队技工分开。

<a id="use-it"></a>

## 实际应用

从仓库根 :

```bash
cd phases/13-tools-and-protocols/13-mcp-async-tasks/code
python3 main.py
python3 -m unittest discover tests -v
```

预期结果序列:

```text
id=0 resultType=complete status=ack
id=1 resultType=task status=working
id=2 resultType=complete status=working
id=3 resultType=complete status=input_required
id=4 resultType=complete status=ack
id=5 resultType=complete status=completed
```

还要核实 `tasks/status`, `tasks/result`, 和 `tasks/list` 返回方法在现代服务中找不到。
验证 `tools/list` 确定性, 和每个当前 HTTP 任务方法反映任务 ID 贯穿 `Mcp-Name`.

<a id="ship-it"></a>

## 交付成果

`outputs/skill-task-store-designer.md` 现在产生一个延伸意识设计:能力谈判、持久回报前创造、当前方法、输入更新流程、所有权、终止、取消、订阅和从已删除的实验方法中迁移。

<a id="exercises"></a>

## 练习

1. 添加第二个未完成的输入密钥。 发送部分 `tasks/update` 证明任务还在 `input_required` 直到两个键都回答。
2. 将租户所有权添加到商店,拒绝错误的委托人出示的有效任务代号。
3. 添加工人合同到期后。 证明两个服务机构无法同时完成相同的任务 。
4. 实施一个后科技反应 SSE 适配器 `subscriptions/listen`。不要添加获得, `Last-Event-ID`,或会议页眉。
5. 添加过期失效清理。 区分过期任务与错误的任务代号, 不泄漏交叉租赁存在 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 在当前扩展名中的含义 |
|------|----------------------------------|
| 任务扩展 | 可选 `io.modelcontextprotocol/tasks` 耐久性同步工作的能力 |
| `CreateTaskResult` | Server-directed `resultType: "task"` 对合格请求的答复 |
| `tasks/get` | 投下完整当前任务快照,包括终端结果或待输入 |
| `tasks/update` | 提交对任务未完成的答复 `inputRequests` |
| `tasks/cancel` | 确认合作取消意向 |
| `input_required` | 任务状态, 显示客户端输入未完成 |
| `pollIntervalMs` | 服务器建议在另一次民意调查之前最小延迟 |
| `ttlMs` | 从任务创建中测量的过期时间 |
| Durable-before-return | 任务代号在发送前必须解决的规则 |
| `notifications/tasks` | 选择性任务全景,提供订阅的SSE答复 |

<a id="legacy-compatibility"></a>

## 遗产兼容性

2025-11-25年实验表面使用客户端要求的任务增强, `tasks/status`, `tasks/result`,并且可选 `tasks/list`。这些名称只保留在被钉住的遗留适配器内。当前客户端使用扩展能力,接受服务器引导的控件,并进行民意测验 `tasks/get`,与 `tasks/update`,并阅读任务快照的最终结果。

<a id="further-reading"></a>

## 进一步阅读

- [Official MCP 任务扩展](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
- [MCP 2026-07-28 Multi Round-Trip Requests](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
- [MCP 2026-07-28 流动 HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
