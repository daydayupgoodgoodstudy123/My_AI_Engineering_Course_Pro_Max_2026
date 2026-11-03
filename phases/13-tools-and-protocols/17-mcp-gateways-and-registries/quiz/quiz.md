# 测验 · Stateless MCP 网关与注册表准入（Stateless MCP Gateways and Registry Admission）

> **阶段 13 · 工具与协议 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 网关的位置与职责 | 位于客户端与多个后端 MCP 服务端之间，对外只暴露一个 MCP 端点，集中做认证、授权、准入、限流、审计，再转发已批准的请求；当前协议下**不需要会话亲和** |
| 2 | 现代网关七步 | 认证 principal → 校验版本/`Mcp-Method`/`Mcp-Name`/`_meta` → 授权 principal、资源、方法、工具、参数 → descriptor/注册表/限流/数据策略 → 为后端构造全新的自包含请求 → 校验后端结果 → 记录不含秘密的审计事件 |
| 3 | 运行时策略是主决策 | 准入（admission）只决定"哪个后端版本可以进入网关"，不授权某次实时调用；每个请求都要基于 principal、租户、参数、已准入的 pin、后端健康、能力交集、数据分级、限流状态重新计算 |
| 4 | 单一 POST 端点 | 每个 JSON-RPC 消息一个 POST，返回 JSON 或请求范围的 SSE；现代 GET/DELETE 返回 405；`Mcp-Session-Id`、`Last-Event-ID` 不产生权限、亲和或重放；头 body 不一致 `-32020` 必须在查找后端之前拒绝 |
| 5 | 每层都做 discovery | 网关对客户端实现 `server/discover`，也去发现每个后端；只宣告网关能端到端兑现的**能力交集**；`serverInfo` 只是自报信息 |
| 6 | 转发时的能力 | 网关是后端的客户端：转发请求带网关自己的 `_meta`，只声明网关能正确中介的能力，不能照抄外层客户端能力 |
| 7 | 命名空间与 pin | 公开名 `notes.search` 等稳定且确定排序，保留到后端的映射；改公开名是一次迁移；准入时对完整 descriptor 规范化哈希，list 与 call 时都比对，变化即下架、拒绝调用、审计、等待重新批准 |
| 8 | 注册表帮助发现，不负责决定 | Registry 的 `server.json` 是发布元数据；发布者验证、来源、准入状态放在**独立的**准入记录里；记录精确的注册表与记录 ID、发布者证据、传输与端点、版本 pin、摘要、issuer/resource、审批人与过期 |
| 9 | 凭证中介与限流审计 | 外层 token 不转发给后端，后端凭证不下发给客户端；限流键 = principal + issuer + resource + 公开工具 + 成本类别 + 时间窗；审计记录请求/追踪 ID、principal、路由、pin 版本、决策与原因、延迟、MRTR 轮次或 task ID，并脱敏 |
| 10 | 交互路由 | 请求范围 SSE 随 POST 关闭而取消；`subscriptions/listen` 走 POST + SSE，首个事件确认支持的子集，subscriptionId 等于打开它的请求 id；MRTR 的 `requestState` 逐字节转发、每轮重新授权；Tasks 用 `taskId` 作 `Mcp-Name`，不实现 `tasks/list`、`tasks/result`；旧协议放进显式的 legacy adapter |

### 核心技能（能动手做到）

- [ ] 画出一次 `tools/call` 经过网关的完整路径，并标出每一步失败时的 HTTP 状态与 JSON-RPC 错误码
- [ ] 写出按 principal 过滤、按公开名排序、只包含已准入且 pin 一致工具的 `tools/list`，并说明为什么必须 `cacheScope: private`
- [ ] 用 `json.dumps(sort_keys=True, separators=(",", ":"))` + SHA-256 实现 descriptor pin，并让 list 与 call 共用同一套路由检查
- [ ] 写出 `server.json` 形状校验 + 外部准入状态拼接的准入函数，并指出它还缺哪些证据字段
- [ ] 手算令牌桶（token bucket）在任意时间序列下的放行/拒绝结果
- [ ] 构造一个 `subscriptions/listen` 请求及其确认事件，说明 subscriptionId 与过滤字段

---

## 二、基础自测（选择题）

**Q1.** 一个符合 2026-07-28 的 MCP 网关，在两次普通客户端请求之间需要保留什么？

- A. 客户端到某个后端实例的会话亲和关系
- B. 把客户端的 `Mcp-Session-Id` 改写成后端会话 ID 的映射表
- C. 以连接为键缓存的"允许"决定，避免重复授权
- D. 不需要协议会话；每个请求都自带验证和路由所需的信息（应用状态可放在数据库、任务句柄或受完整性保护的 MRTR 状态里）

**Q2.** 网关返回的 `tools/list` 会因调用者的角色不同而不同。它应该使用：

- A. `cacheScope: "public"`，并把 `ttlMs` 设得很长以减轻后端压力
- B. `cacheScope: "private"`，配合有界的 `ttlMs`
- C. 以 `clientInfo.name` 为键的共享缓存
- D. 不需要缓存提示，客户端自己决定

**Q3.** 关于官方 Registry 的 `server.json` 记录，正确的用法是：

- A. 校验它的发布形状，然后与**独立的**已验证发布者、来源、策略与审批状态拼接，才决定是否准入
- B. 只要记录存在于官方注册表，就说明它已经过安全审查，可以直接路由
- C. 把 `"verified": true` 字段写进 `server.json`，网关读取它即可
- D. 显示名与知名产品一致即可准入

**Q4.** 网关把一次 `tools/call` 转发给后端时，应该：

- A. 把外层客户端的 bearer token 原样带给后端，方便后端识别用户
- B. 原样复制外层请求的 `clientCapabilities`，保证能力一致
- C. 为后端构造一个全新的自包含请求：新的 JSON-RPC id、网关自己的 `clientInfo`、只包含网关能中介的能力，并用网关为该后端单独获取的凭证
- D. 复用外层请求的 id 与全部 HTTP 头，减少改动

**Q5.** 在现代 Streamable HTTP 中，客户端想长期接收"工具列表已变化"的通知，应该：

- A. 打开一个独立的 GET 事件流，断线后用 `Last-Event-ID` 重放
- B. 用 POST 发送 `subscriptions/listen`（`notifications: {"toolsListChanged": true}`），响应为 SSE；首个事件确认支持的子集，subscriptionId 就是该请求的 JSON-RPC id
- C. 调用 `resources/subscribe`
- D. 携带 `Mcp-Session-Id` 定期轮询

**Q6.** 关于 Tasks 扩展经过网关的路由，正确的是：

- A. 网关应实现 `tasks/list` 让客户端列出所有任务
- B. 任务结果通过 `tasks/result` 获取
- C. 任务需要输入时，客户端重新调用原工具即可
- D. `tasks/get`、`tasks/update`、`tasks/cancel` 用 `params.taskId` 作为 `Mcp-Name`；网关按任务句柄记录 principal 与后端路由；`tasks/cancel` 只是协作式意图

**Q7.** 后端返回 `resultType: "input_required"`（MRTR）。网关的正确做法是：

- A. 网关自己替用户回答，避免打扰
- B. 把 `requestState` 解码后改写成网关格式再发给客户端
- C. 仅当外层客户端支持所需的输入请求时才转发；`requestState` 逐字节保留；客户端用新 id 重试时网关重新授权、检查同一公开路由，再向后端发一个全新的请求
- D. 第一轮已授权，所以第二轮可以跳过授权

**Q8.** 本节 `Gateway.handle` 处理一次被允许的 `tools/call` 时，检查的实际顺序是：

- A. bearer 认证 → `validate_wire` → RBAC → 令牌桶限流 → descriptor pin → 转发 → 记录 allow 审计
- B. `validate_wire` → 转发 → RBAC → bearer 认证
- C. RBAC → bearer 认证 → descriptor pin → `validate_wire` → 限流
- D. 限流 → bearer 认证 → 转发 → `validate_wire`

---

## 三、动手 / 代码题

**Q9.** 运行下面的实验（先把 `notes` 后端的准入状态改为撤销）：

```python
g = main.Gateway()
main.VERIFIED_ADMISSION_STATE["notes"]["admission"]["status"] = "revoked"
# 1) alice 调 tools/list
# 2) alice 直接调 tools/call notes.search
```

1. 写出两次调用的结果（`tools/list` 中有哪些工具？`tools/call` 的状态码与审计决策？）。
2. 这违背了讲义的哪条原则？
3. 重构：写一个 `list` 与 `call` 共用的 `_route(user_id, canonical) -> (backend, tool) | ProtocolError`，让准入、RBAC、pin 在两条路径上完全一致。

**Q10.** 令牌桶实现：

```python
    def consume(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        self.tokens = min(self.capacity, self.tokens + max(0.0, current - self.updated_at) * self.refill_per_second)
        self.updated_at = current
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True
```

1. `tb = TokenBucket(tokens=0, updated_at=100.0)`（默认 capacity 5、每秒补 1），依次调用 `consume(100.5)`、`consume(101.0)`、`consume(110)`，写出每次的返回值与调用后的 `tokens`。
2. 新建网关后，alice 在同一瞬间连续调用 7 次 `issues.list`，状态码序列是什么？
3. 把 `notes.search` 的描述改掉后，alice 连续调用 6 次 `notes.search`，状态码序列是什么？这说明检查顺序有什么问题？
4. bob 连续 10 次调用他无权使用的 `notes.create`，`gateway.buckets` 里有 bob 的桶吗？这是好是坏？
5. 讲义要求限流键包含 principal、issuer、resource、公开工具、成本类别、时间窗。当前代码的键是什么？如何改？

**Q11.** 阅读 `registry_record_is_admissible`：

```python
def registry_record_is_admissible(record, admission, namespace: str = "com.example/") -> bool:
    ...
    return bool(
        isinstance(record.get("name"), str)
        and record["name"].startswith(namespace)
        ...
        and admission.get("publisher", {}).get("namespace") == "com.example"
        and admission.get("publisher", {}).get("status") == "verified"
        and admission.get("provenance", {}).get("source") == "registry.modelcontextprotocol.io"
        and admission.get("admission", {}).get("status") == "approved"
    )
```

1. 实测 `namespace="org.acme/"`、记录名 `org.acme/notes`、发布者命名空间 `org.acme`（已验证）时返回什么？为什么？
2. 对照讲义"For each admitted backend, record ..."清单，当前准入记录缺了哪些证据？
3. 讲义说私有服务端也可以用同一套证据模式准入。当前函数能做到吗？

**Q12.** 写出下列调用的 `(HTTP 状态, JSON-RPC 错误码或说明)`（`g = Gateway()`，均用 `make_request` 构造）：

1. `g.handle("bearer-eve", tools/list)`
2. `g.handle("bearer-eve", tools/list)`，但 `Mcp-Method` 头被改成 `"x"`
3. `g.handle("bearer-bob", tools/call notes.create)`
4. `g.handle("bearer-alice", tasks/cancel {"taskId": "t1"})`
5. `g.handle("bearer-alice", subscriptions/listen, accept="application/json")`
6. `g.handle("bearer-alice", tools/call notes.search, arguments="DROP")`
7. 第 6 题改为合法参数，但删除 `id`（notification）；之后 `g.forwarded_request_ids` 是什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 MCP 网关？为什么企业部署需要它？请按讲义的七步说明一次请求在网关中的处理过程。

**Q14.**（原理深挖）"准入（admission）"与"运行时策略（runtime policy）"有什么区别？为什么讲义说运行时策略才是主决策？策略服务不可用时怎么办？

**Q15.**（工程实践）网关的凭证中介、限流与审计应该怎么设计？请分别说明键、绑定关系与需要脱敏的字段。

**Q16.**（场景设计）公司有 30 个 MCP 后端（其中 3 个还只支持 `2025-11-25`）、3 个租户、需要长期列表变化通知和 Tasks。请设计网关的发现、命名空间、缓存、订阅、Tasks 路由与 legacy adapter。

**Q17.**（追问型）"为什么 `tools/list` 一定要确定性排序和命名空间？改个公开名为什么算迁移？为什么网关只能宣告能力交集？"

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："No step needs a hidden protocol session. Application state can still exist in databases, explicit handles, Tasks, or integrity-protected MRTR state." 以及 "Older gateway designs often multiplexed one client session into several backend sessions and rewrote `Mcp-Session-Id`. That is a legacy compatibility design." A、B 是旧设计；C 违反 "Do not cache an allow decision under a connection or removed session identifier"——用户角色可能在两次请求之间被撤销。本节测试 `test_legacy_headers_do_not_create_gateway_state` 断言网关对象上根本没有 `sessions` 属性。

### Q2 — 答案：B

讲义："When visibility differs by principal, return `cacheScope: private`. A bounded `ttlMs` reduces backend discovery load without allowing a user-specific list to leak across authorization contexts." 代码中网关 `tools/list` 是 `private` + `ttlMs: 10_000`，`server/discover` 也是 `private`（讲义练习 4 讨论了原因）。A 会把 alice 能看到的 `notes.create` 泄露给 bob；C 用自报的 `clientInfo` 做键，任何人都能冒用；D 放弃了缓存控制。

### Q3 — 答案：A

讲义："Publication metadata does not carry the gateway's security decision. Keep verified publisher and provenance evidence in separate admission state ... The gateway checks the `server.json` shape and joins it to that external state." 以及 "Do not accept a server because its display name resembles a familiar product. Do not treat registry presence as an operational security review." B、D 正是讲义点名的错误；C 把安全判定"发明"进 `server.json`，属于 skill 文件 Hard rejects 中的 "Security verification invented inside `server.json`"。测试 `test_registry_server_json_requires_external_verified_admission` 断言 `server.json` 只有 `$schema`、`name`、`description`、`version`、`packages` 五个键，且发布者状态改为 `unverified` 时准入失败。

### Q4 — 答案：C

讲义："Create a fresh self-contained request for the selected backend"、"Do not blindly copy the outer client capabilities to a backend. The gateway is the backend's client"、"Never pass the outer gateway token to a backend." 代码 `_forward` 用 `make_request(..., client_name="enterprise-gateway")` 生成新的 `_meta`（能力为 `{}`），id 为 `gw-1`、`gw-2`……（测试 `test_allowed_call_is_forwarded_with_fresh_backend_id`：外层 id 99，转发 id `gw-1`）。A 是 token passthrough；B 可能让后端以为客户端能处理网关根本无法中介的特性（如 elicitation）；D 让两跳请求混在一起，也破坏追踪。

### Q5 — 答案：B

讲义 "Long-lived change notifications"：POST `subscriptions/listen`，过滤字段是扁平的 `toolsListChanged`、`promptsListChanged`、`resourcesListChanged`、`resourceSubscriptions`；首个事件 `notifications/subscriptions/acknowledged` 确认支持的子集，`_meta` 中 `io.modelcontextprotocol/subscriptionId` 等于打开流的请求 id；没有自动重放、没有自动重新订阅。A、C 是旧传输/旧方法（"Keep those only in a version-gated older path"）；D 依赖已删除的会话。代码只确认 `toolsListChanged`（测试 `test_subscription_acknowledges_only_supported_requested_types`：同时请求 `resourcesListChanged` 时只确认前者）。

### Q6 — 答案：D

讲义 "Tasks extension routing"："Subsequent `tasks/get`, `tasks/update`, and `tasks/cancel` calls use `params.taskId` as `Mcp-Name` ... `tasks/cancel` is a cooperative intent with an empty complete acknowledgment, not a guarantee that work stops." "Do not implement new `tasks/list` or `tasks/result` methods." "A task that needs input exposes complete embedded requests through `tasks/get`; the client answers them through `tasks/update`, not by retrying the original tool call." 代码中 `NAMED_METHODS` 包含三个 tasks 方法，`request_name` 对它们返回 `taskId`；但网关并未实现这些方法，所以返回 404（测试 `test_task_methods_route_by_task_id_header_before_dispatch`，这是练习 2 留的空）。

### Q7 — 答案：C

讲义 "MRTR through a gateway"："the gateway can forward that result only if the outer client supports the needed input request. Preserve `requestState` byte for byte unless the gateway deliberately terminates and reissues the interaction ... The gateway re-authorizes the retry, checks the same public route, then forwards a fresh backend request. It must not assume an earlier round granted unlimited approval." A 让网关越权代替用户；B 会破坏后端的签名校验（见第 15 节）；D 正是讲义警告的"把早先的批准当作后续请求的信任"。本节代码没有实现 MRTR 转发，这是概念题。

### Q8 — 答案：A

`handle` 的实际顺序：`http_method != "POST"` → `USERS.get(bearer)`（未知即 401）→ `validate_wire` → `canonical not in RBAC[...]`（403）→ `bucket.consume()`（429）→ 查找工具并 `_is_pinned`（409）→ `_forward` → 审计 `allow`。认证在线协议校验之前（实测未知 bearer 即使头部不一致也先得到 401），线协议校验在查找后端之前（测试 `test_header_body_mismatch_is_rejected_before_route` 断言 `forwarded_request_ids == []`）。B、C、D 都把昂贵或有副作用的步骤放在了校验之前。注意：本顺序中**没有**准入检查，见 Q9。

### Q9 — 参考答案

1. 实测：`tools/list` 只剩 `['issues.list', 'issues.open']`——`notes.*` 被下架；但 `tools/call notes.search` 返回 **200**，审计记录 `{'principal': 'alice', 'tool': 'notes.search', 'decision': 'allow'}`，请求被转发到了已撤销准入的后端。
2. 原因：`registry_record_is_admissible` 只在 `_visible_tools` 中调用，`tools/call` 分支只查 RBAC、限流、pin。这违背了讲义的两处要求：
   - "Admission record before connection"（Use It 中的 seam 顺序）——撤销准入的后端不应再可路由；
   - 运行时策略要以"admitted descriptor pin"等准入证据为输入。讲义在 descriptor 变化时要求 "Remove it from `tools/list`" 与 "Reject direct calls" 同时发生——pin 这部分代码做到了，准入这部分没有。
   这是典型的"列表过滤 ≠ 授权"漏洞：攻击者只要知道工具名，就能绕过 list 直接调用。
3. 参考重构（思路：一个函数决定"此用户此公开名能否路由"，list 与 call 都调它；已在子类中实际运行：alice 列表为 4 个工具、bob 为 2 个，撤销 `notes` 准入后列表只剩 `issues.*`，`_route("alice", "notes.search")` 抛 `-32003 Backend not admitted`）：

```python
    def _route(self, user_id: str, canonical: str) -> tuple[BackendServer, dict[str, Any]]:
        if canonical not in RBAC.get(user_id, set()):
            raise ProtocolError(-32003, "Forbidden", {"tool": canonical})
        server_name, _, tool_name = canonical.partition(".")
        backend = self.backends.get(server_name)
        if backend is None or not registry_record_is_admissible(
            REGISTRY_SERVER_JSON[server_name], VERIFIED_ADMISSION_STATE[server_name]
        ):
            raise ProtocolError(-32003, "Backend not admitted", {"tool": canonical})
        tool = next((t for t in backend.tools if t["name"] == tool_name), None)
        if tool is None or not self._is_pinned(canonical, tool):
            raise ProtocolError(-32010, "Descriptor changed", {"tool": canonical})
        return backend, tool

    def _visible_tools(self, user_id):
        visible = []
        for server_name, backend in self.backends.items():
            for tool in backend.tools:
                canonical = f"{server_name}.{tool['name']}"
                try:
                    self._route(user_id, canonical)
                except ProtocolError:
                    continue
                visible.append({**tool, "name": canonical})
        return sorted(visible, key=lambda t: t["name"])
```

   `tools/call` 中先 `self._route(...)`，通过后再限流和转发（把便宜的检查放在消耗限流令牌之前，见 Q10 第 3 问）。`-32010` 对应的 409 状态需要在异常处理处映射。

### Q10 — 参考答案

1. 已实测：

| 调用 | 计算 | 返回 | 之后 `tokens` |
|------|------|------|--------------|
| `consume(100.5)` | `min(5, 0 + 0.5×1) = 0.5`，`< 1` | `False` | 0.5 |
| `consume(101.0)` | `min(5, 0.5 + 0.5) = 1.0`，减 1 | `True` | 0.0 |
| `consume(110)` | `min(5, 0 + 9) = 5`，减 1 | `True` | 4 |

   注意被拒绝的那次也更新了 `updated_at` 和 `tokens`（部分令牌被保留下来），所以 101.0 时刚好凑满 1 个。
2. `[200, 200, 200, 200, 200, 429, 429]`（实测）。初始 5 个令牌，同一瞬间几乎没有补充。审计依次为 5 个 `allow` 和 2 个 `rate_limit`。bob 有独立的桶，此时调用 `issues.list` 仍是 200。
3. `[409, 409, 409, 409, 409, 429]`，之后 alice 的桶 `tokens == 0.0`（实测）。pin 校验放在限流**之后**，所以一个已下架的工具也在消耗用户的配额，第 6 次反而报"限流"而不是"descriptor 已变化"。讲义："Apply cheap validation before consuming expensive work. Decide whether rejected calls count against abuse limits, business quotas, or both." pin 检查是纯本地的便宜操作，应放在限流前面（或者明确规定"被拒调用也计入滥用限额"）。
4. 没有（`g.buckets.get("bob")` 为 `None`）：RBAC 拒绝发生在 `setdefault` 创建桶之前。好处是被拒调用不会消耗业务配额；坏处是攻击者可以无限次探测无权限的工具名而不受任何速率限制。讲义要求明确决定"被拒调用是否计入滥用限额"——常见做法是两个桶：业务配额（只计成功调用）与滥用限额（所有调用，含被拒）。
5. 当前键是 `user["id"]`（仅 principal）。改为：

```python
key = (user["id"], user_issuer, gateway_resource, canonical, cost_class(canonical), window)
bucket = self.buckets.setdefault(key, TokenBucket(**limits_for(cost_class(canonical))))
```

   其中写操作（`notes.create`）的成本类别更高、容量更小；时间窗由令牌桶参数体现。会话 ID 不能作为键——讲义："A session id is absent and would be easy to rotate even if it existed."

### Q11 — 参考答案

1. 返回 **`False`**（实测）。`namespace` 参数只作用于 `record["name"].startswith(namespace)`；发布者命名空间却硬编码成 `== "com.example"`，来源硬编码成 `registry.modelcontextprotocol.io`。参数只被部分使用，换一个组织就永远无法准入。修复：从 `namespace` 推导期望的发布者命名空间（`namespace.rstrip("/")`），或把期望值作为参数传入；记录名的命名空间部分应与 `publisher.namespace` 精确相等，而不仅是前缀匹配。
2. 讲义清单与当前记录对照：

| 讲义要求记录 | 当前 `VERIFIED_ADMISSION_STATE` |
|-------------|-------------------------------|
| 精确的注册表与记录 ID | 有（`provenance.source`、`recordId`），但函数**没有校验** `recordId` 与 `name@version` 一致 |
| 已验证的发布者命名空间或域名证据 | 有 `publisher.namespace/status`，没有证据本身 |
| 允许的传输与端点 | 没有端点；只在 `server.json` 中要求 `stdio` |
| 版本 pin 或批准的升级策略 | 只做了 `version == registryVersion` 相等比较 |
| 制品或 descriptor 摘要 | 没有（descriptor pin 在 `Gateway.pins` 中单独计算，未与准入记录关联） |
| 授权 issuer 与 resource | 没有 |
| 审批人、审批时间、过期时间 | 只有 `reviewedBy`，没有时间与过期 |

   讲义也明确说本节只实现"gateway seam"，完整的供应链控制面在第 30 节。
3. 不能直接做到：函数要求 `provenance.source == "registry.modelcontextprotocol.io"`，并且要求 `server.json` 形状与 `stdio` 包。讲义："Private servers can be admitted through the same evidence schema even when they never appear in a public registry." 应允许来源是"内部审查"并改为校验证据字段齐全，而不是写死公共注册表。

### Q12 — 参考答案

已逐一实际运行验证：

| 调用 | 结果 | 说明 |
|------|------|------|
| 1. 未知 bearer | `(401, -32001 "Unauthenticated")` | 带原始 id |
| 2. 未知 bearer + 头部不一致 | `(401, -32001)` | 认证先于线协议校验 |
| 3. bob 调 `notes.create` | `(403, -32003 "Forbidden")`，`data.tool`，审计 `deny` | `-32003` 被特判为 403 |
| 4. `tasks/cancel` | `(404, -32601)` | 头部路由键 `Mcp-Name: t1` 校验通过，但网关未实现 tasks 方法 |
| 5. listen + 只接受 JSON | `(406, -32602 "subscriptions/listen requires an SSE response")` | 用子串判断 `Accept` 是否含 `text/event-stream` |
| 6. `arguments="DROP"` | `(200, ...)` | 网关与后端都**不校验参数类型**，字符串被原样转发——违背讲义"Authorize ... arguments"与第 15 节"Validated arguments" |
| 7. 合法参数的 notification | `(202, None)`，`forwarded_request_ids == ['gw-1']`，审计 `allow` | 调用被**真正转发执行**，但客户端拿不到结果 |

补充：`subscriptions/listen` 的 `notifications` 若是列表会得到 `(400, -32602 "notifications must be an object")`；`toolsListChanged: "yes"`（非 `True`）不会被确认。

### Q13 — 参考回答要点

- **定义**：位于客户端与多个后端 MCP 服务端之间的策略与路由服务（讲义 Key Terms："Policy and routing server between clients and backend MCP servers"），对外一个端点。
- **为什么需要**：回答"哪些服务端被允许、谁能看到/调用哪个工具、同名冲突怎么办、descriptor 变化如何审查、限流与审计在哪做、任意实例能否处理下一个请求"。
- **七步**：
  1. 从传输授权中认证 principal；
  2. 校验 `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name`、`params._meta`（`-32020` 先于 `-32022`）；
  3. 授权 principal、资源、方法、工具与参数；
  4. 应用 descriptor、注册表、限流与数据策略；
  5. 为选中的后端构造全新的自包含请求；
  6. 校验后端结果，返回网关结果；
  7. 记录不含秘密的审计事件。
- 加分点：说明无会话带来的好处——任意实例可处理任意请求、水平扩展无需粘性路由；负载均衡器可以只看头部做路由。

### Q14 — 参考回答要点

- **准入**：决定"哪个后端、哪个版本、哪个 descriptor 可以进入网关"，属于供应链/变更管理，变化频率低（版本发布、重新审批）。
- **运行时策略**：对每个请求基于当前事实计算允许/拒绝：principal、issuer 与资源、租户、方法与名称、规范化参数、已准入的 pin、后端健康、能力交集、数据分级、限流状态、动作绑定的批准。
- **为什么运行时是主决策**：讲义举了三个例子——注册记录仍有效但用户角色已被撤销；descriptor 仍钉住但目标参数跨了租户边界；后端仍被批准但事故策略要求隔离写操作。准入证据只是输入。
- **策略不可用时**：按操作类别预先声明失败策略。写操作与敏感读 fail closed；明确批准的公共只读路径在风险模型允许时可以使用短期的"最后已知策略"。记录做出决定的策略版本与失败路径；不以连接或会话缓存允许决定。
- 结合代码：本节网关在 `tools/call` 上漏掉了准入检查（Q9），正是"把准入当成一次性门槛、没有进入每次调用的策略输入"的反例。

### Q15 — 参考回答要点

- **凭证中介**：
  - 绑定：`外层 principal → 网关角色与策略`；`后端 issuer + resource → 后端注册与 token`；
  - 外层 token 永不转发给后端，后端 token 永不下发给客户端，也不跨 issuer/resource 复用；
  - 代表用户行动时用设计好的 token exchange 或 claims 模型保留委托关系，不用共享服务凭证冒充用户。
- **限流**：键为 principal + issuer + resource + 公开工具 + 成本类别 + 时间窗；先做便宜的校验再消耗昂贵资源；明确被拒调用计入滥用限额还是业务配额（或两者）；分布式部署时令牌桶状态放共享存储（如 Redis 的原子脚本）。
- **审计字段**：请求 ID 与 trace ID（外层与转发两跳关联，讲义练习 1）、认证后的 principal 与 issuer、公开工具与后端路由、descriptor pin 版本、策略决定与原因（及策略版本）、延迟与结果类别、MRTR 轮次或 task ID。
- **脱敏**：bearer token、授权码、refresh token、原始秘密、不必要的敏感参数（存摘要或掩码）。
- 结合代码：本节审计只有 `principal`、`tool`、`decision` 三个字段，转发 ID `gw-N` 只存在网关对象里而没有进审计事件。

### Q16 — 参考回答要点

- **发现**：网关定期对每个后端做 `server/discover`（有界探测），对客户端只宣告能端到端兑现的能力交集；按 principal/租户可能不同，所以网关 discovery 用 `private`。
- **命名空间**：`<后端>.<工具>` 公开名，保存到后端的映射；跨租户的同名后端用 `<租户>.<后端>.<工具>` 或按租户独立的网关资源；公开名变更走迁移流程（审批、审计、缓存失效）。
- **准入与 pin**：每个后端有准入记录（注册表记录 ID、发布者证据、端点、版本 pin、descriptor 摘要、issuer/resource、审批人与过期）；list 与 call 共用一个路由函数（Q9）。
- **缓存**：`tools/list` `private`，键含租户与 principal 的授权上下文，`ttlMs` 有界；descriptor 变化或准入变化时主动失效。
- **订阅**：客户端 POST `subscriptions/listen`；网关只确认它能从后端可靠转发的类型；后端工具变化 → 网关重新校验 pin → 只向有可见性变化的订阅者发送 `toolsListChanged`；断线后客户端重新订阅并刷新列表，无重放。
- **Tasks**：仅当网关能端到端保持生命周期时才宣告 `io.modelcontextprotocol/tasks`；后端返回 `resultType: task` 后，网关把"taskId → principal + 后端路由"写入持久存储；`tasks/get|update|cancel` 用 `taskId` 作 `Mcp-Name`，先校验调用者是否就是创建者；不实现 `tasks/list`、`tasks/result`。
- **legacy adapter**：对 3 个 `2025-11-25` 后端显式识别版本，把 `initialize`、传输会话、GET 流、`resources/subscribe`、旧任务词汇全部封装在适配器里；会话 ID 绝不进入现代路由与授权；优先有界探测 + 显式回退策略，而不是静默降级（讲义练习 5）。

### Q17 — 参考回答要点

- **确定性排序**：同样的输入必须得到同样的列表，才能稳定缓存、做 diff 审计、让模型看到一致的工具顺序（顺序变化会影响模型选择，也会让 `listChanged` 误报）。
- **命名空间**：两个后端都有 `search` 时，"取第一个/最后一个"会让路由依赖发现顺序，攻击者只要让自己的后端先被发现就能劫持调用（第 15 节的 shadowing）。讲义："Never choose the first or last collision."
- **改公开名是迁移**："A public name is part of the approval and audit contract"——审批记录、pin 键、RBAC 规则、限流键、审计查询、客户端保存的工具引用都以公开名为键，改名等于创造了一个"未批准的新工具"，需要重新审批并迁移所有引用。
- **能力交集**：网关宣告的能力是对客户端的承诺。后端支持但网关无法正确中介的特性（如需要回传 elicitation）宣告出去就是虚假承诺，还可能绕过网关策略；网关支持但没有任何后端路径的特性宣告了也无用。讲义："Advertise only the capability intersection the gateway can honor end to end."
- 加分点：namespaced descriptor 不能丢掉 `inputSchema` 等必填字段（测试 `test_tools_list_is_principal_filtered_and_sorted` 断言每个工具都是对象根 schema）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：descriptor pin、shadowing、MRTR `requestState` 的保护。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../16-mcp-security-oauth-2-1/docs/zh.md)：issuer/resource 绑定与"禁止 token passthrough"。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：完整的 HTTP 适配器、请求范围 SSE。
- [阶段 13 · 13 MCP Tasks 扩展](../../13-mcp-async-tasks/docs/zh.md)：`tasks/get`、`tasks/update`、`tasks/cancel` 的语义。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：资源订阅迁移到 `subscriptions/listen` 的背景。

### 本节被哪些后续内容用到
- [阶段 13 · 18 生产环境中的 MCP 认证](../../18-mcp-auth-production/docs/zh.md)：网关入口认证与后端凭证中介的生产实现。
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../20-opentelemetry-genai/docs/zh.md)：讲义练习 1 的追踪上下文传播。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把网关、注册表、后端组合成完整生态。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：讲义点名的完整准入控制面。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：legacy adapter 与版本门控的运维。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：模型侧网关的同类问题（路由、限流、审计）。
- [阶段 19 · 13 综合项目 13：带注册表与治理机制的 Stateless MCP 服务端](../../../19-capstone-projects/13-mcp-server-with-registry/docs/zh.md)：在综合项目中实现注册表治理。

### 延伸关键词
`MCP gateway` · `admission record` · `runtime policy / PDP` · `fail closed` · `server.json` · `publisher verification` · `provenance` · `descriptor pin` · `qualified tool name` · `cacheScope: private` · `token bucket` · `subscriptions/listen` · `request-scoped SSE` · `Tasks extension` · `legacy adapter` · `capability intersection` · `trace context`
