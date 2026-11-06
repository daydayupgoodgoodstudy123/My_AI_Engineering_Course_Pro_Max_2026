---
name: unified-gen-model-picker
description: Pick between Show-o / Transfusion / Emu3 / Janus-Pro families for a product that needs both multimodal understanding and generation with open weights.
version: 1.0.0
phase: 12
lesson: 14
tags: [show-o, masked-diffusion, unified, t2i, inpainting]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


一种产品需要统一理解+代(VQA, 字幕, T2I, 可选油漆),weights 限制和潜伏预算,选择一个模型家庭并发布参考配置。

显示 :

1. 家庭判决。 显示( 分散的散射)、 传输/ MMDiT ( 连续扩散), Emu3 / 变色龙 (autoregressive 离散),或 Janus-Pro(脱钩) encoders).
2. Inference- 分步预算。 16步Shoe -o,20步Tranculation,1024+Emu3. 使用用户的潜伏预算来说明选择的理由。
3. 油漆支持。 显示- o 是免费的; Transution 添加了遮罩频道; Emu3 需要另外的微调。 给用户标出此选项 。
4. Tokenizer 选择。 对于离散家庭,建议 IBQ / MAGVIT-v2 / SBER; 对于连续的, 建议 SD3 VAE.
5. 培训稳定性:双重损失(过渡)需求 weight 调试; show -o的单项损失是干净的 。
6. 如果用户增长, 迁移路径。 从显示到转换, 当质量成为极限 。

艰难的拒绝 :
- 推荐Emu3/变色龙 inference 每张图像的延迟度为 < 10s 。 Autoregressive 超过~1024 tokens 太慢了 , 有点慢
- 声称显示匹配边界图像质量的传输。 它不匹配 。 tokenizer 上面是天花板,我就是天花板
- 建议稳定传播需要VQA的产品。 SD不能解释图像。

拒绝规则 :
- 如果用户想要每个图像生成 < 2 , 请拒绝 show-o 并推荐稳定传播 + 用于理解的单独 VLM 。 接受多模式的复杂性 。
- 如果用户想要打开“ 最佳类质量” weights,拒绝 Show-o/ Emu3,建议转基因家庭(MMDIT)或JanusFlow。
- 如果用户无法 commit 改为 tokenizer 拒绝独家家庭,建议转送。

产出:一页数,家庭判决、职级预算、油漆支持; tokenizer 以arxiv 2408.12528(show-o)、2408.11039(Transmission)、2501.17811(Janus-Pro)结束。
