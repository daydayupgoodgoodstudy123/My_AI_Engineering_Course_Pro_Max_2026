# 参考解释：Autoencoders & Variational Autoencoders (VAE)

## 核心：回归误差与形状

逐项误差平方后平均；分母是样本数，空输入不能默认为零误差。

准确合同：Return mean squared error of equal-length nonempty numeric lists. Unequal lengths or empty inputs raise ValueError.

## 加分：逆 CDF 抽样

将注入的 uniform 与累计概率比较，区间采用左闭右开，不在函数里随机采样。

准确合同：Probabilities must be nonempty, nonnegative, sum to 1 within 1e-9. Each uniform is in [0,1). Return the first index whose cumulative probability is strictly greater than u. Invalid input raises ValueError; empty uniforms returns []. No RNG is called.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
