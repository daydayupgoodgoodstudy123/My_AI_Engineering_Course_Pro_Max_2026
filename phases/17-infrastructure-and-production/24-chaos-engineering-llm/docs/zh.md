<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="chaos-engineering-for-llm-production"></a>

# LLM 生产环境中的混沌工程

> 混乱工程 LLMs 2026年,它自己的学科。 trace+metric+log observability自动 rollback结构有四架飞机:控制(实验调度器)、目标(服务、以下、数据储存)、安全(警卫+中止+交通过滤器) observability (计量+ traces +日志,反馈(转入 SLO 调整)。 Guardrails 强制要求: 如果每日错误预算燃烧 > 2x , 燃烧率提醒暂停实验; 抑制窗口+ trace- ID 相关脱壳警报噪音。 间隔: 每周小金丝雀+ SLO 检查; 每月游戏日+ postmortem;每季度跨团队复原力审计+依赖性绘图。 LLM- 特定实验:内存超载、网络故障、供应商停机、畸形 prompts, KV cache 驱逐风暴。 Harness 混乱工程LLM- 派来的建议, 爆炸性辐射降级, MCP 工具集成; 立木船(CNCF); 混凝土网(CNCF) Kubernetes-native).

**类型：** 了解
**语言:** Python (斯迪利布,玩具混乱实验选手)
**先修要求:** 阶段17 23(大赦国际特别建议),阶段17 13(Observability)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出五个混乱工程的先决条件(SLI/SLO, observability, rollback解释为什么不把任何做法打破。
- 4架飞机的图解(控制、目标、安全、 observability)和反馈循环到 SLO。
- 编号五 LLM- 特定实验(模拟超载、网络故障、供应商停机、畸形) prompt),
- 选择一个工具 Harness立特穆索斯,混杂的马什——给一堆。

<a id="the-problem"></a>

## 问题

传统堆叠中的混杂物测试已经建立。 LLM 堆叠添加新的失败模式。 A 4K-token prompt 与毒气字符拖慢 tokenizer 12秒。上游供应商429秒;网关转机;重试的货币货币服务。A KV cache 暴风雨爆发导致...prefill 饱和的级联计算。

没有一个在单位测试中出现。混乱的工程是你如何在用户之前发现它们。

<a id="the-concept"></a>

## 概念

<a id="prerequisites"></a>

### 先修要求

生产时不要乱跑,没有:

1. **SLI/SLO** 界定服务级别指标和目标。
2. **Observability** — traces计时器 日志 贴在仪表板上
3. **Automated rollback** · 17阶段 20个政策旗帜 rollback.
4. **Runbooks** 分阶段,第17阶段 23阶段
5. **On-call** - 来人回应

失去任何手段 混乱成为真正的事件。

<a id="four-planes--feedback"></a>

### 四架飞机+反馈

**控制飞机** 实验排程器( Litmus 工作流程, 混亂 Mesh 排程, ) Harness UI).

**目标飞机** 服务、舱、节点、货平衡器、数据储存。

**安全飞机** 杀关、压压窗、防爆线限制、错误预算门。

**Observability plane** - 正常度量+ trace- 识别与分辨混乱和自然故障的关联性

**反馈循环** 调查结果反馈到 SLO调整,运行手册更新,代码修正。

<a id="guardrails-are-mandatory"></a>

### Guardrails 强制性

- **烧速警报**:如果每日错误预算燃烧超过预期 2x,则暂停实验。
- **禁止窗口**:在试验期间,在爆炸半径内静默非实验警报。
- **Trace- ID 相关关系**:所有实验引起的错误都带有标签,以便待命时能够解开。

<a id="five-llm-specific-experiments"></a>

### Five LLM- 特定实验

1. **内存超载** 强制 a KV cache 以高通货率发送长文本请求来防止先发制人风暴。 观察: 服务是否优雅地失效或崩溃?

2. **网络失败** 切断两个机构之间的联系 inference 观察:苏丹解放军内部是否出现回弹? (第17阶段 · 19)

3. **供应商中断模拟** 100% 429发自 OpenAI。观察:路径失败到 Anthropic? (第17阶段 16,19)

4. **Malformed prompt** - 注射 tokenizer- 固定有效载荷(例如,深巢) unicode大型 UTF-8 代码点。 观察: 是否只提出一个请求就锁住工人?

5. **KV驱逐风暴** 饱和强迫驱逐 vLLM 显示: LMCache 是恢复还是服务退化?

<a id="cadence"></a>

### Cadence

- **Weekly** 小型金丝雀实验正在进行,也许5%的精选
- **Monthly** 特定情景的预定游戏日;跨组出席; postmortem.
- **Quarterly** 跨团队复原力审计;依赖性地图更新。

<a id="tooling"></a>

### Tooling

- **Harness 混乱工程** 商业;AI派生的实验建议;降低爆炸性辐射; MCP 工具集成。
- **LitmusChaos** - 国家妇女理事会毕业; Kubernetes workflow-based.
- **混乱网** - 国家妇女理事会 sandbox; Kubernetes- 本地的CDD风格
- **Gremlin** 商业;广泛支持。
- **AWS 功能性** / **片断混乱工作室** 管理云献

<a id="starting-small"></a>

### 开始小

第一个实验: 以稳定的交通模式解码复制。 保留重置路线和恢复。 如果这个方法可行且看起来安全, 则会逐渐陷入网络混乱 。

First LLM具体实验:输入一个供应商429 5分钟。观察后退。大多数团队发现后退没有完全测试。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 四架飞机: 控制,目标,安全, observability.
- 燃烧速率暂停: 2x 预算预期每天燃烧。
- 周金丝雀,每月游戏日,季度审计。
- Five LLM 实验:内存、网络、提供者、畸形 prompt科沃风暴

```figure
i4-chaos-guard
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟三次混乱实验, 试验用安全平面门。 实验会比燃烧率流产高出多少 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-chaos-plan.md`。根据堆叠和成熟度,先选择三个实验和工具。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。哪个实验会去燃烧率的大门,为什么?
2. 设计第一个五大混乱实验 vLLM-based RAG 服务。包括成功标准。
3. 你的燃烧率警报暂停了实验。你如何确定根源——混乱还是自然?
4. 争论生产究竟是应该混乱还是只要中转。 何时生产才是正确的答案?
5. 名称三 LLM- 特定故障模式,通用网络机组无法复制。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 斯利/斯洛沃 | "服务目标" | 指标+目标;所需先决条件 |
| 爆炸半径 | "scope" | 受试验影响的服务/用户 |
| 烧速警报 | "预算门" | 当错误预算燃烧速率 > 2x 时开火 |
| 游戏日 | "每月演习" | 计划跨组混乱演习 |
| LitmusChaos | “CNCF工作流程” | 毕业于国家妇女理事会 Kubernetes 混乱工具 |
| 混乱网 | "CNCF CDD" (CNCF CRD) (美国中央情报局) | CNCF sandbox Kubernetes- 本地混乱 |
| Harness CE | "商业AI辅助" | Harness 混乱与大赦国际的建议 |
| Malformed prompt | "tokenizer bomb" | 缓期输入 tokenization |
| KV驱逐风暴 | "先锋级联" | 大规模驱逐引发prefills |

<a id="further-reading"></a>

## 进一步阅读

- [DevSecOps学校——混乱工程2026年指南](https://devsecopsschool.com/blog/chaos-engineering/)
- [安库什·夏尔马 Observability 用于 LLMs (book)](https://www.amazon.com/Observability-Large-Language-Models-Engineering-ebook/dp/B0DJSR65TR)
- [立木船(CNCF)](https://litmuschaos.io/)
- [混乱网(CNCF)](https://chaos-mesh.org/)
- [Harness 混乱工程](https://www.harness.io/products/chaos-engineering)
- [AWS 功能性](https://aws.amazon.com/fis/)
