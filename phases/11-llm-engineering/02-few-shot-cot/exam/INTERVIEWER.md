# 面试官手册：CoTBallot（11/02）

候选人计时期间不要看。候选人手里只有 README、`cotballot/` 和 `tests/`。

## 开场（2 分钟）

- 总时长 60 分钟，含开场 2 分钟。请候选人边做边说明想法，可以提问、查官方文档。
- 五关参考时长为 10、12、12、13、11 分钟，合计 58 分钟。记录变绿时间、pytest 次数和提示次数。
- 不代写；卡住约 5 分钟后，一次只给一级提示。时间分配未经真人校准。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 如何兼顾相似度、难度和标签？ | "Use the declared local ranking, take the best example per label first, then fill from the remaining ranking." |
| 1 | 零个示例和 None 呢？ | "Zero means none. None uses three. The correct helper is already supplied." |
| 1 | 没有终值标记时取最后一个数字吗？ | "No. Only the last nonblank marked line supplies a final answer." |
| 2 | 更新旧 id 会换位置吗？ | "No. Keep the example's original corpus position." |
| 2 | 答案能先转数值存吗？ | "No. Preserve the exact answer text, reasoning and other fields." |
| 3 | 支持科学计数法和单位吗？ | "No. Use only the finite grammar in normalize_answer's docstring." |
| 3 | 1/3 和很长的 0.333 算同一票吗？ | "No. A finite decimal is not exactly one third." |
| 3 | 弃权算进 confidence 分母吗？ | "No. Confidence is the winning vote count divided by valid extracted samples." |
| 3 | 平票怎么选？ | "Choose the numerically smaller exact value. Emit vote keys in numeric order." |
| 4 | 无效答案还输出事件吗？ | "Yes. It is still an attempted sample, with a null answer." |
| 4 | 最后还有 summary 吗？ | "No. Emit one event per sample, and nothing for an empty source." |
| 5 | 找到一个答案就停止吗？ | "No. Inspect every supplied branch, even children of a node that already contains an answer." |
| 5 | 共享节点怎么算成本？ | "Include it in every terminal path where it appears, but bill its id only once globally." |
| 5 | 节点 id 在另一条分支出现就是环吗？ | "No. Only repetition on the current ancestor path is a cycle. Conflicting records for one id are invalid." |

## 每关：要看什么、提示、追问

### Part 1 修示例流水线（目标 10 分钟）

四层缺陷：

1. selector 返回 `answer` 字符串，丢掉完整示例。错误到 `ExampleService.preview → build_cot_prompt → format_example` 才报 TypeError；formatter 本身需要 question、reasoning、answer。
2. extractor 取回复里第一个算术数字，忽略最后一行的明确答案。中间的 48 不能代替 `$-1,200.50`。
3. formatter 只输出 question 和 answer，没有 worked reasoning。本课正是靠 reasoning 把普通 few-shot 变成 few-shot CoT。
4. 同一个问题选 K 个槽位时，每个槽位都对整个 corpus 完整评分排序。修为每个 query 评分一次，再按标签覆盖和排名选取。两边的固定 corpus token 预处理都已给定；这不是“缓存 corpus token”的题。

性能测试选 6,000 条示例中的 160 条。本机三次慢版约 0.709–1.197 秒，参考版约 0.0065–0.0077 秒；限值 0.075 秒。防过修断言保留标签多样性、难度顺序、改变 query 后的结果，以及每个请求槽位的完整记录。

提示：H1 "What did the selector return to the formatter?"；H2 "Does a worked example consist only of an answer?"；H3 指向 selector 的 record projection。

追问："Why not just take the first K ranked examples?"（标签覆盖会丢失）；"What happens when the query changes?"（不能复用另一个 query 的结果）。

### Part 2 示例库（目标 12 分钟）

坑：

- answer 是原始词面，不做 float、分数或千位分隔符归一。`1/3`、长有限小数和带前导零的答案都要原样保留。
- 更新旧 id 保留原 seq。用 replace 删除再插入，会把旧示例移到最后。
- reasoning 的 CRLF、Unicode、label 和 difficulty 都是示例的一部分；不能只存 question/answer。
- 写完关库重开还要读到同一序列。空字符串 label 是精确筛选条件，不是“没有筛选”。
- 记录恰好有六个字段；缺字段或多字段都拒绝。difficulty 必须是非负整数，bool 不算；非法更新不能改变已有示例。

提示：H1 "Which representation belongs in the corpus?"；H2 "Did the update change the example's position?"；H3 指向独立 seq 与 id。

追问："When should numeric normalization happen?"（投票阶段；原始示例和回放证据保留词面）。

### Part 3 精确 self-consistency 投票（目标 12 分钟）

坑：

- 用 Fraction/Decimal 保持精确值。`+024`、`24.00` 合票；`1/3` 与任意有限 0.333… 不合票。大整数不能先过 float。
- 有限 grammar 必须完整匹配：坏千位分组、单位、指数、NaN、零分母都弃权。分数的分子、分母也要先验证千位分组，不能删逗号后再验证；终值标记必须占据整个末尾非空行。
- confidence 的分母是有效答案样本，不是所有尝试；原始 reasoning 和 raw lexeme 仍全部保留。
- 零值有效，不能靠 truthiness 过滤。平票选数值较小值，不能按字符串或出现顺序。

提示：H1 "Are these spellings the same exact number?"；H2 "Which samples contributed a vote?"；H3 提醒 exact fractions 和有效计数。

追问："Is 0.75 confidence a calibrated probability of correctness?"（不是；这里只是有效样本的票份额，相关错误可同时出现）。

### Part 4 累计 ballot 事件投影（目标 13 分钟）

坑：

- 把当前原始 reasoning 恰好追加一次，再从完整批内 history 取累计 ballot。不能每条事件重置历史。
- index 是 attempted；无效提取仍对应一个事件。当前 sample 的 answer 与累计 winner 分开，投票分布保留全部答案，不能只报赢家的票。
- confidence 是有效样本的票份额，不变成百分数；sample_id/text 原样保留，JSON 内转义文本换行，外面只有一个终止 LF。
- source 的逐条拉取、完整事件发布、空源行为和 early-close ownership 全部正确 GIVEN。候选只实现同步 ballot_event；no-read-ahead、丢事件与关闭 wrong 验证给定驱动的集成边界。

提示：H1 "Is this the current sample's answer or the cumulative winner?"；H2 "Which counter gives this event's position?"；H3 核对 attempted、valid、完整 votes 与原始 text 的不同职责。

追问："What changes for very large sample batches?"（增量维护计数，避免每次重算全历史；本题只模拟保留完整历史的短 self-consistency 批次）。

### Part 5 核对给定 ToT 轨迹（目标 11 分钟）

这里不实现搜索、不挑分支，也不调用 evaluator。节点与用量已经给定。

坑：

- 每个有合法终值的节点都贡献一条路径，低 score 分支和其他兄弟不能消失；有答案的节点仍可能有已记录的子节点。
- 路径用量包含祖先；全局用量按实际 node id 去重。非终值叶子也已经消耗 generation/evaluation 调用。
- 一个节点按本地 trace 合同代表一次 generation 加一次 evaluation，共两次调用；tokens 是这两次给定的总 token 字段。
- 共享节点要出现在每条相关路径；当前路径中重复 id 才是环。同 id 的矛盾记录拒绝，不擅自择一。
- 给定 score 必须有限且在 [0,1]，token 数必须是非负整数，bool 不能作为 token 数；校验轨迹字段，不重新执行 evaluator。

提示：H1 "Are you reporting paths or counting unique executed nodes?"；H2 "Did the pruned branch consume calls before it stopped?"；H3 提醒分开 path 和 global seen。

追问："Does a matching selected answer prove the reasoning is correct?"（不证明；这里只核对终值一致性与账目）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 沿调用链核对记录形状、一次修一层、局部重跑 |
| 代码质量 | 15 | 保留词面与精度、清楚的边界、无凑测试代码 |
| 沟通 | 15 | 主动澄清 grammar、平局和分母 |
| 生产意识 | 10 | 版本顺序、有效样本、背压、成本范围和回放限制 |

每项写具体观察证据，没观察到就写“未观察”。
