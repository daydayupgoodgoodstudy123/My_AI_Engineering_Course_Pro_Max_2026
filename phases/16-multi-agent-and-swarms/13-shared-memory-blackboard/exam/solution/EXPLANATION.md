# 参考实现讲解：BlackScope（16/13）

计时结束后再看。参考实现位于本目录的 `blackscope/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前合同；原样 reference 五关与固定完整性能组已有本机运行记录，静态阅读本身不产生运行证据。

## Part 1：decimal-safe 首句与真实 provenance

first_sentence 的有限规则是 `. ! ?` 后紧跟 whitespace 才形成句界，返回首句并保留句末标点。小数点后跟数字不触发句界，没有匹配就返回全文。source 式 `text.split('.')[0]` 在 4.2% 内切开，正确 SummaryDesk.observe 随后把结果交给 require_percent_claim；完整 percentage grammar 找不到带 unit 的数字，于 producer 外两次调用后自然 ValueError。不能修改正确 consumer 接受残缺数字，也不把规则扩成通用 NLP。

append_entry 已正确生成 ID、writer/topic/content、timestamp_ns、full prompt digest 与 source metadata。append_supersession 读取旧记录的 topic，用本次 writer/content/time/prompt/source 追加新 entry，并设置 supersedes=old_id；旧条目不能原地改写。read handles 已给出 immutable Entry snapshots，候选不重写 ownership 或浅/深拷贝机制。

publish_finding 只调用独立 channel.emit，不把 verifier detail 作为 pool fact。typed channel 和 read capabilities 本来正确；普通 writer 名为 verifier 也不能获得独立 finding authority。source 中 verifier 返回 findings 后 caller 又 flag 进 pool，analyst 不读 flags，所以 RUN 2 并没有实际 retraction。完整独立 channel 是本题按课程方向落实的本地 adapter。

正确 decimal-safe 全文 re.split 能得到首句，但仍扫描并物化首句之后的真实正文。参考用 re.search 找第一个声明句界，再切到该 whitespace 起点，标点保留。完整 source article 仍写入 retrieval history，不为速度删掉正文。topic callback snapshot/reentrant subscription 行为也已正确 GIVEN，不属于另一层预埋故障。

P1 当前限值 0.02 秒。固定完整组慢版三次为 0.219885、0.224771、0.238220 秒，参考版为 0.0001577、0.0001976、0.0002087 秒；两侧余量分别为 10.99425 和 95.80843。32 篇合成本地 articles 各保留 14,000 条实际进入服务的 observation rows，完整输出为 64 条 retrieval/summary entries 与 32 条 receipts；fixture 与独立 expected 在 timer 外，整个 SummaryDesk.observe_many 及完整 SummaryReport equality 在内。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另执行 decimal-safe 全文 split；全部业务 guards 与全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为和正式检查分别有自己的验收记录，不能由测量版推定；本机余量不是任意运行环境的墙钟上界或生产 SLA。

P1 只修摘要、append-only producers 与独立 finding publication，没有提供 P3 active lineage、exact finding join 或 consumption solver。source supersedes 虽有字段却没有完整使用，也没有本题 ledger/certificate 运行时。

## Part 2：完整历史版本的 JSONL model

encode_entries 按 entries 声明序生成每条 document：entry_id、writer、topic、完整 content 与完整 encode_metadata(entry)。decode_entries 用本条字段和 decode_metadata 重建 Entry，保留原 ID 和每个版本自己的来源、时间、prompt 与 predecessor。相同文本的不同 ID/writer/source 仍是不同 audit records，不能按 prose 去重；不能只保存 active view、过滤 corrections、重新编号或从另一版本借 content。

ProvenanceLog 的正确 wrapper 调用完整 LedgerDriver。driver 已提供 typed/capability intake、pool/findings 两条 channel、append-only prefix 检查、JSONL append/flush/framing/reopen 与 finding codec。候选不重写通道路由，也不按 writer 字符串分类。完整 metadata codec 已保留精确 ns integer、64-character prompt hash、SourceKey 和 supersedes=0/None；它们是正确依赖的集成护栏。

保存所有原始与更正记录，P3 才能从重开后的真实历史求 active 和核查状态。重复导出相同完整 view 不会形成重复版本，这由完整 driver 的 prefix/append 规则提供；候选仍必须给 driver 正确的全历史 documents。

## Part 3：三个独立 evidence 算法

active_provenance_view 遍历 append history，为同 topic supersedes 追到同一 lineage root；跨 topic link 作为自己的新 root。同一 root 的分叉 correction 也属于该 lineage。每个 root 的 latest 是最后 append 的 entry，最后按原 history order 返回这些 active IDs。同 topic 中没有 correction 关系的独立 roots 不互相覆盖，不能把 topic 当唯一 latest key。原记录仍留在 durable history。

attach_version_findings 对每个 entry 保留全部同时匹配 entry_id 与完整 SourceKey(uri,version) 的 finding。entry 没有 source 就没有 exact finding。只要有 exact DISPUTE，状态为 DISPUTED；否则有 exact MATCH 为 VERIFIED；两者都没有则 UNVERIFIED。旧版 approval 不移给 correction，同 URI 旧 snapshot 也不能批准新 snapshot；这里不把 UNVERIFIED 折成 negative truth。

consumable_entries 先取 active view，policy.role 只有 analyst 才可消费；空 declared topics 只得到空消费视图；按 declared topics 与 VERIFIED 状态筛选，维持 append order。non-analyst、topic 外或 disputed/unverified 都不可消费，writer/provenance 标签不改变调用能力。实际集成从 P1 SummaryDesk 创建来源记录，经 P2 log reopen，再用独立 findings 做消费决策，不只处理手写样例。

合法输入是有限 typed Entry/Finding、唯一且按 history order 排列的 entry IDs，supersedes 指更早 ID 或 None。findings 已从正确独立 channel 进入，verdict 只有 MATCH/DISPUTE；这三项算法消费已授权的 findings，合法域校验不属于本关 solver。source_matches 只是有限 fixture 的 exact text comparison，不是自然语言事实核验。

## Part 4：每个 entry/correction 的九个字段

entry_payload 返回当前观察自己的 entry_id、writer、topic、完整 content、timestamp_ns、prompt_hash、source_uri、source_version 与 supersedes。correction 的 writer、prompt/source version 和 predecessor 可能与旧记录不同，必须各取本条原值；没有 source 时 URI/version 都为 None。普通 content 完整保留，即使文字包含 verdict 或 JSON 片段，也不裁切或重解释。

完整 classify_observations 已按真实 read capabilities 将 Entry 标为 entry/correction，并将独立 VerificationFinding 标为 finding。driver 校验 typed observation，finding_payload 也完整给定。JSON Text Sequence writer 生成 RS byte、JSON wrapper(type/data)、LF，async driver 逐条 publish 并在退出时 close。候选不再选择 finding 目的地、重写分类或修 cadence/UTF-8/close。

本关负责 own provenance domain projection；kind 是正确授权的输入，finding routing 由完整 driver 提供，payload 不赋予 writer 新 authority。

## Part 5：nested required coverage 与 source sets

ClaimCatalog 已完整提供 global UID lookup、ordered occurrence expansion、共享 claim 各处 path 与 missing/cycle markers。decision_index 与 leaf_support 已直接消费正确 P3 admitted EvidenceDecisions；本题实际先运行 P1 service、P2 ledger reopen 和 P3 consumption，再把 leaf decisions 交给 certificate 构造。候选不重做 finding join 或图解析。

build_support 对带 obstacle 的 occurrence 生成其位置的 certificate，保留给定 marker。对 entry leaf，用完整 leaf_support 获得 required、covered、external SourceKey 与 obstacles；entry 0 是正常 ID，由正确 helper 处理。叶子无法取得支持时仍是 required，不能从 requirements 中删掉。

对 derived occurrence，递归按声明序构造 child certificates，分别 union child.required、child.covered、child.sources 和 child.obstacles，再保留 children 返回本层 SupportCertificate。required 不是 covered 的别名；某叶子缺证据不能隐藏 requirement，也不应抹掉其他已有 sources。每个中间层都要有证书，不能只给 root 一组集合。

external sources 只来自 verified leaves 的 SourceKey(uri,version)，同一 URI 的不同 versions 仍分别贡献 key。announced_source 是 wrapper 标签，转述或两个 wrappers 引用同 snapshot 不产生另一个 external key；SourceKey 集合 distinct 不等于现实世界独立性已经核验。complete 属性已正确给定：required 非空、全部被 covered、至少有 source 且没有 obstacles。它描述完整 support certificate，不给缺证据 claim 判 false。

marker 传播是对完整 catalog 的集成，各层 required/covered/source 集合与 certificate 的组合才是候选算法。source/讲解只是提出 derived_from 方向，没有该 claim/certificate DAG 运行时；本地适配只组合有限证据。

## 这套题证明了什么，没证明什么

若候选通过全部原样测试，证据只支持本地有限合同：保留 decimal/unit 首句与 append-only provenance，独立发布 finding，重开全版本日志，实现 active/exact evidence consumption，投影本条 provenance，递归构造 coverage/source certificates。当前原样 reference 五关和固定完整性能组已有本机运行记录；TEMP、独立行为与正式检查各有独立验收边界，不能由 reference 或计时版结果替代。静态数量为 13 candidate/13 reference modules、42 Python 文件、5 tests、43 assert、0 raises、5 skip、26 登记错修，数量不是执行证据。

source 的 verifier 发现不等于阻断，RUN 2 未实际 retraction；本题独立 channel、versioned snapshots、ledger、消费规则与 derived certificates 都是显式本地扩展。四份来源没有 import/run，英文 output artifact 只作数据，没有调用其流程。框架、日期与 production 声明作为固定来源快照，未作当前外部核验。

有限 source fixture 的 exact comparison 不证明自然语言真实、来源可信或现实独立性；read-only/capability API 不证明恶意 Python 代码下的安全隔离。证书集合也不证明通用 memory-poisoning 防护、分布式共识或任意业务决策正确。Python 3.10+ 是目标环境，没有该版本实际运行声明；60 分钟及各关时间尚未真人校准。

P1 当前限值 0.02 秒。固定完整组慢版三次为 0.219885、0.224771、0.238220 秒，参考版为 0.0001577、0.0001976、0.0002087 秒；两侧余量分别为 10.99425 和 95.80843。32 篇合成本地 articles 各保留 14,000 条实际进入服务的 observation rows，完整输出为 64 条 retrieval/summary entries 与 32 条 receipts；fixture 与独立 expected 在 timer 外，整个 SummaryDesk.observe_many 及完整 SummaryReport equality 在内。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另执行 decimal-safe 全文 split；全部业务 guards 与全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为和正式检查分别有自己的验收记录，不能由测量版推定；本机余量不是任意运行环境的墙钟上界或生产 SLA。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
