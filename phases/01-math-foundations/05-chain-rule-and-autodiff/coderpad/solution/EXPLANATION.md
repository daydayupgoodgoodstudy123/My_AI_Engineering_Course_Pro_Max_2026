# 参考解释：Chain Rule & Automatic Differentiation

## 核心：数值梯度

每个平方误差项独立求导，保留目标与参数的对应关系。

准确合同：For equal-length numeric vectors, return the analytic gradient of sum((w-t)^2): 2*(w-t) per coordinate. Empty vectors return []. Unequal lengths raise ValueError.

## 加分：梯度下降一步更新

返回新的参数向量，避免修改调用者对象。学习率为零也属于合法边界。

准确合同：Return w-rate*g for equal-length numeric vectors and rate>=0. Unequal lengths or negative rate raises ValueError. Preserve inputs; empty vectors are valid.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
