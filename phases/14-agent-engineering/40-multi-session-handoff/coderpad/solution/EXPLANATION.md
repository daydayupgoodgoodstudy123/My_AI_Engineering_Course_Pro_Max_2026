# 参考解释：Multi-Session Handoff

## 核心：可验证任务交接

交接应包含目标、当前状态、下一动作与可验证检查；非空字段检查不证明内容真实。

准确合同：Required nonempty string fields: objective, state, next_action. checks must be a nonempty list of nonempty strings. Return sorted missing/invalid field names (among those four). Extra fields allowed; whitespace-only strings are invalid. Do not execute next_action.

## 加分：有界记忆保留

先按 id 合并最新记录，再按时间预算保留；同时间取后出现的更新。

准确合同：Records have id, timestamp, text. Keep the most recent record per id (later input wins timestamp ties), then retain limit records by descending timestamp and lexicographic id ties. Return copied records. limit exact nonnegative int; invalid limit raises ValueError.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
