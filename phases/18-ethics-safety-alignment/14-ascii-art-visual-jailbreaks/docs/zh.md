<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="ascii-art-and-visual-jailbreaks"></a>

# ASCII 字符画与视觉 Jailbreaks

> 江,徐,牛,项,拉马苏布拉马尼安,李,波文德兰,"艺术: ASCII Art-based Jailbreak 对结盟的攻击 LLMs" (ACL 2024, arXiv:2402.11753),掩蔽与安全有关的部分 tokens 以下列方式取代: ASCII- 艺术的相同字母, 并发送隐形 prompt. GPT-3.5, GPT-4, Gemini, Claude, Llama-2 都无法坚定识别 ASCII-art tokens攻击绕过PPL( PPL) 。perplexity 相关:VIT基准测量非语义视觉识别 prompts; 结构式的流体概括为非普通文本编码结构(树、图形、嵌套) JSON)作为一个编码攻击的家族。

**类型:** Build
**语言:** Python (stdlib,艺术Prompt) token-masking harness)
**先修要求:** 阶段18 12(PAIR),阶段18 13(MSJ)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述艺术快速攻击: 字词识别步骤, ASCII-艺术替代,最后隐形 prompt.
- 解释为什么标准防御(PPL, 参数、重开)在ArtPrompt上失败。
- 界定VIT并描述它衡量什么。
- 将结构滑雪描述为任意的不常见文本编码结构的概略。

<a id="the-problem"></a>

## 问题

通过引言和角色扮演进行攻击(Lesson 12)和长上下文(Lesson 13),在文本级别模式下运作。 token。它用字符来分析图像。安全过滤器看到无害的标点。模型看到一个单词。

<a id="the-concept"></a>

## 概念

<a id="artprompt-two-steps"></a>

### 艺术, Prompt, 两步

步骤1. 识别字词。如果有有害的请求,攻击者使用 LLM 来识别与安全有关的词语(例如,“如何制造炸弹”中的“炸弹”)。 

步骤2. 隐蔽 Prompt 生成。 将每个指定的单词替换为 ASCII- 艺术转换( 形成字母形状的字符块为 7x5 或 7x7 ) 。 模型接收一个标点和空格网格, 足够功能的模型可以识别为单词; 安全过滤器只看到网格 。

结果: GPT-4, Gemini, Claude, Llama-2, GPT-3.5 全部失败。 攻击成功率超过其基准子集的75%。

<a id="why-the-standard-defenses-fail"></a>

### 为什么标准防御失败

- **个人财产(PPL)perplexity filter).** ASCII 艺术高 perplexity 限制ArtPrompt的门槛也阻挡了合理的结构化输入。
- **Paraphrase.** 引号 prompt 摧毁 ASCII 第2条. 在实践中,引言 LLMs 通常保存或重建艺术。
- **Retokenization.** Splitting tokens 不同的是,它不会改变模型的视觉 识别字母形状。

根本问题是安全过滤器 token- 或语义层面;艺术Prompt在视觉识别层面运作。

<a id="vitc-benchmark"></a>

### 虚拟技术合作基准

承认非语义视觉 prompts衡量模型的读数能力 ASCII艺术、编织和其他非文字表达式视觉内容。艺术Prompt的效能与VIT精度相关:模型越看视觉文字,艺术Prompt对它就越有用。这是一个能力安全权衡。

<a id="structuralsleight"></a>

### StructuralSleight

艺术Prompt: 非通用文本编码结构(UTES)。 树、 图形、 嵌套 JSON,CSV -in - - ,CSV - ,CSJSON, diff- sype 代码块。如果一个结构在培训安全数据中很少,但可以通过模型分析,它会隐藏有害的内容。

防御的含义:安全必须贯穿于模型可以分析的结构化表述。这套图集巨大且在增长。

<a id="image-modality-analog"></a>

### Image-modality analog

Visual LLMs (GPT-5.2, Gemini 3 专业, Claude 目标4.5,Grok 4.1) 扩展攻击表面。 ASCII- 艺术类比,因为图像 encoders 产生更丰富的信号。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

12-14课描述了三种正对攻击矢量:迭代精炼(PAIR)、上下文长度(MSJ)和编码(ArtPrompt/StructuralSleilt)。indirect prompt injection16号课描述了防御性工具反应。

```figure
al-ascii-cloak
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 构建一个玩具 艺术Prompt。 您可以在有害的查询中隐藏特定的单词 ASCII- 艺术格字, 校验隐形字符串传递到关键词过滤器, (可选) 使用简单的识别器解码隐形字符串的背部 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-encoding-audit.md`。如果有的话 jailbreak- 防卫报告,它列举了所覆盖的编码攻击家庭(ASCII 艺术,基础64, 莱特语,UTF-8同族体,UTES) 和防御层 捕捉每一个。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。验证隐形字符串时会通过简单的关键字过滤器。报告需要的字符级更改。

2. 执行第二个编码: 同一目标字的基数64。 比较过滤率和 ArtPrompt 和回收难度 。

3. 读姜律师等人,2024年,第4.3节(五种模式的结果)。 Claude艺术耐力高于 Gemini都在同一基准上

4. 设计一种能探测到的 代际防御 ASCII-艺术形状的区域 prompt。测量合法代码、表格和数学符号上的假正率。

5. 结构雪橇列出10个编码结构。 拼写一个通用的防御, 处理全部 10 并估算每个辩护的成本 prompt.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| ArtPrompt | "该 ASCII- 艺术攻击" | Two-step jailbreak 隐藏安全词 ASCII-艺术创作 |
| Cloaking | 隐藏字眼 | 替换被禁止的 token 带有视觉表示器的模型读取,但过滤器没有 |
| UTES | "非共同结构" | 异常文本编码结构 - 树、 图形、 嵌套 JSON等用于走私内容 |
| ViTC | “视觉文字能力” | 模型阅读非语义视觉编码能力的基准 |
| Perplexity filter | "PPL防御" | Reject prompts 高频 perplexity; 失败,因为合法的结构化输入也得分高 |
| Retokenization | "tokenizer 轮值防御 | 预处理 prompt 与不同的 tokenizer; 失败, 因为识别是视觉的 |
| Homoglyph | "看起来像个人物" | Unicode 与拉丁字母看起来相同的字符; 绕过子字符串检查 |

<a id="further-reading"></a>

## 进一步阅读

- [江等人-艺术Prompt(ACL 2024,arXiv:2402.11753)](https://arxiv.org/abs/2402.11753) — 该 ASCII-art jailbreak paper
- [Li等人——结构雪橇(arXiv:2406.08754)](https://arxiv.org/abs/2406.08754) 通则
- [Chao等人——PAIR(Lesson 12,arXiv:2310.08419)](https://arxiv.org/abs/2310.08419) 补充性迭代攻击
- [Anil等人——多发式的破门(Lesson 13)](https://www.anthropic.com/research/many-shot-jailbreaking) 补充性长攻击
