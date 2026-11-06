# 参考解释：ZeRO Optimizer State Sharding

## 核心：均衡参数分片

商负责基础片长，余数分给前面的 workers；覆盖所有索引且没有重叠。

准确合同：Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed.

## 加分：模型参数与内存估算

每个参数张量的维度相乘，再乘每元素字节数；标量张量有一个元素。

准确合同：Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
