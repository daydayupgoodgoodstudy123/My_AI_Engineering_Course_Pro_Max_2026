# 参考解释：Cross-Attention Fusion

## 核心：单头注意力

点积按维度平方根缩放，再做稳定 softmax，最后对 value 加权。

准确合同：query is nonempty length d; keys is nonempty NxD and values is NxV with nonempty equal row widths. Compute softmax(query dot key / sqrt(d)) then the weighted sum of value rows. Invalid shapes raise ValueError; implement with Python lists.

## 加分：因果与窗口 Attention Mask

同时满足因果条件和可选局部窗口；不要把未来 token 放进可见区。

准确合同：Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
