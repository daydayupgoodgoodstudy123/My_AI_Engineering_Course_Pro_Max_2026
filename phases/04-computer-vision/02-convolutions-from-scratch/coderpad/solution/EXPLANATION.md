# 参考解释：Convolutions from Scratch

## 核心：一维卷积窗口

题目定义的是 cross-correlation，不翻转 kernel；窗口只覆盖完整位置。

准确合同：Compute valid 1D cross-correlation (kernel is NOT reversed) using exact positive integer stride. Empty kernel or invalid stride raises ValueError. Kernel longer than signal yields [].

## 加分：池化与补齐

窗口不重叠，最后不足宽度的部分仍参加 max；负数窗口不能用零作初值。

准确合同：Use non-overlapping windows of exact positive integer width. Include a shorter final window. Return max per window; empty input yields []. Invalid width raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
