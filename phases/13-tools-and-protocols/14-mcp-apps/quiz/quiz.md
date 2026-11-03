# 测验 · 无状态协议上的 MCP Apps（MCP Apps on the Stateless Protocol）

> **阶段 13 · 工具与协议 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三层分工 | MCP 核心（`server/discover`、`tools/*`、`resources/*`）负责数据交换；MCP Apps 扩展负责声明 UI 与 iframe↔host 的 bridge；浏览器 sandbox / CSP 限制 UI 能触达的范围 |
| 2 | 2026-07-28 无状态核心 | 没有核心 `initialize` / `notifications/initialized`，没有 `Mcp-Session-Id`；每个请求在 `params._meta` 里自带协议版本与 `clientCapabilities`；成功结果必须带 `resultType` |
| 3 | 扩展协商 | 扩展标识符 `io.modelcontextprotocol/ui`，双方都要 opt-in：服务端在 `server/discover` 的 `capabilities.extensions` 宣告，客户端在**每个请求**的 `clientCapabilities.extensions` 里声明 |
| 4 | UI 绑定在工具定义上 | `tools/list` 返回的工具带嵌套 `_meta.ui.resourceUri`（如 `ui://notes/timeline.html`），host 在调用前就能预取、缓存、做安全审查 |
| 5 | App 资源 | `resources/read` 返回 MIME `text/html;profile=mcp-app` 的 HTML，附 `_meta.ui.csp`（四个域名列表）与 `permissions`，以及 `ttlMs`、`cacheScope` |
| 6 | 校验顺序 | 先 JSON-RPC 形状与 `_meta` 类型 → 再比对路由头与 body（不一致 `-32020`）→ 最后才判断版本是否支持（`-32022`，`data` 精确为 supported/requested）；缺 Apps 能力读 UI 资源 `-32021`；未知方法 404 `-32601` |
| 7 | 通知没有响应体 | 没有 `id` 的消息是 notification：接受时 HTTP 202 空 body；出错也只能改 HTTP 状态码，不能生成 JSON-RPC 错误体 |
| 8 | Apps bridge 有独立生命周期 | View 发 `ui/initialize`（带 `appInfo`、`appCapabilities`）→ host 回复能力与上下文 → View 再发 `ui/notifications/initialized`；它只建立一个 iframe 与一个 host 帧之间的桥，不协商协议版本、不创建服务端会话 |
| 9 | sandbox 是边界不是信任 | CSP 默认全空、按需加域；`connectDomains` 本身就是外泄通道；`postMessage` 固定对端 origin 并校验 `event.origin`；同意（consent）留在 host，iframe 不能批准自己的动作；能力可在运行时撤销 |
| 10 | 文本回退是契约的一部分 | 不支持 Apps 的 host：`tools/list` 同一工具但不带 `_meta.ui`，`tools/call` 仍给有用结果，`resources/read` 拒绝并返回 `-32021` |

### 核心技能（能动手做到）

- [ ] 手写一个 2026-07-28 风格的请求：`params._meta` 三个键 + `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name` 三个路由头，并保证头与 body 一致
- [ ] 给定任意畸形请求，按 `_validate` 的顺序推出 HTTP 状态码与 JSON-RPC 错误码
- [ ] 在 `tools/list` 上按客户端能力决定是否附加 `_meta.ui.resourceUri`，并写出无 Apps 时的文本回退
- [ ] 写出 App HTML 中最小的 bridge 安全代码：固定 `hostOrigin`、校验 `event.origin`、按顺序发送 `ui/initialize` 与 `ui/notifications/initialized`
- [ ] 为 App 资源设计缓存键与失效条件（URI、服务端身份与版本、内容摘要、私有时的授权上下文）
- [ ] 解释 `connectDomains` 与 `resourceDomains` 的区别，并说出放开一个域名带来的外泄与供应链风险

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项在 2026-07-28 核心协议中**已经被移除**？

- A. `server/discover` 方法
- B. 成功结果中的 `resultType` 字段
- C. 核心 `initialize` 握手与 `Mcp-Session-Id` 头
- D. 每个请求的 `params._meta` 中的 `clientCapabilities`

**Q2.** 按本节的"现代 Apps 契约"，一个工具的交互式 UI 应该在哪里声明？

- A. 在 `tools/call` 结果里新增一个专门承载 `ui://` URI 的内容块
- B. 只在 `resources/list` 中列出，host 自行猜测哪个工具对应它
- C. 在 Apps bridge 的 `ui/initialize` 响应里告诉 View
- D. 在 `tools/list` 返回的工具定义上，用嵌套的 `_meta.ui.resourceUri`

**Q3.** 一个请求的 body 里 `protocolVersion` 是 `"2025-11-25"`，而 HTTP 头 `MCP-Protocol-Version` 是 `"2026-07-28"`。本节服务端返回什么？

- A. HTTP 400，`-32022`（不支持的版本）
- B. HTTP 400，`-32020`（头与 body 不一致）
- C. HTTP 400，`-32021`（缺少扩展能力）
- D. HTTP 200，按头部的版本正常处理

**Q4.** 客户端把一个合法的 `resources/list` 请求去掉 `id` 后发送（即变成 notification）。本节服务端的返回是：

- A. HTTP 202，body 为空（`None`）
- B. HTTP 200，带 `result` 但 `id` 为 `null`
- C. HTTP 200，带完整 `result`
- D. HTTP 400，`-32600 Invalid Request`

**Q5.** 某客户端把扩展写成了列表：`"extensions": ["io.modelcontextprotocol/ui"]`，然后读取 `ui://notes/timeline.html`。结果是：

- A. HTTP 200，因为列表里包含了扩展标识符
- B. HTTP 400，`-32602`（参数类型错误）
- C. HTTP 400，`-32021`，`data.requiredCapabilities` 指明需要 `io.modelcontextprotocol/ui`
- D. HTTP 400，`-32020`

**Q6.** 关于 Apps bridge 的 `ui/initialize`，下列说法正确的是：

- A. 它是 iframe 与 host 之间 `postMessage` 方言的握手；host 回复后 View 才发 `ui/notifications/initialized`，它不创建任何 MCP 服务端会话
- B. 它就是被移除的核心 `initialize`，只是换了个名字，作用是协商协议版本
- C. View 应该在发出 `ui/initialize` 的同时立即发出 `ui/notifications/initialized`，不必等待 host
- D. host 收到 `ui/initialize` 请求后就可以立刻向 View 推送消息

**Q7.** App 资源的 CSP 中写了 `connectDomains: ["https://api.example.com"]`。最准确的理解是：

- A. 只允许从该域加载字体、脚本和图片
- B. 表示服务端已经审核过发往该域的数据是安全的
- C. 因为是精确 origin 匹配，所以不存在数据外泄风险
- D. App 内执行的任何脚本都能把它拿到的数据发往该域；精确匹配只防止"发错地方"，不判断载荷是否合适

**Q8.** 讲义要求把 App 资源当作"可执行内容"来缓存。下列缓存键设计最符合讲义的是：

- A. 只用 `ui://` URI，同一个 URI 永远复用
- B. 规范化 `ui://` URI + 已准入的服务端身份与版本 + 资源内容摘要 + （`cacheScope` 为 private 时）授权上下文
- C. `ui://` URI + `ttlMs`
- D. 客户端 `clientInfo.name` + URI

---

## 三、动手 / 代码题

**Q9.** 阅读 `McpAppServer._validate` 与 `handle`，**不运行代码**，写出下面四个请求的 `(HTTP 状态码, JSON-RPC 错误码或"无 body")`。所有请求都由 `make_request` 生成，再按说明修改：

1. `make_request("tools/list", 1)`，然后把 body 与头部的版本**都**改成 `"2025-11-25"`。
2. `make_request("resources/read", 2, {"uri": "ui://x"}, apps=False)`（URI 未知 **且** 没有 Apps 能力）。
3. `make_request("tools/call", 3, {})`（忘了传 `name`）。
4. `make_request("foo/bar", 4)`，然后 `del body["id"]`。

```python
        expected_name = params.get("name") or params.get("uri")
        if method in {"tools/call", "resources/read", "prompts/get"}:
            if headers.get("Mcp-Name") != expected_name:
                raise ProtocolError(-32020, "Mcp-Name header does not match body")
```

**Q10.** App HTML 中每个按钮点击都会调用：

```javascript
callTool("notes_open", {id: button.dataset.note})
```

1. 以当前服务端实现，host 把这个请求转成核心 `tools/call` 发给服务端后会得到什么？
2. 完成讲义练习 5：在服务端加入 `notes_open` 工具（含 `inputSchema`），未知 id 时返回什么比较合适？
3. 用户的"批准"应该放在哪一层？为什么不能由 iframe 里的按钮直接代表授权？

**Q11.** 有同学想在 `handle` 外层用 `contextlib.contextmanager` 写一个计时器：

```python
@contextlib.contextmanager
def timed():
    start = time.perf_counter()
    yield
    print(time.perf_counter() - start)

with timed():
    raise ProtocolError(-32020, "mismatch")
```

结果没有看到 `ProtocolError`，而是 `dataclasses.FrozenInstanceError: cannot assign to field '__traceback__'`。另外 `str(ProtocolError(code=-1, message="y"))` 返回空字符串。请解释这两个现象，并给出修复。

**Q12.** `tools/list` 的结果写的是 `"cacheScope": "public"`，但它的内容随客户端是否声明 Apps 扩展而不同。

1. 如果一个共享缓存只用 `method` 作为键，会出现什么问题？分两种先后顺序说明。
2. 讲义说"当可见工具因用户或 token 不同而变化时用 `private`"。这里应该改成 `private` 吗？给出你的缓存键设计。
3. 练习 3：什么情况下 UI 资源本身应改成 `cacheScope: private`？

---

## 四、面试高频题

**Q13.**（基础必考）请完整讲一遍 MCP Apps 从"发现"到"渲染并可交互"的流程，并指出每一步属于核心协议、Apps 扩展还是浏览器 sandbox。

**Q14.**（原理深挖）为什么 MCP Apps 要把 UI 绑定在 `tools/list` 的工具定义上（调用前元数据），而不是让 `tools/call` 的结果"顺便返回一个 HTML"？

**Q15.**（工程实践）你负责一个 MCP host，要渲染第三方服务端提供的 App。请列出 host 侧必须做的安全措施。

**Q16.**（场景设计）为企业内部"报销审批"工具设计一个 MCP App：数据因人而异、需要审批按钮、可能要连一个内部 API。请给出 discovery、工具声明、资源、缓存、CSP、bridge、回退的设计要点。

**Q17.**（追问型）面试官问："既然核心协议删掉了 `initialize`，Apps 又搞了个 `ui/initialize`，这不就是把状态又加回来了吗？还有，为什么一定要先比对头部再判断版本？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义 The Problem 一节列出："There is no core `initialize` request or `notifications/initialized` notification. There is no `Mcp-Session-Id` header."

- A 错：`server/discover` 是新增的、服务端**必须**支持的发现方法。
- B 错：每个成功结果都要带 `resultType` 判别字段（代码 `_success` 用 `setdefault("resultType", "complete")` 补上）。
- D 错：`clientCapabilities` 恰恰是"每个请求都必须带"的，代码中缺了就返回 `-32602 clientCapabilities is required on every request`。

### Q2 — 答案：D

讲义："The modern Apps contract binds a UI to the tool in `tools/list`"，并强调这是 "deliberately pre-call metadata"。代码中 `if self._apps_enabled(meta): tool["_meta"] = {"ui": {"resourceUri": RESOURCE_URI}}`。

- A 错：讲义明确"Avoid inventing a new content block just to repeat the URI"，host 早已知道视图属于哪个工具。
- B 错：`resources/list` 只列出资源，不建立"工具 ↔ 视图"的绑定。
- C 错：`ui/initialize` 是 View 已经加载之后的 bridge 握手，此时 UI 早就该确定了。

### Q3 — 答案：B

`_validate` 先比对 `headers["MCP-Protocol-Version"] != requested_version`，不一致立即抛 `-32020`，根本走不到版本支持检查。测试 `test_header_version_mismatch_precedes_version_support_check` 正是验证这一点。

- A 错：只有当头和 body **一致地**声明了一个不支持的版本时才是 `-32022`。
- C 错：`-32021` 是读 UI 资源却缺 Apps 能力。
- D 错：服务端从不"挑一个信"，歧义必须拒绝——否则代理按头路由、服务端按 body 执行，两者看到的是不同的请求。

### Q4 — 答案：A

`handle` 中 `is_notification = "id" not in body`；处理成功后 `if is_notification: return 202, None`。测试 `test_accepted_notification_returns_202_with_empty_body` 实际验证。JSON-RPC 规定 notification 不产生响应对象，B、C 都违反这一点；D 错，没有 `id` 不是"无效请求"，JSON-RPC 本来就允许 notification。（注意：本模型会照样执行 `resources/list` 的逻辑，只是不返回结果。）

### Q5 — 答案：C

`_apps_enabled` 要求 `extensions` 是 dict **且** `extensions.get(APPS_EXTENSION)` 也是 dict：

```python
        return (
            isinstance(extensions, dict)
            and isinstance(extensions.get(APPS_EXTENSION), dict)
        )
```

列表不满足，于是视为没有 Apps 能力，`resources/read` 抛 `-32021` 并带 `data.requiredCapabilities.extensions.io.modelcontextprotocol/ui`。测试 `test_malformed_extension_map_does_not_grant_apps_capability` 验证了这一点。A 错在"宽松解析"会把畸形输入当成授权；B 错，`-32602` 只用于 `_meta`/`clientCapabilities` 缺失或类型错误，而这里 `clientCapabilities` 本身是 dict；D 错，头与 body 是一致的。（实际验证：把扩展值写成 `True` 也同样不算启用。）

### Q6 — 答案：A

讲义："The View sends `ui/initialize` ... The host returns its capabilities and host context. Only after that response does the View send `ui/notifications/initialized`. The host must wait for this Apps notification before sending messages to the View." 以及 "It does not negotiate the MCP protocol version, create server state, or mint a transport session."

- B 错：两者属于不同协议层，前缀也不同（核心 `notifications/initialized` 已删除，Apps 的 `ui/notifications/initialized` 仍存在）。
- C 错：必须等 host 的响应。代码里 View 只有在收到 `id === 0` 且带 `result` 的消息后才发 initialized。
- D 错：host 要等到 `ui/notifications/initialized` 才能向 View 发消息。

### Q7 — 答案：D

讲义："An allowed domain is still an exfiltration path ... Exact origin matching prevents destination confusion, but it does not decide whether the payload is appropriate."

- A 错：加载脚本/样式/图片/字体由 `resourceDomains` 控制；`connectDomains` 管 fetch、XHR、WebSocket。
- B 错：CSP 是浏览器的目的地策略，不对内容做任何审查。
- C 错：精确匹配恰恰只解决"发到哪"，不解决"发什么"。讲义建议默认为空、不在 iframe 里放 bearer token、尽量由 host 代理窄操作、限制请求/响应大小并审计每个外发请求由哪个用户动作触发。

### Q8 — 答案：B

讲义 "Cache UI resources as executable content"：键为 canonical `ui://` URI、admitted server identity and version、resource content digest，以及 `cacheScope` 为 private 时的授权上下文；"Never reuse a private App resource across principals"。

- A 错：同一个 URI 在不同服务端版本、不同用户下 HTML 和策略元数据都可能不同。
- C 错：`ttlMs` 是失效条件，不是身份。
- D 错：`clientInfo` 是"自报数据，不是授权身份"（讲义原话），不能用作安全边界。

### Q9 — 参考答案

已逐一实际运行验证：

| 请求 | 结果 | 原因 |
|------|------|------|
| 1. 头与 body 都是 `2025-11-25` | `(400, -32022)`，`data = {"supported": ["2026-07-28"], "requested": "2025-11-25"}` | 头 body 一致，通过 `-32020` 检查后才判断版本不支持 |
| 2. 未知 URI + 无 Apps | `(400, -32602 "Unknown resource URI")` | 分支里先检查 URI，再检查 Apps 能力 |
| 3. `tools/call` 缺 `name` | `(400, -32020 "Mcp-Name header does not match body")` | `make_request` 把头写成 `""`，而 `expected_name` 是 `None`，`"" != None` |
| 4. notification `foo/bar` | `(404, None)` | 未知方法 `-32601` 映射到 404；notification 不允许有 JSON-RPC 错误 body |

讨论：

- 第 2 题是一个**设计选择**：先报"资源不存在"会让一个没有 Apps 能力的客户端也能探测 UI 资源 URI 是否存在。反过来先检查能力，就不会泄露这一信息。两种顺序都说得通，但要有意识地选择。
- 第 3 题暴露了一个小瑕疵：本应是参数错误（缺少必填 `name`），却因为头部用了 `""` 兜底而变成了路由不一致。更清晰的做法是在比较头部前先检查 `tools/call` 的 `name` 是否为非空字符串，返回 `-32602`。

### Q10 — 参考答案

1. 当前 `tools/call` 分支只认 `notes_timeline`：`if params.get("name") != "notes_timeline": raise ProtocolError(-32602, "Unknown tool")`。实际运行得到 `(400, {"error": {"code": -32602, "message": "Unknown tool"}})`。也就是说**示例 HTML 里的按钮调用的是一个不存在的工具**，这正是练习 5 留给读者补的部分。

2. 参考实现（已在子类中实际运行验证，返回结果见下）：

```python
NOTES_BY_ID = {note["id"]: note for note in NOTES}

# tools/list 中追加第二个工具（同样可按需附 _meta.ui）
open_tool = {
    "name": "notes_open",
    "description": "Open one note by id.",
    "inputSchema": {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
    },
}

# tools/call 分支
elif method == "tools/call" and params.get("name") == "notes_open":
    note = NOTES_BY_ID.get((params.get("arguments") or {}).get("id"))
    if note is None:
        result = {"content": [{"type": "text", "text": "Unknown note id."}], "isError": True}
    else:
        result = {
            "content": [{"type": "text", "text": f"{note['title']} ({note['created']})"}],
            "structuredContent": {"note": note},
            "isError": False,
        }
```

实际输出：`notes_open {"id": "note-2"}` → `content` 为 `"Per-request metadata (2026-07-29)"`，`isError: False`；未知 id → `isError: True`，HTTP 仍为 200。区分要点：**未知工具**是协议层错误（`-32602`），**工具执行失败**（参数合法但找不到记录）应该用结果里的 `isError: true` 表达，让模型/host 能读到错误文本。

3. 批准放在 **host**。讲义："Keep user consent in the host. The iframe cannot approve its own consequential action." 以及 "A button click and a valid bridge message express intent; neither grants authority." iframe 里的代码来自第三方服务端，可能被 XSS、可能被恶意内容诱导，它发出的 `tools/call` 只是"意图"；host 要校验类型化请求、当前用户、目标与参数，按策略弹出确认或拒绝，并且在**动作发生时**检查能力是否仍有效（可能已被撤销）。

### Q11 — 参考答案

1. **FrozenInstanceError**：`@dataclass(frozen=True)` 会生成一个 `__setattr__`，对**任何**属性赋值都抛 `FrozenInstanceError`。`contextlib.contextmanager` 在 `__exit__` 中把异常重新抛进生成器之前，会在 Python 层执行 `exc.__traceback__ = traceback`，于是触发了冻结检查。直接 `raise`/`except` 不会出问题，因为解释器在 C 层设置 `__traceback__`，绕过了 `__setattr__`——这也是本节测试全部通过的原因。（已实际运行复现。）
2. **`str()` 为空**：dataclass 生成的 `__init__` 不调用 `Exception.__init__`。`BaseException.__new__` 会记录**位置参数**为 `args`，所以 `ProtocolError(-32020, "x")` 的 `str` 是 `"(-32020, 'x')"`；而用关键字参数构造时 `args == ()`，`str` 为空字符串，日志里就什么也看不到。
3. 修复：去掉 `frozen=True`，并在 `__post_init__` 中调用 `super().__init__(self.code, self.message)`：

```python
@dataclass
class ProtocolError(Exception):
    code: int
    message: str
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__init__(f"{self.code}: {self.message}")
```

或者干脆写普通类 `class ProtocolError(Exception): def __init__(self, code, message, data=None): ...`。经验：**异常类不要用 frozen dataclass**。

### Q12 — 参考答案

1. 问题：`tools/list` 的响应取决于请求里的 `clientCapabilities`。
   - 先缓存了 Apps 客户端的响应 → 非 Apps 客户端拿到带 `_meta.ui` 的工具，它会去读 UI 资源，却收到 `-32021`（或者不认识这个字段而忽略）。
   - 先缓存了非 Apps 客户端的响应 → Apps 客户端拿不到 UI 绑定，App 永远不渲染，功能"悄悄降级"。
2. 不需要改成 `private`：这里变化的维度是**客户端能力**，不是用户身份或 token，不涉及敏感数据泄露。但缓存键必须包含影响结果的请求输入：`(服务端身份 + 版本, method, protocolVersion, 规范化后的 extensions 集合)`。如果工具可见性还依赖用户权限，就再加上授权上下文并改为 `private`。
3. UI 资源改为 `private` 的条件：HTML 或其 `_meta.ui`（CSP、permissions）因用户/租户/token 而不同。例如 HTML 中内嵌了当前用户的数据、按租户配置不同的 `connectDomains`、按用户角色显示不同的操作按钮。本节的 HTML 只内嵌了固定的三条 `NOTES`，与用户无关，所以 `public` 合理；一旦 `NOTES` 来自"当前用户的笔记"，就必须 `private`，且缓存键要带授权上下文，绝不能跨 principal 复用。

### Q13 — 参考回答要点

1. **发现**（核心）：客户端发 `server/discover`，请求的 `_meta.clientCapabilities.extensions` 带 `io.modelcontextprotocol/ui`；服务端回复 `supportedVersions`、`capabilities.extensions` 中包含该扩展、`ttlMs`/`cacheScope`、`serverInfo`。
2. **列出工具**（核心 + Apps 元数据）：`tools/list` 返回工具，带 `_meta.ui.resourceUri`。host 此时即可预取 UI。
3. **列出/读取资源**（核心）：`resources/list` 给出稳定描述；`resources/read` 带 `Mcp-Name: ui://...` 头，返回 `text/html;profile=mcp-app` 的 HTML 与 `_meta.ui.csp`、`permissions`。
4. **审查与挂载**（host + 浏览器）：host 审查 CSP/权限，按自己的隔离设计选择 sandbox 属性，渲染到 iframe。
5. **调用工具**（核心）：模型或用户触发 `tools/call`，结果是 `content` + `structuredContent`，`resultType: "complete"`。
6. **bridge 握手**（Apps）：View `ui/initialize` → host 响应 → View `ui/notifications/initialized` → host 把工具结果、主题等上下文推给 View。
7. **交互**（Apps + 核心）：View 通过 bridge 请求动作，host 校验与征得同意后，生成一个**新的、自包含**的核心请求（新 id、完整 `_meta`）。
- 加分点：强调每一步都是独立请求，没有会话；以及无 Apps 时的文本回退路径。

### Q14 — 参考回答要点

- **可预审**：HTML 是可执行内容，host 需要在它被要求显示前就能获取、缓存、做安全审查（CSP、权限、内容摘要、准入策略）。等到调用后才知道 UI，就只能"边执行边审查"。
- **可预加载**：渲染延迟更低，用户点击后立即出现界面。
- **结果保持纯粹**：`tools/call` 只返回数据（`content` + `structuredContent`），同一结果同时服务于 Apps host、纯文本 host 和模型；host 已经知道视图归属，不必再造一个内容块重复 URI。
- **防止动态注入 UI**：如果结果可以随意指定任意 HTML，被提示注入污染的结果就可能让 host 渲染攻击者控制的页面；把绑定放在经过准入的工具元数据上，变化可被检测（descriptor pin、版本变化会触发重新审查）。
- 常见误区：认为"UI 是展示层，随结果走更灵活"。灵活的代价是失去审查窗口。

### Q15 — 参考回答要点

- **隔离**：在独立 origin 的 sandboxed iframe 中渲染；根据自己的 origin 模型选择 `sandbox` 标志，不要照抄教程。App 不能读 host 的 cookie、localStorage、DOM。
- **CSP**：按资源 `_meta.ui.csp` 执行，默认全空；拒绝通配域名；区分 `connectDomains` 与 `resourceDomains`；`frameDomains`、`baseUriDomains` 同样从空开始。
- **权限**：不授予相机/麦克风/位置，除非有可见功能需要。
- **bridge**：`postMessage` 指定精确 target origin，接收端校验 `event.origin`、`jsonrpc`、方法白名单与参数 schema；所有 bridge 消息、工具参数/结果、资源文本都视为不可信输入。
- **同意与授权**：consequential 动作必须由 host 弹出确认；在动作时检查能力和授权，而不仅是在 `ui/initialize` 时。
- **撤销**：账户切换、策略变化、服务端被隔离时，拒绝挂起的特权调用、停止不合规的网络活动、清除敏感渲染状态，必要时卸载或回退到文本。
- **布局安全**：View 只能"请求"尺寸，host 设上限，防止覆盖 host UI 造成欺骗（clickjacking 类风险）；同时保证键盘焦点与无障碍。
- **缓存**：按 Q8 的键缓存，版本/摘要变化时重新审查后才重新挂载。

### Q16 — 参考回答要点

- **Discovery**：宣告 `tools`、`resources`、`extensions.io.modelcontextprotocol/ui`；`cacheScope` 可 public（与用户无关）。
- **工具**：`expense_list`（只读，带 `_meta.ui.resourceUri: ui://expenses/review.html`）与 `expense_approve`（有副作用，`inputSchema` 严格：`expense_id`、`decision` 枚举、`comment` 限长）。因为可见工具可能随用户角色变化，`tools/list` 用 `private` 并按授权上下文缓存。
- **资源**：HTML 尽量是**与用户无关的模板**，数据通过工具结果的 `structuredContent` 下发——这样 UI 资源可以 `public` 缓存，敏感数据不进入可共享缓存。若必须内嵌用户数据，则 `private` + 授权上下文键。
- **CSP**：`connectDomains` 保持为空，内部 API 调用改为由 host 代理的窄工具调用（`expense_approve`），避免在 iframe 中放 bearer token；`resourceDomains` 为空，脚本与样式全部内联打包。
- **bridge**：按钮 → `tools/call expense_approve` 请求 → host 校验当前用户是否有审批权、显示金额与申请人让用户确认 → 生成新的核心请求；拒绝作为正常结果返回，View 不得重试轰炸。
- **回退**：非 Apps host 下 `expense_list` 返回可读的文本表格（不是 "Timeline ready." 这种空话），`expense_approve` 仍可由模型通过对话调用，由 host 的常规确认机制把关。
- **测试**：头/body 不一致 `-32020`、版本 `-32022`、无能力读 UI `-32021`、未知方法 404、notification 202、跨用户缓存隔离、撤销权限后按钮调用被拒。

### Q17 — 参考回答要点

- **`ui/initialize` 不是把状态加回来**：
  - 它是 iframe 与 host 帧之间的**本地** `postMessage` 握手，不经过 MCP 传输，不到达服务端。
  - 它不协商 MCP 协议版本、不创建服务端状态、不签发会话 ID。
  - bridge 触发的每个核心请求仍是新的、自包含的请求，带新 JSON-RPC id 和完整 `_meta`；服务端照样可以水平扩展、无需粘性会话。
  - 状态存在于 host 的浏览器页面中，这本来就是 UI 的天然归属。
- **为什么先比头部再判断版本**：
  - 代理/网关按 `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 头做路由、限流和授权，而服务端按 body 执行。若两者不一致还继续处理，就会出现"代理放行的是 A，服务端执行的是 B"的请求走私（request smuggling）类问题。
  - 只有确认双方看到的是同一个请求后，"这个版本支持吗"才是一个有意义的问题；而 `-32022` 的 `data.requested` 也才有唯一的取值。
- 加分点：指出校验顺序的完整链条——JSON-RPC 形状 → `_meta` 类型 → 头 body 一致 → 版本 → 方法 → 特性能力（`-32021`）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：`_meta`、`resultType`、JSON-RPC 请求与通知的区别。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：本节服务端的基础写法。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：完整的 HTTP 适配器（`Content-Type`、`Accept`、405），本节只建模了解析后的请求。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：`resources/list` / `resources/read` 与 URI 寻址。
- [阶段 13 · 12 显式作用范围与无状态 Elicitation](../../12-mcp-roots-and-elicitation/docs/zh.md)：把"用户同意"留在 host 的另一种形式。

### 本节被哪些后续内容用到
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：工具元数据与 UI 资源都可能被投毒，头 body 一致性是路由安全的基础。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关按路由头转发、对 descriptor 做 pin，与 App 资源的缓存失效直接相关。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把 Apps 扩展放进完整生态中。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：`content` 与 `structuredContent` 的契约。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：为什么工具结果、资源文本和 bridge 消息都要当作不可信输入。
- [阶段 19 · 13 综合项目 13：带注册表与治理机制的 Stateless MCP 服务端](../../../19-capstone-projects/13-mcp-server-with-registry/docs/zh.md)：在综合项目中实现完整的无状态 MCP 服务端。

### 延伸关键词
`io.modelcontextprotocol/ui` · `ui://` · `text/html;profile=mcp-app` · `server/discover` · `resultType` · `ttlMs / cacheScope` · `Content-Security-Policy` · `iframe sandbox` · `postMessage targetOrigin` · `clickjacking` · `request smuggling` · `progressive enhancement / 文本回退`
