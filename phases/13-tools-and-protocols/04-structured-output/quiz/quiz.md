# 测验 · Structured Output：JSON Schema、Pydantic、Zod 与约束解码（Structured Output — JSON Schema, Pydantic, Zod, Constrained Decoding）

> **阶段 13 · 工具与协议 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种获取结构化输出的方式 | prompt 要 JSON（讲义：前沿模型成功率 85%–95%）→ 生成后校验并重试（可靠但贵）→ 受约束解码（解码时屏蔽非法 token） |
| 2 | prompt JSON 的六种失败 | 缺括号、尾逗号、类型错、幻觉字段、被 token 上限截断、混入 "Here is your JSON:" 之类的散文 |
| 3 | 受约束解码 | 把 schema 变成语法/有限状态机，每一步把会违反 schema 的 token 的 logit 屏蔽掉；输出保证可解析且符合 schema |
| 4 | 三种失败模式 | parse error（非法 JSON）、schema violation（能解析但不合规）、refusal（模型拒绝）；strict 下前两种不会发生，refusal 必须作为一等结果处理 |
| 5 | JSON Schema 2020-12 常用关键字 | `type`、`properties`、`required`、`enum`、`minimum/maximum`、`minLength/maxLength/pattern`、`items`、`additionalProperties` |
| 6 | OpenAI strict 的三条额外要求 | 所有属性都列在 `required`；所有对象 `additionalProperties: false`；不能有未解析的 `$ref`；违反时请求阶段就返回 400 |
| 7 | Pydantic / Zod | 用代码类型声明 schema：Pydantic `model_json_schema()` 生成 JSON Schema、`ValidationError` 带路径；Zod 是 TypeScript 等价物 |
| 8 | 开源实现的三种技术 | 基于语法的解码（outlines、guidance、lm-format-enforcer）、与 JSON 解析器同步做 logit masking、带校验器的推测解码 |
| 9 | 重试策略 | 非 strict 时：生成 → 解析 → 校验 → 失败则带错误重试，最多 3 次；讲义：超过 3 次说明 schema 或 prompt 有问题 |
| 10 | 可靠性与模型大小解耦 | 讲义：带语法约束的 3B 模型在结构化任务上胜过只靠 prompt 的 70B 模型 |

### 核心技能（能动手做到）

- [ ] 为一个抽取任务写出 strict 兼容的 JSON Schema（enum、范围、pattern、required、`additionalProperties: false`）
- [ ] 用标准库实现一个带路径的 schema 校验器，并知道它与规范在 `pattern`、`integer`、类型数组上的差异
- [ ] 写一个"三分支"处理器：parse_error / violation / refusal / ok，并为前两者实现带错误反馈的重试
- [ ] 在 schema 校验之外加业务语义校验（如 total 是否等于明细之和），并正确处理浮点误差
- [ ] 用 Pydantic 定义同一个模型，读懂 `model_json_schema()` 的输出（`title`、`$defs`/`$ref`、`additionalProperties`）
- [ ] 解释受约束解码为什么能保证格式，但不能保证内容正确

---

## 二、基础自测（选择题）

**Q1.** 在 OpenAI strict mode（受约束解码）下，讲义列出的三种失败模式中，哪一种**仍然可能发生**、必须由你的代码处理？

- A. parse error
- B. schema violation
- C. refusal
- D. 三种都不会发生

**Q2.** 讲义说 OpenAI strict mode 在普通 JSON Schema 之上"adds three requirements"。是哪三条？

- A. 所有属性都在 `required` 中；所有对象 `additionalProperties: false`；没有未解析的 `$ref`
- B. 所有字段必须是字符串；不允许数组；不允许嵌套
- C. 必须提供 `title`；必须提供 `description`；必须提供 `examples`
- D. 必须使用 `oneOf`；必须有 discriminator；必须声明 `$schema`

**Q3.** 运行本节代码，测试 "schema violation (extra field, bad sku)" 输出的错误是：

- A. 只有 `$.line_items[0].discount: additional property not allowed`
- B. 只有 `$.line_items[0].sku: does not match pattern '^[A-Z0-9-]+$'`
- C. `$.total_usd: missing required field`
- D. `discount` 不允许的额外字段，以及 `sku` 不匹配 pattern，两条都报

**Q4.** 关于受约束解码（constrained decoding）的原理，正确的是：

- A. 先自由生成，再用正则把非法字符删掉
- B. 在每个解码步骤中，把会导致输出违反 schema 的 token 的 logit 屏蔽掉，只从合法 token 中采样
- C. 让模型生成多份候选，选出唯一能通过校验的一份
- D. 把 schema 放进 system prompt，模型自然就会遵守

**Q5.** 用本节的 `validate` 校验 `validate({"type": "integer"}, 2.0)`（`2.0` 来自 `json.loads('2.0')`），结果是：

- A. `[]`，通过
- B. `expected integer, got float`
- C. `below minimum`
- D. 抛出 `TypeError`

**Q6.** 用本节的 `validate` 校验 `sku` 字段（`"pattern": "^[A-Z0-9-]+$"`）的值 `"ABC-123\n"`（末尾带换行），结果是：

- A. 报错：不匹配 pattern
- B. 报错：`expected string`
- C. 抛出 `re.error`
- D. 通过：Python 的 `$` 可以匹配字符串末尾换行符之前的位置，`re.match` 认为匹配成功

**Q7.** 按讲义的重试策略，下列说法正确的是：

- A. 非 strict 场景下"生成 → 解析 → 校验 → 失败则把错误注入后重试"，最多 3 次；超过 3 次仍失败通常说明 schema 或 prompt 需要修正
- B. refusal 也应该重试，直到模型给出结果
- C. 重试次数越多越好，10 次以上能覆盖所有情况
- D. strict mode 下也必须对 parse error 重试

**Q8.** 讲义"Small-model support"一节的核心观点是：

- A. 小模型无法使用受约束解码
- B. 受约束解码只对 70B 以上的模型有效
- C. 带语法约束的 3B 模型在结构化任务上可以胜过只靠 prompt 的 70B 模型，结构化输出让可靠性与模型大小解耦
- D. 小模型在受约束解码下速度会下降到不可用

---

## 三、动手 / 代码题

**Q9.** 本节校验器有三处与 JSON Schema 2020-12 规范不一致（均已运行验证）：

| 调用 | 本节结果 | 规范要求 |
|------|---------|---------|
| `validate({"type": "string", "pattern": "[0-9]+"}, "abc123")` | 报错 | 通过（pattern 是非锚定的搜索） |
| `validate({"type": "string", "pattern": "^[A-Z0-9-]+$"}, "ABC-123\n")` | 通过 | 报错（ECMA-262 的 `$` 只匹配输入末尾） |
| `validate({"type": ["string", "null"]}, 5)` | 通过 | 报错 |

1. 分别解释原因。
2. 写一个 `match_pattern(pattern, value)`，修正前两个问题。
3. 第三个问题为什么在第 02 节的 canonical schema 下特别危险？应如何修？

**Q10.** happy path 的发票满足 schema，但 schema 无法表达"`total_usd` 应等于各行 `qty × unit_usd` 之和"。

1. 有人写了 `sum(li["qty"] * li["unit_usd"] for li in items) == inv["total_usd"]`，对 happy path（`2 × 49.99 + 1 × 120.00`，total 219.98）结果是什么？为什么？
2. 写 `check_semantics(inv)`，正确比较总额，返回与 `ValidationError` 同形状的错误列表。
3. 这类"语义校验"错误应该走哪条处理分支？受约束解码能防止它吗？

**Q11.** 讲义描述了重试策略，但 `main.py` 只做了单次处理，没有实现重试。写 `extract_with_retry(generate, schema, max_retries=3)`：`generate(feedback)` 返回原始字符串；refusal 不重试直接返回；parse_error / violation 把错误列表拼成反馈再调用；超过上限返回 `kind="gave_up"`。用下面三种假生成器测试：

1. 依次返回"尾逗号 JSON"、"带 discount 的 JSON"、"happy path JSON"；
2. 永远返回"缺字段 JSON"；
3. 返回 refusal。

**Q12.**（讲义练习 3）用 Pydantic v2 写出与 `INVOICE_SCHEMA` 等价的 `Invoice` / `LineItem` 模型，调用 `Invoice.model_json_schema()`。

1. 与手写 schema 相比，输出多了哪些东西、结构上有什么不同？
2. 一个不加任何配置的 Pydantic 模型（如 `class Plain(BaseModel): customer: str`）生成的 schema 能直接用于 OpenAI strict mode 吗？缺什么？
3. Pydantic 默认的 lax 模式下，`{"qty": "2"}` 会被怎样处理？这与本节手写校验器有何不同？这种差异在 LLM 输出校验中是好事还是坏事？

---

## 四、面试高频题

**Q13.**（基础必考）让 LLM 稳定输出 JSON 有哪几种方法？各自的可靠性和成本如何？

**Q14.**（原理深挖）受约束解码是怎么实现的？它为什么能保证"可解析 + 符合 schema"？它对哪些 schema 特性支持困难？它能保证输出内容正确吗？

**Q15.**（工程实践）设计一个生产级的"邮件 → 发票"抽取管道。请说明 schema 设计、失败处理（三种失败模式）、重试、语义校验和监控指标。

**Q16.**（场景设计）同一个抽取需求要在 OpenAI（支持 strict）、Anthropic（tool use）、一个自托管的 7B 开源模型上运行。你会分别怎么保证结构化输出？

**Q17.**（追问型）strict mode 下模型返回了 refusal，你该怎么办？怎么区分"合理拒绝"和"应该能抽取却拒绝了"？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Failure collapses to one mode: refusal (the model decides the input does not fit the schema)"；"Parse error. Cannot happen under strict mode"、"Schema violation. Cannot happen under strict mode"。所以 A、B、D 都错。refusal 必须作为带类型的一等结果处理，而且**不应重试**（本节 `process_model_output` 把它作为单独分支返回）。

### Q2 — 答案：A

讲义原文："every property must be listed in `required`, `additionalProperties: false` everywhere, and no unresolved `$ref`. If you break these, the API returns 400 at request time." B、C、D 都是编造的约束。注意第 02 节讲义写的是"no `$ref`"，本节是"no unresolved `$ref`"，两节说法不一致；本节的表述更精确（可以用 `$defs` 定义并引用，只是不能引用解析不到的目标）。

### Q3 — 答案：D

实际输出：

```text
  kind: violation
  error: $.line_items[0].discount: additional property not allowed
  error: $.line_items[0].sku: does not match pattern '^[A-Z0-9-]+$'
```

校验器**收集所有错误**而不是遇到第一个就停止：先检查 `additionalProperties`（发现 `discount`），再逐个属性递归（发现 `sku` 含小写和下划线）。A、B 都只说对了一半；C 是另一个测试用例（missing required）的输出。一次报全所有错误，重试时模型可以一次改完。

### Q4 — 答案：B

讲义："Invalid tokens are masked out of the sampling distribution"；开源实现 "build a deterministic finite automaton from the schema; at every step, mask the logits of tokens that would violate the FSM"。A 是事后修补，不能保证结构合法；C 是"采样 + 过滤"，无保证且昂贵；D 是 prompt 方式，讲义说失败率 5%–15%。

### Q5 — 答案：B

实测返回 `[ValidationError(path='$', message='expected integer, got float')]`。代码用 `isinstance(value, int)` 判断 integer，而 `json.loads("2.0")` 得到 Python float。JSON Schema 2020-12 按数学值判断，`2.0` 是合法 integer，所以这里比规范更严格。在 LLM 输出场景中，`"qty": 2.0` 这类输出并不罕见，被误判会造成不必要的重试。修正：`isinstance(value, float) and value.is_integer()` 也视为整数（同时排除 bool）。

### Q6 — 答案：D

实测 `validate(sku_schema, "ABC-123\n")` 返回 `[]`。Python 正则中 `$` 匹配"字符串末尾**或**末尾换行符之前"，所以 `^[A-Z0-9-]+$` 能匹配 `"ABC-123\n"`；而 JSON Schema 使用 ECMA-262 正则语义，`$` 只匹配输入末尾。要严格匹配，Python 中应使用 `\Z` 或 `re.fullmatch`。这类"差一个换行"的值进入下游（数据库主键、URL 路径）可能导致难以排查的问题。

### Q7 — 答案：A

讲义："generate -> parse -> validate -> if fail, inject error and retry, max 3x. One retry is usually enough. Three retries catches weak-model flakes. Beyond three is a sign of a bad schema"。B 错，讲义："The refusal branch does NOT retry"；C 错，无限重试只会烧钱；D 错，strict 下 parse error 不会发生。

### Q8 — 答案：C

讲义："A 3B-parameter open model with grammar enforcement out-performs a 70B-parameter model with raw prompting on structured tasks. ... it decouples reliability from model size." A、B 与原文相反；D 错，讲义说 2026 年的先进实现对短结构化输出甚至比普通生成更快，对长输出速度大致相同。

### Q9 — 参考答案

1. 原因：
   - 代码用 `re.match`，它只从字符串**开头**匹配；JSON Schema 的 `pattern` 是非锚定搜索（相当于 `re.search`），所以 `[0-9]+` 应在 `"abc123"` 中找到 `123`。
   - Python 的 `$` 会匹配末尾 `\n` 之前的位置（见 Q6）。
   - `t = schema.get("type")` 得到的是列表 `["string", "null"]`，不等于任何一个字符串分支，于是所有类型检查都被跳过；后面的 `minimum`/`enum` 检查也不适用，最终返回 `[]`。
2. 参考实现（已运行验证：四个用例依次为 True / False / True / False）：

```python
def match_pattern(pattern: str, value: str) -> bool:
    # JSON Schema: 非锚定搜索；把末尾未转义的 $ 换成 \Z，避免 Python 的 $ 放过结尾换行
    if pattern.endswith("$") and not pattern.endswith(r"\$"):
        pattern = pattern[:-1] + r"\Z"
    return re.search(pattern, value) is not None
```

   （这是针对常见写法的简化处理；完整做法需要把 ECMA-262 正则逐项翻译，或使用实现了规范的库。）
3. 第 02 节的 canonical schema 用 `"type": ["string", "null"]` 表达 strict 下的"可选字段"。若宿主用本节的校验器做服务端二次校验，**所有**类型数组字段都会被静默放行——一个本该是字符串的字段传入数字、对象都能通过。修正：

```python
types = t if isinstance(t, list) else [t]
if not any(_type_ok(tt, value) for tt in types):
    return [ValidationError(path, f"expected one of {types}, got {type(value).__name__}")]
```

   并补上 `"null"` 类型（`value is None`），再对匹配上的类型分别执行对应关键字检查。

### Q10 — 参考答案

1. 结果是 **False**。实测 `2 * 49.99 + 120.00 = 219.98000000000002`。原因：49.99 无法用二进制浮点精确表示，乘法与加法累积了微小误差，`==` 比较失败。正确的发票会被误判为错误。
2. 参考实现（已运行验证：happy path 返回 `[]`；`qty=2, unit_usd=10, total=999` 返回 `$.total_usd: expected 20, got 999`）：

```python
from decimal import Decimal

def check_semantics(inv, tol=Decimal("0.01")):
    errs = []
    total = sum(Decimal(str(li["unit_usd"])) * li["qty"] for li in inv["line_items"])
    if abs(total - Decimal(str(inv["total_usd"]))) > tol:
        errs.append(ValidationError("$.total_usd", f"expected {total}, got {inv['total_usd']}"))
    return errs
```

   `Decimal(str(x))` 先转字符串再转 Decimal，避免把浮点误差带进来（`Decimal(49.99)` 会得到一长串二进制展开）。这也是讲义的 Pydantic 示例里 `total_usd: Decimal` 的原因。
3. 应该走 **violation** 分支：把语义错误与 schema 错误合并后反馈给模型重试（或交给人工复核）。受约束解码**不能**防止它——它只保证"形状"（`total_usd` 是 ≥ 0 的数字），不保证数值与明细一致。这就是"格式正确 ≠ 内容正确"。

### Q11 — 参考答案

```python
def extract_with_retry(generate, schema, max_retries=3):
    feedback = None
    for attempt in range(1, max_retries + 2):          # 首次 + 最多 3 次重试
        raw = generate(feedback)
        r = process_model_output(raw, schema)
        if r.kind in ("ok", "refusal"):                # refusal 不重试
            return r
        feedback = "Your previous output was invalid:\n" + "\n".join(str(e) for e in r.errors)
    return ParsedResult("gave_up", None, r.errors)
```

实际运行结果：

| 生成器 | 过程 | 最终 kind |
|--------|------|-----------|
| 尾逗号 → discount → happy | parse_error → violation → ok | `ok`（3 次） |
| 永远缺字段 | violation × 4 | `gave_up` |
| refusal | refusal | `refusal`（1 次，不重试） |

要点：反馈内容要具体（带路径的错误，正是 `ValidationError.__str__` 的格式）；把原始输出和错误一起放进下一轮 prompt 效果更好；`gave_up` 时应记录日志、告警，必要时转人工。讲义提醒：持续失败说明 schema 本身有问题（例如对某些输入根本无法满足）。

### Q12 — 参考答案

已用 Pydantic 2.13 实际运行（`LineItem`、`Invoice` 都加了 `model_config = ConfigDict(extra="forbid")`，字段约束用 `Field(pattern=..., ge=..., min_length=..., max_length=...)`，`currency` 用 `Literal["USD", "EUR", "INR"]`）。

1. 差异：
   - 每个模型和字段都多了 **`title`**（如 `"title": "Unit Usd"`、`"title": "Invoice"`）——这就是讲义练习 3 所说"Pydantic 默认设置而手写版本省略的字段"。
   - 嵌套模型被提取到 **`$defs`**，`line_items.items` 变成 `{"$ref": "#/$defs/LineItem"}`，而不是内联。
   - `Literal` 被转成 `{"enum": [...], "type": "string"}`；`ge` 转成 `minimum`。
2. 不能直接用。`Plain` 的输出是 `{"properties": {"customer": {"title": "Customer", "type": "string"}}, "required": ["customer"], "title": "Plain", "type": "object"}`——**没有 `additionalProperties: false`**（Pydantic 默认允许并忽略额外字段，需要 `extra="forbid"` 才会生成）；有默认值或 `Optional` 的字段也不会出现在 `required` 里。OpenAI SDK 的 `parse` 辅助函数会帮你做转换，但手动传 schema 时要自己保证。
3. Pydantic 默认 lax 模式会把 `"2"` **强制转换**成整数 2（实测 `qty` 为 `2`）；`2.0` 也会转换为 `2`。本节手写校验器两者都拒绝（字符串类型错 / float 不是 int）。在 LLM 场景下这是一把双刃剑：好处是减少无谓重试；坏处是可能掩盖模型输出的问题（例如 `"qty": "2 boxes"` 会被拒，但 `"2"` 静默通过）。需要严格校验时使用 `strict=True`（`ConfigDict(strict=True)` 或 `model_validate(..., strict=True)`）。

### Q13 — 参考回答要点

| 方法 | 可靠性 | 成本 / 代价 |
|------|-------|------------|
| prompt 要求 JSON | 讲义：前沿模型 85%–95%，小模型更低；六种失败 | 便宜，但要写修复与重试 |
| 生成后校验 + 重试 | 可靠 | 每次重试都付费、增加延迟；截断问题每次多一轮 |
| 原生 function calling / tool use | 较高 | 需 provider 支持；非 strict 时仍要校验 |
| 受约束解码（strict / responseSchema / outlines 等） | 格式与 schema 保证合规，只剩 refusal | schema 关键字受限；首次编译 schema 可能有开销 |

- 加分点：说清"三种失败模式"及各自处理；无论哪种方式，服务端都要再校验并做业务语义检查。

### Q14 — 参考回答要点

- 实现：把 JSON Schema 编译成语法（正则 / 上下文无关文法 / 有限状态机）；解码时维护当前状态，计算"下一个合法 token 集合"，把其他 token 的 logit 设为 −∞ 再采样。难点在于 token 与字符不对齐（一个 token 可能跨越多个语法符号），需要预先把词表映射到状态转移上（讲义提到 outlines、guidance、lm-format-enforcer）。
- 为什么能保证：每一步都只能走合法转移，结束时必然处于接受状态，所以输出一定可解析、一定满足被编译进去的约束。
- 困难的特性：递归结构、`oneOf/anyOf` 的歧义分支、复杂正则、跨字段约束（如 "a < b"）、数值范围的精确控制等——这也是 OpenAI strict 有诸多限制的原因。
- 不能保证内容正确：只保证形状，不保证值是真的（金额可能编造、语义校验可能失败，见 Q10）；而且强行约束可能迫使模型在不适合的输入上"硬编"内容，所以需要 refusal 通道。
- 加分点：约束过严会扭曲模型分布、降低质量，可以先让模型自由推理再输出结构化结果。

### Q15 — 参考回答要点

- **schema**：`customer`（minLength/maxLength）、`line_items`（数组，每项 sku pattern、qty integer ≥ 1、unit_usd ≥ 0）、`total_usd`、`currency` enum；`additionalProperties: false`；金额在代码中用 `Decimal`。
- **失败处理**：parse_error / violation → 带路径的错误反馈重试（最多 3 次）；refusal → 不重试，记录原因，进入"非发票"队列；gave_up → 人工复核队列。
- **语义校验**：总额等于明细之和（带容差）、币种与金额格式一致、客户名在 CRM 中存在、重复发票检测。
- **监控指标**：各失败模式比例、平均重试次数、refusal 率、语义校验失败率、人工复核率、端到端延迟与成本；用讲义练习 4 的"不可抽取输入"集合测 refusal 与幻觉比例，作为基准。
- 加分点：抽取结果保留原文证据片段（span），便于人工核对。

### Q16 — 参考回答要点

- **OpenAI**：`response_format: {type: "json_schema", strict: true}` 或工具 `strict: true`；schema 满足 strict 三条要求；处理 `refusal`。
- **Anthropic**：用 tool use 承载 schema（强制调用该工具），讲义此处说"Schema enforcement on tool_use inputs"，但第 02 节说"schema is advisory"，本节重试一节也把 Anthropic tool use 列为"strict 之外"——因此稳妥做法是服务端校验 + 重试；讲义：没有 tool call 的 `end_turn` 视为拒绝信号。
- **自托管 7B**：用 outlines / guidance / lm-format-enforcer 等语法约束解码（或推理框架内置的 JSON schema 约束）；讲义说小模型配合语法约束可以很可靠。
- 共同部分：一份 canonical schema（Pydantic）→ 各 provider 适配；统一的三分支处理与语义校验；统一的评测集。

### Q17 — 参考回答要点

- 处理：refusal 是合法结果，不重试；记录拒绝原因，返回带类型的 "refused" 结果；讲义提到 refusal 还可作为安全信号（例如要求抽取受保护内容中的信用卡号）。
- 区分：
  1. 建立评测集：已知"可抽取"与"不可抽取"的样本（讲义练习 4：歌词、数学证明、空邮件等），统计 refusal 率与幻觉率。
  2. 对"应该能抽取却拒绝"的情况，检查 schema 是否过严（例如 currency enum 缺少实际出现的币种、必填字段在原文中确实不存在）。
  3. 给 schema 留出合法的"不确定"表达（可空字段、`confidence` 字段），减少被迫拒绝或被迫编造。
- 常见误区：把 refusal 当错误重试，或者删掉 refusal 通道强行要求输出——这会把"拒绝"变成"幻觉"。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../02-function-calling-deep-dive/docs/zh.md)：strict 标志与三家 schema 方言。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：最小校验器的起点。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：结构化输出的入门讲解。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：理解 logits 与采样，有助于理解 logit masking。

### 本节被哪些后续内容用到
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：用 enum、范围、pattern 设计工具参数。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：MCP 中工具输入输出的契约。
- [阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：agent 中的结构化工具调用。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：refusal 率与抽取准确率的评测。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：refusal 作为安全信号。

### 延伸关键词
`JSON Schema 2020-12` · `strict mode` · `response_format json_schema` · `constrained decoding` · `logit masking` · `outlines / guidance / lm-format-enforcer` · `refusal` · `Pydantic model_json_schema` · `Zod` · `Decimal` · `ECMA-262 regex` · `semantic validation`
