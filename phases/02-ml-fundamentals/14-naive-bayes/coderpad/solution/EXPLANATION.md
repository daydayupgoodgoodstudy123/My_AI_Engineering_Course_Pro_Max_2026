# 参考解释：Naive Bayes

## 核心：词袋向量

按外部 vocabulary 的顺序输出，未知词不扩展向量长度。

准确合同：Return counts aligned to an ordered vocabulary of unique strings; ignore unknown tokens. Duplicate vocabulary entries raise ValueError. Empty vocabulary returns []. No normalization.

## 加分：贝叶斯更新

先算证据的边缘概率作分母。零分母表示当前模型认为该证据不可能。

准确合同：For three probabilities in [0,1], return P(H|E)=prior*likelihood_positive/(prior*likelihood_positive+(1-prior)*likelihood_negative). Out-of-range values or zero evidence probability raise ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
