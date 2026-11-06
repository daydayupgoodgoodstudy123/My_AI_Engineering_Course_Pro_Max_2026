# 参考解释：Conditional GANs & Pix2Pix

## 核心：二维仿射变换

矩阵负责线性变换，offset 负责平移；每个点使用相同参数。

准确合同：Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns [].

## 加分：回归误差与形状

逐项误差平方后平均；分母是样本数，空输入不能默认为零误差。

准确合同：Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
