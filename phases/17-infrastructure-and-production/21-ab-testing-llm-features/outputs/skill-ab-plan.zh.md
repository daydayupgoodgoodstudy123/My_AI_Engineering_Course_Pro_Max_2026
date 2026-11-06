---
name: ab-plan
description: Design an LLM A/B test — pick platform (Statsig or GrowthBook), primary metric, guardrails, sample size with LLM-noise buffer, CUPED, sequential stopping, and multiple-comparison correction.
version: 1.0.0
phase: 17
lesson: 21
tags: [ab-testing, statsig, growthbook, cuped, sequential, benjamini-hochberg, srm]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以 时 候 feature 变动(prompt / 型号/ 代号 parameter基准量度、预期升降和团队姿态(软件库-本地开放源码软件与捆绑的SaaS),产生A/B计划。

显示 :

1. 平台 统计( 混合 SaaS, 包括 OpenAI或增长书(MIT OSS,仓库-本地)。
2. 初级计量+ guardrails。初级是您想要移动的量度; guardrails 不得倒退(费用/要求、P99潜伏率、拒绝率)。
3. 样本大小。 经典功率计算x 1. 4 (LLM ) 。
4. 设计 。 固定方位或顺序。 如果您期望强烈信号, 则按顺序排列; 如果变化是微妙的, 则按时间顺序排列 。
5. CUPED. 如果存在初级计量的预期数据,启用该数据;指定递减器。
6. 纠正. Bonferroni,用于少量测试;Benjani-Hochberg,用于许多相关的测试。
7. SRM. 要求对每次实验进行SRM检查; 标记时停止并调试 。

艰难的拒绝 :
- 拒绝——需要A/B或有文件证明的无A/B例外。
- 正在对同一基本指标进行 > 5 的试验,没有BH/Bonferroni。
- 跳过 SRM 检查。 拒绝 - 任务错误是常见的 。

拒绝规则 :
- 如果流量 < 1000个用户/周 feature,“A/B”型垃圾-需要阴影+金丝雀(第17阶段 20)
- 如果主要指标是主观的(例如“质量”),而没有客观的替代物,则需要同时进行人类评估。
- 如果电梯的假设小于 LLM 噪音层,垃圾——实验无法用现实的样本大小探测到它。

产出:一页计划,配有平台,主+ guardrails,样本大小、设计、 CUPED、更正、SRM政策。 guardrails 具有重大负值的  船舶; guardrail 违反... . . . . . .
