---
name: moderation-stack
description: Recommend a moderation stack configuration for a production deployment.
version: 1.0.0
phase: 18
lesson: 29
tags: [openai-moderation, perspective, llama-guard, layered-moderation, azure-content-safety]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于生产部署,建议三层的中度堆叠配置。

显示 :

1. 输入分类器。 选择 OpenAI Moderation, Llama 卫兵3/4,或视角 API与政策分类相匹配。 Llama 警卫4或 OpenAI omni-moderation.
2. 输出分类器。 与输入分类器相同或不同。 匹配阈值到下游风险模式 。
3. 自定义域规则。 列出一般分类者不会捕捉的域规则: 财务建议拒绝声明、 医疗建议拒绝、 法律拒绝声明模式 。
4. 边缘案件法官,指明人类降级途径,拒绝是最终决定;不明朗的案件由苏丹解放军内部进行人性审查。
5. 迁移计划 如果Azure内容主持人在堆叠中 计划在2027年2月退休前 迁移到Azure AI内容安全

艰难的拒绝 :
- 任何部署,如不节制产出(仅投入是不够的)。
- 任何未对受管制表面(金融、卫生、法律)制定海关域规则的部署。
- 任何部署都完全依靠...LLM- 用于现代聊天应用程序的时代分类( perspective) 。

拒绝规则 :
- 如果用户要求最好的分类,拒绝——分类选择是针对具体政策分类的。
- 如果用户要求阈值,则拒绝单数——阈值取决于风险承受力和下游效应。

产出:一页建议,填充五个部分,在每一层点名分类,并标出移徙义务。 OpenAI 调节剂量和 Llama 卫兵3/4每个都提到过一次
