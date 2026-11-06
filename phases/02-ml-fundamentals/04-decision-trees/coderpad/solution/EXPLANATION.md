# 参考解释：Decision Trees and Random Forests

## 核心：决策树分裂纯度

统计类别频率，再计算一减概率平方和。纯类别集合的 impurity 是零。

准确合同：Return 1-sum(class_fraction^2) for hashable labels. Empty labels returns 0. Labels may be strings or integers.

## 加分：概率分布熵

只对正概率项取对数；先检查分布归一化，再计算 bit 单位的熵。

准确合同：Return Shannon entropy in bits. Require a nonempty list of numeric probabilities in [0,1] summing to 1 within 1e-9, else ValueError. Define 0*log2(0)=0.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
