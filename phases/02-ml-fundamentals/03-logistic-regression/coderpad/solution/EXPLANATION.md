# 参考解释：Logistic Regression

## 核心：稳定 Sigmoid

按正负分支计算，避免对很大的正数调用 exp。

准确合同：Return logistic sigmoid for a finite scalar, avoiding overflow for large positive or negative magnitudes.

## 加分：分类交叉熵

目标是索引而非 one-hot，取对应概率的负对数；对零概率采用题目规定的下限。

准确合同：Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
