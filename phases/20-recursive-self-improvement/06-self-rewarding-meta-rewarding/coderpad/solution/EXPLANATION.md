# 参考解释：Self-Rewarding and Meta-Rewarding: When the Judge Is the Student

## 核心：偏好对的稳定 Loss

先形成相对 reference 的偏好 margin，再用稳定 softplus 避免溢出。

准确合同：Require beta>0. z=beta*(chosen_logp-rejected_logp-reference_margin). Return log(1+exp(-z)) stably as max(0,-z)+log1p(exp(-abs(z))). Inputs are finite scalar log probabilities.

## 加分：Expected Calibration Error

按 confidence 分箱，将每箱准确率与置信度差异按样本数加权。

准确合同：Equal-length nonempty lists: confidence in [0,1], correct exact bool; bins exact positive int. Bin index=min(bins-1,floor(confidence*bins)). Return sum(bin_size/n*abs(mean confidence-bin accuracy)); invalid inputs raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
