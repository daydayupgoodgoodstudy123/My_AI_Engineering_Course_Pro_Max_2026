# 参考解释：Inpainting, Outpainting & Image Editing

## 核心：掩码游程编码

只合并连续相同值；不应把隔开的相同值合成一个 run。

准确合同：Return consecutive [value,count] runs for a list of exact booleans. Empty list returns []; reject non-bool elements with ValueError. Preserve runs and original order.

## 加分：前向加噪

clean 与 noise 的系数分别是累计 alpha 和其补数的平方根。

准确合同：For equal-length vectors and alpha_bar in [0,1], return sqrt(alpha_bar)*clean + sqrt(1-alpha_bar)*noise. Invalid coefficient or unequal lengths raises ValueError. Empty vectors are valid; noise is injected, no RNG.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
