# SOPForge（16/08）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 实际命令、Python 版本与练习副本位置：
- 看过的材料、用过的帮助、H1/H2/H3 次数：

60 分钟含 2 分钟开场与 58 分钟作答，参考分配 12/11/15/10/10。尚未经过真人计时校准，记录自己的观察，不把参考实现或计时后补完算成限时成绩。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 完整验证 | | | | | | |
| 2 revision store | | | | | | |
| 3 owner 澄清恢复 | | | | | | |
| 4 JUnit case evidence | | | | | | |
| 5 typed SOP ports | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | literal 为何不能产生真实函数？为何 traceback 在正确 lookup 出现？怎样选 declared callable、保留全部 case，并做到每次验证只 compile/bind 一次、正确使用 once-exec session 且不串 namespace？加载错误为何不是完成的 case？ | |
| 2 | spec/artifact 的哪组 revision keys 关联各 role？如何保留 critic-approved/verifier-failed 两种判断、尚无 artifact 的 planner spec、完整顺序及替换 snapshot？哪些精度/事务行为来自 GIVEN？ | |
| 3 | 谁拥有缺失字段？哪些 Answer 才是 active？新 revision 后哪些未解问题要更新、哪些 slots 要失效？为何另一个 target blocked 时不能恢复别的 step，且仍须真实验证？ | |
| 4 | 每条 JUnit entry 的 spec revision 身份和 expected/got/exception/args 来自哪个真实 case？为什么成功 case 也要保留？哪些分类/编码/传输行为已完整给定？ | |
| 5 | 输入输出要求哪个 producer、kind 与实际 payload？kind/payload 正确但 producer 错误时怎么办？exposes 为空时能展示什么？哪些 revision links 由现成 helper 校验？ | |

- 60 分钟时五关状态 / 通过关数：
- 提过的澄清问题 / 本应提而没有提的问题：
- 调试时读到的真实 consumer 合同：
- 我曾想删除、硬编码或缓存什么？哪条护栏阻止了过修：
- 无关工作、未解问题 owner 和 revision 是怎样保留的：
- 留下的临时代码或死代码：
- 计时后补完的关与所用帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层调试与完整验证 | 20 | | |
| 持久化建模 | 20 | | |
| owner 澄清与局部恢复 | 25 | | |
| 领域流式展示 | 15 | | |
| SOP 合同与解释 | 20 | | |
| 合计 | 100 | | |

P1 测的是 600 个真实声明 case 的 `TABLE` artifact：fixture/预期构造在 timer 外，完整 `VerificationDesk.inspect` 与全部 `Bundle` 输出检查在 timer 内。本机独占完整三慢三快测得慢路径 0.903041 / 0.980894 / 1.125314 秒，参考路径 0.003861 / 0.003669 / 0.004244 秒；限值 0.08 秒，双侧余量为 11.288 / 18.848 倍。六份测量副本仅把 timing assert 换成 elapsed 输出，慢路径另恢复逐 case 的真实 compile/bind；全部功能护栏与另外四关均通过，不表示慢路径通过原限值。原样五测试参考实现已通过；业务 timer 与整个 pytest wall time 分开记录。个人的一次 pytest wall time 也不是这条业务 timer 的耗时。

- 我的实际测量、完整命令、结果与证据路径：
- 哪些行为仅验证了声明的本地可信 fixture：
- 为什么这不能证明安全沙箱、任意程序正确性或真实 LLM 质量：

SQLite、Question/Answer、revision tags、SOP tree 和 JUnit 是本地显式扩展。不要把题包验证写成原课程脚本执行、真实模型调用、网络运行或外部来源统计的最新核验。
