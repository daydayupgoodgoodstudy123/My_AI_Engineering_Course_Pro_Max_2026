# 测验 · 深入理解 Function Calling：OpenAI、Anthropic、Gemini（Function Calling Deep Dive — OpenAI, Anthropic, Gemini）

> **阶段 13 · 工具与协议 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（例如把 "Forbid tools" 译成"紫外线工具"，Anthropic 的限制条目丢了半句），遇到读不通的地方请直接看英文版。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五个共同要素 | 每家 provider 都需要：工具列表、tool choice、调用输出、调用 id、结果回填；只是字段名和嵌套不同 |
| 2 | 声明的三种信封 | OpenAI `{type:"function", function:{name, description, parameters, strict}}`；Anthropic `{name, description, input_schema}`；Gemini `{functionDeclarations:[{name, description, parameters}]}` |
| 3 | 调用在响应里的位置 | OpenAI 在 `choices[0].message.tool_calls[]`；Anthropic 在 `content[]` 中 `type:"tool_use"` 的块；Gemini 在 `candidates[0].content.parts[]` 中的 `functionCall` |
| 4 | arguments 是字符串还是对象 | 只有 OpenAI 返回**JSON 字符串**，必须 `json.loads`；Anthropic 的 `input`、Gemini 的 `args` 已经是对象 |
| 5 | id 与结果回填 | OpenAI：`role:"tool"` + `tool_call_id`；Anthropic：`user` 消息里的 `tool_result` 块 + `tool_use_id`；Gemini：`functionResponse` + 匹配的 `id`（讲义：Gemini 3 起才有稳定唯一 id） |
| 6 | tool_choice 四种模式 | auto / none / required（Anthropic 叫 `any`，Gemini 叫 `ANY`）/ force 指定工具（Gemini 用 `ANY` + `allowed_function_names`） |
| 7 | strict mode | OpenAI `strict: true` 用受约束解码强制合规，要求所有属性都在 `required` 中、`additionalProperties: false`，"可选"用 `["type", "null"]` 表达 |
| 8 | Gemini 的 schema 方言 | OpenAPI 3.0 子集：类型大写（`OBJECT`/`STRING`）、不支持 `additionalProperties`、可空用 `nullable: true` 而非类型数组 |
| 9 | 各家硬限制 | 讲义：OpenAI 128 个工具、schema 深度 5、参数串 ≤ 8192 字节；Anthropic 64 个工具；Gemini 64 个函数 |
| 10 | Translator 模式 | 代码内只维护一份 canonical `Tool`，在边缘用三个小函数翻译声明、三个 parser 把响应统一成 `Call(id, name, args)` |

### 核心技能（能动手做到）

- [ ] 给定一个 canonical 工具，手写出它在 OpenAI / Anthropic / Gemini 下的声明 JSON
- [ ] 写出三家 provider 响应的 parser，统一成 `{id, name, args}`，并处理 `tool_calls` 为 `null`、arguments 非法 JSON、Gemini 缺 id 等边界情况
- [ ] 把 canonical `ToolChoice(mode=...)` 翻译成三家的 `tool_choice` / `tool_config`
- [ ] 写出三家的"工具结果回填"消息（本节代码未实现的第五要素）
- [ ] 把 JSON Schema 转成 Gemini 的 OpenAPI 子集，正确处理 `["string", "null"]` → `nullable`
- [ ] 判断一个 schema 能否在 OpenAI strict mode 下使用，并指出可空字段 + `enum` 的陷阱

---

## 二、基础自测（选择题）

**Q1.** 三家 provider 中，哪一家返回的工具参数是**需要你自己 `json.loads` 的字符串**？

- A. OpenAI（`function.arguments`）
- B. Anthropic（`input`）
- C. Gemini（`args`）
- D. 三家都返回字符串

**Q2.** 在 Anthropic Messages API 中，宿主执行完工具后，应该如何回填结果？

- A. 发送一条 `role: "tool"` 的消息，带 `tool_call_id`
- B. 发送一条 `role: "assistant"` 的消息，内含 `tool_result` 块
- C. 发送一条 `role: "user"` 的消息，内含 `{type: "tool_result", tool_use_id, content}` 块
- D. 发送 `{functionResponse: {name, id, response}}`

**Q3.** 本节代码中三份模拟响应的"结束原因"字段分别是 `finish_reason: "tool_calls"`、`stop_reason: "tool_use"`、`finishReason: "STOP"`。由此得到的正确工程结论是：

- A. Gemini 的响应说明模型没有发起调用
- B. 只要检查结束原因字段就能判断三家是否发起了调用
- C. Gemini 的 `STOP` 代表请求被安全过滤器拦截
- D. 对 Gemini 不能只看结束原因，必须遍历 `parts[]` 查找 `functionCall`

**Q4.** 运行本节代码，Gemini 声明中 `units` 字段的 `type` 被输出为：

- A. `"STRING"`
- B. `["string", "null"]`（原样保留小写数组）
- C. `"STRING"` 并附带 `"nullable": true`
- D. 该字段被删除

**Q5.** canonical `ToolChoice(mode="required")`（必须至少调用一个工具）在 Anthropic 中对应：

- A. `{"type": "any"}`
- B. `{"type": "required"}`
- C. `"required"`
- D. `{"type": "tool", "name": "..."}`

**Q6.** 要让 Gemini **强制调用某一个指定工具** `get_weather`，正确写法是：

- A. `{"function_calling_config": {"mode": "AUTO"}}`
- B. `{"function_calling_config": {"mode": "FORCE", "name": "get_weather"}}`
- C. `{"function_calling_config": {"mode": "ANY"}}`
- D. `{"function_calling_config": {"mode": "ANY", "allowed_function_names": ["get_weather"]}}`

**Q7.** canonical schema 中 `"units": {"type": ["string", "null"], "enum": ["celsius", "fahrenheit"]}`，且 `units` 在 `required` 中。用标准的 JSON Schema 2020-12 校验器（如 `jsonschema`）校验 `{"city": "X", "units": null}`，结果是：

- A. 通过，因为类型允许 null
- B. 通过，因为 `required` 只要求键存在
- C. 失败：`None is not one of ['celsius', 'fahrenheit']`
- D. 失败：`'units' is a required property`

**Q8.** canonical schema 把可选的 `units` 也写进 `required`，同时允许 null，并设置 `additionalProperties: false`，主要是为了：

- A. 让 Gemini 能识别可选字段
- B. 满足 OpenAI strict mode 的要求：所有属性都必须列在 `required` 中，"可选"只能用可空类型表达
- C. 减少 token 消耗
- D. 让 Anthropic 强制校验 schema

---

## 三、动手 / 代码题

**Q9.** 阅读 `_gemini_schema`：

```python
def _gemini_schema(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict = {}
        for k, v in node.items():
            if k == "additionalProperties":
                continue
            if k == "type" and isinstance(v, str):
                out["type"] = v.upper()
                continue
            out[k] = _gemini_schema(v)
        return out
    if isinstance(node, list):
        return [_gemini_schema(x) for x in node]
    return node
```

1. 本节运行输出中，Gemini 声明的 `units` 为什么还是 `"type": ["string", "null"]`？这在 OpenAPI 3.0 子集里有什么问题？
2. 如果某个工具有一个**属性名**恰好叫 `additionalProperties`（比如一个表单工具），这个函数会怎样？
3. 改写它：类型数组 `[X, "null"]` → `{"type": X.upper(), "nullable": true}`；无法表达的联合类型（如 `["string", "integer"]`）直接抛错；`properties` 下的键是属性名，不能当成 schema 关键字处理。

**Q10.** 下面三种响应会让本节 parser 出什么问题？（均已实际运行）

```python
# (a) OpenAI：模型只回复文本，tool_calls 显式为 null
{"choices": [{"message": {"role": "assistant", "content": "hi", "tool_calls": None}}]}
# (b) OpenAI 非 strict：arguments 是非法 JSON
{"choices": [{"message": {"tool_calls": [{"id": "c1", "type": "function",
    "function": {"name": "x", "arguments": '{"city": "a",}'}}]}}]}
# (c) Gemini 2：两个并行调用都没有 id
{"candidates": [{"content": {"parts": [
    {"functionCall": {"name": "get_weather", "args": {"city": "A"}}},
    {"functionCall": {"name": "get_weather", "args": {"city": "B"}}}]}}]}
```

写出健壮版的 `parse_openai` 和 `parse_gemini`，并说明 (b) 发生时宿主应该怎么处理。

**Q11.** 讲义列出的五个共同要素中，第 5 个"结果回填（Result injection）"本节代码**没有实现**。请写出三个函数 `result_openai(call, result)`、`result_anthropic(call, result, is_error=False)`、`result_gemini(call, result)`，分别返回可以直接追加到对话历史里的消息。用 `Call(id="toolu_xyz789", name="get_weather", ...)` 和结果 `{"temp": 28, "units": "celsius"}` 写出三者的 JSON。

**Q12.** 找讲义（含第 01 节）中的不一致：

1. 本节对比表 "Strict schema" 一行说 Anthropic 是 "schema-is-schema (always enforced)"，而 "Errors and repair" 一节怎么说？宿主应该以哪种说法为准来设计？
2. 第 01 节说 `parallel_tool_calls` 在 Anthropic 上是 "opt-in"；本节怎么说？
3. 对比表 "Force-a-tool" 一行，Gemini 写的是 `tool_config: {function_calling_config: {mode: "ANY"}}`。这能"强制某个指定工具"吗？代码是怎么写的？

---

## 四、面试高频题

**Q13.**（基础必考）请对比 OpenAI、Anthropic、Gemini 三家 function calling 在"声明 / 调用 / 结果"三个环节上的差异，至少说出 5 处。

**Q14.**（原理深挖）OpenAI 的 strict mode 是怎么保证参数一定符合 schema 的？它对 schema 有哪些限制，为什么会有这些限制？开启 strict 之后宿主还需要校验吗？

**Q15.**（工程实践）你的团队要把一个跑在 OpenAI 上的 agent 同时支持 Anthropic 和 Gemini。你会怎么设计代码结构？列出迁移时最容易踩的坑。

**Q16.**（场景设计）一个企业助手注册了 150 个工具，要同时跑在三家 provider 上。按讲义给出的限制，会遇到什么问题？如何设计解决方案？

**Q17.**（追问型）`tool_choice` 设为 required / force 有什么用？会带来什么副作用？什么时候应该用 none？

---

## 五、参考答案与解析

### Q1 — 答案：A

OpenAI 的 `tool_calls[i].function.arguments` 是 JSON **字符串**（运行输出 "OpenAI raw args type : string -> dict"，parser 用 `json.loads` 转成 dict）。Anthropic 的 `input`、Gemini 的 `args` 已是对象，直接用即可。D 错。讲义的移植审查 skill 把"在非 OpenAI 目标上假设 arguments 是字符串"列为 hard reject——对 dict 调 `json.loads` 会直接 `TypeError`。

### Q2 — 答案：C

讲义："You reply with a new `user` message containing a `{type: "tool_result", tool_use_id, content}` block." A 是 OpenAI 的方式；B 错在角色——结果是"用户侧"提供给模型的信息，不是模型说的话；D 是 Gemini 的 `functionResponse`。

### Q3 — 答案：D

本节模拟的 Gemini 响应里，明明有 `functionCall`，`finishReason` 却是 `"STOP"`。所以 Gemini 不能用结束原因判断是否发起了调用，`parse_gemini` 正是通过遍历 `parts[]`、检查 `"functionCall" in part` 来提取调用。A 与事实相反；B 只对 OpenAI 和 Anthropic 成立；C 是编造的含义。稳妥的做法是三家都以"响应里是否有调用对象"为准，结束原因只作辅助。

### Q4 — 答案：B

`_gemini_schema` 只在 `type` 是**字符串**时才转大写（`isinstance(v, str)`）。`["string", "null"]` 是列表，走到 `out[k] = _gemini_schema(v)`，列表里的字符串原样返回，于是输出仍是小写数组。这在 OpenAPI 3.0 子集中不合法（type 必须是单个值，可空要用 `nullable: true`），真实请求很可能被拒绝或被忽略。C 是"应该"的输出（见 Q9）；A、D 都不是实际行为。

### Q5 — 答案：A

代码 `tool_choice_anthropic`：`required` → `{"type": "any"}`。B 不是 Anthropic 的合法取值；C 是 OpenAI 的写法（OpenAI 的 `tool_choice` 可以直接是字符串 `"required"`）；D 是 force 模式。三家同一语义叫法不同：OpenAI `required`、Anthropic `any`、Gemini `ANY`。

### Q6 — 答案：D

代码 `tool_choice_gemini` 的 force 分支：`{"mode": "ANY", "allowed_function_names": [tc.tool_name]}`。只写 `mode: "ANY"`（C）只能保证"必须调用某个工具"，不能保证是哪一个——这正是讲义对比表那一行不完整的地方（见 Q12）。A 是自动模式；B 中的 `FORCE` 模式和 `name` 字段都不存在。

### Q7 — 答案：C

已用 `jsonschema` 4.26 实际验证：`{"city": "X", "units": None}` 报 `None is not one of ['celsius', 'fahrenheit']`。JSON Schema 中 `type` 和 `enum` 是**同时**生效的约束（逻辑"与"）：type 允许 null，但 enum 里没有 null，所以 null 被 enum 拒绝。A 忽略了 enum；B、D 不对，键是存在的。修正方法：`"enum": ["celsius", "fahrenheit", null]`。否则在 strict mode 下模型根本无法表达"不指定单位"，这个"可选"字段名存实亡。

### Q8 — 答案：B

讲义："Strict mode requires ... every property listed in `required`"，同时要求 `additionalProperties: false`。在这种约束下，"可选字段"只能写成"必填但可为 null"。A 错，Gemini 用的是 `nullable`，而且翻译器把 `additionalProperties` 删掉了；C 无关；D 错，Anthropic 声明里没有 strict 字段，translator 直接丢弃了 `strict`。

### Q9 — 参考答案

1. 因为只有 `isinstance(v, str)` 时才转大写；类型数组被当作普通列表递归，字符串元素原样保留。OpenAPI 3.0 的 `type` 只能是单个字符串，可空要写 `nullable: true`。
2. 属性名 `additionalProperties` 会被当成 schema 关键字删掉：实测 `{"type":"object","properties":{"additionalProperties":{"type":"string"}}}` 被翻译成 `{"type":"OBJECT","properties":{}}`，这个参数从声明里消失了。根因是函数不区分"schema 关键字"和"`properties` 下的属性名"。
3. 参考实现（已运行验证，`units` 输出为 `{"type": "STRING", "nullable": true, "enum": [...]}`，属性名 `additionalProperties` 得以保留）：

```python
def gemini_schema(node):
    if isinstance(node, list):
        return [gemini_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k == "additionalProperties":
            continue
        if k == "type":
            types = v if isinstance(v, list) else [v]
            non_null = [t for t in types if t != "null"]
            if len(non_null) != 1:
                raise ValueError(f"Gemini cannot express union type {v}")
            out["type"] = non_null[0].upper()
            if "null" in types:
                out["nullable"] = True
        elif k == "properties":          # 键是属性名，只递归值
            out[k] = {name: gemini_schema(sub) for name, sub in v.items()}
        else:
            out[k] = gemini_schema(v)
    return out
```

补充：`anyOf`、`$ref`、`const` 等关键字也需要按目标 provider 的支持情况处理或报错；翻译失败时**在构建期报错**，比在线上被 provider 拒绝要好。

### Q10 — 参考答案

实际运行结果：(a) `TypeError: 'NoneType' object is not iterable`——`msg.get("tool_calls", [])` 只在键**不存在**时返回默认值，键存在但值为 `None` 时仍返回 `None`；(b) `json.JSONDecodeError: Illegal trailing comma ...`，直接抛出；(c) 返回两个 `id=''` 的调用，结果回填时无法区分 A 和 B。

```python
class ToolCallParseError(Exception):
    pass

def parse_openai(resp):
    msg = resp["choices"][0]["message"]
    calls = []
    for tc in msg.get("tool_calls") or []:              # 同时处理缺失和 None
        fn = tc["function"]
        try:
            args = json.loads(fn["arguments"] or "{}")
        except json.JSONDecodeError as e:
            raise ToolCallParseError(f"{tc['id']}: arguments is not valid JSON: {e}") from e
        if not isinstance(args, dict):
            raise ToolCallParseError(f"{tc['id']}: arguments must be an object")
        calls.append(Call(id=tc["id"], name=fn["name"], args=args))
    return calls

def parse_gemini(resp):
    calls = []
    for i, part in enumerate(resp["candidates"][0]["content"].get("parts", [])):
        if "functionCall" in part:
            fc = part["functionCall"]
            cid = fc.get("id") or f"gemini-local-{i}-{uuid.uuid4().hex[:6]}"   # 本地补 id
            calls.append(Call(id=cid, name=fc["name"], args=fc.get("args", {})))
    return calls
```

(b) 的处理：讲义 "OpenAI (non-strict). ... your JSON parse fails, you inject an error message and re-call"——把解析错误作为这个 `tool_call_id` 的 tool 结果（`{"error": "arguments is not valid JSON: ..."}`）回填，再调用一次模型；同时计数，连续失败则停止。若 provider 不返回 id（Gemini 2），本地补的 id 只用于宿主内部关联，回填时按 provider 要求的方式（位置顺序 + name）对应。

### Q11 — 参考答案

```python
def result_openai(call, result):
    return {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}

def result_anthropic(call, result, is_error=False):
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id,
                                         "content": json.dumps(result), "is_error": is_error}]}

def result_gemini(call, result):
    return {"role": "user", "parts": [{"functionResponse": {
        "name": call.name, "id": call.id, "response": result}}]}
```

实际输出：

```json
{"role": "tool", "tool_call_id": "toolu_xyz789", "content": "{\"temp\": 28, \"units\": \"celsius\"}"}
{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_xyz789", "content": "{\"temp\": 28, \"units\": \"celsius\"}", "is_error": false}]}
{"role": "user", "parts": [{"functionResponse": {"name": "get_weather", "id": "toolu_xyz789", "response": {"temp": 28, "units": "celsius"}}}]}
```

要点：
- OpenAI 的 `content` 是字符串，Gemini 的 `response` 是对象，Anthropic 的 `content` 可以是字符串或内容块数组。
- 三者都必须紧跟在"发起该调用的那条 assistant/model 消息"之后；多个并行调用时，Anthropic 要把所有 `tool_result` 块放进**同一条** user 消息，OpenAI 是每个调用一条 tool 消息。
- Anthropic 的 `is_error: true` 让模型明确知道这是失败结果。
- 真实场景中 id 只能回填给产生它的那家 provider（示例用 Anthropic 的 id 只是为了展示形状）。

### Q12 — 参考答案

1. "Errors and repair" 一节说："Anthropic. `input` may contain unexpected fields; schema is advisory. Validate server-side." "Limits" 一节也说"No strict-mode flag; schema is a contract and the model tends to comply"。"always enforced" 与 "advisory"、"tends to comply" 互相矛盾。设计宿主时应按**最保守**的说法：任何 provider 的参数都要在服务端再校验一次。
2. 本节说："Anthropic historically did single-call; `disable_parallel_tool_use: false` (default as of Claude 3.5) enables multi"，即默认允许并行、可以用 `disable_parallel_tool_use: true` 关闭；这与第 01 节"opt-in on Anthropic"的说法相反。按本节描述，Anthropic 的并行是默认开启、可选择关闭（opt-out）。
3. 只写 `mode: "ANY"` 只能强制"必须调用某个工具"，不能指定是哪个。代码中 force 分支额外加了 `"allowed_function_names": [tc.tool_name]`，把候选集合限制为单个工具，才真正等价于 OpenAI/Anthropic 的"按名字强制"。这里代码比讲义表格更准确。

### Q13 — 参考回答要点

| 环节 | OpenAI | Anthropic | Gemini |
|------|--------|-----------|--------|
| 声明信封 | `{type:"function", function:{...}}` | 扁平 `{name, description, input_schema}` | `{functionDeclarations:[...]}`，一个 tool 对象可含多个函数 |
| schema 字段 | `parameters`（JSON Schema） | `input_schema`（JSON Schema） | `parameters`（OpenAPI 3.0 子集） |
| 调用位置 | `message.tool_calls[]` | `content[]` 中 `tool_use` 块（可与 text 块并存） | `parts[]` 中 `functionCall` |
| 参数类型 | JSON 字符串 | 对象 | 对象 |
| id | `call_...` | `toolu_...` | 讲义：Gemini 3 起有唯一 id |
| 结果回填 | `role:"tool"` + `tool_call_id` | `user` + `tool_result` + `tool_use_id` | `functionResponse` + `name` + `id` |
| 结束原因 | `finish_reason:"tool_calls"` | `stop_reason:"tool_use"` | 本节示例为 `STOP`，需检查 parts |
| tool_choice | 字符串或对象 | `{type: auto/any/none/tool}` | `tool_config.function_calling_config.mode` |

- 加分点：能说出 strict mode 的差异，以及 Anthropic 响应里 text 与 tool_use 可并存（例如 "Looking that up." + 调用），宿主应把整条 assistant 消息原样放回历史。

### Q14 — 参考回答要点

- **原理**：受约束解码（constrained decoding）。把 schema 编译成语法/状态机，每一步解码时把不符合语法的 token 的概率置零（logit mask），所以输出在语法上必然符合 schema（第 04 节详讲）。
- **限制及原因**（讲义）：不支持 `$ref`、不支持有重叠的 `oneOf/anyOf/allOf`、所有属性必须在 `required` 中、`additionalProperties: false`。原因是这些结构难以编译成确定的有限状态机，或会让"该生成哪个分支"产生歧义；要求全部 required 则保证生成路径确定。
- **仍需校验**：strict 保证的是"形状"，不保证"语义"（城市名是否存在、数量是否合理）；也可能出现 `refusal` 而不是调用；并且宿主可能同时对接非 strict 的 provider。服务端校验是最后一道防线。
- 常见误区：以为 strict 能修正"选错工具"。

### Q15 — 参考回答要点

- **结构**：canonical 层（`Tool`、`Call`、`ToolChoice`、`ToolResult`）+ provider adapter 层（声明翻译、tool_choice 翻译、响应解析、结果回填、流式解析）+ 统一的 agent loop。业务代码只接触 canonical 类型。讲义提到生产中有 Pydantic AI 的 `AbstractToolset`、LangGraph、LlamaIndex 的抽象，以及第 17 节的网关模式。
- **常见坑**：
  1. 在 Anthropic/Gemini 上对 `args` 调 `json.loads`（或反之在 OpenAI 上忘了 parse）；
  2. Anthropic 结果回填用错角色（应是 `user` + `tool_result`），并行结果没放进同一条消息；
  3. Gemini schema 方言：类型大写、`nullable`、不支持 `additionalProperties`；
  4. strict 标志在其它 provider 上被静默丢弃，校验强度下降；
  5. 工具数量、schema 深度上限不同；
  6. id 格式与是否存在不同，不能假设 `call_` 前缀；
  7. 判断"是否发起调用"不能只看结束原因。
- 加分点：为每个 adapter 写契约测试（录制的真实响应样本），并在 CI 中对 canonical 工具做三家翻译的快照测试。

### Q16 — 参考回答要点

- 问题：讲义给出的上限是 OpenAI 128、Anthropic 64、Gemini 64，150 个工具在三家都超限；即使不超限，工具越多，模型选错工具的概率越高、每次请求的 prompt token 越多。
- 方案：
  1. **工具路由 / 检索**：先用 embedding 或分类器从 150 个工具里选出与当前请求最相关的 10–30 个，再发给模型（讲义的移植审查 skill 称之为 "needs-router"）。
  2. **分层工具**：按领域分组，先让模型选领域（或用一个 `search_tools` 元工具），再加载该领域的工具。
  3. **合并相近工具**：把 `get_user_by_id`、`get_user_by_email` 合成一个带 enum 参数的工具（第 05 节）。
  4. **多 agent 拆分**：每个子 agent 只持有一个领域的工具。
- 加分点：说明路由本身要有评测（召回率），否则模型连正确工具都看不到。

### Q17 — 参考回答要点

- **required/any**：保证这一轮一定产生结构化调用，适合"抽取 / 分类"类任务（把工具当作结构化输出的通道），或流程中必须先查数据再回答的步骤。
- **force 指定工具**：流程编排确定下一步时使用，如固定先调用 `classify_intent`。
- **副作用**：模型失去"不调用"的选项，即使不需要或信息不足也会硬编参数（幻觉参数）；容易造成循环（每轮都被迫调用）。所以通常只在单步强制，下一轮恢复 auto。讲义还提到 Anthropic 的 `disable_parallel_tool_use` 可以把"必须调用"进一步限制为"只调用一个"。
- **none**：需要模型基于已有工具结果给出最终答复时；或在达到预算/轮数上限时强制收尾，防止继续调用。
- 常见误区：长期把 tool_choice 设为 required，导致 agent 无法自然结束。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：本节把四步循环落到三家 provider 的字段上。
- [阶段 11 · 09 Function Calling 与工具使用](../../../11-llm-engineering/09-function-calling/docs/zh.md)：provider API 的基础用法。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：理解 strict mode 背后的受约束解码。

### 本节被哪些后续内容用到
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../03-parallel-and-streaming-tool-calls/docs/zh.md)：三家流式事件格式与并行结果回填。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../04-structured-output/docs/zh.md)：strict mode 与受约束解码的深入讲解。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：如何写出可移植的 schema。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：把 translator 模式推广为网关。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../21-llm-routing-layer/docs/zh.md)：多 provider 统一接口的现成方案。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：生产环境中的 provider 抽象层。

### 延伸关键词
`tool_calls` · `tool_use / tool_result` · `functionCall / functionResponse` · `tool_choice` · `function_calling_config` · `allowed_function_names` · `strict mode` · `OpenAPI 3.0 schema` · `nullable` · `disable_parallel_tool_use` · `adapter pattern` · `LLM gateway`
