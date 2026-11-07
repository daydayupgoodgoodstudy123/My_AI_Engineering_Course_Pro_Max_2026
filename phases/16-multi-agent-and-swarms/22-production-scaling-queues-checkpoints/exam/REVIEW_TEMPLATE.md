# 16/22 OutboxFlow 复盘

日期：________　环境/Python：________　开始/结束：________
实际总用时：________　独立完成到：________　提示或参考开始时间：________

60分钟是未经真人校准的练习预算。只记录实际运行、提示和代码证据；默认skip、文档示例命令或参考答案结果都不能记为自己的完成。

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest次数 | H1/H2/H3 | 卡住的行为与证据 |
|---|---:|---|---|---|---|---|
| 1 checkpoint / ack / FIFO | 12分钟 | | | | | |
| 2 transaction-aware records | 10分钟 | | | | | |
| 3 commit / dispatch / recovery | 16分钟 | | | | | |
| 4 rainbow CSV | 8分钟 | | | | | |
| 5 nested admin audit | 12分钟 | | | | | |

## 按真实职责评分

与INTERVIEWER使用同一100分表。未独立实现、使用提示后实现和只读懂参考，分别记录；对同一早关根因造成的后关失败说明归属。

| 关 | 分项上限 | 实得 | 代码／测试证据与尚缺行为 |
|---|---|---|---|
| 1（20） | own-run/缺失5；原int numeric latest4；pending ack/FIFO6；完整burst及算法成本5 | | |
| 2（20） | checkpoint key/version/state7；intent own fields6；actual receipt/pending/caller事务7 | | |
| 3（25） | pair atomic/crash边界9；原key独立send后actual receipt ack8；pending drain/numeric恢复/report8 | | |
| 4（15） | 原binding6；own-version active/retire5；完整事件行/CSV集成4 | | |
| 5（20） | LCA admin阶梯7；每层crossed export6；recursive own/children/path/current-run outputs7 | | |
| 合计（100） | | | |

exactcodec、巨大整数/Decimal表示是完整Given与原样projection护栏；P5scoped resolver、mailbox binding、origin classifier和delivery driver也是完整Given。记录是否正确使用，不给这些Given算法额外主评分。

## 逐关回看

1. **P1**：首个foreign state怎样经过正确consumer暴露？过滤和numeric排序分别改变了什么？错误ack是否不改pending response？完整burst报告是否保留每条真实输入与signed amount？
2. **P2**：三个记录的业务key、原runtime/state、intent与actual receipt字段分别如何对应？pending怎样关联完整key？外层rollback是否仍控制低层写？
3. **P3**：三个TODO分别实现了什么？为after_checkpoint/before_commit/after_commit/after_send写出sender与receiver状态。terminal checkpoint为何仍可能需要先drain？
4. **P4**：deploy之后old run的resume、failed_resume和finish属于哪个version？每行active count计算哪一组？retire的许可条件是什么？
5. **P5**：LCA上行/下行路径和每层export怎样独立验证？own/children/fullpath与current-run outbound outputs怎样保留？Given delivery如何消费audit到正确mailbox？

## 证据与下一次练习

- 本次candidate与tests备份：________
- 实际pytest命令、输出文件与时间：________
- 失败的expected/actual、完整trace与责任文件：________
- 提示前独立结论／提示后补全：________
- 参考答案查阅时间与学到的具体行为：________
- 下一次只练的一项行为：________
- P1本机实测输入量／门限／实际耗时（没有测量则填UNMEASURED）：________
- 对外保证应限制到：________

## 当前证明范围

<!-- VALIDATION_STATUS_BEGIN -->
当前42个PY文件、五测试、47条assert、5处pytest.raises、五锁与25个登记错误写法。原样参考五关与本机完整性能组有对应通过记录。独立行为复核的6项有效领域错误均只在指定目标关失败、其余四关通过，每项对应参考副本均五关通过。规定TEMP检查已全部通过：默认五锁、参考五关、starter五关失败、四层、全部25项登记错误写法和reset均有记录。正式检查已通过，记录见 verification.txt；独立行为、性能与正式检查按各自证据范围解释。

P1真实负载150000条immutable Envelope输入；完整QueueDesk.drain_burst与whole BurstReport equality（全部ordered UID/run/amount/body、各run counts与signed amount）都在timer内，fixture与独立expected在外。batch adapter返回完整入站数据，不等于逐条运行并发三态agent；单条ack状态另有行为护栏。

完整校准三个慢样本[1.2884170829784125, 1.3393366250675172, 1.353035124950111]秒，三个快样本[0.008853374980390072, 0.008932374883443117, 0.009660790907219052]秒；限值0.10秒，慢侧／快侧余量12.884171／10.351119。六份测量副本只将timingassert改为elapsed打印，慢版另恢复真实list队首移除；完整五关功能均通过，不表示慢版通过原时间阈值。原样参考另有完整五关通过记录。墙钟观测受环境影响，不构成跨机器SLA；60分钟未经真人校准。
<!-- VALIDATION_STATUS_END -->

有限本地receiver的幂等合同与异常cut，不证明任意API、真实进程崩溃、并发worker、lease/fencing或production durability。未进行的验证应保持“未执行”。

当前领域覆盖包括相同numeric step的跨run独立checkpoint、sender未提交事务的dispatch拒绝、RecoveryReport own-run receipts、failed resume的active状态，以及各group完整route observations与输出source-subtree归属。
