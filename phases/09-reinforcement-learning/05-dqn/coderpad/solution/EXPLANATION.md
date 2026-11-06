# 参考解释：Deep Q-Networks (DQN)

## 核心：Q-learning 更新

终止状态没有未来 bootstrap；非终止状态需要至少一个下一状态动作值。

准确合同：Require alpha,gamma in [0,1]. For terminal transition target=reward and next_values may be empty; otherwise require nonempty next_values and target=reward+gamma*max(next_values). Return current+alpha*(target-current). Invalid inputs raise ValueError.

## 加分：梯度范数裁剪

所有梯度共享一个缩放系数，保留方向；不能逐元素独立裁剪代替范数裁剪。

准确合同：Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
