<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="structured-output--json-schema-pydantic-zod-constrained-decoding"></a>

# Structured Output：JSON Schema、Pydantic、Zod 与约束解码

> 向模特儿问好 JSON连边际模型也失败了5%到15%的时间 Structured outputs 以有限的解码来弥补这一差距:该模型实际上无法排放 token 那样会违反计划 OpenAI严格模式 Anthropic其方案型工具的使用, Gemini的 `responseSchema`皮德兰特 `output_type`和佐德的 `.parse` 5个表面形态的相同想法。这个课程构建了模型验证器,严格的模式合同学习者将被用于每个生产提取管道。

**类型:** Build
**语言:** Python (stdlib, JSON 2020-12子集)
**先修要求:** 阶段13 02 (function calling 深潜)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 写一个 JSON 2020-12年的提炼目标,使用正确的限制(单位、分钟/最大值、所需型式)。
- 解释为什么严格模式和限制解码会提供与“后世有效”不同的保证。
- 区分三种失败模式:分析错误、违反计划、拒绝模式。
- 装上一条抽取管道,并进行打字修理和打字拒绝处理。

<a id="the-problem"></a>

## 问题

一个 agent 阅读购买订单邮件需要将免费文本转换为 `{customer, line_items, total_usd}`. 三种办法。

**办法一: prompt 用于 JSON.** 回归 JSON 与字段客户行_项目,共计_使用85到95%的边界模型。在六种方面失败: 缺失支架,跟踪逗号,错误类型, 幻觉田, 短短时间 token 限量,泄漏的流言像"这是你的 JSON:".

**第二: 代代相传。** 自由产生,分析,验证计划,重试失败。可靠但昂贵的——每次重试都要付出费用,每次减速错误要花一圈。

**办法三:限制解码。** 提供方在解码时执行该计划。 无效 tokens 被蒙上头罩 sampling 分布。输出保证分析并保证验证。失败会崩溃到一种模式:拒绝(模型决定输入不符合方案)。

每2026年,边境供应商就用某种方式来运送第三种办法。

- **OpenAI.** `response_format: {type: "json_schema", strict: true}` plus `refusal` 模式下降时,则会发生。
- **Anthropic.** 执行计划 `tool_use` 输入; `stop_reason: "refusal"` 并不是什么问题,但是 `end_turn` 无 tool call 是信号
- **Gemini.** `responseSchema` 请求一级;2026年 Gemini ships token- 选定类型的级别语法限制。
- **皮德兰特** `output_type=InvoiceModel` 发出结构化的 `RunResult` 输入到 `InvoiceModel`.
- **佐德语( Zod)TypeScript).** 运行时分析器, 对照 Zod 的公式验证提供者输出; 配对 OpenAI的 `beta.chat.completions.parse`.

共同的线索: 宣布一次计划, 强制结束它。

<a id="the-concept"></a>

## 概念

<a id="json-schema-2020-12--the-lingua-franca"></a>

### JSON 2020-12年——法语

每个提供者都接受 JSON 2020-12。您使用最多的构造 :

- `type`: 中有一个 `object`, `array`, `string`, `number`, `integer`, `boolean`, `null`.
- `properties`: 字段名称图至子系统。
- `required`:必须显示字段名称列表。
- `enum`:封闭的允许值组。
- `minimum` / `maximum` (numbers), `minLength` / `maxLength` / `pattern` (strings).
- `items`:每个数组元素都应用子系统。
- `additionalProperties`: `false` 禁止额外字段( 默认值因模式不同而不同) 。

OpenAI 严格模式增加了三个要求:每个财产必须列在 `required`, `additionalProperties: false` 到处都有,没有未解决的 `$ref`如果你打破这些, API 返回400,在请求时间。

<a id="pydantic-the-python-binding"></a>

### 皮但蒂, 和他一起的 Python binding

生成 Pydantic v2 的生成 JSON 数据类型模型的图示 `model_json_schema()`。 皮但蒂的人工智能包起来, 所以你写:

```python
class Invoice(BaseModel):
    customer: str
    line_items: list[LineItem]
    total_usd: Decimal
```

以及该 agent 框架将方案转换为 OpenAI 严格模式 Anthropic `input_schema`, 或 Gemini `responseSchema` 模型输出以打印方式返回 `Invoice` 实例。 验证错误产生 `ValidationError` 输入错误路径。

<a id="zod-the-typescript-binding"></a>

### 佐德,我说 TypeScript binding

佐德语( Zod)`z.object({customer: z.string(), ...})`)是TS等量的。 OpenAI节点 SDK exposes `zodResponseFormat(Invoice)` 翻译为 API的 JSON 气管有效载荷

<a id="refusals"></a>

### Refusals

严格模式无法强制模型回答。 如果输入无法符合模式 (“ 电子邮件是一首诗, 不是一张发票 ” ) , 该模式会发布 `refusal` 字段中包含原因。您的代码必须作为头等结果处理,而不是失败。拒绝也是一种安全信号:一个要求从受保护内容电子邮件中提取信用卡号码的模型,会以附加的安全理由返回拒绝。

<a id="constrained-decoding-in-the-open"></a>

### 控制在开放的解码

Open-weights 执行过程采用三种技术。

1. **基于语法的解码** (`outlines`, `guidance`, `lm-format-enforcer`:从图案中建立一个确定性有限自动图;在每一步,都掩盖 logits 的 tokens 那样会违反密克罗尼西亚联邦的宪法
2. **登录掩码 JSON parser**:运行 a streaming JSON 与模型一起锁定分析器; 在每一步计算有效- 下一步-token set.
3. **Speculative decoding 带有验证器**: 廉价模式草案 tokens验证员执行计划

商业供应商在幕后挑一个。 structured outputs 长的也差不多一样的速度

<a id="the-three-failure-modes"></a>

### 三种失败模式

1. **分析错误 。** 输出无效 JSON。在严格模式下无法实现。非严格提供者仍然可以实现。
2. **侵犯计划** 输出剖面但违反了计划。 在严格模式下无法发生。 通常在外方 。
3. **Refusal.** 模型衰落, 必须作为打印结果处理 。

<a id="retry-strategy"></a>

### 重试策略

当您在严格模式之外时( NAME OF TRANSLATORS)Anthropic 工具使用, 非限制 OpenAI, 旧 Gemini回收模式是:

```
generate -> parse -> validate -> if fail, inject error and retry, max 3x
```

通常只需一次重试即可。 三次重试会捕捉到微弱的模版片片段。 超过三次是坏的图案的标志: 模型无法满足某些输入, 而 prompt 或者需要修复这个计划

<a id="small-model-support"></a>

### 小型模型支助

控制解码对小型模型起作用。parameter 使用语法执行的开放模型比70Bparameter 以结构化任务为原始提示的模型。 这是主要原因 structured outputs 用于生产的物质:它从模型大小中分离出可靠性。

```figure
constrained-decoding
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 船舶的最小值 JSON 标准lib 中的 Schema 2020-12 验证符( 类型、 要求、 enum、 分钟/ 最大、 模式、 项、 附加属性) 。 它会以一个 `Invoice` 假的,装作是 LLM 输出,显示分析错误、计划违规和拒绝路径。对任何提供者在生产中的真实反应都交换假输出。

需要关注的内容：

- 验证符返回已输入的 `[ValidationError]` 列表中包含路径和信件。这就是您想要在重试时显示的形状 prompt.
- 拒绝 branch 。 它记录并返回了输入的拒绝。 14 阶段 = 0 9 使用拒绝作为安全信号 。
- 该 `additionalProperties: false` 检查对称测试输入的火灾, 显示为什么严格模式会关闭被幻觉覆盖的字段的门 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-structured-output-designer.md`。如果使用自由文本提取目标(发票、支持票、简历等),则该技能产生 JSON 2020-12号气管,严格与模式兼容,并有一个反射的弹簧模型,输入拒绝和重新处理插管。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。加上第四个测试案例,该案例 `total_usd` 是一个负数。确认验证人拒绝它 `minimum` 限制路径 。

2. 扩展验证符以支持 `oneOf` 通常的情况是: `line_item` 是一种产品或一种服务,由 `kind`。严格模式在此有微妙的规则;检查 OpenAI的 structured outputs guide.

3. 将相同的发票图写成 Pydantic Base 模型并比较 `model_json_schema()` 输出到手动滚动的图案。默认情况下,将手动滚动版本忽略的一个字段 Pydantic 数据集识别出来。

4. 测量拒绝率。 构造十种不应提取的投入( 歌曲词、 数学证明、 空白的电子邮件) , 然后以严格的方式通过真正的提供者运行。 计数拒绝率相对于幻觉输出率。 这是您对拒绝确认的重写的理由真相 。

5. Read OpenAI的 structured outputs 向上到下 。 识别一个构建它明确禁止以严格的方式 JSON 计划允许。然后设计一个方案,使用非基本禁止的构造,并重新设定它严格兼容。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| JSON 2020-12年计划 | "图案" | 现代供应商都说, |
| 严格模式 | "有保证的阴谋" | OpenAI 通过限制解码执行 schema 的旗帜 |
| 受限解码 | 胶片 | 解码时间执行, 隐藏无效的下一个 --tokens |
| Refusal | 模式衰落 | 当输入无法符合方案时键入结果 |
| 分析错误 | "无效 JSON" | 输出未分析为 JSON; 严格情况下不可能 |
| 违反 " 计划 " | 变形 | 解析但被违反类型/ 要求/ enum/ 范围 |
| `additionalProperties: false` | "不允许额外增加" | 未知字段的紫外线; 需要 OpenAI strict |
| 平时基模 | "转动输出" | Python 发放和验证的类 JSON Schema |
| 佐德计划 | "TypeScript 输出类型" | TS运行时间 供货商输出验证的系统图 |
| 语法执行 | "Open-weights 限制解码” | 以密克罗尼西亚为基础的登录掩码,如大纲/指南 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI — Structured outputs](https://platform.openai.com/docs/guides/structured-outputs) 严格方式、拒绝和计划要求
- [OpenAI - 介绍 structured outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/) - 2024年8月,解释解码保证的发射站
- [皮但蒂人工智能-输出](https://ai.pydantic.dev/output/) - 打字输出_类型绑定, 序列化为每个提供者
- [JSON 计划-2020-12号发布说明](https://json-schema.org/draft/2020-12/release-notes) - 弹簧图
- [微软 - Structured outputs 以阿苏语写 OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs) 企业部署说明和严格说明
