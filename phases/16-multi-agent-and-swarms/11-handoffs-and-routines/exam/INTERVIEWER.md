# 面试官手册：RoutineHop（16/11）

候选人计时期间不看本手册。候选人使用英文 README、`routinehop/` 和测试，逐关修领域实现，保留完整 GIVEN 与断言。

## 开场（2 分钟）

- 总时长 60 分钟：开场 2 分钟，Part 1–5 参考用时 12、11、15、10、10 分钟。时间与难度尚未真人校准，不要求全部完成。
- 请候选人解释当前证据、根因与下一步判断；可以随时澄清，并查 Python 标准库官方文档。
- 只解除当前 skip，记录解锁到首次通过的时间、运行次数和 H1/H2/H3。卡住约 5 分钟时一次给一级提示，主持人不代写代码。
- 英文澄清只在问到时回答；追问用于理解取舍，不增加实现要求。计时期间关闭 solution 和本手册。
- 说明 refund 与 tool effects 都是本地 fixture，无真实财务、模型或网络调用。调用方负责 continuation；typed batches、JSON snapshots 和 nested run audit 是公开本地合同。

## 澄清问题的标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | Is an order ID a number? | No. Preserve the exact discovered decimal token as an opaque string, including leading zeros and explicit zero. |
| 1 | What if no order token is present? | Return AskForOrder before invoking a refund receipt. Do not invent an order ID. Token discovery is supplied. |
| 1 | Who sends a handoff receipt? | The outgoing routine. The target is the incoming routine. |
| 1 | What are three consecutive handoffs? | Three typed directed Transfer edges alternating between two distinct routines. Notes neither consume a slot nor reset the edge window. |
| 1 | May the audit stop at the first loop exit? | No. Exit is sticky, but replay retains every remaining observation, receipt and decision. Each run has an independent guard. |
| 2 | What is persisted for the active Agent? | Its name only. Rebind it through the supplied current runtime catalog when reopening. Do not serialize callable definitions. |
| 2 | Which ordinary data values are supported? | Strict JSON value trees: lists, string-key dictionaries, strings, integers, booleans, null and finite floats. Arbitrary tuples or Python objects are outside this contract. |
| 2 | Should callable-related words be removed from tool data? | No. A functions key or function/invoke text may be ordinary data. Preserve it through the complete receipt codec. |
| 2 | Must I implement exact JSON encoding or file naming? | No. Typed codecs, exact JSON storage and stable session file mapping are complete supplied dependencies. Preserve the full caller schema and order. |
| 3 | Which namespace owns a batch? | The routine active when the batch starts. Bind every call before invocation, including the later skipped tail; every tool name belongs to that original owner. |
| 3 | Does an Agent-shaped dictionary transfer control? | No. Only an actual Agent object does. Other successful returns are strict JSON data or text. |
| 3 | What happens after the first Agent return? | Resolve the target with the supplied policy, emit a transfer receipt and skip every remaining call without invoking it. The next batch uses the new active routine. |
| 3 | What happens on ToolFailure or a removed target? | Record declared ToolFailure and continue. Other programming errors propagate. The complete target policy canonicalizes registered targets and supplies the declared safe fallback. |
| 4 | Which fields should a skipped call expose? | Its kind, call ID, tool, owner and reason. It has no executed result. |
| 4 | Do I classify receipts or implement async transport? | No. Use the complete typed classifier, NDJSON codec and pull/publish/close driver. Project each current receipt's own domain fields. |
| 5 | Does a child inherit the parent's active routine? | No. Each child starts from its own declared initial routine and owns its continuation. |
| 5 | Can a child's final routine become the parent's final routine? | No. Only the parent's own batches update its active routine, even when a child is the last step. |
| 5 | Does parent history include child receipts? | No. Parent history contains its own batch receipts only. Preserve child audit separately in the declared interleaved step structure. |
| 5 | Must I implement tree identity checks or a second batch interpreter? | No. Finite typed tree validation and routine lookup are supplied. Reuse the repaired real Part 3 batch solver. |

## Part 1：opaque intake、outgoing receipt 与 online guard（目标 12 分钟）

四层缺陷：

1. `prepare_refund_request` 把 `00077` 经 int 改成 `77`。正确 `IntakeDesk.refund → refund_receipt → refund_lookup` 在 producer 外两次 consumer 调用后自然抛 KeyError。修 token producer，不改正确 reader 或补默认订单。
2. 缺 token 却制造 ReadyRefund("42")，会消费未请求订单；应返回 AskForOrder，且不调用本地 receipt。
3. Transfer sender 误用 incoming routine，破坏 outgoing origin evidence。
4. 每条 observation 都从完整 audit 重建最后三条 edge。候选应增量维护有界 typed edge state，完整 audit 仍由 caller 保留。

看什么：是否把订单的 lexical identity、缺失时的显式询问、handoff 的 outgoing 责任和 audit/guard 两种状态分开。`order_token`、refund consumers、`is_two_agent_ring` 与完整 replay service 已正确 GIVEN；候选不重写通用 token parser 或 ring predicate。Note 不占 slot、triangle/self edge 不触发两方交替、sticky exit、独立 run 和显式 0 是合同护栏。

性能 fixture cycles=2700，真实产生 8,103 handoffs 与 1,621 notes。fixture/独立 expected 在 timer 外；完整 ReplayDesk 与整个 ReplayReport equality 在 timer 内，包含完整 audit、receipts、stopped 与 first_stop。当前限值 0.075 秒；固定完整校准组两侧余量为 10.03116/16.68830，慢版最大业务 elapsed 0.770186 秒、完整五关 subprocess wall 最大 0.907349 秒。测量副本只替换 timingassert 为 elapsed 输出，慢版另有真实全 audit 重放；它们通过全部其他功能要求，不声称慢版通过原阈值。不得删 audit、少处理 observations、提前停读或硬编码 report 来提速。

提示：

- H1: "Which exact order ID reached the correct receipt lookup?"
- H2: "Was an order actually supplied, and who is the outgoing routine on this receipt?"
- H3：原样保留 token，缺失返回 AskForOrder；receipt 用 from_name；guard 只增量接纳 Transfer，保留独立的完整 caller audit 和 sticky stop。

追问：

- "Why are leading zeros part of identity here?"（它是业务 key，不是需要算术的数量。）
- "Why keep all observations after the exit flag?"（这里 replay 审计每个输入，exit 是判定证据；它不执行退出后的真实 handoff 工具。）
- "Which of these defects is already present in the source demo?"（缺订单默认 42 确实存在；原 source 已保留数字字符串并正确记录 outgoing sender，没有 last-K 实现。）

## Part 2：caller snapshot 与 runtime rebinding（目标 11 分钟）

主要坑：

- 保存完整有序 typed receipt history、session 和 request IDs，不能只留最后一条或丢失 caller identity。
- active 持久化为名称，load 从当前 catalog 获得实际 Agent 与该 runtime 的 callable namespace；不能序列化函数、重建 tool-free Agent 或复用旧 Agent。
- 只替换该 session 的完整 continuation，其他 caller 保留；普通 result 中的 `functions` 键和相关文字仍是 data。

看什么：是否分清可持久化的领域证据与 runtime definition。精确 JSON/typed receipt codec、session-to-file mapping、routine lookup 真正完整 GIVEN。大整数、null、空文本、Unicode 和 opaque nested data 是依赖集成护栏，不要求候选手写精度编码。普通值合法域严格为 JSON 值树，不把任意 Python 对象往返扩大为要求。

提示：

- H1: "Which caller fields survive reopening, and which Agent must come from the current runtime?"
- H2: "Did the reopened active routine expose the new catalog's own tool function?"
- H3：存 session、active.name、全量 typed receipts 与 request IDs；load 用完整 codec 还原 history/order，并按名称查当前 catalog。

追问：

- "Why can equality of a name be insufficient for runtime continuation?"（名字只是持久 identity，继续执行要用当前注入的真实 callable 定义。）
- "Why preserve a functions key inside a result?"（普通 JSON data 不因字段名相似就变成 runtime code。）

## Part 3：original-owner batch 与 control return（目标 15 分钟）

三个独立 TODO：`bind_batch_owner`、`interpret_raw_tool_return`、`run_batch`。

主要坑：

- 批次开始时完整 upfront bind，owner 与 function 都属于原 active routine。同名 tool 在 A/B 可能有不同函数；后来转移 active 不能让尾部改绑，也不能跳过尾部 upfront lookup。
- 仅实际 Agent 是 control return。文本和 Agent 形状的 dict 是普通 data，不按 name/instructions/functions 键推断 transfer，也不把 Agent repr 当工具结果。
- 执行到首次 transfer，记录 outgoing receipt、新 active 和每个尾部 CallSkipped，尾部 callable 不调用；下一批才使用新 namespace。

看什么：是否区分函数归属、返回值类型与副作用边界。完整 catalog lookup/invoke 是 GIVEN，但不提供 batch solver。只捕获声明的 ToolFailure，记录 CallFailed 后继续；空批次保持 active。完整 `transfer_target` 做 target canonicalization/缺失目标 safe fallback，相关断言检验 helper 集成，不是第四个主要算法。合法域中所有 calls 的 tool 名都在 original owner namespace，raw successful return 为实际 Agent 或严格 JSON 值树；不扩大通用输入验证。

提示：

- H1: "Which routine owned every function when this batch began?"
- H2: "Is this return an actual Agent, and have any tail callables already run?"
- H3：先构造全部 BoundCall，再分类每个真实 invoke return；首次 control 后保留 skip receipts 而不 invoke，并将新 active 仅传给下一批。

追问：

- "Why bind a call that will later be skipped?"（完整批次先按原 owner 解析，执行边界不改变其声明归属；合法尾 call 也必须存在原 namespace。）
- "Why continue after ToolFailure but stop effects after transfer?"（前者是声明的局部失败；后者改变控制权，合同明确同批尾部不执行。）

## Part 4：typed receipt 的 NDJSON 证据（目标 10 分钟）

主要坑：

- 各 receipt 保留自己的 call ID/tool/owner 或 sender，以及 result/target/error/reply 等类型专属字段，不借用相邻事件。
- 普通 structured result 保持 JSON data，不能转成 Python repr 或字符串。
- CallSkipped 公开 reason，不能伪造 result；transfer 的 target 不能被 sender 替代。

看什么：是否消费 P3 已决定好的 typed receipts，不重跑工具、不再分类 raw Agent。完整 `receipt_kind`、JSON UTF-8 codec 和 async driver GIVEN；newline/Unicode/close/early disconnect 的断言检查正确依赖的集成，不考 escaping、byte count 或通用 cadence。

提示：

- H1: "Which typed receipt owns these fields?"
- H2: "Did this call run, transfer, fail or get skipped?"
- H3：用完整 classifier 分支，保留各类型自身字段；CallSkipped 只有 reason，structured result 原样交给 codec。

追问：

- "Why isn't after-transfer a tool result?"（工具根本没有执行，公开为 result 会制造不存在的执行证据。）
- "Who closes the source on an early disconnect?"（完整 GIVEN driver；候选保证自身投影与其集成，不重写关闭逻辑。）

## Part 5：nested independent caller runs（目标 10 分钟）

主要坑：

- own BatchStep 从本 run 当前 active 执行，用真实 P3 BatchReport 更新该 run 的下一 own batch，不能每步回到 initial。
- ChildRun 从 child 自己声明的 initial 开始，parent/sibling 的 active 不注入 child；child final 也不回写 parent。最后一步是 child 时，同样不能拿 DFS 最后节点当 parent final。
- own history 只拼接自身 batch receipts；steps 保留 own/child 的声明交错和 typed wrappers，不能 flatten 或把 child history 混入 parent。

看什么：是否把一个 run 内的 continuation 与 caller 组合多个独立 run 分开。完整 finite-tree/global-run-ID/typed-step 校验、routine lookup、audit types 与 RunDesk intake 已 GIVEN；P3 是真正复用的 flat batch solver，递归 continuation 未提供。child state leak 与拿 child final 作 parent final 是同一隔离机制的相邻反例，不拆成多个独立主要算法。没有 own batch 的 parent 保留自身 initial 与空 own history。

提示：

- H1: "Whose active routine should the next own batch continue from?"
- H2: "Which run owns this child history and final routine?"
- H3：为每个 run 建独立 active/history；own batch 更新本层，child 递归返回 ChildAudit 且不修改本层；保留原 steps 顺序，最后返回本层 active。

追问：

- "How does this follow from stateless caller-owned continuity?"（每次独立 run 的 initial/continuation 由其调用方显式提供，嵌套结构不自动共享 active。）
- "Can parent history be persisted without flattening child audit?"（可以，P2 保存 parent 实际 own continuation；child audit 独立保留在 steps 中。）

## 记录与评分（100 分，原创练习）

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| 分层 intake 与完整 replay | 20 | opaque ID 4；缺失先问 3；outgoing sender 4；有界增量 guard 与完整 replay 9 |
| caller snapshot 与重绑定 | 20 | 全量有序 receipts 7；active identity/runtime callable 重绑定 8；session/request IDs/完整替换 5 |
| original-owner batch 算法 | 25 | upfront owner/function binding 8；实际 Agent/data 分类 7；首 transfer/无尾副作用/下一批 active 10 |
| typed 公开证据 | 15 | 各 receipt 自身领域字段 8；structured JSON data 4；skip 不伪造 result 3 |
| 独立 caller continuation | 20 | own sequential active 6；child 独立状态 6；own history/有序 typed steps 6；continuation reopen 集成 2 |

每个子项依据实际代码、测试现象或口头推理评分：完整满足满分，有具体反例的部分实现得部分分，未实现或未观察得 0。另记提示、用时与运行次数，不把 reference 检查计入候选成绩。

当前题包为 45 Python 文件、5 tests、41 assert、0 raises、5 skip、25 登记错修。当前固定完整校准组的慢版三次为 0.770186、0.758556、0.752337 秒，参考版为 0.004450、0.004494、0.004490 秒；相对 0.075 秒限值，两侧余量分别为 10.03116 和 16.68830 倍。六份 NEW 完整副本只把计时阈值断言替换为实际 elapsed 输出，慢版另含真实全 audit 重放回归；其余完整业务断言与五关功能均通过。这不表示慢版通过原阈值。原样参考五关也已通过；原规定 TEMP 的五锁、参考五关、逐层与全部 25 项登记错修检查已通过；独立行为验收的 6 个不同机制均按各自目标关抓住，配套参考五关通过；正式检查已通过，记录见 verification.txt。60 分钟真人用时未校准。原 source 与英文 output artifact 未执行，框架事实没有当前外部核验。

当前本地行为检查覆盖重复 receipt 的 occurrence、Agent 子类的 control return、任何 invocation 前的全量 original-owner lookup、Reply 的真实 routine sender、own history 前缀只拼接一次，以及 caller composition 的每个 own batch 只执行一次。它们服从现有 typed/严格 JSON/finite tree 合同；不改变完整 GIVEN、batch 合法工具域、caller 隔离语义或时间预算。
