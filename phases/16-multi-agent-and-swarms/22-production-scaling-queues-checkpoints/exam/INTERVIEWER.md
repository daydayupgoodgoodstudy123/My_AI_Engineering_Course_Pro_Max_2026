# 面试官手册：OutboxFlow（16/22）

五关共 100 分。建议主持 60 分钟：开场 2 分钟，Part 1/2/3/4/5 分别 12/10/16/8/12 分钟。时间是练习预算，未经真人校准；允许记录未完成部分后进入复盘。

## 开场（2 分钟）

可以直接读给候选人：

> “You maintain an offline durable-execution service. Work through the five parts in order, explain the invariant you are restoring, and run only the unlocked tests. Later parts use your earlier code. The support modules are complete Given; preserve their contracts and the supplied test assertions.”

说明编辑范围：P1 在 `primitives.py` 修已有行为；P2 在 `store.py`；P3 在 `execution.py`；P4 在 `stream.py`；P5 在 `structure.py`。只移除当前关的 skip 装饰器。模型、输入绑定、codec、SQLite transaction resource、独立 receiver、CSV writer、scoped catalog 和 delivery driver 已给定；需要正确调用它们。

要求候选人先复述现象和预期，再定位 producer 与 consumer。卡住时先给 H1，随后 H2、H3；记录提示时间及提示后的独立推导。不要将提示后的完成记成无提示完成。

## 澄清问题的标准回答（English FAQ）

| 关 | 候选问题 | 标准回答 |
|---|---|---|
| 1 | Should I catch the first KeyError in the state reader? | “No. The consumer correctly reads a required field. Trace which checkpoint the producer selected and preserve the consumer contract.” |
| 1 | Is a step a string or a floating-point value? | “It is an arbitrary nonnegative Python integer. Compare the original integer numerically; the large-step case also guards against a lossy shortcut.” |
| 1 | May a new input release a pending response? | “No. Only acknowledgement of that response's exact input UID releases it. A wrong acknowledgement raises without changing the pending response.” |
| 1 | Does the batch drain run the three-state agent for every message? | “No. QueueDesk is an explicit batch input adapter. It returns all actual inputs and consumes them for the complete count and signed-amount report; the single-message state machine has its own checks.” |
| 1 | Is the 0.10-second threshold calibrated? | “It has a recorded complete local calibration with every actual input and output retained. Wall-clock margins vary by environment and do not define an SLA.” |
| 2 | Must I implement Decimal or container encoding? | “No. The exact codec and immutable replay discriminator are complete Given. You own the domain keys, field association, typed reconstruction and pending projection.” |
| 2 | Should each record writer commit? | “No. The caller owns the transaction. A low-level writer must participate without committing independently, so an enclosing failure can roll back the whole operation.” |
| 2 | Can replay overwrite the original runtime or state? | “No. Identical immutable replay retains the original record; conflicting reuse is rejected by the supplied Rows contract.” |
| 2 | Should pending use only a run ID or effect ID? | “No. Select the requested run and match acknowledgements by the complete run, step and effect key.” |
| 3 | Does the sender transaction include the receiver effect? | “No. The receiver is an independent SQLite resource. Commit the sender intent first, deliver independently, then persist the actual returned receipt.” |
| 3 | May dispatch read an open sender transaction? | “No. Check the supplied transaction_open resource observation and reject before contacting the receiver; only committed sender intents are eligible for independent delivery.” |
| 3 | May I fabricate a receipt that looks correct? | “No. The acknowledgement must contain the actual receipt returned by receiver.deliver, whose independent durable effect is observable.” |
| 3 | What closes the send-before-ack gap? | “Retry the same stable composite key. The complete Given receiver stores its effect and original receipt together and returns that original receipt on a matching retry.” |
| 3 | Is a terminal checkpoint sufficient to return immediately? | “No. A committed intent can still be pending. Drain committed pending work before deciding which numeric plans remain.” |
| 3 | Which fault model is scored? | “The four one-shot exception cuts are after_checkpoint, before_commit, after_commit and after_send. Close and reopen the independent resources; this is not real process, network or concurrent-worker fault testing.” |
| 4 | Should resume use the event's newly proposed version? | “No. Successful resume, failed resume and finish all refer to the run's original binding. New starts use their declared runtime choice.” |
| 4 | Does a retire event kill a runtime? | “No. It is an observed request. Report permission only when that version has zero active runs.” |
| 4 | Must I write CSV quoting or an async transport? | “No. The typed event intake and CSV publication driver are complete Given. You own event replay, bindings, counts and row values.” |
| 5 | Must I repair short-name lookup or mailbox ownership? | “No. Full UID and scoped local lookup, owner paths and mailbox binding are complete Given. Same local names across groups remain legal and must be used correctly.” |
| 5 | Is self delivery legal? | “Yes. When source and destination are the same endpoint, its route has one hop. Same-group traffic between different endpoints has two; do not invent a duplicate self hop.” |
| 5 | Must I implement the admin-versus-leaf origin classifier? | “No. bind returns the complete origin classification. Consume that result; the candidate algorithms are the admin ladder, crossed export boundaries and recursive report.” |
| 5 | Is checking the source group's export enough? | “No. Every source-ancestor boundary crossed on the way out needs its own declaration. A valid hop list does not grant export permission.” |
| 5 | Should other runs disappear from every route audit? | “No. Audit each declared message's route. Filter requested-run accepted outbound messages when building outputs; the supplied delivery driver also uses the requested run.” |
| 5 | May I flatten the hierarchy into one output list? | “No. Retain each group's own route audits, ordered child audits and declared outbound outputs at its actual full path.” |
| 全部 | Is this production exactly-once execution? | “No. These are finite local fixtures with a complete explicit idempotent receiver. There is no arbitrary external API, lease, fencing, network or multi-worker guarantee.” |

## 每关：主要坑、观察、提示和追问

### Part 1 checkpoint / ack / FIFO（12 分钟，20 分）

主要坑按实际数据流展开：latest 混入另一个 run；step 按字符串排序；RESPONSE 自行释放；FIFO 从 list 头部反复移除。首个错误在正确的 `resume_checkpoint → read_required_state` consumer 读取目标字段时出现；应修选择结果。

观察候选是否先限定 run 再按原 int step 取最大，缺失 run 返回 None；是否区分 PROCESSING 与等待 ack；是否保留所有真实输入、顺序、run counts 和 signed amount。任意大 int 是合法域护栏，不能通过 float 转换修排序。

- H1：“Which run and step produced the state currently read by this consumer?”
- H2：“Inspect checkpoint selection, then follow the pending response while another input arrives.”
- H3：指向 `CheckpointStore.latest` 的过滤与 key，以及 `AgentQueue.step` 的 response 分支；FIFO 部分询问每次删除队首需要移动多少现有元素。

追问：“Why does a faster queue still need the acknowledgement checks?” 观察点：数据结构只改变出队成本；匹配 UID、状态转移和 response/input 关联仍是行为合同。批量 drain 返回实际 Envelope，不等于运行了并发 agent 状态机。

### Part 2 transaction-aware domain records（10 分钟，20 分）

主要职责是三个独立记录的业务关联与读回：checkpoint 的 run/step/version/state；intent 的 run/step/effect/amount/destination/payload；receipt 的 key/receiver/amount/result。pending 按指定 run 与完整 acknowledged key 关联。所有低层写服从 caller 的 atomic scope。

完整 exact codec、Rows 事务资源和通用 immutable conflict discriminator 是 Given。巨大 step、Decimal coefficient/scale 和 bool/int 等是原样字段投影的依赖护栏，不是候选 precision-conversion 算法或单列评分项。

- H1：“Which fields identify this record, and which fields must survive reopening unchanged?”
- H2：“Check each domain tuple against its own model; then inspect how receipts remove pending intents.”
- H3：指向 checkpoint key `(run, step)`、intent/receipt 的完整 `(run, step, effect)` key，以及低层方法不能独立 commit 的边界。

追问：“What would a commit inside write_checkpoint break?” 观察点：外层异常无法再撤销已提交 checkpoint；P3 无法组合出真正原子的一对记录。P2负责逐 record projection；完整跨 record 组合属于P3。

### Part 3 commit / dispatch / recovery（16 分钟，25 分）

三个 TODO 分别承担真实算法：

1. `commit_checkpoint_and_intent`：在同一 sender atomic scope 写 checkpoint 和 intent；after_checkpoint、before_commit 都在事务内，after_commit 在事务外；此函数不调用 receiver。
2. `dispatch_intents`：先检查Given资源观测 `transaction_open`，若sender事务仍打开则拒绝且不调用receiver；随后遍历该 run 实际 pending；原 key 发送给独立 receiver，after_send 发生在 receiver 返回后、sender ack 前；随后持久化真实返回 receipt。
3. `recover_outbox`：先 drain 已 committed 的 pending，再以修好的 P1 latest 选择该 run 的 numeric checkpoint，继续大于 latest 的声明 plans，并返回真实 durable state/intents/receipts。

- H1：“At this crash cut, which resource has committed and which evidence is still missing?”
- H2：“Separate sender commit, receiver delivery and sender acknowledgement; then inspect terminal-checkpoint recovery.”
- H3：让候选为四个 cut 写出 checkpoint/intent/effect/receipt 的前后状态，并将初始 pending drain 放在判断剩余 plans 之前。

追问：“Why is sending the same key twice safe here?” 观察点：receiver自己的独立事务保存 key、effect、result 与 receipt；匹配重发返回原 receipt。不能仅凭 sender done flag，也不能把保证外推到任意非幂等外部API。

四cut应明确：after_checkpoint/before_commit均回滚sender pair且无effect；after_commit保留pair而尚未发送；after_send可能已有独立effect而sender receipt为空。重开后以同key恢复，并保留完整audit。terminal checkpoint + pending intent 仍需发送。

### Part 4 rainbow bindings CSV（8 分钟，15 分）

候选维护 run→original version 的绑定与 active run 集合。start 采用声明choice；resume/failed_resume/finish读取旧binding；finish移除active但不删除binding。每行计算该行实际version的active count；仅retire且count=0时允许退休。

Given负责event-kind intake、CSV header/quoting和async publication，不提供bindings/count状态算法。合法域不包含未知版本、重复start或finish后resume，不另加off-domain validation主坑。

- H1：“Does this event create a binding, or refer to an existing run?”
- H2：“Follow old across deploy v2, successful resume, failed resume and finish.”
- H3：区分 `bindings` 与 `active`；每行只统计其实际version的active runs，retire_allowed须同时满足retire事件与零active。

追问：“Why retain a finished run's binding?” 观察点：完成事件与审计仍属于原runtime；active membership和runtime identity是不同状态。

### Part 5 nested admin routes / exports（12 分钟，20 分）

主要评分落在三项真实候选算法：

- 根据完整Given source/destination paths构造LCA上行、共同admin和下行阶梯；同group不同endpoint直接两hop，同endpoint自投递一hop，跨组避免相邻相同endpoint重复。
- 对每条确实离开的source祖先边界逐层检查export声明；hop合法和export合法独立检查。
- 递归生成每group自己的RouteAudit、ordered children和full path；outputs只保留本group声明、源在其子树内、目标在其外、accepted且属于请求run的Message。

完整scoped resolver、endpoint ownership/mailbox binding、origin classification和 `deliver_audit` 是Given。候选必须使用这些结果，但不把重复短名解析或origin分类重新写成主算法。delivery driver只消费accepted/current-run的候选audit并投递，不替候选决定route。

- H1：“Which group boundaries does this message actually cross, and what is its lowest common group?”
- H2：“Write the source ascent and destination descent separately; inspect every exited ancestor's exports.”
- H3：指向两path公共前缀；上行包含source group到共同group的admins，下行从共同group下一层到destination group；再递归构造own/children/declared current-run outbound outputs。

追问：“Why can a deep message need both deep and a export declarations?” 观察点：它先离开deep，再离开a；一层声明不授权另一层。另问：“Why does a same-group message reach its mailbox without becoming a cross-group output?” 观察点：direct route accepted与outbound output选择是不同条件。

末关实际链路是P1 Envelope → P3独立receiver → P2重开receipt payload → Message → 候选nested audit → Given mailbox delivery。观察每关真实数据是否被消费，不能用手填早关结果替代。

## 记录与评分（100 分）

按实际行为和代码证据评分。共享依赖失败需定位责任关，不能把同一根因在多关反复扣满；能解释但未实现的部分单独记录。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | own-run选择与缺失run | 5 | |
| 1 | 原int step数值latest，consumer保持正确 | 4 | |
| 1 | pending response、匹配ack与FIFO相关性 | 6 | |
| 1 | 完整实际burst输出与队首算法成本 | 5 | |
| 2 | checkpoint key及完整原version/state关联 | 7 | |
| 2 | intent完整identity/amount/destination/payload投影 | 6 | |
| 2 | actual receipt、pending fullkey关联与caller事务归属 | 7 | |
| 3 | sender pair原子组合与事务内外crash边界 | 9 | |
| 3 | 独立原key发送、真实receipt后ack | 8 | |
| 3 | 初始pending drain、numeric继续与完整RecoveryReport | 8 | |
| 4 | start choice与原run binding，包括failed_resume/finish | 6 | |
| 4 | own-version active count与零active退休条件 | 5 | |
| 4 | 每事件完整own row、顺序与Given CSV集成 | 4 | |
| 5 | LCA完整上行／下行admin路径 | 7 | |
| 5 | 每个跨越source祖先的export许可 | 6 | |
| 5 | recursive own/children/fullpath与declared current-run outputs | 7 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

P2 exact codec是Given；P5 scoped binding/origin/delivery也是Given。正确使用依赖纳入所属行为证据，不能将这些完整Given算法重复列为候选主评分。

## 当前验证边界

<!-- VALIDATION_STATUS_BEGIN -->
当前42个PY文件、五测试、47条assert、5处pytest.raises、五锁与25个登记错误写法。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部25项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。

P1真实负载150000条immutable Envelope输入；完整QueueDesk.drain_burst与whole BurstReport equality（全部ordered UID/run/amount/body、各run counts与signed amount）都在timer内，fixture与独立expected在外。batch adapter返回完整入站数据，不等于逐条运行并发三态agent；单条ack状态另有行为护栏。

完整校准三个慢样本[1.2884170829784125, 1.3393366250675172, 1.353035124950111]秒，三个快样本[0.008853374980390072, 0.008932374883443117, 0.009660790907219052]秒；限值0.10秒，慢侧／快侧余量12.884171／10.351119。六份测量副本只将timingassert改为elapsed打印，慢版另恢复真实list队首移除；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有完整五关通过记录。墙钟观测受环境影响，不构成跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->

当前领域覆盖包括相同numeric step的跨run独立checkpoint、sender未提交事务的dispatch拒绝、RecoveryReport own-run receipts、failed resume的active状态，以及各group完整route observations与输出source-subtree归属。
