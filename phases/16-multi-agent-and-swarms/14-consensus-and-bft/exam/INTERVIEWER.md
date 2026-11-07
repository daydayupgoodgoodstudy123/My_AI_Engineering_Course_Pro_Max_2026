# 面试官手册：RobustCenter（16/14）

候选人计时期间不看本手册。候选人使用英文 README、`robustcenter/` 和测试，逐关修领域实现，保留全部断言与完整 GIVEN。

## 开场（2 分钟）

- 总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间与难度尚未真人校准，不要求全部完成。
- 请候选人解释当前证据与下一步判断，可以随时澄清、查 Python 标准库官方文档。
- 只解除当前 skip，记录解锁到首次通过的时间、运行次数和 H1/H2/H3。卡住约 5 分钟时一次给一级提示，主持人不代写代码。
- 英文澄清在问到时回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 与本手册。
- 说明 confidence/probe/truth 都来自合成本地 fixture，无真实模型校准或网络。agreement、supplied truth comparison 与 distributed security 是不同证据边界。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | Are scalar and percent the same unit? | No. Preserve the parsed signed Decimal and its canonical scalar or percent unit. Lexical parsing is supplied. |
| 1 | Does an abstention lose its probe metadata? | No. Keep it in the audit and D diagnostic, but exclude it from answer clusters and the answer-support denominator. |
| 1 | Which confidence determines support? | The actual declared Probe.confidence, not proposal self-confidence or member counts. Equality at the threshold accepts; zero eligible mass rejects. |
| 1 | What does D measure? | The exact sum of absolute confidence gaps over all unordered probe pairs, with multiplicity. It is a local inspection diagnostic, not an answer center. |
| 2 | Does save append a retry revision? | No. Replace one run with the supplied complete ordered snapshot. Distinct proposal UIDs from one agent remain separate, with one original probe each. |
| 2 | Must I implement SQL transactions or rational encoding? | No. Complete schema, atomic per-run replacement, ordered rows and exact codecs are supplied. Model all proposal and actual probe fields. |
| 3 | What is returned at exact half mass? | The complete minimizer interval between adjacent positive-mass positions, not just its lower endpoint. Ignore zero-mass positions. |
| 3 | How is one center chosen? | Use the requested lower, upper or exact midpoint policy. Exact arithmetic helpers are supplied. |
| 3 | Does a proposal exactly at radius count? | Yes. Include its positive confidence mass; minority UIDs retain original declaration order. |
| 3 | Does accepted imply true? | No. The supplied independent truth comparison is separate. An absent truth label stays None. |
| 4 | Which fields are my projection responsibility? | Seven own proposal fields: kind, UID, agent, raw answer, signed position, unit and self-confidence. Compose them beside the supplied actual probe payload. |
| 4 | Do I classify abstentions or implement length framing? | No. Complete typed observation, numeric primitives, probe binding/projection, UTF-8 framing and async lifecycle are supplied. |
| 5 | Which state is authoritative for an edge? | The sealed decision of its current owning core, including sealed epoch, center/unit and accepted status. |
| 5 | Must an edge inherit its CoreGroup's declaration findings? | No. Audit core declarations and edges independently against the authoritative sealed state. A matching edge can remain clean. |
| 5 | What causes edge-before-core? | Only a sealed decision whose accepted flag is false. Edge echoes cannot make that core accepted. |
| 5 | Does a child use its parent's sealed decision? | No. Each child core has its own sealed decision and ordered own-edge audit. Preserve the nested reports. |
| 5 | Must I recompute evidence admission or truth? | No. Original evidence admission, reference binding and the real Part 3 sealing pipeline are supplied. Edges add no voting mass or truth verdict. |

## Part 1：signed cluster、abstention、mass 与 D（目标 12 分钟）

四层缺陷：

1. canonicalize_proposal 删除负号，将相反 signed claims 错分为同 key。正确 ConfidenceDesk.inspect→validate_cluster_members→require_equivalent 在 producer 外两次调用后自然 ValueError；修 key producer，不改正确 member/unit consumer。
2. ABSTAIN 的非零 probe 被当作 answer cluster 与分母质量；应只保留 audit/abstention 记录，不给 answer support。
3. threshold 误按人数比例，而非 declared confidence mass。即使人数多数，也可能质量低；按 winning_mass≥threshold×eligible_total，total=0 不接受。
4. D 逐对枚举全部 unordered confidence pairs。保持同一个 exact D，排序后用 prefix sums 汇总，完整 Inspection 仍返回所有字段。

看什么：是否区分 signed scalar、ABSTAIN、confidence mass 与 confidence dispersion。完整 numeric_parts、ballot intake、equivalence consumer 和 source-style legacy scorer 已正确 GIVEN。D 的成员域含所有 probe metadata，包括 zero 与 abstention，并保留重复；它是本地诊断，不能调用 P3 solver 求一个中心替代。

P1 当前限值为 0.15 秒。固定完整组慢版三次为 2.089669、2.736338、2.203572 秒，参考版为 0.014413、0.015047、0.013903 秒；两侧余量分别为 13.93112 和 9.96901。2,400 个合成本地 Ballots 的完整 Proposal/Probe、canonical keys、support/abstentions、source-style legacy scores、exact D 与 dispersion_alert 全部保留，D 的独立 closed-form expected 为 ones×zeros。fixture 与独立 expected 在 timer 外，整个 ConfidenceDesk.inspect 与完整 Inspection equality 在 timer 内，之后才读 elapsed；不能删 zero/abstention、只求 extreme gap、裁 records 或预填 report。六份 NEW 完整测量副本只把 timingassert 换成实际 elapsed 输出，慢版另枚举所有真实 unordered confidence pairs；全部业务 guards 和全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为与正式检查有各自验收记录，不能由测量版推定；本机测得余量受运行环境影响，不构成通用墙钟上界或生产 SLA。

提示：

- H1: "Which key did this signed member receive before the correct equivalence check?"
- H2: "Is this an answer, and does admission use confidence mass or head count?"
- H3：保留 Decimal sign/unit，排除 ABSTAIN answer mass，用 inclusive mass threshold，再以排序 prefix sum 计算完整 all-pair D。

追问：

- "Why does a zero-confidence observation still matter to D?"（它与其他 confidence 的 gap 仍是声明的 pair，不能从诊断域删除。）
- "Is this D the source's geometric-median algorithm?"（不是；D 是本地 Inspection 诊断，source 只有簇内 confidence median 距离启发式。）

## Part 2：per-run proposal/probe snapshot（目标 11 分钟）

主要坑：

- 保存每个 run 的完整 ordered snapshot，保留所有 UID/raw answer/agent/kind/self-report。同 agent 的不同 UID 不能按 agent 去重；zero probe mass 不删除原 audit record。
- Probe 的 proposal_uid/probe_uid/confidence/evaluator/assessment 全取实际 q 字段；probe_uid 也取实际记录，不能假定命名格式；不能用 self-confidence 代替 probe confidence 或串用 evaluator/assessment。
- close/reopen 后按 ordinal 恢复同一对 Proposal/Probe；replacement 只影响目标 run，其他 run 保留。

看什么：是否真实建模两类领域字段并保持关联。schema、原子事务、SQL order 与 Fraction codec 完整 GIVEN；精度和 None answer 是依赖集成护栏，不考手写数值 codec。合同是每次输入的完整 snapshot、每 proposal 一个原始 probe，不推断 retry lineage 或多 probe 历史。

提示：

- H1: "Which fields belong to the proposal and which to its actual independent probe?"
- H2: "Did same-agent distinct UIDs and their ordinal association survive reopening?"
- H3：枚举完整 snapshot，按同一 ordinal 分别建 Proposal/Probe rows；使用各自真实字段与给定 codec，load 按原序重建，不按 agent 合并。

追问：

- "Does replacing a run retain unprovided historical snapshots?"（不保证；当前 run 就是本次完整输入，其他 run 独立保留。）
- "Why retain both self-confidence and probe confidence?"（两者是不同 provenance 字段，自报不能伪装成独立 evaluator evidence。）

## Part 3：weighted interval、tie 与 radius support（目标 15 分钟）

三个独立 TODO：weighted_median_interval、choose_interval_center、audit_center_support。

主要坑：

- positive confidence mass 决定一维 sum(weight×distance) 的完整最小化区间；不能按位置 mean 或无权 middle，zero mass 即使在 interval 内部也不决定端点。
- 累积质量恰好一半时保留相邻 positive positions 的 interval，再按请求选 lower/upper/midpoint，不能总取某端。
- radius 支持按 positive mass 求和，边界包含；minority 用原声明序的正质量 UIDs，不能数人头或重新按位置排序 minority。

看什么：是否消费 P2 close/reopen→P1 inspect→positions_from_inspection 的真实结果，并分别实现三项算法。exact scalar arithmetic、comparable-unit intake 与独立 evaluate_truth 完整 GIVEN；缺 truth 为 None，accepted 与 truth 分开。合法域为有限 Decimal positions、nonnegative Fraction weights、同单位、radius≥0、threshold∈(0,1]，total 必须正，不扩大任意对象校验。

提示：

- H1: "Where does the positive cumulative mass reach or cross one half?"
- H2: "Is that a full minimizer interval, and which tie policy was requested?"
- H3：先剔除 zero mass 并按位置累计 exact weight；保留 half-mass interval，再独立选点与做 inclusive-radius mass/minority audit，truth 交给正确 helper。

追问：

- "Can the same interval admit different support under different chosen points?"（可以，选择策略与 radius 决定支持质量，median minimization 本身不保证 threshold 通过。）
- "Why isn't agreement a truth test?"（一致性只描述这些 declared positions，truth 由另给 label 比较，仍不证明现实正确性。）

## Part 4：七个 own proposal 字段（目标 10 分钟）

主要坑：

- UID、agent、kind 各用本 proposal 值，不能把 UID 当 agent 或串到另一提案。
- raw answer 与 normalized signed position 同时保留，不能拿数值文本覆盖原 answer，percent/scalar unit 不能混用。
- self_confidence 是原 proposal 的自报字段，使用精确 primitive；与给定 probe payload 并列，不替代 actual Probe。

看什么：是否实现七个真实 own fields，再组合完整 probe_payload。typed classifier、原 probe binding、numeric_fields/fraction_pair、ABSTAIN projection、probe字段、4-byte framing 和 async driver 都 GIVEN。UTF-8 length、close 与 non-voting probe metadata 是依赖集成护栏，不考 cadence/字节数/来源分类修复。

提示：

- H1: "Which actual proposal owns these seven fields?"
- H2: "Are the original answer and signed normalized position both preserved?"
- H3：直接取 proposal identity/kind/raw answer/self-report，数值与单位用完整 helper，再展开真实 probe_payload；classifier/frame/driver 保持给定实现。

追问：

- "Why expose raw text beside numeric position?"（canonicalization 用于计算，原文用于审计；两者用途不同。）
- "Does a nonzero abstention probe create a numeric answer?"（不产生；完整 public view 保留非投票 probe evidence，并给出无 numeric claim。）

## Part 5：nested sealed Core/Edge audit（目标 10 分钟）

主要坑：

- 递归构造每层 CoreAudit/EdgeAudit 与 ordered children，各 child 从 catalog 取自己的 sealed result，不能借 root decision 或 flatten 掉层级。
- core declaration 的 epoch、claimed center/unit 对照 own sealed；accepted=False 单独形成 core-not-accepted。
- own edge 的 core_uid 对照当前所属 core，epoch/value 对照其 authoritative sealed。wrong-parent/stale/wrong-value 各自报告，不借另一个 core 的 ack 作当前跟随。
- edge 与 core declaration 分别审计；匹配 sealed 的 edge 不继承 group 的 core-epoch/core-value。edge-before-core 仅由 sealed.accepted=False 触发。

看什么：是否尊重 authoritative sealed 与 declared snapshot 的区别，保留所有 own reports。complete catalog/reference validation、original evidence admission 与调用真实 P3 的 seal_core 都 GIVEN；edge-reference 用完整 helper。edges 没有能再累加的独立 mass，不重算 median/support/truth，也不以 edge 数量修正 rejected core。

提示：

- H1: "Which sealed decision is authoritative for this current core and its own edges?"
- H2: "Does this mismatch belong to the core declaration, the edge, or the sealed admission flag?"
- H3：每层取 own sealed，分别检查 core epoch/value/admission 与 edge parent/sealed epoch/value/reference；edge-before-core 只看 sealed.accepted，再递归保留 children。

追问：

- "Can a clean edge coexist with core declaration findings?"（可以，edge 匹配 sealed 即可；current group 的错误声明不自动改写 edge 的审计依据。）
- "Can following edges make a rejected core accepted or true?"（不能；sealed admission 和 truth 都来自已封口的原 core/P3 结果。）

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层 inspection 与 D | 20 | signed/unit key 6；ABSTAIN 4；confidence-mass threshold 4；同值 exact D 与完整业务路径 6 |
| 完整 proposal/probe snapshot | 20 | 完整 ordered UID/Proposal fields 8；actual Probe fields/关联 8；per-run replacement/reopen 4 |
| weighted center 算法 | 25 | positive-mass full interval 10；显式 tie policy 5；inclusive radius mass/minority 10 |
| own proposal evidence | 15 | UID/agent/kind 4；原 answer 3；signed position/unit 5；self-report 3 |
| nested Core/Edge audit | 20 | own sealed core declaration 6；edge parent/sealed epoch/value 7；ordered nested reports 5；reference/admission helper 集成 2 |

按实际代码、测试现象或口头推理评分：完整满足得满分，有具体反例的部分实现得部分分，未实现或未观察得 0。提示、用时和运行次数另记，不把参考结果算作候选成绩。

当前题包为 14 candidate/14 reference modules、45 Python 文件、5 tests、37 assert、1 raises、5 skip、26 登记错修。60 分钟及各关时间未真人校准。P1 当前限值为 0.15 秒。固定完整组慢版三次为 2.089669、2.736338、2.203572 秒，参考版为 0.014413、0.015047、0.013903 秒；两侧余量分别为 13.93112 和 9.96901。2,400 个合成本地 Ballots 的完整 Proposal/Probe、canonical keys、support/abstentions、source-style legacy scores、exact D 与 dispersion_alert 全部保留，D 的独立 closed-form expected 为 ones×zeros。fixture 与独立 expected 在 timer 外，整个 ConfidenceDesk.inspect 与完整 Inspection equality 在 timer 内，之后才读 elapsed；不能删 zero/abstention、只求 extreme gap、裁 records 或预填 report。六份 NEW 完整测量副本只把 timingassert 换成实际 elapsed 输出，慢版另枚举所有真实 unordered confidence pairs；全部业务 guards 和全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为与正式检查有各自验收记录，不能由测量版推定；本机测得余量受运行环境影响，不构成通用墙钟上界或生产 SLA。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
