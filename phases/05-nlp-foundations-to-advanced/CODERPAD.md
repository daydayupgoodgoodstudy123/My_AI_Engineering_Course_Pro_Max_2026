# 05-nlp-foundations-to-advanced：CoderPad 练习

本章 29 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [Text Processing — Tokenization, Stemming, Lemmatization](01-text-processing/coderpad/README.md) | 文本归一化与分词 | N-gram 计数 |
| 02 | [Bag of Words, TF-IDF, and Text Representation](02-bag-of-words-tfidf/coderpad/README.md) | 词袋向量 | Embedding 余弦相似度 |
| 03 | [Word Embeddings — Word2Vec from Scratch](03-word-embeddings-word2vec/coderpad/README.md) | N-gram 计数 | Embedding 余弦相似度 |
| 04 | [GloVe, FastText, and Subword Embeddings](04-glove-fasttext-subword/coderpad/README.md) | BPE 相邻 Pair 合并 | 文本归一化与分词 |
| 05 | [Sentiment Analysis](05-sentiment-analysis/coderpad/README.md) | 词袋向量 | 分类混淆矩阵指标 |
| 06 | [Named Entity Recognition](06-named-entity-recognition/coderpad/README.md) | BIO 标签到实体片段 | 文本归一化与分词 |
| 07 | [POS Tagging and Syntactic Parsing](07-pos-tagging-parsing/coderpad/README.md) | 马尔可夫状态分布 | 稀疏路由 Top-K |
| 08 | [CNNs and RNNs for Text](08-cnns-rnns-for-text/coderpad/README.md) | 一维卷积窗口 | 池化与补齐 |
| 09 | [Sequence-to-Sequence Models](09-sequence-to-sequence/coderpad/README.md) | 时间序列滞后特征 | 受限解码分布 |
| 10 | [Attention Mechanism — The Breakthrough](10-attention-mechanism/coderpad/README.md) | 单头注意力 | 数值稳定的 Softmax |
| 11 | [Machine Translation](11-machine-translation/coderpad/README.md) | N-gram 计数 | 问答 Token F1 |
| 12 | [Text Summarization](12-text-summarization/coderpad/README.md) | 问答 Token F1 | 检索指标 |
| 13 | [Question Answering Systems](13-question-answering/coderpad/README.md) | 问答 Token F1 | 检索指标 |
| 14 | [Information Retrieval and Search](14-information-retrieval-search/coderpad/README.md) | 倒数排名融合 | 词袋向量 |
| 15 | [Topic Modeling — LDA and BERTopic](15-topic-modeling/coderpad/README.md) | 词袋向量 | 概率分布熵 |
| 16 | [Text Generation Before Transformers — N-gram Language Models](16-text-generation-pre-transformer/coderpad/README.md) | Perplexity 与长度 | N-gram 计数 |
| 17 | [Chatbots — Rule-Based to Neural to LLM Agents](17-chatbots-rule-to-neural/coderpad/README.md) | 角色与工具选择 | 对话槽位更新 |
| 18 | [Multilingual NLP](18-multilingual-nlp/coderpad/README.md) | Embedding 余弦相似度 | 分类混淆矩阵指标 |
| 19 | [Subword Tokenization — BPE, WordPiece, Unigram, SentencePiece](19-subword-tokenization/coderpad/README.md) | BPE 相邻 Pair 合并 | N-gram 计数 |
| 20 | [Structured Outputs & Constrained Decoding](20-structured-outputs-constrained-decoding/coderpad/README.md) | 受限解码分布 | 数值稳定的 Softmax |
| 21 | [Natural Language Inference — Textual Entailment](21-nli-textual-entailment/coderpad/README.md) | 词袋向量 | 分类混淆矩阵指标 |
| 22 | [Embedding Models — The 2026 Deep Dive](22-embedding-models-deep-dive/coderpad/README.md) | Embedding 余弦相似度 | 检索指标 |
| 23 | [Chunking Strategies for RAG](23-chunking-strategies-rag/coderpad/README.md) | 重叠窗口切块 | 上下文预算装箱 |
| 24 | [Coreference Resolution](24-coreference-resolution/coderpad/README.md) | BIO 标签到实体片段 | 对话槽位更新 |
| 25 | [Entity Linking & Disambiguation](25-entity-linking/coderpad/README.md) | Embedding 余弦相似度 | 稀疏路由 Top-K |
| 26 | [Relation Extraction & Knowledge Graph Construction](26-relation-extraction-kg/coderpad/README.md) | 声明与证据绑定 | 最短路径搜索 |
| 27 | [LLM Evaluation — RAGAS, DeepEval, G-Eval](27-llm-evaluation-frameworks/coderpad/README.md) | 检索指标 | 问答 Token F1 |
| 28 | [Long-Context Evaluation — NIAH, RULER, LongBench, MRCR](28-long-context-evaluation/coderpad/README.md) | 上下文预算装箱 | 检索指标 |
| 29 | [Dialogue State Tracking](29-dialogue-state-tracking/coderpad/README.md) | 对话槽位更新 | 合法状态转换 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
