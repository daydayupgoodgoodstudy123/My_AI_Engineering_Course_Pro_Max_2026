<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="building-an-mcp-server-stateless-python-and-typescript"></a>

# 构建 MCP 服务端：无状态 Python 与 TypeScript

> 现代 MCP 服务器不记得握手。 它验证每个请求的元数据, 运行一个处理器, 返回一个输入的结果 。

**类型：** 构建
**语言:** Python, TypeScript
**先修要求:** 第13阶段,第06课
**时间:** ~85分钟

<a id="learning-objectives"></a>

## 学习目标

- 强制实施 `server/discover` 用于 MCP `2026-07-28`.
- 校验每个请求的协议版本和客户端能力。
- 展示工具、资源和 prompts 带有确定性清单的顺序。
- 返回 `resultType`,服务器身份,以及正确结果的缓存提示。
- 以同样的无国籍合同 来完成新的限制标准 Python 和 TypeScript.

<a id="the-problem"></a>

## 问题

存储第一个消息后客户端能力的服务器很容易建立,操作也困难。 同一程序可以为相继客户服务。 远程请求可能落到另一个工人身上。 耗尽的能力声明可能会泄露跨权限的行为 。

MCP `2026-07-28` 使用自定义来解析该协议的一部分。 您的应用程序仍然可以保留耐用便条、 工作或明确的状态处理。 它不能保存的是隐藏的协议, 声明更改以后的请求如何解码 。

此课可建立两次笔记服务器 。 Python 和 TypeScript 版本只使用协议核心的标准库。 两种版本都暴露了相同的方法, 并强制执行相同的电线合同 。

<a id="the-concept"></a>

## 概念

<a id="the-modern-dispatch-loop"></a>

### 现代发送环

```text
read one JSON-RPC line
parse the envelope
if it is a notification, do not respond
validate params._meta for this request
route by method
wrap success with resultType and serverInfo
write one JSON-RPC response line
forget request-scoped metadata
```

三个标准规则仍然重要:

- 只写 JSON-RPC 发送给 stdout 的信息。 发送诊断到 stderr 。
- 以新行分隔信件并冲洗每个响应 。
- 等Stdin到达EOF时立即离开

过程寿命是运输寿命,不是现代的 MCP session.

<a id="request-validation"></a>

### 请求验证

每项请求必须:

```json
{
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {},
      "io.modelcontextprotocol/clientInfo": {
        "name": "notes-client",
        "version": "1.0.0"
      }
    }
  }
}
```

需要前两个字段。 `clientInfo` 。验证当前身份形状,但不将其作为认证处理。

如果版本不支持, 返回代码 `-32022` 与 `requested` 和 `supported`。请求中缺失的元数据是无效的参数,代码 `-32602`。从不填充上一个呼叫中缺失的字段。

<a id="mandatory-discovery"></a>

### 强制性发现

现代服务器必须执行 `server/discover`。完整发现结果包括支持的现代版本、能力、可选指令、缓存提示和服务器身份 `_meta`:

```json
{
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {
    "tools": {"listChanged": false},
    "resources": {"listChanged": false, "subscribe": false},
    "prompts": {"listChanged": false}
  },
  "ttlMs": 3600000,
  "cacheScope": "public",
  "_meta": {
    "io.modelcontextprotocol/serverInfo": {
      "name": "notes-server",
      "version": "2.0.0"
    }
  }
}
```

发现者不会打开服务器。 客户端可以调用 `tools/list` 无需打电话寻找是因为 `tools/list` 已经带有相同的请求元数据 。

<a id="tools"></a>

### Tools

`tools/list` 返回工具描述符的确定列表。稳定的排序会改进响应缓存,并使模型环境保持稳定。结果也需要 `ttlMs` 和 `cacheScope`.

`tools/call` 返回内容块和 `isError`。使用 a JSON-RPC 协议信封或方法发生错误 parameters 无效。使用 `isError: true` 当一个有效的工具调用运行但工具本身失败时。

工具注释仍然是提示, 而不是执行 :

- `readOnlyHint`
- `destructiveHint`
- `idempotentHint`
- `openWorldHint`

服务器必须仍然执行真正的授权 。

<a id="resources"></a>

### Resources

`resources/list` 返回稳定的 URI 描述符。 `resources/read` 返回已输入的内容。两者都可在 `2026-07-28`,因此两者都包含 `ttlMs` 和 `cacheScope`.

使用 `cacheScope: "private"` 共享缓存不能在授权范围内重复私人响应 。

现代变革交付不使用 `resources/subscribe`客户端打开 `subscriptions/listen` 和要求 `resourceSubscriptions` 或列表更改类别。 第10课构建了该流量 。

<a id="prompts"></a>

### Prompts

`prompts/list` 具有可隐藏性和确定性。 `prompts/get` 使一个命名 prompt 与辩论。 prompt 后的结果是完整的,但不需要缓存提示,这不是可缓存列表或读取结果之一。

<a id="every-successful-result-is-typed"></a>

### 每一个成功的结果都输入

例子使用一个包装包来取得每一个成功:

```python
def complete(payload):
    return {
        "resultType": "complete",
        **payload,
        "_meta": {SERVER_INFO_KEY: SERVER_INFO},
    }
```

列表、 读取和发现处理器添加 `ttlMs` plus `cacheScope`。集中使用这个包装纸可以防止一个操作者静默地忽略现代结果字段。

<a id="no-server-initiated-requests"></a>

### 没有服务器启动的请求

现代服务器可发送与客户请求相关的通知,或客户打开后发出的通知 `subscriptions/listen` 流。 它不能自己发送 JSON-RPC request.

当一个处理者需要 sampling, elicitation, 或 roots 输入,返回 `input_required` 。客户端满足嵌入输入请求,并用新的请求代号重试原始方法。 Multi Round-Trip Request pattern.

<a id="explicit-legacy-compatibility"></a>

### 明确的遗留兼容性

双层服务器也可以执行 `2025-11-25` 握手 明显分开的遗产 branch。当需要时,它选择现代行为 `_meta` 字段存在, 当收到时会发生遗留行为 `initialize`.

别放 `2026-07-28` 请求通过传统握手路径。 不要在现代标记 `resultType` 字段中显示的初始化结果。本课中的代码是刻意的现代代码,因此其变量始终可见。

```figure
t3-dispatch-loop
```

<a id="use-it"></a>

## 实际应用

运行 Python 服务器的有限演示和测试 :

```bash
cd code
python3 main.py --demo
python3 -m unittest discover tests -v
```

运行 TypeScript 带有 TypeScript runner:

```bash
npx tsx main.ts --demo
```

演示发送 `server/discover`,列出每个原始工具,引用工具,并显示一个不支持的转换错误。每个现代请求都重复元数据。所有成功都包括服务器身份。

<a id="ship-it"></a>

## 交付成果

这艘课船 `outputs/skill-mcp-server-scaffolder.md`。它制作了现代服务器计划,包括发现合同、每项请求的验证、可确定性缓存清单和可选的孤立的遗留适应器。

<a id="exercises"></a>

## 练习

1. 从一个请求中删除能力, 并证明服务器不重复使用先前的请求声明 。
2. 反转 `TOOLS`, `PROMPTS`确认所有列表结果保持稳定 。
3. 添加破坏性 `notes_delete` 工具,并要求在执行器内进行授权检查。 `destructiveHint` 仅作为 UX 提示 。
4. Add `resources/templates/list` 与 `ttlMs`, `cacheScope`和确定性命令。
5. 另建一个遗留适应器 `2025-11-25`。添加测试,证明现代请求从未进入。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| 无国籍服务器 | 处理每个请求, 由它自己的元数据处理, 没有协议会话存储 |
| `server/discover` | 宣传版本和能力的必要现代方法 |
| 完整结果 | 成功现代结果 `resultType: "complete"` |
| 可缓存结果 | 发现、列表或资源阅读结果 `ttlMs` 和 `cacheScope` |
| 决定性清单 | 相同的逻辑注册产生相同的项目顺序 |
| 服务器身份 | 推荐 `io.modelcontextprotocol/serverInfo` 结果 `_meta` |
| 工具错误 | 有效 tool call 返回内容 `isError: true` |
| 协议错误 | 无效 JSON-RPC 或 MCP 请求通过 `error` |

<a id="further-reading"></a>

## 进一步阅读

- [MCP 规格 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/)
- [MCP 服务器发现](https://modelcontextprotocol.io/specification/2026-07-28/server/discover)
- [MCP Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
- [MCP Prompts](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)
- [MCP 平方英尺运输](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
