# LocalToolBench 参考讲解

## Part 1

注册时绑定当前 callable，不能让所有 lambda 最后读同一个 loop cell。weather 拷贝当前 source row 再转换，正确 formatter 不替错 producer 猜字段。合法纯 comparison 用短路 AND；完整 bound metadata 校验已经在 row scan 前给定，不能为了快省去。source registry/file helper 正确给定，不作为新缺陷。

完整连续三慢 0.360336/0.331224/0.343636 秒、三快 0.001683/0.001640/0.001587 秒，限值 0.035 秒，余量 9.46/20.80 倍，全部真实字段/rows/output 保留。SCOPE 提供完整外部 evidence 路径，未达标的更早校准组也保留。6000×1024 宽表只放大真实不同字段 comparison 工作，完整 bound validation/输出都在 timer；表创建与类型验证在两侧相同的 setup，不把必要请求工作移出。

## Part 2

append 将 Invocation 转成深度拥有的 JSON-compatible snapshot，flush GIVEN 逐条追加，再清 pending。replay 还原每条 Invocation，不按 ordinal 或参数排序/去重；相同 tool/arguments 的两次调用也各是一条独立记录。ordered lists、false、错误结果、integer microseconds 都保留。正确 byte-LF codec 不把字符串内 U+2028/NEL 当记录边界。本地 journal 没有事务/崩溃恢复承诺。

## Part 3

先做 shape，再同时检查 catalog 与 allowlist。每个 condition 用 selected table 的实际 field index/schema type 绑定给定 operator/literal primitive；另一 allowed table 的字段顺序可以不同，不能借用 catalog 邻表布局。所有条件完成才生成 plan。projection 缺省选完整 schema，显式 [] 保留为空，unknown/duplicate 拒绝，顺序按请求。再调用 P1 已修 executor；新核心是 compile/bind/policy，不重新考 all 的执行。

## Part 4

正确 driver 返回 (original Probe,result)，包括 caught tool exceptions。先给 header/plan，再逐完成结果投影原 number/label 和 failure policy，交给 GIVEN TAP subset formatter；0 和 `error=False` 的结构化结果都是正常 success，不按字典 truthiness 或 error 键存在与否猜错误；原 label 的大小写也保留。不先收齐 pending futures。close wrapper/driver 取消和 await 未完成任务。source 原来是顺序 demo，TAP 是本地报告工程扩展。

## Part 5

按 ast.iter_fields 递归 AST/list，路径追加字段名和 list index，preorder 报 Import/ImportFrom、exact dunder Attribute、unsafe Name 所有 context。报告外层后仍进内层，strings/comments 本来没有对应禁止节点。字典的 keys/values 字段 preorder 可以和源码位置顺序不同，不能改按位置排序。保留原 native AST line/column，非 ASCII 前缀后的 byte column 仅是 metadata integration guard，SyntaxError 保持解析错误；提交代码从不 exec/eval。

## 这套题证明了什么，没证明什么

它检查本地工具产物、审计快照、有限 typed query、异步完成报告和静态树策略。没有真实模型、联网工具、数据库 SQL、代码执行隔离、安全证明、provider/TAP 完整协议或真人面试校准证据。
