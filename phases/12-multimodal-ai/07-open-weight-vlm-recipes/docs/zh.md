<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="open-weight-vlm-recipes-what-actually-matters"></a>

# 开放 Weight VLM 的构建方案：真正重要的因素

> 2024-2026年开放weight VLM 文献是熔化表的森林。 苹果的 MM1 测试了13 个图像组合 encoder、连接器和数据组合。 Allen AI的 Molmo 证明是详细的人类字幕节拍 GPT-4V蒸馏,Cambrian-1 20+ encoder 对比。 Idefics2 正式确定了五轴设计空间。 原始VLMs 比较了27个受控基准的培训配方。 在所有这些噪音中, 有一小组结果包含在纸面上: 图像 。 encoder 数据混合比连接器结构更重要, 详细的人类字幕比蒸馏合成数据更重要。 这个课读这些表格, 这样您就不必读了 。

**类型:** 学习+实验室
**语言:** Python (stdlib, 烧焦表解析器+食谱提取器)
**先修要求:** 阶段12 0.05 (LLAVA基准)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名五轴VLM设计空间: 图像 encoder连接器 LLM,数据组合,分辨率计划。
- 读取 MM1 / Idefics2 / Cambrian-1 烧蚀表,并预测哪个按钮移动给定的基准 。
- 选择一个食谱( P)encoder,连接器,数据,分辨率),用于计算新的VLM,并配置预算和任务组合。
- 解释为什么详细的人文字幕被拍下来 GPT-4V 蒸馏在同一处 token count.

<a id="the-problem"></a>

## 问题

数百张开着...weight VLMs 存在。 “ 好” 和“ 最新” 之间的大部分差距不是建筑。 它就是数据、 分辨率表, 以及 encoder 选择。知道哪个按钮会先转弯 当你的模型表现不佳, 节省了500万...GPU- 时差

2023年波(LLAVA-1.5, 指示BLIP, MiniGPT-4) 运行在标题栏上 pretraining + LLAVA- Instruct-150k. 良好的基线, 超过 MMMU 35%。

2024年的波(MM1, Idefics2, Molmo, Cambrian-1, Primatic VLMs)流出无遗的流水。 结果令人惊讶,也很实用。

<a id="the-concept"></a>

## 概念

<a id="the-five-axis-design-space"></a>

### 五轴设计空间

Idefics2(Laurençon等人,2024年)称轴:

1. Image encoder. CLIP 移动式 ViT-L/14,SigLIPSO400m14,DINOV2 ViT-g/14,实习生VIT-6B。 Encoders 不同时 patch 大小、分辨率和 pretraining objective.
2. 连接器 MLP (2-4层)、 Q- 时间(32个查询+交叉连接)、  Perceiver Resampler (64个查询)、 C- Astrator (进化+双线共享)。
3. 语言模型。 Llama-3 8B / 70B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 720B, 7B, 720B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 7B, 70B, Mistral 7B,Phi-3,Gemma-2,Quen2.5。 LLM 尺寸是主要的参数成本。
4. 训练数据:对口说明(CC3M、LAION)、间断说明(OBELICS、MMC4)、指示(LLAVA-Instruct、ShareGPT4V、PixMo、Cauldron)。
5. 决议时间表.固定224/336/448, AnyRes, 本地动态. 在训练或常年时被扰动。

每个生产量的VLM都对每个轴进行选择。 MMMU分数的大部分差异是由轴1、4和5解释的,而不是由您选择的连接器。

<a id="axis-1-encoder--connector"></a>

### 轴 1 : encoder > 连接符

MM1 第3.2节显示:从 CLIP 转换 ViT-L/14至SigLIP SO400m/14 增加了3+点 MMMU。 将连接器从 MLP 交换到 Perceiver Resampler 添加不到 1 点。 复制的 Idefics2: SigLIP > CLIP, Q- Former {MLP  Perceiver 在同一处 token count.

坎布里安一号的"坎布里安幻象" Encoders 匹配"(Tong等人,2024年) 20+ encoders 以视觉为中心的基准。 头板的顶部是 DINOv2 和 SigLIP 的混合体; CLIP 是包中 ViT- MAE低一点,CLIP的差 ViT-L到DINOV2 -我到DINOV2 -我到DINOV2 -I to DINOV2 ViT-g/14是~5-7点 在CV-Bench上。

2026 默认 encoder 用于打开 VLMs 是 SigLIP 2 SO400m/14 语义 + 密度 features,有时与 DINOV2 连接 ViT-g/14 features (坎布里安的“空间视觉聚合器”这样做)

<a id="axis-2-connector-design-is-a-wash"></a>

### 轴2:连接器设计是洗涤

MM1、Idefics2、Prisimatic和MM-内置都得出了相同的结论:固定的视觉-token 计算,连接器结构不重要。 patches 在同一时间在32号Q- 格式内执行 token budget.

关乎什么是 token 计数。 更多视觉 tokens = 更多 = 超过 LLM 计算= 达到某个点后,业绩更好,然后降低回报。 64 tokens 光学记录仪的每个图像太少。 576-1024 tokens 多数开放的VLMs. 2048+只帮助文件和图表。

Q- Former 相对于 MLP 是一个成本问题,而不是质量问题:Q- Former 上限 tokens 图像分辨率不考虑任何图像分辨率; MLP 全部发布 patch tokens。对于高频输入,Q- 格式保存 LLM 上下文; 对于低频, 区别在于噪音 。

<a id="axis-3-llm-size-sets-the-ceiling"></a>

### 轴 3 : LLM 设定上限

将 LLM 从 7B 到 13B 可靠地在每张VLM 纸上添加 MMMU 2-4 点。 在 70B 时,您饱和了大多数基准。 VLM 的多式联运推理上限是 LLM文字推理上限——视觉 encoder 只能喂它,不能给它理由

这就是为什么Quen2.5-VL-72B和 Claude Opus 4. 7 粉碎 MMU- Pro 和 ScreenSpot- Pro: 语言大脑巨大。 7B VLM 不能通过智能连接器设计取代 70B VLM 。

<a id="axis-4-data--detailed-human-captions-beat-distillation"></a>

### 轴 4: 数据- 详细的人文字幕, 蒸馏

Molmo + Pixmo (Deitke等人, 2024年) 是每个人应该阅读的2024年结果。 Allen AI 使用人类注解器描述1-3分钟密言到文字传译的图像, 产生712K 高密度插图。 GPT-4V蒸馏 任何地方的训练数据。

摩尔莫-72B拍 Llama-3.2-90B-11个基准中的11个的视觉。三角洲不是建筑,而是标题质量。详细的人类字幕包含每个图像的信息比简短的网页字幕多5-10x,并且始终以事实为依据 GPT-4V蒸馏致幻剂

ShareGPT4V(Chen等人,2023年)和Cauldron(Idefics2)与混合人类+一起遵循同一游戏手册。 GPT-4V 说明。趋势是明确的:对于2026年的边框,说明密度 > 说明数量 > 蒸馏便利。

<a id="axis-5-resolution-and-its-schedule"></a>

### 轴线5:决议及其时间表

Idefics2 的浸渍: 384 - > 448 增加了1-2点。 448 - > 980 图像分割( AnyRes) 增加了3-5 OCR 基准。 平方分辨率训练平原精度中等; 分辨率斜坡( 开始, 完成 448 或本地) 列车速度更快, 终点更高 。

Cambrian-1 运行解析对齐 tokens 权衡:在固定计算时,您可以拥有更多 tokens 分辨率低于或低于 tokens 高分辨率为OCR赢得;低再生-tokens 赢得了对全场的理解

2026年生产配方:第一阶段为384个固定,第二阶段为OCR重度任务,动态分辨率最高达1280。

<a id="the-prismatic-controlled-comparison"></a>

### 原始控制比较

原始VLMs(Karamcheti等人,2024年)是控制所有轴的纸张。 LLM,相同的指令数据,相同的 evaluation ——一个轴一次变化。结果:

- 视觉图像token 计算解释 ~ 60% 的差异 。
- Encoder 选择解释~20%。
- 连接符结构解释~5%。
- 其他的(数据组合、调度器、LR) 其余的~15%。

这是一种粗略的分解, 但这是最干净的答案 "我应该先跳出" 在文献中。

<a id="a-picker-for-2026"></a>

### 2026年的选手

依据证据, 默认的开放 VLM 配方 2026年的新项目 :

- Encoder:SigLIP 2 SO400m/14 与 NaFlex 本地分辨率,与 DINOV2 相混合 ViT-g/14 密度 features 需要分割/grounding.
- 连接符: 2 层 MLP 连接 patch tokens。跳过 Q - 格式,除非您是 token-constrained.
- LLM目标日期:第25/25/ Llama-3.1 / Gemma 2, 7B 费用,质量70B ,按目标延迟度选择。
- 数据: PixMo + shareGPT4V + Cauldron, 与任务特定指令数据同步。
- 分辨率:动态(每长边计256个,最大1 280个像素)。
- 时间表:第一阶段 alignment 第二阶段,完全精细,第三阶段,具体任务细微。

每一个缺省 traces 回到了这个课末引用的论文中的节制烧伤。

```figure
l5-vlm-recipe-knobs
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个烧蚀表解析器和食谱提取器。它编码 MM1 和 Idefics2 烧蚀表( 加密) , 并允许您查询 :

- "给预算X和任务Y,什么配方赢?"
- "如果我用7B交换SigLIP的CLIP" Llama,什么是预期 MMMU 三角洲?"
- "我应该先跳哪个轴才能得到80%的自信"

输出为按排序的配方列表,其中含有预期的基准三角形和“最晚第一个”建议。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-vlm-recipe-picker.md`。根据目标任务组合、计算预算和延迟目标,它释放出一个完整的配方(encoder连接器 LLM,数据组合,分辨率表),并引用每个选择都有道理的通缩。每当新的 VLM 项目启动时,工程师就不再重新发明 Idefics2 通缩表。

<a id="exercises"></a>

## 练习

1. 读MM1第3.2节。 LLM 图像,该图像 encoder 胜出,答案会翻转到13B吗? LLM为什么?

2. Cambrian-1发现,连接DINOV2+SigLIP的功能要么单靠以视觉为中心的基准就超过,但并没有增加MMMU的信号。 预测哪个基准增益和哪些保持平坦。

3. 你的目标是移动界面 agent 2B 上方的 LLM选择 encoder,连接符,分辨率和数据组合。每个选择都使用特定的烧蚀表。

4. 摩尔莫船4B型和72B型。4B型与关闭的7B型VLM型号具有竞争力;72B型号 Llama-3.2-90B-Vision on 11/11 base. 这告诉你什么? LLM- 高原大小假设?

5. 设计一个折叠表,从 encoder 7B VLM 中的质量。 有多少次训练最少运行? 提议四个轴设置 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Ablation | "一个小把戏" | 训练多个运行, 在一个设计- 空间轴中存在差异, 并保持其它所有恒定 |
| Connector | "布里奇"/"投影机" | 绘制愿景的可训练模块 encoder 输出为 LLM的 token 空间( MLP, Q- 前置, Perceiver) |
| 详细的人类字幕 | "密集字幕" | 人文多句描述(通常为80-300) tokens)比网络替代文本更丰富 |
| 蒸馏 | "GPT-4V 字幕" | 更强大的专有性甚低频成像生成的训练数据;方便但易于继承 hallucination |
| 任何Res/ 动态 Res | "高射线" | 用于向大于 encoder本地的分辨率通过平铺或MRoPE |
| 分辨率斜坡 | "Curriculum" | 低分辨率和高分辨率的训练时间表,超速 alignment learning |
| 以愿景为中心的长椅 | "CV -Bench / BLINK" (CV -Bench / BLINK) (CLINK) (CV -BEINK) (CLINK) (CV -BYNK) (BLINK) (CLINK) (CV -BYUK) (BLINK) (CV -BYUG) | Evaluation 而不是语言上重的推理 |
| PixMo | "莫莫的数据" | Allen AI 的712K 高空图像数据集; 人言转换成密文 |

<a id="further-reading"></a>

## 进一步阅读

- [McKinzie等人-MM1(arXiv:2403.09611)](https://arxiv.org/abs/2403.09611)
- [Laurençon等人——概念2/建造VLMs(arXiv:2405.0246)](https://arxiv.org/abs/2405.02246)
- [Deitke等人-Molmo和Pixmo(arXiv:2409.17146)](https://arxiv.org/abs/2409.17146)
- [唐等人——坎布里安-1(arXiv:2406.16860)](https://arxiv.org/abs/2406.16860)
- [卡拉姆切奇等人——原始VLMs(arXiv:2402.07865)](https://arxiv.org/abs/2402.07865)
