<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="ai-gateways--litellm-portkey-kong-ai-gateway-bifrost"></a>

# AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost

> 网关位于应用程序和模型提供者之间。 features 供应商路线、后退、回溯、费率限制、秘密推荐 observability, guardrails. 2026年市场分割: **LiteLLM** 拥有100多个供应商的MIT OSS, OpenAI- 兼容,但细分为~2000 RPS(8GB内存,公布的基准中串联失败); Python,<500RPS, dev/prototyping。 **Portkey** 是控制式飞机(guardrailsPII 编辑, jailbreak 2026年3月2日,20-40毫升的顶部,49美元/百万元的生产级。 **香港AI 网关** 建在香港网关上——香港自己的基准 CPUs:比Portkey快228%,比LiteLLLM快859%;每模式/月定价100美元(加级最高5美元);如果已经在香港,企业适用。 **Bifrost** 自动重置,可配置后端,后退至 Anthropic 在 OpenAI 429. **云层/ 脉冲AI 网关** 数据居住驱动着自我托管决定; 港务局和香港处于开放源码软件+可选管理的中间。

**类型:** 学习
**语言:** Python (stdlib,玩具网关路由模拟器)
**先修要求:** 阶段17 · 0.1 (管理) LLM 平台,第17阶段 16(模式运行)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出六个核心网关 features (路线、后退、重写) rate limits秘密,我告诉你 observability, guardrails).
- 绘制四条2026年的网关(LiteLLM、Portkey、Kong AI、Bifrost),以衡量上限和使用案例。
- 使用香港基准(228%对Portkey,859%对LiteLLLM),并解释为什么它对于 > 500 RPS很重要。
- 选择自托管还是管理给定数据居住权与行动预算。

<a id="the-problem"></a>

## 问题

产品调用 OpenAI, Anthropic,并自我托管 Llama。每个提供者都有不同的 SDK错误模型 rate limit,以及验证方案。您想要失败(如果 OpenAI 429s,试试看 Anthropic),一个单一的证书库,统一 observability, 和 rate limits 每个租户。

重新发明这个在应用程序层的夫妇 每一个服务提供方。 一个网关层将它合并成一个过程 API (typically OpenAI- 和供应商的呼声一致

<a id="the-concept"></a>

## 概念

<a id="six-core-features"></a>

### 六颗核心 features

1. **供应商路线** — OpenAI, Anthropic, Gemini,自办等 API.
2. **Fallback** - 在429,5xx或质量故障时,在其他地方再试一次。
3. **Retries** 以指数反弹, 并被捆绑。
4. **Rate limits** - 租客,每包钥匙,每套模型。
5. **秘密参考** 使用运行时(在应用程序中绝无此功能)从金库提取证书。
6. **Observability** - OTel + GENAI属性(第17阶段-13)+成本归属。
7. **Guardrails** PII 编辑, jailbreak 检测,允许的话题过滤器。

<a id="litellm--mit-oss-python"></a>

### 利特尔姆 - 麻省理工学院, Python

- 100+ 供应商, OpenAI- 兼容,路由器配置,后退,基础 observability.
- 香港基准值约为2000卢比,其中8GB记忆足迹,连续负载下层层故障。
- 最佳匹配 : Python 应用程序, < 500 RPS, dev/staking 网关,实验路线。
- 费用:开放源码软件为0美元;有无云层。

<a id="portkey--control-plane-positioning"></a>

### 控制飞机定位

- 2026年3月的Apache2.0开放源码软件。 GuardrailsPII 编辑, jailbreak 侦测,审计线索。
- 20 -40 ms per- request lantency over. 20 -40 ms subject. 20 -40 ms lotance subness. 20 -40 ms. 请求的顶部。
- 49美元/百万元,用于生产级,保留+SLA。
- 最佳适用性:需要监管的行业 guardrails + observability bundled.

<a id="kong-ai-gateway--the-scale-play"></a>

### 香港AI网关——比例游戏

- 建在香港网关上( 成熟) API 网关产品,lua+OpenResty)。
- 香港自己12点的CPU 等效:比Portkey快228%,比LiteLLLM快859%。
- 定价:100美元/模型/月,最高5美元加级。
- 最佳条件:已经在香港; > 1 000 RPS;愿意获得执照。

<a id="bifrost-maxim-ai"></a>

### 最佳独立研究所

- 自动重试, 配置后端 。
- 返回到 Anthropic 在 OpenAI 429是金刚石食谱
- 较新的入门;商业。

<a id="cloudflare-ai-gateway--vercel-ai-gateway"></a>

### 云层AI网关/电动AI网关

- 管理、零操作。基本重试 observability.
- 最佳条件:为边缘服务 JavaScript 云花/Vercel上的应用程序。
- 与Kong/Portkey的比较有限 guardrails 和 rate limits.

<a id="self-hosted-vs-managed"></a>

### 自我托管与管理

数据居住权是一种强制功能。医疗保健和融资默认自机主(LiteLLM或Portkey OSS或Kong),消费者产品默认管理(Cloudflare AI Gateway)或中层(Portkey管理)。混合:为受监管的租户自行托管,为他人管理。

<a id="latency-budget"></a>

### 长期预算

- 5 -15米的上空,典型。
- 门锁: 20 -40米的上空。
- 刚: 3 -8米
- 云层/电弧: 上面1-3毫秒(前沿优势)。

网关悬浮直接加到TTFT上。对于TTFT P99 < 100 ms SLA, Kong 或 Cloudflare, 对于P99 < 500 ms, 任何。

<a id="rate-limit-semantics-matter"></a>

### 限速语义物质

Simple token- 桶的操作范围可达到中等规模。多租户需要滑动窗口+爆破备抵+每租户的分级。 token- 港轮滑船窗;

<a id="gateway--observability--routing-compose"></a>

### 网关+ observability + 路线拼写

阶段17 · 13 (observability+ 16 (模式路线)+ 19 (门道)是生产中的同一层。选择一种工具覆盖所有三种或仔细地连接它们:大多数2026年部署的组合了Helicoone(observability或 邮政(guardrails与Kong(比例)分拆角色。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 里特尔姆: 中断时间为~ 2000 RPS, 8 GB 内存 。
- 包钥匙:20-40米高空;自2026年3月以来为Apache 2.0米高空。
- 香港:比波特基快228%, 比利特尔姆快859%。
- 香港价格:每模型/月100美元,加级最高5美元。
- 云层/电弧: 悬崖1 -3米

```figure
mx-gateway-fallback
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟网关路径, 以在 429/5xx 下 插入 3 个供应商 的 后退 。 报告 延迟度、 重试率 和 后退 率 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-gateway-picker.md`。根据规模、行动态势、合规性、潜伏预算,选择了一条网关。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`配置从 OpenAI→Anthropic自动托管。预计的点击率是5% 供应商错误率?
2. 贵国的LAF是300米基线上的TTFT P99 < 200米。
3. 医疗保健客户需要自行托管+ PII 编辑+ 审计。 选择 Portkey OSS 或 Kong 。
4. 比较LiteLLLM与Kong:团队应该迁移到哪一座RPS天花板?
5. 设计一个多租户SaaS的费率限制政策:免费级、试用级、付费级。 Token- 酒桶还是滑窗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Gateway | "API broker" | 应用程序和提供者之间的程序 |
| LiteLLM | "麻省理工学院" | Python OSS, 100+供应商, 2K RPS 休息时间 |
| Portkey | "guardrails gateway" | 控制飞机+ observability,阿帕奇 2. |
| 香港AI 网关 | 头号 | 建在香港网关上,基准头目 |
| Bifrost | "马克西姆的大门" | 重试+ Anthropic 后退配方 |
| 云花AI网关 | "顶部管理" | 边缘部署管理网关,零操作 |
| PII 编辑 | "数据清洗" | 在发送到模型之前, Regex + NER 掩码 |
| Jailbreak detection | "prompt injection guard" | 用户输入分类器 |
| 审计线索 | "管制日志" | 每一个 LLM call |
| Token-bucket | "simple rate limit" | 以再充填率限制值 |
| Sliding-window | "precise rate limit" | 时间窗口利率限制; 更公平 |

<a id="further-reading"></a>

## 进一步阅读

- [香港AI 网关基准](https://konghq.com/blog/engineering/ai-gateway-benchmark-kong-ai-gateway-portkey-litellm)
- [真理——AI网关 2026比较](https://www.truefoundry.com/blog/a-definitive-guide-to-ai-gateways-in-2026-competitive-landscape-comparison)
- [技术-顶级 LLM 网关工具 2026](https://techsy.io/en/blog/best-llm-gateway-tools)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [Portkey GitHub](https://github.com/Portkey-AI/gateway)
- [香港AI 网关文档](https://docs.konghq.com/gateway/latest/ai-gateway/)
