# 参考解释：Alignment Anchors: Does the Objective Survive the Edit?

## 核心：L2 归一化

先求平方和的平方根，再检查零范数。零向量没有可唯一确定的方向。

准确合同：Return a new vector divided by its L2 norm. Empty or all-zero vectors raise ValueError. Inputs are finite numbers.

## 加分：向量内积

先检查两个向量长度，避免 zip 静默截断；逐项相乘后求和。

准确合同：Return the dot product of equal-length numeric lists. Empty lists return 0. Unequal lengths raise ValueError. Do not mutate inputs.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
