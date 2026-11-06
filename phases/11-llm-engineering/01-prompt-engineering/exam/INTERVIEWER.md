# 面试官手册：PromptBench（11/01）

候选人计时期间不要看。候选人手里只有 README、`promptbench/` 和 `tests/`。

## 开场（2 分钟）

- 时长 60 分钟，请候选人一边做一边说出想法，可以提问、查官方文档。
- 目标是测试原样通过。记录每关变绿的时间、pytest 次数和提示次数。
- 主持时不代写；卡住约 5 分钟后，一次只给一级提示。

## 澄清问题的标准答案

只在候选人问到时回答，用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 变量值里的花括号还要继续展开吗？ | "No. Inserted values are literal text. Parse the template once." |
| 1 | 多出来的变量和空值呢？ | "Ignore unused keys. Zero, False and an empty string are supplied values." |
| 1 | 空 system 是没传吗？ | "No. Only None selects the default system message." |
| 2 | 相同正文、不同名字要存两份正文吗？ | "No. Share the content object, but keep both named revisions and their metadata." |
| 2 | 能覆盖同名同版本吗？ | "No. Raise ValueError. Unknown versions raise KeyError." |
| 3 | JSON 一定要是 object 吗？ | "No. Any complete value accepted by json.loads is valid here." |
| 3 | bullet 和编号列表怎么认？ | "Use the Python lesson heuristic in the docstring. Numbered lists need at least two matching lines." |
| 3 | 平分按 token 或延迟排吗？ | "No. Keep the input model order on a composite-score tie." |
| 4 | 一行对应一个 case 还是一个 model？ | "One row per model in each case, in input order. The header comes first." |
| 4 | 客户端停止后源怎么办？ | "Close it before client close returns. Do not fetch the next case early." |
| 4 | 响应里的 CR、CRLF 或首尾空格可以统一吗？ | "No. Preserve every field exactly, including bare CR, CRLF and surrounding whitespace." |
| 5 | 少了某项分数是不是零分？ | "No. Report count zero and mean None if never observed. A present zero participates." |
| 5 | 最弱项平分呢？ | "Use CRITERIA order, not alphabetical order." |

## 每关：要看什么、提示、追问

### Part 1 修 Prompt 构建（目标 10 分钟）

四层缺陷：

1. `bind_variables` 把声明名和 `variables.values()` zip。输入 dict 的插入顺序刻意与声明顺序不同，还含无关字段。根因在绑定函数；错值经过 `build_prompt`、`PromptService.preview` 消费后，在外层 prompt 断言才露出来。
2. 多轮构建只保留 user，丢掉 assistant 历史。空内容也是合法历史。
3. `system_override or default` 把明确传入的空串当成没传。只有 None 应选默认值。
4. 模板已被正确解析为 fragments，但渲染器每个字段都扫描并复制全部 fragments。4,500 个不同字段的慢版约 0.68–0.72 秒，限值 0.07 秒；一次按字段名 lookup/join 的参考版约 0.0005–0.0008 秒。

护栏：转义花括号与变量值里的 `{other}` 都保持字面；不能通过反复 format、清掉花括号或只返回部分字段提速。缺失键校验、brace parser 已给正确，零/False/空值不是缺失。

提示：H1 "Which function first associated each name with its value?"；H2 "Does input insertion order define the template contract?"；H3 指向 `bind_variables` 的 zip。

追问："What would invalidate a compiled template?"（模板正文或合同改变）；"Why preserve assistant turns?"（用户下一句可能引用先前回答）。

### Part 2 模板版本库（目标 12 分钟）

坑：

- 内容 hash 只代表精确 UTF-8 正文，不把名字或版本混进正文 hash。
- `read_text` 的通用换行处理会把 CRLF 改掉；正文应按字节写入、读回后解码。
- 同一正文可供两个名字使用，温度、description 和 system override 是各自的 metadata。
- 关掉重开后仍需有按插入顺序排列的全部版本；内存里的列表不算持久化。
- 显式空 system、None、负零温度要保留。读取时检查对象正文是否仍匹配 digest。
- variables 的声明顺序和 binary64 温度值都属于版本 metadata，不能排序或提前四舍五入。

提示：H1 "What exactly does the digest identify?"；H2 "Compare bytes before and after reopening."；H3 指出正文对象和清单的两个职责。

追问："What if a writer stops between the object and manifest writes?"（未引用对象可清理；清单替换要原子）。

### Part 3 Rubric 和模型比较（目标 12 分钟）

坑：

- 只对启用的四类 compliance 分量取平均；word_count、关键词列表不是分量。
- 关键词和 forbidden phrases 按大小写不敏感的子串匹配，不要求完整单词；空 required_keywords 覆盖率为 1。
- JSON 是完整 JSON 值，包括 scalar、null 和 list；带代码围栏或尾随文字不通过。
- 本题沿用源 Python 的 format heuristic。编号列表至少两行；bullet 规则和空文本行为写在 docstring 里，不能换成自己更喜欢的格式定义。
- 排名按 composite 降序，平分保持输入模型顺序；token 和 API latency 保留原值。

提示：H1 "Which values are rubric components?"；H2 "What denominator changes when only max_words is enabled?"；H3 指向 CRITERIA。

追问："Does a high composite prove a better model?"（只是本地规则符合度，不能代替质量评估）。

### Part 4 CSV 模型评分投影（目标 14 分钟）

坑：

- 对当前 case 使用其自己的 criteria，按输入 model 顺序构造行；compare_models 返回的排名是另一份视图，不代替回放顺序。
- 同一个 model 的原始 response、composite、tokens 和 API latency 要对应，不能把 case 总 token 填进每一行，或把毫秒改成秒。
- 零 token、零 latency 和空 response 都是合法回放值，仍保留该模型完整行；不修改源 case 或评分结果。
- CSV codec、header、逐 case 拉取与发布、early-close source ownership 都正确 GIVEN。引用/换行与 no-read-ahead 是完整管线的集成护栏，候选只编写同步 score_rows。

提示：H1 "Which score and metadata belong to this model?"；H2 "Is the comparison view in replay order or ranking order?"；H3 对照 case 的 criteria、results 与比较返回值里的字段单位。

追问："Can zero tokens mean an absent model?"（零使用量仍是一条实际观测）；"What is buffered?"（只缓存当前 case 的模型行，没有固定内存上界）。

### Part 5 嵌套测试报告（目标 10 分钟）

本课没有自然的执行树。这关沿真实的 case→model→scores 报告整理 pattern→model scorecard，不伪造递归 prompt 引擎。

坑：

- 每项 mean 用实际观察到的 count 作分母，缺失不补零；出现的 False/0 仍算一次观察。
- 最弱项只在有观察的 criteria 中选；平分用 CRITERIA 顺序。
- case 名可以在不同 pattern、model 下重复；同一三元组重复才报 ValueError。
- token 求和，latency/composite 按该 model 的 case 数取均值；输出和输入都保持各自顺序，不改原报告。

提示：H1 "Was that criterion missing, or observed as zero?"；H2 "Which fields identify one observation?"；H3 指向 `(pattern, model, case_id)`。

追问："Which criterion should you improve next?"（先看最弱观察项和覆盖率；缺失项需要补数据，不能当作性能为零）。

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 从调用链找错值来源、一次修一处、局部重跑 |
| 代码质量 | 15 | 保留合同、无凑测试代码、命名清楚 |
| 沟通 | 15 | 主动澄清、说明分母和取舍 |
| 生产意识 | 10 | 版本、持久化、字节精度、回放边界和流清理 |

每项写具体证据，没观察到就写“未观察”。真人用时未校准。
