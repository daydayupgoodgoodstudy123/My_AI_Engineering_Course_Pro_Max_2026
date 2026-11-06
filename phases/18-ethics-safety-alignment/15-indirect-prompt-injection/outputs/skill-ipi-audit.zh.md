---
name: ipi-audit
description: Audit an agentic deployment for indirect prompt injection exposure and information-flow-control coverage.
version: 1.0.0
phase: 18
lesson: 15
tags: [ipi, indirect-prompt-injection, ifc, agent-security, owasp-llm01]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agentic 部署说明,审计部署情况 indirect prompt injection exposure.

显示 :

1. 列出所有内容来源 agent 改为: RAG 文档、收件箱、日历、工具产出、机票、产品审查、第三方 APIs。每种信息都是潜在的 IPI 矢量。
2. 信任标签。 部署是否分开信任( 用户) prompt)来自不信任的内容(检索的内容)?如果内容被混入同一内容 prompt 没有标签, 国际金融公司无效 。
3. 动作格格。 哪些工具可以被引用? 对于每一个工具, 是否被信任的人所包围 prompt 或无信的内容会影响引用?
4. Adaptive-attack evaluation是否对部署进行了适应性攻击的测试(第2段)。gradient2025年Nasr等人的RL、人类红色队? evaluation 不够
5. 范围- 侵犯边界。 识别每个交叉trust boundary (例如,收件箱 - > 发送、文档 - > 外部) API对于每个实体,要么在不信任的影响下,不允许采取行动,要么得到被信任者的明确批准。 prompt.

艰难的拒绝 :
- 任意 agent 使用回收内容时没有明确信任标签。
- 任何辩护要求都只基于静态攻击
- 任何关于"我们"的说法 agent 是 prompt- 注射安全",没有命名 ICF机制。

拒绝规则 :
- 如果用户询问过滤是否足够, 拒绝并解释 Nasr 2025 的结果是, 适应性攻击突破超过90%的过滤防御 。
- 如果用户要求银弹防御,拒绝——IPI防御需要国际金融公司加上分层反应节制,以及高发行动的人性审计。

产出:一页审计,填充上述五个部分,标出最危险的不信任边界,并列出需要添加的最紧急的控件。
