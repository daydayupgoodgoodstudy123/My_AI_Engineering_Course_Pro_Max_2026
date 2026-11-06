# 参考解释：Image Fundamentals — Pixels, Channels, Color Spaces

## 核心：矩阵转置

验证每行长度一致后，交换行列索引。注意空矩阵和空行矩阵的区别。

准确合同：Return a new list-of-lists transpose. Empty input returns []. Ragged rows raise ValueError. A rectangular matrix of empty rows transposes to [].

## 加分：训练统计量与变换

只从 train 拟合均值和尺度，再应用到 values；这是数据泄漏的边界。

准确合同：Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
