# 参考解释：Long-Running Background Agents: Durable Execution

## 核心：幂等请求账本

id 绑定 canonical JSON 的 payload；精确重放和冲突复用是两种情况。

准确合同：Requests have id and payload (JSON values). First use of id is executed and recorded; exact canonical-JSON payload replay is not executed again. Conflicting reuse raises ValueError. Return {'executed':[first-use ids], 'replayed':[duplicate ids in encounter order]}. Do not treat bool and int payloads as equal.

## 加分：可验证任务交接

交接应包含目标、当前状态、下一动作与可验证检查；非空字段检查不证明内容真实。

准确合同：Required nonempty string fields: objective, state, next_action. checks must be a nonempty list of nonempty strings. Return sorted missing/invalid field names (among those four). Extra fields allowed; whitespace-only strings are invalid. Do not execute next_action.

## 复盘

将每个失败映射到合同与 fixtures 的具体 case，区分公式、索引、类型、边界和状态问题。
比较 [main.py](main.py) 后关掉答案，自己重写失败部分，再补一个原测试没有直接覆盖的反例。
说明核心的时间、空间复杂度；数据扩大后会先遇到什么限制？
本套只证明这些纯函数符合限定合同。参考实现不是完整模型、协议、权限系统或生产服务。
