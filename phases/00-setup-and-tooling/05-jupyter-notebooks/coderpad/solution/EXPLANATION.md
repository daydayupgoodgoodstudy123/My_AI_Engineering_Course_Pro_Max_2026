# 参考解释：Jupyter Notebooks

## 核心：耗时聚合

以事件名聚合每段 duration，重叠 span 相加不能解释为请求 wall-clock 时间。

准确合同：Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency.

## 加分：均值与总体方差

先求均值，再以总体样本数计算方差；不要无意换成样本方差。

准确合同：Return {'mean':arithmetic mean,'variance':population variance,'min':minimum,'max':maximum} for a nonempty numeric list. Empty input raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
