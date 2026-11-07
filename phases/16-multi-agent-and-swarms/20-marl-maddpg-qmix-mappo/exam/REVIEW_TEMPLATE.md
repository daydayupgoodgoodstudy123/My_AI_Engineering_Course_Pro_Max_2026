# 16/20 CTDEGrid 复盘

- 日期／第几次：
- 模式：独立计时／有人主持／关闭答案后的重做
- 开始／结束；是否按2分钟开场+58分钟编码：
- 实际Python版本、环境与工作副本：
- 看过的材料、澄清问题与帮助：
- 是否打开答案；哪些结果属于计时后：

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest次数 | H1/H2/H3 | 卡住的行为与证据 |
|---|---:|---|---|---|---|---|
| 1 local joint inspection | 12分 | | | | | |
| 2 binary rollout | 10分 | | | | | |
| 3 finite mixer | 16分 | | | | | |
| 4 joint CSV | 10分 | | | | | |
| 5 nested certificates | 10分 | | | | | |

## 按实际职责评分

每项写代码、输出或断言依据；未观察到写“未观察”。参考模式与计时后补完另记。

| 关 | 分项上限 | 实得 | 证据／尚缺行为 |
|---|---|---|---|
| 1（20） | canonical identity 5；local decision 5；collection 4；distance／full inspection 6 | | |
| 2（20） | snapshot序／replacement 6；双方own fields 7；joint state／typed reopen 7 | | |
| 3（25） | numeric formula 9；sufficient certificate 7；Cartesian value oracle 9 | | |
| 4（15） | actual identity／joint行 4；local fields 7；done／training state 4 | | |
| 5（20） | recursive values／children 7；exact path composition 7；certificate／findings 6 | | |
| 合计（100） | | | |

## 逐关回看

- Part 1：是否从正确q_lookup追到row／column producer？相同local input在hidden state／hint变化后决策是否稳定？双方distinct pellet reward、same-pellet tie、terminal absence是否都保留？empty-grid几何如何进入完整Q／joint report？
- Part 2：是否保存全部ordered／repeated transitions？双方observation／Q／action／collected／reward是否独立？before／after、done、policy与原step能否完整typed重开？save空snapshot是否真正替换？
- Part 3：hidden／output／state／ReLU公式哪里验证？充分certificate是否检查hidden与output、允许zero？oracle是否完整枚举、固定features、比value而非tuple？为何negative certificate可无actual gap？
- Part 4：为何joint step只有一行？字段是否归本条actual actor？terminal null、per-agent reward、before／after training state是否准确？原step是否与normalized feature分清？
- Part 5：每层own value／ordered children是否真实？repeated Q每个path是否保留？Fraction保护哪种下溢？true zero mask与negative tiny product如何区别？unknown path、constant无dependency、certificate失败限度如何表达？

## 证据与下一次练习

- 60分钟时已完成／未完成行为：
- 首个失败、根因、最小修改与回归依据：
- 问过的澄清问题／本应先问的问题：
- 能解释的职责边界（local／training、snapshot／learning、certificate／witness）：
- 残留临时代码／改测试／绕过consumer的位置：
- 计时后补完（不计入原成绩）：
- 关闭答案后仍不能独立实现的函数：
- 备份位置／重做目录：
- 下次只改一个习惯：

## 当前证明范围

当前45PY、五测试、42assert、2raises、五锁、28个登记错误写法。完整本地校准已通过：三个慢样本为[0.7627397500909865, 0.7642112921457738, 0.7809399999678135]秒，三个快样本为[0.005859417142346501, 0.005741541972383857, 0.005976958898827434]秒，慢侧／快侧余量为9.534247／13.384733。当前限值0.08秒；六份测量副本只把时间阈值断言换成elapsed打印，慢版另启用真实BFS，完整业务与其他四关全部功能检查通过。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。慢版不声称通过原时间阈值。

P1为192个实际requests×2actors×5candidate actions、size36；完整GridDesk.inspect与whole GridReport equality在timer内，fixture与独立expected在外。所有实际Q、动作、collector／reward、before／after、done与scripted fields均保留，局部测得余量受运行环境影响，不构成通用墙钟上界或SLA。

自行运行后另记命令、环境、功能结果与elapsed。有限测试不证明真实MARL训练、收敛、学习收益、完整符号单调性判定或通用墙钟SLA；60分钟真人分配未校准。

当前领域覆盖包括每个finite binary64 local Q值的完整archive往返、固定state下负bias与Q系数的区别、equal-value联合动作的首个maximum、terminal missing-action投影、按声明Q序的逐路径certificate，以及exact Fraction路径符号与binary64节点值的分离。
