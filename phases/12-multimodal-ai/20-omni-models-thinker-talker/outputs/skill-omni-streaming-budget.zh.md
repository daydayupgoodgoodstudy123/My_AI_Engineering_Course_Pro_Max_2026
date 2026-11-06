---
name: omni-streaming-budget
description: Size a Thinker-Talker streaming voice pipeline (Qwen-Omni / Moshi / Mini-Omni) for a target TTFAB and feature set.
version: 1.0.0
phase: 12
lesson: 20
tags: [qwen-omni, moshi, mini-omni, streaming, ttfab, thinker-talker]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于第一个语音产品规格(目标 TTFAB、麦克风样本率、是/否的视觉、双语、全复)和计算限制(GPU 类别,预算),大小思想家 - 拖车管道。

显示 :

1. 模范家庭取款。 Moshi(最佳床位),Quen2.5-Omni(最佳开放) features),Quen3-Omni(边境质量)、Mini-Omni(简单)。
2. 7B 7B + 200-300M 的 TTFAB. 70B+ 质量思考器, 接受更高的 TTFAB 。
3. 专题信托基金分类,按构成部分分列,估计存在延迟。
4. 双倍模式。 将 VAD 转成默认值时半倍的双倍; 如果产品需要后端通道, 则全倍的双倍 。
5. 视觉整合:带有断层视频框绝对时间戳的TMROPE。
6. 部署形状,单人GPU 与分解(A对A,B对讲者)基于输送需求。

艰难的拒绝 :
- 7 0B 朗读者,讲者必须小一点才能跟上演讲 token rate.
- 使用非streaming speech decoder. TTFAB 爆炸。
- 要求完全的重复是插接和游戏。 它需要专门的训练数据 。

拒绝规则 :
- 如果目标TTFAB < 200ms, 拒绝单A100上比莫希级( 7B 引信) 大的任何内容。
- 如果产品需要流传音乐, 拒绝这个建筑, 建议另外的音乐管道。
- 如果麦克风样本率为48kHz, 质量严格, 显示需要更强的语音 encoder不要盲目地标本

产出:一页 streaming 使用模型选择、大小、 TTFAB 分解、 双面模式、 视觉策略、 部署。 以 2503.20215 (Quen2.5- Omni) 结束, 241,000037 (Moshi) 结束 。
