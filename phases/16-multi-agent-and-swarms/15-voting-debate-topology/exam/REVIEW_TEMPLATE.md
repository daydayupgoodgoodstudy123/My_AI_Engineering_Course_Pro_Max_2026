# 16/15 CorrJury 复盘

- 日期／第几次：
- 模式：独立计时／有人主持／关闭答案后的重做
- 开始／结束时间；是否按 2 分钟开场 + 58 分钟编码：
- Python 版本与环境（实际观察，不推定）：
- 看过的材料、澄清问题、用过的帮助：
- 是否打开答案；若打开，何时开始，哪些结果属于计时后：

## 过程记录

| 关 | 预算 | 解锁时间 | 首次完整结果 | pytest 次数 | H1/H2/H3 | 卡住的具体行为与证据 |
|---|---:|---|---|---|---|---|
| 1 shared replay | 12 分 | | | | | |
| 2 JSON snapshot | 11 分 | | | | | |
| 3 exact law | 15 分 | | | | | |
| 4 TSV fields | 10 分 | | | | | |
| 5 nested model | 10 分 | | | | | |

## 按当前职责评分

每项写具体代码、输出或断言证据；未观察到写“未观察”。参考模式与计时后补完单独记。

| 关 | 分项上限 | 实得 | 证据／尚缺行为 |
|---|---|---|---|
| 1（20） | shared draw/provenance 6；strict majority 4；read/generation cost 4；exact ticket 与完整回放 6 | | |
| 2（20） | ordered family 8；exposures/rates 6；snapshot reopen 4；Given codec 集成 2 | | |
| 3（25） | 两点 kernel 8；convolution 9；unit-mass/tail 6；reopened config/cost 2 | | |
| 4（15） | own identities/outcome 5；observed tally 4；costs/simulated 6 | | |
| 5（20） | integer family counts 8；逐层 model/P3 复用 6；child audits 3；exposures/cost 3 | | |
| 合计（100） | | | |

## 逐关回看

- Part 1：是否从 `seal_sample → require_shared_family_draw` 的合法报错追到上游？同 family 的全部 seats 是否保留同一个 draw ordinal？五票两票为何失败？ticket cutpoint、RNG 消耗、raw outputs 和费用是否保持一致？
- Part 2：重开后是否恢复全部 family 的 probability/seats/tokens、全部 exposure 的 labels/tokens 与两种 rate？相同 opaque labels 的不同 allocations、声明顺序和替换 snapshot 是否完整？哪些工作由 Given codec/driver 完成？
- Part 3：shared seats 与独立 family 的随机单位是否清楚？kernel 的零位置、convolution 的乘法与索引、neutral distribution、deterministic seat offsets、unit mass 和 strict tail 分别如何核对？sampled tally 和 exact probability 是否混用？
- Part 4：十列分别来自哪个 completed report 字段？失败 trial、later trial、三种 cost 和 simulated provenance 是否保真？是否误把 Given TSV driver 当自己的算法工作？
- Part 5：同 family 跨层权重如何相加？每层是否重新构造真实 flat model 并调用 P3？为何 set union 和 child probability product 不成立？nonvoting wrapper 的 own path/config、own/child reads 与 ordered audits 是否完整？

## 证据与下一次练习

- 60 分钟时实际完成的行为／未完成的行为：
- 首个失败、根因、最小修复与回归检查：
- 问过的澄清问题／本应先问的问题：
- 对 family 相关性、exact law、declared cost 或嵌套组合的取舍解释：
- 残留临时代码、改变测试或绕过 consumer 的地方：
- 计时后补完（不计入原成绩）：
- 关闭答案后仍无法独立写出的函数：
- 备份位置／重做目录：
- 下次只改一个习惯：

## 当前证明范围

题包当前为42PY、五测试、36 assert、1 raises、五锁和26个登记错误写法。

128 个真实不同概率配置×3 seats 的完整 `JuryDesk.record_many` 与整个 `BatchReport` equality 都在计时内，fixture 和独立 Random/Fraction expected 在外。限值 0.04 秒；独占连续三慢为 0.401299125、0.408559500、0.405123583 秒，三快为 0.002162083、0.002134875、0.002089166 秒，慢／限值最小 10.03248 倍、限值／快最大值 18.50068 倍。

六份完整测量副本五关功能均通过：仅把 timing assertion 换成实际 elapsed 输出，慢版另外使用真实完整 ticket-deck 映射；不表示慢版满足原限值。未改动测试的完整参考五关也已通过。当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错误写法与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。

若自己运行，另记命令、工作副本、环境、完整功能输出与实际 elapsed；参考模式不能记作自己的完成。这些有限本机数据不构成任意环境墙钟上界、生产 SLA、真实模型准确率或供应商费用证明；60 分钟安排未经真人校准。
