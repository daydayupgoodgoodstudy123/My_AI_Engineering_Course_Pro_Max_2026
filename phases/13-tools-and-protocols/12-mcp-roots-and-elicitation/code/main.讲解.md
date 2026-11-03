# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 12 节 显式作用范围与无状态 Elicitation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v` ｜ **依赖**：仅标准库（`base64`、`copy`、`hashlib`、`hmac`、`json`、`posixpath`、`secrets`、`threading`、`time`、`urllib.parse` 等），无需网络、不访问真实文件系统

---

## 1. 这份代码在考察什么

代码实现了一个 `notes_delete` 工具：用户说"删掉旧的 TPS report"，服务端发现工作区里有三条匹配笔记，必须让**用户**挑一条并确认后才删除。它把讲义的两个主题落到代码上：

1. **显式作用范围**（替代已弃用的 Roots）：工作区作为 `workspaceUri` 参数显式传入；服务端用允许列表授权；用 `uri_within_workspace` 做规范化的路径包含性检查，挡住前缀混淆与编码穿越。
2. **无状态 elicitation**：确认表单（form 模式 `elicitation/create`）嵌在 MRTR 的 `input_required` 结果里；客户端用新 id 重试并带回 `inputResponses` 与签名的 `requestState`。
3. **破坏性操作的状态保护**：state 绑定主体、方法、参数摘要、**候选 id 集合**、阶段、过期与**随机 nonce**；`ReplayStore` 保证每个 nonce 只能被认领一次，并在同一把锁里执行删除。
4. **三种响应分支**：`accept`（校验后删除）、`decline`（终局、消耗 nonce、不删）、`cancel`（不消耗、可重试）。

> 一句话：**作用范围由服务端授权，消歧由用户决定，确认只能用一次**——而且全部在无会话的独立请求中完成。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_NOTES` | 字典 | 5 条笔记：3 条 TPS、1 条购物清单、1 条在工作区外（`/tmp`） | 数据 |
| `TOOLS` | 列表 | `notes_delete` 描述符，`workspaceUri` 与 `title` 必填 | `tools/list` |
| `McpError` | dataclass 异常 | 结构化错误 | 错误码 |
| `ReplayStore` | 类 | 有界、按 TTL 剪枝、加锁的 nonce 存储；`claim_and_consume` 原子地认领并执行操作 | 防重放 |
| `request_meta` / `complete` / `validate_request_meta` | 函数 | 无状态信封与校验 | `-32602` / `-32022` |
| `supports_form_elicitation` | 函数 | 判断 `clientCapabilities` 是否支持 form 模式 | 能力协商 |
| `_normalized_uri_parts` / `uri_within_workspace` | 函数 | URI 解析、解码、规范化、按分量比较 | 包含性 |
| `_b64` / `_unb64` / `_arguments_digest` / `seal_request_state` / `verify_request_state` | 函数 | 与第 11 节同构的签名状态 | HMAC 绑定 |
| `NotesServer` | 类 | 持有笔记、授权工作区、重放存储；实现 discover、tools/list、tools/call、dispatch | 服务端 |
| `NotesServer._elicitation_result` | 方法 | 构造 form 表单与签名 state | MRTR + elicitation |
| `NotesServer._delete_note_once` | 方法 | 在重放存储的临界区内重新检查并删除 | 原子变更 |
| `tool_request` / `run_mrtr` / `main` | 函数 | 构造请求、跑两轮、打印结果 | 演示 |

数据流：`run_mrtr()` → `dispatch(id=1)` → `tools_call`：校验信封 → 授权工作区 → 校验标题 → 检查 form 能力 → 无 state：按标题与包含性筛候选 → `_elicitation_result`（表单 + 签名 state）→ 客户端选择 `choices[-1]` → `dispatch(id=2, inputResponses, requestState)` → 再次授权/校验 → `verify_request_state` → 分支 accept → `_delete_note_once` → `ReplayStore.claim_and_consume` → `complete{deleted: true}`。

---

## 3. 逐段精讲

### 3.1 演示数据与工具描述符

```python
DEFAULT_NOTES = {
    "note-3":  {"title": "TPS report 2023", "uri": "file:///Users/alice/Documents/Notes/tps-2023.md"},
    "note-7":  {"title": "TPS report 2024", "uri": ".../Notes/tps-2024.md"},
    "note-14": {"title": "TPS report 2025", "uri": ".../Notes/tps-2025.md"},
    "note-99": {"title": "shopping list",   "uri": ".../Notes/shopping.md"},
    "note-100": {"title": "outside root",   "uri": "file:///tmp/outside.md"},
}
```

- 三条 TPS 制造"需要消歧"的场景；`note-100` 在工作区外，用来证明"工作区外的匹配不会暴露给用户"（测试 `test_out_of_scope_match_is_not_exposed`）。
- `TOOLS` 中 `workspaceUri` 带 `"format": "uri"`，`title` 带 `"minLength": 1`，二者都在 `required` 中。
- ⚠️ 与第 11 节不同，`tools_list` 返回的是 `sorted(TOOLS, ...)`——新列表，但**元素仍是全局字典的引用**，没有 `deepcopy`。实测：修改返回的 `inputSchema.required` 会污染全局 `TOOLS`。第 11 节专门为此写了测试，这里遗漏了。

### 3.2 `ReplayStore`：有界、可注入时钟、加锁的一次性存储

```python
class ReplayStore:
    def __init__(self, *, max_entries: int = 1_000, clock: Callable[[], float] = time.time) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        self.max_entries = max_entries
        self._clock = clock
        self._consumed: dict[str, float] = {}
        self._lock = threading.Lock()

    def claim_and_consume(self, nonce: str, *, expires_at: float, operation: Callable[[], Any]) -> Any:
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

逐行理解：

- `type(max_entries) is not int`：比 `isinstance` 更严格，`True`（`bool` 是 `int` 子类）会被拒绝。
- `clock` 参数是**依赖注入**：测试传 `lambda: now[0]`，就能随意"拨动时间"。
- `with self._lock:` 整个临界区：剪枝 → 过期检查 → 重复检查 → 容量检查 → **执行操作** → 记录 nonce。
- **剪枝**：只保留未过期的条目。已过期的 state 会在验签阶段被拒，没必要再记住它的 nonce，所以存储大小有上限。
- **容量满**时拒绝新的认领（`-32023`），而不是丢弃旧条目——丢弃未过期的 nonce 会重新打开重放窗口。`-32023` 是本代码自定义的错误码，讲义未定义。
- **`operation()` 成功后才记录 nonce**：删除失败（笔记已不存在、被移出工作区）会抛异常，nonce 不被记录，state 仍可在过期前重试。
- 代价：锁在执行删除期间一直被持有，所有确认操作被串行化；它只在**单进程**内有效，多进程/多副本需要数据库事务或条件写（讲义练习 1）。

### 3.3 能力协商：`supports_form_elicitation`

```python
def supports_form_elicitation(capabilities: dict[str, Any]) -> bool:
    elicitation = capabilities.get("elicitation")
    if not isinstance(elicitation, dict):
        return False
    if not elicitation:
        return True
    return isinstance(elicitation.get("form"), dict)
```

| `clientCapabilities` | 结果 | 依据 |
|---------------------|------|------|
| `{}`（无 elicitation） | `False` → `-32021` | 未声明 |
| `{"elicitation": {}}` | `True` | 讲义：空对象为兼容起见等价于仅 form |
| `{"elicitation": {"form": {}}}` | `True` | 显式 form |
| `{"elicitation": {"url": {}}}` | `False` → `-32021` | 只有 url 不代表支持 form |

- `not elicitation` 判断空字典（空字典为假值）。
- 每个请求都重新判断：讲义"The server must not embed a mode absent from the current request's capabilities, even if an earlier request advertised it."

### 3.4 路径包含性：先规范化，再按分量比较

```python
def _normalized_uri_parts(uri: str) -> tuple[str, str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or parsed.query or parsed.fragment:
        raise ValueError("only plain file URIs are supported")
    path = posixpath.normpath(unquote(parsed.path))
    if not path.startswith("/"):
        raise ValueError("file URI path must be absolute")
    return parsed.scheme, parsed.netloc, path


def uri_within_workspace(workspace_uri: str, candidate_uri: str) -> bool:
    try:
        workspace_scheme, workspace_host, workspace_path = _normalized_uri_parts(workspace_uri)
        candidate_scheme, candidate_host, candidate_path = _normalized_uri_parts(candidate_uri)
        if (workspace_scheme, workspace_host) != (candidate_scheme, candidate_host):
            return False
        return posixpath.commonpath([workspace_path, candidate_path]) == workspace_path
    except (ValueError, TypeError):
        return False
```

处理管线：

1. `urlparse`：拆成 scheme / netloc（主机）/ path / query / fragment；scheme 会被转成小写（实测 `FILE://` 也被接受）。
2. 只接受 `file`，拒绝带 query 或 fragment 的 URI——少一种解析歧义。
3. `unquote`：把 `%2e%2e` 解成 `..`、`%2f` 解成 `/`。**只解一次**。
4. `posixpath.normpath`：折叠 `.`、`..`、重复斜杠。用 `posixpath` 而不是 `os.path`，保证在 Windows 上运行时也按 POSIX 语义处理 `file://` 路径。
5. 主机必须相同。
6. `commonpath` 按**路径分量**求公共前缀：`/Users/alice/Documents/Notes` 与 `.../Notes-evil/secret.md` 的公共路径是 `/Users/alice/Documents`（实测），不等于工作区，于是返回 `False`。
7. 任何解析异常都返回 `False`——**失败即关闭**（fail closed）。

讲义里的两个攻击样例：

| 候选 | 处理后 | 结果 |
|------|-------|------|
| `file:///work/notes-evil/secret.md` | 分量 `notes-evil` ≠ `notes` | `False` |
| `file:///work/notes/%2e%2e/private.md` | `unquote` → `/work/notes/../private.md` → `normpath` → `/work/private.md` | `False` |

- ⚠️ 工作区目录本身也算"在内"（实测返回 `True`）；生产中删除类操作应要求严格子路径。
- ⚠️ 这是**词法**检查，挡不住符号链接与 TOCTOU 竞争（讲义练习 4）。

### 3.5 签名状态（与第 11 节的差异）

`_b64`、`_unb64`、`_arguments_digest`、`seal_request_state` 与第 11 节完全相同。`verify_request_state` 有两处不同：

```python
    expires_at = state.get("expiresAt")
    if type(expires_at) not in (int, float):
        raise McpError(-32602, "invalid requestState expiry")
    if expires_at <= (time.time() if now is None else now):
        raise McpError(-32602, "requestState expired")
```

- 显式检查 `expiresAt` 的类型（第 11 节用 `int(state.get("expiresAt", 0))`）。
- 过期判断用 `<=`：`now == expiresAt` 即视为过期；第 11 节用 `<`，同一时刻仍有效。两节课的边界语义不一致，写测试时要注意。

### 3.6 `NotesServer.__init__` 与授权

```python
        self.notes = copy.deepcopy(DEFAULT_NOTES) if notes is None else notes
        self.authorized_workspaces = {"file:///Users/alice/Documents/Notes"}
        self.replay_store = replay_store if replay_store is not None else ReplayStore()
```

- 默认 `deepcopy` 一份笔记，避免多个测试互相影响；也可以**传入**同一个 `notes` 字典与 `replay_store`，模拟"两台实例共享数据库和重放存储"（测试 `test_two_servers_consume_confirmation_atomically`）。
- `replay_store if replay_store is not None else ...`：不用 `or`，因为一个空的自定义存储对象也可能是假值。
- `_require_authorized_workspace` 用**精确字符串**匹配允许列表。
- ⚠️ **授权不区分主体**：`authorized_workspaces` 是整个服务端共享的集合，任何 `principal` 都能对 alice 的工作区发起删除。实测 `principal="mallory"` 两轮后成功删除 `note-7`。讲义三层规则第一层是"Is this authenticated principal allowed to use this workspace?"——代码只实现了"这个工作区是否被配置"，见测验 Q10。

### 3.7 `_elicitation_result`：表单 + 签名 state

```python
        candidate_ids = [candidate["id"] for candidate in candidates]
        state = {
            "phase": "confirm_delete",
            "principal": principal,
            "method": "tools/call",
            "argumentsDigest": _arguments_digest(arguments),
            "candidateIds": candidate_ids,
            "nonce": secrets.token_hex(16),
            "expiresAt": int(time.time()) + 300,
        }
        return {
            "resultType": "input_required",
            "inputRequests": {
                "delete_choice": {
                    "method": "elicitation/create",
                    "params": {
                        "mode": "form",
                        "message": "Choose one matching note and confirm deletion.",
                        "requestedSchema": {
                            "type": "object",
                            "properties": {
                                "note_id": {"type": "string", "enum": candidate_ids},
                                "confirm": {"type": "boolean"},
                            },
                            "required": ["note_id", "confirm"],
                        },
                    },
                }
            },
            "requestState": seal_request_state(state),
            ...
        }
```

- `candidateIds` 写进签名 state：之后客户端只能在**用户看到过的集合**中选择，不能借机删除别的笔记（测试中选 `note-99` 被拒）。
- `secrets.token_hex(16)`：32 个十六进制字符的密码学安全随机 nonce（`random` 模块不适合安全用途）。
- `requestedSchema` 是扁平对象：一个枚举字符串 + 一个布尔值，符合 form 模式"受限、扁平"的要求。
- ⚠️ 枚举只有 `note-3/note-7/note-14`，表单里**看不到标题**，用户无法做知情选择（见测验 Q11，可用 `oneOf` + `const` + `title`）。
- 实测第一轮 state body：`{"argumentsDigest":"de265e6c...","candidateIds":["note-3","note-7","note-14"],"expiresAt":...,"method":"tools/call","nonce":"d410fdb8...","phase":"confirm_delete","principal":"user-42"}`，base64 部分 355 字符。

### 3.8 `tools_call`：从参数校验到三种分支

**每一轮都先做的事**（无论有无 state）：

```python
        meta = validate_request_meta(params)
        if params.get("name") != "notes_delete": raise McpError(-32602, "unknown tool")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict): raise ...
        workspace_uri = self._require_authorized_workspace(arguments.get("workspaceUri"))
        title = arguments.get("title")
        if not isinstance(title, str) or not title.strip(): raise ...
        if not supports_form_elicitation(meta[CAPABILITIES_META]): raise McpError(-32021, ...)
```

重试时也会重新授权工作区——讲义："re-authorizes the workspace, re-checks containment, and then deletes."

**续传字段必须成对出现**：

```python
        has_state = "requestState" in params
        has_responses = "inputResponses" in params
        if has_state != has_responses:
            raise McpError(-32602, "requestState and inputResponses must be provided together")
```

- 用 `in` 判断"是否存在"而不是判断真假值，所以 `{"requestState": None, "inputResponses": {}}` 会进入后续检查并报 `requestState must be a string`（测试 `test_continuation_fields_require_presence_and_non_null_values` 的四个子用例）。

**第一轮**：用 `title.lower() in note["title"].lower()`（大小写不敏感的子串匹配）且 `uri_within_workspace` 筛候选。没有候选时返回 `complete` + `isError: True`——这是"工具执行结果为失败"，而不是 JSON-RPC 协议错误。

**重试**：验签 → 检查 `phase` → 取 `nonce` 与 `expiresAt` → 取 `delete_choice` → 按 `action` 分支：

| `action` | 行为 | nonce |
|----------|------|-------|
| `cancel` | 返回 `complete`、`deleted: False`、非错误 | 不消耗，可重试 |
| `decline` | `claim_and_consume(..., operation=lambda: None)`，返回 `complete`、`deleted: False` | **消耗**（终局） |
| `accept` 且内容合法 | `_delete_note_once` | 删除成功才消耗 |
| `accept` 内容非法 / 其他 action | `-32602 invalid elicitation response` 或 `invalid deletion confirmation` | 不消耗 |

- 合法内容的判断：`content.get("confirm") is not True or note_id not in state["candidateIds"]`——`confirm` 必须**严格是 `True`**（`1`、`"true"` 都不行），`note_id` 必须在签名候选集中。"Never interpret missing content as consent."
- ⚠️ `accept` + `confirm: false` 被报告为 `-32602` 协议错误（实测），更合理的处理见测验 Q11。

### 3.9 `_delete_note_once`：临界区里的二次检查

```python
        def delete_note() -> None:
            note = self.notes.get(note_id)
            if note is None:
                raise McpError(-32602, "selected note no longer exists")
            if not uri_within_workspace(workspace_uri, note["uri"]):
                raise McpError(-32602, "selected note is outside workspace")
            del self.notes[note_id]

        self.replay_store.claim_and_consume(nonce, expires_at=expires_at, operation=delete_note)
```

- 内部函数 `delete_note` 是一个**闭包**，捕获了 `note_id`、`workspace_uri` 和 `self`，交给重放存储在锁内执行。
- 删除前**再查实时记录**：笔记可能在表单展示后被别人删除（实测 `selected note no longer exists`），或被移出工作区（实测把 `note-3` 的 URI 改成 `/tmp/moved.md` 后得到 `selected note is outside workspace`）。讲义："This catches deletion races and a target moved outside the workspace after the form was shown."
- 这两种失败都不消耗 nonce（实测：`note-14` 被外部删除后，用同一 state 改选 `note-7` 仍能成功）。

### 3.10 `dispatch`、`tool_request` 与 `run_mrtr`

- `dispatch` 与第 11 节相同：只认三个方法；`principal` 关键字参数默认 `"user-42"`；通知不回任何响应。
- ⚠️ 通知也会**完整执行** handler。实测：把一个合法的 `accept` 重试去掉 `id` 后发送，`note-3` 被静默删除，客户端收不到任何确认。JSON-RPC 允许这样，但对破坏性工具来说，服务端可以考虑直接拒绝以通知形式到达的 `tools/call`。测试里特意用标题 `"no matching note"` 来避免副作用。
- `run_mrtr(action=...)` 是一个极简客户端：取第一轮表单中的 `enum`，`accept` 时选最后一个（`note-14`），否则 `content = {}`；只有两轮，所以返回固定的 `[1, 2]`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 工作区作为显式参数 | 模型能看到、可审计、可路由；替代 Roots | 必须服务端授权；应按主体而不是全局允许列表 |
| 精确字符串匹配授权 | 简单、失败即关闭 | `Notes/` 与 `Notes` 被视为不同；先规范化再比较更友好 |
| `unquote` + `normpath` + `commonpath` | 挡住前缀混淆与编码穿越 | 词法检查挡不住符号链接；需要 `realpath`/`O_NOFOLLOW`/OS 沙箱 |
| 候选 id 写进签名 state | 客户端只能在用户看过的集合里选 | 无法区分"用户选的"与"客户端改写的"选择 |
| 随机 nonce + `ReplayStore` | 确认只能用一次，跨实例共享 | 内存锁只在单进程有效；生产用数据库事务 |
| 操作在锁内、成功后才记 nonce | 原子性，失败可重试 | 锁持有时间长，确认操作串行化 |
| decline 消耗、cancel 不消耗 | 区分"明确拒绝"与"未完成" | 需要客户端如实上报 action |
| 有界存储、满了就拒绝 | 防内存耗尽且不打开重放窗口 | 高峰期可能拒绝合法确认（`-32023`） |
| 表单只列 id | 代码短 | 用户看不到标题，消歧失去意义 |
| `tools_list` 不 deepcopy | 省事 | 调用方可污染全局描述符（第 11 节已修） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `threading.Lock` + `with` | `with self._lock:` | 进入时加锁、离开时（包括异常）自动释放 |
| `Callable` 类型 | `clock: Callable[[], float] = time.time`、`operation: Callable[[], Any]` | 参数是"无参、返回 float/Any 的函数" |
| 函数作为参数 / 依赖注入 | `ReplayStore(clock=lambda: now[0])` | 测试中替换时钟 |
| 闭包 | `_delete_note_once` 内部的 `def delete_note()` | 内部函数捕获外层变量 |
| `lambda` | `operation=lambda: None`、`key=lambda tool: tool["name"]` | 匿名小函数 |
| `type(x) is int` vs `isinstance` | `type(max_entries) is not int` | `type` 精确匹配，排除 `bool` 等子类 |
| `x in (a, b)` | `type(expires_at) not in (int, float)` | 成员判断 |
| 字典推导式过滤 | `{key: expiry for key, expiry in self._consumed.items() if expiry > now}` | 构造只含未过期条目的新字典 |
| 列表推导式 + 解包 | `[{"id": note_id, **note} for note_id, note in self.notes.items() if ...]` | 合并 id 与原字段并过滤 |
| `copy.deepcopy` | `copy.deepcopy(DEFAULT_NOTES)` | 每个实例一份独立数据 |
| 条件表达式 | `copy.deepcopy(...) if notes is None else notes` | 一行 if/else |
| `is None` 判断 | `replay_store if replay_store is not None else ReplayStore()` | 不用 `or`，避免假值对象被替换 |
| 元组比较 | `(workspace_scheme, workspace_host) != (candidate_scheme, candidate_host)` | 一次比较多个字段 |
| `urllib.parse` | `urlparse(uri)`、`unquote(parsed.path)` | URI 解析与百分号解码 |
| `posixpath` | `posixpath.normpath`、`posixpath.commonpath` | 平台无关的 POSIX 路径运算 |
| `secrets` | `secrets.token_hex(16)` | 密码学安全随机数 |
| `del` 字典项 | `del self.notes[note_id]` | 删除键 |
| `str.lower()` 与 `in` | `title.lower() in note["title"].lower()` | 大小写不敏感的子串匹配 |
| `str.rsplit` | （测验示例）`uri.rsplit("/", 1)[-1]` | 从右侧分割一次取文件名 |
| 仅限关键字参数 | `def tools_call(self, params, *, principal)` | 必须写 `principal=...` |
| 方法调用链 | `first["result"]["inputRequests"]["delete_choice"]["params"]["requestedSchema"]...` | 逐层取嵌套字典 |
| 数字下划线 | `1_000`、`300_000` | 可读性 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不执行演示 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`：

```text
discover: {
  "resultType": "complete",
  "supportedVersions": ["2026-07-28"],
  "capabilities": {"tools": {}},              ← 不广告 roots
  "ttlMs": 300000,
  "cacheScope": "public",
  "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "explicit-scope-demo", "version": "1.0.0"}}
}
independent request ids: [1, 2]               ← 一轮 input_required + 一次 complete
final: {
  "resultType": "complete",
  "content": [{"type": "text", "text": "deleted note-14"}],
  "structuredContent": {"deleted": true, "noteId": "note-14"},
  "isError": false,
  "_meta": {...}
}
remaining note ids: ['note-100', 'note-3', 'note-7', 'note-99']   ← note-14 已删除
```

（多行 JSON 压缩显示，内容与实际输出一致。）

逐项解读：

- **discover**：只有 `tools`，没有 `roots`，对应讲义 checkpoint "Discovery advertises tools without Roots"。
- **`[1, 2]`**：第 1 次请求返回表单，第 2 次请求（新 id）带回 `accept` + `note-14` + 原样 state，完成删除。
- **`noteId: note-14`**：`run_mrtr` 选择了 `enum` 的最后一项；`enum` 顺序来自笔记字典的插入顺序（`note-3`、`note-7`、`note-14`）。
- **剩余笔记**：`sorted` 按字符串排序，所以 `note-100` 排在 `note-3` 前面。`note-100`（工作区外）和 `note-99`（标题不匹配）从未进入候选集。

讲义 checkpoint 中的其余项（前缀/编码路径被拒、改标题不能复用 state、decline 不删除、两实例只执行一次、能力声明的三种情况、`-32022`、通知无响应）都由测试覆盖，见第 9 节。

---

## 7. 动手改一改

1. **（入门）** 给 `tools_list` 加上 `deepcopy`，并仿照第 11 节写一个"修改返回值不影响下一次结果"的测试。
2. **（入门）** 把 `requestedSchema` 的 `note_id` 改成 `oneOf` + `const` + `title`，让表单显示标题；确认服务端校验与测试都不需要改。
3. **（授权）** 把 `authorized_workspaces` 改成 `{principal: set[workspace]}`，`_require_authorized_workspace` 增加 `principal` 参数；写测试证明 `mallory` 第一轮就得到 `-32602 workspace is not authorized`。
4. **（讲义练习 4）** 写一个基于真实临时目录的版本：在工作区内建一个指向外部的符号链接，证明 `uri_within_workspace` 判为"在内"；再用 `os.path.realpath` 实现第二道检查并说明它为什么仍有 TOCTOU 风险。
5. **（讲义练习 1/3）** 用 `sqlite3` 替换内存笔记与 `ReplayStore`：`consumed_nonces(nonce PRIMARY KEY, expires_at)`，在 `BEGIN IMMEDIATE` 事务中插入 nonce、删除笔记、检查 `changes()`；用两个进程（`multiprocessing`）同时提交，证明只有一个成功。
6. **（讲义练习 2，进阶）** 增加 URL 模式：客户端声明 `{"elicitation": {"url": {}}}` 时，对"连接第三方笔记服务"返回 `mode: "url"` 的 elicitation；重试时服务端检查自己的连接状态，未完成就再次返回 `input_required`；确保第三方凭据不出现在 `inputResponses` 中。

---

## 8. 常见坑

- **把 Roots 或客户端给的文件夹当授权**：显式 URI 也不会自我授权，必须按主体检查。
- **字符串前缀判断包含性**：`Notes-evil`、`%2e%2e`、`%2f` 都能绕过；要先解码、规范化，再按分量比较。
- **多次解码**：本函数只解一次；若下游再解码，`%252e%252e` 会变成 `..`。
- **只做词法检查**：符号链接与 TOCTOU 需要 `realpath`、`O_NOFOLLOW` 或 OS 沙箱。
- **用 form 收集秘密**：令牌、密码、支付信息必须走 URL 模式或其他带外流程。
- **把 decline 与 cancel 混为一谈**：decline 是终局（消耗 nonce），cancel 可重试。
- **把缺失内容当同意**：`confirm` 必须严格为 `True`。
- **先记录 nonce 再执行操作**：操作失败时 nonce 被白白烧掉；先执行后记录、且两者在同一原子边界内。
- **以为进程内锁能跨副本**：多实例要靠数据库事务或条件写。
- **发送当前请求未声明的 elicitation 模式**：能力按请求协商，不能沿用上一次请求的声明。
- **返回全局描述符的引用**：调用方修改后会污染所有后续请求。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m unittest discover tests -v`。实际结果：**Ran 21 tests ... OK**。

测试文件用 `importlib.util.spec_from_file_location("lesson12_main", ...)` 按路径加载 `main.py`（避免与其他课程同名模块冲突）；`setUp` 每个测试新建一个 `NotesServer`，互不干扰。

| 测试 | 验证的性质 |
|------|-----------|
| `test_uri_containment_accepts_child` | 工作区子路径被接受 |
| `test_uri_containment_rejects_prefix_and_traversal` | `Notes-evil` 前缀混淆与 `%2e%2e` 编码穿越都被拒绝 |
| `test_discovery_uses_modern_complete_result` | discover 为 `complete`、版本正确、**不含 `roots`** |
| `test_tools_list_is_deterministic_cacheable_and_described` | `ttlMs=60000`、`public`、含 serverInfo、排序、`required == ["workspaceUri", "title"]` |
| `test_initial_delete_returns_embedded_elicitation` | 首次调用返回 `input_required`，`delete_choice` 是 `elicitation/create`、`mode == "form"` |
| `test_accepted_retry_deletes_selected_note` | 两轮后删除 `note-14`，id 为 `[1, 2]` |
| `test_declined_retry_preserves_notes` | decline 后 `deleted: False`，`note-14` 仍在 |
| `test_decline_is_terminal_for_the_confirmation_state` | decline 之后同一 state 的 accept 得到 `requestState was already consumed` |
| `test_successful_confirmation_state_cannot_be_replayed` | 成功删除后，同一 state 改选 `note-7` 被拒，`note-7` 保留 |
| `test_two_servers_consume_confirmation_atomically` | 两个共享存储的服务端并发重放（`Barrier` 保证同时进入），恰好一个成功 |
| `test_replay_store_is_bounded_and_prunes_expired_claims` | `max_entries=1` 时第二次认领因容量被拒；时钟拨到过期后剪枝，第二次认领成功 |
| `test_cancelled_or_invalid_confirmation_does_not_consume_state` | 非法 accept（`note-99`）与 cancel 都不消耗 nonce，随后合法 accept 成功 |
| `test_out_of_scope_match_is_not_exposed` | 标题 `outside root` 匹配的是工作区外笔记，返回 `isError: True` 的 `complete` 与固定文本 |
| `test_missing_elicitation_capability_is_rejected` | 无 elicitation → `-32021` 与精确 `data` |
| `test_empty_elicitation_capability_implicitly_supports_form` | `{"elicitation": {}}` → 正常返回 form |
| `test_url_only_elicitation_does_not_support_form` | `{"elicitation": {"url": {}}}` → `-32021` |
| `test_changed_arguments_cannot_reuse_state` | 重试时标题改为 `shopping` → `-32602` |
| `test_continuation_fields_require_presence_and_non_null_values` | 四个子用例：只有 state、只有 responses、state 为 null、responses 为 null |
| `test_unsupported_version_is_rejected` | `2025-11-25` → `-32022` 与精确 `data` |
| `test_non_string_protocol_version_is_invalid_params` | 版本为 `None` → `-32602` |
| `test_notification_never_receives_a_json_rpc_response` | 无 `id` 请求返回 `None`（用不匹配的标题避免副作用） |

测试盲区：

- 没有按主体授权的测试（因为代码本身不按主体授权）。
- 没有 `tools_list` 返回值独立性的测试（第 11 节有，这里没有，且确实存在污染）。
- 没有"笔记在表单展示后被删除/移出工作区"的测试——代码有这段逻辑，但未被测试覆盖。
- 没有 `confirm: false`、非法 `action`、过期 state 的测试。
