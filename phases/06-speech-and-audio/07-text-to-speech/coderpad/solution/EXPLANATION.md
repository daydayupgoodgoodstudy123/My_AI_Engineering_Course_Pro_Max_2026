# 参考解释：Text-to-Speech (TTS) — From Tacotron to F5 and Kokoro

## 核心：时间序列滞后特征

特征窗口严格位于预测目标之前，避免把未来信息放进训练数据。

准确合同：window is exact positive int. Return {'x':[each consecutive window before target], 'y':[next value]}. Never include the target in its own features. window>=len(series) yields empty x/y. Invalid window raises ValueError.

## 加分：Warmup 与余弦学习率

把 warmup 和衰减分段；超过总步数后截断到末端学习率。

准确合同：Require exact integer total>0, 0<=warmup<total, step>=0, and peak>=0. If step<warmup return peak*step/warmup; otherwise peak*(1+cos(pi*min(1,(step-warmup)/(total-warmup))))/2. Invalid configuration raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
