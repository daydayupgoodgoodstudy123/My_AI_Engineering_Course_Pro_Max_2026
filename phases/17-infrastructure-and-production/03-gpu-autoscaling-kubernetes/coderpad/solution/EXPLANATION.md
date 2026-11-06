# 参考解释：GPU Autoscaling on Kubernetes — Karpenter, KAI Scheduler, Gang Scheduling

## 核心：容量与副本数

先按目标利用率计算有效容量，再向上取整并限制最小、最大副本数。

准确合同：Compute ceil(arrival_rate/(capacity_per_replica*target_utilization)), clamped to exact integer minimum..maximum. Require arrival_rate>=0,capacity>0,0<utilization<=1,0<=minimum<=maximum. Invalid input raises ValueError. No Kubernetes call.

## 加分：优先级任务调度

只从 queued 候选调度，优先级、创建时间与 id 共同确定稳定顺序。

准确合同：Jobs have unique id(str), priority(number), created(number), status. Select only queued jobs, sorted priority descending, created ascending, id ascending. Return at most capacity ids. capacity exact nonnegative int; duplicate ids or invalid capacity raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
