# 参考解释：Distributed Data Parallel and FSDP from Scratch

## 核心：均衡参数分片

商负责基础片长，余数分给前面的 workers；覆盖所有索引且没有重叠。

准确合同：Require exact ints total>=0 and workers>0. Return workers half-open [start,end] ranges covering 0..total without gaps; allocate one extra item to each earliest worker until the remainder is exhausted. Empty shards are allowed.

## 加分：集体归约

按位置归约，平均时除以 worker 数。空 worker 集合与空向量含义不同。

准确合同：Require a nonempty list of equal-length numeric vectors. Return elementwise sum, or mean if average is True. Ragged/empty worker lists raise ValueError; zero-length worker vectors are valid. No networking.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
