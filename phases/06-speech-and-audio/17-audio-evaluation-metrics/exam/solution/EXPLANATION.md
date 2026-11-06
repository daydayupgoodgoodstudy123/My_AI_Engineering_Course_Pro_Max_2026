# 参考答案讲解：EvalSuite（06/17）

计时结束后再看。参考实现在同目录的 `evalsuite/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修评分代码

**现象**：解锁后的第一个失败在日文那条断言上：`会議は３時からです。` 和 `会議は3時からです` 的 CER 是 0.2，全角的３和句号各算了一个错误。

**第一处**：`_units` 的按字分支直接拆原文，没有经过 `normalize`。这是课里 `cer()` 的老问题（测验 Q10）：WER 规范化了，CER 没有，同一份报告里两个数口径不一样。

**补上规范化以后**：中文那条断言报 `ValueError: nothing to score in reference '我们明天去公园'`。参考文本明明不空，空的是规范化以后的结果：`normalize` 里还留着课里的 `re.sub(r"[^a-z0-9\s]", "", text)`，汉字、假名、西里尔字母、é 全被删掉了。报错的 `error_counts` 离根因隔着两层调用（`score` → `error_counts` → `_units` → `normalize`）。这一关想练的是：报错的位置往往不是出 bug 的位置。前面的标点表已经把标点换成了空格，这一行删掉就行。

**第三处**：What's 和 what is 还是对不上。标点表把撇号也换成了空格，缩写表在后面才查，what's 早已变成 what s。缩写要在去标点之前展开，测验 Q9 的参考答案也提醒了这个顺序。

**最后是速度**：`_punctuation_table()` 每次调用都把 Unicode 的 111 万个码位扫一遍，一次 40 多毫秒，测试里的 24 对句子要 2 秒左右。表只要建一次，参考实现加了 `functools.cache`；模块级常量，或者逐字符查 `unicodedata.category`，也都可以。

修好以后的 `normalize`：

```python
text = unicodedata.normalize("NFKC", text).casefold().replace("\u2019", "'")
if language == "en":
    text = CONTRACTION.sub(lambda m: CONTRACTIONS[m.group()], text)
text = text.translate(_punctuation_table())
if language == "en":
    text = DIGITS.sub(lambda m: f" {spell_number(int(m.group()))} ", text)
return " ".join(text.split())
```

NFKC 把全角字符折成半角，也把 `cafe` 加组合重音符合成 `café`；casefold 处理大小写；缩写和数字只对英文做，中文里的 3 号楼不会变成 three 号楼。

**护栏**：常见的改坏写法各有一条断言接着：

- 为了提速换回课里的 ASCII 正则：中文和俄文被删光，又回到 `nothing to score`。
- 换成 `re.sub(r"[^\w\s]", " ", text)` 或者 `isalnum()` 过滤：Python 的 `\w` 和 `isalnum()` 都不含组合符号（Unicode 的 M 类），印地语的元音符号被当成标点换成空格。किताबें（书，复数）和 किताब 的区别只在词尾的符号上，换掉以后两边是同一串字母，这句的 WER 从 1/4 变成 0。docstring 写的是各种文字的字母、组合符号和数字都保留，标点表只换掉 P 和 S 两类，正是为了这个。
- 只删 `string.punctuation` 里的 ASCII 标点，或者用 NFC 代替 NFKC：日文那句的句号或全角３留了下来，又回到第一条断言。
- 用 NFKD 去掉组合符号来“统一重音”：café 和 cafe 变成同一个词，可在法语里这是真错误，`un café noir` 对 `un cafe noir` 应该是 1/3。
- 只保留字母：数字跟着标点一起没了，3 号楼和 5 号楼的 CER 变成 0。
- 不想调顺序，就把撇号排除在标点之外：缩写是保住了，`'yes'` 两边的引号却留了下来。

## Part 2 排行榜

参考实现只有一张表：`seq` 自增主键记下每个模型第一次出现的先后，`(model, benchmark, metric)` 上有唯一约束，数值和区间两端都存成 REAL。Python 的 float 存进 REAL 再读出来是原样的，3167/52343 和 3166/52343 只差一个错误，打印出来都是 6.05%，排名照样分得开。

再次提交要更新原来那一行：

```sql
INSERT INTO results (...) VALUES (...)
ON CONFLICT (model, benchmark, metric) DO UPDATE SET
    value = excluded.value, n = excluded.n, ci_low = excluded.ci_low,
    ci_high = excluded.ci_high, protocol = excluded.protocol
```

`INSERT OR REPLACE` 看起来一样，其实是先删后插：行号变了，重跑过的 tdt-0.6b 就排到了同分的 ctc-1.1b 后面。排名用 `ORDER BY value ASC|DESC, seq`，方向来自 METRICS。同分不能按模型名排：先出现的 tdt-0.6b 按字母排在 ctc-1.1b 后面，`ORDER BY value, model` 会把它们排反，也会掩盖 `INSERT OR REPLACE` 的问题。

容易漏的几点：

- **commit 和重开**：用 `with self._db:` 自动提交；建表写 `IF NOT EXISTS`。
- **最新的一次说了算**：重跑结果更差也要替换。只留最好的一次，等于让模型反复重跑、挑对自己最有利的数。
- **protocol**：课里第一条规则是“报告你的规范化规则”，FAD 也要求同一个参考集。规则不同的数不能放在一张榜上比，所以 `ranking` 遇到混用就报错；`submit` 不拦，因为重跑可以把规则统一过来。测试里的 aed-1.5b 就是这样：第一次按 whisper-en 规则算出 5.75%，按本榜的规则重算是 6.05%。同一个模型、同一份转写，换一套规范化规则就差了 0.3 个百分点，这也是规则不同的数不能放在一起排的原因。
- **校验看 METRICS**：UTMOS 必须在 1 到 5 之间；WER 没有上限，插入多的时候会超过 1（测验 Q2），按 0 到 1 校验会拒掉合法结果。
- **返回类型**：区间读回成 tuple，`Entry` 才能和测试里的值相等。

## Part 3 配对 bootstrap

`percentile_interval` 先排序，再从两端各去掉 k = round(B(1 − c)/2) 个。B = 1000、c = 0.9 时，1 − 0.9 在浮点里是 0.09999999999999998，乘出来是 49.99999999999999，`int()` 会截成 49，`round()` 才是 50。

`paired_bootstrap` 的核心是同一组下标给两个系统用：

```python
ids = sorted(baseline)
...
deltas = [delta([rng.randrange(n) for _ in range(n)]) for _ in range(replicates)]
```

- **按 id 配对**：两次运行列出句子的顺序可以不同，测试里就把其中一个倒过来了。按位置 zip 会把不同的句子配在一起。
- **两边的 id 完全一致**：参考实现直接比 `baseline.keys() != candidate.keys()`。只比句子数，换了一个 id 的运行会在取值时报 KeyError；只检查 baseline 的 id 都在 candidate 里，candidate 多出来的句子会被悄悄丢掉。
- **delta 是语料级的差**：整个测试集上两个系统各自的错误总数除以单位总数，再相减。逐句错误率之差的平均（课里 `ttr_wer` 的算法）是 −0.055，replicate 的平均也只是接近 −30/720。
- **为什么要配对**：同一句话对两个系统都难或都容易，配对后这部分方差就抵消了。测试里候选系统在 40 句里的 30 句上各少一个错误，配对的 95% 区间是 (−0.051, −0.033)；两个系统各自重采样，区间上端是 +0.022，看起来就不显著了。
- **从排好序的 id 抽**：抽样只取决于数据和 seed，不取决于结果是按什么顺序写下来的。
- **自己的随机数生成器**：`random.Random(seed)`，不动全局的 `random`，别处的代码不受影响，同一个 seed 永远得到同一个答案。
- **平局不算赢**：只改了一句的那组数据里，约 36% 的 replicate（(39/40)^40）没抽到这一句，delta 恰好是 0。只数 delta < 0，p_better 约 0.66，区间上端正好是 0，说明这一处改动不足以下结论。
- **最后一段**把 Part 1 和 Part 2 串起来：service 用 Part 1 的规范化给两次运行打分，没解码出来的 c4 按全部删除计，旧系统 9 个错误，新系统 1 个，delta 是 −8/30；`publish` 再用同一个 bootstrap 给新系统的 WER 配上区间，写进排行榜。

## Part 4 流式报告

状态只有每个域的三项累计：句子数、错误数、单位数，外加一共见过多少句。

```python
async for batch in batches:
    for result in batch:
        tally = totals.setdefault(result.domain, [0, 0, 0])
        ...
        seen += 1
        if seen % every == 0:
            report()
            reported = seen
            yield drain()
if seen != reported:
    report()
    yield drain()
```

- **rate 是合并后的比值**：一个域的错误总数除以单位总数。课里 Step 2 的 `ttr_wer` 把逐句 WER 取平均，seen=4 时 `*` 会算成 0.3375，正确的语料级值是 9/42 ≈ 0.214。短句的 WER 波动大，平均值会被它们主导。
- **`*` 行合并所有句子**，不是各个域 rate 的平均（那样是 0.35）。按切片报告是课里的 Pitfall：总体 WER 会掩盖某个切片的高错误率，两种数都要有。
- **计数跨 batch**：报告点由第几句决定，和 batch 怎么切无关，所以三种切法的输出逐字节相同。
- **结尾**：最后一句刚好是报告点时不再补一份；否则补一份。空的运行只有表头。
- **表头和排序**：表头在读第一个 batch 之前写一次，所以空的运行也有表头；每份报告里的域按名字排序，不按到达的先后。
- **格式由测试的 `csv.DictReader` 决定**：用 csv 模块写进 `StringIO`，`accented, L2` 会被正确地加上引号。手写逗号拼接会把这一行切成五列。
- **到点就输出**：`yield` 写在循环里面，第一份报告出来时只拉取了 2 个 batch。

## Part 5 套件汇总

一个递归 `visit(node, path, parent)`，每个节点都写进结果：

- **叶子**读 `results[(父节点名, 指标)]`，按 METRICS 换算：`(value − worst) / (best − worst)`，再截断到 0 到 1。WER 的 worst 是 1、best 是 0，所以 0.08 得 0.92；CER 1.25 得 0，而不是 −0.25。“越低越好就用 1 − value，否则用原值”的写法只对 0 到 1 的指标成立：UTMOS 的尺度是 1 到 5，3.8 应该得 0.7，不是截断后的 1。
- **组**取计入的子节点（权重不为 0）的加权平均，除以权重和。
- **缺失**：叶子没有结果是 None；计入的子节点里只要有 None，这个组就是 None，一直传到根。兄弟分支照常有分数。只在有结果的子节点上重新归一化，等于奖励不跑难任务的模型。
- **权重为 0** 的子节点照样写进结果，但不计入，缺了也不挡父节点。MMAU-Pro 的 multi-audio 在测试里就是这样：报告出来，但不进总分。
- **按路径记结果**：`wer` 同时出现在 librispeech-other 和 seed-tts-en 下面，按名字记就会互相覆盖。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试文本规范化（Unicode、语言、先后顺序、性能），用 SQLite 建一个有 upsert 语义的排行榜，实现配对 bootstrap，写一个按切片累计的流式报告，以及处理带权重和缺失值的嵌套结构。它不涉及 MOS 人评、UTMOS 和 SECS 背后的模型，不计算 EER（06/06）和 FAD（06/09），也没有用到真实的 ASR 模型、jiwer 或 Whisper 规范化器的完整规则。课里 Exercises 2 和 3（TTS 往返 WER、在 MMAU-Pro 上评测音频语言模型）需要另外动手跑。
