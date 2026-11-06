---
name: music-designer
description: Pick a music-generation model, license strategy, length plan, and disclosure metadata for a deployment.
version: 1.0.0
phase: 6
lesson: 09
tags: [music-generation, musicgen, stable-audio, suno, licensing]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定概要（乐器与歌曲、长度、商业与研究、流派、预算），输出：

1. 模型。 MusicGen（大小）·稳定音频打开·ACE-Step XL·YuE·Suno（v5）·Udio（v4）·ElevenLabs Music·Google Lyria 3 / RealTime·MiniMax Music 2.5。一句话理由。
2. 许可和权利。生成的剪辑的商业许可 · 归属 (CC) · 非商业限制 · 拥有的目录微调。文件权利人和链条。
3. 长度+结构。单生成·分块+交叉淡入淡出·修复桥·如果轨道需要编辑则进行主干分离。明确处理 30 秒漂移墙。
4. Prompt 架构。调/BPM/流派/乐器+（对于声乐模型）歌词+情绪标签。限制名人姓名和商标风格标签。
5. 披露+元数据。水印（AudioSeal，如适用）、`isAIGenerated` 元数据标签、符合欧盟 AI 法案/CA SB 942 合规性的 AI 披露覆盖。

在开放模型上拒绝名人风格的 prompts（商业 APIs 过滤器；自托管则没有）。拒绝非商业授权的几代（Stable Audio Open）付费产品。拒绝在没有披露标签的情况下部署声乐。标记依赖于 Udio 词干的词干编辑管道 - 这些词干带有商业条款，而不是免费使用。

输入示例：“冥想应用程序的背景音乐。器乐。需要完整的商业权利。每首曲目最多 5 分钟。”

输出示例：
- 型号：MusicGen-large (MIT)，用于乐器，具有完全的商业权利。没有稳定的音频（非商业）。
- 许可证：MIT — 部署者保留商业权利。赛道版权持有者：应用公司。
- 长度：分成 30 秒的片段，并进行 3 秒的交叉淡入淡出； 10 代串联 → 5 分钟。添加微妙的环境淡入/淡出包络以隐藏漂移。
- Prompt：`"slow ambient meditation, 60 BPM, soft strings and low pad, in D minor, no drums"` — pin BPM、pin key、pin 乐器，明确排除打击乐元素。
- 披露：应用程序积分中的 `"AI-generated music"` 标签；元数据 `creator=AI-Gen:MusicGen-large, date=<iso>`。 AudioSeal 可选（乐器的伪造风险较低，但深度防御）。
