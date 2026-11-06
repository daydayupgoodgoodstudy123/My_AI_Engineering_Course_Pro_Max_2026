---
name: ai-sre-plan
description: Design an AI SRE rollout for a team — multi-agent triage architecture, structured runbooks, adversarial evaluation, narrow auto-remediation, and predictive-detection posture.
version: 1.0.0
phase: 17
lesson: 23
tags: [ai-sre, multi-agent, runbooks, auto-remediation, adversarial-eval, datadog-bits-ai, neubird, predictive]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以团队规模和事件数量来看 observability 成熟度和风险承受力 产生AI SRE计划

显示 :

1. 建筑,多层agent: 主管+日志 agent + 计量 agent +运行手册 agent +人门。匹配专用 agents 至现有数据来源(数据数据、格拉法纳、洛基、Coffect)。
2. 运行簿转换。 从无结构的集成移到结构化 markdown / 假设/ 校验/ 动作部分。 git.
3. 产品选择。 数据犬比特 AI, Azure SRE Agent内鸟鹰眼,事件。 iO自动驾驶,或DIY。
4. 自动补救范围。 窄安全套( 重新启动缓存、 恢复部署、 缩放在范围内) 。 明确拒绝列表( 地形、 代码、 IAM 、 数据库) 。 政策是代码 。
5. Adversarial evaluation指定自动补救的两种协议大门。
6. 预测性检测姿态。 如果考虑( 麻省理工学院89%的结果), 请命名激活政策 — 呼叫器、 排气前、 自动标尺 — 否则它只是一个仪表板 。

艰难的拒绝 :
- 自动补救,但大变化时没有人门。拒绝——明确标明保险箱的名称。
- 以无结构的运行簿作为知识库。 markdown.
- 拒绝 明确定义什么是自主的

拒绝规则 :
- 如果事件量 < 10 个月, 拒绝完整 AI SRE rollout 成本超过效益,只建议结构化运行手册。
- 如果团队 observability 是不成熟(logs 无法查找, 测量标准稀少), 拒绝—— AI SRE 放大坏数据。
- 如果小组建议先进行“预知性检测” 自动补救 feature拒绝 - 先通过启动政策的问题

产出:一页计划,包括建筑、运行手册计划、产品选择、自动补救范围、对立门、预测姿态。 rollout 时间表: 1-4周结构操作手册,5-8个分类 agent9 -12 狭义的自动补救
