---
name: batch-triager
description: Triage LLM workloads into interactive / semi-interactive / batch lanes, compute stacked discount (batch + cache) savings, and flag mis-triaged workloads.
version: 1.0.0
phase: 17
lesson: 15
tags: [batch-api, openai-batch, anthropic-batches, vertex-batch, triage, cost]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


工作量(名称、用户对延迟期的预期、流量、共享) prompt 结构),产生一个分级+成本计划。

显示 :

1. Lane 。 交互式( TTFT- 绑定、 同步) , 半交互 (分钟确定, 自动队列) , 或者批量( 逐小时确定, 批次) API)))说明用户的具体期望。
2. 当前成本。 计算按当前配置( 同步、 无缓存等) 计算的月成本 。
3. 目标成本。 计算推荐配置后的成本( 批量+缓存或同步+缓存) 。 Express 表示为当前值的% 。
4. 移徙计划:提供方的具体步骤(选择与工作量模式相符的步骤,而不是两者兼具):
   - OpenAI:移徙至 `/v1/batches`. Prompt 自动启用缓存以适应符合条件 prompts (≥1024 tokens) — 否 `cache_control` 选择通过 `prompt_cache_key` 来更严格地确定归属
   - Anthropic: 迁移到信件栏。缓存需要明确再使用 `cache_control` 区块(例如, `{"type": "ephemeral"}`) 上可缓存 prompt 横线; 带有缓存读取定价的批量折价堆叠。
   - 两者: 都使用成功/失败的网络钩和溢出通道来同步 以配合那些错过翻转窗口的批次 。
5. 风险。 如果批次周转在P99为20小时呢? 请列出下游系统的行为( 电子邮件传送、 排队溢出到同步) 。
6. 观察。 抓错位数的测量: 批量完成工作时的P95; 12小时以上警告 。

艰难的拒绝 :
- 以同步模式运行一个隔夜管道, 而不批量运行, 当用户只需要“ 早上” 的延迟时间。 拒绝 — — 点出漏掉的~ 90% 。
- 15分钟内有用户预期的分批采购,拒绝——分批销售服务协议是24小时。
- Ignoring prompt 分批处理工作量,并分担 system prompt拒绝 - 堆叠折扣是关键。

拒绝规则 :
- 如果工作量被作为“实时”销售,但实际用户的期望是分钟,则在建议批次之前必须明确确认。
- 如果工作量针对没有 prompt 批次缓存(例如,任何自定义或自托管堆栈,不重复使用 KV 前缀), 注意只有批次折扣适用, 且重新计算而不节省堆叠。 OpenAI 批量的缓存是自动的; Anthropic 批量缓存需要明确 `cache_control` blocks.
- 如果工作量严格处于延迟状态(例如P99 < 60s),则完全拒绝批次,即属于另一条路。

产出:一页长的分级,车道、当前成本、目标成本、迁移步骤、风险和可观测到的。结尾是连续:随着产品表面的变化,每季度重新处理所有工作量。
