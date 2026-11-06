---
name: runtime-picker
description: Pick a production agent runtime (Agno, Mastra, LangGraph, provider SDK) for a given stack, latency budget, and operational shape.
version: 1.0.0
phase: 14
lesson: 18
tags: [agno, mastra, langgraph, runtime, selection]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以堆叠、潜伏预算 需要原始的和操作形状,选择运行时间

Decision:

1. Python + FastAPI + 千个短寿命 agents 每秒 - > **Agno**.
2. TypeScript + 下个.js/Vercel+统一的多提供者 - > **Mastra**.
3. 持久性状态、清晰的图表、失灵后恢复 - > **LangGraph** (第13条)。
4. Claude- 第一种产品,想要 Claude Code harness 形状 - > **Claude Agent SDK** (第17条)。
5. OpenAI- 材贺玻珇璶 handoffs + guardrails + 跟踪 - > **OpenAI Agents SDK** (Lesson 16) 电话:
6. Multi-agent team, actor- 典型的货币,断层隔离 - > **AutoGen v0. 4 自动 Gen** / **Microsoft Agent Framework** (列松14)
7. 基于角色的协作或由事件驱动的确定性工作流程 - > **CrewAI** 船员或流动(第15条)。
8. 以上无一 - > 直接 API 呼叫 + 从第1课中跳出 stdrip 循环。

显示 :

- 简短的决定文件:堆叠、潜伏目标、原始需要、观察权衡。
- 选的赛跑时间,一个最小的脚架
- 如果今天又在使用一个运行时间,则将实施移民计划。

艰难的拒绝 :

- 选择 Agno 或 Mastra 工作负担是按要求缓慢的,但业绩很少会受到阻碍。
- 选一个 TypeScript 运行时间 Python 没有任何理由的单列曲。 agent 代码是一种营业税。
- Picking LangGraph 检查员增加间接费用,简单的工作流程(Lesson 12)避免了间接费。

拒绝规则 :

- 如果用户想要“所有五个运行时间, 比较” , 拒绝。 基准您的工作量; 框架供应商基准是方向性的 。
- 如果用户想要自我主机 Mastra的 `ee/` features拒绝并指明许可证条款。
- 如果产品需要长期的自动合成工作(小时对天),则拒绝自行托管和前往 Claude Managed Agents 或基于队列的架构( Lesson 29)。

输出: 决定 doc+ scffold + README。 结尾处指向课程 24 () , “ 下一步读什么 ” (What to read next)observability和29课(生产运行时间),用于框架以上操作层。
