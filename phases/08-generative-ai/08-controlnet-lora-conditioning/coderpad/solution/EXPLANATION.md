# 参考解释：ControlNet, LoRA & Conditioning

## 核心：LoRA 增量与参数量

先检查低秩矩阵相乘维度，再乘 alpha/rank；不直接修改 base weights。

准确合同：A is nonempty output-by-rank, B is rank-by-input, both rectangular with nonempty rows. Return (alpha/rank)*A@B; alpha is finite numeric. Invalid shapes raise ValueError. No base weights are modified.

## 加分：Rectified Flow 一步积分

显式 Euler 一步积分只做当前状态加步长乘速度，不在本题里训练速度场。

准确合同：Return state+delta*velocity coordinatewise. Require equal lengths and numeric delta in [0,1]; otherwise ValueError. Empty vectors are valid.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
