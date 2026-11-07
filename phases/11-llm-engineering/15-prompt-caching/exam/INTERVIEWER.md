# 面试官手册

场景：为离线 prompt-cache 实验维护可重放的写入/读取证据、精确费用与布局建议。开场2分钟；Part 1–5分别12/10/16/10/10分钟，共60分钟。用时是设计预算，没有真人校准。先看候选如何解释输入合同，再按需要给 H1/H2/H3；不要要求真实厂商调用。

## 澄清问题标准答案（English）

仅在候选人问到时，用下表英文回答；只澄清现有合同，不主动增加要求或给出修法。

| Question | Answer |
|---|---|
| Does report_horizon_us delete a cache entry? | No. It only clips each write object to [created_us, min(expires_us, horizon)). Every actual write remains a separate observed object, including expired or replaced writes. |
| Which token counts use which rates? | The WRITE, READ and UNCACHED prefix uses write, read and base rates respectively. Every suffix uses the base rate. Billing uses exact rational amounts without intermediate rounding. |
| What does break_even_reads return? | The smallest additional integer n >= 0 satisfying W + nR + S < (n + 1)B, or None if strict savings is impossible. Inputs are exact money for one prefix/write window, not raw per-token rates; equality is not savings. |
| Are the prices, TTL and tokens live provider policies? | No. They are supplied offline fixtures. Times are integer microseconds, token tuples are supplied, and the exercise does not verify a provider cache hit. |

## Part 1：流量事实与写入寿命

主要坑：生产 Request 的 token 字段未完成类型投影，正确 consumer 在外层使用时报错；最终 live entries 不能代表所有真实写入；每次查询全部历史前缀使完整收集迟缓。首错来自 decode_request，经 collect_traffic→Runtime.consume，在正确 usage_counts 执行数值加法时抛 TypeError，距离根因两次调用。报告保留每次 observation 和每个 storage object；TTL/min_tokens/固定写入时钟策略正确给定，不把其集成护栏计为新核。

H1：比较 Request 的声明与实际字段，再定位最先消费它的函数。H2：对照两次写入同一 prefix 后的历史对象与最终 current。H3：按名称投影完整类型，finish遍历写入对象，查询使用 profile-scoped exact-key 索引；观察/寿命仍全部保留。

追问：为什么一次 READ 不产生新对象？报告 horizon 与 cache delete 有何差别？复杂度中请求数和前缀长度各承担什么成本？

## Part 2：完整 journal 关联

主要坑：READ/UNCACHED 也是事实，不能只存写入；同一 prefix 的旧写入对象不能合并；每个 run 必须绑定自己声明的 profile，不能把所有全局费率混入。完整 typed record JSON 编码、原 rate 词面、LF framing、追加/关闭已给定，候选只组织持久化事实与独立 run 视图。

H1：区分全局 append 顺序与 run 内 view。H2：检查 price/run declarations 和事实引用，保留每个 object_id。H3：先读取完整 records，再按 run_id 分组；校验不可变声明、未知引用和重复 lifetime object，按 header.profile_ids 绑定价格。

追问：同名 request_id 为什么可在不同 run 出现？相同 profile_id 的重复相同声明与不同声明如何处理？追加 journal 与事务数据库各有什么边界？

## Part 3：精确 economics

主要坑：READ 只折扣 prefix，变化 suffix 始终 base；storage 按每个真实对象的 token×观察微秒积分再换算小时；严格净节省不能把相等当成功，read≥base 不一定会出现未来节省。所有定价公式和 inverse 都由候选实现，给定 Fraction rate parser 不等于给完算法。

H1：把 prefix、suffix、storage、baseline 分开列式。H2：单位统一为每1K token与微秒/小时；列出 `W+nR+S < (n+1)B`。H3：先判断写入已省钱，再处理 B−R 的符号，正改善时最小 n 为 floor((W+S−B)/(B−R))+1。

追问：为什么只在 inverse 中 suffix 可以抵消？零 baseline 如何报告？来源中“至少两次读取”与其1 write+1 read的0.675倍算例矛盾，哪个可以由数学核实？

## Part 4：实际时钟 CSV 计费事件

主要坑：请求序号不是显式微秒时间；事件角色来自真实 observation；每个新 storage object 只在创建事件进入累计 storage；各事件金额要累计到完整 final totals。输入、CSV quoting/多行字段、身份绑定、真正 pull-through 与 close 都已由 event_driver 正确给定，不把通用缓存全部输入或首 owner 复用作为候选职责。

H1：对照 AccountingEvent 的 request 与 new_lifetimes。H2：调用 Part 3只定价本次请求和这次新建对象，读事件没有新对象。H3：累计三个金额与四个计数；投影真实 timestamp_us/kind，并为 empty stream 返回显式零 TOTAL。

追问：为什么第一次写入可以报告截至已声明 horizon 的观察 storage？这是本地已知窗口重放，不是预测实时最终账单；若未来窗口未知需要改变什么 API？

## Part 5：nested prefix breakpoint

主要坑：保留完整原文与选中 prefix 是不同输出；volatile 祖先约束后代；跨 variants 的共同 token 前缀可能结束在 section 内部，断点只能落在此前完整正长度 leaf 末尾。空 leaf 仍须保留，不能替换前一个正长度断点，也不能阻断后续稳定 leaf；所有 variants 与实际渲染长度都参与边界计算。工具顺序、Unicode 原词面保持是精确匹配的集成护栏，不能通过排序/规范化制造命中。

H1：展开 full leaf paths，同时向下传 stable 状态。H2：先得到所有原始 ordered variants 与真实 LCP，再检查完整 leaf ends。H3：选择首个 volatile leaf 前且不超过 LCP 的最大正末尾，保留所有 original_variants 与首次 volatile path。

追问：为何不能把 dynamic 后的稳定 footer 加回 prefix？single observation 和空 section 的断点分别如何定义？这个本地 Section 输入与真实 tokenizer/cache protocol 有何区别？

## 评分表

| 关卡 | 分数 | 完整行为要求 |
|---|---:|---|
| Part 1 | 25 | 正确定位调用边界8；typed事实和全部写入寿命9；完整路径响应速度及防过修8 |
| Part 2 | 15 | 完整顺序和角色5；run/profile/object关联7；声明与错误边界3 |
| Part 3 | 30 | 角色和suffix10；观察storage精度10；严格inverse和不可能条件10 |
| Part 4 | 15 | 真实时间/角色5；对象计费和累计7；空流/关闭集成3 |
| Part 5 | 15 | 原始完整顺序5；祖先volatile5；LCP与合法断点5 |

85–100：独立定位且解释完整；70–84：主行为正确、少量提示；50–69：部分完成但职责/边界仍混淆；低于50：不能维持完整证据。每次提示记录到 REVIEW_TEMPLATE，不用删除断言换分。性能证据与实际检查状态见 SCOPE；本题不证明生产成本或缓存性能。

本机性能证据：完整公开 collect_traffic 接收2,500条已解析请求、80条约16K字符的真实exact稳定前缀，包含typed投影/正确生命周期/全部2,500观察和80对象寿命/全字段消费；连续三慢1.303471/1.488525/1.447905秒，三快0.008865/0.008538/0.012463秒，限值0.1秒，最差双侧13.035×/8.024×，单慢最大1.489秒。稳定前缀文本本身是索引与所有记录保留的业务输入；不计JSON字节解析、真实provider或费用计算，不声称生产缓存性能。完整copy与实际日志见SCOPE包外证据。
