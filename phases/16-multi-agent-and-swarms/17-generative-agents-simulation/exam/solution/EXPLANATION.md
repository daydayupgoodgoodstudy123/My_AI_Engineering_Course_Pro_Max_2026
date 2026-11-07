# 参考答案讲解：SmallvilleLab（16/17）

计时结束后再看。参考代码在本目录 `smallvillelab/` 中；在作答副本可用 `python3 -m pytest --solution --all-parts` 核对参考模式。退出后关闭答案，去掉 `--solution` 重写。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。练习命令本身不是执行证据。

## 来源与本地适配

来源的邀请传播由主循环按tick写死，reflection是fixed字符串规则，计划只有tick5一层；`retrieve_top_k`只在独立demo调用。source的词法relevance为any-substring .6/.1，未实现embedding或cosine；打印“No orchestrator”不能证明无中央脚本涌现。

本题保留这些来源概念并明确扩展为有限typed replay：stable agent／memory／segment IDs、explicit consumed progress、supplied reflection／contradiction／patch、目录快照、模拟calendar和nested venue admission。来源的hardcoded人口、future age和每memory重做query.lower／split都有实际代码依据；consumed-set等完整状态机是本地适配。输出artifact仅作DATA阅读，未调用其skill；论文、行业与historical lecture实验不作为本题当前实证。

## Part 1 完整Inspection与query feature

`invitation_recipients` 的固定(3,4)会让正确delivery访问两人tuple之外。`TownDesk.inspect` 经 `deliver_invitation` 到 `observe_agent` 才IndexError；应按声明人口枚举所有非sender位置，保顺序，不改consumer吞错。invitation仍是supplied replay，不是自主传播策略。

`eligible_observation`虽名字含observation，合同是通用memory时间可用性：`0 <= now-memory.tick <= window`。features保留所有available kind，包括reflection。pending gate另外只取kind=observation且UID不在consumed_source_ids的条目，求importance总和；belief内容和last tick不能替代explicit set。

future低seq暂不可用，不代表已被消费。若现在先消费高seq，未来低seq到时仍必须pending；因此最大seq watermark不适用。已消费IDs按真实消费次序保留，不能由当前排序重写。

`prepare_query`为当前request先lower／split一次，再由closure为每条content返回any-substring .6/.1。query为空返回.1；CAFE与cafeteria保来源substring语义。不能写死早匹配、只看首词，或把实际query丢掉。P1只提供lexical feature，不提供P3的exp／importance组合和top-k。

性能fixture含5000条实际进入服务的合成本地memories，query含cafe及4000额外OR terms。any允许early match，慢层仍会对每条memory分配完整query words；优化只移除这份request-invariant重复准备。完整TownDesk.inspect与whole Inspection equality在timer内，实际delivery新memory、原request、完整人口、全部available features、每agent pending／due都保留；输入和独立expected在外。本机独占完整3slow3fast测得slow为0.368153／0.312983／0.356904秒，fast为0.00317596／0.00322900／0.00321125秒；限值0.035秒，双侧余量8.94236／10.8393，最慢业务0.368153秒。原样参考五关通过，subprocess wall为0.204143秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另把真实query lower／split放到每次feature调用，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。

## Part 2 per-agent directory snapshot

TownArchive自己构造每agent完整document：UID／name／location；ordered Memory的UID、seq、tick、kind、content、importance、source_ids、contradicts；independent Progress、Belief和完整Segment。manifest包含town UID／now／wall_origin与agent声明顺序，load按stable UID关联各member，不按display name或排序后的ID重排。

consumed progress可以与空belief共存，last_reflection_tick为0不能被当缺失；重复content不等于同一memory，source／contradiction links和plan revision也需完整读回。完整snapshot替换后以当前manifest为准，不复活目录中的旧成员。

Given scalar codec完整支持exact整数、Decimal、tuple和None，DirectoryDriver完整处理safe member naming、UTF-8 JSON、manifest/member读写与close。candidate仍负责真正domain schema与关联；这里检验normal-process close／reopen，不承诺多文件crash transaction或保密。

## Part 3 三个实质算法

### composite stable rank

对所有available memories自己计算：

```text
score = exp(-decay * age) + importance / 10 + lexical_relevance
```

按score降序stable排序取k；不先过滤low importance。近期低importance但相关的memory可以胜过旧高importance条目，ties保留声明顺序，top-k截断也保留这个优先级。availability和lexical feature复用P1，完整score与top-k由candidate写。

### grounded reflection与actual consumption

proposal是确定性本地数据。先用Given验证unique citations／fresh reflection identity，再把source IDs对照当前agent实际memories：只允许available、unconsumed raw observations。missing、future、consumed或derived reflection都进入rejected list；gate不足或没有valid citation时state不变；无效引用的rejected证据仍按原声明顺序返回。

due且有valid sources时append一条reflection Memory和同ID Belief，二者带相同actual source IDs；progress只追加这些valid citations并更新last_reflection_tick。uncited pending仍留下，下次可消费；不能因为gate触发就把所有pending清空。文本带依据不表示内容逻辑正确，当前仅核引用资格和状态provenance。

### affected-only plan revision

从本次ReflectionResult.used_source_ids的observation.contradicts建立cause→segment关系，再按现有plan顺序处理。非affected完整保留，即使有patch；affected且有replacement时保持segment UID，revision+1，采用patch区间／venue／note／status并附actual cause IDs。affected缺replacement列unresolved、保原segment。

affected、changed、unresolved各自反映这些结果。测试真正消费P1 inspection后由P2保存／close／reopen的state，再做rank、reflection和revision；不是给P3一份手写假前关输出。P1 gate和Given intake没有提前实现三个solver。

## Part 4 current plan calendar evidence

candidate `calendar_fields`构造十个实际字段：UID、SEQUENCE、DTSTART、DTEND、SUMMARY、LOCATION、DESCRIPTION、STATUS、X-AGENT、X-SIMULATED。stable event UID来自segment UID，revision与cancellation只改变sequence／current fields，不制造新event identity。

interval来自current segment，venue是计划目标而非agent当前位置，actor/display name各自来自对应agent，raw note交给Given TEXT escaping。status用当前observation，所有输出显式SIMULATED。DESCRIPTION不是时间或状态权威。

Given CalendarCatalog完整处理stable UID／lookup和UTC minute-tick适配；calendar_observations做status分类，publish_calendar／parse_calendar同步处理完整受限VCALENDAR／VEVENT和source.close。candidate只做own domain projection，不要求async、通用cadence或完整RFC，也没有外部calendar写入。

## Part 5 current nested physical execution

PlanCatalog完整绑定真实P3 RevisionResult到action leaves：action interval和内容来自权威current segment，node的占位start／end不覆盖它。global UID、finite unique forest、one-agent-per-tree和venue lookup均是Given；P5不重做contradiction选择或patch replacement。

candidate递归保每层NodeAudit。先查child完整区间是否包含于parent，失败branch的全部descendants标blocked，即使某个leaf自己的区间仍在直接parent内；正常branch按children结果给complete／partial。action若cancelled或now不在 `[start,end)` 则inactive，不移动。active action的整个区间必须落在某一个venue opening，不能仅凭now开放就入场，也不能把多个开放段的外包区间当作连续开放。

随后看当前共享World的physical occupants。新进入目标venue需有capacity；已在该venue则stayed，不多占一席。accepted movement调用Given World.move真正更新位置，并记录Movement；新world沿children和roots声明DFS顺序传下去，不能每branch重置。离开旧venue立即释放occupancy，因此同agent后续移动可以让后面的peer入场。

最终返回完整nested reports、实际movements与final world。反转root顺序会改变谁先占用一席，这是声明的执行语义。这里是在单个simulated now下执行有限动作，没有未来reservation时间表、并发事务或空间常识学习。

## 这套题证明了什么，没证明什么

当前静态清点：45个Python文件、五测试、43assert、0raises、五分关锁和28个登记错误写法。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。P1完整inspection的当前完整性能组通过；5000memories、4000额外OR terms和0.035秒限值的本机测量范围见Part 1，不能推出通用墙钟上界。

这些行为合同检验候选人在有限typed域内完成跨层debug、独立状态snapshot、composite retrieval、来源资格与actual consumption、affected-only revision、calendar observation和nested temporal／physical execution的判断。P5复用P3权威修订结果；Given的codec、catalog、writer与state primitives不能另算候选人的独立实现。

这不证明无脚本社会涌现、believability、ToM、真实LLM／embedding效果、reflection逻辑蕴涵、论文复现、数据库crash atomicity、完整iCalendar RFC或外部投递，也不保证未来reservation可行或并发安全。任何后续有限本机workload结果都依赖环境，不能推出任意规模墙钟上界或SLA。60分钟分配尚未经过真人校准。
