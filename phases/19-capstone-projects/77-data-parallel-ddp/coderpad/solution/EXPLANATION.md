# 参考解释：Data Parallel DDP From Scratch

## 核心：集体归约

按位置归约，平均时除以 worker 数。空 worker 集合与空向量含义不同。

准确合同：Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking.

## 加分：数值梯度

每个平方误差项独立求导，保留目标与参数的对应关系。

准确合同：For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
