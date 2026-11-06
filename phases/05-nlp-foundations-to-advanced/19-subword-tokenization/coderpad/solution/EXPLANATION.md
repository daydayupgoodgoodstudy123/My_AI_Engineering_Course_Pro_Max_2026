# 参考解释：Subword Tokenization — BPE, WordPiece, Unigram, SentencePiece

## 核心：BPE 相邻 Pair 合并

从左到右非重叠合并；一次合并之后跳过两个原始位置。

准确合同：pair must contain exactly two strings. Scan tokens left to right, replacing each non-overlapping adjacent match with concatenation. Preserve unmatched tokens. Invalid pair raises ValueError; input lists do not mutate.

## 加分：N-gram 计数

窗口重叠计数；用 JSON 编码窗口作为可序列化的 key。

准确合同：n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
