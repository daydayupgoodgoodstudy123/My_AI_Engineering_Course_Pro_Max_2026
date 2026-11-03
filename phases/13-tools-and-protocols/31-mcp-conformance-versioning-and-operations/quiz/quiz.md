# 测验 · MCP 一致性工程：版本管理、证据与运维（MCP Conformance Engineering: Versioning, Evidence, and Operations）

> **阶段 13 · 工具与协议 · 第 31 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 一致性是可观测的不变量 | SDK 调通一次 `tools/list` 不等于一致；要在线路（wire）上、版本边界上、经过中间层时、回滚时都能证明 |
| 2 | 两个版本时代（era） | 现代 `2026-07-28`：每个请求自带 `params._meta["io.modelcontextprotocol/protocolVersion"]` 和 `.../clientCapabilities`（必须是精确的命名空间键），成功结果必须有 `resultType`；到 `2025-11-25` 为止是 `initialize` 握手的旧时代，缺 `resultType` 只在**已选定旧时代**后才被视为 complete |
| 3 | strict 与 fallback | 成功的 `server/discover` 或已识别的现代错误（`-32020/-32021/-32022`）证明是现代；fallback 只在"现代探测无结论（超时/空/断开/无法识别）+ 端点在允许名单 + 观察到合法的旧版 `initialize` 结果"时才选旧时代；**收到现代错误绝不降级** |
| 4 | Golden 与 negative transcript | 记录跨越边界的原始字节而不只是 SDK 调用；负例必须断言拒绝边界和稳定错误码；header 不匹配用例必须拿到服务端真实的 HTTP 400 + JSON-RPC `-32020` 响应 |
| 5 | Header 与 body 必须一致 | 顺序：先校验信封和元数据类型 → 比较 `MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` → 相等后才判断版本是否支持；从而区分 `-32020`（不匹配）与 `-32022`（不支持）；header 名大小写不敏感、值大小写敏感；不安全的 `Mcp-Name` 要用 `=?base64?...?=` 哨兵编码 |
| 6 | 未知字段 ≠ 未知 resultType | 附加的未知字段（如 `futureHint`）应保留或有意忽略；未知或未声明能力的 `resultType` 是生命周期判别符，必须拒绝；`task` 只在声明 Tasks 扩展能力后合法 |
| 7 | 方法级载荷校验 | `tools/list` 需要名字唯一、有描述、`inputSchema` 根为 object；`task` 需要 taskId、已知 status、时间戳、`ttlMs`；`completion/complete` 需要 ≤100 个字符串值、`total ≥ 值个数`、`hasMore` 为布尔 |
| 8 | 通知不变量 | 没有 `id` 的通知不能得到任何 JSON-RPC 响应；HTTP 上期望 `202` + 空 body；要测最终出口字节，而不只是 handler 返回值 |
| 9 | SDK 差分与代理证据 | 对比原始结果与 SDK 归一化视图，允许去掉 `resultType`、`_meta`、`ttlMs`、`cacheScope` 等簿记字段，报告被丢弃/改变的语义字段；代理记录 ingress / origin / egress 三视图，检测错误被折叠成 500、body 被改写 |
| 10 | 脱敏、健康窗口与回滚证据 | 在序列化/哈希/日志前脱敏（键名 casefold + 去分隔符后匹配黑名单）；发布门要求非空的 transcript / SDK / 代理证据、健康窗口、以及经可信签名者 HMAC 认证、带三个 SHA-256 pin 的回滚目标；动作是 promote / rollback / hold |

### 核心技能（能动手做到）

- [ ] 给定 header 和 JSON-RPC body，推断 `validate_request` 抛出的错误码（`-32600/-32602/-32020/-32021/-32022`）
- [ ] 给定探测结果和策略，推断 `select_era` 返回 modern、legacy 还是失败关闭
- [ ] 为一条新的协议规则写出一对 golden / negative transcript，并说明负例要断言什么
- [ ] 解释 `Mcp-Name` 的 Base64 哨兵编码规则，并能找出编码/解码不对称的边界情况
- [ ] 用 `compare_sdk_view` 和 `inspect_proxy` 生成差分证据，并说出它们**检测不到**的情况
- [ ] 推演 `ReleaseGate.evaluate` 在不同证据组合下给出 promote / rollback / hold 的逻辑

---

## 二、基础自测（选择题）

**Q1.** 对 `{"tools": []}`（没有 `resultType`）分别调用 `validate_result(..., "legacy")` 和 `validate_result(..., "modern")`，结果是：

- A. legacy 返回 `semanticType="complete"` 且 `inferred=True`；modern 抛出 `ProtocolViolation`
- B. 两者都返回 `semanticType="complete"`
- C. 两者都抛出 `ProtocolViolation`
- D. legacy 抛错；modern 自动补上 `resultType="complete"`

**Q2.** fallback 策略的客户端发出现代探测，收到 JSON-RPC 错误 `-32021`（缺少能力声明）。`select_era` 返回：

- A. `"legacy"`，因为现代请求失败了
- B. 抛出 `ProtocolViolation`，因为没有旧版证据
- C. `"modern"`，因为已识别的现代错误本身证明对方是现代实现
- D. 先返回 `"legacy"`，旧版失败后再回到 `"modern"`

**Q3.** 一个现代请求的 body 中 `protocolVersion` 是 `"2027-01-01"`，而 `MCP-Protocol-Version` header 是 `"2026-07-28"`，其余都正确。`validate_request` 抛出的错误码是：

- A. `-32022`（不支持的版本）
- B. `-32602`（参数无效）
- C. `-32021`（缺少能力）
- D. `-32020`（header 与 body 不匹配）

**Q4.** 在现代时代、未声明任何扩展能力时，下列哪个结果会被 `validate_result` **接受**？

- A. `{"resultType": "future_mode", "tools": []}`
- B. `{"resultType": "complete", "tools": [], "futureHint": true}`
- C. `{"resultType": "task", "taskId": "t-1"}`
- D. `{"tools": []}`

**Q5.** 对一个现代 HTTP 通知（没有 `id`），本节 harness 认为正确的服务端出口是：

- A. HTTP 200 + `{"jsonrpc":"2.0","result":null}`
- B. HTTP 200 + `{"jsonrpc":"2.0","id":null,"result":{}}`
- C. HTTP 202 + 空 body
- D. HTTP 204 + `{"jsonrpc":"2.0","error":{"code":-32600}}`

**Q6.** 运行 `main.py`，原始结果为 `{"resultType":"complete","tools":[],"futureHint":{"preserve":true},"_meta":{"trace":"trace-42"}}`，SDK 视图为 `{"tools": []}`。`compare_sdk_view` 报告的 `droppedFields` 是：

- A. `["futureHint"]`
- B. `["_meta", "futureHint", "resultType"]`
- C. `[]`，因为 SDK 本来就可以去掉未知字段
- D. `["_meta", "futureHint"]`

**Q7.** 用 `inspect_proxy` 检查一次交换：origin 返回 HTTP 400 + JSON-RPC `-32020` 错误 body，egress 返回 **HTTP 502** + **与 origin 完全相同**的 body。结果是：

- A. `passed=False`，issues 含 "proxy collapsed a protocol error into HTTP 500"
- B. `passed=False`，issues 含 "proxy changed the origin JSON-RPC body"
- C. 抛出 `ProtocolViolation`
- D. `passed=True`，issues 为空——这是检查规则的一个盲区

**Q8.** 某候选版本的 transcript、SDK 差分、代理证据、健康窗口全部通过，但回滚证据为 `{}`。`ReleaseGate.evaluate` 的 `action` 是：

- A. `"promote"`，因为候选本身没有问题
- B. `"hold"`，因为没有经过验证的健康回滚目标
- C. `"rollback"`
- D. 抛出异常

---

## 三、动手 / 代码题

**Q9.** 讲义列出的 golden transcript 包括"legacy result without `resultType`, but only in the selected legacy era"，但 `transcript_suite()` 里没有这一条。请补上它并运行：

```python
t = Transcript(
    "golden-legacy-list", "legacy", {},
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    200, {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
)
print(run_transcript(t))
```

1. 这条用例能通过吗？`detail` 是什么？
2. 找出根因（提示：对比 `validate_response` 与 `compare_sdk_view` 调用 `validate_method_result` 的方式）。
3. 给出修复。

**Q10.** 阅读 `encode_header_value` 与 `decode_header_value`：

```python
def encode_header_value(value: str) -> str:
    safe = all(0x20 <= ord(character) <= 0x7E for character in value)
    sentinel = value.startswith("=?base64?") and value.endswith("?=")
    if safe and value == value.strip() and not sentinel:
        return value
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"=?base64?{encoded}?="

def decode_header_value(value: str) -> str:
    starts = value.startswith("=?base64?")
    ends = value.endswith("?=")
    if starts or ends:
        if not (starts and ends):
            raise ProtocolViolation("malformed Base64 MCP header sentinel", -32020)
        ...
```

1. 写出下列值 `encode` 后再 `decode` 的结果：`"inventory_get"`、`" x "`、`"résumé"`、`"what?="`、`"=?base64?abc"`。
2. 哪些值无法往返？为什么？这在真实系统里会造成什么后果？
3. 修复 `encode_header_value`。

**Q11.** `ReleaseGate` 的几个"放水"问题。已实际运行验证以下三种情况都会得到 `promote`（回滚证据有效、SDK 与代理证据正常）：

- (a) `transcripts` 只有 1 条通过的 golden 用例；
- (b) 健康窗口为 `{"sampleCount": 1, "errorRate": 0.9, "maxErrorRate": 1.0, "p95Ms": 9999, "maxP95Ms": 10000}`；
- (c) 健康窗口中 `errorRate` 为 `float("nan")`。

请逐一解释原因，并写一个更严格的 `evaluate_health_strict(health, policy)` 和"必需用例集合"检查。

**Q12.** 负例的精确性。

1. 把 `negative-malformed-tools-list` 的响应换成 `{"jsonrpc":"2.0","id":10,"result":{"tools":[]}}`（缺陷从"缺 inputSchema"变成"缺 resultType"），这条用例还能通过吗？为什么？这违背了讲义的哪句话？
2. 本套件 15 条用例中有多少条负例？其中多少条期望的是同一个错误码？这种设计的风险是什么？
3. 提出一种改进，让负例能证明"在**正确的规则**上被拒绝"。

---

## 四、面试高频题

**Q13.**（基础必考）你的 MCP 客户端通过 SDK 调用 `tools/list` 成功了，集成测试是绿的。为什么这还不能证明协议一致？你会补哪些证据？

**Q14.**（原理深挖）解释 MCP 版本时代的 strict 与 fallback 策略。为什么"收到任何错误就降级到旧协议"是危险的？怎样防止降级攻击？

**Q15.**（原理深挖）前向兼容里，"未知字段"和"未知 `resultType`"为什么要区别对待？透明代理和应用客户端对未知字段的处理有什么不同？

**Q16.**（工程实践）在 Streamable HTTP 上，网关依据 `Mcp-Method`、`Mcp-Name` 等镜像 header 做路由和鉴权。你如何保证网关授权的工具和服务端实际执行的工具是同一个？校验顺序、编码与错误码怎么设计？

**Q17.**（场景设计）请设计一个 MCP 服务端/网关版本的发布门（release gate）：需要哪些证据、如何决定 promote / rollback / hold，回滚目标需要满足什么条件，证据如何脱敏和防伪？

---

## 五、参考答案与解析

### Q1 — 答案：A

```python
    if era == "legacy":
        if result_type is None:
            return {"semanticType": "complete", "wire": preserved, "inferred": True}
    elif era == "modern":
        if result_type is None:
            raise ProtocolViolation("modern result is missing resultType")
```

讲义 Lab A 原样演示了这一点。两个分支不能合并成一个"宽松验证器"——讲义："The separation prevents a malformed modern peer from being rewarded with weaker validation."

- B 错：现代分支缺判别符是无效的。
- C 错：旧时代允许推断。
- D 错：harness 不会替对方"补字段"，那恰恰是讲义失败模式表第一行批评的"SDK synthesizes a missing discriminator"。

### Q2 — 答案：C

```python
    if kind == "jsonrpc_error" and observation.get("code") in MODERN_ERROR_CODES:
        return "modern"
```

已识别的现代错误说明对方懂现代协议，只是请求有问题，应该修正请求或停止。讲义："Never downgrade because the server returned `-32020`, `-32021`, or `-32022`." 降级会掩盖 header 不匹配、缺能力声明或版本不支持这些真实问题。测试 `test_recognized_modern_error_never_triggers_legacy_fallback` 断言返回 `"modern"`。

### Q3 — 答案：D

`validate_request` 先构造 `mirrored = {"mcp-protocol-version": protocol_version, ...}`，逐个与 header 比较，不相等即抛 `-32020`；**只有在比较全部通过之后**才检查 `protocol_version != MODERN_VERSION` 并抛 `-32022`。已实际运行验证：body 2027 + header 2026 → `-32020`；body 和 header 都改成 2027 → `-32022`。这个顺序让"不一致"（完整性问题）和"不支持"（能力问题）可区分。

- A：只有两者一致且都为 2027 时才是 `-32022`。
- B：`-32602` 用于 `_meta` 缺失或 protocolVersion 不是字符串。
- C：`-32021` 用于缺 `clientCapabilities`。

### Q4 — 答案：B

附加的未知字段 `futureHint` 被保留在 `wire` 中，`resultType="complete"` 是核心类型（讲义 Lab B）。

- A 错：`future_mode` 不在允许集合中，"unknown or unadvertised resultType"。
- C 错：`task` 需要声明 `io.modelcontextprotocol/tasks` 能力（测试 `test_extension_result_type_requires_advertised_capability`）。
- D 错：现代时代缺 `resultType`。

### Q5 — 答案：C

```python
def notification_http_outcome(request):
    if "id" in request:
        raise ValueError("request has an id and is not a notification")
    return 202, None
```

`run_transcript` 对通知比较 `(response_status, response_body) == (202, None)`，否则报 "notification received a response body"。A、B 是讲义失败模式表里的典型错误："Notification middleware emits `{result: null}`"——handler 返回 `None`，中间件却包成了成功响应。D 同样是禁止的响应。

### Q6 — 答案：A

`compare_sdk_view` 把 `{"resultType", "_meta", "ttlMs", "cacheScope"}` 视为簿记字段，先从原始结果中去掉，剩下的语义字段是 `tools` 和 `futureHint`；SDK 视图中没有 `futureHint`，于是 `droppedFields=["futureHint"]`、`semanticMatch=False`（实际输出 `"sdkDroppedFields": ["futureHint"]`）。

- B、D 错：簿记字段允许被 SDK 去掉。
- C 错：讲义 "Do not assume every difference is an SDK bug. The point is to make the transformation visible." 差异必须被报告，再由发布策略决定是否接受。

### Q7 — 答案：D

```python
    if (origin.get("status") in {400, 404} and isinstance(origin_body, dict)
            and "error" in origin_body and egress.get("status") == 500):
        issues.append("proxy collapsed a protocol error into HTTP 500")
    if origin.get("body") != egress.get("body"):
        issues.append("proxy changed the origin JSON-RPC body")
```

折叠检测只认 egress 状态**恰好是 500**；body 相同又不触发第二条。已实际运行验证：400→502、400→200（body 不变）都得到 `passed=True`、issues 为空，只有 400→500 被发现。更稳妥的规则是"egress 状态必须等于 origin 状态"（除非策略明确允许某种映射）。

### Q8 — 答案：B

```python
        rollback_ready = rollback_evidence_ready(rollback, self.trusted_rollback_signers)
        if not rollback_ready:
            reasons.append("no verified healthy rollback target")
        if not reasons:      action = "promote"
        elif rollback_ready: action = "rollback"
        else:                action = "hold"
```

缺回滚证据本身就是一个 reason，所以不能 promote；又因为回滚不可用，只能 hold。讲义："Require that rollback target to be verified and healthy before promotion, not only after the candidate fails. A successful release without a usable recovery path is not production-ready." 测试 `test_healthy_candidate_holds_without_verified_rollback_target` 正是此场景。

### Q9 — 参考答案

1. **不能通过**。已实际运行：`passed=False`，`detail='rejected with -32600: tools/list must return a complete result'`。
2. 根因：`validate_response` 先调用 `validate_result(response["result"], era, capabilities)`，它在旧时代推断出 `semanticType="complete"`，但**返回值被丢弃了**；随后 `validate_method_result(request["method"], response["result"])` 读取的是**原始结果**里的 `resultType`，即 `None`，于是 `tools/list` 分支判定 "must return a complete result"。而 `compare_sdk_view` 的写法是对的：

```python
    validated = validate_result(raw_result, era, capabilities)
    method_result = dict(validated["wire"])
    method_result["resultType"] = validated["semanticType"]
    validate_method_result(method, method_result)
```

   所以测试 `test_sdk_differential_preserves_legacy_complete_inference` 能通过，但同样的旧版结果走 `run_transcript` 就失败了——这正是"套件里缺少旧版 golden 用例"所掩盖的 bug。`completion/complete` 在旧时代也会因同样原因失败。
3. 修复（已运行验证：旧版用例通过，原 15 条仍全部通过）：

```python
    if has_result:
        if status != 200:
            raise ProtocolViolation("successful JSON-RPC result requires HTTP 200")
        validated = validate_result(response["result"], era, capabilities)
        method_view = dict(validated["wire"])
        method_view["resultType"] = validated["semanticType"]
        validate_method_result(request["method"], method_view)
        return
```

   并把 `golden-legacy-list` 加入 `transcript_suite()`，同时把测试里的 `assertEqual(len(results), 15)` 改为 16。

### Q10 — 参考答案

1. 已实际运行验证：

| 原值 | encode 结果 | decode 结果 |
|------|------------|------------|
| `"inventory_get"` | 原样 | `"inventory_get"` |
| `" x "` | `"=?base64?IHgg?="` | `" x "` |
| `"résumé"` | `"=?base64?csOpc3Vtw6k=?="` | `"résumé"` |
| `"what?="` | 原样 `"what?="` | **抛出** `malformed Base64 MCP header sentinel` |
| `"=?base64?abc"` | 原样 | **抛出** 同上 |

2. 不对称：`encode` 只在值**同时**以 `=?base64?` 开头**且**以 `?=` 结尾时才认为它"像哨兵"，需要编码；`decode` 却在**任一**条件成立时就进入哨兵分支，且要求两端都有。于是"只有一端像哨兵"的合法名字（如以 `?=` 结尾的工具名）被原样发送，又被接收方当作残缺哨兵拒绝，报 `-32020`。后果：这类名字的工具**永远无法被调用**，而且错误码看起来像"header 被篡改"，会误导排查。（完整哨兵值如 `"=?base64?aGk=?="` 能正确往返，因为 encode 会把它再编码一层。）
3. 修复（已运行验证三个值都能往返）：

```python
def encode_header_value(value: str) -> str:
    safe = all(0x20 <= ord(c) <= 0x7E for c in value)
    looks_like_sentinel = value.startswith("=?base64?") or value.endswith("?=")   # and → or
    if safe and value == value.strip() and not looks_like_sentinel:
        return value
    return "=?base64?" + base64.b64encode(value.encode("utf-8")).decode("ascii") + "?="
```

   原则：编码器判断"需要编码"的条件必须**覆盖**解码器"进入特殊分支"的条件。应补一个属性测试：对任意字符串 `decode(encode(s)) == s`。

### Q11 — 参考答案

- **(a) 只有 1 条用例也 promote**：门只检查"非空"和"每条都通过、digest 合法"，不检查**覆盖了哪些用例**。讲义说 "Keep the same stable case names across layers"，门应该要求一组必需的用例名（至少包括 header 不匹配、缺 resultType、通知不响应等）。
- **(b) 宽松阈值也 promote**：`evaluate_health` 的阈值 `maxErrorRate`、`maxP95Ms` **来自健康数据本身**（`health.get("maxErrorRate", 0.01)`），提供证据的一方可以顺便放宽阈值；`sampleCount` 只要求 > 0，1 个样本就够。讲义要求 "minimum sample count"，失败模式表也写了 "Canary has no samples but appears healthy → Minimum sample count is enforced"。阈值应是发布策略，不应是证据。
- **(c) NaN 也 promote**：`nan > 0.01` 为 `False`，所以 NaN 永远"不超标"。另外 `errorRate="0.5"`（字符串）会直接抛 `TypeError`，没有类型检查。

更严格的实现（已运行验证：(a)(b)(c) 都不再 promote，完整套件 + 正常健康窗口仍 promote）：

```python
import math

POLICY = {"minSamples": 500, "maxErrorRate": 0.01, "maxP95Ms": 500}   # 来自发布策略，而不是证据
REQUIRED_CASES = {c.name for c in transcript_suite()}

def evaluate_health_strict(health, policy=POLICY):
    reasons = []
    n, err, p95 = health.get("sampleCount"), health.get("errorRate"), health.get("p95Ms")
    if isinstance(n, bool) or not isinstance(n, int) or n < policy["minSamples"]:
        reasons.append(f"health window needs at least {policy['minSamples']} samples")
    for label, value, limit in (("error rate", err, policy["maxErrorRate"]),
                                ("p95 latency", p95, policy["maxP95Ms"])):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            reasons.append(f"{label} is missing or not a finite number")
        elif value > limit:
            reasons.append(f"{label} exceeds the release threshold")
    return not reasons, reasons

def missing_required_cases(transcripts):
    passed = {c.name for c in transcripts if c.passed}
    return sorted(REQUIRED_CASES - passed)
```

再进一步：健康窗口本身也应该被认证（像回滚证据一样签名），并带观测起止时间；回滚证据的 HMAC 也没有时间戳或有效期，一份很久以前的 "healthy: true" 证明可以被无限期重放——应在载荷里加入观测时间并设置最大有效期。

### Q12 — 参考答案

1. **还能通过**（已实际运行：`passed=True`，detail 是 "modern result is missing resultType"）。原因：`run_transcript` 只比较 `expected_error_code == error.code`，而 `validate_response` 里几乎所有失败都使用默认码 `-32600`。用例名说的是"工具列表畸形"，实际触发的却是另一条规则，用例仍是绿的。讲义："For each negative case, assert the rejection boundary and stable error code. 'The call failed' is too weak."——只断言 `-32600` 只比"失败了"强一点点。
2. 15 条用例中 4 条 golden、11 条负例；11 条负例里除 header-mismatch 期望 `-32020` 外，其余 **10 条全部期望 `-32600`**（missing-result-type、unknown-result-type、response-jsonrpc-version、response-id-mismatch、result-error-exclusivity、malformed-error、error-http-mapping、malformed-tools-list、task-required-fields、malformed-completion-result）。风险：某条规则被误删或写错时，只要同一请求恰好触发了另一条 `-32600` 规则，套件依然全绿——测试失去了"定位"能力。
3. 改进：给 `ProtocolViolation` 增加稳定的 `rule` 标识（如 `"result.missing_type"`、`"tools_list.input_schema"`、`"http.error_mapping"`），`Transcript` 增加 `expected_rule` 字段，`run_transcript` 同时比较 `code` 和 `rule`；或者至少断言 `detail` 包含预期子串。这样每条负例都证明了"在它声称测试的那条规则上被拒绝"。

### Q13 — 参考回答要点

- SDK 返回的是**归一化后的对象**，它可能替你补上缺失的 `resultType`、丢掉未知字段、吞掉错误码；它不能证明线上传了什么。
- 未被回答的问题（讲义 The Problem 一节）：请求是否带了现代的每请求元数据？`MCP-Protocol-Version`、`Mcp-Method`、`Mcp-Name` 是否与 body 一致？响应是否真的带了 `resultType`？客户端会不会保留将来的附加字段？现代错误会不会意外触发旧版握手？代理是否保留了 origin 状态码和错误？通知序列化器有没有违规输出响应？发布/回滚的理由能否在不存储密钥的情况下被证明？
- **补的证据**：原始 wire transcript（状态、header、body，SDK 解码之前）；golden + negative 用例集；版本时代选择记录；SDK 差分报告；ingress/origin/egress 三视图代理证据；脱敏后的证据摘要。
- 在四个层次运行同一套用例名：进程内适配器、真实二进制+真实传输、staging 网关、canary。
- 加分点：提到官方 MCP conformance 项目作为外部套件，但本地 transcript 仍然必要，因为它覆盖你自己的代理、SDK、认证、扩展和发布路径。

### Q14 — 参考回答要点

- **strict**：必须证明是现代实现（`server/discover` 成功或收到已识别的现代错误），否则失败；绝不降级。
- **fallback**：只做一次有界的现代探测；超时、空响应、断开、无法识别——这些只是"无结论"，**不等于**对方是旧版；只有端点被显式配置/列入允许名单，且旧版探测返回了合法的 `initialize` 结果和预期的旧版修订号，才选择旧时代。并把端点策略、无结论观测、旧版正面证据和最终选择一起记录。
- **为什么"出错就降级"危险**：
  - 现代错误（`-32020/-32021/-32022`）包含纠错信息，降级会掩盖 header 不匹配、缺能力、版本不支持等真实缺陷；
  - 攻击者、故障或过滤性代理只要**丢弃现代响应**就能迫使客户端降到更弱的旧协议（降级攻击，类似 TLS 降级）；
  - 旧时代"缺 resultType 视为 complete"的宽松规则会奖励畸形的现代对端。
- **防护**：允许名单 + 正面证据 + 记录选择；每条 transcript 旁记录所选时代。
- 加分点/追问：本节代码对 `-32601`（Method not found）这类非现代错误一律"不是安全的回退证据"（已验证），而旧版服务端对 `server/discover` 很可能就回 `-32601`。这是偏保守的选择：如何把它归类为"无结论"（`unrecognized`）需要明确的策略，而不能在代码里隐式决定。

### Q15 — 参考回答要点

- **附加未知字段**：结果对象和 `_meta` 都可以新增字段，这是前向兼容的正常方式。验证器应保留（或有意忽略）它们，除非违反保留契约。
- **未知 `resultType`**：它是**生命周期判别符**，决定客户端该"拿结果走人"（complete）、"补充输入"（input_required）还是"去轮询任务"（task）。把不认识的值当 complete 处理，意味着可能丢掉一个仍在进行的任务或一次输入请求。所以必须拒绝；扩展类型只在声明对应能力后才合法。
- **同一个响应里可能同时有"可接受的未知字段"和"不可接受的未知类型"**，两者都要测。
- **判别符只是第一层**：之后还要做方法级载荷校验（tools/list、task、completion 的字段要求），拼写正确的 `resultType` 不能让畸形载荷变得一致。
- **透明代理 vs 应用客户端**：代理应该**保留**未知字段（否则下游永远拿不到新特性）；应用客户端可以忽略，但 SDK 差分要让这个选择**显式**并写入发布策略，而不是悄悄发生。
- 加分点：本节 `compare_sdk_view` 只报告"丢弃"和"改变"，不报告 SDK **新增/合成**的字段（已验证 SDK 视图多出 `nextCursor` 也是 `semanticMatch=True`），而讲义要求记录 "fields lifted, synthesized, stripped, or changed"。

### Q16 — 参考回答要点

- **原则**：body 是协议的唯一真相；镜像 header 只用于路由/策略，二者不一致是完整性失败，不是"二选一"的提示。
- **校验顺序**：
  1. 解析并校验 JSON-RPC 信封与元数据类型（精确的命名空间键）；
  2. `MCP-Protocol-Version` vs `_meta` 中的 protocolVersion；
  3. `Mcp-Method` vs `method`；
  4. 方法有路由名时，`Mcp-Name` vs body 中的名字（本节代码依次取 `params.name`、`taskId`、`uri`）；
  5. 全部相等后，才判断版本/能力是否支持。
  这样 `-32020`（不匹配）与 `-32022`（不支持）可区分，并且网关不会"按 header 授权、origin 按 body 执行另一个工具"。
- **header 细节**：名字大小写不敏感、值大小写敏感；同名 header 冲突值直接拒绝；不安全、非 ASCII、首尾有空白的 `Mcp-Name` 必须用 `=?base64?...?=` 哨兵（UTF-8）；残缺哨兵、非法 Base64、非法 UTF-8、未编码的不安全值一律 `-32020`；编码器与解码器的判定条件必须对称（见 Q10）。
- **每一跳都校验**：网关和 origin 都做同样的比较；中间层在 HTTP 层拒绝畸形请求时可能没有 JSON-RPC body，证据里要记录拒绝来自哪一层。
- **测试**：header 不匹配的负例必须捕获服务端真实的 HTTP 400 + `-32020` 响应，而不能在本地校验器抛错后就算通过。

### Q17 — 参考回答要点

- **证据输入**：
  - 一致性：golden + negative transcript，覆盖一组固定的必需用例名，每条带脱敏证据摘要；
  - SDK 差分：每个发布的 SDK/版本各一份；
  - 代理：ingress / origin / egress 三视图，检测状态码映射、body 改写、content type、SSE、缓存头、trace 关联；
  - 健康窗口：最小样本数、最大错误率、延迟分位数、资源饱和、观测时长、与已准入基线对比——阈值来自策略而不是证据；
  - 回滚证据：确切的前一版本、准入证据摘要、制品与描述符 SHA-256 pin、当前 Registry 状态、当前健康结果、路由恢复步骤，以及可信发布控制器身份对这些字段的认证。
- **决策**：全部通过 → promote；有失败且回滚目标已验证 → rollback；有失败且回滚目标不可用 → hold（"Roll back to whatever was there" is not an operational control）；**即便候选全绿，没有可用回滚目标也要 hold**。
- **防伪与脱敏**：在序列化、哈希、日志、上传之前脱敏（键名统一 casefold 并去掉分隔符再匹配黑名单，再加方法级参数策略）；对脱敏后的证据包做哈希；回滚证明用 HMAC（演示）或生产中的 KMS / 公钥签名；比较签名用常量时间比较；证明应带时间与有效期，防止重放。
- 常见误区：用真值判断代替精确类型（`healthy: "yes"`、任意非空字符串当 digest）；"零错误"但零样本；只在候选失败后才去找回滚目标。
- 加分点：指出本节 `redact` 是**精确匹配**黑名单——`X-Auth-Token`、`idToken`、`privateKey`、`sessionToken` 都不会被脱敏，以"列表对"形式存储的 header（`[["Authorization", "Bearer ..."]]`）也会漏过（已验证），生产需要更完整的策略。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：镜像 header、请求级 SSE、通知的 HTTP 语义。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：`server/discover` 与新旧协议回退的客户端实现。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关基于 header 的路由与策略。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：回滚目标所需的准入证据、pin 与状态。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：`task` 结果类型与扩展能力协商。

### 本节被哪些后续内容用到
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把一致性 transcript 与发布门纳入综合项目的证据要求。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：健康窗口、canary 与回滚的生产流程。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：采集 ingress/origin/egress 证据与 trace 关联。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：证据脱敏、审计日志与密钥管理。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：健康窗口里的延迟分位数指标。

### 延伸关键词
`conformance suite` · `golden / negative transcript` · `protocol era` · `version negotiation` · `downgrade attack` · `resultType discriminator` · `forward compatibility` · `Mcp-Name Base64 sentinel` · `-32020 / -32021 / -32022` · `HTTP 202 notification` · `SDK differential` · `proxy evidence` · `redaction` · `HMAC attestation` · `hmac.compare_digest` · `health window` · `promote / rollback / hold`
