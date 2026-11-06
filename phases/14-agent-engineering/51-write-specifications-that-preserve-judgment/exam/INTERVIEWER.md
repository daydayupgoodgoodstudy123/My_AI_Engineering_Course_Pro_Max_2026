# 面试官手册：SpecModes（14/51）

候选人计时期间不要看。候选人手里只有 README、specmodes/ 与 tests/。

## 开场（2 分钟）

说明 60 分钟，一次解锁一关，原样通过测试。请候选人讲清谁能决定、边界怎样执行、证明具体支持什么。所有动作使用本地 fake，不要求真实 SDK 或模型。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | Must every bounded decision have a number? | No. A typed allowed dependency or interface list is also an executable boundary. Rationale alone is not a boundary. |
| 1 | Why are four example kinds required? | This exercise makes the lesson's normal/edge/failure/forbidden recommendation mandatory. The original lesson example only has a normal case. |
| 1 | Can delegated rationale be empty? | Yes, at specification time. The agent owns the choice and explains it later. Constrained decisions need rationale now. |
| 2 | What orders revisions? | Physical contiguous revision numbers. Replay an inclusive prefix; do not sort by question, mode or rationale. |
| 2 | What does None rationale mean? | Preserve the previous rationale. An explicit empty string replaces it. Mode changes retain boundary; boundary changes retain mode. |
| 3 | Is audit a higher proof level that replaces others? | No. MATCH maps each claim kind to its specific receipt kind. Required receipts also need explicit claim binding, finite cases and authority scope where applicable. |
| 3 | Can a good receipt excuse a bad required one? | No. Every named required receipt must be valid. Valid receipts may jointly cover declared cases; extra cases do not hurt. |
| 4 | What protocol is this? | A private exercise NDJSON format with event, decision and reasons. It is not JSON-RPC or a framework method contract. |
| 4 | When are limits enforced? | Before the next fake effect, using measured completed counts and elapsed seconds. Any bounded limit applies globally; allowlists apply to the current bounded choice. |
| 4 | What if locked and budget-expired coincide? | Checkpoint wins, then return without applying the action or reading future attempts. |
| 5 | What does blocked contain? | Actual failing leaf occurrence paths in depth-first index order. A passing ANY hides its failed siblings. It is not merely the first failing metric. |

## 每关：要看什么、提示、追问

### Part 1 修规格编译（目标 12 分钟）

一个测试叠了四个缺陷：

1. decision_issues 接受只有 rationale 的 bounded。compile_contract 消费错误通过结果，在另一个函数 compile_boundary 访问 None 的 kind 时才报 AttributeError。
2. examples 只检查非空，未覆盖本题要求的四类意图。
3. locked checkpoint 路由丢了该 decision 的 rationale，同问题不同 id 不能混用理由。
4. 编译带序号的有序 catalog 时，前端 pop 不断搬移剩余条目，形成平方开销。

看什么：是否从 consumer 异常查回 validator 前提；是否保留 unknown/delegated 判断空间与理由绑定。性能不是按名字线性查固定表，输出要保留每个原值和 occurrence ordinal。

提示：
- “Which earlier result promised that this boundary could be compiled?”
- “What intent is absent if the only example is a passing normal case?”
- “Can the catalog be visited in order without repeatedly moving its remainder?”

追问：schema 接受把生产写入改成 delegated，为什么不等于产品授权？

### Part 2 修订史（目标 10 分钟）

坑：
- arbitrary revision prefix，不能只返回最新状态。
- 多个相同 question 用 id 定位，按最初 added 顺序返回。
- None 理由表示保留，空字符串表示明确替换。
- 改 mode 保留 boundary，改 boundary 保留 mode；显式 None boundary 要清除，原单位/文字不丢。

连续 revision 不接受重复或跳号，拒绝前不写任何内容。给定读取 helper 按 UTF-8 文件物理行读取，U+2028/U+0085 是合法字符串内容，作为原文护栏，不是待修主坑。

看什么：是否把持久化事件与当时的 typed decision 分开，重放不让未来修订渗入过去。

提示：“What exactly was known at revision three?”

追问：若两位作者同时追加，本题 single-writer 连续编号还够吗？

### Part 3 证明对准主张（目标 12 分钟）

坑：
- 单元、wire、browser、replay、audit 是匹配关系，不是自由替换全序。
- receipt 必须明确绑定当前 claim id，不能只因名字存在就用。
- 只有有效 receipt 贡献有限 case union，所有声明案例都要覆盖。
- 所有 required refs 都要有效；authority scope 精确集合匹配，不能默许额外权限。

每份 receipt 的首错按存在、passed、kind、binding、scope 顺序，失败状态优先于 kind。

看什么：是否把“一个 passing case”与“声明范围完整覆盖”区分。非空 case/proof schema helper 已给对，不把空集放行当主任务。

提示：“What exact claim did this receipt exercise?”

追问：覆盖有限 case universe 为何不能声称证明所有真实运行安全？

### Part 4 私有在线策略（目标 12 分钟）

坑：
- locked 在 effect 前 checkpoint，且优先于同时到期预算。
- 全局任一 source/retry count 或 elapsed 达门槛即 stop；同次多个原因合成一条按声明顺序的 packet。
- dependency/interface 白名单同样是 bounded，无数字也要执行。
- continue 前恰好执行一次 fake，终止/取消后不多读、不再执行。

看什么：是否清楚输入是已完成工作的 snapshot，不把拟议动作计为已完成源；是否用 source/effect 计数证明边界。

提示：“Which action is authorized before apply runs?”

追问：真实工具具有不可撤销效果时，还需哪些外部授权与审计设计？

### Part 5 边界 AST（目标 10 分钟）

坑：
- ALL 与 ANY 的许可规则，达到门槛意味着下一动作不可继续。
- passing ANY 隐藏失败兄弟，failing ANY 汇总全部实际 blocker。
- occurrence path 不是 metric 名，同指标不同位置都要保留。
- DFS 顺序和完整 blocker 集合，不能只返回第一失败叶。

看什么：是否给出实际阻塞约束，而非把一个失败叶误作 ANY 失败证明。schema 与数值/单位 helper 已正确给出。

提示：“Does this failed leaf still block a choice when its sibling authorizes it?”

追问：如何为人类展示 blocker，且不声称它是唯一最小解释？

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 调试与编译 | 25 | 前提、例子意图、理由与复杂度 |
| 历史保存 | 15 | typed prefix 与局部修订 |
| 证明匹配 | 25 | kind/binding/cases/scope |
| 在线授权 | 20 | checkpoint、预算、effect 边界 |
| 结构与沟通 | 15 | AST 许可与实际 blocker |

记录用时、提示次数和观察证据；没观察到的写未观察。
