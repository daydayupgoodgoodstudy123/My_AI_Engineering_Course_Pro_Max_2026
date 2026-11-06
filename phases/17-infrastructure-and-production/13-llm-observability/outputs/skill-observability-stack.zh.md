---
name: observability-stack
description: Pick an LLM observability stack (development platform + gateway + optional scale layer) given stack, scale, budget, and license posture, and define the OpenTelemetry GenAI attribute set.
version: 1.0.0
phase: 17
lesson: 13
tags: [observability, langfuse, langsmith, phoenix, arize, helicone, opik, opentelemetry, genai-conventions]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定堆栈( P)LangChain / 软性/原始 SDK), 比例 (traces预算、许可证态势(仅限MIT与商业许可)和自营单位要求 observability plan.

显示 :

1. 发展平台选择。LangChain要么是首个广告,要么是"彗星OSS",要么不是"星际开放源码软件", 加上堆叠和许可证
2. 网关/ 遥测选择。 Helicone( 代理+网关)、 SigNuz( 全 APM)、 OpenLLMetry (纯 OTel) 如果已经使用 AI 网关( 17 阶段 · 19) , 请命名整合 。
3. 比例/ 片层。 可选; 长期分析的 AX 或原始冰山, Phoenix for RAG drift.
4. OTel GenAI 常规。 请指定最小属性集 : `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.request.temperature`, `gen_ai.response.finish_reasons`,加上具体项(租户)_ID, 用户_任务)
5. Sampling 政策。 100%错误,100%高成本( > 0.10/call),N%成功 sampling 原保留窗口(14d/30d/90d)。
6. 警告。五个必须具有警报的尺度:错误率、P99 TTFT、成本/要求、 prompt- 缓冲击球率,拒绝率。

艰难的拒绝 :
- 具体框架内仪器 SDK 拒绝-框架锁定。
- 100%保持 traces 数据狗类价格 > 500美元/百万,用于无管制的工作量。 sampling.
- 无视开放遥测GenAI公约。拒绝 — 2026年互换要求它们这样做。

拒绝规则 :
- 如果 traces每天 > 5M,小组坚持完全保留数据犬,拒绝不作费用预测。
- 如果团队只选麻省理工学院的 选择兰斯密斯,拒绝——朗福斯就是麻省理工学院的同等人。
- 如果团队没有AI网关 选择赫利科内作为网关 observability接受 - 代理服务器加倍作为门户,最多~ 500 RPS(第17阶段 · 19 级涵盖网关比例)。

输出: 命名 dev 平台、 网关、 比例层( 如果有的话) 的一页计划, OTel 属性集 sampling 规则,五个警告。结尾为信号堆叠漂移的单一度量: LLM 过去七天来,电话里有完整的OTel GenAI属性。
