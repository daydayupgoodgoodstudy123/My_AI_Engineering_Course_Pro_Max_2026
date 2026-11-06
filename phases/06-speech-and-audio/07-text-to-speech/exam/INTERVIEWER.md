# 面试官手册：TTSFront（06/07）

候选人计时期间不要看。候选人手里只有 README、`ttsfront/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 没有句点的 "Dr" 也展开吗？ | "Yes. Any word in the table expands; a period right after it is part of it." |
| 1 | 句子以缩写结尾，比如 "Elm Dr."，句末还停顿吗？ | "No. The period belongs to the abbreviation. We accept that." |
| 1 | 带千分位或小数点的数字（1,000、3.5）？ | "Out of scope. Plain digit runs only." |
| 1 | 词典里同时有 "Kokoro" 和 "kokoro" 怎么办？ | "That doesn't happen here. Pick one and say which." |
| 2 | 同一个发音再加一次，只是 priority 不同？ | "ValueError. Changing a priority isn't part of this API." |
| 2 | 要不要对音段做 Unicode 归一化（NFC 或 NFD）？ | "No. Store exactly what you're given." |
| 2 | 重音符号算单独的音段吗？ | "Whatever the caller sends. We don't re-segment." |
| 3 | 时长全是 0 怎么办？ | "Every phone still gets one frame." |
| 3 | 空列表？ | "Return an empty list." |
| 4 | 标点后面什么算空白？ | "Anything str.isspace() accepts, newlines included." |
| 4 | 句点后面跟引号（`Hi."`）？ | "Out of scope. Only whitespace after the mark ends a chunk." |
| 4 | min_chars 算不算开头的空格？ | "No. Count the chunk as it will be sent, stripped." |
| 4 | 一句话很长、没有标点怎么办？ | "Not in this version. Tell me what you'd do." |
| 5 | rate 支持 "fast" 这样的关键字吗？ | "No. Percentages only; anything else is a ValueError." |
| 5 | break 两边 prosody 一样，要合并吗？ | "No. A break always separates segments." |
| 5 | 文档带不带命名空间？ | "Real SSML carries the W3C namespace. Accept it with or without." |

## 每关：要看什么、提示、追问

### Part 1 修文本前端（目标 12 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏：

1. `number_words` 把 21–99 的十位和个位用连字符连起来（"forty-two"），docstring 写的是一个空格。错误不在这里报出来：normalize 把 "forty-two" 当成一个词交给 phonemize，词典里没有，退回字形规则，`rule_phones` 在 "-" 上报 ValueError，离根因隔了三层调用。
2. phonemize 查词典区分大小写。测试词典里的产品名按原样写成 "Kokoro"，normalize 输出的是 "kokoro"，查不到就退回字形规则，念成 K AO K AO R AO。
3. 分词正则把 "Dr." 拆成 "Dr" 和 "."。这个句点被当成停顿；缩写判断看到的“下一个词”也成了 "."，所以 "Dr. Lee" 读成 "drive . lee"。一个根因，两个症状。
4. `rule_phones` 在每个位置从剩余长度开始往下试，一个词要做 O(L²) 次切片和哈希。普通的词看不出来，3000 个字母的 "hahaha…" 要 1.1 秒左右。规则最长 MAX_RULE（4）个字母，从这里往下试就够了。不能照课里的代码写死成 `(3, 2, 1)`："tion" 有 4 个字母。
5. 护栏：词典里没有的词必须用字形规则、按最长匹配读出来。为了提速跳过长词、截断、丢掉 OOV 词，或者把匹配长度改小（只按单个字母读、写死成 3、从短往长试），都会在 "Ghumare station" 和那串 "ha" 上挂掉：只有最长匹配才会把 "station" 里的 "tion" 读成 SH AH N，否则读成 T IH AO N。

看什么：traceback 指向 `rule_phones` 时，是在那里补一条 "-" 的静音规则、或者像课里的代码那样跳过没有规则的字符，还是顺着往上找到 `number_words`。前两种改法会让 "forty-two" 绕过词典，念成 F AO R T Y T W AO，第一个断言照样挂。在 normalize 里把 "-" 替换成空格能过 Part 1，但 Part 5 直接调用 `number_words`，到那里还会读出 "twenty-one"。查词典时只多试一次首字母大写（`word.capitalize()`）也能过 "Kokoro" 这一条，但词典里写成 "KOKORO" 或 "McDonald" 的词照样查不到；该做的是把词典的键折叠成小写再查。测试抓不到这种写法，算在代码质量里。

提示：
- H1："Which function produced the string that rule_phones choked on?"
- H2："What does number_words(42) return, and what does its docstring promise?"
- H3：直接指出 `number_words` 里十位和个位之间的连接符。

追问：
- "3.5 comes out as 'three, pause, five'. How would you read decimals?"（分词时把数字中间的小数点留在数字里，读作 point；和缩写一样，句点的含义要看上下文）
- "Dr. before a capitalized word is doctor. Where does that rule break?"（全大写的文本、句末的 "Elm Dr."、"Dr. 5"；真实系统用带上下文的规则或 WFST 归一化器）
- "The production lexicon has 130k entries. Where does the case-folded index live?"（建一次、缓存起来；不要每次 phonemize 都重建，更不要每个词扫一遍词典）

### Part 2 发音词典（目标 12 分钟）

坑：
- 一个词有多种发音。以词为主键，或者用 INSERT OR REPLACE，第二种发音会把第一种顶掉。
- 读回顺序：priority 降序，同 priority 按添加顺序。把 (priority, seq) 一起 `reverse=True` 排序，平局就变成新加的在前。
- 词不分大小写，并按小写报告。原样存 "Church"，就查不到 "church"。
- IPA 的音段不是一个码位一个音：鼻化元音 "ɑ̃" 是两个码位，塞擦音 "t͡ʃ" 是三个。把音段拼成一个字符串、再按字符拆回来，组合符号会变成单独的“音段”。
- 不要做 Unicode 归一化。测试里的 "õ" 是 o 加 U+0303，NFC 会把它合成 U+00F5：打印出来一模一样，比较却不相等。反过来用 NFD 也不行："ich" 里的 "ç" 是一个预组合码位 U+00E7，NFD 会把它拆成 c 加 U+0327。
- 以组合符号开头的音段（前面没有字母可附着）要报 ValueError，用 `unicodedata` 判断。空音段也要报 ValueError；直接取 `segment[0]` 会在空字符串上报 IndexError。
- 重复的发音要报 ValueError。只靠 UNIQUE 约束，报的是 IntegrityError。查重也不分大小写：测试用 "Tomato" 再加一次 tomato 已有的发音，拿原样的词去查就查不到存成小写的那一行。
- `table()` 给每个词取 priority 最高、同级里最早加的那一种。按添加顺序取第一种，或者让后面的行覆盖前面的，tomato 都会拿错。
- Python 的 sqlite3 默认开着隐式事务，不 commit 的话，关闭后重开什么都没有。建表要写 `IF NOT EXISTS`，否则重开时报 table pronunciations already exists。

追问：
- "Drop seq from your ORDER BY and the test still passes. Is the tie order guaranteed?"（不保证。SQLite 只保证 ORDER BY 里写出的键；在 (word, priority) 上建索引以后，同 priority 的行会倒过来返回，新加的在前。测试抓不到这一条，只能靠追问）
- "Why JSON rather than joining the segments with a separator?"（分隔符要保证不会出现在音段里，还得自己处理转义；JSON 原样还原，不用设计格式）
- "If you ever need to compare pronunciations, should you normalize?"（比较时用规范化后的副本，存的仍是原样）
- "How do you choose between 'read' as present and as past tense?"（priority 只给出默认读法；同形异音词要看词性或上下文，那是前端消歧模型的事）
- "An editor changes a pronunciation while the TTS server is running. When does the server see it?"（服务端缓存 table() 的结果时，要有版本号或失效机制）

### Part 3 时长取整成帧（目标 11 分钟）

坑：
- 每个音素各自取整，总帧数会漂移：3 个 2.4 帧的音素，各自取整是 6 帧，合起来是 7.2 帧，应该给 7 帧。
- 总数“四舍五入、0.5 进位”。Python 的 `round()` 是银行家舍入，`round(2.5) == 2`。
- 余数平局给前面的音素。把 (余数, 下标) 一起倒序排，平局就成了后面的优先。
- 浮点：30 ms 和 55 ms 在 12.5 ms 的 hop 下是 2.4 帧和 4.4 帧，余数在数学上都是 0.4，浮点算出来却是 0.3999999999999999 和 0.40000000000000036，那一帧就给了后面的音素。用 `Fraction` 或整数运算，或者比较前先舍入到固定位数。
- 至少一帧要在分配之前做（份额取 max(1, 时长/hop)）。分配完再补 `max(1, f)`，总帧数就和时长对不上。余数和总数也都从加了下限的份额算：7.5 ms 只有 0.6 帧，下限之后份额是整 1 帧、余数是 0。拿 0.6 去比余数，[7.5, 31.25] 会分成 [2, 2]。
- 差的帧按余数补，不是按份额大小补：[20, 30, 45, 30] 是 1.6、2.4、3.6、2.4 帧，该补的是余数 0.6 的第 1 个和第 3 个，按份额大小补就给了 3.6 和第一个 2.4。
- 按累计时长逐个取整也能保住总数，但分法不同：[30, 30, 30] 会分成 [2, 3, 2]，测试要的是 [3, 2, 2]。
- 最后一段把 Part 1–3 串起来：词典（Part 2）、前端（Part 1）、课里的时长表、1.25 倍语速，再分配成帧。要求帧区间首尾相接，总帧数等于缩短后的总时长。

追问：
- "Why not floor everything and give the rest to the last phone?"（误差全堆在最后一个音素上，句末停顿被拉长）
- "Largest remainder isn't monotonic: lengthening one phone can take a frame from another. Does that matter here?"（对 TTS 影响很小，但要知道这是取舍）
- "The vocoder upsamples by 256 but the acoustic model hops 300 samples. What breaks?"（音频时长和音高都会错，两边的 hop 必须一致）
- "Durations arrive one phone at a time. Can you allocate online?"（按累计时长取整：每个音素拿 round(累计) 减去已分配的帧数，code/main.讲解.md「动手改一改」第 3 题和 quiz 里改写 `duration` 的那道题就是这个思路；和最大余数法的结果不一定一样）

### Part 4 流式切块（目标 13 分钟）

坑：
- 输出格式由测试的解析代码决定：server-sent events，每个事件是一行 `data: ` 加 JSON，后面跟一个空行。只写一个 `\n` 会报 every event ends with a blank line。
- 句点要看后一个字符才能判断。LLM 可能先发 " 3."，下一个 token 才是 "50"。在一个 delta 的末尾就下结论，"3.50" 会被切开。这个错只在切块方式变化时暴露，测试用了 token、单字符、随机三种切法。
- "Dr." 后面的句点不结束 chunk。缩写要看句点前的整个词：用 `endswith("st")` 这类后缀判断，"the rest." 会被当成 "St."，这一句就和下一句粘在一起。
- 标点后面的换行也是空白（`str.isspace()`）。只认空格的话，`Press "Send".` 和下一行的 "Done." 会粘成一块。
- 句末标点不受 min_chars 限制。"Sure, Dr. Lee." 只有 14 个字符，也要马上发出去，首句延迟靠的就是这个；逗号、分号、冒号才要等 chunk 够长。
- min_chars 按发出去的样子数：去掉两头空白，包括末尾的标点。测试从两边卡住这个边界：默认 20 时，19 个字符的 "which includes tax," 不能切（连上前面的空格数是 20）；min_chars=19 时它必须切（写成 `>`，或者不数那个逗号，都差一个）。
- 一段 delta 里可能有好几个切点，要循环切到没有为止。每段只切一次的话，整段文字一次到达时，第一块之后的全都剩成一大块。
- 第一个 chunk 要尽早发。测试数 LLM 被拉取了几个 token：拉到 "Sure"、"."、" Here" 就该发出 "Sure."。先读完整个流再切，会拉取 100 个。
- 流结束时剩下的文本是最后一个 chunk，只剩空白就不发。
- 事件里的 JSON 要用 `json.dumps` 生成。文本里带引号（`Press "Send".`），手拼字符串的话 `json.loads` 会报 Expecting ',' delimiter。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。

追问：
- "The user barges in after chunk 2. What do you cancel, and how does the client know what was spoken?"（`aclose()` 关掉生成器，同时取消 LLM 的生成；客户端凭 seq 知道播到哪一块）
- "A 400-character sentence with no punctuation?"（加 max_chars，在最后一个空格处切；首句延迟和韵律之间的取舍）
- "What does min_chars trade off?"（首句延迟和合成质量；chunk 太短韵律会断，每块还有固定开销。第一块可以用更小的阈值）

### Part 5 SSML 展开（目标 12 分钟）

坑：
- ElementTree 的 text 和 tail：子元素后面的文字存在子元素的 tail 里，属于父元素的 prosody。用子元素的 prosody 读 tail，"to you." 会变成 1.5 倍语速。
- 嵌套的 prosody 是叠加：rate 相乘，pitch 相加。直接覆盖会把 "or sooner" 算成 0.5 倍、-0.5 st。
- break 的时间单位：先判断 "s" 再判断 "ms"，"250ms" 会变成 `float("250m")` 报错。
- 真实的 SSML 带 W3C 命名空间，ElementTree 给出的 tag 是 `{http://www.w3.org/2001/10/synthesis}speak`，要去掉前缀。每个元素都要去，只处理根元素的话，里面的 prosody 会被当成未知元素。
- 相同 prosody 的相邻文字合并成一段，空白照原样折叠成一个空格。每一片先 strip 再用空格拼，会多出 "T T S ," 和 "one ." 里的空格；只 strip 两头、不折叠中间，"call" 后面的换行和缩进会留在段里。标签之间只有换行和缩进的文字不输出空段。
- break 总是把段分开，哪怕两边的 prosody 一样。遇到 break 要先把待合并的文字输出，再输出 break，不然 "Thanks" 会排到 break 后面。
- say-as cardinal 直接用 Part 1 的 `number_words`。如果 Part 1 的连字符是在 normalize 里替换掉的，这里会读出 "twenty-one"。

追问：
- "Why flatten instead of handing the SSML to the model?"（多数声学模型只接受文本加少量全局控制；分段后每段可以单独设语速和音高，也能单独缓存）
- "Pitch in semitones, percent or Hz?"（半音是对数刻度，叠加就是相加；百分比要相乘；Hz 和说话人的基频有关）
- "The SSML comes from users. What could go wrong?"（超大或很深的文档、超长的 break；要限制文档大小、嵌套深度和 break 时长）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、缓存、取消、输入校验 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
