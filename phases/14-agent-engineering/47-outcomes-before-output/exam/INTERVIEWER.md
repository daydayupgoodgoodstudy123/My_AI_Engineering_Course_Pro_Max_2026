# 面试官手册：Outcomes（14/47）

候选人计时期间不要看。候选人只有 README、`outcomes/` 和 `tests/`。

## 开场（2 分钟）

- 说明 60 分钟，请边做边讲，可问问题、可查官方文档。
- 记录各关时间与 pytest 次数；约 5 分钟卡住后一次给一级提示，不代写。
- 明确有限词典不是语义模型，真实需求仍需证据与人的判断。

## 澄清问题的标准答案

只在问到时用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 别名从哪里来？ | "The caller supplies a finite alias table. Do not infer arbitrary synonyms." |
| 1 | 技术出现在 constraints 呢？ | "It is allowed when that exact technology has compatibility evidence." |
| 2 | 内容相同但 parent 不同呢？ | "Different revisions. The parent is part of the stored content." |
| 2 | history 从哪头开始？ | "The requested revision first, then its parents." |
| 3 | 要处理所有英文复数吗？ | "No. Use the supplied tokenizer and its finite PLURALS map." |
| 3 | 重叠短语怎么选？ | "Longest from the current token, then phrase id. Continue after the selected match." |
| 3 | span 是字节吗？ | "Python-character offsets in the original text, end exclusive." |
| 4 | 没变化的编辑也计数吗？ | "Yes. Quiet edits consume an ordinal but emit no block." |
| 4 | 要重写去重算法吗？ | "No. _delta already compares complete issue sets correctly." |
| 5 | 怎么判断子结果放宽约束？ | "Allowed-value sets are explicit. A child may narrow an inherited set, never widen it." |
| 5 | non-goal 是语义匹配吗？ | "No. Stable outcome ids, inherited from ancestors." |

## 每关：要看什么、提示、追问

### Part 1 结果框架（目标 12 分钟）

四层缺陷：
1. _names_output 只看 proposed_output 原字串，漏掉提供的 alias。错误在 decision 的结论才暴露，根因经过 validate 在两层以下的帮助函数。
2. constraints/non_goals 只看列表非空，里面全是空白也通过。
3. 任意技术有 receipt 就放行当前技术，PostgreSQL 的理由替 Rust 作了决定；证据必须绑定本技术。
4. reason_for 每条 constraint 重新扫描不可变兼容表。6000 条 constraint 对 18000 条 receipt，慢版三次约 0.438–0.449 秒，参考 0.892–0.962 毫秒，限值 0.05 秒，双侧至少 8 倍。

护栏：合法技术约束不是 outcome 泄漏；不同兼容快照互不借用。Part 1 的 alias 是有限大小写/空白归一子串规则；Part 3 才是整词与最长短语。

提示：
- H1："Which helper decided that the output was absent?"
- H2："Whose compatibility receipt did that constraint use?"
- H3：指出 _names_output、边界项检查与 reason_for。

追问："Can a keyword scan prove a technology choice has been earned?"（不能；这里只验证提供的 receipt 绑定，真实理由还需评审。）

### Part 2 修订史（目标 10 分钟）

坑：
- parent 是内容身份的一部分，同样 frame 的根版本与子版本不能混成一个对象。
- newest-first 沿父链走，不按文件名或写入顺序列举。
- JSON 要恢复 Frame 与 Constraint 类型；载入的可变列表不能改动存下的版本。
- 父版本不存在先报错，不留下孤儿对象。

正文只要求保留判断来源；内容寻址修订对象是本题的存储模型。序列化由标准库完成，不把键序或转义作为新主坑。

追问："What should be included in a revision's identity?"（本题 frame 与 parent，真实系统可能还包括作者和批准证据，必须先定义。）

### Part 3 有限泄漏词典（目标 14 分钟）

坑：
- 同起点的 vector 与 vector database 取最长，不被词典声明顺序抢走。
- 整 token 匹配，databasesafe 不是 database；连字符、有限复数与大小写由 tokens 给定。
- span 回到原文字符位置，不是归一词拼起来后的位置或 UTF-8 字节偏移。
- 同长按 id，独立出现的位置都保留。

提示：先匹配规范 token，再从被选 token 的原始 offset 返回证据。

追问："What does this detector miss?"（词典以外的同义词、上下文是否有证据、隐含架构选择；不能声称理解全部方案泄漏。）

### Part 4 工作坊编辑（目标 12 分钟）

坑：
- 所有编辑都占序号，quiet edit 也算，初始 issues 只做 baseline。
- 一次编辑的所有增加/删除放进同一完整块，再拉未来输入。
- 编辑私有深拷贝，不能改调用者的 frame；未知字段报错。

完整 issue-set 比较由正确 _delta 提供，保留无变化与重复项护栏，候选人不重做第 38/40/44 课的变化去重。

追问："Can the diff be treated as a durable source of truth?"（不能，它只是视图；应存 frame 修订与编辑事件。）

### Part 5 结果分解（目标 12 分钟）

坑：
- user 从最近非空祖先继承，分支自己的用户影响后代，不影响兄弟。
- allowed-value 集合只可收窄，继承表不可原地改坏兄弟。
- 祖先 non-goal id 在深处仍有效，新增约束和排除项按明确规则组合。
- 先序保持孩子顺序，没有有效 user 就报错。

这不是自然语言约束推理。集合、id 与继承规则是本题明确的结果分解模型。

追问："When should an outcome tree become separate tasks?"（子结果可分别验证、角色或约束已明显不同，就应明确拆分。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分 |
| 调试方法 | 20 | 沿结论追帮助函数、比较实际证据 |
| 代码质量 | 15 | 原文/规范token、身份/父链、继承/变更清楚 |
| 沟通 | 15 | 澄清有限模型，主动说明局限 |
| 生产意识 | 10 | 证据归属、兼容约束、修订追溯 |

记录具体证据，没观察到写“未观察”；提示次数与用时另记。
