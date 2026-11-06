# 参考解释：Object Detection — YOLO from Scratch

## 核心：边框 IoU

先算交集，再用两框面积减交集得到并集；相接边界不产生交集面积。

准确合同：Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection.

## 加分：非极大值抑制

按稳定顺序选择保留框，再抑制与已保留框过度重叠的候选。

准确合同：Return kept original box indices, selecting descending score with original-index ties. Suppress candidates with IoU strictly >threshold against a kept box. Boxes are valid positive-area xyxy; reject unequal lengths or threshold outside [0,1]. Empty inputs return [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
