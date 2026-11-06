---
name: skill-cost-patterns
description: Decision framework for LLM cost optimization -- caching strategies, rate limiting, model routing, and budget controls
version: 1.0.0
phase: 11
lesson: 11
tags: [caching, cost-optimization, rate-limiting, model-routing, budget, llm-ops]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="llm-cost-optimization-patterns"></a>

# LLM 成本优化模式

当建造 LLM 应用本决定框架控制成本。

<a id="when-to-optimize"></a>

## 何时优化

**立即优化:**
- Monthly LLM 支出超过500美元,即基础设施预算的10%
- 消费者产品每查询的费用超过0.01美元
- 你的 system prompt 超过1000 tokens 并随所有请求一起发送
- 30%以上的查询是重复或近乎重复的
- 你正在从100个增加到10,000个以上的日常用户

**尚未优化时 :**
- 您的DAU还不到100个, 并且仍然在验证产品市场是否合适
- 月支出低于100美元,增长缓慢
- 你还是在转 prompt 设计(将您锁定为 prompt)

<a id="caching-strategy-selection"></a>

## 缓存策略选择

<a id="exact-caching"></a>

### 精确的缓存

**使用时间 :** temperature=0, 相同 prompts 重复,需要决定性的产出。

```python
key = sha256(json.dumps({"model": m, "messages": msgs, "temp": 0}))
```

- 执行:30分钟
- 点击率:大多数应用程序为10-25%,常见问题机器人为40-60%
- 延迟时间: < 1ms( 命令查询)
- 风险:如果基本数据发生变化,则反应会停滞

**跳过时 :** temperature > 0,每个查询都是独特的实时数据。

<a id="semantic-caching"></a>

### 语义缓冲

**使用时间 :** 用户用不同语言、常见问题产品、客户支持等提出同样的问题。

- 执行:2-4小时(embedding +相似度+储存)
- 点击率: 精确缓存之上的15-35%
- 长期:10至50米(embedding +ANN 搜索)
- 风险: 假阳性( 返回错误缓存回答类似但不同的问题)

**阈值准则:**
- 0.98+:非常保守,几乎没有假阳性,打击率较低
- 0.95: 事实的平衡
- 0.90:攻击性强、打击率高但回答错误的风险
- 0.85:只针对低录取率申请(建议,自动完成)

**跳过时 :** 每个查询都有独特的上下文(代码生成), 回复必须反映最新数据, 查询空间是无限制的 。

<a id="provider-prompt-caching"></a>

### Provider prompt caching

**使用时间 :** system prompt > 1,024 tokens (OpenAI或特定模型的最低值,同一前缀反复发送。

| 提供商 | 动作 | Savings |
|----------|--------|---------|
| Anthropic | Add `cache_control: {"type": "ephemeral"}` 以 system message | 90%的缓存前缀( 写价25% 后) |
| OpenAI | 无( 自动) | 50%在缓存前缀上 |
| 谷歌 | 使用上下文缓存 API 具有明确的 TTL | ~75% 位于缓存上下文 |

**跳过时 :** system prompt 每项请求的变动 prompt 长度最小。

<a id="model-routing-rules"></a>

## 示范路线规则

<a id="keyword-based-simple-fast"></a>

### 基于关键字( 简单、 快)

```
simple:  <= 5 words OR matches FAQ keywords -> gpt-4o-mini ($0.15/$0.60)
medium:  general queries, summaries        -> claude-sonnet ($3/$15)
complex: "analyze", "compare", "debug"     -> gpt-4o ($2.50/$10)
```

- 执行:1小时
- 准确度:70-80%
- 节省:模型成本的40-60%

<a id="embedding-based-more-accurate"></a>

### Embedding- 基于(更准确)

嵌入每个分类的50-100个标签查询。 由最近的邻居分类新的查询 。

- 执行:4-8小时
- 准确度:85-92%
- 节省:模型成本的50-70%
- 额外费用:~0.02/1亿美元 tokens 用于分类 embeddings (negligible)

<a id="ml-based-production-grade"></a>

### 以最低水平为基础(生产等级)

训练一个小分类器( 后勤回归或小 BERT) 历史查询/模型对。

- 执行:1-2周
- 准确度:90-95%
- 节省:模型成本的60-75%
- 要求:生产流量中贴有标签的训练数据

<a id="rate-limiting-configuration"></a>

## 限制配置的速率

<a id="token-bucket-parameters-by-tier"></a>

### Token bucket parameters 按级别

| Tier | 桶大小 | 补充率 | 最大 RPM 值 | 每日上限 |
|------|-------------|-------------|---------|-----------|
| 免费 | 50K tokens | 500/sec | 10 | 50公里 |
| Pro | 500K tokens | 5K/sec | 60 | 500K |
| Enterprise | 5M tokens | 50K/sec | 300 | 5M |

<a id="implementation-checklist"></a>

### 实施清单

1. 将多功能应用程序储存在 Redis(非模拟)
2. 利用原子行动(多边/EXEC)防止种族状况
3. 返回 `Retry-After` 带有拒绝回复的标题
4. 追踪被拒绝的请求,将其作为衡量标准( > 5%的拒绝=过紧的分层限制)
5. Implement graceful degradation:先拒绝昂贵的模型请求,保持廉价的模型访问

<a id="budget-controls"></a>

## 预算控制

<a id="three-threshold-circuit-breaker"></a>

### Three-threshold circuit breaker

| 阈值 | 动作 | Reversible |
|-----------|--------|------------|
| 占每月预算的70% | 记录警告,通过 Slack/ PagerDuty 警报小组 | 是(自动) |
| 占每月预算的85% | 通向最便宜的车型 | 是( 自动, 下个账单周期) |
| 占每月预算的95% | 只提供缓存响应, 拒绝新 LLM calls | 是( 手工重设或下个周期) |

<a id="per-user-cost-tracking"></a>

### 用户费用跟踪

跟踪每个用户的累积成本。 旗用户超过中位数 10 倍。 常见原因 :
- 合法电源用户( 升级其级别)
- Prompt injection 循环( 机器自动发送请求)
- 整合效率低下( 客户重试每次错误)

<a id="cost-tracking-fields"></a>

## 费用追踪领域

记录每 API 使用这些字段调用 :

```json
{
  "timestamp": "2026-04-02T10:30:00Z",
  "model": "gpt-4o",
  "input_tokens": 1523,
  "output_tokens": 487,
  "cached_input_tokens": 1024,
  "latency_ms": 1847,
  "cost_usd": 0.006142,
  "user_id": "user_abc123",
  "cache_status": "partial_hit",
  "request_category": "customer_support",
  "complexity_class": "medium",
  "routed_from": "gpt-4o"
}
```

<a id="key-metrics-to-dashboard"></a>

### 仪表板的关键度量

- **每个查询的费用** (P50, P95, P99) -- -- 按模式分列 feature,按用户级别
- **缓存点击率** -- 准确的语义,趋势随时间推移
- **型号分布** - 每种模式的交通流量百分比,每种模式的成本
- **预算燃烧率** - 按目前费率计算,目前的支出与按月预测的支出之比
- **拒绝率** - 请求率受限制的百分比,按级别分列

<a id="common-mistakes"></a>

## 常见错误

| 错误 | 为何痛 | 修复 |
|---------|-------------|-----|
| 缓存 temperature > 0 | 非确定性输出, 过期缓存显示错误的种类 | 只存缓存临时=0 电话, 或者接受缓存响应会失去随机性 |
| Semantic cache 门槛太低 | 表面上相似的查询返回错误的答案 | 开始于0.95, 仅测量假正率后降低 |
| 没有缓存无效 | 当基础数据改变时, 回复会变得静止 | 设置TTL(1小时动态数据,24小时静态数据),数据更新无效 |
| 将所有交通都转往最便宜的模型 | 质量下降, 用户注意 | 按复杂程度分列的路线,按层次衡量质量,设定最低质量阈值 |
| 用户无限制 | 一名虐待使用者烧毁整个预算 | 始终执行每个用户的配额,即使慷慨 |
| 忽略输出 tokens | 产出成本比投入每件多2-5x token | 设定最大值_适当使用标记 stop sequences压缩产出 |
| 之前的缓存 prompt 稳定 | 缓存包含旧的响应 prompts | 仅在以下启用缓存 prompt 完成, 开始冲洗缓存 prompt changes |

<a id="pricing-reference-as-of-april-2026"></a>

## 定价参考(截至2026年4月)

| 模型 | 输入 ($/1M) | Output ($/1M) | 缓存输入( 1M) | 最适合 |
|-------|-------------|--------------|--------------------|---------| 
| gpt-4.1-nano | $0.10 | $0.40 | $0.025 | 高容量简单任务 |
| gpt-4o-mini | $0.15 | $0.60 | $0.075 | 简单路径、 分类 |
| gemini-2.5-flash | $0.15 | $0.60 | $0.0375 | 预算多式联运 |
| claude-haiku-3.5 | $0.80 | $4.00 | $0.08 | 快速中层任务 |
| o4-mini | $1.10 | $4.40 | $0.275 | 预算理由 |
| gemini-2.5-pro | $1.25 | $10.00 | $0.3125 | 长环境, 多式联运 |
| gpt-4o | $2.50 | $10.00 | $1.25 | 通用设备, function calling |
| claude-sonnet-4 | $3.00 | $15.00 | $0.30 | 平衡质量/成本 |
| claude-opus-4 | $15.00 | $75.00 | $1.50 | 最高质量,复杂推理 |
