<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="llm-observability-stack-selection"></a>

# LLM Observability 技术栈选型

> 2026年 observability 市场分为两类。 开发平台( LangSmith, Langfuse, Comet Opik) 将监测与 Evals 捆绑在一起, prompt 网关/仪器(Helicone、SigNoz、OpenLLMetry、凤凰)侧重于遥测。兰富斯是麻省理工学院许可的核心,具有很强的开放源码软件平衡(50K事件/月度自由云)。凤凰城是Elastic 许可证2.0下的开放遥测数据,极适合漂移/漂移。RAG 可视化,不是持久性生产后端。 AX 使用零副本 Iceberg/ Parquet 集成, 声称比单板便宜100x observability。兰斯密斯的线索 LangChain/LangGraph,39美元/用户/mo,仅在企业号上自行托管。 agent traces通用生产模式:通过开放遥测仪粘贴的网关(Heliconne/Portkey)+电子平台(Phoenix/TruLens)。

**类型:** 学习
**语言:** Python (斯迪利布,玩具) trace-sampling simulator)
**先修要求:** 阶段17 · 08 (Inference 计量,第14阶段(Agent Engineering)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 区分发展平台(组合:评价+ prompts + 会议),来自网关/遥测工具(traces + 仅限量度)。
- 地图六大工具(Langfuse、LangSmith、Phoenix、Arize AX、Helicone、Opik),
- 解释开关的遥测格模式, 使您能够将网关工具与单独的 eval 平台结合起来 。
- 命名 2026 成本差异器 (Arize AX的零副本法与单板摄入量之比) , 并标出粗略 100x乘数 。

<a id="the-problem"></a>

## 问题

你运了个 LLM feature起作用了,你没有能见度 prompt failures,工具循环,潜伏回归,成本攀升,或 prompt- 破烂的点击率,你谷歌"LLM observability" 并获得八种工具,它们都声称它们用三个不同的价格点解决了同样的问题。

他们不能解决同样的问题 兰斯密斯回答"为什么这样做 LangGraph 跑步失败?"凤姐回答"是我的 RAG 管道漂流?" Helicone回答"哪个应用程序在燃烧 tokens兰富斯回答"我能自己主持吗?" 不同的工具,不同的观众

选取涉及四个轴: 堆叠 (S)LangChain生来 SDK? 多供应商? ,许可容忍(只允许麻省理工学院? 确定? 商业罚款? ) ,预算(免费水平? 100美元/美元? 1 00美元? ) , 以及自我托管(必须? 美好吗? 永远不? )

<a id="the-concept"></a>

## 概念

<a id="two-categories"></a>

### 两类

**发展平台** bundle observability 与评估, prompt 管理、数据组版本、会话重播。您运行实验,请查看 prompt 工作, 数据集回归为新 prompt 朗斯密斯,兰福兹,彗星奥皮克

**网关/遥测工具** instrument inference 电话... prompt,反应, tokens静脉、模型、成本。 Helicone, SigNoz, OpenLellMetry, Phoenix. 最小化。可以通过 OpenTelephat 与一个单独的电子工具合并。

<a id="langfuse--oss-balance"></a>

### 朗福斯-开放源码软件平衡

- 核心阿帕奇/麻省理工学院领有执照;通过 Docker.
- 无云级:每月50K活动,支付:团队29美元/月。
- Evals, prompt management, traces,数据集。所有四个平台的合理覆盖 features.
- 甜点: 你想要兰斯密斯级 features 但要自己做主或者继续持有开放源码软件许可证

<a id="phoenix-arize--telemetry-first-opentelemetry-native"></a>

### 凤凰城(阿瑞兹)——遥测第一,开放遥测-本土

- 弹性驾驶证2.0;
- 不错 RAG 和漂浮的视觉化。 Embedding- 太空散落地上,作为头等舱运货
- 并非设计为持久性生产后端——主要是开发时间 observability.
- 可爱的地方: RAG 管道开发,漂移调试,配有单独的生产网关。

<a id="arize-ax--the-scale-play"></a>

### Arize AX —— 比例游戏

- 商业:通过冰山/Parquet进行零副本数据湖集成。
- 索赔 ~ 100x 比单曲便宜 observability 缩放(数据类) traces 在您自己的 PARKET 上 S3; Arize 直接读取 。
- 甜点: > 10M traces每天,现有的数据湖,想要 LLM- 特定的仪表板没有数据狗定价。

<a id="langsmith--langchainlanggraph-first"></a>

### 兰斯密斯 LangChain/LangGraph first

- 商业,39美元/用户/月,仅对企业号自行托管。
- 最优秀的班级 LangChain 和 LangGraph 堆叠。如果你没有在,它就不那么有说服力了。
- 甜蜜的一席之地: 团队致力于 LangChain愿意付钱

<a id="helicone--proxy-based-minimum-viable"></a>

### 赫利科内——基于代理的最低可行度

- 15 -30分钟设置,换掉 `OPENAI_API_BASE` 致赫利科尼代理。
- 麻省理工学院领执照;免费100K req/mo,支付20美元/mo+。
- 包括故障、缓存、 rate limits - 也当个通道
- 深度小一点 agent / 多步数 traces.
- 甜点:快速启动,单堆应用程序,需要网关+ observability 在一个。

<a id="opik-comet--oss-dev-platform"></a>

### Opik(彗星)-OSS dev平台

- 阿帕奇2.0,完全的开放源码软件。
- Similar feature 设置为带彗星遗产的兰富斯。
- 甜点: ML团队已经在彗星上,想要 LLM observability 在同一条窗帘里

<a id="signoz--opentelemetry-first-full-apm"></a>

### SigNoz - 开放遥测系统- 第一层完整

- 2. 处理一般杀伤人员地雷 LLM 通过开放遥测。
- 甜点: 统一 observability 服务领域和 LLM calls.

<a id="the-glue-opentelemetry--genai-semantic-conventions"></a>

### 胶水:开放遥测+GenAI语义学

2025年底发表了GenAI语义学公约(GenAI)`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`使用 OTel 的工具可以相互操作。 正在出现的生产模式 :

1. 与GenAI公约的OTel LLM call.
2. 每天通向网关(Helicone/Portkey)的路线。
3. 双重船到电子平台( Phoenix / Langfuse) , 用于回归 。
4. 将数据湖(冰山)存档,以便通过Arize AX或DuckDB进行长期分析。

<a id="the-trap-instrumenting-at-the-wrong-layer"></a>

### 陷阱: 仪器在错误的层

里面有乐器 agent 框架(例如,添加 LangSmith) traces和你们一起到那个框架。 HTTP/OpenAI-SDK 平面( 通过 OpenLellMetry 或您的网关) 具有可移动性。

<a id="sampling--you-cant-keep-everything"></a>

### Sampling - 你不能把一切都留着

每天1万份申请,全trace 留存费用超过 LLM 调用。 以规则为例: 100%的错误, 100%的高成本, 5%的成功。 总是保持总和; 保持粗糙的长尾巴 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 兰弗斯自由云:每月50K事件。
- 兰斯密斯:39美元/用户/月。
- 免费的赫利酮:100克朗/月
- Arize AX索赔: ~ 100x比标度的单石块便宜。
- GenAI开放遥测公约:2025年航运,2026年广泛通过。

```figure
i4-otel-glue
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟 1M -trace 每天(100%摄取, sampling, sampling +错误)报告存储成本和每件之下损失的。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-observability-stack.md`。根据堆叠、规模、预算、许可证态势,选择工具。

<a id="exercises"></a>

## 练习

1. 球队在 LangChain 想要自己托管开放源码软件 observability选择朗弗斯或奥皮克,并解释
2. 5点 traces每天与Datadog 引用每月150K,计算Arize AX的折叠。
3. 设计一个 Open 遥测 GenAI 属性, 设置您或组织的指导 。 LLM call.
4. 问一下菲尼克斯是否足以生产。
5. 赫利科内是20米的代理机顶,在P99 TTFT 300米的高度,可以接受吗?如果SLA是100米呢?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| OpenLLMetry | "奥特为 LLMs" | 用于 LLMs |
| GENAI 公约 | "奥特属性" | 标准 OTel 属性名称 LLM calls |
| LangSmith | "LangChain observability" | 商业平台包装 LangChain ecosystem |
| Langfuse | 奥斯兰斯密斯 | 具有类似功能的MIT OSS feature set |
| Phoenix | "武装德维兹工具" | 开放遥测- 本地 dev/ eval 平台 |
| 自动交换 | "scale observability" | 商业零副本冰山/石板 observability |
| Helicone | "proxy observability" | HTTP 代理收藏 LLM 遥测+网关 features |
| Opik | "Comet LLM" | 彗星的Apache 2. 0 OSS dev平台 |
| 会话重播 | "trace rerun" | 重放一个完整 agent 与会议 tool calls |
| Eval | "脱机测试" | 正在运行的候选人模式/prompt 标签数据集 |

<a id="further-reading"></a>

## 进一步阅读

- [西格诺斯- 顶端 LLM Observability 工具 2026](https://signoz.io/comparisons/llm-observability-tools/)
- [朗富斯-阿里兹 AX替代分析](https://langfuse.com/faq/all/best-phoenix-arize-alternatives)
- [普雷马里——设立朗弗斯、兰斯密斯、赫利科内、凤凰城](https://blog.premai.io/llm-observability-setting-up-langfuse-langsmith-helicone-phoenix/)
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [凤凰医生](https://docs.arize.com/phoenix)
- [赫利科内医生](https://docs.helicone.ai/)
