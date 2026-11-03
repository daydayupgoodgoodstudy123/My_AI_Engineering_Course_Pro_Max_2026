# 测验 · 构建 MCP 客户端：发现、路由与新旧协议兼容回退（Building an MCP Client: Discovery, Routing, and Dual-Era Fallback）

> **阶段 13 · 工具与协议 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：中文讲义为机器翻译，"时代"即 protocol era（现代 / legacy 协议代际），"允许列表"即 allowlist；有疑义以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Peer 而非会话 | 客户端为每个 server 维护一条 peer 记录（传输句柄、选定的 era 与版本、发现的能力、工具列表、待配对 id、传输健康），这是**客户端簿记**，不是协议会话；现代 server 仍在每个请求上收到版本与能力 |
| 2 | 每个请求从零盖章 | 版本、capabilities、clientInfo 在**序列化前**写进每个请求的 `params._meta`，不要"挂在连接对象上"就以为发出去了 |
| 3 | stdio 先发 `server/discover` | 给 era 划清边界：有些 legacy server 在初始化前也会接受操作，先发 `tools/list` 可能得到含糊的成功 |
| 4 | 探测的三类结果 | DiscoverResult → 现代；可识别的现代错误 → 现代（`-32022` 换版本用新 id 重试，`-32020/-32021` 修正请求）；含糊信号（未识别错误、超时、断开、空响应）→ 除非该 peer 显式允许 legacy，否则 fail closed |
| 5 | 可识别的现代错误 | `-32020` HeaderMismatch、`-32021` MissingRequiredClientCapability、`-32022` UnsupportedProtocolVersion；一旦出现就**绝不降级**，即使 peer 在 allowlist 上 |
| 6 | allowlist 是运维意图，不是证据 | `allow_legacy=True` 绑定到固定的命令 / 端点，只授予"探测一次"的许可；`-32601`、超时等**不是** legacy 的正面证据 |
| 7 | legacy 的正面证据 | 有时限的单次 `initialize`，要求：`jsonrpc: "2.0"` 且 id 匹配；恰好一个 `result`；`protocolVersion` 在配置的 legacy 集合中；`capabilities` 是对象；`serverInfo` 的 name/version 为非空字符串。全部通过后才发 `notifications/initialized` |
| 8 | era 缓存 | 选定的 era 按传输 peer 缓存，不在每次调用前重新探测；传输重启或端点变化时丢弃缓存重新协商 |
| 9 | 合并与碰撞策略 | 先排序再合并；碰撞时"加前缀 `<server>/<tool>`"或"拒绝并给出清晰配置错误"，**永不**静默覆盖；同时保存 canonical 名与 local 名 |
| 10 | 路由与恢复 | canonical 名 → peer + local 名 → 新 id → 按 era 构造请求 → 校验响应 id；传输不可用时不发送；恢复 = 重连 → 重新 discover / list → 按安全策略用新 id 重试；变更走 `subscriptions/listen`，不支持 `Last-Event-ID` 续传；`input_required` 时不阻塞读取、用新 id 重试 |

### 核心技能（能动手做到）

- [ ] 写出客户端的 era 协商状态机：discover 成功 / 可识别现代错误 / 含糊信号 / allowlist 探测 / fail closed 各走哪条路径
- [ ] 严格解码 JSON-RPC 响应：id 类型与值都匹配、`result` 与 `error` 恰好一个、错误码是真正的整数
- [ ] 从多个 peer 合并工具并处理碰撞，说清"谁拿到无前缀名字"由什么决定
- [ ] 发现并修复本节 `merge("reject")` 静默丢弃、`connect_all` 一个 peer 失败拖垮全部的问题
- [ ] 按 `ttlMs` + `cacheScope` + 授权上下文实现工具列表缓存（讲义练习 3）
- [ ] 设计传输断开后的恢复流程，并区分可自动重试与不可自动重试的操作

---

## 二、基础自测（选择题）

**Q1.** 一个**未**设置 `allow_legacy` 的 peer，对 `server/discover` 返回 `-32601 Method not found`。本节客户端会：

- A. 发送 `initialize`，尝试 legacy 握手
- B. 抛出 `RuntimeError`（"... legacy compatibility is not allowlisted"），该 peer 只收到过一条 `server/discover`
- C. 认定它是现代 server，直接发 `tools/list`
- D. 用更旧的协议版本再发一次 `server/discover`

**Q2.** 下列哪个错误码**不属于**本节的"可识别的现代错误"（`RECOGNIZED_MODERN_ERRORS`）？

- A. `-32020`
- B. `-32021`
- C. `-32022`
- D. `-32601`

**Q3.** 一个设置了 `allow_legacy=True` 的 peer 对 discover 返回 `-32022`，`data.supported` 为 `["2099-01-01"]`，而客户端只支持 `2026-07-28`。结果是：

- A. 抛出 "no mutually supported modern version"，不发送 `initialize`
- B. 既然在 allowlist 上，就退回 legacy 发送 `initialize`
- C. 用 `2099-01-01` 重试 discover
- D. 把 peer 的 era 标为 legacy

**Q4.** 按讲义，选择 legacy era 前对 `initialize` 结果的检查中，下列哪一项**不是**要求？

- A. 响应 id 与请求 id 匹配
- B. `protocolVersion` 在客户端配置的 legacy 修订集合中
- C. 结果包含 `resultType: "complete"`
- D. `serverInfo` 的 `name`、`version` 都是非空字符串

**Q5.** 运行本节 demo（peer 为 notes、files、archive，三者都有 `search` 工具），canonical 名 `search` 被路由到哪里？

- A. `archive:search`
- B. `notes:search`
- C. `files:search`
- D. 抛出碰撞错误

**Q6.** 对一个现代 peer 连续调用两次 `connect_all()`，该 server 一共收到几条 `server/discover`？

- A. 2 条
- B. 0 条
- C. 1 条
- D. 取决于 discover 结果的 `ttlMs`

**Q7.** 现代客户端的 `subscriptions/listen` 流断开了。正确的做法是：

- A. 带 `Last-Event-ID` 重连，从断点续传
- B. 等待 server 主动重新连接客户端
- C. 等待 server 发来 JSON-RPC 请求通知变更
- D. 用新的 request id 重新打开 listen，并重新拉取相关的列表 / 资源

**Q8.** 关于本节的 `Peer` 记录，正确的是：

- A. 它就是 MCP 协议会话，server 端也保存着同样的数据
- B. 它是客户端簿记（传输、era、版本、能力、工具等），不是协议会话；现代 server 仍从每个请求的 `_meta` 获得版本与能力
- C. 它由 server 在 discover 结果中下发
- D. 它等价于旧版的 `Mcp-Session-Id`

---

## 三、动手 / 代码题

**Q9.** 讲义对碰撞策略的要求是 "**Reject on collision.** Do not load the duplicate and surface a clear configuration error." 本节 `merge` 的实现：

```python
                if canonical_name in self.registry:
                    if policy == "reject":
                        continue
                    canonical_name = f"{peer.name}/{local_name}"
```

1. peer `alpha` 有 `search`，peer `beta` 有 `search`、`read`，`merge("reject")` 之后 `registry` 里有什么？问题在哪？
2. 按讲义练习 4 改写：碰撞时启动失败，错误信息中包含两个 peer 的名字；并说明为什么应该**收集全部碰撞后**一次性报错。

**Q10.** 观察 `connect_all`：

```python
    def connect_all(self) -> None:
        for peer_name in sorted(self.peers):
            self._connect_peer(self.peers[peer_name])
```

1. 添加一个传输总是抛 `ConnectionError`、名为 `aaa` 的 peer，再添加一个正常的现代 peer `zzz`。调用 `connect_all()` 后两个 peer 的 `(era, available)` 各是什么？
2. 这对"一个 host 连多个 server"的场景意味着什么？改写 `connect_all`，让一个 peer 的失败不影响其它 peer，并把失败原因返回给调用方。
3. 讲义要求"fail closed"。你的改写还满足 fail closed 吗？

**Q11.** 用 `MultiServerClient(legacy_probe_timeout_ms=275)` 连接一个 allowlisted 的 `LegacyFakeServer`，随后调用 `discover_tools()`。

1. 写出 server 依次收到的消息 `(method, id)` 以及对应的 `timeout_ms`。
2. 为什么 `notifications/initialized` 没有 id、也没有超时？为什么它必须在所有检查通过**之后**才发？
3. `decode_rpc_response` 中有这样一个条件：`type(response_id) is not type(expected_id)`。如果去掉它，测试 `test_discovery_rejects_a_boolean_response_id_for_an_integer_request` 会怎样？为什么？
4. 讲义说代码把 `legacy_probe_timeout_ms` "passes to the transport adapter; a real stdio or HTTP adapter must enforce that deadline rather than merely record it"。本节的 fake server 是如何对待这个参数的？`discover_tools` 发出的请求有超时吗？

**Q12.**（讲义练习 3）本节客户端完全忽略了 `tools/list` 结果中的 `ttlMs` 和 `cacheScope`。设计一个 `ToolCache`：

- `public` 结果可以被任何授权上下文复用；
- `private` 结果只能被同一授权上下文复用；
- 过期后必须重新拉取；`ttlMs` 为 0 或缺失时不缓存。

写出实现，并用"alice 拉到的 private 列表，bob 拿不到"和"过期后拿不到"两个用例验证。

---

## 四、面试高频题

**Q13.**（基础必考）为什么"discover 失败就退回 legacy"是危险的？请列举至少四种会产生相同表象的情况。

**Q14.**（原理深挖）本节的 legacy 回退同时要求"运维 allowlist"和"协议正面证据"。为什么缺一不可？它与 TLS 等协议中的降级攻击（downgrade attack）有什么相似之处？

**Q15.**（工程实践）多个 MCP server 暴露同名工具时，你会采用什么合并策略？本节"按 peer 名字母序先到先得"的规则有什么隐患？模型最终看到的工具名还要注意什么？

**Q16.**（场景设计）一个 stdio MCP server 在执行 `tools/call` 时进程崩溃。客户端应该如何恢复？哪些调用可以自动重试，哪些不行？

**Q17.**（追问型）server 返回了 `resultType: "input_required"`。客户端应该怎么处理？本节代码是怎么处理的？为什么讲义强调"不要阻塞 peer 的响应读取"？

---

## 五、参考答案与解析

### Q1 — 答案：B

`-32601` 不在 `RECOGNIZED_MODERN_ERRORS` 中，于是进入 `_probe_legacy(peer, "unrecognized discovery error -32601")`，而该 peer 没有 allowlist，立即抛出 `RuntimeError(f"{peer.name}: {trigger}; legacy compatibility is not allowlisted")`。测试 `test_unrecognized_error_without_allowlist_fails_without_initialize` 断言 server 只收到 `["server/discover"]`。

- A 错：讲义 "Do not treat `-32601` as positive legacy evidence. It only makes an explicitly allowlisted peer eligible for one legacy probe."
- C 错：未识别的错误不能证明对方是现代 server。
- D 错：只有 `-32022` 才会触发换版本重试。

### Q2 — 答案：D

代码：`RECOGNIZED_MODERN_ERRORS = {-32020, -32021, -32022}`，分别是 HeaderMismatch、MissingRequiredClientCapability、UnsupportedProtocolVersion。`-32601` 是 JSON-RPC 通用的 Method not found，现代和 legacy server 都可能返回，所以只是"含糊信号"。

### Q3 — 答案：A

`-32022` 是可识别的现代错误：代码从 `data.supported` 中找双方都支持的版本，`_mutual_version(["2099-01-01"])` 返回 `None`，抛出 "no mutually supported modern version"。测试 `test_recognized_modern_errors_never_fall_back` 的第三个子用例正是这个场景，并断言只发过一条 `server/discover`。这也是讲义练习 1。

- B 错：讲义 "Recognized modern errors remain modern even when the peer is on the legacy allowlist. Once a server proves that it understands the modern error vocabulary, sending `initialize` would be a downgrade."
- C 错：客户端不支持 2099 版本，不能用它发请求。
- D 错：现代 server 被标成 legacy 是最糟糕的结果。

### Q4 — 答案：C

讲义列出的 5 项要求：JSON-RPC 2.0 且 id 匹配；恰好一个 `result`、没有 `error`；`protocolVersion` 在 legacy 集合中；`capabilities` 是对象；`serverInfo` 的 name/version 为非空字符串。`resultType` 是**现代**结果的字段，legacy 的 initialize 结果不会有它（第 07 节讲义："Do not stamp modern `resultType` fields onto legacy initialization results"）。客户端只是在 legacy era 下把**后续**普通结果缺失的 `resultType` 视为 `"complete"`。

### Q5 — 答案：A

实际 demo 输出：

```text
Merged tools
  create               -> notes:create
  files/search         -> files:search
  notes/search         -> notes:search
  read                 -> files:read
  restore              -> archive:restore
  search               -> archive:search
```

`merge` 按 `sorted(self.peers)` 遍历，顺序是 archive、files、notes，第一个遇到 `search` 的 archive 拿到无前缀名字，其余两个加前缀。注意这意味着：一个 **legacy** server 仅仅因为名字字母序靠前，就拿走了最"自然"的工具名——见 Q15。

### Q6 — 答案：C

```python
    def _connect_peer(self, peer):
        if peer.available and peer.era in {"modern", "legacy"}:
            return
```

已经选定 era 且可用的 peer 直接返回，不再探测（测试 `test_selected_peer_era_is_cached_for_transport_lifetime`）。讲义："Cache the selected era for the transport peer. Do not probe again before every call."

- D 错：`ttlMs` 是给 discover **结果**用的缓存提示，本节代码并未使用它；era 缓存的生命周期是传输生命周期。

### Q7 — 答案：D

讲义："On disconnect, open a new listen request and refetch relevant lists or resources. Modern streams do not resume with `Last-Event-ID`."

- A 错：明确不支持续传。
- B、C 错：现代 server 不会主动连接客户端，也不会发起独立 JSON-RPC 请求；变更只通过客户端打开的 listen 流以通知形式到达。

### Q8 — 答案：B

讲义："This is client bookkeeping. It is not protocol session state. On modern MCP, the server still receives current version and capabilities on every request." 代码中 `_request` 每次都用 `modern_request(...)` 重新盖章，测试 `test_modern_tool_call_repeats_metadata` 验证了 `tools/call` 也带版本。

- A、C 错：server 端什么也不保存，peer 记录完全在客户端。
- D 错：`Mcp-Session-Id` 是旧版 HTTP 的会话机制，现代 MCP 中不存在。

### Q9 — 参考答案

1. 实测 `merge("reject")` 后 `registry` 为 `['read', 'search']`，其中 `search` 属于 alpha，beta 的 `search` 被 `continue` **静默跳过**——没有日志、没有异常。这实际上是"静默丢弃"，与讲义"surface a clear configuration error"不符；运维者无从知道 beta 的工具从未被加载，模型也永远调不到它。
2. 改写（已实际运行，输出 `ValueError: tool name collisions: 'search': alpha vs beta`；prefix 策略下仍得到 `['beta/search', 'read', 'search']`）：

```python
    def merge(self, policy: str = "prefix-on-collision") -> None:
        if policy not in {"prefix-on-collision", "reject"}:
            raise ValueError("policy must be prefix-on-collision or reject")
        registry, owner, conflicts = {}, {}, []
        for peer_name in sorted(self.peers):
            for tool in self.peers[peer_name].tools:
                local = tool["name"]
                canonical = local
                if canonical in registry:
                    if policy == "reject":
                        conflicts.append(f"{local!r}: {owner[local]} vs {peer_name}")
                        continue
                    canonical = f"{peer_name}/{local}"
                    if canonical in registry:
                        raise ValueError(f"canonical collision: {canonical}")
                registry[canonical] = MergedTool(canonical, peer_name, local, tool.get("description", ""))
                owner.setdefault(local, peer_name)
        if conflicts:
            raise ValueError("tool name collisions: " + "; ".join(conflicts))
        self.registry = dict(sorted(registry.items()))
```

   为什么收集全部后再报错：配置错误往往不止一处，一次只报一个会让运维"修一个、启动、再报下一个"反复循环；另外先构建到局部变量、确认无误后再赋给 `self.registry`，失败时不会留下一个"合并了一半"的注册表（原代码先 `self.registry.clear()`，中途抛异常会让注册表处于半成品状态）。

### Q10 — 参考答案

1. 实测：`{'aaa': ('unknown', False), 'zzz': ('unknown', False)}`。`aaa` 的 `ConnectionError` 触发 `_probe_legacy`，因未 allowlist 抛出 `RuntimeError`，异常直接冲出 `connect_all` 的循环，按字母序排在后面的 `zzz` **根本没有被尝试连接**。
2. 含义：一个坏掉的 server（进程起不来、配置错误）会让 host 失去**所有** server 的工具，故障被放大。改写（已实测：返回 `{'aaa': 'aaa: ConnectionError; legacy compatibility is not allowlisted'}`，`zzz` 变为 `('modern', True)`）：

```python
    def connect_all(self) -> dict[str, str]:
        failures: dict[str, str] = {}
        for peer_name in sorted(self.peers):
            try:
                self._connect_peer(self.peers[peer_name])
            except RuntimeError as exc:
                failures[peer_name] = str(exc)
        return failures
```

3. 仍然满足 fail closed：fail closed 的含义是"证据不足时**不降级、不启用**这个 peer"，失败的 peer 保持 `era="unknown"`、`available=False`，`discover_tools` 会跳过它，`call` 会返回 "Transport unavailable"。隔离的是故障范围，而不是放松安全判断。调用方应把 `failures` 写进启动报告（skill 要求输出"startup report listing peer, selected era..."）。

### Q11 — 参考答案

1. 实测：

| 顺序 | method | id | timeout_ms |
|------|--------|----|-----------|
| 1 | `server/discover` | 1 | 1000（`discovery_timeout_ms` 默认值） |
| 2 | `initialize` | 2 | 275（`legacy_probe_timeout_ms`） |
| 3 | `notifications/initialized` | 无 | None |
| 4 | `tools/list` | 3 | None |

   id 由客户端级的 `_new_id()` 单调递增分配，所有 peer 共用一个计数器，每次（包括重试）都是新 id。

2. `notifications/initialized` 是**通知**：不期待响应，所以没有 id，也没有需要等待的超时。必须在所有检查通过后才发，是因为它的语义是"我接受了你的 initialize 结果，握手完成"；如果版本不受支持或 `serverInfo` 畸形时也发了，就等于确认了一个客户端并不支持的协议状态（测试 `test_allowlisted_unsupported_legacy_revision_fails_closed` 断言此时**没有**发送它）。

3. 测试会失败。Python 中 `True == 1` 为真，若只比较值，`id: true` 的响应会被当作请求 1 的响应接受，`connect_all` 不会抛 "invalid JSON-RPC response envelope"。在 JSON 中 `true` 和 `1` 是不同类型，严格的关联必须同时比较类型与值；同理 `1` 和 `"1"` 也不应相互匹配。

4. fake server 只是把 `timeout_ms` 追加到 `self.timeouts_ms` 列表里**记录**下来，并不真正计时——这正是测试能断言 `[1_000, 275, None]` 的原因。`discover_tools` → `_request` → `_send(peer, message)` 没有传超时，后续的 `tools/list` / `tools/call` 都是**无界等待**。真实适配器需要在读取响应时实施截止时间（如 `select` / `asyncio.wait_for`），并给普通请求也设置超时。

### Q12 — 参考答案

参考实现（已实际运行：alice 得到 `['admin_tool']`、bob 得到 `None`；时钟推进 31 秒后 alice 得到 `None`；`public` 列表 bob 可以复用）：

```python
import time

class ToolCache:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.entries = {}

    def key(self, peer, scope, auth_context):
        if scope == "public":
            return (peer, "public")
        return (peer, "private", auth_context)

    def get(self, peer, auth_context):
        for k in ((peer, "public"), (peer, "private", auth_context)):
            hit = self.entries.get(k)
            if hit and hit[0] > self.clock():
                return hit[1]
        return None

    def put(self, peer, auth_context, result):
        ttl = result.get("ttlMs", 0)
        scope = result.get("cacheScope", "private")     # 缺失时取安全默认
        if ttl > 0:
            self.entries[self.key(peer, scope, auth_context)] = (
                self.clock() + ttl / 1000, result["tools"])
```

要点：
- 缓存键必须包含授权上下文（对 private），否则就是讲义和 skill 中的硬性拒绝项"Sharing a private cached list across authorization contexts"。
- 用 `time.monotonic()` 而不是 `time.time()`，避免系统时钟调整导致过期判断错误；可注入 `clock` 便于测试。
- legacy peer 的结果没有缓存提示，按 `ttlMs` 缺失处理为"不缓存"，与讲义"Do not require modern cache fields on a response from an earlier negotiated era"一致。
- 收到 list-change 通知时应主动失效对应条目。

### Q13 — 参考回答要点

- 讲义："A malformed modern request, an overloaded server, a dead process, and an old server can all produce the same timeout or connection close. Those signals are ambiguous."
- 会产生"discover 失败"表象的情况：
  1. 真正的 legacy server（不认识 `server/discover`）；
  2. 现代 server，但客户端请求构造有 bug（例如缺 `_meta`，得到 `-32602`）；
  3. 现代 server 过载 / 慢，超时；
  4. 进程已崩溃或启动失败，连接关闭 / 空响应；
  5. 中间代理或网关返回了自己的错误；
  6. 恶意或被篡改的 server 故意装作不认识，诱导客户端降级到语义更弱的旧协议。
- 危险：把 2–6 当成 legacy 会让客户端对现代 server 发 `initialize`，走错误的协议分支，或者在本应报错修复时"悄悄降级"，掩盖真实故障。
- 正确做法：只有 DiscoverResult 和可识别的现代错误能确定现代 era；含糊信号要么 fail closed，要么（仅限 allowlist）做一次有时限的 legacy 探测，并要求正面证据。

### Q14 — 参考回答要点

- **只有 allowlist、没有证据**：运维允许了，但对方其实是坏掉的现代 server 或冒充者，回一个畸形结果、错误或干脆超时，客户端就进入 legacy——这会把运维的"许可"误当成事实。本节要求 initialize 结果在 id、版本、capabilities、serverInfo 上全部合格。
- **只有证据、没有 allowlist**：任何 server 只要回一个像样的 initialize 结果就能把自己"降级"到连接级状态、语义更弱的旧协议。讲义："Do not use a wildcard that lets an arbitrary server opt itself into weaker semantics."
- **与降级攻击的相似处**：TLS 降级攻击中，中间人通过干扰握手让双方退回到更弱的协议版本；对策是"双方都支持高版本时不允许回退"（如 TLS 的降级保护机制）。本节的"可识别现代错误后绝不降级""allowlist 绑定固定命令 / 端点""legacy 探测有时限且只一次"是同样的思想。
- 加分点：allowlist 应绑定到**固定的命令或端点**而不是 server 自报的名字；era 缓存在传输重启 / 端点变化时作废，防止"换了个 server 却沿用旧判断"。

### Q15 — 参考回答要点

- **策略**：
  - prefix-on-collision：保留第一个的原名，后续加 `<server>/<tool>` 前缀；对模型友好，但"谁是第一个"需要明确规则。
  - reject：碰撞即启动失败，强迫运维显式改名或配置别名；最安全。
  - 永远不要 silent overwrite：讲义 "It hides which server receives a model-selected action."
- **"字母序先到先得"的隐患**：
  - 稳定、可复现（不依赖启动时序），这是它的优点；
  - 但无前缀名的归属由 **peer 的配置名**决定，而不是由可信度或用户意图决定：demo 中 legacy 的 archive 拿走了 `search`；新加一个名为 `aaa` 的 server 就会"抢走"已有的无前缀名，模型原本调用 `search` 的行为悄悄改投到另一个 server——这正是第 15 节工具投毒 / 影子工具的攻击面；
  - 恶意 server 还可以注册名为 `notes/search` 的工具占位：实测本节代码在 notes 的 `search` 需要加前缀时会抛出 `canonical collision: notes/search`，导致整个合并失败（拒绝服务）。
- **改进**：对重要工具配置显式别名 / 优先级；可信 server 优先；禁止 local 名包含分隔符 `/`；启动报告列出所有被加前缀的工具。
- **模型侧名字**：部分模型 provider 对工具名字符集和长度有限制，`/` 不一定被允许，映射到 provider 时可能需要再做一次转义（例如换成 `__`），并保持可逆映射。

### Q16 — 参考回答要点

- **检测**：读取响应时遇到 EOF / 管道断开 / 超时；把该 peer 标为不可用，失败所有在途请求（skill："fail in-flight work"）。
- **恢复**：
  1. 重启进程（stdio）或重连（HTTP）；
  2. **丢弃 era 缓存**，重新 `server/discover`（讲义："If the transport restarts or its endpoint changes, discard the peer-era cache and negotiate again"）；
  3. 重新 `tools/list`，重新合并（工具可能变了）；
  4. 重新打开 `subscriptions/listen`；
  5. 在途请求按安全策略处理。
- **重试规则**：
  - 只读、幂等操作（如 `notes_search`、`tools/list`）可自动用**新 id** 重试；
  - 非幂等操作（如 `notes_create`、转账、发邮件）不能盲目重试——崩溃可能发生在执行之后、响应之前；需要应用层幂等键或交给用户决定（skill："Refuse to retry a non-idempotent call automatically without an application idempotency key or user decision"）；
  - `idempotentHint` 可作参考，但它只是提示。
- 本节代码现状：`_request` 不捕获 `TimeoutError` / `ConnectionError`，异常直接冒泡，`peer.available` 仍是 `True`（已实测），也没有重启逻辑——恢复部分是留给读者的。

### Q17 — 参考回答要点

- **正确处理**（讲义）：`input_required` 结果中嵌入了输入请求（sampling / elicitation / roots）；客户端去满足这些请求（调用模型、询问用户、提供目录范围），然后用**新的 JSON-RPC id** 重试**原方法**，并在重试中带上这些输入。
- **本节代码**：`_request` 只检查现代结果"有没有" `resultType`，不检查值；我们实测把 server 的 `tools/call` 结果改为 `resultType: "input_required"`，`client.call` 直接把它原样返回给调用方，没有任何 MRTR 处理。
- **为什么不能阻塞读取**：同一个 peer 上可能有多个在途请求（多个工具并行调用），响应按 id 异步到达。如果读取线程在等用户回答 elicitation 时卡住，其它请求的响应就无人读取，可能超时，stdio 管道缓冲区还可能被写满导致 server 阻塞。应把"满足输入"放到独立的任务中，读取循环只负责按 id 分发响应。
- 加分点：重试时要保持与原请求的关联（日志 / trace），但不能复用旧 id；用户拒绝提供输入时应把结果作为取消 / 错误返回给模型。第 11、12 节详细展开。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：`_meta`、`server/discover`、`-32022` 与协议时代。
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：本节客户端对接的 server 形态（`ModernFakeServer` 是它的简化版）。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../03-parallel-and-streaming-tool-calls/docs/zh.md)：多个在途调用与按 id 关联响应（Q17）。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：工具命名与命名空间。

### 本节被哪些后续内容用到
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：真实的 stdio / HTTP 传输适配器、超时与 `-32020`。
- [阶段 13 · 10 MCP Resources 与 Prompts：无状态服务端的可寻址上下文](../../10-mcp-resources-and-prompts/docs/zh.md)：`subscriptions/listen`（讲义练习 5）。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：`input_required` 与重试（Q17）。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：工具名抢占、影子工具与路由安全（Q15）。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：把多 server 合并与路由放到网关层。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：超时、取消、重试与幂等（Q16）。
- [阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：agent 侧如何使用合并后的工具目录。

### 延伸关键词
`MCP client` · `peer` · `protocol era` · `server/discover` · `-32020 / -32021 / -32022` · `fail closed` · `legacy allowlist` · `positive legacy evidence` · `notifications/initialized` · `namespace merge` · `collision policy` · `tool shadowing` · `cacheScope` · `subscriptions/listen` · `input_required` · `idempotency key`
