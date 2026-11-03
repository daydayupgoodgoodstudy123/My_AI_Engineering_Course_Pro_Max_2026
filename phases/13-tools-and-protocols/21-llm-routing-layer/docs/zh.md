<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="llm-routing-layer--litellm-openrouter-portkey"></a>

# LLM 路由层：LiteLLM、OpenRouter、Portkey

> 供应商锁定费用昂贵。 不同的工具调用工作量适合不同的模式。 运行网关给一个 API 表面、重试、故障、成本跟踪 guardrails。三种类型在2026年占主导地位:LiteLLM(开放源码自托管)、OpenRouter(管理SaaS)、Portkey(生产级,开放源码于2026年3月)。这堂课命名了决策标准并沿着一条标准路径通道前进。

**类型：** 了解
**语言:** Python (stdlib, 路由+故障+成本跟踪器)
**先修要求:** 阶段13 02 (function calling13阶段 17(门路)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 区分自营、管理和生产级路线选择。
- 实施一个后备链,按照确定的优先顺序对供应商的故障进行重试。
- 每一请求的跟踪费用 token 供求者之间的使用。
- 选择LiteLLLM、 OpenRouter 和 Portkey 之间的生产限制 。

<a id="the-problem"></a>

## 问题

供应商路线很重要的假设情况:

1. **成本.** Claude 索纳特要3倍于海库的花费。 对于分级任务,海库就够了;对于合成任务,索纳特值得。每个请求都得路线。

2. **Failover.** OpenAI 时间不好,每个请求都失败了 Anthropic 无需重新部署。

3. **Latency.** 现场聊天的UI需要快速的时间到第一...token. 批量摘要没有。

4. **Compliance.** 欧盟用户必须留在欧盟区域,按区域分列。

5. **Experimentation.** A/B两个模型,工作量相同,用测试桶运进。

每一个整合的手动编码都是重复的。 路径网关给出了一个 OpenAI-compatible API 处理 rest.

<a id="the-concept"></a>

## 概念

<a id="openai-compatible-proxy-shape"></a>

### OpenAI- 兼容的代理形状

所有人都说话 OpenAI- 形状,路由通道暴露了 `/v1/chat/completions`,接受 OpenAI 和内部的替代 Anthropic / Gemini 客户不在乎

<a id="model-aliases"></a>

### 模型别名

而不是被钉住的快照ID 你的代码说 `our_smart_model`。网关地图用别名显示真实模型。当供应商载运新一代时,您可以更改别名服务器侧面;您的代码不会触动任何东西。

<a id="fallback-chains"></a>

### 后退链

```
primary: openai/gpt-4o
on 5xx: anthropic/claude-3-5-sonnet
on 5xx: google/gemini-1.5-pro
on 5xx: refuse
```

网关在配置中定义此选项。 重计根据预算计算, 所以后退级联不会爆炸成本 。

<a id="semantic-caching"></a>

### 语义缓冲

Identical-or-near-identical prompts 击中一个缓存而不是提供者。 agent loops 30到60%。 embedding- 基于;接近相同 prompts 共享缓存槽 。

<a id="guardrails"></a>

### Guardrails

Gateway-level:

- **PII 编辑。** 发送前的 Regex 或基于 ML 的通行证 prompts.
- **违反政策。** Reject prompts 含有违禁内容。
- **输出过滤器 。** 漏水时的灌木补全

港仔和香港两艘船都认为 guardrails利特尔姆让他们任选

<a id="per-key-rate-limits"></a>

### Per-key rate limits

One API 键 = 一个团队。 每一个关键预算阻止一个团队使用共享配额。 大多数网关支持这一点 。

<a id="self-hosted-vs-managed-trade-offs"></a>

### 自我托管与管理下的权衡

| 因素 | 利特尔姆(自办) | 打开路由器( 管理) | 港口钥匙(生产) |
|--------|----------------------|----------------------|----------------------|
| 代码 | 开源 Python | 管理 SaaS | 开放源码(Mar 2026)+管理 |
| Setup | 部署代理服务器 | 签个名 | 要么 |
| Providers | 100+ | 300+ | 100+ |
| Billing | 钥匙 | 打开 Router 信用 | 钥匙 |
| Observability | OpenTelemetry | Dashboard | 完整 OTel + PII 编辑 |
| 最适合 | 想要完全控制的团队 | 快速原型 | 遵守规定生产 |

LiteLLM 赢得了您拥有 SRE 团队并想要数据主权。 如果您想要单次订阅, 而没有次下载, 打开 Router 赢得了 。 需要时端口键会赢 guardrails 和遵守出盒子。

<a id="cost-tracking"></a>

### 费用跟踪

每一个请求都包含 `provider`, `model`, `input_tokens`, `output_tokens`。每模型乘以每模型-token 价格(从网关的定价表中提取)。

<a id="mcp-plus-routing"></a>

### MCP 加上路线

网关可以同时经过 LLM 电话和 MCP sampling 请求。 sampling 请求的模型Preview 偏好于一个特定的模型, 网关会转换为右后端。 这是第13阶段 ・ 17 的 。MCP 课程的路径连接有时会合并成一个服务。

<a id="routing-strategies"></a>

### 分期付款战略

- **静态优先级。** 列表中的第一个; 错误时返回 。
- **负载平衡 。** 圆柱或加权。
- **Cost-aware.** 选最便宜的模型 见面时的延迟/质量。
- **Latency-aware.** 选上个N分钟里最快的模型
- **Task-aware.** Prompt 分类路径编码到一个模型,总结到另一个模型。

```figure
tp-router-failover
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行~ 150 行的路径网关: 接受 OpenAI- 形形请求, 转换为每个提供者的根根, 运行优先的后退链, 跟踪每个要求的成本, 并应用 PII 编辑输入。 运行它时有三种情况: 正常请求, 初级提供者的断线触发后退, PII 渗漏被编辑捕获 。

需要关注的内容：

- `ROUTES` dict:别名 - > 优先排序的具体提供者清单。
- 5xx的回路回路重回
- 成本跟踪器乘数 token 按每模型费率计算的使用率。
- PII 重新加载器在传输前清洗 SN 形状的图案 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-routing-config-designer.md`。根据工作量概况(时间、成本、合规性),技能选择了LiteLLLM/ OpenRouter/Portkey,并制作了路径配置。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`触发断电情景;确认第二个供应商的后退土地,成本被正确计算。

2. 添加语义缓冲: SHA256 prompt 是一个查找键; 缓存点击会立即返回。 测量一次重复呼叫的成本节约 。

3. 添加a prompt 代码的分类器... prompts 给一个假名 支持智慧和"总结..." prompts 来个假名,以速度为主

4. 设计每组预算:每个团队都有每月支出上限;一旦上限被击中,网关会拒绝申请。 选择执行颗粒( 每一个请求或窗口) 。

5. 读取利特勒姆、 OpenRouter 和 Portkey docs 并排。 列出其中的 feature 每艘船舶,而另外两艘则不这样做。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 运行通道 | "LLM proxy" | One-API- 在许多供应商面前的地表层 |
| OpenAI-compatible | 说到 OpenAI schema" | Accepts `/v1/chat/completions` 形状,翻译为任何后端 |
| 型号别名 | "我们的_smart_模型" | 密码中的姓名, 连接到混凝土模型的网关地图 |
| 后退链 | “ 重试列表” | 失败时试图提供的有条理的供应商名单 |
| 语义缓冲 | "Prompt-embedding cache" | 键是 embedding 的 prompt; 近似重复的共享缓存被击中 |
| Guardrails | “产出/产出过滤器” | 重编 PII, 拒绝违反政策 |
| Per-key rate limit | 团队预算 | 限额 API key |
| 费用跟踪 | "请客费" | Aggregate token 使用量 x 每个模型的价格 |
| LiteLLM | "开放代理" | 开放源码软件自控路径通道 |
| OpenRouter | "管理好的萨斯" | 设有以信用计费的网关 |
| Portkey | "生产选择" | 以 guardrails 建于 |

<a id="further-reading"></a>

## 进一步阅读

- [利特尔姆 - 医生](https://docs.litellm.ai/) 自行托管的路线网关
- [打开 Router - 快速启动](https://openrouter.ai/docs/quickstart) - 管理路线SaaS
- [端口钥匙-医生](https://portkey.ai/docs) 生产路线 guardrails
- [真理-LitellM 与 OpenRouter 的对立](https://www.truefoundry.com/blog/litellm-vs-openrouter) ——决定指南
- [中继机 LLM 网关比较 2026](https://relayplane.com/blog/llm-gateway-comparison-2026) 供应商调查
