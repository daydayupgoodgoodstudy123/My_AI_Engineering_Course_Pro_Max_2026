# 参考解释：Stochastic Processes

## 核心：马尔可夫状态分布

验证分布和转移矩阵每行归一化，再按行向量乘矩阵更新分布。

准确合同：Distribution is a nonempty probability row vector; transition is an NxN row-stochastic matrix. Reject wrong shapes, negatives or row/distribution sums outside 1e-9 with ValueError. Return distribution @ transition.

## 加分：折扣回报

从末尾向前累加未来回报，时间复杂度线性。

准确合同：Return G[t]=rewards[t]+gamma*G[t+1], final continuation 0. gamma must be in [0,1], otherwise ValueError. Empty rewards returns [].

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
