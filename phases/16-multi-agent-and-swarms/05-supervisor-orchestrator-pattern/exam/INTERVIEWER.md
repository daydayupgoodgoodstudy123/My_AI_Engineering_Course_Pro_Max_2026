# LeadSynth 面试官手册

## 开场与澄清

让候选区分原始工作上下文、窄summary、实际usage与声明cap；不要预告缺陷位置。每关卡住约5分钟一次只给一级提示，记录具体观察。

|Question|Standard answer|
|---|---|
|Are durations measured by running workers here?|No. They are finite sealed completion observations from an injected local replay.|
|Does timeout kill a Python thread?|No. The desk reports twice the prefix median including this completion; no threads run.|
|Do two workers mean two independent sources?|No. Only distinct original source ids support a value.|
|Can the lead choose the more popular conflicting value?|No. All contradictory exact values remain visible.|
|Do I implement Markdown or async cleanup?|No. Implement the domain projection callbacks; framing, publication and closure are supplied.|
|What does a node budget count?|All descendant task nodes of that node, not only depth or immediate children.|

## Part 1 修

三层：producer把working_context list放进summary string槽，正确format_subanswer在根因外调用strip自然AttributeError；cap用team平均数而不是此worker的声明上限；每封口一次重排全部时长前缀。原summary保留空白，展示才strip；cut仍保留原usage，不能把已观测tokens截到cap。median包含当前值、零和重复值，偶数取中间两值平均，不用last/mean/recentK替代。

提示一：What contract does the lead consume? 提示二：Whose cap owns this worker? 提示三：Which observations determine the current timeout diagnostic? 性能是完整CompletionDesk.record及所有输出guard，不只测裸median helper；完整连续3慢3快实测：slow2.937686/2.944109/2.912093秒，fast0.027849/0.027044/0.028101秒，limit0.27秒，双余量10.7855×/9.6082×；完整11500个sealed outcomes及每个artifact/display/cap/median/threshold/slow字段均在timer内核验。单slow最大2.9441秒，六个NEW完整副本各全5通过。P3冲突合并不在本关。

## Part 2 存

主要坑：同summary对象可属于不同question；manifest必须保留完整query assignment与顺序，不能按content合并；原summary不做展示归一化；usage整数不经float。给定内容SHA/UTF8/JSON和I/O，字节长度/符号零是集成护栏。提示：Is shared content also shared assignment identity? 追问：同一query重存替换当前快照，不追加旧assignment；修改一个query是否应重写另一份manifest？

## Part 3 算

主要坑：先按worker scope/cut隔离claim；按原sourceid合并，不把重复引用当多票；所有矛盾value保留，只有conflicting且自己预算>0才请求定向followup。来源union保留firstseen顺序，不能按字母重排；followup不能借用其他claim预算。P1提供窄artifact，P2提供重开记录，三个P3函数全部独立TODO。supported只是本地双source标签，不是真值或语义判断。提示：Which original source supports which exact value? 追问：预算耗尽是否允许隐藏冲突？

## Part 4 流

主要坑：缺答有missing类别和原error；成功/cut使用原summary，不用question或private context代替；lead保留supported/unverified/conflicting三部分，不选赢家。存在但summary为空的artifact仍为complete，不能误用旧error；private context不能附加到正文。candidate同步worker/lead领域投影，完整异步driver和安全Markdownfence/heading原语GIVEN；当前发布/关闭和身份/封套是集成护栏。提示：Which outcome category and body belong in this block? 追问：为何lead最终报告仍有unresolved矛盾？

## Part 5 构

主要坑：followup scope必须proper subset；每node预算覆盖全部descendants；leaf evidence保留原question和scope，不能贴到兄弟任务。leaf原scope是有序tuple，集合相同不能替代原序；内部unresolved不丢失，输入档案不改。有限shape/cycle验证给定，不主考拓扑执行。提示：What does this branch promise to investigate? 追问：两个深度相同的树是否消耗相同任务数？

## 评分与限制

每关0–4：未定位/复现/主路径/边界归属/解释来源反例，总20；仅原创练习评分。记录提示、未观察事项，不作招聘结论。源demo只拼摘要，没有typedclaim/持久化/流/树；这些是正文失败模式、ShipIt和练习要求的显式本地适配。未运行源sleep，无真实LLM/network/线程取消或生产研究收益结论。

| 分数 | 每关可观察标准 |
|---:|---|
| 0 | 未定位 |
| 1 | 能复现 |
| 2 | 主路径正确 |
| 3 | 边界归属正确 |
| 4 | 能解释来源与反例 |

| 关 | 分值 | 得分与证据、提示 |
|---|---:|---|
| Part 1 | 0–4 |  |
| Part 2 | 0–4 |  |
| Part 3 | 0–4 |  |
| Part 4 | 0–4 |  |
| Part 5 | 0–4 |  |
| 合计 | 20 | 五关分别记录，每关 0–4 分。 |
