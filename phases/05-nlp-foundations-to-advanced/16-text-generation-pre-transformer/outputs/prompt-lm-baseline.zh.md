---
name: lm-baseline
description: Build a reproducible n-gram language model baseline before training a neural LM.
phase: 5
lesson: 16
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库和目标使用（下一个单词预测、重新评分、perplexity 基线），输出：

1. N 元语法顺序。用于通用英语的 Trigram，如果语料库较大则使用 4-gram，用于语音重新评分的 5-gram。
2. 平滑。默认为修改型 Kneser-Ney；拉普拉斯仅供教学。
3. 图书馆。 `kenlm` 用于生产，`nltk.lm` 用于教学，自己动手只是为了学习数学。
4. Evaluation。在训练集和测试集之间保留 perplexity 与一致的 tokenization。

拒绝报告正在比较的系统之间使用不同的 tokenization 计算的 perplexity — perplexity 数字仅在相同的 tokenization 下才具有可比性。标记测试集中的 OOV 率； KN 处理 OOV 的能力很差，除非你在训练期间预留了特殊的 `<UNK>` token。
