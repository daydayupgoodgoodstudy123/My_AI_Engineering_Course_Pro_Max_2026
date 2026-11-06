---
name: role-designer
description: Produce a role roster for a multi-agent system, naming the planner/executor/critic/verifier for a given task with explicit I/O schemas.
version: 1.0.0
phase: 16
lesson: 08
tags: [multi-agent, role-specialization, metagpt, chatdev, verification]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


任务,制作一份专门的角色名册,配有I/O的图案和一个确定性核查员。 CrewAI, LangGraph,自动Gen,或自定义环。

显示 :

1. **角色表** 3-5个角色,每个名字,至少:规划者、执行者、核查者。 Critic 可选.
2. **每一角色的I/O方案。** 对于每个角色:它消费什么(来自上游角色)和产生什么(菜鸟,而不是小说)。使用数据类式的标记。
3. **验证说明。** 命名确定性检查: 测试套件、 键取检查器、 系统验证器、 插入器。 描述出入/ 失效标准 。
4. **Critic 规格( 可选) 。** 如果包括的话,请说明它判断的主观质量。具体的清单,而不是“好代码”。
5. **沟通解密规则** 列出每个下游角色在缺少细节时可以向上游提出的问题,这样就不会发明。
6. **修订循环预算。** Max回合后会升到人类身上
7. **框架图。** 每一行一行:如何在 CrewAI, LangGraph自动枪。

艰难的拒绝 :

- 任何名册上都没有确定性核查员LLM 名册上没有进行MAST检查。
- 模糊 I/ O (“ 执行器返回输出 ” ) 。 总是说明计划 。
- Critic 和验证器合并。 它们捕获不同的错误; 如果两者都有必要, 两者都必须存在 。

拒绝规则 :

- 如果任务没有确定性正确性检查(纯基因工作、创造性写作),则拒绝推荐人造审查者循环或多功能-agent 改为辩论(Lesson 07)。
- 如果任务太小,不能发挥3+的作用(10分钟以下的人类工作),则拒绝并建议单agent.

输出: 角色设计简报, 与 MAST 失败格检查关闭: 确认至少存在一个确定性验证器 。
