# 参考实现讲解：PeerResult（16/12）

计时结束后再看。参考实现位于本目录的 `peerresult/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前合同；原样 reference 五关和固定完整性能组已有本机运行记录，静态阅读本身不产生运行证据。

## Part 1：discovered endpoint 与 pending lifecycle

make_poll_url 应从传入的 discovered tasks endpoint 拼接经过 quote 的 opaque task ID，再附加独立 query。硬编码 default peer 时，正确 LocalTransport.get 分解 URL 后调用 read_task，在不存在的 peer/task 上自然 KeyError。错误在 producer 外两次 consumer 调用之后暴露；不能修改正确 transport 或制造默认 task。

task_id_from_route 从 urlsplit(route).path 取最后一个路径段，再 unquote。不能把 `?trace=1` 作为 task identity。source 本来也用 suffix split 处理 route，讲解明确指出 query 问题；source client 硬编码 poll endpoint 与 discovered submit endpoint 不一致，也是来源实际问题。

classify_terminal 只处理 completed/failed，保留 document 的真实 state、artifact 与观察 tick。HTTP GET 成功只代表拿到了 task document，不代表 task completed。正确 envelope_status 根据 typed state 显示 error/result；第三层是行为断言，不是编造 success 键引起的异常。source client 本来已识别 failed 终态，failed-as-completed 是本题显式局部回归。

poll_pending 保存 pending 与 results。每个 logical tick 只遍历当前 pending 的稳定副本，做真实 local GET/JSON decode；先 classify terminal，再对仍未完成且 tick 到 deadline 的 task 生成 timeout。这样 completion 恰在 deadline 时有效，每个 task 有自己的超时预算。终态结果只记录一次并从 pending 移除，最后按原 request 顺序返回所有 completed/failed/timeout receipts，不用完成先后重排。

P1 当前限值 0.07 秒。固定完整组慢版三次为 0.702968、0.670234、0.662439 秒，参考版为 0.002720、0.002595、0.002550 秒；两侧余量分别为 9.46342 和 25.73884。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另恢复重复 terminal GET/JSON decode；其余完整业务 guards 和全五关功能通过，不能说慢版通过原阈值。原样 reference 五关另行通过。规定 TEMP 校验已通过五锁、参考全五关、starter 五关失败、P1 分层、28 项登记错修和 reset 一致性检查，记录在 verification.txt。独立行为记录为 6 个核心错误及 1 个不计入核心数量的同方向辅助错误：对应参考全五关通过，错误各自由目标关捕获，证据在题包外 fresh-review.json。正式检查已通过，记录见 verification.txt；正式归档保留独立验收记录。 本机结果不是任意环境墙钟上界或生产 SLA。

deadline、首结果不覆盖、empty batch 和 working 不提前终止都是声明合同。PollDesk intake、LocalTransport、artifact conversion、status consumer 与完整 fixture 已正确 GIVEN；P1 不提供 P3 card/mode/schema solver。source 没有批量 logical poller，不能称其原 demo 也存在本题的批量重复轮询实现。

## Part 2：manifest 与每次 attempt 的 artifact

save 按声明序枚举全部 Attempt。每条 manifest 记录自己的 task_id、attempt、peer、card_version，以及 envelope.task_id/state/observed_at。artifact 存在时，用完整 member_name 分配独立文件，经 encode_artifact 得到 explicit tag 与 payload，并把 member/tag 写回该条 manifest；没有 artifact 时 member/tag 为 None。

load 按 manifest 顺序，取本条自己的 member/tag 交给完整 decoder，再重建 TaskEnvelope 与 Attempt。不能按 task_id 折叠 retries，不能排序 task/attempt，不能复用首条 artifact member 或最后一条 peer。replacement 覆盖完整当前 manifest，加载 membership 只由它决定；旧的未引用 member 文件不需要为本合同删除。不同目录是独立 snapshot。

完整 codec 对 text 做原 UTF-8 bytes 往返，对 structured 做 JSON 编解码，不做 text 内容嗅探。JSON-looking text、Unicode、精确整数、空数组/null 与精细 float 是正确 codec 的集成护栏，候选不重写精度算法。archive 的普通 structured data 限于严格 JSON 值树：list、字符串键 dict、string/int/bool/null 与有限 float；P5 typed ReviewBundle 是另一 local domain，不保证可存进 wire archive。archive 不提前套用 P3 的 flat review schema；P2 codec 不提供 card negotiation 或 schema validator。

## Part 3：三个独立 adapter TODO

validate_local_card 固定 local protocol_version 恰为 `a2a-0.3`，不是 startswith。name 是非空 string，version 是 string，skills 是 list[str]；modalities 是非空 list 且只含 text/structured，endpoints.tasks 是非空 string，auth 恰为 `{'type':'none'}`。card 可有额外键，但不能以 newer protocol 字段替代 required local shapes。这里不要求把 name/version/skills 的值锁为示例中的某一组字面量，也不宣称当前协议兼容性。

negotiate_review_modality 先验证 card，再检查实际 artifact.type 是否 advertised，返回实际 tag。不取 card.modalities[0]，也不从 data 内容猜模态。显式 text 就是 opaque text，即使内容像 JSON。

adapt_review 消费 P1 已正确分类的 terminal envelope，只接受 completed 且有 artifact 的成功结果。text 要为 string，直接成为 ReviewResult.text。structured data 必须是 dict 且键恰为 issues/lines，缺项不能以空 issues 或 0 lines 补齐；issues 必须 list[str]，按原序保留重复字符串；lines 必须 `type(value) is int` 且非负，bool/float 都不合法，0 是合法声明。返回的 issues 用 tuple 表达，不经过集合去重，lines 不经 float。

这里验证的是远端声明的 flat review schema，不重新运行词法 reviewer，不据本地 source 重新计行，也不修 source 的 count(newline)+1。P1 的正确 failed receipt、P2 的 tagged artifact 都是真实依赖，但没有给出本关三项算法。实际整合路径先由 PollDesk 取得 structured terminal artifact，经 AttemptArchive save/reopen，再交 adapt_review 消费。

## Part 4：state 与 artifact 的独立变化

TaskProjection 为单 task 保存 previous state、previous artifact 和 final 标记。每个 snapshot 用完整 public_artifact 得到明确 tag/data 的 public view；分别比较 state 与 artifact。第一次 submitted 且 artifact=None 只发 state，重复相等观察不发事件；state 不变而 artifact 出现、内容改变或从有值变为 None 时仍发 artifact。相等的 None 后续观察不重复发事件。

按本次 snapshot 的领域顺序产生 local-state、local-artifact，再在 terminal 时追加 local-final 并设置完成标记。重复调用 final snapshot 返回空 tuple，不再制造 final。failed 的 artifact 保持原 text/tag；这由完整 final_payload/public view 提供，候选不重新解释为成功或结构化结果。

完整 public_artifact 已复制 data，使保留的 public snapshot 不被 incoming data 的后续修改影响；候选不重写这项 ownership 逻辑。完整 terminal predicate、typed public views、SSE JSON/UTF-8 frame codec 和 async pull/publish/close driver 已 GIVEN。driver 在 terminal observation 后停止拉取并关闭 source。候选实现 change suppression/order/final-once，不重写 cadence、escaping 或网络订阅，也不猜 opaque peer 内部执行步骤。

## Part 5：真正的 recursive GroupAudit

structured leaf 是本地 typed ReviewBundle，不是 P3 的 flat JSON review schema。完整 review_leaf/ReviewCatalog 已提供 tag-aware dispatch、global file/issue/group lookup、ordered group/own occurrences、canonical issues 和每个 membership 的 full path。text leaf 原样返回 ReviewAudit.text，不解析 JSON；真实 polled text 经 archive reopen 与 flat adapter 后仍保留同一原文，再交本层审计。共享 issue 的多个 membership 与 canonical unique count 都已由依赖提供。

candidate 为每个 root group 递归构造 GroupAudit。每层检查 own schema 是否 issue-group-v1；从 catalog 查 declared file，缺失记 group-file，否则检查 inclusive `1 <= start <= end <= file.lines`，无效记 group-lines。非 root child 还要与 parent 同 file，且完整 span 在 parent span 内，否则记 child-span。未知 bundle schema 在 `('artifact',)` 位置记 schema finding。

逐层只检查该 group 的 own occurrences：issue 文件未知或不等于 group.file，记 issue-file；已知 file 下不在 inclusive physical line interval，记 issue-lines；不在 own group.start/end 内，记 group-membership。这些检查独立收集，不因 schema 不认识或某一项失败就丢掉其他 finding；issue-lines 始终使用 issue 自己声明 file 的物理行数，不借用 group file 的较宽范围。坐标为声明的非 bool 整数，负或越界值是被审计的数据，不作为 generic type-validation 异常。合法最后一行与单行 span 都包含在范围内。

递归按声明序产生 child reports，每层保留 own findings，不能用一份平铺 findings 替代 GroupAudit 树。最后用完整 all_group_findings flatten 已建好的 reports，把 root schema finding 放在前面，得到稳定的 nested findings 顺序。unique_issues 来自全部声明的 canonical collection，包含未被 groups 引用的 issue；memberships 来自全部 group-reference occurrences。一个 issue 两处引用就有两个 membership，不要求候选 dedup 或再展开 identity graph。

file/group/span schema 与 recursive audit 是 source flat issues/declared lines 的本地领域扩展，不是 A2A task delegation、recursive ownership 或 budget tree。完整 expander 没有提供 domain validator，候选仍需构造层级报告并检查 child/own constraints；声明 file lines 也不通过重新读取或运行被 review 的代码计算。

## 这套题证明了什么，没证明什么

若候选通过全部原样测试，证据只支持本地有限合同：修正 discovered polling 与 terminal/pending 行为，重开完整 ordered attempt/artifact snapshot，实现 pinned card/mode/flat schema，投影 observed changes，并递归审计 declared review groups。当前原样 reference 五关和固定完整性能组已有本机记录；TEMP、独立行为与正式检查各有独立的验收边界，不能以 reference 或计时版结果替代。当前数量为 45 Python 文件、5 tests、40 assert、5 raises、5 skip、28 登记错修，数量不是执行证据。

来源固定于课程内 `a2a-0.3`、`/.well-known/agent.json` 和 custom REST，不是当前 A2A wire specification 的实现或符合性证明。原 source 的 keyword reviewer 不是实际模型审查；source 已识别 failed，未提供本题 batch poller、archive、SSE 或 nested DSL。四份来源未执行，英文 output artifact 只作数据，没有调用其流程；日期、采用量与框架声明是来源快照，未作当前外部核验。

logical deadlines 不证明网络超时策略，local replay 不证明跨组织互操作、鉴权、并发快照一致性、生产 review 质量、任意代码正确性或 sandbox 安全。file spans 只依据声明值审计，不是重新分析 source。Python 3.10+ 为目标环境，没有该版本实际运行声明；60 分钟及各关用时尚未真人校准。

P1 当前限值 0.07 秒。固定完整组慢版三次为 0.702968、0.670234、0.662439 秒，参考版为 0.002720、0.002595、0.002550 秒；两侧余量分别为 9.46342 和 25.73884。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另恢复重复 terminal GET/JSON decode；其余完整业务 guards 和全五关功能通过，不能说慢版通过原阈值。原样 reference 五关另行通过。规定 TEMP 校验已通过五锁、参考全五关、starter 五关失败、P1 分层、28 项登记错修和 reset 一致性检查，记录在 verification.txt。独立行为记录为 6 个核心错误及 1 个不计入核心数量的同方向辅助错误：对应参考全五关通过，错误各自由目标关捕获，证据在题包外 fresh-review.json。正式检查已通过，记录见 verification.txt；正式归档保留独立验收记录。 本机结果不是任意环境墙钟上界或生产 SLA。