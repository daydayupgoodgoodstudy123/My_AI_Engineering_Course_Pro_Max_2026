---
name: card-audit
description: Audit a model card, datasheet, or system card for completeness and verifiability.
version: 1.0.0
phase: 18
lesson: 26
tags: [model-card, datasheet, system-card, transparency, mitchell-2019]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 model card,数据表或系统卡、完整性审计、数字分类和可核查性。

显示 :

1. 部分覆盖。 检查每个金刚石部分都填满了。 旗子缺失的: 道德考量是最常用的模型卡字段( Oreamuno 等人, 2023 )。
2. 量化分类。 evaluation 指标,报告是否按人口因素或任务因素分列。
3. Datasheet alignment。如果卡片引用训练数据,是否有一个配套数据表(Gebru等人,2018年)?模型卡索赔要求与基本数据表一样强。
4. 可核实的证明:是否有任何索赔要求得到加密证明(Laminator 2024, Duddu等人)或其他第三方核查的佐证?未经核实的索赔要求被标为自我报告。
5. 可持续性足迹:碳/水/能源使用情况是否报告? 2025年标准化组织新出现的管理要求。

艰难的拒绝 :
- 任意 model card 不带道德考虑。
- 引用数据集的任意一张卡片,无数据表或同等文档。
- 任何声称“经性别测试”的卡片,没有分类的衡量报告。

拒绝规则 :
- 如果用户问卡片是否“够好”,
- 如果用户要求自动生成卡片,则拒绝使用,除非使用卡德根式(Liu等人,2024年)的系统,并进行人体审查。

产出:对五个部分进行一页审计,标出缺失的内容,并列出最紧迫的新增内容。
