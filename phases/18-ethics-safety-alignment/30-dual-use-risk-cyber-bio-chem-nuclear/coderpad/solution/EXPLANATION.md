# 参考解释：Dual-Use Risk — Cyber, Bio, Chem, Nuclear Uplift

## 核心：风险登记与排序

分值量表属于本题，乘积相同时用严重性和 id 确定顺序。

准确合同：Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria.

## 加分：独立权限与批准

批准不能绕过独立 capability 授权；allow 也不代表已经执行或被 OS 隔离。

准确合同：If capability is absent from granted return 'deny' even if approved. Otherwise side_effect=True and approved=False returns 'ask'; otherwise 'allow'. side_effect and approved must be exact bool, else ValueError. No action executes.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
