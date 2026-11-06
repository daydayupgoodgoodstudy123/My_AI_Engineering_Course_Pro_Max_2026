# 测验 · 带 Schema 校验的工具注册表（Tool Registry with Schema Validation）

> **阶段 19 · 综合项目 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 注册表是唯一事实来源 | 回答三个问题：有哪些工具、参数是什么形状、调用哪个 handler。讲义："A tool the agent cannot validate is a tool the agent cannot call." |
| 2 | ToolRecord 六字段 | `name`、`description`、`schema`、`handler`、`idempotent`（供分派器决定能否重试）、`timeout_ms`（覆盖默认超时） |
| 3 | schema 与 handler 分离 | schema 是数据，handler 是代码；校验器只看 schema，handler 对它不透明，避免把校验逻辑塞进 handler |
| 4 | JSON Schema 2020-12 子集 | 八个关键字：`type`、`properties`、`required`、`enum`、`minLength`、`maxLength`、`pattern`、`items`（代码另外允许 `description`） |
| 5 | 不支持的关键字 | `oneOf`、`anyOf`、`allOf`、`$ref`、条件关键字；注册时出现任何白名单外的关键字都会被拒绝 |
| 6 | JSON Pointer 错误路径 | RFC 6901：`/a/b/2`；`~` 转义为 `~0`、`/` 转义为 `~1`；模型读路径比读句子更容易一次改对 |
| 7 | 收集全部错误 | 校验器不在第一个错误处停止（类型不匹配时只停止该子树），一次返回所有问题 |
| 8 | 不做类型强转 | 字符串 `"42"` 不能通过 `number`；`True` 不能通过 `integer`（Python 中 `bool` 是 `int` 的子类，需特判） |
| 9 | 重复注册需显式 override | 默认拒绝重名注册，`override=True` 才替换，且保持原注册顺序——防止工具目录悄悄漂移 |
| 10 | 不是安全边界 | 校验只保证"形状"，handler 通过校验后仍可能作恶；超时与沙箱由第 23 节分派器等后续层负责 |

### 核心技能（能动手做到）

- [ ] 给定 schema 和参数，手工推演校验器输出的全部错误（路径、关键字、顺序）
- [ ] 正确写出带 `~0`/`~1` 转义的 JSON Pointer，并说清根路径的表示问题
- [ ] 解释 Python 中 `bool`/`int`、`1 == True`、`1.0` 与整数在 JSON Schema 校验里的陷阱
- [ ] 为校验器增加 `additionalProperties: false` 等新关键字，并同时更新"schema 形状检查"
- [ ] 找出注册阶段漏检的问题（名字正则的 `$`、`type` 为列表、非法正则）并修复
- [ ] 把校验错误组织成适合模型自我纠正的反馈

---

## 二、基础自测（选择题）

**Q1.** 讲义坚持把工具的 schema 与 handler 分开存放，主要原因是：

- A. 为了让 handler 可以是异步函数
- B. schema 是数据、handler 是代码；校验器保持纯数据处理，handler 对它不透明，避免把校验逻辑写进 handler
- C. 为了减少内存占用
- D. 因为 JSON Schema 不能描述 Python 函数

**Q2.** 下列哪一组关键字**不在**本节实现的子集中，注册时会被拒绝？

- A. `type`、`properties`、`required`
- B. `enum`、`pattern`、`items`
- C. `minLength`、`maxLength`、`description`
- D. `oneOf`、`anyOf`、`allOf`、`$ref`

**Q3.** schema 为 `{"type": "integer"}`，传入 Python 值 `True`，`validate` 的结果是：

- A. 返回一个 `keyword="type"` 的错误，消息为 `expected integer, got bool`
- B. 返回 `Ok()`，因为 `bool` 是 `int` 的子类
- C. 返回 `Ok()`，因为 `True == 1`
- D. 抛出 `TypeError`

**Q4.** schema 要求 `user.email` 为字符串，输入是 `{"user": {"email": 0}}`，错误路径是：

- A. `user.email`
- B. `/user`
- C. `/user/email`
- D. `$.user.email`

**Q5.** 对象 schema 有一个名为 `"a/b"` 的属性，输入中它的类型错误。按 RFC 6901，代码输出的错误路径是：

- A. `/a/b`
- B. `/a~1b`
- C. `/a~0b`
- D. `/"a/b"`

**Q6.** 依次执行 `register("a", ...)`、`register("a", ..., override=True)`，然后 `names()` 返回：

- A. `["a"]`，且 `get("a")` 返回第二次注册的记录
- B. `["a", "a"]`
- C. 第二次注册抛出 `ValueError`
- D. `[]`，因为 override 会先删除旧记录

**Q7.** schema 为 `{"enum": [1, 2]}`（没有 `type`），传入 Python 值 `True`，本节校验器的结果是：

- A. 返回 `enum` 错误
- B. 返回 `type` 错误
- C. 注册时就被拒绝，因为 enum 必须配合 type
- D. 返回 `Ok()`——因为 Python 中 `True == 1`，`True in [1, 2]` 为真

**Q8.** schema 为 `{"type": "number"}`，模型传来字符串 `"42"`。本节校验器会：

- A. 自动转成 `42` 后通过
- B. 通过，因为 `"42"` 看起来像数字
- C. 返回 `expected number, got str` 的类型错误——校验器不做类型强转
- D. 抛出 `ValueError`

---

## 三、动手 / 代码题

**Q9.** 阅读注册阶段的两段代码：

```python
    _NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
    ...
        if not self._NAME_RE.match(name):
            raise ValueError(...)
```

```python
def validate_schema_shape(schema: dict) -> None:
    ...
    t = schema.get("type")
    if t is not None and t not in PRIMITIVE_TYPE_MAP:
        raise ValueError(f"unsupported type: {t!r}")
    ...
    pattern = schema.get("pattern")
    if pattern is not None and not isinstance(pattern, str):
        raise ValueError("pattern must be a string")
```

分别预测下面三次调用的结果，说明问题并给出修复：

1. `registry.register("db.get_user\n", schema={"type": "string"}, handler=print)`
2. `validate_schema_shape({"type": ["string", "null"]})`
3. 注册 `{"type": "string", "pattern": "("}` 后 `validate("t", "x")`

**Q10.** 讲义"Going further"建议加入 `additionalProperties: false`。请修改代码实现它（只支持布尔值），要求：

- 注册时 `additionalProperties` 必须是 `bool`，否则 `ValueError`；
- 值为 `False` 时，输入中任何未在 `properties` 中声明的键都报错，路径指向该键，`keyword="additionalProperties"`。

**Q11.** 手工推演：schema 为

```python
{"type": "array",
 "items": {"type": "object", "required": ["id"],
           "properties": {"id": {"type": "integer"}}}}
```

输入 `[{"id": 1}, {"id": "2"}, {}]`。写出全部错误（顺序、路径、关键字、消息）。再推演 schema
`{"type": "object", "required": ["a"], "properties": {"b": {"type": "string", "minLength": 3, "pattern": "^z"}}}` 对输入 `{"b": "ab"}` 的全部错误。

**Q12.** 下面四个现象都是"本节校验器与 JSON Schema 2020-12 规范或 RFC 6901 不一致"的地方。逐一解释原因并说明是否需要修复：

1. `{"type": "integer"}` 拒绝 `1.0`；
2. 根位置的错误路径是 `"/"`，而 `{"": 1}` 中空字符串键的类型错误路径也是 `"/"`；
3. `{"minLength": 5}`（没有 `type`）对 `"ab"` 返回 `Ok`；
4. `{"pattern": r"^\d+$"}` 接受阿拉伯-印度数字 `"١٢٣"`。

---

## 四、面试高频题

**Q13.**（基础必考）为什么 agent harness 需要一个带 schema 校验的工具注册表？校验失败时应该怎样把错误反馈给模型？

**Q14.**（原理深挖）既然很多模型 API 已经支持 structured outputs / 约束解码，为什么 harness 侧仍要做参数校验？两者是什么关系？

**Q15.**（工程实践）讲义说一个 harness 可能注册 200 个工具、每轮只暴露 10–40 个。你如何管理这样的工具目录（命名、版本、覆盖、漂移、暴露策略）？

**Q16.**（场景设计）设计一个"让模型一次就能改对"的参数校验错误格式。返回全部错误还是第一个？错误太多怎么办？

**Q17.**（追问型）讲义说注册表"is not a security boundary"。以测试中的 `fs.read`（handler 为 `lambda path: open(path).read()`）为例，通过了 schema 校验之后还有哪些风险？分别由哪一层来防？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The schema is data. The handler is code. Mixing them tempts you to put validation logic inside the handler, which is the bug we are stopping." 官方 `quiz.json` 的答案也是"So the validator stays pure data, and the handler stays opaque code"。A 与分离无关（handler 本来就可以是同步或异步）；C 不是动机；D 是错误的推理——问题不在 JSON Schema 能否描述函数，而在职责分离。

### Q2 — 答案：D

讲义："The keywords we are not adding (oneOf, anyOf, allOf, $ref, conditionals) ... turn the validator into a tree walker with cycles." 代码通过白名单拒绝它们：

```python
ALLOWED_KEYWORDS = {
    "type", "properties", "required", "enum",
    "minLength", "maxLength", "pattern", "items", "description",
}
```

`test_unknown_keyword_rejected` 验证了 `{"type": "object", "oneOf": []}` 会抛 `ValueError`。A、B、C 中的关键字全部在白名单内（`description` 是代码额外允许的注释字段）。注意白名单同样会拒绝 `title`、`default`、`additionalProperties` 等真实工具 schema 中常见的字段（实测均抛 `ValueError`）。

### Q3 — 答案：A

```python
def _type_matches(value: Any, expected: str) -> bool:
    types = PRIMITIVE_TYPE_MAP[expected]
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("integer", "number"):
        if isinstance(value, bool):
            return False
        return isinstance(value, types)
    return isinstance(value, types)
```

Python 里 `isinstance(True, int)` 为 `True`，所以代码对 integer/number 先排除 `bool`。消息里的 `got bool` 来自 `type(value).__name__`。B 正是没有这段特判时的 bug；C 混淆了相等与类型；D 不会发生。测试 `test_integer_vs_boolean` 钉住了这一点。

### Q4 — 答案：C

`_walk` 递归下降时用 `_path(path, prop_name)` 逐段拼接：根 `""` → `/user` → `/user/email`。测试 `test_nested_path` 断言了这个值。A 是点号写法；B 只到上一层；D 是 JSONPath 语法，不是 JSON Pointer。

### Q5 — 答案：B

```python
def _path(prefix: str, segment: str | int) -> str:
    seg = str(segment).replace("~", "~0").replace("/", "~1")
    return f"{prefix}/{seg}"
```

RFC 6901 规定 `~` → `~0`、`/` → `~1`，且必须**先**替换 `~`（否则 `/` 转成的 `~1` 里的 `~` 会被再次转义成 `~01`）。实测 `"a/b"` → `/a~1b`、`"m~n"` → `/m~0n`。A 会被解析成两层路径 `a` → `b`；C 是 `~` 的转义；D 不是合法写法。

### Q6 — 答案：A

```python
        if name not in self._records:
            self._order.append(name)
        self._records[name] = rec
```

只有首次注册才追加到 `_order`，override 只替换字典中的记录，因此 `names()` 仍是 `["a"]`、位置不变（`test_override_replaces`）。B 是不检查就追加的结果；C 是**没有**传 `override=True` 时的行为；D 不符合代码。

### Q7 — 答案：D

```python
    if "enum" in schema:
        if value not in schema["enum"]:
```

`in` 用 `==` 比较，而 Python 中 `True == 1`、`False == 0`。没有 `type` 时不会走 `_type_matches` 的 bool 特判，于是 `True` 通过 `{"enum": [1, 2]}`，`False` 通过 `{"enum": [0]}`（实测均为 `Ok`）。JSON Schema 规范中 `true` 与 `1` 是不同的值，应判为不通过。A 是规范期望的结果；B 不会出现（没有 type）；C 不对，代码允许无 type 的 enum（讲义："treats a schema with `enum` as untyped enum check"）。修复：比较时同时比较类型，例如 `any(type(v) is type(value) and v == value for v in enum)`，或对 bool 单独处理。

### Q8 — 答案：C

讲义："It does not coerce types (a string `"42"` does not pass a number schema)." 实测输出 `[{'path': '/', 'keyword': 'type', 'message': 'expected number, got str'}]`。A、B 是"宽松校验"的行为，会把模型的错误掩盖到 handler 里；D 错，校验失败返回错误列表而不是抛异常。

### Q9 — 参考答案

1. **名字带换行被接受**（实测 `names()` 返回 `['db.get_user\n']`）。原因：Python 正则的 `$` 能匹配"字符串末尾"或"末尾换行符之前"。修复：用 `self._NAME_RE.fullmatch(name)`，或把 `$` 换成 `\Z`。实测 `re.fullmatch(pattern, "db.get_user\n")` 为 `False`。
2. **抛 `TypeError: unhashable type: 'list'`** 而不是 `ValueError`。`t not in PRIMITIVE_TYPE_MAP` 要对 `t` 求哈希，列表不可哈希。JSON Schema 允许 `"type": ["string", "null"]`（可空字段很常见），这里既不支持也没有给出清晰错误。修复：先检查 `isinstance(t, str)`，不是字符串就 `raise ValueError("type must be a string in this subset")`；或者支持列表并在 `_walk` 里改为"任一类型匹配"。
3. **注册成功，校验时返回 `keyword="pattern"`、`message="invalid regex: ..."` 的错误**。这是 schema 作者的 bug，却被报告成"参数错误"，模型会徒劳地反复修改参数。修复：在 `validate_schema_shape` 中 `re.compile(pattern)`，失败就在注册时 `ValueError`；还可以把编译结果缓存起来，避免每次校验重新编译。

### Q10 — 参考答案

```python
ALLOWED_KEYWORDS = {
    "type", "properties", "required", "enum",
    "minLength", "maxLength", "pattern", "items", "description",
    "additionalProperties",
}

# validate_schema_shape 中增加：
    ap = schema.get("additionalProperties")
    if ap is not None and not isinstance(ap, bool):
        raise ValueError("additionalProperties must be a bool in this subset")

# _check_object 中改为：
    props = schema.get("properties", {})
    for prop_name, prop_value in value.items():
        if prop_name in props:
            _walk(props[prop_name], prop_value, _path(path, prop_name), errs)
        elif schema.get("additionalProperties") is False:
            errs.append(ValidationError(
                path=_path(path, prop_name),
                keyword="additionalProperties",
                message=f"unexpected property {prop_name!r}",
            ))
```

已在副本上实测：对 `{"id": 1, "idd": 2}` 返回 `[{'path': '/idd', 'keyword': 'additionalProperties', 'message': "unexpected property 'idd'"}]`；`{"id": 1}` 返回 `Ok()`；`additionalProperties` 为 schema 对象时注册被拒；原有 19 个测试仍全部通过。

要点：

- 两处都要改——只改 `_check_object` 不改白名单，注册阶段就会拒绝这个关键字。
- 用 `is False` 而不是 `not ...`，因为未设置时 `get` 返回 `None`，`not None` 也为真，会误伤所有对象。
- 它能拦住模型拼错的参数名（如 `idd`），否则拼错的键会被静默忽略，而真正的参数又不是必需的，错误只会在 handler 里以奇怪的方式暴露。

### Q11 — 参考答案

第一个（实测输出）：

```text
[{'path': '/1/id', 'keyword': 'type',     'message': 'expected integer, got str'},
 {'path': '/2/id', 'keyword': 'required', 'message': "missing required property 'id'"}]
```

- 元素 0 合法；元素 1 的 `id` 是字符串，路径 `/1/id`；元素 2 缺少 `id`，路径同样指向 `/2/id`（本节约定 required 错误指向缺失属性"将要在的位置"）。
- 顺序：数组按下标遍历；对象内先检查 `required`，再按**输入**的键顺序检查属性。

第二个（实测输出）：

```text
[{'path': '/a', 'keyword': 'required',  'message': "missing required property 'a'"},
 {'path': '/b', 'keyword': 'minLength', 'message': 'length 2 < minLength 3'},
 {'path': '/b', 'keyword': 'pattern',   'message': "value 'ab' does not match pattern '^z'"}]
```

- 同一个字符串上的 `minLength`、`maxLength`、`pattern` 是**独立检查**的，全部报告；而类型错误会让该子树提前 `return`，不再检查其他关键字。

### Q12 — 参考答案

1. **`1.0` 不是 integer**：代码用 `isinstance(value, int)`，`1.0` 是 `float`。JSON Schema 2020-12 按数学值判断，小数部分为 0 的数就是 integer。若模型输出 `{"limit": 10.0}`，规范允许但本校验器拒绝。是否修复取决于策略：严格拒绝可以减少歧义，但应在错误消息里说明；符合规范的写法是 `isinstance(value, float) and value.is_integer()` 也算 integer。
2. **根路径 `"/"`**：RFC 6901 中整个文档的指针是空字符串 `""`，而 `"/"` 指向的是键为 `""` 的成员。代码用 `path or "/"` 把根表示成 `"/"`，于是"根类型错误"和"空键成员错误"的路径相同（实测都是 `/`），无法区分。空键很罕见，但路径应当可以无歧义地还原位置；修复办法是根位置使用 `""`，或在错误中额外给出 `instance_location` 字段。
3. **无 `type` 时关键字被忽略**：`_walk` 只在 `t == "string"` 时调用 `_check_string`，`t == "object"` 时才看 `properties`/`required`。按规范，`minLength` 只要实例是字符串就生效，与是否写了 `type` 无关。实测 `{"minLength": 5}` 对 `"ab"`、`{"properties": {"a": {"type": "string"}}}` 对 `{"a": 1}` 都返回 `Ok`——静默放行比报错更危险。修复：按"实例的实际类型"分派检查，而不是按 schema 的 `type`。
4. **`\d` 的 Unicode 语义**：Python 的 `str` 正则默认 Unicode 模式，`\d` 匹配所有 Unicode 十进制数字；讲义说 pattern 是"ECMA-262-compatible regex"，ECMA-262 中 `\d` 只匹配 ASCII 的 `[0-9]`。若该字段随后被 `int()` 解析或拼进路径，可能引起意外。修复：编译时加 `re.ASCII`，或在 schema 中写 `[0-9]`。另外 `re.search` 不自动锚定，`"abc"` 会匹配 `"xxabcxx"`（这一点与规范一致，schema 作者需要自己写 `^...$`）。

### Q13 — 参考回答要点

- **单一事实来源**：工具名 → schema → handler 的映射只在注册表里维护，分派器"问一次、之后信任"（讲义学习目标）。
- **提前失败**：没有校验时，错误参数会一路传到 handler，表现为堆栈或更糟的副作用；讲义："the only failure mode is a stack trace from the handler"。校验把失败前移到"调用之前、形状层面"。
- **反馈给模型**：返回结构化错误列表（JSON Pointer 路径 + 关键字 + 期望/实际），作为 tool result 回传，让模型在下一轮修正（讲义："The model fixes that in the next call without a round of natural language"）。
- **注册纪律**：名字规范、重名需显式 override、schema 形状在注册时就检查。
- 加分点：校验应纯函数化（讲义："no I/O, no time, no globals"），这样可以在回放日志上重新运行，和第 20 节的确定性回放配合。

### Q14 — 参考回答要点

- **约束解码 / structured outputs**：在生成时限制 token，让输出满足某个 schema，降低格式错误率。
- **为什么 harness 仍要校验**：
  - 不是所有模型、所有供应商都支持，或只支持 schema 的子集；
  - 工具调用可能来自其他来源（MCP 客户端、用户回放、另一个 agent），不一定经过约束解码；
  - 防御性编程：注册表是 harness 自己的契约，不应把正确性寄托在上游；
  - 语义约束（路径必须在工作区内、ID 必须存在）约束解码做不到，需要额外校验层；
  - 校验结果可以审计、回放。
- **关系**：约束解码是"预防"，harness 校验是"兜底 + 反馈"；两者使用同一份 schema，最好由注册表统一导出。
- 常见误区：认为开启 strict 模式后就可以去掉校验。

### Q15 — 参考回答要点

- **命名**：本节规则 `snake_case` 段用 `.` 分隔（如 `db.get_user`），天然形成命名空间，便于按前缀分组和权限控制；用 `fullmatch` 防止隐藏字符。
- **重复与覆盖**：默认拒绝重名，override 必须显式并记录审计日志（谁、何时、为什么覆盖）；讲义："Two parts of the codebase silently registering the same tool name is the kind of bug that takes a week to find."
- **版本**：schema 变化视为版本变化（名字带版本或记录内带 schema hash），旧会话回放时能找到当时的 schema；注册表应深拷贝 schema，防止注册后被外部修改（实测：注册后修改原 dict 的 `type` 为 `"tuple"`，`validate` 抛 `KeyError`）。
- **暴露策略**：按任务、权限、上下文预算挑选 10–40 个工具给模型（工具检索 / 渐进披露），描述保持一行；不常用的工具按需加载。
- **漂移检测**：CI 中导出所有工具的 schema 快照做 diff；监控每个工具的校验失败率，失败率突增往往意味着描述或 schema 不清晰。

### Q16 — 参考回答要点

- **每条错误包含**：JSON Pointer 路径（`/user/email`）、关键字（`type`/`required`/`enum`…）、期望值（讲义例子中的 `expected_type: string`）、实际值或类型；可选附上该字段 schema 的 `description`。
- **全部还是第一个**：返回全部（本节做法），模型可以一次改完；但类型错误时停止该子树，避免级联噪声（本节 `_walk` 在类型错误后 `return`）。
- **错误过多**：按路径去重、限制条数（如前 20 条）并注明"还有 N 条"；`enum` 错误不要把超长枚举全部回显。
- **区分错误来源**：schema 本身的错误（非法正则）不应报告成参数错误（见 Q9）。
- **格式**：结构化 JSON 比自然语言好；同时附一句人类可读的摘要，便于日志检索。
- 加分点：统计每类错误的出现频率，反过来改进工具描述——这是"把每一次纠正转化为系统改进"的思路。

### Q17 — 参考回答要点

- **schema 只保证 `path` 是字符串**，无法阻止：路径穿越（`../../etc/passwd`）、读取密钥文件、符号链接逃逸、读取超大文件导致内存耗尽、读取设备文件阻塞。另外测试里的 `open(path).read()` 不关闭文件、不限制编码。
- **分层防御**：
  - 语义校验层：路径规范化后必须位于工作区根目录下，拒绝符号链接逃逸；
  - 权限与策略层：第 20 节的 `before_tool_call` hook 做 allow/deny（如禁止读取 `.env`）；
  - 分派层（第 23 节）：超时、输出大小上限、错误分类；
  - 沙箱层（第 26 节）：拒绝列表与路径隔离、只读挂载；
  - 审计层：记录每次调用的参数与结果摘要。
- 讲义原话："It is not a security boundary. A malicious handler can still misbehave after validation passes. The dispatcher in lesson twenty-three adds timeout and sandbox layers. The registry adds shape."
- 常见误区：在 schema 里用 `pattern` 试图过滤 `..`——正则很难覆盖所有编码与规范化形式，路径安全应在规范化之后判断。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：工具输入输出为什么必须结构化。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：JSON Schema 与约束解码。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../../13-tools-and-protocols/05-tool-schema-design/docs/zh.md)：如何写好工具 schema。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：模型侧的结构化输出。
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：注册表要接入的循环与 `before_tool_call` hook。

### 本节被哪些后续内容用到
- [阶段 19 · 22 通过换行分隔的 stdio 传输 JSON-RPC 2.0](../../22-jsonrpc-stdio-transport/docs/zh.md)：把注册表暴露给模型客户端。
- [阶段 19 · 23 函数调用分派器](../../23-function-call-dispatcher/docs/zh.md)：分派前调用 `validate`，并利用 `idempotent`、`timeout_ms`。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：在形状校验之外补上安全边界。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../../13-tools-and-protocols/17-mcp-gateways-and-registries/docs/zh.md)：生产级工具注册表的准入治理。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../../13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/docs/zh.md)：工具目录漂移与回滚。

### 延伸关键词
`JSON Schema 2020-12` · `RFC 6901 JSON Pointer` · `additionalProperties` · `$ref / $defs` · `type coercion` · `bool is int` · `re.fullmatch` · `ECMA-262 regex` · `tool catalog drift` · `progressive disclosure` · `constrained decoding` · `defense in depth`
