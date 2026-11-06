# 参考解释：Structured Outputs: JSON, Schema Validation, Constrained Decoding

## 核心：配置合同校验

必填缺失和未知字段独立收集；字段存在但值为 None 不在这个浅层合同的检查范围。

准确合同：required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid.

## 加分：工具参数校验

schema 控制精确 key 集合和类型；不要做隐式字符串或 bool 转换。

准确合同：schema maps required field name -> one of string,integer,boolean. arguments must be a dict with exactly these keys, with str/exact int/exact bool respectively. Return True when valid, False otherwise. Unknown schema type is invalid. No coercion.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
