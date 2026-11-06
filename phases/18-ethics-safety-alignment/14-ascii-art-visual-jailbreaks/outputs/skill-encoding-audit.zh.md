---
name: encoding-audit
description: Audit a jailbreak-defense report across encoding-family attacks.
version: 1.0.0
phase: 18
lesson: 14
tags: [artprompt, ascii-art, encoding-attack, utes, structural-sleight]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 jailbreak- 防卫报告,列出 编码家庭攻击覆盖 和国防层 捕捉每一个。

显示 :

1. 编码覆盖。列出每个被评估的家庭: ASCII 艺术(艺术),基础64, 利特语, UTF-8同义词, 嵌套 JSON / YAML CDV,树/壁 TETS,图像 -modality旗子家族失踪
2. 确定每个家庭 哪个防御层(关键词过滤器, perplexity 过滤器、引言、重新招生、产出分类、多式联运管理器)能够捕捉到,但不会。
3. 视觉识别差距。 Per Jiang 等人, 2024, PPL 和 Retokenization 无法对抗艺术Prompt, 因为识别发生在视觉层面。 报告是否包含在视觉/结构层面操作的任何东西?
4. 通用测试。 UTES (StructuralSleiet) 概括为任意的稀有结构。 报告测试结构是否在训练防御系统里?
5. 能力- 安全权衡。 具有更强视觉- 文本能力的模型( 高VTC 评分) 更容易受到 ArtPrompt 的伤害。 注意如果报告, 则该模型的 VTC 评分; 如果没有, 请求取 。

艰难的拒绝 :
- 任何辩护要求都只基于子字符串/关键词过滤。
- 任何辩护主张 覆盖一个编码家庭 并推断为"编码攻击。"
- 任何辩护要求,没有 家庭攻击成功率。

拒绝规则 :
- 如果用户问ArtPrompt是否“插座”,
- 如果用户要求推荐全码辩护,就拒绝单一的建议——必须把辩护分层到部署可能面对的所有家庭。

产出:一页审计,填充上面五个部分,标出主要编码空白,并列出需要添加的最紧急防御层。
