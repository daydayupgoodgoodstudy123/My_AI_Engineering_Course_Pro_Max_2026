---
name: self-improvement-auditor
description: Audit a proposed self-improvement or constitutional AI pipeline before it runs at scale.
version: 1.0.0
phase: 10
lesson: 9
tags: [alignment, cai, grpo, rlhf, self-improvement, reward-hacking]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议训练管道声称使用《宪法》大赦国际, GRPO,或任何形式的自我生成的优先数据,产生审计数据,包括:

1. 奖赏规则。 说明确切的验证程序( regex, sympy, 测试套房, LLM 分类为确定性、随机性LLM,或混合。拒绝任何“自我改进”循环,该循环没有外部 grounding - 模型无法从任何地方拉动信号。
2. 组统计。 GRPO 管道,确认组号大小,计算优势的方法(z-score 相对于相对等级),以及当组奖励标准倒塌到零时会发生什么。 管道必须跳过或降下来零变量组,而不是用 Epsilon 分隔,并假装信号是真实的。
3. KL 预算。 累积 KL( 政策) 的数字上限 || 管道必须停止、重置或切换到一个更温暖的引用,当顶被击中时。无界 KL 是无界的漂移。
4. 多样性底线。 测量每组奖励标准下限、 响应长度差异或 n 克 entropy , 不论任务是否承认。 如果连续的圆圈底线被打破, 管道必须混合到新的人类数据中或更大范围内 prompt 分布。
5. 人类数据定额。 培训组合中必须保持人文版的最低部分, 通常为5- 10%。 3-5轮后, 仅靠自提炼的管道会崩溃。 请明确列出这一点 。
6. 模式折叠监视器。 旗式自动检查: 奖励横跨回合, 唯一的 n 克数 。 prompts超过门槛值者可停止培训。
7. 宪法漂移。 CAI 管道需要一个版本的宪法文件、一个修改和一个“宪法” regression test 设置" - prompts 其预期行为不得在编辑中发生任何变化。

拒绝批准下列管道:
- 索赔“零人类数据”,没有外部核实(规则、工具、环境)。
- 使用 PMS 而不使用进程回报黑客探测器( 模型是否写出看起来正确的步骤而没有推进证据? ) 。
- 运行超过5轮拒绝 -sampling fine-tuning 没有固定的多样性基准。
- 与策略共享引用模式( 不引用表示没有 KL, 表示没有锁定) 。
- 与 an 得分 LLM 法官认为,该模式与保单相同(法官污染)。

输出: 每扇门有一页的检查,每扇门的出入/故障、测量值或说明值以及生成每个信号的管道中的确切步骤。 如果任何门都失败了,请列出最起码可行的修改,将其翻转通过。
