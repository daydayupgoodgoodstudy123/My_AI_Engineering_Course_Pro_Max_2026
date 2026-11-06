---
name: groupchat-selector
description: Configure an AutoGen/AG2-style GroupChat selector for a task, naming the selector variant, termination, and anti-hot-speaker rules.
version: 1.0.0
phase: 16
lesson: 10
tags: [multi-agent, groupchat, autogen, ag2, speaker-selection]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给任务和 agent 名册, 生成 GroupChat 配置: 选择器、 输入器、 终止规则 guardrails.

显示 :

1. **选择变量 。** 圆柱形(便宜、公平、盲目) LLM- 选定的(通货性、昂贵)或习惯(LLM + 以规则为基础的后退)。
2. **选择输入 。** 如果 LLM- 选择: 最近N消息, agent 特殊性, 转弯计数。 如果自定义: 明确规则 。
3. **终止规则。** Max弹壳, 爆炸 token,目标验证器,或组合。
4. **热声道减低** Per-agent 转弯,选择输入时的语音平衡分数, K 连续转动后强制旋转。
5. **减轻上下浮。** 预测计划(每个角色的广度观察)、汇总 checkpoints,上下文上限 agent.
6. **Observability.** 日志选择器输入, 选择器选择, 一次转 agent latency.

艰难的拒绝 :

- 任意 LLM- 选择的配置, 不记录选择器输入/ 输出。 调试变得不可能 。
- 配置没有最大值_圆帽。
- 对称性聊天(不专门)——使用辩论(Lesson 07)。

拒绝规则 :

- 如果任务有已知的DAG结构, 拒绝 GroupChat 并推荐 LangGraph 确定论静态图。
- 如果任务需要严格的审计线索,请拒绝 GroupChat; 建议 LangGraph 带了检查器
- 如果 agents 超过5-6,拒绝平板的 GroupChat 推荐嵌套组或等级模式。

产出: 1页的 GroupChat 配置简报。 接近成本估算 (C)LLM- 选中的每个回合需要一个选择器呼叫) 。
