# 参考答案讲解：SourceWeave（11/06）

计时结束后再看。同目录 `sourceweave/` 为参考实现，全部离线。

## Part 1

正确 Hit 使用 Chunk.flat_id；source-local ordinal 独立保留。错误在正确的 render_context/validate_hit 消费边界外显，不靠伪造数组越界。replace_corpus 从原文产生全新 chunks/vocab/IDF/vectors，并整体提交下一 generation。旧 immutable snapshot 不改；空 replacement 也推进 generation。

性能修复只把完整 corpus fit 留在 replacement 阶段。每个 query 继续完整 embed/search/project/render，使用相同 source TF-IDF formula/backend。没有答案缓存、删必要工作或 sleep。最终实际三慢三快数据和 workload 记录于 SCOPE 及外部 timing evidence。

## Part 2

SQLite 保存有序 documents/terms/chunks、generation 与 binary64 vector BLOB；IDF 同样用单坐标 binary64 BLOB，保留符号零和低 mantissa；SQLite REAL 会将 -0.0 读回 +0.0，不能满足字节精确合同。保存前给定验证器检查 spans/coordinates。一个 transaction 覆盖 DELETE 与所有 INSERT，任何 failure 恢复旧 snapshot；重开 load 不 fit，原词表维度顺序与 IDF/vector 坐标一起恢复，即便该顺序不是字母顺序。相同文本和名字不等于相同来源；空 corpus 不是从未保存。

## Part 3

显式 question 转 source whitespace tokens，distinct keywords 去 stopwords。逐句按原 hit 顺序扫描，strip/len>=10，用 distinct intersection 分数，只在更高正分时更新。记录赢家的原 byte interval 和当前 retrieved-local label。source toy punctuation 与 literal-period splitting 保持，不假装真实 semantic model 或 fact verifier。没有正支持即 uncited fallback；eligible 句子中的 stopword-only overlap 不增加支持，恰好 10 字符的候选仍有效。

## Part 4

正确 GIVEN 驱动逐片回放原文并收集完整 fragments，空 fragment 的位置和 source/encoder ownership 都由它保留。候选 citation_appendix 在完整 body 上读取 marker，按首次出现顺序保留唯一 label，仅导出实际引用的 references。unknown label 是错误；无 marker 返回空字符串。给定 footnote helper 保留并转义原始 metadata，候选构造两个前置 LF、完整 footnote 行和恰好一个末尾 LF。回放驱动只调用并发布该结果，不替候选选择来源或构造附录。

## Part 5

递归 visit 最大 fitting boundary，oversized section 内的 fitting 多句 paragraph 同样整体保留。section 放得下就整体 emit，否则进入 paragraphs/sentences，只有超大 leaf 用原 token byte windows。section_path 继承，raw heading token 只覆盖一次。输出 byte slice 直接来自原文；重复 text 不能通过全文 find 重新定位。尾窗必须保留。docs 有 recursive chunking 概念，source 没有本树算法；有限 parser、offset helpers 与输入 tree 是教学扩展。

## 本地性能证据

完整三慢三快：slow 0.409298, 0.403860, 0.408013 秒；fast 0.003081, 0.003044, 0.002979 秒；限值 0.045 秒，双侧最小余量 8.97 与 14.61 倍。48 documents×384words、180terms、8 个完整 query；来源 fit 只在初始 replacement 外部准备，两侧计时均保留所有 query 输出。详见 SCOPE 的真实外部证据路径。

## 证据边界

测试验证确定性 bookkeeping、source toy 抽取和本地存储/回放合同；不证明真实 LLM 答案质量、事实性、tokenizer 精度、生产 RAG latency、协议兼容性或 crash durability。60 分钟时间分配未经真人校准。
