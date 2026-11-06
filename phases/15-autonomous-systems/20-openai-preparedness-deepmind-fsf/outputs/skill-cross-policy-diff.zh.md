---
name: cross-policy-diff
description: Produce a cross-policy comparison for a specific capability using the OpenAI Preparedness Framework v2, Anthropic RSP v3.0, and DeepMind FSF v3 as reference.
version: 1.0.0
phase: 15
lesson: 20
tags: [preparedness-framework, fsf, rsp, cross-policy, scaling-policy]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于特定的前沿能力(例如“远程自主”、“自动复制和适应”、“研发自动化”),可以产生一个跨政策差异,显示三个框架如何将能力分类以及哪些缓解触发因素。

显示 :

1. **OpenAI PF v2 分类 。** 跟踪或研究。 如果跟踪, 请命名“ 能力+保障报告触发程序 。 如果搜索, 请注意政策语言是“ 潜在” 的缓解 。
2. **Anthropic RSP v3.0 分类。** 哪个阈值(ASL-3、AI研发-4、硬编码禁止)? 哪一种缓解(肯定性案例、安全+部署)?确认承诺是否在 Anthropic- 单级或行业建议级。
3. **深沉 FSF v3 分类 。** 哪个域( 网络、 生物、 ML 研发、 CBRN) ? CCL 或跟踪能力级别 ? 是欺骗性 alignment 是否援引了监测?
4. **趋同摘要。** 三种政策是否就能力的严重程度达成一致,或者是否存在有意义的分歧?哪种分类最严格,哪些最少?
5. **242. 衡量依赖性。** 每种分类都取决于能力测量。 请指明如何测量能力, 以及哪个电子算法提供者( METR、 A波罗、 内部、 第三方)拥有这种测量。

艰难的拒绝 :
- 跨政策要求 alignment 依据是宣布语言相似,没有文件级证据。
- 任何分类,如果无法指明源文件中的具体条款。
- 处理“研究类别” (OpenAI)相当于“分类”——它们具有不同的操作后果。

拒绝规则 :
- 如果用户无法为每种分类提供源文件段落,则拒绝并首先要求引用。
- 如果用户将政策存在视为实际中缓解的证据,则拒绝要求提供具体缓解发射的证据。
- 如果声称能力由框架“覆盖”,但该词没有出现在文件中,则拒绝并要求具体条款的提及。

输出格式 :

返回 diff 文档,使用:
- **能力定义** (一句话)
- **OpenAI PF v2 行** (分类、触发、来源条款)
- **Anthropic RSP v3.0 行** (分类、触发、单方面-五建议)
- **深最小 FSF v3 行** (域域, CCL/ TCL, 欺骗性-)alignment involvement)
- **趋同摘要** (协议+有意义的分歧)
- **计量所有权** (电子供应商,电子供应商的士气)
- **读者建议** (最严格、最不严格、最合理)
