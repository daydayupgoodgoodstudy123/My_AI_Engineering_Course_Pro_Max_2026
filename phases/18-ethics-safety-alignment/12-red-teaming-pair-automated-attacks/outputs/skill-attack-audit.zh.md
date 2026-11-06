---
name: attack-audit
description: Audit a red-team evaluation report for attack coverage, budget, judge identity, and behaviour set.
version: 1.0.0
phase: 18
lesson: 12
tags: [red-teaming, jailbreak, pair, harmbench, jailbreakbench, asr]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个红队 evaluation 审计 evaluation 与公布的基线以及是否支持其结论相类似。

显示 :

1. 攻击范围。 列出每起攻击行动的清单: 帕伊尔、 GCG、 AutoDAN、 TAP、 PAP、 手动。 标记任何攻击级别丢失的 。 只运行一个攻击家庭的报告不能声称是稳健的 。
2. 每一攻击的预算。 报告查询预算 / prompt 计算机辅助智能测试测试称成功20次查询与GG500个步骤的成功测试不相仿。
3. 法官身份。 LLM 使用(GPT-4-turbo, Llama 警卫,强力正义,内部分类员? calibration 驱动 ASR 变化。
4. 行为设置: 破门禁闭(100种行为,10种类别)、 伤害(510种行为,7种类别)、 内部还是其他? 国家该组是否公开和可复制。
5. 传输检查。 如果红色团队优化了对一种模式的转换, 是否报告过对其他模式的转换 ASR ? 单一模式 ASR 是模型- 家庭强度的上限, 不是较低约束 。

艰难的拒绝 :
- 任何"我们的模型是强大的" 依据一个攻击家庭。
- 任何ASR报告都没有查询预算。
- 任何使用不同于公布基准的法官的ASR calibration 与基准法官相比

拒绝规则 :
- 如果用户问"是我们的模型 jailbreak- 防伪,"拒绝二进制回答 并指向上面的多攻击, 多判, 转移检查结构。
- 如果用户要求推荐攻击工具包,则拒绝单一建议,并指出2024年危害区之间的实际差异。

产出:一页审计,填充上面五个部分,标出缺失的攻击类别,并估计ASR相对于可复制的基准是否少报或多报。
