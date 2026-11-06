# 测验 · 综合项目 13：带注册表与治理机制的 Stateless MCP 服务端（Capstone 13: Stateless MCP Server with Registry and Governance）

> **阶段 19 · 综合项目 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/tests/test_main.py](../code/tests/test_main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 六个必须对齐的"真相" | `server.json`（在哪装/连）、`server/discover`（进程现在支持什么）、每个请求的协议版本与能力、授权（issuer/resource/scope）、策略（这次动作能不能做）、审计（越过边界的记录且不泄密） |
| 2 | 两层发现 | Publication 层 = `server.json` + Registry API；Runtime 层 = `server/discover`。二者回答不同的问题，Registry schema 日期（`2025-12-11`）与 MCP 协议版本（`2026-07-28`）彼此独立 |
| 3 | 反向 DNS 命名空间 | 验证了 `example.com` 的发布者只能用 `com.example/*` 或其子命名空间（如 `com.example.team/*`）；schema 合法不等于拥有命名空间 |
| 4 | Stateless 请求信封 | 讲义：`2026-07-28` 去掉了 `initialize`、`notifications/initialized` 与 `Mcp-Session-Id`；每个请求在 `params._meta` 里携带 `protocolVersion`、`clientCapabilities`（及可选 `clientInfo`） |
| 5 | 结果信封与错误码 | 结果带 `resultType: "complete"` 和 `_meta.io.modelcontextprotocol/serverInfo`；版本缺失/非字符串 → `-32602`；字符串但不支持 → `-32022` 且 data 恰为 `{"supported": [...], "requested": "..."}`；镜像 header 不一致 → `-32020` |
| 6 | 可缓存的发现 | `tools/list` 顺序稳定（代码按名字排序）、带 `ttlMs` 与 `cacheScope`；按用户授权的结果用 `private`，不能放进共享缓存 |
| 7 | Streamable HTTP | 单一 POST 端点；每个请求返回一个 JSON 或一个请求级 SSE 流；无独立 GET 流、无 session DELETE、无 `Last-Event-ID` 重放；header `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 要与 body 一致 |
| 8 | 授权 ≠ 传输元数据 | 每次调用校验 issuer、audience/resource、过期、scope，再做第二层策略决策；`readOnlyHint`/`destructiveHint` 只是给客户端的提示，不是授权控制 |
| 9 | Approval record | 绑定 actor、tool、规范化参数摘要（sorted-keys JSON 的 SHA-256）、目标服务器、过期时间；改一个参数就无法重放；它是独立证据，不是 token 里的"魔法 scope" |
| 10 | 证据包 | Wire、Proxy、Admission、Retry、Rollback 五类证据缺一不可；本地模型只证明合约逻辑，不证明 HTTP、OAuth、Registry 发布、负载均衡 |

### 核心技能（能动手做到）

- [ ] 写出一个合法的 `tools/call` 请求（HTTP header + JSON-RPC body + `_meta`），并说出每个字段的作用
- [ ] 用 `validate_meta` 的逻辑判断任意 `_meta` 应返回 `-32602`、`-32022` 还是放行
- [ ] 实现"发布元数据 vs 运行时 `serverInfo`"的漂移检查，并能构造让它失败的输入
- [ ] 按 issuer → audience → expiry → tool → scope → size → approval 的顺序推演 `policy_decide` 的拒绝原因
- [ ] 为 approval 加上"一次性使用"与跨副本共享存储，并解释为什么进程内存不行
- [ ] 读懂 21 个单元测试分别在证明哪条边界，并补写参数 schema 校验的负例测试

---

## 二、基础自测（选择题）

**Q1.** 调用 `server.discover(meta)` 时，`meta` 中**没有** `io.modelcontextprotocol/protocolVersion` 字段。按本节代码与讲义，返回的错误码是：

- A. `-32022`，data 为 `{"supported": ["2026-07-28"], "requested": null}`
- B. `-32020`
- C. `-32602`，且不带 `data`
- D. `-32000`

**Q2.** 下面哪一项是 `server/discover` 而**不是** `server.json` 负责回答的问题？

- A. 这个进程当前支持哪些协议版本、能力和扩展，以及它的 `serverInfo`
- B. 服务器的包或远程端点在哪里
- C. 服务器的名字、标题、描述和版本应如何发布到 Registry
- D. 安装时需要声明哪些环境变量输入

**Q3.** 本节代码中 `discover` 返回 `cacheScope: "public"`，而 `tools_list` 返回 `cacheScope: "private"`。讲义给出的理由最接近：

- A. `tools/list` 的结果太大，无法公共缓存
- B. `public` 只能用于 `server/discover`
- C. `private` 的 `ttlMs` 更长
- D. 工具可见性通常随用户授权而变化，按用户区分的结果不能放在共享的公共缓存后面

**Q4.** 已为参数 `{"title": "new bug"}` 签发了一条 15 分钟有效的 `ApprovalRecord`。在本节代码中，以下哪种调用会被 `dispatch` **放行**？

- A. 同一用户、同一工具、参数改为 `{"title": "new bug "}`（多一个空格）
- B. 同一用户、同一工具、同样参数，在第一次成功调用之后**再调用一次**
- C. 另一个用户 `u43` 持有合法 token，使用同一条 approval 和同样参数
- D. 同一用户，但把 approval 用在 `https://other.example.com/mcp` 服务器上

**Q5.** 发布者已验证域名 `example.com`。下列 `server.json` 的 `name` 中，哪一个能通过 `validate_publisher_namespace`？

- A. `com.example.team/incident-tools`
- B. `example.com/incident-tools`
- C. `io.example/incident-tools`
- D. `com.examplefoo/incident-tools`

**Q6.** 关于讲义描述的 stateless MCP（`2026-07-28`），说法**错误**的是：

- A. 协议版本和客户端能力是"请求事实"而不是"连接事实"
- B. 负载均衡器可以把同一客户端的连续请求发往不同副本
- C. 需要跨调用状态时，应该显式签发不透明 handle，并存放在共享持久系统中
- D. 客户端仍需先发送 `initialize`，服务器用 `Mcp-Session-Id` 记住能力协商结果

**Q7.** `tools_list` 为 `postgres.readonly` 输出 `"readOnlyHint": true`。关于这个注解，正确的理解是：

- A. 服务器会因此拒绝所有写 SQL
- B. 它是帮助客户端展示风险的提示，不是可信的授权控制；真正的约束要靠 token 校验、策略与 handler 本身
- C. 带 `readOnlyHint` 的工具可以跳过 scope 检查
- D. 它会被写入 `server.json` 供 Registry 审核

**Q8.** 以下 `version` 值中，哪一个能通过本节的 `validate_registry_document`？

- A. `^1.2`
- B. `1.x`
- C. `1.0.0-rc.1`
- D. `latest`

---

## 三、动手 / 代码题

**Q9.** 讲义说 TypeScript 模型的 `tools/call` 会"enforce the same bounded input schemas advertised by `tools/list`"。阅读 Python 的 `dispatch`：

```python
    now = time.time()
    allowed, reason = policy_decide(server, tool, token, args, now, approval)
    if not allowed:
        ...
        return error(-32000, reason)
    try:
        response = server.handlers[tool](args)
    except Exception as exc:
        ...
        return server.result(
            content=[{"type": "text", "text": str(exc)}],
            isError=True,
        )
```

1. 用合法 token 调用 `postgres.readonly`，参数分别为 `{"sql": 1, "extra": "x"}` 和 `{}`，各返回什么？审计记录的 outcome 各是什么？
2. 写一个最小的 `validate_args(schema, args) -> list[str]`（支持 `type: object/string`、`required`、`additionalProperties: false`），并说明把它插在 `dispatch` 的哪一步、返回什么形态的结果。

**Q10.** 讲义要求 approval 绑定"one-time or repeat-use policy"。

1. 用本节代码证明：同一条 approval 可以被无限次重放（只要参数不变）。
2. 设计一次性 approval：需要增加哪些字段？在"两个无状态副本 + 负载均衡"的部署下，"已使用"状态应该放在哪里？为什么不能放在进程内存？
3. `arguments_digest({"n": 1})` 与 `arguments_digest({"n": 1.0})` 相等吗？这对 approval 意味着什么？

**Q11.** `policy_decide` 的检查顺序与大小限制：

```python
    if token.issuer != server.trusted_issuer:
        return False, "token issuer is not trusted by this server"
    if token.audience != server.url:
        return False, "token audience does not match this server"
    if token.is_expired(now):
        return False, "token has expired"
    schema = server.tools.get(tool)
    if schema is None:
        return False, f"no such tool: {tool}"
    if not token.has_scope(schema.required_scope):
        return False, f"missing scope: {schema.required_scope}"
    if len(json.dumps(args)) > 8192:
        return False, "payload too large"
```

1. 参数 `{"sql": "中" * 1400}` 会被拒绝吗？`len(json.dumps(args))` 是多少？它的 UTF-8 字节数又是多少？这条限制有什么问题，应如何改？
2. 为什么先校验 issuer/audience/expiry，再查工具是否存在？如果反过来会泄露什么？
3. 讲义练习 4："为只读服务器签发的 token 拿去调用 state-changing 服务器"。按上面的顺序，拒绝原因是哪一条？对应哪个单元测试？

**Q12.** 讲义第 8 步要求审计记录 "actor, issuer, resource, tool, policy decision, request identifier, trace context, latency, and outcome"。对照 `AuditEntry`：

```python
@dataclass(frozen=True)
class AuditEntry:
    ts: float
    user: str
    issuer: str
    tool: str
    outcome: str
    args_redacted: dict
    response_redacted: dict
```

1. 缺了哪些字段？
2. `redact({"note": "mail a.b+c@x-y.co.uk ssn 123-45-6789 phone 555-123-4567"})` 的输出是什么？基于正则的脱敏有哪些局限？讲义还给出了哪种替代做法？

---

## 四、面试高频题

**Q13.**（基础必考）MCP 生态里 Registry 的 `server.json` 与运行时的 `server/discover` 分别是什么？为什么要分开？如何检测两者的漂移？

**Q14.**（原理深挖）讲义描述的 stateless MCP 去掉了 session 之后，原来放在 session 里的东西去了哪里？对水平扩展、取消、重连分别有什么影响？

**Q15.**（工程实践）一个远程 MCP 服务器收到 `tools/call`，从 HTTP 请求进来到 handler 执行，完整的校验链路是什么？哪些检查必须在 handler 之前完成？

**Q16.**（场景设计）平台需要开放一个"删除生产数据库中某表数据"的 MCP 工具，给内部 Agent 使用。你会如何设计它的发布、授权、审批和审计？

**Q17.**（追问型）`tools/list` 为什么要求"确定性顺序"？`ttlMs` 和 `cacheScope` 应该如何取值？如果工具列表按用户不同，却被标成 `public`，会出什么事？

---

## 五、参考答案与解析

### Q1 — 答案：C

`validate_meta` 中：

```python
    requested = meta.get("io.modelcontextprotocol/protocolVersion")
    if not isinstance(requested, str):
        return error(-32602, "protocolVersion must be a string")
```

缺失时 `requested` 为 `None`，不是字符串 → `-32602`（invalid params），`error()` 在 `data=None` 时不加 `data` 键。讲义："A missing or non-string protocol version is invalid params `-32602`. Error `-32022` is only for a supplied string that is unsupported"。单元测试 `test_missing_or_non_string_version_is_invalid_params` 用 `None`、整数 `20260728`、列表三种情况验证并断言没有 `data`。A 混淆了两种错误；B `-32020` 是 HTTP 镜像 header 不一致；D 是本代码用于策略拒绝的通用码。

### Q2 — 答案：A

讲义表格：Publication 层（`server.json` + Registry API）回答"这是什么服务器、包或远程端点在哪、如何配置"；Runtime 层（`server/discover`）回答"这个进程支持哪些协议版本、能力、扩展和服务器身份"。B、C、D 都属于 `server.json`（D 对应讲义"Keep secrets as declared environment-variable inputs"）。单元测试 `test_registry_document_and_runtime_discovery_remain_separate` 断言 Registry 条目里**没有** `tools`，运行时结果里**有** `capabilities`。

### Q3 — 答案：D

讲义："Per-user authorization should normally produce `cacheScope: "private"`. Do not put user-specific tool visibility behind a shared public cache." `discover` 描述的是服务器整体能力，对所有调用者一样，可以 `public`。注意：本节代码的 `tools_list` 其实返回全部工具、并未按用户过滤，`private` 体现的是"生产中工具可见性会随授权变化"这一设计意图。

### Q4 — 答案：B

`ApprovalRecord.authorize` 只检查 actor、tool、target、参数摘要和过期时间，**不记录是否已使用**。实测同一条 approval、同样参数连续调用 3 次全部成功。A：多一个空格，JSON 不同，SHA-256 不同 → "approval arguments do not match"；C：actor 不匹配 token subject → 拒绝；D：target 不匹配 → 拒绝（而且 token 的 audience 先就不匹配）。讲义要求 approval 绑定"one-time or repeat-use policy"，代码只实现了"可重复使用直到过期"这一种，见 Q10。

### Q5 — 答案：A

`reverse_dns_namespace("example.com")` 得到 `com.example`。代码判断 `namespace == expected or namespace.startswith(f"{expected}.")`，所以 `com.example.team` 是合法子命名空间（对应子域 `team.example.com`）。B 是"正序"写法，讲义："Keeping the domain labels in their ordinary order names a different namespace"；C 是另一个域名 `example.io`；D 只是字符串前缀相同，`startswith("com.example.")` 要求后面紧跟点号，所以 `com.examplefoo` 被正确拒绝（已实际验证）。

### Q6 — 答案：D

讲义："MCP revision `2026-07-28` removes protocol sessions and the `initialize` / `notifications/initialized` handshake. It also removes `Mcp-Session-Id`." 交付物 hard reject 第一条就是使用这三者的设计。A、B、C 都是讲义原意：版本和能力随每个请求携带，任意健康副本都能独立校验；跨调用状态用显式 handle（Key Terms："Explicit handle — Ordinary application data for named server-managed state, not protocol connection state"）。

### Q7 — 答案：B

讲义："Tool annotations such as `readOnlyHint` and `destructiveHint` help clients present risk. They are not trusted authorization controls." 本节 `postgres.readonly` 的 handler 根本不解析 SQL，传入 `"DROP TABLE users"` 照样返回成功（stub 实现）；真正的只读保证应来自数据库只读账号、SQL 白名单等。C 错：所有工具都检查 `required_scope`；D 错：注解出现在 `tools/list` 中，`server.json` 不含工具列表。

### Q8 — 答案：C

`VERSION_RANGE_RE = r"(?:^[~^<>=]|[*]|(?:^|\.)x(?:$|\.))"`（忽略大小写）拒绝以 `~ ^ < > =` 开头、含 `*`、或以 `x` 作为一段的版本；另外 `latest`（不区分大小写）也被拒绝。实测：`^1.2`、`1.x`、`latest` 被拒；`1.0.0-rc.1`、`v1`、`2024.01.01` 通过。规则的目的：Registry 中一个版本必须指向一个确定的发布，不能是范围或浮动标签。

### Q9 — 参考答案

1. 实测结果：
   - `{"sql": 1, "extra": "x"}`：**放行**，返回 `isError: False`、`structuredContent: {"rows": [[1]], "sql": 1}`，审计 outcome 为 `allowed`。schema 声明了 `sql` 必须是字符串且 `additionalProperties: false`，但 Python 从未校验。
   - `{}`：通过策略，handler 中 `args["sql"]` 抛 `KeyError('sql')`，返回 `isError: True`，`content` 文本为 `'sql'`（`str(KeyError)` 的结果），审计 outcome 为 `handler_error`。错误信息对调用者毫无帮助，而且 handler 已经被调用了。
2. 参考实现：

```python
def validate_args(schema: dict, args: object, path: str = "arguments") -> list[str]:
    if schema.get("type") == "object":
        if not isinstance(args, dict):
            return [f"{path} must be an object"]
        props = schema.get("properties", {})
        issues = [f"{path}.{k} is required" for k in schema.get("required", []) if k not in args]
        if schema.get("additionalProperties") is False:
            issues += [f"{path}.{k} is not allowed" for k in args if k not in props]
        for k, sub in props.items():
            if k in args:
                issues += validate_args(sub, args[k], f"{path}.{k}")
        return issues
    if schema.get("type") == "string" and not isinstance(args, str):
        return [f"{path} must be a string"]
    return []
```

   插入位置：在 `policy_decide` 放行之后、调用 handler 之前（工具存在才有 schema 可用）。返回形态参照 TS 模型的约定："invalid arguments for a known tool return a complete result with `isError: true` without invoking the executor"——即 `server.result(content=[{"type": "text", "text": "; ".join(issues)}], isError=True)`，同时审计记一条 `denied:invalid_arguments`。补测试：断言 handler 未被调用（可用 `unittest.mock` 替换 handler 并检查 `call_count == 0`）。

### Q10 — 参考答案

1. 证明（已实测）：

```python
args = {"title": "x"}
ap = main.ApprovalRecord.for_action("u", "jira.create", args, de.url, time.time() + 900)
for i in range(3):
    print(main.dispatch(de, token, "jira.create", args, main.request_meta(), [], ap)["isError"])
# False False False —— 三次都创建了 Jira issue
```

2. 一次性 approval 设计：
   - 新增字段：`approval_id`（随机不可猜的 ID）、`use_policy`（`"once"` / `"repeat"`）、可选 `max_uses`。
   - 在 handler 执行**之前**以原子操作"消费"它：例如在共享存储中 `SET approval:{id}:used 1 NX EX <ttl>`（Redis）或数据库唯一约束插入；消费失败即拒绝。
   - 不能放进程内存：两个副本之间不共享内存，负载均衡把第二次请求发到另一个副本时，那里没有"已使用"记录，approval 就能被重放。这正是讲义"stateless"原则的推论：跨调用状态必须是显式的、放在共享持久系统里。
   - 先消费再执行，如果执行失败，需要定义是否允许重试（可结合 idempotency key，见讲义 Retry 证据）。
3. 不相等（实测两个 SHA-256 不同）：`json.dumps` 把 `1` 序列化为 `1`、`1.0` 序列化为 `1.0`。sorted keys + 紧凑分隔符只规范了键顺序和空白，没有规范数字表示。若客户端在审批时与调用时使用不同的序列化（如某端把整数转成浮点），合法调用会被误拒（fail closed，安全但影响可用性）。更严格的做法是采用 RFC 8785（JCS）一类的规范化 JSON，或在 schema 层先把参数规范化为声明的类型再算摘要。

### Q11 — 参考答案

1. 会被拒绝。实测 `len(json.dumps({"sql": "中" * 1400}))` = **8411**（默认 `ensure_ascii=True`，每个汉字转义成 6 个字符 `中`），超过 8192；而实际 UTF-8 字节数只有 **4211**（`ensure_ascii=False` 时 1411 个字符）。问题：限制的是"转义后的字符数"而不是真实负载大小，中文等非 ASCII 内容的有效上限被缩小约一半，且与 HTTP 层的字节限制口径不一致。改为：

```python
size = len(json.dumps(args, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
if size > 8192: ...
```

   生产中更应该在 HTTP 入口按 `Content-Length` / 读取字节数先限流，避免先完整解析超大 JSON。
2. 先做身份与资源绑定的检查，是"fail closed + 最小信息暴露"：未认证或 token 不属于本服务器的调用者，连"工具存不存在""需要什么 scope"都不应该知道（错误信息 `missing scope: jira:write` 本身就泄露了权限模型）。实测：issuer 不可信且工具名不存在时，返回的是 `token issuer is not trusted by this server`，不会暴露工具清单。
3. 拒绝原因是第二条 `token audience does not match this server`——token 的 audience 是只读服务器 URL，而 `server.url` 是 destructive 服务器。对应单元测试 `test_token_audience_is_bound_to_one_server`，它还断言审计里留下了 1 条记录。注意这一步发生在 approval 检查之前，所以即使持有合法 approval 也没用。

### Q12 — 参考答案

1. 缺少：**resource/audience**（token 发给哪个服务器）、**结构化的 policy decision**（目前只是拼在 `outcome` 字符串 `denied:<reason>` 里）、**request identifier**（JSON-RPC id）、**trace context**（如 W3C `traceparent`）、**latency**。另外 `handler_error` 分支没有记录异常类型；`ts` 用的是 `time.time()`，无法注入时钟，测试过期逻辑只能依赖真实时间。
2. 输出（实测）：`{'note': 'mail [email] ssn [ssn] phone 555-123-4567'}`——邮箱与 SSN 被替换，电话号码没有。基于正则的局限：
   - 只覆盖预设模式，漏掉电话、地址、token、API key、内部主机名等；
   - SQL、自由文本中的敏感信息形态无穷，正则难以穷举；
   - 也可能误伤（例如把形如邮箱的非敏感字符串替换掉）；
   - 实现上先 `json.dumps` 再替换再 `json.loads`，若模式误匹配到引号或转义字符，可能产生非法 JSON。
   讲义给出的替代："Redact or digest sensitive arguments and results before persistence"——对敏感字段只存**摘要**（如 SHA-256，与 `arguments_digest` 同思路），既能比对"是否同一操作"又不暴露原文；并且"Keep the audit sink outside model-visible context"。

### Q13 — 参考回答要点

- **`server.json`**：Registry 的发布元数据，版本化 schema（讲义示例 `2025-12-11`），描述名字（反向 DNS 命名空间）、标题、描述、版本、包或远程端点（`streamable-http` / `sse` URL）、配置输入。它是"静态的、可审核的声明"。
- **`server/discover`**：运行时 RPC，返回 `supportedVersions`、`capabilities`、扩展、`serverInfo`，以及 `ttlMs`/`cacheScope`。它是"活进程此刻的事实"。
- **为什么分开**：发布记录变更走审核流程，进程能力随部署变化；把能力写进 `server.json` 会导致"列出的能力与实际不符"。交付物 hard reject："Treating `server.json` as live capability discovery"。
- **漂移检测**：先校验 `server.json`（形状 + 命名空间归属），再对发布的 remote URL 发起 `server/discover`，比较 `serverInfo.name/version` 与发布的 name/version，以及所需能力是否存在。本节 `validate_runtime_alignment` 实现了 name/version 比较；讲义练习 1 要求把"发布的 URL 改了但服务器没变"也报告出来。
- 加分点：Registry schema 版本与协议版本互相独立，不要互相"对齐日期"；私有目录的组织元数据应放在发布记录旁边，必要时用 `_meta.io.modelcontextprotocol.registry/publisher-provided`（4 KB 限制）。

### Q14 — 参考回答要点

- **协议版本与能力**：从"握手时协商一次"变成"每个请求的 `params._meta` 携带"，服务器从消息本身校验。
- **服务器身份**：每个结果的 `_meta.io.modelcontextprotocol/serverInfo`。
- **跨调用的业务状态**：不再藏在 session 里，而是显式签发不透明 handle，存在共享持久系统（数据库、Redis）中。
- **水平扩展**：任意副本可处理任意请求，不需要 sticky session；讲义第 9 步要求两个副本 + 至少 100 个并发请求证明正确性不依赖亲和性。
- **取消**：请求级 SSE 流被关闭视为取消；讲义的 Retry 证据要求证明"请求取消不会悄悄变成持久任务的取消"。
- **重连**：没有 `Last-Event-ID` 重放；断线后用新的 JSON-RPC id 重新请求，读操作可安全重试，写操作需要幂等键（讲义练习 7）。
- 常见误区：以为 stateless 就是"系统里没有任何状态"——Key Terms 明确："No protocol session; cross-call state is explicit and server-managed"。

### Q15 — 参考回答要点

1. **传输层**：校验 `Origin`、TLS、请求大小；`Accept` 头；镜像 header（`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name`）与 body 一致，否则 `-32020`，且不进入策略和工具（讲义练习 3）。
2. **协议层**：JSON-RPC 结构、`_meta` 存在、版本是字符串（否则 `-32602`）、版本受支持（否则 `-32022`）、`clientCapabilities` 是对象。
3. **认证**：Bearer token 的签名、issuer（与该资源记录的授权服务器一致）、audience/resource（本服务器）、过期。
4. **授权**：工具存在、token 有所需 scope。
5. **参数**：按 `inputSchema` 校验（本节 Python 缺失，见 Q9）、大小限制。
6. **策略**：针对具体工具和参数的第二层决策（如 OPA）；高风险动作校验 action-bound approval（一次性则原子消费）。
7. **执行**：handler；超时、取消。
8. **审计**：无论放行还是拒绝都记录，脱敏/摘要后写入模型不可见的审计汇聚点。
- 必须在 handler 之前：1～6 全部。讲义练习 4、5 都要求证明"在 handler 运行之前"失败。
- 加分点：客户端侧还要按 issuer 区分客户端凭据、发送 resource indicator、校验返回的 `iss`；优先 Client ID Metadata Documents，Dynamic Client Registration 作为兼容。

### Q16 — 参考回答要点

- **隔离发布**：把它放在独立的 state-changing 服务器上（本节的 `internal-destructive` 与 `internal-readonly` 分开），独立 URL、独立 audience、独立部署身份与凭据——讲义："Separation is useful only if credentials, policy, deployment identity, and audit controls are also separate"。
- **schema 收紧**：只接受明确的表名枚举、条件结构化描述，禁止任意 SQL；`destructiveHint: true` 让客户端显示风险，但不依赖它。
- **授权**：token 必须 audience 为该服务器、带专用 scope；短有效期。
- **审批**：人类审批生成 approval record，绑定 actor、tool、规范化参数摘要、目标环境（prod）、过期时间、**一次性**；聊天里一句"可以"不算审批（讲义："A chat message alone is not proof of approval"）。
- **执行保护**：先 dry-run 返回影响行数，审批里绑定这个预估；执行时超过阈值则中止；事务或备份快照保证可回滚。
- **审计**：记录审批 ID、请求 ID、trace、影响行数、耗时，参数做摘要。
- **证明**：负例测试——无审批、过期审批、改参数重放、错 audience token、重复使用一次性审批，全部在 handler 之前失败。

### Q17 — 参考回答要点

- **确定性顺序**：讲义："a stable tool order so identical lists can reuse prompt caches"。工具列表通常被放进模型提示词的前部，顺序一变，前缀缓存就失效，成本和延迟上升；同时也便于比较两次结果是否"字节一致"（讲义练习 2）。代码用 `sorted(..., key=lambda item: item.name)` 实现。
- **`ttlMs`**：新鲜度提示。能力很少变化的 `server/discover` 可以长（代码 1 小时），工具列表可以短一些（代码 60 秒），工具变化频繁或有 `listChanged` 通知时再相应调整。
- **`cacheScope`**：结果对所有调用者都相同才可 `public`；随用户授权变化必须 `private`。
- **错标 `public` 的后果**：共享缓存（网关、CDN、客户端共享层）可能把管理员可见的工具列表返回给普通用户，泄露高风险工具的存在与 schema；或者反过来让用户看不到自己有权使用的工具。即使调用本身仍会被授权检查拦下，信息泄露与错误路由已经发生。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：JSON-RPC 与 stateless 请求信封。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../../13-tools-and-protocols/09-mcp-transports/docs/zh.md)：POST 端点、请求级 SSE 与镜像 header。
- [阶段 13 · 16 MCP 授权：CIMD、签发者绑定、PKCE 与升级认证](../../../13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/zh.md)：issuer、audience、resource indicator。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../../13-tools-and-protocols/28-mcp-tool-contracts-and-content/docs/zh.md)：讲义指定的必修前置，工具 schema 与错误契约。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../../13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：取消、幂等、重试（Retry 证据）。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../../13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/docs/zh.md)：Admission 与 Rollback 证据。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../../13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/docs/zh.md)：Wire 与 Proxy 证据。

### 本节被哪些后续内容用到
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../../13-tools-and-protocols/17-mcp-gateways-and-registries/docs/zh.md)：网关层的准入与策略。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：补上本节 Python 缺失的参数 schema 校验。
- [阶段 19 · 22 通过换行分隔的 stdio 传输 JSON-RPC 2.0](../../22-jsonrpc-stdio-transport/docs/zh.md)：TS 模型所用的 stdio 传输。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：为审计补上 trace context 与延迟。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../15-constitutional-safety-harness/docs/zh.md)：同样的"策略 + 审计"思想用于模型输入输出。

### 延伸关键词
`server.json` · `server/discover` · `reverse-DNS namespace` · `resultType` · `-32602 / -32022 / -32020` · `ttlMs / cacheScope` · `Streamable HTTP` · `resource indicator` · `audience binding` · `action-bound approval` · `RFC 8785 JCS` · `idempotency key` · `OPA`
