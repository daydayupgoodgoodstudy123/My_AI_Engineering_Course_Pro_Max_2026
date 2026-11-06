# 参考解释：Why Multi-Agent?

## 核心：并行加速上限

不可并行部分限制整体速度；公式只描述这个简化的延迟模型。

准确合同：Return 1/(serial_fraction+(1-serial_fraction)/speedup). Require serial_fraction in [0,1] and speedup>=1; otherwise ValueError. This models latency, not queueing throughput.

## 加分：Token 成本计费

按供应商分别积累输入与输出费用；价格单位是每 token，不能误乘每百万 token 的数值。

准确合同：usage rows contain provider,input_tokens,output_tokens exact nonnegative ints. prices maps provider to [input_price,output_price] per token, nonnegative. Return {'total':sum,'by_provider':sums}. Unknown provider raises KeyError; negative/invalid counts or prices raises ValueError. Empty usage yields zero totals.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
