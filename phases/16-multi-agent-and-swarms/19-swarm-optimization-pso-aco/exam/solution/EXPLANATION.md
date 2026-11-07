# 参考答案讲解：SwarmTune（16/19）

计时结束后再看。参考代码在本目录 `swarmtune/` 中；在作答副本可用 `python3 -m pytest --solution --all-parts` 核对参考模式。退出后关闭答案，去掉 `--solution` 重写。当前原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。练习命令本身不替代执行记录。

## 来源与本地合同

来源numeric PSO本已复制flat best vectors、clamp实际position、最大化并只评价changed candidate；本题P1是显式local regressions，不是修来源同样的错误。真实source evaluator原样保留，中心代入 `1-.08*(1+1)=.84`；printed optimum1不是oracle，也不采lecture实验作全局最大值或收敛证明。

来源ACO按task-type row轮盘赌，同步current-row decay再按inclusive quality gate沉积，没有延迟worker、retry、graph path、实际LLM或model训练。baseline与ACO共用RNG但噪声交错，不能假定paired outcomes。这里的allocated numeric job→deferred Outcome、完整checkpoint、typed observations和nested ant trails是显式本地适配。output仅DATA，未调用skill；论文、当代框架、cost／speedup数字未外部核验。

## Part 1 四个numeric primitives

`update_personal_best`把p_best指到当前mutable x后，一次合法后续movement会连带改best坐标，而stored fitness不变。测试先在(.72,.4)记录best，再移动到(.72+.2,.4+.2)的更差位置；正确 `best_report → score_reader` 才发现坐标／score不一致。修为strict improvement时 `list(particle.x)` 的flat值快照，不改consumer，不需要recursive deepcopy。

`step_particle`按惯性／认知／社会项更新velocity，再把x+v截在declared bounds内；不是把velocity限制到position区间。每particle两个实际RNG factors由Given scheduler产生，并在二维共用，不擅换成逐维draw或额外随机版本。

`update_global_best`保strict maximizing best-so-far，tie返回已有Best；不接受更差值或由打印强设fitness。current position、personal best、global best是不同记录，不能混作一个向量或分数。

`evaluate_changed_candidate`真实评价changed index的新coordinates，把结果写入对应current score cache，其余current scores保留。慢路径每次重评全population，属于真实evaluator重复工作；快路径不能省掉changed evaluation或拿旧score冒充结果。每轮仍需完整current_scores、population_mean、own best和global best，changed steps与final RNG／checkpoint／Allocation都保留。

Given ScoreEvaluator记录实际trace，功能guard要求至少initialization+updates的调用证据且每个changed coordinates／score出现；它没有exact线性上限，也不把内部冗余calls写进公共report伪装成相等。真正性能比较以完整job与whole report为界。

当前fixture为780个实际particles×4轮，完整OptimizationDesk.run和whole OptimizationReport equality在timer内，输入／独立expected在外。本机独占完整3slow3fast测得slow为1.58501537／1.48940483／1.48805696秒，fast为0.010484084／0.01240925／0.0110989581秒；限值0.16秒，双侧余量9.30035599／12.8936076，最慢业务1.58501537秒。原样参考五关通过，subprocess wall为0.283843917秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另重复评价实际未变粒子，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。

## Part 2 完整binary checkpoint

参考布局先存global best coordinates／fitness，再对每个declared particle依次存x、v、p_best、p_best_fit；metadata保checkpoint UID、iteration、bounds、full RNG、evaluator version、particle IDs，以及完整RouteTable rows／applied epochs、Allocation ledger、ordered pending Outcome。

load按同一布局重建每个独立typed字段，不由current x推断p_best，不丢source Allocation或arrival顺序，不把重复Outcome自行去重。重开后继续PSO需用当前Random state，不能用initial seed重来。Given binary64 codec保signed zero／subnormal bits，tagged scalar／tuple codec保完整RNG；candidate负责真正领域布局与关联。

CheckpointMembers只提供normal-process state.bin／metadata.json读写和close，不承诺双成员crash原子事务。测试实际先运行一个已分配numeric job，`outcome_from_report(report, uid, arrival, epoch, ...)`把actual report score clip到quality域并绑定该report的Allocation；这个constructor不选route或判gate。P2保存真实state／Outcome，P3重开消费它们，不是闲置前关调用。

## Part 3 三个独立ACO算法

### requested-row roulette

使用requested_row取得该task_type的stable snapshot row，按声明agent顺序计算累计weights；一次random()乘total，落在半开区间的agent胜出。zero weight没有长度，draw正好在边界进入后一个区间。finite positive total与unique声明由完整Given校验，candidate写实际roulette和RouteChoice字段，inference不改table。

### explicit-epoch decay

`apply_route_decay`对新epoch把每row每weight更新为 `max(floor, weight*(1-rho))`，保声明顺序并追加applied epoch；已处理epoch返回同语义table，不再乘一次。它是单独的完整table操作，不隐含在每次inference或feedback里。

### original-allocation verified feedback

Outcome先关联原Allocation，再检原route、verified、success和inclusive threshold；accepted才向原task_type／agent加reinforce×quality。所有accepted／rejected决策都保原outcome／allocation／task身份、arrival、epoch、amount和reason。unknown allocation／route不造新row，失败／未验证／低质不学习；当前正在推理的task不能取代delayed outcome归属。

完整Given conservatively要求请求row有finite positive total，潜在reinforce×quality及weight+amount可表示；即使后续gate会拒绝，也允许先拒超大输入。这只限定数值域，没有提前判acceptance。feedback自身不自动做event幂等去重，epoch replay保护属于独立decay。测试真实P1 report→bound Outcome→P2 close/reopen→P3三个操作，完整typed LearningDecision由candidate policy产生。

## Part 4 实际numeric／route／learning观察

candidate按Given observation_kind构造每条own fields。iteration同时保best_fitness、mean_fitness、best coordinates和full current_scores，后续iteration读后续report。route保actual task／type／agent／draw／total，没有learning amount。

learning投影实际P3 sealed decision的original Allocation／task／agent、arrival／epoch、quality、accepted或rejected status、actual amount／reason。amount不是quality；拒绝也保事件。Given提供classification／learning_status、同步NDJSON writer／parser／close，candidate不重新判断quality或实现另一套stream cadence。

## Part 5 nested ant-path certificates

GraphCatalog完整提供global edge／vertex lookup、finite unique forest／path／allocation intake、trail key和sealed epoch binding，输入的decision是真实修好P3的结果。候选人不复制quality gate，仍须自己验证path、计算credit并fold shared state。

每层先保before。按own path声明序，遇未applied epoch先对所有trails做一次decay／floor并记epoch，之后才审path；无论后续invalid或rejected，该epoch已经发生；即使新epoch的第一条就是rejected-learning path，完整before／after仍显示真实蒸发而没有credit。连续性从path.start逐edge核source与当前位置相等，每次成功保visited prefix并推进target；最终位置必须到destination。

仅valid path且actual decision.accepted时deposited amount。对matching task_type／destination的真实visited edges按visit次数加decision.amount；loop重复edge不去重，其他task／destination只受decay不获foreign credit。empty path仅start==destination才可valid，且没有edge获得credit。

接着以当前state依次处理children，再处理后续roots；不能每child重置outer state或每ant重复decay。ExpeditionAudit保own audits、ordered children和本层actual before／after，TrailReport保final state；input immutable snapshot不改。invalid path保prefix／reason，rejected-learning消费P3结果，不重判verification／threshold。

Graph intake还按所有声明path长度和sealed amount计算保守credit上界，要求max(weight,floor)+上界可表示；即使path之后失败，也可能先拒巨大输入。这是完整Given合法域，未提供path continuity、multiplicity、epoch或整树solver。

## 这套题证明了什么，没证明什么

当前静态清点：48个Python文件、五测试、39assert、3raises、五锁、26个登记错误写法。当前原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。780particles×4轮完整numeric replay、whole OptimizationReport equality与0.16秒限值的本机完整性能组通过，测量范围见Part 1，不构成通用墙钟上界。

这些行为合同检验候选人在有限可表示typed域内完成flat numeric调试、完整checkpoint续接、task-row roulette、显式epoch decay、original-allocation反馈、实际字段投影与nested path／trail状态fold的判断。P4/P5复用真实P3 sealed quality decisions；Given codec、classification、identity／numeric intake和资源driver不应另计候选人独立算法。

这不证明真实LMPSO prompt velocity、model-weight训练、全局最优／收敛、ACO收益、统计显著性、论文／speedup复现、后台异步worker、外部投递或distributed exactly-once。normal-process成员读回不保证crash事务。有限本机workload结果都依赖环境，不能推出任意规模墙钟上界或SLA。60分钟分配尚未经过真人校准。
