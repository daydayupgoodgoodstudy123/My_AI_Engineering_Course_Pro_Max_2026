# 测验 · Structured Outputs：JSON、Schema 校验与约束解码（Structured Outputs: JSON, Schema Validation, Constrained Decoding）

> **阶段 11 · LLM 工程 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 问题的本质 | LLM 只输出字符串，应用需要类型化数据；讲义："This is not a prompt engineering problem. It is a decoding problem." |
| 2 | 四级可靠性光谱 | Prompt-based（约 90% 有效）→ JSON mode（保证可解析，不保证 schema）→ Schema mode（保证匹配 schema）→ Constrained decoding（token 级强制） |
| 3 | JSON Schema | 描述"形状"的契约语言：`type`、`properties`、`required`、`enum`、`minimum/maximum`、`items`、`minItems/maxItems`、`oneOf/anyOf/allOf` |
| 4 | Pydantic 模式 | 用 Python 类声明字段与类型，自动生成 JSON Schema；OpenAI SDK、Instructor 直接接受 Pydantic 类 |
| 5 | 约束解码原理 | 每一步把会导致非法输出的 token 概率置 0（logit 置 −∞），模型只能走向合法输出；Outlines 把 schema 编译成有限状态机，XGrammar 用下推自动机处理嵌套语法 |
| 6 | Tool use / function calling | 同一问题的另一种接口：模型输出"函数名 + 结构化参数"；当模型需要**选择**用哪个 schema 时更合适 |
| 7 | 校验 + 重试 | 解析 → 校验 → 把错误回传给模型再试（Instructor 的做法）；本节代码的重试**不回传错误** |
| 8 | Schema 管不到的失败 | 幻觉值（类型对、值错）、enum 同义词、深层嵌套、数组长度、可选字段被省略 |
| 9 | 可选字段的处理 | 讲义建议：语义上重要的字段设为 required，缺失时强制模型显式输出 `null`，而不是让它悄悄省略 |
| 10 | 代码的简化之处 | 手写校验器不查多余字段、把 `True` 当数字放行；`next_valid_tokens` 只看最后一个字符，无法区分"字符串内/外"与"对象/数组上下文" |

### 核心技能（能动手做到）

- [ ] 手写一个递归 JSON Schema 校验器，支持 object/array/string/number/integer/boolean、`required`、`enum`、`minimum/maximum`、`minItems/maxItems`，并返回带路径的错误信息（如 `.customer.email`）
- [ ] 说出 Python 中 `bool` 是 `int` 子类带来的校验陷阱，并修好它
- [ ] 用一个"容器栈 + 字符串状态"的小状态机，给出部分 JSON 之后合法的下一个 token 类别
- [ ] 实现"带错误反馈"的重试循环：把上一次输出和校验错误放回对话再请求一次
- [ ] 对同一个抽取任务，分别写出 OpenAI `response_format`、Anthropic tool use（`input_schema`）、Instructor（`response_model`）三种调用方式
- [ ] 设计一个抽取 schema：哪些字段用 enum、哪些设为 required + nullable、哪些加数值范围，并说明理由
- [ ] 说清"schema 合规 ≠ 内容正确"，并为抽取结果设计字段级准确率评测

---

## 二、基础自测（选择题）

**Q1.** 关于 OpenAI 的 JSON mode（`response_format: {"type": "json_object"}`），下列说法正确的是：

- A. 它保证输出符合你提供的 JSON Schema
- B. 它通过 few-shot 示例提高 JSON 的成功率，但不做任何保证
- C. 它等价于 tool use，模型会输出一个函数调用
- D. 它保证输出能被 JSON 解析器解析，但不保证键、类型与你期望的 schema 一致

**Q2.** 执行 `validate_schema({"product": "Test", "in_stock": True}, PRODUCT_SCHEMA)`，返回值是：

- A. `['.price: required field missing']`
- B. `['price: required field missing']`
- C. `[]`，因为缺失的字段不会被递归检查
- D. `[': expected object, got dict']`

**Q3.** 约束解码（constrained decoding）保证输出合法的机制是：

- A. 生成完成后用正则表达式修复不合法的部分
- B. 在 system prompt 里放入 JSON Schema，让模型自觉遵守
- C. 在每一步采样前，把会导致输出不合法的 token 的概率置为 0（logit 置为 −∞），只在合法 token 中采样
- D. 生成多个候选，选出能通过校验的那一个

**Q4.** 原文写的是"$348"，模型输出 `{"product": "Sony WH-1000XM5", "price": 299.99, "in_stock": true}`。下列哪种手段**能**发现这个问题？

- A. 开启 JSON mode
- B. 把抽取结果与原文做事实核对（人工标注评测集或 LLM-as-judge）
- C. 给 `price` 加上 `"minimum": 0`
- D. 换成约束解码

**Q5.** 本节代码中 `next_valid_tokens('{"product"', {})` 的返回值是：

- A. `[':']`
- B. `['"', '}']`
- C. `['any']`
- D. `['a-z', '"']`

**Q6.** 某字段（如 `discount`）在原文中常常缺失，但下游业务必须知道"是没有折扣还是模型漏抽了"。按讲义建议，schema 应该：

- A. 把它设为 required，并允许 `null`，强制模型显式给出 `null`
- B. 把它设为可选（不放进 `required`），缺失时就省略
- C. 设为 required，缺失时让模型填 0
- D. 从 schema 中删掉，后处理时再用正则抽取

**Q7.** 下列哪种场景**最适合**用 tool use / function calling 而不是单一的 `response_format` schema？

- A. 从每条评论中抽取固定的三个字段
- B. 只需要一个合法的 JSON，结构不重要
- C. 系统有 10 种不同的抽取 schema，需要模型根据输入内容决定用哪一个
- D. 模型不支持 JSON Schema 时的退路

**Q8.** 执行 `validate_schema({"product": "x", "price": True, "in_stock": True}, PRODUCT_SCHEMA)`，返回值是：

- A. `['.price: expected number, got bool']`
- B. `[]`
- C. 抛出 `TypeError`
- D. `['.price: True is less than minimum 0']`

---

## 三、动手 / 代码题

**Q9.** 阅读 `next_valid_tokens` 的核心分支：

```python
    last_char = stripped[-1] if stripped else ""

    if last_char == "{":
        return ['"', "}"]
    elif last_char == '"':
        if stripped.endswith('":'):
            return ['"', "0-9", "true", "false", "null", "[", "{"]
        return ["a-z", '"']
    elif last_char == ":":
        return [" ", '"', "0-9", "true", "false", "null", "[", "{"]
    elif last_char == ",":
        return [" ", '"', "{", "["]
    elif last_char in "0123456789":
        return ["0-9", ".", ",", "}", "]"]
```

1. 运行结果中 `{"product"` 和 `{"product": "Sony"` 都得到 `['a-z', '"']`。正确答案分别是什么？问题出在哪里？
2. `if stripped.endswith('":')` 这个分支什么时候会被执行？
3. 输入 `[1,` 时返回 `[' ', '"', '{', '[']`，输入 `{"a": 1,` 时也返回同样的结果。分别指出它漏掉了什么、多给了什么。
4. 不依赖任何库，设计一个能修好上述问题的思路（可以写代码）。

**Q10.** 校验器的 `number` 分支与 `object` 分支：

```python
    elif schema_type == "number":
        if not isinstance(data, (int, float)):
            errors.append(f"{path}: expected number, got {type(data).__name__}")
            return
        minimum = schema.get("minimum")
        ...
    # object 分支
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                _validate(value, properties[key], f"{path}.{key}", errors)
```

实测：`price: True`、`price: float("nan")`、多出的字段 `"color": "red"` 都返回 `[]`（通过）。

1. 解释为什么 `True` 和 `NaN` 能通过（`json.loads('{"price": NaN}')` 在 Python 中能成功解析吗？）。
2. 修改代码，让三者都报错（多余字段在 schema 写了 `"additionalProperties": false` 时才报错）。

**Q11.** 抽取管道：

```python
def extract_with_retry(text, schema, max_retries=3):
    for attempt in range(max_retries):
        raw = simulate_llm_extraction(text, schema, attempt)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"    Attempt {attempt + 1}: JSON parse error -- {e}")
            continue
        errors = validate_schema(data, schema)
        if not errors:
            return data
        print(f"    Attempt {attempt + 1}: Schema validation errors -- {errors}")
    return None
```

1. 实际运行中四条输入的重试分支有没有被触发过？为什么？
2. 这个重试与讲义描述的 Instructor 重试有什么本质区别？
3. 第四条输入"This sentence contains no product information at all."得到 `{"product": "Unknown", "price": 0, "in_stock": false}` 并**通过校验**。这说明了什么？配套的 `outputs/prompt-structured-extractor.md` 规定"缺失的数字用 0、字符串用 \"unknown\"、布尔用 false"，这与讲义"Failure Modes"一节的建议是否一致？
4. 改写成"带错误反馈"的版本。

**Q12.** `python_type_to_schema` 中有一个分支：

```python
    if field.field_type in type_map:
        schema["type"] = type_map[field.field_type]
    elif field.field_type == list:
        schema["type"] = "array"
        schema["items"] = {"type": "string"}
    elif isinstance(field.field_type, dict):
        schema = field.field_type
```

1. 执行 `python_type_to_schema(SchemaField({"type": "object", "properties": {}}))` 会发生什么？
2. 即便修好第 1 问，`schema = field.field_type` 之后再写 `schema["enum"] = ...` 还有什么隐患？
3. 本节的 `SchemaField` 还有哪些与 Pydantic 不同、在实际使用中会碰壁的简化？（至少两点）

---

## 四、面试高频题

**Q13.**（基础必考）让 LLM 稳定输出结构化数据，有哪几种做法？各自保证到什么程度？生产中你会怎么选？

**Q14.**（原理深挖）约束解码在实现上是怎么做的？为什么"token 边界与语法边界不对齐"是难点？约束解码会不会影响输出质量？

**Q15.**（工程实践）设计一个从商品描述中抽取结构化信息的生产管道（每天 100 万条），从 schema 设计、调用方式、校验、重试、评测到监控，说说你的方案。

**Q16.**（场景设计）抽取 schema 上线半年后需要改版：新增字段、重命名字段、把 `price` 从 number 改成 `{amount, currency}` 对象。哪些是破坏性变更？你怎么做版本管理？

**Q17.**（追问型）"既然 OpenAI 的 Structured Outputs 用约束解码保证 100% 符合 schema，讲义也说 'No retries needed. No validation needed.'，那应用侧还需要校验吗？"

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："the API guarantees the output is valid JSON... But it may not match your expected schema -- extra keys, wrong types, missing fields."
- A 描述的是 Schema mode（`response_format: {type: "json_schema", ...}`）。
- B 描述的是 prompt-based 做法，JSON mode 是 API 级别的保证。
- C 混淆了两种接口：tool use 输出函数调用，JSON mode 输出普通 JSON 文本。

### Q2 — 答案：A

`_validate` 在 object 分支先遍历 `required`，对缺失的键追加 `f"{path}.{key}: required field missing"`；顶层 `path` 为空字符串，所以路径是 `.price`（实际运行输出 `['.price: required field missing']`）。
- B 少了前导点，与代码的路径拼接方式不符。
- C 错：`required` 检查不依赖递归，缺失字段正是在这里被发现的。
- D 错：输入本身是 dict，类型检查通过。

### Q3 — 答案：C

讲义："at each token position during generation, the decoder masks out all tokens that would produce invalid output... that token is set to probability zero."
- A 是后处理修复，不是约束解码，也无法保证结果正确。
- B 是 prompt-based 方法，约 90% 可靠，没有任何保证。
- D 是"采样多次 + 过滤"（rejection sampling），成本高且不能保证一定有合法候选。

### Q4 — 答案：B

这是讲义"Hallucinated values"一节的原例："Schema validation cannot catch this -- the type is correct, the value is wrong."
- A、D 只管语法/结构，299.99 是合法 number。
- C 中 299.99 ≥ 0，范围约束也拦不住。
- 只有把结果与原文对照（有标注的评测集、LLM-as-judge、或要求模型给出原文出处 span 再做字符串核对）才能发现。`outputs/skill-structured-outputs.md` 也写到："Schema-valid but factually wrong: add an LLM-as-judge validation step"。

### Q5 — 答案：D

实际运行输出 `{"product"  ['a-z', '"']`。函数只看最后一个字符 `"`，分不清这是"键的结束引号"还是"字符串的开始引号"，于是返回"继续写字母或闭合引号"。**正确答案应该是 A `[':']`**——键之后只能跟冒号。这是代码的 bug，见 Q9。
- B 是 `{` 之后的返回值。
- C 是"无法识别的最后一个字符"（例如字符串内部的字母）时的返回值。

### Q6 — 答案：A

讲义："Set them as required in the schema even if the data is sometimes missing -- force the model to produce `null` explicitly." 用 JSON Schema 写作 `"discount": {"type": ["number", "null"]}` 并放入 `required`。
- B 正是讲义说的"Optional field omission"失败模式：省略可能是"真没有"，也可能是"漏抽了"，下游无法区分。
- C 用 0 冒充缺失，把"未知"伪装成"已知的 0"，与幻觉值同类问题（见 Q11 第 3 问）。
- D 放弃了结构化输出，回到正则解析自由文本的老路。

### Q7 — 答案：C

讲义："Tool use is preferred when the model needs to choose which function to call, not just fill in parameters. If you have 10 different extraction schemas..."
- A、B 用 schema mode / JSON mode 即可。
- D 不成立：tool use 本身就依赖 JSON Schema（Anthropic 的 `input_schema`）。

### Q8 — 答案：B

Python 中 `bool` 是 `int` 的子类，`isinstance(True, (int, float))` 为 `True`；接着 `True < 0` 即 `1 < 0` 为 False，不触发 minimum 错误。于是返回 `[]`（已实际运行验证）。
- A 是"应该"的行为；代码在 `integer` 分支写了 `or isinstance(data, bool)`，在 `number` 分支却忘了。
- C 错：比较 `True < 0` 合法，不会抛异常。
- D 错：`True` 等于 1，不小于 0。
- 对照：Pydantic 默认（lax 模式）也会把 `True` 转成 `1.0`，`strict=True` 时才报 `float_type` 错误（已实际验证）。

### Q9 — 参考答案

1. 正确答案：`{"product"` 之后只能是 `:`；`{"product": "Sony"` 之后只能是 `,` 或 `}`。问题在于函数**只看最后一个字符**，没有记录"当前是否在字符串内部""这个字符串是键还是值""外层容器是对象还是数组"这些状态。最后一个字符都是 `"`，所以两者得到同样的（错误）答案。
2. **永远不会执行**：进入该分支的前提是 `last_char == '"'`，而 `stripped.endswith('":')` 要求最后一个字符是 `:`，二者矛盾——这是死代码。作者大概想处理"冒号之后"，但那已经由 `elif last_char == ":"` 分支负责。
3. - `[1,`：处在数组中，逗号后应是**任意值**，函数漏掉了 `0-9`、`true`、`false`、`null`（以及负号 `-`）。
   - `{"a": 1,`：处在对象中，逗号后只能是**键**（`"`），`{` 和 `[` 是非法的，函数多给了。
   - 同理，数字后面它总是给出 `}` 和 `]` 两者，不区分当前容器；负数（`-`）落到 `else` 分支返回 `['any']`。
   - 参数 `schema` 完全没有被使用，所以它只能约束"JSON 语法"，不能约束"schema"（例如键名必须是 `product`、`price` 的值必须是数字）。
4. 思路：从头扫描部分 JSON，维护**容器栈**和**字符串状态**（含转义），据此决定期望的下一类 token。参考实现（已在本节的 9 个示例状态上运行验证，结果分别是 `{` 之后 `['"', '}']`、键之后 `[':']`、值字符串之后 `[',', '}']`、对象内逗号之后 `['"']`、`[1,` 之后包含 `0-9` 的全部值类别、`{"a": [1]` 之后 `[',', '}']`）：

```python
def next_valid_tokens_v2(partial):
    stack, in_string, escape = [], False, False
    expect, prev = "value", ""
    for ch in partial:
        if in_string:
            if escape: escape = False
            elif ch == "\\": escape = True
            elif ch == '"':
                in_string = False
                expect = "colon" if prev == "key" else "comma_or_close"
            continue
        if ch.isspace(): continue
        if ch == '"':
            in_string = True
            prev = "key" if expect in ("key", "key_or_close") else "value"
        elif ch in "{[":
            stack.append(ch)
            expect = "key_or_close" if ch == "{" else "value_or_close"
        elif ch in "}]":
            stack.pop(); expect = "comma_or_close"
        elif ch == ":":
            expect = "value"
        elif ch == ",":
            expect = "key" if stack[-1] == "{" else "value"
        else:                       # 数字或 true/false/null 的一部分
            expect = "comma_or_close"
    if in_string:
        return ["<string-char>", '"']
    VALUE = ['"', "0-9", "-", "true", "false", "null", "[", "{"]
    if expect == "value": return VALUE
    if expect == "value_or_close": return VALUE + ["]"]
    if expect == "key": return ['"']
    if expect == "key_or_close": return ['"', "}"]
    if expect == "colon": return [":"]
    if not stack: return ["<EOS>"]
    return [",", "}" if stack[-1] == "{" else "]"]
```

仍然的简化：数字未写完时还应允许继续 `0-9`、`.`、`e`；`true/false/null` 写到一半时应只允许补全剩余字母；要真正"按 schema 约束"，还需在 `expect == "key"` 时只允许 schema 中尚未出现的键名、在值位置按该键的类型收窄。Outlines 的做法是把 schema 编译成正则再编译成 FSM，XGrammar 用下推自动机处理任意深度的嵌套——上面的"栈"正是下推自动机的雏形。

### Q10 — 参考答案

1. - `True`：`bool` 是 `int` 的子类（见 Q8）。
   - `NaN`：`isinstance(float("nan"), float)` 为真；所有与 NaN 的比较都返回 False，所以 `nan < 0` 和 `nan > max` 都不成立，范围检查形同虚设。Python 的 `json.loads('{"price": NaN}')` **能**成功解析（得到 `{'price': nan}`，已实际验证），尽管 NaN 不是标准 JSON；`json.dumps` 默认也会写出 `NaN`。
   - 多余字段：object 分支只校验 `properties` 里**有**的键，`if key in properties` 把其它键直接跳过。讲义 Key Terms 把"no extra disallowed fields"列为 schema compliance 的一部分，代码没有实现。
2. 修改（已运行验证：`True` 报 `expected number, got bool`，NaN 报 `is not a finite number`）：

```python
import math

    elif schema_type == "number":
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            errors.append(f"{path}: expected number, got {type(data).__name__}")
            return
        if isinstance(data, float) and not math.isfinite(data):
            errors.append(f"{path}: {data} is not a finite number")
            return
        ...

    # object 分支，在遍历 data.items() 时：
        allow_extra = schema.get("additionalProperties", True)
        for key, value in data.items():
            if key in properties:
                _validate(value, properties[key], f"{path}.{key}", errors)
            elif allow_extra is False:
                errors.append(f"{path}.{key}: additional property not allowed")
```

此外，解析时可用 `json.loads(raw, parse_constant=...)` 拒绝 `NaN`/`Infinity`。注意 `additionalProperties` 默认为 true（JSON Schema 规范），所以只在显式写 `false` 时报错；OpenAI 的 strict 模式要求每个对象都写 `additionalProperties: false`。

### Q11 — 参考答案

1. **一次都没有触发**。`simulate_llm_extraction` 在 `attempt == 0` 时对所有输入返回的都是合法 JSON 且能通过 `PRODUCT_SCHEMA`：Sony 那条第一次就带着 `categories` 通过了，第二次的分支（去掉 categories）永远走不到。运行输出里没有任何 `Attempt N:` 行。想看到重试，需要让第一次返回坏数据（例如 `"price": "$348"` 或带 markdown 围栏）。
2. 本质区别：**这里的重试不把错误告诉模型**。`simulate_llm_extraction(text, schema, attempt)` 只多传了一个 `attempt` 计数，输入内容完全一样；对真实 LLM 来说，这只是"再抽一次签"（靠采样随机性）。讲义描述的 Instructor："it sends the errors back to the model as context and asks it to fix the output"——模型能看到"price 应该是 number，你给了 str"，从而有针对性地修正。另外，函数参数 `schema` 在模拟器里也没被使用。
3. 说明 **schema 合规 ≠ 内容正确**：没有任何产品信息的句子被"编造"成了一个名为 Unknown、价格 0 的产品，类型全对，校验全过。下游库存系统会多出一条脏数据。
   - 配套 prompt 的"缺失时用 0 / unknown / false"与讲义的建议**不一致**：讲义要求"force the model to produce `null` explicitly"，把"未知"与"真实的 0 / false"区分开。`in_stock: false` 尤其危险——"没有提到库存"被写成了"缺货"。
   - 更好的设计：字段类型设为 `["number", "null"]` 并 required；或增加 `"found": boolean` / `"is_product": boolean` 先做判别；无法抽取时让整个结果为 `null` 或进入人工复核队列。
4. 带错误反馈的版本（已用一个"第一次输出带 markdown 围栏和 `"$348"`、看到错误后修正"的假 LLM 运行验证：第 2 次成功）：

```python
def extract_with_feedback(text, schema, llm, max_retries=3):
    messages = [{"role": "user",
                 "content": f"Extract per schema {json.dumps(schema)}:\n{text}"}]
    for attempt in range(1, max_retries + 1):
        raw = llm(messages)
        try:
            data = json.loads(raw)
            errors = validate_schema(data, schema)
        except json.JSONDecodeError as e:
            errors = [f"invalid JSON: {e}"]
        if not errors:
            return data, attempt
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user",
             "content": f"Your output had errors: {errors}. Return only corrected JSON."},
        ]
    raise ValueError(f"failed after {max_retries} attempts: {errors}")
```

要点：保留上一轮的原始输出作为 assistant 消息，再追加带具体错误的 user 消息；失败时抛异常或返回带原因的结果，而不是静默返回 `None`；生产中还要记录每次重试的次数与错误类型做监控。

### Q12 — 参考答案

1. 抛出 `TypeError: unhashable type: 'dict'`（已实际运行验证）。第一行 `field.field_type in type_map` 要对 `field_type` 求哈希来查字典键，而 dict 不可哈希，于是在到达 `isinstance(..., dict)` 分支之前就崩了。这个分支等于**不可达**。修法：先判断 `isinstance(field.field_type, dict)`，或改成 `type_map.get(field.field_type)` 前先排除 dict。
2. **别名（aliasing）问题**：`schema = field.field_type` 没有复制，随后的 `schema["enum"] = ...`、`schema["minimum"] = ...` 会直接修改调用者传入的那个 dict。如果同一个子 schema 被多个字段复用，修改会互相"串味"。应写成 `schema = copy.deepcopy(field.field_type)` 或 `dict(field.field_type)`。
3. 至少两点：
   - `list` 的元素类型被写死为 `{"type": "string"}`，无法表示 `list[int]` 或对象数组；Pydantic 从 `list[str]` 这样的类型注解中推出 `items`。
   - `default` 参数存了但从未使用，既不写进 schema，校验时也不会补默认值；Pydantic 会在 schema 中输出 `"default": []`，实例化时自动填充。
   - 不支持可空类型（`Optional[float]` → `anyOf: [number, null]`）、嵌套模型、`description`（讲义 skill 文件指出"The model reads these as instructions"）。
   - `model_to_schema` 的参数 `name` 没有被使用（Pydantic 会生成 `"title": "Product"`）。
   - 作为对照，`Product(BaseModel)` 的 `model_json_schema()` 实际输出包含 `title`、`default` 等字段，`required` 为 `["product", "price", "in_stock"]`，与本节手写结果的核心部分一致。

### Q13 — 参考回答要点

- **四个层级**（讲义的光谱）：
  1. Prompt-based："只返回 JSON"，无保证，讲义估计约 90%；常见失败是 markdown 围栏、前言文字、截断、结构错误。
  2. JSON mode：保证可解析，不保证 schema。
  3. Schema mode：提供 JSON Schema，保证输出匹配（OpenAI `json_schema`、Anthropic tool use 的 `input_schema`、Gemini `response_schema`）。
  4. Constrained decoding：token 级强制，开源推理侧常用 Outlines、XGrammar、Guidance。
- **还有两种工程手段**：tool use（模型选择函数并填参数）；Instructor（任意供应商 + Pydantic 校验 + 带错误反馈的自动重试）。
- **怎么选**：托管 API 且供应商支持 → 优先 schema mode / tool use；自托管模型 → 推理框架里的语法约束；供应商不支持或 schema 过于复杂 → Pydantic 校验 + 反馈重试兜底。原型阶段才用纯 prompt。
- 加分点：无论哪种方式，应用侧都保留一层校验（见 Q17）；语义正确性需要额外的评测与核对。
- 常见误区：把 JSON mode 当成 schema 保证；以为"100% 合规"就等于"100% 正确"。

### Q14 — 参考回答要点

- **基本做法**：解码每一步拿到 logits 后，先计算"当前语法状态下哪些 token 合法"，对非法 token 的 logit 加 −∞（mask），再做 softmax 与采样；然后根据选中的 token 推进语法状态。
- **怎么高效地算 mask**：
  - Outlines（讲义引用 Willard & Louf 2023）：把 JSON Schema 转成正则，再编译成有限状态机（FSM），**离线**预计算"每个 FSM 状态 → 合法 token 集合"的索引，解码时查表。
  - 嵌套结构（任意深度的 JSON、递归 schema）超出正则的表达能力，需要上下文无关文法与下推自动机（PDA）；讲义提到 XGrammar 用 PDA 编译，每 token 掩码约 100 ns。
- **token 边界难点**：BPE 词表里的 token 往往跨越多个语法单元，例如 `",` 、`":"`、` true}`。合法性必须按"整个 token 的字符串能否让自动机继续走下去"来判断，而不是按单个字符；词表有 10 万级 token，每一步逐个检查太慢，所以需要预计算与缓存。
- **对质量的影响**：
  - mask 会把概率质量强行重新分配，若模型"本想"说别的，可能被迫走进低概率路径；
  - 格式约束可能挤压推理空间——常见做法是在 schema 里先放一个 `reasoning` 字段，再放答案字段（字段顺序会影响生成顺序）；
  - 字段 `description` 与 prompt 依然重要，约束解码只管"形状"不管"内容"。
- 加分点：能说清本节 `next_valid_tokens` 为什么不够（只看最后一个字符，没有状态栈），以及 Q9 的栈正是 PDA 的雏形。

### Q15 — 参考回答要点

- **Schema 设计**：扁平优先（skill 文件："Nested objects beyond 2 levels increase extraction errors"）；分类字段用 enum；数值加范围；重要字段 required + nullable；每个字段写 `description`；带 `schema_version`。
- **调用方式**：使用供应商的 schema mode 或 tool use（strict），自托管时用语法约束；批量任务用 batch API 降低成本；temperature 设低。
- **校验层**：Pydantic 模型做类型 + 业务规则校验（如 `currency` 合法、`price` 在品类合理范围内、跨字段一致性）。
- **失败处理**：带错误反馈的重试（上限 2–3 次）；仍失败 → 死信队列 / 人工复核，绝不静默写入默认值。
- **评测**：人工标注一个评测集（讲义练习 4：50 条起步），指标包括 exact match、字段级准确率、类型合规率，找出最难抽取的字段；改 prompt 或 schema 前后跑回归。
- **置信度**：讲义练习 5——多次抽取看一致性，或用 token 概率；低置信字段送人工。
- **监控**：解析失败率、校验失败率、重试率、`null` 比例、各字段分布漂移、延迟与成本；抽样做线上事实核对。
- 常见误区：只看"解析成功率 100%"就认为管道健康。

### Q16 — 参考回答要点

- **破坏性变更**（讲义练习 2 的定义）：删除 required 字段、重命名字段（对消费者等于删除 + 新增）、修改类型（`price: number → object`）、收紧约束（缩小 enum、提高 minimum）、把可选改为必填。
- **非破坏性变更**：新增可选字段、放宽约束（扩大 enum、放宽范围）、补充 description。
- **版本管理做法**：
  - schema 带版本号，与 prompt 一起版本化存储；输出数据带 `schema_version`；
  - 破坏性变更走新版本，旧版本并行一段时间，下游逐步迁移；
  - 提供迁移/适配函数（v1 → v2，如把 `price: 348` 转成 `{amount: 348, currency: "USD"}`，但货币需要来源信息，不能凭空假设）；
  - 用"schema diff"工具在 CI 中自动识别破坏性变更并阻断；
  - 新版本上线前在评测集上对比两版字段级准确率。
- 加分点：类比 API 版本管理与数据库 migration；注意历史数据回填的成本。

### Q17 — 参考回答要点

- **需要**，理由：
  1. **截断**：达到 `max_tokens` 时输出可能在中途停止，得到不完整的 JSON；
  2. **拒答**：模型可能因安全策略拒绝回答，返回的不是你的 schema（OpenAI 的 SDK 为此单独提供了 refusal 字段）；
  3. **schema 子集**：供应商的 strict 模式只支持 JSON Schema 的一个子集（例如要求对象都写 `additionalProperties: false`、所有字段放进 `required`），部分约束（复杂 pattern、跨字段约束）只能在应用侧检查；
  4. **业务规则与跨字段一致性**：例如本节嵌套订单示例中 `total` 应等于各项 `quantity × price` 之和（`3 × 9.99 + 24.99 = 54.96`），schema 表达不了；
  5. **幻觉值**：类型正确、值错误，见 Q4；
  6. **防御性编程**：供应商、模型版本、SDK 都可能变化，换模型或切到不支持约束解码的后端时，校验层是最后一道防线。
- 讲义的"No retries needed. No validation needed."应理解为"不需要为语法和结构做重试"，不是"不需要任何校验"。
- 加分点：校验失败的样本要进入监控和评测集，用来改进 prompt 和 schema。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 20 Structured Outputs & 约束解码](../../../05-nlp-foundations-to-advanced/20-structured-outputs-constrained-decoding/docs/zh.md)：讲义明确建议先读，FSM/CFG logit processor、Outlines、XGrammar 的解码器层原理都在那里。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：logits → softmax → 采样的流程，约束解码就是在 softmax 之前加 mask。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：理解"token 边界与语法边界不对齐"为什么让约束解码变难。
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)：prompt-based 结构化输出与抽取 prompt 的写法。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../02-few-shot-cot/docs/zh.md)：few-shot 示例提升格式遵从；"先推理再输出答案"与字段顺序设计相关。

### 本节被哪些后续内容用到
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：tool use 是结构化输出的另一种接口。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)：抽取结果的字段级评测。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../12-guardrails/docs/zh.md)：输出校验是 guardrail 的一部分。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：Agent 的工具调用建立在结构化输出之上。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：同一主题在工具协议语境下的深入。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../../13-tools-and-protocols/05-tool-schema-design/docs/zh.md)：schema 字段命名与 description 的设计。

### 延伸关键词
`JSON mode` · `json_schema / strict` · `additionalProperties` · `Pydantic` · `Instructor` · `tool use / input_schema` · `constrained decoding` · `logit mask` · `FSM / pushdown automaton` · `Outlines` · `XGrammar` · `Guidance` · `retry with feedback` · `schema versioning` · `field-level accuracy`
