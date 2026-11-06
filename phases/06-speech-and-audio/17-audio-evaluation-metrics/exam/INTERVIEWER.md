# 面试官手册：EvalSuite（06/17）

候选人计时期间不要看。候选人手里只有 README、`evalsuite/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 中文和日文里的数字要不要读成英文单词？ | "No. Contractions and spelled-out numbers are English rules. In other languages digits stay digits." |
| 1 | 重音算不算错误？ | "Yes. café and cafe are different words. Only the way the accent was typed doesn't matter." |
| 1 | 哪些语言按字算？ | "Chinese, Cantonese and Japanese: zh, yue and ja. Everything else is scored by word." |
| 1 | 2026 读成年份还是数字？ | "A plain number: two thousand twenty six. Years are out of scope." |
| 2 | 重跑的结果更差，要不要保留更好的那次？ | "No. The latest run replaces the old one. Keeping the best of several runs flatters the model." |
| 2 | 同分按什么排？ | "By when the model first showed up on that benchmark and metric. A re-run doesn't move it." |
| 2 | protocol 是什么？ | "How the number was computed: the text normalizer behind a WER, the reference set behind a FAD. Results under different protocols aren't comparable." |
| 3 | 重采样句子还是词？ | "Utterances. Errors inside one utterance aren't independent." |
| 3 | delta 正好是 0 的 replicate 算不算赢？ | "No. That's a tie." |
| 3 | 必须用 randrange 吗？ | "Any method, as long as all the draws come from one random.Random(seed)." |
| 4 | 空的运行输出什么？ | "Just the header." |
| 4 | 同一句会不会到两次？ | "No. Each utterance arrives once." |
| 4 | 行尾用 `\r\n` 还是 `\n`？ | "Whatever the csv module writes by default. The test reads either." |
| 4 | 每个 batch 报一次吗？ | "No. Every `every` utterances, wherever the batches split, plus one at the end if the last ones weren't reported." |
| 5 | 缺结果按 0 分还是跳过？ | "Neither. That node has no score, None, and neither does any group that counts it. Its siblings keep theirs." |
| 5 | 权重为 0 的子集缺了结果呢？ | "It doesn't count, so it doesn't block anything. Still report it." |

## 每关：要看什么、提示、追问

### Part 1 修评分代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. 按字计数的分支（CER）直接拆原文，没有经过 `normalize`，全角的３和句号都算成了错误。课里的 `cer()` 就是这样（测验 Q10）：WER 规范化了，CER 没有。
2. 补上规范化以后，`normalize` 里残留的 `re.sub(r"[^a-z0-9\s]", "", text)`（课里的原式）把汉字、假名、西里尔字母和 é 全删了。错误不在 `normalize` 报出来，而是两层之后，在 `error_counts` 里报 `ValueError: nothing to score in reference '我们明天去公园'`。
3. 缩写在标点之后才展开，而标点表已经把撇号换成了空格，what's 永远是 what s。测验 Q9 提醒过：先展开缩写，再删标点。
4. `_punctuation_table()` 每次调用都把 Unicode 的 111 万个码位扫一遍，一次 40 多毫秒，24 对句子要 2 秒左右。
5. 护栏，每种常见的改坏写法都有一条断言接着：
   - 为了提速换回课里的 ASCII 正则：中文和俄文被删光。
   - 换成 `re.sub(r"[^\w\s]", " ", text)` 或 `isalnum()` 过滤：Python 的 `\w` 不含组合符号，印地语的元音符号被换成空格，किताबें（复数）和 किताब 成了同一串字母，这句的 1/4 变成 0。
   - 只删 `string.punctuation` 里的 ASCII 标点，或者用 NFC 代替 NFKC：日文那句的句号或全角３还在。
   - 用 NFKD 去掉重音：café 和 cafe 分不开了。
   - 只保留字母：3 号楼和 5 号楼成了一样的。
   - 为了保住缩写，不把撇号当标点：'yes' 两边的引号留了下来。

看什么：是不是先读 traceback、打印规范化之后两边的实际内容；有没有意识到参考文本不空、空的是规范化的结果；每改一处就重跑；提速前有没有先测量（计时或 cProfile）。

提示：
- H1："What do both sides look like right before they are compared?"
- H2："What does normalize('我们明天去公园', 'zh') return, and which line makes it so?"
- H3：直接指出对应的那一行（字符分支、ASCII 正则、缩写和标点的先后、每次重建的表）。

追问：
- "Why not just use jiwer or Whisper's normalizer?"（可以，但要固定版本，把规则写进报告。Whisper 的英文规则把数词转成阿拉伯数字，方向和这里相反，两种规则下的分数不能放在一起比，这就是 Part 2 的 protocol）
- "Mandarin with English words mixed in: WER or CER?"（混合错误率：汉字按字，英文按词）
- "The normalizer changes next month. What happens to last month's numbers?"（规则的版本跟着结果一起存；换了规则就重算，或者分开排）

### Part 2 排行榜（目标 13 分钟）

坑：
- 不 commit 的话，关闭连接就丢数据，重开后 `get` 报 KeyError。
- 建表没写 `IF NOT EXISTS`，重开报 `table results already exists`。
- 每个 (model, benchmark, metric) 只能有一行：要有唯一约束，再次提交是更新，不是追加。
- `INSERT OR REPLACE` 是先删后插，行号会变，重跑过的 tdt-0.6b 就排到了同分的 ctc-1.1b 后面。要用 `INSERT ... ON CONFLICT ... DO UPDATE`，或者先 UPDATE、没有再 INSERT。
- 同分按第一次出现的先后排，不按模型名：先出现的 tdt-0.6b 按字母排在 ctc-1.1b 后面，`ORDER BY value, model` 会把这两个排反。
- 重跑结果更差也照样替换。aed-1.5b 第一次按 whisper-en 规则算出 5.75%，按本榜规则重算是 6.05%；只在新结果更好时才更新，榜上留下的是 whisper-en 那一条，重开后的 `get` 会挂。
- 值要原样存取。3167/52343 和 3166/52343 只差一个错误，打印出来都是 6.05%，存成四位小数就并列了。区间要读回成 tuple。
- 方向看 METRICS：WER 越低越好，UTMOS 越高越好。
- 不同 protocol 的结果不能放在一起排，`ranking` 报 ValueError，不能悄悄只留一种 protocol；`submit` 照收，因为重跑可以把 protocol 改过来。在 `submit` 里拒收，aed-1.5b 的第一次提交就会报错。upsert 也要更新 protocol 这一列。
- 校验用 METRICS 的范围。WER 没有上限，插入多的时候会超过 1，写死 0 到 1 会拒掉合法结果。

追问：
- "Two eval jobs submit at the same time?"（SQLite 的写锁和 WAL 模式；或者把提交排进一个队列）
- "Someone re-runs until the number looks good. What should the board keep?"（最新一次；另存全部历史，附 seed 和代码版本）
- "Should the board store per-utterance results?"（存了才能在任意两个提交之间做 Part 3 的配对比较）
- "Why REAL for the value and not TEXT?"（TEXT 列会把数字存成字符串，`ORDER BY` 就按字符串比：10.5 排在 9.5 前面，5.0e-05 排在 0.001 后面。测试里的值都是 0 到 5 之间的普通小数，看不出来，读候选人的建表语句时留意）

### Part 3 配对 bootstrap（目标 12 分钟）

坑：
- `percentile_interval` 要先排序，k 按 docstring 四舍五入。1 − 0.9 在浮点里是 0.09999999999999998，用 `int()` 截断得到 49 而不是 50。上端是 `ordered[B − 1 − k]`，写成 `ordered[B − k]` 两端就不对称了。
- 按 utterance id 配对，不能按位置 zip：测试里两次运行列出句子的顺序不同。
- 两次运行的 id 必须完全一样：少一句、多一句、换了一句都报 ValueError。只比句子数，换了 id 的那组会在取值时报 KeyError；只检查 baseline 的 id 都在 candidate 里，多出来的那句会被悄悄忽略。
- delta 是整个测试集上两个语料级错误率之差。取 replicate 的平均，或者逐句错误率之差的平均（课里 `ttr_wer` 的算法），都对不上 −30/720。
- 每个 replicate 只抽一组下标，两个系统共用。各自重采样的话，句子难度带来的方差抵消不掉，区间上端是 +0.022，30 处改进看不出来。
- 有放回地抽。`rng.sample` 每次抽到的都是整个测试集，区间缩成一个点，换 seed 也不变。
- 从排好序的 id 里抽，结果才和输入顺序无关。
- 用一个 `random.Random(seed)` 抽完全部 replicate，不碰全局的 `random`。每个 replicate 都新建一个 `Random(seed)` 的话，所有 replicate 抽到的是同一组句子。
- `p_better` 只数 delta < 0 的 replicate。只改了一句的那组数据里，约 36% 的 replicate 没抽到这一句，delta 恰好是 0；把它们算成赢，p_better 就从约 0.66 变成 1.0。
- 最后一段把 Part 1 和 Part 2 串起来：没解码出来的 c4 按全部删除计（service 已经写好），格式差异不算错误。

追问：
- "Why paired? When can't you pair?"（同一测试集上两个系统的错误高度相关，配对能消掉句子本身的难度；测试集不同就只能各自重采样，或者干脆不比）
- "Is 1000 replicates enough?"（百分位本身有蒙特卡洛误差；端点贴近 0 时要加大）
- "You compare 20 models pairwise. What goes wrong?"（多重比较；用 Holm 或 Bonferroni 校正，或者像 TTS Arena 那样给名次也带上区间）
- "Why resample utterances and not words?"（同一句里的错误不独立，按词重采样会让区间偏窄）

### Part 4 流式报告（目标 13 分钟）

坑：
- 输出格式由测试里的 `csv.DictReader` 决定。域名 `accented, L2` 里有逗号，手写 `",".join(...)` 会把一行切成五列，测试在 `int(' L2')` 上报 ValueError。用 csv 模块写，用默认的 dialect：`QUOTE_NONNUMERIC` 会给 rate 加引号，第一份报告那一行就对不上了。
- 第一行是表头，空的运行也要写，所以不能等第一份报告才写；表头只写一次，每份报告前都写一遍的话，`DictReader` 会把第二个表头当数据，在 `int('seen')` 上报错。
- 每份报告里的域按名字排序，不按到达的先后；rate 用 `str()` 写，不要保留固定的小数位。
- 每个域的 rate 是这个域的错误总数除以单位总数。课里 Step 2 的 `ttr_wer` 是逐句 WER 的平均，seen=4 时 `*` 会算成 0.3375，正确值是 9/42 ≈ 0.214。
- `*` 行合并所有句子，不是各个域 rate 的平均（那样是 0.35）。
- `every` 按全部句子计数，跨 batch 累积。在 batch 内计数的话，一句一批时一份中间报告都没有。每句都要检查是否到了报告点：等一个 batch 处理完才检查，5 句一批时就错过了第 2 句和第 4 句的报告。
- 最后一句刚好落在报告点上时，不再补写一份。
- 报告到点就输出，不能先把整个流读完。测试会数拉取了几个 batch。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。

追问：
- "Workers retry and the same utterance arrives twice?"（按 utterance id 去重，记住每句的计数；后到的结果覆盖先到的时，先减掉旧值）
- "A domain has three utterances so far. Do you show its rate?"（标出样本数，或者附上区间，可以接 Part 3）
- "Why not average per-utterance WER?"（短句的 WER 波动大，还可能超过 1，平均值会被短句主导）

### Part 5 套件汇总（目标 12 分钟）

坑：
- 叶子先按 METRICS 换算到 0 到 1：worst 记 0，best 记 1，越界截断。WER 0.08 是 0.92 分；CER 1.25 是 0 分，不是 −0.25。越低越好的用 1 − value、其余用原值，这种写法在 UTMOS 上不对：3.8 分会截成 1，应该是 (3.8 − 1) / 4 = 0.7。
- 组的分数是子节点分数的加权平均，权重默认 1，要除以权重和。每一层的节点都可以带权重，不只是指标叶子：asr 的 2 倍权重和 multi-audio 的 0 都在组这一层。
- 缺结果的叶子是 None，把它计入的父节点也是 None，一直传到根；兄弟分支照常有分数。按 0 分算不对，只在有结果的子节点上重新归一化也不对，后者等于奖励不跑难任务的模型。
- 权重为 0 的子节点照样出现在结果里，但不计入，缺了也不挡父节点。
- 结果按路径给，不按名字：`wer` 在两个子集下都有。
- 未知指标、负权重报 ValueError。未知指标在没有结果时也要报，测试传的是空的 results。

追问：
- "Is a weighted mean across tasks meaningful?"（取决于每个指标的 0 到 1 怎么定；也可以按名次，或者按相对最强模型的比例汇总）
- "MMAU-Pro multi-audio is 22%, under the 25% chance rate. How should that score?"（按随机水平校正：(acc − 0.25) / 0.75，截断到 0）
- "Who picks the weights, and when?"（发布前定好，写进套件；看过结果再调权重，就是在挑对自己有利的数）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规则版本、并发、重跑、多重比较、去重 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
