# 面试官手册：SwarmTune（16/19）

候选人计时期间不要看。候选人使用README、`swarmtune/`和`tests/`；以实际typed records、docstring和测试为合同。这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

总时长60分钟，编码58分钟：Part 1–5分别12、10、16、10、10分钟。请候选人边做边解释，随时澄清，可以查Python官方文档。逐关解除skip，之前的测试继续保留，记录具体行为而不只数完成关数。

主持人记录解锁时间、首个完整结果、运行次数、问题与提示等级。卡住约4–5分钟后从H1开始，一次给一级，不代写代码。独立完成和提示后完成分别记。真人难度／用时尚未校准。

本题是有限numeric replay。来源PSO已正确做flat快照、位置clamp、最大化及changed evaluation；P1是本地教学回归。source evaluator原样保留，中心为0.84而非printed1。来源ACO同步按当前row蒸发，没有真实LLM、延迟worker／retry或graph path；本题的numeric job→deferred outcome和nested trails是显式适配，不能采来源打印或论文数字为当前证明。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | evaluator要修到中心=1吗？ | "No. Keep the supplied source evaluator. Its center evaluates to 0.84; the source print is not an optimum oracle." |
| 1 | PSO random factors逐维独立吗？ | "No. The local source-style contract draws two factors per particle and shares them across the two dimensions." |
| 1 | bounds限制velocity吗？ | "Clamp the actual resulting position. Keep the declared velocity, even when it points outside the bounds." |
| 1 | 可以用旧score避免评价吗？ | "No. Every changed candidate must be evaluated at its actual coordinates. Preserve unaffected current scores and the full report; the functional guard has no linear upper call bound." |
| 2 | 只存seed可以resume吗？ | "No. Persist the full current RNG state, all independent particle vectors and best values, plus routing and deferred records." |
| 2 | checkpoint binary codec要自己写吗？ | "No. Binary64 vector packing and exact tagged metadata codecs are complete Given. You own the field layout, vector associations and reconstruction." |
| 2 | 双成员保证crash事务吗？ | "No. CheckpointMembers covers normal-process write, read and close. It does not promise a crash-atomic pair or distributed exactly-once behavior." |
| 3 | roulette选哪个row，边界呢？ | "Use the requested task row in declared agent order with one random draw and half-open cumulative intervals. Zero-weight entries have no interval." |
| 3 | feedback会顺便decay吗？ | "No. Complete-table decay is a separate explicit-epoch operation. Replaying the same epoch does not decay again." |
| 3 | delayed outcome奖励谁？ | "Bind its original Allocation. Require verified, success and quality at or above the inclusive threshold, then update only that task-agent route." |
| 3、5 | 有限输入为什么仍被拒绝？ | "Given intake conservatively checks representable totals and potential additions. It may reject huge inputs even if a later gate or path would reject them; this numeric domain is not a candidate policy task." |
| 4 | 需要重新判quality吗？ | "No. Project the actual sealed Part 3 decision. Typed classification, accepted/rejected status, NDJSON and close are complete Given." |
| 5 | visited edge重复怎么办？ | "Credit each actual traversal separately, only on the matching task and destination trail. Finite graph cycles are legal." |
| 5 | invalid或rejected path遇新epoch呢？ | "Decay all trails once before the first encountered path of that epoch, regardless of its later result. Share epoch state across every child and root." |
| 5 | 每层audit要保什么state？ | "Keep that layer's actual entering and leaving TrailState, its own path audits and ordered children. Later children and roots continue from the previous result." |
| 全部 | 是否证明训练收益或最优性？ | "No. This is finite local numeric replay, not real LLM prompt or weight optimization, a convergence proof or a routing benefit experiment." |

## 每关：主要坑、观察、提示、追问

### Part 1 numeric PSO replay（12分钟，20分）

四层按实际调用暴露：

1. `update_personal_best`把p_best绑到mutable x。测试先在(.72,.4)改善，再合法移动到(.72+.2,.4+.2)，后者fitness更差，别名使旧best坐标随之变动。正确 `best_report → score_reader` 在producer之外两次调用处检查真实score coherence，自然ValueError。应存独立flat numeric list，不改consumer或用recursive deepcopy。
2. `step_particle`clamp了velocity却放任实际x越界。按source三项速度更新，再clamp新position；实际v保留，不因撞边界自动归零。
3. `update_global_best`比较方向反了。任务是最大化，只有strict improvement换best；tie保原best，不强塞来源printed1。
4. `evaluate_changed_candidate`每改变一粒子重算全部current scores。只真实评价changed index并更新其cache，保未变项；不能返回stale分数或把所有own best无条件覆盖。

观察：是否从正确reader回查flat alias；是否区分position／velocity和current／best-so-far；是否保完整numeric报告。Given提供source evaluator／trace、RNG scheduler、correct readers和独立expected，候选人只修四primitive，不提前做ACO policy。

提示：

- H1："Which stored coordinates changed after a later motion, despite keeping their old fitness?"
- H2："Separate a flat personal-best snapshot, actual position bounds, maximizing comparison and the one changed current score."
- H3："Copy the numeric best list on improvement, clamp x after updating v, retain strict maximizing best, and evaluate only the changed index while preserving the full current score vector."

追问：

- "Why isn't this a recursive ownership problem?"（状态是flat numeric vectors，list值快照即可。）
- "Why retain the full current score vector?"（每轮mean和报告依赖全部实际current scores，不能只保best。）
- "What does an evaluator call guard establish?"（真实changed坐标被评价；不把内部多余calls伪报成同样数量，也不将exact上限当功能合同。）

### Part 2 binary checkpoint与deferred ledger（10分钟，20分）

主要坑：

- 每粒子UID的x／v／p_best／p_best_fit独立；binary布局不能把current写进own-best member，不能把global best或iteration漏掉。
- 需要bounds、evaluator version和完整Random state。close/reopen之后继续应等价于同一总轮次，不能由seed重启或重跑优化冒充恢复。
- 独立routing rows／applied epochs、完整Allocation ledger、ordered pending Outcome的UID／allocation／quality／verified／success／arrival／epoch都保留，重复记录与声明序不能吞掉。

观察：是否先画字段／vector布局，再接Given pack/unpack与metadata codec。state.bin和metadata.json的读写／close由完整CheckpointMembers给定，但whole checkpoint序列化仍candidate-owned。signed zero／subnormal bits是Given codec集成护栏，不让candidate另写精度算法。

真实整合：一个已分配numeric job经P1得到actual report，`outcome_from_report`只绑定其Allocation并clip实际score到quality域；P2保存该真实state与Outcome，P3消费真实重开ledger，而不是unused调用。

提示：

- H1："Which independent fields are needed to continue this exact experiment rather than start a similar one?"
- H2："Map each particle's four numeric members and preserve full RNG, route rows, allocations and pending arrivals separately."
- H3："Build the declared binary vector layout and tagged metadata, then reconstruct the complete typed checkpoint through the supplied member driver."

追问：

- "Why isn't a seed enough?"（当前RNG已消耗，且粒子／best／pending状态都已变化。）
- "Why retain repeated equal pending records?"（archive按声明保存事件，不自行推断去重或exactly-once语义。）

### Part 3 三个ACO policy算法（16分钟，25分）

三个真实TODO：

1. `choose_task_route`只取请求task_type的immutable row，按声明agent序、一次random draw、半开累计区间选择。不能用首row、让zero weight吃边界或在inference改weights。
2. `apply_route_decay`按显式epoch对全table乘(1-rho)并应用floor，保row／agent序；已applied epoch不重复数值衰减，新epoch追加。它与feedback分开，不等于source每次当前row deposit前decay。
3. `apply_verified_feedback`先绑定原Allocation，核route存在、verified／success／inclusive quality threshold，accepted才加reinforce×quality到该task-agent。unknown allocation／route或拒绝事件保自身reason、arrival、epoch、amount0，不造新route，也不奖励当前inference task。

测试实际P1报告→Outcome→P2 close/reopen→P3 policy。Given有限域、stable snapshot、row／ledger lookup和LearningDecision constructor不提供roulette／decay／gate solver。反馈函数没有自动重复event去重；epoch replay保护只属于decay。

观察：是否区分inference snapshot与learning update、arrival与epoch、任务身份与类型；是否给所有accepted／rejected decisions完整归因。保守representability是完整Given输入边界，不作为第四主算法。

提示：

- H1："Which task row and original allocation own this decision?"
- H2："Keep roulette, explicit decay and delayed feedback as separate operations with separate state effects."
- H3："Use one half-open weighted draw; apply whole-table decay only for a new epoch; then reinforce only the verified successful original task-agent at the inclusive threshold, retaining each rejection reason."

追问：

- "Why not decay during every inference?"（会把调用次数当epoch并让读路径学习，破坏显式replay合同。）
- "Why can a low-quality outcome still be logged?"（记录拒绝也是实际learning evidence，不能只保成功。）
- "What does conservative finite intake exclude?"（潜在加法／credit不可表示的超大输入；即使后续被拒，也不扩张候选政策职责。）

### Part 4 actual NDJSON fields（10分钟，15分）

主要坑：

- iteration保本条iteration、complete current_scores、population_mean和best-so-far各自值，不能用best冒mean或缓存首轮。
- route保own task UID／task_type／agent／draw／total；inference没有learning amount，不能变成reinforcement事件。
- learning保sealed decision的original allocation／task／agent、arrival／epoch、quality／status／amount／reason，accepted与rejected都发布，不能拿quality冒deposited amount。

观察：是否真正投影P1/P2/P3实际输出，每条字段由本条typed对象拥有。完整Given提供event kind／status分类、同步NDJSON writer／parser和close；这里不重判quality、不考通用cadence或framing。

提示：

- H1："Which actual event owns these numeric and task fields?"
- H2："Separate iteration best from mean, inference from learning, and delayed arrival from epoch."
- H3："Build each kind's own fields from its typed report, choice or sealed decision; preserve later events and rejected learning without recomputing the gate."

追问：

- "Why log current mean and best separately?"（best可不降而population当前质量变化，两项反映不同状态。）
- "Does observing an inference teach the router?"（没有；learning来自单独的actual Outcome与P3 decision。）

### Part 5 nested ant paths与shared epochs（10分钟，20分）

主要坑：

- 从声明start按ordered edges检查真实source→target连续与destination reach；失败保traversed prefix和原因，不因存在edge UID就算有效。
- 只有有效path且实际sealed P3 decision accepted才credit。向matching task_type／destination的visited edges加amount，重复visit按次数计，不set去重、不均分全graph或污染其他trail。
- 所有own paths／children／roots传同一个当前TrailState与applied epochs。新epoch在首path之前蒸发全trail一次，即使该path之后invalid／rejected；不每ant或每group重蒸发。
- 每层ExpeditionAudit实际填写进入的before和离开的after、own PathAudit及ordered children，顶层返回最终state；不能把证书state都写成outer input。

观察：是否保root／child前后状态连续、input snapshot不变；能否解释loop重复ab credit和后续epoch decay。GraphCatalog的global binding／forest intake／conservative numeric bounds以及修好的P3真实sealed decision是完整Given依赖；P5不再实现quality gate，实际path／multiplicity／shared fold仍candidate-owned。

提示：

- H1："Which edges were actually traversed, and which state enters the next child?"
- H2："Validate continuity and destination, credit visit multiplicity on the correct trail, and share epoch state across the forest."
- H3："Capture before, process own paths in order with first-encounter epoch decay, use the sealed decision for valid-path credit, then thread the resulting state through each child and retain after."

追问：

- "Why are finite cycles allowed?"（path是有限edge序列，重复visit本身定义multiplicity，不是无界遍历。）
- "Why does an invalid first path still trigger decay?"（epoch语义由首次encounter触发，path admission是之后的独立判断。）
- "What is Given from Part 3?"（actual accepted/rejected金额与原task归因；P5只消费，不复制gate。）

## 记录与评分（100分）

每项写实际代码位置、行为或断言依据；未观察到写“未观察”。提示、沟通和用时另记，不从参考代码推定候选人能力。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | flat personal-best snapshot与真实reader coherence | 5 | |
| 1 | actual position bounds与velocity语义 | 5 | |
| 1 | strict maximizing best／tie retention | 4 | |
| 1 | changed真实evaluation、current cache与whole report | 6 | |
| 2 | independent particle numeric布局／关联 | 7 | |
| 2 | global state／bounds／evaluator／full RNG | 7 | |
| 2 | complete route／allocation／deferred ledger及reopen | 6 | |
| 3 | requested-row half-open roulette／exact draw | 8 | |
| 3 | whole-table once-per-epoch decay／floor | 7 | |
| 3 | original allocation verified feedback／complete decisions | 10 | |
| 4 | own iteration vectors／mean／best | 6 | |
| 4 | actual route identity／draw fields | 4 | |
| 4 | sealed learning attribution／arrival／epoch／amount／reason | 5 | |
| 5 | path continuity／destination／failure prefix | 5 | |
| 5 | visited multiplicity与task/destination credit | 5 | |
| 5 | shared epoch decay及forest state threading | 6 | |
| 5 | 每层before／after、own／child完整certificates | 4 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

静态48PY、五测试、39assert、3raises、五锁、26个登记错误写法。当前原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。

P1为780个合成本地particles×4轮，完整OptimizationDesk.run与whole OptimizationReport equality在timer内，输入／独立expected在外，0.16秒的本机完整性能组通过。报告保全部真实numeric state，功能guard要求changed candidate真实评价，没有exact线性call上限；登记清单或来源打印不能代替执行证据。60分钟真人用时也未校准。

本机独占完整3slow3fast测得slow为1.58501537／1.48940483／1.48805696秒，fast为0.010484084／0.01240925／0.0110989581秒；限值0.16秒，双侧余量9.30035599／12.8936076，最慢业务1.58501537秒。原样参考五关通过，subprocess wall为0.283843917秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另重复评价实际未变粒子，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
