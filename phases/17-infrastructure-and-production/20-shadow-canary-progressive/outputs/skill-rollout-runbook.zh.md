---
name: rollout-runbook
description: Design a shadow → canary → A/B → 100% rollout plan for a new LLM model or prompt template, with five canary gates, noise-floor-aware thresholds, and a seconds-fast rollback path.
version: 1.0.0
phase: 17
lesson: 20
tags: [rollout, canary, shadow, progressive-delivery, feature-flags, argo-rollouts, flagger, kserve]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


候选人变化(新模式,新模式) prompt 模板、新的路由器政策、基准生产量度和风险承受力 rollout runbook.

显示 :

1. 阴影计划 持续时间(24-72小时) 记录的数据:输出, token 计数, 隐蔽, 拒绝, 错误。 提醒 : > 20% 的成本转换, > 30% 输出长度的转换, 任何违反计划 。
2. 气管进化。阶段(1% 10% 25% 50% 75% 100% ) 。每个阶段(30米-24小时,以流量为基础;确保每个阶段有足够的数据可以进行统计。
3. 五个关口。 指定潜伏点P99、 成本/ 要求、 错误/ 拒绝、 输出长度P99、 缩略图下调率的准确阈值。 设置在噪音层之上( 预期15% 的不折不扣的偏差) 。
4. 工具。 名称 rollout 控制器( Argo) Rollouts和《公约》第四条第8款的执行情况 feature 即时的标记系统 rollback.
5. Rollback 路径。文档中显示三个动作:翻转旗  折叠摘要  校验。目标时间:60秒以内结束。
6. 跳过 A/ B? 理由。 改进的变差跳过 A/ B; 明显不同的变化( 新行为, 新成本曲线) 需要 A/ B 。

艰难的拒绝 :
- 跳过阴影模式。 拒绝 - 成本攀升和长度回归会滑过离线的 Eval 。
- 门的距离比15%差强。拒绝——假警报会停止合法 rollouts.
- Rollback 拒绝——这不是 rollback是个损坏报告

拒绝规则 :
- 如果更改是安全关键(例如PII处理变化),则需要明确的额外门:在开始使用金丝雀之前,在影子样本中进行零 PII渗漏。
- 如果流量小于100瑞克/小时,则需要延长罐头级,否则门声会超过信号。
- 如果小组无法提供五个金丝雀门的基准量度,则拒绝 rollout 基线是先决条件。

输出:一页长的运行手册,有阴影、金丝雀、门、工具 rollback,A/B 姿态。 rollback 钻头要求:排练 rollback 第一次真正部署之前
