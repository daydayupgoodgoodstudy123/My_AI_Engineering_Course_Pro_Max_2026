---
name: gateway-picker
description: Pick an AI gateway (LiteLLM, Portkey, Kong AI, Cloudflare/Vercel) given scale, latency budget, compliance, ops posture, and pricing tolerance.
version: 1.0.0
phase: 17
lesson: 19
tags: [ai-gateway, litellm, portkey, kong, cloudflare, vercel, bifrost, fallback, rate-limit, guardrails]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于RPS(目前和预计12个月),延迟预算、合规(需要自办主机? ), guardrails 需要( PII 编辑, jailbreak 发现、审计和定价容忍度,提出网关建议。

显示 :

1. 主网关。 名称工具。 使用 RPS 上限、 管理费和 feature fit.
2. 后退链,三个供应商排队 OpenAI → Anthropic 自行托管为卡通式。 计算预期值 availability.
3. 限速政策。 建议的滑坡窗口 > 500 RPS; token- 包可以接受,租客的分级
4. Guardrails键。jailbreak 需要; 需要时, Kong + guardrails; 仅使用 develop 级的LiteLLLM。
5. Observability 13个选取;确认OTel GenAI公约的流通。
6. 移徙:如果从应用层面的融合中转移,则分阶段进行 rollout (网关上的金丝雀占1%,推广成功。)

艰难的拒绝 :
- 拒绝-香港基准显示级联故障;首先迁移。
- TTFT P99 < 100 ms SLA. 的Portkey,拒绝30 ms 间接费用占用了太多的预算。
- 受监管的预科顾客的云花AI网关。拒绝——只管理;没有自我主机。

拒绝规则 :
- 如果规模模糊性很大(目前的100个RPS,计划6个月后2K+),则在承诺使用LiteLLM之前,需要制定迁移计划。
- 如果遵守要求二级SOC, 所选择的门户是开放源码软件,没有管理下的SLA, 则需要客户自己的SOC 2证明。
- 如果球队没有 Kubernetes 并挑选香港的自我主机,拒绝——建议管理好香港或波茨基。

产出:一页决定,包括网关、后备链、费率限制政策, guardrail posture, observability 流动,移民计划,最后有一个标准: 关口P99 超过最后一小时; 警告违反。
