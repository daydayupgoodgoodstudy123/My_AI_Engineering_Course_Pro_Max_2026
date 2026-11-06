# 参考解释：Evaluation: Benchmarks, Evals, LM Harness

## 核心：Perplexity 与长度

对数域平均后再指数化，避免先连乘造成下溢；各步真值概率无需总和为 1。

准确合同：Return exp(-mean(log(p))) for nonempty true-token probabilities, each 0<p<=1. Invalid inputs raise ValueError. Probabilities are not required to sum to 1 because each refers to a different timestep.

## 加分：Expected Calibration Error

按 confidence 分箱，将每箱准确率与置信度差异按样本数加权。

准确合同：Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
