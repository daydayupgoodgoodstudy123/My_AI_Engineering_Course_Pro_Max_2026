# 参考答案讲解：CTDEGrid（16/20）

计时结束后再看。参考代码在本目录 `ctdegrid/`；在作答副本可用 `python3 -m pytest --solution --all-parts` 核对参考模式。退出后关闭答案，去掉 `--solution` 重写。原样参考五关、完整性能组、独立行为复核与规定TEMP均有对应通过记录；正式检查已通过，记录见 verification.txt。命令本身不替代实际证据。

## 来源与本地合同

来源实际有两个pellet，不是讲义描述的one-pellet环境；没有碰撞额外费用或每agent必须收一个的约束。具名MADDPG／QMIX／MAPPO风格函数在执行时每步做相同集中式assignment，MAPPO直接调用MADDPG分支，没有Q表、numeric mixing network、critic更新、梯度或已学习policy。来源assignment最小化distance sum，episode makespan是另一目标；本题oracle比较固定状态的mixer value，不是环境最短完成步数。

本地服务明确适配scripted local Q、actual joint rewards、immutable execution／training records、binary snapshot、参数化mixer与nested audit。source Manhattan本已是算术，P1四缺陷是教学回归，不能归为来源同缺陷或真实策略训练收益。source讲解实验与外部当代框架／baseline说法没有在这里核验；output只作DATA读取，不调用skill。

## Part 1 四个local primitives

`encode_local_observation`应原样保agent UID、size、cell和target。row／column交换后，经 `local_actor → q_lookup` 两次外部调用，在正确的q_lookup处对非对称canonical key自然KeyError；修producer，不改正确table或捕异常伪装合法row。local_actor的动作选择另有hint依赖缺陷。

`local_actor`从lookup得到本actor Q row后，调用完整Given `local_argmax`，按声明序取first maximum，忽略central diagnostic hint。相同local observation／Q在other-agent state与hint变化时动作保持相同；这是执行依赖合同，允许training log另有central state。

`joint_collect`按actor序消费同一remaining pellets，两次实际collection都记入collected／rewards。不能首成功就break，也不能每次对original inventory重算而奖励同pellet两次；Given collect_one已提供单collector精确规则。terminal world保持空Q、None action、不动的state。

`candidate_distance`在无障碍正交方格上用两轴绝对差之和。慢路径对每个实际candidate action做真实BFS；每个距离构成实际ActionValue，整row参与actor选择、movement和collection，快路径仍保全部业务。这个等式不适用于有障碍的另一环境。

P1为192个实际requests×2actors×5candidate actions、size36；完整GridDesk.inspect与whole GridReport equality在timer内，fixture与独立expected在外。所有实际Q、动作、collector／reward、before／after、done与scripted fields均保留，局部测得余量受运行环境影响，不构成通用墙钟上界或SLA。

完整本地校准已通过：三个慢样本为[0.7627397500909865, 0.7642112921457738, 0.7809399999678135]秒，三个快样本为[0.005859417142346501, 0.005741541972383857, 0.005976958898827434]秒，慢侧／快侧余量为9.534247／13.384733。当前限值0.08秒；六份测量副本只把时间阈值断言换成elapsed打印，慢版另启用真实BFS，完整业务与其他四关全部功能检查通过。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。慢版不声称通过原时间阈值。

## Part 2 complete binary snapshot

`transition_record`保存UID、episode、原step、full before／after World、两份Observation、两份有序ActionValue、actions、collected、rewards、done与policy。`restore_transition`按相同布局重建typed records，不把首actor复制到第二actor，不把before代after，不由joint done推断丢失的local字段。

完整GridReport按声明序保存全部transitions，重复相等记录也保留，save空snapshot替换旧内容。完整Given是exact scalar／tuple binary codec与normal-process BinaryFile framing／read／write／close，不是whole domain serializer。binary64 signed zero由codec保真，candidate仍须传对reward字段；没有crash-atomic或distributed persistence承诺。

## Part 3 数值、充分证书与actual oracle

### numeric mixer

每hidden row计算bias + local Q weighted sum + fixed training-feature weighted sum，再按该row identity／ReLU激活。output为output bias + output-state项 + output weights乘全部hidden values。不同state项、activation和output weights都是真实参数，不用简单Q sum代替。

完整Given校验合法shape、有限有界参数与direct Q values，features为 `(float(size), step/(step+1))`。原step仍是任意非负整数并完整进archive／CSV；比较内features固定，不因枚举action改变。测试实际P1 inspection→P2 save／close／reopen→restored rows及features→P3算法，不是unused前关调用。

### sufficient structural certificate

对hidden input weights和output weights逐个检查负数，按声明序报告 `hidden[j][i]`／`output[j]`；zero允许，bias和state项在固定state下只是常数。identity／ReLU单调，所有这些weights非负给出充分certificate。

该条件不完整：例如2q-q包含negative weight但合成仍可单调，dead activation也可使实现值常量。失败只说明这个证书不成立，不证明actual nonmonotonicity或greedy gap。

### Cartesian value oracle

由每row first local maximum确定greedy tuple／Q values，同时完整枚举product of rows，用同一numeric mixer与固定features计算所有joint values。strict improvement保第一个best tuple；返回greedy／best各自value、best-greedy gap和组合数。zero weights或ties可让tuple不同却value同优，不能把tuple不等当failure。

## Part 4 每个joint turn的actual CSV

每条JointTransition一行，episode、原step、policy来自本条；两actor各自obs／Q／action／reward独立编码，done与full before／after training_state另列。terminal missing action写null，不造stay；per-agent reward不以joint sum替代。

完整Given提供cell JSON编码、CSVWriter和async publish／close流程，测试用csv.DictReader读取实际输出；candidate只实现领域row。training_state被明确允许用于training log，不能反过来作为P1 actor决策依据。这里不重考通用CSV escaping或stream cadence。

## Part 5 actual nested expression audit

完整ExpressionCatalog提供global Q lookup和finite unique-node tree intake，candidate递归求值与构造audit。QRef查实际value并产生单位dependency；Constant只有数值、无Q dependency；Sum保bias并对ordered child values加权；Relu保child audit并对自己的child value截0。所有中间层、ordered children和nested findings都保留，不能只给root数值。

对每个referenced Q保留每条代数路径的系数乘积。每跨一个Sum edge，用 `Fraction(edge.weight)` 乘child coefficient；重复Q经不同nodes出现仍保多项，按catalog声明Q顺序输出。系数是actual binary64值的精确Fraction，不是声称恢复原十进制文本；true zero中和路径，极小negative不会因float乘法下溢被误作零。

逐节点own value另按声明顺序用binary64计算。一个tiny expression的数值与exact path sign是不同证据，不能把下溢后的数字零当证书。ReLU不按当前一次输入的inactive状态消除negative dependency；当前充分条件要求每Q所有exact path products非负，偏保守但不会用抵消抹去negative path。

未知Q返回None value与完整context path，向上保findings／None；常量bias不冒充Q引用。输入来自真实P1→P2 reopen→P3 oracle选出的greedy local Q，nested Sum／Relu值与per-Q路径组合仍是P5 candidate职责；没有训练、shared occurrence expansion或shortname解析任务。

当前领域覆盖包括每个finite binary64 local Q值的完整archive往返、固定state下负bias与Q系数的区别、equal-value联合动作的首个maximum、terminal missing-action投影、按声明Q序的逐路径certificate，以及exact Fraction路径符号与binary64节点值的分离。

## 这套题证明了什么，没证明什么

当前45PY、五测试、42assert、2raises、五锁、28个登记错误写法。完整本地校准已通过：三个慢样本为[0.7627397500909865, 0.7642112921457738, 0.7809399999678135]秒，三个快样本为[0.005859417142346501, 0.005741541972383857, 0.005976958898827434]秒，慢侧／快侧余量为9.534247／13.384733。当前限值0.08秒；六份测量副本只把时间阈值断言换成elapsed打印，慢版另启用真实BFS，完整业务与其他四关全部功能检查通过。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。慢版不声称通过原时间阈值。

在这些测试实际通过后，可支持候选人在声明有限typed域内完成local identity／execution调试、实际joint collection、完整rollout reconstruction、fixed-state numeric mixing、充分结构证书、有限Cartesian value witness、actual CSV投影和nested exact-sign audit的判断。P3与P5是两个透明candidate certificate位置；完整Given codec、shape／identity intake、argmax及resource driver不另计为候选人独立算法。

这不证明MADDPG／QMIX／MAPPO训练、学习收益、收敛、真实decentralized learned-policy质量、benchmark优势、完整符号单调性判定、任意表达式或任意程序正确性。negative certificate failure不是actual greedy gap证据；empty-grid距离结论不外推障碍环境。normal-process archive不保证crash事务。任何后续有限本机结果都依赖环境，不推出任意规模墙钟上界或SLA；60分钟真人用时未校准。
