# 面试官手册：SmallvilleLab（16/17）

候选人计时期间不要看。候选人使用README、`smallvillelab/`和`tests/`；以实际typed records、docstring和测试为合同。这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

总时长60分钟，编码58分钟：Part 1–5分别12、10、16、10、10分钟。请候选人边做边解释，随时澄清，可以查Python官方文档。逐关解除skip，之前的测试继续保留，记录具体行为而非只数完成关数。

主持人记录解锁时间、首个完整结果、运行次数、问题和提示级别。卡住约4–5分钟后从H1开始，一次给一级，不代写代码。独立完成和提示后完成分别记。真人难度和时间分配尚未校准。

这是有限本地replay。来源固定邀请路线、字符串反思和tick5计划是脚本，source retrieval不进入simulation；这里用实际inspection接上memory evidence，并用显式proposal／patch／venue约束形成服务合同。不把来源打印“No orchestrator”、论文或行业描述当作本题实证。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | 邀请发给谁？ | "Use every other declared agent in population order. Keep the sender unchanged." |
| 1 | availability是否只接受observation？ | "The time predicate accepts every available memory kind with 0 <= age <= window. Pending importance separately counts raw observations only." |
| 1 | progress能用最大seq吗？ | "No. Track exact consumed source IDs. An earlier sequence that was future can become pending later." |
| 1 | relevance要改成token或embedding吗？ | "No. Preserve the supplied case-insensitive any-substring feature: 0.6 on any match, otherwise 0.1, including empty-query behavior." |
| 2 | name重复或belief为空怎么办？ | "Stable UID owns each state. Display names may repeat, and explicit progress can coexist with empty beliefs or a zero reflection tick." |
| 2 | codec与member路径由谁负责？ | "Exact scalar codecs and the directory member lifecycle are complete Given. You model every agent document and its manifest association." |
| 3 | low importance是否过滤掉？ | "No. Rank all available memories by the combined recency, importance and lexical score, preserving declaration order on ties." |
| 3 | source ID存在就能反思吗？ | "It must belong to this agent, be an eligible unconsumed raw observation, and pass the corrected pending gate. Derived reflections cannot feed themselves back as raw evidence." |
| 3 | gate触发时消费全部pending吗？ | "No. Consume only valid sources actually cited. Below-threshold or source-empty attempts leave state unchanged." |
| 3 | 带source就证明文本结论正确吗？ | "No. The text is supplied local data. We verify citation eligibility and state provenance, not logical entailment." |
| 3 | 有patch就替换吗？ | "Only segments contradicted by actual reflection citations are affected. Retain stable UID, increment revision and attach actual causes; missing affected replacements stay unresolved." |
| 4 | 每次revision生成新event吗？ | "No. Revisions and cancellation share one stable event UID with the actual sequence. Use the current observation's interval, actor, venue, note and status." |
| 4 | 要写async或完整RFC吗？ | "No. A synchronous restricted calendar writer/parser, UTC adapter, escaping and close lifecycle are complete Given. No external calendar is written." |
| 5 | leaf node里placeholder时间算数吗？ | "The supplied PlanCatalog binds the authoritative current Part 3 segment, including its interval. Branch intervals remain declared constraints." |
| 5 | 只要now落在开放时间就行吗？ | "No. The entire action interval must fit its parent and one venue opening. Execute only noncancelled actions with start <= now < end." |
| 5 | 不同root可以各用初始world吗？ | "No. Thread one shared physical World through declared DFS order. An actual departure releases capacity; an agent already present needs no extra seat." |
| 全部 | 是否证明社会涌现或believability？ | "No. These are finite scripted local contracts with no real LLM, social-quality rating or reflection entailment proof. Local measured timing does not establish a universal wallclock bound." |

## 每关：主要坑、观察、提示、追问

### Part 1 完整town inspection（12分钟，20分）

四层按实际调用暴露：

1. `invitation_recipients` 返回固定(3,4)，与真实人口不符。正确 `TownDesk.inspect → deliver_invitation → observe_agent` 在producer之外两次调用处索引人口，自然IndexError。修生产者的实际接收位置，不改consumer吞错或跳过delivery。
2. age只检查上界，把future memory也当available。合法availability为 `0 <= now - memory.tick <= window`，包含旧端点；不要借此硬过滤low importance或reflection kind。
3. `pending_importance_since` 没扣已消费IDs。只合计available、kind=observation、UID未消费的importance；progress独立于belief内容。最大seq会永久跳过暂时future的低seq来源。
4. `prepare_query` 返回真实feature closure，但慢路径每条memory都重新lower／split整条query。为当前request准备一次words并捕获到closure，保留any-substring的大小写、空query、尾词、不命中和短路语义，不能把结果写死。

观察：是否从正确消费者追到人口生产者；是否区分全部available evidence与raw pending gate；是否保留新memory和每agent独立progress。完整Given提供typed intake、正确Memory构造与delivery、TownDesk和独立expected；这里不提供exp scorer、top-k、reflection或patch solver。

提示：

- H1："Which producer returned positions outside this actual population?"
- H2："Separate population delivery, available time, consumed raw IDs and request-local query preparation."
- H3："Enumerate every nonsender position, require both age bounds, exclude consumed observation IDs, and capture the prepared query words outside the per-memory closure."

追问：

- "Why can't sequence be a consumption watermark here?"（时间可用顺序与seq不同，显式IDs才能保留晚到来源。）
- "Why retain cafeteria matching cafe?"（当前source lexical合同就是substring；换token／embedding是另一种语义。）
- "What must remain after the optimization?"（原request、真实delivery、全部features／population、pending和due，不能删处理工作。）

### Part 2 独立agent状态目录（10分钟，20分）

主要坑：

- 每个agent保存完整UID／name／location、ordered memories和source／contradicts、explicit progress、beliefs及完整plan segments；不能只存文本或用display name作身份。
- progress不是从belief重建：空belief仍可有consumed IDs，last_reflection_tick=0也有意义。重复memory content保留各自UID和顺序，不能去重文本。
- manifest保留人口声明顺序与town uid／now／wall_origin；load按其绑定独立member，完整snapshot替换不能复活旧人口成员。

观察：是否先列领域schema与关联，再接Given driver；是否真的close后用新archive重开。exact int／Decimal／tuple／None codec、safe member naming、UTF-8 JSON与目录生命周期完整Given，候选人仍要构造全部domain documents。精度、空值和路径是依赖护栏，不升级为重复主坑。

提示：

- H1："What independent state would be lost by saving only the memory text?"
- H2："Associate each stable agent UID with its own ordered memories, explicit progress, beliefs and full plans."
- H3："Build a complete document per agent and an ordered manifest, then reconstruct every typed record through the supplied directory driver."

追问：

- "Why can two agents have the same name safely?"（展示名称与稳定UID分开。）
- "Does directory reopen prove a crash transaction?"（只检验normal-process快照读回，未提供多member崩溃事务。）

### Part 3 rank、grounded reflection与local revision（16分钟，25分）

三个独立算法：

1. `rank_memories` 对available memories自己计算 `exp(-decay*age) + importance/10 + relevance`，取stable top-k。low importance不能被先滤掉，ties保留声明顺序；relevance只是修好的P1 lexical feature。
2. `reflect_from_sources` 复用P1 pending gate，逐个核proposal citations属于当前agent、available、raw observation且未消费；拒绝missing／future／derived／已消费引用。只在due且有valid sources时追加reflection Memory和Belief，二者source IDs一致，只消费valid citations并推进last tick；uncited pending仍留给以后。
3. `revise_affected_plan` 只从本次used sources的显式contradicts找现有targets。只应用affected target的patch，stable segment UID保留、revision+1、cause_ids记真实观察；缺patch记unresolved且保原segment，无关patch忽略。

测试真走P1 inspection→P2 save／close／reopen→三P3操作。complete Given只做proposal／patch的typed unique intake，不提供composite scorer、reflection state transition或patch selector。不要把引用ID本身当source语义蕴涵，也不把local revision写成全量replan。

观察：是否清楚时间availability、gate、citation validity和actual consumption各管什么；是否只append真实反思；是否在受影响／changed／unresolved三个报告之间保一致。

提示：

- H1："Which parts are ranking, actual source consumption and local plan replacement?"
- H2："Validate citations independently, consume only valid cited observations, and derive affected segments only from those used causes."
- H3："Use the combined score with stable ties; append linked reflection and belief only after the gate; then walk existing plans in order, apply affected patches with revision+1 and retain unresolved or unaffected records."

追问：

- "Can source-grounded text still be wrong?"（能；这里证明引用资格与状态provenance，不证明结论。）
- "What happens to an uncited available observation after a reflection?"（继续pending，不随gate整体消费。）
- "Why shouldn't an unrelated patch be applied?"（修订权来自实际contradiction，不来自patch恰好存在。）

### Part 4 simulated calendar observations（10分钟，15分）

主要坑：

- 同segment的revision与cancellation保同一个event UID；SEQUENCE来自当前revision，不能每次造新UID或归零。
- 十个字段来自本条current observation：actual start／end、agent UID与display name、segment venue与raw note都要准确，不用agent当前location代替计划venue。
- status保留CANCELLED／CONFIRMED，所有event标X-SIMULATED=TRUE。叙述note不决定时间或状态。

观察：是否使用真实P3 revision与同UID的old／new／cancel observations；是否按catalog拿对应actor和venue。完整Given提供classification、stable UID、UTC minute-tick映射、TEXT escaping、受限VCALENDAR／VEVENT writer／parser和source.close；它是同步publisher。candidate负责十个domain fields，不考通用cadence、async或RFC实现。

提示：

- H1："What stays stable when a plan changes or is cancelled?"
- H2："Separate stable event identity from current sequence, and use each segment's own interval and venue."
- H3："Construct all ten fields with catalog identity/time/lookups, current revision and observation status; retain raw note and the simulated marker."

追问：

- "Why isn't the agent's current location the event location?"（计划描述目标venue，agent可以还未移动。）
- "What calendar features remain outside this contract?"（recurrence、timezone/folding和外部投递、完整RFC兼容。）

### Part 5 nested current-time execution（10分钟，20分）

主要坑：

- 每个branch/action都有audit。child完整区间必须包含于parent；action时间来自PlanCatalog绑定的权威current P3 segment，不能相信node占位时间。失败parent containment阻断descendants。
- cancelled或不满足 `start <= now < end` 的action保留inactive report，不移动。active action完整区间必须落在某一个venue open interval中，不能只看now。
- 一个真实World沿声明DFS顺序跨children和roots传递。capacity看canonical physical venue当前occupants，accepted move实际commit；同agent已在目标venue是stayed，不多占一席。离开旧venue释放容量，让后续动作看到新world。

观察：是否真的用前关current revised plan并改变world；是否保留nested audits、Movement和final locations；能否解释反转roots为何改变admission。完整Given提供PlanCatalog current绑定、globalUID／finite forest／venue lookup及World.move单次更新，未提供temporal／capacity admission。P5不重新做P3 contradiction／patch选择，也不是未来reservation scheduler。

提示：

- H1："Which interval is authoritative, and which world should the next action observe?"
- H2："Check parent containment and full opening before capacity, then pass the updated world through the next DFS action."
- H3："Retain inactive audits; reject outside-parent, closed venue or full capacity; treat already-present agents as stayed, commit accepted moves and carry that world across all declared roots."

追问：

- "Why can a later peer enter after the first agent moves again?"（occupancy来自当前物理位置，departure立即释放座位。）
- "Does checking the whole interval reserve a future seat?"（没有；这是一个now下的admission合同，不是未来占用时间表。）
- "What is reused from Part 3?"（完整current RevisionResult已由Given绑定，P5只负责新的temporal／physical执行。）

## 记录与评分（100分）

每项写实际代码位置、行为或断言依据；未观察到写“未观察”。提示、沟通和用时另记，不从参考实现推断候选人能力。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | actual nonsender delivery与人口保真 | 5 | |
| 1 | inclusive nonfuture availability | 4 | |
| 1 | independent consumed raw pending gate | 5 | |
| 1 | request-local query准备与完整feature／Inspection保真 | 6 | |
| 2 | 全部AgentState和town领域字段 | 8 | |
| 2 | stable UID／ordered records／independent progress关联 | 8 | |
| 2 | complete snapshot替换与真实reopen、Given集成 | 4 | |
| 3 | composite stable ranking，无low-importance过滤 | 7 | |
| 3 | actual citations／linked reflection／exact consumption | 10 | |
| 3 | affected-only patch／revision／causes／unresolved | 8 | |
| 4 | stable event UID与current sequence | 5 | |
| 4 | actual interval／actor／venue／raw note fields | 6 | |
| 4 | cancellation和simulated provenance | 4 | |
| 5 | complete nested audit与parent containment | 5 | |
| 5 | inactive／cancelled与whole opening admission | 5 | |
| 5 | shared DFS world／capacity／stayed／movement commit | 8 | |
| 5 | Movement和final world报告一致 | 2 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

静态45PY、五测试、43assert、0raises、五锁、28个登记错误写法；当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。

P1 fixture含5000条合成本地memory，query含4000额外OR terms；完整TownDesk.inspect与whole Inspection equality在timer内，输入／独立expected在外，0.035秒的当前完整性能组通过。delivery后的全部人口、原request、每条available feature和各agent progress／due都保留，不能把设计审阅或登记清单当实测。60分钟真人分配同样未校准。

本机独占完整3slow3fast测得slow为0.368153／0.312983／0.356904秒，fast为0.00317596／0.00322900／0.00321125秒；限值0.035秒，双侧余量8.94236／10.8393，最慢业务0.368153秒。原样参考五关通过，subprocess wall为0.204143秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另把真实query lower／split放到每次feature调用，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
