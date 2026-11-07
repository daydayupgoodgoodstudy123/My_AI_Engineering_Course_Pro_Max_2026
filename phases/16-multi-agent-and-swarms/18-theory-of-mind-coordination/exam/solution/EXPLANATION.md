# 参考答案讲解：MindTrace（16/18）

计时结束后再看。参考代码在本目录 `mindtrace/` 中；在作答副本可用 `python3 -m pytest --solution --all-parts` 核对参考模式。退出后关闭答案，去掉 `--solution` 重写。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。练习命令本身不是执行证据。

## 来源与本地适配

来源Agent只有flat(other,box)观察流水，目标选择根据最近记录与sorted actual available；ToM组还被注入j modulo boxes的preference prime。它没有docs描述的own_beliefs／other_models、partial visibility或高阶context，也没有真实LLM。prime不能当作从行为推断心智的证据，打印Takeaways与lecture历史实验不是本题oracle。

本题明确适配为typed partial-visible observations、独立belief版本、subject-prior／action解释、false-belief prediction、actual own choice、SQLite、JSON Patch和bounded epistemic graph。来源每chooser排序及同轮先commit后collection提供control动机；其他完整状态与visibility是本地显式合同。output artifact仅作DATA，不调用其中skill；论文、框架与当代产品结论未外部核验，不采用为本题能力证明。

## Part 1 写入、可见性与control库存

第一个KeyError在正确consumer `read_subject_record`。`append_observation`把observer／subject反接，`ReplayDesk.run`经 `observation_view`读取所请求完整三元key时找不到。修writer的字段顺序，保UID／value／turn／ordinal／kind；不要改latest index或用默认值掩盖错误。

`deliver_visible_event`只向显式witness投递，并按population声明顺序返回；不在visible_to的人保原观察，即使它与actual world不一致。current-time event admission和latest完整key资源是Given。completion只撤active intentions，不删historical observations或independent beliefs。

`available_view`为完整(world UID,generation)构造一次sorted immutable actual boxes，再复用给同一joint turn的所有control chooser。合法域保证一个key只对应一份immutable inventory；领取后新generation或另一个world另建view。私有ToM exclusions不属于共享canonical view。

完整Given control先让所有未完成agent基于同一original inventory按声明顺序rng.choice，再按first claimant领取，保exact random_state、duplicates、taken与新World。重用排序不能改变候选顺序或RNG消费，不能提前领取使后续chooser看到另一份库存。空actual inventory不draw、不造collection或generation进展。

性能fixture含800个实际agents、6000个真实可选token，均为合成本地输入。完整ReplayDesk.run和whole ReplayReport equality在timer内，保原request、visibility／history、active targets、canonical view、全部choices／settlement／completed、新world和exact RNG；独立expected与输入在外。本机独占完整3slow3fast测得slow为0.496627083／0.418092667／0.421194秒，fast为0.00152341696／0.00149420812／0.00150162494秒；限值0.04秒，双侧余量10.4523167／26.2567644，最慢业务0.496627083秒。原样参考五关通过，subprocess wall为0.195406417秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另重复实际同generation库存排序，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。

## Part 2 independent history SQLite snapshot

BeliefArchive分别建模ordered observation rows与ordered BeliefVersion rows。每row保自己的UID、完整observer／subject／proposition key、value、turn／ordinal；observation另保kind，belief version另保source_uid。同key／同value可出现多次，声明顺序不等于clock排序，不能只存latest。

snapshot header保存UID、population身份／name／collected和subject priors；已完成与未完成agent各自保留准确状态，与独立历史共同重开。believed value是typed输入，不由observed truth或world推断；archive根本没有world oracle参数。save完整替换旧snapshot，close／reopen恢复全部独立记录及关联。

Given codec完整处理tuple identity、exact int／Decimal、False／None等scalar树和key编码，SnapshotDB完整提供schema、事务、ordered resources与close。candidate仍真正构造领域rows／header并重建typed snapshot；不是只调用whole-snapshot serializer。这里不承诺分布式exactly-once或任意外部API原子性。

## Part 3 三个真实算法与两种候选域

### subject action interpretation

`build_other_models`逐个从该subject prior的believed_available和preference开始，使用Given `subject_actions`绑定当前observer／subject／now下的chronological action evidence。合法action是approach-target字符串，其他fact保历史而不解释成approach。

每个actual target若不在perceived candidates则追加；把它移到preference首位，保其余顺序。更新source IDs与last_seen_turn，并由snapshot supplied completion决定active。这样真实观察改变模型，却不会把旧alternatives全部清空；Given binder不提前做这种belief解释。

### perceived-domain prediction

`predict_subject_target`没有World参数，只在该subject believed_available内选择首个有效preference，若无匹配则同subject首候选。inactive或perceived-empty交Given constructor产no-target。

例如subject相信old／phantom，再被观察到approach ghost，其预测可为ghost，即使actual库存只有blue／green。与actual world求交会用oracle偷偷修正subject false belief，改变题意。该预测忠实于声明模型，不代表真实读心或准确率保证。

### own actual choice

`choose_own_target`拿actual AvailableView，排除其他Prediction中非None目标，剩余按canonical顺序一次rng.choice；全部被排除则回同一actual boxes，空actual view直接None且零draw。subject perceived targets不能变成own可用库存，额外probe或先draw再判断也会改RNG合同。

测试确实将P1真实visible observations交P2 save／close／reopen，再调用三个P3算法。model snapshot保留原始control决定前population／completion语义，own选择在同original actual view上展示alternative policy；没有从control结算后的已领取库存继续行动，也没有配对收益实验。complete Given只提供action绑定、prior validation与typed Prediction构造。

## Part 4 actual ordered JSON Patch

Given `model_deltas`只把真实P3 Prediction转成typed changes，不解释subject或计算target。candidate对每个admitted delta亲自构造op／path，replace再加本条encoded value；remove不带value。三项就是实际JSON Patch领域字段，不需要虚构额外业务包装。

保留所有操作的声明顺序，重复path也不合并／排序，不能借首条path或写死值。empty batch发布完整空document。observer／time admission、explicit operation classifier、完整logical path与JSON Pointer escaping、scalar codec、同步publisher／parser和source.close都是完整Given；False／null／remove／escaped IDs是其集成护栏，不是另一套candidate privacy或unknown算法。

## Part 5 bounded current-context chain

`graph_from_predictions`只把实际P3 Prediction装配进一阶nodes，公开声明的额外higher-order nodes再给出context-specific beliefs。Given EpistemicGraph提供node／edge binding、query bound validation和known／unknown结果构造，没有完整chain walker。

candidate从query.root开始，对每个requested subject执行 `one_hop(current, subject)`，更新current并追加contexts。必须从刚到的model找下一步，不能一直从root取，也不能只走首阶。最后只查实际final context，报告完整path与requested／traversed order。

同agent在不同context可有不同belief。显式cycle允许按有限requested chain重复走；max_order和subject list给出界，不该用global visited-agent／node集合提前截断。缺link时在实际已走到的context调用Given missing_answer，不回root或world；空chain读root自身。

known False和known None由完整Given answer_for区别于缺link／proposition的unknown，candidate只正确接入结果。这里没有UNKNOWN→negative的独立主考，也没有真实认知递归或无限模型求解。

## 这套题证明了什么，没证明什么

当前静态清点：48个Python文件、五测试、38assert、0raises、五分关锁、26个登记错误写法。当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。800agents×6000实际tokens的完整ReplayDesk.run、whole ReplayReport equality与0.04秒限值的本机完整性能组通过，测量范围见Part 1，不构成通用墙钟上界。

这些行为合同检验候选人在有限typed域内完成writer／visibility调试、独立历史snapshot、subject action解释、perceived预测／actual选择、有序delta投影和bounded current-context解释的判断。Given完整key／codec／classifier／one-hop／answer资源及constructor-only Prediction adapters不能另算candidate独立solver。

这不证明真实ToM、mind reading、无脚本涌现、higher-order synergy、LLM能力、alternative policy收益、论文复现、外部RFC投递或文件保密，也不建立分布式exactly-once。有限本机workload结果都依赖环境，不能推出任意规模墙钟上界或SLA。60分钟分配尚未经过真人校准。
