# 面试官手册：MusicBox（06/09）

候选人计时期间不要看。候选人手里只有 README、`musicbox/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 提示词里写 "92.5 bpm" 怎么办？ | "Prompts only use whole numbers, and a piece keeps an integer bpm. The tests don't cover decimals." |
| 1 | 和弦要不要转位或重新配声部？ | "No. Root position, root first, in octave 4." |
| 2 | 速度表可以为空，或者不从 tick 0 开始吗？ | "No. It starts at tick 0. Anything else is a ValueError." |
| 2 | 要不要校验音符的音高和力度范围？ | "Not in this session. The tests only check the tempo map and the disclosure flag." |
| 2 | `ai_generated` 写成 "yes" 或 1 算不算？ | "No. It has to be exactly True." |
| 2 | id 用什么格式？ | "Any unique string. UUIDs are fine." |
| 3 | 协方差除以 n 还是 n − 1？ | "n − 1, the same as np.cov." |
| 3 | 两个模型的 FAD 一样时谁排前面？ | "Your call. Say what you chose. The tests don't cover it." |
| 4 | 每个小节都从第 0 步开始吗？ | "Yes. A new bar always starts at step 0." |
| 4 | 第一个 bar 之前就来了音符？ | "That's a broken stream. Raise a ValueError." |
| 4 | token 在小节中间结束了怎么办？ | "Send that bar, then keep sending bars until the last note has finished." |
| 4 | 同一个音高在一个小节里重叠？ | "Send both. The player deals with it. The tests don't cover it." |
| 4 | 流的最后一个 token 是 "bar"，后面什么都没有？ | "That bar was opened, so send it, even empty. The tests don't cover it." |
| 5 | 引用了不存在的段落？ | "Raise an error that names it. The tests don't cover it." |
| 5 | repeat 是 0 或负数？ | "Malformed. A ValueError is fine. The tests don't cover it." |
| 5 | endings 的个数和 repeat 次数不一样？ | "Also malformed. Your call, the tests don't cover it." |
| 5 | 音符可以延到小节线以后吗？ | "Yes. Only its start has to be inside its bar." |

## 每关：要看什么、提示、追问

### Part 1 修作曲和渲染（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `chord_tones` 先判断 `endswith("m")`，而 "dim" 也以 m 结尾，所以 "G#dim" 被拆成根音 "G#di" 加小三和弦。错误不在 `chord_tones` 报出来，而是在下一层的 `note_number` 里报 `KeyError: 'G#di'`，调用链是 render → chord_tones → note_number。
2. `parse_bpm` 是课里 `fake_generate` 的原样写法：`split()` 把 "128 bpm" 切成两个词，`int("")` 抛的 ValueError 被吞掉，速度静默回到 120。现象出现在时长上：8 小节算出 16 s，而不是 15 s。
3. `seconds` 用了 `tick // PPQ`，一拍以内的位置全被截掉，一个十六分音符的时刻算成 0。
4. 找“上一小节还在响的同一个音”时，`_held_until` 每次都从头扫描整个音符列表，是 O(n²)。2000 小节（约一小时）要 2 秒左右，限值 0.15 秒。
5. 护栏 A：速度要的是写在 bpm 前面的那个数。图省事改成“取提示词里的第一个数”，"8 bars of lofi at 90 bpm" 会读成 8；改成“取最后一个数”，"jazz at 140BPM for 32 bars" 会读成 32。
6. 护栏 B：提速时不能改掉连音。测试从三处查：
   - rock 进行在 D 大调里是 D–G–A–D，第 4、5 小节都是 D 和弦，D4（62）要从第 4 小节保持到第 5 小节末。去掉保持音，或者只在最后几个音符里找，都会在这里挂掉，因为每小节的鼓点音符排在和弦音后面。
   - A4（69）同时在 A 和弦和 D 和弦里，要从第 3 小节一直保持到第 5 小节末。只在上一小节开始的音符里找，或者只在整个和弦重复时才保持，都会在这里挂掉。
   - 16 小节都是 D 和弦时，三个和弦音从头保持到尾。“只看最近 N 个音符”不管 N 取多大，都会被足够长的保持音打断，这条断言专门拦这种凑数的写法。

看什么：是不是先读 traceback，找出 "G#di" 这个值是谁造出来的；是不是先 `print(piece)` 看实际的 bpm，而不是直接去改时长公式；每改一处就重跑。

提示：
- H1："Where does the string 'G#di' come from?"
- H2："Print the piece the pop prompt produces. Is its tempo what the prompt asks for?"
- H3：直接指出 `chord_tones` 里两个 `endswith` 的顺序，或者 `parse_bpm` 对 "128 bpm" 的切分。

追问：
- "Why PPQ 480?"（能被 2、3、4、5、6、8、16 整除，八分音符、三连音、十六分音符都落在整数 tick 上）
- "The lesson warns that models drift off the BPM. How would you check a generated audio clip?"（用 beat tracking，例如 librosa 的 `beat_track`，和提示词要求的 BPM 比较，超出容差就重新生成或丢弃）
- "Why not drop the legato feature to make render fast?"（那是改了产品行为。要保持的音一定在上一小节里还在响，记住上一小节每个和弦音在列表里的位置就够了，不管它是从哪一小节开始响的）

### Part 2 曲库（目标 12 分钟）

坑：
- Python 的 sqlite3 默认开着隐式事务，不 commit 的话，关闭连接就丢数据，重开后看不到曲子。
- 速度表用 JSON 存，读回来是 list 的 list，要转回 tuple，否则和原来的 Track 不相等。
- 音符要按加入时的顺序原样读回。拆成一张 notes 表再 `ORDER BY start` 读，会把最后那个 tick 0 的鼓点挪到前面，同一时刻和弦音的顺序也没有保证。
- 用 MIDI 文件的整数“每拍微秒数”存速度，140 bpm 会变成 428571 µs，读回来是 140.00014 bpm。
- 生成种子是 64 位无符号数，单独放进 SQLite 的 INTEGER 列会报 OverflowError，放进 REAL 会丢精度。和 meta 一起存成 JSON 就没有问题。
- `ids()` 要按自增列或 rowid 排序。track_id 上有 UNIQUE 或 PRIMARY KEY 时，不写 ORDER BY 的 `SELECT track_id FROM tracks` 会走覆盖索引，按 UUID 的字典序返回。测试存了 6 首曲子，碰巧排对的概率只有 1/720。
- `Track.seconds` 要逐段累加：每一段用这一段的速度，最后一段只算到目标 tick。只用第一个速度，或者一律用目标 tick 所在那一段的速度，都不对。tick 要按这首曲子自己的 `ppq` 换算成拍；照抄 `compose.seconds` 用模块里的 `PPQ`，在 ppq 为 960 的那条断言上会挂。
- 校验在 Python 里做：速度表不从 0 开始、tick 不递增、速度不是正数、meta 里没有 `ai_generated: True`，都要 ValueError。

追问：
- "Why store ticks and a tempo map instead of seconds?"（tick 是精确的整数网格；改速度时音符的音乐位置不变；秒由速度表推出来，存浮点秒还会让小节线上的音因为舍入落到线的另一边）
- "What else belongs in the generation record for the EU AI Act or California SB 942?"（模型和版本、生成时间、披露标记、水印 id、许可证和权利链）
- "A user asks for a track in the style of a famous singer. Where does that get stopped?"（课里的 Pitfalls：商业 API 会过滤，开源模型不会。要在生成前用自己的过滤名单拦下，并把拒绝记进日志）

### Part 3 FAD 评测（目标 12 分钟）

坑：
- 均值项是两个均值之差的平方和，不是欧氏距离。
- 协方差除以 n − 1（docstring 写明了，np.cov 和 frechet_audio_distance 都这样算）。除以 n 会在“整体放大两倍”那条断言上挂掉。
- tr√(Σ_r Σ_g) 是矩阵平方根的迹。逐元素开方，或者用 √(tr M) 代替，在“分布相同、只平移均值”那条断言上就不再是 4.5。二维时 tr√M = √(tr M + 2√det M)，因为 M 的两个特征值都是非负实数。
- 生成结果全落在一条直线上时，det M 在数学上是 0，浮点算出来可能是 −2e-22 这样的负数，直接开方报 `math domain error`，要先截到 0。
- 生成集合和参考集完全相同时，结果可能是 −5.6e-17 这样的负数。距离不能是负数，也要截到 0。
- 两个集合都至少要有两个点。只检查生成集合的话，参考集只有一个点时报的是 ZeroDivisionError，不是 ValueError。
- “平移”和“放大两倍”两条断言里，两个协方差成比例，有几种错写法在那里碰巧算对：只用对角线（丢掉协方差的交叉项）、把 tr√(Σ_r Σ_g) 写成 tr(√Σ_r √Σ_g)、把 M 当成对称矩阵求行列式。只有塌缩的那条断言能看出来。
- 排名按 FAD 从低到高。`sorted(scores)` 不写 key 会按模型名排。
- 最后一段是端到端检查：同一种风格（lofi）的生成比另一种风格（rock）的生成离参考集更近。

提示：
- H1："What is tr(sqrt(M)) in terms of the eigenvalues of M?"
- H2："For a 2×2 matrix, the eigenvalues add up to tr M and multiply to det M."
- H3：直接给出 tr√M = √(tr M + 2√det M)。

追问：
- "FAD is biased on small sets. How many clips do you need?"（偏差随样本数下降，比较时两边的样本数要相同；课里引用的 MusicCaps 数字是在几千条片段上算的）
- "Would you ship a model on FAD alone?"（不会。还要看 CLAP 衡量的文本对齐、人工偏好或 ELO，以及 30 秒以后的结构问题）
- "Why max(0, d) and not abs(d)?"（对 −5.6e-17 这样的舍入误差两种都行；真算出明显的负数说明公式错了，abs 会把错误藏起来）
- "VGGish embeddings have 128 dimensions. What changes?"（没有闭式解，要算矩阵平方根，例如做特征分解或用 `scipy.linalg.sqrtm`；协方差接近奇异时加一个很小的 εI）

### Part 4 流式输出小节（目标 14 分钟）

坑：
- 输出格式由测试里的解析代码决定：Server-Sent Events，每个事件是一行 `data: <json>` 加一个空行。只写一个换行（NDJSON 的习惯）会报 "every event ends with a blank line"；漏了 `data:` 会报 "every event carries its JSON on a data: line"。
- 越过小节线的音符要在小节线处截断，剩下的部分放到下一小节的第 0 步，标成 tied，排在这一小节的新音符前面。
- 一个音符可以跨好几个小节。
- 正好在小节线上结束的音不再响进下一小节。第二小节（bar 1）的 62 从第 0 步占满 16 步，第三小节必须是空的。把“越过小节线”的判断写成 ≥，第三小节会多出一个 0 步的 tied 音；把剩下的步数往后面的小节分时也一样，写成 ≥ 会在流结束后多发一个只有 0 步 tied 音的小节。
- 每个小节从第 0 步开始。第二小节的 62 前面没有 pos，忘了在 bar 上把位置清零的话，它会沿用上一小节最后的 pos，落在第 12 步。
- 还在响的音用 {pitch: 剩余步数} 的 dict 记也能通过测试，但同一音高的两个音同时越过小节线时会合并成一个，而澄清问题的答案是两个都发。测试不覆盖，可以追问。
- 空小节也要发出去，播放器靠它计时。
- token 结束时如果还有音在响，要继续发小节，直到最后一个音结束。
- 下一个 "bar" 一到就要发出上一小节，不能等整个流读完。测试会数拉取了几个 token。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出这里需要 async generator。

追问：
- "Why tie the note instead of starting it again in the next bar?"（重新敲一次会多出一个起音，听起来就成了两个音）
- "The player disconnects halfway through. What should happen to the model?"（`aclose()` 一路传到上游，停止生成，省下 GPU）
- "The lesson says AR models start to loop after about 30 seconds. Where could this stream notice it?"（按小节做 n-gram 重复检测，重复太多就停下重新生成，或者交叉淡化接上一段新的）

### Part 5 歌曲结构（目标 12 分钟）

坑：
- "play" 列表里混着段落名（字符串）和 repeat 组（dict），段落本身又分 "bars" 和 "play" 两种。
- 嵌套重复：主歌里 riff 重复两次，外层又把主歌加副歌重复两次。
- 小节长度由拍号决定：beats × ppq × 4 / unit。3/4 是 1440 tick，6/8 也是 1440；只看分子会把 6/8 算成 2880。用 `/` 算会得到 1440.0 这样的浮点 tick，和整数比较时相等，测试能过，但 tick 网格是整数，应该用 `//`。
- 每一遍后面接自己的结尾（第一结尾、第二结尾），第二遍从第一结尾之后开始。
- 同一个段落可以出现很多次（副歌出现 3 次），只有出现在自己里面才是死循环。用全局的 visited 集合会把正常的复用当成循环；完全不检查会 RecursionError。
- 起点落在小节外的音符要报 ValueError（6/8 小节里 tick 1440 的音）。判断是 0 ≤ tick < 小节长度，写成 ≤ 会放过正好落在下一条小节线上的音。
- 用 try/except RecursionError 把死循环转成 ValueError 也能通过测试，但那是递归撞到上限之后才发现，合法但嵌套很深的结构也会被误报。看到这种写法，记在代码质量里，再问候选人怎么用 path 检查。

追问：
- "How would you regenerate only the bridge, the way Udio's inpainting does?"（结构树给出这一段的 tick 区间，只遮住这一段重新生成，前后不动）
- "Can you cache the expansion of a section?"（可以缓存相对时间线，每次使用时加上偏移；不能缓存绝对时间）
- "What about D.S. al Coda, or a jump back to the chorus?"（那就不再是树，要按图处理，同样要防止无限循环）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、披露与版权、流式取消、评测指标的局限 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
