# 参考解释：Load Testing LLM APIs — Why k6 and Locust Lie

## 核心：滑动窗口限流

清掉左边界以及更早的已接受事件，只让真正接受的事件占用槽位。

准确合同：Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot.

## 加分：分位数与 Goodput

分位数使用明确的 nearest-rank 定义，goodput fraction 统计达标请求比例。

准确合同：Use nonempty nonnegative numeric latencies and deadline>=0. Return {'p50':nearest-rank median,'p95':nearest-rank 95th percentile,'goodput_fraction':fraction <=deadline}. Nearest-rank index=ceil(p*n)-1. Invalid input raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
