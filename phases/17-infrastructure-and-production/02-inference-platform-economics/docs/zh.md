<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="inference-platform-economics--fireworks-together-baseten-modal-replicate-anyscale"></a>

# Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale

> 2026年 inference 市场不再 GPU 时间租赁。它分解成自定义硅( Groq, Cerebras, Samba Nova) , GPU 平台(基础、联合、烟火、模式),以及 API- 第一个市场(复制品,深 Infra)。 GPU 和10T+的4B价值, tokens/ 日 告诉你量驱动模型的原理。 2026年1月, 基调关闭了300M系列E, 5B 。 竞争性定位规则很简单: 烟花优化了潜伏度, 共同优化目录宽度, Baseten优化了企业抛光, 模式优化了 Python- 本地DX,再生优化多式联运的覆盖范围,任何规模的优化分布 Python。这个课给你一个矩阵 你可以交给一个创始人。

**类型:** 学习
**语言:** Python (标准、玩具/每次呼叫经济学比较)
**先修要求:** 阶段17 · 0.1 (管理) LLM 平台,第17阶段 -04年(内部维修引擎)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出三个市场区(客户硅、 GPU platforms, API- 首先是) 并绘制每个供应商的地图到一个段。
- 解释为什么"每个...token" API 价格模型压缩到服务引擎的成本曲线上,而不是硬件。
- 计算每个请求的有效成本,至少三个供应商,并解释每分钟(Baseten、Modal)每分钟比-token.
- 确定哪个平台是特定工作量(无服务器爆破、稳定高通量、微调变异、多式联运)的正确默认值。

<a id="the-problem"></a>

## 问题

您对管理超标平台进行了评估。 您决定需要一个更窄、 更快的供应商 : 用于潜伏的烟花, 用于宽度的共享, 用于一个精细调整的定制模式的 Baseten 。 现在您有六个真正的选择, 而定价页面没有排队 。 Firework 显示$/ M tokens; Baseten 显示 $/ minute; 模式显示 $/ second; Replicate 显示 $/ protective。 您不能在不模拟工作量的情况下将它们正面对头比较 。

更糟糕的是,每一页价格背后的商业模式不同。 烟花在共享时运行自己的自定义引擎( 火力保护) GPUs; 对应的token 速度反映了它们的利用率曲线。 Baseten 给了您 Truss + 专用 GPUs;每分钟反映独家性。 Python 无服务器 - 每秒开出一次次秒冷的计费。 相同输出( a) LLM 3个不同的费用职能。

这课的模型是六号 每一个赢的时候都会告诉你

<a id="the-concept"></a>

## 概念

<a id="the-three-segments"></a>

### 这三个部分

**自定义硅** - Groq(LPU)、Cerebras(WSE)、Samba Nova(RDU)。 GPU- 以同一模型为基础的组群。token 价格(克瓦克为~0.99美元/米) Llama-70B 2025年底),但对于隐蔽敏感使用案例是无法击败的。 Groq 是声音生产选择 agents 和实时翻译。

**GPU platforms** 以全国人口调查(H100, H200, B200, 2026年)或有时以AMD为基准, 烟火、摩尔、任何规模。 GPU 租房(RunPod, Lambda)和“超标管理服务”(Bedrock)。

**API- 首个市场** 复式、深 Infra、 OpenRouter、Fal. 粗体目录、按支付率或每秒支付,强调先拨时间。

<a id="fireworks--latency-optimized-gpu-platform"></a>

### 烟花-优化 GPU platform

- 消防引擎(定制);销售量比 vLLM 等效配置。
- 批量级别,在非互动工作量中,为服务器无率的50%。
- 精细调整的模型与基准模型的费率相同,它是一个真正的差异者,而供应商则为您收取溢价。 LoRA.
- 2026年中期:按需提高 GPU 2026年5月1日起每小时租金1美元。
- 财务信号:4B估值,10T+ tokens/日处理。

<a id="together--breadth-optimized"></a>

### 共同——优化宽度

- 200+ 模型,包括上游出版后几天内公开源排放量。
- 等值的复制品价格50-70% LLM 模型——“AI 本地云”定位是量和目录。
- Inference + fine-tuning + 一次培训 API.

<a id="baseten--enterprise-polish-optimized"></a>

### 基地-企业政治优化

- 特鲁斯框架:带有依赖性、秘密、在一个舱单中提供配置的模型包装。
- GPU 以合理的冷启动方式进行每分钟开单。
- SOC 2 第二类,HIPAA - 准备,普通的fintech和保健选择。
- 5B估值,2026年1月E系列(300M来自CapitalG、IVP、NVIDIA)。

<a id="modal--python-native-optimized"></a>

### 摩尔- Python-native-optimized

- 纯为基础设施编号 Python。 `@modal.function(gpu="A100")` 并部署一个指挥。
- 每秒开单。 冷开始于2-4 个, 并带有升温前的值; 小模型小于 1 个 。
- 87M系列B,价值为1.1B(2025年)。

<a id="replicate--multimodal-breadth"></a>

### 复现——多式联运宽度

- 付费/ 密码。 默认图像、 视频和音频模型平台 。
- 集成生态系统( Zapier, Vercel, CMS 插件) 。
- 竞争力较低 LLM per-token 价格,但赢得多式联运。

<a id="anyscale--ray-native"></a>

### 任何规模的光线

- 建在雷身上,雷图博是任何规模的专利 inference 引擎( 与 vLLM).
- 最佳分发 Python 工作量 inference 步骤是一个较大的图形中的节点。
- 管理雷群集,与雷AIR和雷服务公司紧密结合

<a id="per-token-versus-per-minute--when-each-wins"></a>

### Per-token 相对于每分钟-当每场获胜时

Per-token 当工作量是隐性不敏感和爆炸性时,你只支付你使用的东西。当利用率高且可预测时,每分钟就有意义——你每击一拳,就击败token 一旦你饱和 GPU.

粗略规则:工作量超过30%的,持续使用专用 GPU,每分钟(Baseten, Modal)开始按-token (烟花,一起)下面,每个...token 赢是因为你不给闲钱

<a id="custom-engine-is-the-real-moat"></a>

### 自定义引擎是真正的护城河

上面每个平台 vLLM 和 SGLang 消防、雷图尔博、巴登 inference 堆叠。定制引擎声称,市场营销是暗淡的,诚实的框框是: vLLM + SGLang 占生产开放源头的80% inference,平台层的分歧者是DX、归属和苏丹解放军。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- Fireworks GPU 租金:每小时加薪1美元,2026年5月1日生效。
- 烟花索赔: 4x 延迟时间低于 vLLM 等效配置。
- 合计:比复制品便宜50-70% LLMs.
- 基底价值:5B(系列E,2026年1月,3 000万美元圆)。
- 模式价值:1.1B(系列B,2025年)。
- 每分钟的节拍token 持续使用率超过~30%。

```figure
cost-per-token
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 比较6个供应商在各种定价模式中综合工作量的情况。 tokens运行它以找到 折叠之间每 -token 和每分钟。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-inference-platform-picker.md`根据工作量概况、苏丹解放军和预算,选择主要 inference 平台和命名的后台。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`Baseten(每分钟)击败烟火(每-)token70B模型的H100?
2. 您的产品为图像生成服务, 加上聊天和语音对文本。 请为每个文件选择平台 modality 并命名连接它们的网关模式。
3. 烟花会提高您主模型的价格1美元/小时。 如果40%的交通量转移到分批级别( 50% 关闭) , 则可以模拟混合成本影响 。
4. 受监管客户需要2类SOC 2 + HIPAA+专用 GPUs。哪个三个平台是可行的,哪一个在FinOps上获胜?
5. 比较每1 000次预测的费用 Llama 3.1 70B " 无烟火服务器 " 、 " 共同点燃 " 、 " 以之为本 " 和 " 重复 " API。 哪种最便宜的预测是10个/ 日?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 自定义硅 | "non-GPU chips" | Groq LPU, Cerebras WSE, Samba Nova RDU——优化解码 |
| FireAttention | 烟火引擎 | Custom attention 内核; 市场比 vLLM |
| Truss | "基础格式" | 模范包装表; 依赖性+机密+服务配置 |
| Per-token | "API pricing" | 充电 tokens 已消耗; 支付不闲置的费用 |
| Per-minute | "专门定价" | 以墙上时钟充电 GPU 时间; 高利用率获胜 |
| Per-prediction | "复制定价" | 每一型号的调试收费;图像/视频通用 |
| RayTurbo | "任何规模的引擎" | Proprietary inference 与雷对立; vLLM 围绕雷群集 |
| 批量级 | 半关 | 降低速度的非互动队列;在烟火中常见 OpenAI |
| 按基本费率进行精细调整 | "Fireworks LoRA" | Charge LoRA- 按基数计算满足的要求(差异) |

<a id="further-reading"></a>

## 进一步阅读

- [烟花定价](https://fireworks.ai/pricing) — 每-token 费率,分批处理, GPU rental.
- [基础定价](https://www.baseten.co/pricing/) ——每分钟费率、承付能力、企业层级。
- [模式定价](https://modal.com/pricing) 每秒 GPU 费率和自由级。
- [AI 定价](https://www.together.ai/pricing) 模型目录和每份token rates.
- [任意规模的定价](https://www.anyscale.com/pricing) -雷图博和雷的定价
- [Northflank-烟火](https://northflank.com/blog/7-best-fireworks-ai-alternatives-for-inference) 比较评估。
- [基础资源——大赦国际 Inference API 2026年供应商](https://infrabase.ai/blog/ai-inference-api-providers-compared) - 卖主的风景
