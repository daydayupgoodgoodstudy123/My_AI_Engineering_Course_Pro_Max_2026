# 参考答案讲解：LALMKit（06/10）

计时结束后再看。参考实现在同目录的 `lalmkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修输入代码

**现象**：解锁后的第一个错误是 `merge` 里的 ValueError：`4 audio vectors for 3 AUDIO_PAD positions`。`merge` 本身没有 bug，它只是第一个发现两边对不上的地方。

**顺着往上找**：音频向量来自 `project`。5 帧的 clip 两两一组，最后一帧单独成组、补零，一共 3 个向量；2 帧的 clip 1 个，合计 4 个。AUDIO_PAD 的个数来自 `expand` 收到的 `counts`，也就是 `audio_tokens`，它把 `5 // 2` 算成了 2。`stack_frames` 的 docstring 写明补零、不丢帧，所以错的是计数，不是 projector。这一关想练的是：报错的位置往往不是出 bug 的位置；两个数对不上时，先想清楚哪一个是事实。

**依次修四处**：

1. `audio_tokens` 向上取整：`-(-num_frames // stack)`。
2. `expand` 在每个 AUDIO 槽位原地展开。原来的写法和课里的 `interleave_with_text` 一样，把所有音频放在文本前面。多音频的提问里，“Audio 1 和 Audio 2 哪个更响”就失去了位置信息。
3. `pad_batch` 的 mask 按每行的长度生成，不能用 `token != PAD` 反推：这里 `PAD = EOS`，第二行里真实的 EOS 被遮掉了。位置 id 是从 mask 算出来的，所以 mask 一错，位置也跟着错。
4. 位置 id 不要对每个 token 重新求前缀和。原来的写法是 O(L²)，十分钟的通话（15,000 个 audio token）要 0.5 秒左右。每行直接写成 `[0] * 填充数 + list(range(行长))`。

**护栏**：遇到 ValueError，最省事的办法是让两边凑上：在 `merge` 里把音频截到槽位数，或者让 `stack_frames` 丢掉最后不满的一组。这样不报错了，但帧数不是 stack 整数倍的 clip，最后那几帧没有进模型，ids 断言会挂。`(n + 1) // stack` 只在 stack=2 时等于向上取整，stack=3 的断言会挂。

## Part 2 结果库

参考实现只有一张表：`seq` 自增主键记录第一次写入的顺序，`(model, item_id)` 唯一，`output` 允许 NULL。写入用 upsert：

```sql
INSERT INTO predictions (model, item_id, output) VALUES (?, ?, ?)
ON CONFLICT (model, item_id) DO UPDATE SET output = excluded.output
```

- **重跑是替换**：冲突时更新原来那一行，seq 不变，所以重跑过的 item 留在原位。`INSERT OR REPLACE` 是先删后插，行会拿到新的 seq，排到最后；`INSERT OR IGNORE` 留下的是第一次的输出。
- **顺序要写出来**：`predictions` 用 `ORDER BY seq`。不写 ORDER BY 时，SQLite 会走 (model, item_id) 的唯一索引，按 item_id 的字母顺序返回。测试里的 q-417、q-052、q-139 故意不按字母顺序记录，所以靠默认顺序或 `ORDER BY item_id` 都会挂。`pending` 按传进来的顺序返回。
- **按模型区分**：唯一约束只建在 item_id 上，一个模型的答案会盖掉另一个模型的。
- **原样存储**：前导空格、`\r\n`、结尾的空格和换行都原样存、原样读回。官方评分器读的是原始输出，以后换解析规则，也要从原话重新算。
- **None 和空字符串**：None 表示调用失败，`pending` 会把它交给下一次重跑；空字符串是模型真的什么都没说，是一个答案（算错），不重跑。
- 和样板一样，写入要 commit（参考实现用 `with self._db:`），建表要写 `IF NOT EXISTS`。

## Part 3 选择题评分

`parse_choice` 分两步收集候选，最后要求恰好一个：

```python
LETTER = re.compile(r"\b([A-Z])(?=[).:]|\s*$)")
```

- 字母：单独的大写字母，后面紧跟 `)`、`.`、`:` 或者答案结尾。句首冠词 "A dog ..." 后面是空格，不算；"(B)"、"B."、"Answer: C" 都算。超出选项范围的字母不算，比如 2 个选项时的 C。写死 `[A-D]` 又不检查范围的话，`score` 取 `choices[2]` 会报 IndexError。
- 全文：整个答案去掉首尾空格和句号以后，忽略大小写，等于某个选项的文本。不能用“包含”：`dog barking and a siren` 同时包含三个选项的文本。
- 候选放在集合里：同一个选项提两次还是一个；两个不同的选项，一个都不选。

`score` 只算至少有两个选项的题（课里 Step 3 的过滤条件），按类别统计答对数、题数和 `1/len(choices)` 之和：

- 没有输出、调用失败、解析不出来的都算错，题数照算。这组数据 speech 的准确率是 1/3；只在读得出来的答案上算，会变成 1/2。
- chance 是随机猜的期望准确率。speech 的三道题分别有 2、4、3 个选项，随机水平是 0.36，不是 0.25。
- overall 是按题平均（0.4），macro 是各类别准确率的平均（0.52）。multi 是 0.25，正好等于随机水平，这就是课里说的多音频比较接近随机。

最后一段用给好的 `BenchmarkRun` 把 Part 2 和 Part 3 串起来：第一次跑时 mx-3 超时，存成 None；第二次只重新问它；报告从库里读原始输出再打分，和直接打分的结果一致。

## Part 4 实时上下文

状态是一个按到达顺序排列的片段列表，每个片段是一个 turn，或者一个 clip（累计的样本数，加上已经从前面丢掉的 token 数）：

```python
async for event in events:
    if isinstance(event, AudioChunk):
        if clip is None:            # 一段连续音频的第一块
            clip = _Clip()
            segments.append(clip)
        clip.samples += event.num_samples
    else:
        clip = None
        segments.append(event)
    _fit(segments, budget, event)
    yield _render(segments)         # 每次都是新的 list
```

- clip 的 token 数是 `clip_tokens(总样本数) - 已丢弃数`，所以无论音频怎么切块，结果都一样。每块单独取整再相加，16 个 1000 样本的块会算成 32 个 token，而不是 25 个。
- `_fit` 先算出超了多少，再从最旧的 clip 开始，从它的前面丢 token。一个 clip 丢空了，两个标记也一起去掉，多省 2 个。
- 音频丢光了还超预算，才从最旧的 turn 开始丢，跳过 system turn 和刚到的 turn；还不够就报 ValueError。
- 只有一段 clip、而且还在录的时候，它就是最旧的音频，也从前面丢。麦克风连续送 2 秒（50 个 token）、预算 40 时，最后的 context 是最新的 38 个 token 加两个标记。
- 丢掉的东西不会回来，所以片段列表要跨事件保留。每个事件都从完整历史重新裁一遍的话，丢过一次 turn 以后历史总长一直超预算，新来的音频每次都会先被丢光；测试里长 user turn 被丢掉以后再来一段音频，查的就是这一点。只有还开着的 clip（后面还有音频块接上）会在新音频到来时重新出现。
- 每个事件之后 yield 一次，不提前读后面的事件。

## Part 5 消息展平

一个递归函数 `walk(content, role, where)`：

- 字符串就是一个文本片段；列表就逐个处理 part。遇到 `tool_result` 就递归进它的 `content`，路径加上 `.content`。
- 遇到音频就把计数器加一，标成 "Audio N"。计数器属于这一次 `flatten` 调用，所有消息共用，按阅读顺序递增；放在模块级，第二次调用会接着上一次编号。
- token 数：文本是词数，音频用 Part 1 的 `clip_tokens`。
- 报错时把当前路径写在信息开头，例如 `messages[3].content[0].content[1].content[0]: audio must be 16000 Hz, got 44100`。
- 空的音频也报错。课里 Pitfalls 建议先做 VAD 门控，门控以后一段 clip 可能什么都不剩；放过去就成了一个 0 个 token 的 clip，模型看到的只有一对空的起止标记。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链调试，能把 LALM 的输入对齐（音频占位符、projector 产出的 token 数、左填充、mask 和位置），能为评测建一个可以重跑、原样保存输出的结果库，能把自由文本答案稳健地映射到选项、按类别和随机水平报告，能写一个按预算裁剪的流式上下文，也能处理嵌套的多模态消息。它不涉及真实的音频 encoder 和 projector 的训练（课里的 Stage 1、Stage 2），不涉及真实的 tokenizer 和 chat template，也不涉及官方评分器用的 embedding 匹配和 LLM 评判。课里 Step 1 到 Step 3 的真实模型调用和 MMAU-Pro 评测需要另外动手跑。
