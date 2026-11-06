# 参考解释：Support Vector Machines

## 核心：距离与形状校验

统一计算逐维绝对差，再按指标归约；长度错误必须先拒绝。

准确合同：Equal-length numeric vectors: metric l1 gives sum absolute differences; l2 gives Euclidean distance; linf gives maximum absolute difference, or 0 for empty vectors. Unknown metric or unequal lengths raises ValueError.

## 加分：确定性的最近邻

距离可用平方值比较；相同距离按原索引排序以保证可复现。

准确合同：Return indices of the k nearest points by squared Euclidean distance; ties use lower original index. All points must match query dimension. k is an exact int in [0,len(points)], otherwise ValueError. k=0 returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
