# 参考解释：ASCII Art and Visual Jailbreaks

## 核心：文本归一化与分词

先 casefold 再按固定 ASCII 正则分词，明确该规则的多语言限制。

准确合同：Casefold Unicode text, then return all contiguous ASCII [a-z0-9]+ tokens in order. Punctuation separates tokens. No stemming, stop-word removal or Unicode word matching.

## 加分：分类信号合并

同类信号取最严重值，跨类再判断阻断阈值；没有信号时不凭空生成命中。

准确合同：Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
