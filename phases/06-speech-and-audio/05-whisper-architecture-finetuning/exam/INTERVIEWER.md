# 面试官手册：LongForm（06/05）

候选人计时期间不要看。候选人手里只有 README、`longform/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 最后一个窗口要不要往回挪，凑满 30 秒？ | "No. The last window starts on the schedule and stops at the end. Whisper pads it." |
| 1 | 空录音怎么办？ | "Raise a ValueError. The code already does." |
| 1 | overlap 不是整数个样本怎么办？ | "Round it to the nearest sample. The code already does." |
| 2 | 时间戳不在 0.02 秒的格点上，要不要就近取整？ | "No. An off-grid time is a bug upstream. Raise a ValueError." |
| 2 | language 是 en、task 是 translate，合法吗？ | "Yes. Whisper just writes English. The tests don't cover it." |
| 2 | 文本里出现 `<\|` 怎么办？ | "Raise a ValueError. It can't be told apart from a special token." |
| 2 | previous 是空字符串时怎么写？ | "Write `<\|startofprev\|>` with nothing after it. An empty string and None are different decodings, the same as for text. The tests don't cover it." |
| 2 | segments 顺序乱了，或者互相重叠？ | "Raise a ValueError. Whisper's timestamps only move forward. The tests don't cover it." |
| 3 | 某个窗口的输出没有时间戳怎么办？ | "It can't be stitched. The service only asks for timestamped output." |
| 3 | 词的中点正好落在分界点上？ | "It's in the docstring: the later window." |
| 3 | 词的结束时间越过了真实音频，要不要截到音频结尾？ | "No. Keep the times Whisper gave. Only a word that starts in the padding is dropped." |
| 4 | 流结束时剩下的不足一个窗口，要不要转写？ | "Yes. Decode whatever is left, unless nothing is left." |
| 4 | 判成幻觉的窗口，要不要发一个事件告诉客户端？ | "No event. Just skip it." |
| 4 | previous 要不要只留最后 223 个 token（Whisper 的上限）？ | "Whisper does. Here, no. The tests don't need it." |
| 5 | adapter 的参数算不算进 total？ | "Yes, the way PEFT's print_trainable_parameters counts all params." |
| 5 | bias 要不要训练？ | "No. bias='none', as in the lesson." |
| 5 | PEFT 的 target_modules 列表不认通配符吧？ | "Right. PEFT wants a single regex string for patterns. Here each name in a target may use shell wildcards, as the docstring says." |

## 每关：要看什么、提示、追问

### Part 1 修窗口计划（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 个护栏：

1. `mel_frames` 用的是课里 `encoder_frames` 的不补边公式 `1 + (n - 400) // 160`：30 秒算出 2998 帧，10 ms 的 clip 算出 −1。错误不在 `mel_frames` 报出来，而是在 `plan_windows` 的下一步，`encoder_positions` 的输入检查报 ValueError。
2. `encoder_positions` 向下取整 `n // 2`。kernel 3、stride 2、padding 1 的卷积输出 ceil(n / 2) 个位置：1 帧是 1 个位置，201 帧是 101 个。
3. `plan_windows` 每加一个窗口，都要扫一遍之前所有的窗口，看新窗口是不是被包含，是 O(n²)。60 小时的录音有 8,640 个窗口，要 1.2 秒左右。
4. 这次扫描掩盖了循环本身的 off-by-one：`range(0, n, step)` 在某个窗口已经到达结尾之后还会再起窗口，新窗口整个落在前一个里面，30 秒的录音会多出 25–30 秒这一段。课里的 `chunk_schedule` 用 `if end == total_seconds: break` 避开了这个问题。
5. 护栏：最后一个样本也要被覆盖。把录音截到整帧（`n - n % 160`），或者跳过只多出不到 1 秒的尾窗，都会在 55 秒加 1 个样本这条断言上挂掉。把最后一个窗口往回挪、凑满 30 秒，会在第一条断言上挂掉（澄清问题里已经说了不挪）。

看什么：是不是先读 traceback、顺着 −1 往上游找；是不是先 `print(plan_windows(...))` 看实际的窗口；去掉扫描、看到多出的窗口之后，是去修循环，还是把扫描换个写法加回来。

提示：
- H1："Which function first produced a value that the next one rejected?"
- H2："How many frames does a centered STFT give for 160 samples, before Whisper drops the last one?"
- H3：直接指出 `mel_frames` 的公式和 docstring 不一致。

追问：
- "Why is 30 s exactly 3000 frames and not 2998?"（center=True 两端各补 200 个样本，帧数是 1 + n // 160，Whisper 再丢掉最后一帧；课里的公式是不补边的）
- "Why plan in samples rather than seconds?"（`int(2.01 * 16000)` 是 32159；浮点秒数换算成样本会截断，`start += step` 累加还会漂移）
- "The last window holds 15 s of audio. What does Whisper see in the other 15 s, and what can go wrong there?"（补零的静音；课里的 Pitfalls 说会在尾部静音里幻觉，Part 3 用 positions 处理）

### Part 2 decoder 序列（目标 12 分钟）

坑：
- 文本要原样保留，包括开头的空格。BPE 的词 token 自带前导空格，`" Hello"` 和 `"Hello"` 是两个 token。解析时 `strip()` 会让往返失败。
- 时间戳写成两位小数：`<|0.70|>`，不是 `<|0.7|>`，也不是 `<|0.7000000000000001|>`。
- 格点检查不能用 `%`：`0.58 % 0.02` 是 0.0199…，连 `30.0 % 0.02` 都不是 0。要先 `round(t / 0.02)` 得到格数，再比较差值。
- `int(t / 0.02)` 会截断：0.58 变成 28 格，写出 `<|0.56|>`。解析时用“格数 × 0.02”还原也不行：35 × 0.02 是 0.7000000000000001，往返不相等。
- 也不能先取到百分位再看奇偶：`round(t * 100) % 2` 会把 1.081 当成 1.08 收下，写出去再读回来就变了。格点检查的容差只能盖住浮点误差，不能盖住真正的偏差。
- 时间戳 token 只到 `<|30.00|>`，30.02 秒没有对应的 token，要报 ValueError。窗口里出现 30 秒以后的时间，多半是上游忘了减去窗口起点。
- 照抄课里的 `build_prompt`：task 只要不是 "transcribe" 就当成翻译，拼错的 "transcription" 也不报错；`LANG[language]` 报的是 KeyError，测试要的是 ValueError。
- `<|notimestamps|>` 后面又出现时间戳、缺 `<|endoftext|>`，都要报 ValueError。
- 没有 segments、text 也是 None 的 decoding（`Decoding("is")`）要写成不带 `<|notimestamps|>` 的形式，读回来 text 还是 None。写成 `<|notimestamps|>` 加空文本，读回来就成了 `text=""`。

追问：
- "How many timestamp tokens are there?"（`<|0.00|>` 到 `<|30.00|>` 共 1,501 个，排在词表最后：50,364 + 1,501 = 51,865。0.02 秒就是一个 encoder 位置）
- "Why does the prompt carry both a language token and a task token?"（语言 token 说的是音频里的语言，任务 token 决定转写还是翻成英文；法语音频翻英文是 `<|fr|><|translate|>`）
- "What does `<|startofprev|>` do, and why is it risky?"（`condition_on_previous_text` 把上文喂给 decoder；一次幻觉会污染后面所有窗口，Part 4 处理）
- "What does your parse do with `<|xx|>` as the language, or `<|0.7|>` as a timestamp?"（docstring 要求报 ValueError，测试不覆盖。最省事的写法是解析完用 to_text 再写一遍，和输入不同就报错）

### Part 3 拼接重叠窗口（目标 12 分钟）

坑：
- 窗口里的时间加上窗口起点，才是录音里的时间。直接用浮点数相加会得到 27.240000000000002，所以 docstring 要求保留两位小数。
- 词按中点归属，不按起点。按起点归属时，27.24–27.76 的 " split" 会留在前一个窗口，52.0–53.2 的 " again" 也一样。
- 中点正好落在分界点上时归后一个窗口。两边都用 `<=` 和 `>=` 会重复，两边都用 `<` 和 `>` 会丢词。在样本整数上比较最稳，浮点数在这种边界上可能差一个 ulp。
- 只在相邻窗口之间裁剪。课后练习“每块只保留距离块边界超过 2.5 秒的词”如果对每个窗口的两端都用，会丢掉录音开头和结尾的词。
- 分界点是实际重叠区的中点，不是固定的 2.5 秒：`overlap_s=2.0` 时分界点在 29 秒。
- 最后一个窗口只有 15 秒真实音频，后面是补零。从补零里解码出来的 " Thanks for watching!" 要丢掉（课里的 Pitfalls：短 clip 补零后会在尾部的静音里幻觉）。判断用 Part 1 算出的 positions × 0.02 秒；用真实样本数 `window.end - window.start` 也能通过，两者最多差 10 ms。
- 判断补零看词的起点。最后一个词 " end" 是 14.8–15.4 秒，结束时间越过了真实音频，但它是在真实音频里开始的，要保留。按结束时间或中点判断，都会丢掉录音的最后一个词。
- 最后一段是端到端检查：Part 1 的窗口计划、Part 2 的解析和这一关的拼接串起来。模拟的 Whisper 在窗口边缘只听到半个词，结果里每个词必须恰好出现一次。

追问：
- "Suppose there were no timestamps. How would you merge the overlap?"（对重叠区两边的词序列做最长公共片段对齐，从对齐区的中间接上；HF 的 chunked pipeline 不带时间戳时就是这么做的）
- "Why not cut at silence instead?"（WhisperX 用 VAD 在静音处切，不会切在词中间，也不会把静音送进模型）
- "What do overlapping windows buy over sequential decoding?"（窗口之间互不依赖，可以整批送进 GPU；代价是重叠区重复计算、需要拼接）

### Part 4 流式转写（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：每个事件是 `data: <json>` 加一个空行，也就是以 `\n\n` 结尾，最后一个是 `data: [DONE]`。只用一个 `\n`，事件就分不开。
- 窗口要跨块拼接，不管怎么切块（包括空块），结果都一样。
- 流结束时剩下的样本也要转写，长音频转写不能丢尾巴（这一点和 03 的窗口打标不同）。但流正好是整数个窗口时，不能再用空窗口多调一次 decode。
- 一个窗口满了就要马上解码、输出，不能先把整个流读完。测试会数被拉取了多少块。
- 幻觉判断看整个窗口的文本，不是每个 segment 分开看；比较时忽略大小写和标点。"Thanks for watching!"、"thanks for watching"、"Thanks, for watching." 是同一个三词组出现三次。
- 三词组要逐词滑动着数。这个窗口以 " Okay." 开头，循环从第 2 个词才开始；每 3 个词切成一组再数，切出来的组和循环错开一个词，同一组最多只出现两次。
- 只看这个窗口自己的文本，不要把上文拼进去一起查。上文是上次重置以来的全部文本，一小时里同一句话说上三次，就会把一个正常的窗口当成幻觉。测试里 5 个窗口都说 " hi"，每个都要输出。
- 判成幻觉的窗口不输出，而且要重置上文，不能把它的文本喂给下一个窗口（课里的 Pitfalls：`condition_on_previous_text` 的级联）。测试会检查每次 decode 收到的 previous。
- 时间要保留两位小数：最后一个窗口从 90 秒开始，90 + 8.46 是 98.46000000000001。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。

追问：
- "Whisper itself flags a window when its gzip compression ratio is above 2.4. Why does that catch loops?"（重复的文本压缩得特别好；Whisper 会换更高的温度重新解码，用到 0.5 以上的温度时还会清空上文）
- "What else would you drop before it reaches the user?"（no-speech 概率高且平均 logprob 低的窗口；更好的办法是先用 VAD 门控，静音不送进模型）
- "The client disconnects mid-stream. What runs, what leaks?"（`aclose()` 在 yield 处抛 GeneratorExit；正在跑的 decode 要能取消，缓冲区随生成器释放）
- "Why consecutive windows here, but overlapping windows in Part 3?"（流式要尽快出字，顺着窗口带上文解码；离线可以并行解码再拼接）

### Part 5 LoRA 参数（目标 12 分钟）

坑：
- 树里 dict 和 list 混用：layers 是 list，路径里用下标（`layers.0`）。只处理 dict 会在 list 上报错，或者漏掉所有层。
- target 按 PEFT 的规则匹配路径末尾的名字，所以 `"q_proj"` 同时命中 self-attention 和 cross-attention（`encoder_attn`）的 q_proj。课里的 `lora_params` 正是漏了这部分，还把 Turbo 的 encoder 也按 4 层算：它给出 655,360，正确的是 3,276,800。
- 带点、带通配符的 target 要逐段比较：`"decoder.layers.*.fc1"` 只命中 decoder 的 4 个 fc1。
- 比较的是整段名字。`"proj"` 不能命中 `q_proj`，要报 ValueError；对整条路径做 `fnmatch(path, "*" + target)` 会让它命中所有的 q_proj、k_proj、v_proj 和 out_proj。整条路径加 `"*."` 前缀再 fnmatch 能通过测试，区别只在通配符跨段的时候：按 docstring 逐段比，`"decoder.*.fc1"` 什么都不命中，可以拿来追问。
- 两个 target 命中同一层时，这一层只挂一个 adapter。按 target 循环、往 list 里追加，`["q_proj", "v_proj", "encoder_attn.q_proj"]` 会把 cross-attention 的 q_proj 算两遍。
- 一个 [out, in] 权重上的 adapter 有 rank × (in + out) 个参数。课里的 `2 * d * rank` 只对方阵成立，fc1 是 5120 × 1280。
- `proj_out` 和 `embed_tokens` 共享权重：total 里只算一次；给 `proj_out` 加 adapter 时，形状要从被共享的那个权重拿。
- bias 不训练；adapter 参数算进 total；某个 target 匹配不到任何模块、或者匹配到的不是 Linear 层，都要报 ValueError。这比 PEFT 严格：PEFT 只在整张列表一个模块都没命中时报错，Embedding 和 Conv1d 上也能挂 LoRA。这里按 docstring 来。

追问：
- "Why q_proj and v_proj?"（LoRA 原论文的经验，性价比最高；数据多、领域差得远时再加 k_proj、out_proj 和 MLP）
- "You have 5 hours of audio. Which targets now?"（课里说少于 10 小时就冻结 encoder：只在 decoder 上加，比如 `"decoder.layers.*.self_attn.q_proj"`）
- "Training is done. How do you serve it?"（把 B·A 合并回权重，推理没有额外开销；或者保留 adapter，按领域热切换）
- "Where does the 4x memory saving come from?"（梯度和优化器状态只为 0.4% 的参数保存；冻结的底座权重还在显存里，要再省就量化，比如 QLoRA）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出批量、取消、幻觉防护、显存 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
