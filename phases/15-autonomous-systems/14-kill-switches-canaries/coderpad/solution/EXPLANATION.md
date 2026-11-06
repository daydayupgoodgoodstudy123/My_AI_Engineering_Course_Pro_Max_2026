# 参考解释：Kill Switches, Circuit Breakers, and Canary Tokens

## 核心：灰度发布判定

没有样本是证据不足；错误率或尾延迟任一超限就不晋级。

准确合同：Each sample has ok exact bool and latency>=0. Empty samples returns 'insufficient'. Validate thresholds 0<=max_error_rate<=1,max_p95>=0 and samples; invalid input raises ValueError. Compute nearest-rank p95. Return 'rollback' if error rate>threshold or p95>threshold; otherwise 'promote'. These are local decisions, no deployment.

## 加分：证据分层 Gate

只接受精确 True 证据；缺失和 truthy 字符串都不代表检查通过。

准确合同：For each sorted unique required name, accept only evidence[name] is exactly True. Return {'ready':bool,'failed':sorted names}. Missing, false, None and truthy non-bool values all fail. Unrequired evidence does not affect readiness. No deployment is performed.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
