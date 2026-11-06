# 参考解释：Introduction to JAX

## 核心：数值梯度

每个平方误差项独立求导，保留目标与参数的对应关系。

准确合同：For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError.

## 加分：矩阵乘法

先验证矩形和内维度，再按行、列、求和维度三层遍历。矩阵乘法不能用逐元素相乘代替。

准确合同：Multiply nonempty rectangular numeric matrices using row-by-column products. Reject empty matrices, ragged rows, empty rows or incompatible inner dimensions with ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
