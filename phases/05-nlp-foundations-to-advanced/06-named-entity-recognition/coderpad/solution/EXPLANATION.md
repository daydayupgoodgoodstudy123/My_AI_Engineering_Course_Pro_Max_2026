# 参考解释：Named Entity Recognition

## 核心：BIO 标签到实体片段

维护活动实体类型和起点；遇到不匹配的 I 标签按合同开启新实体。

准确合同：Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities.

## 加分：文本归一化与分词

先 casefold 再按固定 ASCII 正则分词，明确该规则的多语言限制。

准确合同：Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
