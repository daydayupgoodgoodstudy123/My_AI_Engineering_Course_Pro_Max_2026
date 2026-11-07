# 面试官手册：CTDEGrid（16/20）

候选人计时期间不要看。候选人使用README、`ctdegrid/` 与 `tests/`，合同以实际typed records、docstring和测试为准。这是原创练习评分，不是公司或官方认证标准。

## 开场（2分钟）

总计60分钟，编码58分钟：Part 1–5分别12、10、16、10、10分钟。请候选人边做边解释，随时澄清，可以查Python官方文档。逐关解除skip，之前的测试继续保留；记录实际行为与证据，不只数完成关数。

主持人记录解锁时间、首次完整结果、运行次数、问题和提示等级。卡住约4–5分钟后从H1开始，一次给一级；独立完成与提示后完成分开记。真人难度／时长尚未校准。

来源实际有两个pellet，没有碰撞额外费用或每人必须收一个的限制；三种具名style每步使用相同集中式assignment，MAPPO分支直接复用MADDPG分支。来源Manhattan本已是算术，本题坐标／hint／collection／BFS错误是本地教学回归。local Q、numeric mixer和nested certificate是明示适配，没有训练、收敛或benchmark收益证明。来源讲解实验与当代框架说法不是当前oracle。

## 澄清问题的标准答案

候选人问到时，用英文回答。

| 关 | 问题 | 标准回答 |
|---|---|---|
| 1 | grid有障碍或碰撞罚分吗？ | "No. It is an obstacle-free square with legal integer cells. Actors may share a cell; there is no collision penalty." |
| 1 | 一次只能收一个pellet吗？ | "No. Preserve both distinct collections in one joint transition. A shared pellet rewards only the first declared collector." |
| 1 | critic_hint是合法actor动作来源吗？ | "No. Choose the first maximum of that actor's local Q row. Changing hidden state or a diagnostic hint must not change an otherwise identical local decision." |
| 1 | terminal还要造stay／Q吗？ | "No. Initially terminal requests retain empty local Q rows and missing actions." |
| 2 | binary codec要自己实现吗？ | "No. Exact tagged scalar/tuple encoding and the normal-process file/close resource are complete Given. You own the full transition mapping and reconstruction." |
| 2 | 重复transition、central state要保吗？ | "Yes. Preserve declared order, repeated equal records, both local records and full before/after training state. Saving replaces the whole snapshot." |
| 3 | features会随选中的action改变吗？ | "No. Use fixed features for the entire comparison: float(size) and step divided by step plus one. Preserve the original integer step in storage and CSV." |
| 3 | 给了MixerSpec是否已给solver？ | "No. Parameters and bounded finite intake are supplied. Implement numeric mixing, the structural certificate and full Cartesian value comparison separately." |
| 3 | 负系数就证明greedy错吗？ | "No. It fails a sufficient certificate. An actual greedy gap requires the separate fixed-state Cartesian value oracle." |
| 3 | greedy和best action tuple必须一样吗？ | "No. Compare values. Ties and zero weights may produce different tuples with the same optimum value; retain the first declared maximum." |
| 4 | central training_state列算泄漏吗？ | "It is explicitly permitted in this training log. It must stay separate from the two local execution records and must not influence the actor." |
| 4 | 两actor动作需要两行吗？ | "No. One actual joint transition owns one row, with each actor's own observation, Q row, action and reward." |
| 5 | repeated QRef要去重吗？ | "No. Retain every algebraic path contribution in declared Q order. A constant bias has no Q dependency." |
| 5 | 极小negative product可按0处理吗？ | "No. Compose path coefficients as exact Fractions of the actual edge values. Only a true zero product is neutral; node values remain separate binary64 calculations." |
| 5 | inactive ReLU能证明certificate通过吗？ | "No. This is a conservative path-sign certificate. Dead activations or cancellation may have no actual gap while failing it." |
| 全部 | 是真正MADDPG／QMIX／MAPPO训练吗？ | "No. This is finite scripted local execution and declared value decomposition, with no gradient updates, learned policy or convergence claim." |

## 每关：主要坑、观察、提示、追问

### Part 1 local joint inspection（12分钟，20分）

四层按真实调用暴露：

1. `encode_local_observation`交换本actor row／column。非对称raw key通过 `local_actor → q_lookup` 两次外部调用进入正确dict lookup，自然KeyError。应修producer的canonical identity，不改consumer、table或吞异常。
2. `local_actor`虽做真实lookup，却返回central diagnostic hint。应使用本条row的first maximum；counterfactual other-agent状态／hint变化不能改变相同local observation与Q values的决策。
3. `joint_collect`在首个成功collector后break，漏第二个不同pellet。让双方依次消费同一remaining inventory；完整Given的collect_one已经处理同pellet按声明序只奖励一次。
4. `candidate_distance`对每个实际candidate action做真实BFS。声明世界无障碍，两个轴的Manhattan距离即精确答案。每个距离都进入实际Q row、actor选择和joint transition，不能删Q rows或硬编码动作来满足时间。

观察：是否从正确lookup回查编码；是否区分central training与local decision；是否保双方reward和完整report。Given提供legal binding、clipped move、local_argmax、collect_one、完整GridDesk和独立expected，不提供这四修复。

提示：

- H1："Which key did the producer change before the correct local lookup?"
- H2："Keep local identity and local action selection separate from central hints; inspect both collectors and the declared geometry."
- H3："Preserve row and column, use the supplied first-max local argmax, process both collectors against the remaining inventory, and compute exact two-axis distance on the empty grid."

追问：

- "Why does changing the hint make a useful counterfactual?"（本local inputs不变，可直接观察决策是否依赖隐藏central信息。）
- "Why can't this distance shortcut solve an obstacle world?"（该等式依赖当前无障碍域；绕障路径属于另一合同。）
- "What must remain inside the full inspection?"（所有request的双方五动作Q、实际action、collection／reward和joint state。）

### Part 2 complete binary rollout（10分钟，20分）

主要坑：

- 全部ordered transitions逐条保存，包含UID／episode／原step与重复相等记录；save是完整snapshot replacement，不是追加旧episode或只存末条。
- 每个actor的agent UID／size／cell／target、完整ActionValue序列、action／collected／reward独立，不能把actor0字段复制成actor1。
- full before／after World、joint done和scripted-policy label需要重建成typed records；terminal None actions与空Q rows不能由central state存在推断为实际动作。

观察：candidate负责 `transition_record` 与 `restore_transition` 的领域字段／关联。完整Given是exact tagged scalar／tuple binary codec和normal-process BinaryFile读写／close；signed zero是codec集成护栏，不要求另写精度算法或crash事务。P2直接保存已绑定local records，候选人不需实现global-to-local过滤。

提示：

- H1："What distinguishes this complete snapshot from just the last joint state?"
- H2："Map both actors independently and retain ordered transitions, before/after worlds and terminal absence."
- H3："Serialize all declared fields into exact scalar/tuple records, then reconstruct World, Observation, ActionValue and JointTransition in the same order through the supplied file resource."

追问：

- "Why retain repeated equal transitions?"（保存声明snapshot，不自行推断去重语义。）
- "Does an archived scripted action become a trained policy?"（没有，记录是行为证据，没有参数学习。）

### Part 3 三个finite mixer算法（16分钟，25分）

三个独立TODO：

1. `mix_joint_value`逐hidden row计算local-Q affine项、hidden bias和固定training-feature项，按该row的identity／ReLU激活，再加output weights、output bias及output state项。不能跳ReLU、漏state项或把公式换为简单sum。
2. `validate_monotonicity`扫描hidden和output weights，负数按声明顺序报告精确位置；zero合法，bias／state项不因正负破坏固定state下对Q的充分证书。失败不自动产生actual counterexample。
3. `joint_action_oracle`用P1使用的完整Given local_argmax选greedy，同时枚举全部Cartesian组合，以同一features调用实际mixer。保greedy／best tuple与value、best-greedy gap及组合数，strict improvement保首个maximum；不能只算greedy或用tuple不等当gap。

真实整合为P1 GridDesk→P2 save／close／reopen→restored Q rows／training features→三个算法。features是 `(float(size), step/(step+1))`；任意原非负整数step仍原样保留。完整Given只给shape／bounded finite参数与Q校验、training features和first-max local_argmax，不给numeric mix／certificate／oracle。

观察：能否区分architecture certificate与actual value witness；是否覆盖negative output、cancellation、zero weights／ties和hidden ReLU。非法nan由Given拒绝，是集成guard，不扩成第四主算法。

提示：

- H1："Are you computing a value, certifying a sufficient condition, or finding an actual value witness?"
- H2："Keep the state fixed, evaluate every declared affine and activation stage, then compare the complete joint action product by value."
- H3："Implement the hidden/output formula; report negative hidden and output locations with zero allowed; enumerate product(*rows) and retain the first maximum plus the actual greedy value gap."

追问：

- "Why can 2q-q fail the certificate without a greedy gap?"（逐系数充分条件保守，代数抵消后仍可能单调。）
- "Why are fixed state coefficients acceptable?"（同一比较中不依赖所选actions，才是在同一joint-value函数上比较。）
- "Why can different tuples both be optimal?"（zero weights或equal values使argmax不唯一，目标是value。）

### Part 4 actual joint-transition CSV（10分钟，15分）

主要坑：

- 每条实际joint transition一行，episode、原step与policy来自本条对象；不能按两个actor把step翻倍或把归一化feature写进step。
- obs0／q0／action0／reward0与obs1／q1／action1／reward1分别取own typed字段，不复用首actor或用joint reward冒个体reward。
- done与明确允许的training_state保本条before／after，terminal action保持null；local execution信息与central training log有清楚列边界。

观察：完整Given提供cell codec、CSVWriter及async publication／source-close／writer-close；candidate只写真实领域row。通用escaping／cadence不是主要坑；测试使用csv.DictReader检查实际输出。

提示：

- H1："Which joint transition and actor own this column?"
- H2："Keep one row per joint turn, two independent local field groups and the explicit central training column."
- H3："Project episode, original step and policy, encode each actor's actual fields with cell, then retain done and actual before/after training state, including terminal null actions."

追问：

- "Why is central state allowed here but not in the actor's decision?"（training evidence与execution input职责不同，前者合同明确允许。）
- "Why not log only total reward?"（会丢失实际collector归因，不能检查双方local行为。）

### Part 5 nested numeric path certificates（10分钟，20分）

主要坑：

- 真正递归QRef／Constant／Sum／Relu，保每层own value、ordered children和所有findings；Sum bias是常量，ReLU读自己child value，不能只给root最终结果。
- 按每个referenced Q收集所有root-to-leaf系数乘积，重复Q通过不同node产生独立代数贡献，按catalog Q声明序报告；bias没有Q dependency。
- 系数从实际binary64 edge values转Fraction再精确相乘，保符号与true zero mask；极小negative不能因float乘积下溢为0而获certified。逐节点value仍按声明顺序算binary64，不把两种算术合同混为一个。
- 每Q所有路径乘积非负才给充分证书；unknown Q返回None value并保完整nested path。cancellation／dead ReLU可能失败但没有实际greedy gap，不重用negative flag伪造gap。

观察：actual P1→P2 reopen→P3 joint oracle的greedy actions确实选择P5输入Q values。Given提供ExpressionCatalog的global lookup与finite unique-node tree intake，不含recursive evaluation、path composition或证书solver。这里没有shared occurrence／shortname题。

提示：

- H1："Which intermediate node and algebraic path produced this value or coefficient?"
- H2："Keep every repeated Q contribution, separate node values from exact path signs, and propagate nested findings."
- H3："Recursively build children and own binary64 value; multiply each dependency coefficient by Fraction(edge.weight), retain all paths in declared Q order, and certify only when every exact product is nonnegative."

追问：

- "Why not sum all coefficients before certifying?"（当前是每路径充分条件，抵消不抹去negative path证据。）
- "Why can an inactive ReLU still fail this certificate?"（证书不利用当前局部斜率证明全域，不把一次value当全局证明。）
- "What does exact Fraction protect here?"（actual float coefficient的乘积符号不被中间下溢误作true zero；不承诺原十进制文本精度。）

## 记录与评分（100分）

每项记录代码位置、实际行为或断言依据；未观察到写“未观察”。提示、沟通和用时另记，不由参考代码推定候选人完成。

| 关 | 评分项 | 分值 | 实得／证据 |
|---|---|---:|---|
| 1 | canonical local identity与正确lookup | 5 | |
| 1 | local Q argmax及hint counterfactual independence | 5 | |
| 1 | 双方collection／reward及same-pellet语义 | 4 | |
| 1 | exact empty-grid distance与完整inspection | 6 | |
| 2 | 全snapshot序／重复／replacement | 6 | |
| 2 | 双方own typed observation／Q／action／reward | 7 | |
| 2 | before／after、done／policy与close／reopen重建 | 7 | |
| 3 | 完整数值hidden／activation／state／output公式 | 9 | |
| 3 | 充分certificate与negative位置／zero语义 | 7 | |
| 3 | 全Cartesian oracle／tie／actual value gap | 9 | |
| 4 | own episode／原step／policy与joint行 | 4 | |
| 4 | 双方独立local fields与terminal absence | 7 | |
| 4 | own done与actual training-state列 | 4 | |
| 5 | recursive values／bias／activation／child reports | 7 | |
| 5 | repeated Q exact Fraction path composition／zero | 7 | |
| 5 | per-Q充分certificate／unknown nested findings | 6 | |
| 合计 | Part 1/2/3/4/5 = 20/20/25/15/20 | 100 | |

## 当前验证边界

当前45PY、五测试、42assert、2raises、五锁、28个登记错误写法。完整本地校准已通过：三个慢样本为[0.7627397500909865, 0.7642112921457738, 0.7809399999678135]秒，三个快样本为[0.005859417142346501, 0.005741541972383857, 0.005976958898827434]秒，慢侧／快侧余量为9.534247／13.384733。当前限值0.08秒；六份测量副本只把时间阈值断言换成elapsed打印，慢版另启用真实BFS，完整业务与其他四关全部功能检查通过。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。慢版不声称通过原时间阈值。

P1为192个实际requests×2actors×5candidate actions、size36；完整GridDesk.inspect与whole GridReport equality在timer内，fixture与独立expected在外。所有实际Q、动作、collector／reward、before／after、done与scripted fields均保留，局部测得余量受运行环境影响，不构成通用墙钟上界或SLA。

P3和P5是两个candidate certificate位置，按各自实际算法分别评分；完整Given codec／lookup／shape／driver不另计独立算法。60分钟真人用时尚未校准。

当前领域覆盖包括每个finite binary64 local Q值的完整archive往返、固定state下负bias与Q系数的区别、equal-value联合动作的首个maximum、terminal missing-action投影、按声明Q序的逐路径certificate，以及exact Fraction路径符号与binary64节点值的分离。
