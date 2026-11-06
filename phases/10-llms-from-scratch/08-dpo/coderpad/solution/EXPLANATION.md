# 参考解释：DPO: Direct Preference Optimization

## 核心：偏好对的稳定 Loss

先形成相对 reference 的偏好 margin，再用稳定 softplus 避免溢出。

准确合同：Require beta>0. z=beta*(chosen_logp-rejected_logp-reference_margin). Return log(1+exp(-z)) stably as max(0,-z)+log1p(exp(-abs(z))). Inputs are finite scalar log probabilities.

## 加分：稳定 Sigmoid

按正负分支计算，避免对很大的正数调用 exp。

准确合同：Return logistic sigmoid for a finite scalar, avoiding overflow for large positive or negative magnitudes.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
