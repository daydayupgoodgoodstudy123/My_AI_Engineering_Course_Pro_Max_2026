---
name: classifier-stack-audit
description: Audit a deployment's input/output classifier stack (model, taxonomy, input rails, output rails, dialog rails) and flag adversarial-attack gaps.
version: 1.0.0
phase: 15
lesson: 18
tags: [llama-guard, nemo-guardrails, input-rails, output-rails, colang, adversarial-attacks]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给部署的分类器堆叠( Q)Llama 卫兵版本, NeMo Guardrails 配置, 自定义分类器, normalization 并标注堆叠不覆盖的表面

显示 :

1. **示范库存。** 列出正在使用的分类 。 Llama 卫兵3 (8B / 1B-INT4) 与 Llama 警卫4号(多式,S1-S14)。 Guardrails 版本。 任何自定义分类器。 如果部署接受图像, 请确认分类器是多式的 。
2. **分类图绘制。** 地图在分类分类器分类上宣布了业务类别。 操作员关心的每个类别都必须映射到分类类别; 未标定的类别没有被保护 。
3. **铁路覆盖。** 输入轨迹在模型转弯前确认,输出轨迹在响应船前确认。对数轨(NeMo中的Colang)强制实施交叉弯曲限制。 单圈分类无法捕捉多圈攻击。
4. **Normalization.** 确认输入为NFKC 常规、同质拼图,在分类前有零维/变异选择字符被剥除。 Raw-byte 分类是Emoji 走私的100% ASR目标(Huang等人,2025年)。
5. **攻击体覆盖。** 每一个记录在案的攻击(moji 走私、同质文字、 文本中重置、 语义句)都列出堆叠中的具体防御。 仅使用分类的防御无法进行审计; 需要按照宪法( Lesson 17) 和运行时间( Lesson 10, 13, 14) 进行分层处理 。

艰难的拒绝 :
- 使用只对文本进行分类的多式联运投入。
- 无部署 normalization step.
- 仅配备输入轨迹的部署(没有敏感类别产出的产出轨迹)。
- 堆叠将分类器作为单一的安全层。
- ASR称,经营人不能自行分发。

拒绝规则 :
- 如果用户所申报的分类类别没有映射到分类分类, 请先拒绝并需要映射。 未绘制地图 = 无保护 。
- 如果部署说明 Llama 3 ASR 数字在多式联运输入面、垃圾和需要 Llama 4号警卫或多式联运分类员。
- 如果用户在高风险环境下认为分类层足够,请拒绝。 欧盟《AI法案》第14条(第15条)要求上级人员监督。

输出格式 :

返回分类审计, 包括:
- **示范库存** (名称、版本、 modality)
- **分类图绘制** (业务人员类别 分类人员类别)
- **铁路覆盖** (输入/输出/对话框; 模式之前/之后的开关)
- **Normalization note** (NFKC y/n,同形y/n,零边带y/n)
- **攻击体覆盖** (攻击 防卫)
- **图层完整性** (分类+结构+运行时间;需要3个)
- **Readiness** (生产/中转/仅研究)
