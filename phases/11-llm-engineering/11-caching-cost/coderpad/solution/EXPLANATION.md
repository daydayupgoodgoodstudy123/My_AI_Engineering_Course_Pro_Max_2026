# 参考解释：Caching, Rate Limiting & Cost Optimization

## 核心：TTL 缓存回放

缓存有效条件是 now 严格小于 expiry；过期边界不能继续返回旧值。

准确合同：Events have op put/get, key(str), time(number), plus value for put. ttl>=0 else ValueError. Put expiry=time+ttl. Return values for get events, None when absent or time>=expiry. Values are JSON-compatible and copied. Unknown op raises ValueError. Events are chronological.

## 加分：Token 成本计费

按供应商分别积累输入与输出费用；价格单位是每 token，不能误乘每百万 token 的数值。

准确合同：usage rows contain provider,input_tokens,output_tokens exact nonnegative ints. prices maps provider to [input_price,output_price] per token, nonnegative. Return {'total':sum,'by_provider':sums}. Unknown provider raises KeyError; negative/invalid counts or prices raises ValueError. Empty usage yields zero totals.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
