---
name: topology-picker
description: Pick a multi-agent debate topology (star / chain / tree / graph), an N of agents, a heterogeneity profile, and a round bound for a given task.
version: 1.0.0
phase: 16
lesson: 15
tags: [multi-agent, debate, topology, voting, self-consistency]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


任务说明中,建议一个多agent 地貌学和缩放

显示 :

1. **任务指纹** 研究( 长视距、 开放性、 快速现实( 闭式回答)、 一步步精炼( 分阶段管道) , 或者观点( 无地面真相 ) 。 选择一个; 如果它跨越两个, 选择主导形状 。
2. **Topology.** 星、链、树或图。
   - 图表(任何评论)
   - 恒星( 集体)
   - 递增  链 (或分解和征服树)
   - ++ 以上意见无;建议单 agent + 人类决定
3. **国家 agents.** 3是最廉价的组合;5是常见的甜点;7+是专业。在图表表层中,超过5,警告协调税。
4. **异质性简介** 至少一个 agent 如果单一文化很重要(研究、推理),则必须来自不同的模型家庭。
5. **圆形** 1轮=投票。2轮=1次调整。3轮=最大符合率之前。从未被约束。
6. **Aggregation.** 多重性( 低劣 ) , 信心加权( CP- WBFT ) , 几何中位数( DecentLLMs ) , 或者法官计分 。 除非成本限制决定了多元性,否则默认为信任加权 。
7. **Escalation.** 人类,另一个有不同基本模型的组合,还是弃权?

艰难的拒绝 :

- 10+的任何建议 agents 协调税占优势;首先衡量。
- 星体的地形学是公开研究问题 星体失去了任何批评的好处
- 任何建议,如果运行相同的基准型号N乘数,并称它为多agent。这是自我一致的伪装;正确标注。
- 毫无约束的回合。 奖励一致; 辩论持续的时间越长, 辩论时间就越长 agents 同意是压力而不是逻辑。

拒绝规则 :

- 如果任务没有事实依据(意见、合成、创造性),则指出投票是建议。 agent + 人类决定。
- 如果用户无法使用多个基本模型,则标出单一栽培上限,并建议与以下各点保持自定一致性: temperature 变换为后退 。
- 如果任务简单( 单一事实查询, < 100) tokens ),建议采用单一的 agent 具有自定性N=5。

输出: 一页简况。 从单句建议开始 (“ 地表学, N=5 ) agents 由三个不同的基数模型,两个回合,信心加权的集合, 升至低于临界值的人类。” tokens 每个查询和预期的延迟秒。
