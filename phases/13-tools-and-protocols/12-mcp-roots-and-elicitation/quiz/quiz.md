# 测验 · 显式作用范围与无状态 Elicitation（Explicit Scope and Stateless Elicitation）

> **阶段 13 · 工具与协议 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两个看似相同的问题 | "这次操作能碰哪个工作区"是**作用范围与授权**；"用户指的是三条匹配笔记中的哪一条"是**交互式消歧**。混在一起会导致"客户端给了个文件夹就当作有权删除其中一切"的危险设计 |
| 2 | Roots 已弃用，且从来不是沙箱 | 2026-07-28 弃用 `roots/list` 与 `notifications/roots/list_changed`；Roots 只是信息性提示，不限制服务端进程能读什么、不授权调用者、不构成 OS 沙箱 |
| 3 | 显式作用范围的替代方案 | 按调用变化时用 `workspaceUri`/`directory` 工具参数；操作针对资源时用资源 URI；一个部署对应一个固定工作区时用服务端配置；必须"技术上无法逃逸"时用进程沙箱或 jail 文件系统 |
| 4 | 三层规则 | **授权**（这个已认证主体能否使用该工作区）→ **包含性 Containment**（规范化后的目标是否在工作区边界内）→ **沙箱**（服务端被攻破时 OS 能否阻止逃逸） |
| 5 | 包含性检查要先规范化再按路径分量比较 | 朴素字符串前缀会被 `Notes-evil/` 和 `%2e%2e` 骗过；代码用 `unquote` + `normpath` + `commonpath` |
| 6 | Elicitation 仍在，但投递方式变了 | 方法名仍是 `elicitation/create`，但服务端不再发反向请求，而是放进 MRTR 的 `input_required` 结果；客户端用新 id 重试 |
| 7 | 能力按请求协商 | `"elicitation": {}` 等价于仅支持 form；`{"form": {}}` 支持 form；`{"url": {}}` 不支持 form；缺失或只有 url 时返回 `-32021`，`requiredCapabilities = {"elicitation": {"form": {}}}` |
| 8 | Form 与 URL 两种模式 | form：受限的扁平 JSON Schema，用于选择、确认、非敏感偏好；**不能收密码、API key、token、支付凭据**。url：带外（out-of-band）流程，客户端展示完整地址并征得同意，不得预取；`accept` 只表示用户同意打开 |
| 9 | 三种响应分支 | `accept` 校验内容后继续；`decline` 返回完整的、非错误的拒绝结果（终局）；`cancel` 安全停止并允许稍后重试。缺失内容绝不当作同意，decline 不能变成反复弹窗 |
| 10 | 破坏性状态保护 | 签名 state 绑定主体、方法、参数摘要、候选 id 集合、阶段、短过期；变更前再查实时记录；不可逆操作用**一次性 nonce**存入所有实例共享的重放存储，nonce 认领与变更在同一原子边界内 |

### 核心技能（能动手做到）

- [ ] 把一个依赖 Roots 的旧设计改写为显式 `workspaceUri` 参数，并说出三层规则各由谁负责
- [ ] 手算任意 URI 是否通过 `uri_within_workspace`，解释前缀混淆与编码穿越为何被拒
- [ ] 写出 form 模式 `elicitation/create` 的 `requestedSchema`，并根据 `clientCapabilities` 判断能否发送
- [ ] 正确区分 `accept`/`decline`/`cancel` 的服务端行为，说明哪个消耗 nonce、哪个不消耗
- [ ] 读懂 `ReplayStore.claim_and_consume` 的加锁、剪枝、容量与"操作成功才记录 nonce"逻辑
- [ ] 跑通 `main.py` 与 21 个单元测试，并指出代码在"按主体授权工作区"、表单可读性等方面的简化

---

## 二、基础自测（选择题）

**Q1.** 关于 MCP 中的 Roots，下列说法正确的是：

- A. Roots 是 OS 级沙箱，客户端声明后服务端进程无法读取 Roots 之外的文件
- B. Roots 在 2026-07-28 被弃用，它一直只是信息性提示，不授权调用者，也不构成沙箱
- C. Roots 在 2026-07-28 中被升级为强制授权机制
- D. 2026-07-28 服务端可以在处理请求时向客户端发送实时的 `roots/list` 反向请求

**Q2.** 工作区为 `file:///work/notes`，下面哪个候选 URI **能**通过本节代码的 `uri_within_workspace` 检查？

- A. `file:///work/notes-evil/secret.md`
- B. `file:///work/notes/%2e%2e/private.md`
- C. `file://otherhost/work/notes/a.md`
- D. `file:///work/notes/sub/../a.md`

**Q3.** 客户端在 `_meta` 中声明 `"io.modelcontextprotocol/clientCapabilities": {"elicitation": {"url": {}}}`，调用 `notes_delete`。本节服务端返回：

- A. `-32021`，`data` 为 `{"requiredCapabilities": {"elicitation": {"form": {}}}}`
- B. `input_required`，嵌入 `mode: "url"` 的 elicitation
- C. `input_required`，嵌入 `mode: "form"` 的 elicitation，因为 url 支持隐含 form 支持
- D. `-32602 missing client capabilities`

**Q4.** 下列哪项**适合**用 form 模式 elicitation 收集？

- A. 用户的 GitHub 个人访问令牌
- B. 第三方服务的 OAuth 授权
- C. 在三条同名笔记中选择要删除的一条并确认
- D. 用户的信用卡号

**Q5.** 用户在删除确认表单上点击了"拒绝"（`decline`）。本节代码的行为是：

- A. 返回 `-32602` 错误，提示用户必须确认
- B. 重新返回同一个表单，直到用户接受
- C. 不消耗 nonce，客户端随时可以用同一个 state 再提交 `accept`
- D. 返回 `resultType: "complete"`、`isError: false`、`deleted: false`，并消耗 nonce，此后同一 state 的 `accept` 会被拒绝

**Q6.** 对于 `cancel`（用户关闭了表单）和"内容非法的 `accept`"（例如选了不在候选集里的 `note-99`），本节代码：

- A. 两者都消耗 nonce
- B. 两者都不消耗 nonce，state 在过期前仍可再用
- C. `cancel` 消耗 nonce，非法 `accept` 不消耗
- D. 非法 `accept` 消耗 nonce，`cancel` 不消耗

**Q7.** 讲义说 URL 模式的 `accept` 响应意味着：

- A. 用户同意打开该 URL，并不证明外部流程已经完成；服务端重试时要检查自己的状态
- B. 外部 OAuth 流程已经成功完成
- C. 客户端已经预取了该 URL 并验证了证书
- D. 第三方凭据会出现在 `inputResponses` 中

**Q8.** 测试 `test_two_servers_consume_confirmation_atomically` 让两个 `NotesServer` 共享同一个笔记字典与 `ReplayStore`，并发用同一个 state 分别删除 `note-14` 与 `note-7`。期望结果是：

- A. 两个都删除成功，因为签名都合法
- B. 两个都失败，因为发生了竞争
- C. 恰好一个成功、一个返回错误，两条笔记中恰好剩一条
- D. 结果不确定，取决于线程调度，所以测试是 flaky 的

---

## 三、动手 / 代码题

**Q9.** 对下面每个候选 URI，写出 `uri_within_workspace("file:///Users/alice/Documents/Notes", candidate)` 的返回值，并说明决定性的那一步（`urlparse` / `unquote` / `normpath` / `commonpath` / 主机比较）：

```text
(a) file:///Users/alice/Documents/Notes/a.md
(b) file:///Users/alice/Documents/Notes-evil/secret.md
(c) file:///Users/alice/Documents/Notes%2f..%2fprivate.md
(d) file://evilhost/Users/alice/Documents/Notes/a.md
(e) file:///Users/alice/Documents/Notes/a.md?x=1
(f) file:///Users/alice/Documents/Notes
(g) file:///Users/alice/Documents/Notes/%252e%252e/x
```

另外：为什么讲义说即使这一函数完全正确，真实文件系统服务端仍可能逃逸？

**Q10.** 阅读授权相关代码：

```python
    def __init__(self, *, notes=None, replay_store=None) -> None:
        self.notes = copy.deepcopy(DEFAULT_NOTES) if notes is None else notes
        self.authorized_workspaces = {"file:///Users/alice/Documents/Notes"}
        ...

    def _require_authorized_workspace(self, workspace_uri: Any) -> str:
        if not isinstance(workspace_uri, str):
            raise McpError(-32602, "workspaceUri must be a string")
        if workspace_uri not in self.authorized_workspaces:
            raise McpError(-32602, "workspace is not authorized")
        return workspace_uri
```

1. 用 `server.dispatch(request, principal="mallory")` 走完两轮，`mallory` 能删除 alice 工作区里的笔记吗？这违反了三层规则中的哪一层？
2. 请修改数据结构与检查函数，让授权按主体进行。
3. 客户端传入 `file:///Users/alice/Documents/Notes/`（多一个斜杠）会怎样？这是 bug 还是可接受的行为？

**Q11.** 第一轮返回的 `requestedSchema` 实测为：

```json
{"type": "object",
 "properties": {"note_id": {"type": "string", "enum": ["note-3", "note-7", "note-14"]},
                "confirm": {"type": "boolean"}},
 "required": ["note_id", "confirm"]}
```

1. 站在用户角度，这个表单有什么问题？这与讲义开头"The user sees the decision"的目标有什么冲突？
2. 请改写 schema，让用户能看到每个候选的标题（可使用 `oneOf` + `const` + `title` 的写法），并说明服务端校验逻辑是否需要改变。
3. 用户在表单里选了 `note-3` 但把 `confirm` 设为 `false` 后提交（`action: "accept"`），代码返回什么？你认为更合理的行为是什么？

**Q12.** 阅读 `ReplayStore.claim_and_consume`：

```python
        with self._lock:
            now = self._clock()
            self._consumed = {key: expiry for key, expiry in self._consumed.items() if expiry > now}
            if expires_at <= now:
                raise McpError(-32602, "requestState expired")
            if nonce in self._consumed:
                raise McpError(-32602, "requestState was already consumed")
            if len(self._consumed) >= self.max_entries:
                raise McpError(-32023, "replay protection capacity exhausted")
            result = operation()
            self._consumed[nonce] = expires_at
            return result
```

1. 为什么 `operation()` 要放在锁内执行？为什么 nonce 在 `operation()` **成功之后**才记录？
2. 剪枝时只保留 `expiry > now` 的条目，为什么已过期的 nonce 可以安全删除？
3. `test_replay_store_is_bounded_and_prunes_expired_claims` 中 `max_entries=1`，时间从 100 变到 111。逐步写出三次调用的结果。
4. 讲义练习 1 要求换成 SQLite。写出"认领 nonce + 删除笔记"在同一事务中的 SQL 思路，并说明为什么单进程的 `threading.Lock` 不够。

---

## 四、面试高频题

**Q13.**（基础必考）MCP 的 Roots 为什么被弃用？新设计中"作用范围"应该怎么表达？

**Q14.**（原理深挖）为什么"字符串前缀检查"不能用于路径包含性判断？一个正确的实现应包括哪些步骤？只做到词法层面还缺什么？

**Q15.**（工程实践）设计一个需要用户确认的破坏性 MCP 工具（例如删除数据库表），在 2026-07-28 无状态协议下，你如何保证"用户确认的就是被执行的"、并且确认只能用一次？

**Q16.**（场景设计）一个 MCP 服务端需要用户授权访问第三方服务（如 Google Drive）。你会用 form 还是 URL 模式 elicitation？完整流程是什么？有哪些安全要点？

**Q17.**（追问型）`accept`、`decline`、`cancel` 有什么区别？为什么不能把它们当成同义词？如果客户端把 `decline` 误报成 `cancel` 会怎样？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Roots were informational guidance. They did not constrain what the server process could read, did not authorize the caller, and did not create an operating-system sandbox." 以及 "MCP 2026-07-28 deprecates `roots/list` and `notifications/roots/list_changed` for new designs." A、C 把提示当成了安全机制；D 错，2026-07-28 服务端不能发实时反向请求，过渡期若仍需 `roots/list`，只能嵌在 MRTR 的 `inputRequests` 中，并且这只是迁移适配器。

### Q2 — 答案：D

`file:///work/notes/sub/../a.md` 经 `normpath` 变为 `/work/notes/a.md`，`commonpath` 等于工作区路径，返回 `True`。A：路径分量 `notes-evil` ≠ `notes`，`commonpath` 为 `/work`；B：`unquote` 后为 `/work/notes/../private.md`，`normpath` 为 `/work/private.md`，不在工作区内；C：`netloc` 为 `otherhost`，与工作区的空主机不同，直接返回 `False`。（同类 URI 在本节工作区上已实测。）

### Q3 — 答案：A

`supports_form_elicitation`：`elicitation` 是非空字典时，必须有 `form` 键且值为字典；`{"url": {}}` 没有 `form`，返回 `False`，于是抛出 `-32021`。测试 `test_url_only_elicitation_does_not_support_form` 断言了完全相同的 `data`。B 错，本节工具只用 form；C 错，讲义："A URL-only declaration does not"；D 错，`{"elicitation": {"url": {}}}` 是合法字典。

### Q4 — 答案：C

讲义列出 form 的适用场景："choosing one of several candidates; confirming a destructive operation; collecting non-sensitive preferences"。A、D 是秘密，讲义："Do not use form mode for passwords, API keys, access tokens, or payment credentials. Those secrets would pass through the MCP client and could reach logs or model context." B 应该用 URL 模式，让敏感交互直接走服务端控制的 web 流程。

### Q5 — 答案：D

代码：

```python
        if action == "decline":
            self.replay_store.claim_and_consume(nonce, expires_at=expires_at, operation=lambda: None)
            return complete(content=[{"type": "text", "text": "deletion declined"}],
                            structuredContent={"deleted": False}, isError=False)
```

讲义："An explicit `decline` is terminal, so the lesson consumes the nonce without deleting anything." 以及"Return a complete, non-error refusal outcome"。测试 `test_decline_is_terminal_for_the_confirmation_state` 验证随后的 `accept` 得到 `requestState was already consumed`。A 把拒绝当错误；B 违反"Never convert decline into a repeated prompt loop"；C 描述的是 `cancel` 的行为。

### Q6 — 答案：B

讲义："Validate the interaction before claiming the nonce. A malformed response or `cancel` performs no mutation and leaves the state retryable until expiry." 代码中 `cancel` 分支直接返回，不触碰 `replay_store`；非法 `accept` 在 `note_id not in state["candidateIds"]` 处抛 `-32602`，也在认领之前。测试 `test_cancelled_or_invalid_confirmation_does_not_consume_state` 先发非法 accept、再发 cancel，最后用同一 state 的合法 accept 成功删除。

### Q7 — 答案：A

讲义："An `accept` response means the user agreed to open the URL. It does not prove the external flow completed. On retry, the server checks its own state and either completes or returns another `input_required` result." C 违反"must not prefetch the URL"；D 违反"Keep third-party credentials out of `inputResponses`"（练习 2），凭据应该直接进入服务端控制的 web 流程。

### Q8 — 答案：C

测试用 `threading.Barrier(2)` 让两个线程同时进入 `claim_and_consume`，确保真正并发；`ReplayStore` 内部的锁保证只有一个线程能认领 nonce 并执行删除，另一个看到 `requestState was already consumed`。断言：结果中恰好 1 个 `result`、1 个 `error`，`note-14`/`note-7` 中恰好剩 1 个。D 错，屏障 + 锁让结果在"谁成功"上不确定，但"恰好一个成功"是确定的，测试不会 flaky。

### Q9 — 参考答案

已全部实测：

| 候选 | 结果 | 决定性步骤 |
|------|------|-----------|
| (a) `.../Notes/a.md` | `True` | `commonpath` = 工作区路径 |
| (b) `.../Notes-evil/secret.md` | `False` | `commonpath` 按**路径分量**比较，得到 `/Users/alice/Documents` |
| (c) `.../Notes%2f..%2fprivate.md` | `False` | `unquote` 把 `%2f` 解成 `/`，得到 `/Users/alice/Documents/Notes/../private.md`，`normpath` 后为 `/Users/alice/Documents/private.md` |
| (d) `file://evilhost/...` | `False` | `(scheme, netloc)` 不同 |
| (e) `...a.md?x=1` | `False` | `_normalized_uri_parts` 拒绝带 query/fragment 的 URI，抛 `ValueError` 被捕获返回 `False` |
| (f) 工作区本身 | `True` | `commonpath` 等于自身——工作区目录本身也算"在内" |
| (g) `%252e%252e` | `True` | `unquote` 只解一层，得到字面目录名 `%2e%2e`，不是 `..`，词法上仍在工作区内 |

关于 (g)：本函数只解一次码是正确的；但如果下游组件再解一次码，`%2e%2e` 就会变成 `..`——"规范化一次，并保证下游不再解码"是关键。关于 (f)：如果某条笔记的 `uri` 恰好就是工作区目录，删除它就等于删除整个工作区，生产中应要求目标是严格子路径。

**为什么仍可能逃逸**：这是**词法**检查。真实文件系统上，工作区内的一个符号链接 `Notes/link -> /etc` 可以让 `Notes/link/passwd` 在词法上"在内"、实际指向外部；检查与使用之间还存在 TOCTOU（检查时是普通文件，打开时被替换成链接）。讲义："A production filesystem server must also defend against symbolic-link races and platform-specific path semantics."（练习 4）解决办法：解析真实路径（`realpath`）后再比较、用 `openat` + `O_NOFOLLOW` 逐级打开、或者干脆依赖第三层——OS 沙箱 / chroot / 容器挂载。

### Q10 — 参考答案

1. **能**。已实测：`principal="mallory"` 第一轮得到 `input_required`，第二轮成功删除 `note-7`。`authorized_workspaces` 是全服务端共享的集合，不区分主体；state 虽然绑定了主体，但只保证"发起者和确认者是同一个人"，不保证"这个人有权使用该工作区"。这违反了第一层**授权**："Is this authenticated principal allowed to use this workspace?"
2. 修改：

```python
        self.workspace_acl: dict[str, set[str]] = {
            "user-42": {"file:///Users/alice/Documents/Notes"},
        }

    def _require_authorized_workspace(self, workspace_uri: Any, principal: str) -> str:
        if not isinstance(workspace_uri, str):
            raise McpError(-32602, "workspaceUri must be a string")
        if workspace_uri not in self.workspace_acl.get(principal, set()):
            raise McpError(-32602, "workspace is not authorized")
        return workspace_uri
```

   在 `tools_call` 中传入 `principal`；第一轮和重试时都要调用（代码已在每轮开头调用，只需加参数）。生产中 ACL 来自数据库/IdP 的组成员关系，而不是硬编码。
3. 实测返回 `-32602 workspace is not authorized`。授权用的是**精确字符串匹配**，`Notes/` 与 `Notes` 被当成不同工作区。这是"失败即关闭"（fail closed），在安全上可接受，但体验差。改进：先用 `_normalized_uri_parts` 规范化工作区 URI，再与同样规范化过的允许列表比较。

### Q11 — 参考答案

1. 用户只看到 `note-3 / note-7 / note-14` 三个内部 id，看不到对应的 "TPS report 2023/2024/2025"，无法做出知情选择——这恰恰违背了讲义"The user sees the decision"：消歧的意义就在于让**用户**决定是哪一条。演示中 `run_mrtr` 直接选 `choices[-1]`，掩盖了这个问题。另外 `message` 也没有提到匹配的标题或工作区。
2. 改写示例：

```python
"note_id": {
    "type": "string",
    "title": "Note to delete",
    "oneOf": [
        {"const": c["id"], "title": f'{c["title"]} ({c["uri"].rsplit("/", 1)[-1]})'}
        for c in candidates
    ],
},
"confirm": {"type": "boolean", "title": "I understand this cannot be undone"},
```

   服务端校验**不需要变**：仍然检查 `note_id in state["candidateIds"]` 且 `confirm is True`。标题只用于展示，签名 state 中的候选 id 集合才是权威。注意：标题来自数据，可能含误导性文本，客户端应当作纯文本渲染。
3. 实测返回 `-32602 invalid deletion confirmation`，且 nonce 不被消耗。更合理的做法之一：把"accept 但 `confirm=false`"视为用户未同意，返回 `complete` + `deleted: false`（非错误），并按产品决定是否当作终局（类似 decline）。当前实现把一个合法的用户选择报告为协议错误，客户端可能会误以为是 bug 并重试。

### Q12 — 参考答案

1. **锁内执行**：把"检查 nonce 未用过 → 执行删除 → 记录 nonce"变成一个原子临界区；若先记录再在锁外删除，删除失败时 nonce 已被烧掉；若先在锁外删除再记录，两个线程可能都通过检查、都执行删除。**成功后才记录**：`operation()` 抛异常（例如笔记已不存在、已移出工作区）时不记录 nonce，state 在过期前仍可重试（实测：`note-14` 被外部删除后，同一 state 改选 `note-7` 仍能成功）。代价是锁在删除期间一直被持有，所有确认操作串行化。
2. 过期的 state 本身就会在 `verify_request_state` 阶段被拒绝（`expires_at <= now`），不可能再走到 `claim_and_consume`，所以无需继续记住它的 nonce。这让存储有界：存活条目数 ≤ 有效期内的确认次数。
3. 逐步：
   - `now=100`，认领 `first`（过期 110）：存储为空，执行操作，`completed=["first"]`，存储 `{first: 110}`。
   - `now=100`，认领 `second`（过期 120）：剪枝后仍有 `first`，`len == 1 >= max_entries`，抛 `-32023 replay protection capacity exhausted`，操作未执行。
   - `now=111`，认领 `second`：剪枝删掉 `first`（110 不大于 111），存储为空，执行操作，`completed=["first", "second"]`。
   注意 `-32023` 是本节代码自定义的错误码，讲义没有定义它。
4. SQLite 思路：

```sql
BEGIN IMMEDIATE;                                   -- 立刻拿写锁
INSERT INTO consumed_nonces(nonce, expires_at) VALUES (?, ?);   -- nonce 为主键，重复即失败
DELETE FROM notes WHERE id = ? AND workspace = ? AND id IN (/* 已签名候选集 */);
-- 检查 changes() == 1，否则 ROLLBACK
COMMIT;
```

   主键约束保证同一 nonce 只能插入一次，插入与删除同事务提交或同时回滚。`threading.Lock` 只在**单个进程内**有效；多副本部署时两个进程各有一把锁，互不可见，必须由共享存储（数据库唯一约束、条件写、Redis `SET NX`）提供原子性。讲义："A production database should couple the nonce claim and mutation in one transaction or equivalent conditional-write boundary."

### Q13 — 参考回答要点

- **为什么弃用**：Roots 只是客户端提供的信息性提示，既不限制服务端进程、不授权调用者，也不是沙箱，却容易被误当作安全边界；它还依赖会话期的反向请求和变更通知，与 2026-07-28 的无状态设计冲突。
- **新的表达方式**：每次调用变化 → 工具参数 `workspaceUri`/`directory`；针对资源 → 资源 URI；固定工作区 → 服务端配置；需要技术隔离 → 进程沙箱/jail 文件系统。
- **好处**：模型能看到并复述显式句柄；便于检查、重放、审计与路由；任何实例都能处理。
- **仍需三层**：显式 URI 不会自我授权，服务端仍要授权、规范化包含性检查，并依赖 OS 沙箱兜底。
- 加分点：过渡期可在 MRTR `inputRequests` 中嵌入 `roots/list`，但应标记为迁移适配器；2025-11-25 对端的 legacy 适配器不能让 Root 列表绕过服务端授权。

### Q14 — 参考回答要点

- **前缀检查的问题**：`/work/notes-evil` 以 `/work/notes` 开头；`/work/notes/../secret` 也以它开头；还有 `%2e%2e`、`%2f` 等编码、大小写、重复斜杠、Unicode 规范化差异。
- **正确步骤**：只接受预期的 scheme，拒绝 query/fragment → 比较主机 → 解码一次 → 规范化（`normpath` 去掉 `.`、`..`、多余斜杠）→ 要求绝对路径 → 按**路径分量**比较（`commonpath` 或逐段比较）→ 可选要求"严格子路径"。
- **词法之外**：符号链接（需 `realpath` 或 `O_NOFOLLOW` 逐级打开）、检查与使用之间的竞争（TOCTOU）、硬链接、挂载点、Windows 的大小写不敏感与 `\` 分隔、macOS 的大小写不敏感文件系统；最终兜底靠 OS 沙箱。
- 加分点：在变更前**再次检查**（本节 `_delete_note_once` 在删除前重新检查实时记录的包含性）。

### Q15 — 参考回答要点

- **第一轮**：校验参数、授权（按主体）、找到候选；返回 `input_required`，内嵌 form 模式 `elicitation/create`，表单展示足够的信息（名称、行数、环境）与明确的确认项。
- **签名 state**：绑定已认证主体、方法、工具名、参数摘要、候选集合、阶段、短过期、随机 nonce；需要保密时用认证加密。
- **重试处理**：验签 → 校验主体/参数/过期 → 区分 `accept`/`decline`/`cancel` → 校验 `accept` 内容（目标在候选集内、确认为真）→ **重新授权 + 重新检查实时记录** → 在同一事务中认领 nonce 并执行变更。
- **一次性**：nonce 存在所有实例共享的存储中，唯一约束 + 同事务；decline 也消耗 nonce（终局），cancel 与非法响应不消耗。
- **审计**：记录主体、目标、nonce、结果；不要把表单中的敏感内容写进日志。
- 局限说明：服务端无法区分"用户在表单里选的"和"恶意客户端改写的 note_id"，签名候选集只能把选择限制在用户看到过的范围内；更高风险的操作可再叠加 URL 模式的带外确认或二次认证。

### Q16 — 参考回答要点

- **选 URL 模式**：OAuth 授权涉及第三方凭据，form 模式会让秘密经过 MCP 客户端、可能进入日志或模型上下文。
- **流程**：工具调用 → 服务端发现未授权 → 返回 `input_required`，嵌入 `elicitation/create`（`mode: "url"`、`message`、服务端控制的 `https` URL，URL 中带一次性、绑定主体的 state 参数）→ 客户端展示完整目标地址并征得同意（不预取）→ 用户在浏览器完成 OAuth，令牌直接存到服务端 → 客户端用新 id 重试原请求（`accept` 只代表用户同意打开）→ 服务端查自己的状态：完成则继续，否则再次返回 `input_required`。
- **安全要点**：服务端必须把浏览器中的用户绑定到发起 MCP 操作的同一已认证主体（防止会话固定/授权串号）；URL 只能指向服务端控制的域；第三方凭据永不出现在 `inputResponses`；客户端声明了 `elicitation.url` 能力才能发送；URL elicitation 不能替代 MCP 客户端与服务端之间的授权（那是第 16、18 节的 OAuth 话题）。

### Q17 — 参考回答要点

- **语义**：`accept` = 用户提交了交互（内容仍需校验）；`decline` = 用户**明确拒绝**；`cancel` = 用户关闭或没能完成，没有给出意见。
- **服务端行为**：accept → 校验后继续；decline → 返回完整的非错误拒绝结果，作为终局（本节消耗 nonce）；cancel → 安全停止，允许稍后重试（不消耗 nonce）。
- **为什么不能混用**：把 decline 当 cancel，会让服务端以为还能再问，可能变成反复弹窗骚扰用户（讲义："Never convert decline into a repeated prompt loop"），而且拒绝过的 state 仍然可用，事后可能被重放成 accept；把 cancel 当 decline，则用户误关窗口后无法继续；把缺失内容当同意，则是严重安全漏洞（"Never interpret missing content as consent"）。
- 加分点：客户端误报属于客户端 bug，服务端的防线是"state 一次性 + 每次都要显式 `confirm: true`"。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：`tools/list`、`tools/call` 的基础结构。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：MRTR、`requestState` 的 HMAC 绑定；本节在其上增加 nonce 防重放。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：`file://` 资源 URI 的边界检查原则。
- [阶段 13 · 05 工具 Schema 设计](../../05-tool-schema-design/docs/zh.md)：`inputSchema` 与表单 `requestedSchema` 的设计。

### 本节被哪些后续内容用到
- [阶段 13 · 13 MCP Tasks 扩展](../../13-mcp-async-tasks/docs/zh.md)：长时间任务中也可能需要 elicitation。
- [阶段 13 · 14 无状态协议上的 MCP Apps](../../14-mcp-apps/docs/zh.md)：更丰富的用户交互界面。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：MRTR 状态篡改与重放。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)：客户端与服务端之间的授权（URL elicitation 不替代它）。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：三层规则中的沙箱层。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：破坏性操作的确认模式。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：路径隔离的综合实践。

### 延伸关键词
`Roots deprecation` · `explicit scope` · `workspaceUri` · `path containment` · `posixpath.commonpath` · `percent-encoding traversal` · `symlink / TOCTOU` · `elicitation/create` · `form mode / URL mode` · `accept / decline / cancel` · `nonce` · `replay store` · `-32021` · `fail closed`
