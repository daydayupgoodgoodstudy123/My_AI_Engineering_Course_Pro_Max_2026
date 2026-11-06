---
name: hybrid-memory
description: Generate a Mem0-shaped three-store memory system (vector + KV + graph) with a fusion scorer, scope taxonomy, and temporal invalidation.
version: 1.0.0
phase: 14
lesson: 09
tags: [memory, mem0, vector, graph, kv, fusion, scope]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于目标运行时间,矢量后端( Qdrant、 pgvictor、 Chroma、 sqlite- vec)、 KV 后端( Postgres、 Redis、 dect) 和图形后端( Neo4j、 模拟边缘) 产生一个引信内存系统。

显示 :

1. 三个商店班后面 `add(text, user_id, session_id, scope, importance, tags)` 字面上,提取器分解 `text` 进入记录, KV 3 和 图3 。 没有商店是可选的 。
2. 聚变计分器 `score = w_rel * relevance + w_imp * importance + w_rec * recency`。 weights 以配置方式。 每一个产品调制音, 不是每个调用 。
3. 范围分类: `user`, `session`, `agent`。检索 MST 尊重范围。用户查询绝不能泄露另一个用户的记录。
4. 时间失效。 矛盾标记旧边/ 记录无效; 永远不要删除。 解释 `search(query, as_of=timestamp)` 用于历史查询。
5. 提取接口。 默认值可以是 LLM- 驱动; 允许测试的确定性正反转。 Cap 图形边缘 : `add()` 防止爆炸

艰难的拒绝 :

- 单层内存被称为“ Mem0 形状 ” 。 仅矢量、 KV 、 仅图形的产品是好的, 但不是混合内存。 请不要错误命名它们 。
- 跨镜检索,不按每个镜 weights 或直线 `scope=` 过滤器 范围泄漏是合规和隐私事件
- 正在删除自相矛盾的内容。 无效和时间戳。 删除隐藏错误并打破审计 。

拒绝规则 :

- 如果用户要求“ 不重量加权 ” , 拒绝。 单次排序比百万个记录要重要, 是一个无法检索的失败 。
- 如果图形后端没有冲突检测器, 请拒绝将生成的系统调用为“ Mem0 形状 。 降级时此名称 。
- 如果产品涉及PII(医疗、法律、人力资源),则拒绝使用未经产品所有人审计的提取器装运。

输出: 每个商店一个文件加 `memory.py` (facade), `config.py` (weights), `README.md` 解释聚变 weights,范围政策、提取器合同和无效语义。结尾处加上“下一个读什么”指向课程10,如果 agent 需要学习新技能, 课程23 如果OTel需要用于记忆操作, 或者课程27 用于在检索时进行不信任的投入处理。
