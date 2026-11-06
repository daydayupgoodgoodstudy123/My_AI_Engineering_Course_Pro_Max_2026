---
name: skill-embeddings-picker
description: Pick a tokenization approach for a new language model or text pipeline.
version: 1.0.0
phase: 5
lesson: 04
tags: [nlp, tokenization, embeddings]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务和数据集描述，您输出：

1. Tokenization策略（字级、BPE、WordPiece、SentencePiece、字节级BPE）。一句话理由。
2. Vocabulary 尺寸目标。仅限英语 LM：32k。多语言：64k-100k。代码：50k-100k。
3. 库调用准确的训练命令。将库命名为（Hugging Face `tokenizers`、`sentencepiece`）。引用论点。
4. 一个可重复性的陷阱。 Tokenizer 模型不匹配是最常见的无声生产错误。命名哪个 tokenizer 与预训练的 checkpoint 配对并警告不要交换。

当用户是 fine-tuning 预训练的 LLM 时，拒绝建议训练自定义 tokenizer （微调必须使用预训练的 tokenizer）。拒绝为任何生产 inference 路径推荐字级 tokenization。将非英语或多脚本语料库标记为需要 SentencePiece 并带有字节回退。
