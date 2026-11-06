---
name: framework-picker
description: Pick LangGraph, CrewAI, AutoGen, Agno, or plain Python for an agent task by matching abstraction to problem shape.
version: 1.0.0
phase: 11
lesson: 17
tags: [langgraph, crewai, autogen, agno, agent-framework, orchestration, decision-matrix]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于任务说明(问题形状,总计) LLM 一次运行呼叫, 分支模式, 耐久性和恢复需求, human-in-the-loop checkpoints,平行的扇子,会话内存,预期每天运行量),输出:

1. 形状匹配。 一句话命名适合的抽象名称: 图( 类型状态、 名称转换) , org 图表( 专家角色、 管理器路径) handoffs),聊天(agents 单声道直到结束) agent 使用工具。 如果您无法选择一个, 任务不是 agent- 形状还不错,停止和分解。
2. 分支权威。 谁选择下一步: 开发者( 明确边缘) , 管理者 LLM (CrewAI 自动调用自路(Agno), 自动调用。 token 费用 LLM- 酌情选择路线。
3. 国家预算。确认是否需要恢复启动后、时间旅行或人为中断。如果需要, LangGraph 赢得状态第一抽象; Agno 只覆盖会话范围内存 。
4. 框架选择。 langgraph, crewai,自动,阿格诺,普通_python 。 包含一个一则理由, 用于绘制形状和状态, 以解析框架的核心抽象 。
5. 逃生舱,如果每天运行量超过10_千块,或者两块或更少 LLM 拨打无状态,建议简单 Python 与提供者 SDK 相反,在任务小的情况下,没有一个框架是最快的框架。

拒绝推荐 AutoGen 使用已知的 DAG 的确定性工作流程; GroupChatManager 花费 tokens 选择发言者,开发者可以静态地电线。 CrewAI 通过 `output_pydantic` / `output_json` (see [docs.crewai.com/en/concepts/tasks](https://docs.crewai.com/en/concepts/tasks)),但该词 `context` 频道仍然流过下一个任务 prompt 字符串。 推回 CrewAI 当工作流程依赖于原始 `context` 以结构化状态执行任务,而不连接其中的一个输出模式。 LangGraph 要求2个电话摘要;国家格鲁夫管理费是纯税。 当任务粉丝横跨4个以上平行的副工人,使用减义词时,将重压回阿格诺; Agno 船舶a `Parallel` 键,其输出加入按步名键的对齐(见 [docs-v1.agno.com/workflows_2/overview](https://docs-v1.agno.com/workflows_2/overview) 和 [docs.agno.com/workflows/access-previous-steps](https://docs.agno.com/workflows/access-previous-steps)),但它没有暴露发牌式的扇子和剪切 API 与 LangGraph's.

示例输入 : “ 长期研究工作流程: 计划, 向三个检索者发送信息, 合成, 人类批准摘要, 撰写报告, 引用源代码 。 崩溃后必须恢复 。 生产将每天运行50次 。 ”

输出示例：
- 形状: 图形。 输入计划, 三个平行检索器, 命名合成和写入之间的转换 。
- 分流: 开发者通过有条件边缘决定。 没有每个回合管理器 LLM.
- 国家:要求恢复和人为干扰。 LangGraph mandatory.
- Framework: langgraph状态、发送扇形消息、中断_之前,和邮差救护 全部头等舱。
- 逃生舱:不适用。 每天50次运行远低于平原 -- --Python 门槛值和工作流程太明显,无法脱离框架。
