# 面试官手册

这是 60 分钟的离线五关练习。候选只修领域模块，不改测试、正确给定依赖或五关顺序；主持安排与提示如下。

## 开场（2 分钟）

- 说明总时长 60 分钟，五关参考用时为 12、11、15、10、10 分钟；时间和难度尚未经过真人校准。
- 请候选人边做边解释，可以随时澄清、查 Python 标准库官方文档。只修包内领域代码，不改测试、正确给定依赖或关卡顺序。
- 记录每关从解锁到变绿的时间、pytest 次数和提示级别。主持人不代写代码；卡住约 5 分钟时一次给一级提示，不要求全部做完。
- 澄清问题只在候选人问到时用表中的英文回答；追问用于理解取舍，不是新增实现要求。计时期间不给候选人看本手册或 solution。

## Part 1：raw record 与诊断

三个主要缺陷：producer 提前把 answer 格式化成字符串；把 agreement=1 当正确；一维 diameter 枚举所有 pair。第一个错误在 `make_round_record → report_round → render_numeric_record` 外部正确数值格式消费者自然 ValueError，不能改消费者用 float(str) 掩盖精度损失。完整 report 与全部人口字段在 timer 内验证，防只取端点样本、恒定 diameter 或丢显示行的过修。

7,000 位参与者只构成纯数值诊断的完整输出压力 fixture，不是建议的真实 LLM agent 数量；没有逐行模型调用或 sleep。

完整 RoundDesk.record 的 7,000 位参与者输出全部在 timer 内检查。独立完整校准组限值 0.10 秒，三次慢版 0.896–0.904 秒、三次快版 0.0054–0.0065 秒，双侧余量 8.96×/15.41×。六个测量副本仅把 elapsed 限值断言换成实际测量打印，慢版另换 diameter 实现，其余五关功能检查保留；原样计时断言由规定 checker 验证。这是本机数值服务检查，不是生产 SLA。

看什么：是否保留 producer 的数值类型和精度，沿正确 renderer 的合同找根因；是否分开 agreement 与 truth，并验证完整人口的 report。

提示：

- H1: "What type reached the numeric renderer?"
- H2: "Can every agent agree on the same wrong value?"
- H3: 指向 raw record、独立 truth 诊断和只求一维最大差的 diameter；不能删输出字段提速。

追问：

- "Why can parsing display text back to float lose information?"（显示格式已经舍入，不能替代原数值。）
- "What does the diameter measure that truth error does not?"（人口内部离散程度与对外部真值的误差不同。）


## Part 2：命名二进制向量

主要职责是 declared 名字表顺序、每轮局部 agent 顺序变动时的 answer/confidence 成对对齐、初始与后续轮完整记录。truth 是独立 metadata，0.0 不是缺席。数值不变的相邻封口轮也各有独立 index，不能合并成一条记录。完整 binary64/UTF8/optional truth codec 是实际 GIVEN；signed zero/subnormal 的精确往返是使用该依赖的护栏，不要求再写字节解析器。

看什么：重开后能否按声明名字表恢复每轮成对的 answer/confidence，并保留初始、重复或未改变的完整轮记录和 truth metadata。

提示：

- H1: "Which identity owns each answer and confidence pair?"
- H2: "Did this round arrive in the same order as the declared name table?"
- H3: 指向名字对齐、成对写入和完整轮布局；scalar、optional truth 和文件生命周期是正确给定依赖。

追问：

- "Should an unchanged numeric round be omitted?"（不应；完成轮和其顺序仍属于保存的记录。）
- "Is truth zero the same as absent truth?"（不是；完整给定 codec 保留两者，领域布局要传递原值。）


## Part 3：numeric dynamics

三个独立新职责：稳定 own+allothers 加权答案、每个 agent 自己的 capped confidence 与 revised history、初始化一次并执行固定追加轮数。不能排除 own、把 answer 与 confidence 错配、丢 cancellation residual、溢出有限凸均值或因已 agreement 而早停。完整 snapshot 已给定，正文 previous-round 与实际 main 活引用差异不是候选预埋坑。P1 没有加权 solver。

看什么：P1 诊断不能替代 weighted solver；检查 own 与 peers 的成对权重、每个 agent 的 confidence/history，以及固定追加轮数。

提示：

- H1: "Which answer belongs to this confidence, including the target's own answer?"
- H2: "Does a finite convex mean require an overflowing intermediate sum?"
- H3: 分别检查一次 revise、一次完整 round commit 和固定轮数 orchestration；正确 frozen snapshot 已给定。

追问：

- "Why continue requested rounds after agreement reaches one?"（这是固定轮数合同，confidence/history 仍演化，agreement 不表示答案为真。）
- "Is the scripted confidence a calibrated probability?"（不是；它只是本地权重，按来源规则增长并封顶。）


## Part 4：封口 round CSV

主要坑是把完整 vector 的 agreement/error 换成 agent singleton 指标、混用不同阶段数据、漏整轮诊断行。每个 agent 保留自己的 answer/confidence，全部同行共享完整封口 vector 的 diagnostics。async cadence/close/header/CSV quoting 为实际 GIVEN，相关断言只检查集成。

看什么：一轮各行是否共享同一完整 vector 的 diagnostics，同时保持每个 agent 自己的数值并输出一条整轮诊断行。

提示：

- H1: "Which sealed vector supplies this row's diagnostics?"
- H2: "Are the answer and confidence owned by this agent or by another row?"
- H3: 指向同步领域 rows 的 agent 字段与整轮诊断行；async pull、CSV 与关闭流程已给定。

追问：

- "Why is singleton agreement inappropriate for an agent row?"（该字段报告整个人口的一致程度，不能用自身 singleton 替代。）
- "Does missing truth mean that the numeric mean is unavailable?"（不意味；mean 来自人口，truth error 才依赖外部标签。）


## Part 5：共享推导 DAG

主要职责是每轮一个共享 vector 而非每个 agent 复制上一棵树、边权来自前轮 confidence、非零因果根追溯及初始 target 的自身根；多个因果根按初始 agent 顺序返回。完整 RoundCatalog 实现 round/agent identity 与上一轮 handle 查询；候选不修 namespace/短名查找。truth 是外部评测 metadata，不是求解输入；不能在解释中再跑 weighted solver。

看什么：是否每轮只建一个共享 vector、使用前轮 confidence，并在不重跑 solver 的情况下追溯非零因果初始输入。

提示：

- H1: "Which completed round owns this edge's weight?"
- H2: "Do these agent reports point to one previous vector or copied subtrees?"
- H3: 指向共享节点、前轮权重和零权重根；完整 RoundCatalog 已负责 round/agent 身份与 previous handle。

追问：

- "Why should truth not appear among the causal roots?"（它是外部评测 metadata，不参与 revise。）
- "What does a zero-confidence input contribute to a later weighted answer?"（没有该边的数值贡献，但初始 target 自己仍有其 round-zero 记录。）


## 澄清问题

| 问题 | 标准回答 |
|---|---|
| Is agreement a literal majority vote? | No. The numeric demo uses a tolerance around the unweighted mean; the named majority baseline is also an arithmetic mean. |
| Does rounds include the initial answer? | Here it counts extra exchanges, exactly as the source loop. Round zero is recorded separately. |
| Must candidates fix source live-reference aliasing? | No. The complete supplied frozen snapshot follows the prose requirement to read the previous round. |
| Is confidence a calibrated probability? | No. It is a scripted nonnegative numeric weight, grown by the source cap rule. |
| Must candidates implement async transport or identity lookup? | No. The full driver/codec and RoundCatalog are supplied. |

## 评分

| 维度 | 分值 | 证据 |
|---|---:|---|
| 分层调试与完整性能路径 | 20 | raw 精度、truth 独立性、完整输出及真实 diameter 工作 |
| 持久化建模 | 20 | 名字/成对值/轮次/truth 正确对齐 |
| weighted dynamics | 25 | 稳定权重、自己的 confidence/history、固定轮数 |
| 领域流式展示 | 15 | 同一 sealed vector diagnostics 与实际数值行 |
| 推导结构与解释 | 20 | 共享节点、前轮权重、非零根与证明限度 |

不把课程打印的 improvement Takeaways 当 oracle。完整全连接同步模型一轮后就是公共 weighted mean，继续轮数只按合同演化 confidence/history；不要求新 alpha、拓扑、收敛停止规则或真实 LLM 收益。
