---
name: modality-bridge-picker
description: Recommend Q-Former vs MLP projector vs Perceiver resampler for a VLM configuration given token budget, quality target, and training compute.
version: 1.0.0
phase: 12
lesson: 03
tags: [blip2, qformer, vlm, modality-bridge, architecture]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个愿景 encoder的 token 计算每个图像, LLM上下文预算, 图像目标数 prompt,以及培训计算预算,建议 modality 连接使用和说明理由的桥梁 parameter 计数和 token economics.

显示 :

1. Token budget 审计。 tokens 图像的每张图像 encoder, tokens 每个桥选项后每个图像, 以及 LLM 用于已声明图像的上下文- /prompt counts.
2. 桥比较。 用于每个Q- 前方( 32) tokens~188M参数, MLP 投影仪(全部) patches,~20M参数)和 Perceiver 恢复器(K 通过 N- 级可学习查询) cross-attention,变量)中,给 parameters质量代理 培训成本
3. 建议:对所述制约因素作出单一最佳选择,并单行说明理由。 token budget + 低培训计算)。
4. 两阶段培训 trace如果选择Q-Former,请概述第1阶段的ITM+ITG损失和第2阶段LM损失。 列出每个阶段的代表性数据集(CO、LAION、视觉基因组)。
5. 通勤检查单。 呼叫器在锁定桥之前应该进行五次实验( 询问计数, 两阶段还是单级, 投影器深度, 冻结时间表, 细微子集) 。

艰难的拒绝 :
- 任何忽视 token budget. " 使用 MLP " 与 576 tokens 以 4k 上下文中的 10 张图像为单位, 每张图像均失败 。
- 要求Q-Former严格控制着MLP。 在一幅无限制的图像上, MLP 赢得了高质量任务。
- 将 Perceiver 恢复器作为Q- Former 等效。 火焰哥对每个 LLM 层; BLIP-2 应用一次。

拒绝规则 :
- 如果打电话者要求一座桥梁,可以处理录像,而没有具体说明有多少框架和以什么框架速度,那么拒绝——视像桥与单一图像桥因规格而不同,而不只是规模。
- 如果 LLM 发射范围从头到尾训练,用视觉塔(早期融合、变色龙式)、拒绝——12.11课单独涵盖该情况。
- 如果没有说明培训计算,则拒绝并询问打电话者是否可负担BLIP-2阶段(~100个A100小时)的费用,或只提供投影器的培训。

产出:一页桥建议 token math, parameter 编辑器 校对、推荐的建筑、培训大纲和通缩清单。结尾处有一个“阅读下一步”段落,指向12.04(Flamingo) cross-attention- 每一个地方,只有MLP的12.05(LLVA)课程,或数据-V-建筑交换的12.07(增殖)。
