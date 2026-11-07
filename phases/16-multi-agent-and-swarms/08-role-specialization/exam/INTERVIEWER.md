# 面试官手册：SOPForge（16/08）

候选人计时期间不看本手册。候选人使用英文 README、`sopforge/` 和测试；只补领域实现，不改测试、正确 GIVEN 或关卡顺序。

## 开场（2 分钟）

- 说明总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时为 12、11、15、10、10 分钟。时间和难度尚未经过真人校准，不要求全部完成。
- 请候选人边做边说明证据与判断，可以随时澄清、查 Python 标准库官方文档。目标是让测试原样通过，解除当前 skip 后再进入下一关。
- 记录每关从解锁到首次通过的时间、pytest 次数和 H1/H2/H3。主持人不代写代码；卡住约 5 分钟时一次给一级提示。
- 需求问题只在问到时用下表英文回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 和本手册。
- 说明题包只运行声明的本地可信代码 fixture；这里的 `exec` 不提供隔离，不让候选人另接不可信程序或真实模型。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | Is the critic approval enough to ship? | No. It is a finite structural review. The deterministic verifier must execute every declared case and retain its evidence. |
| 1 | May a literal or comment containing a function definition count as that function? | No. The contract requires the declared module-level function with a return statement. |
| 1 | Can I always call add_two or stop after the first passing case? | No. Bind spec.task_name and retain every declared success, mismatch and exception. |
| 1 | May I cache the namespace between verifications? | No. Compile and bind once per verification. The supplied session executes once, shares its namespace across those cases and starts fresh for the next verification. |
| 2 | Do critic and verifier reports share a persisted slot? | No. Keep distinct role slots for each artifact revision and link them to the exact specification revision. |
| 2 | Must I implement SQLite transactions or the value codec? | No. The complete database and tagged-codec primitives are supplied. Use them without narrowing or reshaping values. |
| 3 | Who should answer missing information? | Ask the declared owner of each missing required field. Do not invent a value or ask about unrelated optional fields. |
| 3 | Which answer may create a new revision? | Only one matching the active question, field, owning role and current base specification revision. |
| 3 | Should clarification rerun the whole pipeline? | No. Invalidate only field-dependent slots and resume only the requested blocked step through the real critic and verifier. |
| 3 | What happens to another pending question after an answer? | Reissue every still-unanswered pending step question against the new specification revision, keeping its declared owner. |
| 3 | Does an explicit zero mean missing? | No. Field presence is handled by the supplied helper. An explicit zero is provided information. |
| 4 | Is critic prose a testcase result? | No. Project the actual executed verifier cases, including successful cases, in their recorded order. |
| 4 | Must I write XML escaping, async cadence or outcome classification? | No. The complete classifier, writer, counts and driver are supplied. Provide the domain entries with their own evidence and identity. |
| 5 | Is a declared kind label sufficient? | No. Check the real producer, declared kind and actual typed payload against the role port contract. |
| 5 | Can a parent expose an arbitrary descendant or undeclared record? | No. A stage exposes only its own declared valid output ports. |
| 5 | Must I implement scoped identity lookup or revision-link algorithms? | No. The complete catalog and link helpers are supplied. Call their validation as secondary guards. |

## Part 1：完整可信验证（目标 12 分钟）

四层缺陷：

1. critic 用 substring 接受 literal 里的伪 `def`。错误沿 `VerificationDesk.inspect → verifier → callable_lookup` 在正确消费者自然抛出 `KeyError`；根因是批准了不存在的函数，不能改 lookup 掩盖它。
2. verifier 绑定硬编码 `add_two`，忽略 `spec.task_name`。同一 artifact 中两个看起来合理的函数会让它查错对象。
3. 首个成功就返回，漏掉后面的 mismatch 和 exception，也丢掉完整证据。
4. 每个 case 重新真实 compile 同一 artifact 并绑定 callable。应每次 verification 只 compile/bind 一次；完整 GIVEN `ExecutionSession` 在慢、快路径都只 exec 一次，case 共享其 namespace，下一次 verification 再创建独立 session。

看什么：是否顺着真实 consumer 的合同找到上游批准错误；是否分别修 declared callable、完整 case loop 和编译/绑定作用域；是否保留两种报告、原 artifact、digest 及每个 case。完整 session 保证 once-exec；计数函数检查其正确使用与 case 间状态连续，重复 inspect 与 changed source 检查 verification 间隔离，不能用跨 artifact 缓存换速度。

性能路径使用含 600 个真实声明 case 的 `TABLE` artifact。fixture 和独立预期在 timer 外；完整 inspect 与完整输出相等检查在 timer 内。本机独占完整三慢三快测得慢路径 0.903041 / 0.980894 / 1.125314 秒，参考路径 0.003861 / 0.003669 / 0.004244 秒；限值 0.08 秒，双侧余量为 11.288 / 18.848 倍。六份测量副本仅把 timing assert 换成 elapsed 输出，慢路径另恢复逐 case 的真实 compile/bind；全部功能护栏与另外四关均通过，不表示慢路径通过原限值。原样五测试参考实现已通过；业务 timer 与整个 pytest wall time 分开记录。不能用只看首尾 case、固定结果、删证据或不执行来换速度。

提示：

- H1: "Which function was actually created before callable_lookup consumed the approval?"
- H2: "What happens after the first passing case, and which declared function is being called?"
- H3：分别指向结构 critic、`spec.task_name`、完整 case loop 与 compile/bind 的作用域；正确 lookup 和报告构造不需修改。

追问：

- "Why is a fresh dictionary not a security sandbox?"（它没有进程隔离、资源限制或不可信代码防护。）
- "What does passing these cases establish?"（仅这些声明输入的行为，不证明任意输入或一般程序正确。）

次要集成护栏：完整编译/session helper 只把真实编译或模块 exec 异常包装为 `TrustedLoadError`，正确 desk 仅捕获该类型，保留 `executed=False`、`passed=False`、空 cases 和独立 `load_error`。不能广泛 catch 正确 lookup 的 `KeyError` 来掩盖第一层根因；这不是第五个候选缺陷。

原课 critic 本来就是 substring 模拟器；原课 verifier 已经一次执行并遍历全部测试。后三处是本题的教学回归，不能说原 demo 也有相同缺陷。P1 不要求 question/revision/resume。

## Part 2：revision-bound SQLite snapshot（目标 11 分钟）

主要坑：

- artifact ID 相同的不同 revision 都必须保留；只按 ID 保存或重组会串旧新证据。
- critic 和 verifier 是独立 role slots；critic 批准与 verifier 失败可以同时存在，不能合成一个 approval。
- 重开时以 artifact/spec 的完整 revision keys 做 join，并保持 snapshot 声明的 spec 与 bundle 顺序。
- 保存的是当前完整 snapshot；被替换掉的 artifact 不应重新出现。尚未产出 artifact 的 planner spec 也必须保留，不能只保存已执行的子集。

看什么：能否把 snapshot 拆成 spec、artifact、critic、verifier 领域行，再按复合 identity 组回；是否调用完整 `require_bundle_links` 后使用给定事务。大整数、signed zero、UTF8、嵌套参数和原 source 的往返是 codec 使用护栏；事务、commit、建表和字节精度不是候选需要重写的主要坑。

提示：

- H1: "Which revision owns each of the two reports?"
- H2: "Does an artifact ID alone identify the saved source and its specification?"
- H3：指向各 role kind、复合 revision key、spec lookup 和按 artifact 行重建 bundle；db/codec 已完整给定。

追问：

- "Why keep a critic-approved but verifier-failed bundle?"（它保留两个角色不同的判断与失败证据，后续修订和复盘需要。）
- "Why should a rejected binding preserve the previous snapshot?"（无效证据不应替换已保存的完整 dossier；给定事务与校验按此合同使用。）

## Part 3：owner 澄清与局部恢复（目标 15 分钟）

三个独立 TODO：`required_field_questions`、`apply_clarification_answer`、`resume_blocked_step`。

主要坑：

- 缺失 required 字段要向各自声明 owner 提问，阻塞目标 step；不能继续执行、猜值或询问无关 optional 字段。
- Answer 必须匹配 active question ID、field、owner、spec ID 和当前 base revision，不能让旧答案或别的角色推动新 revision。
- 新 revision 要保留所有仍未解 pending step 问题的 owner 并重新生成问题 identity；不能丢其他 step 的问题或继续接受旧 revision 的答案。
- 字段变化只 invalidate 声明依赖它的 slots，包括旧 rejected 结果；无关 completed bundle 保持原对象与 run count。
- 一个 target blocked 时不得恢复另一个 step；只 resume 请求的 blocked target，一次 executor 后真实走 repaired critic/verifier。已保留完整结果不重复执行，critic approved 但 case 失败仍是 rejected。

看什么：是否把问题、答案和新 revision 的转换写清；是否在依赖边界保留可复用证据；是否避免把所有 steps 重跑或直接制造通过报告。presence、finite lookup、question ID 与新 revision/预算构造都是完整 GIVEN，不把通用 missing/default 判断列为主要算法。

提示：

- H1: "Which role owns the missing field for this step?"
- H2: "Which active question and base revision does this answer satisfy?"
- H3：将三步分开检查：生成义务、验证答案并局部失效、仅目标执行后调用真实 VerificationDesk；不要清空无关 artifact/report。

追问：

- "Why invalidate an old rejected slot as well as a completed slot?"（两者都基于旧字段，旧拒绝证据也不能当新 revision 的结果复用。）
- "Why is resume not a new critic-only approval?"（critic 检查结构，行为结论仍要来自实际 verifier case evidence。）

## Part 4：case evidence 的 JUnit 投影（目标 10 分钟）

主要坑：

- 遍历真实 `VerifierReport.cases` 的全部记录，成功 case 也保留，不能把 critic prose 当测试或只输出失败。
- mismatch 的 message 来自自己的 expected/got，body 保留自己的 args；exception 用自己的 error type、原 message 和 args，不能串到邻近 case。
- classname 关联本次 spec ID、revision 和 task_name；artifact revision 可独立变化，不能替代 spec revision。name 使用实际 case ID，保持证据顺序。

看什么：同步 `case_entries` 是否只做领域选择和诊断组装，不重跑代码；是否在成功时不制造 issue。完整 outcome classifier 已区分 failure/error，空异常消息仍是 error；XML writer、escaping、counts、async pull/publication/close 全部 GIVEN，相关断言是集成护栏，不是通用流节奏考题。

提示：

- H1: "Which completed verifier case owns this JUnit entry?"
- H2: "Where do expected, got and exception evidence come from for this case?"
- H3：指向全部 case、case-specific 诊断与 classname/name；把分类和 XML 编码交给给定依赖。

追问：

- "Can an approved critic justify a passing testcase?"（不能；testcase 来自实际执行证据。）
- "What distinguishes a mismatch from an execution error?"（前者得到不符合期望的值，后者调用抛异常；保留的证据不同。）

## Part 5：nested SOP typed ports（目标 10 分钟）

主要坑：

- 每层 role 有自己的 required inputs；producer、kind 和实际 typed payload 都要符合，critic report 不能填充 verifier 的 executor artifact input。
- 输出要同时符合 port、真实 producer、声明 kind 和实际 payload type；改 kind 标签不改变 payload。
- `exposes` 只能展示本层已声明、且符合本角色输出 port/producer/kind/payload 合同的输出；为空时不展示本层有效输出，不能凭名字制造输出或展示任意 descendant record。
- 按声明顺序对所有 nested stages 应用同一合同，保留完整 path 和每层独立 issues。

看什么：是否使用完整 `SOPCatalog` 解析 handle/path，依照 `ROLE_INPUTS`/`ROLE_OUTPUT` 检查真实角色边界，并调用现成 payload/revision link helper。revision link 校验属于次要防错护栏；候选不重写其算法。短名作用域查找、通用 recursive ownership 不是主要考点。

提示：

- H1: "Which producer and payload type does this role port require?"
- H2: "Was this exposed output actually produced at this stage?"
- H3：把 required inputs、typed outputs、declared exposes 分开检查，再调用给定 link helper；身份解析已经完整实现。

追问：

- "Why check the payload type after checking its kind string?"（标签可以与实际对象不符，schema 必须落到 payload。）
- "Why keep critic and verifier as separate output contracts?"（它们的职责、证据来源与 schema 不同，批准不等于确定性通过。）

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层调试与完整验证 | 20 | 结构根因 5；声明 callable 4；全部 cases 5；单次编译/绑定、正确 session 与完整性能路径 6 |
| 持久化建模 | 20 | revision 复合关联 8；独立两 role slots 5；顺序/完整 snapshot 4；正确使用校验与给定依赖 3 |
| owner 澄清与局部恢复 | 25 | 按 owner 提问 5；active answer/base revision 7；选择性失效 6；只恢复目标并实际验证 7 |
| 领域流式展示 | 15 | 全部真实 cases 5；case-specific 诊断 6；身份和正确使用完整 driver 4 |
| SOP 合同与解释 | 20 | typed required inputs 6；真实 producer/kind/payload 6；声明 exposes/全部层次 5；给定次要校验与证明边界 3 |

每个子项按实际证据给分：完整满足得满分，部分正确但仍有反例得部分分，未实现或未观察得 0。逐项写下代码、测试现象或口头推理证据；提示级别、用时、运行次数另记，不凭印象补分，也不把参考实现结果记到候选成绩。

当前计数为五 tests、43 assert、6 raises、五 skip、27 项登记错修。当前原样五测试参考实现通过；独立 source-first fresh 的 7 个有效 core 方向初抓 1、漏抓 6，最终均为目标关失败且其他四关通过，全部 matching reference 五关通过。27 项登记错修与默认锁、starter、分层修复、reset 已由规定原 TEMP `--write` 检查器全部通过。完整三慢三快校准证据保持。60 分钟尚无人类计时校准。题包只验证本地可信 fixture，没有真实 LLM、网络、任意代码隔离、通用正确性或来源中外部统计的最新核验。
