# 测验 · MCP Tool Contracts 与内容（MCP Tool Contracts and Content）

> **阶段 13 · 工具与协议 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五道关卡 | Discover（确定性分页列表）→ Admit（校验描述符并套用本地策略）→ Invoke（校验参数、构造传输元数据）→ Execute（执行并正确分类失败）→ Consume（使用前校验内容块与结构化输出）；准入与消费两关由宿主掌握 |
| 2 | JSON Schema 是运行时边界 | MCP `2026-07-28` 中 `inputSchema`/`outputSchema` 缺省方言为 2020-12；无参工具应写 `{"type":"object","additionalProperties":false}`，比 `{"type":"object"}` 严格 |
| 3 | 输出契约对错误结果同样生效 | 一旦发布 `outputSchema`，每个 complete 结果（包括 `isError: true`）都必须给出符合 schema 的 `structuredContent`；客户端要验证，不能信描述符 |
| 4 | `structuredContent` 可以是任意 JSON 值 | 对象、数组、字符串、数字、布尔、`null` 都可以；兼容用的序列化文本块不是校验来源 |
| 5 | 五种内容块 | `text`、`image`、`audio`（base64 + mimeType）、`resource_link`（以后再取，需重新授权）、`resource`（现在就嵌入，需现在限额） |
| 6 | `x-mcp-header` 是路由元数据 | 把参数镜像到 `Mcp-Param-{name}` 供网关路由；名称是 HTTP token、忽略大小写唯一、类型只能是 string/integer/boolean、只能位于 `inputSchema.properties` 的直接成员；绝不能镜像凭据 |
| 7 | 头部值编码 | 非空、全部为 `!`～`~` 可见 ASCII 且不以 `=?base64?` 开头才走明文；否则一律 `=?base64?{Base64UTF8}?=`；布尔小写、整数十进制且在 ±9007199254740991 内 |
| 8 | 服务端一致性闸门 | 忽略大小写找到已识别的头、解码哨兵、与 JSON body 精确比较；缺失、重复、多余、畸形、不一致都在分发前以 HTTP 400 + JSON-RPC `-32020` 拒绝；审计只记头名不记值 |
| 9 | 游标是不透明的 | 只要 `nextCursor` 存在且不为 `null` 就继续；`""` 是合法游标；不得解码、递增、比较或推断页码；非法游标返回 `-32602` |
| 10 | Completion 是授权面 + 两层错误 | 补全要套用被引用 prompt/资源的同一授权边界、最多 100 个值、限流；协议错误（未知工具、畸形请求、缺元数据、非法游标）走 JSON-RPC error，可操作的执行失败走 `isError: true` 结果 |

### 核心技能（能动手做到）

- [ ] 手写一个"只认识子集"的 JSON Schema 校验器，并说清它对未知关键字是放行还是拒绝
- [ ] 给定任意字符串，判断它作为 `Mcp-Param-*` 头值时走明文还是 base64 哨兵，并能写出编码结果
- [ ] 遍历整棵 schema 树找出所有 `x-mcp-header`，拒绝位于 `oneOf`、`items`、嵌套对象、`$defs` 或 `outputSchema` 中的注解
- [ ] 写出正确的游标循环（`is None` 判断），并加上页数上限与重复游标检测
- [ ] 区分"应返回 JSON-RPC error"与"应返回 `isError: true` 结果"的场景，并让错误结果仍满足输出 schema
- [ ] 为 `completion/complete` 设计按调用者过滤、限流、结果上限和 `hasMore` 的实现

---

## 二、基础自测（选择题）

**Q1.** 工具参数 `region` 声明了 `"x-mcp-header": "Region"`。参数值为 `"eu west"`（中间有一个空格）时，客户端应发出的头部是：

- A. `Mcp-Param-Region: eu west`
- B. `Mcp-Param-Region: eu%20west`
- C. `Mcp-Param-Region: =?base64?ZXUgd2VzdA==?=`
- D. 拒绝发送，因为头部值不能含空格

**Q2.** 某次 `tools/list` 返回 `{"tools": [...], "nextCursor": ""}`。正确的客户端行为是：

- A. 再发一次 `tools/list`，参数中带上 `"cursor": ""`
- B. 结束分页，因为空字符串表示没有下一页
- C. 把游标替换成 `"1"` 再请求，便于服务端定位页码
- D. 尝试 base64 解码该游标以了解剩余页数

**Q3.** 下面哪一处出现的 `x-mcp-header` 注解可以被准入？

- A. `inputSchema.properties.region.oneOf[0]`
- B. `inputSchema.properties.regions.items`
- C. `inputSchema.$defs.region`（由 `properties.region` 通过 `$ref` 引用）
- D. `inputSchema.properties.region`，类型为 `string`

**Q4.** 下列哪种情况应该返回 **JSON-RPC error**，而不是 `isError: true` 的工具结果？

- A. 报表数据源暂时不可用
- B. 请求的工具名不存在
- C. 日期超出了工具支持的范围
- D. 业务规则拒绝了这次操作

**Q5.** 工具 `tag_catalog` 发布了 `outputSchema: {"type": "array", "items": {"type": "string"}}`。某次执行失败，服务端想返回 `isError: true`。正确做法是：

- A. 仍需返回符合该 schema 的 `structuredContent`（例如一个数组），再加上说明错误的文本块
- B. `isError: true` 时可以省略 `structuredContent`，输出 schema 只约束成功结果
- C. 返回 `structuredContent: {"error": "..."}`，因为错误信息必须是对象
- D. 改为返回 JSON-RPC error，因为有输出 schema 的工具不能返回 `isError`

**Q6.** 关于 `resource_link` 与内嵌 `resource` 内容块，说法正确的是：

- A. `resource_link` 指向的 URI 一定出现在 `resources/list` 中
- B. 客户端拿到 `resource_link` 后可以直接读取，不需要再做授权
- C. `resource_link` 指向以后再取的数据，跟随时要重新授权；内嵌 `resource` 现在就携带数据，需现在执行大小和内容限制
- D. 内嵌 `resource` 适合大文件，因为能省一次往返

**Q7.** 参数 `shard` 声明为 `{"type": "integer", "x-mcp-header": "Shard"}`，值为 `9007199254740992`。客户端应该：

- A. 发送 `Mcp-Param-Shard: 9007199254740992`
- B. 发送 `Mcp-Param-Shard: 9.007199254740992e15`
- C. 把值四舍五入到 `9007199254740991` 后发送
- D. 拒绝：该值超出 JavaScript 安全整数范围，中间件可能会把它舍入成别的值

**Q8.** 在本节代码中，`analyst` 与 `operator` 分别以前缀 `""` 请求 `deployment_review` 的 `environment` 补全，返回值分别是：

- A. 两者都是 `["development", "production", "staging"]`
- B. analyst 为 `["development", "staging"]`，operator 为 `["development", "production", "staging"]`
- C. analyst 为 `[]`，operator 为 `["production"]`
- D. analyst 收到 JSON-RPC 错误 `-32602`，operator 收到全部值

---

## 三、动手 / 代码题

**Q9.** 讲义要求"Error results cannot omit or violate a published output schema"。阅读服务端 `tools_call` 的参数校验分支：

```python
        try:
            validate_json_schema(arguments, tool["inputSchema"])
        except ContractViolation as exc:
            return complete(
                content=[{"type": "text", "text": str(exc)}],
                isError=True,
            )
```

1. 调用 `route_report` 时漏传 `report`（`{"region": "eu"}`），服务端返回什么？本节的 `ContractClient.call` 会怎样处理这个结果？
2. 这和讲义的哪条规则冲突？对比同一函数里 `report == "unavailable"` 分支的写法，给出修复。
3. 讲义 Build It 说 "The client implements: ... argument and result validation"。`ContractClient.call` 真的在发送前校验了参数吗？

**Q10.** 讲义的生产故障表中有一行："One malformed tool breaks discovery → Reject the bad descriptor and admit valid tools independently"。`discover_tools` 的准入循环是：

```python
            for tool in result["tools"]:
                try:
                    validate_tool_descriptor(tool)
                except ContractViolation as exc:
                    self.rejections.append({"tool": tool.get("name", "<unknown>"), "reason": str(exc)})
                    continue
                self.tools[tool["name"]] = tool
```

1. 如果某个描述符的头部属性写成 `{"type": ["string", "null"], "x-mcp-header": "R"}`，或者服务端在 `tools` 数组里混进了一个字符串 `"oops"`，会发生什么？
2. 写一个 `admit(tool)` 包装函数修复它，使任何畸形描述符都被记录为拒绝，而其它工具照常准入。

**Q11.** 头部值的编码与解码：

1. 写出 `encode_parameter_header_value` 对以下输入的输出：`"eu-west"`、`"europe-λ"`、`""`、`"=?base64?SGVsbG8=?="`。
2. `decode_parameter_header_value("=?base64?=")` 返回什么？为什么这是一个解析漏洞？如何修复？
3. 部署策略 `SENSITIVE_NAMES = {"api_key", "apikey", "authorization", "password", "secret", "token"}` 用**精确匹配**。属性 `access_token`（头名 `Access-Token`）能被准入吗？改成"子串匹配"会带来什么新问题？

**Q12.** 阅读 `completion_complete`：

```python
        self.completion_calls[principal] = self.completion_calls.get(principal, 0) + 1
        if self.completion_calls[principal] > 3:
            raise McpError(-32029, "completion rate limit exceeded")
        ...
        matches = [item for item in allowed if item.startswith(prefix)]
        return complete(
            completion={"values": matches[:100], "total": len(matches), "hasMore": False}
        )
```

指出至少三处与"限流 / 结果上限"语义不符的地方，并给出修复思路（含代码）。

---

## 四、面试高频题

**Q13.**（基础必考）一次 MCP 工具调用从发现到结果被模型使用，要经过哪些校验关卡？每一关由谁负责、防的是什么？

**Q14.**（原理深挖）`x-mcp-header` 为什么存在？它带来了哪些安全与一致性风险？协议和本节代码分别用什么规则控制这些风险？

**Q15.**（工程实践）你在写一个合并多个 MCP 服务器工具的网关。描述你的"描述符准入"与"结果消费"逻辑，以及如何保证一个坏工具不拖垮整个服务器。

**Q16.**（场景设计）设计一个 `search_evidence` 工具（讲义 Practice Lab）：给出 input/output schema、内容块组合、头部路由字段、分页与授权策略，以及你会写哪些测试。

**Q17.**（追问型）为什么说"Completion is assistance, not discovery bypass"？如果补全接口没有做授权会泄露什么？生产中还要补哪些控制？

---

## 五、参考答案与解析

### Q1 — 答案：C

明文条件是"非空且每个字符都在 `!`(0x21) 到 `~`(0x7E) 之间、且不以 `=?base64?` 开头"。空格是 0x20，不在范围内，所以必须编码：`base64("eu west".encode("utf-8")) = "ZXUgd2VzdA=="`，得到 `=?base64?ZXUgd2VzdA==?=`（已用代码实际计算）。A 的原样空格在中间件中可能被修剪或规范化；B 的百分号编码不是本协议规定的格式；D 错，讲义明确要求"Encode ... spaces ... instead of rejected"。

### Q2 — 答案：A

讲义："An empty string is a valid cursor. Truthiness would stop too early." 正确判断是 `if result.get("nextCursor") is None: break`。本节服务端故意在第一页返回 `""`，demo 的游标轨迹为 `['<first>', "''"]`，说明客户端确实带着空串发了第二次请求，并拿到了 `route_report`、`tag_catalog`。C、D 违反"不透明游标"原则：客户端不得解码、递增或推断页码。

### Q3 — 答案：D

只有 `inputSchema.properties` 的**直接成员**可以携带注解，且类型须为 string/integer/boolean。代码中 `iter_header_annotation_nodes` 遍历整棵树，要求路径恰好是 `("properties", <name>)`。A、B、C 都会被拒（测试 `test_x_mcp_header_inside_one_of_is_rejected`、`..._items_...`、`..._ref_definition_...`）。讲义："Resolving a reference does not turn the referenced node into a direct top-level property."

### Q4 — 答案：B

未知工具名属于"请求无法正确分发"，返回 JSON-RPC error（代码中为 `-32602 "unknown tool"`）。A、C、D 都是"调用已到达工具、工具报告了可操作的失败"，应返回 `isError: true` 的 complete 结果，模型往往能据此修正参数或重试。讲义："Models can often repair a tool execution error. They cannot repair a server that violated its own output schema."

### Q5 — 答案：A

讲义："every complete tool result commits to returning conforming `structuredContent`, including results with `isError: true`. The error flag classifies execution outcome; it does not waive the published output contract." 测试 `test_error_result_cannot_omit_required_structured_output` 与 `test_error_result_cannot_return_nonconforming_structured_output` 分别验证了 B 与 C 的做法会被客户端拒绝。若要在 schema 内表达失败，应像 `route_report` 那样在 schema 中预留字段（如 `accepted: false`）。D 混淆了两层错误。

### Q6 — 答案：C

讲义："A resource link is not proof that the resource appears in `resources/list`"（A 错），"The client still applies its resource policy when it follows the URI"（B 错）。"Use links for large or independently changing artifacts. Use embedded resources for small evidence that must travel atomically with the result."（D 说反了）。

### Q7 — 答案：D

`JS_SAFE_INTEGER_MAX = 2**53 - 1 = 9007199254740991`。`9007199254740992` 超出范围，`_parameter_text` 抛 `ContractViolation("mirrored integer is outside the JavaScript safe range")`（测试 `test_unsafe_integer_values_are_rejected`）。讲义："Values outside that range are rejected instead of rounded by an intermediary." C 正是讲义要避免的"静默改值"；B 的科学计数法不是十进制整数表示。

### Q8 — 答案：B

`allowed` 映射：`analyst → ["development", "staging"]`，`operator → ["development", "production", "staging"]`，未知调用者 → `[]`。前缀 `""` 匹配所有允许项（已实测）。讲义："An analyst in the sample receives `development` and `staging`. Only an operator can receive `production`." 补全不会对 analyst 报错，而是**过滤**——这样不会通过错误信息暴露"production 存在"。

### Q9 — 参考答案

1. 实测服务端返回：

```json
{"resultType": "complete",
 "content": [{"type": "text", "text": "$.report: required property missing"}],
 "isError": true,
 "_meta": {...}}
```

   没有 `structuredContent`。`ContractClient.call` 调用 `validate_tool_result` 时抛出 `ContractViolation: outputSchema requires structuredContent`——客户端把这个"参数错误"当成了服务端违约，模型拿不到可修复的错误信息。
2. 冲突的规则：讲义 "Error results cannot omit or violate a published output schema"，以及 "If the tool declares an output schema, model an actionable failure inside that schema"。本节**四个工具都声明了 outputSchema**，所以参数校验失败的通用分支对每个工具都违约。`report == "unavailable"` 分支的写法是对的：`structuredContent={"region": ..., "accepted": False}` + `isError=True`。修复思路：
   - 每个工具提供一个"失败时的合规结构"工厂，例如 `tag_catalog → []`、`evidence_bundle → {"artifact": "", "blockCount": 0}`、`route_report → {"region": arguments.get("region", ""), "accepted": False}`；参数校验失败时返回它；
   - 或者在 schema 设计阶段就预留错误形态（如 `oneOf` 成功/失败两种结构，前提是校验器支持）；
   - 若参数根本无法满足 schema 中的必需字段，也可以考虑在协议层按畸形请求处理，但讲义倾向让模型能修复的错误走 `isError`。
3. **没有**。`call` 只检查工具是否已准入，就把参数原样发给服务端；参数校验只发生在服务端的 `tools_call` 中，客户端只做了**结果**校验。讲义五道关卡中 "Invoke. Validate arguments and build transport metadata" 属于客户端/宿主一侧——这是讲义描述与代码的差距。修复：在 `call` 开头加 `validate_json_schema(arguments, tool["inputSchema"])`。

### Q10 — 参考答案

1. 两种情况都会让 `discover_tools` **整体崩溃**（已实测）：
   - `{"type": ["string", "null"], ...}`：`validate_header_annotations` 中 `property_schema.get("type") not in {"string", "integer", "boolean"}` 用列表去查集合，抛 `TypeError: unhashable type: 'list'`；
   - 字符串 `"oops"`：`validate_tool_descriptor` 里 `tool.get("name")` 抛 `AttributeError`，而且 `except` 分支里的 `tool.get(...)` 也会再次失败。
   两者都不是 `ContractViolation`，`except` 接不住，异常冒泡到调用方，**所有**合法工具也都没被准入——正是讲义表格里要避免的故障。
2. 参考实现（已验证两种输入都被转换成拒绝）：

```python
def admit(tool: Any) -> None:
    if not isinstance(tool, dict):
        raise ContractViolation("descriptor must be an object")
    try:
        validate_tool_descriptor(tool)
    except ContractViolation:
        raise
    except Exception as exc:                       # 任何意外都视为畸形描述符
        raise ContractViolation(f"malformed descriptor: {type(exc).__name__}") from exc

# discover_tools 中：
for tool in result["tools"]:
    try:
        admit(tool)
    except ContractViolation as exc:
        name = tool.get("name", "<unknown>") if isinstance(tool, dict) else "<non-object>"
        self.rejections.append({"tool": str(name), "reason": str(exc)})
        continue
    self.tools[tool["name"]] = tool
```

   更根本的做法是先用 schema 校验描述符本身的形状（`name` 是字符串、`inputSchema` 是对象、`type` 是字符串等），再做语义检查。另外 `result["tools"]` 本身也应先确认是列表。

### Q11 — 参考答案

1. 实测输出：

| 输入 | 输出 | 原因 |
|------|------|------|
| `"eu-west"` | `eu-west` | 全部可见 ASCII，明文 |
| `"europe-λ"` | `=?base64?ZXVyb3BlLc67?=` | `λ` 非 ASCII（UTF-8 为 `CE BB`） |
| `""` | `=?base64??=` | 空串不满足"非空"，base64 载荷为空 |
| `"=?base64?SGVsbG8=?="` | `=?base64?PT9iYXNlNjQ/U0dWc2JHOD0/PQ==?=` | 看起来像哨兵，必须再编码一次，接收方才能还原字面文本 |

2. 返回 `""`（实测）。`"=?base64?=" `以前缀 `=?base64?` 开头、以后缀 `?=` 结尾，但两者**共用了中间的 `?`**——字符串长度 10 小于前缀 9 + 后缀 2 = 11，切片 `value[9:-2]` 得到空串，被当作合法的空载荷。空串的规范编码是 `=?base64??=`，所以这是一个"接受非规范形式"的漏洞：代码已经专门检查了 base64 的规范性（重新编码比对），却漏了哨兵外壳本身的规范性。修复：

```python
    if value.startswith(BASE64_SENTINEL_PREFIX):
        if (len(value) < len(BASE64_SENTINEL_PREFIX) + len(BASE64_SENTINEL_SUFFIX)
                or not value.endswith(BASE64_SENTINEL_SUFFIX)):
            raise ContractViolation("parameter header uses a malformed base64 sentinel")
```

3. **能被准入**（实测 `access_token`、`user_password`、`credential` 都被准入；只有属性名或头名**恰好**等于名单中的词才拒绝，`region` + 头名 `Authorization` 会被拒）。改为子串匹配（先把名字小写并把非字母数字替换为 `_`，再看是否包含 `token`、`password`、`secret`、`auth`、`credential`、`cookie`、`session` 等）能抓住这些变体，但会误伤：实测 `author_name` 因包含 `auth` 而被判为敏感。工程上的折中：
   - 子串规则只用于"拒绝镜像到头部"——误伤的代价只是这个字段不能用于路由，可以接受；
   - 更稳的做法是反过来用**白名单**：只允许明确登记过的路由字段（`region`、`tenant`、`shard`）镜像，其它一律拒绝；
   - 讲义的 `quiz.json` 也把 credential 与 PII 字段列为应拒绝对象，而代码名单里没有它们。

### Q12 — 参考答案

问题（均已实测或由代码直接可见）：

1. **不是"速率"而是"终身配额"**：计数器只增不减、没有时间窗口，同一 principal 在服务器生命周期内第 4 次调用起永远被拒。
2. **无效请求也消耗配额**：计数在校验 `ref`/`argument` 之前进行，实测连续 3 次 `unknown completion reference` 后，第 4 次直接得到 `-32029`。
3. **`hasMore` 写死为 `False`**：`values` 截断到 100 个，但匹配数超过 100 时 `hasMore` 仍是 `False`，客户端会以为已经拿全了。
4. 次要：计数器字典无界增长（每个 principal 一个键）；客户端侧没有 debounce（讲义列出的"request debouncing in the client"）。

修复示例（滑动窗口 + 先校验后计数 + 正确的 `hasMore`，已在小例子上验证：窗口内前 3 次放行、第 4 次拒绝、61 秒后恢复；150 个匹配时返回 100 个、`total=150`、`hasMore=True`）：

```python
class SlidingWindowLimiter:
    def __init__(self, limit=3, window=60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.calls: dict[str, list[float]] = {}

    def allow(self, principal: str) -> bool:
        now = self.clock()
        recent = [t for t in self.calls.get(principal, []) if now - t < self.window]
        if len(recent) >= self.limit:
            self.calls[principal] = recent
            return False
        recent.append(now)
        self.calls[principal] = recent
        return True

# completion_complete 中：先校验 ref / argument / value，再
#   if not self.limiter.allow(principal): raise McpError(-32029, "completion rate limit exceeded")
# 返回：
#   {"values": matches[:100], "total": len(matches), "hasMore": len(matches) > 100}
```

### Q13 — 参考回答要点

- **Discover**（客户端发起、服务端提供）：确定性、分页的 `tools/list`；客户端按不透明游标走完所有页，有页数上限和重复游标检测（本节 `MAX_TOOL_LIST_PAGES=100`、`seen_cursors`）。防：漏页、无限分页。
- **Admit**（宿主）：校验描述符形状、`inputSchema` 是对象 schema、`x-mcp-header` 位置/类型/唯一性/敏感字段策略；坏描述符单独拒绝，不影响其它工具。防：恶意或畸形描述符进入模型上下文。
- **Invoke**（宿主/客户端 + 传输）：按 `inputSchema` 校验参数，构造 `Mcp-Param-*` 头（编码），审计只记头名。防：错误参数、头部注入与不一致。
- **Execute**（服务端）：校验请求元数据（协议版本、能力）、HTTP 头与 body 一致性（400/-32020）、参数校验；把失败分成 JSON-RPC error 和 `isError` 结果。
- **Consume**（宿主）：校验每个内容块（类型、base64、mimeType、大小），按 `outputSchema` 校验 `structuredContent`，`resource_link` 跟随时重新授权。防：服务端违约的数据进入模型或下游代码。
- 关键原则：讲义 "A server cannot force a client to trust its annotations, schemas, or outputs."

### Q14 — 参考回答要点

- **用途**：让负载均衡、网关、策略引擎无需解析 JSON body 就能按参数路由（如按 region 选后端）。
- **风险**：
  1. 机密泄露：头部会出现在代理、WAF、trace 日志中；
  2. 不一致（解析分歧）：Unicode、空白、控制字符在中间件里被规范化或截断，网关与源站看到不同的值；
  3. 头部注入：CR/LF 进入头部；
  4. 整数精度：JavaScript 中间件把大整数舍入；
  5. 隐藏注解：放在 `oneOf`、`items`、`$ref` 里，部分客户端看不到，导致路由不一致。
- **控制**：协议层——HTTP token 名、忽略大小写唯一、仅 string/integer/boolean、仅直接顶层属性、安全整数范围、非可见 ASCII 一律 base64 哨兵编码、服务端解码后与 body 精确比较、失败 400/-32020。部署层（本节代码）——拒绝镜像敏感字段、遍历整棵 schema 树（含 `outputSchema`）、审计只记头名。
- 加分点：讲义 "Audit the header name, not its value"；本节测试 `test_encoded_values_remain_redacted_from_client_and_server_audits` 连编码后的值也不允许出现在审计里（编码不是加密）。

### Q15 — 参考回答要点

- **发现**：对每个上游服务器独立分页，记录完整的 page trace；`nextCursor is None` 才停止，设页数上限与重复检测；同名工具冲突要有命名空间策略。
- **准入**：每个描述符独立 `try` 准入，任何异常都转成拒绝记录（见 Q10），不能让一个坏工具让整个服务器不可用；准入时不信任 annotations（讲义 "Tool annotations treated as policy → Enforce authorization and approval outside annotations"）。
- **调用**：参数先按 `inputSchema` 校验；镜像头部按规范编码；凭据放在受保护的请求数据或网关自己的认证里，不镜像。
- **消费**：内容块逐个校验（类型、base64、mimeType 白名单、大小上限）；有 `outputSchema` 就强制校验 `structuredContent`（包括错误结果）；兼容文本只用于展示；`resource_link` 不自动跟随。
- **证据**：讲义 "Do not claim gateway compatibility from a successful `tools/call` alone. Capture the descriptor, page trace, admitted tool set, rejected tool set, and one validated result."
- 常见误区：用 `{"type": "object"}` 当无参工具 schema；把 `structuredContent` 当字典；用 truthiness 判断游标。

### Q16 — 参考回答要点

- **inputSchema**：

```json
{"type": "object",
 "properties": {
   "query":  {"type": "string", "minLength": 1},
   "limit":  {"type": "integer", "minimum": 1, "maximum": 50},
   "region": {"type": "string", "x-mcp-header": "Region"}},
 "required": ["query", "region"],
 "additionalProperties": false}
```

   注意本节校验器不支持 `minimum`/`maximum`（会静默忽略），所以讲义要求"`limit` is bounded by application validation"——在处理函数里再检查一次。
- **outputSchema**：`{"type": "array", "items": {"type": "object", "properties": {"uri": {"type": "string"}, "title": {"type": "string"}, "score": {"type": "number"}}, "required": ["uri", "title", "score"], "additionalProperties": false}}`。失败时返回 `[]` + `isError: true` + 说明文本，满足 schema。
- **内容块**：一个兼容文本块（JSON 序列化数组）+ 每条结果一个 `resource_link`。
- **授权**：结果在服务端按调用者过滤；补全同样过滤；客户端跟随链接时再次授权；无权访问的 URI 不出现在任何输出中。
- **测试**：分数为字符串的非合规输出被拒；`x-mcp-header` 放在 `items` 中被拒；两页列表（含 `""` 游标）；头部值覆盖可见 ASCII、Unicode、控制字符、首尾空白、哨兵样文本、安全整数上下界；HTTP 夹具接受大小写不同的头名、拒绝缺失或不一致值（400/-32020）；无权调用者看不到受限 URI。

### Q17 — 参考回答要点

- **原因**：`completion/complete` 给 prompt 参数和资源模板参数提供建议，往往直接查询后端名字空间；如果不按引用对象的授权边界过滤，调用者无需拥有 `resources/list` 或 prompt 权限就能**枚举**租户名、环境名、项目名。讲义："it can leak names that ordinary list methods protect."
- **泄露示例**：本节中 analyst 若能补全出 `production`，就知道了生产环境的存在和名字；多租户系统中可能泄露其它客户名称。
- **控制**（讲义列表）：输入校验、按调用者过滤、客户端 debounce、服务端限流、结果数上限（≤100，`total` + `hasMore`）、日志不记录敏感建议值。
- **实现细节**：对无权调用者返回过滤后的结果（甚至空列表）而不是带信息的错误；限流按时间窗口、先校验后计数（见 Q12）。
- 加分点：补全结果只是"建议"，最终提交的参数仍要在调用时再做一次授权。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：本节服务端的 `dispatch` 结构与无状态请求元数据。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：Streamable HTTP 的完整校验顺序，本节的参数头一致性只是其中一环。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：`resource_link`、内嵌资源与 prompt 引用（补全的对象）。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../04-structured-output/docs/zh.md)：JSON Schema 基础。
- [阶段 13 · 05 工具 Schema 设计](../../05-tool-schema-design/docs/zh.md)：参数命名、描述与约束。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：JSON-RPC 错误与通知。

### 本节被哪些后续内容用到
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：在契约之上处理超时、取消与背压。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：描述符准入扩展到注册表与漂移检测。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：把本节的契约检查变成一致性测试。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关如何利用路由元数据与准入结果。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../../19-capstone-projects/21-tool-registry-schema-validation/docs/zh.md)：综合项目中的工具注册与 schema 校验。

### 延伸关键词
`JSON Schema 2020-12` · `structuredContent` · `outputSchema` · `content blocks` · `resource_link` · `x-mcp-header` · `Mcp-Param-*` · `base64 sentinel` · `JavaScript safe integer` · `opaque cursor` · `completion/complete` · `JSON-RPC -32602 / -32020` · `HTTP header injection` · `parser differential`
