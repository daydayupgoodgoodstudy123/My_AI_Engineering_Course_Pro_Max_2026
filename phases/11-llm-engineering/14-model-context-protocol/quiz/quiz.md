# 测验 · Model Context Protocol（MCP）（Model Context Protocol (MCP)）

> **阶段 11 · LLM 工程 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、测试 [code/tests/test_main.py](../code/tests/test_main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节讲义按 MCP 2026-07-28 修订版讲解（无状态请求、`server/discover`、MRTR 等）。下面涉及协议细节的题目与答案均以讲义原文为准，用「讲义：“…”」标注；`inputRequests` 等字段的具体结构讲义没有展开，相关代码题中的字段形状是示意。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MCP 解决什么问题 | 把"每个 AI 应用 × 每个外部能力"的定制集成矩阵，收敛成一个标准 JSON-RPC 接口：服务端发布一次，任何合规客户端都能发现、调用、解析 |
| 2 | 角色划分 | Host 是 AI 应用（拥有模型与 UI），内部挂载多个 client；**一个 client 只与一个 server 通信**；transport 承载 JSON-RPC 消息 |
| 3 | 三种服务端原语 | Tools（可调用动作，带 JSON Schema 输入）、Resources（URI 寻址的可读内容）、Prompts（可复用模板） |
| 4 | 无状态请求 | 2026-07-28 移除 `initialize` 握手与协议级会话；每个请求在 `params._meta` 中携带协议版本（必需）、客户端能力（必需）、客户端身份（推荐） |
| 5 | 错误码 | 缺少 `_meta`/必需字段或类型错误 → `-32602` Invalid Params；格式正确但不支持的版本 → `-32022` UnsupportedProtocolVersionError，`data` 含 `supported` 与 `requested` |
| 6 | `server/discover` | 每个现代服务端必须实现；返回支持的版本、能力、服务端身份，以及 `ttlMs`/`cacheScope` |
| 7 | 显式结果类型 | 每个结果有 `resultType`：`complete` 或 `input_required`；后者只能出现在 `tools/call`、`resources/read`、`prompts/get`；缺省视为 complete |
| 8 | 缓存提示 | 列表/读取结果带 `ttlMs` 和 `cacheScope`（`public` 可共享、`private` 限调用方上下文）；列表顺序确定，有利于客户端缓存与 prompt cache 稳定 |
| 9 | 传输 | stdio 或 Streamable HTTP：单一 POST 端点，每条消息一个 POST，响应为 JSON 或请求级 SSE；没有 GET 流、DELETE、`Mcp-Session-Id`、`Last-Event-ID` |
| 10 | 状态与安全边界 | 需要连续性时由服务端签发不透明句柄（state handle），作为普通参数传递；每个请求都要鉴权；变更类工具标 `destructiveHint` 并由 host 要求人工批准；工具输出与资源内容一律视为不可信数据 |

### 核心技能（能动手做到）

- [ ] 手写一个带完整 `_meta` 的 JSON-RPC 请求，并说出每个字段缺失时服务端应返回的错误码
- [ ] 用装饰器注册 tool / resource / prompt，并实现 `tools/list`、`tools/call` 等方法的分发
- [ ] 区分 JSON-RPC request 与 notification，正确处理"无 `id` 不响应"
- [ ] 读懂 20 个单元测试分别在验证哪条协议规则，并能补写新的负向测试
- [ ] 为工具参数实现 JSON Schema 校验，区分"协议错误"与"工具执行错误"
- [ ] 实现基于 `server/discover` 与 `-32022` 的版本协商客户端
- [ ] 用 `input_required` + `requestState` 实现需要用户确认的破坏性工具（讲义练习 4），并保持服务端无状态

---

## 二、基础自测（选择题）

**Q1.** 关于 MCP 中 host、client、server 的关系，正确的是：

- A. 一个 client 可以同时与多个 server 通信，host 只能连一个 client
- B. Server 拥有模型和 UI，host 只负责传输
- C. Host 是 AI 应用，可以挂载多个 client；每个 client 代表 host 与**一个** server 通信
- D. Client 和 server 必须运行在同一个进程里

**Q2.** 一个请求的 `params._meta` 中缺少 `io.modelcontextprotocol/protocolVersion`；另一个请求带了格式正确的版本字符串 `"2025-11-25"`，但服务端只支持 `2026-07-28`。两者分别应返回：

- A. `-32602` Invalid Params；`-32022` UnsupportedProtocolVersionError，且 `error.data` 包含 `supported` 与 `requested`
- B. 都返回 `-32022`
- C. `-32600` Invalid Request；`-32601` Method not found
- D. 都返回 HTTP 400，不带 JSON-RPC 错误

**Q3.** 讲义说 2026-07-28 的 MCP 是"stateless"。下列理解正确的是：

- A. MCP 服务端不能保存任何应用数据
- B. 客户端只需在第一次请求时发送协议版本，之后服务端会记住
- C. 无状态意味着不需要鉴权
- D. 状态不藏在连接或 `Mcp-Session-Id` 后面；需要连续性的工作流由服务端签发不透明句柄，客户端在后续调用中把它当普通工具参数传回，并且每个请求仍要单独鉴权

**Q4.** `resultType: "input_required"`（Multi Round-Trip Requests，MRTR）可以由哪些方法返回？

- A. 所有方法，包括 `tools/list` 和 `server/discover`
- B. 只有 `tools/call`、`resources/read`、`prompts/get`
- C. 只有 `server/discover`
- D. 只有 notification

**Q5.** 关于 2026-07-28 的 Streamable HTTP，下列说法与讲义一致的是：

- A. 客户端先 GET 建立长连接，再用 DELETE 结束会话
- B. 单一端点接受 POST，每条 JSON-RPC 消息一个 POST；请求的响应是一个 JSON 对象或一个以最终响应结束的请求级 SSE 流；被接受的 notification POST 返回 HTTP 202 且无响应体
- C. 每个连接用 `Mcp-Session-Id` 头标识会话，断线后用 `Last-Event-ID` 重放
- D. 只能使用 WebSocket

**Q6.** 远程 `tools/call` 的 HTTP POST 中，`Mcp-Name` 请求头的规则是：

- A. 所有请求都必须带，值为服务端名称
- B. 只有 `server/discover` 需要
- C. 只有 `tools/call`、`resources/read`、`prompts/get` 需要，值必须分别与工具名、资源 URI、prompt 名一致；缺失或不一致返回 HTTP 400 与 `HeaderMismatch`（`-32020`）
- D. 可选头，不影响请求处理

**Q7.** 在本节代码中执行：

```python
server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
```

返回值是：

- A. `{"jsonrpc": "2.0", "id": None, "error": {"code": -32601, ...}}`
- B. `{"jsonrpc": "2.0", "id": None, "error": {"code": -32602, ...}}`（因为缺少 `_meta`）
- C. 抛出 `KeyError: 'id'`
- D. `None`——消息中没有 `id` 键，按 JSON-RPC 是 notification，不产生响应

**Q8.** `add` 工具的 `inputSchema` 声明 `a`、`b` 都是 `integer`。在本节代码中调用 `tools/call`，`arguments` 为 `{"a": "40", "b": "2"}`，结果是：

- A. 成功返回 `resultType: "complete"`，内容为 `{"sum": "402"}`，`isError: false`——服务端从未按 `inputSchema` 校验参数，字符串被直接拼接
- B. 返回 `-32602`，提示参数类型错误
- C. 返回 `-32603` tool handler failed
- D. 自动把字符串转成整数，返回 `{"sum": 42}`

---

## 三、动手 / 代码题

**Q9.** 测试 `test_handler_key_and_type_errors_are_internal_errors` 断言：调用 `add` 时只传 `{"a": 1}`（缺少必需参数 `b`），服务端返回 `-32603`。相关代码：

```python
            tool = self.tools[name]
            try:
                output = json.dumps(tool.handler(**arguments))
            except Exception:
                return self._error(request_id, -32603, "tool handler failed")
            result = self._complete(
                {"content": [{"type": "text", "text": output}], "isError": False}
            )
```

1. 缺少必需参数、类型错误、多余参数这三种情况，本代码分别返回什么？从"谁犯了错"的角度，`-32603`（Internal error）合适吗？
2. 写一个 `validate_arguments(schema, arguments)`：检查 `required`、未声明的参数、基本类型（注意 `bool` 是 `int` 的子类）；在调用 handler 之前执行，失败时返回 `-32602`。
3. 结果里的 `isError` 字段在本代码中永远是 `False`。什么样的错误适合放在 `isError: true` 的结果里，而不是 JSON-RPC `error`？（讲义提到阶段 13 · 28 会专门讨论 protocol error 与 tool-domain error 的区别。）

**Q10.** 本节的 `MCPClient.request`：

```python
    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        request_params = dict(params or {})
        request_params["_meta"] = request_metadata()
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": request_params}
        )
        if response is None:
            raise RuntimeError("request did not receive a response")
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return response["result"]
```

1. 这个客户端能做讲义练习 2 要求的"收到 `-32022` 后从 `supported` 中选择版本"吗？为什么？
2. 写一个 `NegotiatingClient`：保存当前版本；`connect()` 先调 `server/discover`，若收到 `-32022` 则从 `error.data.supported` 读取服务端版本；与客户端自己支持的版本列表求交集后选最新的；对缺少 `resultType` 的旧结果按 `complete` 处理。
3. 讲义练习 5 的"双时代 stdio 客户端"：什么情况下允许回退到 2025-11-25 的 `initialize` 流程？什么情况下不允许？

**Q11.** 讲义练习 4：让 `delete_user` 在执行前要求用户确认。

1. 按讲义描述，第一次 `tools/call` 应返回什么？客户端的重试请求必须满足哪些条件？
2. 实现一个 `ApprovalServer(MCPServer)`。要求：第一次调用返回 `input_required`（带 `inputRequests` 和 `requestState`）；重试时校验 `requestState` 且参数一致，用户批准才执行，拒绝则返回 `isError: true` 的结果；**服务端不在内存里保存待确认请求**（保持无状态）。
3. 你的实现还有什么安全隐患？

**Q12.** 讲义练习 3：给"创建草稿"操作返回服务端签发的 `draftId`，之后的"更新草稿"必须带上它。

1. 为什么说这是"应用状态"而不是"协议会话"？和旧版的 `Mcp-Session-Id` 有什么本质区别？
2. 设计 `create_draft` / `update_draft` 两个工具的 `inputSchema` 与返回值，并说明 `draftId` 应该如何生成、如何校验权限。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 MCP？它和各家模型 API 的 function calling 是什么关系？Tools、Resources、Prompts 分别适合承载什么？

**Q14.**（原理深挖）MCP 为什么从"握手 + 会话"转向无状态请求？带来了哪些好处和代价？新旧版本如何共存？

**Q15.**（工程实践）你要上线一个远程 MCP 服务端，安全上要做哪些事？

**Q16.**（场景设计）为公司内部的工单系统设计一个 MCP 服务端：列出原语映射、关键 schema、缓存策略和审批规则。

**Q17.**（追问型）为什么 `tools/list` 要按确定顺序返回并带 `ttlMs`/`cacheScope`？什么时候必须用 `private` 而不能用 `public`？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The host is the AI application. An MCP client inside that host speaks to one server." Key Terms："Host | Owns the model and UI and mounts one or more MCP clients"；"Client | Speaks MCP to one server on behalf of a host"。A 把一对多关系放反了；B 混淆了 host 与 server；D 错，transport 可以是 stdio（子进程）或 Streamable HTTP（远程）。本节代码用的是进程内直接调用 `server.handle(...)`，只是为了让协议可见。

### Q2 — 答案：A

讲义："A missing `_meta`, a missing required field, or a required field with the wrong type is malformed and returns Invalid Params (`-32602`). A well-formed version string that the server does not support returns `UnsupportedProtocolVersionError` (`-32022`)... Its data contains `supported`... and `requested`"。代码 `_validate_metadata` 严格按这个顺序检查：`_meta` 是否为字典 → 版本键是否存在 → 是否为字符串 → 是否受支持 → `clientCapabilities` 是否为对象 → `clientInfo`（可选）结构是否正确。测试 `test_missing_protocol_version_is_invalid_params` 还专门断言 `-32602` 的错误**不带** `data`，`test_unsupported_protocol_version_returns_spec_error` 断言 `-32022` 的 `data.requested == "2025-11-25"`。C 的 `-32600`、`-32601` 分别是信封非法与方法不存在。

### Q3 — 答案：D

讲义："Stateless does not mean an application can never maintain state. It means that state is not hidden behind an MCP connection or `Mcp-Session-Id`. If a workflow needs continuity, the server mints an opaque handle and the client passes that handle as an ordinary tool argument on later calls. Authorization must still be checked on every request." A 是常见误解；B 是旧版握手的思路，讲义 Step 2 特别提醒 "Do not cache this metadata only in a connection object"——本节 `MCPClient.request` 每次调用都重新构造 `_meta`；C 恰好相反。

### Q4 — 答案：B

讲义："`input_required` means the server needs another round trip through the Multi Round-Trip Requests pattern. Core servers may return it only from `tools/call`, `resources/read`, or `prompts/get`." 列表和发现类方法不应要求额外输入。本节代码没有实现 MRTR，所有结果都是 `complete`（见 Q11）。

### Q5 — 答案：B

讲义："Modern Streamable HTTP exposes one endpoint that accepts POST. Each JSON-RPC message gets its own POST. A request POST receives either one JSON object or a request-scoped Server-Sent Events stream that ends with the final response. An accepted notification POST receives HTTP 202 with no response body" 以及 "There is no standalone MCP GET stream, DELETE session endpoint, `Mcp-Session-Id`, or `Last-Event-ID` replay in 2026-07-28." A、C 描述的是讲义明确说已不存在的旧机制；需要长期变更通知时，讲义说用 `subscriptions/listen` 的 POST，其响应保持为 SSE 流。D 错，MCP 用 stdio 或 Streamable HTTP。

### Q6 — 答案：C

讲义："`Mcp-Method` is required on every JSON-RPC request and must match `method`. `Mcp-Name` is required only for `tools/call`, `resources/read`, and `prompts/get`, where it must match the tool name, resource URI, or prompt name. A missing required header or mismatch returns HTTP 400 with `HeaderMismatch` code `-32020`." 另外 `MCP-Protocol-Version` 头必须与 `_meta` 中的版本一致。这些头让网关、负载均衡器、WAF 不解析 JSON body 也能路由和审计请求，而"头与 body 必须一致"防止了"头里写 add、body 里调 delete_user"的绕过。本节代码是进程内传输，没有实现 HTTP 头校验（讲解第 7 节练习 5）。

### Q7 — 答案：D

```python
        request_id = message.get("id")
        if "id" not in message:
            return None
```

JSON-RPC 2.0 中没有 `id` 的消息是 notification，不需要也不应该有响应（讲义："A notification has no `id` and expects no response"）。注意判断的是"键是否存在"而不是值是否为 `None`：`{"id": None, ...}` 会走到后面并返回 `-32600`（测试 `test_null_request_id_is_invalid`）。代码对 notification 的检查放在 `jsonrpc` 版本与 `method` 校验**之前**，所以即使是不合法的无 id 消息也不响应（测试 `test_idless_invalid_envelopes_receive_no_response`）——对不需要响应的消息回一个错误，对方也无处接收。A、B、C 都与代码不符。

### Q8 — 答案：A

已实际运行：返回 `{"resultType": "complete", "content": [{"type": "text", "text": "{\"sum\": \"402\"}"}], "isError": false, ...}`。`tools/call` 只检查工具名是否存在、`arguments` 是否为字典，然后直接 `tool.handler(**arguments)`；Python 的 `+` 对字符串是拼接。同理 `{"a": 1.5, "b": True}` 返回 `{"sum": 2.5}`（`True` 被当作 1）。`inputSchema` 只是**发布给客户端/模型看的**，服务端若不校验，就等于信任模型生成的参数——而模型生成的参数恰恰是不可信输入。B 是正确实现应有的行为（见 Q9）；C 是参数缺失或多余时的行为；D 不会发生。

### Q9 — 参考答案

1. 三种情况都会让 `tool.handler(**arguments)` 出问题，但表现不同（已实测）：
   - 缺少 `b`：`TypeError`（缺少位置参数）→ 被捕获 → `-32603 tool handler failed`；
   - 多余参数 `c`：`TypeError`（意外关键字参数）→ `-32603`；
   - 类型错误 `"40"`：**不报错**，返回 `{"sum": "402"}`。
   
   从"谁犯了错"看，这三种都是**调用方**的参数问题，用 JSON-RPC 的 `-32602` Invalid params 更准确；`-32603` Internal error 应留给服务端自身的故障（如 handler 内部 bug、返回值无法序列化——测试 `test_non_serializable_tool_result_is_an_internal_error`）。把客户端错误报成内部错误，会让客户端无法区分"我传错了，改参数重试"和"服务端坏了，别重试"。现有测试把"缺参数 → `-32603`"固化了下来，修改实现时需要同步修改该测试。
2. 参考实现（已在 5 组参数上运行验证）：

```python
TYPE_CHECKS = {
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number":  lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string":  lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "object":  lambda v: isinstance(v, dict),
    "array":   lambda v: isinstance(v, list),
}

def validate_arguments(schema, arguments):
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in arguments:
            return f"missing required argument: {key}"
    for key, value in arguments.items():
        if key not in props:
            return f"unexpected argument: {key}"
        expected = props[key].get("type")
        if expected and not TYPE_CHECKS[expected](value):
            return f"argument {key} must be {expected}"
    return None

# 在 tools/call 分支中、调用 handler 之前：
#     problem = validate_arguments(tool.input_schema, arguments)
#     if problem:
#         return self._error(request_id, -32602, problem)
```

   运行结果：`{"a": "40", "b": "2"}` → "argument a must be integer"；`{"a": 1}` → "missing required argument: b"；`{"a": 1, "b": 2, "c": 3}` → "unexpected argument: c"；`{"a": True, "b": 1}` → "argument a must be integer"；`{"a": 1, "b": 2}` → 通过。生产中用 `jsonschema` 库做完整校验（枚举、范围、嵌套、`additionalProperties: false`）。
3. 协议本身正常、工具也被正确调用，但**业务上失败**的情况适合 `isError: true`，例如"用户不存在""余额不足""外部 API 返回 404"。这类结果应该交给**模型**看到并据此调整（换参数、告诉用户），而 JSON-RPC `error` 面向的是客户端程序（格式错、方法不存在、版本不支持）。本节 `delete_user` 删除一个不存在的用户也会"成功"，就是缺少这一层。

### Q10 — 参考答案

1. **不能。** 客户端把错误统一转成 `RuntimeError(message)`，**丢掉了 `code` 和 `data`**，调用方无法判断是不是 `-32022`，也拿不到 `supported` 列表；而且 `request_metadata()` 总是使用模块常量 `PROTOCOL_VERSION`，没有"当前协商版本"这个状态可以修改。
2. 参考实现（已运行验证：把初始版本设为 `2025-11-25`，`connect()` 收到 `-32022` 后切换到 `2026-07-28`，随后 `add(1, 2)` 返回 `{"sum": 3}`）：

```python
class MCPError(Exception):
    def __init__(self, error):
        super().__init__(error["message"])
        self.code = error["code"]
        self.data = error.get("data")

class NegotiatingClient:
    PREFERRED = ["2026-07-28", "2025-11-25"]          # 客户端支持的版本，按优先级

    def __init__(self, server):
        self.server, self._id, self.version = server, 0, self.PREFERRED[0]

    def _send(self, method, params=None):
        self._id += 1
        p = dict(params or {})
        p["_meta"] = request_metadata(protocol_version=self.version)
        resp = self.server.handle({"jsonrpc": "2.0", "id": self._id, "method": method, "params": p})
        if "error" in resp:
            raise MCPError(resp["error"])           # 保留 code 与 data
        result = resp["result"]
        result.setdefault("resultType", "complete")  # 旧结果缺省视为 complete
        return result

    def connect(self):
        try:
            found = self._send("server/discover")
        except MCPError as e:
            if e.code != -32022:
                raise
            found = {"supportedVersions": e.data["supported"]}
        common = [v for v in self.PREFERRED if v in found["supportedVersions"]]
        if not common:
            raise RuntimeError(f"no common version: {found['supportedVersions']}")
        self.version = common[0]
        return found
```

3. 讲义："a dual-era client probes with `server/discover`. A discovery result or a recognized modern error such as `UnsupportedProtocolVersionError` identifies a modern server. Any error or timeout that is not recognized as modern permits fallback to the 2025-11-25 `initialize` flow." 也就是说：拿到 discover 结果、或拿到可识别的现代错误（如 `-32022`）→ 对方是现代服务端，**不允许**回退到 `initialize`，而应在现代协议内选择版本；只有"不认识的错误"或"超时"才允许回退。讲义强调 "Legacy behavior is compatibility code, not the modern default"。

### Q11 — 参考答案

1. 讲义："An eligible tool call... returns `resultType: input_required` with at least one of `inputRequests` or `requestState`. The client gathers any requested input, retries the original method with a new JSON-RPC ID and the corresponding `inputResponses`, and echoes the exact `requestState` when one was provided." 重试条件：**原方法**（仍是 `tools/call`）、**新的 JSON-RPC id**、带上 `inputResponses`、**原样回传** `requestState`。讲义还强调不要"invent a server-to-client JSON-RPC request"——旧版那种服务端主动发请求的方式（如 `elicitation/create`）在新协议中改为 MRTR。
2. 参考实现（字段形状为示意；已运行验证：首次调用返回 `input_required`，批准后删除成功，拒绝返回 `isError: true`，篡改签名或换成 `user_id=8` 都返回 `-32602`，`add` 不受影响）：

```python
import base64, hashlib, hmac, json, time

SECRET = b"server-side-secret"                 # 生产中来自密钥管理服务

def seal(payload):                             # 把状态签名后交给客户端保管
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode()
    sig = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"

def unseal(token):
    body, _, sig = token.rpartition(".")
    expected = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    payload = json.loads(base64.urlsafe_b64decode(body))
    return payload if payload["exp"] > time.time() else None

class ApprovalServer(MCPServer):
    def handle(self, message):
        params = message.get("params") if isinstance(message, dict) else None
        if (isinstance(params, dict) and message.get("method") == "tools/call"
                and params.get("name") == "delete_user" and "id" in message):
            err = self._validate_metadata(params, message["id"])
            if err:
                return err
            args = params.get("arguments", {})
            state = params.get("requestState")
            if state is None:                  # 第一次：要求确认
                return {"jsonrpc": "2.0", "id": message["id"], "result": {
                    "resultType": "input_required",
                    "inputRequests": [{"kind": "confirm",
                                       "message": f"Delete user {args.get('user_id')}?"}],
                    "requestState": seal({"tool": "delete_user", "args": args,
                                          "exp": time.time() + 300}),
                    "_meta": {SERVER_INFO_KEY: self.server_info}}}
            saved = unseal(state)              # 重试：校验签名、过期、参数一致
            if saved is None or saved["args"] != args:
                return self._error(message["id"], -32602, "invalid or mismatched requestState")
            answers = params.get("inputResponses") or []
            if not answers or answers[0].get("approved") is not True:
                return {"jsonrpc": "2.0", "id": message["id"], "result": self._complete(
                    {"content": [{"type": "text", "text": "cancelled by user"}], "isError": True})}
        return super().handle(message)         # 校验通过后走正常的 tools/call
```

   关键设计：`requestState` 由服务端**签名**后交给客户端保管，服务端内存里不保存任何待确认请求，所以任何一个服务端实例都能处理重试——这正是无状态的意义。若用"随机 token + 服务端字典"实现，就又把状态藏回了服务端。
3. 隐患：
   - **重放**：同一个 `requestState` 在 5 分钟内可以重复使用（实测批准后再用同一个 state 仍能再删一次）；需要一次性 nonce（这时需要少量共享存储）或让删除操作幂等。
   - **"批准"由谁做出**：`inputResponses` 是客户端发来的，服务端无法确认真的经过了人类点击；真正的人工批准必须由 host 的 UI 实现（讲义："Mark mutating tools with `destructiveHint: true` and require host approval"），服务端侧的确认只是第二道保险。
   - **状态内容可见**：签名只防篡改不防窥视，状态里有敏感数据时要加密。
   - **鉴权**：重试请求同样要做授权检查，并确认发起重试的主体与第一次是同一个。

### Q12 — 参考答案

1. `draftId` 是**业务对象的标识**，作为普通工具参数显式出现在每次调用中：任何服务端实例、甚至另一个客户端（在有权限时）都可以用它继续操作；它的生命周期由业务决定（草稿可以存一周），存储在数据库里。旧版 `Mcp-Session-Id` 是**协议层**的隐式上下文：绑定在连接上，对模型和业务逻辑不可见，需要粘性会话或共享会话存储，断线后恢复复杂。讲义："If a workflow needs continuity, the server mints an opaque handle and the client passes that handle as an ordinary tool argument on later calls."
2. 设计示例：

```python
@server.tool("create_draft", "Create an email draft and return its id.", {
    "type": "object",
    "properties": {"subject": {"type": "string", "maxLength": 200},
                   "body": {"type": "string", "maxLength": 20000}},
    "required": ["subject", "body"],
    "additionalProperties": False,
})
def create_draft(subject, body):
    draft_id = "drf_" + secrets.token_urlsafe(16)   # 不可猜测，不暴露自增主键
    DRAFTS[draft_id] = {"owner": current_principal(), "subject": subject, "body": body}
    return {"draftId": draft_id}

@server.tool("update_draft", "Update an existing draft by draftId.", {
    "type": "object",
    "properties": {"draftId": {"type": "string", "pattern": "^drf_[A-Za-z0-9_-]{22}$"},
                   "body": {"type": "string", "maxLength": 20000}},
    "required": ["draftId", "body"],
    "additionalProperties": False,
})
def update_draft(draftId, body):
    draft = DRAFTS.get(draftId)
    if draft is None or draft["owner"] != current_principal():   # 每次都校验归属
        return {"error": "draft not found"}                       # 不区分"不存在"与"无权限"
    draft["body"] = body
    return {"draftId": draftId, "updated": True}
```

   要点：句柄随机且不可猜测；**每次请求**都从鉴权信息得到当前主体并校验归属（讲义："Authorization must still be checked on every request"）；不存在与无权限返回相同信息，防止枚举；草稿存放在持久化存储中，与连接无关。`current_principal()` 表示从 HTTP 层鉴权结果中取出的调用者身份。

### Q13 — 参考回答要点

- **定义**：MCP 是基于 JSON-RPC 的开放协议，让 AI 应用以统一方式发现和调用外部的工具、资源与提示模板（讲义 Key Terms："JSON-RPC protocol for server discovery, tools, resources, prompts, and extensions"）。
- **解决的问题**：没有标准时，N 个 AI 应用 × M 个外部能力需要 N×M 套胶水代码（发现、调用、错误、传输、鉴权）；有了 MCP，服务端实现一次，客户端实现一次，变成 N + M。
- **与 function calling 的关系**：function calling 是**模型 API 层**的能力（模型输出"想调哪个函数、参数是什么"）；MCP 是**应用与外部能力之间**的协议。典型链路：host 用 `tools/list` 拿到工具清单 → 转换成模型 API 的 tools 参数 → 模型产生 tool call → host 通过 MCP `tools/call` 执行 → 把结果交回模型。讲义强调："MCP standardizes communication. It does not decide which tool the model should call, make untrusted content safe..."
- **三原语**：Tools 是有副作用或需要计算的动作（查询数据库、发邮件）；Resources 是按 URI 读取的上下文数据（配置、文件、文档）；Prompts 是用户主动选用的模板（如 `code_review`）。
- 加分点：说明 host 负责把 Tools 交给模型、把 Prompts 展示给用户、决定何时读取 Resources；破坏性工具需要 host 层审批。

### Q14 — 参考回答要点

- **为什么转向无状态**（基于讲义的描述归纳）：每个请求自带版本与能力，服务端"can process a valid request without recovering a prior negotiation record"。
- **好处**：任意实例都能处理任意请求，便于水平扩展、负载均衡与 serverless 部署，无需粘性会话或共享会话存储；断线重连没有"会话恢复"问题；每个请求可独立审计与路由（配合 `Mcp-Method`/`Mcp-Name` 头）。
- **代价**：每个请求都携带 `_meta`，略增开销；需要连续性的工作流要显式设计 state handle（练习 3）；服务端主动向客户端要输入改为 MRTR 的"返回 + 重试"模式，客户端逻辑变复杂；Roots、Sampling、Logging 被标记为弃用，旧实现需要迁移。
- **共存**：服务端通过 `server/discover` 公布支持的版本；客户端在 stdio 上先探测 discover，结果或可识别的现代错误表示现代服务端，只有不可识别的错误或超时才回退到 2025-11-25 的 `initialize`（练习 5）；兼容代码要隔离在适配层（本节 skill 文件："Permit those mechanisms only inside a clearly isolated adapter"）。
- 常见误区：把"无状态"理解为"不能有状态"或"不需要鉴权"。

### Q15 — 参考回答要点

讲义 "Step 5: enforce safety outside protocol state" 列出的要点：

- **每个 HTTP 请求都做鉴权**，并校验 audience（令牌确实是发给本服务的）。
- **本地服务绑定 localhost**，Streamable HTTP 校验 `Origin` 头（防止浏览器中的恶意网页对本地服务发起请求）。
- **变更类工具**标 `destructiveHint: true` 并要求 host 审批；注意它只是提示，服务端自己仍要做权限检查（本节 `delete_user` 标了 hint，但服务端照样直接执行）。
- **显式传递目录与文件范围**，不依赖已弃用的 Roots。
- **把资源内容和工具输出当作不可信数据**：它们可能包含间接 prompt injection（第 12 节），host 不能把它们当指令执行。
- **stdio 下 stdout 只留给 JSON-RPC**，诊断信息写 stderr。
- 补充：参数按 schema 严格校验（Q8/Q9）；HTTP 头与 body 一致性校验（`-32020`）；限流与审计日志；最小权限的后端凭据；工具描述本身也可能被投毒（阶段 13 · 15）。

### Q16 — 参考回答要点

- **原语映射**：
  - Resources：`ticket://{id}`（单个工单只读视图）、`queue://{team}`（队列概览）——只读上下文；
  - Tools：`search_tickets`（只读，分页）、`create_ticket`、`add_comment`、`close_ticket`（`destructiveHint: true`）、`reassign_ticket`；
  - Prompts：`summarize_ticket`、`draft_reply`。
- **Schema**：每个参数有类型、长度上限、枚举（如优先级 `low/medium/high`）、`additionalProperties: false`；描述写给模型看（何时使用、何时不要使用）；分页用不透明游标。
- **结果**：`tools/call` 返回结构化 JSON 文本；业务失败用 `isError: true`；列表按确定顺序排序。
- **缓存**：`tools/list`、`prompts/list` 若对所有用户相同可 `public`；`resources/list`、`resources/read` 含按用户权限过滤的数据，必须 `private`，`ttlMs` 设短（工单状态变化快）；`tools/call` 不缓存（讲义："A tool call returns a complete, non-cacheable result because its output can depend on current state"）。
- **审批**：关闭、重新指派、批量操作需要 host 层人工批准；可用 MRTR 在服务端再确认一次（Q11）。
- **安全与运维**：每请求鉴权、按用户权限过滤数据、审计日志、限流；工单内容视为不可信（用户可能在工单里写注入指令）。

### Q17 — 参考回答要点

- **确定顺序**：工具清单通常会被放进模型请求的 tools 参数或 system prompt 的前缀部分。如果每次顺序不同，前缀就变了，provider 的 prompt caching（第 11、15 节）无法命中；客户端也无法用简单比较判断清单是否变化。讲义："A deterministic `tools/list` order plus a freshness hint lets clients cache discovery safely and improves prompt-cache stability." 本节代码用 `sorted(..., key=lambda item: item.name)` 实现，测试 `test_tool_list_is_deterministic_and_cacheable` 断言顺序为 `["add", "delete_user"]`。
- **`ttlMs`**：告诉客户端这份清单多久内可以不重新拉取（本节代码统一 30 秒；讲义示例中 discover 为 1 小时）。
- **`cacheScope`**：讲义："`cacheScope: public` permits shared caching; `private` confines reuse to the calling context." 只要结果**可能因调用者而不同**——按用户权限过滤的工具清单、个人资源、含租户数据的配置——就必须是 `private`，否则共享缓存（网关、CDN、多用户共享的客户端）会把 A 用户能看到的工具或数据给 B 用户。本节代码对所有可缓存结果都用 `private`，是保守但安全的选择。
- 追问加分：`tools/call` 的结果默认不可缓存，因为它依赖当前状态并可能有副作用。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：讲义声明的先修课；MCP 的 tools 最终要转换成模型 API 的 function calling。
- [阶段 11 · 03 Structured Outputs](../../03-structured-outputs/docs/zh.md)：讲义声明的先修课；JSON Schema 是工具输入契约的基础。
- [阶段 11 · 12 Guardrails、安全及内容过滤](../../12-guardrails/docs/zh.md)：工具输出与资源内容是间接注入的入口，第 12 节讲义也在 Related 中指向本节。
- [阶段 13 · 01 工具接口](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：为什么 agent 需要结构化的输入输出。

### 本节被哪些后续内容用到
- [阶段 11 · 13 构建生产环境中的 LLM 应用](../../13-production-app/docs/zh.md)：讲义 Related 指出用 MCP 替代各自定制的工具 schema。
- [阶段 13 · 06 MCP 基础](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)、[阶段 13 · 07 构建 MCP 服务端](../../../13-tools-and-protocols/07-building-an-mcp-server/docs/zh.md)、[阶段 13 · 08 构建 MCP 客户端](../../../13-tools-and-protocols/08-building-an-mcp-client/docs/zh.md)、[阶段 13 · 09 MCP 传输](../../../13-tools-and-protocols/09-mcp-transports/docs/zh.md)：协议各部分的深入实现。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../../13-tools-and-protocols/11-mcp-sampling/docs/zh.md)、[阶段 13 · 12 显式作用范围与无状态 Elicitation](../../../13-tools-and-protocols/12-mcp-roots-and-elicitation/docs/zh.md)：MRTR 与弃用特性的迁移。
- [阶段 13 · 15 MCP 安全](../../../13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/zh.md)、[阶段 13 · 16 MCP 授权](../../../13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/zh.md)：工具投毒与授权。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../../13-tools-and-protocols/28-mcp-tool-contracts-and-content/docs/zh.md)、[阶段 13 · 29 MCP 可靠性、取消与流量控制](../../../13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)、[阶段 13 · 30 MCP 注册表供应链](../../../13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/docs/zh.md)、[阶段 13 · 31 MCP 一致性工程](../../../13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/docs/zh.md)：讲义 "Continue the MCP Deep Dive" 列出的四节。
- [阶段 19 · 13 带注册表与治理机制的 Stateless MCP 服务端](../../../19-capstone-projects/13-mcp-server-with-registry/docs/zh.md)、[阶段 19 · 22 通过换行分隔的 stdio 传输 JSON-RPC 2.0](../../../19-capstone-projects/22-jsonrpc-stdio-transport/docs/zh.md)：综合项目。

### 延伸关键词
`JSON-RPC 2.0` · `params._meta` · `server/discover` · `-32602 / -32022 / -32020 / -32603` · `resultType` · `MRTR / input_required / requestState` · `ttlMs / cacheScope` · `Streamable HTTP` · `stdio` · `destructiveHint` · `state handle` · `Origin 校验` · `tool poisoning`
