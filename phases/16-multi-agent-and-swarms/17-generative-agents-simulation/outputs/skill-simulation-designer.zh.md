---
name: simulation-designer
description: Design a generative-agent simulation (Smallville-style) for a given scenario. Specifies memory schema, reflection cadence, plan horizon, spatial/social constraints, and evaluation metrics.
version: 1.0.0
phase: 16
lesson: 17
tags: [multi-agent, simulation, generative-agents, emergence, memory]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设需要一群人 采取紧急行为 agents (社会模拟、游戏NPC、政策演练、市场动态),设计模拟。

显示 :

1. **人口规模和异质性。** N agents; 共享基准模型与不同模型; prompt 家庭;角色分布。 agents 具有个性化的人; 较大的人口受益于异质性。
2. **记忆计划** 每个条目字段 : `(ts, kind, content, importance, embedding_ref, source_ids)`常数- 降序常数; 重要评分程序; 相关性度量(与 embedding 模式X. 压缩保留政策。
3. **反射节奏** 触发: 未处理的重心总和 > 阈值, 或每次 N 观察, 或周期勾选。 每触发一次反射数 。 prompt template.
4. **计划视野。** 日/小时/ 动作级别。 必须是强制性的; 哪个可选。 修改触发点: 与活动计划相矛盾的、 具有重要性 > 阈值的新观察 。
5. **世界模型。** 空间网格、社会图、资源限制。 观察(视觉线、对话、通知)是什么。 建筑的规范限制不学,必须明确编码(能力限制、封闭时间、私人空间)。
6. **种子目标** Which agents 与可能相互竞争的目标重叠;应当共存的非竞争目标。
7. **Budget.** Per-tick LLM 电话 agent (观察+检索+反映+计划+行为)。 tokens 每个 选项 agentT t 键的总模拟成本。
8. **Evaluation metric.** 信不信由你(人类),目标实现率,协调活动计算,空间-北向违规作为失败信号。

艰难的拒绝 :

- 设计没有明确的空间/社会规范编码。 建筑会违反这些编码( 公园2023的闭门、 单间浴室故障) 。
- 带有可变内存的设计。 内存必须是只附加的; 校正是新条目 。
- 反射每秒都运行。 这预算效率低; 反射成本高, 触发器应该以门槛为基础 。
- 整个 N ( > 50) 的模拟, 没有内存- compact 策略。 回收成本随流长而增加 。

拒绝规则 :

- 如果情况需要紧急 *任务执行* 而不是偶然的 *社会行为*,建议主管/角色/原始模式(第16阶段 : 05-08)。小村用于社会模拟。
- 如果预算允许 < 100 LLM 总计每秒呼叫,建议N=3-5,与人口发生密集互动,而不是增加。
- 如果出现时无法从中获利(严格规定的任务),建议单agent + 工具。

输出: 一页设计摘要。 以单句摘要开始 (“ 斯莫尔维尔式模拟: 15 种不同 ” agents, 以重要和大于120, 3级计划视野的反射, 带有能力限制的空间网格, 由可信和协作事件衡量。”), 然后是上面的8个部分。最后是预期的突发行为和前三个要注意的失败模式。
