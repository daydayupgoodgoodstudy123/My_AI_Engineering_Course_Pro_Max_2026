# 参考解释：InternVL3: Native Multimodal Pretraining

## 核心：图像 Patch 切分

先确定 patch 起始位置，再按 patch 内行列展开，不混淆两种遍历顺序。

准确合同：image is a nonempty rectangular 2D scalar matrix; both dimensions must be divisible by exact positive int patch_size. Return flattened patches in row-major patch order, pixels within each patch row-major. Invalid shape or size raises ValueError.

## 加分：模型参数与内存估算

每个参数张量的维度相乘，再乘每元素字节数；标量张量有一个元素。

准确合同：Each shape is a list of exact positive integer dimensions; [] represents one scalar. bytes_per_parameter exact positive int. Return total elements times bytes per parameter. Empty shapes list yields 0. Invalid dimensions/byte width raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
