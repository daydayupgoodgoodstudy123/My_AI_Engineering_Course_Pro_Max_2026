# 参考实现讲解：RobustCenter（16/14）

计时结束后再看。参考实现位于本目录的 `robustcenter/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前合同；原样 reference 五关与固定完整性能组已有本机记录，静态阅读本身不产生运行证据。

## Part 1：signed cluster、ABSTAIN 与 D

完整 numeric_parts 识别有限 signed decimal（点或逗号）、可选 percent/%，返回 canonical percent/scalar unit。canonicalize_proposal 只需保留该数值的 sign；删除负号会让 key 与真实 signed member 不等价。正确 ConfidenceDesk.inspect 调 validate_cluster_members，再由 require_equivalent 自然 ValueError；错误在 producer 外两次调用后暴露，不能改正确 consumer 接受矛盾簇。

legacy_support_report 只把非 None key 的 ANSWER clusters 放进 eligible mass。每簇质量是实际 Probe.confidence 之和，total 是全部 eligible answer mass；胜者质量达到 inclusive threshold×total 才接受，且 total 必须正。ABSTAIN 的 UID、原 record 与 Probe 仍在完整审计中，但不构成 answer 或 answer denominator。source cp_wbft 本来用 confidence mass；人数门槛是本题的局部教学回归，typed abstention 政策也是显式本地选择。

pairwise_confidence_disagreement 的 D=Σ(i<j)|c_i−c_j| 使用全部声明 probe confidence，包括 zero、abstention 与重复值。排序后，对第 i 个值 c，前面所有 gap 之和为 i×c−prefix；逐项累加再更新 prefix，得到与真实 unordered-pair enumeration 完全相同的 exact Fraction。不能用 max−min 或删除 zero confidence 替代。

D 与 dispersion_alert 是完整 Inspection 的实际诊断字段，不是额外空转工作；它不计算答案位置的 median。完整 legacy_cluster_scores 使用 source 式簇内 confidence median 距离启发式，已经 GIVEN，与 D 和 P3 position solver 都不同。P1 不提供 weighted median/tie/radius 算法。

P1 当前限值为 0.15 秒。固定完整组慢版三次为 2.089669、2.736338、2.203572 秒，参考版为 0.014413、0.015047、0.013903 秒；两侧余量分别为 13.93112 和 9.96901。2,400 个合成本地 Ballots 的完整 Proposal/Probe、canonical keys、support/abstentions、source-style legacy scores、exact D 与 dispersion_alert 全部保留，D 的独立 closed-form expected 为 ones×zeros。fixture 与独立 expected 在 timer 外，整个 ConfidenceDesk.inspect 与完整 Inspection equality 在 timer 内，之后才读 elapsed；不能删 zero/abstention、只求 extreme gap、裁 records 或预填 report。六份 NEW 完整测量副本只把 timingassert 换成实际 elapsed 输出，慢版另枚举所有真实 unordered confidence pairs；全部业务 guards 和全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为与正式检查有各自验收记录，不能由测量版推定；本机测得余量受运行环境影响，不构成通用墙钟上界或生产 SLA。

## Part 2：完整 per-run snapshot 与 ordinal

ProposalArchive.save 枚举当前输入的完整 ballots，为 Proposal 和其一个实际 Probe 分别生成相同 ordinal 的 rows。Proposal 保存 uid/agent/kind/原 answer/self_confidence；Probe 保存 proposal_uid/probe_uid/confidence/evaluator/assessment；probe_uid 取实际 q 记录，不能根据 proposal UID 推造。self-confidence 与 independent probe confidence 各有自己的 provenance，不能互相代替。

完整 Database 已提供 schema、目标 run 的原子 snapshot replacement、SQL ordinal 排序和 close/reopen；Fraction 的 numerator/denominator codec 与 raw answer text storage 也 GIVEN。candidate 仍须真实选择并关联全部正确字段，再按对应 rows 重建 Ballot；不能把 evaluator 当 assessment、agent 当原 answer，或按 agent 去重。

save 替换该 run 为这次提供的完整 ordered snapshot，其他 run 保留。zero-probe records 与 same-agent distinct UIDs 都留在 snapshot，但没有推断出的 retry lineage、历史 revision append 或每 proposal 多 probe history。load 不存在的 run 返回空 tuple，ABSTAIN answer=None 和精确有理质量由正确 schema/codec 保留；这些是依赖集成护栏。

## Part 3：真正的一维 weighted median

weighted_median_interval 接受 comparable-unit finite Decimal positions 与 nonnegative Fraction weights；完整 intake 已提供。只让 positive mass 决定最小化 sum(weight×absolute distance) 的区间，先按位置排序。累计质量首次严格超过一半时，区间退化到该位置；恰好一半时，完整 interval 从当前位置到下一个 positive-mass position。重复位置保留全部质量，zero mass 位于区间内外都不定义端点；total=0 时明确 ValueError。

choose_interval_center 独立按 lower/upper/midpoint 请求选择，midpoint 用完整 exact arithmetic helper；不能在求 interval 时偷偷决定 tie policy。source decentllms 只对字符串簇里的 confidence 做启发式评分，并没有这个答案位置最小化算法。

audit_center_support 按 inclusive radius 判断每个 positive-mass position，累加实际 Fraction support，total 保留全部非负质量。accepted 比较 support≥threshold×total；minority 是原声明序中 radius 外的 positive-mass proposal UIDs，不随位置排序重排。center 与单位原样进入 CenterAudit。

完整 evaluate_truth 用另给 TruthLabel、unit 和 radius 比较，缺 label 返回 None。agreement acceptance 不改变 truth，truth False/None 也不是把 support 重新计一次。测试实际从 P2 save/close/reopen 得到原 Ballots，经修好的 P1 inspect 和完整 positions_from_inspection，再调用三个 solver；不是手填一个 center 报告。

## Part 4：七个 own fields 与完整 probe dependency

proposal_payload 的七个候选字段是 kind、proposal_uid、agent、原 answer、signed position、unit、self_confidence。取本条 Proposal 的真实值，原 answer 与 canonical numeric text 同时保留；scalar 与 percent 不混用。numeric_fields 与 fraction_pair 都完整给定，候选组合实际字段，不重写精确数值编码。

完整 public_observation 已做 typed intake、ANSWER/ABSTAIN 分类、P1 canonical numeric 读取与实际 probe binding；probe_payload 已完整投影 probe_uid/probe_confidence/evaluator/assessment。将它与七字段合成，不能用 p.self_confidence 伪造 probe evidence。ABSTAIN 仍保留非投票 Probe，answer/position/unit 无 numeric claim。

完整 writer 产生 4-byte network-order payload byte length 与 UTF-8 JSON，async driver 逐项发布并 close。framing、字节数、escaping、cadence 与分类是 GIVEN 集成边界，本关重点是七个 own proposal fields。

## Part 5：Core 与 Edge 独立对照 sealed

完整 seal_core 真实复用 P1 inspection/P2 reopened ballots 与三个 P3 solver，产出 SealedCore，包括 epoch、original proposal UIDs 和 CenterAudit。CoreCatalog 已提供 original evidence admission、UID/reference binding 与 finite unique-tree 校验。edges 没有独立 voting mass，候选不再算 median/support/truth 或证据去重。

audit_core_tree 先使用完整 catalog validation，再递归对每个当前 CoreGroup 取自己的 SealedCore。current.epoch 不同于 sealed.epoch 记 core-epoch；claimed_center/unit 不同于 sealed.decision 记 core-value；sealed.decision.accepted=False 记 core-not-accepted。保留该层 path、sealed 与 own findings。

每个 own EdgeAck 单独建立 EdgeAudit：edge.core_uid 对当前 CoreGroup UID 检查，错误记 edge-parent；edge.epoch 对当前 authoritative sealed epoch 检查，错误记 edge-epoch；edge center/unit 对 sealed CenterAudit 检查，错误记 edge-value。完整 references_valid 按 ack 声明的 core 查 original proposal refs，失败记 edge-reference；wrong parent 即使另一个 core 的 refs 可解析，也仍有 edge-parent。仅当当前 sealed accepted=False 时记 edge-before-core。

core declaration 与 edge 都独立对照 sealed，不能把当前 group 的错误 declaration 当成 edge 的权威。比如 CoreGroup 声明 epoch=9/center=6，而 sealed 是 epoch8/center5：core 有自己的两项 findings，一个 epoch8/center5 的 matching edge 仍可没有 findings。edge-before-core 不由 core findings 是否为空决定，只由 authoritative accepted flag 决定。

递归 children 时各取 child 自己的 sealed result，保留 ordered nested CoreAudit 与 own EdgeAudit；不能把 root decision 用到 child 或丢掉中间层。following edges 不改变原 core 的 support、accepted 或 truth；这是 Core-first/Edge-following 概念的本地审计 adapter，不是 source 已有 certificate protocol。

## 这套题证明了什么，没证明什么

若候选通过全部原样测试，证据只支持本地有限合同：保留 signed/unit proposal，处理 abstention/mass 与 exact D，重开完整 proposal/probe snapshot，实现 scalar weighted-median interval/tie/radius，投影 own evidence，递归审计 sealed Core/Edge declarations。当前原样 reference 五关与固定完整性能组已有本机运行记录；TEMP、独立行为与正式检查分别验收，不能由 reference 或测量版替代。静态数量为 14 candidate/14 reference modules、45 Python 文件、5 tests、37 assert、1 raises、5 skip、26 登记错修，不是执行证据。

source 是 scripted single-round aggregator，confidence-space heuristic 不是位置 median，也没有本题的 D、typed abstention、archive、framed service 或 nested certificate。四份来源没有 import/run，英文 output artifact 仅作数据，没有调用其流程。论文数值、框架、BFT 与 empirical 说法作为固定来源快照，未作当前外部核验。

合成 Probe 不证明真实模型已经校准或 evaluator 已受安全认证；supplied TruthLabel comparison 不证明现实答案正确。此本地树没有网络、签名、PBFT phases、quorum safety 或 n/3 容错保证，也不证明 secure sandbox 或实际 distributed consensus。Python 3.10+ 为目标环境，没有该版本实际运行声明；60 分钟及各关时间尚未真人校准。

P1 当前限值为 0.15 秒。固定完整组慢版三次为 2.089669、2.736338、2.203572 秒，参考版为 0.014413、0.015047、0.013903 秒；两侧余量分别为 13.93112 和 9.96901。2,400 个合成本地 Ballots 的完整 Proposal/Probe、canonical keys、support/abstentions、source-style legacy scores、exact D 与 dispersion_alert 全部保留，D 的独立 closed-form expected 为 ones×zeros。fixture 与独立 expected 在 timer 外，整个 ConfidenceDesk.inspect 与完整 Inspection equality 在 timer 内，之后才读 elapsed；不能删 zero/abstention、只求 extreme gap、裁 records 或预填 report。六份 NEW 完整测量副本只把 timingassert 换成实际 elapsed 输出，慢版另枚举所有真实 unordered confidence pairs；全部业务 guards 和全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为与正式检查有各自验收记录，不能由测量版推定；本机测得余量受运行环境影响，不构成通用墙钟上界或生产 SLA。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
