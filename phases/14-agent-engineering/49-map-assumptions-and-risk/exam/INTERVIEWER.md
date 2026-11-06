# 面试官手册

## 开场

“You have 60 minutes. Work through the five locked tests in order. Keep the assertions unchanged, and talk through evidence, decisions and boundaries as you go.”

场景是从路线图里拆出假设：有材料不代表得到支持，被否定的前提也不能继续当可构建前提。代码为本地小服务，无真实实验平台。

## 澄清问题标准答案

| Candidate question | Standard answer |
|---|---|
| What does evidence mean? | Supports and rejects are explicit verdicts. Inconclusive or absent evidence leaves the assumption open. Do not infer verdicts from text. |
| What is the ranking tie-break? | Higher example risk score first, then lexicographically smaller unique id. Rank all assumptions, but select experiments only for open ones. |
| Which timestamps matter? | Registration must be strictly earlier than the earliest observation in the first N arrivals, even for a partial batch. Compare aware instants, preserve the raw strings in storage. |
| What happens to uncertainty? | A decisive result lowers uncertainty by one down to one; ambiguous evidence leaves it unchanged. This is an exercise rule. |
| Which samples count? | Only the first sample_size arrivals for that experiment. Later observations cannot revise a complete batch. |
| What does the stream emit? | One supplied logfmt line per completed experiment, immediately. At EOF emit partial and empty batches in declared order. Stop pulling once every declared experiment completes. |
| What is the tree language? | A known id leaf, or a nonempty all/any group. The docstring gives three-valued rules; this is a finite exercise extension, not natural-language inference. |

## 每关：要看什么、提示、追问

### Part 1 修假设图（目标 12 分钟）

一个测试里叠了四个缺陷：

1. 证据 producer 丢弃 reject 极性，`map_decision → ranked_rows → evidence_status` 的错误最终出现在上层 build action。
2. 修好后 chooser 又把 rejected 当未决。
3. 下一实验与公开排名的同分规则不同。
4. 逐项比较所有其他项生成 rank 造成平方开销。

看什么：是否顺着上层错误决定查到 producer，并逐层验证，不删掉有反面证据的行。

提示：“Which layer determines whether this evidence supports the premise?”；“Does a rejected claim need another build experiment?”；“Can the ranks come from one ordered pass?”

防过修：排名保留 supported/rejected；inconclusive 仍 open；输入顺序不变，空图合法。正确整数与风险公式 helper 已提供，bool/float 只是护栏。

追问：为什么得分高不自动意味着现在可以构建？如何在真实环境校准这三个维度？

### Part 2 保存预注册表（目标 10 分钟）

坑：
- CSV 里 None 与空证据不同，包括 Evidence('','')。
- 阈值 float 精确值及 signed zero。
- 原始多行 Unicode、边缘空白和时区字符串。
- 保存替换两个表而非追加。

看什么：是否先确认精确往返的声明类型与原文边界。

提示：“Could reading this table reconstruct the same dataclass and exact threshold?”

追问：本题不承诺两文件原子事务，生产里如何处理只写完一表的故障？不要要求候选人实现未给定的事务。

### Part 3 判定实验（目标 12 分钟）

坑：
- 注册时间要早于首份结果而非最后一份，partial batch 同样检查。
- 以真实 instant 判断时区与等时。
- 样本不足应 ambiguous 且不改 uncertainty。
- 两个方向都含等号，只取首 N 次到达。
- 负证据对应 fail action。

看什么：是否区分证据不足与已经否定。

提示：“Could this threshold have been chosen after seeing one observation?”；“Is this insufficient evidence or failing evidence?”

追问：本题的平均数与减一规则有哪些限制？不要把有限样本判定说成因果证明。

### Part 4 在线决定（目标 12 分钟）

坑：
- 完成一个实验就发，不能等整个输入。
- 所有实验完成后不再拉取。
- EOF 对未满/零样本给 ambiguous，顺序按声明而非 id。
- yield 后关闭不预取。

看什么：是否以消费者可以看到的事件与 source 拉取边界检查实现。SampleBook 已正确管理独立累计、首 N 冻结和一次报告，编码 helper 已正确给出。

提示：“What should the consumer see before the next source pull?”

追问：如果观察源必须显式释放连接，接口还应如何表达资源所有权？本题只检查不多读，不要求替调用方关闭其源。

### Part 5 复合假设（目标 10 分钟）

坑：
- ALL 与 ANY 的三值规则不同。
- 已决定的子树不能贡献高风险候选。
- 仅 open 根选择能影响结论的 open 叶。
- 风险同分稳定且不改输入。

看什么：是否把状态与可影响根的候选一起递归返回。

提示：“Can changing this open leaf still change the root?”

追问：共用叶多次引用为何不需要重复实验？若引入因果依赖或概率，哪些当前假设不够？

## 评分

| 维度 | 分值 | 观察 |
|---|---|---|
| 调试与复杂度 | 25 | 找到 producer/consumer 契约，保留排名语义 |
| 精确持久化 | 15 | 类型、原文、阈值及替换语义 |
| 实验判定 | 25 | 预注册、方向、模糊证据和行动 |
| 在线边界 | 20 | 及时输出、终止、EOF 和取消 |
| 复合结构与沟通 | 15 | 三值逻辑、有效下一实验和边界说明 |

参考实现只是一种解法；允许等价实现通过原样测试。
