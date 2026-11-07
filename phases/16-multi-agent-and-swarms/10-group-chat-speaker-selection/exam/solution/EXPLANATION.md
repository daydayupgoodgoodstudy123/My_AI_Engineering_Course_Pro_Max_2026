# 参考实现讲解：FloorFair（16/10）

计时结束后再看。参考实现位于本目录的 `floorfair/`；可在自己的练习副本用 `python3 -m pytest --solution --all-parts` 检查。这里解释当前合同，静态阅读不产生运行通过结论。

## Part 1：终止、最近视图与真实发言

第一个 `KeyError` 在正确 `approval_reader` 出现。`ChatDesk.run` 遇到 `Please do not TERMINATE` 时，suffix rule 提前结束，完整 report 中没有 reviewer 的真实 approved evidence。之后 `approval_card` 调 reader 按 reviewer 读取，自然找不到。根因是 stop intake，不是 consumer；不能补一个默认 approval。

本地合同要求 `content.strip() == 'TERMINATE'`。否定句只是普通内容，首尾空白可以忽略。原 source 的 `strip().endswith('TERMINATE')` 与这个公开合同不同；本题 exact rule 不是任何框架的官方默认声明。

`recent_selector_context` 先选择 `history[-window:]`，再逐条调用完整 `render_message`，保持每条 message ID/speaker/content 及原顺序。window=0 返回空 tuple，大于 history 时保留全部；这是已声明边界的集成护栏。不能取 oldest messages、只保留最后一条，或用空 context 提速。selector view 变小不意味着 raw transcript 可以删掉。

`record_committed_turn` 只接受属于 roster 的 Utterance。Decision 是诊断选择，即使 accepted，也不是实际 speech；拒绝的 Proposal 不产生 Utterance，而 accepted 空文本仍提交一轮。完整 desk 用真实 counts 记录后续 turn，不能把两次事件都算一轮。

性能路径有 8,000 条真实 archived user messages，window=3，80 次真实 `ContextDigestSelector` callback。每次读取完整当前窗口并计算实际 SHA256 reason，随后真实提交 Decision 和 Utterance。fixture 与独立 expected 在 timer 外；完整 `ChatDesk.run`、整个 `ChatReport` equality 和 selector.calls==80 在 timer 内，包括 8,080 条消息、160 条 observations、全部 inputs/choices/reasons/counts。

先取窗口再格式化，避免每次遍历渲染整个 archived pool。当前限值 0.05 秒，本机 Python 3.12.14 的完整固定三慢三快组业务 timer 如下；精确值与六份原始结果路径见 [校准报告](/tmp/exam-11-16-work/draft16-10/actual/group02-summary.json)。

| 次序 | 慢版（秒） | 快版（秒） |
|---|---:|---:|
| 1 | 0.585339 | 0.000476167 |
| 2 | 0.567921 | 0.000541417 |
| 3 | 0.579745 | 0.000484208 |

该组先三慢、后三快。最小慢值/限值为 11.3584×，限值/最大快值为 92.3503×；最慢业务 timer 约 0.58534 秒，小于 3 秒，六份完整五关进程 wall 最大约 0.738924 秒，小于 5 秒。

六个独立完整副本仅把 elapsed 限值断言换成测量打印，慢版另仅恢复真实 whole-history-format-before-window，正确 recent context 不变。完整 run、整个 report equality、callback count 与其他四关全部保留；六份记录都是带测量打印的五关功能通过，不表示慢样本通过原 0.05 秒断言。保留原计时断言的 reference 完整五关另通过，进程 wall 约 0.183642 秒，与 P1 业务 timer 分开。完整输出和 callback 护栏要求真实工作仍在，不能预填固定 report、跳过 callback、清空 context 或裁掉 raw history。

## Part 2：完整选择证据与 utterance association

完整 `ChatArchive.__init__` 在给定 transaction 中调用 `ensure_schema`，schema 初始化已经 GIVEN。候选负责保存每个 conversation 的 roster、baseline 和按 position 排列的 observations。Decision fields 包含自己的 thread/ID、speaker choice、reason、完整 context、turn、accepted 和 private_prompt；Utterance fields 保留自己的 identity/content、turn、decision_id、question/reply/verdict metadata。两种记录都不能压缩成最后选择的 speaker。

`save` 在完整 transaction 中只替换目标 thread 的 snapshot 与 observation tail，其他 conversation 保留。`load` 按 position 恢复原混合 record 顺序，用完整 `restore_event` 生成 typed records，Utterance 仍指向自己的 Decision，不把 message_id 当 decision_id。

完整 `event_tag` 负责 typed discriminator，exact scalar codec 保留 bool/int/text/tuple/Fraction，整数不经过 float；Unicode、CRLF、空文本与大于 2^53 的 baseline 是使用正确依赖的护栏。`archive_counts` 已完整给定，按实际 Utterance 加 baseline；候选无需实现发言计数算法。private_prompt 可以保留在审计 snapshot，同时排除在 Part 4 的公开 schema 外。

## Part 3：三个独立的选择算法

合法输入为同一 conversation 的 typed events、唯一 question IDs、typed roster/actual counts、positive integer weights 和 positive max_consecutive。完整 validators 校验 roster、actual counts、weights/cap，`committed_messages` 负责事件分类；单 conversation/unique question IDs 是声明的合法输入域。这些依赖不提供以下三个算法。

`update_question_obligations` 按实际 Utterance 遍历：结构化 question_id 创建带 thread/addressee/message ID 的 Question，按创建顺序保留；reply_to 只消除 exact question ID、同 thread、named addressee 三项都匹配的那一个。内容里写 `@manager` 或引用一个问题的文本不创建结构化义务，Decision 也不创建或回答问题。

`speaker_deficits` 只使用 active roster。令 T 为 active speakers 的实际 committed count 总数，W 为 active weights 总数，对每位返回 `Fraction((T+1)*weight, W) - own_count`。missing count 按 0；inactive 的 weight/count 排除。结果可以为负，不是 probability，也不是把 proposed decisions 当 speech 后的份额。空 active roster 返回空 tuple。

`select_next_speaker` 先移除达到 consecutive cap 的上一位 speaker。若无 eligible，返回 None。然后按 pending 的 creation order 找第一个 addressee eligible 的问题，返回其 named speaker，即使它的 deficit 为负；受 cap 阻塞的问题保持 pending。没有可选问题时取最大 deficit，平票保留原 roster 顺序。不能先按 deficit 选完再忽略问题，或为了回答问题绕过 hard cap。

这三个算法把 named obligation、actual weighted shares 与 hard cap 合起来；通用 selector legality/fallback 不能代替它们。合同不保证任意约束下无饥饿，全部受阻时不虚构 fallback speech。

## Part 4：每条 observation 的公开字段

完整 `observe_turn` 校验 accepted Decision 与 committed message 的 thread、decision_id、speaker binding，生成 reject/commit/stop outcome。commit 的 turn/speaker 来自真实 message，reject/stop 的 public speaker 为 None；delta 由给定 before-after 产生，非 commit 为 0。

`DecisionProjection.payload` 只返回六个声明字段：thread、turn、kind、speaker、reason 和 deficit。它们来自本条 observation，deficit 通过完整 `delta_text` 保留 numerator/denominator，例如 `1/2`；不截成整数，不借用相邻记录。private_prompt 既不能替代 reason，也不作为额外 public 字段输出。

logfmt 是本题明确的 JSON-scalar-valued finite dialect。完整 reader/writer 处理 Unicode、引号、换行和 null；async driver 提供逐项发布与关闭。候选不重写 escaping、cadence、分类、delta 推导或发言计数，重点是 own evidence 与公开字段边界。

## Part 5：累计 agent quotas、own pending 与 total budget

输入是 finite typed thread tree、全局唯一 question IDs、完整 catalog 可解析的 reply refs，以及唯一 speaker 名与非负整数 caps。`ThreadCatalog` 已建立 question owner path、ancestor/subtree 查询，提供 committed-message 分类与 ancestor-stack cycle 拒绝。完整 `reply_evidence(path)` 已检查 owner thread 和 named addressee，返回授权 answered IDs 与全部 wrong-thread/wrong-addressee issues；候选调用并保留这些结果，不实现授权谓词。相应的两项 authority 错修只验证 GIVEN 的集成。

`audit_speaker_quotas(actual_messages, max_speaks)` 按声明序逐个处理 agent，只筛选该 node 自身 actual Utterance 中 speaker 匹配的消息。used 是完整累计数量，其他 speaker 穿插不清零；超限或未授权回复仍是实际发言并计入，Decision 不计。这与 Part 3 当前 consecutive streak 的算法不同。声明过但未发言的 agent 仍有 used=0 的行；未声明 agent 不产出行，默认空 `max_speaks` 返回空 tuple。

对声明 cap，remaining 为 `max(0, cap-used)`。第 cap 条消息合法，第一条超限是该 agent 的第 cap+1 条，即筛选序列索引 cap 的消息。`first_excess` 取 `messages[cap:cap+1]` 的 message ID，得到零或一个元素 tuple；不取最后一条，不提前标记 cap-th，也不按 ID 真值过滤。cap=0 时首条实际消息即为 first_excess，空 message ID 仍保留为 `('',)`。cap 校验已完整 GIVEN，含 0 的非负整数是正常合法域。

每个 node 的 `speaker_quota` 只审计 own messages，不累计 children，也不继承祖先的 per-agent 声明。own pending 则从 own questions 减去完整 `reply_evidence` 提供的 answered IDs。`complete` 仅表示该 node 的 own pending 为空，不表示 child/parent 完成、没有 issues、没有 quota excess 或预算仍充足。

另对每个 path，total used 是整个 subtree 的实际 Utterance 数。该 node 的剩余 total budget 为 `max(0, min(limit[a] - used[a] for a in ancestors_including_self))`。每个 ancestor 的 total limit 约束其整个 subtree，因此不能只看 own limit，不能把各层 residual 相加，也不能把 per-agent quota 的 own-only 范围套到 total budget 上。未授权或超限回复仍消耗覆盖它的 total budget；Decision 诊断不计。

source docs 第 126 行的练习提出 max-speaks-per-agent，`speaker_counts` 也累计实际 Msg.speaker。本题以这些概念构造 own-thread quota audit；Thread 树、声明序配额行、first_excess 和继承 total budget 是显式本地 adapter，source 没有该配额服务。这里审计既有消息，不实现 reservation、继承 per-agent vector cap 或阻止未来发言的运行时策略。

P1 的固定性能路径有校准报告中的本机测量记录。当前原规定 TEMP checker 已通过默认五锁、参考全五关、逐层与全部 32 项登记错修检查，其中两项 reply-authority 错修验证完整 GIVEN 的集成。Part 5 配额的三项独立实际错修分别覆盖 per-agent 归属、首条超限边界与累计历史保留；每项均为 Part 5 失败、其他四关通过，各对应 reference 全五关通过。这些结果不计作候选成绩，具体记录见 verification.txt 与独立验收报告。

## 这套题证明了什么，没证明什么

若候选实现通过全部原样测试，证据只支持：在本地确定性 conversation desk 中，能修终止/最近视图/真实发言，保存完整 selector audit 与 association，实现 named obligations、精确 weighted deficits 与 cap/tie 策略，公开正确领域 evidence，并审计 own cumulative per-agent quotas、首条超限证据、own pending 和 inherited total budget。P1 校准报告中的本机 reference 与六份带测量打印的记录只支持其声明的性能边界；当前原规定 TEMP checker 的全部 32 项登记错修检查通过；Part 5 配额独立矩阵的三项错修均仅目标关失败，各对应 reference 全五关通过。静态题包为 45 Python 文件、5 tests、39 assert、2 raises、5 skip、32 项登记错修；静态数量及参考记录都不计作候选成绩。60 分钟真人用时尚未校准。

结构化 Question/reply、exact terminal、weighted deficit、SQLite snapshot、finite logfmt、per-agent quota audit 与 nested thread total budget 都是课程概念的显式本地扩展，不宣称原 source 已有完整服务。原 LLM-style selector 是确定性状态机，不是真实 LLM；source 打印结果与讲解中的历史运行不是本题执行证据。

本任务未执行原 source、模型或网络，英文 output skill 仅作来源数据，没有调用其流程。框架谱系/版本说法作为课程快照，没有当前外部核验。Python 3.10+ 是目标环境，现有测量记录使用 3.12.14，不代表实际在 3.10 运行。有限合法域检查不证明通用公平性、任意输入安全、隐私审查或模型质量。

上述性能结果仅覆盖本机这一有限 workload、完整业务路径、测量边界与当前环境。测得余量不保证任意系统负载下的通用墙钟上界，也不是生产 SLA；60 分钟及各关用时仍未经过真人校准。
