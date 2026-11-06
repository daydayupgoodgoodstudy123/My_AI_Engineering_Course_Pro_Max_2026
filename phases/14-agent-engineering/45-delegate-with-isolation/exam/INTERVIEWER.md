# 面试官手册：Delegate（14/45）

候选人计时期间不要看。候选人只有 README、`delegate/` 和 `tests/`。

## 开场（2 分钟）

- 说明 60 分钟，请边做边讲，可澄清、可查官方文档。
- 记录各关时间和 pytest 次数；约 5 分钟卡住后，一次给一级提示。
- 不要求全部做完，不替候选人写代码。

## 澄清问题的标准答案

只在问到时，用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 路径是磁盘安全检查吗？ | "No. Inputs are relative lexical claims without '..'. Normalize '.', repeated separators and trailing slashes; do not inspect symlinks." |
| 1 | 只读调查也会占写路径吗？ | "No. Inspection paths are not exclusive write claims." |
| 2 | 空文件可以再写一次吗？ | "No. Empty evidence is still created evidence. Use exclusive creation." |
| 2 | id 和文件名能带斜杠吗？ | "Yes. They are opaque strings, encoded with the provided reversible helpers." |
| 3 | claimed_passed 能用吗？ | "Only as a summary. Read the assigned proof command, exit code and captured output." |
| 3 | 共享接口冲突直接选一个吗？ | "No. Record a decision with all involved units and merge none of them." |
| 3 | 整合函数会真的 merge 和跑命令吗？ | "No. It validates supplied receipts and the supplied final diff/gate result." |
| 4 | 输出是 Lamport 协议吗？ | "No. It is private NDJSON. Hold early children until prerequisite verdicts exist." |
| 4 | 流结束但有 worker 没交接呢？ | "Reject missing handoffs, then reject their held dependants." |
| 5 | 最长前缀 owner 能覆盖祖先 owner 吗？ | "No. Show every write claimant; only transitive serial order allows shared paths." |

## 每关：要看什么、提示、追问

### Part 1 所有权预览（目标 12 分钟）

五层缺陷：
1. claim_parts 直接 split，没规范化。错误穿过 _claims，在 conflicts 的重叠报告里才暴露。
2. 只读调查路径也加入写所有权索引，阻塞本来独立的 worker。
3. 重复工作单元产生重复冲突行；重复 id 仍应阻塞计划，但冲突报告不能重复。
4. owner 只查空串，空白 owner 没有被识别为缺失责任人。
5. 所有路径逐对比较；应按前缀树只找同分支与祖先声明。

护栏：同父目录下的兄弟路径、api 与 apiary 都不能误报。5400 条声明的性能限值为 0.1 秒；慢/快各测三次都满足 8 倍余量，慢版单次约 1 秒。

提示：
- H1："Where does the reported claim first become different from the path contract?"
- H2："Do inspection paths grant write ownership?"
- H3：指出 claim_parts、_claims 和冲突列表去重。

追问："Do separate worktrees make two overlapping contracts independent?"（不；文件隔离不等于所有权或接口决策隔离。）

### Part 2 证据隔离（目标 10 分钟）

坑：
- 文件必须独占创建；检查 exists 再覆盖写不是同一保证，空文件也不例外。
- 单元之间不能共用输出目录，特殊 id 是不透明名字，不是路径。
- 证据是原始 bytes，不能按文本解码重编码。
- 重开与列举要恢复原名字并按解码后的 id 排序。

名称编码 helper 已给对，统一大写 Base32 保证大小写不敏感文件系统下的独立性。casefold 唯一性与不透明 id 往返只是 helper 护栏，不增加本关主坑。

追问："What if a worker crashes after creating an empty file?"（需要另一层完成标记或提交协议；本题拒绝悄悄覆写已有证据。）

### Part 3 整合器（目标 16 分钟）

坑：
- 读 proof command、exit、output，不能信 claimed_passed。
- 改动集必须位于本项写 scope；只读项有改动即拒绝。
- 任一前置被拒或缺失，下游不能进入 merge_order；按依赖波次再按 id 整合。
- 两份合格交接改同一接口时记 decision，双方都等待决策，而非静默选一个。
- 完整 gate 与最终 diff 都要核验；最终 diff 多文件或少文件都不合格。

提示：先把单个交接审查与跨交接整合分开。

追问："Why keep both worker output and the integrator's full gate?"（局部证明与跨单元契约不同；需要两层证据。）

### Part 4 在线交接（目标 12 分钟）

坑：
- 子项先到时暂存；不能在前置结论还未知时宣布 accepted。
- 一个回执解锁的所有后续结论先发完，再读未来 worker 输入。
- 失败结论要沿依赖阻塞已暂存子项；流结束的缺失交接也要显式拒绝。
- 关闭消费者后不能继续读取 worker；未知 worker 输出 unknown 拒绝。

格式由 _line 给定：每条结论一行 JSON，属于本题私有格式，没有时钟、水位线或 Lamport 先验。

追问："What if a dependency is invalidated after acceptance?"（需要新 epoch/取消与重验规则；当前输入每个 unit 只有一个回执。）

### Part 5 所有权树（目标 10 分钟）

坑：
- 每个文件显示全部祖先和精确 claimants，不能以最长前缀掩盖并发双 owner。
- 只有传递依赖关系能证明两项串行；无关系的重叠写要全部列出冲突。
- 同一单元的重复/嵌套声明只算一个 owner；只读项不进入写树。
- 根声明与无 owner 的文件都不能漏，路径按组件匹配。

追问："Can this prove two agents made compatible designs?"（不能；只检查声明与顺序，还需预先确定共享接口和整合证明。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分 |
| 调试方法 | 20 | 沿报告找源头、看实际字段、逐层重跑 |
| 代码质量 | 15 | 所有权与证据清楚，决策显式 |
| 沟通 | 15 | 主动澄清、说明独立与串行边界 |
| 生产意识 | 10 | worktree局限、证据不可覆写、完整gate、取消 |

记录具体证据，未观察到写“未观察”。提示与用时另外记录。
