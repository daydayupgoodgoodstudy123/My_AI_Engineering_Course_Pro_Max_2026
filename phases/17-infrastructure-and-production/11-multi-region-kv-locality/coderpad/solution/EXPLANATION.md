# 参考解释：Multi-Region LLM Serving and KV Cache Locality

## 核心：LRU 缓存淘汰

每次访问将 key 移到最近端，满额时只移除最旧项。

准确合同：Replay string-key accesses in a cache of exact nonnegative integer capacity. Every access inserts/touches the key. Evict least recently used when full. Return final keys from least to most recent. capacity 0 returns []; invalid capacity raises ValueError.

## 加分：TTL 缓存回放

缓存有效条件是 now 严格小于 expiry；过期边界不能继续返回旧值。

准确合同：Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
