---
name: hierarchy-fitness
description: Decide whether a multi-agent task fits hierarchical, flat supervisor, or sequential. Surface the failure modes that matter.
version: 1.0.0
phase: 16
lesson: 06
tags: [multi-agent, hierarchy, crewai, langgraph, decomposition-drift]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于任务说明和可选的星体结构,建议协调模式(平板主管、等级主管、顺序主管)并列出具体故障模式。

显示 :

1. **任务形状分析。** 是任务 单线流, 与独立 branches还是有自己小队的巢状小组?
2. **判决模式** 序列、 平板或等级。 如果分级, 请指定深度 ( 2 个级别 , 3 个级别 , 需要 严格的审计 ) 。
3. **分解计划** 顶层经理应该做的精确分割。 对于每个 branch,指定子管理员和外壳范围。
4. **调节预算。** 高级经理必须前允许的回合数 commit默认 2。
5. **Guardrails.** 三个最低 guardrails:每层金丝雀工人, 每种合成的源头链, 分解漂移的警报。
6. **失败模式核对表 。** 最有可能的是任务形状 { task- 指派错误、 输出错误、 共识环} ? 描述每个模式的一个具体症状和一个缓解方式 。

艰难的拒绝 :

- 任何建议,如提出深度大于2,而没有指明具体审计或要求的或有组织要求,则需说明深度大于2。
- 单线流任务等级。 这些应该是连续管道 。
- 没有明确调节预算的设计。

拒绝规则 :

- 如果任务简单到适合 agent (在~10以下) tool calls),拒绝等级,建议单agent.
- 如果任务没有自然的团队界限(每个子步骤取决于其他步骤),则拒绝并建议集体聊天模式。
- 如果用户想要“现实主义”的等级(因为人类的兽体很深), LLM 高低的等级,建议奉承

产出:一页简报。打开时使用模式判断,结束三个最大风险及其 guardrails.
