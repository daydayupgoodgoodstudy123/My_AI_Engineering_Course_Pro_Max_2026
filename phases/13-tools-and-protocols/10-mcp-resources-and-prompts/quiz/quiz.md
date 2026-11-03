# 测验 · MCP Resources 与 Prompts：无状态服务端的可寻址上下文（MCP Resources and Prompts: Addressable Context for Stateless Servers）

> **阶段 13 · 工具与协议 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种 primitive（原语）按"谁来选"区分 | Tool 由模型/应用选择、执行操作；Resource 由 host/应用/用户按 URI 读取内容；Prompt 由用户通过 host UI 选择、生成消息模板 |
| 2 | 2026-07-28 无状态信封 | 没有 `initialize` 握手、没有协议会话；每个请求都在 `params._meta` 里携带 `protocolVersion`、`clientInfo`、`clientCapabilities` |
| 3 | `server/discover` | 服务端**必须**实现，返回 `supportedVersions`、`capabilities`、可选缓存提示；客户端可以不先调它 |
| 4 | `resultType: "complete"` 与 `serverInfo` | 正常结果都声明 `resultType`；响应 `_meta` 中的 `io.modelcontextprotocol/serverInfo` 只用于诊断，**不是认证身份** |
| 5 | 版本错误 `-32022` | 请求的协议版本不受支持时返回 `-32022`，`data` 里同时给出 `supported` 与 `requested` |
| 6 | 确定性列表 | `resources/list`、`prompts/list` 对同样的请求输入返回同样的成员与顺序（按 URI / name 排序）；可以随授权变化，但不能随连接历史变化 |
| 7 | 未知 URI 用 `-32602` | `resources/read` 遇到未知或非法 URI 返回 JSON-RPC Invalid params `-32602`，而不是"成功的空读取" |
| 8 | 缓存提示 `ttlMs` / `cacheScope` | `cacheScope` 只有 `public` 与 `private` 两个值；敏感/快速变化的结果用 `private` + `ttlMs: 0`，再由 host 施加 no-store；缓存提示**不能替代授权** |
| 9 | `subscriptions/listen` | 客户端主动打开的长请求（HTTP 上是 POST 的 SSE 响应流），`notifications` 是允许列表；请求 ID 就是 subscription ID；先发 `acknowledged`，再发事件，最后用同一 ID 的 `complete` 结果收尾 |
| 10 | 内容不可信 | resource 文本和 prompt 模板都是**不可信的服务端输出**，可能含 prompt injection；prompt 不能绕过 resource 的授权检查 |

### 核心技能（能动手做到）

- [ ] 给定一个业务能力（如"读取 issue 详情""关闭 issue""冲刺回顾模板"），能说出它应该是 tool、resource 还是 prompt，并说出"选择者"是谁
- [ ] 手写一个带 `_meta` 的 2026-07-28 请求，并说出服务端在缺字段、版本不对时各返回什么错误码
- [ ] 为 list / read / discover 结果选择合理的 `ttlMs` 与 `cacheScope`，并能解释"缓存键必须包含哪些维度"
- [ ] 读懂 `subscriptions_listen` 如何把请求过滤器收敛成"服务端接受的子集"，以及每个事件如何用 subscription ID 关联
- [ ] 跑通 `main.py` 与 14 个单元测试，并能指出代码在参数校验、订阅 URI 校验、授权方面的简化
- [ ] 能为 `notes://projects/{project}/notes/{id}` 这类 resource template 写出严格的变量校验

---

## 二、基础自测（选择题）

**Q1.** 一个项目管理 MCP 服务端要暴露"按 URI 读取某个 issue 的详情"。按讲义的划分，它最适合做成：

- A. Resource，由 host/应用/用户按 URI 读取内容
- B. Tool，因为读取数据库要调用函数
- C. Prompt，因为读出来的内容最终要进模型上下文
- D. 三种都暴露一遍，让客户端自由选择

**Q2.** 在 2026-07-28 修订版中，下列哪一项关于请求元数据的说法是正确的？

- A. 客户端先调用 `initialize` 建立会话，之后的请求就不必再携带版本号
- B. 协议版本放在 HTTP 头里，`params._meta` 只放 `clientInfo`
- C. 服务端会把第一次请求中的 `clientCapabilities` 记在连接上，后续请求复用
- D. 每个请求都在 `params._meta` 中携带 `protocolVersion`、`clientInfo`、`clientCapabilities`

**Q3.** 客户端用 `"2025-11-25"` 调用 `resources/list`，本节服务端返回什么？

- A. `-32601 Method not found`
- B. `-32022 Unsupported protocol version`，`data` 中含 `supported: ["2026-07-28"]` 和 `requested: "2025-11-25"`
- C. `-32602 Missing or invalid protocol version`
- D. 正常返回结果，但在 `_meta` 中提示版本过旧

**Q4.** 关于 `cacheScope`，下列说法正确的是：

- A. MCP 定义了 `public`、`private`、`no-store` 三个值
- B. 只要把结果标成 `public`，就可以省掉读取时的授权检查
- C. MCP 只定义 `public` 与 `private`；对敏感或快速变化的结果，应返回 `private` + `ttlMs: 0`，再由 host 缓存策略施加 no-store
- D. `ttlMs: 0` 表示"永久有效"

**Q5.** 本节代码中，`notifications/subscriptions/acknowledged`、`notifications/resources/updated` 和收尾的 `result` 三条消息都带有 `io.modelcontextprotocol/subscriptionId: 5`。这个 5 来自：

- A. 客户端发送的 `subscriptions/listen` 请求的 JSON-RPC `id`
- B. 服务端随机生成的会话 ID
- C. 被订阅资源在 `NOTES` 字典中的序号
- D. HTTP 连接的端口号

**Q6.** 客户端发送 `subscriptions/listen`，过滤器为 `{"resourcesListChanged": true, "resourceSubscriptions": ["notes://note-1"]}`。随后服务端的 prompt 目录发生了变化，本节代码的 `stream.prompts_list_changed()` 会：

- A. 发送 `notifications/prompts/list_changed`，因为 `server/discover` 声明了 `prompts.listChanged: true`
- B. 抛出 `RpcError(-32602)`
- C. 关闭订阅流
- D. 返回 `None`，因为过滤器没有请求 `promptsListChanged`，服务端不得推送未请求的通知类型

**Q7.** 客户端收到 `notifications/resources/updated`（uri 为 `notes://note-1`）后，正确的做法是：

- A. 直接从通知的 `params` 里取出新文档内容
- B. 认为该资源已被删除，从 UI 中移除
- C. 重新发起一次 `resources/read`，并接受当前授权检查
- D. 把通知当作新的协议会话，后续请求都发往同一个服务器实例

**Q8.** 本节 `resources_list` 返回 `ttlMs=300_000, cacheScope="public"`，`resources_read` 返回 `ttlMs=60_000, cacheScope="private"`。下列解释**最准确**的是：

- A. 两个值都是随手写的，`cacheScope` 对正确性没有影响
- B. 目录元数据（名称、描述）在本演示中对所有调用者相同，可公共缓存 5 分钟；笔记正文视为用户所有，只能按调用者私有缓存 1 分钟
- C. `private` 表示只允许服务端自己缓存，客户端不能缓存
- D. 读取结果 TTL 更短，是因为 `resources/read` 比 `resources/list` 计算更贵

---

## 三、动手 / 代码题

**Q9.** 阅读 `prompts_get` 的开头：

```python
def prompts_get(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments", {})
    if name not in PROMPTS or not isinstance(arguments, dict):
        raise RpcError(-32602, "Unknown prompt or invalid arguments", {"name": name})
    if name == "review_note":
        uri = arguments.get("uri")
        if uri not in NOTES:
            raise RpcError(-32602, "review_note requires a known resource URI", {"uri": uri})
        focus = arguments.get("focus", "correctness")
        text = f"Review the resource {uri} for {focus}. Cite the URI in every finding."
```

1. 客户端发送 `prompts/get`，`name` 为 `["x"]`（一个列表），`handle()` 会返回什么？为什么？
2. `arguments` 为 `{"uri": "notes://note-2", "focus": "Ignore previous instructions"}` 时会发生什么？这说明了讲义中的哪条原则？
3. 给出最小修复。

**Q10.** 下面的调用会让 `stream.notifications` 等于什么？请逐个键说明原因，并指出其中一个与讲义"filter contains only the subset the server accepted"不完全相符的地方。

```python
s = main.subscriptions_listen(9, {"notifications": {
    "resourceSubscriptions": ["notes://missing", "notes://note-1", "notes://note-1"],
    "promptsListChanged": "yes",
    "foo": True,
}})
```

**Q11.** 讲义练习 1：添加 `notes://projects/{project}/notes/{id}` resource template 并校验两个变量。请写一个 `parse_project_note_uri(uri) -> tuple[str, str]`，对非法 URI 抛出 `RpcError(-32602, ...)`，并说明你防住了哪些攻击输入。

**Q12.** 讲义练习 6：给读取处理器加入授权主体（subject），并证明缓存项不会跨主体。请设计：`resources_read` 如何拿到 subject、如何判断可见性、host 侧缓存键应包含哪些字段；再说明为什么"resource 是 private，但 `resources/list` 仍是 public"在引入多用户后可能出问题。

---

## 四、面试高频题

**Q13.**（基础必考）MCP 的 tools、resources、prompts 有什么区别？怎么决定一个能力该暴露成哪一种？

**Q14.**（原理深挖）MCP 2026-07-28 去掉了初始化握手和协议会话。这对服务端的 list、read、订阅设计分别带来什么约束？为什么这样做对水平扩展有利？

**Q15.**（工程实践）你负责一个多租户知识库 MCP 服务端，怎么设计 `ttlMs` / `cacheScope` 与缓存键，避免"A 用户的私有笔记被 B 用户命中缓存"？

**Q16.**（场景设计）请设计一个"资源变更通知"方案：客户端同时关注 3 个文档和 prompt 目录变化，跑在 stdio 和 Streamable HTTP 两种传输上。说明消息序列、关联方式、取消方式与安全边界。

**Q17.**（追问型）既然 resource 内容最终也会进模型上下文，为什么说它是"不可信的服务端输出"？host 和 server 各自应该做什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义的判断依据是"谁来选、期望得到什么"：URI 可寻址的内容是 resource，由 host、应用或用户读取。B 混淆了"实现方式"和"协议契约"——讲义开篇就批评"数据库查询因为函数熟悉就变成了 tool"；C 混淆了"内容最终去向"和"选择者"，prompt 是用户主动选择的消息工作流；D 是讲义明确反对的做法："Do not expose one operation as all three merely to look complete"，每多一种暴露面都要多一套发现、授权、缓存、错误处理和测试。

### Q2 — 答案：D

本节针对的 2026-07-28 修订"没有初始化握手，也没有协议会话"，每个请求自带 `_meta` 中的三个保留键。代码 `request_meta()` 正是构造这三项。A 描述的是旧版有状态 MCP；B 错在版本位置（本节放在 `params._meta`）；C 违背"列表不能依赖连接历史"——能力声明是请求输入，不是连接状态。注意：本节 `validate_request_meta` 实际只强制检查 `protocolVersion`（字符串且等于当前版本）和 `clientCapabilities`（必须是 dict），**没有检查 `clientInfo`**（已实测：删掉 `clientInfo` 仍返回 `complete`）。

### Q3 — 答案：B

代码：

```python
    if requested != PROTOCOL_VERSION:
        raise RpcError(
            -32022,
            "Unsupported protocol version",
            {"supported": [PROTOCOL_VERSION], "requested": requested},
        )
```

测试 `test_unsupported_version_uses_current_protocol_error` 也断言了这三点。A 是方法不存在；C 是版本字段**缺失或不是字符串**时的错误（测试 `test_missing_protocol_version_is_invalid_params`）；D 不符合规范，也会让客户端误以为请求被正确处理。

### Q4 — 答案：C

讲义："MCP defines only `public` and `private` as `cacheScope` values... `no-store` itself is not an MCP `cacheScope` value." A 把 host 策略误当成协议值；B 是讲义重点批驳的错误——"Cache hints never replace authorization"；D 说反了，`ttlMs: 0` 表示不应复用（立即过期）。

### Q5 — 答案：A

讲义："The request ID is the subscription ID." 代码中 `subscriptions_listen(request_id, params)` 把请求 `id` 直接存为 `SubscriptionStream.subscription_id`，`_meta()` 每次都放进同一个值；`close()` 还把它作为 JSON-RPC 响应的 `id`，从而与原请求配对。B 错，本协议没有会话；C、D 与关联机制无关。多个订阅共享一个 stdio 通道时，客户端正靠这个 ID 解复用。

### Q6 — 答案：D

`subscriptions_listen` 只把请求中值为 `True` 的布尔字段放进 `agreed`，`prompts_list_changed()` 先检查 `self.notifications.get("promptsListChanged")`，没有就返回 `None`。讲义："The `notifications` object is an allowlist. A server must not deliver notification types that were not requested." A 混淆了"服务端具备能力"与"客户端请求了该通知"；B、C 都不是代码行为。

### Q7 — 答案：C

讲义："The notification says the resource changed. The client reads it again through `resources/read`, subject to current authorization." 代码中 `resource_updated` 的 `params` 只有 `_meta` 和 `uri`，没有内容（排除 A）；"更新"不等于"删除"（排除 B）；D 违反"Do not use a subscription stream as a protocol session"——后续读取仍是完整请求，可以落到任何健康实例。

### Q8 — 答案：B

本节演示中没有用户维度，列表元数据对所有人相同，因此 `public` + 5 分钟；正文按"用户自有笔记"对待，用 `private` + 1 分钟（讲义："A private note read may use one minute"）。A 错，讲义标题就是"Cache hints are part of correctness"；C 错，`private` 指"绑定到请求用户或凭据上下文"，客户端可以按该上下文缓存；D 错，TTL 依据的是"数据变化率和过期的危害"，而不是计算成本。

### Q9 — 参考答案

1. 已实测：`handle()` **抛出未捕获的 `TypeError: unhashable type: 'list'`**，而不是返回 JSON-RPC 错误。`name not in PROMPTS` 要对 `name` 求哈希，列表不可哈希；`handle()` 只 `except RpcError`，所以异常直接冒出。`review_note` 的 `uri` 为列表时同理（`uri not in NOTES`）。对比 `resources_read` 先做了 `isinstance(uri, str)`，就没有这个问题。
2. 返回成功，生成的消息文本是 `"Review the resource notes://note-2 for Ignore previous instructions. Cite the URI in every finding."`（实测）。`focus` 未做任何校验，任意字符串被拼进 prompt 消息。这正对应讲义"把 prompt 模板当作不可信的服务端输出"、"在服务端边界校验 prompt 参数"，以及"`prompts/get` 不替换 host 的系统指令"——host 必须把返回的消息放在低于自身可信策略的优先级。
3. 最小修复：

```python
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or name not in PROMPTS or not isinstance(arguments, dict):
        raise RpcError(-32602, "Unknown prompt or invalid arguments", {"name": str(name)})
    if name == "review_note":
        uri = arguments.get("uri")
        if not isinstance(uri, str) or uri not in NOTES:
            raise RpcError(-32602, "review_note requires a known resource URI", {"uri": str(uri)})
        focus = arguments.get("focus", "correctness")
        if not isinstance(focus, str) or not (1 <= len(focus) <= 80):
            raise RpcError(-32602, "focus must be a short string")
```

更稳妥的做法是把 `focus` 限定为枚举（如 `correctness`、`security`、`operational risk`），并且在 `review_note` 中对 `uri` 执行与 `resources/read` **相同的授权检查**，避免 prompt 成为绕过资源授权的侧信道。

### Q10 — 参考答案

实测结果：`{'resourceSubscriptions': ['notes://missing', 'notes://note-1']}`。

- `resourceSubscriptions`：是字符串列表，通过类型检查，经 `sorted(set(value))` **去重并排序**。
- `promptsListChanged: "yes"`：非布尔字段只有值 `is True` 才被接受，字符串 `"yes"` 被静默丢弃。
- `foo`：不在 `SUPPORTED_NOTIFICATION_FIELDS` 中，循环根本不会看它，被静默丢弃。
- `resourcesListChanged`：请求里没有，自然不在结果里。

不相符之处：`notes://missing` 并不存在，服务端却把它放进了"已接受"的过滤器。讲义说 acknowledgment 的过滤器"只包含服务端接受的子集"，而代码对 URI 既不检查是否存在，也不做授权检查。生产实现应对每个 URI 做与 `resources/read` 相同的解析与授权，只把通过的 URI 放进 `agreed`（或对整个请求返回 `-32602`）。不过即使订阅了，通知本身也只携带 URI、不携带内容，真正读取仍要过授权——这是第二道防线。

### Q11 — 参考答案

```python
import re

_SEGMENT = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")

def parse_project_note_uri(uri: object) -> tuple[str, str]:
    if not isinstance(uri, str) or len(uri) > 200:
        raise RpcError(-32602, "Unknown or invalid resource URI", {"uri": str(uri)[:200]})
    prefix = "notes://projects/"
    if not uri.startswith(prefix):
        raise RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri})
    parts = uri[len(prefix):].split("/")
    if len(parts) != 3 or parts[1] != "notes":
        raise RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri})
    project, note_id = parts[0], parts[2]
    if not (_SEGMENT.fullmatch(project) and _SEGMENT.fullmatch(note_id)):
        raise RpcError(-32602, "Unknown or invalid resource URI", {"uri": uri})
    return project, note_id
```

已在本地验证：`notes://projects/alpha/notes/n-1` → `("alpha", "n-1")`；`notes://projects/../notes/x`、`notes://projects/a/notes/x/extra`、`notes://projects/a%2F..b/notes/x`、`notes://projects/a/notes/`、超长字符串都抛 `-32602`。

防住的输入：路径穿越（`..`）、多余段、URL 编码绕过（`%` 不在白名单字符集中）、空变量、超长输入、非字符串类型。要点：用**白名单 + `fullmatch`** 而不是黑名单；解析出的变量作为**类型化参数**传给存储查询，绝不拼进文件路径或 SQL；解析成功之后**还要做授权**——模板只描述"如何构造合法地址"，不代表调用者能读。

### Q12 — 参考答案

- **subject 从哪来**：无状态协议下，凭据是请求输入（HTTP 上来自 `Authorization` 头经过验证后的 token 主体），由传输层解析后传给 handler，例如 `resources_read(params, subject)`；绝不能从 `clientInfo` 或 `serverInfo` 推断身份（讲义：serverInfo "is not an authentication identity"）。
- **可见性判断**：给每个 note 增加 `owner` / `tenant` / `acl` 字段，读取时先解析 URI，再检查 `subject` 是否在 ACL 中；不可见时返回与"未知 URI"相同的 `-32602`，避免通过错误码区分"存在但无权"和"不存在"而泄露存在性。
- **缓存键**：`(server, method, uri, tenant, subject, scopes, locale, cursor, protocolVersion)`——讲义："A cache key must include every request dimension that changes visibility, including tenant, user, scope, locale, and pagination cursor." 对 `private` 结果，键里必须有 subject；无法安全表达这些维度时用 `private` + `ttlMs: 0` 加 host no-store。
- **验证方法**：用 alice 读取 note-1 并命中缓存，再用 bob 读取同一 URI，断言 bob 得到 `-32602` 且缓存没有被命中（缓存未命中计数 +1）。
- **list 为什么会出问题**：一旦引入多用户，`resources/list` 返回的是"调用者可见的资源"，成员随授权变化；若仍标为 `public`，共享缓存就可能把 alice 可见的条目（哪怕只是名称和描述）返回给 bob，泄露存在性与元数据。此时列表也应改为 `private`，或只有在所有用户可见集合完全相同时才用 `public`。

### Q13 — 参考回答要点

- **按选择者与意图区分**：tool = 模型/应用选择、执行操作（可能有副作用）；resource = host/应用/用户按 URI 读取内容；prompt = 用户在 host UI 中主动选择的消息模板（如斜杠命令）。
- **例子**：`notes://note-1` 是 resource；`delete_note` 是 tool；`review_note` 是 prompt。
- **决策顺序**：先问"谁来选"，再问"是否改变状态"，最后问"是否有稳定地址"。
- **不要三份都暴露**：每多一种暴露面，就多一套发现、授权、缓存、错误处理、测试与文档。
- 加分点：prompt 的 URI 参数要走与 resource 读取相同的授权；prompt 返回的消息不替代 host 的系统指令。
- 常见误区：把"读数据库"做成 tool 只因为它是函数；把隐藏的策略做成 prompt 让 host 偷偷注入。

### Q14 — 参考回答要点

- **list**：不能依赖同一连接上先前的调用（如"先 list 第一页，服务端记住游标"）；分页游标必须放在请求里；结果确定性排序，相同输入得到相同快照。
- **read**：每次读取都是完整请求，独立做版本校验、参数校验、授权；URI 不能依赖进程或连接。
- **订阅**：`subscriptions/listen` 是一个长请求，它的存活期就是订阅期；HTTP 上关闭响应流即取消；它不是会话，之后的读取可以去任何实例。
- **错误**：版本问题在每次请求上用 `-32022` 报告，而不是握手失败。
- **水平扩展收益**：任何健康实例都能处理任何请求，负载均衡不需要会话粘性；实例重启不丢"会话状态"；缓存提示（`ttlMs`/`cacheScope`）让中间层和客户端都能安全复用结果。
- 加分点：授权可以改变可见集合（凭据是请求输入），但连接历史不能；`server/discover` 提供一次稳定快照供 UI 构建。

### Q15 — 参考回答要点

- **分类**：公共 prompt 目录 → `public`，TTL 分钟级；租户内共享但非全员可见的列表 → `private`；个人笔记正文 → `private` 短 TTL；含密钥或高速变化的结果 → `private` + `ttlMs: 0` + host no-store。
- **缓存键**：包含 tenant、user/subject、scopes、locale、分页 cursor、协议版本、URI/方法；不要只用 URI 做键。
- **授权优先**：缓存命中之前仍要确认该 subject 对该键有权（或保证键里含 subject）；权限撤销后靠短 TTL 或主动失效。
- **失效**：结合 `subscriptions/listen` 的 `resources/updated` 事件主动失效，但事件只触发重新读取，不携带内容。
- **观测**：记录 cache hit 时的 subject 与键，做"跨主体命中"告警；写测试证明 bob 命中不了 alice 的条目。
- 常见误区：认为"URI 稳定"就可以 `public`；把 `no-store` 写进 `cacheScope`。

### Q16 — 参考回答要点

- **请求**：一次 `subscriptions/listen`（如 `id: 17`），`notifications = {"promptsListChanged": true, "resourceSubscriptions": [doc1, doc2, doc3]}`。也可以按业务拆成多个 listen 请求。
- **消息序列**：先 `notifications/subscriptions/acknowledged`（过滤器只含服务端接受的子集，无权或不存在的 URI 被剔除）→ 之后若干 `notifications/resources/updated` / `notifications/prompts/list_changed`，每条 `_meta` 都带 `subscriptionId: 17` → 服务端优雅结束时发一个 `id: 17` 的 `resultType: "complete"` 响应。
- **传输差异**：stdio 上多个订阅共享一个通道，靠 subscription ID 解复用；Streamable HTTP 上 listen 是 POST，响应保持为 SSE 流，客户端关闭流即取消订阅；不再使用旧的 `resources/subscribe` RPC 与 HTTP GET 事件端点。
- **安全边界**：订阅时对每个 URI 做授权；事件不携带内容，收到后客户端重新 `resources/read`，并接受当时的授权；权限被撤销后的读取会失败。
- **可靠性**：断线后客户端重新 listen 并做一次全量 read/list 对账（通知可能丢失）。
- 加分点：在客户端侧对同一 URI 的高频更新做去抖（debounce），避免读风暴。

### Q17 — 参考回答要点

- **为什么不可信**：resource 文本来自服务端存储，可能是任何人写入的数据，可能包含 prompt injection（"忽略之前的指令……"）、密钥、误导命令或畸形标记；prompt 模板同理，可能拼入未校验的参数（见 Q9）。
- **host 侧**：保留来源（provenance），把 resource 当**数据**而不是指令放进上下文；自己的系统策略保持更高优先级；对 prompt 返回的消息做展示/确认；对需要执行的动作仍走 tool 审批。
- **server 侧**：限制内容大小；返回准确的 MIME 类型；按调用者权限脱敏字段；不返回无关记录；校验 prompt 参数；prompt 中的 URI 走与 read 相同的授权。
- 加分点：结合阶段 14 的 prompt injection 防御，把外部内容用定界符包裹、标注来源，并对高风险工具调用加人工确认。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：JSON-RPC 请求/通知/错误码与无状态信封。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：本节服务端 `handle()` 分派结构的来源。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：理解"POST 响应保持为 SSE 流"和 stdio 多路复用。
- [阶段 13 · 05 工具 Schema 设计](../../05-tool-schema-design/docs/zh.md)：tool 的命名与参数约束，与 prompt 参数声明对照。

### 本节被哪些后续内容用到
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：同一无状态信封下，服务端如何向客户端要模型输入。
- [阶段 13 · 12 显式作用范围与无状态 Elicitation](../../12-mcp-roots-and-elicitation/docs/zh.md)：`file://` 资源的根目录边界检查。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：resource/prompt 内容作为攻击面。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：内容项与 MIME 类型的更多约定。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：讲义"Capstone Connection"要求的目录快照、授权读取、prompt 解析与订阅记录。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：缓存键与失效策略的通用方法。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：把 resource 内容当作不可信数据处理。

### 延伸关键词
`server/discover` · `resultType` · `resources/list` · `resources/read` · `resource template` · `prompts/get` · `ttlMs` · `cacheScope` · `subscriptions/listen` · `subscriptionId` · `-32602` · `-32022` · `SSE` · `provenance`
