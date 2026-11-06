---
name: cache-auditor
description: Audit an LLM prompt template and traffic pattern for cacheability. Recommend prompt restructure, TTL choice, parallelization fix, and semantic-cache threshold.
version: 1.0.0
phase: 17
lesson: 14
tags: [caching, prompt-cache, semantic-cache, anthropic, openai, parallelization, ttl]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 prompt 模板、交通模式(抵达率、平行因数)和供应商(Anthropic, OpenAI, Gemini,自办 vLLM),产生一个缓存审计。

显示 :

1. 前缀结构。 将模板分割成静态( 可缓存) 和动态( 不缓存) 区域。 标出前缀中的任何动态内容, 并提议重写 。
2. 技术实验室的选择 Anthropic 5- min ( 1. 25x write) 相对于 1 小时(2x write) 。 选择以到达率为基础, 当前缀在1小时之内被连续重复使用时, 选择 1小时赢 。
3. 平行审计。 计算带有共享前缀的平行请求。 如果 N > 2 和平行, 则需要序列化先行删除模式。 量化预期的账单削减 。
4. Semantic cache 选择。决定是否值得 L1 。 开放式聊天: 也许不( 低点击) 。 结构化的 FAQ / 支持: 是。 设置余弦阈值, 开始0. 95; 仅以响应质量的 Eval 向下调 。
5. 预计节省。 计算每月 $ delta 相对于 无缓冲基线, 以当前流量和预计的点击率为准 。
6. 可见。一个仪表板测量仪表板,它可以捕捉回归:L2缓存在上一个滚动时段的点击率;如果跌落 > 20%,则警告。

艰难的拒绝 :
- 要求“ 50%的储蓄” 而不计算预期的点击率和写作溢价。 拒绝 - 计算每个层次 。
- 当简单的重写移动时, 将动态内容保留在前缀中。 拒绝签名 。
- 使用共享的前缀, 且不连带第一模式的平行请求。 拒绝 — 声明5- 10x 帐单通胀 。

拒绝规则 :
- 如果 prompt 大于80%的动态内容 token拒绝承诺缓存,建议最好还是用语义来缓冲
- 如果 semantic cache 门槛值降至0.85以下,没有反应质量的反弹,拒绝- hallucination 隐蔽风险
- 如果服务商不支持明确的缓存_控件( 非)Anthropic, 非Gemini注意,打击率是机会性的,没有保证。

产出:一页审计清单,列出前缀重写、TTL、平行模式、L1门槛值、预期节余、可观察。 prompts 在任何模板修改后。
