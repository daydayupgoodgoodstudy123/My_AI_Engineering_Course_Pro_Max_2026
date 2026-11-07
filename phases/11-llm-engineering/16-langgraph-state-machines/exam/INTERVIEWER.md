# 面试官手册

场景：本地agent运行记录可从显式旧点fork，持久化并发布完整superstep状态。开场2分钟；五关12/10/16/10/10分钟，共60分钟，没有真人用时校准。不要求SDK或真实模型。记录提示等级，所有assert保留。

## 澄清问题标准答案（English）

仅在候选人问到时，用下表英文回答；只澄清现有合同，不主动增加要求或给出修法。

| Question | Answer |
|---|---|
| Which checkpoint does a fork advance? | Use the explicit thread_id and from_id. Advance that historical snapshot without rerunning earlier nodes; do not substitute the latest checkpoint. |
| Who owns recursive copying in Part 3? | The given runtime owns caller state, each worker input and returned delta, and the published state and update containers. assemble_superstep does not implement recursive ownership. |
| What must assemble_superstep still guarantee? | Each worker completes exactly once on the common pre-state. Collect all updates before reduction, merge in declaration order, reject multiple overwrite writers even when values match, and retain every update including an empty delta. |
| Does append implement full add_messages behavior? | No. Here append means list concatenation preserving existing items and duplicate new values. Message-ID replacement and RemoveMessage semantics are outside this exercise. |
| Is completion_order actual concurrent SDK execution? | No. It is a deterministic local arrival-order simulation. The exercise runs no LangGraph SDK, real model or network service. |

## Part 1：historical fork

主要坑：显式历史ID被替换为latest；只拷贝state外层导致正确pending消费改变父分支；声明append却覆盖原消息；每条祖先边都在线性seen-list中查是否已访问。首错choose_checkpoint生产错误snapshot，fork_and_trace调用正确MemoryBook.apply_fork，正确pop_pending查找请求指定action时在外层KeyError；不要改坏consumer或虚构IndexError。三条语义修好后才能看到真实深history热点。

H1：核对request.from_id与返回snapshot，而非只看global最新记录。H2：比较fork前后完整父state，随后检查declared field reducer。H3：显式scoped ID lookup；deepcopy分支state；append保留旧值和重复新值；parent的scoped索引查找已给定正确；用path-local set判断重复祖先并重建完整链。

追问：fork为何无需重跑旧节点？父与兄弟branch如何保持独立？完整历史日志与某一条ancestry有何不同？真实cycle与上一次查询已见过的共享祖先如何区别？每个祖先的state为何不能借用当前head？

## Part 2：artifact与lineage发布

主要坑：thread+checkpoint共同构成身份；commit顺序不能变成字典/文件名排序；新branch的parent可以位于旧branch；artifact写入失败前不可先发布index。完整state、pending node、reducers、schema version都要留。安全路径、完整codec和单artifact atomic writer是真实Given，不考rawdecimal词面或通用JSON framing。

H1：分开观察artifact存在与index可见。H2：先检查现有完整记录和scoped parent，再写入。H3：相同记录重试return、冲突拒绝；writer成功后才append_index。load_all依index顺序恢复并检查文件身份，不用目录遍历当commit顺序。未index的有效artifact仍不可见；文件内容与索引scoped身份不符必须拒绝。

追问：为什么允许未index的孤立artifact而不允许悬空index？这里对并发writer、fsync和断电恢复承诺了什么？

## Part 3：Send superstep

主要坑：收齐所有worker前归并会让后续worker看到partial state；completion顺序不是reducer声明顺序；overwrite默认值不能在多writer时静默last-writer-wins；到达集合相等仍可能次数不符。完整Given runtime拥有caller私有state、每次worker输入、返回delta和最终state/每份delta证据的递归隔离；候选assemble_superstep只实现exact-once、barrier、声明序与冲突算法，public run_superstep入口已给定。

H1：分别列出worker看到的state与最后commit的state。H2：按到达序收集结果，但不要边收边改共同prestate。H3：所有wrapped worker读取同一未归并prestate；收齐所有outputs，先数overwrite writers，再按声明序调用已修merge_single。到达序列必须完整且每个worker恰好出现一次，set相等不代表次数正确。

追问：append一般不交换，为什么必须明确顺序？两个overwrite恰好相同值也拒绝的合同有什么好处？真正并发时worker异常如何影响commit？返回空delta的worker是否仍有证据？构建证据时为何不能重新调用worker？

## Part 4：committed patch

主要坑：只能对exact parent做diff；JSON Pointer中`~`与`/`是字段身份，不可错序转义；append逐项保留顺序和重复；patch依据完整child.state，不是其中一个worker delta。实际JSON-line驱动、当前checkpoint绑定、close/pull-through由给定实现负责。

H1：先用patch转换parent并与child完整相等比对。H2：区分append尾部与overwrite；考虑字段名含`/~`。H3：按child字段序逐个比较，转义先`~`后`/`；合法append发`/-`，其他changed field按parent是否存在用replace/add。新字段不能replace；旧list不再是前缀时必须替换完整list。

追问：为什么worker_updates不是多个可单独提交patch？为何重复message不能set去重？有delete时合同与编码要补什么？

## Part 5：lineage divergence

主要坑：共同祖先取两条真实parent路径最近交点，不是global最新；suffix必须排除交点；同名ID在不同thread不相关。正确全图shape/parent/cycle validation已给定，shared parent合法；候选任务是path/LCA/divergence，不重写旧课暂停恢复或嵌套subgraph执行。

H1：画两条root-to-head链。H2：比较共同前缀，记住最后相同位置。H3：按scoped parent走链并逆序，找到共同prefix长度；完整paths保留交点，suffix从它之后开始。无共同root返回None和两条完整suffix。相同head的suffix均为空；相同branch标签不能替代实际checkpoint身份。

追问：一条head恰为另一条祖先时返回什么？branch_id和parent_id职责怎样区分？共享祖先为何不是cycle？

## 评分表

| 关卡 | 分数 | 行为要求 |
|---|---:|---|
| 1 | 25 | 真实调用边界与历史点8；隔离/reducer9；完整深链响应及防过修8 |
| 2 | 15 | 完整scoped记录6；不可变/顺序4；失败发布一致性5 |
| 3 | 30 | exact-once/barrier10；声明序10；overwrite冲突/完整证据/空batch10 |
| 4 | 15 | exactparent/完整commit5；pointer/append7；Given驱动集成3 |
| 5 | 15 | 最近祖先5；完整path/suffix5；thread/分叉边界5 |

85–100独立完成并解释；70–84主行为正确且少量提示；50–69仅部分行为或边界不清；低于50不能维持完整状态证据。提示与未完成部分填复盘，不删除断言换通过。性能实测和证据边界见SCOPE。

当前性能验证保留完整18,000点历史调用，并另外测量34,000点typed记录的公开fork_and_trace：关系验证与scoped index构建、真实pending action、分支copy/reducer/commit、34,001条ancestry与完整records逐字段比较都在计时内。独立期望值与typed输入在调用前准备；不预计算业务结果，不更改GC。连续三慢三快在0.25秒限值下，慢侧余量8.76倍、快侧10.67倍，最慢2.45秒；只说明本地CPU教学压力，不代表SDK或生产吞吐。
