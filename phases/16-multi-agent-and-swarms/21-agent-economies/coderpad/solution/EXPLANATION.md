# 参考解释：Agent Economies, Token Incentives, Reputation

## 核心：成本预算治理

拒绝的成本不占用余额，后续更便宜的请求仍可能被接受。

准确合同：Sequentially accept each nonnegative numeric cost if spent+cost<=limit, otherwise reject and keep spent unchanged. Return {'accepted':[bool per request],'spent':total}. Negative limit/cost raises ValueError. No rounding, billing API, or actual charge.

## 加分：幂等请求账本

id 绑定 canonical JSON 的 payload；精确重放和冲突复用是两种情况。

准确合同：Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
