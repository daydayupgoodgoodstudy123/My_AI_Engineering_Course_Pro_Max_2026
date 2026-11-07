# 面试官手册：BlackScope（16/13）

候选人计时期间不看本手册。候选人使用英文 README、`blackscope/` 和测试，逐关修领域实现，保留全部断言与完整 GIVEN。

## 开场（2 分钟）

- 总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间与难度尚未真人校准，不要求全部完成。
- 请候选人解释当前证据、根因和下一步判断，可以随时澄清、查 Python 标准库官方文档。
- 只解除当前 skip，记录解锁到首次通过的时间、运行次数与 H1/H2/H3。卡住约 5 分钟时一次给一级提示，主持人不代写代码。
- 英文澄清在问到时回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 和本手册。
- 说明 sources 与 verifier 都是有限本地 fixture，没有真实模型或网络核查。证据状态与 support certificate 不宣称自然语言真假或现实来源独立性。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | What is a sentence boundary here? | A period, exclamation mark or question mark followed by whitespace. Keep the first sentence's punctuation; a decimal point without following whitespace stays inside it. |
| 1 | What if there is no boundary? | Return the complete input. This is a finite local rule, not general natural-language sentence segmentation. |
| 1 | Can a correction change the old record? | No. Append a new identity with its own provenance and a supersedes link. Keep the historical record unchanged. |
| 1 | Where does a verifier finding go? | Through the separate typed VerificationChannel. Do not publish it as an ordinary fact. |
| 2 | Should the ledger keep only active entries? | No. Encode every original and correction version, in append order, with its original ID and own complete provenance. |
| 2 | Must I implement channel routing, flushing or timestamp encoding? | No. The complete LedgerDriver and exact metadata/finding codecs are supplied. Model the entry documents and reconstruction. |
| 3 | Is there only one active record per topic? | No. Independent roots remain separate. Only same-topic corrections share a lineage; a cross-topic link starts its own lineage. |
| 3 | Can an approval follow a correction or the same source URI? | No. Join both the immutable entry ID and the complete source URI/version key. |
| 3 | What wins when exact findings disagree? | Any exact DISPUTE wins over MATCH. With no exact finding the status is UNVERIFIED, not false. |
| 3 | Who may consume an entry? | Only an analyst, and only active VERIFIED entries in its declared topics. Other roles consume none. |
| 4 | Do I decide whether an observation is a finding? | No. Authorized channel classification, routing and finding projection are complete supplied dependencies. Project the entry or correction's own provenance. |
| 4 | Which fields belong in an entry payload? | Its ID, writer, topic, complete content, nanosecond time, full prompt hash, source URI/version and supersedes link. |
| 4 | Must I implement JSON sequence framing or close behavior? | No. The complete RS-plus-JSON-plus-LF writer and async publication/close driver are supplied. |
| 5 | Do wrapper labels add independent external sources? | No. Union verified external SourceKey values only. Two wrappers around the same snapshot still contribute one key. |
| 5 | Are required and covered the same set? | No. Preserve every required immutable entry, even when it lacks support. Covered entries come from verified leaf decisions. |
| 5 | Must I resolve shared claims or detect graph cycles? | No. The complete catalog supplies each ordered occurrence and full missing/cycle markers. Build certificates over that expanded structure. |
| 5 | Does an incomplete certificate make a claim false? | No. The supplied completeness predicate describes missing support, not a truth verdict. |

## Part 1：首句、append-only correction 与 finding 发布（目标 12 分钟）

四层缺陷：

1. first_sentence 按任意句点切开 4.2%，丢掉完整 percentage unit。正确 SummaryDesk.observe 随后调用 require_percent_claim，producer 外两次调用后自然 ValueError；修首句 producer，不改正确 grammar consumer。
2. append_supersession 原地改旧 writer record 并返回旧 ID。应追加独立 ID、新 content/time/prompt/source 与 old-ID link，保留旧 provenance。
3. publish_finding 把 verifier detail 写成普通 pool fact。应调用已有独立 channel capability，pool 不改变。
4. decimal-safe 全文 re.split 虽得到正确首句，仍扫描并物化真实完整 tail。参考在首个声明句界停止，全文继续保留在 source audit。

看什么：是否分开分句内容、历史记录与独立核查输出。append IDs、full prompt digest、immutable read snapshots、typed channel 与 topic callback snapshots 都正确 GIVEN，不要求修 shallow/deep ownership 或 callback reentrancy。P1 不提供 P3 active/join/consumption solver。

P1 当前限值 0.02 秒。固定完整组慢版三次为 0.219885、0.224771、0.238220 秒，参考版为 0.0001577、0.0001976、0.0002087 秒；两侧余量分别为 10.99425 和 95.80843。32 篇合成本地 articles 各保留 14,000 条实际进入服务的 observation rows，完整输出为 64 条 retrieval/summary entries 与 32 条 receipts；fixture 与独立 expected 在 timer 外，整个 SummaryDesk.observe_many 及完整 SummaryReport equality 在内。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另执行 decimal-safe 全文 split；全部业务 guards 与全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为和正式检查分别有自己的验收记录，不能由测量版推定；本机余量不是任意运行环境的墙钟上界或生产 SLA。

提示：

- H1: "Which producer first lost the decimal percentage and its unit?"
- H2: "Did this correction preserve the old version, and did the finding stay outside the fact pool?"
- H3：按有限 .!?+whitespace 规则保留首句标点；追加 linked correction；finding 只发独立 channel；首边界即停但保留完整 source article。

追问：

- "Why retain the full article when only its first sentence is summarized?"（正文是持久审计来源，摘要与 source history 用途不同。）
- "Did the source demo actually retract the poisoned conclusion?"（没有；caller flag 回池中，analyst 不看 flags，讲解明确指出 RUN 2 仍未阻断。）

## Part 2：完整版本 provenance JSONL（目标 11 分钟）

主要坑：

- 全部原始和 correction versions 都必须建模，不能 active filtering、去掉 superseded records 或重新编号。
- 每条保存自己的 ID/writer/topic/content 和完整 metadata，不能从另一条取 content、把 topic 当 writer 或复用旧 prompt/source。
- 相同文本仍可属于不同 immutable provenance records，不能用 content 代替 identity。
- decode 按原 append order 恢复独立 versions，与历史记录一起重开；重复导出同一 view 不产生额外版本。

看什么：是否知道 durable history 与 active projection 的区别。完整 LedgerDriver 已控制 channel/capability intake、prefix 检查、JSONL append/flush/reopen；精确 metadata 与 finding codec 也 GIVEN。时间精度、link=0/None、完整哈希与 ordinary writer label 都是依赖集成护栏，channel 隔离不是本关候选主修点。

提示：

- H1: "Which historical versions and original identities must still exist after reopening?"
- H2: "Does every document retain that version's own content and provenance?"
- H3：按原序 encode 全部 entry ID/writer/topic/content，metadata 交给完整 helper；decode 原字段与 metadata，不过滤或 reindex。

追问：

- "Why isn't saving the active view enough?"（更正依据、旧来源与消费决策需要完整历史可追踪。）
- "Who routes an ordinary writer named verifier?"（完整 typed/capability driver；writer 文本不能给 entry 授予 finding authority。）

## Part 3：active lineage、exact join 与 consumption（目标 15 分钟）

三个独立 TODO：active_provenance_view、attach_version_findings、consumable_entries。

主要坑：

- latest 是每个 same-topic correction lineage 的最新 append，不是每个 topic 一条；同 root 的较晚分叉也退休此前 active version。独立 roots 保留，跨 topic supersedes 不退休另一 topic。
- finding 同时匹配 immutable entry ID 和完整 SourceKey(uri,version)。旧 approval 不移给 correction，同 URI 的旧 snapshot 也不匹配；保留全部 exact findings，DISPUTE 优先。
- 先 active，再只允许 analyst 消费声明 topics 内 VERIFIED entries。空 topics 不授权消费；缺 exact finding 保持 UNVERIFIED，不能绕过 topic/role 或把缺证据写成 false。

看什么：是否分别实现三个算法，实际消费 P1 SummaryDesk→P2 ledger reopen 的 history/findings。独立 channel 与 fixture source comparison 是正确依赖，没有 active/join/消费 solver。合法域是有限 typed records、history-order unique IDs、supersedes 只指更早 ID 或 None；findings 已授权且 verdict 为 MATCH/DISPUTE，不要求候选通用输入校验。

提示：

- H1: "Which correction lineage owns this latest entry?"
- H2: "Does this finding name this exact entry and this exact source snapshot?"
- H3：保留每个 same-topic root 的 latest；精确 join 后以 DISPUTE/MATCH/无 finding 定状态；再按 analyst/topic/active/VERIFIED 条件选择。

追问：

- "Can one topic have multiple active roots?"（可以，彼此没有同 topic correction 链的独立记录不互相覆盖。）
- "Why isn't UNVERIFIED a negative truth verdict?"（有限 fixture 没有对应独立核查，不代表真实世界已证伪。）

## Part 4：entry/correction 自身公开证据（目标 10 分钟）

主要坑：

- entry 与 correction 都保留自己的 writer/topic/content 和 ID，不把 correction 写回原 retrieval 的身份。
- source URI 与 source version、full prompt hash 与 timestamp_ns 各取本条原值，不能串用字段或借用前一版本。
- correction 的 supersedes 保留原 ID，普通 content 完整保留，不把文本裁成摘要或改成 finding 解释。

看什么：是否直接投影本条 nine-field provenance。kind 已经授权；完整 classifier/router、finding payload、JSON sequence codec、async publish/close 都 GIVEN。这里不让候选再选 finding 通道，也不考 byte-count、collect-all cadence 或 cached first identity 算法。

提示：

- H1: "Whose provenance belongs to this actual entry or correction?"
- H2: "Which source version, prompt and predecessor did this version declare?"
- H3：直接投影本条九个字段，source 缺失时 URI/version 为 None；content 原样保留，kind/finding/wire/close 交给完整 driver。

追问：

- "Why expose a correction's predecessor?"（消费者需要关联历史版本，不能只看到一条无来源的新值。）
- "Does verdict-like content grant independent finding authority?"（不会；typed channel 已由完整 driver 区分，payload 保留普通文本。）

## Part 5：nested coverage 与 distinct source support（目标 10 分钟）

主要坑：

- 每个 derived layer 都构造 SupportCertificate 并保留 ordered child certificates，不能只算 root 集合就丢掉层级证据。
- required 与 covered 分别 union。未获支持的叶子仍是 required，不能以 covered 反推 required 来隐藏缺口；已有 covered/source evidence 也不能被擦除。
- external source 集合只来自真实 P3 admitted leaves，distinct identity 是 URI+version，同 URI 的不同 versions 仍分别保留。wrapper announced_source 或转述不能制造 external authority；同 snapshot 的多重 wrappers 不增加 source key 数量。

看什么：是否消费完整 occurrence expansion，复用 leaf_support 的正确 P3 decision lookup，递归合成 required/covered/sources/obstacles。UID resolver、shared occurrences、missing/cycle full paths 与 complete predicate 真 GIVEN；marker 的传播是依赖集成，主要算法是各层证据集合与 certificate 的组合。P5 实际使用 P1 service、P2 reopen、P3 consumption 的证据。

提示：

- H1: "Which immutable entries are required, and which verified leaves actually cover them?"
- H2: "Did this wrapper add a real external snapshot or only another label?"
- H3：obstacle/leaf 先用给定 marker 与 leaf_support；递归保留 children，分别 union 四种集合，来源仅为 child external SourceKeys，complete 交给已有 predicate。

追问：

- "Why can two wrappers still provide one source key?"（它们引用同一 external snapshot，重复转述不等于另一个来源。）
- "Does distinct URI/version prove real-world independence?"（不证明，只是本地集合 identity；相关性与来源可信度需要额外证据。）

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层摘要与 correction | 20 | decimal/unit 首句 5；append-only correction 5；finding 发布 4；early-stop 与完整业务路径 6 |
| 完整版本 ledger | 20 | 全部历史/原 ID/声明序 8；每版完整 own provenance 8；重开与正确 helper 集成 4 |
| active exact evidence policy | 25 | topic-local lineage/独立 roots 8；exact join/dispute priority 9；analyst/topic/verified consumption 8 |
| own provenance projection | 15 | own identity/content 6；own time/prompt/source URI+version 7；correction predecessor 2 |
| derived support certificate | 20 | ordered hierarchical certificates 6；required/covered 独立合成 7；distinct external source keys 5；obstacle 集成 2 |

按实际代码、测试现象或口头推理评分：完整满足得满分，有具体反例的部分实现得部分分，未实现或未观察得 0。提示、用时与运行次数另记，不把参考结果算作候选成绩。

当前题包为 13 candidate/13 reference modules、42 Python 文件、5 tests、43 assert、0 raises、5 skip、26 登记错修。P1 当前限值 0.02 秒。固定完整组慢版三次为 0.219885、0.224771、0.238220 秒，参考版为 0.0001577、0.0001976、0.0002087 秒；两侧余量分别为 10.99425 和 95.80843。32 篇合成本地 articles 各保留 14,000 条实际进入服务的 observation rows，完整输出为 64 条 retrieval/summary entries 与 32 条 receipts；fixture 与独立 expected 在 timer 外，整个 SummaryDesk.observe_many 及完整 SummaryReport equality 在内。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另执行 decimal-safe 全文 split；全部业务 guards 与全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为和正式检查分别有自己的验收记录，不能由测量版推定；本机余量不是任意运行环境的墙钟上界或生产 SLA。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
