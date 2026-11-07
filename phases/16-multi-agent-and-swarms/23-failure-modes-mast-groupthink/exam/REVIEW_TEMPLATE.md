# 16/23 MASTStorm 复盘

日期：________　Python/环境：________　开始／结束：________
实际总用时：________　独立完成到：________　首次提示／参考时间：________

60分钟未经真人校准。区分自己的实现、提示后完成和参考运行；默认skip与说明中的命令不能当完成证据。

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest次数 | H1/H2/H3 | 卡点／expected与actual |
|---|---:|---|---|---|---|---|
| 1 evidence / breaker | 12分钟 | | | | | |
| 2 full CSV archive | 10分钟 | | | | | |
| 3 actual budget / causal retry | 16分钟 | | | | | |
| 4 own-event syslog | 8分钟 | | | | | |
| 5 sealed nested accounting | 12分钟 | | | | | |

## 按真实职责评分

使用与INTERVIEWER相同的100分表，给出实际代码／测试证据；早关依赖导致的后关失败注明归属。

| 关 | 分项上限 | 实得 | 证据与尚缺行为 |
|---|---|---|---|
| 1（20） | primary/unknown/tags5；probe/cooldown5；reset/isolation4；incremental expiry/strict gate/fullreport6 | | |
| 2（20） | 完整incident字段7；action/budget4；独立observation5；重复顺序/typed reopen4 | | |
| 3（25） | shared actual budget/admission8；causal children/retry/UID cache10；whole-root trace/outcome/calls/effects7 | | |
| 4（15） | own identities5；phase/note/Given severity-wire5；actual positive validation closing5 | | |
| 5（20） | nested edges/ordinal7；own+subtree三类counts7；root/paths/serviceorder/Fraction/empty6 | | |
| 合计（100） | | | |

codec、完整P1 breaker、完整sealed P3、severity与trace binding是Given。记录调用是否正确，不将这些实现再算候选算法。P2独立observation关联与P4closing仍是真实责任；P5不重复这项判断。

## 逐关回看

1. P1：producer如何破坏原primary证据并在正确renderer暴露？合法unknown为什么正常？probe/reset/过期减计数与strict equality分别由哪些行为支持？
2. P2：12列如何对应IncidentRecord与Observation？同incident重复snapshot、False/None/True与quoted newline是否完整读回？
3. P3：哪条路径真的invoke、debit、record？为什么budget在allow前检查？成功sibling如何在失败dependency重试时保持cached？同service不同effect怎样区分？
4. P4：每行9字段属于哪个event/incident/observation？什么情况下closing=True？severity是完整Given，candidate投影了哪些own字段？
5. P5：每个retry的child edge怎样保留？cached/short/budget/dependency-failed各贡献多少actual calls？pruning path、service顺序、declared-root分母与empty怎样处理？

## 实际证据与下一次练习

- candidate/tests备份：________
- pytest实际命令／输出文件／时间：________
- 失败trace与责任模块／最小修复：________
- 提示前结论／提示后完成：________
- 参考查阅时间及具体学到的行为：________
- P1测量输入量／window／门限／实测（未测填UNMEASURED）：________
- next practice只练一项行为：________
- 本次能证明的有限合同：________

## 当前证明范围

<!-- VALIDATION_STATUS_BEGIN -->
当前48个Python文件、五个测试、43条assert、0处pytest.raises、五锁与26个登记错误写法。领域覆盖包括声明的primary与原symptoms独立关联、配置的正整数attempt上限、全部dependency sibling、原event顺序、完整祖先retry路径及first-actual service顺序。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过；12份matching reference各自五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部26项登记错误写法和reset均有实际记录。正式检查已通过，记录见 verification.txt。

P1真实负载40000个bool outcome、window20000、strict threshold .5；完整BreakerDesk.replay和entire ReplayReport equality（每个actual allow/record序号、state、sample count、failure count及完整final window）均在timer内，独立expected在外。

完整校准三个慢样本[1.345574207836762, 1.4553501659538597, 1.3413112498819828]秒，三个快样本[0.00878770905546844, 0.010089250048622489, 0.009202209068462253]秒；限值0.12秒，慢侧／快侧余量11.177594／11.893847。六份测量副本仅将timing assert改为实际elapsed打印，慢版另恢复真实bounded outcome窗口重sum；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有全五关通过。墙钟记录受环境影响，不作跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->

有限logical-time provider与sealed trace不证明现实恢复、真实STRATUS质量、跨机器重试语义或生产10×放大。没有执行的检查保持未执行，不借reference或stage认可补写通过。
