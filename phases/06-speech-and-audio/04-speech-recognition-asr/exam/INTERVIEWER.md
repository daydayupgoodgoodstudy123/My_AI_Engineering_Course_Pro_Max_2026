# 面试官手册：ASRKit（06/04）

候选人计时期间不要看。候选人手里只有 README、`asrkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | WER 要不要先统一大小写、去标点？ | "Not here. Inputs arrive normalized. Compare words exactly." |
| 1 | 参考文本为空时 WER 是多少？ | "Raise a ValueError, as the docstring says. An utterance with no reference words has no WER." |
| 1 | WER 能超过 1 吗？ | "Yes. Insertions have no upper bound." |
| 2 | 用 NFC 还是 NFKC？ | "NFC. NFKC changes what was said: m² becomes m2." |
| 2 | 存的时候要不要转小写、去标点？ | "No. Store what you were given, in NFC. The scorer normalizes its own copy." |
| 2 | 同一个模型版本对同一条语音再记一次？ | "The same text is a no-op. Different text is a bug upstream, so raise a ValueError." |
| 2 | id 区分大小写和重音吗？ | "Yes. Unicode normalization is the only change." |
| 3 | 输入是概率还是对数概率？ | "Log-probabilities, straight from a log_softmax. A token the model rules out is -inf." |
| 3 | 要不要加语言模型？ | "Not in this part." |
| 3 | 能活下来的前缀不到 beam 个怎么办？ | "Return the ones you have." |
| 3 | 两个前缀分数完全一样怎么排？ | "Smaller prefix first, as the docstring says. The tests don't depend on it." |
| 4 | 一个字母占了好几帧，每帧都发 partial 吗？ | "No. Only when the word gains a letter." |
| 4 | 流结束时最后一个词后面没有空格？ | "The end of the stream closes it. Send its final." |
| 4 | 时间戳用什么单位？ | "Integer milliseconds, 20 ms per frame." |
| 5 | 节点编号是按拓扑序排好的吗？ | "No guarantee. Treat them as opaque ids." |
| 5 | 两条路径拼出同一句话？ | "List it once, with its best score." |
| 5 | 词格里有环？ | "Malformed lattice. Raise a ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修解码和打分（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏：

1. `greedy_decode` 只在输出字母时更新 `prev`，就是测验 Q9(b) 问的那种写法。blank 不再把重复隔开，`hello` 解成 `helo`。错误不在解码处报出来，而是在测试第一行的 WER 断言：`wer('hello world', 'helo world')` 等于 0.5。
2. `wer` 除以假设的词数。静音解出空串时报 ZeroDivisionError；删词多的时候 WER 偏大。
3. `edit_distance` 是没有记忆化的三路递归，指数级。10 个词对 10 个词，本机要 0.5 到 1.4 秒。测试里这句每个词都听错了，所以只在词相同时走捷径、不做记忆化的递归一样慢，过不了。
4. 只加记忆化（`lru_cache`）能过计时，但 600 个词的会议转写要递归一千多层，超过 Python 默认的 1000 层，报 RecursionError。要改成自底向上的表。
5. 护栏：插入多时 WER 可以大于 1。为了让 WER 落在 0 到 1 之间而截断，或者改成除以两份转写里较长的那个，都会在这里挂掉。

看什么：是不是先读 pytest 打出来的实际参数（'helo world'），而不是先去怀疑 WER；改分母时有没有说清 N 是什么；改递归时有没有想到长转写。

提示：
- H1："Which value in that failure did you not expect?"
- H2："Decode a _ a by hand with the lesson's two rules. What does greedy_decode return for it?"
- H3：直接指出 `prev = token` 的缩进。

追问：
- "Why not just raise the recursion limit?"（治标不治本：递归深度随转写长度线性增长，两小时的会议有一两万个词。自底向上的表没有深度问题，只留两行时空间是 O(M)）
- "How would you report WER for a whole test set?"（语料级：总错误数除以总参考词数，不是把每句的 WER 取平均；两边用同一套规范化规则）

### Part 2 转写库（目标 12 分钟）

坑：
- SQLite 按字节比较 TEXT。不在 Python 里先做 NFC，从 macOS 文件名来的 NFD id 查不到用 NFC 存进去的同一条语音，报 KeyError。写入和查询都要做：测试里 `add_utterance` 和 `get` 收到的都是 NFD 的 id。
- 假设文本也存成 NFC。minutes 的假设是以 NFD 传进来的，只在比较时做 NFC、存进去的是原文，读回来的韩文就是拆开的字母。
- NFKC 不是更彻底的 NFC。它把 m² 变成 m2、ﬁ 变成 fi，改掉了说出来的内容。
- 存储层不做 WER 那套规范化（小写、去标点、去重音）。`zoe-0001` 必须查不到 `zoë-0001`。
- 同一个模型版本再记一次：NFC 之后相同就什么都不做，不同就报 ValueError。用 `INSERT OR REPLACE` 会静默覆盖；比较前不做 NFC，会把 NFD 写法的同一句话当成冲突；忽略大小写比较，会放过真正的改动。
- 已有的 id 再 `add_utterance` 要报 ValueError。只靠 UNIQUE 约束，报的是 IntegrityError。
- 未知 utterance 要报 KeyError。只靠 FOREIGN KEY 约束不行：SQLite 默认不检查外键，要先 `PRAGMA foreign_keys = ON`，打开了报的也是 IntegrityError。
- 不 commit 的话，重开后什么都没有。建表不写 `IF NOT EXISTS`，重开时报 table utterances already exists。
- `pairs` 按语音添加的顺序返回。测试里 minutes 的假设比 zoë 的先记，按假设写入的顺序（`h.rowid`）或者按 id 排序，都会把顺序弄反。不写 ORDER BY 时，顺序取决于查询计划；在参考实现的表结构下，SQLite 先扫假设表，结果同样是反的。

追问：
- "Annotators correct a reference next month. What happens to the WER you already reported?"（参考文本也要有版本；每个分数要能追溯到当时用的参考文本和模型版本）
- "Where does WER normalization live, and how do you stop it drifting?"（评分时对副本做；规范化规则本身也要带版本）
- "Model names come from a config file someone edited on a Mac. Does `pairs` still find them?"（模型名同样要先做 NFC，docstring 里写了。测试里的模型名都是 ASCII，这一点没有检查）

### Part 3 前缀 beam search（目标 14 分钟）

坑：
- `log_add` 是课里 `ctc_beam` 的写法 `log(exp(a) + exp(b))`，docstring 说的却是不会下溢、可以接受 -inf。新前缀的两份概率起始都是 -inf，两个 -inf 进去，`exp` 都是 0，`log(0)` 报 math domain error。只补上 -inf 的判断，36 秒的长语音还会再报一次，因为累积对数概率低于 -745 时 `exp` 下溢成 0。测验 Q12 讲的就是这件事。
- 合并时取 max 就成了 Viterbi，只看最好的一条对齐。第一个测试里 greedy 和 Viterbi 都选空串，正确答案是 a：0.16 + 0.24 + 0.24 = 0.64，大于空串的 0.36。
- 照课里 Step 2 的简化 beam，重复字母一律合并，`a _ a` 只剩一个 a。每个前缀要分开记以 blank 结尾和以字母结尾两份概率；和末尾相同的字母只能从 blank 结尾的那份扩展出新字母，从字母结尾的那份只能并回原前缀。
- 和末尾不同的字母要从两份之和扩展。只从 blank 那份扩展，前面几个断言都能过，穷举对拍会挂。
- 返回的分数是两份之和；概率为 0 的前缀不返回。
- 每一帧都要剪到 beam 个。beam 为 1 的那条断言专门查这个：每帧都剪，第一帧之后只剩空串，结果是空串（0.36）；只在最后截断，算出来的是精确的最优解 a（0.64），断言会挂。只在最后截断的写法如果漏到长语音那一步，会跑不完。
- 剪枝按两份之和排序，而且要先把落到同一个前缀上的概率加完再剪。`a_or_ab` 那条：第二帧 b 最大，最好的单条路径是 a b（0.9 × 0.4 = 0.36）；a 有两条对齐，a _ 是 0.315，a a 是 0.225，合起来 0.54。只按较大的那一份排（0.315 < 0.36），或者先把候选截到 beam 个再合并，beam 为 1 时留下的都是 ab。
- 最后一段是端到端检查：解码结果经过 Part 2 的库存进去，再用 Part 1 的 WER 打分，beam 要把 greedy 丢掉的那个 o 找回来。

追问：
- "Where would a language model go?"（扩展到词边界时加上 λ·log P_LM 和长度奖励，也就是 shallow fusion）
- "Beam 8 versus 64, with no LM?"（收益很小。没有 LM 时，CTC 的 beam 主要是把同一前缀的多条对齐加在一起）
- "Why not rescale the beam every frame instead of working in logs?"（可以，但要把缩放量记下来加回去，否则返回的就不是对数概率）

### Part 4 流式解码（目标 12 分钟）

坑：
- 输出格式由测试里的 `parse_sse` 决定：每条消息一行 `event:`、一行 `data:`，后面跟一个空行。只换一行会报 every message ends with a blank line。
- 上一帧的 token、正在说的词、整条流的帧号都要跨块保留。每块重置 `prev`，跨块的重复字母会多出一个；每块从 0 数帧号，时间戳就错。空块不代表流结束，`if not chunk: break` 会把后面的帧全丢掉。
- 两个词之间有两个空格 token（中间隔着一个 blank），开头还有一个空格，都不能产生空词。
- `start_ms` 是这个词第一个字母帧的起点。测试里 w 前面隔着一个 blank，拿“上一个空格的下一帧”当起点会早 20 ms。`end_ms` 是最后一个字母帧的终点，字母延续的帧也算：hello 的 o 占了 11、12 两帧，所以是 260，不是 240。
- 空格帧也要更新 `prev`。`go on` 的帧是 g、o、空格、o、n。在空格分支里提前 `continue`、跳过了 `prev = token`，第二个 o 会被当成重复吞掉，得到 go 和 n。
- 流结束时，最后一个词也要发 final。
- 一有新字母就发 partial，不能先把整个流读完。测试会数被拉取了多少块。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。

追问：
- "The speaker stops but the stream stays open. When does the last word become final?"（端点检测：连续若干帧都是 blank 就定稿，或者接 VAD）
- "Why integer milliseconds?"（帧号乘以帧移是精确的；浮点秒数累加会漂移）
- "What changes if this decoder used beam search?"（beam 会改写已经输出的内容，partial 和 final 才真正不同：只有所有 beam 共有的前缀才能定稿）

### Part 5 词格 n-best（目标 12 分钟）

坑：
- 节点编号不是拓扑序（9 到 1 再到 6）。按编号遍历会在终点前断掉，报 no path。
- 1 和 6 之间有两条平行弧（peach、speech）。用 `(src, dst)` 当字典键会丢掉一条。
- 同一句话会走出好几条路径：0 到 5 有两条 it's（一条前面先有一段停顿，经过 13），6 到 7 也有两条静音路径。n-best 要按词序列去重，留最好的分数，而且每个节点都要去重。中间节点只按路径留前 n 条、到终点才去重的话，n 为 4 时节点 6 的前 4 条被 speech 和 peach 各占两条，beach 到不了终点。
- lm_weight 只乘语言模型分数。lm_weight 为 0 时只看声学分数，选的是 "wreck a nice beach"。
- 20 段的“梯子”有 2^20 条路径，穷举要将近 1 秒。每个节点只留 n 个最好的不同词序列，工作量就是弧数乘 n。
- 环要报 ValueError。测试里的环挂在死胡同 11 上，不挡住终点，所以只靠“走不到终点”查不出来；递归的 DFS 不做检查，会一直递归到 RecursionError。这条检查放在计时之后，穷举路径的写法会先在计时上挂掉，不会卡在环上。

追问：
- "Why keep n distinct word sequences per node, not n paths?"（最后要的是 n 句不同的话；同一前缀接同一条弧还是同一句，所以在中间节点去重是安全的）
- "A real lattice has millions of arcs. What changes?"（先按分数剪枝；k-best 用 Eppstein 一类的惰性算法；或者先做确定化，让每句话只剩一条路径）
- "Where does the LM weight come from?"（在开发集上调，通常还配一个词插入惩罚）
- "A second node has no incoming arcs. What does your topological sort do with it?"（Kahn 要从所有入度为 0 的节点开始。只从起点开始，那个节点指向的节点入度永远减不到 0，会被误报成环。测试里的词格只有一个源点，这一点没有检查）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、版本、数值稳定、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
