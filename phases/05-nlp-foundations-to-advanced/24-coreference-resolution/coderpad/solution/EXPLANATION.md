# 参考解释：Coreference Resolution

## 核心：BIO 标签到实体片段

维护活动实体类型和起点；遇到不匹配的 I 标签按合同开启新实体。

准确合同：Labels are O, B-TYPE or I-TYPE with nonempty TYPE. Return {'type','start','end'} spans with half-open indices. I-TYPE without matching active type is treated as B-TYPE. Invalid label syntax raises ValueError. Consecutive B labels always start new entities.

## 加分：对话槽位更新

先复制旧状态，再逐项替换或删除；None 代表删除而非一个已填槽值。

准确合同：state and changes are dicts with only cuisine, area, people. Unknown keys in either raise ValueError. Changes with None delete a slot; other values replace it. Return a new merged dict without mutating either input. Value typing is upstream.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
