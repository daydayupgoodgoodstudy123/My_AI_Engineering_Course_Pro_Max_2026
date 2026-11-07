# 面试官手册：MindTrace（16/18）

候选人计时期间不要看。候选人使用README、`mindtrace/`和`tests/`；以实际typed records、docstring和测试为合同。这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

总时长60分钟，编码58分钟：Part 1–5分别12、10、16、10、10分钟。请候选人边做边解释，随时澄清，可以查Python官方文档。逐关解除skip，之前的测试继续保留，记录具体行为而不只数完成关数。

主持人记录解锁时间、首个完整结果、运行次数、问题与提示等级。卡住约4–5分钟后从H1开始，一次给一级，不代写代码。独立完成和提示后完成分别记。真人时间与难度尚未校准。

本题是有限typed replay。来源用flat observations、随机选择和preference prime模拟token协调，没有真实LLM、partial visibility、subject belief solver或高阶context解释器。这里的显式扩展不能当作真实ToM／synergy或统计收益证据；来源打印和论文／行业叙述也不是本题oracle。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | 完整belief key是什么？ | "Observer, subject and proposition, in that order. The latest index and read consumer are complete Given." |
| 1 | visible_to顺序决定投递顺序吗？ | "No. Deliver only to declared witnesses, in population order. Nonwitnesses keep their previous evidence." |
| 1 | completion是否删历史？ | "No. Withdraw completed active intentions only. Observation and belief history remains independent evidence." |
| 1 | cache的合法身份是什么？ | "The full World UID and generation identify one immutable inventory. All simultaneous control choices use that unchanged canonical view before collection." |
| 2 | 存latest还是全部版本？ | "Store every ordered observation and independent believed version, with its own full key, clock, ordinal and source. No world-truth oracle is passed to the archive." |
| 2 | exact codec／SQL事务要自己写吗？ | "No. Tagged scalar and key codecs, tables, transactions, ordered resources and close are complete Given. You own the domain rows and snapshot associations." |
| 3 | subject observed target不在真实world怎么办？ | "Keep its perceived domain. Subject prediction has no world argument and may consistently predict a false belief." |
| 3 | 其他fact会被当作approach吗？ | "No. Action evidence is declared approach-target string data; other fact kinds remain historical records. The supplied binder selects the matching observer, subject and time." |
| 3 | action如何更新prior？ | "Preserve perceived alternatives. Add the observed target if absent and move it to the front of that subject's preference in actual action time order." |
| 3 | own排除后为空怎么办？ | "Choose from the same real inventory as fallback. With no actual boxes, return no choice and consume no random draw." |
| 3 | 这是control结算后的继续执行吗？ | "No. The model snapshot retains original pre-control state. This is an alternative policy on the same original actual view, with no measured improvement claim." |
| 4 | 同path重复更新能合并吗？ | "No. Preserve every admitted operation and declaration order. Use that delta's own operation, supplied path and own value." |
| 4 | null与remove谁来区分？ | "The explicit operation classifier is Given. A replace has its actual value, including null; a remove omits the value field." |
| 5 | 每次从root找subject吗？ | "No. Each edge starts from the current model context reached by the previous subject." |
| 5 | agent重复或cycle怎么办？ | "Follow the finite requested chain. The same agent may have different beliefs in different contexts; declared bounded cycles may revisit nodes." |
| 5 | 空chain或缺link怎么办？ | "An empty chain reads the root. On a missing link, stop at the actual traversed context and use the supplied unknown constructor, without root or world fallback." |
| 全部 | known False／None与unknown如何处理？ | "Complete Given answer constructors distinguish known values from absence. This is an integration boundary, not another negative-belief solver." |

## 每关：主要坑、观察、提示、追问

### Part 1 可见观察与joint control（12分钟，20分）

四层按实际调用暴露：

1. `append_observation`把observer和subject接反，写入错误完整key。正确 `ReplayDesk.run → observation_view → read_subject_record` 在producer之外两次调用处按要求读取，出现自然KeyError。修writer，不改consumer／latest index或塞默认值。
2. `deliver_visible_event`把partial-visible event广播全人口。只向visible_to里的witness投递，并保population顺序；未见者保旧观察／错误belief，不能用world truth补齐。
3. `withdraw_completed_target`保留已完成者的active targets。只撤active intentions，不删除历史；完整completion和control settlement由Given调用链处理。
4. 每个simultaneous chooser重复sort未变库存。`available_view`按完整World UID／generation复用canonical immutable inventory；私有预测排除不能污染共享view，领取后新generation另建。

观察：是否从正确key读取回查writer；是否分开visibility、active intent和history；是否保同一原始world上完全相同的RNG消费与first-claim settlement。一个key不可对应两份不同available；不要求为违反immutable generation合同的输入设计通用cache恢复。

完整Given提供typed event／current admission、full-key latest index、自然consumer、实际ReplayDesk与独立expected。P1不提前解释subject action或预测目标。

提示：

- H1："Which writer first disagrees with the complete key requested by this evidence consumer?"
- H2："Separate observer binding, explicit witnesses, completed active intentions and the unchanged joint-turn inventory."
- H3："Write observer then subject, filter witnesses in population order, remove completed intentions only, and cache the canonical sorted inventory by both World UID and generation."

追问：

- "Why preserve unseen prior evidence even if it is wrong?"（可见性模型允许belief与actual world不同，不能悄悄纠正。）
- "Why not share a ToM-filtered inventory?"（排除项属于own policy；control共享的是实际完整候选域。）
- "What must match after sorting reuse?"（完整view、choices、RNG state、duplicates、settlement和新world，不只最后数量。）

### Part 2 独立历史SQLite snapshot（10分钟，20分）

主要坑：

- observations保全部声明rows，同key／同value也不合并为latest；turn排序不能代替声明顺序。
- BeliefVersion是独立believed value，保UID、完整key、turn／ordinal和source_uid。archive没有world oracle，不能用当前观察或truth placeholder覆盖belief。
- header保snapshot UID、declared population与subject priors；display name可重复，identity／关联不能串。complete replacement要清掉旧rows，close后真实重开。

观察：是否自己建模domain rows与重建typed records；是否保持observation history和independent belief versions不同职责。exact tagged scalar／key codec、SQLite schema／transaction／ordered resources和close完整Given；giant integer、tuple／Decimal、False／None是依赖护栏，不另立generic precision或presence主坑。

提示：

- H1："What independent information disappears if each key keeps only one latest value?"
- H2："Keep every observation and believed version with its own declaration order, identity, clock and source."
- H3："Build full header and two ordered domain row collections, use supplied codecs and SnapshotDB, then reconstruct the same complete snapshot after reopening."

追问：

- "Why can't observations replace believed versions?"（观察与被归属的belief可以不一致，版本和来源各自有意义。）
- "What does a local SQLite transaction establish here?"（这份snapshot的本地replace／reopen，不是分布式exactly-once或任意API事务。）

### Part 3 subject解释／预测与own choice（16分钟，25分）

三个真实candidate算法：

1. `build_other_models`从每个subject自己的prior出发，按Given绑定的实际visible action时间顺序解释approach target：加入perceived candidates、移到preference首位，保旧替代项、实际source IDs与last_seen_turn；completion决定active，不重新广播或撤回。
2. `predict_subject_target`只在该subject perceived domain内找首个有效preference，否则回同subject首候选；inactive或perceived-empty为typed no-target。没有world参数，ghost可被预测，不能与actual库存求交来“纠正”。
3. `choose_own_target`从actual view排除其他预测的非None targets，有剩余则按原顺序一次rng.choice；全被排除回同actual inventory，actual为空返回None且不draw。不用subject false-belief域作own fallback。

测试真的P1可见观测→P2 save／close／reopen→P3解释／预测。snapshot和completion语义保留original control决定前状态，own choice在同original actual view上展示alternative policy；没有对control settled world继续领取，也没有收益度量。

观察：是否始终分清subject perceived与own actual；是否只解释合法approach-target action、保fact历史；是否保chronological evidence与exact RNG。Given action binder／prior validation／typed Prediction constructor不提供三个solver。

提示：

- H1："Whose candidate domain is authoritative for this decision?"
- H2："Interpret the subject's visible actions without deleting its perceived alternatives, then keep own choice inside the actual inventory."
- H3："Move each observed target to that subject's preference front; predict within its believed candidates; exclude predicted targets from actual boxes and fall back to the same actual boxes with exactly one choice."

追问：

- "Can a wrong prediction still satisfy this contract?"（能；它可忠实表达subject false belief，不是world oracle。）
- "Why is this not evidence of ToM payoff?"（有限声明模型和替代动作示例，没有paired policy outcome或统计检验。）
- "What would reusing control completed winners do?"（把同一original-world替代policy误当control之后状态，改变subject active语义。）

### Part 4 ordered JSON Patch字段（10分钟，15分）

主要坑：

- candidate实际逐条构造op／path／value，不能把batch包装当operation；每条读自己的delta，不能复用首条path或写死value。
- 所有admitted operations保声明先后，重复path也保留，不能按path排序或合并最后一条。
- 使用Given explicit op：replace保本条encoded value，remove无value字段。empty document是合法完整输出，外层publisher保留它。

观察：实际P3 Prediction经Given model_deltas只做数据装配，再进入candidate projection。observer／time admission、complete logical key path／JSON Pointer escape、op分类、scalar codec、同步publisher／parser／close全部完整Given；不重考visibility、null缺失判断或escaping算法。三个domain字段就是实际JSON Patch职责，不虚增包装字段。

提示：

- H1："Which actual delta owns each operation field?"
- H2："Preserve all admitted operations in order, even when their paths repeat."
- H3："For each admitted delta build op and its supplied logical path; add its encoded value only for replace, then append the operation without collapsing paths."

追问：

- "Why can two replacements followed by removal matter?"（有序change evidence不能等同只保final state。）
- "What does model_deltas actually compute?"（只绑定真实Prediction输出，不解释subject或求target。）

### Part 5 bounded current-context解释器（10分钟，20分）

主要坑：

- 按requested subject chain逐层更新current node，从刚到的context找下一条edge；不能每步重回root或只走首阶。
- 同agent在不同context可持不同belief，保完整context path、requested／traversed order。读取最终实际context，不借world或首阶答案。
- 显式cycle合法，有限subject chain和max_order给出界。重复agent／node不意味着立即停止；缺link只停在实际已走到的context，空chain读root。

观察：是否真的消费P3预测进入Given构建的一阶graph，再处理公开声明的高阶nodes；是否每次one-hop更新current并记录path。Given提供global UID／edge binding、finite query validation和exact answer／missing constructors，known False／known None只作集成护栏，不列第三UNKNOWN→negative主算法。

提示：

- H1："Which model context owns the next subject edge?"
- H2："Carry the reached context forward and retain every requested finite step, including revisits."
- H3："Validate the bounded query, start at root, follow one_hop(current, subject), append reached nodes, and use the supplied final or missing answer constructor at that actual path."

追问：

- "Why is a global visited-agent set wrong?"（名字相同可处于不同context；有限请求可有合法循环。）
- "What limits traversal here?"（声明subject chain长度及Given max_order，不是无界递归。）
- "Does graph_from_predictions provide a high-order solver?"（只将实际P3输出装配成一阶nodes，不走chain或预测。）

## 记录与评分（100分）

每项写实际代码、行为或断言证据；未观察到写“未观察”。提示、沟通和用时另记，不从参考实现推定候选人能力。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | writer完整observer／subject evidence接线 | 6 | |
| 1 | declared witnesses与population顺序 | 4 | |
| 1 | completed active撤回、历史保留 | 4 | |
| 1 | canonical generation view复用与whole control保真 | 6 | |
| 2 | complete ordered observation rows | 6 | |
| 2 | independent belief versions／keys／sources | 8 | |
| 2 | header／priors关联、声明顺序、replacement／reopen | 6 | |
| 3 | subject action解释、prior保留与active／source报告 | 10 | |
| 3 | perceived-domain preference prediction | 7 | |
| 3 | own actual exclusion／fallback与exact RNG | 8 | |
| 4 | 所有admitted operations及重复path顺序 | 5 | |
| 4 | own op／path／encoded value与operation-specific字段 | 7 | |
| 4 | actual Prediction整合与Given接口正确使用 | 3 | |
| 5 | successive current-context traversal | 8 | |
| 5 | final context与完整path／order报告 | 5 | |
| 5 | finite requested cycles／重复context | 4 | |
| 5 | empty／missing query流程与Given结果集成 | 3 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

静态48PY、五测试、38assert、0raises、五锁、26个登记错误写法。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。

P1为800个合成本地agents×6000个实际token候选，完整ReplayDesk.run及whole ReplayReport equality在timer内，输入／独立expected在外；0.04秒的当前完整性能组通过。每个choice、exact RNG、actual collection和新库存都保留，不能把登记清单或source打印当实测。60分钟真人分配同样未校准。

本机独占完整3slow3fast测得slow为0.496627083／0.418092667／0.421194秒，fast为0.00152341696／0.00149420812／0.00150162494秒；限值0.04秒，双侧余量10.4523167／26.2567644，最慢业务0.496627083秒。原样参考五关通过，subprocess wall为0.195406417秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另重复实际同generation库存排序，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
