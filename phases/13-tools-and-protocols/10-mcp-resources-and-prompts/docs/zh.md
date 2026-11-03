<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-resources-and-prompts-addressable-context-for-stateless-servers"></a>

# MCP Resources 与 Prompts：无状态服务端的可寻址上下文

> 工具可以操作,资源可以显示可处理的内容。 Prompts 软件包用户选择的信件模板。 良好 MCP 服务器保持这些合同的单独性和可预测性。

**类型:** Build
**语言:** Python
**先修要求:** 第13阶段,第07课(建立 MCP 服务器,第13阶段,第09课(MCP Transports)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 在工具、资源以及 prompts 消费者的意图。
- 发布资源 prompt 通过强制的表面 `server/discover`.
- 构建确定性 `resources/list` 和 `prompts/list` 结果.
- Apply `ttlMs` 和 `cacheScope` 而不泄漏用户特定数据。
- 返回 JSON-RPC 错误 `-32602` 用于无效或未知的资源 URI 。
- 打开 a `subscriptions/listen` POST- 响应流, 并通过订阅编号连接到每个事件 。
- 处理资源内容和 prompt 模板为不信任的服务器输出 。

<a id="start-with-the-consumer"></a>

## 以消费者为起点

最容易被滥用的方法 MCP 。数据库查询会成为工具,因为函数是熟悉的。可重复使用的工作流程会变成资源,因为它存储在文件中。 A prompt 成为隐藏策略, 因为主机可以输入它 。

开始选择和期望

| Primitive | 主要意图 | 选择所有人 | 典型结果 |
|---|---|---|---|
| 工具 | 执行操作 | 型号或应用程序 | 结构化行动结果 |
| Resource | 在 URI 读取内容 | 主机、应用程序或用户 | 文本或二进制内容 |
| Prompt | 启动可重复使用的信件工作流程 | 通过主机界面的用户 | 一个或多个 prompt messages |

备注 `notes://note-1` 是一个资源,因为它是可处理的内容。 `delete_note` 是一个工具,因为它会改变状态。 `review_note` 是一个 prompt 因为用户选择了准备的审查工作流程。

不要仅为了显得完整，就把同一个操作同时暴露为这三种形式。每增加一种接口形式，都需要处理发现、授权、缓存、错误，以及测试和文档。

<a id="the-2026-07-28-stateless-envelope"></a>

## 2026-07-28无名信封

课程目标 MCP 协议修改 `2026-07-28`。在本配置文件中,没有初始化握手或协议会话。每个请求都带有其协议版本和客户端能力 `_meta` keys.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/list",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": {
        "name": "course-client",
        "version": "1.0.0"
      },
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```

服务器必须执行 `server/discover`其结果得到支持
版本、资源和 prompt 能力、执行特性和
缓存提示。 客户端可以直接调用另一种方法, 但发现时会给它
制作UI之前,要有一个稳定的快照。

```json
{
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {
    "resources": {"listChanged": true, "subscribe": true},
    "prompts": {"listChanged": true}
  },
  "ttlMs": 3600000,
  "cacheScope": "public"
}
```

正常结果声明 `"resultType": "complete"`答复 `_meta` 确定执行中与 `io.modelcontextprotocol/serverInfo`。此信息对诊断有用。它不是一个验证身份。含有无支持的修订返回的请求 `-32022` 以及请求的修改和服务器支持的修订。

无国籍合同会改变您的设计本能。 列表不能取决于先前对一个连接的调用。 授权可能会更改可见集, 因为证书是请求输入, 但连接历史不能 。

<a id="resources-are-stable-uri-contracts"></a>

## 资源稳定 URI 合同

资源由 URI 识别内容。 在处理器前设计 URI 。

良好的 URI 属性 :

- 足够稳定到可以订书或通过申请之间
- 名称已间隔到服务器域 。
- 独立于进程 ID 或连接 。
- 在进入储存设施前验证。
- 授权每读一次

`notes://note-1` 胜过 `note-1` 因为它的命名空间是明确的。 文件服务器可能使用 `file://` URIs, 但必须在解决符号链接和相对部分后检查配置的目录边界 。

`resources/list` 返回当前在呼叫者面前可见的资源。排序时使用稳定的密钥,如 URI 。确定性命令防止噪音缓存丢失、改变快照和主机在刷新之间跳动的 UI 。

```json
{
  "resultType": "complete",
  "resources": [
    {
      "uri": "notes://note-1",
      "name": "Architecture decision",
      "description": "Why the service uses a stateless boundary",
      "mimeType": "text/markdown"
    }
  ],
  "ttlMs": 300000,
  "cacheScope": "public",
  "_meta": {
    "io.modelcontextprotocol/serverInfo": {
      "name": "notes-server",
      "version": "2.0.0"
    }
  }
}
```

`resources/read` 返回一个或多个内容项目。未知的 URI 不是成功的空读取。当前资源规格指定了无效或未知的资源 URI JSON-RPC 无效 parameters代码 `-32602`.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Unknown or invalid resource URI",
    "data": {
      "uri": "notes://missing"
    }
  }
}
```

这种区分使客户客户与有效的空文档分开,也防止了意外地退居到更广泛的查看中。

<a id="resource-templates"></a>

### 资源模板

资源模板描述参数化 URI 的一组。 在列出每个具体项目时使用该组, 费用会很高或没有被绑定 。 例如, `notes://projects/{project}/decisions/{decision}` 告诉客户如何在不归还每项决定的情况下建立有效地址 。

模板不会削弱验证。 分析变量, 应用授权, 强制执行长度和字符限制, 并用输入构建存储查询 parameters。从不将任意的 URI 尾部连接到文件系统路径或数据库语句中。

<a id="content-is-not-trusted-instruction"></a>

### 内容不可信指令

资源文本可包含 prompt injection, 秘密, 误导命令, 或错误的标记。 主机应该保存源代码, 并将资源内容作为数据处理。 服务器应该限制内容大小, 返回准确的 MIME 类型, 编辑无法访问的字段, 并避免返回不相关的记录 。

<a id="prompts-are-user-controlled-templates"></a>

## Prompts 是否由用户控制模板

MCP prompts 用于选择明确的用户。主机可以将其变成斜线命令、菜单项目或工作流程按钮。协议不需要一个 UI 。

`prompts/list` 申请授权时,应具有决定权。 prompt 需要一个稳定的名称、 一个有用的描述, 以及让主机在之前收集输入的参数声明 `prompts/get`.

```json
{
  "resultType": "complete",
  "prompts": [
    {
      "name": "review_note",
      "title": "Review a note",
      "description": "Review one note for a named concern",
      "arguments": [
        {
          "name": "uri",
          "description": "The note resource URI",
          "required": true
        }
      ]
    }
  ],
  "ttlMs": 600000,
  "cacheScope": "public"
}
```

`prompts/get` 解析参数到信件中。 它不替换主机的系统指令。 主机决定返回的信件如何输入模式上下文, 并保持自己信任的政策的优先级 。

Validate prompt 服务器边界上的参数。 A prompt URI 应用直接读取资源时, 需要通过相同的授权检查。 不要做 prompt 环绕资源访问的侧面频道。

<a id="cache-hints-are-part-of-correctness"></a>

## 缓存提示是正确性的一部分

`ttlMs` 告诉客户结果可以再利用多久。 `cacheScope` 描述谁可以共享缓存值 。

| Scope | 含义 | 典型用途 |
|---|---|---|
| `public` | 在批准许可的情况下,用户之间可重新使用 | Public prompt catalog |
| `private` | 与请求用户或证书上下文相符合 | 用户自备的便笺内容 |

从数据变化率和腐烂性损害中选择 TTL。 5分钟可能适合公众 prompt 单子,读个私人便条可能要用一分钟

MCP 仅定义 `public` 和 `private` 作为 `cacheScope` 对于隐含或迅速变化的结果,返回 `cacheScope: "private"` 与 `ttlMs: 0`,然后在主机缓存策略中应用更严格的非仓库规则。 `no-store` 本身不是 MCP `cacheScope` 值.

缓存提示永远不能取代授权。 缓存密钥必须包含所有更改可见度的请求维, 包括租户、 用户、 范围、 本地化和渐变光标。 如果共享缓存无法安全表达这些维度, 请使用 `private` 具有零TTL和主机级的无商店政策。

<a id="subscriptions-use-a-client-opened-response-stream"></a>

## 订阅使用客户打开的反应流

现代订阅模式取代了前者 `resources/subscribe` 区域方案中心及老 HTTP 获取事件终点 。

客户端发送 `subscriptions/listen` 正常的状态 JSON-RPC 请求。 HTTP 这是SSE流的POST, 其响应仍然开放。 `notifications` 对象是一个允许列表。服务器不能交付未请求的通知类型。

```json
{
  "jsonrpc": "2.0",
  "id": 17,
  "method": "subscriptions/listen",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {},
      "io.modelcontextprotocol/clientInfo": {
        "name": "course-client",
        "version": "1.0.0"
      }
    },
    "notifications": {
      "resourcesListChanged": true,
      "promptsListChanged": true,
      "resourceSubscriptions": [
        "notes://note-1"
      ]
    }
  }
}
```

请求的 ID 是订阅的 ID。 在任何请求的事件之前, 服务器会发送 `notifications/subscriptions/acknowledged`。它的过滤器只包含服务器所接受的子集。

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/subscriptions/acknowledged",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/subscriptionId": 17
    },
    "notifications": {
      "resourcesListChanged": true,
      "resourceSubscriptions": [
        "notes://note-1"
      ]
    }
  }
}
```

以后每况愈下 流上都会有相同的元数据

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/subscriptionId": 17
    },
    "uri": "notes://note-1"
  }
}
```

通知上说资源已经改变,客户又读了一遍 `resources/read`,但需获得当前授权。它不假定事件包含新文档。

多个订阅可共享一个标准频道。 订阅 ID 让客户解析它们。 over HTTP,关闭响应流时取消订阅。一个服务器优雅地结束该流,返回最终 `resultType: "complete"` 答复与最初请求相关。

不使用订阅流作为协议会话。 稍后读取仍是一个完整的请求, 它可以到达任何健康的服务器实例 。

```figure
t3-primitive-sort
```

<a id="interactive-lab"></a>

## 交互式实验

使用此数字从项目跟踪器中分类五个能力:发布细节、创建问题、短程审查模板、项目政策和近距离问题。 然后决定哪些清单可以公开隐藏,读作必须保持私有性,哪些资源值得更新通知。

对于每一个分类,请给选择者命名。如果模型执行动作,请使用工具。如果主机读取了 URI 地址处理的内容,请使用资源。如果用户启动已准备好的信件工作流程,请使用 prompt.

<a id="practice-lab"></a>

## 练习实验

从仓库根运行模拟器 :

```bash
cd phases/13-tools-and-protocols/10-mcp-resources-and-prompts/code
python3 main.py
python3 -m unittest discover tests -v
```

检查本顺序的笔录:

1. Confirm `server/discover` 宣传目前的修订和两种能力。
2. 确认列表结果已分类和使用 `resultType: "complete"`.
3. 确认列表并读取结果时带有有意缓存提示 。
4. 将读取的 URI 改为 `notes://missing` 并观察 `-32602`.
5. 在资源活动之前确认订阅确认。
6. 确认事件并优雅地关闭两个自动订阅编号 `5`.

该 Python 模型不会打开一个真实的 HTTP 连接。它代表信息 a SDK 必须将数据放在请求范围响应流上。使用官方 SDK 用于生产中的装配和运输。

<a id="shipped-artifact"></a>

## 交付成果

`outputs/skill-primitive-splitter.md` 是一个可重复使用的设计审查 MCP 原始选择。 它现在检查确定性发现、缓存范围、无效的 URI 行为和现代订阅过滤器。

课也是上船的 `assets/primitive-split.svg`,即离线研究的原始和订阅边界静态版本。

<a id="verify-it"></a>

## 验证

```bash
cd phases/13-tools-and-protocols/10-mcp-resources-and-prompts/code
python3 main.py
python3 -m unittest discover tests -v
```

预期结果:主要程序打印a JSON 记录和测试命令报告至少12次通过测试。

<a id="capstone-connection"></a>

## 与综合项目的联系

当您的综合项目服务器显示可覆盖的知识时, 请使用此合同 。 包含一个确定目录快照, 一个授权资源读取, 一个 prompt 解析,一个无效的 URI 案例,和一个订阅记录。

您的证据应该显示,没有列表取决于连接历史, 订阅活动从不允许访问相关资源。

<a id="exercises"></a>

## 练习

1. 添加a `notes://projects/{project}/notes/{id}` 资源模板并验证两个变量。
2. 添加页码到 `resources/list` 并保持决定性秩序
3. 将一个资源更改为 `cacheScope: "private"` 与 `ttlMs: 0`,添加一个主机级的无仓库政策,并解释两种控制所必须面对的威胁。
4. 添加a prompt- 列出更改订阅, 并证明当过滤器省略时没有发送事件 `promptsListChanged`.
5. 创建两个同时订阅的用户, 并证明每个事件都包含正确的请求代号 。
6. 添加一个权限, 由读取处理器来控制, 并证明缓存项不能交叉 。

<a id="key-terms"></a>

## 关键术语

- **Resource:** 由URI处理的内容被 MCP server.
- **Prompt:** 由用户控制的邮件模板被曝光 MCP server.
- **确定性清单:** 发现结果显示,成员稳定,并订购了相同的请求投入。
- **`ttlMs`:** 缓存新时间以毫秒计 。
- **`cacheScope`:** 缓存结果的共享边界 。
- **`subscriptions/listen`:** 长期请求,其响应流提供明确过滤的通知。
- **订阅 ID :** 原始的监听请求 ID, 在通知元数据中重复 。
- **无效 parameters:** JSON-RPC 错误 `-32602`,用于无效或未知的资源 URI。
- **不支持的协议版本 :** JSON-RPC 错误 `-32022`,包括 `supported` 和 `requested` revisions.
- **`server/discover`:** 返回支持的修改、 能力、 身份和可选缓存提示的强制服务器方法 。

<a id="further-reading"></a>

## 进一步阅读

- [MCP 2026-07-28资源](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
- [MCP 2026-07-28 Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)
- [MCP 2026-07-28订阅](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/subscriptions)
- [MCP 2026-07-28 缓冲](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching)
