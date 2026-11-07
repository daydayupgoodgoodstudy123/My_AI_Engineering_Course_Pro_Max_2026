# 参考实现讲解：RoutineHop（16/11）

计时结束后再看。参考实现位于本目录的 `routinehop/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前合同，参考五关和完整性能组已有本地运行证据，原规定 TEMP 的全部检查已通过，独立行为验收的 6 个不同机制均按各自目标关抓住，配套参考五关通过；正式检查已通过，记录见 verification.txt。

## Part 1：opaque intake、outgoing origin 与有界 guard

`order_token` 已完整识别声明范围的 decimal token。订单 ID 是不做算术的 key，`00077` 必须原样进入 ReadyRefund；若先转 int 再转 str，就变成 `77`。正确 `IntakeDesk.refund` 调用 `refund_receipt`，后者调用 `refund_lookup`，因 lookup 里只有 `00077` 而自然 KeyError。根因在 producer，错误在它之外两次 consumer 调用后暴露；不能改 lookup 或制造默认 receipt。

缺 token 时返回 AskForOrder，IntakeDesk 因此不调用 receipt，也不记录 refund invocation。原 source 确实使用缺失默认订单 42，讲解要求询问；但 source 已保留找到的数字字符串，所以本题 int 归一化是局部教学回归。显式 `0` 是正常 opaque ID，不按数字真值替换。

`make_transfer_receipt` 把 from_name 放进 sender、to_name 放进 target。source 本来也用 outgoing active.name 记录 handoff；incoming sender 的错误属于本题 producer。这个 receipt 是 origin evidence，不能让正确 consumer 替 producer 猜来源。

LastKLoopGuard 保持本 run 的 `deque(maxlen=3)`，只有当前 event 是 Transfer 时才 append。Note 不消耗 slot，也不清空最近 handoffs。完整 `is_two_agent_ring` 已检查三条 directed edges 是否在两个不同 routines 间交替；three-agent triangle 与 self edge 都不满足。stopped 成立后保持 True；每次 ReplayDesk.replay 都创建独立 guard。

完整 audit 由 caller 顺序保存全部 events，guard 只维护有界在线判定状态。不应为每条 observation 清空 deque 并扫描已经增长的完整 audit；也不能裁掉 audit 以换取速度。ReplayDesk 在 exit 后继续保留每条输入、receipt 和 sticky decision；这里是审计 replay，不执行退出后的真实 handoff 工具。

性能 fixture 的 cycles=2700，含 8,103 条真实 handoff receipts、1,621 条 notes，共 9,724 observations。fixture 与独立 expected 在 timer 外；完整 `ReplayDesk.replay` 和整个 `ReplayReport` equality 在 timer 内，包括 audit、所有 receipts、每条 stopped 与 first_stop，之后才取得 elapsed。其他完整性断言仍保留。当前固定完整校准组的慢版三次为 0.770186、0.758556、0.752337 秒，参考版为 0.004450、0.004494、0.004490 秒；相对 0.075 秒限值，两侧余量分别为 10.03116 和 16.68830 倍。六份 NEW 完整副本只把计时阈值断言替换为实际 elapsed 输出，慢版另含真实全 audit 重放回归；其余完整业务断言与五关功能均通过。这不表示慢版通过原阈值。原样参考五关也已通过；原规定 TEMP 的五锁、参考五关、逐层与全部 25 项登记错修检查已通过；独立行为验收的 6 个不同机制均按各自目标关抓住，配套参考五关通过；正式检查已通过，记录见 verification.txt。不得预填 report、少处理 observations 或在首个 exit 截断输入。

P1 只有 intake、receipt producer 与 typed edge audit guard，不提供 P3 raw-return classifier、batch binding 或 transfer-tail solver。source 没有 last-K 实现；这是 Ship It/Exercise 2 概念的本地补全，不能说原 demo 也有该重复扫描缺陷。

## Part 2：caller continuity 与 runtime identity

Continuation 包含 session、active Agent、完整 typed receipt history 与 request_ids。持久文档只存四个声明字段：session、active、history、request_ids；active 存名称，不把 Agent 的 instructions/functions/callable 定义放进 JSON。save 用完整 typed receipt codec 按原序保存全部 history，并保留完整 request ID 序列；只替换该 session 对应 snapshot。

load 用完整 reader 打开文档，逐条 decode typed receipts，把 history 与 request_ids 恢复为声明 tuple，并调用 `catalog.agent(saved_active_name)`。新 runtime 即使 routine 名相同，Agent 与函数对象也可能不同；必须使用当前 catalog 实例，才能继续执行它自己的工具。tool-free Agent 或旧缓存 Agent 都不能代替该重绑定。

精确 JSON 读写、typed receipt tag 和 session-to-file mapping 已完整 GIVEN。普通 result 合法域是严格 JSON 值树：list、字符串键 dict、string/int/bool/null 和有限 float，不承诺任意 tuple、callable 或 Python 对象。大于 2^53 的整数不用经 float，Unicode、空文本与 null 正常保留；包含 `functions` 键、function/invoke 文字的普通 data 也完整保留。它们是正确依赖的集成护栏，候选重点是完整 caller schema 与 runtime identity。

## Part 3：一个批次的三条边界

`bind_batch_owner` 在任何调用前，先遍历全部 ToolCall，创建携带原 active owner、call 和该 owner 实际 function 的 BoundCall。完整 catalog 负责按 owner 解析，同名 `same` 在 A/B 可能绑定不同函数。合法域要求每个 call 的 tool（包括以后 skipped 的尾部）都存在原 owner namespace，不能在 transfer 后才改到新 namespace 查找。

`interpret_raw_tool_return` 只在实际 `isinstance(value, Agent)` 时返回 AgentReturn，其余合法 text/严格 JSON data 返回 DataReturn。一个含 name/instructions/functions 的 dict 是普通业务 data；内容相似不等于 runtime control object。真实 Agent 也不能转为 repr 再伪装普通工具文本。

`run_batch` 顺序调用 bound functions。DataReturn 形成保留 call_id/owner/tool/value 的 CallResult。AgentReturn 先交给完整 `catalog.transfer_target`，获得当前注册目标，或声明的首个安全 routine fallback；再生成 outgoing Transfer，更新 current，并进入 tail skip 状态。之后每个 call 都生成 CallSkipped，但绝不 invoke。下一次 run_batch 才从报告的新 active 绑定自己的全部函数。

只捕获声明的 ToolFailure，把该 call 记录为 CallFailed 后继续；其他编程异常不统一吞掉。空批次返回原 active 与空 receipts。目标 canonicalization/fallback、lookup/invoke 和 error type 是完整 GIVEN 依赖；候选仍须正确调用，但这些集成护栏不构成额外主要 solver。所有调用都是注入的本地 callable，没有模型调度或实际外部退款。

## Part 4：每种 typed receipt 的公开字段

`receipt_kind` 已完整按实际类型分类。ReceiptProjection 只做本条领域投影：

| 类型 | 公开字段 |
|---|---|
| CallResult | kind、call_id、tool、owner、result |
| Transfer | kind、call_id、tool、sender、target |
| CallSkipped | kind、call_id、tool、owner、reason |
| CallFailed | kind、call_id、tool、owner、error |
| Reply | kind、sender、content |

result 保持 JSON data，不用 Python repr；target 是 receipt 自己的目标，不拿 sender 替代。CallSkipped 没有执行，所以没有 result，after-transfer 是 reason。projection 不执行工具，也不再解释 raw Agent return，直接消费 P3 的 typed receipts。

完整 codec 负责 JSON escaping、UTF-8 与单条 newline，async driver 逐项 pull/publish，并在正常结束或消费者提前断开时关闭 source。相关完整性和 early-close 断言检验依赖集成；本关不要求重写 generic cadence、关闭逻辑、字节计数或 classifier。

## Part 5：独立 runs 的 caller composition

source 明确 run 间状态由 caller 管理，多个 runs 也由 caller 组织；main 的 active/history 只在单次 run 内保留，讲解提出返回 history+active 续接。RunNode/BatchStep/ChildRun 与 typed nested audit 是这些概念的显式本地适配，不是 source 已有 DSL 或 SDK 运行时。

对一个 RunNode，先从 catalog 取自身 initial，建立本层 active、history、steps。遇到 BatchStep，用传入的真实 P3 batch_runner 执行该层当前 active 与 calls，记录 OwnBatchAudit 的 step ID、before/after 和 receipts；把 receipts 接到本层 history，并以 report.active 续接下一 own batch。不能每个 batch 都回到 initial，也不重写或硬编码 batch solver。

遇到 ChildRun，递归审计 child 自己声明的 RunNode，结果包成 ChildAudit 放入当前 steps。child 从自己的 initial 开始，不接受 parent/sibling 的 current；返回时也不覆盖 parent active/history。这样 children 与 own batches 保持声明的交错顺序，而 parent history 只含 own receipts。即使最后一步是 child，parent final 仍是本层 active；没有 own batch 的 parent 保留自身 initial 与空 history。

完整 RunCatalog/RunDesk 已校验 finite typed tree、global unique run IDs、每层 unique step IDs 和可解析 initial routines，并提供真实 P3 solver 默认依赖。候选实现的是递归 continuation composition；不实现 namespace/shared-DAG/全局 visited 算法，也不重新分类 raw Agent 或复制 batchtail 逻辑。child active 泄漏和拿末尾 child final 作为 parent final 是同一隔离机制的相邻反例。

最后可把 parent 的实际 final Agent 与 own history 组成 Continuation，经 P2 store 保存并在当前 runtime reopen；nested child audit 仍保留在 steps 中，不为持久化 parent 而把 child receipts 塞进 parent history。


当前本地行为检查覆盖重复 receipt 的 occurrence、Agent 子类的 control return、任何 invocation 前的全量 original-owner lookup、Reply 的真实 routine sender、own history 前缀只拼接一次，以及 caller composition 的每个 own batch 只执行一次。它们服从现有 typed/严格 JSON/finite tree 合同；不改变完整 GIVEN、batch 合法工具域、caller 隔离语义或时间预算。

## 这套题证明了什么，没证明什么

若候选通过全部原样测试，证据只支持本地有限合同：保留 opaque order 并在缺失时询问，正确记录 outgoing handoff，增量审计 last-three typed edges，持久化完整 caller continuation 并重绑定 runtime tools，执行 original-owner/Agent-control/skip-tail 批次，投影完整 typed receipts，以及组合独立 caller runs。当前原样参考五关与固定完整性能组已有本地证据；原规定 TEMP 的全部检查已通过，独立行为验收的 6 个不同机制均按各自目标关抓住，配套参考五关通过；正式检查已通过，记录见 verification.txt。静态数量为 45 Python 文件、5 tests、41 assert、0 raises、5 skip、25 项登记错修，数量本身不是执行证据。

原 source 的 scripted_router 是确定性关键字规则，没有真实模型，也未读取 instructions/history。原 source 已保持数字字符串与 outgoing sender；默认订单 42 是其实际简化，其他本地 adapters 不可归为 source 已有缺陷或服务。四份来源只作静态阅读，英文 output artifact 未作为 skill 调用。课程中的框架谱系、日期和 SDK 说法是来源快照，未作当前外部核验。

普通 data 仅保证严格 JSON 值树范围，有限 tree/catalog 合同不证明任意 Python 对象安全、通用授权、模型质量、生产退款正确性或 SDK 行为。caller composition 不证明并行执行隔离或任意 distributed workflow。Python 3.10+ 是目标环境，没有该版本实际运行声明；60 分钟及各关时间尚未经过真人校准。

P1 的 0.075 秒限值已有固定完整组测量：慢版 0.770186/0.758556/0.752337 秒，参考版 0.004450/0.004494/0.004490 秒，两侧余量 10.03116/16.68830。六份测量版完整五关功能通过；慢版阈值断言由实际 elapsed 输出替代，不能据此说它通过原阈值。原样五测参考另行通过。测得余量受本机运行环境影响，不构成任意负载下的通用墙钟上界或生产 SLA，也不证明真实模型收益。
