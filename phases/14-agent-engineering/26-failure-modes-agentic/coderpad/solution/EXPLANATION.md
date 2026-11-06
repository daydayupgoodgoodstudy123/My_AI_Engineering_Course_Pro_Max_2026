# 参考解释：Failure Modes: Why Agents Break

## 核心：有限指数退避

生成重试计划而不实际等待；最大尝试数和上限共同约束成本。

准确合同：Return [min(cap,base*2**i) for i in range(attempts)]. attempts exact int 0..30; base/cap nonnegative numeric. Invalid input raises ValueError. No sleeping, randomness or calls are performed.

## 加分：合法状态转换

允许边应显式列出，终态不再接受新转换，包括重放到同一状态。

准确合同：Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
