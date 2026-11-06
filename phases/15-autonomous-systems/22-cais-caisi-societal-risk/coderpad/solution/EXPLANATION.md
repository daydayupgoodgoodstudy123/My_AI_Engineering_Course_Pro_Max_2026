# 参考解释：CAIS, CAISI, and Societal-Scale Risk

## 核心：风险登记与排序

分值量表属于本题，乘积相同时用严重性和 id 确定顺序。

准确合同：Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria.

## 加分：分组选择率差异

先保留每组分母，再比较选择率；单个 gap 不能替代完整公平性分析。

准确合同：Equal-length nonempty lists; groups are strings and selected exact booleans. Return {'rates':group->selected_count/group_count,'gap':max(rate)-min(rate)}. Invalid length/labels raises ValueError. This is descriptive demographic-parity evidence, not a complete fairness judgment.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
