---
name: mast-auditor
description: Run a MAST-style failure-mode audit on a multi-agent system. Categorize execution-trace failures into Specification / Coordination / Verification and the Groupthink families; rank mitigations by expected failure reduction.
version: 1.0.0
phase: 16
lesson: 23
tags: [multi-agent, failure-modes, MAST, groupthink, circuit-breaker, audit]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


假设一个多...agent 系统及抽样执行 traces,运行失败模式的审计。

显示 :

1. **样本构建。** 至少200个 traces 由制作的,在任务类型和时间窗口之间统一取样。 sampling 方法和偏见风险。
2. **分类通行证。** 每种 trace标记 `success | failure`。如果失败,指定一个MAST类别(标注/coord/核查),并酌情指定一个或多个群体思维家庭标记(单体养殖/符合/Tom/混合运动/级联)。
3. **分发表。** 与 Cemri 2025 的参考分布( 41.77 / 36.94 / 21.30) 相比, MAST 分类和组思维标记的计算和百分比。 从引用中严重扭曲的系统通常有一个特定的薄弱层。
4. **最大的失败模式。** 确定三种最常见的具体模式(例如,“二” agents )文件复制步骤。
5. **缓解等级。** 在每个顶级模式中,从标准图书馆中提出一个缓解办法:明确角色合同、共同版本的状态、独立核查员、 circuit breaker检测诊断-验证三重体,根据模式频率,按预期的故障减少顺序排列。
6. **沉默失败的风险。** 有多少失败产生似是而非的输出与巨大错误? 沉默率驱动了核查层的投资。
7. **缓慢失败的代理人。** 建议2-3 个在大错发生之前表面漂流的活度量: 约定速率、 重试速率、 输出长度分布、 间隔时间agent 编辑距离 。

艰难的拒绝 :

- 审计没有随机或分层抽样。 手工选择的失败过多地呈现出戏剧性案例, 错过了缓慢失败的漂移 。
- “添加核查者”是指除非知道目前的故障率。
- 忽略了 MST 未知事件。 如果 trace 不属于某一类别,分类不完整;提议延长而不是强制实行某一类别。
- 要求每季度审计就足够了,无需进行业务缓慢监测。

拒绝规则 :

- 如果 traces 缺少每 -agent 审计不能区分协调失误与角色冲突。agent 重新审核前先记录
- 如果系统失败不足50次 traces 样本总数太小,无法得出分布估计。 建议使用更长的观察窗口 。
- 如果 traces 含有 PII, 分析前掩码。

输出: 一份三页的报告。 以一则判决摘要开始( “ 41% 的标注失败, 12%的协调, 39%的验证差距, 8%的未知值; 顶级模式是双重评审冲突; 最高ROI 的缓解是明确的角色合同 ” ) ) , 然后是上面七个部分。 最后是优先行动列表 : 三次减缓, 包括执行成本和预期的失败率削减 。
