# 参考解释：Emu3: Next-Token Prediction for Image and Video Generation

## 核心：因果与窗口 Attention Mask

同时满足因果条件和可选局部窗口；不要把未来 token 放进可见区。

准确合同：Return length x length booleans where row i may attend column j iff j<=i and, if window provided, i-j<window. length exact int >=0; window None or exact positive int. Invalid configuration raises ValueError.

## 加分：向量量化最近码字

对每个向量遍历全部码字，按平方距离比较；并列选较低索引。

准确合同：Codebook must be a nonempty set of same-dimensional numeric rows. All vectors must have that dimension. Return nearest codeword index per vector by squared Euclidean distance, ties to lower index. Invalid dimensions or empty codebook raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
