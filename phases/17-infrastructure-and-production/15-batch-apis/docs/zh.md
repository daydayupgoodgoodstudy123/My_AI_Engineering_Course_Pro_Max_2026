<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="batch-apis--the-50-discount-as-industry-standard"></a>

# 批处理 APIs：作为行业标准的五折优惠

> 每个主要供应商装运一批合成货物 API 50%的折扣和~24小时的周转。 OpenAI, Anthropic,谷歌,和大多数 inference 平台( Fireworks 批量级, 共批量) 执行相同的模式。 Stack 批次与 prompt 管道的缓冲和隔夜下降到同步无焦的成本的~10%。 规则非常简单: 如果它不是交互的, 它属于批量。 内容生成管道、 文件分类、 数据提取、 报告生成、 批量标签、 目录标记 — 任何容忍24小时延迟的事物, 都留在桌上直到它被批量。 2026年的生产模式是将每一个新的管道分解。 LLM 工作量进入三条通道:交互式(与缓冲同步)、半交互式(与后退同步排队)、批量(夜间、缓存输入堆叠),装作互动但最容容留潜伏废物分钟的工作量。

**类型:** 学习
**语言:** Python (stdlib, 玩具批次- vs- sync 成本模拟器)
**先修要求:** 阶段17 14(Prompt 语义缓冲( S)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出三批供应商 APIs (OpenAI, Anthropic以及50%的折扣+24小时周转担保。
- 计算每一夜分类工作量的堆叠批次+缓存输入的成本,并与同步无焦距基线进行比较。
- 将工作量转换成交互/半互动/批量,并证明车道合理。
- 列出两个陷阱:部分互动(用户预期速度超过24小时)和输出-系统流(每个提供者的批量文件格式不同)。

<a id="the-problem"></a>

## 问题

你们的团队在夜间运送一个报告生成管道。 50,000份文件, 总结每个文件, 汇总摘要, 起草执行摘要。 同步运行需要4小时, 每晚2000美元。 您听到批量文件 。 APIs.

批量能让你减50%。 您也启用 prompt 正在缓冲 system prompt 账单跌到180/晚上, 占基线的9%。同样的管道, 有三个配置变化 。

批量是最便宜的杠杆 LLM 成本工具包是没有人拉。原因主要是组织性的:团队认为“实时”是“早上前”的。这段课就是说,不能把90%的账单留在桌面上。

<a id="the-concept"></a>

## 概念

<a id="the-three-batch-apis"></a>

### 三批货 APIs

**OpenAI Batch API**: JSONL 文件上传并列出请求。 承诺24小时周转( 通常为~ 2-8 小时) 。 输入和输出的50%折扣 tokens. `/v1/batches` 端点。 符合缓存条件的投入也在上面得到缓存输入定价。

**Anthropic 信件栏**: JSONL 上传。 24小时周转。 50%的折扣。 支持 `cache_control` 暗藏文件是明确的, 读取自动在批量中发生 。

**Google Vertex AI 批量预测**: 大查询或 GSS 输入。 Gemini与Vertex输油管结合。

<a id="semantic-asynchronous-not-slow"></a>

### 语义: 模糊, 不慢

批量是"我保证24小时内回来" - - 不是"这需要24小时。"典型P50是2-6小时。 GPU 库存使用不足。

<a id="stack-with-caching"></a>

### 堆放着缓存

一份50k文件的总结 与相同的4K -token system prompt:

- 同步未切换: 50000 ×(输入x4000 + 美元输出x200),按全额计算。
- 同步缓存 : system prompt 首写后缓存; 其余的 49999 获得10x便宜的输入 。
- 批量缓存: 所有以上内容, 加上读写上50%的折扣 。

堆栈:批量+缓存 =~ 10%同步未剪切的帐单。 任何过夜运行并共享的工作量 system prompt 应该用这个

<a id="workload-triage"></a>

### 工作量排减量

**Interactive** 用户等待回复。 TTFT 很重要。 prompt 缓冲,不能分批

**Semi-interactive** 用户提交任务, 只需在分钟内检查。 如果批量不可用, 则以回溯方式进行同步 。 想象中等量 RAG indexing.

**Batch** 用户会“ 早上” 或“ 下个小时” 期待结果。 内容管道、 比例分类、 离线分析。 总是批量, 总是堆叠缓存 。

常见错误:将一切归类为互动,因为管道是生产,生产不是潜伏物——苏丹解放军。

<a id="the-partial-interactivity-trap"></a>

### 部分互动陷阱

Some features 显示交互性, 但可以容忍 5 - 10 分钟。 例如: 一份带有“ 更新” 按钮的晚间客户健康报告。 用户点击刷新; 等待 10 分钟是好的。 团队以同步方式将它发运。 50 个同时发件的刷新费用是批量和发送的邮件的成本 10x 。

问一个问题:“24小时对于这个用户意味着什么?” 如果答案是“他们不会注意到”,那么就分批问。

<a id="the-output-schema-trap"></a>

### 输出系统陷阱

批量文件格式因提供商而异 :

- OpenAI: JSONL,每行一个请求。
- Anthropic: JSONL,每行一条信息;响应格式嵌入。
- vertex: 大查询表或 GSS 前缀, 带有 TFRecord 。

跨供应商写入“ 一批客户端” 意味着每个供应商的适配码。 广告多供应商批量的网关( 键盘、 LiteLLM 某些阶梯) 仍然会将原始格式打包得稀薄 。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 供应商之间的批量折扣:输入+输出50%平坦。
- 苏丹解放军:保证24小时,2-6小时,典型的P50。
- 堆放批次 + 已缓存的输入: ~ 10% 同步未隐藏的成本 。
- 工作量分类规则:如果24小时的延迟期可以接受,则必须分批处理。

```figure
batch-lane-triage
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 计算同步、同步+缓冲、批量和批量+缓冲等工作成本,共50k文件工作量。报告节约了美元和百分比。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-batch-triager.md`鉴于工作量的特点,将分成互动/合并/批次和估计节省。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`需要100公里的输油管token system prompt 和500至token 输出,计算整个堆栈(批量+缓存)的节余与同步基线。
2. 选三个 features 将每个人引向互动/半成批
3. 用户抱怨他们的报告用了3小时。 是批量的错误处理还是合法的交互? 写决定标准 。
4. 批量 API 返回 SLA 是 24 h, P99 是 20 小时。 您如何将这个信息告诉用户? 边框的下游系统行为是什么?
5. 计算折中值: 批量+缓存的共享前缀长度比用您自己保留的整夜运行要便宜多少 GPU?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Batch API | "自动折扣" | 半速,24小时转弯 |
| JSONL | "批量格式" | One JSON 每行请求; OpenAI/Anthropic standard |
| 信件栏 | "Anthropic batch" | Anthropic批量数 API 产品名称 |
| 批量预测 | "异狄氏剂批量" | 静脉注射器的批量 API product |
| 苏丹解放军 | "24小时承诺" | 保证,不是典型的;典型为2-6小时 |
| 工作量排减量 | "互动决定" | 交互式/半批次/批次路线决定 |
| 输出图 | "反应格式" | Per-provider JSONL 版式; 非可移动 |
| 堆积折扣 | "批量+缓存" | ~ 10%的未显示同步账单, 两者都适用 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch) — JSONL 格式和 `/v1/batches` semantics.
- [Anthropic 信件栏](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing) 批量格式和 `cache_control` interaction.
- [AI 批量预测](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/batch-prediction-gemini) — Gemini 批量语义学
- [金融业 - OpenAI 与 Anthropic API 定价 2026](https://www.finout.io/blog/openai-vs-anthropic-api-pricing-comparison)
- [赞・范里尔 LLM API 费用比较 2026年](https://zenvanriel.com/ai-engineer-blog/llm-api-cost-comparison-2026/)
