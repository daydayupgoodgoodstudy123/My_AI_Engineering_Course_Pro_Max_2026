# SplitCase 面试官手册（16/01）

计时期间不给候选人看。开场2分钟，五关12/11/15/10/10，共60；没有真人校准。允许澄清、查标准库、边做边解释；卡住约5分钟一次只给一级提示。

## 澄清合同

|关|问题|英文回答|
|---|---|---|
|1|这里是模型token吗？|"No. Input is floor of the combined Python character length divided by four; output and tool calls are fixture facts."|
|2|unknown usage就是0吗？|"No. Persist the declared None or integer exactly; the restoration codec is supplied."|
|3|要选最优agent数量吗？|"No. Evaluate the two supplied designs only; input plus output forms one call's context extent."|
|3|fact缺失怎么定义？|"Only declared required ids absent from that boundary's forwarded set. No text-based fact extraction is requested."|
|4|要写CSV和async吗？|"No. Encode the current stage's domain row; quoting, incremental publication and closure are supplied."|
|5|相同role跨branch共享private吗？|"No. Private notes reach only descendants of their own scope, then the recipient role filter applies."|

## Part 1 输入与用量

四层：recipient误用sender，required fact丢失，经ReplayService.preview到正确required_fact_value读值时自然KeyError；所有role私有note混进当前输入；fanout用量循环覆盖旧分支；独立call计长度时临时拼接完整system/user。第一层producer外有真实消费者，不能吞错或伪造fact。保留task、addressed summary、own note、每branch与完整request/output。

性能是独立call边界的完整本地record请求，不是历史增量token缓存。32M+32M字符压力fixture预先装载，完整request/output/usage断言在计时范围内。完整连续3slow3fast实测：slow0.013454/0.016685/0.011765秒，fast0.000013084/0.000015541/0.000021833秒，limit0.0005秒，两侧余量23.53×/22.90×；六个完整副本各全五关通过，最长wall0.586秒。首组未满足慢侧8×的数据完整保留在题包外维护证据。H1 "Which recipient was this message intended for?" H2 "Whose note entered this view?" H3 指向projection、branch totals与独立call长度合同。

## Part 2 完整JSON快照

主要看完整design、reported usage与独立task/cost metadata；整数id/微秒/计数不经float，大于2^53仍int；role/message/private顺序与原CRLF/Unicode原样。重复recipient和相同timestamp不合并消息，正文首尾空白与空字符串仍是原值。有限float metadata保留binary64值。正确typed restore codec给定，candidate写完整payload和I/O；不把模型编译成报告再存。None/0与空值是整合护栏，无需另写default算法。无crash-atomic承诺。H1 "Which fields define this saved design?" H2 "Which values changed representation?" H3 指向完整JSON值与重开。

## Part 3 固定设计比较

role context用各自最大完整call，不能把终身总usage当peak；required loss按每个summary boundary单独报告，不把所有optional omissions当损失；multi不能靠低tokens掩盖required loss或自身超限。single失去可行性时可比较更贵但满足声明约束的multi，两个都可行时没有token收益就保留single。报告仍保留正负delta与损失证据。先前P1真实调用投影/usage和P2恢复是依赖，不是已给完整P3。H1 "What stayed live in one call?" H2 "Which fact was required at this boundary?" H3 指向peak、conservation、两固定设计取舍；不声称真实质量收益。

## Part 4 阶段CSV数据

当前stage保留原run/index/role，不按role合并；input/output字段不互换，未知为空但0保留；partial failure仍是一行，status来自完成记录；lost_fact_ids只包含该stage required omissions，不用run级总损失或所有省略facts。correct CSV adapter与全部async driver给定，header/发布/关闭断言是整合护栏，candidate职责是阶段字段编码。H1 "Which completed stage owns these fields?" H2 "Was this fact required?" H3 指向同步row。不是provider tokenstream。

## Part 5 嵌套scope

每条路径独立继承shared与private notes，不把左branch的局部状态污染右branch；同role出现在另一branch也不继承前者private；full path与child顺序保留，同名局部leaf不能按key全局合并；leaf通过修好的P1 role投影得到facts，再报告required missing。合法空scope没有leaf，不产生伪报告行。有限树/unknown recipient校验已给定。H1 "Which ancestors own this note?" H2 "Are these two same-role leaves in the same scope?" H3 指向分支局部递归状态。没有编造执行DAG或LLM记忆机制。

## 记录

五关各8分推进、调试20、代码15、沟通15、工程判断10，仅是原创练习评分。记录具体证据与提示；未观察写未观察，不以本地fixture推断生产multi-agent收益。
