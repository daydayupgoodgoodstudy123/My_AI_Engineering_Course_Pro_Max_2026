---
name: vllm-stack-decider
description: Decide vLLM deployment layout — production-stack Helm chart, KV offload (native CPU or LMCache), router/observability integration — given workload and fleet size.
version: 1.0.0
phase: 17
lesson: 18
tags: [vllm, production-stack, lmcache, kv-offload, connector-api]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


视工作量而定(prompt 机队(发动机, GPU 类型)和操作环境(Kubernetes- 本地、多租户、预算),生产a vLLM 堆叠计划

显示 :

1. 堆叠。 使用 vLLM 生产堆叠电路图(建议新部署)或滚动你自己。 操作员/ 重整电路程序适用的国家 。
2. KV 卸载。 选择 :
   - 无( 短 prompts低货币——间接费用超过效益)。
   - Native vLLM CPU 卸载( 单引擎 HBM 压力, 简单) 。
   - LMCache 连接器(多引擎前缀再利用、先发制人重力或多租户共享) prompts).
3. 监测 HBM 使用情况。 `--gpu-memory-utilization` 以预发信号维持922号警戒
4. 路由器集成。 Cache-aware路由器(第17阶段 · 11) 确认 KV 事件频道配置 。
5. Observability· Prometheus 刮刮每个发动机,OTel GenAI属性(第17阶段-第13阶段),Grafana 仪表板模板,取自生产堆放。
6. 预期影响。 量化预期的输送量增量相对于当前量—— 参考16x H100 基准形状( 当 KV 足迹超过 HBM 时, LMCAche 帮助 )

艰难的拒绝 :
- 不加共同的预言或先发制人地部署LMCACHE。
- Running vLLM 拒绝,先发制人将是一个惊喜。
- 手滚生产堆积,当赫尔姆图覆盖使用情况时。

拒绝规则 :
- 如果舰队有 < 2 引擎,就拒绝使用LMCache—— 跨引擎再利用是关键;单引擎是本地使用的。
- 如果工作量 prompts < 1K 级 tokens 和 < 100 conconconcondal, 拒绝卸载任何类型的货物- HBM 头部已足够 。
- 如果团队没有K8的能力, 拒绝生产堆放器—— 从单引擎开始 vLLM + 简单代理。

输出:一页命名堆叠、 KV 卸载选择、 HBM 监测、路由器整合 observability以单门结束: HBM 使用 P99 在过去24小时。
