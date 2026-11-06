---
name: supervisor-designer
description: Design a supervisor/orchestrator-worker system for a given research-style query, specifying lead prompt, worker roles, decomposition rules, and synthesis template.
version: 1.0.0
phase: 16
lesson: 05
tags: [multi-agent, supervisor, orchestrator, anthropic-research, langgraph]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给用户查询, 使其受益于平行 subagent 研究,制作一个主管-模式设计,准备连接到任何框架(LangGraph, OpenAI Agents SDK, CrewAI Hierarchical).

显示 :

1. **复杂度估计。** 此查询简单吗 (1) agent, 3-10 tool calls),中(2-4名工人),或复杂(5+名工人)? Anthropic规模努力的疲劳。
2. **Lead system prompt.** 包括:(a) 分解说明,(b) 合成说明,(c) 明确规则,即铅从来不读原始来源内容,仅读工人摘要。
3. **Worker system prompts.** 每个角色一个,每个单位都指明其狭窄的范围和牵头人预期的产出格式。
4. **次级问题分解规则。** 铅是如何分割查询的?粗略的先行小数,还是直接分解?什么使子问题变得不合格(与另一个问题重叠,过于宽泛)?
5. **综合模板。** 明确的冲突处理规则:如果两名工人返回相互矛盾的事实,合成必须提出分歧,而不是沉默地挑一个。
6. **模特儿配对** 哪个是铅(引因级),哪个是工人(加速/更衣级),请解释一下权衡。
7. **Observability requirements.** Minimum trace 点:计划,每个工人的起/终、合成输入、合成输出。

艰难的拒绝 :

- 任何铅能自行使用的工具设计。 只能进行规划和合成。
- Worker prompts 允许范围漂移(例如“研究与X有关的任何材料”而无约束)。
- 隐藏冲突的合成模板 。

拒绝规则 :

- 如果查询简单(估计低于10) tool calls 总计),拒绝设计,建议单agent 反之,咬住 Anthropic 15× token 成本调查。
- 如果查询是相继的( 第2步需要第1步输出), 则拒绝推荐管道/ 链式模式 。
- 如果用户正在优化确定性和审计,则拒绝监督员应提出 LangGraph 静态图。

输出: 单页设计简报。 从复杂度估算和符合模式的判断开始 ( “ 监督器适合 ” ) 。 如果系统持续运行, 则会使用彩虹部署提醒 。
