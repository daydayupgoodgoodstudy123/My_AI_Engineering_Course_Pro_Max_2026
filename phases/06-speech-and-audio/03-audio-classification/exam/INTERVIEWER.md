# 面试官手册：ClipTag（06/03）

候选人计时期间不要看。候选人手里只有 README、`cliptag/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 2 | 采样率不同的 clip 能放进同一个 bank 吗？ | "No. Reject it with a ValueError. We don't resample." |
| 2 | 特征长度不一致怎么办？ | "Also a ValueError. The first clip fixes the size." |
| 2 | id 用什么格式？ | "Any unique string. UUIDs are fine." |
| 3 | classify 要不要搜 eval 里的 clip？ | "No, only train. Eval is what we measure on." |
| 3 | k 比 train 数量还大怎么办？ | "Your call. Say what you chose. The tests don't cover it." |
| 4 | 流结束时剩下不够一个窗口的样本怎么处理？ | "Drop them. No padding, no partial window." |
| 4 | 时间戳要保留几位？ | "Plain floats, start and end in seconds." |
| 5 | 分数里出现 ontology 里没有的标签？ | "That's a bug upstream. Raise a ValueError naming the labels." |
| 5 | 一个类出现在它自己下面？ | "Malformed ontology. Raise a ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修特征代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏：

1. 短于一帧的 clip 被切出一个残缺帧。错误不在 `frame_signal` 报出来，而是两层之后，在 `apply_filterbank` 里报 IndexError。
2. `summarize([])` 报 IndexError，应该报 ValueError。
3. 方差除以 `t - 1`，与 docstring 写的总体方差不一致，单帧 clip 还会除零。
4. 方差循环里每次都重新算一遍均值，是 O(T²)，3000 帧要 2 秒左右。
5. 护栏：特征带 1e8 的偏移时方差必须准。为了提速改成 E[x²]−E[x]² 的一遍算法，会在这里挂掉。

看什么：是不是先读 traceback、顺着调用链往上游找；是不是先 `print(repr(...))` 看实际数据；每改一处就重跑。

提示：
- H1："Which function first produced something the next one didn't expect?"
- H2："How long is each frame that reaches dft_mag?"
- H3：直接指出 `frame_signal` 对短信号的计算式。

追问：
- "Why not compute the variance in one pass?"（数值稳定性；Welford 可以一遍算出来，而且稳定）
- "The lesson mentions SpecAugment. Where would it go in this pipeline, and should eval clips get it?"（只用在训练时）

### Part 2 特征库（目标 12 分钟）

坑：
- Python 的 sqlite3 默认开着隐式事务，不 commit 的话，关闭连接就丢数据。重开后的断言会挂。
- 建表没写 `IF NOT EXISTS` 的话，重开会报 `table clips already exists`。
- 只靠 CHECK 约束拦非法 split，报的是 IntegrityError，测试要的是 ValueError。
- 特征必须原样读回。用 float32 存，或者读回成 tuple，都会挂。JSON 或 REAL 都能存准。
- 插入顺序要靠自增列或 rowid 排序，UUID 排不出插入顺序。

追问：
- "You change featurize parameters next month. What happens to the clips already in the bank?"（特征版本：存特征配置的 hash，配置不一致就拒绝或重算）
- "Two writers at once?"（SQLite 写锁；需要时换数据库或排队写）

### Part 3 分类和评估（目标 12 分钟）

坑：
- 相似度要按降序排。
- 只能在 train 里检索，否则 eval 里一模一样的 clip 会自己投给自己。
- 平票规则在 docstring 里。照抄课里的 `Counter.most_common` 会选错，因为它按出现顺序处理平票。
- macro F1 要覆盖 eval 里的每一类，包括模型一次都没预测出的类（该类 F1 记 0）。只算预测出来的类，会把 0.44 算成 0.89。
- 最后一段是端到端检查：真实的正弦波经过 Part 1 的特征和 Part 2 的库之后，必须分对。

追问：
- "Accuracy is 0.8 here. Is this a good model?"（少数类召回为 0；要看每类召回和 macro F1，这正是课里讲的不平衡问题）
- "A million clips in the bank?"（预先算好范数、做向量化、用近似最近邻索引；按标签分片）
- "Where does balanced sampling belong?"（训练时用，评估时不用）

### Part 4 流式打标（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：每个事件一行 JSON，要换行分隔。缺了换行会报 Extra data，多一个空行会报 Expecting value。
- 不管数据怎么切块（包括空块），结果都要一样：窗口必须跨块拼接，不能每块单独处理。
- 窗口一凑齐就要输出，不能先把整个流读完。测试会数被拉取了多少块。
- 结尾不足一个窗口的样本丢掉（这是澄清问题）。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。

追问：
- "Why count samples instead of adding hop_s to a float?"（浮点累加会漂移；用整数样本下标就不会）
- "The client disconnects mid-stream. What runs, what leaks?"（`aclose()`，finally 里清理资源）
- "hop 0.25 s vs 0.05 s?"（延迟和算力的取舍；可以缓存相邻窗口共享的帧）

### Part 5 标签树汇总（目标 12 分钟）

坑：
- children 可能是 dict，也可能是 list，而 list 里还会混着 dict。只处理 dict 会在 list 上报 TypeError。
- 同一个类会挂在两个父类下面（Whistling），两条路径上的祖先都要拿到分数。
- 一个类自己的分数比子类高时，保留自己的分数。
- 没有任何分数的分支不出现在结果里。
- 未知标签和“自己包含自己”都要报 ValueError。

追问：
- "max vs noisy-OR for the parent score?"（max 保证父类分数不低于子类，noisy-OR 会叠加多个子类的证据）
- "AudioSet is a DAG. What breaks if you memoize by name?"（同一个名字在不同位置的子树可能不同）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、并发、版本、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
