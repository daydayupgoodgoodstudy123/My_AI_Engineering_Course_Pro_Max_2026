# 面试官手册：EvalPair（11/10）

计时期间不展示。开场 2 分钟，五关 12、12、14、10、10 分钟，合计 60；未经真人校准。允许澄清、查标准库文档、边做边解释；卡住约五分钟时只给一级提示。

## 澄清问题标准答案

| 关 | 问题 | 英文回答 |
|---|---|---|
| 1 | judge 是在线模型吗？ | "No. The injected local fixture returns a complete EvalScore, including reasoning and max_score." |
| 1 | empty rubric/reference？ | "None selects the default rubric; an empty rubric requests no scores. A missing or empty reference has a zero ROUGE-L metric." |
| 1 | word token 规则？ | "Use source lowercase split tokens, retaining punctuation and repeated tokens." |
| 2 | 精度在哪里？ | "Keep raw score decimal spellings and raw text; unjudged None is not numeric zero, and a missing reference is not an empty reference." |
| 2 | 能覆盖 run 吗？ | "A run id is immutable. This local format makes no crash-atomicity or concurrent-writer claim." |
| 3 | 按什么配对？ | "Match exact case_id/criterion keys and category assignments before sampling. Every compared score must be judged." |
| 3 | category 的单位？ | "First average matched criterion differences within each case, then resample cases. Each group starts a local Random(seed)." |
| 3 | 什么时候 block？ | "Block if any criterion or category interval upper endpoint is below minus tolerance. Overall improvement cannot override it." |
| 4 | missing judge 是 failure 吗？ | "No. It is skipped; runtime error, failed judge and passed judge are distinct outcomes." |
| 5 | 再跑 bootstrap？ | "No. Report same-case, same-criterion coverage and carry each category's supplied comparison evidence and original path unchanged." |

## Part 1 typed judge 与 ROUGE-L（12 分钟）

坑：
- producer 过早把 EvalScore 转成 dict，正确 EvalResult.average_score 读取 s.score，在 producer 外一两次调用报 AttributeError。保留完整 typed score 到内存边界，reasoning/max_score 不丢。
- set overlap 不是 ordered LCS，反序相同词汇和重复 token 都必须按 source ROUGE-L 处理。
- `//` 把合法半分均值截断；empty scores 的 0.0 已正确给定，不新增 truthiness 缺陷。
- naive LCS 重复计算相同后缀子问题。真实完整 metric request 必须保留 tokenization、序列语义和输出，不能给所有不相等文本返回零。

计时合同：两条 13×13 的真实 word-token 序列，一条全不相交，一条只有双方中间各一个 shared token，完整 EvalService.evaluate（empty rubric 已正确给定）在 timer 内；全输出保留。完整最终连续三慢 2.057934/2.013349/2.061825 秒、三快 0.000027834/0.000027459/0.000027709 秒，限值 0.08 秒，双侧余量 25.17/2874.19 倍；所有功能 guards 与两条完整输出保留。完整外部证据 `/tmp/exam-11-16-work/draft11-10/timing-final`。仅给 disjoint fastpath、其余仍递归的真实错修耗时 1.1305 秒，已被同一限值抓住。None/empty 和 criteria None/[] 的正确边界已给定。H1 "What type reached average_score?" H2 "Does equal vocabulary imply equal sequence?" H3 指向 producer、真除法和 LCS 状态。追问：能否从 fixture 分数推断模型质量？（不能。）

## Part 2 evaluation bank（12 分钟）

坑：
- CSV quoting/multiline 字段必须保留一个 observation，不能逐物理行分割原输出。
- score decimal spelling 不经 float 重新格式化，reference present 与 empty、score None 与 0 分别保留。
- immutable run 的 metadata、原 row 顺序与独立 prompt version 不串；不能排序后当成原历史。seed 可超过 binary64 的精确整数范围，不能经 float；raw input/output 首尾空白也保留。

H1 "Which values are data rather than delimiters?" H2 "Can a numeric round trip keep the original spelling?" H3 指向 CSV writer/reader 与显式 presence 字段。追问：是否保证断电原子性？（没有这个承诺。）

## Part 3 paired stratified bootstrap（14 分钟）

坑：
- 先以完全相同 case/criterion 键配对，再对差值有放回采样；不把独立两次 run 当成配对，不按 row 位置 zip，也不能仅打乱样本后无放回取遍。合法微小差值不能提前 round 成零。
- criterion 自己按 case 采样；category/overall 先在 case 内平均，避免 rubric 多的 case 获得更多票。每 group 用独立相同 seed 的 Random，端点合同见 docstring；小 B/低 confidence 时 upper index 至少是 lower index，不能产生倒置区间。
- adverse category 的完整 interval 必须保留，判定看 criterion/category 的 upper endpoint 与 tolerance；overall improvement 不遮蔽它。

空 run 无 interval；缺键、缺 judge、category 改动先拒绝。H1 "What is the sampling unit?" H2 "Which scores share a case?" H3 指向 pairing、case-level delta 与 category decision。追问：bootstrap 是否保证真实部署效果？（不保证，本题只有明确的有限统计合同。）

## Part 4 completed JUnit XML（10 分钟）

候选实现同步 `encode_testcase(result)`，一次仅消费这一条 CompletedCase。suite envelope、completion 拉取与当前结果发布、绑定和关闭全由正确 GIVEN driver 负责；candidate 没有跨 case cache 或 async loop。

坑：
- case_id/category 的 XML attribute 与 output/reference/message 原文本都是数据，不能手拼、反转义或预转义而改变还原后的值。
- 构造完整 testcase 属性，system-out 用字段身份正确的 JSON text 保留原始 output/reference；Python repr、错字段或丢原始 payload 都不合格。
- 给定 kind/message 应落为恰当且唯一的 outcome 子节点，success 只有 system-out。不能漏 message、重复挂节点或改判 raw flags；四态分类与精确 seconds helper 均正确 GIVEN。

pending-case 可观察性、empty suite、关闭和完成记录的 driver 绑定由 integration guards 验证。buffer-all 与首次 identity 复用 wrong 在正确 driver 内验证，候选不修通用 cadence 或维护首 case 状态。H1 "Which XML fields and payload values must survive parsing?" H2 "Is this value text or structure?" H3 指向同步 testcase 的属性、JSON-in-text 与子节点。追问：source 已有这个协议吗？（没有，这是明确的本地报告扩展，不声称完整 JUnit runner API。）

## Part 5 paired coverage hierarchy（10 分钟）

坑：
- 同 category 中 baseline 与 variant 数量相等，不代表同 case/criterion 已配对；未配对两侧保留不同路径。
- 每 criterion 有自己的 paired count，不能从 category total 广播或跨 case 借一个 score。None≠0 是 integration guard，主核是明确配对关系。
- 所有 declared category 保留原顺序及已有 comparison evidence/path，包括不利 category、全无 judge 或没有 case 的 category；不因 favorable overall 抹掉原 evidence。每个 criterion 使用自己声明的索引，第二个不能沿用第一个的路径。

catalog/id/shape helper 正确 GIVEN。P5 不 resample、不做 gate、不算分数均值树、不引权重政策。H1 "Which exact key has both sides?" H2 "Where did this category evidence originate?" H3 指向 pair coverage 与原 evidence path。追问：source 本来有树算法吗？（没有；TestCase.category 与 EvalResult.scores 的有限层级是明示教学适配。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，原测试通过即得 |
| 调试方法 | 20 | consumer 类型、序列反例、逐层验证和性能证据 |
| 代码质量 | 15 | 保留文本/精度/必要工作，统计采样单位清楚 |
| 沟通 | 15 | 主动澄清配对、缺测、category 和有限报告合同 |
| 工程判断 | 10 | 区分本地证据、统计合同和真实模型/部署证明 |

未观察写未观察；提示、变绿时间与复盘后补完分开记录。
