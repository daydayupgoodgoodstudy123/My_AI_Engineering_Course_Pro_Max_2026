---
name: production-rag
description: Deploy a regulated-domain RAG chatbot with role + jurisdiction filtering, prompt caching, guardrails, and live drift monitoring.
version: 1.0.0
phase: 19
lesson: 08
tags: [capstone, rag, chatbot, regulated, llama-guard, nemo-guardrails, ragas, langfuse]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于有规范的地产(法律合同、临床试验协议、保险单或类似),应部署一个聊天室,以可核查的引证回答问题,尊重作用和司法准入政策,并监测漂移情况。

构建计划 :

1. 以 docling 或无结构分析元素; 通过 ColPali 路径显示丰富的文档。 Emit 块块, 带有角色和权限标签 。
2. 指数密度(Voyage-3或Namic-emed-v2) 成 pgvector + pgvictor 标度; 稀有 BM25 通过Tantivy。
3. Wire LangGraph conversational agent:检索(按角色+管辖权过滤,混合密度+BM25, reciprocal rank fusion),重排(bge-reranker-V2-gemma-2b或Voyage重排-2),合成(Claude 索内特4.7与 prompt caching).
4. Assemble prompts 具有稳定的前缀:系统序言 - > 政策块 - > 重排上下文 - > 用户查询。 prompt- 缓冲击中率。
5. Guardrails: Llama 内莫,输入和输出的卫兵4 Guardrails v0.12 用于非域和政策禁止问题的轨迹,输出上的Presidio PII清洗,引用后过滤器。
6. 制作一套200个问题的专家标签的金色的(回答、引用),准确引用的比对分、正确回答、RAGAS的忠诚。
7. 建一个50 -prompt 红队(PAIR、TAP、PII提取、外域、跨管辖区探测器)。
8. 凤凰号漂流仪表盘追踪搜索 NDCG 和引用忠诚度周刊; 警告5%下降。
9. 朗弗兹成本报告: prompt- 缓冲击中率, tokens 每个查询,美元/克雷里 逐级。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | RAGAS 忠诚+回答相关性 | 网上评分 在200号问题金色组 |
| 20 | 引用正确 | 含有可核查源锚的回答分数 |
| 20 | Guardrail coverage | Llama 警卫4人及格率+ jailbreak 套件结果 |
| 20 | 费用/潜伏工程 | Prompt- 破烂弹,p95 延迟,$/克雷 |
| 15 | 漂移监测仪表板 | 具有每周检索质量趋势的凤凰号实况仪表板 |

艰难的拒绝 :

- 任何聊天室泄漏跨法域数据。 角色+管辖过滤必须在检索前强制进行, 而不是在获取后 。
- Synthesis prompts 中断缓存前缀( 在系统和上下文之间重新排序策略) 。 将会破坏缓存经济学 。
- Guardrail 配置未登录的红色队运行 。
- 答复不引证;引用不引证可核实的锚。

拒绝规则 :

- 拒绝在受管制的域内部署 没有管辖权的标记 每一个块。
- 拒绝在专家标签的金色问题上进行检索。 污染会破坏Eval的信誉。
- 拒绝在README中没有明确的SOC2/HIPAA/GDPR适用矩阵的情况下要求“符合”要求。

输出:含有摄入管道的回收站, LangGraph conversational agent问200号金牌50号prompt 红队 凤凰漂流仪表板 兰福斯成本仪表板 还有一张写上 prompt 每一个都解决
