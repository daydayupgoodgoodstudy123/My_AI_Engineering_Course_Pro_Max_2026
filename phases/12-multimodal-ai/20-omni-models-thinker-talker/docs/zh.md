<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="omni-models-qwen25-omni-and-the-thinker-talker-split"></a>

# 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工

> GPT- 2024年5月的4o产品演示不是因为基本模型,而是因为产品形状——一个声音界面,你说话,模型看到相机所看到的,它在250米以下就回话。开放生态系统用的是这些声音。 rest Quen2.5-Omni (2025年3月)是参考开放式设计:一个思想家(大型文字生成者) transformer加上一个朗读者(平行的发声器) transformer),由 streaming speech tokens。 Mini-Omni 简化了它, Moshi 匹配了它的潜伏, GLM-4-Voice 将其扩展至中文。 这个课程读到思想- 陶尔克建筑和潜伏预算 streaming 实时对话工作。

**类型：** 构建
**语言:** Python (stdlib, streaming 管道延缓模拟器 + VAD 循环)
**先修要求:** 阶段12 - 19(奥地利-LLMs阶段12 16(任何)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 拆开 inference 编导成“思考者”(文字推理)和“朗读者”(语音合成),并解释为什么平行 streaming works.
- 按构成部分计算对话互动的时间到第一段落(TTFAB)预算。
- 描述 TMROPE 在思想家内部的视觉、音频和文字之间的时间匹配位置编码 。
- 列出三种实时对话模式:半迷半迷,转弯,完全迷糊。

<a id="the-problem"></a>

## 问题

实时语音助理必须做很多,快速:

1. 倾听用户的声音。 tokenization语音活动检测(VAD),以了解他们何时发言。
2. 也可以看到。摄像头输入 2 -4 FPS, 与音频一起流到思想家。
3. 想想看,根据谈话历史做出回应
4. 说吧,合成 audio tokens,解码到波形,流到用户的扬声器。

每一步都增加延缓度。 沟通感需要总回程 < 500米 - - - 低于500米 - - 用户停止注意时滞 。 GPT-4个单位声称有约250米,莫希~160米,昆古尼~350到500米。

每一个部件都需要流出,没有什么可以"打乱一切然后解码。"

<a id="the-concept"></a>

## 概念

<a id="thinker-and-talker"></a>

### 思想家和说话者

昆古力 -奥米尼的分解:

- 思考者:7B-80B 生成文本 transformer。将断开的文本和图像合并为 audio tokens产出文本 tokens 代表什么说。
- 朗读者:一个较小的演讲 transformer (200M-1B) 计算思想家的文本输出 tokens 加上最近的演讲文字 tokens。 产出独立演讲 tokens (原VQ指数)。
- Speech decoder: 一个 streaming waveform decoder (SNAC,MoVQGAN家庭) 发言 tokens 实时到音频样本。

分离很重要,思考者必须大点才算好。说者可能小点,因为其工作是本地的,将文字转换成语言 tokens。 大话人没有更直白的表达力,而是慢。

双向运行 :

1. 思想家发布文本 token t_i.
2. Talker 读取 t_i（通过 streaming），并输出语音 tokens：s_i、s_{i+1}、…、s_{i+k}。
3. Speech decoder 消耗演讲 tokens 因为他们来时会发出声音样本
4. 等到思强在文字上 token t_{i+3}, 朗读者已经为 t 流出音频_0..t_{i+2}.

<a id="tmrope--time-aligned-multimodal-positions"></a>

### TMROPE——符合时间的多式联运立场

思考者需要整合图像框架(比如 4 FPS ) 、 音频框架( 以50 框架/ 秒 递增) 和对话历史文本。 一个天真的序列顺序( 所有图像, 然后所有音频, 然后是文字) 将会丢失时间 。 alignment.

TMRoPE 为每个 token 分配绝对时间戳。视觉 token 位于 t=2.3s；Audio token 位于 t=2.32s；用户说出“stop”的文本 token 位于 t=2.35s。RoPE 根据时间戳旋转 attention，使模型把这些输入视为在时间上同时发生。

模型在概念上看到视频框和音频。

<a id="streaming-speech-synthesis"></a>

### Streaming 语音合成

Speech tokens 迷你奥米尼语( Xie & Wu, 2024) 引入了“ 语言模式可以听到、 边思考边说话” streaming":思考者输出 tokens 朗读者输出 tokens 谈话者在思考者开始后立即开火 commits 下一条文字 token。没有批量边界。

Moshi(Défossez等人,2024年10月)是最快的开放式实施。 transformer 发短信和演讲 tokens 使用“ 内部独白” 将思维流与语音流区分开来。 这实际上是思想家+朗读者在经过仔细训练后融合成一个模型。

<a id="vad-and-turn-taking"></a>

### 增值和转业

声音活动检测在输入侧运行。

- 半个多面性: 用户会说话, 模型会听。 模式会说话, 用户会听。 清除 handoff 通过 VAD 静默检测(~ 200米) 。
- 完全不解: 两者同时说话。 模型可以反向(“ uh-huh ” ) 或中断。 难度更大。 Moshi 支持此选项 。

Quen2.5- Omni 默认支持半双倍, 并通过静默阈值转动。 全倍需要应用程序层的处理 。

<a id="qwen3-omni-november-2025"></a>

### Quen3-Omni(2025年11月)

接班人。 Quen3-80B 思想家,更大的朗读者, 改进了TMROPE-v2. 与 GPT-4米250米,开 weights与OmniBench公司竞争的基准 Gemini 2.0 活下来

<a id="production-latency-budget"></a>

### 生产延迟预算

典型的 streaming interaction:

- 缩略语 - > audio tokens:40-80米。
- Prefill (prompt +历史:7B时100-200米,70B时更多。
- 第一个思考者文字 token:40米。 。
- 朗读者处理第一文本 token20米 20米 20米 20 ms.
- 第一次演讲 tokens commit:40米。 。
- 残余VQ编码:30米。
- 语音波解码: 50-80米

边境安全数据库共计:320-510米,7B时,600-900米。 边境质量通常是指70B+;因此是边界的潜伏差距。

<a id="token-rate-math"></a>

### Token- 数学

16kHz演讲,50赫兹基础演讲 tokens需要50个演讲 tokens per second 。 朗读者必须排放 50 吨/秒以跟上。 LLM 30-80吨的H100, 一个小(200-300M)朗读者足够快; 一个7B朗读者会落后。

这就是为什么小的 专门朗读者模型的存在 而不是“只是使用主模型”。

```figure
l5-thinker-talker
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 模拟思想- 塔克管道 token- 排放率
- 计算可配置模型大小和麦克风样本率的 TTFAB。
- 以 VAD 沉默门槛表示半个半翻转。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-omni-streaming-budget.md`实时语音产品的目标 feature 设置(视距、双语、全复)、选取Quen2.5-Omni、Quen3-Omni、Moshi或Mini-Omni,大小为思想家/Talker。

<a id="exercises"></a>

## 练习

1. 目标为三百米,7B智者三百米朗读者 写下每个部件的潜伏

2. Quen2.5-Omni使用TMROPE。描述模型所看到的 prompt 用户开始在 t=1s 上发言, 相机在 t=1.2s 上抓取手势 。

3. 完全不解的支持要求模型在监听时发出音频。 推荐一个训练数据格式来教它 。

4. 描述“内在独白”的分离,

5. 计算产出预算:一个朗读者必须多快地退出 tokens 以跟上16kHz的演讲 在50个基底层 tokens/sec?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Thinker | "大脑恢复" | 大型文本生成 transformer 制作什么说 |
| Talker | 发声的嘴 | 小 transformer 生成离散的语句 tokens 来源于思想家的文字 |
| TTFAB | (单位:千美元) | 时间到第一个音频字节: 从用户语音结束到第一个音频样本结束 |
| TMRoPE | "Time-aligned RoPE" | 位置编码,使用绝对时间戳横跨视觉、音频、文字 |
| Half-duplex | "Turn-taking" | 用户和模型替代; VAD 静默检测用户的完成 |
| 全双工 | "Simultaneous" | 模特能同时说话和听,后道能 |
| 内心独白 | "摩希分离" | 单一模型设计,其中思考-流和讲-流间 |

<a id="further-reading"></a>

## 进一步阅读

- [Xu等人-Quen2.5-Omni(arXiv:2503.20215)](https://arxiv.org/abs/2503.20215)
- [Qwen 工作队-Quen3-Omni(ARXiv:2509.177765)](https://arxiv.org/html/2509.17765v1)
- [谢和吴-微型奥米尼(arXiv:240816725)](https://arxiv.org/abs/2408.16725)
- [Défossez等人-Moshi(阿尔西夫:2410000037)](https://arxiv.org/abs/2410.00037)
- [Zeng等人-GLM-4-Voice(arXiv:2412.02612)](https://arxiv.org/abs/2412.02612)
