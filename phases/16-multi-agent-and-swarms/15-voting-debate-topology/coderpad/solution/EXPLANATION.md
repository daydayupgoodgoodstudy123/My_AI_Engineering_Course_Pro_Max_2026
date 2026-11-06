# 参考解释：Voting, Self-Consistency, and Debate Topology

## 核心：集成投票与并列

每个样本列独立投票，确定并列规则，避免模型排列影响结果。

准确合同：Input is model-by-example label matrix of strings. Return one majority label per example; ties choose lexicographically smallest label. Empty model list returns []; ragged rows raise ValueError.

## 加分：Quorum 与重复选票

每个成员只贡献一票，重复不能增加 quorum；矛盾票必须拒绝。

准确合同：votes is [[member,value],...]; members is a unique member-id list. Ignore exact repeated votes; conflicting votes from one member or a nonmember raise ValueError. required exact int >len(members)/2 and <=len(members). Return the value with at least required distinct voters, else None. Values are strings.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
