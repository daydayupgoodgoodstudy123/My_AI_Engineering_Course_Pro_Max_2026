---
name: societal-risk-review
description: Review a deployment for societal-scale-risk posture using the CAIS four-risk framework and CAISI / SB-53 regulatory context.
version: 1.0.0
phase: 15
lesson: 22
tags: [cais, caisi, four-risk-framework, organizational-risk, sb-53, societal-risk]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于拟议或正在使用AI, 编制社会风险规模审查,对照CAIS四种风险框架对部署进行标记,清点组织风险次转移物,并列出监管面。

显示 :

1. **4个危险标记** 对于这四类(恶意使用、人工智能竞赛、组织风险、流氓AI)中的每一类,请说明部署是否与它有关以及如何接触。 部署可以触及多个类别;“不适用”必须在一句话中说明理由。
2. **组织风险清单。** 将部署分机的分机计数:安全文化、审计严格、多层防御、信息安全。 任何杠杆都“丢失”是标记的空白。
3. **管理面。** 说明适用的监管框架:欧盟AI法案(如果在欧盟或为欧盟服务的用户中),加利福尼亚SB-53(如果签署和适用),CAISI自愿协议(如果实验室已经签署的话),遵守是一个部署大门,而不是一个良好的部署。
4. **External-evaluation posture.** 命名外部 evaluations 部署或基地模型(METR、CAISI、阿波罗、灰天鹅等)已经使用。 evaluation 是一个标记的缺口 长视距自动部署。
5. **结构力暴露。** 估计该组织在部署方面承受了多少竞争压力,以及这种压力如何与组织风险杠杆作对。 面临激烈的种族压力的团队首先将审计列为优先事项;这是CAIS的调查结果。

艰难的拒绝 :
- 使用没有硬编码禁止层的有害能力类别(第17条)。
- 在竞争条件下部署,不进行独立审计。
- 长期自主部署,无外部能力 evaluation.
- 欧盟部署没有第14条HITL(第15条)。
- 加利福尼亚部署没有事故报告程序,如果SB-53签署。

拒绝规则 :
- 如果用户不能指定基准模型的外部评价员,则首先拒绝和要求识别。evaluation 单凭自己是不够的。
- 如果用户把“我们有比例政策”视为遵守灾难性风险条例,则拒绝并要求具体的监管表层图。
- 如果用户提议在种族压力下部署而不进行审计,则拒绝提供CAIS关于组织风险的调查结果并列出其名称。

输出格式 :

重新进行社会风险审查,包括:
- **四种风险表格** (类别,接触过或没有,性质)
- **组织风险记分卡** (安全文化/审计/防御/防腐)
- **管制面** (遵守状况的适用框架)
- **External-evaluation posture** (蒸发器, 范围, 音频)
- **结构力暴露** (低/中/高与理由)
- **部署准备情况** (生产/中转/仅研究)
