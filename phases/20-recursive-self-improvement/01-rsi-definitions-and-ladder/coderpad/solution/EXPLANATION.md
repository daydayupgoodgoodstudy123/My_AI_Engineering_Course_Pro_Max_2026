# 参考解释：What "Recursive" Adds: From Self-Refinement to RSI

## 核心：折扣回报

从末尾向前累加未来回报，时间复杂度线性。

准确合同：Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns [].

## 加分：并行加速上限

不可并行部分限制整体速度；公式只描述这个简化的延迟模型。

准确合同：Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
