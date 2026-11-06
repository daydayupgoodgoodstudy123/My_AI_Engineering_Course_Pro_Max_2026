# 参考解释：Instance Segmentation — Mask R-CNN

## 核心：图像 Patch 切分

先确定 patch 起始位置，再按 patch 内行列展开，不混淆两种遍历顺序。

准确合同：image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError.

## 加分：边框 IoU

先算交集，再用两框面积减交集得到并集；相接边界不产生交集面积。

准确合同：Boxes are [x1,y1,x2,y2], with x2>=x1 and y2>=y1; reject other shapes/reversed bounds with ValueError. Return intersection area / union area, or 0 if union is zero. Touching edges have zero intersection.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
