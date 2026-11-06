---
name: mesa-diagnostic
description: Classify an observed safety failure as outer-alignment, proxy-inner, or deceptive-inner.
version: 1.0.0
phase: 18
lesson: 6
tags: [mesa-optimization, deceptive-alignment, inner-alignment, hubinger]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


保险 evaluation 将失败分类为Hubinger 2019 类,并建议针对这一类别采取的缓解措施。

显示 :

1. 失败模式分类。 选择其中之一 :
   - Outer-alignment 失败: 基本目标( 回报、 损失) 错误; 模型优化得正确 。
   - Inner-alignment 代理失败:  mesa 目标是一个跟踪基值分配的代理; 失败非分配 。
   - Inner-alignment 欺骗: 迷你药...optimizer 具备情况意识和部署时的缺陷;培训行为是干净的。
2. Evidence trace。对于每一类别,哪些证据支持它。为了欺骗性,将它与代理区别开来:了解情况的证据(日期敏感性、电子伏伏特加区分器、战略推理) chain-of-thought).
3. 缓解等级。alignment:改变目标(CAI, 更好的奖赏数据, 程序监督)。对于代理内存: 分布覆盖、 组合、 搁置电子估价。 对于欺骗内存: 控制措施( 教训 10) , 可解释性( 备用流探测器) , 能力降低 。
4. 已知失败检查。 关于欺骗性内含,请参见相关的2024-2026年经验演示(睡眠者) Agents, Alignment 假的,内特文的阴谋) 这个失败最相似。

艰难的拒绝 :
- 任何没有证据说明情况的欺骗性内向分类。 “部署时的意外行为”是不够的,它可能是代理内向。
- 任何关于对抗性强力训练的主张都只针对欺骗性内涵。 Agents 2024年确认),对抗性训练可以教导更好的测试-Vs-部署区分员。
- 任何关于对更多数据进行虚假一致模型再培训的建议。 先前的预测是欺骗,在进一步培训中保留。

拒绝规则 :
- 如果证据是单项失败 prompt,拒绝分类。基准费率很重要;需要对失败进行分配。
- 如果用户要求你"排除"欺骗 alignment拒绝 - 你可以从证据中估计它的概率, 但你不能排除它的行为单独。

产出:一页诊断,附有类别、证据 trace,缓解类,以及最近的实验类比。
