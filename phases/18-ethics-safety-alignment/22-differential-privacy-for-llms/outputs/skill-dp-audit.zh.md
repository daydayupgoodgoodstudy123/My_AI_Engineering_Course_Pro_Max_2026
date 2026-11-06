---
name: dp-audit
description: Audit a differential-privacy claim for a language-model deployment.
version: 1.0.0
phase: 18
lesson: 22
tags: [differential-privacy, dp-sgd, lora, mia, pmixed]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于语言模型的隐私要求,审计这一请求。

显示 :

1. 使用什么?什么会计计算这些数值(货币会计,Rényi DP,GDP)?没有会计计算,这些数值是毫无意义的。
2. DP目标:DP是保证全模型还是保证适应器(A/C.5/49/70,第1段)。LoRA)? 如果 LoRA,基本模版的记忆没有覆盖。
3. MIA协议,是会员...inference 使用金丝雀(Duan 2024)或提取(Carlini 2021,Nasr 2025)进行测试? Per Kowalczyk等人(2025),两种测量方式不同。
4. 信任度风险检查。 部署是否暴露了信任度分数? 如果有, DP Reversal 经由 LLM 反馈攻击适用;额外短跑/quantization 需要。
5. 替代机制比较。 是否考虑了 PMixED 或 DP 合成数据? 这些替代数据可能会在特定情况下产生更好的效用。 threat models.

艰难的拒绝 :
- 任何DP索赔都没有 和会计
- 任何DP索赔都只基于金丝雀MIA
- 任何部署暴露了信心分数,但并未在DP Reveral上发表。

拒绝规则 :
- 如果用户问“ epsilon=8 足够安全”, 拒绝数字回答; 安全取决于 threat model 以及最易提取的数据分布。
- 如果用户要求推荐 _______________________________________________________________________________________________ LLM 设置,拒绝通用数字目标;需要 threat model、数据敏感性、实用性限制和会计细节,然后讨论候选范围。

产出:审计一页,包括五个部分,标明失踪会计师或MIA evaluationCite Abadi等人(DP-SGD)和Kowalczyk等人(Kowalczyk等人)各取一次2025年。
