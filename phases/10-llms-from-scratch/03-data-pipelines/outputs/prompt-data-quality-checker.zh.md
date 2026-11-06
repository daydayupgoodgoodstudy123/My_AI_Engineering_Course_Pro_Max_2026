---
name: prompt-data-quality-checker
description: Validate and debug data quality in LLM pre-training pipelines
version: 1.0.0
phase: 10
lesson: 3
tags: [data-pipeline, deduplication, quality-filter, pre-training, llm, data-cleaning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="data-quality-checker-for-llm-pre-training"></a>

# LLM 预训练数据质量检查器

在构建或审核 LLM 预训练的数据管道时，使用此框架在问题到达模型之前捕获问题。

<a id="red-flags-in-pipeline-output"></a>

## 管道输出中的危险信号

**重复数据删除删除了不到 20% 的 Web 数据。** 常见爬网通常包含 30-40% 的重复项。如果您的重复数据删除步骤删除的数据少于 20%，则说明您的 MinHash parameters 太保守，或者您的阈值太高。检查： shingle 大小 k、散列函数数量、LSH band 数量、Jaccard 阈值。

**压缩比低于2.0个字符/token.** 这意味着你的tokenizer分裂得太激进了。通过更多合并重新训练，增加 vocabulary 大小，或者检查 tokenization 之前是否不会对文本进行不必要的碎片化。

** 压缩比高于 6.0 个字符/token.** 您的 tokenizer 已经学习了非常特定于域的合并，可能无法泛化。这对于特定领域的模型来说很好，但对于通用模型来说是一个警告信号。

**序列利用率低于90%。** 填充过多。要么您的文档非常短（过滤它们或增加最小文档长度），要么您的序列打包效率低下（从简单填充切换到多文档打包）。

**Vocab 利用率低于 50%。** 您的 vocabulary 的一半以上在此语料库中未使用。 vocabulary 对于您的域来说太大，或者 tokenizer 是在非常不同的数据上进行训练的。

<a id="quality-filter-calibration"></a>

## 质量过滤器 Calibration

在每个管道阶段对 1,000 个文档的随机样本运行这些检查：

1. ** 清洁后随机读取 20 个文档。** 它们是否包含残留的 HTML、JavaScript、导航文本或样板？如果是，则您的 HTML 剥离不完整。

2. **随机阅读20个通过质量过滤器的文档。** 其中是否有垃圾邮件、关键字列表或机器生成的？如果是，收紧过滤器阈值。

3. **随机阅读20个未通过质量过滤的文档。** 其中有真正的好内容吗？如果是，则您的过滤器过于激进。放宽阈值或为特定模式添加例外。

4. **从 dedup 中读取 20 个随机的近似重复对。** 它们实际上相似吗？如果不是，请降低 Jaccard 阈值或增加哈希函数的数量。

<a id="data-mixing-ratios"></a>

## 数据混合比率

没有通用的公式。从这些基线开始，并根据 evaluation 进行调整：

| 类别 | Llama 3 比率 | 起点 |
|----------|--------------|----------------|
| 网页文字 | 50% | 50% |
| 代码 | 25% | 15-25% |
| 书籍/学术 | 13% | 10-15% |
| 数学 | 8% | 5-10% |
| 多语言网络 | 4% | 5-10% |

如果模型应该擅长编程，则增加代码比率。如果推理很重要，则提高数学比率。如果需要减少噪音，请降低幅材比率。更改比率后始终根据基准进行评估。

<a id="scaling-estimates"></a>

## 缩放估计

对于给定的目标 token 计数：

- 来自网络的 1T tokens：预计约 3-5TB 原始文本，清理和重复数据删除后约 1.5-2TB
- Tokenization 速度 (Rust)：每核 ~100M tokens/秒
- Tokenization 速度 (Python)：每核 ~1-10M tokens/秒
- MinHash 以 128 个哈希值、16 个频段进行重复数据删除：每个核心每秒约 10K 个文档
- 序列打包：I/O 限制，对于 10GB 以上的语料库使用内存映射文件

对于 15T tokens（Llama 3 规模），计划约 30-50TB 的原始输入数据、在 64 核计算机上进行 1-2 周的预处理以及用于中间文件的 100TB+ 磁盘。

<a id="checklist-before-training"></a>

## 培训前检查表

1. token 总数与您的计算预算相匹配（使用 Chinchilla 缩放或 Llama 3 过度训练比率作为指导）
2. Dedup 删除了 30-40% 的网络数据
3. 质量过滤器删除了 10-20% 的剩余数据
4. 英文压缩比为3-5个字符/token
5. 序列利用率95%以上
6. 随机抽查显示每个流程阶段的文本清晰、连贯
7. 数据混合比率已在小规模训练中得到验证
8. PII 去除已在样本上得到验证
9. 所有二进制格式（打包序列、token ID 数组）均通过往返编码/解码测试
10. 管道是可重复的：相同的输入使用固定的随机种子产生相同的输出
