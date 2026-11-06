---
phase: 13
phase_dir: 13-tools-and-protocols
phase_title: 工具和协议
lesson: 01
lesson_dir: 01-the-tool-interface
lesson_title: 工具接口：为什么 Agents 需要结构化输入输出
section: 概念 › 为什么不直接通过 prompt 要求模型输出 JSON？
section_en: The Concept › Why not just prompt the model to emit JSON?
date: 2026-10-12
tags: [function-calling, tool-use, structured-output, strict-mode, constrained-decoding, tool-use-training]
related: [13/02-function-calling-deep-dive, 13/04-structured-output]
---

# 用 prompt 要求输出 JSON 与原生 function calling 的区别

## 📍 提问位置

| 层级 | 位置 |
|---|---|
| 阶段 | 第 13 阶段「工具和协议」（`13-tools-and-protocols`） |
| 课程 | 第 01 课「工具接口：为什么 Agents 需要结构化输入输出」（`01-the-tool-interface`） |
| 章节 | 「概念」›「为什么不直接通过 prompt 要求模型输出 JSON？」 |
| 原文 | [zh.md 第 103 行](../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md#why-not-just-prompt-the-model-to-emit-json) · [en.md 第 79 行](../../13-tools-and-protocols/01-the-tool-interface/docs/en.md#why-not-just-prompt-the-model-to-emit-json) |
| 后续课程 | [第 02 课 深入理解 Function Calling](../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md) · [第 04 课 Structured Output](../../13-tools-and-protocols/04-structured-output/docs/zh.md) |

原文摘录：

> 原生 function calling 有三个优势。第一，提供商针对精确的调用结构进行端到端训练，使严格模式下的有效 JSON 比例升至 98%–99%。第二，调用载荷占据独立的协议位置，不混在自由文本里，因此 tool call 不会泄露到用户可见的回复中。第三，提供商通过受约束解码保证 schema 合规性（OpenAI 的 strict mode、Anthropic 的 `tool_use`、Gemini 的 `responseSchema`）。输出保证能够通过校验。

---

## Q1：用 prompt 要求模型输出 JSON 和原生 function calling 到底有什么区别？

### 一句话

- **prompt 要求 JSON**：JSON 混在普通回复文本里，模型可能写对也可能写错，由你的代码负责找出来、解析、校验。
- **原生 function calling**：工具的 schema 作为 API 参数传入，调用以单独的结构化块返回；开启 strict 后参数一定符合 schema。

打个比方：前者是让对方在聊天里口头报一张表，后者是递给对方一张有固定格子和下拉框的表让他填。

### 例子：用户说"帮我查一下明天上海的天气，用华氏度"

**做法 A：在 prompt 里要求 JSON**

```python
system = """你可以使用 get_weather 工具。
需要调用时，只输出如下 JSON，不要输出其他内容：
{"tool": "get_weather", "args": {"city": string, "unit": "celsius" | "fahrenheit"}}"""

resp = client.messages.create(
    model="claude-opus-5-5", max_tokens=1024,
    system=system,
    messages=[{"role": "user", "content": "帮我查一下明天上海的天气，用华氏度"}],
)
text = resp.content[0].text   # 拿到的只是一段字符串
```

模型可能返回：

````
好的，我来帮你查一下！
```json
{"tool": "get_weather", "args": {"city": "上海", "unit": "华氏度", "date": "明天",}}
```
````

| 问题 | 在例子里的表现 |
|---|---|
| JSON 混在自由文本里 | 前面有一句客套话，外面还包了 \`\`\`json，要靠正则抠出来 |
| 多余的末尾逗号 | `"明天",}`，`json.loads` 直接报错 |
| 虚构字段 | schema 里没有 `date` |
| 值不合规 | `unit` 应为 `"fahrenheit"`，模型写成了 `"华氏度"` |

代码只能写成"先猜位置、再试解析、失败就修或重试"：

```python
import json, re
m = re.search(r"\{.*\}", text, re.S)
try:
    call = json.loads(m.group())
except Exception:
    ...   # 修 JSON？重试？
# 还得自己检查多余字段、enum 是否合法
```

隐蔽风险：如果正则没识别出这是一次调用，整段 JSON 会作为普通回复**直接显示给用户**（即原文说的"泄露"）。

**做法 B：原生 function calling（tool use）**

```python
tools = [{
    "name": "get_weather",
    "description": "查询某城市的天气预报",
    "strict": True,                          # 开启受约束解码
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city", "unit"],
        "additionalProperties": False,       # 不允许多余字段
    },
}]

resp = client.messages.create(
    model="claude-opus-5-5", max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "帮我查一下明天上海的天气，用华氏度"}],
)
```

返回的 `resp.content` 是分开的块，`stop_reason` 为 `"tool_use"`：

```json
[
  {"type": "text", "text": "我来查一下上海的天气。"},
  {"type": "tool_use", "id": "toolu_01A...", "name": "get_weather",
   "input": {"city": "上海", "unit": "fahrenheit"}}
]
```

```python
for block in resp.content:
    if block.type == "tool_use":
        args = block.input          # 已经是 dict，无需解析
        result = get_weather(**args)
    elif block.type == "text":
        show_to_user(block.text)    # 只有 text 块给用户看
```

### 对照原文三个优势

| 原文优势 | 在例子里对应什么 |
|---|---|
| 1. 端到端训练 | 模型很少把调用写进 prose、很少用 \`\`\` 包裹（见 Q2） |
| 2. 独立的协议位置 | 调用在 `tool_use` 块里，与 `text` 块分开，按类型分发，不会误显示给用户 |
| 3. 受约束解码 | 开 `strict: True` 后每个 token 只能从合规 token 中选：`unit` 只能是两个 enum 值，`date` 生成不出来，末尾逗号不可能出现 |

### ⚠️ 原文需要更正的地方

1. **Anthropic 只有开启 `strict: true` 才是"保证通过校验"。** 普通 tool use 靠训练，可靠性很高但不是硬保证。原文把"训练"和"严格模式"混在一起：开了严格模式，合规性由解码机制保证，不是"98%–99%"这种统计数字。
2. **只保证格式，不保证内容。** 用户说"魔都"，模型仍可能填 `"city": "魔都"`，完全符合 schema 但 API 查不到。语义校验要自己做。
3. **只想要 JSON 结果、并不调用工具时**（例如抽取字段），用结构化输出参数 `output_config: {"format": {...}}` 约束最终回复，不必靠 prompt。Gemini 的 `responseSchema` 属于这一类（约束回复格式），并不是专门的 function calling 机制。
4. "5%–15% 失败率""98%–99%"原文没有给来源，只能当作大概印象。

---

## Q2：原生 function calling 的"格式靠训练"，具体是怎么训练的？

> 更正 Q1 的措辞：训练只能让错误**很少出现**，不能保证**完全不出现**；"不可能出现"要靠 strict 的受约束解码。
>
> Anthropic、OpenAI 没有公开具体训练方法。以下是业界通行做法，依据是开源模型（Qwen、Llama、Mistral 等）公开的格式和相关论文。

### 底层事实：模型输出的仍然只是 token

"独立通道"不是模型有第二个输出口，而是用**专用特殊 token** 标记调用的开始和结束。API 服务器识别这些标记，把中间内容切出来包装成 `tool_use` 块。

以 Qwen 公开的格式为例（简化）：

```
<|im_start|>system
你可以使用以下工具：
<tools>
{"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {...}, "unit": {"enum": ["celsius","fahrenheit"]}}, ...}}
</tools>
<|im_end|>
<|im_start|>user
帮我查一下明天上海的天气，用华氏度<|im_end|>
<|im_start|>assistant
<tool_call>
{"name": "get_weather", "arguments": {"city": "上海", "unit": "fahrenheit"}}
</tool_call><|im_end|>
<|im_start|>tool
{"temp_f": 72, "condition": "多云"}<|im_end|>
<|im_start|>assistant
明天上海多云，约 72°F。<|im_end|>
```

- API 的 `tools=[...]` → 被服务器渲染进 prompt（Anthropic 文档也说明会根据工具定义生成额外系统提示，并计费）
- 模型输出的 `<tool_call>...</tool_call>` → 被服务器解析成 `tool_use` 块

### 训练流程

| 步骤 | 做什么 | 解决什么 |
|---|---|---|
| 1. 固定格式 + 特殊 token | `<tool_call>` 等设为词表保留 token，普通文本切不出来 | 边界无歧义，解析不用正则猜 |
| 2. 调用轨迹数据 | 工具定义 → 用户请求 → 调用 → 工具结果 → 最终回答 | 提供"正确样子"的大量示范 |
| 3. 监督微调（SFT） | loss 只算 assistant 生成部分（loss masking） | 学会"决定调用 → 纯 JSON → 停下等结果" |
| 4. 强化学习（RL） | 可自动验证的奖励：能否解析、是否符合 schema、有没有编造工具/字段、执行后任务是否完成 | 压低剩余错误，可大规模训练 |
| 5. 评测 | BFCL（调用格式与参数正确性）、τ-bench（多轮真实任务完成率） | 衡量效果 |

**数据来源**：真实 API（如 ToolBench 抓取 RapidAPI 上的上万个接口）；强模型合成后**实际执行**、只保留跑通的样本（APIGen 等的思路）；人工标注修正。

**数据必须覆盖的情况**（不能只有"该调就调"）：
- 不需要工具 → 直接回答
- 缺必要参数 → 先追问用户，不瞎编
- 一次调用多个工具（并行调用）
- 工具报错 → 换方式重试或如实告知
- 没有合适工具 → 不编造工具

**为什么能"训掉"Q1 里的毛病**：训练数据里 `<tool_call>` 后面从不出现客套话、从不用 \`\`\`json 包裹、`unit` 永远是 enum 值，所以这些错误在模型输出分布里概率极低。

### 训练与 strict 的分工

| 层 | 作用 | 效果 |
|---|---|---|
| 训练 | 让模型**倾向于**在正确时机输出正确结构 | 格式错误罕见；同时学会该不该调、调哪个、参数怎么填 |
| 受约束解码（strict） | 生成时把不合 schema 的 token 概率置零 | 格式错误**不可能** |

- 只有训练能解决"判断"问题（调不调、调哪个、`city` 填什么），约束只管格式。
- 只有约束没有训练，模型被硬塞进陌生格式，内容质量往往下降。实际系统两层都要有。

---

## 🔁 复习自测

1. 用 prompt 要 JSON 时，最常见的四类错误是什么？各举一个例子。
2. "tool call 泄露到用户回复"具体是怎么发生的？原生 function calling 为什么能避免？
3. Anthropic 普通 tool use 和 `strict: true` 在可靠性上有什么本质区别？
4. strict 模式能保证 `city` 填对吗？为什么？
5. 只想要 JSON、不调用工具时，该用什么机制？
6. "独立协议通道"在模型层面是怎么实现的？
7. SFT 时为什么要做 loss masking？
8. tool use 为什么特别适合用 RL 训练？举出至少三种可自动验证的奖励。
9. 训练和受约束解码各解决什么问题？为什么两者都需要？

<details>
<summary>参考答案要点</summary>

1. 混在 prose/代码块里、末尾逗号等语法错误、虚构字段、值或类型不合规（enum 写成中文）。
2. 应用代码没识别出那段文本是调用，就当普通回复展示；原生方式下调用在 `tool_use` 块里，按块类型分发。
3. 普通 tool use 靠训练，概率上很可靠；strict 靠受约束解码，格式由机制保证。
4. 不能。只保证符合 schema（字符串），语义正确性要自己校验。
5. 结构化输出：Anthropic 的 `output_config.format`（Gemini 的 `responseSchema` 同类）。
6. 特殊保留 token（如 `<tool_call>`）标记边界，服务器解析成结构化块。
7. 只让模型从自己该生成的 token 学习，不去学预测用户输入或工具结果。
8. 结果可以程序化判定：能否解析、是否符合 schema、是否编造工具/字段、执行是否成功、任务是否完成。
9. 训练管"判断与倾向"，约束管"格式硬保证"；只有约束会损害内容质量，只有训练无法做到 100%。

</details>
