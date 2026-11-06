# PIISpan 面试官手册

开场 2 分钟：逐关解锁，断言不改，先观察实际异常。五关 12/10/16/10/10 分钟，共 58 分钟；总计 60 分钟，没有真人校准。

## 澄清标准答案

- 偏移与匹配？ “Offsets are codepoints in the original text. Fingerprints cover the complete match, not its capture groups.”
- 重叠策略？ “Higher priority wins first, then longer coverage, earlier source interval, lexical kind and original candidate ordinal. Accept only intervals disjoint from already accepted intervals.”
- 相邻与重复？ “Adjacent half-open spans are separate. Repeated values at different intervals retain separate evidence.”
- 脱敏与拦截？ “A failed pii_scrubbing result alone permits sanitized delivery. Other failed output checks still block.”
- 落盘范围？ “Store only sanitized payload bytes and safe interval audit fields. Runtime originals and raw detector details are excluded.”
- 流语义？ “The correct supplied sandwich and driver process complete messages, preserve owner identity and close the source. Candidate work is safe response/audit projection.”

## Part 1 修：原始区间脱敏

坑：
- `findall` 把多 capture-group 的 tuple 当完整匹配交下游；`GuardService.inspect` 调正确 `pii_fingerprint` 后在 `.encode` 报 AttributeError，距 producer 一两次调用。
- 替换第一种实体后，第二种 detector 的偏移来自被修改文本，不能用来审计原文；本例首先由正确的 disjoint validator 检出重叠，修复后仍须通过原始 offset 断言。
- `pii_scrubbing` 的 failed 表示发现并脱敏，不等于 hard block。
- 每个 span 都把整份输出转字符表、改区间并 join，完整长文本请求响应慢；所有字符都参与实际输出，没有空循环。

H1：顺着第一个调用栈看值的实际类型。H2：分别核对完整 match、原文 interval、delivered response。H3：先从原文收集全部 disjoint spans，最后拼接切片；scrub 状态按 source 的类别例外处理。追问：为何 Unicode codepoint 与 UTF-8 byte 偏移不能混用？满篇 placeholder 为什么会丢合法内容？

## Part 2 存：脱敏 payload 与独立 audit

坑：
- raw original 只能留运行时，不能作为 debug 字段写到 manifest。
- 相同脱敏文本可能来自不同原值；共享 blob 不等于共享 audit。
- manifest 必须选择自己的 redacted blob，load 校验该地址对应的实际 digest；正文 CRLF 与 Unicode 不作规范化。

完整安全 AuditSpan codec/恢复、字节编码、content key、atomic writer 正确给定且 candidate/ref/reset 相同；confidence 词面与每个原始安全字段由该 codec 保留。候选负责安全外层 manifest、redacted blob 选择、每 key audit 所有权、覆盖更新和 digest 校验。H1：检查两个不同原文得到同一 placeholder 的情况。H2：分开 payload identity 与 audit owner。H3：只投影安全 audit 字段，manifest 指向共享 redacted blob。追问：这为什么不等于文件权限、加密或匿名化安全证明？

## Part 3 算：重叠裁决

坑：
- 先按优先级/覆盖裁决，再按原文顺序渲染；不能先贪图早出现的低优先级大区间。
- half-open 相邻区间不相交，不合并成同实体。
- 同一值在多个源区间重复出现，不能按 value 去重；接受结果按原文顺序返回，拒绝的 bridge 不再阻挡后续区间。

P1 的原文 renderer/指纹是修好的依赖，不重做。H1：列已接受区间而非把整组连通重叠合并。H2：跟踪 priority chain 中被拒绝的 bridge。H3：按合同 rank 逐个判断与已接受区间的交集，最后 source-order 输出。追问：这个 greedy policy 为什么不是最大权调度？

## Part 4 流：安全完成消息

坑：
- 发布 `delivered` 的脱敏正文或拒绝，不发布 raw model output。
- audit 只保留类别/通过状态/confidence/latency 与 PII 安全 span；原始 details 可能有敏感文本。
- input_results/output_results 保留各自阶段和精确 check 值，输入检查不能冒充输出报告。

实际正确的 sandwich、callback 短路、request identity、NDJSON 编码、逐消息消费和关闭均给定，在线 assertions 只是 integration guards。原始 span 的 codepoint 数值由已修 P1 给定；公开投影直接保留字段，Unicode witness 防止额外的 byte-count 改写，属于集成 guard。候选 `project_delivery` 负责实体正文、类型结果与完整安全审计。H1：比较 runtime trace 与 public record 的允许字段。H2：分别核 input/output 审计数组。H3：明确安全字段投影，delivered 与 raw_output 不能替换。追问：为什么不能宣称任意 partial regex chunk 可安全早释放？

## Part 5 构：报告阶段证据

坑：
- input block 后不应有 model/output 执行证据。
- 一个请求可多个 detector 失败，但 blocked request 只计一次，原因取 source-order 第一条 hard failure。
- scrub-only 是 permitted delivery 且应有 scrub event；所有进入输出阶段的请求都必须有 model_called 和一个 pii_scrubbing。

给定 primitive shape validator，不给完整状态验证器；候选保留所有 failed check 的原始阶段路径。H1：先按输入失败、输出失败、通过三种路径分类。H2：每条路径核 report/model_called/pii_scrubbed 的相互约束。H3：验证后每请求累计一次，保留所有失败路径与原 report。追问：统计 detector failure 与 blocked request 是什么不同口径？

## 评分表

| 项目 | 分值 | 标准 |
|---|---:|---|
| Part 1 | 25 | 四层修复，原始证据与实际响应速度 |
| Part 2 | 15 | 安全外层 manifest、独立 audit 所有权、正确 blob 与 digest 校验 |
| Part 3 | 30 | priority/coverage、已接受区间、邻接、重复 occurrence 与原文顺序 |
| Part 4 | 15 | delivered、精确安全字段、阶段与 Unicode 原文偏移 |
| Part 5 | 15 | 必需 model/scrub 证据、阶段一致性与请求级统计 |

记录 H1 定位/H2 合同分解/H3 机制提示的时点，观察后续能否独立解释。80 分以上且隐私字段/阶段规则完整表示熟悉本练习，不能外推为安全工程认证。

计时证据：完整 inspect 连续三慢 0.599856/0.549903/0.551619 秒，三快 0.004421/0.004431/0.004248 秒；限值 0.06 秒，最差双侧余量 9.165×/13.541×。SCOPE 包含完整样本与真实绝对证据路径；不代表生产吞吐。
