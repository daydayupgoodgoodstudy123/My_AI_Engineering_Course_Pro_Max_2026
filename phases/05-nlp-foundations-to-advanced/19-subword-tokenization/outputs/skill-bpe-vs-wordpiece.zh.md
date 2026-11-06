---
name: skill-bpe-vs-wordpiece
description: Pick tokenizer algorithm, vocab size, library for a given corpus and deployment target.
version: 1.0.0
phase: 5
lesson: 19
tags: [nlp, tokenization]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定语料库（大小、语言、领域）和部署目标（从头开始训练 / fine-tuning / API 兼容 inference），输出：

1. 算法。 BPE、Unigram 或 WordPiece。一句话理由。
2. 图书馆。 SentencePiece、HF Tokenizers 或 tiktoken。原因。
3. 词汇大小。四舍五入到最接近的 1k。原因与模型大小和语言覆盖范围有关。
4. 覆盖范围设置。 `character_coverage`、`byte_fallback`、特殊-token 列表。
5. 验证计划。保留集上每个字的平均 tokens、OOV 率、压缩比、往返解码相等性。

拒绝在具有罕见脚本内容的语料库上训练字符覆盖率<0.995 tokenizer。在 CI 中没有冻结 `tokenizer.json` 哈希检查的情况下拒绝发送词汇。将 16k 词汇下的任何单语 tokenizer 标记为可能不符合规范。
