---
name: skill-tokenizer
description: Choosing and building tokenizers for LLM projects
version: 1.0.0
phase: 10
lesson: 1
tags: [tokenizer, bpe, wordpiece, sentencepiece, llm, nlp]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="tokenizer-selection-and-implementation"></a>

# Tokenizer选型与实施

当启动 LLM 项目时，应用此决策框架进行 tokenizer 选择。

<a id="when-to-use-each-tokenizer"></a>

## 何时使用每个 tokenizer

**字节级 BPE（tiktoken）：** 您正在构建 fine-tuning GPT 系列模型。您需要保证处理任何输入字节序列。你不想要未知的tokens。

**WordPiece（拥抱脸）：** 您正在使用 BERT 系列模型进行分类、NER 或 embedding 任务。对于依赖字边界信号的下游任务，您需要“##”延续前缀。

**SentencePiece（BPE 或 Unigram）：** 您正在从头开始训练。您需要与语言无关的 tokenization。您的数据包括 CJK 语言、泰语或其他没有空格单词边界的文字。 LLaMA、T5 和大多数多语言模型都使用此。

<a id="vocabulary-size-guidelines"></a>

## Vocabulary 尺寸指南

- 32K tokens：单语言模型的良好默认值，保持 embedding 层较小
- 50K-64K tokens：更适合多语言或代码较多的模型
- 100K+ tokens：仅当您有大量训练数据并且想要短序列时

较大的 vocabulary 意味着较短的序列（较便宜的 inference），但 embedding 矩阵中的 parameters 较多。对于具有 4096 维 embeddings 的 100K vocabulary，仅 embedding 层就是 400M parameters。

<a id="pre-tokenization-rules-that-matter"></a>

## tokenization 之前的重要规则

1. 在 BPE 之前按空格分割以防止跨字合并
2. 如果您希望模型学习算术，请单独分隔数字
3. 在 tokenization 之前规范化 Unicode (NFC) 以获得一致的行为
4. 为您的用例添加特殊的 tokens：`<pad>`、`<eos>`、`<bos>`、`<unk>` 以及任何特定于任务的标记

<a id="red-flags-in-tokenizer-behavior"></a>

## tokenizer 行为中的危险信号

- 目标语言的生产力高于 2.0：模型浪费 context window
- 常见域词拆分为 3+ tokens：使用域数据重新训练
- tokenization 号码不一致：检查分位规则
- 大型 vocabulary 具有许多一次性 tokens：减小 vocabulary 尺寸

<a id="building-a-custom-tokenizer---checklist"></a>

## 构建自定义 tokenizer - 清单

1. 收集代表性训练数据（目标域中至少 1GB 文本）
2. 选择算法：BPE 用于通用，Unigram 用于多语言
3. 根据上述指南设置 vocabulary 大小
4. 配置预 tokenization：空格分割、数字处理、标点符号
5. 添加特殊tokens
6. 使用Hugging Face tokenizers库进行训练（Rust后端，速度快）
7. 验证：检查所有目标语言中保留文本的丰富性
8. 测试边缘情况：空字符串、超长输入、二进制数据、表情符号、RTL 文本
9. 将 tokenizer 与模型 checkpoints 一起保存并版本化
