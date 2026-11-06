<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="managed-llm-platforms--bedrock-vertex-ai-azure-openai"></a>

# 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI

> 三个超标器,三个不同的策略。AWS Bedrock是一个模型市场—— Claude, Llama巨人,稳定, 紧跟在一后面 API。 OpenAI 独家 OpenAI 伙伴关系加上专用专用的专用输送单位。 Gemini- 首先是最先进的长字符和多式故事。 OpenAI 以~50米中位数和~75米上方的贝德洛克 Llama 3.1 405B等值—— PTU解释差距是因为专用容量比按需共享要快。 决定规则不是“ 最快 ” , 而是“ 哪个模型目录和 FinOps 表面适合我的产品 ” 。 这个教训教你们如何选择减让,而不是情绪。

**类型:** 学习
**语言:** Python (标准、玩具成本和延迟参照)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具和协议)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出三个平台策略(市场与排他性对等) Gemini- 首先是,并匹配每个产品使用案例。
- 解释一下在阿苏尔购买的 提供输送单位 OpenAI 以及为什么点播的贝德洛克通常读数在405B级时慢于~25米。
- 每个平台的 FinOps 属性表面图( 贝德罗克 应用程序) Inference 简介与Vertex项目-每组与Azure范围+PTU保留)
- 写下“两家最低供货商”政策,解释为什么2026年单家供货商锁门是昂贵的错误。

<a id="the-problem"></a>

## 问题

你选的 Claude 3.7 索纳特的商品,现在你需要服务。 Anthropic API 直接,或者你可以通过 AWS Bedrock 调用, 或者你可以通过一个网关。 API 是最简单的; 贝德洛克添加了 BAA、 VPC 终点、 IAM 和 CloudWatch 属性。 网关添加了失败、 统一计费和标签 。 rate limits 跨供应商。

更深层的问题是目录。如果需要的话 Claude 和 Llama 和 Gemini 在同一产品中,你不能从一个地方买下所有的东西 除非那个地方是贝德洛克加维特克斯加阿苏尔 OpenAI 超标不能互换——它们各自对谁拥有模型层作出了不同的赌注。

这条课描绘了三个赌注, 潜伏差距, 芬诺普斯差距, 和锁定风险。

<a id="the-concept"></a>

## 概念

<a id="three-strategies"></a>

### 三项战略

**AWS 贝德洛克** - 市场。 Claude (Anthropic), Llama 土卫六(AWS),稳定(图像),Cohere(embeddings), Mistral,加上图像和 embedding 子目录。 1 API,一个IAM表面,一个云表输出。贝德洛克的赌注是,客户比他们想要单一模型更想要选择性。

**Azure OpenAI**——独家合作关系。你可以在 Azure 数据中心使用 GPT-4 / 4o / 5 / o-series、DALL·E、Whisper，以及对 OpenAI 模型进行 fine-tuning。“Azure OpenAI Service”目录中没有非 OpenAI 模型；这些模型由另一个产品 Azure AI Foundry 提供。Azure 押注 OpenAI 会保持前沿地位，而客户希望围绕这一特定合作关系获得企业级管控。

**阴性人工智能** — Gemini 首先,其他的都得等一秒 Gemini 1.5 / 2.0 / 2.5 Flash and Pro, 加上模型花园(第三方)。token Gemini 上下文是差异符。

<a id="latency-gap-at-scale"></a>

### 规模的延迟差距

人工分析持续使用基准。 Llama 3.1 405B部署(按需分摊),东经 OpenAI 中位数token 延迟时间大约50米;贝德洛克大约75米。 差距不是AWS故障,而是能力模型差异。 Azure出售PTU(临时输送单位),保留该单位。 GPU 租户的容量。Bedrock的等值(临时输送量)存在,但每单位开始大约21美元/小时,大多数客户按需共享。

随需共享能力与其它客户的流量竞争。 专用能力并不。 如果您的产品在P99时的TTFT < 100 ms, 您要么在阿祖尔购买PTU, 购买Bedrock 提供传输, 要么接受默认差异 。

<a id="provisioned-throughput-economics"></a>

### 提供投入经济学

亚祖尔PTU: 保留区块 inference 计算。 超过~ 70%的节余与需求对可预见工作量的响应。 固定的每小时费用, 不论交通情况如何—— 即使空闲时您也要支付预订费用。 平衡通常大约为40- 60%的持续使用。

贝德洛克提供的投入:根据模型和区域,每小时21-50美元。 类似的数学——平衡大约是高峰期的一半,需要每月承付。

供应的阴性激素容量按每件出售 Gemini SKU;定价因模式和区域而异,而且较少公开公布。

<a id="finops-surface--the-real-differentiator"></a>

### FinOps 表面—— 真正的差异

**贝德洛克应用程序 Inference Profiles** 显示市场中最干净的属性。 `team`, `product`, `feature`; 路径通过所有模型的引用; 云表在不进行后处理的情况下打破每个剖面图的成本。 添加了 2025, 仍然是最颗粒的超标原生体 。

**Vertex** 属性是每个团队的项目加标签。 您将每个团队建模为 GCP 项目, 在每一个资源上贴标签, 并使用 BigQuering Billing + DataStudio 进行卷起。 更多工作, 但大Query 给了您任意的 SQL 成本数据。

**Azure** 使用订阅/ 资源组范围加标签, 将 PTU 保留为头等成本对象。 标记是从资源组继承的, 不是请求, 所以每个请求的归属需要应用程序 Insights 定制的度量或印页盖的网关 。

模式:贝德洛克是最干净的本地人, 维特克斯通过大奎里最灵活,阿祖尔最不透明,除非你乐器。

<a id="lock-in-is-the-2026-risk"></a>

### 锁定是2026年的风险

单一高度承诺在一种模式占主导地位时是好的。 Claude 3.7 四分之一, Gemini 下一秒2.5个 GPT5号,然后是1号平台 锁在2/3的边界

模式工作组采用:任何产品关键型的供应商最低限额为2人。 LLM 贝德洛克加阿苏 OpenAI 它们是共同的一对 Claude 来 GPT 与另一个不同,它们之间互不相干,相同的网关。 availability 断气时升起( 如阿苏) OpenAI 2025年1月事件,AWS 东一号停机)是决定性的。

<a id="data-residency-baas-and-regulated-industries"></a>

### 数据居住区、BAAs和受监管行业

贝德洛克:大多数区域BAAs;VPC终点; guardrails常见的fintech默认。
Azure OpenAI:HIPAA, SOC 2, ISO 27001;欧盟数据居住;企业监管违约。
vertex: HIPAA, GDPR, 每个区域的数据居住区; Google Cloud 的合规堆。

这三个选项都符合基本检查框。 差异在于数据保存政策、日志处理方式以及滥用监测是否读取您的流量( 默认大多数选择使用; 企业可选择退出 ) 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- Azure OpenAI 中位 TTFT 开 Llama 3.1 405B等值:~50毫秒(与PTU)
- 底盘中位点TTFT:~75毫秒。
- 提供Bedrock的输送量:每单位21-50美元/小时。
- 亚祖尔PTU平衡:~40%-60%的持续使用。
- 高利用率的PTU储蓄与需求:高达70%。

```figure
i4-platform-lanes
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 比较三个综合工作量平台 — — 它根据需求来模拟对私人电话电话和电话服务经济学、TTFT差异和成本归属的忠诚性。 运行它以查看私人电话和电话服务公司在哪些方面能取回资金,市场模式宽度超过私人电话和电话服务公司的差距。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-managed-platform-picker.md`鉴于工作量概况(需要模型、TTFT SLA、每日数量、合规要求),它建议采用一个主要平台、一个后备平台和一个FinOps仪器计划。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。Azure PTU对70B类模型的需求有多大的持久利用?计算平衡,并与广告中的40-60%带作比较。
2. 需要你的产品 Claude 3.7 索纳特和 GPT设计一个双向提供者的部署—— 转到哪个超标、什么网关在前面,什么是失败政策?
3. 受监管的医疗保健客户需要BAAs、美国东部数据居住和100ms P99 TTFT。 features.
4. 你发现贝德洛克的账单是4x 这个月没有交通变化。 Inference 档案,你如何找到罪犯?
5. 读读《月经》 OpenAI 和贝德洛克定价页面。100米token/month Claude 较便宜的 Anthropic API贝德洛克点播 还是布德洛克提供传输?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Bedrock | "AWS LLM service" | 跨行业的模型市场 Claude, Llama泰坦,我说... Mistral, coher 轴 |
| Azure OpenAI | "Azure's ChatGPT" | Exclusive OpenAI 具有企业控制的Azure数据中心模型 |
| 阴性人工智能 | "Google's LLM" | Gemini- 具有第三方模型的模型园的第一个平台 |
| PTU | "专用能力" | 提供产出股-保留 inference GPUs,每小时价格 |
| Application Inference Profile | "铺设标签" | 带有标签的每产品成本/使用量简介,云观察-本地 |
| 模范花园 | "Vertex目录" (Vertex 分类表) | 通用电子格式的第三方模型部分,与 Gemini |
| 双供应商最低 | "LLM redundancy" | 管理所有关键事项的政策 LLM 横跨 ++2 的超标路径 |
| BAA | "海保会的文件" | 商业联系协定;需要初级保健;所有三个机构提供 |
| 虐待监测 | "守门人" | 供应商安全扫描 prompts/产出;企业选择退出 |

<a id="further-reading"></a>

## 进一步阅读

- [AWS 贝德罗克定价](https://aws.amazon.com/bedrock/pricing/) 权威费率卡和规定输送定价。
- [Azure OpenAI 服务定价](https://azure.microsoft.com/en-us/pricing/details/azure-openai/) - 个人经济学和工资卡。
- [电动 AI 生成 AI 定价](https://cloud.google.com/vertex-ai/generative-ai/pricing) — Gemini 级数和模范花园附加费。
- [人工分析 LLM Leaderboard](https://artificialanalysis.ai/) 各个提供者之间持续存在的潜伏和输送量基准。
- [AI杂志——AWS Bedrock诉Azure OpenAI CTO 2026年指南](https://theaijournal.co/2026/03/aws-bedrock-vs-azure-openai/) 企业决策框架。
- [芬诺特-贝德罗克对维特克斯对阿苏尔·菲奥普斯](https://www.finout.io/blog/bedrock-vs.-vertex-vs.-azure-cognitive-a-finops-comparison-for-ai-spend) 分属权并列。
