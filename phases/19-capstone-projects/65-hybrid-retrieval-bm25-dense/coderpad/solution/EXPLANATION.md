# 参考解释：Hybrid Retrieval with BM25 and Dense Embeddings

## 核心：倒数排名融合

排名从 1 开始，每个列表内重复 id 只计第一次；不同列表证据累加。

准确合同：For each ranking, score each id once at its FIRST 1-based rank using 1/(constant+rank). Sum across lists. Return ids sorted by descending total score, then lexicographic id. constant>=0 else ValueError; empty rankings yields [].

## 加分：Embedding 余弦相似度

点积除以两个范数乘积；零范数采用题目约定的零相似度。

准确合同：Return cosine similarity of equal-length numeric vectors. Define zero-norm or empty-vector similarity as 0. Unequal lengths raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
