# 面试官手册

这是 60 分钟的离线五关练习。候选只修领域模块，不改测试、正确给定依赖或五关顺序；主持安排与提示如下。

## 开场（2 分钟）

- 说明总时长 60 分钟，五关参考用时为 12、11、15、10、10 分钟；时间和难度尚未经过真人校准。
- 请候选人边做边解释，可以随时澄清、查 Python 标准库官方文档。只修包内领域代码，不改测试、正确给定依赖或关卡顺序。
- 记录每关从解锁到变绿的时间、pytest 次数和提示级别。主持人不代写代码；卡住约 5 分钟时一次给一级提示，不要求全部做完。
- 澄清问题只在候选人问到时用表中的英文回答；追问用于理解取舍，不是新增实现要求。计时期间不给候选人看本手册或 solution。

## Part 1：typed intake 与结构 report

主要缺陷有四层：缺 manager 被标为有证据、unknown 被降成 negative、canary 接收 branch label、每个 manager 重走全部后代。首层在 producer 外经过 `inspect_branch → typed_leaf_consumer` 两次正确调用后自然违反“VERIFIED 必须有封存 leaf 引用”的一般合同。最终结构算法只做证据身份集合汇总，不负责 P3 obligation 意义。

性能检查覆盖完整 `HierarchyDesk.inspect` 及全部 branch、leaf、canary、manager report 输出。深链只压结构辅助服务，不建议真实层级无限加深。独立全输出检查防止只返回 root、漏 manager 或丢 citation 的过修。

完整结构服务的本机校准覆盖 4,000 个真实 manager report，全部 branch/leaf/canary/manager 输出相等检查位于 timer 内；限值 0.085 秒，三次慢版 0.796–0.834 秒，三次参考版 0.0067–0.0079 秒。双侧余量分别 9.36×、10.73×。这是本地完整路径的响应检查，不是部署 SLA。

看什么：沿真实 consumer 的合同定位首次产生错误数据的位置；分清结构身份集合与原 obligation 的语义归属。每次修一层后重跑，不通过删 report 字段提速。

提示：
- H1: "What evidence makes this branch available to the consumer?"
- H2: "Did the leaf state or the question change before this consumer ran?"
- H3: 指向 branch/leaf producer、原问题 canary 和完整 manager report 的结构汇总边界。

追问：
- "Can VERIFIED establish that the answer is true?"（只能证明封存引用可用，不能替代 leaf 的认知状态或答案验证。）
- "Which work can be shared across manager reports without losing any report?"（复用结构汇总，仍输出全部 manager 与完整证据身份。）


## Part 2：ZIP dossier

主要职责是 manifest 声明的逻辑顺序、member 链接、id 一致性及多个 summary 指向同一封存 leaf。ZIP 插入顺序和默认文件命名都不能替代 manifest；悬空 leaf 引用必须拒绝。完整 typed codec/UTF8/ZIP 生命周期是正确给定实现，状态往返是依赖集成护栏，不另考 unknown 转换。

看什么：能否把 ZIP member 位置和领域身份分开，重开后还原 manifest 顺序、没有直接 leaf 的 manager 和共享引用。

提示：
- H1: "Which record declares the dossier's logical order?"
- H2: "Does this reference name a leaf identity or an archive member?"
- H3: 指向 manifest 的逻辑 id、member 链接和重开后的引用校验；codec 和 ZIP 生命周期无需重写。

追问：
- "Does a shared leaf require duplicate serialized workers?"（保留引用与一个封存 leaf 身份，不制造额外执行。）
- "What should happen when a manifest reference has no member?"（拒绝档案，不能静默丢失证据。）


## Part 3：decomposition drift

三个独立 TODO 分别处理逐边 local obligation composition、最短路径首漂移/稳定同长顺序、原问题 canary 比较。错误部门、未声明 local id、缺失映射和未知证据有不同归因。结构上能到达某 leaf 不代表它完成了某原 obligation。known canary 不覆盖 hierarchy 的状态；两条通道分别留名。

看什么：能否逐条边组合明确的 local obligation 映射，并把结构可达、语义完成和独立 canary 三件事分开。

提示：
- H1: "Which original obligation does this local identifier represent?"
- H2: "What is the first edge where that mapping stops being valid?"
- H3: 分别检查逐边 composition、最短首漂移及同长顺序、canary 的独立证据归因。

追问：
- "Why is a reachable leaf insufficient to discharge the original obligation?"（它可能没有正确 binding 或不符合部门准入。）
- "Can a missing canary be replaced by the hierarchy result?"（不能；那会虚构独立佐证。）


## Part 4：领域 provenance 行

候选只实现同步领域 row：leaf 的原 obligation 归属、完整 manager/leaf 路径和当前 leaf 身份；branch audit 必须保留 branch 类别与 audit result，不能伪造 leaf 执行。完整 async pull/publication/close 和 TSV codec 是实际正确 GIVEN。cadence/header/UTF8 断言只验证该集成，不是候选主要坑。

看什么：实际 leaf 执行和 branch audit 是否分别保留类别、身份、路径与原 obligation；不把提供好的 transport 当候选 TODO。

提示：
- H1: "Which completed event owns this row?"
- H2: "Is this identifier the sealed leaf or the worker's display name?"
- H3: 指向同步 row projection 的 leaf/branch 类别、完整路径和原 obligation 字段；异步 driver 与 quoting 已给定。

追问：
- "Does another citation path mean another worker execution?"（不意味着；执行身份和引用出现路径分开。）
- "Should a branch audit be represented as a leaf result?"（不应；两种事件的证据含义不同。）


## Part 5：typed 嵌套解释

主要职责是 UNKNOWN 逐层保留、共享 leaf 每次 citation 的 manager 路径、P3 已归属原 obligation 的 evidence paths 和唯一实际 leaf 身份。MISSING/已知 conflict 的断言是 typed aggregate 护栏；不重做 P3 的 mapping 或把状态误称真实答案。shape/cycle 检查完整给定。

看什么：未知、缺席和已知冲突是否保留不同含义；共享 leaf 的每条路径与唯一身份是否同时呈现。

提示：
- H1: "What is known at this node, and what is merely absent?"
- H2: "Which citation paths reach the same sealed leaf?"
- H3: 指向 typed aggregate、已归属原 obligation 的路径，以及一个 manager 同时拥有 children 和直接 citation 的情形。

追问：
- "Why keep both citation paths and a unique leaf count?"（路径解释归属，身份避免把共享证据误当额外执行。）
- "Can UNKNOWN be summarized as a negative answer?"（不能；缺少已知结论与已知否定是不同状态。）


## 澄清问题

| 问题 | 标准回答 |
|---|---|
| Does VERIFIED mean the answer is true? | No. Branch VERIFIED only means sealed leaf references are available. Each leaf retains its own epistemic state. |
| Can summary text establish an original obligation? | No. Use the declared finite local identifiers, bindings and department contracts. |
| Does a shared citation rerun the worker? | No. Keep every citation path and one actual leaf identity. |
| Must candidates implement async scheduling or TSV quoting? | No. Both are complete supplied dependencies; implement domain projections. |

## 评分与复盘

| 维度 | 分值 | 可观察证据 |
|---|---:|---|
| typed intake 与完整结构输出 | 20 | 分层修复、原问题边界、真实完整性能路径与过修防护 |
| 有序持久化模型 | 20 | manifest/member 身份、共享引用与完整往返 |
| obligation drift 算法 | 25 | 逐边组合、首漂移、独立 canary 状态归属 |
| 领域事件投影 | 15 | 原 obligation、路径、leaf/branch 类别 |
| 嵌套解释与沟通 | 20 | typed 状态、出现路径、唯一身份与证据限度 |


每关评价可观察输出及其依赖边界。不要把 summary 内容当事实 oracle；不要求真实模型、并发 worker、在线验证或跨进程原子写入。reference 和 canonical wrong-fix 供复盘解释具体机制。

档案不能因 manager 没有直接 leaf 就省略它。P3 的同深度首漂移保持 encounter order；缺席 canary 与 hierarchy UNKNOWN 各自保留，不制造独立 corroboration 或已知分歧。P4 的 leaf id 与 worker 显示名不同。P5 的 unavailable manager 为 MISSING，内部 manager 也可直接引用封存 leaf；该引用不是再执行 worker。这些是现有领域合同的边界断言。
