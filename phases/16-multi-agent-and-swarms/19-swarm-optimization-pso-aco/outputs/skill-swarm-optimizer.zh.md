---
name: swarm-optimizer
description: Choose between PSO, ACO, genetic algorithms, and gradient-based optimizers for a given LLM or agent optimization problem. Bio-inspired swarm algorithms are gradient-free and suit LLM-era workloads where the search space is discrete or the fitness function is black-box.
version: 1.0.0
phase: 16
lesson: 19
tags: [multi-agent, swarm-optimization, PSO, ACO, prompt-optimization, routing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 LLM 或 agent 优化问题, 选择右侧 optimizer.

显示 :

1. **问题指纹** 搜索空间( 连续数字, ) prompt 字符串, 型号 weights,路径图),健康信号(自动测试, LLM 法官、人薪、商业KPI)、时间与价值(分钟、小时、天)。
2. **Optimizer choice.** 公共支助处,ACO,基因算法 DPO/RL,手动调试。每个都有一个默认使用大小写 :
   - 连接空间的连续数字  PSO
   - 路径或路径选择  ACO
   - 独立的符号/程序 遗传算法
   - 不同报酬 DPO/RL
   - 低维、快速反弹 网格/随机搜索
3. **人口规模缩小。** 10-30 用于 PSO/GA, 用于 ACO 的pheomone矩阵大小。 预算计算: N × T x 成本- 成本- 年。 不要运行 swarms 成本超过他们生产的价值
4. **适配+优质门。** 哪个功能能让候选人得分?
5. **协调监测。** 日志 g_最佳或异频稳定。 注意差异( 灾难性漂移) 和过早的趋同( 当地最佳 ) 。
6. **衰变/勘探调试。** 公关系统惯性及认知/社会 weights; 丙酮衰减率和存款额。权衡:低衰减率  粘在早期赢家身上;高衰变率  没有记忆。
7. **重置条件** 什么时候的反省 distribution shifts 或部署模式变化,重置 g_暂时的最好或零的费洛蒙 腐烂的记忆比没有记忆还糟糕

艰难的拒绝 :

- Swarm optimizers 需要人来检查的活儿 每块土地的成本都比预算高
- 人口规模大于50,没有明确的预算理由,回报减少占主导地位。
- 费洛蒙没有优质门的路线,快速但错误 agents 锁定
- 用于没有自然连续的离散搜索空间的 PSO embedding。使用 GA 或模拟安眠药代替。

拒绝规则 :

- 如果用户试图优化一些没有明确健身功能的东西, 建议首先定义健身。 Swarm optimizers 没有评价员是无济于事的。
- 如果用户预算低于100美元,建议人工调整+缓冲 swarms.
- 如果 distribution shifts 每天,推荐在线学习或强盗,而不是 swarm optimizers.

输出: 一页的简要。 以一句话建议开始 (“ 使用 ACO , 将高品质的光素存储在 3 - 3 上 ”agent × 4-任务型路由问题。 衰变0.05, 阈值 0.6, 200 warmup 之后是上面的七个部分,最后是预算概算和一周 rollout plan.
