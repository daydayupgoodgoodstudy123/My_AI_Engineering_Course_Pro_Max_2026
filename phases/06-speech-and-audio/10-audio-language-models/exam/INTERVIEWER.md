# 面试官手册：LALMKit（06/10）

候选人计时期间不要看。候选人手里只有 README、`lalmkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | `audio_tokens` 和 projector 的输出对不上，以哪个为准？ | "The projector. It zero-pads the last run of frames, so the count has to include that run." |
| 1 | 批量生成时填充在左边还是右边？ | "Left. These batches go to generate." |
| 1 | padding 位置的 position id 填什么？ | "Zero, as the docstring says. Those positions are masked anyway." |
| 1 | 可以给 PAD 换一个单独的 id 吗？ | "No. PAD is the tokenizer's pad token, and that is end-of-text. Keep it." |
| 2 | 输出要不要先 strip 或者规范化？ | "No. Store exactly what came back. The official scorer reads the raw text." |
| 2 | 同一个 (model, item) 又跑了一次，留哪个？ | "The latest. One prediction per model and item, and it keeps its place in the list." |
| 2 | 调用失败存什么？ | "None. It's asked again on the next run. An empty string is a real answer and is not retried." |
| 3 | 小写的 "(b)" 算不算选 B？ | "Not by the docstring's rules. Say what you would change. The tests only use capitals." |
| 3 | 答案里出现两个不同的字母？ | "Then it picks nothing, and it counts as wrong." |
| 3 | 开放题（没有选项）怎么算？ | "Skip it here. Open-ended answers need an LLM judge, the way the official evaluator does it." |
| 3 | 某一题根本没有输出？ | "It counts as wrong. The denominator is every multiple-choice item." |
| 4 | system turn 本身就超预算怎么办？ | "Raise a ValueError. Same when the system turn and the turn that just arrived don't fit." |
| 4 | 已经丢掉的 turn 以后还能回来吗？ | "No. Once something is dropped, it stays dropped." |
| 4 | 一段音频还没说完，要等它结束再输出吗？ | "No. Yield after every event. An open clip shows the tokens it has so far." |
| 4 | 还在录的那段 clip 也能丢 token 吗？ | "Yes. When it's the only clip, it is the oldest audio, so it loses tokens from the front like any other." |
| 5 | tool_result 里还能再嵌 tool_result 吗？ | "Yes, to any depth." |
| 5 | 不是 16 kHz 的音频要不要重采样？ | "No. Raise a ValueError that says where it is." |
| 5 | 音频没写 sampling_rate 怎么办？ | "Reject it like a wrong rate. We don't guess the rate. The tests don't cover it." |
| 5 | "Audio N" 的编号每条消息从 1 开始吗？ | "No. One numbering for the whole conversation, in reading order." |

## 每关：要看什么、提示、追问

### Part 1 修输入代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `audio_tokens` 用 `//` 向下取整，而 `stack_frames` 会把最后不满一组的帧补零。5 帧的 clip，projector 出 3 个向量，展开时只留了 2 个 AUDIO_PAD。错误不在 `audio_tokens` 报出来，而是两层之后在 `merge` 里报 ValueError（`4 audio vectors for 3 AUDIO_PAD positions`），`merge` 本身没有 bug。
2. `expand` 把所有音频放在文本前面，这正是课里 `interleave_with_text` 的写法（测验 Q11 指出的第一点）。docstring 要求每个 AUDIO 槽位在原地展开。
3. `pad_batch` 用 `token != PAD` 生成 mask，可 `PAD = EOS`（Qwen 系的 tokenizer 用 end-of-text 做 padding），第二行里真实的 EOS 也被遮掉了。位置 id 是从 mask 算出来的，也跟着错。
4. 位置 id 对每个 token 重新求一遍 mask 的前缀和，是 O(L²)。十分钟的通话是 15,000 个 audio token，要 0.5 秒左右，测试限 0.02 秒。
5. 护栏：看到 ValueError，最省事的“修法”是让两边凑上：在 `merge` 里把音频截到槽位数，或者让 `stack_frames` 丢掉最后不满的一组。不报错了，但帧数不是 stack 整数倍的 clip，最后那几帧没进模型，ids 断言会挂。
6. 护栏：`(n + 1) // stack` 只在 stack=2 时等于向上取整，stack=3 的断言会挂。

测试拦不住的一种凑法：把 `PAD` 改成别处不用的 id（比如 0），mask 照旧按 `token != PAD` 生成，测试也能过。这是改了 tokenizer 的约定，mask 仍然从 id 反推，那个 id 一出现在真实内容里就会再错。看到这样改，问候选人为什么动 `PAD`，回答见上面的澄清问题。

看什么：是不是先读报错信息（4 个音频向量，只有 3 个 AUDIO_PAD 位置），再判断哪一边是对的；有没有去读 `stack_frames` 的 docstring；是不是每改一处就重跑。

提示：
- H1："merge is only the messenger. Which of its two inputs is wrong?"
- H2："How many vectors does the projector make from 5 frames, and how many slots did expand make?"
- H3：直接指出 `audio_tokens` 里的 `//`。

追问：
- "Qwen2-Audio's pooling drops the odd frame instead. Is dropping wrong?"（两种都可以，关键是 processor 算出的 token 数和模型实际产出的一致。真实实现也在把音频特征放进序列时检查两者数量是否相等）
- "Why left padding for generation?"（新 token 都接在右端；右填充时每行最后一个位置可能是 pad，还要单独找每行最后一个真实 token）
- "Nothing raised for the PAD/EOS mix-up. How would you have caught it?"（mask 只能由长度生成，不能由 id 反推；transformers 的 generate 在 pad token 和 eos token 相同时会警告 attention mask 推不出来；测试里放一行带 EOS 的样例）
- "Ten minutes is 15,000 audio tokens here. What would you do before it reaches the LLM?"（加大 stack 或池化，按 VAD 切段，先 diarize 再分段送，这是课里 Pitfalls 的建议；或者换长上下文的模型，并看它的长音频 benchmark）

### Part 2 结果库（目标 12 分钟）

坑：
- 每个 (model, item) 只有一条。重跑是替换，不是追加，普通 INSERT 会重复计数。
- `INSERT OR REPLACE` 是先删再插：行拿到新的 seq，重跑过的 item 跑到列表末尾，测试要求它留在原位。要用 `INSERT ... ON CONFLICT (model, item_id) DO UPDATE`，或者先 UPDATE、没命中再 INSERT。
- `INSERT OR IGNORE` 留下的是第一次的输出。
- `predictions` 要写 `ORDER BY seq`（或 rowid）。不写 ORDER BY 时，SQLite 会走 (model, item_id) 的唯一索引，按 item_id 的字母顺序返回；测试里的 id 故意不按记录顺序排，所以不写 ORDER BY、写 `ORDER BY item_id`、`INSERT OR REPLACE` 配不写 ORDER BY，都会在第一个断言挂掉。`pending` 也按传进来的顺序返回，不排序。
- 唯一约束只建在 item_id 上，GPT-4o Audio 的答案会盖掉 Qwen 的。
- 原始输出必须原样往返：前导空格、`\r\n`、结尾的空格和换行都要在。strip 以后，官方评分器拿到的就不是模型的原话了。
- None（调用失败）和 ""（模型什么都没说）是两回事：前者要重跑，后者是一个答案，只是答错了。`output or ""` 会把失败吞掉；用真假值判断 pending，会把空答案也拿去重跑。
- 和样板一样要 commit，建表要写 `IF NOT EXISTS`。

追问：
- "Why keep the raw text instead of the parsed letter?"（换解析规则、或者改用官方的 embedding 匹配时，不用重新调用模型；API 模型重跑要花钱，同一个模型版本也可能已经下线）
- "The runner crashes after 900 of 1,800 items. What is in the store?"（每次 record 都 commit 的话，900 条都在，重跑只问剩下的。只在 `close()` 里 commit 也能通过测试，但进程一崩，这一轮的结果全丢，`pending` 也就没用了）
- "Two runners write to the same store at once?"（SQLite 的写锁；upsert 放在事务里；或者每个 runner 写自己的库，最后按 (model, item) 合并）
- "The vendor updates the model under the same name."（model 字段要带版本或权重 hash，否则新旧结果混在一起；还要记下 prompt 模板和解码参数，即测验 Q16 说的控制变量）

### Part 3 选择题评分（目标 12 分钟）

坑：
- 字母要按 docstring 识别：单独的大写字母，后面紧跟 `)`、`.`、`:` 或者答案结尾。用 `\b[A-D]\b` 去找，会把句首的冠词 "A" 当成选项 A。
- 超出选项数的字母不算。写死 `[A-D]` 又不检查范围，2 选 1 的题答 "C" 时，`score` 里的 `choices[2]` 会报 IndexError；测试用 2 个选项的 "(C)" 拦这一条。
- docstring 里“单独的大写字母”这一条没有测试，句首冠词那条断言测的是字母后面跟什么。不写 `\b` 的正则（比如 `([A-Z])(?=[).:])`）也能通过测试，但会把 "CD." 里的 D 当成选项 D。读候选人的正则时留意，可以当追问。
- 全文匹配要求整个答案就是某个选项的文本（忽略大小写、首尾空格和句号）。用“选项文本出现在答案里”，`dog barking and a siren` 里同时有三个选项的文本。
- 同一个选项提两次还是一个选项；两个不同的选项，一个都不选。用集合，不要数匹配次数，也不要取第一个或最后一个。
- 至少两个选项才是选择题，这是课里 Step 3 的 `len(item["choices"] or []) > 1`。漏了 `or []`，开放题的 None 会报 TypeError。
- 没有输出、调用失败、解析不出来的都算错，而且留在分母里。只在读得出来的答案上算，speech 会从 1/3 变成 1/2。
- 随机水平按每题的选项数算：`1/len(choices)` 的平均。写死 25% 只对 4 选 1 成立。
- macro 是各类别准确率的平均，overall 是按题平均，这组数据分别是 0.52 和 0.4。
- 最后一段用给好的 `BenchmarkRun` 把 Part 2 和 Part 3 串起来：第一次跑时 mx-3 超时，存成 None；第二次只重新问它；从库里读出原始输出再打分，结果要和直接打分一致。

追问：
- "multi is 25% here, and so is chance. What do you tell the product team?"（多音频比较就是随机水平；skill 文件的规则是低于 30% 拒绝这类请求，确认超过 40% 才能上线；课里 MMAU-Pro 表上所有模型都在 20% 到 26% 之间）
- "Your parser and the official evaluator disagree on 3% of the items. Which number do you report?"（能和排行榜比的只有官方评分器的数字，自己的解析只是 sanity check，见课里 Step 3；把有分歧的题拿出来看）
- "Qwen2.5-Omni 52.2% vs GPT-4o Audio 52.5%. Is one better?"（1,800 题时单个准确率的标准误约 1.2 个百分点，0.3 点的差在误差之内；要做配对 bootstrap，这是第 17 课的内容）

### Part 4 实时上下文（目标 14 分钟）

坑：
- 输出是模型此刻会看到的 token id：turn 照原样，clip 是 AUDIO_BOS、n 个 AUDIO_PAD、AUDIO_EOS，和 Part 1 的 `expand` 一样。每个事件之后 yield 一次，测试按事件的下标取快照。
- 连续的音频块是同一个 clip，token 数按整个 clip 的样本数算。每块单独取整再相加，每一块都会向上取整：16 个 1000 样本的块算出 32 个 token，不是 25 个。每块各成一个 clip 也不对。
- 两个标记各占一个 id，也算在预算里。
- 先丢最旧的音频：从最旧那个 clip 的前面一个 token 一个 token 地丢，不是整段丢，也不是先丢最新的音频。一个 clip 丢空了，两个标记跟着一起去掉。
- 音频丢光了才丢 turn，从最旧的开始；system turn 和刚到的 turn 不丢；这两个加起来还超预算就报 ValueError。不分种类、一律先进先出，会先把 system turn 丢掉。
- 丢掉的东西不会回来，所以状态要跨事件保留。每个事件都从完整历史重新裁一遍的写法不对：丢过一次 turn 以后，历史总长一直超预算，之后新来的音频每次都会先被丢光。测试里有一段：长的 user turn 被丢掉以后，新来的音频要能放进它腾出来的位置。
- 还在录的 clip 也从前面丢。只有一段 clip 时，它就是最旧的音频。测试最后让麦克风连续送 2 秒（50 个 token），最后一个 context 是最新的 38 个 token 加两个标记；把正在录的 clip 保护起来不裁，会在这里报 ValueError。
- 每次 yield 一个新的 list。一直 yield 同一个 list 再原地修改，收集到的快照全都会变成最后的状态。
- 事件一到就要输出，不能先把整个流读完。测试会数拉取了多少个事件。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。

追问：
- "Why drop audio before text?"（同样一段对话，音频的 token 远比文字多，这里每秒 25 个，32K 的上下文只装得下 22 分钟左右；文字是对话的主线，旧音频的内容往往已经体现在后面的回答里。也可以先把旧音频转写或摘要成文字再丢）
- "Dropping tokens from the middle invalidates the KV cache after that point. What would you do?"（攒够一批再丢，减少重算；只在调用模型之前裁剪；或者用 sliding-window attention 的模型）
- "The lesson says most LALMs are offline batch models. What does a real streaming system need beyond this?"（流式 encoder、增量 prefill、用 VAD 判断用户说完了，这是第 11、14、15 课的内容）

### Part 5 消息展平（目标 12 分钟）

坑：
- content 可以是字符串（一个文本 part 的简写），也可以是 part 列表；tool_result 的 content 也一样，而且可以继续嵌套。把字符串当列表遍历，会一个字符一个字符地报 unknown part type。
- 片段按阅读顺序输出，也就是前序遍历。先处理完这一层的 part、再回头展开嵌套的 tool_result，顺序和编号都会错。
- "Audio N" 在整段对话里统一编号，按阅读顺序递增，不是每条消息从 1 开始。Qwen2-Audio 的 chat template 也这样编号，模型靠它区分多段音频（测验 Q13）。
- 计数器要在每次调用里新建。放在模块级，第二次调用会从 Audio 5 开始。
- 文本的 token 数是词数，音频用 Part 1 的 `clip_tokens`。照课里 `fake_audio_encoder` 的 `int(秒数 × 50)` 算帧数再整除 2，尾部会被截掉：0.5 秒得到 12 个 token，`clip_tokens` 是 13 个。
- 报错信息开头写出位置，比如 `messages[3].content[0].content[1].content[0]`。路径要随递归一路传下去，进入嵌套内容时加上 `.content`。
- 不是 16 kHz 的音频报 ValueError，不重采样；未知的 role 和 part 类型也报 ValueError。
- 空的音频（比如 VAD 门控以后什么都没剩）也报 ValueError，不能变成一个 0 个 token 的 clip。
- docstring 还要求 text 不是字符串时报 ValueError，测试没有覆盖；不检查的话，`count_words(None)` 报的是 AttributeError，也没有位置。没写 `sampling_rate` 的音频同样没有测试，见澄清问题。

追问：
- "The processor wants the clips as a list, in the same order as their placeholders. How do you guarantee that?"（在同一次遍历里既产出占位符又收集音频，编号和列表顺序来自同一个计数器）
- "One tool result holds a 40-minute recording."（按 Part 4 的预算处理；或者在工具一侧先切段、先 diarize，只把相关的片段放回对话）
- "Why is `int(0.58 * 50)` a bug in the lesson's encoder?"（浮点乘法得到 28.999999999999996，截断成 28，正确的帧数是 29；帧数要用整数样本数来算）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 token 预算、评测可复现、随机水平和误差、KV cache、并发写入 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
