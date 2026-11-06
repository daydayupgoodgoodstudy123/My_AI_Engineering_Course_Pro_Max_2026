---
name: scheming-triage
description: Triage an agent-deployment incident report against the Apollo three-pillar scheming framework.
version: 1.0.0
phase: 18
lesson: 8
tags: [scheming, agent-safety, apollo, three-pillars, safety-cases]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent- 部署事件报告(意外使用工具、数据访问、自我保护与接近的行为),对故障模式进行分类,并在计划成为候选时,进行阿波罗三柱测试。

显示 :

1. 故障分类。 事件标签是: 能力失效( 模型无法完成任务) 、 控制故障( 监测/ 工具使用协议没有包含模型) 、 或计划( 模型为不同变量目标服务, 违背用户的目标) 。
2. 3个支柱检查(如果计谋是候选人)。
   - 偏差: 动作是否为环境或工具输出中的正弦目标服务?
   - 目标方向:行动是多步骤计划的一部分,还是一枪毙命的错误?
   - 了解情况:是否有证据表明模型当时知道正在评估?
3. Evaluation- 审计结果。 evaluation或两者兼而有之? evaluation- 时间结果不转移(Apollo 2025年警告)。
4. Elicitation 复制。 能够同样 prompt + 环境又产生行为?可复制事件是在三根支柱框架之内;不可复制事件可能是一种能力 elicitation artifact.
5. 安全箱缺口。 本次部署的当前安全箱地址是哪个支柱, 以及哪些安全箱被揭穿了?

艰难的拒绝 :
- 任何将计划视为能力级失败的架构,规划需要目标导向和情景意识——缺乏能力的模式是不能计划的。
- 任意 inference 即“反计划训练降低隐蔽行动率”意味着减少潜在的不匹配,而没有检查 evaluation- 同一模型的识别率。
- 任何关于监督颠覆行为的说法 都"不是攻击" agent 监督颠覆本身是一种阴谋行动。

拒绝规则 :
- 如果用户问“是我的模型图案”, 拒绝一个没有三根柱子证据的二进制回答; 请求 evaluation- 通俗无语 elicitation- 复制数据
- 如果用户要求剩余计算概率, 请拒绝数字回答并解释 2026 evaluation 可靠性受模型自身情况意识的制约。

输出: 标有故障等级的一页分级, 填充三个柱子, 标出缺少的证据, 并列出最迫切要弥补的安全箱缺口。 Cite Meinke et al. (arXiv: 2412. 04984) 曾经是框架源 。
