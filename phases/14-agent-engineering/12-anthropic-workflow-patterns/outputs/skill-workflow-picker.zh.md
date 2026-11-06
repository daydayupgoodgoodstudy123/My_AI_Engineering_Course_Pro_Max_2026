---
name: workflow-picker
description: Pick the right pattern (prompt chain, router, parallel, orchestrator-workers, evaluator-optimizer, or full agent) for a given task and produce the minimal implementation.
version: 1.0.0
phase: 14
lesson: 12
tags: [anthropic, workflows, agents, patterns, minimal]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


根据任务说明,选择适合和产生最小正确执行的最低限度模式。

决定树 :

1. - 你能列举一下台阶吗? **prompt chain** 或 **routing**.
2. 产出是否需要在独立运行中汇总? - > **parallelization** (分解或表决)。
3. 您是否需要一个专家人才库,其成员因任务而异? - > **orchestrator-workers**.
4. 法官通过前你是否需要再加精炼? **evaluator-optimizer** (自定义形状)
5. 以上任何一项,还是职级数取决于中间结果? - > **agent loop** (列松01号)

显示 :

- 用于工作流程:纯函数组成 LLM + tool calls没有框架。
- 用于 agents: 该 ReAct 从01课循环 加上任何工具注册 任务要求。
- 一个 `README.md` 与决定理由、步骤计算,预期 token 以及可观察到的成功标准。

艰难的拒绝 :

- 争取框架(LangGraph自动Gen, CrewAI当任务为三步 prompt 系统 超工程隐藏了实际问题
- 3人管弦乐手是"多 -agent工人们不是 agents;它们 LLM 打电话,用"笔记本"来澄清
- Evaluator-optimizer 没有任何停止条件。 `max_iter` 和"失败的通过"的回转, 循环可以无限旋转。

拒绝规则 :

- 如果用户要求"多agent" 当任务实际上是路由器时,拒绝并重命名。agent 标签包含不需要的操作成本(协调、调试、撤销)。
- 如果用户想要一个开放式研究任务的工作流程,则拒绝并推荐 agent 工作流是用来进行可预测的轨道的
- 如果用户想要 agent 拒绝并推荐 prompt chaining. Agents 添加隐蔽和失效模式; 仅在需要时使用。

输出: 模式选择+最小代码 + README。 结尾处指向13( ) 课时“ 读取下一步什么 ” ( W)LangGraph如果国家需要持久的,第16条(OpenAI Agents SDK) 用于 handoffs 和 guardrails或一年级,如果你选择 agent 毕竟
