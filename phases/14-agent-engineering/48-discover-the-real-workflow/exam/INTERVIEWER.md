# 面试官手册：FlowMap（14/48）

候选人计时期间不要看。候选人只有 README、`flowmap/` 与 `tests/`。

## 开场（2 分钟）

- 说明 60 分钟，请边做边讲，可问问题、可查官方文档。
- 记录每关时间与 pytest 次数；约 5 分钟卡住后一次给一级提示，不代写。
- 证据与 carrier 字段是已记录的调查材料，程序不推断自然语言的真实性或真实权限。

## 澄清问题的标准答案

只在问到时，用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | artifact 也算直接支持吗？ | "Yes. Levels1 and2 directly support current behavior; levels3 and4 remain unconfirmed." |
| 1 | 高 confidence 的采访算直接观察吗？ | "No. Confidence does not change the evidence ladder." |
| 1 | 输入可以先按 order 排吗？ | "No. Validate the recorded order exactly as given, contiguous from one." |
| 2 | 存储时修顺序吗？ | "No. Save the complete snapshot; audit decides whether it is valid." |
| 3 | 没 artifact 就是 hidden state 吗？ | "No. Only an explicit memory/chat/personal-notes carrier proves that recorded concern." |
| 3 | 报告出来的 authority 要删吗？ | "Keep it as an unconfirmed lead. Do not promote it to verified authority." |
| 4 | gap 等于 idle_ms 呢？ | "Same segment unless the actor changes. Idle means strictly greater." |
| 4 | end 用下一条时间吗？ | "The last event in that segment. The next event closes it but is not part of it." |
| 4 | 最后一步和空录屏呢？ | "Emit the last step at stream end. Empty input emits the header only." |
| 5 | 一个流程是另一个前缀呢？ | "Keep its terminal ids even when that node also has children." |
| 5 | count 数不同用户吗？ | "Observations. Several observations from one user remain separate evidence." |
| 5 | 原因没查明呢？ | "Record unknown, rather than inventing a reason." |

## 每关：要看什么、提示、追问

### Part 1 工作流证据（目标 12 分钟）

四层缺陷：
1. supports 只认 level1，runbook 等 artifact 被错误排除。错误在 audit 的 status，经过 _grounded 才到两层以下的支持判断。
2. 任一步有强证据就让整个流程 grounded；其他步骤只有报告或推断时仍需证据。
3. round 的半偶舍入把 12.5% 写成 12；本题明确要求整数百分比四舍五入为 13。
4. 每个 _view 都先把全部步骤 asdict，再取一个；320 步变平方级。慢版三次 0.201、0.200、0.198 秒，参考 0.707、0.689、0.697 毫秒，限值 0.02 秒，双侧至少 8 倍。

护栏：高 confidence 不能把采访升级成观察；输入顺序不静默排序，空流程不是 grounded。百分比单位与舍入是本题精度契约，正文没有要求这种展示单位。

提示：
- H1："Which evidence level disappeared before status was computed?"
- H2："Does the evidence support every step or only one step?"
- H3：指出 supports、grounded 汇总与 _view。

追问："What would confidence add without changing the evidence level?"（评估同类证据的不确定性，但不把别人转述变成亲自观察。）

### Part 2 工作流快照（目标 10 分钟）

坑：
- 一个步骤可能有多个不同级别的 receipt，顺序都是证据，不能只留第一条或按级别重排。
- 恢复 Step 与 Evidence 类型、整数 level 和原始 confidence；direct 布尔不足以重建四级证据。
- 只替换指定 workflow 的完整快照，旧 receipt 不残留，另一个 workflow 不受影响。

顺带覆盖 Unicode、引号、换行、制表符、空工作流与未知 id。SQL 绑定值和标准 JSON 是工具，不把引号转义当主坑。

追问："Why keep the weak receipt next to direct evidence?"（差异本身可能显示政策或执行脱节，不能为了看起来 grounded 就删掉材料。）

### Part 3 找四样东西（目标 14 分钟）

坑：
- 同一步的 exception、handoff、hidden state、authority 都可能同时成立，不能只返回一个。
- 弱 authority 保留为未确认，不能因 confidence 高变成 verified，也不能直接删掉。
- hidden state 需要显式 carrier；没有 artifact 只说明证据不足，不能凭空断言它在聊天或记忆里。
- handoff 要看相邻 actor 变化，verified 同时依赖两侧；按明确风险优先级和步骤排序。

提示：先列全部明确 concern，再标证据强弱，最后排序。

追问："Could a runbook prove what the user actually did yesterday?"（artifact 支持当前行为的具体程度仍需核实；题目把它作为显式 receipt，现实要检查内容和时点。）

### Part 4 录屏分段（目标 12 分钟）

坑：
- actor 变化或真正 idle 都会切步；同一时间戳的输入顺序仍有意义。
- end 是当前段最后事件，等待属于新段且只有超过阈值的 gap 记 wait_ms。
- 边界事件到达就发旧段，不先读完整录屏；流结束仍须发最后一段。

CSV helper 已给对，测试按 csv.DictReader 解析，带逗号 actor 原样往返。输入是事件记录，不是实际视频解码。

追问："What did the screen recording miss?"（side channels、未被记录的等待和授权；还需日志、访谈和其他 artifact 补证。）

### Part 5 真实变体树（目标 12 分钟）

坑：
- 短路径的 ends 不能因还有孩子就丢掉，empty path 也只是一个真实终点。
- count 数观察，不数不同用户；users 与 reasons 各自保留首次次序。
- 每条叶子路径来自真实观察，不把两个变体平均或拼出没走过的路径。
- children 按观察次数再按规范化 actor/action；未查明原因标 unknown。

身份归一 helper 已给对，输入不能被原地重排。

追问："Which variant should become the product requirement?"（先解释角色、风险、旧流程、熟练度或政策差异，不能按次数直接抹掉少数高风险路径。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分 |
| 调试方法 | 20 | 沿结果追证据层级、逐次验证 |
| 代码质量 | 15 | 观察/推断、计数/用户、事件/段落分工清楚 |
| 沟通 | 15 | 澄清证据与边界，说明不能自动判断的部分 |
| 生产意识 | 10 | authority、例外、缺失材料和变体解释 |

记录具体观察证据，没观察到写“未观察”；提示次数和用时另记。
