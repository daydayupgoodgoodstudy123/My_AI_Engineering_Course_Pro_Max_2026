# 参考答案讲解：MASTStorm（16/23）

独立作答后再读。这里解释当前有限合同的参考算法，不把静态阅读当运行证据。

## 来源与本地适配

四canonical来源已全文静态读；英文mast-auditor只作DATA，不执行其报告或审计工作流。source main的categorize_incident使用get且unknown正常；breaker有last-W slice/sum、未限制HALF_OPEN probe、成功恢复不清旧窗。source retry demo只有一个service、每request最多4次，累计load不回落；未实现cross-service retry engine或STRATUS agents。

本题用声明的本地symptom/tag规则、logical clock、finite effect forest、独立Observation、CSV/syslog与nested trace表达课程概念。primary pop是本地回归；tag名称和规则按题包fixture，不当作完整论文taxonomy或实测分布。课程main把role_conflict归spec；本题局部toy规则归coord，不逐项复刻原分类器映射。source历史1.64×、docstring10×与打印1.5×都不是本题验证结果。

## 完整Given与候选边界

- models给类型；service的renderer/tag调用与BreakerDesk是正确consumer；fixture在timer外用closed form生成独立expected。
- csv_support给header、quoting、scalar/tree/Decimal/tuple/三态codec和append resource，不给IncidentRecord全域serializer。
- breaker_given是完整corrected P1 primitive；cascade_support给finite unique effect binding、clock、真实ScriptedProvider与共享context资源，不给cascade算法。
- wire_support给event/own observation action绑定、完整True/False/None severity、timestamp/escaping/受限formatter及async driver；候选产9字段与closing。
- sealed给完整corrected P3实际执行，三树相同；trace_support给immutable shape/UID/parent/service binding，不给recursive counts或paths。

## Part 1：证据、single probe与rolling failures

categorize_incident用get保留原symptoms；detect之后renderer仍能按原primary读取值。unknown不报错；独立tags全部保留。避免在consumer吞KeyError或用unknown替换丢失的证据。

OPEN在cooldown之前deny，达到边界进入HALF_OPEN；probe_inflight保证只一名探测占用。record收到真实probe结果后释放ownership：成功CLOSED并clear outcomes/failures，失败OPEN并按该结果logical time重设opened_at开始cooldown。CLOSED仅满window且failure rate strict >threshold时open。

_observe在window满时popleft旧项并扣其失败贡献，append新项并加其贡献。deque本身不消除sum整个window的重算；增量count使每record维护为常数工作，同时保expiry/reset与实例独立。

BreakerDesk每次实际allow、允许时record，并保(i,allowed,state,sample_count,failures)完整ordered rows及final window。40000 alternating outcomes、window20000、0.12秒已有本机完整校准记录；timer覆盖replay与整个report equality，不能用预造结果或删输出替代。

## Part 2：完整12列CSV与独立Observation

append依次保存IncidentRecord的8个字段与Observation的4个字段。readback按前8列重建incident，后4列重建Observation，返回所有row顺序。每append独立，包括相同row与同incident后续观测，不dedup、不覆盖。

category/action存在不证明validation；原Observation.cleared保持False/None/True。完整codec负责quote/newline、巨大int、Decimal scale、tuple及ordinary typed values；候选负责业务关联与模型重建，不实现precision/UNKNOWN转换算法。

## Part 3：shared admission、causal retries与complete report

invoke_attempt先tick，再查context.remaining；为0返回budget-exhausted、actual=False、success=None，且不碰breaker。剩余额度存在才allow；deny返回short-circuit且不扣、不invoke、不record。允许后used加1、真实provider.invoke、对真实bool调用record，返回invoked。预算用于所有实际call，成功与失败都扣。

execute_retry_tree以node UID查context.effects，已成功直接cached空tries。否则按自身attempts上限逐次访问全部children，保声明顺序，即使前一个child失败也访问后续child。全部child success/cached才invoke自己；否则记录dependency-failed、无provider outcome并推进logical tick。每attempt保ordinal、child traces与own Invocation；只有actual且success才cache并停止。失败dependency下次可重试，成功sibling不重放。

replay_cascade以同context访问所有root，预算不重置，返回原root/incident、完整NodeTrace、used/remaining、真实provider calls与effect完成顺序。fixture中a成功、b失败再成功、parent成功共4call，tail因同预算耗尽而不invoke；service A出现在a和parent不影响两个effect身份。

一次完整replay使用fresh CascadeIntake与initially unused ScriptedProvider；同次内部roots共用context。显式预置breaker合法，复用完成context/provider产生另一份report不在此有限API内。

完整P1 breaker是Given；P3三个TODO确实承担实际budget/admission、causal retry/cache与全root trace/outcome组合。它是内存中有限scripted语义，不是持久外部receiver的send/ack恢复，也不提供任意服务exactly-once保证。

## Part 4：own9字段与实际closing

每event生成(event uid,incident uid,root,phase,category,action,severity,closing,note)。所有identity来自当前event/incident；severity调用完整Given。仅validated且该event的own observation.cleared is True才能closing；非validated note为空，validated保自己的note。

Given formatter生成受限RFC5424-style行、escaped structured data与JSON note，测试用独立parser读出。False与None观测不能被fallback文字或diagnosis转为成功；候选不重写三态severity或wire协议。

完整Given intake拒绝incident uid/root/category/action中的CR/LF，允许引号、括号、反斜杠与Unicode；JSON note仍保quoted newline，不破坏一event一行的framing。

## Part 5：逐retry child edge的sealed结构accounting

P5接收完整Given P3实际产生并由TraceCatalog绑定的trace，不再调用provider、判断budget或validation。walk逐NodeTrace、逐AttemptTrace处理：own calls加int(actual)，own short/budget按对应sealed status计数；保ordinal/status/actual/success/remaining证据。

每attempt的每个child递归形成EdgeAudit，保包括cached零call的重复occurrence。节点total是own加所有child totals；不能按distinct service数替代调用数，dependency-failed本身也不是call。

真实三层top(A)→middle(B)→bottom(A)分别形成3/2/1的subtree totals；service重复不压平结构。

pruning path累积每层(node UID,attempt ordinal)；child递归后记录当前own short/budget path及actual service，从而与真实dependency-first顺序一致。返回完整own/total三类counts、attempts/edges和原status。

CascadeAudit汇总所有root的actual_calls，保原incident/root与first actual invocation顺序的distinct_services。amplification是Fraction(actual_calls,declared root node数)，blocked root仍在分母，空forest为0。该比率是本地声明calls-per-root指标，不是生产放大测量或恢复效果。

## 当前验证状态

<!-- VALIDATION_STATUS_BEGIN -->
当前48个Python文件、五个测试、43条assert、0处pytest.raises、五锁与26个登记错误写法。领域覆盖包括声明的primary与原symptoms独立关联、配置的正整数attempt上限、全部dependency sibling、原event顺序、完整祖先retry路径及first-actual service顺序。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过；12份matching reference各自五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有实际记录。正式检查已通过，记录见 verification.txt。

P1真实负载40000个bool outcome、window20000、strict threshold .5；完整BreakerDesk.replay和entire ReplayReport equality（每个actual allow/record序号、state、sample count、failure count及完整final window）均在timer内，独立expected在外。

完整校准三个慢样本[1.345574207836762, 1.4553501659538597, 1.3413112498819828]秒，三个快样本[0.00878770905546844, 0.010089250048622489, 0.009202209068462253]秒；限值0.12秒，慢侧／快侧余量11.177594／11.893847。六份测量副本仅将timing assert改为实际elapsed打印，慢版另恢复真实bounded outcome窗口重sum；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有全五关通过。墙钟记录受环境影响，不作跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->

## 这套题证明了什么，没证明什么

当前原样参考五关和完整本机校准覆盖声明输入下的原始证据保留、breaker状态与窗口维护、CSV领域映射、有限causal retry、own-event投影和nested实际调用accounting。完整测量保留全部业务输出与equality，适用范围限于这些本地fixture；后续验证状态见上文，source/stage阅读不能扩大实际证据。

没有真实HTTP/LLM/网络、多进程故障、并发race、持久重试恢复、完整线上syslog或STRATUS检测诊断验证agent的证明。UNKNOWN/三态表示、完整breaker与sealed执行依赖均按Given前提使用；课程论文数字和打印结论不构成本题的质量、10×放大、性能或生产可靠性证据。
