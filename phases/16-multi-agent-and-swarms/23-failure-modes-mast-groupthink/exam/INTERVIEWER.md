# 面试官手册：MASTStorm（16/23）

五关共100分。建议60分钟：开场2分钟，P1/P2/P3/P4/P5分别12/10/16/8/12分钟。时间未经真人校准；记录未完成工作后进入复盘，不用未验证的用时承诺评判候选。

## 主持开场（2分钟）

可直接读：

> “You maintain a deterministic incident and retry service. Work through the five parts in order. Explain each invariant, follow the real data flow and run the unlocked tests. The support modules are complete Given; keep their contracts and the test assertions.”

编辑范围为primitives、store、cascade、stream、structure五个candidate模块；测试只删除当前Part的skip装饰器。先读当前test与类型，复述expected/actual，再定位producer或状态变更。每关提示依次H1/H2/H3，记录时间和提示后的独立推导。

说明完整Given：P1正确renderer/tag collector；P2 CSV与exact三态codec；P3完整corrected breaker、logical clock、provider与finite intake；P4 observation绑定、severity与wire；P5完整sealed P3执行和trace binding。候选须正确使用，不重写这些依赖。

## 澄清问题（English FAQ）

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | Should the renderer reject an unknown category? | “No. Unknown is a legitimate result. The original primary key exists in the snapshot; preserve it so the correct renderer can still read its value.” |
| 1 | Should I catch the first KeyError in render_incident? | “No. Trace the destructive producer read. Keep the renderer's original-evidence contract.” |
| 1 | Is threshold equality enough to open? | “No. The declared comparison is strict greater-than and requires a full window. Keep the sample gate and cooldown boundary.” |
| 1 | Can several calls own HALF_OPEN before a result? | “No. One probe owns the slot. A successful probe clears the old outcome window, failure count and probe ownership.” |
| 1 | What does a failed recovery probe do? | “It reopens the breaker at the probe result's logical time, releases the probe slot and starts a fresh cooldown.” |
| 1 | Can I optimize by omitting report rows? | “No. Retain each actual allow/record decision and the complete final window. The complete local 40000/20000 replay has a recorded calibration; wall-clock margins are environment observations, not an SLA.” |
| 2 | Must I write CSV quoting or exact numeric encoding? | “No. CSVRows and the scalar/tree/Decimal/tuple/tri-state codec are complete Given. You own all twelve domain field associations and typed reconstruction.” |
| 2 | Does an action imply validation success? | “No. Preserve the independent Observation action, time, cleared value and note. True, False and None remain distinct.” |
| 2 | May equal rows or repeated incident IDs be deduplicated? | “No. Each append is an independent ordered snapshot, including identical rows.” |
| 3 | Do I implement the breaker again? | “No. breaker_given.py is the complete corrected P1 primitive. P3 owns actual-call budget, causal retries and the complete invocation trace.” |
| 3 | Does every retry or decision spend the budget? | “No. Spend one unit only for an actual provider invocation, whether it succeeds or fails. Short-circuit, exhausted-budget and dependency-failed decisions produce no provider outcome.” |
| 3 | Should the budget check happen after breaker.allow? | “No. Check remaining budget first so a zero-call path cannot reserve a half-open probe. Tick semantics are logical local evidence, not wall time.” |
| 3 | Is the cache keyed by service? | “No. Cache completed effect node UIDs in the shared root context. Distinct effects may use the same service.” |
| 3 | Can I stop visiting siblings after one dependency fails? | “No. Visit all declared children in order for that parent attempt. Invoke the parent only after all children are success or cached.” |
| 3 | Do later roots get a new budget? | “No. All roots, descendants and retries in this incident share the same context and remaining budget.” |
| 3 | May I reuse a completed context for a separate report? | “No. One complete replay uses a fresh CascadeIntake and an initially unused provider. Explicitly preloaded breaker resources remain legal.” |
| 3 | Is cached a new successful provider call? | “No. It is a zero-attempt trace for an already completed effect. Preserve that status and do not call or record a provider outcome.” |
| 4 | Must I implement the syslog protocol or severity classifier? | “No. Complete restricted encoding, observation binding and True/False/None severity are Given. You own the nine projected fields and actual closing decision.” |
| 4 | May a structured incident identifier contain a newline? | “No. Incident UID, root, category and action are single-line strings enforced by Given intake. Quotes, brackets, backslashes and Unicode are legal; the JSON note may retain quoted newlines.” |
| 4 | Can diagnosed or a positive fallback note close the incident? | “No. Closing requires phase validated and that event's own observation.cleared is True.” |
| 4 | May I copy the first incident's fields to every event? | “No. Use each event's own incident, root, category, action and observation note.” |
| 5 | Does P5 execute retries or admit budget again? | “No. sealed.py supplies the complete real P3 execution. P5 folds that immutable actual trace and never rejudges budget, breaker or validation.” |
| 5 | Are repeated service names one call? | “No. Count each actual invocation occurrence. Keep cached child occurrences with zero calls and preserve every retry edge.” |
| 5 | What is the amplification denominator? | “The number of declared root nodes in the sealed forest, including blocked roots. It is actual calls per root node; an empty forest has zero amplification.” |
| 5 | Must I expand a shared service graph? | “No. Finite unique effect nodes and complete parent/service binding are Given. Recursively account for the actual retry trace rather than expanding shared objects.” |
| 5 | What order should pruning paths and services use? | “Use actual child-first execution order. Paths retain each ancestor node and its retry ordinal; distinct services retain first actual invocation order.” |
| 全部 | Does this implement STRATUS or prove a 10x incident? | “No. This is a finite scripted local adapter. It implements no live STRATUS agents and claims no production amplification, recovery, network or model result.” |

## 每关主持、提示与追问

### Part 1 原始证据与完整breaker（12分钟，20分）

首个KeyError由producer pop掉primary symptom，经detect传给正确renderer后读取原key自然出现。保留symptom，不改renderer绕过证据。unknown本身正常；tag collector会保留全部独立命中。

后续breaker需single HALF_OPEN probe、successful reset与bounded rolling failed count。record只处理实际admitted bool outcome；满window才按strict >判断。候选更新失败总数时应减去过期失败贡献，再加入本次贡献，实例状态彼此独立。

失败probe释放slot、按该结果logical time重开并重新cooldown；不能保持HALF_OPEN或沿用过期opened_at。

- H1：“Which producer changed the evidence the renderer is about to read?”
- H2：“After detection is correct, follow OPEN, cooldown, a pending probe and its result.”
- H3：指向pop/get、probe_inflight、成功恢复时outcomes/failures一起clear；滚动窗询问旧项离开时对失败总数的贡献。

追问：“Why is deque alone insufficient?” 观察点：candidate已用deque，但每record仍sum整个window；需要增量total，同时保过期/阈值/reset与完整ReplayReport。40000 outcomes、window20000、0.12秒已有完整本机校准记录，实际观测见SCOPE；不能删输出、预造返回、加sleep/padding或改GC。

### Part 2 完整append-only CSV（10分钟，20分）

候选把IncidentRecord投成12字段：uid/root/primary/symptoms/category/tags/action/call_budget和Observation的action_uid/at/cleared/note，读回重建两个模型。保相同row的重复出现、原症状、全部tags与声明顺序。

CSV header/quote、exact codec、巨大整数/Decimal和三态表示均完整Given。候选的字段关联是真实职责；不能因codec正确而把whole domain serializer也说成Given。action存在与独立validation是不同事实。

- H1：“Which fields belong to the incident, and which belong to its independent observation?”
- H2：“Compare the twelve columns with IncidentRecord and Observation, then reopen every row.”
- H3：指向前8个incident字段与后4个observation字段；保全部rows而不是latest/dedup，cleared必须来自observation。

追问：“Why may one incident ID have False, None and True observations in different rows?” 观察点：每row是独立append snapshot；缓解动作、未知状态和实际clear不能互相替代。只评价实际mapping，不额外考Given三态或precision转换。

### Part 3 三个真实causal算法（16分钟，25分）

`invoke_attempt`推进logical tick，先查remaining，再调用该service的Given breaker.allow；只有实际provider.invoke才used+=1并record真实结果。其返回Invocation区分invoked与short-circuit/budget-exhausted，后两者actual=False、success=None。

`execute_retry_tree`先查effect UID cache；未完成节点按自己的attempts上限依序访问全部children。依赖全部success/cached才调自身provider，否则记dependency-failed。只有actual且success才缓存此UID并停止；失败依赖可在下一parent attempt重试，成功sibling保cached。

`replay_cascade`以同context遍历所有root，保原incident/root、完整nested trace、used/remaining、真实provider calls和effects顺序。P1 breaker完整Given；P2 archive实际重开给context，不给完整cascade solver。

每次完整replay使用fresh CascadeIntake与initially unused provider；同次replay内的roots共享它。预置breaker是合法资源，不表示可复用已经完成的context产生另一份report。

- H1：“Which decisions actually call the provider and consume this root's budget?”
- H2：“Follow the first successful sibling while another dependency fails and the parent retries.”
- H3：将budget check放在allow前；effect cache按node.uid；每次parent attempt完整记录children和own Invocation，后续root不换context。

追问：“Why are two calls to service A not necessarily the same effect?” 观察点：node UID是effect身份，service仅资源选择。再问：“Why is short-circuit not a provider failure?” 观察点：没有invoke，也没有record或预算消耗；回报保non-invoked状态，不伪造outcome。

### Part 4 own-event syslog投影（8分钟，15分）

候选逐event投9字段：event_uid、incident uid、root、phase、category、action、severity(e)、closing、note。非validated note为空；validated用该event独立observation.note。closing只在validated且cleared is True成立。

完整event/observation intake、action绑定、三态severity与timestamp/escaping/formatter/async writer为Given。候选应使用它们，不把fallback文字或未知observation当clear，也不复制首incident字段到peer。

incident uid/root/category/action允许quote、bracket、backslash和Unicode，但不含CR/LF；完整Given intake保证单行framing。Observation note通过JSON保quoted newline。

- H1：“Which incident and observation belong to this event?”
- H2：“Compare detected, diagnosed and three validated observations: False, None, True.”
- H3：指向phase=='validated'与cleared is True的联合条件；九字段从当前e/r取，severity调用Given，note只从当前validated observation取。

追问：“Does serializing a validated event prove mitigation worked?” 观察点：只能表达声明的独立observation；False/None不closing。受限RFC5424-style本地adapter不等于完整或线上syslog实现。

### Part 5 sealed trace递归accounting（12分钟，20分）

完整sealed P3会真实执行脚本provider并产生trace；TraceCatalog给shape/UID/parent/service binding，没有subtree totals。candidate递归每个NodeTrace的每次AttemptTrace及每个child EdgeAudit，保attempt ordinal、invocation status/actual/success/remaining与原nested结构。

own_calls只计inv.actual；subtree total=own+全部child totals。short-circuit与budget-exhausted分别累计，dependency-failed本身不是provider call；cached child保结构、0 calls。pruning path包含每层(node UID,attempt ordinal)，按child-first执行顺序收集，actual distinct services也按首次真实调用排序。

递归须贯穿实际top(A)→middle(B)→bottom(A)三层，分别保3/2/1的subtree calls；不能只处理immediate child或按service名合并。

- H1：“Which trace occurrences invoked a provider, and which only explain pruning?”
- H2：“Keep every child under each parent retry, including the cached second occurrence.”
- H3：递归返回own/total三类计数与edges；在child递归后记录当前invocation的service/pruning path；总actual calls与sealed calls ledger对应，Fraction(total,len(roots))，空forest为0。

追问：“Why can four calls have only two distinct services?” 观察点：service身份和attempt occurrence不同。另问：“Why does the blocked later root stay in the report?” 观察点：它仍是声明root，贡献0调用但保budget-block完整path，amplification分母仍包含它。

P5不重新判断validation、预算准入或breaker，不重写P3，不展开共享service对象。评分给真实nested accounting，不把sealed trace误说成预先给完所有答案。

## 100分评分表

按独立实现、提示后完成与只读懂参考分别记录。早关依赖失败应定位责任，不把同一根因跨关反复扣满。

| 关 | 评分项 | 分值 | 实得／代码与测试证据 |
|---|---|---:|---|
| 1 | 原primary证据与合法unknown/完整tags | 5 | |
| 1 | single half-open probe与cooldown | 5 | |
| 1 | successful reset与实例隔离 | 4 | |
| 1 | 真实增量expiry计数/strict gate/完整ReplayReport | 6 | |
| 2 | incident/root/primary/原symptoms/category/all tags | 7 | |
| 2 | own action与root call_budget | 4 | |
| 2 | 四个独立Observation字段关联 | 5 | |
| 2 | append重复顺序与完整typed reopen | 4 | |
| 3 | shared actual-call budget与admission-before-probe | 8 | |
| 3 | 全children因果重试与effect UID成功cache | 10 | |
| 3 | 全root完整trace、真实outcome/calls/effects关联 | 7 | |
| 4 | 当前event/incident/root/category/action身份 | 5 | |
| 4 | own phase/note与Given severity/wire集成 | 5 | |
| 4 | 实际validated cleared True才closing | 5 | |
| 5 | 全nested retry edges与ordinal invocation evidence | 7 | |
| 5 | own+subtree actual/short/budget三类accounting | 7 | |
| 5 | 原root关联、完整paths/service顺序/Fraction与empty | 6 | |
| 合计 | P1/P2/P3/P4/P5 = 20/20/25/15/20 | 100 | |

P2保独立observation与P4closing是各关真实职责；不把它们隐藏为Given，也不在P5第三次判断。codec、完整P1 breaker、完整sealed P3和severity只按正确使用留证据，不重复主评分。

## 当前验证边界

<!-- VALIDATION_STATUS_BEGIN -->
当前48个Python文件、五个测试、43条assert、0处pytest.raises、五锁与26个登记错误写法。领域覆盖包括声明的primary与原symptoms独立关联、配置的正整数attempt上限、全部dependency sibling、原event顺序、完整祖先retry路径及first-actual service顺序。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过；12份matching reference各自五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有实际记录。正式检查已通过，记录见 verification.txt。

P1真实负载40000个bool outcome、window20000、strict threshold .5；完整BreakerDesk.replay和entire ReplayReport equality（每个actual allow/record序号、state、sample count、failure count及完整final window）均在timer内，独立expected在外。

完整校准三个慢样本[1.345574207836762, 1.4553501659538597, 1.3413112498819828]秒，三个快样本[0.00878770905546844, 0.010089250048622489, 0.009202209068462253]秒；限值0.12秒，慢侧／快侧余量11.177594／11.893847。六份测量副本仅将timing assert改为实际elapsed打印，慢版另恢复真实bounded outcome窗口重sum；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有全五关通过。墙钟记录受环境影响，不作跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->
