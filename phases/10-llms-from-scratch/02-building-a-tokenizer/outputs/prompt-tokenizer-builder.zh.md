---
name: prompt-tokenizer-builder
description: Build and debug production-quality tokenizers for LLM projects
version: 1.0.0
phase: 10
lesson: 2
tags: [tokenizer, bpe, byte-level, special-tokens, chat-template, multilingual]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="production-tokenizer-builder"></a>

# 生产 Tokenizer Builder

当为 LLM 项目构建或调试 tokenizer 时，请遵循此框架。

<a id="pipeline-checklist"></a>

## 管道清单

每个生产 tokenizer 都需要这五个阶段。如果缺少一项，您将在生产中遇到边缘情况。

1. **Normalize** -- 应用 NFKC Unicode normalization。这会折叠连字（“fi”->“fi”），标准化全角字符并标准化空格。跳过此步骤，同一个单词会根据其输入方式而获得不同的 token ID。

2. **Pre-Tokenize** -- 在 BPE 之前将文本分割成块。对于以英语为中心的模型，使用 GPT-2 的正则表达式模式。将 SentencePiece 的原始字节方法用于多语言模型。该选择决定了 BPE 是否可以跨字边界合并。

3. **BPE Merge** -- 将学习到的合并表应用于每个块内的字节序列。合并表是tokenizer学到的知识。其他一切都是管道。

4. **Special Token Injection** -- 在 BPE 运行之前准确匹配特殊 tokens。 [BOS]、[EOS]、[PAD]，聊天模板标记获得固定ID。他们从不参与合并。

5. **ID Mapping** -- 将 token 字符串转换为整数。该模型仅看到整数。

<a id="debugging-tokenizer-issues"></a>

## 调试Tokenizer问题

**症状：模型在聊天输入上产生垃圾**
- 检查聊天模板。每个模型都有不同的格式。 Llama 3 使用 `<|start_header_id|>` 标记。 ChatGPT 使用 `<|im_start|>` 标记。错误的模板将输入置于训练分布之外。

**症状：非英文文本使用过多 tokens**
- 检查生育力（每个字tokens）。高于 2.0 意味着 tokenizer 在该语言上浪费了 context window。解决方案：使用更多多语言数据重新训练，增加 vocabulary 大小，或将 SentencePiece 与 Unigram 结合使用。

**症状：数字和算术失败**
- 检查数字是如何标记化的。 “1234”作为 token 表示该模型无法进行数字级操作。在预 tokenization 期间单独分割数字。

**症状：代码tokens效率低下**
- 检查缩进是如何处理的。 GPT-2的tokenizer在空间上浪费了tokens。 Codex 和 StarCoder 使用特殊缩进 tokens（4 个空格 = 1 token）。

<a id="vocabulary-size-decision"></a>

## Vocabulary 尺寸决定

- 32K tokens：单语言，小模型，有限计算。 Embedding 层为 32K * d_model parameters。
- 50K-64K：多语言或代码较多。大多数项目都具有良好的平衡性。
- 100K+（GPT-4、Llama 3）：仅限海量训练数据。较短的序列，但 100K * d_model embedding parameters。

对于 4096 维模型：32K 词汇 = 131M embedding 参数。 128K 词汇 = 524M embedding 参数。即embedding层中的400M parameters。

<a id="speed-requirements"></a>

## 速度要求

- 训练数据 tokenization：使用 Rust 支持的库（tiktoken、HuggingFace tokenizers）。纯 Python 慢 10-100 倍。
- Inference tokenization：延迟问题较少（单序列），但仍然使用编译的实现。
- 基准：标记 1GB 文本并测量挂钟时间。如果时间超过 60 秒，请切换到 Rust 后端。

<a id="chat-template-validation"></a>

## 聊天模板验证

在部署任何聊天模型之前，请验证模板：

1. 使用 tokenizer 对已知对话进行编码
2. 将其解码回文本
3. 将逐个字符与模型文档中的预期格式进行比较
4. 支付 attention 至：标题 tokens 后的换行符、内容前的空格、回合结束标记
5. 测试边缘情况：空system message，很长user message，多个助手轮流

聊天模板错误是导致聊天模型性能下降的最常见原因。
