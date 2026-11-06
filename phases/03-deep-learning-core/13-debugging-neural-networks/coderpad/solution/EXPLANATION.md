# 参考解释：Debugging Neural Networks

## 核心：梯度范数裁剪

所有梯度共享一个缩放系数，保留方向；不能逐元素独立裁剪代替范数裁剪。

准确合同：Return gradients scaled together so L2 norm is at most maximum; leave already-small vectors unchanged in value. maximum>=0, otherwise ValueError. Zero and empty vectors are valid.

## 加分：阈值异常检测

先算总体标准差；常量序列不存在可计算的非零 z-score。注意阈值是严格大于。

准确合同：Use population mean/variance from values; flag abs(z)>threshold (strict). Constant or empty lists yield all False/empty. Negative threshold raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
