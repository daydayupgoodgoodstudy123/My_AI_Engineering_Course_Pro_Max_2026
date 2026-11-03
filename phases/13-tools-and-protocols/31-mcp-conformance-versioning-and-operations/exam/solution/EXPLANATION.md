# 参考答案讲解：conformance（13/31）

计时结束后再看。参考实现在同目录的 `conformance/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修发布闸门

**现象**：解锁后第一个失败是“no credential reaches the report”，闸门的报告里能找到 Bearer token、`X-Api-Key` 的值、`access_token`、`client.secret` 和 `Set-Cookie`。闸门本身没有直接处理这些字段。

**顺着往下找**：报告里的证据来自 `ReleaseGate._transcripts`，它对每个用例调用 `redact`。`redact` 拿原始键名去查 `SECRET_KEYS`，可 `SECRET_KEYS` 里存的是规范化以后的形式，`Authorization` 和 `authorization` 对不上，`X-Api-Key` 和 `xapikey` 也对不上。`canonical_field_name` 就在旁边，写好了却没人调用。这一关想练的是：报错的位置在闸门，出 bug 的位置在两层调用之下。

**依次修四处**：

1. `redact`：先 `canonical_field_name(key)` 再查黑名单。课里说的就是这件事：camelCase、连字符、下划线、点号几种写法必须落到同一个形式上，否则一种写法能绕过另一种写法的策略。黑名单是精确匹配，`tokenCount`、`secretary`、`passwordPolicy` 都不能被删掉。
2. `evaluate_health`：缺字段时不能用会通过的默认值。每个观测值都要先确认存在、类型对（`sampleCount` 是整数，`errorRate` 和 `p95Ms` 是数字，布尔值不算），再和阈值比较；正好等于阈值算健康。只把默认值改成会失败的值，字符串 `"1200"` 还是会在比较时抛 TypeError。
3. `rollback_evidence_ready` 的两处：状态必须正好是 `active`，Registry 的状态还有 `deprecated` 和 `deleted`，只拦 `deleted` 会让已经弃用的版本当回滚目标；三个 pin 要用 `is_sha256_digest` 检查，签名对了不代表字段格式对。
4. `evaluate` 的推导式里每次都调用 `self._transcripts(cases)`，320 个用例就把整个语料脱敏 320 遍。改成先算一次 `transcripts`，再从里面取每个用例的证据求摘要。

**护栏**：常见的提速写法是直接对原始证据求摘要，或者按用例名把摘要缓存在闸门上。前者换一次凭证摘要就变，后者改了证据摘要却不变，测试分别用“换凭证”和“改库存数”两组对照抓住它们。用例摘要的定义是 `digest(redact(evidence))`，只覆盖这个用例自己的证据。

## Part 2 transcript 夹具目录

每个用例一个 JSON 文件，文件里是课里那个 fixture 的形状，再加 `capabilities` 和 `expect`：

```json
{"name": "...", "era": "modern", "capabilities": [...], "headers": {...}, "request": {...},
 "responseStatus": 200, "responseBody": {...}, "expect": null}
```

- **文件名**：名字转小写，其他字符的每一段换成一个 `-`，去掉两头的 `-`。这个 slug 是有损的，所以准确的名字存在文件里面，`names()` 读文件内容，`load` 核对文件里的名字。`../../etc/passwd` 只会变成 `etc-passwd.json`，写不到目录外面。
- **冲突**：写之前先看目标文件是否已经存着另一个名字，是就报 ValueError，原文件不动。名字精确比较，`GOLDEN-MODERN-LIST` 和 `golden-modern-list` 是两个不同的用例，共用一个文件就是冲突。
- **头名**：原样存。课里的规则是查找前先把头名归一，这是比较时的事；存储层要保住证据本身，`Mcp-Method` 和 `mcp-method` 同时出现正是“冲突的重复头”这个负例要证明的东西。
- **时代**：和每条 transcript 存在一起。读到没有 era 或 era 不是 `modern`、`legacy` 的文件就报错。课里说，不记下时代，同一个缺失字段在一次运行里看着合法，在另一次运行里就不合法。
- **往返**：frozenset 存成排序列表再读回 frozenset，None 存成 null，整数还是整数。`json.dumps` 和 `json.loads` 本身能保住 Python 的 int、float 和 Unicode，要小心的是自己加的转换。
- **易变值**：`normalize_volatile` 递归地把 `taskId`、`createdAt`、`lastUpdatedAt` 的非空字符串换成固定值，返回新对象。负例里的空字符串、数字和 null 是“畸形响应”这件事本身，替换掉负例就不再是负例。同样的行为录两次，写出来的文件逐字节相同。

## Part 3 响应一致性校验

`validate_response` 按 docstring 的顺序检查，第一条不满足的规则抛 `Violation(rule, detail)`：

```text
notification → missing-body → envelope → exclusive → error-shape → error-status
→ result-status → result-shape → missing/unknown/method resultType → 方法载荷
```

- 没有 body 指的是 `None`；`{}` 是一个 body，违反的是 envelope。布尔值不算整数，`total: true`、`ttlMs: true` 都不合法。
- 附加字段不报错，判别字段不认识就拒绝，课里两条规则分开写，就是因为同一个响应里可以同时出现可以接受的未知字段和不能接受的未知结果类型。`resultType` 先判断是不是字符串，再查集合。
- legacy 时代缺 `resultType` 时，语义类型是 complete，方法载荷用这个语义类型检查；推断出来的值不写回原始结果。课里的 `compare_sdk_view` 也是先复制一份再补上 `resultType`。
- `task` 要同时满足两件事：Tasks 能力已经协商，方法是 `tools/call`。
- 通知只有一种合法结果：HTTP 202，没有 body。中间件把 handler 返回的 None 包成 `{"jsonrpc": "2.0", "result": null}` 发出去，这在 202 下也是违规。
- `check_case` 区分三种期望：None 要求接受；整数要求一个合法的 JSON-RPC 错误并且错误码一致，所以 HTTP 500 带着 -32020 不算服务端正确拒绝；规则名要求正好违反这一条。“调用失败了”太弱，课里说负例要断言拒绝的边界和稳定的错误码。

最后一段把 Part 1–3 串起来：夹具存进目录，`run_corpus` 按名字逐个检查，结果交给闸门。

## Part 4 代理三视图 TAP

用三个字典：`pending` 按第一次出现的顺序存还没拼齐的 exchange 和它已经到的视图，`deadlines` 存截止时间，`reported` 记已经报告过的 exchange。

```python
async for event in events:
    clock = max(clock, event["at"])
    if exchange not in reported:
        views = pending.setdefault(exchange, {})
        deadlines.setdefault(exchange, at + timeout_ms)
        views.setdefault(view, event)          # 重复投递只留第一份
        if len(views) == 3:
            yield line(exchange, judge_exchange(...))
    for overdue in [x for x in pending if deadlines[x] < clock]:
        yield incomplete(overdue)
```

- 判定前先脱敏：各个采集器有的发出前已经脱敏，有的没有，统一 `redact` 之后再比较，才是同一种形式在比。
- collapse 只针对 origin 的 400 或 404 JSON-RPC 错误变成客户端的 500，这时不再另报状态变化；其他状态不一致报 STATUS_CHANGED；body 不一致另报一条。
- 时钟用事件里的捕获时间，取目前见过的最大值，测试完全确定。先应用事件再检查超时，所以 exchange 还开着时到的视图都算数。
- 每拼齐一个就 `yield`，测试数被拉取了多少个事件。计划行只能放在最后，因为在流结束之前不知道总数。

## Part 5 SDK 差分

先递归比较，得到按报告顺序排列的 dropped、synthesized、changed，再把能配对的 dropped 和 synthesized 合成 lifted：

- 对象按成员比，两边的名字合在一起排序；列表按下标比；其他值用 canonical JSON 比较，所以 `12` 和 `"12"` 不同，`true` 和 `1` 不同（Python 的 `==` 认为它们相等），列表和对象不同。
- `allowed` 的键是对象的 JSON Pointer，值是 SDK 可以从这个对象里删掉的成员。只有删除被允许，补上和修改都照常报告，所以 legacy 结果被 SDK 补上的 `resultType` 会出现在报告里。
- 路径按 RFC 6901 转义，先 `~` 后 `/`。
- 配对条件：名字相同，值相等，合成成员所在的对象是被删成员所在对象的祖先。祖先按指针加 `/` 的前缀判断，`/s` 不是 `/stats/page` 的祖先。每个成员最多参与一次配对，结果报在被删成员原来的位置。配对要在输出之前做完：新位置可能排在前面，边扫描边输出会把同一个成员既报成 synthesized 又报成 lifted。

最后一段回到闸门：课里 Lab D 说，代理修好以后 SDK 差分仍然会挡住发布，把 `futureHint` 放进 SDK 视图，结果才变成 promote。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着证据链调试，把脱敏、健康窗口和回滚证据做成发布闸门的一部分，设计一个能精确往返、能发现冲突的夹具目录，按课里的规则实现响应一致性校验，写一个处理乱序、重复和超时的流式拼接器，以及对嵌套 JSON 做带路径的差分。它不涉及请求侧的头与 body 一致性、Base64 哨兵和时代协商（06、08、09 课的题考过），不涉及真实的 HTTP 传输、代理部署和 TLS 两侧的抓包，也没有接官方的 MCP conformance 套件。课里的 Practice Lab（请求范围 SSE 的 transcript）需要另外动手做。
