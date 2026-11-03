# 测验 · MCP 基础：无状态请求与 JSON-RPC（MCP Fundamentals: Stateless Requests and JSON-RPC）

> **阶段 13 · 工具与协议 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，"无国籍""握手不动""运输头"等译法不准确，阅读时请以英文版为准。本测验中的协议细节均以讲义（MCP `2026-07-28`）为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种 server primitive | Tools（模型控制的动作，`tools/list` + `tools/call`）、Resources（URI 寻址的数据，`resources/list` + `resources/read`）、Prompts（可复用模板，`prompts/list` + `prompts/get`） |
| 2 | 被弃用的客户端特性 | roots、sampling、logging 仍在 `2026-07-28` schema 中但已 deprecated；elicitation 改走 Multi Round-Trip Requests（MRTR）；现代 server 从不主动发起 JSON-RPC 请求 |
| 3 | JSON-RPC 2.0 三种信封 | Request `{jsonrpc, id, method, params}`；Response `{jsonrpc, id, result}` 或 `{..., error}`；Notification 没有 `id`、不期待响应。`id` 只用于配对响应，不创建会话 |
| 4 | 每请求元数据 `params._meta` | `protocolVersion` 与 `clientCapabilities` **必填**；`clientInfo` **推荐**，是自报的展示/调试信息，不是安全凭证 |
| 5 | 无状态（stateless）不变量 | server 只能根据**当前请求**决定如何处理，不能从上一个请求、stdio 进程、HTTP 连接或单独的传输头推断版本和能力 |
| 6 | 完整结果与 server 身份 | 每个成功的现代结果带 `resultType`（普通最终结果为 `"complete"`），并在结果 `_meta` 中放 `serverInfo` |
| 7 | 可缓存结果 | `*/list`、`resources/read`、`server/discover` 等必须带 `ttlMs` 与 `cacheScope`；安全默认 `ttlMs: 0` + `"private"`；列表顺序要确定，保证缓存键和模型上下文稳定 |
| 8 | `server/discover` 与 `-32022` | 每个现代 server 必须实现 discover（返回 supportedVersions、capabilities、instructions、身份、缓存提示），但它**不是门禁**；版本不支持返回 `-32022`，`data` 含 `requested` 与 `supported`，客户端换版本并用**新的 id** 重试 |
| 9 | 请求生命周期顺序 | 解析信封 → 校验 JSON-RPC 字段 → 校验 `_meta`（`-32602`）→ HTTP 头与 body 一致性（`-32020`）→ 版本支持（`-32022`）→ 能力与路由、参数校验 → 鉴权 → 返回完整结果 → 忘掉本请求元数据 |
| 10 | 协议时代（era）与应用状态 | `2025-11-25` 及以前用 `initialize` 握手、连接级能力；双时代实现 = 无状态现代核心 + 隔离的 legacy 适配器。无状态不禁止持久**应用**状态：用不透明 handle 存到共享存储，每次都鉴权 |

### 核心技能（能动手做到）

- [ ] 手写一个合法的 `tools/list` 现代请求和对应的 complete 结果（含 `_meta`、`resultType`、`ttlMs`、`cacheScope`、`serverInfo`）
- [ ] 区分 `-32600` / `-32601` / `-32602` / `-32020` / `-32022` 各自代表的失败类型，并说出它们在生命周期中出现的先后
- [ ] 读懂本节 `validate_request`，指出它与讲义生命周期**顺序不一致**的地方并改正
- [ ] 解释为什么 server 不能"沿用"上一个请求声明的 capabilities，并用测试验证这一点
- [ ] 区分 `isError: true` 的工具执行错误与 JSON-RPC 协议错误，给 `tools/call` 补上参数类型校验
- [ ] 说清 `cacheScope: "public"` 与 `"private"` 对缓存复用范围的影响，判断一个结果该用哪一个

---

## 二、基础自测（选择题）

**Q1.** 在 MCP `2026-07-28` 中，每个现代请求的 `params._meta` 里**必须**携带的两个字段是：

- A. `clientInfo` 与 `protocolVersion`
- B. `sessionId` 与 `clientCapabilities`
- C. `protocolVersion` 与 `clientCapabilities`
- D. `clientInfo` 与 `serverInfo`

**Q2.** server 返回 JSON-RPC 错误码 `-32022`，含义是：

- A. 协议版本不受支持，`data` 中给出 `requested` 和 `supported`
- B. 方法不存在
- C. 参数非法（例如缺少 `_meta`）
- D. HTTP 头与 body 中的版本/方法不一致

**Q3.** 用本节代码构造 `make_request(1, "tools/list", version="2027-01-01")`，再删掉其中的 `clientCapabilities`，交给 `dispatch`。返回的是：

- A. `-32602`（capabilities 缺失）
- B. `-32600`（Invalid Request）
- C. 一个 `resultType: "complete"` 的结果
- D. `-32022`（版本不受支持）

**Q4.** 关于 JSON-RPC notification，下列说法正确的是：

- A. notification 的 `id` 固定为 `null`
- B. notification 没有 `id`，接收方不返回响应；本节 `dispatch` 遇到没有 `id` 的消息直接返回 `None`
- C. notification 必须带 `result` 字段
- D. notification 的 `id` 必须是字符串

**Q5.** 下列哪个结果在 `2026-07-28` 中**必须**带 `ttlMs` 与 `cacheScope`？

- A. `tools/list` 的结果
- B. `tools/call` 的结果
- C. 一个 JSON-RPC error 响应
- D. 一条取消通知

**Q6.** 关于 `io.modelcontextprotocol/clientInfo`，正确的是：

- A. 必填，缺失时返回 `-32602`
- B. 是安全凭证，server 应据此决定授权
- C. 若本请求缺失，server 应沿用同一连接上一个请求里的值
- D. 推荐但非必填，是自报的展示与调试信息；缺失时请求仍合法，但若存在且格式错误，本节代码返回 `-32602`

**Q7.** 本节 `TOOLS` 列表的定义顺序是 `notes_search`、`notes_list`。`tools/list` 结果中工具的顺序是：

- A. `notes_search`、`notes_list`（保持定义顺序）
- B. 每次运行随机
- C. `notes_list`、`notes_search`
- D. 取决于 dict 的哈希值

**Q8.** stdio 客户端关闭了 server 进程的 stdin。在 `2026-07-28` 的语义下，这意味着：

- A. MCP 会话被终止，下次连接必须重新 `initialize`
- B. 只是传输活动结束；现代 MCP 没有协议会话，也就无所谓"终止会话"
- C. server 应清除该会话缓存的 client capabilities
- D. 客户端需要先发 `notifications/initialized` 才能再次通信

---

## 三、动手 / 代码题

**Q9.** 讲义给出的生命周期是："第 3 步要求 `_meta` 中有版本字符串和 capability 对象，缺失或格式错误为 `-32602`；……第 5 步在确认一致之后，拒绝不受支持的版本 `-32022`"。下面是本节 `validate_request` 的节选：

```python
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        return rpc_error(request_id, -32602, f"{VERSION_KEY} is required")
    if version not in SUPPORTED_VERSIONS:
        return rpc_error(
            request_id,
            -32022,
            "Unsupported protocol version",
            {"requested": version, "supported": SUPPORTED_VERSIONS.copy()},
        )
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        return rpc_error(request_id, -32602, f"{CAPABILITIES_KEY} is required")
```

1. 它与讲义的顺序有什么不一致？构造一个能暴露差异的请求，并写出代码实际返回与讲义期望返回的错误码。
2. 为什么讲义坚持"先结构校验、再版本协商"？从"客户端如何根据错误做下一步"的角度解释。
3. 改写这段代码，使其符合讲义顺序。

**Q10.** 阅读 `dispatch` 中 `tools/call` 分支：

```python
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "notes_list":
            ...
        elif name == "notes_search" and isinstance(arguments.get("query"), str):
            ...
        else:
            result = complete_result(
                {
                    "content": [{"type": "text", "text": f"Unknown or invalid tool: {name}"}],
                    "isError": True,
                }
            )
```

1. 请求 `{"name": "notes_search", "arguments": "JSON-RPC"}`（`arguments` 是字符串）会发生什么？
2. 这段代码把"工具不存在"和"参数不合法"都放进了 `isError: true` 的结果里。说明工具执行错误（`isError`）与 JSON-RPC 协议错误的区别，以及各自更适合哪种失败。
3. 改写这个分支：`arguments` 不是对象时返回 `-32602`；未知工具返回 JSON-RPC 错误；`notes_search` 缺 `query` 时返回模型可读、可自我纠正的 `isError` 结果。

**Q11.** 运行下面的代码：

```python
r = main.dispatch(main.make_request(1, "server/discover"))
r["result"]["capabilities"]["tools"]["listChanged"] = True
print(main.SERVER_CAPABILITIES)
```

1. 输出是什么？为什么？
2. 这个现象和本节"无状态"主题有什么关系？在真实 server 里可能造成什么后果？
3. 给出修复方法，并指出 `tools/list` 分支里同类的隐患。

**Q12.** 用本节 `trace_message` 依次追踪以下 5 条消息，写出每条的 `kind / era / detail`：

```python
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}
{"jsonrpc": "2.0", "method": "notifications/initialized"}
{"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}}
{"jsonrpc": "2.0", "id": 4, "error": {"code": -32022, "message": "Unsupported protocol version"}}
```

再对照本节 `outputs/skill-mcp-handshake-tracer.md` 的规则（"把 `initialize` 和 `notifications/initialized` 标为 legacy"、"把 `-32022` 视为现代证据"），指出 `trace_message` 有哪两处不符合，并给出修改思路。

---

## 四、面试高频题

**Q13.**（基础必考）MCP `2026-07-28` 所说的"无状态"具体指什么？它和 `2025-11-25` 及以前的 `initialize` 握手模型有什么区别？没有握手之后，版本和能力协商靠什么完成？

**Q14.**（原理深挖）为什么 server 不能根据同一连接上前一个请求声明的 capabilities 来处理当前请求？请从多路复用、水平扩展、网关和安全几个角度回答。

**Q15.**（工程实践）请描述一个现代 MCP 请求在 server 端的完整处理顺序，并解释为什么顺序本身就是安全属性（提示：讲义中 `Mcp-Name: notes.read` 与 `params.name: notes.delete` 的例子）。

**Q16.**（场景设计）你的 MCP server 需要支持一个跨多次调用的"草稿编辑"工作流，部署在 3 个无共享内存的副本上。在协议核心无状态的前提下怎么设计？哪些东西**不能**放进共享存储？

**Q17.**（追问型）`tools/list` 结果的 `cacheScope` 什么时候可以是 `"public"`，什么时候必须是 `"private"`？如果某 server 按用户权限过滤工具列表却标了 `public`，会出什么问题？为什么还要求列表顺序确定？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The protocol version and client capabilities are required. Client identity is recommended." 代码中 `validate_request` 也是：缺版本或缺 capabilities → `-32602`；`clientInfo` 只有"存在但格式错误"时才报错。

- A 错：`clientInfo` 是推荐项。
- B 错：现代协议没有 `sessionId`，`Mcp-Session-Id` 是旧版 Streamable HTTP 的概念。
- D 错：`serverInfo` 放在**结果**的 `_meta` 里，由 server 填写。

### Q2 — 答案：A

讲义：版本不受支持时返回 `-32022`，`data` 为 `{"requested": "2027-01-01", "supported": ["2026-07-28"]}`。本节实际运行的第 4 个请求正是如此。

- B 是 `-32601`（Method not found，本节请求 `resources/list` 时会返回它）。
- C 是 `-32602`（Invalid params）。
- D 是 `-32020`（HTTP 头与 body 不一致，在第 09 节传输层实现）。

### Q3 — 答案：D

实际运行结果为 `-32022`。原因是 `validate_request` 先检查"版本是否受支持"，后检查 capabilities 是否存在，所以缺 capabilities 的问题被版本错误"盖住"了。按讲义生命周期（第 3 步结构校验在第 5 步版本协商之前），**期望**应为 A（`-32602`）。这是本节代码与讲义的一处不一致，详见 Q9。

- B 错：`jsonrpc` 和 `method` 都合法，不会触发 `-32600`。
- C 错：版本不受支持，不可能成功。

### Q4 — 答案：B

讲义："Notification: `{jsonrpc, method, params}` with no `id`"。代码：

```python
def dispatch(message):
    if "id" not in message:
        return None
```

- A 错：JSON-RPC 2.0 中 `id: null` 不等于"没有 id"；notification 的定义是**不含** `id` 成员。
- C 错：`result` 属于响应。
- D 错：请求的 `id` 可以是字符串或数字；notification 根本没有 `id`。

### Q5 — 答案：A

讲义列出的可缓存结果：`tools/list`、`resources/list`、`prompts/list`、`resources/templates/list`、`resources/read`、`server/discover`。代码里 `tools/list` 带 `ttl_ms=30_000, cache_scope="public"`，`server/discover` 带 `ttl_ms=3_600_000`。

- B 错：`tools/call` 是一次动作的执行结果，代码中 `complete_result` 不传 `ttl_ms`，因此没有缓存提示。
- C、D 错：错误和通知都不是"成功结果"，没有缓存提示一说。

### Q6 — 答案：D

讲义："Client identity is recommended. It is self-reported display and debugging data, not a security credential." 测试 `test_client_info_is_recommended_not_required` 删掉 `clientInfo` 后仍得到 complete 结果。我们另外验证：`clientInfo` 为 `{"name": "x"}`（缺 `version`）时返回 `-32602 "io.modelcontextprotocol/clientInfo is malformed"`。

- A 错：不是必填。
- B 错：任何客户端都可以自报名字，不能用来授权；授权要靠真正的认证（第 16、18 节）。
- C 错：从前一个请求推断正是无状态协议禁止的行为。

### Q7 — 答案：C

代码 `sorted(TOOLS, key=lambda tool: tool["name"])` 按名字字典序排列，`"notes_list" < "notes_search"`（第 7 个字符 `l` < `s`）。实际输出确认 `notes_list` 在前。这也意味着讲义练习 3"反转注册表"在本代码中已经被"预先演示"了：定义顺序本来就是反的，输出仍然有序。

- A 错：Python 3.7+ 的 list 会保持插入顺序，但这里显式排序了。
- B、D 错：`sorted` 是确定性的，与哈希无关。

确定顺序的意义：讲义 "List items should have deterministic ordering so equivalent responses produce stable cache keys and stable model context."——顺序变了，缓存命中率和 prompt 前缀缓存都会受影响，模型看到的工具顺序也会抖动。

### Q8 — 答案：B

讲义："Closing stdin or an HTTP response ends transport activity. It does not terminate a protocol session because modern MCP has no protocol session." 代码最后打印 `Transport closes. No protocol session was created or terminated.`

- A、D 描述的是 `2025-11-25` 及以前的 legacy 握手流程。
- C 错：现代 server 本来就不该缓存"会话级 capabilities"。

### Q9 — 参考答案

1. **不一致**：代码在检查 capabilities **之前**就做了版本支持性检查。暴露差异的请求：版本 `2027-01-01` 且没有 `clientCapabilities`。实际运行返回 `-32022`；按讲义顺序应先发现结构缺陷，返回 `-32602`。
2. **为什么先结构后版本**：讲义说这个顺序让"malformed input, header confusion, version negotiation, capability failure, authorization, and handler failure"成为**彼此可区分的证据**。客户端收到 `-32022` 的标准动作是"换一个双方都支持的版本，用新 id 重试"；但这个请求本身就缺 capabilities，换版本重试后还会再失败一次，白白多一个往返，而且日志中第一条证据指向了错误的原因。先报 `-32602` 能让客户端直接修正请求构造的 bug。
3. 改写（已实际运行验证：版本 `2027-01-01` + 缺 capabilities → `-32602`；只有版本不对 → `-32022`）：

```python
    version = meta.get(VERSION_KEY)
    if not isinstance(version, str):
        return rpc_error(request_id, -32602, f"{VERSION_KEY} is required")
    if not isinstance(meta.get(CAPABILITIES_KEY), dict):
        return rpc_error(request_id, -32602, f"{CAPABILITIES_KEY} is required")
    client_info = meta.get(CLIENT_INFO_KEY)
    if client_info is not None and (...):          # 结构校验全部放前面
        return rpc_error(request_id, -32602, f"{CLIENT_INFO_KEY} is malformed")
    # （HTTP 边界在这里比较头与 body，不一致 → -32020，见第 09 节）
    if version not in SUPPORTED_VERSIONS:           # 最后才做版本协商
        return rpc_error(request_id, -32022, "Unsupported protocol version",
                         {"requested": version, "supported": SUPPORTED_VERSIONS.copy()})
    return None
```

### Q10 — 参考答案

1. **崩溃**：`arguments = "JSON-RPC"`，`arguments.get("query")` 抛出 `AttributeError: 'str' object has no attribute 'get'`（已实际运行验证）。`dispatch` 没有任何异常处理，在真实 server 里这会变成未处理异常，最好情况是框架兜底返回 `-32603 Internal error`，最差是进程退出、同一 stdio 上的后续请求全部失败。
2. **两类错误的区别**：
   - **JSON-RPC 协议错误**（`error` 字段）：请求本身不能被处理——方法不存在、参数结构不对、工具名未知、版本不支持。面向的是**客户端程序**，通常不会被原样交给模型。
   - **工具执行错误**（`result.isError: true`）：工具被正常调用，但执行失败或业务输入不满足要求。`content` 会进入模型上下文，模型可以读懂并自我纠正（例如补上 `query` 再调一次）。
   - 本节代码把"未知工具"也放进 `isError`，混淆了两者，而且 `Unknown or invalid tool: notes_search` 这句话无法告诉模型到底缺了什么。
3. 参考实现（已在本节代码上替换运行，三种情况分别得到 `-32602`、`-32602`、`isError: true`）：

```python
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return rpc_error(request_id, -32602, "tools/call needs string name and object arguments")
        known = {tool["name"] for tool in TOOLS}
        if name not in known:
            return rpc_error(request_id, -32602, f"Unknown tool: {name}")
        if name == "notes_search" and not isinstance(arguments.get("query"), str):
            result = complete_result({
                "content": [{"type": "text",
                             "text": "notes_search requires a string 'query', e.g. {\"query\": \"JSON-RPC\"}"}],
                "isError": True,
            })
        elif name == "notes_list":
            ...
```

要点：结构性错误走协议错误；业务输入问题给出"模型能看懂的修正提示"。这与第 05 节"工具 schema 设计"中错误信息要可执行的原则一致。

### Q11 — 参考答案

1. 输出 `{'tools': {'listChanged': True}}`（已实际运行）。`SERVER_CAPABILITIES.copy()` 是**浅拷贝**：外层 dict 是新的，但 `"tools"` 对应的内层 dict 仍是同一个对象。调用方修改结果里的内层 dict，就改到了模块级全局常量。
2. **与无状态的关系**：本节的核心是"一个请求的处理不能影响下一个请求"。浅拷贝让某次请求的响应对象与全局配置共享内存，任何下游（中间件、缓存层、测试代码）对响应的修改都会**泄漏到后续所有请求**——这正是一种隐蔽的跨请求状态。真实后果：server 开始对所有客户端宣称它支持 `listChanged`，而实际上并不支持；或缓存层就地改写了 `ttlMs`，导致后续响应的缓存提示错误。
3. 修复：`import copy`，用 `copy.deepcopy(SERVER_CAPABILITIES)`；或者把常量定义成不可变结构（如 `types.MappingProxyType`），或每次用函数现场构造。`tools/list` 分支的 `sorted(TOOLS, ...)` 也只是新建了一个列表，里面的工具 dict（包括 `inputSchema`）仍与全局 `TOOLS` 共享，同样应 `deepcopy`。`SERVER_INFO.copy()` 与 `CLIENT_INFO.copy()` 因为只有一层字符串值，浅拷贝已足够。

### Q12 — 参考答案

实际运行结果：

| # | 消息 | kind | era | detail |
|---|------|------|-----|--------|
| 1 | `initialize` | request | legacy | connection-scoped handshake |
| 2 | `notifications/initialized` | notification | unknown | no response expected |
| 3 | 无 `resultType` 的 result | response | legacy | resultType=absent |
| 4 | 只有版本、没有 capabilities 的 `tools/list` | request | invalid | missing modern request metadata |
| 5 | `-32022` 错误 | response | unknown | code=-32022 |

与 skill 规则不符的两处：

1. `notifications/initialized` 是 legacy 握手的一部分，skill 要求"Label `initialize` and `notifications/initialized` as legacy only"，代码把所有 notification 都标为 `unknown`。改法：在 notification 分支里对这个方法名单独返回 `era="legacy"`。
2. skill 要求"Interpret `-32022` as modern evidence"，代码对所有错误一律标 `unknown`。改法：维护一个现代专属错误码集合 `{-32020, -32021, -32022}`，命中时标 `modern`。

另外两点值得注意：第 3 条只因缺 `resultType` 就被判为 legacy，严格说只能算"不符合现代规范"，也可能是有 bug 的现代 server；第 5 条若把 `result` 换成非 dict（如列表），`result.get` 会抛异常——追踪器面对的是不可信输入，应先做类型检查。

### Q13 — 参考回答要点

- **定义**：协议核心中，每个普通请求都**自描述**（`params._meta` 携带协议版本、client capabilities，推荐携带 clientInfo），server 只根据当前请求决定如何处理；不存在 MCP 协议会话。讲义："every ordinary request is independently interpretable and no MCP session exists"。
- **与 legacy 的区别**：`2025-11-25` 及以前是"先连接 → `initialize` 协商版本和能力 → `notifications/initialized` → 正常操作"，能力属于**连接**；早期 Streamable HTTP 还有可选的协议会话（`Mcp-Session-Id`）。
- **没有握手后靠什么协商**：
  - 每个请求自带版本，server 不支持就返回 `-32022` + `supported` 列表，客户端换版本用新 id 重试；
  - 可选地先调 `server/discover` 获取 supportedVersions、capabilities、instructions，但它不是门禁，客户端可以直接发 `tools/list`。
- 加分点：指出"无状态"有时代含义——legacy 适配器可以保留连接状态，但要与现代核心隔离，并在任何 parser 运行前就做出"走哪条路"的明确选择。
- 常见误区：把"无状态"理解为"不能有任何持久数据"（见 Q16）；把 `id` 当成会话标识。

### Q14 — 参考回答要点

- **多路复用**：讲义开篇场景——同一进程或 HTTP worker 可能连续收到**不同客户端**、不同 capabilities 的请求。沿用上一个请求的声明会用错权限或返回错误的 wire shape。
- **水平扩展**：负载均衡把请求分发到多个副本，副本之间不共享内存；如果处理依赖"之前在这个连接上声明过什么"，就必须做 sticky session，扩缩容和故障转移都会出问题。
- **网关与代理**：网关可能把多个下游客户端汇聚到一条上游连接，"连接 = 客户端"的假设不成立。
- **安全**：能力声明决定 server 可以返回哪些内容形态、发起哪些交互；从历史推断会让一个客户端"继承"另一个客户端的能力，构成权限混淆。讲义也强调不能仅凭 stdio 进程、HTTP 连接或某个传输头推断这些值。
- **可测试性**：每个请求可独立重放、独立测试（本节 `test_missing_capabilities_are_not_inferred` 就是这个不变量的测试）。
- 加分点：说出"请求结束后忘掉请求级协议元数据"是第 9 步，也是防止状态泄漏的最后一道保障（对照 Q11 的浅拷贝问题）。

### Q15 — 参考回答要点

- **顺序**（讲义 9 步）：
  1. 解析一个 JSON-RPC 信封；
  2. 确认 `jsonrpc == "2.0"`、有 `id`、`method` 是字符串、`params` 是对象；
  3. 要求 `_meta` 中有版本字符串和 capabilities 对象，否则 `-32602`；
  4. HTTP 边界：比较版本、方法、名称相关的头与 body，不一致 `-32020`（即使其中一个版本值本身也不受支持）；
  5. 一致之后，版本不受支持 `-32022`；
  6. 检查所需 capabilities，按 `method` 路由并校验方法参数；
  7. 在 handler 运行**之前**对具体操作认证、授权；
  8. 返回带 server 身份的完整结果；
  9. 忘掉请求级协议元数据。
- **为什么顺序是安全属性**：如果网关按头里的 `Mcp-Name: notes.read` 做授权，而源站执行 body 里的 `params.name: notes.delete`，攻击者就能以"读"的权限完成"删"。先确认头与 body 一致，才能保证"被授权的"和"被执行的"是同一个操作。
- **为什么顺序也是可观测性属性**：每类失败对应唯一的错误码与阶段，日志能精确区分"请求构造 bug""版本协商""越权""handler 故障"。
- 加分点：指出本节代码把版本检查放在 capabilities 检查前（Q9），以及没有实现第 4、7 步（第 09 节和第 16/18 节分别补上）。

### Q16 — 参考回答要点

- **原则**：讲义"Neither meaning forbids durable application state. A workflow, task, or draft can live behind an opaque handle in a shared store."
- **设计**：
  1. `drafts_create` 工具在共享存储（数据库、Redis 等）中创建草稿，返回一个**不透明 handle**（如随机 ID，不包含可猜测信息）；
  2. 后续 `drafts_edit` / `drafts_commit` 把 handle 作为**普通工具参数**传入；
  3. 任一副本收到请求后，照常完成 9 步生命周期，并对"这个调用者能否操作这个 handle"做认证和授权（handle 本身不是凭证）；
  4. 草稿记录归属主体、过期时间，支持并发控制（版本号 / ETag）。
- **不能放进共享存储的**：协议上下文——协议版本、client capabilities、clientInfo 等。讲义："Protocol context must not leak into that store as a substitute for the removed session." 否则就是把被删除的会话换个地方偷偷复活。
- 加分点：提到第 13 节 MCP Tasks 扩展正是"在无状态核心上运行持久任务"的标准化方案；handle 要设过期与审计。
- 常见误区：用 `Mcp-Session-Id` 或 stdio 进程身份作为草稿归属依据。

### Q17 — 参考回答要点

- **语义**：`ttlMs` 是结果可被复用的时长；`cacheScope` 决定**谁**可以复用。`public` 表示不依赖调用者身份，可跨授权上下文共享（如共享网关缓存）；`private` 表示只能在同一授权上下文内复用。讲义给出的安全默认是 `ttlMs: 0` + `"private"`（本节 `complete_result` 中 `cache_scope or "private"` 也是这个默认）。
- **何时 public**：结果对所有调用者完全相同——如本节固定的两个工具、`server/discover` 的版本列表。
- **何时必须 private**：结果依赖认证主体、租户、权限、地域等——如按角色过滤的工具列表、`resources/read` 读到的用户私有文件。
- **标错的后果**：管理员请求后，带管理工具的列表被网关按 public 缓存，普通用户在 TTL 内命中缓存，看到（并可能让模型尝试调用）本不该看到的工具——信息泄露 + 诱发越权尝试。反过来，把公共结果标 private 只是降低命中率，不会泄露，所以默认偏 private 是安全的取舍。
- **为什么要确定顺序**：等价的响应应该字节级相同，才能得到稳定的缓存键；工具列表进入模型上下文，顺序稳定也让 prompt 前缀缓存命中、模型行为可复现（对照讲义练习 3、4）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：工具的输入/输出契约是 MCP Tools primitive 的基础。
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../02-function-calling-deep-dive/docs/zh.md)：MCP 的 `tools/call` 最终会被 host 转换成各家的 function calling。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../04-structured-output/docs/zh.md)：`inputSchema` 就是 JSON Schema。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：工具命名、描述与可自我纠正的错误信息（对应 Q10）。

### 本节被哪些后续内容用到
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：把本节的校验与分发扩展成完整的 notes server。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：客户端侧的 discover、`-32022` 重试与 legacy 回退。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：生命周期第 4 步的头与 body 一致性检查（`-32020`）。
- [阶段 13 · 10 MCP Resources 与 Prompts：无状态服务端的可寻址上下文](../../10-mcp-resources-and-prompts/docs/zh.md)：另外两个 server primitive。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)、[阶段 13 · 12 显式作用范围与无状态 Elicitation](../../12-mcp-roots-and-elicitation/docs/zh.md)：被弃用的 sampling/roots 的替代方案与 MRTR。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：不透明 handle + 共享存储的标准化（对应 Q16）。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)、[阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：生命周期第 7 步与网关场景。

### 延伸关键词
`JSON-RPC 2.0` · `notification` · `params._meta` · `protocolVersion` · `clientCapabilities` · `server/discover` · `resultType` · `ttlMs / cacheScope` · `-32022 UnsupportedProtocolVersion` · `-32020 header mismatch` · `stateless protocol` · `legacy initialize` · `MRTR` · `opaque handle`
