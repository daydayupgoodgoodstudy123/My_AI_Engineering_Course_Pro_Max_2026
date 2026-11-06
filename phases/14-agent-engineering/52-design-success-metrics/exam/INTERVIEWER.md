# 面试官手册：MetricPlan（14/52）

候选人计时期间不看。候选人只有 README、metricplan/ 与 tests/。

## 开场（2 分钟）

说明60分钟，逐关解锁、原样测试通过，请边做边讲。澄清证据和测量需要，约5分钟卡住后给一级提示。本题不宣称有限回放证明生产安全。

## 澄清问题的标准答案

只在问到时用英文回答。

| 关 | 问题 | 回答 |
|---|---|---|
| 1 | Is population optional when source is present? | No. Source, window and population are independent contract fields. |
| 1 | Does every question need outcome and guardrail? | No. Those roles are required across the plan, not on every question. |
| 1 | May the reader drop source receipts? | No. Read the complete bounded snapshot and preserve all fields. |
| 2 | Are excluded replays discarded? | No. Preserve evidence; inclusion only controls the outcome denominator. |
| 2 | Is the last inserted row the latest? | No. Compare aware instants, then stable ids; preserve raw timestamp text. |
| 3 | Which failure wins? | Any pilot production write is fail. An incomplete safe batch is ambiguous. |
| 3 | Does a worsened counter always fail? | In this contract it downgrades a pass to ambiguous, without erasing fail. |
| 4 | Is it a sliding last-N window? | No. Complete disjoint batches; global pilot writes never disappear. |
| 4 | What if a write is in an excluded replay? | Bail out immediately, before a successful batch and without a future pull. |
| 5 | Can a metric serve two questions? | Yes. Shared references remain attached to every question. |
| 5 | Must a risk-only child goal have an outcome? | No. Only the whole root plan needs outcome and guardrail coverage. |

## 每关：要看什么、提示、追问

### Part 1 指标报告（目标 12 分钟）

坑：
1. report→validate→metric_issues漏population，错误在上层valid状态出现。
2. 合法counter被报告过滤掉，局部改善转移给其他角色的成本消失。原课report本来遍历所有kind，这是本题新植。
3. 本地源reader逐字节无缓冲读取，1,098,957 bytes（约1.05MiB）的正常pilot receipt文件产生大量系统调用。缓冲本来用bytearray，不能误诊成反复bytes拼接；应按块或完整读取有上限快照。

实测慢三次0.394/0.381/0.382秒，参考1.224/1.080/1.009毫秒；限值0.04秒，双侧至少8倍。finite与重名计频helper本来正确；NaN非法、missing不同于invalid；提速不能丢receipt/Unicode或更改原合同。

看什么：从报告状态追到独立合同字段，确认系统调用粒度而非乱删证据。

提示：“Which contract field cannot be recovered from source or window?”；“Which legal metric role disappeared?”；“How many reads does one snapshot cause?”

追问：source稳定快照假设若不成立，如何固定测量输入？为什么这个测量数字仍不等于因果证明？

### Part 2 回放证据表（目标 10 分钟）

坑：
- 所有原始回放都保存，包括excluded、错误答案与零耗时；还原整数毫秒、bool、population和原始文本。
- recent按真实时刻和id选最新N，再按从旧到新返回；写入次序和时区字符串不能代替instant。
- 同id替换完整快照时更新查询索引，另一个id的材料不能被动改变。

看什么：存储源记录与选择测量人群分开；时间helper已给对。

提示：“Can this excluded replay still be evidence of unsafe behavior?”；“Does an id encode observation time?”

追问：如果多个来源对同一id有冲突记录，服务应保存什么额外来历？本题只是单writer替换合同。

### Part 3 预定复合决定（目标 14 分钟）

坑：
- 整个pilot的writes先于局部通过，excluded和非目标population不能遮住安全事故。
- 固定合格批次的正确率与偶数中位数；毫秒转换秒；未满批次ambiguous而非零分fail。
- counter只把pass降ambiguous；既有fail不被覆盖。pass阈值含等号，fail_rate只在严格低于时fail。

冻结与首批选择helper已给对，不重做注册时区算法。数字与行动顺序是本题明确决策合同，源课给了示例而非通用统计标准。

看什么：先区分安全否定、证据不足和局部改善，再算联合通过。

提示：“Could speed excuse a production write?”；“What does an even replay median mean?”

追问：为什么十次回放的pass不能代替真实pilot？counter应该如何在真实团队预先定界？

### Part 4 试点指标流（目标 12 分钟）

坑：
- 完整固定批次输出三行后再拉下一事件，不把旧批次混进下一批。
- 任意write立即Bail out且终止，不能先发成功行、过滤excluded后才检查或继续拉未来事件。
- EOF只补真正存在的合格partial batch，编号跨批次递增；无样本不伪造窗口。

行编码helper已给对，是本题TAP样式合同，不要求外部协议知识。

看什么：源拉取与消费方可见输出的边界。

提示：“Which events belong to the pilot guardrail but not the batch denominator?”

追问：生产源的资源所有权应怎样表达？本题只要求取消不预拉，不替调用方关闭任意source。

### Part 5 GQM追溯（目标 12 分钟）

坑：
- 目标/子目标与问题的路径完整保留；共享metric引用不是重复定义，每个相关问题都算。
- unknown链接、空问题、catalog孤儿明确给诊断；未测指标ambiguous。
- 聚合最差状态fail>ambiguous>pass，不能平均掉风险；覆盖outcome+guardrail在整个root计划，不在每个question。

看什么：区分结构追溯与指标好坏；不把风险question强加outcome，不把未测写成通过。

提示：“Which question does this number answer?”；“Can one passing metric hide a failed guardrail?”

追问：这个GQM结构验证能否发现一个容易收集但不能改变决策的指标？现实还需要怎样的人类判断？

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 调试与效率 | 25 | 合同字段、counter、源读取粒度 |
| 精确持久化 | 15 | 全量证据、类型、时间选择 |
| 决策算法 | 25 | 安全优先、固定批次、反指标 |
| 在线边界 | 20 | 输出、终止、EOF、取消 |
| 追溯与沟通 | 15 | 共享引用、风险question、来源边界 |

记录具体证据、提示次数和时间，未观察到写“未观察”。允许等价实现。
