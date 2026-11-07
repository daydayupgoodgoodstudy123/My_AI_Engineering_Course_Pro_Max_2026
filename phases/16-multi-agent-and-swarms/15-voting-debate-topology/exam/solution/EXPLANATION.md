# 参考答案讲解：CorrJury（16/15）

计时结束后再看。参考代码在本目录 `corrjury/` 中；在自己的作答副本可用 `python3 -m pytest --solution --all-parts` 检查参考模式，再关闭答案、去掉 `--solution` 重写。当前完整参考五关、固定校准组与独立行为复核有对应通过记录，规定 TEMP 检查已通过；正式检查已通过，记录见 verification.txt。

## 来源与本地模型

来源 `code/main.py` 的 `SimAgent.answer` 每次独立抽签；同一个 `error_bias` 只让错误答案标签相同，不产生共享正确性事件。`majority` 已用线性字典计数，概率比较也是常量时间。graph 只让少数转向既有多数，不能由此演示真实辩论收益、超线性 read cost 或时延。

本题把讲解中的共享 latent 练习形式化为有限 toy：不同 family 独立，同 family 全部 seats 完全共享一次 RIGHT/WRONG。exact integer ticket、完整 sampled report、声明 generation/read 费用、JSON 配置、精确 family law、TSV 与 nested jury 都是显式本地适配；预埋回归不表示来源同样有错。输出 artifact 只是来源数据，未执行其中 skill。来源论文、年份和 benchmark 叙述没有做当代外部核验。

## Part 1 真实 shared-family replay

第一个失败出现在正确的 `require_shared_family_draw` consumer。`draw_family_trial` 按 seat 独立取 ticket，`JuryDesk.record` 经 `seal_sample` 把这些 evidence 交给 consumer，于是发现同 family 使用多个 draws。不要删校验或把多个 draw 的 ordinal 硬改成一样；一次 `stream.take(family)` 和一次 category mapping 应先决定该 family 的结果，再向 `seat_ids(family)` 的每个 seat 发布同一个真实 ticket/outcome。

其后处理三个独立职责：

1. `sampled_jury_result` 统计本次真实 RIGHT seats；对合法正奇数 N，胜出阈值为 `N // 2 + 1`。这是一次观察的分类，不是成功概率。
2. `trial_cost` 分别计算 generation 与 reading。generation tokens 是各 family 的 `seats × generation_tokens` 之和；reading tokens 是所有声明 exposures 的 tokens 之和，分别乘自己的 rate，用 Given exact-money helpers 相加，保留原 exposures。reader/sender 是 opaque cost labels，不代表网络端点或真实传输证明。
3. 对 exact probability `a/d`，合法 roll 属于整数 `[0,d)`；成功区间为 `[0,a)`。因此 `roll < a` 与构造 a 个 RIGHT、d-a 个 WRONG 再索引同一 roll 完全等价。无需额外抽签、float 转换或分母长度的列表。边界 p=0、p=1、roll=a-1/a 都保持其数学意义。

完整 Given 包含 `seat_ids`、配置校验、actual replay ticket stream、shared-draw consumer、family outcome projection、service orchestration、exact money helpers 与独立 expected fixture。P1 不提供 P3 的 kernel、convolution 或 tail。

128 个真实不同概率配置×3 seats 的完整 `JuryDesk.record_many` 与整个 `BatchReport` equality 都在计时内，fixture 和独立 Random/Fraction expected 在外。限值 0.04 秒；独占连续三慢为 0.401299125、0.408559500、0.405123583 秒，三快为 0.002162083、0.002134875、0.002089166 秒，慢／限值最小 10.03248 倍、限值／快最大值 18.50068 倍。每个概率实际决定自己的 draw range 和结果，完整输入／ticket／votes／分类／费用均保留。

六份完整测量副本五关功能均通过：仅把 timing assertion 换成实际 elapsed 输出，慢版另外使用真实完整 ticket-deck 映射；不表示慢版满足原限值。未改动测试的完整参考五关也已通过。当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错误写法与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。

## Part 2 完整配置 JSON snapshot

`JuryArchive` 的职责是选择并恢复完整领域字段。参考实现保存 config UID；ordered families 中的 UID、exact probability、seat multiplicity、generation_tokens；ordered reads 中的 UID、reader、sender、tokens；相同 reader/sender labels 不会合并不同声明 allocations；以及独立 generation/read rates。load 用相同字段重建 typed records，并调用 Given validation。

一个 save 对应一份完整当前 snapshot。重开新 archive 必须与原配置相等；后一次 save 替换整份声明，不能留下旧 family 或 exposure，也不能排序改变声明顺序。family block 保留 seats，不拆成多次独立抽签。

完整 Given 已提供 Fraction 分子／分母字符串 codec、Decimal text codec、UTF-8 JSON 原子替换、load 与 close。候选人仍须接上所有真实字段和关联；精度、Unicode 与制表符是这些 helper 的集成护栏。这里只存配置，没有试验历史、provider pricing 或运行时模型恢复合同。

## Part 3 精确概率 law

### family kernel

对 k 席 family、成功概率 p，正确票数随机变量只取0或k：

```text
P(X=0) = 1-p
P(X=k) = p
P(X=j) = 0, 0<j<k
```

参考实现分配 k+1 个 exact Fraction 位置。三席同 family 不是三次独立 Bernoulli；即使观察到三张 RIGHT，其共同来源仍只有一次结果。p=0/1 时也保留完整支持长度和零项。

### independent-family convolution

初始 neutral distribution 是 `(Fraction(1),)`。每加入一个独立 family，对旧分布索引 i 和该 kernel 索引 j，把 `p_i * q_j` 加到新分布的 i+j。索引表示正确 seats 数，不是 family 数；概率相乘表达独立，累加合并得到相同正确票数的不同情形。

保留从0到总 seats 的全部位置，包括零；deterministic family 仍贡献固定席位，不能因无随机不确定性而从 law 中消失。三个独立单席 p=1/3 的完整分布为 `(8,12,6,1)/27`；同一个三席 family 的分布则为 `(2/3,0,0,1/3)`。二者严格多数概率分别是7/27和1/3。

### strict-majority tail

`exact_majority_reliability` 验证合法 config 和完整输入 distribution：长度 N+1、每项 exact 非负 Fraction、总和为1。阈值是 `N//2+1`，从该索引起求尾和，连同完整 distribution、配置 UID 和 corrected `trial_cost` 返回。

测试把 P1 的真实 sampled config 经 P2 保存、close、reopen 后交给这三个 solver。sampled result 与 exact reliability 不能互代；读取 exposure 只改变本模型的费用，不改变既定 family law。records、arithmetic helpers、validation 是 Given，三个概率算法均由候选人完成。

## Part 4 completed trial 的十列 TSV

`trial_fields` 只投影已经完成的报告。字段顺序为：trial ID、config UID、Given canonical family outcomes、observed correct seats、total seats、passed、generation、reading、total、simulated。

失败 trial 同样有自己的 tally 和费用，后续 trial 必须绑定自己的配置与结果。不要固定成功、替换身份、交换费用列，也不要重新采样或计算另一份分类。参考实现读取 report 的 own fields，以 `canonical_outcome_field` 和 `cost_field` 处理相应值。

`wire_support` 已完整实现 canonical outcome rendering、TSV quoting、每 report 发布和 async input close。测试使用实际 TSV parser 检查十列与嵌入制表符，并观察 close；这些是 Given 集成验证，候选人主要负责真实字段归属和证据保真。

## Part 5 nested shared-cause assembly

`JuryCatalog` 完整负责全局 family/node lookup、finite unique ordered tree expansion、path 和 profile-to-flat-config binding。候选人接收已解析 occurrence，需要为每个真实层级组装自己的完整模型；即使当前层没有 own seats，也保留自己的 path/config、read allocations 与 child audit。

参考实现先递归得到 ordered child audits，然后按 own allocations 与 children 顺序，把相同 family 的整数 seat counts 相加。family 的首次出现顺序保留；reads 先取当前 node 的，再依次接上各 child config 的完整 reads。由 catalog 构造当前层 config，再实际调用 P3 的 kernel、convolution 和 majority-tail，返回包含 path、family_counts、config、exact 与 children 的 JuryAudit。

例子中 root 自己有共享 family 一席，left 有该 family 三席，right 有另一个 family 三席。父层不是两个 child 的“成功票”，而是同一 family 四席、另一个 family 三席，共七席。其严格多数要求四席；概率 law 必须按这两个全局 cause 的真实权重组合。set union 会丢失四席权重，覆盖 child count 会改坏总票数，乘 child success probabilities 则替换了父层的事件和依赖关系。

测试确实先采样、保存并重开 family 配置，再把该实际 profile 用于 nested catalog。每层既保留自己的完整分布和费用，也保留 child audits。全局 family 身份相同表示共享 cause；不同 jury node 仍各有 path。这里复用 P3 law 和 P1 cost，没有第二套概率 solver，也不要求候选人实现通用 DAG／名称／循环处理。

## 这套题证明了什么，没证明什么

当前题包为42PY、五测试、36 assert、1 raises、五锁和26个登记错误写法。128 个真实不同概率配置×3 seats 的完整 `JuryDesk.record_many` 与整个 `BatchReport` equality 都在计时内，fixture 和独立 Random/Fraction expected 在外。限值 0.04 秒；独占连续三慢为 0.401299125、0.408559500、0.405123583 秒，三快为 0.002162083、0.002134875、0.002089166 秒，慢／限值最小 10.03248 倍、限值／快最大值 18.50068 倍。

六份完整测量副本五关功能均通过：仅把 timing assertion 换成实际 elapsed 输出，慢版另外使用真实完整 ticket-deck 映射；不表示慢版满足原限值。未改动测试的完整参考五关也已通过。当前独立行为复核的 6 项有效新方向均在指定目标关失败、其余四关通过，每项对应的新参考副本五关通过。规定原 TEMP 校验全部通过：默认五锁、参考五关、starter 五关失败、四层依次暴露、全部 26 项登记错误写法与重做副本均有对应记录。正式检查已通过，记录见 verification.txt；完整性能组、独立行为、TEMP 和正式归档仍按各自证据范围解释。

这些有限测试用于判断候选人在该有限域内是否完成 shared-draw debugging、完整配置 snapshot、精确 family kernel/convolution/tail、observed TSV projection，以及 nested integer-seat model assembly 的判断。P1 sampled majority 与 P3 exact tail 是各自职责；P4消费 Given classification，P5复用P3，不应重复宣称为独立算法实现。

本模型只覆盖二值结果、family 内完全共享、family 间独立和声明费用，不证明真实 LLM 准确率、经验相关性、模型多样性收益、真实辩论／拓扑效果、论文复现、网络传输、供应商计费或安全性。任何后续本机有限 workload 结果都依赖环境，不能推出任意规模墙钟上界或 SLA。60分钟安排尚未经过真人校准。
