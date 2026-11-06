# 参考解释：Dimensionality Reduction

## 核心：2×2 实特征值

使用迹与行列式构造二次方程，检查判别式，再对两个实根排序。

准确合同：Require a 2x2 numeric matrix. Return its two real eigenvalues sorted ascending. A negative discriminant or invalid shape raises ValueError. Repeated eigenvalues appear twice.

## 加分：训练统计量与变换

只从 train 拟合均值和尺度，再应用到 values；这是数据泄漏的边界。

准确合同：Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
