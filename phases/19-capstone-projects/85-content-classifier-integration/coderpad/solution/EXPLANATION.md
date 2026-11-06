# 参考解释：Capstone 85 — Content Classifier Integration

## 核心：分类信号合并

同类信号取最严重值，跨类再判断阻断阈值；没有信号时不凭空生成命中。

准确合同：Each signal has category(str), severity exact int 0..3. block_at exact int 0..3. Keep max severity per category, return {'categories':sorted category->max mapping,'blocked':any severity>=block_at}. Empty signals never block. Invalid severity/threshold raises ValueError. No model classifier is called.

## 加分：风险登记与排序

分值量表属于本题，乘积相同时用严重性和 id 确定顺序。

准确合同：Each risk has unique id string, severity and likelihood exact integers 1..5. Return ids ordered descending severity*likelihood, descending severity, ascending id. Invalid scores or duplicate ids raises ValueError. These are exercise scales, not regulatory criteria.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
