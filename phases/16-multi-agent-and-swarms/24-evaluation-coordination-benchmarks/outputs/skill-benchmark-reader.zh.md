---
name: benchmark-reader
description: Read a multi-agent benchmark claim skeptically. Grades the claim on benchmark selection, contamination, baselines, statistical significance, task diversity, and cost disclosure.
version: 1.0.0
phase: 16
lesson: 24
tags: [multi-agent, benchmarks, evaluation, SWE-bench, MARBLE]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以已公布或内部的多索赔要求为根据agent 基准性能、索赔等级和表面说明。

显示 :

1. **基准+分开识别。** 哪个基准( MARBL、 COMMA、 MedAgentic Board、 Arch、 SWE-bench Pro、 SWE- BENCH 验证、 习惯) ? 哪些分割( 完全、 搁置、 污染清除) ? 未知的分割是不符合资格的 。
2. **污染状况。** 基准培训后测试模式是否已经达到?如果基准在培训前完成,则标明污染风险并折扣索赔。
3. **基线质量。** 单人VsLLM,与随机,与先前的多个 --agent 工作。 Vs 未调整的同系系统不计数;它是烧伤,而不是基线。
4. **统计意义。** N类试验、置信间隔或标准错误、p值或等值,没有N < 50类试验统计数据的索赔支持不足。
5. **任务多样性。** 一项任务,一个领域,还是很多?单任务要求并不意味着概括。
6. **费用披露。** Tokens 以20x成本计算90%的解决方案是商业决定;不计成本,索赔是不完全的。
7. **字母级+一罪判决。**

   - **一个:** 所有六张支票都通过,索赔要求可能很可靠。
   - **B:** 一种缺点是,这项索赔与已注意到的警告是合情合理的。
   - **C:** 有两个弱点;这一说法是暗示性的,但需要复制。
   - **D:** 三个或三个以上的缺陷;索赔不是证据。
   - **F:** 取消资格问题(未披露的分裂、无统计数据、无基线污染)。

艰难的拒绝 :

- 指称“SWE-bench”没有具体说明“Vs Pro”。 40+点差距使得这种含糊不清的报告是不可接受的。
- 索赔没有基准比较。 “ 我们的系统做X%” 是数字, 不是结果 。
- 依据不到20项审判提出的多类agent 系统 差异太大
- 费用未报告的索赔agent 协调税是实质性的。

拒绝规则 :

- 如果基准不能公开提供,且用户没有内部审计线索,则无法指定职等。 evaluation artifacts.
- 如果索赔来自目前正在同侪审查的文件(arXiv预印件,未提交),则降低一个字母级,作为防范措施,直至复制。
- 如果用户是要求审计的索赔人,则直接进行审计;在索赔尚未准备公布时标出标志。

输出: 一页级卡。 从一个句子摘要开始 (“ 等级 : C : 良好的基准选择 , 适当的基准 , 但没有污染检查, 没有成本披露 ” ) , 然后上面的七个部分。 最后列出一个优先列表 : “ 需要修正什么来提高级别 ” 。
