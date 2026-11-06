# 参考解释：Production Serving Stack — KV Offloading and Cache-Aware Routing

## 核心：LRU 缓存淘汰

每次访问将 key 移到最近端，满额时只移除最旧项。

准确合同：Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError.

## 加分：有界批处理装箱

保持任务顺序，超限时开启新批；单个超大请求不能悄悄被丢弃。

准确合同：items are {'id','tokens':exact positive int}; maximum exact positive int. Preserve input order, greedily pack consecutive items while sum tokens<=maximum. Oversized item raises ValueError rather than silently dropping it. Return list of lists of ids; empty input yields [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
