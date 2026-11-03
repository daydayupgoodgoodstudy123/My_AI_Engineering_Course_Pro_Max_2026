<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-fundamentals-stateless-requests-and-json-rpc"></a>

# MCP 基础：无状态请求与 JSON-RPC

> Modern MCP 请求必须包含足够元数据,以便自己理解、授权、选择和重新尝试。

**类型:** 学习
**语言:** Python
**先修要求:** 第13阶段,第01至05段
**时间:** ~55分钟

<a id="learning-objectives"></a>

## 学习目标

- Distinguish MCP客户端的服务器原始 features.
- 构建有效 JSON-RPC 2.0 请求和答复 MCP `2026-07-28`.
- 将协议版本、客户能力和客户身份附于每一项请求。
- 使用 `server/discover` 并处理 `UnsupportedProtocolVersionError` 手握不动
- Trace 一项独立请求,从审定到完整的结果。

<a id="the-problem"></a>

## 问题

一个 MCP 服务器可在同一程序上接收不同客户端的、功能不同的连续两次请求,或 HTTP 工人。 如果服务器记得上次声明的请求, 它会应用错误的权限或返回错误的线形 。

MCP `2026-07-28` 取消这一模糊性。 协议核心是无国籍的。 服务器必须决定如何处理当前请求中当前的请求, 而不是连接历史中的请求 。

这改变了心理模式。 旧的顺序是连接第一, 握手第二, 操作第三。 现代顺序比较简单 :

1. 客户发送了自描述请求 。
2. 服务器验证了请求的版本和能力 。
3. 服务器处理该方法。
4. 服务器返回已输入的结果或 JSON-RPC 错误.

下一个请求从头重复同样的程序。

<a id="the-concept"></a>

## 概念

<a id="server-primitives"></a>

### 服务器原始

MCP 服务器暴露了三种原始元素:

1. **Tools** 以 `tools/list` 援引的 `tools/call`.
2. **Resources** 使用URI处理的数据, `resources/list` 并用 `resources/read`.
3. **Prompts** 以 `prompts/list` 并用 `prompts/get`.

Roots, sampling,并保持伐木在 `2026-07-28` 兼容性计划,但已经折旧。 roots直接提供模型者 APIs 用于 sampling,以及用于记录的标准或开放遥测。 Elicitation 可通过 Multi Round-Trip Requests,其中服务器返回输入请求,客户端重试原始操作。现代服务器从不启动独立 JSON-RPC request.

<a id="json-rpc-envelopes"></a>

### JSON-RPC envelopes

MCP 使用 JSON-RPC 2.0:

- Request: `{jsonrpc, id, method, params}`
- Response: `{jsonrpc, id, result}` 或 `{jsonrpc, id, error}`
- Notification: `{jsonrpc, method, params}` 无 `id`

请求 `id` 与一个答复相关,它不创建协议会议。

<a id="required-request-metadata"></a>

### 请求的元数据

现代要求都包含 `_meta` 对象在 `params`:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/list",
  "params": {
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

需要协议版本和客户能力。 建议用户身份 。 这是自我报告显示和调试数据, 而不是安全证书 。

服务器不得从先前的请求、 标准进程、 a 和 HTTP 连接,或仅运输头。

<a id="complete-results-and-server-identity"></a>

### 完整结果和服务器身份

现代成果包括 `resultType`通常的最终结果用途 `"complete"`服务器还应在结果元数据中注明自己:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "resultType": "complete",
    "tools": [],
    "ttlMs": 30000,
    "cacheScope": "public",
    "_meta": {
      "io.modelcontextprotocol/serverInfo": {
        "name": "notes-server",
        "version": "1.0.0"
      }
    }
  }
}
```

`tools/list`, `resources/list`, `prompts/list`, `resources/templates/list`, `resources/read`, 和 `server/discover` 包括 `ttlMs` 和 `cacheScope`。安全默认值是 `ttlMs: 0` 和 `cacheScope: "private"`。列表项目应具有确定性排序,以便等效响应产生稳定的缓存键和稳定的模型背景。

<a id="discovery-without-a-handshake"></a>

### 发现者没有握手

每个现代服务器都必须执行 `server/discover`。客户可在另一种检索方法之前调用它:

- `supportedVersions`
- server `capabilities`
- 可选使用 `instructions`
- 服务器身份结果 `_meta`
- 缓存提示

发现是有用的,但它不是大门。客户可以发送 `tools/list` 首先,因为这项请求已经具有其协议版本和能力。

如果请求的版本不支持, 服务器返回 JSON-RPC code `-32022` 与:

```json
{
  "requested": "2027-01-01",
  "supported": ["2026-07-28"]
}
```

客户选择一个相互支持的现代版本,并重试新版本 JSON-RPC 请求编号。

<a id="one-request-lifecycle"></a>

### 一项请求的生命周期

Trace 以此顺序排列的现代请求:

1. 分析一个 JSON-RPC envelope.
2. Confirm `jsonrpc` 是 `"2.0"`, 一个 `id` exists, `method` 是一个字符串, `params` 是一个对象。
3. 需要版本字符串和能力对象 `params._meta`; 元数据格式错误或缺失 `-32602`.
4. 在一个 HTTP 边框, 比较版本、 方法以及应用的名称标题与正文。 匹配是一个 `-32020` 即使在两个版本中有一个值不支持的情况下 。
5. 平等确立后,拒绝匹配但无支持的版本 `-32022`.
6. 检查所需能力,然后通过 `method` 并证实方法上的具体论点。
7. 在操作员运行前验证并授权混凝土操作 。
8. 返回带有服务器身份的完整结果 。
9. 忘记请求范围的协议元数据 。

命令阻止两个组成部分解释不同的通话。 `Mcp-Name: notes.read` 源代码执行时 `params.name: notes.delete`。它还将输入格式错误、标头混乱、版本谈判、能力故障、授权和处理器故障作为不同证据。

关闭标准或 HTTP 响应结束传输活动。 它不会终止协议会话, 因为现代 MCP 没有协议会话 。

<a id="explicit-legacy-compatibility"></a>

### 明确的遗留兼容性

版本通过 `2025-11-25` 使用 `initialize`, `notifications/initialized`,连接范围能力,以及先前可移动的 HTTP。 当一个两时代的客户与旧服务器交谈时, 这种行为仍然具有相关性 。

保持时代的分隔。 需要的每个请求元数据可以识别现代请求。 仅通过文档中的后退路径选择遗留连接。 不要发送 `initialize` 默认为 `2026-07-28` server.

因此,“无国家”具有特定时代的含义。 `2026-07-28`,这是一个协议,它不易:每个普通请求都是可独立解释的,没有 MCP 版本通过 `2025-11-25`,初始化和谈判能力属于连接,因此兼容性适应器可以保留这一遗留连接状态。 两时代的实施并不是一个允许的国家机器。 它是一个与孤立的遗留适应器相邻的无国籍现代核心,在两个分析器运行之前都有明确的选择决定。

两者都不允许持久应用状态。 一个工作流程、任务或草稿可以在共享的商店中以不透明手柄为后盾。 客户端发送该手柄作为普通输入,且每个复制版本都认证并授权使用。 协议上下文不能泄漏到该仓库,以替代删除的会话 。

```figure
mcp-tool-call
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 建造,验证, traces,并发送现代 MCP 没有框架的邮件。运行 :

```bash
python3 code/main.py
python3 -m unittest discover code/tests -v
```

注意输出中的三种变量 :

- 每一个请求都重复 `_meta` fields.
- 每一个成功的结果 `resultType: "complete"` ,并包括服务器身份。
- 列表结果具有明确的缓存提示, 且由确定顺序决定 。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-handshake-tracer.md`。历史文件名保持稳定,但文物现在是一个无国籍者请求追踪器。它独立审核每条信息,仅在遗迹存在时才标注其手握流量。

<a id="exercises"></a>

## 练习

1. 将请求的协议版本更改为 `2027-01-01`错误代码 `-32022` 数据为支持版本做广告。
2. Remove `io.modelcontextprotocol/clientCapabilities` 确认服务器不从第一个请求中再使用功能 。
3. 将模拟工具登记册反转。 确认 `tools/list` 仍然返回相同的确定性秩序。
4. Change `cacheScope` 来自 `public` 以 `private`解释在每种情况下哪些授权情况可以重复答复。
5. 添加可选 `clientInfo` 疏漏测试。 请求应保持有效, 因为推荐客户身份, 不需要 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| 无国籍议定书 | 每一份请求都提供解释它所需的元数据 |
| 请求元数据 | 版本、客户能力和建议的客户身份 `params._meta` |
| `server/discover` | 版本、能力、指令和身份的强制服务器方法 |
| `resultType` | 质疑每个成功的现代结果 |
| 可缓存结果 | 包括所需成果 `ttlMs` 和 `cacheScope` hints |
| 协议时代 | 现代的每个请求元数据或遗留的连接范围初始化 |
| 运输寿命 | 进程、连接或响应流寿命,而非协议会话状态 |
| `-32022` | 不支持协议版本错误, 由请求和支持版本构成 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP Architecture](https://modelcontextprotocol.io/specification/2026-07-28/architecture)
- [MCP 基础协议](https://modelcontextprotocol.io/specification/2026-07-28/basic)
- [MCP 服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [MCP 2026-07-28变化](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
