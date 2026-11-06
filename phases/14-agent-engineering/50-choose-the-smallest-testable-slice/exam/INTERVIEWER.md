# 面试官手册：SlicePick（14/50）

候选人计时期间不要看。候选人手里只有 README、slicepick/ 和 tests/。

## 开场（2 分钟）

说明 60 分钟，一次解锁一关，测试原样通过。请候选人说明证据资格、取舍和取消边界，不要求生产部署。可以问澄清问题，卡住时逐条给提示。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | Are empty required proofs valid? | No. The supplied helper rejects empty or blank proof requirements. Extra offered proofs are allowed. |
| 1 | What is candidate identity? | The unique Candidate.id. Two candidates can have identical Slice values and still be separate alternatives. |
| 1 | How do score ties resolve? | Higher score, lower effort, then lexicographically larger slice name and candidate id. |
| 2 | Should the score be recomputed when loading? | No. Preserve the exact stored selected_score, raw evidence and selected id. |
| 3 | Is every UI mock a false minimum? | No. A UI mock may test comprehension. In this exercise ui-only blocks when the declared need includes real data. Use the explicit Design fields. |
| 3 | What makes a stop rule effective? | Every result has a nonblank action, and at least one normalized action differs from keep building. Other nonblank domain instructions are allowed. |
| 4 | What happens after the error limit? | Emit the current measurement, then the failed decision, then return without pulling another observation. A correct outcome resets consecutive errors. |
| 4 | What does EOF mean? | After any evidence use rule.passed with reason complete; with no evidence use rule.ambiguous with reason no-evidence. These are controlled pilot rules, not statistical inference. |
| 5 | What counts as missing? | Every unbuilt node on a connected trigger-to-first-outcome path, including endpoints. Tie-break by the full node-id tuple. |

## 每关：要看什么、提示、追问

### Part 1 修切片决定（目标 12 分钟）

一个测试叠了四个缺陷：

1. score 内接受零 effort，在同一函数的分母运算出现 ZeroDivisionError，正确行为是正 effort 校验的 ValueError。
2. score 内不可逆与可逆 consequence 惩罚系数颠倒，分数交给上一层 choose 后，表现为选错 candidate id；这是真实的 producer/consumer 跨层缺陷。
3. alternatives 按 Slice 值过滤，丢掉内容相等但 id 不同的候选。
4. 宽 proof tuple 对每项 required 重新线性查找。

看什么：是否修上游前提、保持资格先于打分，区分值与身份。非空 proof 和类型 helper 从起始正确给出，不是候选人主缺陷。

提示：
- “Which function first violated the scoring precondition?”
- “Did the two candidates become the same decision because their payloads match?”
- “Can membership comparisons use one representation without rewriting the raw evidence?”

追问：公式为何不是通用成本模型？风险评分不能替代哪些资格证明？

### Part 2 决策快照（目标 10 分钟）

坑：
- selected_id 绑定实际候选身份，不能凭相等 Slice 猜一个。
- selected_score 原 float 位值及 signed zero，不能重新打分或格式化缩短。
- 原 proof 元组次序、重复项与原文，StopRule 多行文字。
- 嵌套 dataclass/tuple/bool 恢复及保存前拒绝未知 id。

看什么：是否把比较用归一化与原始证据分开。正确 atomic_json helper 直接可用，不再考事务提交或 rename 顺序。

提示：“What would a reopen need to reproduce the exact recorded decision?”

追问：如果多个 writer 并发写同名快照，当前 helper 哪些保证不成立？

### Part 3 false minimums 与停止规则（目标 12 分钟）

坑：
- 相对于 ProofNeed 判，不把 UI 形式本身判死。
- 同一设计可触发多类，全部按固定次序报告。
- 缺 proof、false minimum 或无有效停止规则的设计不进入打分。
- pass/fail/ambiguous 都要行动，但只需至少一个改变“keep building”。

看什么：是否从明确字段处理证据需要，而非猜自由文本。

提示：“What uncertainty was removed to make this slice look small?”

追问：一张 synthetic dashboard 能证明什么，不能证明什么？

### Part 4 在线 pilot（目标 12 分钟）

坑：
- 连续错误，正确结果清零，不是总错误数。
- 每份 measurement 立即输出，触发时先 measurement 再 decision。
- terminal decision 后不多读，yield 后取消也不预取。
- 有证据的 EOF 与没有证据的 EOF 使用不同声明行动。

看什么：是否以可观察顺序检查源拉取与事件边界。SSE 编码由正确 helper 提供。

提示：“What can the consumer see before the next observation is requested?”

追问：为何这个 guardrail 不足以证明 pilot 达到 outcome？

### Part 5 最少补全工作流（目标 10 分钟）

坑：
- 代价是未建节点数，不是路径总长度。
- trigger/outcome 也算节点，不能拼接互不连通的已有片段。
- 完整路径字典序平局，不能按邻接输入顺序随意选。
- 到第一个 outcome 停止，不把无关已建节点塞进输出。

看什么：是否把连通性与最小证据链一起建模，重用给定 DAG 校验。

提示：“Does this proposed slice actually connect a trigger to an observable result?”

追问：若节点代价不同或边也有部署成本，状态应怎样扩展？

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 调试与取舍 | 25 | 前提、系数、身份和复杂度 |
| 精确持久化 | 15 | typed snapshot 与原始证据 |
| 证据算法 | 25 | 相对 proof need 与停止规则 |
| 在线边界 | 20 | 顺序、终止、EOF 和取消 |
| 结构与沟通 | 15 | 最少连通补全与清楚说明 |

记录每关用时、提示次数与实际证据；未观察到的能力写未观察。
