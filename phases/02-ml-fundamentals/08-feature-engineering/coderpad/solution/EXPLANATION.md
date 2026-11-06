# 参考解释：Feature Engineering & Selection

## 核心：训练统计量与变换

只从 train 拟合均值和尺度，再应用到 values；这是数据泄漏的边界。

准确合同：Compute mean and population standard deviation from nonempty train, then transform values. If training variance is zero use scale=1. Return {'mean','scale','values'}. Never fit on values; empty train raises ValueError.

## 加分：词袋向量

按外部 vocabulary 的顺序输出，未知词不扩展向量长度。

准确合同：Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
