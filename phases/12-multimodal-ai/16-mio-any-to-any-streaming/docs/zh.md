<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mio-and-any-to-any-streaming-multimodal-models"></a>

# MIO 与任意模态互转的 Streaming Multimodal Models

> GPT-4o 船舶上最开放的产品模型无法复制: agent 2024年后期开放生态系统的答案是 MIO(Wang等人,2024年9月)。MIO象征文字、图像、语言和音乐,训练一个因果 transformer 并创造出任何 modality 向任意 modalityAnyGPT(Zhan等人,2024年2月)是概念的证明;MIO是扩大;United-IO 2 (Allen AI,2023年12月)是具有远见+行动的表弟。 grounding。这个课读到任何模式——4个 tokenizers,一个 transformer, streaming- 友好的解码。

**类型:** 学习
**语言:** Python (斯迪利布,四号...modality token 分配器+ streaming 解码环)
**先修要求:** 阶段12 11(沙米隆),第6阶段(语音和音频)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 设计共享 vocabulary 文本、图像、演讲和音乐 tokens 没有任何碰撞。
- 比较SED -Tokenizer 以及演讲者关于压缩+重建的折中(Speacher)的剩余视频-VQ(Speech)。
- 解释一下四阶段的课程 培养任何一代人
- 列出三种开放的任意配方及其主要的权衡:MIO、AnyGPT、IO 2。

<a id="the-problem"></a>

## 问题

统一 multimodal model 语言模式 + 音频。 每一个跳动都会丢失信息,增加潜伏,使培训复杂化。 GPT- 4o的演示录像显示一个带有第二反应的单一模型的替代物;开放系统以几个月为后退。

工程挑战:

- Tokenizers 必须为每个 modality以无损的压缩为重建,并生产 tokens 费率 transformer 能够消耗。
- 单 vocabulary 必须给文字( 32k+)、图像( 16k+)、 语音( 4k+)、 音乐( 8k+) 分配空间。 最少40万多个条目 。
- 训练数据必须涵盖每一对投入产出(文字图像、图像语音、语音图像等)或模型必须组成。
- Inference 必须流出输出 tokens 足够快,可以进行谈话的延迟( < 500ms-first-audio-byte) 。

<a id="the-concept"></a>

## 概念

<a id="four-tokenizers-for-four-modalities"></a>

### Four tokenizers 四个 modalities

MIO's tokenizer stack:

- 文字: 标准 BPE, vocab~ 2000。
- 图片:SED-Tokenizer (2023)-量化 VAE 带有离散代码簿, 4096 项, 32x32 tokens 每一个图像。
- 演讲:语音识别器剩余VQ(2023年)——将16kHz波形编码为8个等级代码;第一级内容粗略,后一级添加了口音和口音特性。
- 音乐:类似残余VQ(Meta的音乐Gen/Encodc家庭),4-8本法典。

每个 modality 生成整数 tokens. 该 tokens 共享时断开ID区域 vocabulary:

```
text:   0..31999
image:  32000..36095  (4096 image tokens)
speech: 36096..40191  (4096 speech base tokens, plus residual layers)
music:  40192..48383  (8192 music tokens)
sep:    48384..48390  (<image>, <speech>, <music>, </...>, etc.)
```

共计:~48k vocabulary输入 embedding 和输出投影覆盖所有它。

<a id="streaming-decode"></a>

### Streaming decode

语音生成使用剩余VQ。 transformer 预测基调( 层 0) 语句 tokens;平行解码的残余量化器预测随后的层。 token 大约是 16kHz 的50米音频。

该 streaming pattern:

1. 用户用麦克风说话; 实时音频 tokenizer 发表演说 tokens 每50分钟
2. 军事情报组织消耗量 tokens 他们将随着他们的到来而加以证实。prompt prefill + 递增式)
3. 输出 tokens 流出生成; 平行的演讲 decoder 将其转换为有~50-150米潜伏度的音频样本。
4. 时间到第一个音节:~ 300- 500米,在MIO纸上,接近 GPT-4米~250米

小型-奥米尼(arXiv:2408.16725)、GLM-4-Voice(arXiv:2412.02612)和Moshi(arXiv:241000037)是相辅相成的 streaming speech-LLM 特别是Moshi单程轮程160米 GPU.

<a id="four-stage-curriculum"></a>

### 四阶段课程

军事情报组织的培训课程:

1. 第1阶段 - alignment大型 modality- 文字图像,文字语音,文字音乐。 token vocabulary 共享的区段。 vocabulary.
2. 第二阶段——间断。modality 断开文档(带图像+视频的博客,带记录稿的播客等)。modality context.
3. 第三阶段——增强语音。额外音频数据可以提高语音质量,同时不丧失文字能力。
4. 第4阶段 - SFT。 modalities: VQA, 字幕、 解说、 语音对话对话框 。

缺少一个阶段会降低特定能力:跳过第2阶段,模型会失去交叉modality 上下文;跳过第3阶段,演讲很不好。

<a id="chain-of-visual-thought"></a>

### Chain-of-visual-thought

MIO 引入视觉思维链:模型释放中间 image tokens 作为一种推理步骤。 "猫爬树吗?"模型:

1. Emits `<image>` tokens 绘制场景( 从输入图像或草图中) 。
2. 爱咪丝的文字分析草图。
3. 抓住最后的答案

中间图像是一个抓图。 基准在空间合理性任务上有所改进。 想法反映了 chain-of-thought 用于文字推理。

<a id="competitors-in-any-to-any"></a>

### 任何对任何一个竞争者

- 任何GPT( arXiv: 2402.12226): 4 modalities 类似设计。
- 统一化的IO 2 (arXiv: 2312.1717): 增加视觉行动输出、深度和正常度。 任务的多样性更大,规模较小 。
- NExT-GPT (arXiv:2309.05519): LLM + modality- 特定传播 decoders没有一个单一模式的方法。
- Codi(arXiv:2305.11846):可作曲扩散;通过共同潜伏而成的。

情报组最接近纯度token 任何GPT都是它的理论祖先

<a id="latency-budget"></a>

### 长期预算

谈话产品,每个元素的潜伏物都很重要:

- 缩略语到 audio tokens~50米。
- Prefill (audio tokens +历史:~100米,8B型号。
- 第一项产出 token~50米。
- 并行的剩余VQ+演讲 decoder:~100 -150米。

时间到第一个字节的总时间:~ 300米 GPTMoshi索赔160米。 MIO/AnyGPT在400至600米的范围之内,每个公共基准。

<a id="why-any-to-any-stays-hard"></a>

### 为什么任何对任何人 保持坚硬

即使在2026年,打开任何到任何模型的痕迹 关闭两个轴:

- 语音质量。 tokenizer 与11Labs级的声音相比,
- Cross-modality 逻辑。问模型“关于你所看到的”还是失败的频率比纯视觉任务。

昆尼(Lesson 12.20)是2025年最先进的公开尝试。

```figure
any-to-any-stream
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 定义四个modality vocabulary 分配和打印。
- 通过下列途径选择多式联运投入(文字、图像、音频剪辑、音乐)清单 tokenizer router.
- Simulates streaming 解码文本对语音响应 以潜伏计数。
- 计算给定的预期时间到第一音节 encoder, prefill, 和 decoder latencies.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-any-to-any-pipeline-auditor.md`。基于一个谈话产品规格(modalities 在, modalities 调查组负责审核MIO家庭设计选择,并计算长期预算。

<a id="exercises"></a>

## 练习

1. 您的产品接受语音输入并返回语音输出。 端到端的预算目标是什么? 列出花费时间的组件 。

2. 语音控制器剩余 VQ 使用 8 种代码。 提议为什么需要平行解码剩余级别( 依次) , 以及它能节省多少时间 。

3. 你的 vocabulary 有32k 文本+ 4k 图像+ 4k 语音。添加 8k 音乐和~ 10 分隔符。 embedding-matrix parameter 费用在隐藏的dim 4096?

4. 视觉思维链释放出中间图像。 什么样的问题会有好处? 额外问题伤害了哪些类型的人? tokens?

5. 读 Moshi (arXiv: 241000037) 。 请描述它的“ 内在独白” 技术, 并比较 MIO 的视觉思维链 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Any-to-any | "混合型进出" | 接受并随风播放文字、图像、演讲和音乐的单一模型 |
| Residual-VQ | "Speech tokenizer stack" | Multi-codebook tokenization 每个层增加信息; 基层为内容, 后层为 prosody |
| SEED-Tokenizer | "图像代码" | 分解图像 tokenizer 使用MIO使用的4096号输入代码簿 |
| Chain-of-visual-thought | 视觉抓痕 | 模型生成中间图像, 以此推理出最终答案 |
| Time-to-first-audio-byte | "TTFAB" | 从用户声音到第一个音频输出的延迟; < 500 ms 用于交谈感觉 |
| 四阶段课程 | 训练秘方 | Alignment - > 间断 - > 增强语音 - > SFT,按顺序 |

<a id="further-reading"></a>

## 进一步阅读

- [王等人——军事情报组织(arXiv:2409.17692)](https://arxiv.org/abs/2409.17692)
- [Zhan等人—— 任何GPT(arXiv:2402.12226)](https://arxiv.org/abs/2402.12226)
- [Lu等人——IO 2联合号(arXiv:2312.17172)](https://arxiv.org/abs/2312.17172)
- [吴等人——NEXT-GPT (arXiv:2309.05519)](https://arxiv.org/abs/2309.05519)
- [Tang等人-Codi(arXiv:2305.11846)](https://arxiv.org/abs/2305.11846)
