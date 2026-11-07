# 面试官手册：WorkPull（16/09）

候选人计时期间不看本手册。候选人使用英文 README、`workpull/` 和测试，只修领域实现，不改断言、正确 GIVEN 或五关顺序。

## 开场（2 分钟）

- 说明总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间和难度尚未经过真人校准，不要求全部完成。
- 请候选人边做边说出证据和下一步判断，可以随时澄清、查 Python 标准库官方文档。解除当前 skip 后再逐关推进。
- 记录每关解锁到首次通过的时间、pytest 次数、H1/H2/H3。主持人不代写代码；卡住约 5 分钟时一次给一级提示。
- 澄清问题只在问到时用下表英文回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 和本手册。
- 说明这是确定性的本地逻辑事件 adapter。duration 是整数逻辑微秒，不运行 sleep、线程或真实模型，也不把模拟完成时间当线程 benchmark。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | What identifies a result when one worker completes several tasks? | The task ID identifies the result. Preserve the actual completing worker as a separate field. |
| 1 | Can an empty ready queue end the run? | Only when ready work, running work and future arrivals are all drained. |
| 1 | How are simultaneous events ordered? | Use logical time, then the supplied unique sequence. Event objects themselves are not comparable. |
| 1 | Must I implement the worker histogram or zero-duration handling? | No. Both are complete supplied dependencies. Preserve their actual observations and counts. |
| 2 | Does declaring or pulling a task make it complete? | No. Follow the observed lifecycle: not-arrived, ready, running and finally complete only after completion evidence. |
| 2 | Should the journal use pre_assigned as the worker? | No. It is only a fixed-assignment hint. Persist and replay the actual observed worker. |
| 2 | Must I write signed-integer, text or tuple codecs? | No. The complete signed64 codec, append framing and read-order primitives are supplied. |
| 3 | May priority admit an unsubscribed or future task? | No. Check arrival and that worker's topic subscriptions before comparing priorities. |
| 3 | Is there a topic wildcard or interval validation to implement? | No wildcard syntax is defined. Match topic strings exactly; the supplied desk already validates a positive integer aging interval. |
| 3 | Where does age start? | At the task's arrival time. At each pull, use base priority plus complete elapsed aging intervals. |
| 3 | How do equal scores and simultaneous workers behave? | Visit free workers in declared order, break task ties by original task sequence and remove each claimed task before the next worker. |
| 3 | Should I optimize by duration or preempt running work? | No. This is a nonpreemptive pull policy, not a global matching or shortest-job optimizer. |
| 4 | Can a pull event carry a fabricated completed result? | No. Project only that phase's recorded fields. Completion carries its own actual result and finish instant. |
| 4 | Must I implement UTF8 lengths or async cadence? | No. Complete JSON encoding, byte framing, publication and closure are supplied. |
| 5 | Do child topic scopes widen parent topics? | No. Intersect every declared ancestor restriction with the worker subscriptions. An empty intersection remains empty. |
| 5 | Which pools are visible? | The worker's own group pools and shared ancestor pools. Sibling pools and private ancestor pools stay outside that view. |
| 5 | What contributes to a group total? | Actual completions by its own and descendant workers. Queued, running and unserved work is not completed. |
| 5 | Must I implement scoped names or subtree lookup? | No. The complete full-UID resolver and subtree catalog are supplied. |

## Part 1：完整 FIFO replay（目标 12 分钟）

三个主要缺陷：

1. `record_completion` 错把 worker UID 当 task result key。后续正确 `receipt_card → task_result_reader` 按 task ID 读取，自然在 producer 外两次调用处抛 `KeyError`。根因是结果 identity 错，不能修改正确 reader/card 迁就它。
2. `producer_finished` 只看 ready/running 为空，忽略 future arrivals。间隙后的真实任务仍要到达、执行和完成，不能当队列暂空就结束。
3. calendar 每次 `min(events, key=event_order)` 后再 remove，反复扫描真实事件集合。参考保持 `(time_us, sequence, event)` 的稳定 heap，不能让平局退到比较不可比较的 Event。

看什么：是否沿消费者合同修 task identity，并保留实际 worker 和回调真实结果；是否把暂空与 producer 完结分开；是否保留全部事件和顺序再优化 calendar。receipt 按 task 声明顺序，completion 按实际逻辑完成顺序。worker histogram、idle worker 的 0、零 duration 的完整执行/事件处理都已正确 GIVEN，不是候选主要坑。

性能 fixture 是 12 批、每批 250 个真实 Task，共 3,000 项；第 b 批在逻辑微秒 5000×b 到达，duration 为 1+i%3，实际本地 payload 转换、完整 `CompletionDesk.run` 和整个 `RunReport` equality 都在 timer 内；fixture/独立 expected 构造在外。限值为 0.14 秒，本机固定三慢三快组测得业务 timer：慢版 1.2555–1.2973 秒，快版 0.01660–0.01749 秒，双侧余量 8.9679× / 8.0034×，快侧接近 8× 门槛。精确记录见 [校准报告](/tmp/exam-11-16-work/draft16-09/actual/group03-summary.json)。不能省 trace、只跑部分任务、固定 worker/result 或跳过回调来提速。

六个测量副本仅把 elapsed 限值断言改成打印，慢版另仅恢复真实 min/remove calendar；完整业务 equality 和其他四关原样保留，六份都通过五关功能检查。测量版结果不表示慢版通过原 elapsed 限值断言。最慢业务路径 1.2973 秒，六份五关进程 wall 最大 1.4465 秒；原样 reference 五关另通过，wall 约 0.2282 秒。这是本机环境记录，不是任意负载下的通用墙钟上界或生产 SLA。

提示：

- H1: "Which identity did the result producer write, and which identity does the reader require?"
- H2: "What work still exists when both ready and running are temporarily empty?"
- H3：分别指向 task-keyed ledger、future-arrival drain 和稳定 `(time, sequence)` calendar；histogram 与零 duration driver 保持原样。

追问：

- "Why does the original static thread demo safely exit on an empty queue?"（它在线程启动前已把全部任务入队，没有后续 arrival。）
- "Why keep the sequence even with a heap?"（相同逻辑时间仍需稳定事件顺序，且 Event 没有比较运算。）

future arrivals、逻辑事件和完整结果 ledger 是本地 adapter；不能把动态输入下的终止回归描述成原静态 demo 本来存在的 bug。

## Part 2：observed lifecycle journal（目标 11 分钟）

主要坑：

- task 定义和观察记录是两类状态：尚未到达的声明不能变 completed，pull 也只能是 running。
- 重开后使用 observed worker、start、completion finish 和 result，不能用 `pre_assigned` 或 arrival time 代替实际证据。
- 追加记录保留 task 声明顺序和 lifecycle 观察顺序；不按 arrival time 排定义，也不丢已有 trace。

看什么：能否给 task/worker/event 写清领域行，再按记录逐项重放 not-arrived/ready/running/complete；是否只在 completion 使用实际结果。Journal 输入是声明一次的 typed 定义和实际 driver lifecycle。完整 signed64/text/tuple codec、framing、追加读写和 partial-frame 拒绝已给定。大整数精度、UTF8 与残缺 frame 断言是依赖集成护栏，byte count、浮点转型或通用 missing 判别不是主要出题点。

提示：

- H1: "Which observation actually changed this task's phase?"
- H2: "Was this worker observed at pull time or only suggested by the task definition?"
- H3：分开定义行与 event 行，按 append 顺序重放；task 的最终输出顺序仍按定义，字节编解码交给完整 helper。

追问：

- "Why can a pull record contain a scheduled finish without proving completion?"（确定性 duration 可给出逻辑 finish，但真正 completion 仍是独立观察。）
- "Why keep both definitions and raw events?"（能恢复声明状态与实际经历，而不是只保存一个容易混淆来源的最终标签。）

## Part 3：specialist aging 与独占 claim（目标 15 分钟）

三个独立 TODO：`eligible_ready_tasks`、`effective_priority`、`claim_free_workers`。

主要坑：

- 先检查实际到达和当前 worker 的 topic，不能让高 priority 跳过 admission，也不能让 future work 被领取。
- 在实际 pull 时刻按 `base + (now - arrival_us) // aging_interval` 计算整数 aging。不能从 duration、全局 clock 零点或上次排序时刻计算等待。
- equal scores 按原 task sequence，不能按当前 ready 排列。free workers 按声明顺序各自选取，并马上移除已领取任务，防同批重复 claim。
- running work 不抢占；没有合适 topic 的任务可以留在 unfinished，不用把它硬塞给别的 worker。

看什么：能否分别实现 admission、score 和独占 claim；是否针对每个 worker 重新看剩余 eligible tasks；是否用 P2 reopen 的真实任务跑 P1 desk。P1 calendar 只按时间管理事件，不提供 topic/age/claim solver。

提示：

- H1: "Which tasks have arrived and match this worker before priority is considered?"
- H2: "How long has this task actually waited at this pull instant?"
- H3：按声明 worker 顺序处理独立 remaining，使用原 task sequence 裁决平票，每个 claim 后移除任务；不要改成按 duration 的全局优化。

追问：

- "Why recompute age when a worker becomes free?"（等待时间变化，入队时一次排序不等于实际 pull 的有效分。）
- "Does this policy guarantee a globally optimal makespan?"（不保证；它是明确的顺序 specialist pull 合同。）

## Part 4：观察事件的领域 frame（目标 10 分钟）

主要坑：

- 每条 event 保持自身 kind、task ID、记录时间与 trace 顺序，不用 start 替代 completion 时刻。
- arrival 只带 queued priority，不制造 worker 或 result；pull 带实际 worker/start/记录的 finish，不伪造完成结果。
- completion 保留自身实际 worker、start/finish 和 payload result，不能用 task ID 或固定分配提示代替。

看什么：同步 `event_payload` 是否只投影真实记录，不重跑 scheduler 或执行任务。完整 frame/JSON UTF8 writer 和 async pull/publication/close 已给定；byte length、传输 cadence、关闭次数的断言是集成护栏，不能改成另一道通用流实现题。

提示：

- H1: "What did this lifecycle phase actually observe?"
- H2: "Does this field belong to an arrival, a pull or a completed result?"
- H3：按三种 phase 分支组装领域 payload；只用 event 自身的 time/worker/value，framing 与传输交给正确依赖。

追问：

- "Why is a pull result field misleading?"（领取不等于完成，结果必须来自 completion evidence。）
- "Why must a completion use its own event time?"（start 是开始，completion time 才是该完成观察的时刻。）

## Part 5：嵌套 subscriptions 与 pool（目标 10 分钟）

主要坑：

- worker topics 要与所有已声明 group restrictions 逐层取交集；用 union 会放宽祖先约束，空交集不能回退成全部 topics。
- 自己组的 pool 可见；祖先 pool 只有 shared 才继承，sibling 和 ancestor private 不进入视图。
- 每个 full worker 的计数来自实际 completions；group total 汇总本组及完整 subtree 的 worker，不漏后代，也不把全局计数套给每个 worker。
- queued、running 或不被订阅的 work 不是 completed，不能用任务数或声明 worker 数代替完成证据。

看什么：是否用完整 GIVEN `GroupCatalog` 的 UID、ancestor、subtree 查询实现领域边界；是否保持每个 worker 的 subscriptions 顺序。full UID resolver 与一次 subtree catalog 已完成，不考 scoped shortname、generic recursive ownership 或 shared occurrence 去重。

提示：

- H1: "Which ancestor restrictions still apply to this worker's topics?"
- H2: "Is this pool local, shared by an ancestor or outside the worker's boundary?"
- H3：分开 topic 交集、pool 可见性和实际完成 counts；用现成 catalog 取身份与 subtree，不重写解析器。

追问：

- "Why does a parent group include descendant completions?"（它的 completed 表示整个所属 subtree 的实际工作量，不仅是直接 worker。）
- "Does a shared pool in a sibling become visible?"（不会；shared 只允许向该 pool 的后代继承。）

当前题包有 36 条 assert、2 处 raises、五个测试与五个 skip 锁，登记 24 项错修。独立 source-first 验证覆盖 6 个领域错修：等 payload 的不同 task identity、完整 aging interval、声明 worker 次序、arrival 的 signed priority、显式空 topic restriction，以及 shared sibling pool 的祖先边界。6 个错修均在 NEW 完整副本中只使指定关失败、其余四关通过，配对 reference 均为五关通过；原规定 TEMP --write checker 的默认五锁、参考全五关、starter 五失败、逐层与全部 24 项错修检查通过。完整执行命令、内容 SHA、权限记录和日志见 exam 外 fresh-review.json。

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层调试与完整 replay | 20 | task identity/真实结果 7；future drain 5；稳定 calendar/完整输出性能路径 8 |
| lifecycle 持久化 | 20 | 定义与观察分离 7；actual worker/result/phase 8；顺序/完整 append 与正确使用 codec 5 |
| specialist aging 与 claim | 25 | arrival/topic admission 7；实际 pull aging 8；平票/worker 次序/独占 claim 10 |
| 领域事件投影 | 15 | phase 字段边界 6；实际时间/worker/result 6；正确使用完整 driver 3 |
| subscriptions、pool 与完成量 | 20 | topic 交集 6；private/shared 边界 6；actual worker/subtree totals 6；解释来源与证明边界 2 |

每个子项按观察到的证据给分：完整满足得满分，部分正确但有具体反例得部分分，未实现或未观察得 0。逐项写下代码、测试现象或口头推理证据；提示、用时和运行次数另记，不把参考答案结果记到候选成绩。

静态题包当前为 45 Python 文件、5 tests、36 assert、2 raises、5 skip、24 登记错修。本机原样 reference、六个测量版本及原规定 TEMP checker 均有实际检查记录；默认五锁、参考全五关、逐层和全部 24 项登记错修检查通过。人类用时未校准，参考检查不计作候选成绩；完整检查结果见 verification.txt 与独立验收记录。原线程/sleep demo 未运行，输出 skill 仅作来源数据，没有执行其架构建议；题包不证明真实线程加速、真实模型收益、生产 broker 能力或当代框架事实。
