<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="audio-language-models-the-whisper-to-audio-flamingo-3-arc"></a>

# 音频语言模型：从 Whisper 到 Audio Flamingo 3 的演进

> Whiseper(Radford等人,2022年12月) 固定语音识别——680公里的低调多语种语言,简单 encoder-decoder transformer,一个基准,它随后每次发布 ASR 时都会引用。但是承认不是理性的。问“这段录音中有什么乐器”或“发言者表达什么情绪”或“第3分钟发生什么”需要听觉理解,而不是抄录。 Qwen-奥迪奥、萨尔蒙、LTU和NVIDIA的3号音频火烈鸟(AF3,2025年7月)逐步建造该堆:保持低语级 encoders,对 Q 源代码进行螺旋,对音频文本指示数据进行训练,添加 chain-of-thought 推理,这课会走过弧线

**类型:** Build
**语言:** Python (stdlib, 日志- 毫光谱 + 音频 Q 前骨架)
**先修要求:** 第六阶段(语音和音频),第12阶段 -03阶段(Q-前)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 从波形中计算日志- 毫秒光谱: 窗口、 FFT、 过滤库、 日志转换 。
- Compare encoder 选项:低语 encoder击球手,低调的混血儿,当他们赢了
- 创建音频 Q 前身: 可学习查询, 交叉到光谱 patches.
- 解释一下,然后...LLM与终端到终端音频-LLM 培训:为什么端到端的尺度更适合推理。

<a id="the-problem"></a>

## 问题

语音识别由Whisper解决。 OCR- Oudio是商品。 但是“ 商品” 停止在转录上。 如果模型不能解释它听到的是什么 — — 时间、 扬声器、 情感、 音乐结构、 环境声音 — — 光是抄录无法驱动产品 features.

三个明显路线:

1. 连锁:低语记录, LLM 用于纯语音情景。音乐、环境音频、多声器重叠、情感失灵。

2. 端到端的音频-LLM:一个音频 encoder feeds audio tokens 直接变成 LLM,跳过转录。保存声学信息(音频、扬声器、环境)。需要新的训练数据。

3. 混合: 音频 encoder + 文本 decoder 既能写又能讲道理 Qwen-奥迪奥和音频火烈鸟选择这条路线

<a id="the-concept"></a>

## 概念

<a id="log-mel-spectrogram-the-input-feature"></a>

### 日志- 毫秒光谱图: 输入 feature

每个音频 encoder 以相同开头 feature:对数光谱图。

1. 重标为16千赫
2. 短时间Fourier变形 25米窗户 10米跳
3. 获取FFFT结果的大小 。
4. 应用 MEL 过滤库( 通常为 80 个过滤器, 日志间距为 0-8000 Hz) 来对感知频率进行扭曲 。
5. 动态范围的日志压缩( log(1 + x) ) 。

结果: 2D 形状阵列( T, 80) , T 是时间框架数。 对于30秒的弹夹, 速率为100赫兹 框架数 : (300, 80) 。

<a id="whispers-encoder"></a>

### Whisper's encoder

Whisper's encoder 是一个12级 ViT-style transformer 将日志- 毫秒光谱图作为时间框架的序列处理。 输出: 每个时间框架隐藏一个矢量 。

给ASR,Whisper decoder 是一个 cross-attention transformer 生成文本 tokens 以 encoder 输出。标准 encoder-decoder.

用于ALMs(奥地利-LLMs,你想要的, encoder 输出为输入到不同的 LLM模式: encoder 冻着的,Q型可训练的, LLM 冻着或调动。

<a id="beats-and-audio-specific-encoders"></a>

### BET和音频专用 encoders

Whisper是语言主导数据的培训对象,音乐和环境音频则较弱。

BEATs(Chen等人,2022年)是自律的 transformer 听音乐和环保声音比低语好 parameter count.

AF-Wiper(Audio Flamingo 3的混合体):口哨+BEAT features Whisper传递语言信号,BEAT传递声信号

<a id="audio-q-former"></a>

### 音频 Q 前

与 BLIP-2 的视觉Q前端相同。 固定数量的可学习查询( 通常为 32 或 64) 。 encoder输出框。 查询成为 audio tokens 消费 LLM.

Training alignment 阶段:单是Q-前端,反向+音频文本对口的字幕损失(AudioCaps, Clotho)。 LLM训练教学数据

<a id="the-arc--salmonn-qwen-audio-af3"></a>

### 弧度——萨尔蒙, Qwen-奥迪奥,AF3

SALMONN(Tang等人,2023年):低语+BEATs+Q-前+ LLaMA第一个打开的音频LLM 有关MMAU的基准显示,该模型的复合度为0.55。

Qwen-Audio(Chu等人,2023年):类似的结构,经过较丰富的数据集培训,为多方向对话调制。

LTU——倾听、思考、理解(Gong等人,2023年):明确推理数据,重点是 chain-of-thought 音频剪辑上,小点但重点更突出

3号音频火烈鸟(Goel等人,2025年7月):目前开放的SOTA. 8B LLM 骨干(wen2 7B),低语 encoder 与BEAT对等,64号口令Q-ex,1M+音频文字教学对等培训。MMAU 0.72与某些子任务中专有边界匹配。

AF3还按需介绍 chain-of-thought 音频: 模型可以可随意发布思维 tokens ("让我先指出乐器:") 在最后答案之前。 复杂的推理任务精确度在思考被允许时会提升3-5点。

<a id="cascaded-vs-end-to-end"></a>

### 连锁和终端到终端

连锁输油管:

1. 语音记录音频 / 文本。
2. LLM 原因超过文本。

完美地为"总结这个播客"工作。
- 音乐中的气氛是什么?
- 是谁,爱丽丝或鲍勃?
- 爆炸发生在什么秒? grounding 丢失在文本中。
- ”这是真音还是假音?“——深假探测需要声学。 features.

端对端保存声波信号。 Qwen-奥迪奥和AF3 处理音乐,环境和情绪

<a id="2026-production-recipe"></a>

### 2026年生产配方

对于新音频理解产品:

- 折叠式: 抄录是目标, 没有音乐,没有情感 inference.
- FF3/ 编号 Qwen- 听家,如果: 音乐,情感, 多声器,或复杂的音频推理。

连锁店更便宜,更简单 端对端更能干

<a id="mmau--the-audio-reasoning-benchmark"></a>

### MMAU——音频推理基准

MMAU(大规模多式音频理解)是2024-2025年音频推理基准:

- 10000个音频文本的QA对 横跨语言,音乐,环境声音。
- 涵盖分类、时间推理、因果推理、无限制质量评估。
- 测试连锁管道系统失灵之处。

0.72时开放SOTA(AF3);专利边界~0.78(Gemini 2.5 专业, Claude 差距小于视频MME的开放版三角形,显示音频-LLMs 正在成熟。

```figure
audio-text-ctc
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 执行对日志- 兆位光谱计算, 以标准lib 方式: 窗口、 幼稚的 DFT、 梅尔过滤器银行 。
- 音频 Q 前骨架: 给定 encoder 输出框,计算 Q, K, V, attention,并发布N tokens.
- 玩具任务上连锁比对

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-audio-llm-pipeline-picker.md`。根据音频任务(调制、音乐标记、情感) inference,多声带对称、环境分类),它选取级联、终端到终端的AF3或混合型。

<a id="exercises"></a>

## 练习

1. 计算一个 16 kHz, 25 ms 窗口, 10 ms hips, 80 mel bins 30 秒的剪辑的日志- 毫光谱维度。 在 48 kHz 中如何改变 ?

2. 为什么小声会听音乐? features 贝特斯捕捉到Whisper没有吗?

3. 音频 Q 前端, 64 个查询对 32 个: 64 个复杂任务能有什么回报? 32 个另算什么?

4. 阅读AF3第4节,即时思考。 chain-of-thought 帮得最多

5. 使用 AF3 输出, 执行最小的二分化管道。 您如何信号扬声器变化 ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 日志光谱 | "Mel features" | 梅尔过滤器库后2D(时间、频率)对数放大值阵列 |
| 音频 Q 前 | 帕西韦尔 | Cross-attention 音频瓶颈 encoder 输入 LLM |
| Cascaded | "ASR-then-LLM" | 语音记录和文字的管道 LLM 原因; 丢失音频信息 |
| End-to-end | "Audio-LLM" | Audio features 输入 LLM 直接通过 Q- exe 保存音频信号 |
| 节拍 | "Audio音频节目 encoder" | SSL transformer 音乐节目培训;音乐+环境声音强 |
| MMAU | 听力推理长椅 | 10k 配对的质量保证,横跨语言、音乐和环境;2024年的反弹标准 |
| 随要求思考 | "奥迪奥・科特" | 模式可以任选推理 tokens 在最后回答之前, 提高准确度 3-5 pts |

<a id="further-reading"></a>

## 进一步阅读

- [Radford等人——Whisper(arXiv:2212.04356)](https://arxiv.org/abs/2212.04356)
- [楚等人- Qwen-奥迪奥(arXiv:23110.7919)](https://arxiv.org/abs/2311.07919)
- [Goel等人——音频火烈鸟3号(arXiv:2507.08128)](https://arxiv.org/abs/2507.08128)
- [唐等人——萨尔蒙特(arXiv:2310.13289)](https://arxiv.org/abs/2310.13289)
- [贡等人-LTU(arXiv:2305.10790)](https://arxiv.org/abs/2305.10790)
