# 面试官手册：LocalToolBench（11/09）

计时期间不展示。开场 2 分钟，五关 12、12、12、10、12 分钟，合计 60；未经真人校准。允许澄清、查文档、边做边解释；卡住约 5 分钟后一次只给一级提示。

## 澄清问题标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | traceback 是 formatter 错吗？ | "The formatter consumes the declared weather result. Check which registered producer returned that object." |
| 1 | comparison 有副作用吗？ | "No. They are valid, pure, total comparisons; full bound metadata is checked before any row execution." |
| 1 | file size 要修吗？ | "The correct UTF8 in-memory file helper and registry index are supplied." |
| 2 | append 立刻落盘吗？ | "Append stages an owned snapshot; the supplied flush writer persists pending snapshots in order." |
| 2 | failures/list order？ | "Keep every invocation, including structured failures; list order is meaningful." |
| 3 | catalog 就是 allowlist 吗？ | "No. A table must be both present and explicitly allowed." |
| 3 | empty projection？ | "Missing means the full schema; an explicit empty list returns empty objects. Duplicate fields are rejected." |
| 3 | later invalid/empty table？ | "The complete query must be rejected before scanning, even if an earlier condition is false or the table is empty." |
| 4 | probe 编号重排吗？ | "Emit completion order but retain each original declared probe number." |
| 4 | result=0？ | "It is a successful result. Only the supplied structured error policy marks a failure." |
| 5 | submitted code 会运行吗？ | "Never. Parse and inspect only, retaining all structural violations and native AST positions." |

## Part 1 dispatcher 与 bound kernel（12 分钟）

坑：
- loop 中 lambda 捕获最后 handler，weather call 得到 search-shaped row；正确 weather formatter 在生产者外一两次调用报 KeyError。不能删 formatter 或把错误数据硬补成天气。
- Fahrenheit 转换写回共享 Celsius row，后续调用看到被污染的 source。源 Python 的 copy 是该合同直接锚点。
- `all` 之前先构造全部 comparison results，失去合法纯 AND 的短路。完整 query/bound metadata 校验仍必须先做，不能因 first false 吞掉后续非法条件。

正确 registry index、工具参数边界、UTF8 file size、strict typed table/comparator 和 complete bound-plan validation 给定。P1 不给完整 P3 compiler。实际压力 fixture 是 6000 行、1024 个不同真实字段，不是复制同一个 predicate；table 构造两侧同样在计时外，完整 bound validation/row scan/projection 在内。完整连续三慢 0.360336/0.331224/0.343636 秒，三快 0.001683/0.001640/0.001587 秒，限值 0.035 秒，双侧余量 9.46/20.80 倍，最慢 0.361 秒。完整证据 `/tmp/exam-11-16-work/draft11-09/timing-group2`；更早未达标校准组也保留于包外。

H1 "Which callable produced this row?" H2 "Who still owns the Celsius fixture?" H3 指向注册绑定、source copy 和纯合取执行。追问：为什么 validation 不能同样短路？（条件非法是整条请求错误，和合法条件结果 false 不同。）

## Part 2 invocation audit（12 分钟）

坑：
- append 需要 owned snapshot；调用者之后修改 nested arguments/result 不能改写待 flush 历史。
- 参数列表保留顺序，不能排序、set 化或按“相同参数”去重调用；相同 tool/arguments 的两次真实调用仍分别记录。
- 失败也是真实 invocation，保留结构化结果、原 ordinal 与 append 顺序。

LF codec/flush writer 正确 GIVEN，精确 integer microseconds 与 Unicode 是 integration guards；不再考通用 flush/line splitting。H1 "What can the caller still mutate before flush?" H2 "Is a failed invocation absent or recorded?" H3 指向 snapshot 与每次 invocation。追问：是否保证事务与崩溃恢复？（不保证，只是声明的本地追加格式。）

## Part 3 typed query compiler（12 分钟）

坑：
- catalog presence 不等于 table authorization，unknown/denied 不回退第一张表。
- 使用当前 table schema 绑定 field/literal/operator，另一张 allowed table 可以有不同字段布局；不能按 literal 自己猜类型、做 string→number coercion 或把 > 改成 >=。
- 完整 projection 的字段和顺序要保留，未知字段/重复字段/非法 later condition 都在扫描前拒绝；空表也校验。

primitive type/operator compatibility、shape helpers 与 P1 bound executor 已正确，不重写其 short-circuit。H1 "Which table schema owns this field?" H2 "When is the complete plan valid?" H3 指向 allowlist、实际 field type/operator 与 projection。追问：原文已有 projection 吗？（没有，是本题明示的有限教学扩展；原 Exercise1 已要求受限表查询。）

## Part 4 completed probe TAP（10 分钟）

坑：
- completion order 不能变成 probe 原编号；先声明完整 plan，再按完成结果输出。
- structured error 和 raised tool failure 都是 failed probe；0 这类 falsey success 和 `error=False` 的结构化结果仍 ok。
- 完成的 probe 在 earlier declared probe 仍 pending 时就可观察，不先收齐所有结果。

原 label 的大小写保留。正确 async driver/绑定/cancellation/TAP finite-subset formatter GIVEN。Event/timeout 只是判断被阻塞的增量边界，不是 P1 性能基准。H1 "Which declared probe finished?" H2 "What makes this outcome fail?" H3 指向 original number/outcome/current completion。追问：source 有 TAP token 协议吗？（没有；这是本地工具探测报告扩展，不声称完整 TAP 或 provider 协议实现。）

## Part 5 AST inspection（12 分钟）

坑：
- 函数、分支里的 Import/unsafeName 一样检查，不能只扫顶层。
- 外层 dunder Attribute 被报告后仍遍历内部链，保留每个 violation 的 typed path/位置与 preorder。
- 字符串/comments 不是语法节点；source 的 unsafe Name 检查包括 Store context，非双端双下划线的属性不扩大禁止。

字典的 keys 与 values 在 AST 中的字段遍历可以和源码位置顺序交错，仍按 `ast.iter_fields` preorder 报告。native byte column 仅作 metadata integration guard。

H1 "Is this text or a syntax node?" H2 "Which inner node remains after this outer violation?" H3 指向递归 ast.iter_fields 与全部 issues。追问：能否据此声称沙箱安全？（不能，本题甚至不执行代码；只检查声明的静态策略。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，原测试通过即得 |
| 调试方法 | 20 | 从 consumer 找 producer，数据验证假设与逐层推进 |
| 代码质量 | 15 | 必要 work、结果、精度与顺序保留，无死代码 |
| 沟通 | 15 | 主动澄清信任边界、验证阶段、projection 与 probe 语义 |
| 工程判断 | 10 | 说明 pure predicate/TAP subset/静态 AST 的范围 |

未观察到的写“未观察”。提示、变绿时间与原 60 分钟成绩分开记录。
