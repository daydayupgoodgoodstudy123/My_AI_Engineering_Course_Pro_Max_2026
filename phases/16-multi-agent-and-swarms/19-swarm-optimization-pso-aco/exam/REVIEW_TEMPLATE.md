# 16/19 SwarmTune 复盘

- 日期／第几次：
- 模式：独立计时／有人主持／关闭答案后的重做
- 开始／结束时间；是否按2分钟开场+58分钟编码：
- 实际Python版本、环境与工作副本：
- 看过的材料、澄清问题与帮助：
- 是否打开答案；哪些结果属于计时后：

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest次数 | H1/H2/H3 | 卡住的行为与证据 |
|---|---:|---|---|---|---|---|
| 1 numeric PSO | 12分 | | | | | |
| 2 binary checkpoint | 10分 | | | | | |
| 3 delayed ACO | 16分 | | | | | |
| 4 actual observations | 10分 | | | | | |
| 5 nested trails | 10分 | | | | | |

## 按实际职责评分

每项写代码、输出或断言依据；未观察到写“未观察”。参考模式与计时后补完另记。

| 关 | 分项上限 | 实得 | 证据／尚缺行为 |
|---|---|---|---|
| 1（20） | flat best 5；actual bounds 5；max／ties 4；changed evaluation／report 6 | | |
| 2（20） | particle布局 7；global state／RNG 7；route／ledger／pending与reopen 6 | | |
| 3（25） | requested-row roulette 8；epoch decay 7；original feedback decisions 10 | | |
| 4（15） | iteration own fields 6；route fields 4；learning fields 5 | | |
| 5（20） | continuity／destination 5；multiplicity／trail 5；shared epoch／fold 6；layer certificates 4 | | |
| 合计（100） | | | |

## 逐关回看

- Part 1：是否从best_report／score_reader追到alias？实际更差movement后best是否独立？clamp放position还是velocity？max／tie语义如何保持？changed index是否真实评价，其他current scores和完整report是否保留？
- Part 2：binary布局是否区分每粒子x／v／p_best／fit？full RNG而非seed如何续接？独立routing table／epochs、Allocation ledger和完整ordered／repeated Outcome是否重开一致？Given codec／member边界在哪里？
- Part 3：roulette是否请求正确row、半开边界、一次draw？decay是否全表且同epoch一次？feedback是否奖励原task-agent并保所有拒绝reason？保守representability是否交Given而没有擅扩合法域？
- Part 4：iteration mean／best／score vector、route identity／draw、learning original attribution／arrival／epoch／amount分别来自哪条actual event？是否误把inference当learning或重判gate？
- Part 5：实际path是否连续并到destination？visited prefix、重复edge credit和task/destination是否准确？invalid first path与new epoch顺序如何？所有children／roots和每层before／after是否共享实际state？

## 证据与下一次练习

- 60分钟时已完成／未完成行为：
- 首个失败、根因、最小修改与回归依据：
- 问过的澄清问题／本应先问的问题：
- 解释过的取舍（current／best、checkpoint continuation、inference／learning、epoch／path）：
- 残留临时代码／改测试或绕过consumer的位置：
- 计时后补完（不计入原成绩）：
- 关闭答案后仍不能独立实现的函数：
- 备份位置／重做目录：
- 下次只改一个习惯：

## 当前证明范围

静态48PY、五测试、39assert、3raises、五锁、26个登记错误写法；当前原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。P1完整OptimizationDesk.run与whole OptimizationReport equality的780particles×4轮／0.16秒合同的本机完整性能组通过，输入／独立expected在timer外。

若自行运行，另记命令、环境、原样功能输出与elapsed；不能把登记清单、设计批准或来源历史打印记作执行记录。有限本机结果不证明PSO全局最优／收敛、真实LLM训练或routing收益，也不是任意墙钟SLA。60分钟真人分配未校准。

本机独占完整3slow3fast测得slow为1.58501537／1.48940483／1.48805696秒，fast为0.010484084／0.01240925／0.0110989581秒；限值0.16秒，双侧余量9.30035599／12.8936076，最慢业务1.58501537秒。原样参考五关通过，subprocess wall为0.283843917秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另重复评价实际未变粒子，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
