# 面试官手册：CreditEcon（16/21）

候选人计时期间不要看。候选人使用README、`creditecon/` 与 `tests/`，合同以实际typed records、docstring和测试为准。这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

总计60分钟，编码58分钟：Part 1–5分别12、10、16、10、10分钟。请候选人边做边解释，随时澄清，可以查Python官方文档。逐关解除skip，之前的测试继续保留；按实际行为与证据评分。

主持人记录解锁时间、首次完整结果、运行次数、问题与提示等级。卡住约4–5分钟后从H1开始，一次给一级；独立完成与提示后完成分开记。真人难度／用时尚未校准。

来源exact／sampled已正确使用每次排列的空联盟起值，second_price也已正确；本题P1错误是本地教学回归。来源Reputation只有per-use EMA和floor，没有独立确认receipt、slashing或wall-clock decay。本题criteria／receipt、Fraction账目、SQLite、sample blocks与nested teams是明示本地适配；来源输出文件只作DATA静态读取。讲义实验、当代网络／协议／法律说法未在本题核验。

## 澄清问题的标准答案

候选人问到时，用英文回答。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | P1要先实现Shapley吗？ | "No. P1 consumes externally supplied credits and replays utility observations. It does not allocate players; the three allocation algorithms belong to P3." |
| 1 | v(empty)就是baseline字段吗？ | "Not always. Criteria with an empty required set also contribute. Use the actual empty-coalition value, and preserve signed grand-minus-empty surplus." |
| 1 | 首个异常是否应在consumer吞掉？ | "No. The publication consumer correctly rejects a nonzero residual. Follow the statement back to its producer and keep that consumer contract." |
| 1 | 平价、单个bid怎样处理？ | "The first declared highest bidder wins and pays the second-highest amount. Fewer than two bids means no sale." |
| 1 | confirmed是否代表真实身份或密码学验证？ | "No. It is declared independent local evidence. Only confirmed quality enters this per-use EMA; unconfirmed receipts leave the score unchanged." |
| 1 | 0或负utility能否当missing？ | "No. Both are valid exact values. Coalition identity is set-valued and observations belong to one immutable game." |
| 2 | Fraction／Decimal codec要自己写吗？ | "No. Exact scalar/container encoding and the atomic SQLite row resource are complete Given. You own domain row association, order, replacement and typed reconstruction." |
| 2 | unconfirmed receipt要过滤吗？ | "No. Store its status and all other fields as observed. Persistence does not apply another quality gate." |
| 2 | 相等observation可以去重吗？ | "No. Preserve every ordered occurrence, all permutations and all domain fields. Saving replaces the complete snapshot." |
| 3 | exact是简单把singleton value平分吗？ | "No. Compute every player's weighted before-and-after subset marginal and retain every evidence term, including zero and negative contributions." |
| 3 | samples为0、players为空合法吗？ | "Yes. Zero completed samples yield zero estimates and the actual residual. A zero-request, zero-completion sampled report is approximate but not partial; partial means completed is less than requested. An empty roster also has a valid empty exact allocation." |
| 3 | 能平均各block的mean吗？ | "No. Combine marginal totals and divide by the actual number of completed full permutations. Requested work is metadata, not evidence." |
| 3 | sampled总和balanced就等于exact吗？ | "No. Complete permutation marginals telescope to the surplus, but each player's estimate remains approximate. Preserve mode, requested, completed and partial metadata." |
| 4 | exact也除completed吗？ | "No. Exact block totals are already credits. Sampled blocks use actual completed count, with zero estimates when no permutation completed." |
| 4 | 负credit、unit和quantum怎么处理？ | "Retain each agent's signed exact values and the declared synthetic unit and quantum scale. CSV publication performs no payment and no new receipt gate." |
| 5 | 每层players是所有primitive吗？ | "No. They are that Team's direct child UIDs. Its value for selected children is the original primitive game's utility at their primitive-member union." |
| 5 | 两branch共享primitive是否算两次？ | "No. Evaluate the set union once. Keep each child as a distinct local player and explain only the newly introduced primitive members." |
| 5 | 可以求primitive Shapley再按组相加吗？ | "No. That generally differs from the declared direct-child game. Reuse the repaired P3 exact solver on each actual local team game." |
| 5 | UID去重证明现实Sybil-proof或Owen value吗？ | "No. This is a declared finite identity model and a specific nested team game. It proves neither real identity uniqueness nor an Owen-value allocation." |
| 全部 | 是真实token收益或投资事实吗？ | "No. Bids, credits, denominations and observations are synthetic exact data. There is no external transfer, chain, market result or investment claim." |

## 每关：主要坑、观察、提示、追问

### Part 1 supplied credit与utility replay（12分钟，20分）

四层按真实调用暴露：

1. `efficiency_report`把grand value当surplus，非零空联盟的合法外给credits因此产生错误residual。调用链是 `efficiency_report → publish_statement → residual_check`；producer外两次调用后，正确consumer自然抛ValueError。应修报告，不改consumer或伪造credits。
2. `second_price_payment`取最高bid作为charge。保stable first-highest winner，charge取second-highest；少于两个bid仍无sale。
3. `update_reputation`接受self-report且忽略确认状态。unconfirmed直接保current，confirmed才把receipt.quality带入 `max(floor, alpha*current+(1-alpha)*quality)`。这是唯一的本地质量gate，不扩成P2/P4策略。
4. `CoalitionOracle.value`对相同immutable game的相同coalition重复调用完整utility evaluator。正确优化仍须产生所有ordered receipts和total；缓存作用域属于本Oracle绑定的Game，即使external UID相同，changed content的新binding也不能借值。0／负值是合法命中，成员重复按set归一。

观察：能否从correct residual consumer回溯producer，分清supplied allocation与求解器；是否保留signed surplus、confirmed quality和完整replay。完整Given提供game／coalition intake、真实criterion evaluator、publication consumer与replay，不提供Shapley allocator。

提示：

- H1："Which producer made the correct publication consumer reject otherwise balanced supplied credits?"
- H2："Separate surplus, second-price charge and confirmed quality. Then inspect repeated exact coalition observations within one immutable game."
- H3："Use grand minus actual empty value; keep the first highest winner and second-highest charge; update only confirmed quality; reuse the exact game-owned receipt for equal coalition sets without dropping replay rows."

追问：

- "Why can empty-required criteria change the efficiency target?"（它们属于每个coalition，包括v(empty)，不能只减baseline字段。）
- "Why is a negative surplus still publishable?"（合法外给signed credits可以精确平衡负surplus；clamp会改合同。）
- "What must remain inside the timed replay?"（完整CreditDesk.replay、全部ordered receipts／contributions／total及whole-report equality；fixture与独立expected在timer外。）

### Part 2 complete SQLite accounting（10分钟，20分）

主要坑：

- 保存Game UID／players／baseline和全部ordered criteria；每条observation保game、coalition、value及完整criterion contributions，重复相等的occurrence也保留。
- permutations、QualityReceipt各字段、signed allocations、Efficiency各独立字段都有关联。grand total与surplus分列，不能存成同一个值，也不能从self-report重建confirmed quality。
- save完整替换旧snapshot；后次空observations／permutations／receipts要移除先前rows。close／reopen重建完整typed records与unit／Decimal quantum scale。

观察：candidate负责 `AccountingArchive.save/load` 的domain mapping与重建。完整Given提供Fraction／Decimal／tuple／frozenset codec和SQLite atomic row replace／ordered read／close；精度codec不是候选人新算法。P2保存unconfirmed状态，不再判定是否奖励；不声称分布式exactly-once或真实资金账本。

提示：

- H1："Which domain records and repeated occurrences belong to the complete snapshot?"
- H2："Keep game, observations, permutations, quality, credits and statement fields separate, and preserve their declared order through replacement."
- H3："Map every typed field to ordered rows through RowDriver, then reconstruct Criterion, Game, UtilityReceipt, ReplayReport, QualityReceipt, Efficiency and AccountingSnapshot, retaining unit and Decimal quantum."

追问：

- "Why retain an unconfirmed receipt?"（持久化记录观察事实；是否更新声誉由P1的独立gate负责。）
- "Why not rebuild surplus from grand on load?"（它们是独立domain字段；完整snapshot不能丢掉空联盟与已供应statement。）

### Part 3 三个allocation算法（16分钟，25分）

三个独立TODO：

1. `shapley_exact`对每个player枚举其他players的全部subsets，计算 `|S|! (n-|S|-1)! / n!` 与 `v(S+i)-v(S)`，累积signed credit并保完整Marginal evidence。不能忘before、错factorial、clip负值或省掉null terms。
2. `shapley_sampled`每次从原声明roster建立fresh list，使用同一条调用方Random流shuffle；从actual empty起步逐个求marginal，累计每人total并保全部completed full permutations。不能重用上次打乱的list而改变seed轨迹，也不能把未完成request记作证据。
3. `allocation_report`对sampled blocks先合计totals再除actual completed总数；one exact block保持exact credits。报告requested／completed／partial／approximate，并调用修好的P1 efficiency_report。0 completed给零estimate及真实residual；sampled的partial精确为completed<requested，所以0 requested／0 completed仍approximate=True、partial=False，不能把零estimate伪造成balanced proof。

真实整合为P1 observations／statement→P2 SQLite save、close、reopen→restored Game→三个P3算法。完整Given只有same-game／roster／block与full-permutation intake，不提供allocator或averaging solver。常数baseline变化不影响marginals，actual v(empty)仍可能包含empty-required criteria。

观察：是否理解exact weights、单一RNG消费、totals与mean的区别，以及negative／null／synergy／zero samples／empty roster。完成排列的总量telescoping不保证每人估计与exact相等。

提示：

- H1："Which values are marginal evidence, raw sample totals and final credit estimates?"
- H2："Use true before-after subset differences for exact allocation, fresh full seeded permutations for sampling, and actual completion counts for reports."
- H3："Enumerate each player's other-player subsets with factorial weights; accumulate complete-permutation marginal totals using a fresh roster each time; combine compatible sampled totals over total completed, and pass the resulting credits to P1 efficiency_report."

追问：

- "Why does an additive constant leave credit unchanged?"（每个after-before消去相同常数，效率目标也是grand−empty。）
- "Why is averaging block means wrong for unequal block sizes?"（一个sample的证据权重应相同；不同block completed数不能等权。）
- "What does a zero-completion residual show?"（当前没有分配证据；剩余surplus必须如实报告，不能称balanced。）

### Part 4 actual sample-block CSV（10分钟，15分）

主要坑：

- 每个agent／block一行，game和agent来自本条实际对象，total取该agent own marginal total，按声明players序发布。
- sampled credit除该block actual completed，zero completed给0；exact totals已经是credits。negative和null保留精确numerator／denominator，不clamp。
- requested、completed、mode、partial与Given statement.residual对应实际block；unit和quantum保synthetic身份、逗号／Unicode与scale，不造真实payment或第三quality gate。

观察：完整Given提供header、CSV quoting／writer、async publication和sealed block_context／efficiency；candidate实现领域row投影。P4的completed denominator与P3聚合是明确的一对职责，不另把baseline或确认策略当新修复。测试使用独立csv.DictReader读取实际输出。

提示：

- H1："Which agent and actual block own each projected column?"
- H2："Separate raw total from credit, exact from sampled, and requested from completed work."
- H3："Emit each agent's own exact total and credit numerator/denominator, dividing sampled totals by completed only when nonzero; preserve actual mode, partial flag, supplied residual, unit and quantum."

追问：

- "Why does exact mode have no sample denominator?"（exact totals本身已是weighted allocation，除零样本计数没有意义。）
- "Why keep a nonzero residual in a zero-completion CSV?"（输出要表示实际缺证据的状态，不能凭发布动作制造平衡。）

### Part 5 nested direct-child team games（10分钟，20分）

主要坑：

- 真正递归Primitive／Team，为每个node保members和children audits；每个Team的players是own direct child UIDs，保声明序，不把所有primitive平铺成同一个游戏。
- candidate构造本层 `V(selected)=primitive v(selected children的primitive union)`，共享primitive在union只出现一次。调用修好的P3 exact solver与report，不把primitive Shapley分组求和或复制root credits给children。
- 每条actual Marginal转为TeamSupport，保child UID、before children、before members、introduced=`after-before`、after members、signed marginal和weight。overlap中已有primitive不是newly introduced，support值是after−before而非absolute utility。
- 空Team与one-child wrapper都保own local game／efficiency；每层V(empty)是original actual empty value。global UID、typed DAG和cycle intake已完整Given，不另考scoped names或per-parent shared occurrence展开。

观察：实际P1→P2 reopen→P3 primitive exact报告作为P5前关链；P5仍亲自构造membership union、local characteristic callback与support。题中primitive credits为(5,7,6)，root direct-child credits为(10,8)，能直接区分错误的分组相加；signed game另保negative／null child credits和含empty-required criterion的actual empty。这不是Owen value或现实Sybil-proof证明。

提示：

- H1："Who are the players of this specific team game, and what primitive union does a selected child coalition introduce?"
- H2："Build every child's members and audit first, then construct the parent's own direct-child value function before calling P3."
- H3："Use direct child UIDs as local players, evaluate primitive utility on their membership union, run the repaired exact allocator, and explain each returned marginal with before, after-minus-before and after primitive sets."

追问：

- "Why can grouped primitive Shapley differ from team credit?"（改变players与characteristic game会改变可出现的加入顺序和marginal结构。）
- "Why keep b out of left's introduced members after right?"（right已带入b，left此时只新增a；utility仍按完整union求值。）
- "Does a unique declared UID authenticate a real operator?"（没有，输入身份一致性不等于现实身份唯一或抗Sybil。）

## 记录与评分（100分）

每项记录代码位置、实际行为或断言依据；未观察到写“未观察”。提示、沟通和用时另记，不能由参考代码推定候选人完成。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | supplied surplus与正确publication consumer | 5 | |
| 1 | stable second-price charge与no sale | 4 | |
| 1 | confirmed quality、EMA与floor | 5 | |
| 1 | game-scoped完整utility replay与signed observations | 6 | |
| 2 | full Game／criterion／observation领域关联 | 7 | |
| 2 | permutations／receipts／credits／独立statement字段 | 7 | |
| 2 | order／replacement／typed reopen与denomination | 6 | |
| 3 | weighted subset exact solver与完整evidence | 9 | |
| 3 | fresh seeded complete permutations与actual totals | 8 | |
| 3 | completed-block aggregation与真实metadata／residual | 8 | |
| 4 | own game／agent／total与行序 | 4 | |
| 4 | actual completed denominator与signed exact credit | 6 | |
| 4 | mode／partial／residual／unit／quantum | 5 | |
| 5 | recursive members、own local games与children audits | 7 | |
| 5 | direct-child union utility与真正复用P3 exact | 7 | |
| 5 | complete weighted marginal primitive support | 6 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

<!-- VALIDATION_STATUS_BEGIN -->
当前45个PY文件、五测试、44条assert、0处pytest.raises、五锁与25个登记错误写法。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部25项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。

P1真实负载为4 players、1024个meaningful weighted criteria、2400 complete seeded permutations与12000个actual prefix utility requests。完整CreditDesk.replay与whole ReplayReport equality（所有ordered criterion contributions／exact utility／total）都在timer内，fixture与独立expected在外；actual calls诊断保合法观察、key集合覆盖及distinct-key下界。

完整校准三个慢样本为[2.3391742499079555, 2.1870040411595255, 2.210948708001524]秒，三个快样本为[0.028253958094865084, 0.031847041100263596, 0.028866957873106003]秒，当前限值0.26秒，慢侧／快侧余量8.411554／8.164024。六份测量副本仅将timingassert改成elapsed打印，慢版另使用真实criterion重算；全五关功能检查均通过，这不表示慢版通过原时间阈值。原样参考五关另有规定检查记录。局部余量受运行环境影响，不构成通用墙钟上界或SLA；60分钟真人分配未校准。
<!-- VALIDATION_STATUS_END -->

完整Given的codec、intake、driver、consumer与helper不另计独立candidate算法。有限合成游戏的正确性不证明真实市场激励、无条件truthfulness、现实身份真实性、Owen value或真实资金结算；60分钟真人用时未校准。

当前领域覆盖包括ordered permutation与unordered coalition的区别、null贡献的完整weighted evidence、approximate与partial的独立语义、raw marginal total与credit的独立列，以及三名direct-child的实际subset weights和Primitive叶节点自身零玩家游戏的actual empty账目。
