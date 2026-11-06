# 参考解释：Capstone 12 — Video Understanding Pipeline (Scene, QA, Search)

## 核心：视频均匀采样

覆盖首尾时间点，单帧采样单独处理，避免除以 count-1 为零。

准确合同：Require exact nonnegative integers length/count and count<=length. Return count indices spanning 0..length-1 using floor(i*(length-1)/(count-1)). count=0 -> []; count=1 -> [0]. Invalid input raises ValueError.

## 加分：上下文预算装箱

先按相关性排序，再按剩余预算装入；超大项跳过，不阻断后续小项。

准确合同：items contain id(str), tokens(exact nonnegative int), score(number). Sort descending score with lexicographic id ties, then greedily accept each item that fits remaining exact nonnegative integer budget; skip oversize items and continue. Return selected ids in that order. Invalid costs/budget raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
