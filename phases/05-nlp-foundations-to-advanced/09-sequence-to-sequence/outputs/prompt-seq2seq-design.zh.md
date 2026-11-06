---
name: seq2seq-design
description: Design a sequence-to-sequence pipeline for a given task.
phase: 5
lesson: 09
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定一个任务（翻译、摘要、释义、问题重写），输出：

1. 建筑学。预训练 transformer encoder-decoder（BART、T5、mBART、NLLB）是默认值。基于 RNN 的 seq2seq 仅适用于特定约束（streaming，边缘 inference，教学法）。
2. 启动checkpoint。将其命名为（`facebook/bart-base`、`google/flan-t5-base`、`facebook/nllb-200-distilled-600M`）。将 checkpoint 与任务和语言覆盖范围相匹配。
3. Decoding strategy。贪婪的确定性输出，波束搜索（宽度 4-5）的质量，sampling 和 temperature 的多样性。一句话辩解。
4. 发货前需要验证的一种故障模式。曝光偏差表现为较长输出的生成漂移；在 90% 长度和眼球处对 20 个输出进行采样。

拒绝建议从头开始训练 seq2seq 不到 1M 的并行示例。将使用贪婪解码面向用户的内容的任何管道标记为脆弱（贪婪重复和循环）。
