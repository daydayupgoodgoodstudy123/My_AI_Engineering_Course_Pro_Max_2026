---
name: agent-budget-audit
description: Audit an agent deployment's cost-governor stack and flag missing layers before enabling unattended runs.
version: 1.0.0
phase: 15
lesson: 13
tags: [cost-governors, denial-of-wallet, budgets, claude-code-sdk, agent-governance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议 agent 使用,审计成本管理器堆叠 与十二层参考和标志 缺少, 调得不够,或过度调控。

显示 :

1. **层层清单。** 12个参考层中的每个层(每个请求上限,每个任务) token budget,每个任务美元预算,每个工具帽,迭代上限,每分钟/小时/日/月滚动上限,速度限制,分层路由, prompt 缓存、 上下文窗口、 HITL checkpoints,杀死开关),说明是否配置了它,以及它的价值。
2. **失败模式映射** 每次时间尺度的故障( 运行循环、 缓慢泄漏、 错误释放、 合法激增) 都列出具体层, 以及速度 。
3. **工具专用上限。** 列出每个工具 agent 可以是调用。 对于每个用户, 请指定一个会话上限和理由。 没有明确的上限的任何工具都是一个开放式循环 。
4. **警报阀门** 与上限无关:人们按什么消费率来呼唤?观察到的电子商务案例(1 200美元 $4 800)是一个每周的成长问题,而不是一个月的上限问题。
5. **杀开道** 火盖着火了,会怎样? rollback,警告,可重新启用程序。确认杀死开关是外部 agent (该 agent 无法编辑自己的上限)。

艰难的拒绝 :
- 任何没有按任务编列的预算的自主部署。
- 任何未加注意的长视距运行 没有速度限制。
- 工具表面,在新工具添加时没有每个工具的上限( < 30天)。
- 切换 agent 自己可以改变
- 月上限为唯一的上限(其他时间尺度均无保障)。

拒绝规则 :
- 如果用户无法按今天的模型价格来计算最坏的价格,则拒绝并需要计算成本的估算。
- 如果概算因一个错误超过该组织可接受的损失,则拒绝并要求降低上限。
- 如果用户将自动模式分类器( 列单 10) 视为预算的替换, 请拒绝。 分类器按成本顺序排列; 需要两个层次 。

输出格式 :

以下列方式退回成本管理审计:
- **图层表格** (字符名、配置的 Y/ n、 值)
- **失败模式覆盖** (4行:循环/泄漏/释放/激增)
- **每人的脚盖** (工具、帽子、理由)
- **警报阈值** (速度、所有者、频道)
- **切换路径** (触发、动作、可重生程序)
- **Readiness** (生产/中转/仅研究)
