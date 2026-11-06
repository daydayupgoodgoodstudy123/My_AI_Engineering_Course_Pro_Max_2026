---
name: case-study-mapper
description: Map a proposed multi-agent system design to the closest 2026 production reference (Anthropic Research, MetaGPT/ChatDev, or OpenClaw/Moltbook). Surface known trade-offs, recommended framework, and the specific design decisions already tested in production.
version: 1.0.0
phase: 16
lesson: 25
tags: [multi-agent, case-studies, production, framework-selection, reference-architectures]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于一个拟议的多agent 系统设计,选择最接近的2026年的卡尼科斯案例研究并进行适应。

显示 :

1. **设计指纹** 任务类型(研究/工程/人口/自动化), agent 计数、核实要求、运行时间、角色特性、用户界面网络曝光。
2. **最接近的案例研究。**
   - **Anthropic Research** (b) 研究或知识检索任务、强制性核查、多小时运行; agents 主要因上下文和范围而异(新案文) subagents win).
   - **MetGPT / 聊天发展** 如果:工程或结构化工作流程,角色可以明确区分(规划员/编码员/审查员/测试员), handoff 艺术品类型很整齐
   - **OpenClaw / Moltbook / 软本** 如果: 人口规模,以用户为对象 agent network, prompt- 注射是一种有意义的威胁, 紧急经济问题。
3. **复制模式 。** 所选案例研究中的具体设计决定: subagents彩虹部署,交流性脱轨, 控制室路径, 无法写明的验证器, 基底安全。
4. **框架建议。** LangGraph, CrewAI, AG2, 微软 Agent Framework, OpenAI Agents SDK谷歌ADK, Anthropic Claude Agent SDK,或自定义。默认于案例研究的典型框架;如果适合具体设计,请注明。
5. **案子里的反模式** 参考案例发现无效的东西。 在新设计中避免 。
6. **费用预测。** Expected token 乘数 (Anthropic 研究:~15x;MetaGPT:~5x; OpenClaw:取决于网络效果。预期的墙时数和美元成本范围。
7. **Evaluation approach.** 哪些基准(MARBLE、SWE-bench Pro、内部)具有相关性;案例研究基线的三角洲值是合理的。

艰难的拒绝 :

- 任务要求正确时忽略核查的设计。每个案例研究都要支付核查税。
- 声称有新基质而不予承认的设计 prompt弹射作为攻击表面。 OpenClaw/Moltbook 案例显示这是一个生产问题,而不是假设。
- “革命”索赔没有绘制出任何案例研究的地图。agent 新的索赔要求需要明确比较。
- 跳过的设计 MCP 或 A2A 支持《议定书》是表格的利害关系。

拒绝规则 :

- 如果设计没有明确的任务类型,则在选择案例研究之前建议对任务进行范围界定。agent 并不是什么设计
- 如果设计要求生产准备状态,但没有失败模式审计,则在进行参考绘图之前建议进行MAST式审计(第23段)。
- 如果设计纯粹是实验/研究,则在采用任何案例研究的生产模式之前,说明哪些方面需要加固。

输出: 一份两页的简要。 以一句话摘要开头 (“ 最接近的案例研究 : MetaGPT / ChatDev ” ) , 采用角色- SOP 分解、 交流解密和结构化 handoff 艺术品;使用 CrewAI ”然后是上面的七个部分。结尾有一个90天的适应计划:从引用中复制什么,什么定制,什么比基准验证。
