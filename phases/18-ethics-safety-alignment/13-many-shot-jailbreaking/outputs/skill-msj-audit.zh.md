---
name: msj-audit
description: Audit a long-context safety evaluation for many-shot jailbreaking coverage.
version: 1.0.0
phase: 18
lesson: 13
tags: [many-shot-jailbreaking, context-window, power-law, anthropic]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


保险 evaluation 进行长期分析, evaluation 包括许多被枪杀的犯人

显示 :

1. 射击量的覆盖范围:报告测试的射击数(应包括1、5、16、64、256, 以及至少1+++++1M上方的模型)。如果是的话。 evaluation 测试单枪匹马,ASR是无信息性的——MSJ是一个曲线。
2. 电源法适合。 报告每个行为类别的配对指数。 一个浅度指数表示该类模式是ICL-robust; 一个陡峭指数表示MSJ效果过大。
3. 科学、司法和司法部的效能因类别而异:暴力内容、欺骗、自残、生物武器。 jailbreak。 evaluation.
4. 辨识身份。 是基于分类 prompt 是否对分类者本身进行了对抗性强度评估? Anthropic报告的61% - > 2% 的削减取决于分类 calibration.
5. 组合检查。 evaluation 测试 MSJ + PAIR, MSJ + 有说服力的模板, 或者 MSJ + 编码 ? 组合攻击通常比任何单项技术都强 。

艰难的拒绝 :
- 任何“我们长文本模型是安全的”索赔,根据是仅5发 evaluation.
- 任何辩护要求,没有报告 jailbreak 在同一分类中,ASR和良性ICL业绩——权衡是关键。
- 任何类别汇总的ASR,无分类细目。

拒绝规则 :
- 如果用户询问MSJ能否完全补丁, 拒绝二进制回答; MSJ 与 ICL 共享一个机制, 如果不消除 ICL 就无法取消 。
- 如果用户要求推荐射击数 evaluation,拒绝一个数字;要求电源法适合5至512发子弹。

产出:一页审计,报告射杀率、每一类别适合的权力法、国防识别和一个构件攻击漏洞。Anthropic)作为方法上的参考。
