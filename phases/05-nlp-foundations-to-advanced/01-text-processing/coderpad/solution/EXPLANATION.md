# 参考解释：Text Processing — Tokenization, Stemming, Lemmatization

## 核心：文本归一化与分词

先 casefold 再按固定 ASCII 正则分词，明确该规则的多语言限制。

准确合同：Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching.

## 加分：N-gram 计数

窗口重叠计数；用 JSON 编码窗口作为可序列化的 key。

准确合同：n is exact positive int. Return a dict whose keys are JSON strings encoding each token window (json.dumps defaults) and whose values are counts. n>len(tokens) or empty tokens returns {}. Invalid n raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
