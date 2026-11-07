# RobustCenter（16/14）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本、Python 版本和实际命令：
- 看过的材料、使用的帮助与 H1/H2/H3 次数：

60 分钟包含 2 分钟开场与 58 分钟作答，参考分配 12/11/15/10/10；时间与难度尚未真人校准。限时结果、参考检查和计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 signed/abstain/mass/D | | | | | | |
| 2 per-run snapshot | | | | | | |
| 3 interval/tie/radius | | | | | | |
| 4 own seven fields | | | | | | |
| 5 nested sealed audit | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么正确 cluster consumer 才 ValueError？signed/unit、ABSTAIN、confidence mass 与 D 的域各是什么？怎样保持同值 exact D 与完整 Inspection？ | |
| 2 | 当前 run 的完整 snapshot 和 ordinal 怎样恢复？same-agent distinct UIDs、zero-mass audit 与各自实际 probe ID 怎样保留和关联？哪些 SQL/codec 已 GIVEN？ | |
| 3 | positive-mass weighted median 的 full interval 如何找到？interior zero mass、half mass/tie/radius/minority 如何保持？为什么 accepted 与 truth 分开？ | |
| 4 | 七个 own proposal fields 来自谁？raw answer、signed position/unit 与 self-report 怎样保留？哪些 probe/framing 行为已 GIVEN？ | |
| 5 | authoritative sealed 与 CoreGroup declaration 怎样区分？core/edge 为何独立审计，edge-before-core 究竟看什么？children 怎样保留自己的 sealed reports？ | |

- 60 分钟时各关状态 / 通过关数：
- 提过的澄清问题 / 本应提出的问题：
- 正确 consumer 与责任 producer：
- 哪个尝试在丢 audit、混自报与 probe、数人数代替质量或预填结果：
- P1 confidence diagnostic 与 P3 position minimizer 的区别：
- P2 full snapshot 为什么不等于 retry lineage 或多 probe 历史：
- 哪些是完整 GIVEN，哪些是我实现的领域算法：
- 一个 matching edge 与 core declaration finding 共存的证据：
- agreement、supplied truth label 与真实安全保证怎样区分：
- 留下的临时代码或死代码：
- 计时后补完的关与帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层 inspection 与 D | 20 | | |
| 完整 proposal/probe snapshot | 20 | | |
| weighted center 算法 | 25 | | |
| own proposal evidence | 15 | | |
| nested Core/Edge audit | 20 | | |
| 合计 | 100 | | |

P1 当前限值为 0.15 秒。固定完整组慢版三次为 2.089669、2.736338、2.203572 秒，参考版为 0.014413、0.015047、0.013903 秒；两侧余量分别为 13.93112 和 9.96901。2,400 个合成本地 Ballots 的完整 Proposal/Probe、canonical keys、support/abstentions、source-style legacy scores、exact D 与 dispersion_alert 全部保留，D 的独立 closed-form expected 为 ones×zeros。fixture 与独立 expected 在 timer 外，整个 ConfidenceDesk.inspect 与完整 Inspection equality 在 timer 内，之后才读 elapsed；不能删 zero/abstention、只求 extreme gap、裁 records 或预填 report。六份 NEW 完整测量副本只把 timingassert 换成实际 elapsed 输出，慢版另枚举所有真实 unordered confidence pairs；全部业务 guards 和全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为与正式检查有各自验收记录，不能由测量版推定；本机测得余量受运行环境影响，不构成通用墙钟上界或生产 SLA。

- 我的实际命令、结果、环境与证据路径：
- timer 内完整业务与 timer 外准备分别是什么：
- 为什么丢 zero/abstention、只求 extreme gap 或预填 report 不算修复：
- 为什么本地结果不能写成 PBFT/security/truth 保证或生产 SLA：

当前静态数量为 45 Python 文件、5 tests、37 assert、1 raises、5 skip、26 登记错修，不等于执行结果。source confidence heuristic 不是位置 median；本题 D、typed abstention、snapshot、frame 与 Core/Edge certificate 都是显式本地扩展。四份来源与英文 output artifact 仅静态阅读，未调用其流程或当前外部核验。Python 3.10+ 为目标环境，60 分钟真人时间仍未校准。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
