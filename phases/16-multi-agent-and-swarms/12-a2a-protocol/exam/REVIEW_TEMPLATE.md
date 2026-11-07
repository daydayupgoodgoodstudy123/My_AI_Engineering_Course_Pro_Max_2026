# PeerResult（16/12）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本、Python 版本和实际命令：
- 看过的材料、使用的帮助与 H1/H2/H3 次数：

60 分钟包含 2 分钟开场与 58 分钟作答，参考分配 12/11/15/10/10；时间与难度尚未真人校准。限时结果、参考检查和计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 discovery/terminal/pending | | | | | | |
| 2 ordered attempts/members | | | | | | |
| 3 card/mode/flat schema | | | | | | |
| 4 change-only SSE | | | | | | |
| 5 recursive review audit | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么正确 transport 两层后才 KeyError？query 怎样污染 task identity？HTTP 成功与 task failed 怎样分开，pending/deadline/首终态怎样保持？ | |
| 2 | 每次 retry 的 metadata/member 属于谁？manifest 顺序与 snapshot membership 怎样恢复？哪些 tag/精度行为是完整 GIVEN？ | |
| 3 | pin 和 required card shapes 是什么？actual artifact tag 是否 advertised？flat issues/lines 怎样检查必填项，额外 card metadata 怎样保留？ | |
| 4 | state 相同的 artifact change 会不会丢？artifact 清空怎样表示，相等 snapshot 怎样抑制，terminal 时 state/artifact/final 次序与 final-once 怎样保证？ | |
| 5 | GroupAudit 怎样递归保留每层 own findings？child 与 parent file/span、own issue/file/group 的边界怎样检查，物理行数取自哪个 file？哪些 lookup/occurrences 已 GIVEN？ | |

- 60 分钟时各关状态 / 通过关数：
- 提过的澄清问题 / 本应提出的问题：
- 正确 consumer 合同与责任 producer：
- 哪个尝试在编造 task、丢 failed、裁 artifacts、少 poll 必要输入或硬编码结果：
- 哪些是我实现的主要算法，哪些是完整 GIVEN 与集成护栏：
- archive 的普通 structured data 与 P3 flat schema 怎样分开：
- declared lines 与重新审查 source 的边界：
- unique issue（含未引用 canonical）与全部 membership refs 分别代表什么：
- P3/P5 如何消费真实 polled/archived/adapted artifact，而不是只处理手填例子：
- 留下的临时代码或死代码：
- 计时后补完的关与所用帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层 polling 与完整结果 | 20 | | |
| ordered attempt archive | 20 | | |
| pinned review adapter | 25 | | |
| change-only observation | 15 | | |
| recursive review audit | 20 | | |
| 合计 | 100 | | |

P1 当前限值 0.07 秒。固定完整组慢版三次为 0.702968、0.670234、0.662439 秒，参考版为 0.002720、0.002595、0.002550 秒；两侧余量分别为 9.46342 和 25.73884。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另恢复重复 terminal GET/JSON decode；其余完整业务 guards 和全五关功能通过，不能说慢版通过原阈值。原样 reference 五关另行通过。规定 TEMP 校验已通过五锁、参考全五关、starter 五关失败、P1 分层、28 项登记错修和 reset 一致性检查，记录在 verification.txt。独立行为记录为 6 个核心错误及 1 个不计入核心数量的同方向辅助错误：对应参考全五关通过，错误各自由目标关捕获，证据在题包外 fresh-review.json。正式检查已通过，记录见 verification.txt；正式归档保留独立验收记录。 本机结果不是任意环境墙钟上界或生产 SLA。

- 我的实际命令、结果、环境与证据路径：
- timer 内完整业务与 timer 外准备分别是什么：
- 为什么跳过必要任务、删 artifacts 或预填结果不算修复：
- 为什么本地结果不能写成 current A2A 符合性、真实模型审查质量或生产 SLA：

当前静态数量为 45 Python 文件、5 tests、40 assert、5 raises、5 skip、28 登记错修，不等于运行结果。来源只固定 local a2a-0.3/custom REST；批量轮询、attempt archive、SSE 和 nested file/span audit 是本地适配，不是 source 已有完整服务。四份来源与英文 output artifact 仅静态阅读，未调用其流程或作当前外部核验；Python 3.10+ 为目标环境，60 分钟真人用时仍未校准。
