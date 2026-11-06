# 参考解释：Instruction Tuning (SFT)

## 核心：受限解码分布

只在合法 token 的 logits 上计算归一化，非法位置概率保持零。

准确合同：allowed is a list of unique valid indices; return softmax over allowed logits with 0 at every disallowed index. Preserve original output length. Empty allowed, duplicate/out-of-range/non-int index, or empty logits raises ValueError. Use stable exponentiation.

## 加分：分类交叉熵

目标是索引而非 one-hot，取对应概率的负对数；对零概率采用题目规定的下限。

准确合同：Require nonempty nonnegative probabilities summing to 1 within 1e-9 and exact integer target index in range. Return -log(probabilities[target]); use clamp minimum 1e-12. Invalid input raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
