# 参考解释：Hyperparameter Tuning

## 核心：超参数网格与预算

先排序参数键，再保留候选值原序，保证网格枚举可复现并遵守数量预算。

准确合同：Enumerate Cartesian products with parameter keys sorted lexicographically and option order preserved. Return at most limit dicts; limit is exact nonnegative int. Empty parameter dict produces [{}] if limit>0. Any empty option list produces []. Invalid limit raises ValueError.

## 加分：稀疏路由 Top-K

完整排序按分数与原索引双键，保证 ties 可复现。

准确合同：Return the indices of k largest scores, descending score with lower original index ties. k exact int in [0,len(scores)], else ValueError; k=0 returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
