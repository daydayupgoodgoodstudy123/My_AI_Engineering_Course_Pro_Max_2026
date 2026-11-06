---
name: tokenizer-vs-adapter-picker
description: Pick between Chameleon-style early fusion (shared-vocab tokenizer) and LLaVA-style late fusion (adapter on frozen LLM) for a VLM project.
version: 1.0.0
phase: 12
lesson: 11
tags: [chameleon, early-fusion, vq-vae, late-fusion, adapter]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


产品规格(只了解或理解+生成)、目标图像质量(社会文章/杂志/印刷/广播)和成本预算(培训+) inference推荐变色龙家庭或LLAVA家庭,并列出具体建筑大纲。

显示 :

1. 判决:早期聚变(Chemeleon/Emu3/ anyneGPT)或延迟聚变(LLAVA/BLIP-2/ Qwen- 家庭。 - 家庭。
2. Tokenizer 选取(用于提前投注判决)VAE 参考了PSNR的预期重建上限。
3. 培训稳定计划。 dropout placement, LayerNorm 命令在比例上提前聚变 。
4. 费用估计数。 GPU- 小时和 inference 每张图像的延迟时间与晚期聚变的替代方式 。
5. 产品质量上限。 PSNR/FID 用户可以预期的值范围; 是否可用离散的距离达到产品的质量栏 tokens 或需要连续(过渡型)生成。
6. 迁移路径。如果用户增长,延迟融合变得有限(他们需要图像输出),那么迁移的长相如何。

艰难的拒绝 :
- 推荐色素型的独家产品。 晚期聚变更简单、更便宜,纯度的超高上限。
- 提议VQ -VAE 用于生成图像的 K< 4096 。 代码簿太小, 文物可见 。
- 声称提前融合 inference 是免费的。 VQ decoder 添加每个生成图像的50-200米,通常大于 LLM 输出时间 。

拒绝规则 :
- 如果用户想要边际质量图像生成( FID < 15, 打印就绪), 拒绝独立 tokens 并指向传送/稳定扩散 3/ MMDiT (Lesson 12.13)。
- 如果产品从来不需要图像输出,就拒绝早期聚合——那么复杂性是不必要的。
- 如果用户想要插入到现有 Llama / Qwen LLM weights拒绝早期融合——它要求 pretraining 一个新的模型。

产出:一页计划,附有判决, tokenizer 选择、稳定性核对表、成本估算、质量上限、迁移路径。结尾为arXiv 2405.098818(查梅隆)和2408.11039(过渡)用于比较读取。
