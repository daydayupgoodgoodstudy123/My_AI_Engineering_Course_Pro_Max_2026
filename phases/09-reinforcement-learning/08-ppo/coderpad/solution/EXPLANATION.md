# 参考解释：Proximal Policy Optimization (PPO)

## 核心：PPO Clipped Surrogate

分别计算原始与裁剪后的目标再取较小者，负 advantage 的符号不能丢失。

准确合同：Return mean(min(ratio*A,clip(ratio,1-epsilon,1+epsilon)*A)). Require equal nonempty lists, ratios>=0, and 0<=epsilon<1; otherwise ValueError. Keep the sign of advantages.

## 加分：Actor-Critic Advantage

每个 reward 对应当前和下一状态 value，因此 values 长度多一项。

准确合同：values contains one more element than rewards. Return one-step TD advantage r[t]+gamma*v[t+1]-v[t]. Require gamma in [0,1] and exact length relation; otherwise ValueError. Empty rewards plus one value returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
