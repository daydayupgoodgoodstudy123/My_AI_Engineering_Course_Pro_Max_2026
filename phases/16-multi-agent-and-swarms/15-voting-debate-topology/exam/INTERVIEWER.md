# 面试官手册：CorrJury（16/15）

候选人计时期间不要看。候选人使用英文 README、`corrjury/` 和 `tests/`；主持人以实际 docstring、测试和 typed records 为合同。本手册是原创练习评分，不是公司或官方认证标准。

## 开场（2 分钟）

说明总时长 60 分钟，编码 58 分钟：Part 1–5 分别 12、11、15、10、10 分钟。请候选人边做边说，随时澄清，可以查 Python 官方文档。目标是让测试原样满足合同；不以是否全部完成代替具体观察。

按顺序每次解除一个 skip，保留之前的测试。记录每关解锁时间、首个完整结果、运行次数、澄清问题和提示等级。主持人不代写代码；卡住约 4–5 分钟时从 H1 开始，一次给一级。时间分配没有真人校准，提示后完成与独立完成分别记录。

服务完全本地模拟。来源以独立 agent 抽签、线性 tally 和常量概率比较演示拓扑；共享 family、integer tickets、declared read cost、精确分布和嵌套组合是本题显式适配。不要把来源打印的 Takeaways、论文描述或年份当作本题已核验事实。

## 澄清问题的标准答案

只在问到时回答，用英文说。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | 相同错误标签是否自动表示相关？ | "No. In this local model, one declared family shares one actual draw and outcome. Different families are independent." |
| 1 | 每个 seat 需要独立 ticket 吗？ | "No. Keep every declared seat, but all seats in one family retain the same actual draw ordinal and outcome." |
| 1 | ticket 的合法范围是什么？ | "The supplied roll is an integer in [0, probability.denominator). Do not draw again or change replay order." |
| 1、3 | 多数票与可靠性是什么关系？ | "Part 1 classifies one observed odd-seat sample. Part 3 computes the exact probability of a strict majority from the full law." |
| 1、2、5 | reader/sender 要验证成网络端点吗？ | "No. They are opaque declared cost labels. Charge the declared token exposures using the separate read rate." |
| 2 | 存试验历史还是当前配置？ | "One save replaces the complete current configuration snapshot. Preserve family and exposure declaration order." |
| 2 | 需要自己写 Fraction、Decimal 或原子写文件吗？ | "No. Exact scalar codecs and atomic UTF-8 JSON snapshot I/O are supplied. You own complete domain field modeling." |
| 3 | 同 family 的三票是否是三次 Bernoulli？ | "No. That family contributes either zero or all three correct seats. Independent family kernels are then convolved." |
| 3 | 空 convolution 和零概率质量如何处理？ | "The empty convolution is unit mass at zero. Keep every support position, including exact zero entries." |
| 3 | read exposure 会改变成功概率吗？ | "No. It changes declared cost, while the fixed family probabilities and seat model determine the law." |
| 4 | 可以重抽样或重算 tally 吗？ | "Project the completed report's own evidence. Canonical family outcomes, scalar rendering, TSV quoting and async publication are supplied." |
| 5 | 两个分支用了相同 family，如何合并？ | "Add their integer seat multiplicities into one global family block, then invoke the repaired Part 3 solvers for that layer." |
| 5 | 可以只保留 family 集合或乘 child probability 吗？ | "No. A set loses seat weight, and child success probabilities are not a substitute for the parent's joint seat law." |
| 5 | 需要实现循环检测或名称解析吗？ | "No. The supplied catalog expands a finite unique ordered node tree and binds declared global family profiles. Every assembled subtree has a positive odd seat total." |
| 全部 | 这是实际模型精度或费用评测吗？ | "No. These are finite local simulated observations and declared cost rates. Performance evidence is limited to the recorded local fixed workload; human interview timing is uncalibrated." |

## 每关：主要坑、观察、提示、追问

### Part 1 修 sampled jury（12 分钟，20 分）

四层职责按实际调用逐步出现：

1. `draw_family_trial` 对每个 seat 抽签，破坏同 family 共用真实 ticket 的合同。错误在 producer 之外两次调用的 `JuryDesk.record → seal_sample → require_shared_family_draw` 才以 `ValueError` 暴露；consumer 本身正确，不应绕过它。
2. 正奇数票的胜出阈值是 `N // 2 + 1`。五票中两票正确仍然失败，不能把向下取整的一半当多数。
3. generation 与 reading 是两项独立声明费用。generation 由各 family 的 seats×generation_tokens 计，reading 由每条 exposure 的 tokens 计，分别用自己的 rate，再精确相加。
4. `ticket_outcome` 构造 denominator 长的完整 RIGHT/WRONG deck 后选真实 roll。应保留同一个合法整数 roll 的 exact category，同时避免构造整个 deck；不能改 RNG、缩减配置或固定结果。

观察：候选人是否从合法 consumer 回查生产者；是否保留每张票与 draw ordinal；是否能解释整数区间边界；是否先保证完整输出再分析成本。`seat_ids`、ticket stream、seal、money helpers、service orchestration 和独立 expected 都是完整 Given；这里不要求概率 kernel。

提示：

- H1："Which producer first violates the evidence consumer's contract?"
- H2："Compare draw ordinals within a family, then separate observed majority, generation and reading."
- H3："One draw belongs outside the seat loop. For a legal roll, locate the successful integer interval without materializing the ticket deck."

追问：

- "Why do equal error labels fail to establish correlated correctness?"（标签相同不改变独立抽样机制；共享 latent 才明确联动。）
- "What must remain identical after the ticket optimization?"（RNG 消耗、roll、family/seat 关联、全部报告与费用。）
- "Does declared reading cost demonstrate coordination latency?"（只证明这个本地费用模型，未建网络或上下文质量模型。）

### Part 2 完整 JSON 配置快照（11 分钟，20 分）

主要坑：

- family 是有 seat multiplicity 的独立声明块；保存 UID、exact probability、seats、generation_tokens，不能把一个 family 拆成多份独立来源，也不能重开后一律设成一票。
- 每条 exposure 的 UID、reader、sender、tokens，以及 generation/read 两个不同 rate 都属于配置。相同 opaque labels 可以对应不同 exposure allocations，均需保留；字段必须与所属记录关联，不能只存“够算一个样例”的摘要。
- 保留 family 和 exposure 声明顺序，close 后用新 archive 重开；一次 save 替换当前完整 snapshot，不能把两份配置混合。

观察：是否先列领域字段再接 Given codecs/driver；是否用真实重开检查完整 equality。`Fraction`/`Decimal` 字符串编码、UTF-8 JSON、原子替换、close 和配置校验均有完整实现。精度与中文／制表符是集成护栏，不把通用 JSON 写入当主要算法。

提示：

- H1："What would be lost if this file only stored probabilities?"
- H2："List every FamilySpec, ReadExposure and JuryConfig field with its order and owner."
- H3："Build ordered family and exposure records using the supplied scalar codecs, and reconstruct the same typed configuration after reopening."

追问：

- "Why store both generation and read rates?"（职责不同，混用会给出结构正确但费用错误的结果。）
- "Is a snapshot a replay history?"（这里一次保存是一份完整当前配置，没有 trial lineage 或历史日志合同。）

### Part 3 精确 family law（15 分钟，25 分）

三个独立 TODO：

1. `family_mass_kernel`：k 席共享 family 的质量只在 0 和 k；其余位置保留精确零。把 seats 当独立 Bernoulli 会改变模型。
2. `convolve_family_mass`：独立 family 的联合质量相乘，正确票数下标相加，再累加到完整支持；空输入是 `(Fraction(1),)`，deterministic family 也保留固定席位与完整支持，不裁掉零位置。
3. `exact_majority_reliability`：验证长度 N+1、非负 exact Fraction、总质量为 1；从严格多数阈值起求尾和，返回完整 distribution、配置身份和修好的独立 cost。

测试真的先由 Part 1 生成 sampled report，再由 Part 2 关闭／重开它的 config。P1 的一次 observed tally 不提供精确可靠性；`Fraction`、records 与配置校验是 Given，kernel、convolution、tail 都需候选人写。

观察：是否先说出随机变量的单位，再写循环；是否区分 family 内完全共享与 family 间独立；是否以完整分布而非单个成功数验证。三票同 family、p=1/3 时可靠性仍为 1/3；三个独立一票 family 时为 7/27。

提示：

- H1："What values can one perfectly shared family contribute to the correct-seat count?"
- H2："For two independent partial counts, where does their joint probability belong?"
- H3："Place 1-p at zero and p at the whole family seat count; convolve by adding indices and multiplying masses, then sum only counts at or above N//2+1."

追问：

- "Why does adding reading leave reliability unchanged here?"（固定 law 未变；费用模型单独依赖 exposures。）
- "What fails if family errors are only partially correlated?"（两点 kernel 不再适用，需要明确 joint model，不能由当前模型推出真实相关性。）
- "How would seat count affect exact convolution cost?"（支持长度随总席位增长；当前有限域未承诺任意规模性能。）

### Part 4 已完成 trial 的 TSV 投影（10 分钟，15 分）

主要坑：

- trial ID 与 config UID 各自有含义；每一条都绑定自己的已完成 report，不能把配置身份当作试验身份。
- 发布 observed correct_seats、total_seats、passed，包括失败 trial；使用 Given canonical family outcomes，不重抽样或重算分类。
- generation、reading、total 三列互不替代，最后保留真实 `simulated` 标记。十列顺序以测试 parser 为准。

观察：是否直接沿 report 的字段投影；第二条记录和失败记录能否保留自己的数据。TSV quoting、cost rendering、async 拉取／发布／关闭均是完整 Given。测试覆盖制表符与 close，但不把 cadence、escaping 或相关性算法算作本关主要工作。

提示：

- H1："Which completed object owns each output column?"
- H2："Compare trial versus config identity, observed tally, and the three separate costs."
- H3："Return ten fields in parser order, using canonical_outcome_field and cost_field around the report's own evidence."

追问：

- "Why publish simulated=True?"（保留证据性质，避免把本地抽样当外部观测。）
- "Where should resource cleanup belong?"（Given publisher 的 finally；投影只处理领域字段。）

### Part 5 nested joint-family model（10 分钟，20 分）

主要坑：

- 每层 own allocations 和所有 child 的 family_counts 按全局 family UID 累加整数权重；相同 family 跨分支仍是同一个 shared cause。用 set 去重丢席位，覆盖 child 计数也会改变模型。
- 先构造该层完整 flat config，再调用修好的 P3 kernel、convolution、tail；不能把 child 成功概率相乘或把 children 的票看成独立多数结果。
- 保留每层 path、ordered children、config、full distribution 和 cost。没有 own seats 的协调层仍有自己的 path/config/audit；read exposures 按 own 在前、随后 children 顺序递归合入，并复用正确的 cost 依赖。

观察：是否能解释父层 4+3=7 个 seats 和两个全局 family；是否真的复用 P3 而非写第二套概率算法。catalog 的 UID lookup、finite unique tree expansion、路径构造和 profile-to-config binding 完整 Given；候选人负责 multiplicity aggregation 与 nested law assembly，不负责通用 short-name、DAG occurrence 或循环校验。

提示：

- H1："What is the random cause shared by these two branches?"
- H2："Combine integer seats per family before asking for this layer's law."
- H3："Audit children first, add their family_counts to own allocations, concatenate own/child reads, build the flat config, and run the three Part 3 functions for this layer."

追问：

- "Why is union insufficient?"（同 family 的一席加三席变四席；identity 相同不代表权重消失。）
- "Why can a parent differ from the product of child reliabilities?"（父层对全部 seats 做 strict majority；shared causes 和判定事件均不同。）
- "Does this audit verify a real debate topology?"（只核对声明的有限 shared-cause model，不证明真实协作收益。）

## 记录与评分（100 分）

按实际观察给分，每格注明代码位置、行为或断言证据。未观察到写“未观察”，不从参考答案推断候选人能力；提示等级、沟通和用时另记。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | 每 family 一个实际 draw，保留全部 seats 与 provenance | 6 | |
| 1 | observed 正奇数 strict majority | 4 | |
| 1 | generation/read 分开精确计费并保留 exposures | 4 | |
| 1 | exact ticket 边界与等价完整回放，避免 denominator deck | 6 | |
| 2 | 完整 ordered family 字段与 multiplicity | 8 | |
| 2 | 完整 exposures 与独立 rates | 6 | |
| 2 | 替换 snapshot、close／reopen 与完整关联 | 4 | |
| 2 | 正确集成 Given exact codecs | 2 | |
| 3 | shared-family 两点 kernel 与零支持 | 8 | |
| 3 | 独立 family convolution、下标与 neutral law | 9 | |
| 3 | 完整 unit-mass 校验和 strict-majority tail | 6 | |
| 3 | 真实 reopened config 与 corrected cost 关联 | 2 | |
| 4 | own trial/config identity 与 Given outcome | 5 | |
| 4 | actual correct/total/passed，含失败记录 | 4 | |
| 4 | 三项 own costs 与 simulated 标记 | 6 | |
| 5 | own/child 全局 family 整数权重累加 | 8 | |
| 5 | 每层真实 model 构建与 P3 law 复用 | 6 | |
| 5 | path 与 ordered child audits 完整 | 3 | |
| 5 | own/descendant exposures 与正确 cost 依赖 | 3 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

静态清点：42PY、五测试、36 assert、1 raises、五锁和26个登记错误写法。P1 sampled strict majority 与 P3 exact majority tail 都是候选人职责；P4 使用 Given tally，P5 复用 P3。

128 个真实不同概率配置×3 seats 的完整 `JuryDesk.record_many` 与整个 `BatchReport` equality 都在计时内，fixture 和独立 Random/Fraction expected 在外。限值 0.04 秒；独占连续三慢为 0.401299125、0.408559500、0.405123583 秒，三快为 0.002162083、0.002134875、0.002089166 秒，慢／限值最小 10.03248 倍、限值／快最大值 18.50068 倍。

六份完整测量副本五关功能均通过：仅把 timing assertion 换成实际 elapsed 输出，慢版另外使用真实完整 ticket-deck 映射；不表示慢版满足原限值。未改动测试的完整参考五关也已通过。当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错误写法与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。

这些有限本机数据不构成任意环境墙钟上界、生产 SLA、真实模型准确率或供应商费用证明；60 分钟安排未经真人校准。
