# WorkPull（16/09）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本位置、Python 版本与实际命令：
- 看过的材料、用过的帮助、H1/H2/H3 次数：

60 分钟包含 2 分钟开场和 58 分钟作答，参考分配 12/11/15/10/10。时间和难度尚未经过真人校准；限时成绩、参考实现检查和计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 完整 FIFO replay | | | | | | |
| 2 lifecycle journal | | | | | | |
| 3 specialist aging/claim | | | | | | |
| 4 observed event frames | | | | | | |
| 5 nested subscriptions/pools | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么错误在正确 result reader 才暴露？task ID 与 actual worker 怎样分别保留？为什么暂空不等于 producer 完结？稳定 calendar 如何保留全部真实事件？ | |
| 2 | task 声明、arrival、pull、completion 怎样区分？为何不能用 pre_assigned、arrival time 或已知 duration 伪造实际完成？重开保留哪两种顺序，相同 payload 的不同 task 是否仍独立？ | |
| 3 | 为什么先做 arrival/topic admission？age 从哪里开始，在何时重算？平票如何裁决，不足一个完整 interval 如何计分，声明 worker 次序怎样保持，如何避免重复 claim？ | |
| 4 | 每个 phase 允许哪些字段？completion 的时间/worker/result 属于哪条真实记录？arrival 的 signed priority 是否原样保留，哪些 byte framing 与 async 行为是完整 GIVEN？ | |
| 5 | 有效 topics 为什么取祖先交集？显式空 restriction 与 None 有何区别，shared sibling pool 是否可见？每个 worker 与整个 subtree 的完成数分别来自什么实际证据？ | |

- 60 分钟时五关状态 / 通过关数：
- 提过的澄清问题 / 本应提而未提的问题：
- 读到的真实 consumer 合同与根因：
- 哪些尝试是在硬编码、删输出或改变观察来源：
- 正确 GIVEN 如何使用，哪些算法仍由我实现：
- 逻辑时间、业务 timer 与 pytest wall time 如何区分：
- 留下的临时代码或死代码：
- 计时后补完的关与所用帮助：
- 关掉答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层调试与完整 replay | 20 | | |
| lifecycle 持久化 | 20 | | |
| specialist aging 与 claim | 25 | | |
| 领域事件投影 | 15 | | |
| subscriptions、pool 与完成量 | 20 | | |
| 合计 | 100 | | |

性能 fixture 为 12 批、每批 250 项，共 3,000 个真实本地任务；arrival=5000×批序，duration=1+i%3。fixture 和独立 expected 在 timer 外；完整 `CompletionDesk.run` 与整个 `RunReport` equality 在 timer 内。限值 0.14 秒，本机完整三慢三快组为慢版 1.2555–1.2973 秒、快版 0.01660–0.01749 秒，余量 8.9679× / 8.0034×；快侧接近 8×。精确数值见 [校准报告](/tmp/exam-11-16-work/draft16-09/actual/group03-summary.json)。

六份测量副本用打印代替 elapsed 限值断言，慢版另只恢复 min/remove calendar；完整业务输出 equality 和其他四关保留，均为测量版五关功能通过，不能记成慢版通过原阈值断言。原样 reference 完整五关另通过（进程 wall 约 0.2282 秒）。逻辑微秒、业务 timer 与进程 wall 分开记录；这些本机余量不保证任意负载下的墙钟上界，也不是生产 SLA。人类 60 分钟用时仍未校准。

- 我的实际命令、结果、测量条件与证据路径：
- 哪些结论只支持本地确定性 adapter：
- 为什么不能把它写成原 source 已运行、真实线程 speedup、模型收益或生产 broker 验证：

原 demo 的静态任务预入队与空即退出是匹配的。future arrivals、逻辑事件、结果 pool、journal、event frame 和 nested pool manifest 是显式扩展；来源输出 skill 作为数据读取，不是已执行的架构评估。

当前题包有 36 条 assert、2 处 raises、五个测试与五个 skip 锁，登记 24 项错修。独立 source-first 验证覆盖 6 个领域错修：等 payload 的不同 task identity、完整 aging interval、声明 worker 次序、arrival 的 signed priority、显式空 topic restriction，以及 shared sibling pool 的祖先边界。6 个错修均在 NEW 完整副本中只使指定关失败、其余四关通过，配对 reference 均为五关通过；原规定 TEMP --write checker 的默认五锁、参考全五关、starter 五失败、逐层与全部 24 项错修检查通过。完整执行命令、内容 SHA、权限记录和日志见 exam 外 fresh-review.json。