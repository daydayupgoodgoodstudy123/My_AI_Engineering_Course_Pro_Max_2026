# 参考解释：Long-Context Evaluation — NIAH, RULER, LongBench, MRCR

## 核心：上下文预算装箱

先按相关性排序，再按剩余预算装入；超大项跳过，不阻断后续小项。

准确合同：items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError.

## 加分：检索指标

先截取 top-k，再分别计算命中、召回和首命中位置；分母 k 不随返回数量缩小。

准确合同：ranked is a unique document-id list; relevant is a list treated as a set. k exact positive int. Return precision=len(top-k relevant)/k, recall=hits/number of unique relevant (0 if none), reciprocal_rank=1/first relevant rank within top-k (0 if none). Duplicate ranked ids or invalid k raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
