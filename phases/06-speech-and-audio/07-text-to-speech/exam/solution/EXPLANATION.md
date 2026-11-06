# 参考答案讲解：TTSFront（06/07）

计时结束后再看。参考实现在同目录的 `ttsfront/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修文本前端

**现象**：解锁后的第一个错误是 `rule_phones` 报的 `ValueError: no grapheme rule for '-' in 'forty-two'`，而 `rule_phones` 本身没有错。

**顺着往上找**：`rule_phones` 只处理小写字母，"-" 是别人交给它的。phonemize 在词典里查不到 "forty-two"，才退回字形规则；这个词是 normalize 产生的；normalize 只是把 `number_words(42)` 的结果按空格拆开，而 `number_words` 用连字符连接十位和个位，和它 docstring 里的 "two thousand twenty six" 不一致。报错的位置离根因隔了三层调用。在 `rule_phones` 里给 "-" 加一条静音规则，或者像课里的代码那样跳过没有规则的字符，都能让报错消失，但 "forty-two" 仍然绕过了词典，念成 F AO R T Y T W AO，第一个断言照样挂。

**依次修四处**：

1. `number_words`：十位和个位之间用空格。
2. phonemize：先把词典的键统一成小写，建一次索引，再用小写的词去查。测试词典里的 "Kokoro" 是按产品名原样写的。
3. normalize：缩写后面紧跟的句点属于缩写。参考实现在读词之前把这种句点从 token 列表里去掉，这样它不会变成停顿，"Dr." 的上下文判断看到的下一个词也是 "Lee"，读作 doctor。
4. `rule_phones`：规则最长 MAX_RULE（4）个字母，候选长度从 `min(MAX_RULE, 剩余长度)` 开始往下试。原来从剩余长度开始试，每个位置都要切出并哈希一串很长的子串，3000 个字母要 1.1 秒左右，修好后不到 2 毫秒。上限要用 MAX_RULE，不能照课里的代码写死成 `(3, 2, 1)`："tion" 有 4 个字母。

**护栏**：词典里没有的词要用字形规则、按最长匹配读出来，这是课里 Pitfalls 说的 OOV 兜底。为了提速跳过长词、截断、丢掉 OOV 词，或者把匹配长度改小（只按单个字母读、写死成 3、从短往长试），都会在 "Ghumare station" 和那串 "ha" 上挂掉。最长匹配把 "station" 读成 S T AH SH AH N；匹配长度不到 4 时，"tion" 被拆成 T IH AO N。

## Part 2 发音词典

参考实现只有一张表：`seq` 自增主键记录添加顺序，`word` 存小写，`phones` 存 JSON 列表，`priority` 是整数。查询按 `ORDER BY priority DESC, seq`，同一个词的多种发音都留着。

容易漏的几点：

- **音段原样还原**：IPA 的一个音段可能由几个码位组成。"ɑ̃" 是 ɑ 加组合波浪号 U+0303，"t͡ʃ" 是 t、连音符 U+0361、ʃ 三个码位。用 JSON 列表存，`json.loads` 读回来逐码位一致。把音段拼成一个字符串再用 `list()` 拆，组合符号会变成单独的“音段”。
- **不做归一化**：测试里的 "õ" 写成 o 加 U+0303。NFC 会把它合成 U+00F5，打印出来一样，`==` 却不相等。反方向也一样："ich" 的 "ç" 是一个预组合码位 U+00E7，NFD 会把它拆成 c 加 U+0327。两种写法都要原样回来，所以哪种归一化都不能做。词典的职责是原样保存调用方给的音标。
- **非法音段在 Python 里拦**：空音段、以组合符号开头的音段（`unicodedata.category` 以 M 开头）、重复的发音，都抛 `ValueError`。只靠 UNIQUE 约束，抛的是 IntegrityError。查重和查词一样不分大小写：测试用 "Tomato" 再加一次 tomato 已有的发音，要拿小写的词去比。
- **commit 和重开**：`with self._db:` 自动提交，建表写 `IF NOT EXISTS`。
- `table()` 给每个词取第一种发音，正好是 phonemize 要的词典格式，`TTSService` 就是这样把 Part 2 接到 Part 1 上的。

## Part 3 时长取整成帧

FastSpeech 式的模型给每个音素预测一个时长，length regulator 需要的是整数帧。参考实现用最大余数法：

```python
shares = [max(Fraction(1), Fraction(d) / Fraction(hop_ms)) for d in durations_ms]
total = math.floor(sum(shares) + Fraction(1, 2))
frames = [math.floor(s) for s in shares]
order = sorted(range(len(shares)), key=lambda i: (frames[i] - shares[i], i))
for i in order[: total - sum(frames)]:
    frames[i] += 1
```

- 总数先定下来：份额之和四舍五入，0.5 进位。各自取整再相加，3 个 2.4 帧会变成 6 帧，丢了 1 帧。Python 的 `round()` 对 0.5 取偶数，`round(2.5)` 是 2。
- 每个音素先拿整数部分，差的帧按余数从大到小一个一个补，余数相同给前面的音素。
- 浮点在这里会出错：30 ms 和 55 ms 是 2.4 帧和 4.4 帧，余数在数学上相等，浮点算出来却一个是 0.3999999999999999、一个是 0.40000000000000036，那一帧就给了后面的音素。`Fraction(d)` 按浮点数的精确值计算，相等的余数就是相等。
- 至少一帧要放在份额里（课里的 `max(1, ...)`），这样总数也按至少一帧来算。分配完再补 `max(1, f)`，总帧数会比时长多。
- 最后一段把 Part 1–3 串起来：词典给出 "kokoro" 的发音，前端读出 "21" 和标点，课里的时长表按 1.25 倍语速缩短，再分配成帧。帧区间要首尾相接，总帧数等于缩短后的总时长。

## Part 4 流式切块

用一个缓冲区，每来一段 delta 就从头找第一个已经能判断的切点：

```python
async for delta in deltas:
    buffer += delta
    while (cut := _first_cut(buffer, min_chars)) is not None:
        chunk, buffer = buffer[:cut].strip(), buffer[cut:]
        if chunk:
            yield _event(seq, chunk)
            seq += 1
```

- 标点后面必须跟着空白才算切点，所以缓冲区最后一个字符永远不判断，等下一段 delta 来了再说。"3." 和 "50" 分两次到达时，这样不会把数字切开；"3.50" 和 "1,000" 也不需要单独的数字规则。空白用 `str.isspace()` 判断，换行也算。
- 句点前面的整个词在 ABBREVIATIONS 里（"Dr."）就不切。只看后缀的话，"rest." 也会被当成 "St."。
- 句末的 . ? ! 不看长度，短句也马上发，首句延迟靠这个；, ; : 要等 chunk 够 min_chars 才切。长度按发出去的样子数：去掉两头空白，带上末尾的标点，"which includes tax," 是 19。
- 一段 delta 里可能有好几个切点，所以用 `while` 一直切到没有为止。一凑齐就 `yield`，所以第一个事件出来时只拉取了 3 个 token。
- 流结束时把剩下的文本作为最后一块，空白不发。
- 格式由测试的解析代码决定：每个事件是 `"data: " + json.dumps(...) + "\n\n"`。JSON 要用 `json.dumps` 生成，文本里的引号才会被转义。

## Part 5 SSML 展开

先写 `_tag()` 去掉命名空间前缀，每个元素都经过它，再递归 `walk(element, prosody)`：

- `prosody` 的 rate 乘上外层的 rate，pitch 加上外层的 pitch，得到内层的 prosody。
- 元素自己的 `text` 用内层的 prosody；每个子元素处理完后，它的 `tail` 用当前元素的 prosody。ElementTree 把子元素后面的文字挂在子元素的 tail 上，这是最容易读错的地方。
- 文字先放进一个待合并的缓冲区。prosody 变了、遇到 break、或者文档结束时，把缓冲区拼起来，空白折叠成一个空格，非空才输出一段。片段先拼接再折叠空白，"T T S" 和后面的 "," 之间才不会多出空格。
- `break` 先清空缓冲区，再输出 `{"break_ms": ...}`。单位先判断 "ms" 再判断 "s"。
- `say-as` 复用 Part 1 的 `digit_words` 和 `number_words`。
- 其他元素抛 `ValueError`，消息里带上元素名。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链找到根因，能为一个词多种发音的 IPA 词典建表并原样存取，能用精确的最大余数法把时长变成帧，能写出跨 delta 判断切点的流式生成器，也能递归展开带继承属性的标记。它不涉及声学模型、vocoder、语音克隆的训练或推理，也不涉及真实的 espeak-ng 或 Kokoro。课里 Step 2 到 Step 5 的内容需要另外动手跑。
