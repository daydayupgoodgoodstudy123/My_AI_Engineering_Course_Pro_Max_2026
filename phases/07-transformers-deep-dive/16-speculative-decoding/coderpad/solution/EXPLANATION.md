# 参考解释：Speculative Decoding — Draft, Verify, Repeat

## 核心：推测解码前缀验收

只验收连续相同前缀，遇到首个不匹配就停止，不保留后面偶然匹配的 token。

准确合同：Return {'accepted':longest matching prefix of draft and verified, 'next':first verified token after that prefix or None}. draft may be shorter; verified may be empty. Exact token equality; no probabilities or sampling are modeled.

## 加分：Perplexity 与长度

对数域平均后再指数化，避免先连乘造成下溢；各步真值概率无需总和为 1。

准确合同：Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
