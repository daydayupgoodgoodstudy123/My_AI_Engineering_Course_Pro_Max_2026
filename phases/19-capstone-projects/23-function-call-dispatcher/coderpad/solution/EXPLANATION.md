# 参考解释：Function Call Dispatcher

## 核心：角色与工具选择

权限过滤先于关键词评分；最高分并列时弃权，不能靠输入排列决定。

准确合同：Each route has name(str), roles(list), keywords(list). Among role-eligible routes, score set intersection with query_tokens. Return unique highest positive-scoring name. No positive match or a tie returns None. Duplicate route names raise ValueError; input order must not resolve a tie.

## 加分：工具参数校验

schema 控制精确 key 集合和类型；不要做隐式字符串或 bool 转换。

准确合同：schema maps required field name -> one of string,integer,boolean. arguments must be a dict with exactly these keys, with str/exact int/exact bool respectively. Return True when valid, False otherwise. Unknown schema type is invalid. No coercion.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
