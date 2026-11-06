<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="long-video-understanding-at-million-token-context"></a>

# 百万 Token 上下文中的长视频理解

> 24个FPS的1小时4K视频,修补和嵌入,制作约6 000万 tokens3万个2小时播客插曲 tokens。全蓝光 feature 胶片,甚至压缩 与侵略性的池子, 是数十万 tokens。 Google 的 Gemini 1.5 (2024年3月) 开启了这个时代,token 现场拍摄了一小时长的视频。 attention缩放路径。 LongVILA 和 Video- XL 进一步缩放摄取。 VideoAgency 将原始环境转换为 agentic 检索。 每种方法在计算、 回忆和工程复杂性上都是不同的权衡。 这个课程可以同时阅读它们。

**类型:** Build
**语言:** Python (stdlib, 针头在哈伊斯塔克模拟器+) agentic- 检索路由器)
**先修要求:** 阶段12 · 17(录像时间) tokens)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 计算全部视觉-token 计为各种FPS和集合的长式视频。
- 解释三个缩放路径:粗糙的上下文( A)Gemini 编号 1.5,环 attention (LWM), token 压缩 (LongVILA/ Video- XL)
- 比较原始文本视频 VLMs 和s agentic- 检索视频VLMS(视频代理),关于准确性和延迟性。
- 设计一个针头在Haystack测试 30分钟视频和测量回溯 在特定分钟。

<a id="the-problem"></a>

## 问题

单边的 Quen2.5-VL 大小 patches 340 本地分辨率为~729 tokens3x3 集合点是81 tokens 30分钟的剪辑,1 FPS=1 800框架=145 800 tokens2025年前可打开VLMs,紧凑。 tokens - 最合适的环境

电影2小时,在1FPS是583k tokens超过大多数2026年开放模式;要求 Gemini 2.5 更积极或集中。

出现了三条缩放路径。

<a id="the-concept"></a>

## 概念

<a id="path-1-brute-context-gemini-15-claude-opus"></a>

### 路径1:布鲁特上下文(Gemini 1.5, Claude Opus)

丢弃硬件解决问题。 缩放上下文到百万个 tokens,将所有东西放在一起处理 forward pass.

Gemini 1.5 使用1M发射的推进器 tokens; Gemini 1.5 超升至10M; Gemini 2.5 2026年的试验用时可靠,纸张(arXiv:2403.05530)记录针头在Haystack中回溯99.7%,最高可达~9.5M。 tokens.

工程:一种习惯 attention 执行内存等级( 本地+全球+稀有)加 MoE 专家路线, 以获取长文本效率。 未全部发布 。 非公开源代码 。

<a id="path-2-ring-attention-lwm-longvila"></a>

### 路径2:环 attention (LWM, 长VILA)

Ring attention 将长序列分布在设备之间的“环”中,每个设备都持有块。 Attention 在整个序列中,每个设备在环状图案中将其块发送到下一个时段,计算部分 attention并汇总。

LWM(Liu等人,2024年)培训了1M-token 培训用上下文而不是四边形来计算尺度,四边形以 attention 被摊销过环的装置。

LongVILA(arXiv:2408.1018)将图案改制为1400框架视频,共192次 tokens =268k环境,受过环形训练 attention 横跨8线平行

<a id="path-3-token-compression-video-xl-longva"></a>

### 路径 3 : Token 压缩( Video- XL, LongVA)

便宜于野蛮背景:在 LLM 看见序列。

视频- XL (arXiv: 2409. 14485) 使用视觉摘要 token:N框架的每个剪辑都产生一个“摘要” token 上北北北北北北北北北北北北北北北北北北北北北北北北北北北 inference, 该 LLM 见一份摘要 token 每一段, 急剧缩小了上下文。

长VA 延伸 LLM 上下文为200公里至2米,具有“长背景传输”技术。

Token 压缩转换为可缩放性的具体时间戳。 模型一般知道发生了什么,但有时却忽略了准确的框。

<a id="path-4-agentic-retrieval-videoagent"></a>

### 路径 4 : Agentic 检索( VideoAgent)

不要将全部视频反馈到 LLM。相反,将视频作为数据库使用 LLM 查询。

视频代理( arXiv: 2403.10517):

1. LLM 读到这个问题。
2. LLM 要求相关剪辑的检索工具 (“ 用猫给我显示片段 ” ) 。
3. 工具返回匹配剪切时间戳 。
4. LLM 透过VLM读取这些剪辑
5. LLM 构成答复或询问后续问题。

这是 LLM-作为-agent 适用于长视频的图案。 inference 更坚固的工程(回收质量成为瓶颈)。

<a id="needle-in-a-haystack-benchmarks"></a>

### 针头在海雀中的基准

标准长文本测试: 在视频的随机点插入一个独特的视觉或文字标记, 然后询问需要回溯的查询 。

Metric: Recall@k 穿过视频长度和标记位置。

Gemini 2.5 30分钟内,在90分钟的视频中,准分 > 99%回响。打开72B模型(Quen2.5-VL-72B, InternVL3-78B)分到~85-90%,并降低到60。

视频代理可以在2+小时匹配或击败原始文本模型,因为如果工具好的话,检索会击中针头。

<a id="which-path-to-pick"></a>

### 选择哪条路

15分钟的外缘精度:打开72B+本地环境通常有效。

30分钟至1小时内容:开放长视或视频XL; Gemini 2.5 关闭,质量条条很重要——边界关闭。

2小时加1小时的内容:视频代理或类似的检索模式。或者,将数据摘要汇总为小块并输入分级摘要。

<a id="2026-production-pattern"></a>

### 2026年生产模式

实际上,生产长视频管道是混合的:

1. 运行动态- FPS sampling + 在整个视频上进行积极的集合(获得100公里-token )全球代表性)。
2. 将全球摘要转至72B VLM。
3. 如果用户询问详细问题,请运行 agentic 使用摘要作为索引检索 。

这结合了全球理解的粗略文字和当地细节的检索。

```figure
mm-video-token-budget
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- Computes token budgets 视频,从1分钟到3小时,在不同FPS+共享。
- 模拟针头在哈伊斯塔克运行:在随机时间戳上打标记,提问,记分。
- 包括a agentic- 回收路由器模拟器, 提取特定的剪辑, 供下游VLM 使用。

运行预算表,感受规模差距。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-long-video-strategy-planner.md`。鉴于视频持续时间和查询的复杂性,它选择了粗略文字、压缩和 agentic 检索,计算潜伏值+质量预期值。

<a id="exercises"></a>

## 练习

1. 1个联邦公共服务局,81个45分钟的讲座 tokens 每个框架。 tokens适合哪一种模型?

2. 设计针头在Haystack测试: 你什么时候注射标记, 以及确切的查询格式?

3. 将粗体文字 Quen2.5-VL-72B (80k 上下文) 与视频代理(Claude 3⁄5 + 检索) 在一个一小时的视频上。 哪个在回想中获胜? 哪一个在潜伏中获胜 ?

4. Ring attention内存以线性速度计算, 以序列长度计算, 并在设备计数中以线性速度计算。 如果您放弃环状旋转阶段, 请解释原因和失败之处 。

5. Read Gemini 1.5 第5节,针头在海斯达克。 token boundary?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 布鲁特语背景 | "只是更多, tokens" | Scale LLM 环境对数百万个 tokens; 在一个通道中处理所有信息 |
| Ring attention | LWM 风格的平行 | Distributed attention 模式,每个设备都持有块并旋转 |
| Token compression | "Summary tokens" | 减少每页 tokens 透过一个学问的压缩机 LLM |
| Needle-in-haystack | NIH测试 | 在随机点插入一个独有的标记, 请模式在测试时提醒它 |
| Agentic retrieval | "LLM 用作查询计划" | LLM 要求相关剪辑的检索工具, 通过 VLM 读取, 组成答案 |
| VideoAgent | "视频检索模式" | Canonical agentic- 检索设计:问题 - > 工具 - > 剪辑 - > 回答 |

<a id="further-reading"></a>

## 进一步阅读

- [Gemini 团队 - Gemini 1.5(arXiv:2403.05530)](https://arxiv.org/abs/2403.05530)
- [刘等人——LWM/RingAtention(arXiv:2402.08268)](https://arxiv.org/abs/2402.08268)
- [薛等人——长寿(arXiv:2408.1018)](https://arxiv.org/abs/2408.10188)
- [Shu等人——视频XL(arXiv:2409.14485)](https://arxiv.org/abs/2409.14485)
- [王等人——录像代理(arXiv:2403.10517)](https://arxiv.org/abs/2403.10517)
