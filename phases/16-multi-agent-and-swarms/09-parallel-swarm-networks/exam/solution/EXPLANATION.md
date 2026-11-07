# 参考实现讲解：WorkPull（16/09）

计时结束后再看。参考实现位于本目录的 `workpull/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前实现合同，静态阅读不产生运行通过结论。

## Part 1：结果 identity、producer drain 与 calendar

第一个 `KeyError` 来自正确 `task_result_reader`。`record_completion` 把结果写在 `ledger.by_task[completion.worker_uid]`，后续 `receipt_card` 按 task ID 调用 reader，所需的 key 从未写入。修复 producer，使 key 是 `completion.task_id`，完整 Completion 仍保留实际 worker、start/finish 和真实 callback value。同一个 worker 做多项任务时，每个任务都有自己的结果。

这也是为何不能把 reader 改成“随便找一个 worker 结果”，或把 callback value 换成 task ID。worker histogram 已由完整 `increment_worker_histogram` 正确更新，包含 idle worker 的零计数；候选不重写统计逻辑。

`producer_finished` 要同时确认 ready、running 和 future arrivals 都已清空。间隙里 ready/running 可以都为空，但 future task 仍会到达。正确 driver 会推进逻辑时间，并完整处理 duration 为 0 的任务；零 duration 不是缺失，也不是本题候选缺陷。

calendar 接收真实不可比较的 Event。慢写法反复 `min(..., key=event_order)` 并 remove；参考把事件存为 `(time_us, sequence, event)`，初始 heapify，push/pop 使用 heap，peek 直接读堆顶。sequence 由完整 driver 唯一递增，稳定处理同一时间的事件，也避免 heap 比较 Event 本身。这个 calendar 只管理时间顺序，没有 P3 的 topic、aging 或独占 claim。

3,000-task fixture 每项都实际调用本地 payload transform：反转 payload 文本并附上其 SHA256。fixture 和独立 expected report 在 timer 外构造；timer 包含完整 `CompletionDesk.run` 与整个 `RunReport` equality，覆盖 inputs、trace、completions、actual worker/result、counts、cards、unfinished 和 finished_us。不能只保留计数、抽样任务或预填固定结果。

性能 fixture 有 12 批、每批 250 项，共 3,000 个真实任务；arrival=5000×批序，duration=1+i%3，各批间保留 future arrivals。限值为 0.14 秒。本机 Python 3.12.14 的固定三慢三快组业务 timer 如下，精确值与六份原始结果路径见 [校准报告](/tmp/exam-11-16-work/draft16-09/actual/group03-summary.json)。

| 次序 | 慢版（秒） | 快版（秒） |
|---|---:|---:|
| 1 | 1.289456 | 0.016601 |
| 2 | 1.297269 | 0.017493 |
| 3 | 1.255510 | 0.016853 |

该组按先三慢、后三快执行。最小慢值除以限值为 8.9679×，限值除以最大快值为 8.0034×；快侧接近 8× 门槛。最慢业务 timer 为 1.2973 秒，小于 3 秒；六份完整五关的进程 wall 最大为 1.4465 秒，小于 5 秒。

六个独立完整副本只把 elapsed 限值断言换成测量打印，慢版另仅还原 calendar 的真实 min/remove；完整 run 与整个 report equality，以及其余四关全部保留。六份记录都是测量版五关功能通过，不能据此说慢版通过了原 0.14 秒断言。保留原计时断言的 reference 完整五关另通过，进程 wall 约 0.2282 秒；这不是 P1 业务 timer。这里的整数 duration 是逻辑时间，和两种实际墙钟测量也不能混同。

## Part 2：定义与观察分开的追加 journal

`TaskJournal.append` 把 task、worker 和 lifecycle 分成有明确 kind 的领域 tuple，交给完整 `append_records`。task 保存 topic、payload、arrival/duration、priority 和 fixed-assignment hint；worker 保存 full UID/topics/pool；event 保存自身 kind、task ID、观察时刻、实际 worker、start/finish、value 和 priority。输入是声明一次的 typed task/worker 定义与真实 driver lifecycle，不在这里推断调度。

`load` 按物理追加顺序读取，再分别恢复 Task、Worker 和 Lifecycle，组成 `TraceArchive`。task tuple 保留定义顺序，trace tuple 保留观察顺序；arrival time 不决定定义的输出排列。

`task_states` 先把所有声明 task 标为 not-arrived，然后按 trace 重放：arrival 变 ready，pull 变 running，仅 completion 变 complete。running 输出保留 actual worker/start，但完成时刻和 result 仍为空；即使 pull 记录已经有确定性 scheduled finish，也不能把它当作实际完成。completion 再提供自己的 worker/start/finish/value。`pre_assigned` 不替代 observed worker，arrival 不替代 completion time。

完整 `binary_support.py` 已实现 WPJ1 magic、追加 length framing、signed64 整数、UTF8 text、tuple 与 None 的编解码、读取顺序和 partial-frame 拒绝。测试的 `2**60+17` 位于 signed64 范围内，精确往返不经过 float；候选主要实现领域行与观察重放，不重写精度/字节 codec，也不宣称任意大小整数都可存。

## Part 3：admission、aging 与 simultaneous claims

三个 TODO 不能互相替代。

`eligible_ready_tasks` 先保留 `arrival_us <= now` 且 task topic 出现在当前 worker subscriptions 中的任务，并保留原输入顺序。topic 是声明字符串的精确匹配，没有 `*` wildcard 语法；再高的 priority 也不能让未来或未订阅任务进入候选集。

`effective_priority` 在真实 pull 时刻按 `task.priority + (now - task.arrival_us) // aging_interval` 算整数分。未来任务明确拒绝。`aging_interval` 的 positive int 校验已由正确 desk 给定；等待时间从 enqueue/arrival 开始，不从 service duration 或 clock 零点开始，也不是入队时算一次就永远不变。

`claim_free_workers` 建本批 remaining，按 free workers 声明顺序逐个处理。每个 worker 从剩余 eligible tasks 中取有效分最高的任务，同分使用原 task sequence；登记 claim 后立即移除该 task，下一 worker 不能再领取它。当前 ready/free 不含 running work，所以没有抢占。

P1 修好的 calendar 只推进事件。P3 独立实现 specialist、age score 和独占 claim，再通过 reopened P2 定义与完整 desk 联动。没有合适 worker 的任务留在 unfinished，不改成全局最优 matching、shortest-job 调度或按 `pre_assigned` 分配。

## Part 4：每种观察的 payload

`EventProjection.event_payload` 共同保留 `kind`、`task_id` 和本条 `time_us`，再按 phase 补字段：

- arrival：只有 `queued_priority`。
- pull：本条记录的 `worker_uid`、`start_us`、`finish_us`；不制造 result。
- completion：自己的 worker/start/finish 与 `result=event.value`；观察时刻是自己的完成 time，不是 start。

projection 不再调度或执行任务。完整 `wire_support.py` 已实现 JSON、UTF8 编码、4-byte big-endian payload byte length、async 发布和关闭。候选职责是 phase-specific 字段与真实时间/worker/result，byte count、cadence 和 close 的断言是正确依赖的集成护栏。

## Part 5：topic 交集、pool 可见性与完成量

完整 `GroupCatalog` 给出 group path、full worker/pool UID、ancestor 判定以及一次构建的 subtree worker catalog。相同 local worker 名字能对应不同 full UID，候选直接使用给定 resolver，不重新实现 scoped names 或 shared occurrence 遍历。

递归传递当前 topic scope。`Group.topics is None` 表示没有新增限制；显式 tuple 则与已有 scope 取交集，空 tuple/空交集保持为空。每个 worker 的 own subscriptions 再与 scope 相交，并按 worker 原声明顺序输出。

pool 视图包含本组声明的全部 pools，以及 owner 为 ancestor 且 `shared=True` 的 pools。private ancestor 不向下开放；sibling 即使有同名或 shared pool，也不在该 worker 的 ancestor chain。

先按 actual Completion 的 full worker UID 累计完成量。每个 worker 展示自己的 count；每组用给定 subtree worker UIDs 汇总本组及所有后代的实际完成。不能只加直接 worker、把全局总数复制给每个 worker，或把 queued/unserved work 当完成。catalog 提供结构，candidate 决定 topic/pool/actual-work 的领域语义。

当前题包有 36 条 assert、2 处 raises、五个测试与五个 skip 锁，登记 24 项错修。独立 source-first 验证覆盖 6 个领域错修：等 payload 的不同 task identity、完整 aging interval、声明 worker 次序、arrival 的 signed priority、显式空 topic restriction，以及 shared sibling pool 的祖先边界。6 个错修均在 NEW 完整副本中只使指定关失败、其余四关通过，配对 reference 均为五关通过；原规定 TEMP --write checker 的默认五锁、参考全五关、starter 五失败、逐层与全部 24 项错修检查通过。完整执行命令、内容 SHA、权限记录和日志见 exam 外 fresh-review.json。

## 这套题证明了什么，没证明什么

若候选实现通过全部原样测试，证据只支持：在声明的本地逻辑事件 adapter 中，能修结果与终止/事件数据结构，保存 observed lifecycle，实施明确的 specialist aging/claim policy，投影真实 trace，以及处理 nested topic/pool 边界与实际完成量。现有运行记录覆盖本机原样 reference 与六份测量版功能检查；原规定 TEMP checker 的五锁、参考全五关、逐层和全部 24 项登记错修也有实际通过记录；具体检查结果见 verification.txt 与独立验收记录，不计作候选成绩。人类 60 分钟用时尚未校准。

原 source 在线程启动前把全部任务预入队，空即退出在那份静态输入下正确。原 `fake_work` 用 sleep，并返回 task result，但三种 runner 都没有收集该返回值；原 main 只报告耗时与 worker counts。future arrivals、完整 logical result pool、journal、frame、精确 aging 规则和 nested manifest 都是课程概念的本地显式扩展，不宣称原源码已有该完整运行时。

本任务没有执行原 source、sleep、线程 demo、模型或网络。打印 speedup 和讲解中的历史运行结果不是这里的 oracle；逻辑时间与 event-calendar 性能不能证明真实线程并行收益、生产队列 durability、重试/幂等、broker 吞吐、真实 LLM 质量或当代框架事实。英文 output skill 仅作为来源数据读取，没有调用其流程。Python 3.10+ 是题包目标环境，现有测量记录使用 3.12.14，不代表已在 3.10 实际运行。

快版余量 8.0034× 紧邻门槛，本机测得的整组结果不是任意系统负载下的通用墙钟上界或生产 SLA。性能结论仅限上述完整 workload、业务路径、测量边界与当前运行环境。
