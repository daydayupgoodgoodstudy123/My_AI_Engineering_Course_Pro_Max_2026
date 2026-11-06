---
name: skill-concept-prompt-designer
description: Turn user utterances into well-formed SAM 3 concept prompts with splitting, disambiguation, and fallbacks
version: 1.0.0
phase: 4
lesson: 24
tags: [sam3, open-vocab, prompt-engineering, segmentation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="concept-prompt-designer"></a>

# 概念 Prompt 设计师

SAM 3 的准确性在很大程度上取决于 prompt 概念的表述方式。此技能将自由格式的用户话语标准化为 SAM 3 可以很好处理的 prompts。

<a id="when-to-use"></a>

## 何时使用

- 构建接受自然语言对象查询的 UI。
- 通过上游调用者发送句子的 API 公开 SAM 3。
- 调试较差的 SAM 3 匹配 — 通常是 prompt 格式错误，而不是模型错误。

<a id="inputs"></a>

## 输入

- `utterance`：原始用户字符串。
- `context`：可选域提示（例如“监视”、“医疗”、“零售”）。
- `max_concepts`：每个话语提取的最大概念；默认 5。

<a id="rules-sam-3-prefers"></a>

## SAM 3 更喜欢的规则

- **简短的名词短语，而不是句子。** `"cat"` 胜过 `"there is a cat"`。
- **具体名词。** `"skateboard"`胜`"thing to ride on"`。
- ** 紧邻名词之前的修饰符。** `"red car"` 胜于 `"car that is red"`。
- **Lowercase.** SAM 3 很强大，但根据经验，在小写输入上稍好一些。
- **单数或复数。** 两者都有效；当需要多个实例时，复数会有所帮助。

<a id="steps"></a>

## 步骤

1. ** 通过常用分隔符进行标记** — 逗号、分号、“and”、“or”、“&”。
2. **删除填充前缀** —“查找”、“显示”、“分段”、“检测”、“定位”、“a”、“an”、“the”。
3. **仅在可见时保留介词修饰符** - `"striped red umbrella"` 是，`"umbrella from yesterday"` 否（`"from yesterday"` 不在图像中）。
4. ** 使用可选的 `context` 消除冲突 **：
   - 监视上下文中的 `"window"` -> `"building window"`。
   - `"window"` 在医疗领域 -> 经常出错；建议用户澄清。
5. **Fallback** 如果拆分产生零个概念，则返回到确切的字符串 * 和 * 话语包含至少一个具体名词。如果无法提取具体名词，则不要发出概念 - 仅返回警告并要求用户澄清（请参阅规则）。
6. **Cap at `max_concepts`.** 如果提取的概念多于调用者要求的概念，则按话语顺序保留第一个 `max_concepts` 并在 `dropped` 下发出 rest原因是 `"exceeded max_concepts"`。当用户粘贴长枚举时，这可以限制延迟。

<a id="output-format"></a>

## 输出格式

```
[designed prompts]
  utterance:    <original>
  concepts:     ["concept_1", "concept_2", ...]
  dropped:      ["filler_1", ...]
  warnings:     ["concept too abstract", "may match many classes", ...]

[sam3 calls]
  For each concept run: sam3.detect(image, concept)
  Merge outputs with distinct concept tags per detection.
```

<a id="examples"></a>

## 示例

```
in:  "can you find me a cat or two dogs?"
out: ["cat", "dogs"]
dropped: ["can you find me", "a", "or two", "?"]
note: "dogs" kept plural because the utterance says "two dogs" — plural hint preserved.

in:  "segment the big red truck and the blue sedan"
out: ["big red truck", "blue sedan"]
dropped: ["segment", "the", "and"]

in:  "thing near the door"
out: ["door"]
warnings: ["'thing' is too abstract for SAM 3; fell back to 'door'"]

in:  "striped red umbrella, green hat, pink balloon"
out: ["striped red umbrella", "green hat", "pink balloon"]
```

<a id="rules"></a>

## 规则

- 切勿将超过 8 个单词的句子传递给 SAM 3 — 准确度会低于此值。
- 当话语不包含可提取的具体名词时，不要运行 SAM 3；返回警告并要求澄清。
- 不要根据带引号的字符串内的标点符号进行拆分；如果引用 `"black and white cat"`，则将其保留为一个概念。
- 始终记录原始话语和派生概念以进行生产调试。
