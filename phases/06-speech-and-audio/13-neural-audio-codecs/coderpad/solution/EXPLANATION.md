# 参考解释：Neural Audio Codecs — EnCodec, SNAC, Mimi, DAC and the Semantic-Acoustic Split

## 核心：向量量化最近码字

对每个向量遍历全部码字，按平方距离比较；并列选较低索引。

准确合同：Codebook must be a nonempty set of same-dimensional numeric rows. All vectors must have that dimension. Return nearest codeword index per vector by squared Euclidean distance, ties to lower index. Invalid dimensions or empty codebook raises ValueError.

## 加分：回归误差与形状

逐项误差平方后平均；分母是样本数，空输入不能默认为零误差。

准确合同：Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
