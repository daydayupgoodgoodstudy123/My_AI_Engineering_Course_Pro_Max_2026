# BlackScope（16/13）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本、Python 版本与实际命令：
- 看过的材料、使用的帮助与 H1/H2/H3 次数：

60 分钟包含 2 分钟开场与 58 分钟作答，参考分配 12/11/15/10/10；时间与难度尚未真人校准。限时结果、参考检查和计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 summary/correction/finding | | | | | | |
| 2 complete version ledger | | | | | | |
| 3 active/exact join/consume | | | | | | |
| 4 own provenance projection | | | | | | |
| 5 derived support | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么正确 percent consumer 才 ValueError？怎样保留 decimal/unit/punctuation、旧 provenance 与独立 finding？怎样首句早停但保留完整正文？ | |
| 2 | 为什么 retired versions 也要保存？原 ID/append order 和每版 metadata 怎样重开？哪些 codec/channel 行为已经 GIVEN？ | |
| 3 | same-topic lineage 与独立 root 怎样区分？entry/source-version exact join 和 dispute priority 是什么？role/topic 如何限制 active VERIFIED 消费？ | |
| 4 | 九个 payload 字段来自哪一版？correction predecessor 和 source URI/version 怎样保留？哪些 kind/finding/wire/close 逻辑是 GIVEN？ | |
| 5 | 每层 certificate 怎样保留？required 与 covered 为什么不同？wrapper 与真实 external SourceKey 怎样区分？哪些 occurrence/leaf lookup 已 GIVEN？ | |

- 60 分钟时各关状态 / 通过关数：
- 提过的澄清问题 / 本应提出的问题：
- 正确 consumer 与责任 producer：
- 哪个尝试在裁 source、改旧 provenance、写 finding 回 fact pool 或预填 report：
- P1 的 channel 修复与 P2/P4 已给定 routing 怎样区分：
- P3/P5 如何实际消费 service 与 ledger reopen 的证据：
- 为什么同 URI 不同 version、同 topic 不同 root、相同文本的不同记录不能随意合并：
- 为什么空 topic view 不授权消费，同 root 的较晚分叉取最新 append：
- 为什么缺 finding/缺完整 certificate 不是 false claim：
- distinct source keys 与现实来源独立性的界线：
- 留下的临时代码或死代码：
- 计时后补完的关与帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层摘要与 correction | 20 | | |
| 完整版本 ledger | 20 | | |
| active exact evidence policy | 25 | | |
| own provenance projection | 15 | | |
| derived support certificate | 20 | | |
| 合计 | 100 | | |

P1 当前限值 0.02 秒。固定完整组慢版三次为 0.219885、0.224771、0.238220 秒，参考版为 0.0001577、0.0001976、0.0002087 秒；两侧余量分别为 10.99425 和 95.80843。32 篇合成本地 articles 各保留 14,000 条实际进入服务的 observation rows，完整输出为 64 条 retrieval/summary entries 与 32 条 receipts；fixture 与独立 expected 在 timer 外，整个 SummaryDesk.observe_many 及完整 SummaryReport equality 在内。六份 NEW 完整副本只把 timingassert 换成实际 elapsed 输出，慢版另执行 decimal-safe 全文 split；全部业务 guards 与全五关功能通过，不能说慢版通过原限值。原样 reference 五关另行通过。TEMP、独立行为和正式检查分别有自己的验收记录，不能由测量版推定；本机余量不是任意运行环境的墙钟上界或生产 SLA。

- 我的实际命令、结果、环境与证据路径：
- timer 内完整业务与 timer 外准备分别是什么：
- 为什么裁掉 source tail、少处理 report 或预填 expected 不算修复：
- 为什么不能把本地证据写成自然语言事实核验、生产 memory-poisoning 防护或通用墙钟 SLA：

当前静态数量为 42 Python 文件、5 tests、43 assert、0 raises、5 skip、26 登记错修，不等于运行结果。source RUN 2 没有真实 retraction；完整独立 channel、active policy、persistence 与 derived support 是课程方向的显式本地扩展。四份来源与英文 output artifact 仅静态阅读，未调用其流程或当前外部核验。Python 3.10+ 是目标环境，60 分钟真人时间仍未校准。

当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错修与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。
