# 参考解释：Production Quantization — AWQ, GPTQ, GGUF K-quants, FP8, MXFP4/NVFP4

## 核心：对称整数化

由最大绝对值确定对称 scale，使用明确的舍入规则；全零时避免除零。

准确合同：bits must be exact int 2..8. Set bound=2**(bits-1)-1, scale=max(abs(values))/bound (or 1 for empty/all-zero input). Return {'values':[rounded x/scale clipped to -bound..bound], 'scale':scale}. Python round (ties to even) defines rounding.

## 加分：回归误差与形状

逐项误差平方后平均；分母是样本数，空输入不能默认为零误差。

准确合同：Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
