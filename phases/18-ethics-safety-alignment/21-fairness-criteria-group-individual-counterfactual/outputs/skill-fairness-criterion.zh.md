---
name: fairness-criterion
description: Identify which fairness criterion a claim invokes and audit the associated assumptions.
version: 1.0.0
phase: 18
lesson: 21
tags: [fairness, demographic-parity, equalized-odds, counterfactual-fairness, impossibility]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于公平主张或政策,确定援引的标准、索赔取决于哪些假设以及不可能的理论对其余标准意味着什么。

显示 :

1. 标准识别。 标注要求针对的是一个:人口均等、均等率、有条件使用准确性平等、个人公平、反事实公正。 模糊不清的要求必须在诉讼前解决。
2. 基准率审计。部署中每个组的基准率是多少? 在不平等的基准率下,Chouldechova/KMR 2017不可能适用:没有模型满足所有三个组的标准。
3. 因果关系。 如果索赔要求是反事实的公平,那么因果关系是什么呢? 反事实公正只有与赔偿要求一样合理。 没有赔偿要求就是无效的。
4. 相似度衡量标准:如果索赔是个人公平,那么,什么是相似度衡量标准? 选择是具体任务,是一项政策决定,而不是统计决定。
5. 干预的合法性. 如果索赔使用了反事实推理,是否涉及对受保护属性的干预?如果是,则考虑反事实的反跟踪(arXiv:2401.13935)回避法律问题。

艰难的拒绝 :
- 任何“公平”索赔,没有标准识别。
- 任何“公平标准都得到满足”的主张,
- 任何没有公布因果性地宣称的反事实公平。

拒绝规则 :
- 如果用户问公平标准是“正确标准”,
- 如果用户问模型是否公平, 拒绝二进制要求; 公平是标准相对的。

产出:一页审计,涵盖以上五个部分,说明不可能执行之处,并列出索赔中隐含的政策选择。
