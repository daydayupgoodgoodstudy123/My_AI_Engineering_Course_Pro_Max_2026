# 面试官手册：PeerResult（16/12）

候选人计时期间不看本手册。候选人使用英文 README、`peerresult/` 和测试，逐关修领域实现，保留所有断言与完整 GIVEN。

## 开场（2 分钟）

- 总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间与难度尚未真人校准，不要求全部完成。
- 请候选人解释当前证据与下一步判断，可以随时澄清、查 Python 标准库官方文档。
- 只解除当前 skip，记录解锁到首次通过的时间、运行次数与 H1/H2/H3。卡住约 5 分钟后一次给一级提示，主持人不代写代码。
- 英文澄清在问到时回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 和本手册。
- 说明任务来自 deterministic local replay，无 HTTP、真实模型或 sleep。协议形状固定在课程快照，nested review 是领域证据树，不是 delegated agents。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | Which endpoint should polling use? | The discovered tasks endpoint supplied with that request, preserving the opaque task ID and optional query separately. |
| 1 | Does HTTP success imply task success? | No. The explicit task state determines completed or failed, and failed artifacts remain available. |
| 1 | What happens at a task's deadline? | Observe that tick first. A terminal result at the deadline wins; otherwise that task times out independently. |
| 1 | May completed tasks be polled again? | No. Keep their first terminal result, poll only pending IDs and return all results in request order. |
| 2 | Can attempts be collapsed by task ID? | No. Preserve every declared retry attempt, its own metadata and its associated artifact member. |
| 2 | Should JSON-looking text be decoded as structured data? | No. The complete tagged codec preserves text bytes and structured JSON according to the explicit tag. |
| 2 | Must replacement delete every old member file? | No. Reopening follows the complete current manifest; unreferenced old files do not define snapshot membership. |
| 3 | Is a2a-0.30 compatible with this pin? | No. Require the exact local a2a-0.3 value. This is not a current protocol compatibility exercise. |
| 3 | Can extra card keys replace required local fields? | No. Extra keys are permitted, but required fields retain their declared local shapes, including tasks endpoint and auth none. |
| 3 | Which modality should be selected? | The actual artifact tag, and only if the validated card advertises it. Text remains opaque. |
| 3 | What is a structured flat review? | Exactly issues and lines: issues is a list of strings; lines is a non-bool nonnegative integer. Preserve declared values and duplicate issue order. |
| 3 | Should I recompute the source line count? | No. Validate the declared count. Do not rerun the reviewer or change the source's counting formula. |
| 4 | Can an artifact change without a state change? | Yes. Compare the two observed dimensions independently and suppress equal repeats. |
| 4 | What is the event order? | Changed state, changed artifact, then one final event at terminal state. A projection observes one task. |
| 4 | Must I implement SSE escaping or transport closing? | No. Typed public views, terminal classification, the SSE codec and async publication/close driver are complete supplied dependencies. |
| 5 | Are groups delegated tasks or agents? | No. They are a local nested review-domain structure over declared files and inclusive line spans. |
| 5 | Must I resolve shared issue identities or expand membership paths? | No. The complete catalog supplies ordered occurrences, canonical issues and full paths. Build the recursive domain reports and checks. |
| 5 | What constrains a child group and an own issue? | A child stays in its parent's file and span. An own issue must match its group's file and lie within both the declared file and its own group span. |
| 5 | Should negative coordinates raise a type-validation error? | No. Coordinates are declared non-bool integers; negative or out-of-range values are audit inputs that produce located findings. |

## Part 1：discovery、terminal receipt 与 pending polling（目标 12 分钟）

四层缺陷：

1. make_poll_url 硬编码 default peer。正确 `LocalTransport.get → read_task` 在 producer 外两次调用后查不存在 peer/task，自然 KeyError；修 URL producer，不改 transport 或编造 task。
2. route parser 把 query suffix 当作 task ID。任务 identity 从 URL path 解码，query 不能污染 ID。
3. classify_terminal 把 failed TaskEnvelope 标为 completed。正确 status consumer 用 error/result 合同揭示错误；HTTP 成功不等于 task 成功，不编造 success 键或另一条异常链。
4. 每轮遍历全部原 requests 并真实 GET/JSON decode 已终态任务。只遍历 pending，终态或 timeout 后移除，保留第一次结果。

看什么：是否沿正确 consumer 找 producer；是否保留 discovered endpoint、task state 与所有 typed artifacts。LocalTransport、artifact conversion、status consumer、PollDesk intake 与完整 fixture 已正确 GIVEN。deadline 相等时 completion 优先、独立 timeout、输入序输出、empty batch 与首终态不覆盖是合同护栏，不是省略业务工作的理由。

P1 当前限值 0.07 秒。固定完整组慢版三次为 0.702968、0.670234、0.662439 秒，参考版为 0.002720、0.002595、0.002550 秒；两侧余量分别为 9.46342 和 25.73884。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另恢复重复 terminal GET/JSON decode；其余完整业务 guards 和全五关功能通过，不能说慢版通过原阈值。原样 reference 五关另行通过。规定 TEMP 校验已通过五锁、参考全五关、starter 五关失败、P1 分层、28 项登记错修和 reset 一致性检查，记录在 verification.txt。独立行为记录为 6 个核心错误及 1 个不计入核心数量的同方向辅助错误：对应参考全五关通过，错误各自由目标关捕获，证据在题包外 fresh-review.json。正式检查已通过，记录见 verification.txt；正式归档保留独立验收记录。 本机结果不是任意环境墙钟上界或生产 SLA。

提示：

- H1: "Which peer URL did the correct transport actually receive?"
- H2: "Did the query alter identity, and does this terminal receipt still say failed?"
- H3：分别修 discovered URL/path-only ID/保留 terminal state，再仅遍历 pending；结果按原请求序保留每个 task 的首终态与独立 deadline。

追问：

- "Why retain a failed artifact?"（它是失败任务的实际输出证据，HTTP 层成功没有抹掉失败。）
- "Which defects match the source demo?"（硬编码 poll 地址与 query suffix 是来源实际问题；source client 已识别 failed，没有批量 pending poller。）

## Part 2：ordered attempts 与 member association（目标 11 分钟）

主要坑：

- 同 task retries 都要留，manifest 记录各 attempt 自己的 task/attempt/peer/card/state/time，不能按 task ID 去重或排序。
- 每条 artifact 有自己的 member/tag 关联，load 不能复用首条 member 或最后 peer metadata。
- 重开完整当前 snapshot，并以 manifest 的声明序和 membership 恢复；不同 archive 互不影响。

看什么：是否把领域记录与独立 artifact files 正确关联。完整 explicit-tag codec、directory I/O 和 member_name GIVEN，精确 integer/JSON/text bytes 是依赖集成护栏，不考候选实现 codec。P2 不提供 P3 card/mode/schema solver；artifact 中的扩展 JSON data 也不应被 flat review adapter 的 schema 提前删掉。wire archive 只承诺 text/严格 JSON 值树，P5 typed bundle 不属于该持久化域。

提示：

- H1: "Which attempt owns this metadata and artifact member?"
- H2: "Did reopening retain both retries and the exact manifest order?"
- H3：按 attempts 声明序分配独立 member，把完整 envelope/peer/card metadata 与 member/tag 同存；load 逐行 manifest 重建，不合并同 task。

追问：

- "Why isn't the newest attempt enough for an archive?"（retry 过程与各次 peer/card/outcome 都是声明的审计记录。）
- "What defines membership after replacement?"（当前 manifest；物理旧文件是否还在不决定加载结果。）

## Part 3：card、modality 与 flat schema（目标 15 分钟）

三个独立 TODO：`validate_local_card`、`negotiate_review_modality`、`adapt_review`。

主要坑：

- exact `a2a-0.3` pin 不接受 prefix 匹配或新协议字段替代。校验 name/version、skills list、modalities、endpoints.tasks 与本地 auth 形状；extra card keys 允许。
- 以实际 artifact.type 对 advertised modes 协商，不取 modes[0]，不按 JSON-looking 内容推断模态。
- completed 的 structured flat data 必须同时包含 issues/lines，缺项不能补默认值；issues 必须 list[str]，lines 必须严格非 bool、非负 int，保留重复、顺序与 0。text 保持原文，不重算 declared lines。

看什么：是否分别实现三项 solver，消费 P1 正确 terminal receipt 与 P2 tagged data。P1/P2 没有提供 card negotiation 或 schema validator；本关消费真实 PollDesk→archive reopen 的 structured artifact，不能只对手填例子工作。name 要非空 string，version 为 string，skills 为 list[str]；modalities 非空且只含 text/structured，tasks endpoint 是非空 string，auth 恰为 `{'type':'none'}`。这是 local pinned contract，不是任意 protocol validator。

提示：

- H1: "Which literal version and local field shapes did the card promise?"
- H2: "Is this actual tag advertised, and are these declared review values valid?"
- H3：分开 exact card validator、actual-tag membership 和 flat schema adapter；strict int 排除 bool/float，保留 issues 顺序，text 分支不解析 JSON。

追问：

- "Why reject bool as a line count in Python?"（bool 是 int 的子类，但不是这里声明的行数类型。）
- "Why not fix the source count(newline)+1 while adapting?"（adapter 验证远端声明，重跑或改公式会改变输出合同与 opaque lifecycle 边界。）

## Part 4：change-only SSE projection（目标 10 分钟）

主要坑：

- state 与 artifact 独立比较；state 不变时也可能出现 artifact 或更新内容，不能被 state gate 吞掉。
- artifact 变为 None 也属于可见变化；相等 snapshot 抑制重复，变化事件按 state→artifact→final 排列，terminal artifact 先于 final。
- projection 完成后不再产出第二个 final；不从 snapshot 猜测远端内部 steps。

看什么：候选是否维护本 task 的 previous state/artifact 和 final 标记，保留观测到的变化。完整 public_artifact（含独立 data 副本）、terminal predicate、final_payload、SSE writer 与 async driver 都真 GIVEN；retained view 稳定性由完整 GIVEN 提供，tag/data/failed view 与 close 断言检查依赖集成，不是候选 ownership 或通用流式故障修复。

提示：

- H1: "Which observed dimension changed in this snapshot?"
- H2: "Would an unchanged state hide a new artifact, and where should final appear?"
- H3：分别比较与更新 state/artifact，按领域顺序收集 changed events；terminal 时最后发 final 并记住完成状态，codec/driver 保持给定实现。

追问：

- "Why is this still an opaque lifecycle?"（只投影实际 snapshots 的可见变化，不推断 agent 内部工作过程。）
- "Who stops pulling and closes after a terminal snapshot?"（完整 GIVEN driver；projection 负责领域事件和 final-once。）

## Part 5：recursive file/span review reports（目标 10 分钟）

主要坑：

- 真递归构造 GroupAudit，保留每层 own findings 和 ordered child reports；只平铺 occurrence 检查不能替代层级报告。
- child group 必须与 parent 同 file，且 inclusive span 完全包含于 parent；自身 span 还要在声明 file 行区间内。
- 每个 own issue membership 检查文件归属、declared file lines 与 own group span，不能只在更宽的祖先范围内合法就放过。
- unknown bundle/group schema 在完整 path 产出 Finding，不终止其余约束审计；收集其余领域 findings，边界含最后一行。

看什么：是否将递归报告与领域约束放在正确 group 层。global lookup、ordered shared occurrences、canonical unique issue collection、tag dispatch 和已建 report flatten 全部 GIVEN，不要求候选写 resolver、shared-DAG walk、dedup 或 recursive ownership。typed line counts/coordinates 为非 bool 整数，负或越界值要成为 findings。group 是 review evidence，不是 task delegation 或 subtree budget；text leaf 检查还使用真实 polled/archived/flat-adapted 证据。

提示：

- H1: "Which group owns this report and this issue membership?"
- H2: "Does the child stay inside its parent, and does the issue fit its own file and group?"
- H3：递归传入 parent 检查 child file/span，逐层只检查 own occurrences，构造有序 GroupAudit children，再用给定 flatten 汇总所有 located findings。

追问：

- "Why can unique issue count differ from membership count?"（canonical 包含所有声明 issue，含未引用者；membership 包含全部 group refs，同 issue 可以多处引用，这两种集合均由完整 Given 提供。）
- "Why validate declared file lines rather than review the source again?"（这里审计远端结果 schema 与 domain constraints，不重新执行 code review。）

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层 polling 与完整结果 | 20 | discovered URL/query-free ID 6；failed receipt 4；pending-only 完整性能路径 6；独立 deadline/首终态/输入序 4 |
| ordered attempt archive | 20 | 完整有序 retry manifest 8；own metadata/member association 8；snapshot replacement/reopen 4 |
| pinned review adapter | 25 | exact card/字段形状 8；actual advertised mode 7；strict flat schema/declared values 10 |
| change-only observation | 15 | 独立 artifact/state 变化与抑制 8；领域事件顺序 4；final once 3 |
| recursive review audit | 20 | ordered GroupAudit/own findings 6；child file/span 5；own issue file/line/group 检查 7；schema/path/inclusive boundary 2 |

每个子项按实际代码、测试现象或口头推理评分：完整满足得满分，有具体反例的部分实现得部分分，未实现或未观察得 0。另记提示、用时和运行次数，不把 reference 结果算作候选成绩。

当前题包为 45 Python 文件、5 tests、40 assert、5 raises、5 skip 与 28 项登记错修。P1 当前限值 0.07 秒。固定完整组慢版三次为 0.702968、0.670234、0.662439 秒，参考版为 0.002720、0.002595、0.002550 秒；两侧余量分别为 9.46342 和 25.73884。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另恢复重复 terminal GET/JSON decode；其余完整业务 guards 和全五关功能通过，不能说慢版通过原阈值。原样 reference 五关另行通过。规定 TEMP 校验已通过五锁、参考全五关、starter 五关失败、P1 分层、28 项登记错修和 reset 一致性检查，记录在 verification.txt。独立行为记录为 6 个核心错误及 1 个不计入核心数量的同方向辅助错误：对应参考全五关通过，错误各自由目标关捕获，证据在题包外 fresh-review.json。正式检查已通过，记录见 verification.txt；正式归档保留独立验收记录。 本机结果不是任意环境墙钟上界或生产 SLA。