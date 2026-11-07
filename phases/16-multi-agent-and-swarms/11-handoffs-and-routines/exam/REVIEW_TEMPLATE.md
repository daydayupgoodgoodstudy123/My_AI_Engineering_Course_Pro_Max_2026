# RoutineHop（16/11）复盘

- 日期 / 第几次做：
- 模式：独立计时 / 有人主持 / 重复练习
- 开始与结束时间：
- 练习副本、Python 版本与实际命令：
- 看过的材料、使用的帮助与 H1/H2/H3 次数：

60 分钟包含 2 分钟开场与 58 分钟作答，参考分配 12/11/15/10/10；时间与难度尚未真人校准。限时结果、参考检查和计时后补完分别记录。

| 关 | 解锁时间 | 首次通过 | 运行次数 | 首个症状 / 责任模块 | 修根因的证据 | 提示级别 |
|---|---|---|---|---|---|---|
| 1 intake/receipt/online guard | | | | | | |
| 2 caller snapshot/rebinding | | | | | | |
| 3 original-owner batch | | | | | | |
| 4 typed NDJSON evidence | | | | | | |
| 5 independent caller runs | | | | | | |

## 逐关反思

| 关 | 需要解释清楚的问题 | 我的证据与一个过修反例 |
|---|---|---|
| 1 | 为什么正确 receipt lookup 才抛 KeyError？opaque ID、缺失时询问与 outgoing sender 的责任分别在哪里？怎样增量维护 last-three edges，同时保留完整 audit？ | |
| 2 | 哪些字段属于完整 continuation？active 为什么只存名称却必须从当前 catalog 重绑定？JSON 普通数据与 runtime callable 怎样区分？ | |
| 3 | 为什么所有 call 都要 upfront 在原 owner 绑定？实际 Agent 与 Agent-shaped dict 怎样分类？首次 transfer 后哪些副作用被禁止，下一批用谁？ | |
| 4 | 每种 receipt 的公开字段来自谁？structured result 怎样保留？为什么 skipped 没有 result？哪些 codec/driver 行为已 GIVEN？ | |
| 5 | own batches 怎样续接 active？每个 child 从哪里开始？最后一步是 child 时 parent final/history 为什么仍独立，steps 怎样保持交错？ | |

- 60 分钟时各关状态 / 通过关数：
- 提过的澄清问题 / 本应提出的问题：
- 正确 consumer 合同与责任 producer：
- 哪个尝试在硬编码 report、删除 audit、默认订单或执行 skipped tail：
- 我实现的主要算法与完整 GIVEN 依赖分别是什么：
- ToolFailure、Agent transfer 与普通 data 各自的处理：
- 原 owner 的 namespace 与下一 batch 的 active 怎样区分：
- parent/child/sibling 各自 active 与 history 的证据：
- 留下的临时代码或死代码：
- 计时后补完的关与帮助：
- 关闭答案后仍不能独立重写的部分：
- 下次只改一个习惯：

## 评分与证明边界

| 维度 | 满分 | 得分 | 可观察证据 / 未观察 |
|---|---:|---:|---|
| 分层 intake 与完整 replay | 20 | | |
| caller snapshot 与重绑定 | 20 | | |
| original-owner batch 算法 | 25 | | |
| typed 公开证据 | 15 | | |
| 独立 caller continuation | 20 | | |
| 合计 | 100 | | |

P1 性能 fixture cycles=2700，真实处理 8,103 handoffs、1,621 notes，共 9,724 observations。fixture/独立 expected 在 timer 外；完整 ReplayDesk 与整个 ReplayReport equality 在 timer 内。限值 0.075 秒；固定完整校准组两侧余量 10.03116/16.68830。六测为 timingassert 替换成 elapsed 输出的完整功能版本，慢版还含真实全 audit 重放；不能称慢版通过原阈值。原样参考五关通过，原规定 TEMP 全部检查通过，独立行为验收的 6 个不同机制均按各自目标关抓住，配套参考五关通过；正式检查已通过，记录见 verification.txt。不能把少处理输入、丢完整审计或预填 expected 当作性能修复。

- 我的实际命令、结果与测量环境：
- 完整 timer 内路径和 timer 外准备分别是什么：
- 限时结果、参考结果、静态阅读与实测证据怎样区分：
- 为什么这不能写成真实模型收益、真实退款效果、SDK 保证或通用墙钟 SLA：

当前静态数量为 45 Python 文件、5 tests、41 assert、0 raises、5 skip、25 登记错修，静态数量不等于运行结果。普通 data 限于严格 JSON 值树，不保证任意 Python 对象；catalog、精确 codec、typed classifier、async driver 与有限树校验为完整 GIVEN。caller-run composition 是 source 概念的显式本地适配，不是 source 已有 DSL。四份来源和英文 output artifact 只静态阅读，未执行或当前外部核验；Python 3.10+ 为目标环境，60 分钟真人用时仍未校准。

当前本地行为检查覆盖重复 receipt 的 occurrence、Agent 子类的 control return、任何 invocation 前的全量 original-owner lookup、Reply 的真实 routine sender、own history 前缀只拼接一次，以及 caller composition 的每个 own batch 只执行一次。它们服从现有 typed/严格 JSON/finite tree 合同；不改变完整 GIVEN、batch 合法工具域、caller 隔离语义或时间预算。
