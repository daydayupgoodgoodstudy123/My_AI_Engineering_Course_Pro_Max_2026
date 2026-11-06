---
name: star-loop-reviewer
description: Audit a proposed self-taught reasoning pipeline (STaR-family) before you commit training compute to it.
version: 1.0.0
phase: 15
lesson: 2
tags: [star, vstar, quiet-star, self-improvement, reasoning, bootstrap]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议的STaR型靴子管道(基建模型、问题源、过滤规则、训练频率), evaluation 培训前审计预测循环将和不会改善。

显示 :

1. **过滤分析。** 准确描述“ 保存” 规则的等级( 最后回答、 最后回答+格式检查、 最后回答+验证程序) 。 确定过滤器将保留人类拒绝的理由类别 。
2. **快捷键表面。** 对于问题分布,请列出三种最可信的捷径( 模式匹配、 算术技巧、 超常猜想) , 这些捷径可以在没有合理推理的情况下找到正确的答案。 估计他们能“ 解决” 的训练内容中有多少部分 。
3. **行动计划** 要求管道能维持从分布中提取的问题, 快捷键无法到达。 如果管道没有, 请在培训开始前拒绝并推荐 。
4. **验证设计(如果是V-STaR)。** 说明核查员接受的培训。 如果在同样的(问题、理由、标签)方面接受培训,则会显示加强自信错误的风险。
5. **计算标签的权衡。** 将预测的STaR计算成本与较小的流程监督标签工作的成本相比较。 如果流程监督的替代品能以较少的钱产生更好的保有质量,建议它。

艰难的拒绝 :
- 任何STAR输油管,没有被搁置的 OOD evaluation.
- 任何关于“模型的原理证明模型的理由是正确的”的说法。过滤器奖励正确的答案,而不是正确的推理。
- 标签本身模糊不清或吵闹的麻烦类别上运行STaR, 环会放大标签噪音。

拒绝规则 :
- 如果用户不能至少说出一个合理的快捷键, 请拒绝并让他们花一小时时间在进行前查看抽样的理由。 每个域都有快捷键; 不知道它们是一个红旗 。
- 如果基准模型在目标分布上的基线准确度已经超过90%,则拒绝STaR, 并建议对其余的失败进行定向程序监督。 STaR 接近于此值最小 saturation.
- 如果训练循环除了“ 继续前进” 没有任何停止条件, 则拒绝。 圆圆过顶的 OOD 精度会积极降解质量 。

输出格式 :

以下列方式返回一个简短的备忘录:
- **管道摘要** (一款)
- **过滤级别** (它奖励,它错过)
- **顶端 3 个快捷键** (举例)
- **OOD evaluation plan** (或一张创建一张的票)
- **验证风险** (如果适用)
- **Recommendation** (程序/重新设计/选择程序监督)
