---
name: orchestration-picker
description: Pick an orchestration topology (supervisor, swarm, hierarchical, debate, or none) for a given problem and implement it minimally.
version: 1.0.0
phase: 14
lesson: 28
tags: [orchestration, supervisor, swarm, hierarchical, debate]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以产品领域和任务类别,选择最低的地形学。

Decision:

1. 1 agent +工作流程模式(课程12)已经足够? - > 根本不使用地形学。
2. 2-4名负有不同职责的专家? - > **supervisor-worker**.
3. 需要时间和专家才能干净地手淫? **swarm**.
4. 10+专家,主管预算失败? - > **hierarchical**.
5. 准确性比成本重要,多建议方+批评有帮助? - > **debate** (第25页)。

显示 :

1. 选的脚架
2. 上台来 swarm; 将深度限制嵌入等级; 圆顶辩论。
3. Observability 钩子数 handoff 或每步(OTel GenAI跨越,课程23)。
4. 读读我那部分

艰难的拒绝 :

- 呼叫3号 LLM 连续呼叫"多 -agent"这是 prompt chain.
- Swarm 弹跳是肯定的
- 以每只专家1个为底部的等级 branch平坦点

拒绝规则 :

- 如果用户想要多个...agent 单一的 ReAct 循环把手,拒绝和建议一课。
- 如果用户想要主管执行两步任务, 请拒绝并推荐 prompt 链条(Lesson 12)
- 如果域有遵守/审计要求,则拒绝 swarm 并推荐上司或上下级。

输出: 具有决定理由的表层脚架 + README。 结尾处指向13号课( 指向“ 下一步读什么 ” ) ( README) 。LangGraph)执行监督员,课程16(OpenAI Agents SDK) 用于 handoffs- 做为工具,或者25课 讨论细节。
