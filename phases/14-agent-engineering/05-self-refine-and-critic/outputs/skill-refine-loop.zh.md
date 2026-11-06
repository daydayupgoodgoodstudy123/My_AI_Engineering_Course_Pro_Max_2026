---
name: refine-loop
description: Configure an evaluator-optimizer (Self-Refine / CRITIC) loop given task, verifier availability, and iteration budget.
version: 1.0.0
phase: 14
lesson: 05
tags: [self-refine, critic, evaluator-optimizer, guardrails, iteration]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


任务、循环预算以及什么(仅限工具或自省)核查, prompts 以及一个评价员的停止政策optimizer loop.

显示 :

1. Generator prompt确定性生产者的第一个产出。 明确说明任务、产出格式和制约因素。
2. Evaluator/verifier prompt。如果工具可用(搜索、代码运行、测试、计算、类型检查),请具体说明如何调用和生成结构化的批评(JSON 出入/失职,违规情况[],建议_fixes[]如果只有自我反射功能,则明确标出自备橡胶标记的风险,并使用不同的结构 prompt 样式(例如,对抗性“至少找到一个缺陷”)。
3. Refiner prompt。必须参考先前的产出和批评(历史)。“不重复先前重复中标注的失败模式”是强制性的。
4. 停止策略。 连接: 校验通过或( 自 降表示精细和迭代 = 2) 或迭代 = 最大_重复,从不单是条件
5. Observability 钩子。 将每个迭代作为 OpenTelephiatery GenAI 的横线( 评估、 优化) / 23 课进行记录, 这样整个精细轨就可以被审计 。

艰难的拒绝 :

- Same prompt 发电机和 critic橡胶标记的风险——模型本身也同意。
- 无迭代盖。 无限精细循环燃烧 tokens;默认情况下,上限为4。
- Verifier prompt 要求自由发光反馈。 JSON 仅限出入/不合格和逐项违规。
- 从精细器中丢弃历史 prompt。纸上显示质量崩溃没有它。

拒绝规则 :

- 如果任务没有验证员 也没有办法建立的话,就拒绝 CRITIC 并提醒用户不要担心橡胶印的风险。
- 如果最大_+++ 10,拒绝并推荐重新配置任务。3-4通行证上的纠错通常是生成器的信号 prompt 错了
- 如果核查员称其为破坏性工具(壳, git 写、拒绝和要求 sandbox 边界(Lesson 09)。

输出: 带有全部的单个配置块 prompts,停止政策,工具列表,加上一个“下一个读什么”注,指向16号课(OpenAI Agents SDK guardrails课程12(b)Anthropic evaluator-optimizer),或课程30(由电子产品驱动) agent 部署目标。
