# 面试官手册：FloorFair（16/10）

候选人计时期间不看本手册。候选人使用英文 README、`floorfair/` 和测试，只修领域实现，不改断言、完整 GIVEN 或五关顺序。

## 开场（2 分钟）

- 说明总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间和难度尚未经过真人校准，不要求全部完成。
- 请候选人边做边解释证据与下一步判断，可以随时澄清、查 Python 标准库官方文档。解除当前 skip 后逐关推进。
- 记录每关解锁到首次通过的时间、pytest 次数和 H1/H2/H3。主持人不代写代码；卡住约 5 分钟时一次给一级提示。
- 澄清问题只在问到时用下表英文回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 与本手册。
- 说明 selector 和 agent 输出是本地确定性 callback，没有真实模型或网络。exact termination、question/fairness/budget 都是公开的本地合同。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | What terminates this local chat? | Only the entire message, after trimming whitespace, exactly equal to TERMINATE. A negated mention is ordinary content. |
| 1 | Is that the official framework default? | No. It is this exercise's explicit contract. The source demo uses a suffix check. |
| 1 | Which messages reach the selector? | The last window complete utterances in their original order. Keep the full raw transcript separately. |
| 1 | Does a selector decision count as speech? | No. Only a committed agent utterance counts, including accepted empty text. A rejected pick remains diagnostic. |
| 2 | May I keep only the selected speaker? | No. Persist each decision's own complete input, choice, reason and audit fields, plus each utterance's decision association. |
| 2 | Do I reimplement turn counting or scalar encoding? | No. event_tag, schema initialization, archive_counts, exact scalar codecs and transaction primitives are complete supplied dependencies. |
| 2 | Does replacing one snapshot remove another conversation? | No. Replace only the requested conversation and preserve its declared record order. |
| 3 | Does an @mention create a question? | No. Only structured question metadata creates an obligation. Keep unique questions in creation order. |
| 3 | Who can resolve a question? | Its named addressee, replying to the exact question ID in the same conversation thread. |
| 3 | Which speakers contribute to the deficit formula? | Active speakers only. Use actual committed counts, active weights and exact Fraction arithmetic; a missing count is zero. |
| 3 | Can a pending question bypass the consecutive cap? | No. Apply eligibility first. A blocked question stays pending; another eligible speaker may be selected. |
| 3 | How are remaining choices ordered? | Oldest eligible unanswered addressee first; otherwise greatest deficit, with declared roster order for ties. Return None if none is eligible. |
| 4 | Must I classify or bind raw decisions myself? | No. observe_turn provides the correct outcome, committed binding and deficit delta. Project that observation's own fields. |
| 4 | What can the public line contain? | Only thread, turn, kind, speaker, reason and exact deficit text. Do not include private selector prompts. |
| 4 | Must I implement logfmt escaping or async cadence? | No. The complete finite-dialect codec, exact formatter and publication/close driver are supplied. |
| 5 | Does another speaker reset an agent's quota usage? | No. Count all of that agent's own-thread committed utterances cumulatively, including excess turns. This is separate from Part 3's consecutive streak. |
| 5 | Which quota rows are returned? | Follow max_speaks declaration order, including declared agents with no speech. An empty declaration produces no rows; undeclared agents produce no row. |
| 5 | When does first_excess appear? | The cap-th turn is allowed. Return zero or one message ID for the cap+1st turn, even if that ID is empty. A zero cap makes the first actual turn excess. |
| 5 | Are per-agent quotas inherited by children? | No. They cover only the declaring node's own actual utterances. Total thread limits cover subtrees and all ancestor residuals constrain remaining total budget. |
| 5 | Must I implement reply authorization? | No. Complete reply_evidence supplies authorized answer IDs and all issues. Use it for own pending state and preserve its issues. Cross-thread lookup does not grant answering effect. |
| 5 | Does child completion settle a parent obligation? | No. Each node reports its own unanswered questions. |
| 5 | Must I implement cap validation or question identity? | No. Unique declared speaker names, nonnegative integer caps, global question lookup and tree queries are complete supplied dependencies. |

## Part 1：review replay 与真实发言（目标 12 分钟）

四层缺陷：

1. suffix stop 把 `Please do not TERMINATE` 当终止，reviewer 尚未发出真实 approval 就退出。正确 `approval_card → approval_reader` 随后消费 reviewer evidence，自然在根因外两次调用处抛 `KeyError`。不能改 reader 制造 approval。
2. selector 取 oldest window，违反最近完整消息合同；内容和顺序都要保留。
3. `record_committed_turn` 把 Decision 诊断也算实际发言。accepted Decision 仍不是 Utterance，rejected 不发言，accepted 空文本却是真实一轮。
4. 先格式化整个 archived history 再截窗口，重复处理不需要的消息。先取最后 window 条，再用完整 renderer 格式化；raw transcript 不删。

看什么：是否沿正确 consumer 合同找到提前 stop；是否分开完整历史、有限 selector view、诊断选择和实际 speech；是否保留每个 callback 的输入、choice、reason 与完整 report。

性能 workload 是 8,000 条真实 archived user messages、80 次真实 `ContextDigestSelector` 调用、window=3；每次 callback 读取窗口并计算实际 SHA256 reason。fixture/独立 expected 在 timer 外，完整 `ChatDesk.run`、整个 `ChatReport` equality 和 callback count 在 timer 内。限值 0.05 秒，本机完整三慢三快组测得慢版 0.567921–0.585339 秒、快版 0.0004762–0.0005414 秒，双侧余量 11.3584× / 92.3503×。精确记录见 [校准报告](/tmp/exam-11-16-work/draft16-10/actual/group02-summary.json)。不能以空 context、少跑 callback、丢 transcript 或固定结果换速度。

六个完整测量副本只把 elapsed 断言改为打印，慢版另只恢复真实 whole-history-format-before-window；全部功能护栏和其余四关保留，六份都通过带测量打印的五关功能检查。这不表示慢样本通过原限值断言。最慢业务路径约 0.58534 秒，六份五关进程 wall 最大约 0.738924 秒；原样 reference 五关另通过，wall 约 0.183642 秒。它们是本机有限 workload 的记录，不是任意负载下的通用墙钟上界或生产 SLA。

提示：

- H1: "Which message ended the loop before the approval reader received its evidence?"
- H2: "Is this selector input recent, and is this event actual speech or a diagnostic choice?"
- H3：分别检查 exact whole trimmed terminal、recent window、Utterance-only counts 与 slice-before-render；正确消费者和 renderer 保持原合同。

追问：

- "Why keep raw history when selector input is bounded?"（输入控制成本，完整历史保留审计；两者用途不同。）
- "Why is an accepted empty utterance still a turn?"（提交行为来自 Utterance identity，不由 content 的真值决定。）

exact TERMINATE 是本题局部规则，不能称作官方默认。window=0 和大于 history 的行为是集成护栏，不作为第五个主要缺陷。P1 不提供 P3 问题/deficit/cap solver。

## Part 2：完整 selector audit snapshot（目标 11 分钟）

主要坑：

- Decision 必须保留自己的 input/context、choice、reason、accepted 和 private audit，不能只存最后一次选择或复用另一条 input。
- Utterance 保留自己的 identity/content 和 `decision_id`，不能用 message_id 代替对应选择。
- 按声明 record 顺序重开完整 snapshot；替换只影响请求 conversation，旧 tail 不残留，其他 conversation 不丢。

看什么：是否清楚区分两种领域记录并保存完整字段和关联。完整 `ensure_schema`、`event_tag`、exact scalar codec、typed `restore_event`、transaction 和 `archive_counts` 都 GIVEN；turn counting 不是这一关的候选主算法。大整数、Unicode、空文本、bool 与 rejected/accepted 并存检查依赖集成，不考手写精度 codec。

提示：

- H1: "Which decision owns this input and which utterance refers to it?"
- H2: "Did reopening preserve the original mixed observation order?"
- H3：分开完整 Decision fields 和 Utterance fields，用 position 保持顺序，只替换目标 thread；计数与 codec 交给正确 helper。

追问：

- "Why archive a rejected decision without an utterance?"（它是真实诊断证据，需要知道输入与拒绝理由，但不应伪造成发言。）
- "Why keep private prompts in audit but exclude them from public output?"（两个视图有不同字段合同，不是把审计证据删除。）

## Part 3：named questions、weighted deficits 与 cap（目标 15 分钟）

三个独立 TODO：`update_question_obligations`、`speaker_deficits`、`select_next_speaker`。

主要坑：

- 只把结构化 questions 放入 creation-order pending；只有 named addressee 对 exact ID 的同 thread reply 才消除那一个义务，不能按 @文本或 addressee 批量清空。
- deficit 用 actual committed turns 与 active weights：`Fraction((active_turns+1)*weight, active_weight) - own_count`。inactive 的大 weight/count 不参与，结果可以为负。
- 先排除达到 max_consecutive 的上一位，再按最早 eligible 未答问题的 addressee 优先；cap-blocked 问题保留 pending。
- 无 question 时按最大 deficit，平票保持 roster 声明序；无人 eligible 返回 None，不绕过 cap 虚构发言。

看什么：是否分别实现 obligation、精确份额差额和选择顺序，使用 P1 真实 counts 与 P2 reopen 证据，而不是 proposed choices。完整 GIVEN 只有 typed/positive-input validation 和 committed 分类，没有问题或 fairness 算法。这三个算法的核心是 obligation 与实际轮次的份额差额，不能用通用 selector legality/fallback 代替。

合法域是同一 conversation 的 typed records、唯一 question IDs、positive integer weights/cap。不要把任意 off-domain 验证扩成主要要求。

提示：

- H1: "Which exact question remains unanswered, and who was named to answer it?"
- H2: "Are these shares based on active speakers' actual turns or on proposed choices?"
- H3：分三步核对 pending ID/owner、精确 active deficit、cap 后的 oldest question/deficit/tie；不要把硬 cap 当可忽略的偏好。

追问：

- "Can an eligible unanswered addressee win with a negative deficit?"（可以，问题义务优先于份额差额。）
- "Does this policy guarantee no starvation under every hard cap?"（不保证；合法候选可能全部受阻，合同要求返回 None。）

## Part 4：公开的 classified evidence（目标 10 分钟）

主要坑：

- 每条 observation 的 thread、turn、kind、speaker 和 reason 来自自身；reject/stop 不制造 proposed speaker。
- 完整 deficit delta 用给定 `delta_text` 表示，不截掉分数或借用邻条 evidence。
- 公开字段恰好为 thread/turn/kind/speaker/reason/deficit，private_prompt 不能代替 reason，也不能作为额外字段输出。

看什么：是否直接投影完整 `observe_turn` 的产物。accepted/message binding、reject/commit/stop 分类、before/after delta 都已正确 GIVEN；候选不重新分类或更新 counts。完整 logfmt reader/writer、escaping、async cadence 和 close 都是依赖护栏。

提示：

- H1: "Which actual observation owns these public fields?"
- H2: "Is this text the public reason or the private selector prompt?"
- H3：只投影六个声明字段并使用 exact formatter；分类、binding 与 transport 保持给定实现。

追问：

- "Why does a rejected pick publish no committed speaker?"（选择被拒，没有对应真实 utterance；正确 classifier 已表达该区别。）
- "Why preserve a fractional delta in evidence?"（它描述实际份额变化，取整会丢掉有意义的差额。）

## Part 5：累计 agent quotas 与 inherited total budget（目标 10 分钟）

主要坑：

- 每个声明 agent 的 used 是该 agent 在本 thread 所有实际 Utterance 的累计数，其他 speaker 穿插不清零，Decision 诊断不计，超限或未授权回复仍计。按 `max_speaks` 声明序产出行，静默 agent 也有行，未声明 agent 不产出行。
- remaining=`max(0, cap-used)`；第 cap 条仍合法，`first_excess` 只能是第 cap+1 条的实际 message ID，不能取最后一条或把 cap-th 当超限。它是零或一个元素 tuple，空 ID 不丢；cap=0 时首条即超限，空声明没有 quota 行。
- quota 只覆盖 own messages，不继承声明或累计 child speech。own pending 从本层 questions 与完整 GIVEN 的 answered IDs 得到；child complete 不消除 parent pending。
- total `limit` 覆盖完整 subtree 的实际 Utterance。own 及全部 ancestor residual 共同约束，remaining=`max(0,min(residuals))`，不能求和或只看本层。它与 own per-agent quota 是不同维度。

看什么：是否区分累计 per-agent usage、P3 consecutive streak 与 subtree total usage；是否给出真正第一条超限证据并保留全部真实 speech。完整 `ThreadCatalog.reply_evidence` 已提供 owner-thread/named-addressee 授权 answers 和全部 issues，候选负责调用和保留，不重写授权比较。两项 authority 错修是 GIVEN 集成护栏，不是主要候选算法。finite typed tree、global unique qIDs 与可解析 refs 是合法域；非负 caps（含 0）、唯一声明 speaker 名、identity、ancestor/subtree 和 cycle 拒绝均 GIVEN，不要求 shortname 或 shared occurrence 算法。

提示：

- H1: "Which own committed turns belong to each declared agent, even when other speakers intervene?"
- H2: "Which actual message is that agent's first turn beyond its allowance, and which total budgets cover a child?"
- H3：按声明序筛选本层实际 Utterance，累计 used、截到非负 remaining，取索引 cap 的至多一个 message ID；用完整 reply_evidence 算 own pending，另汇总 subtree speech 并取全部祖先 total residual 的最小值。

追问：

- "How does cumulative quota differ from the consecutive cap?"（前者不因其他 speaker 发言而清零，后者只描述当前连续 streak。）
- "Does an excess or unauthorized reply still consume total budget?"（是，真实 Utterance 同时参与自身 agent 的累计 usage 与覆盖它的 total budget；不产生回答效力也不能删掉该发言。）
- "What does complete mean for one node?"（其自身 pending 为空，不代表 parent 完成，也不等于没有 issues、没有 quota excess 或尚有预算。）

P1 的固定性能路径有校准报告中的本机测量记录。当前原规定 TEMP checker 已通过默认五锁、参考全五关、逐层与全部 32 项登记错修检查，其中两项 reply-authority 错修验证完整 GIVEN 的集成。Part 5 配额的三项独立实际错修分别覆盖 per-agent 归属、首条超限边界与累计历史保留；每项均为 Part 5 失败、其他四关通过，各对应 reference 全五关通过。这些结果不计作候选成绩，具体记录见 verification.txt 与独立验收报告。

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层调试与完整 replay | 20 | exact terminal/真实 approval 5；recent context 4；真实发言 5；有界 render 与完整性能路径 6 |
| 完整 audit snapshot | 20 | 每条 Decision input/choice/reason 8；Utterance association 7；目标 snapshot/顺序与正确 helper 集成 5 |
| 问题义务与份额策略 | 25 | exact named obligations 8；active actual Fraction deficits 8；cap/question/deficit/tie 次序 9 |
| 领域公开证据 | 15 | own observation fields 6；完整 delta 4；public/private schema 5 |
| 累计 agent 配额与 total budget | 20 | own cumulative usage/声明序 6；非负 remaining/首条超限证据 5；own pending/complete 3；subtree 与祖先 residual 6 |

每个子项按可观察证据评分：完整满足得满分，部分正确但有具体反例得部分分，未实现或未观察得 0。写下代码、测试现象或口头推理证据；提示次数、用时和运行次数另记，不把参考结果算进候选成绩。

当前静态题包为 45 Python 文件、5 tests、39 assert、2 raises、5 skip、32 登记错修。原规定 TEMP checker 全部检查通过，独立 Part 5 配额的三项错修均为目标关失败、其他四关通过，各对应 reference 全五关通过；数量和检查结果不计作候选成绩。60 分钟真人用时未校准。原 source 与输出 skill 未执行，框架事实未作当前外部核验。
