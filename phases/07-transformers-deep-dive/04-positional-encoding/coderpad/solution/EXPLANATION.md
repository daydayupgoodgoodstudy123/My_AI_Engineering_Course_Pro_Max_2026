# 参考解释：Positional Encoding — Sinusoidal, RoPE, ALiBi

## 核心：Sinusoidal 位置编码

成对输出同频率 sin/cos，指数中的维度分母必须与合同一致。

准确合同：dimensions is exact positive even int and position is numeric >=0. Return sin(position/10000**(2*i/dimensions)) then cos of the same angle for i=0..dimensions/2-1, interleaved. Invalid configuration raises ValueError.

## 加分：二维仿射变换

矩阵负责线性变换，offset 负责平移；每个点使用相同参数。

准确合同：Apply 2x2 matrix and 2D offset to each 2D point. Return a new list of transformed points. Invalid matrix, offset, or point shapes raise ValueError. Empty points returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
