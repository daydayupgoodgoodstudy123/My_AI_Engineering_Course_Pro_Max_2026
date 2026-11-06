# 面试官手册：EvidPlan（14/44）

候选人计时期间不要看。候选人只有 README、`evidplan/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟，请候选人说出思路，可澄清、可查官方文档。
- 记录每关时间、pytest 次数。约 5 分钟卡住后一次给一级提示，不代写。
- 不要求全部做完；`support.py` 的 `_components` 是已给的正确 SCC partition，`ancestors` 和 `latest_records` 也已给对；`cycle_members` 是 Part 1 的调试范围，不要求从零写 SCC。

## 澄清问题的标准答案

只在候选人问到时，用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 有未知依赖还查环吗？ | "Yes. Report unknown references and any cycle in the known subgraph independently." |
| 1 | resolver 要经过所有路径吗？ | "No. It must be a transitive prerequisite. Dependency execution waits for all prerequisites." |
| 1 | 必须自己写 SCC 吗？ | "No. _components already partitions the known graph. Use it if it helps; identify every cyclic vertex, not just one representative." |
| 2 | 重复事件能合并吗？ | "No. Keep every receipt and its position. A repeated done event is still a distinct log record." |
| 3 | artifact_changed 后旧 proof 还能用吗？ | "No. Reprove the item and all affected downstream items after that revision." |
| 3 | proof 之后才能 done 吗？ | "Yes. Exact command, exit zero, then a later done receipt. latest_records already scans the journal correctly." |
| 3 | approved 代表什么？ | "An explicit permission event in this exercise. It is not proof that a real human authorized an external action." |
| 4 | 要调度真实并发 agent 吗？ | "No. Incoming receipts may be interleaved. Render them online without prefetching." |
| 5 | 拆分项之间要串行吗？ | "No. Each keeps the original prerequisites. Downstream items wait for all replacements." |
| 5 | resolvers 引用被拆分的项呢？ | "Expand to every replacement id, just like dependency references." |

## 每关：要看什么、提示、追问

### Part 1 校验与波次（目标 12 分钟）

五层缺陷：
1. plan_document 无论校验是否失败都调用调度器，未知依赖在 execution_waves 抛 ValueError，未得到应有的 blocked 文档。
2. 环报告把只是位于环下游的 tail 也列成环成员。cycle_members 的正确行为是只返回真正能回到自身的顶点。
3. 一处未知依赖让独立的已知子图环检测也被跳过。
4. 不可逆项未检查 resolver 前置依赖；这是人工标注的机械检查，不推断产品风险。
5. cycle_members 为每个顶点独立搜索能否回到自身；环之后的长尾让它重复走相同祖先，最坏 O(V × (V + E))。用给定 `_components` 的一次划分识别多顶点分量和显式自环。

护栏：重复依赖只算一次，不能通过删环边继续执行；精确成员要包含多个不相交环、三节点环和自环，排除下游尾节点、孤立节点及未知引用。waves 的一万项依赖链计时护栏为 0.14 秒。环成员性能测量用两节点环和四千项阻塞尾链，阈值 0.1 秒；慢/快各三次实测余量记录在 SCOPE.json。

提示：
- H1："Which layer promised to return a blocked document?"
- H2："Are downstream vertices necessarily members of the cycle?"
- H3：指出 plan_document 的调度条件和 _cycle_report。
- 性能卡住时先问："How many times is the same tail traversed?" 再指出 `_components` 返回一次完整 partition；让候选人区分多顶点分量和单顶点自环。

追问："What part of irreversible ordering still needs human judgment?"（哪些不确定性相关、resolver 是否真的解决了风险。）

### Part 2 计划与进度日志（目标 10 分钟）

坑：
- 源计划覆盖保存，进度事件追加保存，两者生命周期不同。
- 同项重复回执仍保留，不能按 id 或完整事件去重。
- JSON 重开要恢复 evidence/depends_on/resolvers 的 tuple 类型。

顺带覆盖换行摘要、Unicode 路径、整数退出码及摘要内 U+2028/U+0085 原样往返。JSONL 以文件物理 LF 分行，合法字符串里的 Unicode 分隔符是内容。JSON quoting 直接使用标准库，这些是原文护栏，不把转义作为主坑。

追问："How would you distinguish a complete append from a torn final record?"（长度或校验、提交标记、恢复策略；本题不模拟断电。）

### Part 3 中断恢复（目标 15 分钟）

坑：
- 上游 artifact revision 不只重开本项，还使下游旧证明失效；上游重验不能自动复活旧下游证明。
- 有新鲜 proof 的项仍须等自己的依赖完成，才可成为 complete。
- 不可逆项缺 approval 时既不 complete，也不 ready；没有安全下一项时 next 是 None。
- 只能接受本项确切 proof 命令，done 回执还须晚于这次成功 proof。

latest_records 已正确提供最新 proof 和日志位置；最新失败覆盖旧成功作为顺带边界，不要求候选人再修一次“取首条还是末条”。next 按可执行 id 排序。

提示：先把“本项证明有效”和“依赖已完成”分开判定。

追问："Does a successful command prove the artifact matches the requested behavior?"（只有证明义务选择合理时才支持相应主张；本题只验证回执规则。）

### Part 4 在线 Markdown（目标 12 分钟）

坑：
- 每个事件造成的所有视图变化都要发完，再拉取下一个事件。
- 复用已有进度初始化，不重发旧输出，不重跑已完成工作。
- 同一事件可能让多项清单变化，必须按 id 发，不能随源计划顺序输出。完整内容去重由给定 `_changes` 正确提供，相关错修只作 helper 护栏。
- 消费者关闭生成器后不能继续消耗 worker 输入。

格式是本题给定的 Markdown 行；数据以计划与事件为真源，不从旧 Markdown 反向猜状态。

追问："Where should a real concurrent executor record completion?"（持久化 proof/产物/完成回执后，让视图消费已提交事件。）

### Part 5 拆分与不可逆依赖（目标 11 分钟）

坑：
- 多证明项拆成独立子项，继承原前置项和证据；不能无意把两次验证串成新依赖。
- 下游依赖与 resolver 引用都扩成全部替代项，并保持顺序去重。
- 自动生成的 id 不能碰撞原有或其他生成 id。
- 检查每一个不可逆项的 resolver 是否在传递前置集合中，不能误用“每条图路径都经过 resolver”。

追问："What happens if the two proof commands validate different contracts?"（应把 change/evidence 进一步拆明，本题的机械复制不替代语义审查。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分 |
| 调试方法 | 20 | traceback、数据、一次一层、定向重跑 |
| 代码质量 | 15 | 校验/进度/视图分工清楚，保留证明义务 |
| 沟通 | 15 | 主动澄清并解释依赖取舍 |
| 生产意识 | 10 | 人工判断边界、日志恢复、证明局限 |

记录具体证据；没观察到写“未观察”，提示次数和用时另记。
