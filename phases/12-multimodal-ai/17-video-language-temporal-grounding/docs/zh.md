<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="video-language-models-temporal-tokens-and-grounding"></a>

# 视频语言模型：时间 Tokens 与 Grounding

> 视频不是一堆照片。 5秒的剪辑含有因果顺序、 动作动词和事件时间, 而图像模型无法代表 。 Video-LLaMA (Zhang等人,2023年6月)发运了第一个公开视频-LLM 带有音频-visual grounding。视频目录和视频 LLAVA 缩放模式。 到 2025 年 Quen2.5- VL 的 TMROPE 缩小了与边际专利模型的缺口。 每个系统都解决了时间问题 tokens 不同——每段Q-前,每段Concat-pool,每段TMROPE token。这个课读取图案,建立一个统一的Vs-动力框架取样器,并根据时间进行评估 grounding tasks.

**类型:** Build
**语言:** Python (stdlib, 框架取样器+时间-)grounding evaluator)
**先修要求:** 阶段12 · 08(LLAVA-One Vision)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么时间位置编码会改变视频 VLM 的性能, 而不取决于视觉 encoder.
- 比较统一、动态-FPS和事件驱动的框架 sampling 在 tokens- 每秒对齐 grounding accuracy.
- 描述 Q 前每页( Video-LLaMA与集合框架(Video-LLAVA)与M-RoPE-每-token (Quen2.5-VL)设计。
- 列出四个视频基准:视频MME、TempCompas、Egoschema、视频MMMU。

<a id="the-problem"></a>

## 问题

30台FPS的1分钟视频为1800框架。 tokens 每个框架(ViT-B 224,是352k(约合352k) tokens 大于2024年的 LLM context.

现有三项削减战略:

1. 子抽样框架(根据内容而定,1-8个FPS)。
2. 集合每个框架 patch tokens 积极(3x3或4x4双线性池)
3. 通过需要16个框架的剪辑和输出的 Q-ex 压缩 tokens.

每一次交换都是不同的。 子抽样会丢失时间细节。 合并会丢失空间细节 。 Q- eight 会同时丢失一些但会节省 tokens.

时间位置编码是另一个轴:模型如何知道框架5出现在框架6之前?选项包括简单的 1D 时间 RoPE (Video-LLaMA),学习时间 embeddings 高频电话(Video-LLAVA)和高频电话(Quen2.5-VL,全立方公尺)。

<a id="the-concept"></a>

## 概念

<a id="video-llama-q-former-per-clip--audio-branch"></a>

### Video-LLaMA:每段Q- 前端数 + 音频 branch

Video-LLaMA (2023年)是第一个公开的视频LLM结构 :

- 2支FPS(约8秒)的16号弹夹。
- Per-frame ViT features - > 在所有16个框架交叉上传的视频Q前身 - > 32个已学习查询 - > LLM.
- 平行音频 branch: 波形 - > 图像光度音频 encoder - > 音频 Q-前端 - > 32个查询 - > LLM.

优点:视听联合推理。弱点:固定剪辑长度,没有任意的时间 grounding.

<a id="videochat-and-video-llava"></a>

### 视频域名和视频LLAVA

视频Chat保存了视频-LLaMA 视频-LLAVA (Lin等人,2023年) 培训了一个单一的视觉 encoder 图像和视频框上alignment 两者都是冻结的 CLIPencoder + MLP+ 组合键 LLM.

都不用长视频,都是8-16框架系统

<a id="qwen25-vl-and-tmrope"></a>

### Quen2.5-VL和TMROPE 系统

Qwen2.5-VL 引入TMRoPE——时间Modality 旋转位置 Embedding. 每个 patch token 带有 t, h, w) 位置, t 是实际时间戳( 不是框架索引)。

简单时间的关键差异 embedding:

- 绝对时间,不是索引。模型看到的是“4.2秒”,而不是“15号框”。
- Per-token 旋转, 不是每个剪切。 每个视觉 token 以时间戳独立旋转。
- 与动态 FPS 兼容。 如果您在这里的 2 FPS 和那里 4 FPS 进行抽样, TMROPE 将处理本地间距不均的情况 。

TMROPE 启用“ 猫跳到什么秒” 查询。 模型可以在“ 4. 2 秒内输出 ” 。 视频LLaMA 只能说"早点在弹夹里"

<a id="frame-sampling-strategies"></a>

### Frame sampling strategies

统一: 样本N框架平均时间长度。 简单, 失去运动峰值 。

动态 FPS: 基于运动强度的样本。 光学流或框架差异为密度更高者选择高振动区块 sampling上面有25万伏特加火车

事件驱动: 运行轻量级探测器, 更多在动作发生时进行取样。 由视频代理使用 。

键框架 + 上下文: 在射击边界和几个相邻框上取样。 用于电影内容 。

<a id="pooling-per-frame"></a>

### 每个框架集合

1个FPS和576个 tokens 每个框,5分钟的剪辑是172 800 tokens。与 Quen2.5-VL-72B 的128k 相上下文相容但成本昂贵。

3x3双线池减至64 tokens 每个框架 - > 19 200 tokens 5分钟,大部分任务都不错

更积极的游泳池(6x6 - > 16) tokens /每个框架) agent 空间细节不重要的工作流程。

<a id="the-four-video-benchmarks"></a>

### 四个视频基准

- 视频MME:全面视频理解,短+中+长。
- TemperCompuls: 细微的时空推理, “ 之前” /“ 之后” 问题。
- Egoschema:长象第一人称视频。
- 视频-MMMU:多式多纪律视频问题。

完整视频- VLM evaluation 点击所有四个。他们强调不同的轴——TempCompax是所有关于订购,EgoSchema是三分钟加一分钟的推理,视频MME横跨持续时间。

<a id="grounding-output-formats"></a>

### Grounding 输出格式

时间输出格式 grounding:

- 免费的文字:“猫在四秒内跳动。”很容易分析,但很不精确。
- Structured JSON: `{"event": "jump", "start": 4.1, "end": 4.3}`昆古力 -VL训练这个
- Token- 基础:特别 `<time>4.1</time>` tokens 与答案隔开。 Quen2.5- VL 的内部格式 。

Token- 基点对下游使用最准确。 JSON 输出格式切换。

<a id="2026-best-practice"></a>

### 2026年最佳做法

2026年的录像VLMS:

- Encoder: SigLIP 2 带 M -RoPE 或TMRoPE (Qwen2.5-VL)。
- Frame sampling:动态FPS(1-4视运动而定),最大尺寸上限。
- 每架集合: 3x3双线。
- 产出:结构 JSON 与时间+事件字段相匹配。
- 基准:一般视频MME+Temprogass;长方位Egoschema。

```figure
video-temporal-patches
```

<a id="use-it"></a>

## 实际应用

`code/main.py` includes:

- 统一和动态FPS框架取样器。
- 玩具时间-grounding 评估员:给时间 T 的“ 地面真相” 事件和一个模型输出, 以容忍度来评分准确性 。
- 视频对比LLaMA (16 框架,Q 前),视频-LLAVA(8 框架,MLP),Quen2.5-VL(动态FPS+TMROPE)。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-video-vlm-frame-planner.md`。如果视频任务(监测、行动识别、时间) grounding,总和),它选择框架取样器、集合系数、输出格式和预期精度级。

<a id="exercises"></a>

## 练习

1. 3分钟的烹饪演示,选制服和动态FPS。 token count.

2. TMROPE 添加了具体什么,即简单的时间 embedding 桌子不能吗?

3. 写一个 JSON 时间图 grounding 显示 VLM 可以学会排放。 包含错误案例 。

4. 阅读视频- LLAVA第3节关于 "Alignment 为何这比训练分开的图像和视频更好? encoders?

5. 鉴于视频MME 头版, 顶层开放模型和顶层专利模型之间自2026年以来的差别有多大? LLM scale?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Temporal grounding | "时间定位的答案" | VLM 输出事件发生时的具体时间戳范围 |
| TMRoPE | "Time-Multimodal RoPE" | 3D 旋转位置,带有绝对时间戳, Qwen2.5-VL 使用 |
| 动态 FPS | "Motion-aware sampling" | 在高振动区段取样更多,静态区段较少 |
| 框架共享 | "每个框架的空间压缩" | Reduce patches 以双线内插法 LLM |
| 视频Q前 | "剪贴压缩机" | Cross-attention 向 K 学习查询的 N 框架映射瓶颈 |
| VideoMME | "维多长椅" | 全面短/中/长视频基准,2 500+样本 |

<a id="further-reading"></a>

## 进一步阅读

- [张等人——录像LLaMA (arXiv:2306.02858)](https://arxiv.org/abs/2306.02858)
- [Li等人——视频聊天(arXiv:2305.06355)](https://arxiv.org/abs/2305.06355)
- [Lin等人——视频LLAVA(arXiv:2311.10122)](https://arxiv.org/abs/2311.10122)
- [Qwen 工作队-Quen2.5-VL(ARXiv:2502.13923)](https://arxiv.org/abs/2502.13923)
- [Lin等人-VILA-1.5(arXiv:2312.07533)](https://arxiv.org/abs/2312.07533)
