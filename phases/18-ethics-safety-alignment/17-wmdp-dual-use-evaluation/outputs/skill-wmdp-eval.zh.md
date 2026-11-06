---
name: wmdp-eval
description: Audit a dual-use capability claim against WMDP, unlearning evaluation, and elicitation studies.
version: 1.0.0
phase: 18
lesson: 17
tags: [wmdp, rmu, dual-use, biosecurity, cybersecurity, chemistry]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以双重用途能力(“我们的模型对生物武器/网络攻击/化学没有有意义的帮助”)为例, evaluation.

显示 :

1. 基准覆盖范围:大规模大规模毁灭性武器方案(或等效的黄区基准)是否运行?报告每个域的分数(生物、网络、化学)。
2. Unlearning trace如果采用不学习方式(RMU或替代方法),报告通用能力三角形(MMLU、HELM、HumanEval)。
3. 拒绝式反向审计。 基准是通过原始完成还是通过生产安全堆放来操作的? 仅仅因为安全堆放而得分较低的模型在堆放被绕过时仍然具有双重用途。
4. Elicitation 复选能力不等于 elicitation- 硬化能力。 Anthropic· 典型的收购试验,或相当的“新手”研究,被引用?
5. 新手- vs- 专家拆分。 新手- 相对提升和专家- 绝对能力是不同的。 两者都处理了吗 ?

艰难的拒绝 :
- 任何没有进行大规模毁灭性武器方案等效能力测量的双重用途安全要求。
- 任何没有通用能力三角洲的未学习索赔。
- 任何"没有有意义的提升"索赔 没有新人在环行研究。

拒绝规则 :
- 如果用户询问其模型是否跨越 ASL-3, 拒绝直接回答; 阈值是特定实验室的( 列斯森 18) 和 elicitation-dependent.
- 如果用户要求使用“安全”的大规模毁灭性武器方案截断, elicitation 抵抗,隐性知识障碍, 和部署表面。

产出:一页审计,填充上述五个部分,标出缺失的最重要证据,并确定索赔是大规模毁灭性武器计划一级还是部署一级。
