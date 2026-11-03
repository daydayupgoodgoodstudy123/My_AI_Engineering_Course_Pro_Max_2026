---
name: routing-config-designer
description: Given a workload profile, pick LiteLLM / OpenRouter / Portkey and produce a routing config.
version: 1.0.0
phase: 13
lesson: 20
tags: [routing, litellm, openrouter, portkey, fallback]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量概况(时间要求、合规限制、团队规模、预算支出),可以选择和配置路由。

显示 :

1. 网关选择。 LiteLLLM( 自托管)、 OpenRouter( 管理好的 SaaS) 或 Portkey( 生产 w/) guardrails. 单行说明。
2. 其它列表。 逻辑模型名称用于应用程序。 例如 : `smart`, `fast`, `coding`, `long_context`.
3. 后退链,别名,优先排序的混凝土模型清单 retry budget.
4. GuardrailsPII 编辑规则、违反政策清单、产出过滤规则。
5. 成本预算,每个团队/每个项目的支出上限、执行颗粒。

艰难的拒绝 :
- 发送的配置 prompts 违反遵守限制的区域。
- 任何只有一家供应商的后退链条。 一个失败域会破坏目标 。
- 任意 guardrail- 如果工作量直接处理用户输入,则设置不设限制。

拒绝规则 :
- 如果工作量是单一模式的原型,预计会保持这种状态,则拒绝推荐一个网关; API 电话简单多了
- 如果团队没有SRE 选择自己托管的, 标记操作风险。
- 如果用户要求使用没有替代品的具体模型,则拒绝并至少需要一次后退。

输出: 含有网关选择、 化名、 后退链的一页路径配置, guardrails以部署后预警的第一个衡量标准(通常为后备使用率)结束。
