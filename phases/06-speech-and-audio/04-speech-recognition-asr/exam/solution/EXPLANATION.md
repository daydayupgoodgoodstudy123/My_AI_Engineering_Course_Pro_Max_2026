# 参考答案讲解：ASRKit（06/04）

计时结束后再看。参考实现在同目录的 `asrkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修解码和打分

**现象**：解锁后的第一个失败是 `wer('hello world', 'helo world')` 等于 0.5，而不是 0。看上去是 WER 出了问题，其实打分没错（两个词错了一个），错的是传进来的假设。

**顺着往上找**：假设来自 `transcribe`，`transcribe` 调的是 `greedy_decode`。第二个 l 前面隔着一个 blank，按课里的两条规则（先合并相邻的重复，再删 blank）应该保留下来。`greedy_decode` 把 `prev = token` 写在了 `if` 里面，只有输出字母时才更新，blank 帧不会刷新 `prev`，于是隔着 blank 的第二个 l 被当成重复跳过了。这和“先删 blank 再合并”是同一个错误。这一关想练的是：先看失败里的实际数据，再决定去哪找。

**依次修四处**：

1. 把 `prev = token` 挪到 `if` 外面，每一帧都更新。
2. `wer` 除以参考词数 N，不是假设的词数。原来的写法在静音解出空串时除以 0；删词多的时候也会把 WER 算大：参考六个词、假设 "the cat sat"，原来算出 3/3 = 1.0，应该是 3/6 = 0.5。
3. `edit_distance` 的三路递归没有记忆化，调用次数随长度指数增长，10 个词对 10 个词，本机要 0.5 到 1.4 秒。测试用的这句每个词都听错了，词相同时走捷径也帮不上忙。
4. 加上 `lru_cache` 能过计时，但递归深度大约是两份转写的词数之和，600 个词的会议转写要递归一千多层，超过 Python 默认的 1000 层上限。参考实现用课里 Step 3 的自底向上动态规划，只保留上一行：时间 O(N·M)，空间 O(M)。

**护栏**：WER 的分母是参考词数，插入没有上限，所以 WER 可以大于 1（测验 Q8、Q11）。用 `min(1.0, ...)` 截断，或者除以 `max(len(ref), len(hyp))`，都会让 `wer("a b", "a b c d e")` 从 1.5 变成 1.0 或 0.6。

## Part 2 转写库

参考实现有两张表：`utterances`（自增的 `seq` 负责添加顺序，`utt_id` 唯一，加上 `reference`）和 `hypotheses`（主键是 `(utt_id, model)`）。所有进来的 id、模型名和文本，先过一遍 `unicodedata.normalize("NFC", ...)`，再写入、查询或比较。

为什么要在 Python 里做：SQLite 按字节比较 TEXT，不懂 Unicode 的等价。“zoë”的 NFC 写法是一个 U+00EB，NFD 写法是 `e` 后面跟组合分音符 U+0308，字节不一样。macOS 的文件名通常是 NFD，标注表格里通常是 NFC，不规范化就会查不到，或者同一条语音存成两份。韩文在 NFD 下会拆成字母（자모），NFC 再拼回音节。

容易漏的七点：

- **NFC，不是 NFKC**：NFKC 会折叠兼容字符，m² 变成 m2，从 PDF 复制来的连字 ﬁ 变成 fi，参考文本的内容就变了。
- **写入、查询、比较之前都做 NFC**：测试用 NFD 的 id 去 `get`，minutes 的假设也是以 NFD 传进来的。只在写入时规范化，或者只在比较时规范化、存进去的还是原文，都会漏掉一处。
- **存储层不做 WER 规范化**：小写、去标点、去重音，是打分时对副本做的事。大小写和标点要原样读回，`zoe-0001` 也不能查到 `zoë-0001`。
- **模型版本不可变**：同一个版本对同一条语音再记一次，NFC 之后相同就什么都不做，不同就报 ValueError，这样历史上的 WER 才能复现。比较要在 NFC 之后做，并且区分大小写。
- **错误在 Python 里检查**：SQLite 默认不执行外键约束；打开 `PRAGMA foreign_keys` 以后，报的也是 IntegrityError，测试要的是 KeyError。重复的 id 也一样，UNIQUE 约束报 IntegrityError，测试要 ValueError。
- **commit**：插入后不 commit，`close()` 之后数据就没了。参考实现每次写入都放在 `with self._db:` 里。
- **顺序跟着语音走**：`pairs` 按 `utterances.seq` 排序。测试里 minutes 的假设比 zoë 的先记，按假设表的写入顺序排，或者按 id 排，minutes 都会排到前面。

## Part 3 前缀 beam search

每个前缀记两份对数概率：`p_blank`（以 blank 结尾的对齐）和 `p_token`（以前缀最后一个字母结尾的对齐）。每来一帧，对 beam 里的每个前缀：

```python
total = log_add(p_blank, p_token)
add(prefix, ends_blank=total + frame[blank])              # 这一帧是 blank
for token, lp in enumerate(frame):
    if token == blank or lp == -math.inf:
        continue
    if prefix and prefix[-1] == token:
        add(prefix, ends_token=p_token + lp)              # 同一个字母延续，不算新字母
        add(prefix + (token,), ends_token=p_blank + lp)   # 中间隔了 blank，是新字母
    else:
        add(prefix + (token,), ends_token=total + lp)
```

`add` 用 `log_add` 把落到同一个前缀上的概率加起来。一帧处理完，按两份之和排序，只留前 beam 个，概率为 0 的丢掉。

几个关键点：

- **求和，不是取最大**：第一个测试里每帧 blank 是 0.6、a 是 0.4。最好的单条路径是两帧都选 blank（0.36），greedy 也选它；但 a 有三条对齐（a a、a _、_ a），合起来是 0.64。这就是课里说的 CTC 对所有对齐求和，beam search 因此能找到 greedy 找不到的结果。
- **每一帧都剪枝**：beam 为 1 时，第一帧之后只剩空串（0.6 对 0.4），a 再也追不上，结果是空串。beam search 是近似算法，beam 太窄就会丢掉更好的答案；只在最后截断的写法算出来的是精确解，所以这条断言能把它查出来。
- **按两份之和排序，加完再剪**：`a_or_ab` 里第一帧 a 是 0.9，第二帧 blank、a、b 分别是 0.35、0.25、0.4。最好的单条路径是 a b（0.36），但 a 有两条对齐，a _ 是 0.315，a a 是 0.225，合起来 0.54。beam 为 1 时，要先把这两份记到同一个前缀上，再按两份之和排序截断，留下的才是 a。
- **两份概率分开记**：`a _ a` 必须解成 aa。简化版 beam 只记前缀本身，分不清最后一帧是不是 blank，课里的 `main.py` 就因此把 hello 解成了 helo。
- **和末尾不同的字母从两份之和扩展**，和末尾相同的字母只能从 `p_blank` 扩展出新字母。把这两条规则混用，前几个断言可能都能过，穷举对拍会挂。
- **log_add 要稳定**：starter 里的 `log_add` 是课里 `ctc_beam` 的 `log(exp(a) + exp(b))`。两个 -inf 进去时 `log(0)` 报错；1800 帧（36 秒）之后累积对数概率在 -1000 左右，`exp` 下溢成 0，也报错。改成 `max(a, b) + log1p(exp(-|a - b|))`，并且先处理 -inf。测验 Q12 讲的就是这件事。
- **穷举对拍**：测试里 5 帧、3 个 token 一共 243 条路径，按课里的两条规则折叠后求和，就是每个前缀的精确概率。beam 足够大、什么都不剪时，每一个前缀都要对上。

最后的端到端检查：o 所在的两帧里 blank 都略高（0.5 对 0.45），greedy 把 o 丢了，解成 "g home"，WER 是 0.5；beam 把 o 的三条对齐加起来（0.6525，大于 0.25），解成 "go home"，WER 是 0。两份假设经过 Part 2 的库存进去，再用 Part 1 的 WER 打分。

## Part 4 流式解码

逐帧处理，几个状态跨块保留：上一帧的 token `prev`、正在说的词 `word`、这个词第一个字母所在的帧号 `start`、最后一个字母帧之后的帧号 `end`，以及整条流的帧号 `index`。

```python
token = argmax(frame)
if token == SPACE:                 # 空格收尾；连续的空格只算一次
    if word:
        yield final
        word = ""
elif token != BLANK:
    if token != prev:              # 课里的折叠规则：新字母
        if not word:
            start = index
        word += VOCAB[token]
        yield partial
    end = index + 1                # 字母延续的帧也算进这个词
prev = token
index += 1
```

流结束时还有没收尾的词，就发它的 final。

- 状态跨块保留，切块方式才不影响结果。重复字母被切在两块之间时，`prev` 还记着上一块最后一帧，不会多出一个字母。这一点是 CTC 特有的：折叠规则要看前一帧。
- 每一帧都更新 `prev`，空格帧也一样。`go on` 里两个 o 之间只隔一个空格，空格帧不更新 `prev`，第二个 o 就会被当成重复。
- 时间戳用整数帧号乘 20 ms，不会漂移。`start` 记第一个字母所在的帧，`end` 跟着每个字母帧往后挪。测试里 w 前面隔着一个 blank，hello 的 o 占了两帧，这两处都会被查到。
- partial 在词多了一个字母时发，final 在空格或流结束时发。greedy 解码只会往后追加，不会改写已经输出的字母，所以这里不用等若干帧“稳定”再定稿；换成 beam search 才会改写，那时才需要稳定前缀的规则。
- 格式由测试的 `parse_sse` 决定：`event: <种类>`、`data: <一行 JSON>`，再加一个空行。

## Part 5 词格 n-best

分两步：

1. 用 Kahn 算法求拓扑序：从入度为 0 的节点开始，每取出一个节点，就把它出弧终点的入度减一。最后还有节点没被取出，说明有环，报 ValueError。这样词格里任何位置的环都能查出来，包括挂在死胡同上、不挡住终点的环。
2. 按拓扑序做动态规划：每个节点收集到达它的 (词序列, 分数)。轮到这个节点时，同一个词序列只留最好的分数，再取前 n 个，沿出弧扩展。弧的分数是 `am + lm_weight * lm`，没有词的弧只加分数。到终点就返回；终点一直没有路径到达，报 ValueError。

为什么可以在中间节点就去重、截断：最后要的是 n 句不同的话。同一个前缀接上同一条弧还是同一句话，分数低的那条永远赢不了；不在前 n 名的前缀，不管后面接什么，都有 n 句不同的话排在它前面。所以每个节点只留 n 个，工作量是弧数乘 n，和路径数无关。测试里的 20 段梯子有 2^20 条路径，穷举要将近 1 秒，动态规划不到 0.1 毫秒。

这组数据里的几处安排：节点编号不是拓扑序；1 和 6 之间有 peach、speech 两条平行弧；0 到 5 有两条 it's（一条前面有一段停顿），6 到 7 有两条静音路径，同一句话会走出四条路径；11 是死胡同。去重要在每个节点做：只在终点去重的话，n 为 4 时节点 6 的前 4 条路径被 speech 和 peach 各占两条，beach 到不了终点。lm_weight 为 1 时，语言模型把 "recognize speech" 推到第一；lm_weight 为 0 时只看声学分数，"wreck a nice beach" 更好。这就是课里说的 LM fusion：声学上接近的候选，由语言模型来分高下。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 CTC 解码和 WER，处理 Unicode 文本的存取，实现对数域的前缀 beam search，写跨块保持状态的流式解码器，以及在 DAG 上做 k-best 动态规划。它不涉及声学模型本身：没有训练 CTC、RNN-T 或 attention 模型，也没有实现 CTC loss 的前向后向算法。它也不涉及真实音频和 Whisper、Parakeet 的推理与部署，课里 Step 4、Step 5 用到的库需要另外动手跑。语言模型只以词格上现成的分数出现，shallow fusion 本身没有实现。
