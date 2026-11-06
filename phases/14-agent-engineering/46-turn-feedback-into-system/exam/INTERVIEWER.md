# 面试官手册：Promote（14/46）

候选人计时期间不要看。候选人只有 README、`promote/` 和 `tests/`。

## 开场（2 分钟）

- 说明 60 分钟，请边做边讲，可澄清、可查官方文档。
- 记录各关时间与 pytest 次数，约 5 分钟卡住后一次给一级提示，不代写。
- 原因、候选覆盖关系和有效 owner 是题目给定的调查结果，不要求自然语言理解。

## 澄清问题的标准答案

只在问到时，用英文回答。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 同样的两条输入算重试吗？ | "No. Each is an independent observation and its recurrence count adds." |
| 1 | 一条一次性的严重更正呢？ | "Promote it. Consequence can justify a control before recurrence does." |
| 2 | save 接收增量还是快照？ | "A complete snapshot. Saving it twice must not double its count." |
| 2 | 存储会拒绝空白 owner 吗？ | "No. This store preserves values; ownership policy is checked before it is called." |
| 3 | 怎么知道候选控件真的能处理原因？ | "The investigator supplies covers and verified. We do not infer causality from prose." |
| 3 | 一个症状对应两个原因呢？ | "Keep both causes and choose a control for each." |
| 4 | 窗口最左端的观察还在吗？ | "No. Window is supplied correctly and uses (now-width, now]." |
| 4 | 提升以后证据过期要撤回吗？ | "No. Promotion is permanent for this view. Retirement needs a separate evidence review." |
| 5 | 深层原因都没有有效 owner 呢？ | "Use the deepest effective owned cause, including an ancestor. If none exists, raise ValueError." |
| 5 | DAG 有环吗？ | "No. Inputs are acyclic; shared nodes may appear along different paths." |

## 每关：要看什么、提示、追问

### Part 1 更正提升（目标 12 分钟）

五层缺陷：
1. product disagreement 落入 instruction 默认层。错误在 ratchet 结果才暴露，根因是两层以下的 choose_target，不能把产品分歧自动写成指令。
2. recurrence 为 1 的普通偏好也被提升；永久复杂度需要复发或严重后果。
3. 内部多空格使同一原因生成不同指纹。原课已有 lowercase；这里预埋的是有限空白归一规则，显示文本不能跟着改。
4. 同指纹后条覆盖计数，而不是把独立观察次数相加；严重后果应保留。
5. 每加入一个分组就重排整个已有集合，批量提升是平方级排序。4500 条更正限值 0.12 秒，慢版三次 2.050、2.066、2.379 秒，参考 7.761、7.468、7.665 毫秒，双侧至少 8 倍余量。

护栏：先合并再判门槛，第一条原始 cause/symptom 不变，严重首次能提升。观察次数不是请求幂等 id，不能按内容去重。

提示：
- H1："Which owning layer did the correction lose on the way through ratchet?"
- H2："Compare the canonical identity and the original evidence separately."
- H3：指出 choose_target、_eligible、grouped 更新和循环里的排序。

追问："When should a one-off correction still become a control?"（严重后果足以支付永久复杂度；不是所有偏好都进规则。）

### Part 2 棘轮记录（目标 10 分钟）

坑：
- save 写入的是已经累计的完整快照，不能当新更正再次相加。
- Control 及 Record 类型、symptom/cause 原文、review_date 和 owner 全部读回，不能只存 rule 和 fingerprint。
- 按 owning target 查询，不根据显示 rule 再猜目标。

顺带检查关闭重开、整数计数、Unicode/换行/制表符。类已经给出 schema 初始化与 close，提交和 SQL 引号不作为主坑。

追问："Why keep the original cause as well as a fingerprint?"（摘要用于身份，原文用于复核观察和以后重判归属。）

### Part 3 原因与症状（目标 14 分钟）

坑：
- 按原因分组，不能把相同症状的不同原因合并。
- 候选必须 verified、覆盖此 cause，而且不能只复述任一症状。
- 在有效候选中选最早有效层，平层按 id；没有有效候选保留 None。
- 产品分歧必须是 human 候选，不能因 executable 层排序靠前就抢走人工选择。

covers 是显式原因键，层次顺序是本题给定的有限政策，不证明真实因果或所有风险都按同一全序治理。

提示：先按 cause 建组，再审候选资格，最后排序。

追问："How would a team establish verified in practice?"（用可重放场景证明控件能预防相应失败，保留证据与负责人。）

### Part 4 在线提升（目标 12 分钟）

坑：
- severe 观察首次就发；不能一律等待 recurrence threshold。
- 某原因提升后继续处理其他原因，不结束整个观察流。
- 提升记录必须在拉取下一条观察之前发出，消费者关闭后不能预读未来输入。

自定义 threshold 同样决定触发的那条观察，不能固定为默认的 2。窗口累计由正确 Window 提供；同因只提升一次的护栏保留。输出由 _line 给定，每个事件一份 SSE 记录，不要求外部服务。

追问："Does an expired observation retire a control?"（不会，退役还要有意味明确的窗口、复审和证据。）

### Part 5 为什么图（目标 12 分钟）

坑：
- 只在 effective 且有 owner 的原因放控件，祖先仍可能是最深的有效位置。
- 深度按路径计算，同一共享节点从深路径抵达时也要考虑，不能用一个全局 visited 忽略它。
- 同归属原因合并原始症状并去掉相同症状的重复观察；不同 owner 不能混为一个控件。
- 同深度按原因名、owner 排序；没有任何有效归属时报 ValueError。

输入图只读，不能为排序结果原地重排 why。它是一张已标注的原因 DAG，不推断谁有真实组织授权。

追问："Does deeper always mean a better causal explanation?"（不；本题显式 effective 先筛选，深度只是已接受模型里的选择规则。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分 |
| 调试方法 | 20 | 沿结果找源头、看真实字段、逐层重跑 |
| 代码质量 | 15 | 身份/证据、资格/排序、窗口/流控制分开 |
| 沟通 | 15 | 主动澄清并解释永久复杂度 |
| 生产意识 | 10 | 归属证据、严重后果、复审和退役 |

记录具体证据；没观察到写“未观察”。提示和用时另记。
