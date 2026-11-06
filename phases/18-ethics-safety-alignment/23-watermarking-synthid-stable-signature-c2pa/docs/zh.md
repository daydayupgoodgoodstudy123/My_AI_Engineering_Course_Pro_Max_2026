<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="watermarking--synthid-stable-signature-c2pa"></a>

# 水印：SynthID、Stable Signature、C2PA

> 三种技术结构 2026年AI 生成content provenance合成数据(Google DeepMind)——2023年8月发射的图像水印,文本+视频,2024年5月(Gemini 2024年10月通过负责的GenAI工具包, 2025年11月与 Gemini 3 Pro. 文本水印调整下一步token sampling 概率不明显;图像/视频水印在压缩、裁剪、过滤、框架率变化中存活。 decoder 因此,每个输出都包含固定信息;在 FPR < 1e-6 中,已裁剪的图像(占内容的10%)检测到 > 90%。后续的“ 稳定符号不稳定”(arXiv:2405. 07145, 2024年5月) - fine-tuning C2PA——加密签名、篡改式明显元数据标准(C2PA2.2 Explor 2025),水标识和C2PA是互补的:元数据可以剥除,但含有较丰富的来源;水标识通过转换法持续存在,但信息较少。

**类型：** 构建
**语言:** Python (stdlib, token-水印嵌入+检测)
**先修要求:** 阶段10 · 04 (sampling01-09(信息理论)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Describe token- 水平水标记(合成文字样式)及其可探测机制。
- 描述稳定标志和2024年的清除攻击 打破它。
- 国家C2PA的作用,以及它为什么补充了水的标记。
- 说明主要限制:具体模型信号、解释性下强度和保留意义攻击(arXiv:2508.20228)。

<a id="the-problem"></a>

## 问题

2023-2024年,人们看到深刻的假象和AI生成的内容大规模地进入政治和消费者环境。 水印是拟议的技术来源信号:在创造时标记几代人,然后检测。 2025年的证据:没有水印无条件坚固,但与C2PA元数据相融合,组合提供了有用的源代码故事。

<a id="the-concept"></a>

## 概念

<a id="text-watermarking-synthid-text-style"></a>

### 文本水印( SynthID- 文本样式)

Kirchenbauer等人2023机制,由谷歌制作:

1. 在每个解码步骤中,都用前一个 K 来散开 tokens 产生假的 vocabulary 变成"绿色"和"红色"
2. Bias sampling 向绿色组进发 将  加到绿色 logits.
3. 一代人更绿色 tokens 而不是机会会产生。

检测: 重写每个前缀, 计数绿色 tokens ,计算一个 Z 级。 z 级为 > 0 , 水印文本为 < 0 , 人类文本为 < 0 。

属性：
- 读者无法理解( . ) , 质量损失很小 。
- 可通过进入 vocabulary 分区函数。
- 改写文本对解释性措辞不强——使信号毁于一旦。

合成信息数据库文本通过谷歌的负责任的GenAI工具包公开发布,

<a id="stable-signature-image"></a>

### 稳定签名(图像)

Fernandez等人, ICCV 2023. 精细调制潜伏扩散 decoder 所以每个生成的图像都包含一个嵌入于潜在表达式中的固定二进制信息。 检测会用神经解码从潜伏中解码 decoder。在 FPR < 1e-6 中,已裁剪的图像(占内容的10%)检测到 > 90%。

2024年5月“稳定签名不稳定”(arXiv:2405.07145): fine-tuning 该 decoder 保存图像质量时删除水印。 fine-tuning 价格低廉;水印的对抗性坚固度有限。

<a id="synthid-unified-detector-november-2025"></a>

### 合成ID统一探测器(2025年11月)

Alongside Gemini 3 Pro:一个多媒体探测器,从文字、图像、音频和视频中读取合成信息码信号 API。统一谷歌源代码堆放

<a id="c2pa"></a>

### C2PA

联盟 Content Provenance 和真实性。 密码签名的篡改明显元数据标准。 C2PA 2. 2 解释器 (2025年)。 C2PA 显示的源代码声明(谁创建了、何时改造了)由创建者键签名。

补充水印:
- 元数据可以被剥除;水印不能(容易)得到。
- 元数据丰富(完整的来源链);水印带有位元。
- C2PA取决于平台的采用;水印自动嵌入。

谷歌在搜索、阿德斯和“关于这个图像”中都集成。

<a id="limitations"></a>

### Limitations

- **Model-specific.** 合成ID 水印代代来自合成ID 驱动模型。 没有合成ID 的模型代代代不是水标记, 所以“ 没有合成ID 信号” 并不是真实性的证据 。
- **Paraphrase.** 文字水印无法幸存, 意思是保留参数 。
- **变形攻击** arXiv:2508.20228 (2025) 显示有保留意义的攻击,摧毁了文字水印和许多图像水印。
- **精细的去除。** 每一"稳定签名是不稳定的,"后一代 fine-tuning 删除嵌入的水印。

<a id="eu-ai-act-article-50"></a>

### 《欧盟大赦国际法》第50条

AI 生成内容标签的透明度守则(2025年12月第一稿,2026年3月第二稿,预计2026年6月最后版本) [欧洲联盟委员会地位网页](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content)该守则自2026年4月起仍在起草,时间表可能改变,需要技术层面的监管层必须标出深层假象。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

22-23课涉及模型的发布(私人数据、来源信号),27课涉及培训-数据管理,24课是要求采取这些技术措施的监管框架。

```figure
an-watermark-greenlist
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 构建一个玩具文字水印。 Tokens 是整数 0. N-1; 水印 sampling 偏向于散列定义的绿色组。 检测器计算绿色-token z -score,你可以在1000到1000时观察探测结果token 数代人,看方言摧毁信号, 并测量假阳性速度 在人类文字上。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-provenance-audit.md`. 鉴于内容的部署附有来源申报,审计:水印机制(如果有),C2PA签字链(如果有),每个文件的对抗性强弱,以及每个文件的可靠性。modality coverage.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`.报告标记水的z-score 1000 -token 代名词与人文文字。 确定95%的置信率值为误正率 。

2. 执行一个参数攻击,以取代30%的 tokens 与同义词。重新测量z级。

3. 读Kirchenbauer等人,关于坚固度的第6节。为什么文字水印在副句子下失败,但图像水印在作物中存活?

4. 设计一个使用 SynthID- text + C2PA 元数据的配置。 描述消费者看到的源码链 。 确定每个组件的失败模式 。

5. 2024年“ 稳定签名是不稳定的” 结果显示 fine-tuning 设计一个限制这次攻击的部署控制,例如,需要签字释放微调 checkpoints.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| SynthID | "谷歌的水印" | 跨模式出处信号;文字、图像、音频、视频 |
| Token watermark | "Kirchenbauer-style" | Biased-sampling 文字水印可以通过绿色探测到token z-score |
| 稳定签名 | "图像水印" | Fine-tuned-decoder 水印; ICCV 2023 |
| C2PA | "元数据标准" | 加密签名的篡改源代码元数据 |
| 引言的稳健度 | "重新措辞打破它" | 文本水印属性; 目前有限 |
| 精调去除 | "对抗性无水印" | 攻击,通过 decoder fine-tuning |
| 跨式探测器 | "统一合成码" | 2025年11月统一 API across modalities |

<a id="further-reading"></a>

## 进一步阅读

- [Kirchenbauer等人——大语言模型的水印(ICML 2023,arXiv:2301.10226)](https://arxiv.org/abs/2301.10226) — 该 token- 水印装置
- [Fernandez等人——稳定签字(ICCV 2023,arXiv:2303.15435)](https://arxiv.org/abs/2303.15435) 图像水印纸
- [“稳定签名不稳定”(arXiv:2405.07145)](https://arxiv.org/abs/2405.07145) 清除攻击
- [Google DeepMind 合成集成软件](https://deepmind.google/models/synthid/) - 跨模式的水印
- [C2PA 2.2 解释器(2025)](https://c2pa.org/specifications/specifications/2.2/explainer/Explainer.html) 元数据标准
