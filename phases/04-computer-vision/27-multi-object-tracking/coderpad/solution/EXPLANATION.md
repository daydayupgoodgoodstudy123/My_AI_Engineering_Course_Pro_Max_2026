# 参考解释：Multi-Object Tracking & Video Memory

## 核心：边框 IoU

先算交集，再用两框面积减交集得到并集；相接边界不产生交集面积。

准确合同：Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection.

## 加分：合法状态转换

允许边应显式列出，终态不再接受新转换，包括重放到同一状态。

准确合同：Allowed edges: queued->running/canceled; running->waiting/completed/failed/canceled; waiting->running/canceled. Return target if allowed, otherwise ValueError. Terminal states cannot transition, including to themselves.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
