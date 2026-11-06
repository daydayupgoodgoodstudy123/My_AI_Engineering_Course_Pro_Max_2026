# 参考解释：Language Model Evaluation Harness

## 核心：Perplexity 与长度

对数域平均后再指数化，避免先连乘造成下溢；各步真值概率无需总和为 1。

准确合同：Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep.

## 加分：检索指标

先截取 top-k，再分别计算命中、召回和首命中位置；分母 k 不随返回数量缩小。

准确合同：ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
