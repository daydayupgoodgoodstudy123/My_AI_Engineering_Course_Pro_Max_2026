<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="parallel-tool-calls-and-streaming-with-tools"></a>

# 并行 Tool Calls 与工具调用中的 Streaming

> 三次独立的天气调查是连续三次。 平行运行, 全部时间崩溃到最慢的单次通话。 每个边境提供者现在都发出多个 tool calls 在一个转弯。 回报是真实的; 管道是微妙的。 这个课分两半: 平行的扇子外溢和流出参数重新组合, 重点是 ID- 关系陷阱 。

**类型：** 构建
**语言:** Python (stdlib, 线性池+) streaming harness)
**先修要求:** 阶段13 02 (function calling 深潜)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下 `parallel_tool_calls: true` 存在并且何时禁用它 。
- 平行扇形外出时, 校正流出参数块会切到右工具调用 ID 。
- 重新组合部分 `arguments` 字符串为完整 JSON 早点解开
- 运行一个三城市天气基准, 显示相继时间和平行时间 。

<a id="the-problem"></a>

## 问题

没有平行的电话, agent 回答“孟加拉、东京和苏黎世的天气如何?

```
user -> LLM
LLM -> call get_weather(Bengaluru)
host -> run executor, reply with result
LLM -> call get_weather(Tokyo)
host -> run executor, reply with result
LLM -> call get_weather(Zurich)
host -> run executor, reply with result
LLM -> final text answer
```

Three LLM 往返旅行, 每趟旅行都支付执行员的潜伏费。 大约4x理想的墙上时钟时间 。

平行呼叫 :

```
user -> LLM
LLM -> call get_weather(Bengaluru); call get_weather(Tokyo); call get_weather(Zurich)
host -> run all three executors concurrently, reply with three results
LLM -> final text answer
```

One LLM 执行时间是三个的最长时间,而不是总和。 OpenAI, Anthropic, 和 Gemini 显示在扇式外出工作量上,墙上时数减少60%至70%。

价格是相关的复杂。 当三个调用完成时, 您的结果必须包含匹配 `tool_call_id` 以便模型可以排列它们。当结果流时, 您必须将部分参数碎片组合成完整 JSON 执行前。 Gemini 3个增加了独特的识别码,部分是为了解决一个现实世界的问题,即对同一工具的两个平行呼叫是无法区分的。

<a id="the-concept"></a>

## 概念

<a id="enabling-parallel"></a>

### 启用平行

- **OpenAI.** `parallel_tool_calls: true` 默认在默认时间上设置 `false` 强迫序列。
- **Anthropic.** 平行通过 `disable_parallel_tool_use: false` (默认于 Claude 3.5和3.5加起来)设置 `true` 连环画
- **Gemini.** 总是平行的; `tool_config.function_calling_config.mode = "AUTO"` 由模型决定

当工具已订购依赖性时禁用平行( P)`create_file` 然后 `write_file`),当一个呼叫的输出告知另一个输入时,或者当限制利率无法处理扇形退出时。

<a id="id-correlation"></a>

### 与外界关联

模型的每个呼叫都有 `id`。所有结果,主机返回必须包含相同的代号。没有该代号,结果就模糊不清。

- **OpenAI.** `tool_call_id` 在每个工具功能信息上。
- **Anthropic.** `tool_use_id` 在每个 `tool_result` block.
- **Gemini.** `id` 在每个 `functionResponse` (Gemini 3岁及以上; Gemini 与同名同名的同名电话匹配)。

<a id="running-calls-concurrently"></a>

### 同时在打来电话

主机通过自己的线条、 连线或远程工人运行每个呼叫的执行器。 最简单的是 : harness 使用线性池;生产使用 `asyncio.gather` 完成顺序无法预测——ID是识别符号。

一个常见的错误: 以调用列表顺序而不是完成顺序来回答结果。 这通常有效, 因为模型只关心 `tool_call_id`,但如果结果被丢弃或重复,异常提交就会更难调试。最好按完成顺序回答,并有明确的代号。

<a id="streaming-tool-calls"></a>

### Streaming tool calls

当模型流出时 `arguments` 3个平行电话的块流。 您需要每个 id 中一个累积器 。

由提供者形状 :

- **OpenAI.** 每个块 `choices[0].delta.tool_calls[i].function.arguments` (部分字符串) 块包含 `index` (在呼叫列表中的位置)您累积了每个指数, 读取 `id` 当它初次出现,并分析 JSON 当 `finish_reason = "tool_calls"`.
- **Anthropic.** 流动事件 `message_start`,然后一个 `content_block_start` 带有类型 `tool_use` (包含 ID、 名称、 空输入) `content_block_delta` 活动包含 `input_json_delta` chunks. `content_block_stop` 关闭每个街区。
- **Gemini.** `streamFunctionCallArguments` (Gemini 3 和 3) 排放块 `functionCallId` 所以请打工时要干净 Gemini 3, streaming 一次回一个完整电话

<a id="partial-json-and-the-parse-early-trap"></a>

### Partial JSON 和粗糙的陷阱

你无法分析 `arguments` 直到它完成,部分 JSON 例如 `{"city": "Beng` 无效,会升起。正确的门是供应商的断线信号: OpenAI的 `finish_reason = "tool_calls"`, Anthropic的 `content_block_stop`, 或 Gemini流端事件。 仅此尝试 `json.loads`更强有力的方法采用渐进式 JSON 能够产生结构完成的事件的解析器; OpenAI的 streaming 指南建议对显示“ 思考” 实时指标的 UX 使用此功能。 宽度计数作为完整性测试( 引用字符串中的括号或内容漏出导致虚假阳性) 不可靠, 并且只应用作非正式的调试超常 。

<a id="out-of-order-completion"></a>

### 超期完成

```
call_A: fast API, returns first
call_B: slow API, returns second
call_C: median API, returns third
```

主机答复必须仍然引用ID:

```
[{role: "tool", tool_call_id: "call_A", content: ...},
 {role: "tool", tool_call_id: "call_B", content: ...},
 {role: "tool", tool_call_id: "call_C", content: ...}]
```

答复中的顺序与正确性无关 OpenAI 或 Anthropic. Gemini 只要符合 ID , 即可接受任何顺序 。

<a id="benchmark-sequential-vs-parallel"></a>

### 基准:顺序与平行

该 harness 在 `code/main.py` 模拟三个执行器, 400、 600和 800 ms 的延时。 序列运行总共 1800 ms 。 平行运行最多( 400、 600、 800) = 800 ms 。 差异是不变的, 不相称的, 所以节省量会随着工具的计算而增加 。

现实世界警告:平行呼叫在下游的压力 APIs13阶段 17项涵盖网关级服务 backpressure;计划在未来阶段重试语义。

<a id="streaming-fan-out-wall-clock"></a>

### Streaming 扇形外挂墙时钟

如果模型本身流出,您可以在一个呼叫参数完成后立即执行,而不是等待所有呼叫的最后确定。这是一个优化 OpenAI 文档,但并非全部 SDKs 曝光,我们 harness 在此课中, 只需模拟流产生完整的参数, 即启动此调用 。

```figure
tp-parallel-fanout
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 第一次运行三次模拟天气呼叫, 连续并平行使用 `concurrent.futures.ThreadPoolExecutor` 并打印墙上时钟的时间。 后半部重播一个假的 streaming 反应—— `arguments` 三个平行电话在一条溪上断裂,并按每条路重新组装。 `StreamAccumulator`. 否 LLM没有网络,只是重新组装逻辑

需要关注的内容：

- 连续定时器点击1.8秒,平行定时器在相同的假延时器上点击0.8秒。
- 累积器处理的部件 以缓冲每ID 和解析方式到达 不正常的 只有当每次呼叫 JSON 完成 。
- 执行器一旦ID的争论结束 就启动, 而不是在所有流结束之后。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-parallel-call-safety-check.md`。如果使用工具登记册,那么工具可以安全地平行进行技能审计,这些工具可以订购依赖关系,而且将覆盖下游 rate limits - 以每件工具返还订正登记册 `parallel_safe` flags.

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 确认平行顺序比约为 `max/sum` (真正的运行与理想略有不同,因为线性排期、序列化和 harness 是否在什么时间, 平行的悬浮分布不再重要?

2. 将累积器扩展到处理“ 中流电话被取消” 的大小写, 将其缓冲丢弃并释放 `cancelled` 事件。哪个提供者明确记录此案例? Anthropic的 `content_block_stop` 语义和 OpenAI的 `finish_reason: "length"` behavior.

3. 将线索库替换为 `asyncio.gather`。 基准 。 您应该看到由于背景切换成本较低而获得的微小赢家, 但只有在执行者真正做 I/ O 的情况下才能看到 。

4. 选择两个不应平行的工具(例如: `create_file` 然后 `write_file`增加一个 `ordering_dependency` 向登记处发送图表,并打开该图上的平行扇子。 这是最小的附属意识排期机制, 未来 agent-工程阶段正式确定

5. Read OpenAI平行功能调用区 Anthropic的 `disable_parallel_tool_use` 识别一个真实世界的工具类型 Anthropic 建议取消平行性。 (提示: 同一资源上随之发生的突变 。)

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Parallel tool calls | "一转就出来" | 模型发布多个 tool calls 在一个助手信息中 |
| `parallel_tool_calls` | "OpenAI国旗 | 启用或禁用多调放 |
| `disable_parallel_tool_use` | "Anthropic反转 | 选择退出标记; 默认值被启用 |
| Tool call id | 校正手柄 | 每调用标识符后, 结果信件必须回覆 |
| Accumulator | "树脂缓冲" | 部分的每ID字符串缓冲 `arguments` chunks |
| 超期完成 | "先尝尝" | 平行呼叫以无法预测的顺序结束; ID 是胶水 |
| 依赖性图 | 组织上的限制 | 其产出纳入其他工具投入的工具;不能平行 |
| 分析早期陷阱 | "JSON. . 分离爆炸了." | 试图分析一个不完整的 `arguments` string |
| `streamFunctionCallArguments` | "Gemini 3 feature" | 流式参数块, 每调用独有的代号 |
| 补全单回复 | "别等了" | 收到结果后,请按ID键 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI - 平行 function calling](https://platform.openai.com/docs/guides/function-calling#parallel-function-calling) 默认行为和选择退出的旗帜
- [Anthropic 平行工具的使用](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use) — `disable_parallel_tool_use` 和结果的批量
- [谷歌 - Gemini function calling 平行区域](https://ai.google.dev/gemini-api/docs/function-calling) 与身份有关的平行电话 Gemini 3
- [OpenAI — Streaming 使用工具的反应](https://platform.openai.com/docs/api-reference/responses-streaming) 集成参数重新组装 OpenAI streams
- [Anthropic — Streaming messages](https://docs.anthropic.com/en/api/messages-streaming) — `content_block_delta` 与 `input_json_delta`
