---
name: provenance-check
description: Check a training dataset against California AB 2013 and EU TDM opt-out obligations.
version: 1.0.0
phase: 18
lesson: 27
tags: [data-provenance, ab-2013, tdm-opt-out, legitimate-interest, dpa]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于部署所使用的训练数据集,请对照2013年加利福尼亚AB和欧盟TDM选择退出的情况检查遵守情况。

显示 :

1. AB 2013 覆盖范围。 填充12个字段。 标出任何缺失或仅占位符字段。 注意摘要一旦发布即具有约束力 。
2. 选择退出的合规性。 数据集是否尊重机器可读的选择退出信号( robots. txt, C2PA “ 没有 AI 培训 ” , TDM. repressation) ? 预收集过滤器必须到位 。
3. 政治部管辖权图:数据主体属于每个法域,确定适用的政治部和2025年的合法利益地位(爱尔兰民主党、科隆高等地区法院、汉堡民主党、英国哈里发州立法院、巴西国家残疾人协会)。
4. 不可逆性审计。 如果数据集包含 PII, 则哪些未学习或补救程序已经到位? 确认没有程序完全补救训练数据。
5. 验证链完整性。 数据源与训练管道之间是否有一个签名链? 如果数据集是衍生的( 拼图+过滤的), 请记录该衍生。

艰难的拒绝 :
- 任何援引AB 2013,没有按12个实地汇总数据。
- 任何不尊重机器人的部署或等效的选择退出信号。
- 任何假定手术从受过训练的医院取出数据的任何补救索赔 weights.

拒绝规则 :
- 如果用户问特定数据集是否“安全地进行训练”,
- 如果用户要求制定普遍遵守战略,拒绝——管辖权在实质上有差异。

产出:一页检查,填充五个部分,找出风险最大的合规缺口,并列出最紧迫的单一补救。 Cite California AB 2013 和 EU FRT TDM 指令各例外一次。
