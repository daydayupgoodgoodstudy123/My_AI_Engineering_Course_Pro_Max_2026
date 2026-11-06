# PIISpan 参考讲解

## Part 1

用 `finditer(...).group(0)` 保留完整匹配。多 capture groups 的 `findall` 结果可能是 tuple，正确指纹 helper 对字符串编码时会暴露 producer 的投影错误。本例在第一层修好后，错误的后续偏移与前一区间重叠，正确 disjoint validator 先报告 ValueError；不应移除验证。所有 recognizer 都在原文上扫描，收集完后统一按原文位置排序；本关合同保证 disjoint，不做 P3 的 overlap policy。renderer 依次取原文间隙与 placeholder 后 join，完整保留未匹配字符。source 中 pii_scrubbing 的 failed 表示发现并处理实体，单独出现时可放行脱敏结果；其他失败照常 block。

原始慢实现每个 span 将真实输出转字符列表，修改该区间并重新 join。每次重建都产生最终要交付的正文，没有虚假工作。计时包括完整 inspect 的匹配、原始审计/指纹、渲染与决策；fixture 构造和独立期望值在两侧相同且在 timer 外。最终连续六次本机数据及此前未达标组均记录在 SCOPE 的绝对证据路径。

## Part 2

脱敏 UTF-8 payload 的正确 codec/hash 与原子替换 primitive 给定。完整 audit_to_records/audit_from_records 是正确 GIVEN：安全字段投影、原有 validate_audit 合同校验及 AuditSpan 构造恢复均已实现，candidate/ref/reset 同字节。候选保存 redacted blob，再为每 key 组合该安全 codec 结果与 payload 地址的外层 manifest。不同原文可产生相同 placeholder，所以 blob 可以共享，audit 必须各自独立。运行时 original 不写入文件。原始 confidence 词面与 span 指纹由 GIVEN codec 保留，不是候选的数值表示任务；候选必须正确选取 redacted 正文、保持独立 key 所有权并在恢复时核验 blob digest。正文 CRLF、Unicode 不作规范化。 不同脱敏 blob 并存时，旧 key 与新 key 都必须按各自 manifest 的地址恢复；blob 字节被改动时拒绝。完整 audit 校验先于 blob 写入，非法 audit 不产生部分落盘。这里不验证文件权限、加密、抗字典攻击或真正匿名化。

## Part 3

按 `(-priority,-length,start,end,kind,ordinal)` 排序候选，逐一与已经接受区间比较严格半开区间交集。被拒绝 bridge 不影响后续独立候选；相邻端点相等不算相交；重复值不按 value 去重。选完后回到原文顺序，即便互不重叠的优先级与原文先后相反也一样；被拒 bridge 不参与后续排斥。复用修好的 P1 renderer 与给定指纹 helper。这个明确的 greedy teaching policy 是 source 按 PII 类别顺序脱敏的区间化适配，不是最大权区间算法。

## Part 4

正确给定 sandwich 保证 input failure 不调 replay，output hard failure 拒绝，scrub-only 返回 sanitized delivery。正确 driver 保证当前 request identity、完整消息、NDJSON 和 close。候选只投影 trace.delivered/outcome 及两阶段的安全 check 字段和 PII span；check latency/confidence/passed 保留原值，Unicode 偏移仍是原文 codepoint；不序列化 details、raw_output 或原始 transcript。传输 guards 保留，但不把通用 collect-all→yield 当本关新核心。

## Part 5

primitive shape 通过后，按 input failure、output hard failure、permitted 三条路径验证 report/model_called/pii_scrubbed。input blocked 必须没有后续证据；其他路径必须有 model_called 和恰好一个 pii_scrubbing，包括 hard output block；hard output blocked 不得声称安全 scrub delivery；permitted 时 scrub flag 对应 pii_scrubbing result。block_reason 对应第一条 hard failure。每条 trace 只计一次请求，同时保留所有 failed check 的 `(report ordinal,stage,index,category)` 路径与原 report。它消费已有证据，不重新运行 detector 或模型，也不构造任意执行树。

计时证据：完整 inspect 连续三慢 0.599856/0.549903/0.551619 秒，三快 0.004421/0.004431/0.004248 秒；限值 0.06 秒，最差双侧余量 9.165×/13.541×。SCOPE 包含完整样本与真实绝对证据路径；不代表生产吞吐。

## 这套题证明了什么，没证明什么

它验证有限 recognizer 和本地 replay 下的原始区间证据、精确安全持久化、声明的 overlap policy、完成消息安全投影和两阶段统计。它没有证明广泛 PII 检出能力、真实 moderation 效果、密码学隐私、真实模型安全、任意 partial chunk 安全释放、生产吞吐或真人 60 分钟通过率。
