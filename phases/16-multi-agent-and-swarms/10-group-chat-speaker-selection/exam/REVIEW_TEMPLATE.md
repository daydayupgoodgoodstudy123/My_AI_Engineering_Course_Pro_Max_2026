# FloorFair（16/10）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本位置、Python 版本与实际命令：
- 看过的材料、用过的帮助、H1/H2/H3 次数：

60 分钟包含 2 分钟开场和 58 分钟作答，参考分配 12/11/15/10/10。时间和难度尚未经过真人校准；限时结果、reference 检查与计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 review replay | | | | | | |
| 2 audit snapshot | | | | | | |
| 3 obligations/deficits/cap | | | | | | |
| 4 public evidence | | | | | | |
| 5 cumulative quotas/total budget | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么正确 approval reader 才报错？exact terminal 的本地合同是什么？如何区分 raw history、recent view、Decision 与实际 Utterance，并先取窗口再格式化？ | |
| 2 | 每个 Decision 的完整 input/choice/reason 属于谁？Utterance 怎样关联自己的 decision_id？替换 snapshot 如何保留其他 conversation？哪些 codec/count 行为已 GIVEN？ | |
| 3 | 哪个 exact named question 未被授权回答？active actual-turn deficit 如何精确计算？cap、oldest eligible question、最大 deficit 与 roster tie 的次序是什么？ | |
| 4 | 每条公开字段来自哪个实际 observation？完整 delta 如何保留？private audit 与 public schema 怎样分开？哪些分类/binding/transport 已 GIVEN？ | |
| 5 | own per-agent cumulative usage 为什么不随 interleaving 清零？cap-th 与 cap+1st 如何区分，first_excess 怎样保留实际 ID？own pending 如何使用 GIVEN answers，subtree speech 如何消耗本层和祖先 total budget？ | |

- 60 分钟时五关状态 / 通过关数：
- 提过的澄清问题 / 本应提而未提的问题：
- 读到的正确 consumer 合同与责任 producer：
- 哪个尝试在硬编码、删证据、减少 callback 或混淆 proposed/committed：
- 哪些行为来自完整 GIVEN，哪些算法由我实现：
- 问题义务优先与 hard cap 发生冲突时如何处理：
- cumulative per-agent quota 与 consecutive streak、subtree total budget 各覆盖哪些真实发言：
- private prompt 在 audit 与 public output 中分别如何保留或排除：
- 留下的临时代码或死代码：
- 计时后补完的关与所用帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：


P1 的固定性能路径有校准报告中的本机测量记录。当前原规定 TEMP checker 已通过默认五锁、参考全五关、逐层与全部 32 项登记错修检查，其中两项 reply-authority 错修验证完整 GIVEN 的集成。Part 5 配额的三项独立实际错修分别覆盖 per-agent 归属、首条超限边界与累计历史保留；每项均为 Part 5 失败、其他四关通过，各对应 reference 全五关通过。这些结果不计作候选成绩，具体记录见 verification.txt 与独立验收报告。

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层调试与完整 replay | 20 | | |
| 完整 audit snapshot | 20 | | |
| 问题义务与份额策略 | 25 | | |
| 领域公开证据 | 15 | | |
| 累计 agent 配额与 total budget | 20 | | |
| 合计 | 100 | | |

性能 fixture 为 8,000 条真实 archived user messages、80 次真实 `ContextDigestSelector` callback、window=3。fixture/独立 expected 在 timer 外；完整 `ChatDesk.run`、整个 `ChatReport` equality 与 callback count 在 timer 内，保留 8,080 条消息、160 条 Decision/Utterance observations 和全部 input/choice/reason/counts。限值 0.05 秒，本机完整三慢三快组为慢版 0.567921–0.585339 秒、快版 0.0004762–0.0005414 秒，余量 11.3584× / 92.3503×；精确记录见 [校准报告](/tmp/exam-11-16-work/draft16-10/actual/group02-summary.json)。

六份完整测量副本仅将 elapsed 断言换成打印，慢版另仅恢复全 history 格式化后取窗口；完整功能护栏和其他四关保留，均为带测量打印的五关功能通过，不能记成慢样本通过原阈值断言。原样 reference 完整五关另通过（进程 wall 约 0.183642 秒）。业务 timer、完整进程 wall 与真人用时分开记录；这些本机有限 workload 的余量不是任意环境下的墙钟保证或生产 SLA，真人时间仍未校准。

- 我的实际命令、结果、测量条件与证据路径：
- 为什么少跑 callback、空 context 或删 raw transcript 不算修复：
- 为什么这些本地行为不能写成真实 LLM 收益、公平性定理、官方 termination 默认或框架现状核验：

P3 合法域为同一 conversation 的 typed records/unique question IDs 与 positive weights/cap；P5 为 finite typed tree/global unique qIDs/可解析 refs、唯一声明 speaker 名及非负整数 caps。完整 GIVEN 提供校验、identity 和 reply_evidence；候选重点是 obligation、actual-turn shares、own cumulative quota/首条超限、own pending 与 inherited total budget。两项 authority 错修只验证 GIVEN 集成。原 source/英文 output skill 仅作来源阅读，没有执行；Python 3.10+ 是目标环境，真人用时尚未校准。
