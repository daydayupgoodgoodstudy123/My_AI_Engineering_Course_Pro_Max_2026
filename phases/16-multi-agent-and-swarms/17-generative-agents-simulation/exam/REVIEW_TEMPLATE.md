# 16/17 SmallvilleLab 复盘

- 日期／第几次：
- 模式：独立计时／有人主持／关闭答案后的重做
- 开始／结束时间；是否按2分钟开场+58分钟编码：
- 实际Python版本、环境和工作副本：
- 看过的材料、澄清问题与帮助：
- 是否打开答案；哪些结果属于计时后：

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest次数 | H1/H2/H3 | 卡住的行为与证据 |
|---|---:|---|---|---|---|---|
| 1 inspection | 12分 | | | | | |
| 2 agent directory | 10分 | | | | | |
| 3 rank／reflection／revision | 16分 | | | | | |
| 4 calendar fields | 10分 | | | | | |
| 5 nested execution | 10分 | | | | | |

## 按实际职责评分

每项写代码位置、输出或断言依据；未观察到写“未观察”。参考模式和计时后补完另记。

| 关 | 分项上限 | 实得 | 证据／尚缺行为 |
|---|---|---|---|
| 1（20） | actual delivery 5；nonfuture availability 4；consumed pending 5；query和完整Inspection 6 | | |
| 2（20） | 完整领域schema 8；UID／ordered records／progress关联 8；replacement／reopen／Given集成 4 | | |
| 3（25） | composite rank 7；grounded reflection与actual consumption 10；local revision 8 | | |
| 4（15） | stable UID／sequence 5；own interval／actor／venue／note 6；cancel／simulated 4 | | |
| 5（20） | nested audit／containment 5；inactive／whole opening 5；shared DFS commit 8；movement／final world 2 | | |
| 合计（100） | | | |

## 逐关回看

- Part 1：是否从正确人口consumer的IndexError追到hardcoded positions？availability为何保全部可用kind而pending只取raw？future低seq如何在之后成为pending？query feature语义及完整Inspection保留了什么？
- Part 2：UID与name是否分离？每agent的memories／sources／contradicts、progress、beliefs和plans是否完整？空belief与零last tick是否仍有explicit progress？manifest顺序与完整replacement如何重开？
- Part 3：三分量与stable tie如何计算？proposal中哪些source被拒绝，哪些实际消费？uncited pending和derived memory如何处理？affected／changed／unresolved与cause IDs是否一致？无关patch为何不应用？
- Part 4：十字段归属哪条observation？同segment的old／new／cancel UID与sequence如何变化？venue与agent当前location是否混用？哪些escaping／writer／close行为属于Given？
- Part 5：action使用current segment还是node placeholder？是否检查整个child／opening区间？inactive如何保留？shared World如何跨root传递？stayed、departure release和accepted movement怎样影响后续capacity？

## 证据与下一次练习

- 60分钟时已完成／未完成行为：
- 首个失败、根因、最小修改与回归依据：
- 问过的澄清问题／本应先问的问题：
- 解释过的取舍（source provenance、local revision、calendar identity、physical occupancy）：
- 残留临时代码／改测试或绕过consumer的位置：
- 计时后补完（不计入原成绩）：
- 关闭答案后仍不能独立实现的函数：
- 备份位置／重做目录：
- 下次只改一个习惯：

## 当前证明范围

静态清点45PY、五测试、43assert、0raises、五锁、28个登记错误写法；当前原样参考五关与完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定 TEMP 检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部28项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能和正式检查仍按各自证据范围解释。P1完整TownDesk.inspect与whole Inspection equality的0.035秒合同的当前完整性能组通过，fixture含5000条合成本地memories和4000额外query OR terms，输入／独立expected在外。

若自行运行，另记命令、环境、原样功能结果和elapsed，不能把登记清单或来源历史输出记成执行记录。有限本机结果不证明无脚本涌现、社会质量、反思逻辑蕴涵、未来reservation可行性或任意墙钟SLA。60分钟真人分配未校准。

本机独占完整3slow3fast测得slow为0.368153／0.312983／0.356904秒，fast为0.00317596／0.00322900／0.00321125秒；限值0.035秒，双侧余量8.94236／10.8393，最慢业务0.368153秒。原样参考五关通过，subprocess wall为0.204143秒。六份完整五关测量版本保留全部业务输出guard，仅把timing断言改为真实elapsed打印；slow另把真实query lower／split放到每次feature调用，不能称slow通过原限值。测得余量依赖本机环境，不是任意墙钟上界或SLA。
