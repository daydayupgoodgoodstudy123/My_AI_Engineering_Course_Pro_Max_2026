<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="llava-and-visual-instruction-tuning"></a>

# LLaVA 与视觉指令微调

> LLAVA( 2023年4月) 是地球上复制最多的多式联运结构, 它用一个双层 MLP 取代 BLIP-2 的Q- 格式, 取代 Flammingo 的门 cross-attention 幼稚 token 并接受过关于158公里视觉指示旋转的培训 GPT任何在2023年至2026年间建造VLM的执业者都可制造某种LLAVA。 LLAVA-1.5添加了 AnyRes. LLAVA-NEXT 的碰撞分辨率。 LALVA-OneVision 统一图像、多图像和视频,它们都包含在一个配方中。这个课程读了配方,执行投影器,并解释了为什么“简单者赢了”。

**类型:** Build
**语言:** Python (stdlib, 投影器+ 指令板块构建器)
**先修要求:** 阶段12 02(CLIP),阶段11(PS)LLM 工程-指示调试)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 构建一个映射的双层 MLP 投影器 ViT patch embeddings 来文日期: 2000年12月31日(第1024号) LLM的 embedding 暗( dim 4096) 。
- 双阶段配方:(1)投影机 alignment 558k 标题对, (2) 视觉指示调频 158k GPT- 4个产生的转弯
- 构造 LLAVA 格式 prompt 与 image token placeholder, system prompt,以及用户/辅助者旋转。
- 解释为什么社区从Q-Former 迁移到MLP,尽管Q-Former token-预算赢

<a id="the-problem"></a>

## 问题

BLIP-2 的 Q 前置( Lesson 12.03) 压缩图像到 32 tokens干净、高效、对基准有好处,但有两个问题。

首先,Q-Former是可受训的,但其损失不是最后的任务。第一阶段是ITC+ITM+ITG。第二阶段是LM损失。询问中了解到一些中间表示 LLM 然后解码。信息丢失在瓶颈中。

第二,Q -Former需要188M参数, 在LLAVA的2023规模上,你不得不与目标共同设计它 LLM修改 LLM,重新培训Q - 以前的。 encoder每一个组合都是一个单独的研发项目。

法兰西州LLAVA的回答很尴尬, ViT576年的 patch tokens,通过一个双层 MLP(`1024 → 4096 → 4096`将所有576个都扔进 LLM输入序列,没有瓶颈,没有第1阶段 pretraining 训练MLP直接失去LM

数据来自何方? GPT- 4 (仅文本) 生成指令数据。 feed GPT-4 图像的COCO标题和捆绑框数据,要求它提供对话、描述和复杂的推理问题。158k 指令-回复是免费的。没有人类的注释。

结果:VLM在8A100赛上跑了一天,击败了MMMU上的Flamingo,并运送了一个开着的 checkpoint 2023年末,它产下了50个叉子

<a id="the-concept"></a>

## 概念

<a id="the-architecture"></a>

### 架构

13B时LALVA-1.5:
- Vision encoder: 中央应急循环系统 ViT-L/14@336(第一阶段冻结,可选择解冻阶段2)。
- 投影机: 2 层 MLP 和 GELU activation, `1024 → 4096 → 4096`.
- LLM维库纳-13B(后来) Llama-3.1-8B).

Forward pass 图像+文字 prompt:

```
img -> ViT -> 576 patches of dim 1024
patches -> MLP -> 576 tokens of dim 4096
prompt: system + "<image>" placeholder + user question
replace <image> token with the 576 projected tokens
feed the full sequence to the LLM
decode response
```

图像占了576个 tokens 的 LLM 2048年,则1472年 tokens 文本。在 32k 上下文中,这是一个圆形错误。

<a id="stage-1-projector-alignment"></a>

### 第1阶段:投影仪 alignment

Freeze ViT冻结 LLM。仅培训 2 层 MLP. 数据集: 558k 图像插图对( LAION-CC- SBU) 。损失: 以预测为条件的语种模型 image tokens.

单 epoch 投影机学会绘制地图 ViT- 空间到 LLM- 空间,没有任务监督

<a id="stage-2-visual-instruction-tuning"></a>

### 第二阶段:视觉指令调试

解除投影器(仍可训练)的引信。 LLM (通常全部,有时 LoRA158k 视觉指示转弯列车。

指令数据是骗局。 Liu等人生成的:
1. 拍一张COCO的图像
2. 解开文本描述( 5 个人类标题 + 边框列表) 。
3. 发送到 GPT- 4个加3个 prompt templates:
   - 对话:“在用户和助手之间就这个图像进行前后的对白。”
   - 详细描述:"给图像一个丰富、详细的描述。"
   - 复杂的推理:“问一个需要对图像进行推理的问题,然后回答。”
4. Parse GPT-4的输出成对(指示、反应)

所有这些都没有直接触及图像——只有文字描述。 GPT4个幻觉,图像内容很合理。有些噪音,但效果不错:158k转动足以解开对话。

<a id="why-the-community-copied-this"></a>

### 为什么社区复制了这个

- 没有第一级的损失可以调和 整个LM损失
- 放映机列车数小时,而不是几天
- LLM 可用交换( LLAVA- Llama2, LLAVA-)Mistral由再训练来进行
- 视觉指示数据管道的使用 GPT-4,而且便宜 重新生成一个新的域。

<a id="llava-15-and-llava-next"></a>

### 激光器-1.5和激光器-NEXT

LLAVA-1.5 (2023年10月) 补充:
- 学术任务数据( VQA、 OKVQA、 RefCOCO) 混合到指令调试中 。
- 更好 system prompt.
- 2048  32k 上下文。

法兰西-新陆空空空航(2024年1月)补充说:
- 目标:将高射线图像分割成2x2或1x3网格,其中336x336种作物,加上一个全球低射线缩略图。 tokens; 总计约2880个视觉 tokens 自动记录仪和图表任务跳跃。
- 与 ShareGPT4V 更好地混合指令数据(高质量) GPT-4V 说明)。
- 更强的基数 LLMs (Mistral-7B, Yi-34B., 7B., Yi-34B., 7B., Yi-34B., 7B. 7B., Yi-34B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B. 3B.

<a id="llava-onevision"></a>

### LLaVA-OneVision

12.08课深入地涵盖《一视》。短版本:同一投影机,但经过培训的课程包括单一图像、多图像和视频,一个模式与共享视觉-token budget.

<a id="the-comparison-to-q-former"></a>

### 与 Q- 格式的比较

| | Q- 原型( BLIP-2) | 最低生活水平(LLVA) |
|---|---|---|
| Visual tokens 每个图像 | 32 | 576(基准)或2880(任何反射) |
| 可训练参数 | 188兆+液态 | 40米+LM |
| 第1阶段损失 | ITC+ITM+ITG | 只限 LM |
| LLM drop-in | 需要再培训 | 以最少的再培训交换 |
| Multi-image | Awkward | 自然(碳酸盐) |
| Video | Awkward | 自然(每框架) |
| Token budget | 小号 | 大号 |

劳动和社会政策部在简单化的基础上获胜 token 灵活度。 Q - 前方赢取 token budget. 到2023年底, token budget 不再成为约束性限制(LLM 环境发展到32k-128k+,简单为主。

<a id="the-prompt-format"></a>

### 该 prompt format

```
A chat between a curious human and an artificial intelligence assistant. The assistant gives helpful, detailed, and polite answers to the human's questions. USER: <image> Describe this image in detail. ASSISTANT: The image shows ...
```

`<image>` 是占位符 token. 之前 tokenization,它被576视觉 tokens (或AnyRes的2880号)。 Tokenizer 我们看到的序列比训练的要长一点 但是 LLM 处理新颖输入 因为第一阶段教它。

<a id="parameter-economy"></a>

### Parameter economy

液态汞含量-1.5-7B分类:
- CLIP ViT-L/14 @ 336:303M(冻结阶段1,经常解冻阶段2)。
- 投影机(2x线性):~22M 可训练。
- Llama-7B: 7B。 -对。
- 总计:7.3B参数,第2阶段可受训:全7B+22M投影仪。

第2阶段的培训费用:8xA100时~20小时。这是关键数字,一天,一个节点可以复制。这就是LALAVA传播的原因。

```figure
mm-llava-projector
```

<a id="use-it"></a>

## 实际应用

`code/main.py` implements:

1. 纯度为2层的 MLP 投影器( 玩具尺寸为 16 ° 32 ° 32 °) Python.
2. 该 prompt- 建设管道: system prompt + `<image>` 改为 N tokens + 用户转动+ 助理生成占位符。
3. 一个视觉化的576token 视觉块看起来像 LLM 上下文(消耗的百分比为2k/ 32k/128k)。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-llava-vibes-eval.md`。如果有LALVA-家庭 checkpoint10号prompt 感官- Eval 套件( 3个字幕, 3个 VQA, 2个推理, 2个拒绝) 并报告一个人读计分卡。 不是基准; 用于确认投影器和 LLM 连接良好。

<a id="exercises"></a>

## 练习

1. 计算训练员parameter 计算 2 层 MLP 投影器的数值 `1024 → 4096 → 4096`. 与 GELU 和偏见,它代表什么部分的LALVA-13B?

2. 构造一个 LLAVA prompt 写下预期助理的回应。 LLAVA 为什么要拒绝这个 zero-shot 以及需要哪些训练数据 reinforce 拒绝?

3. 阅读 LLAVA- NEXT 博客的 AnyRes 部分。 计算视觉 token AnyRes 中一个 1344x672 图像的计数。 与基数 576 相比 tokens 336x336时

4. LLAVA 第1级投影机在字幕上接受LM损失训练。 如果您跳过第1级直接跳到第2级( 视频指令调频) , 将会发生什么? 请输入原始 VLM 反动( arXiv: 2402. 07865) 以解答 。

5. 激光雷达-内建器-150k 用途 GPT4 带有COCO说明来生成指令。 对于一个新的域(医疗X光、卫星图像),描述生成域指示的四步数据管道。 每步会出什么问题?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 投影仪 | "MLP桥" | 双层 MLP 带 GELU mapping ViT 暗到 LLM dim |
| Image token | "<image> placeholder" | Prompt 标记被 N 投影视觉所取代 tokens 之前 inference |
| 视觉指令调试 | "LLAVA第2阶段" | 培训 GPT- 4 生成(图像、指令、响应)三胞胎 |
| 第1阶段 alignment | "Projector pretraining" | Freeze ViT 和 LLM, 带LM字幕损失的火车投影机 |
| AnyRes | “多区域裁剪平铺（Multi-crop tiling）” | 将高射线图像分割成瓷砖网格, 并连接每个瓷砖的视觉 tokens |
| LLaVA-Instruct | "GPT-4-generated" | 158k 指令-回应对,根据COCO说明合成+ GPT-4 |
| Vision encoder freeze | "锁上后骨" | CLIP weights 第一阶段不更新,有时第二阶段也不更新 |
| ShareGPT4V | "更好的标题" | 1M 密文字幕由 GPT-4V,用于提高质量 alignment |
| VQA | "视觉问题回答" | 回答关于图像的自由形式问题的任务 |
| 原始VLMs | "设计空间纸" | 卡拉姆切奇2024年系统坠毁测试投影器和数据选择 |

<a id="further-reading"></a>

## 进一步阅读

- [Liu等人——视觉指示图(arXiv:2304.08485)](https://arxiv.org/abs/2304.08485) - 激光器纸
- [Liu等人——通过视觉指示改进基线(arXiv:23100.03744)](https://arxiv.org/abs/2310.03744) - 激光器 - 1.5
- [陈等人——ShareGPT4V(阿尔西夫:2311.12793)](https://arxiv.org/abs/2311.12793) - 密集的字幕数据集。
- [卡拉姆切奇等人——原始VLMs(arXiv:2402.07865)](https://arxiv.org/abs/2402.07865) 设计空间的浮流
- [Li等人——LLAVA-One Vision(arXiv:2408.0326)](https://arxiv.org/abs/2408.03326) 统一单一图像、多图像、视频。
