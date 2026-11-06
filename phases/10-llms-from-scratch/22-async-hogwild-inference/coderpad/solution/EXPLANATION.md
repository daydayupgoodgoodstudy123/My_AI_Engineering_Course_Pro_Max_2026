# 参考解释：Async and Hogwild! Inference

## 核心：幂等请求账本

id 绑定 canonical JSON 的 payload；精确重放和冲突复用是两种情况。

准确合同：Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal.

## 加分：滑动窗口限流

清掉左边界以及更早的已接受事件，只让真正接受的事件占用槽位。

准确合同：Times are nondecreasing numeric timestamps. Keep only accepted timestamps in (now-window,now]. Accept when fewer than maximum remain. maximum exact positive int and window>0; descending timestamps/invalid config raises ValueError. Return decision bools; rejected events consume no slot.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
