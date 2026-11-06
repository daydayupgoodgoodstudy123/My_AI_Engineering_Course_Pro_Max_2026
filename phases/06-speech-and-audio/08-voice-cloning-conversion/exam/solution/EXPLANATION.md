# 参考答案讲解：CloneGate（06/08）

计时结束后再看。参考实现在同目录的 `clonegate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修水印代码

**现象**：解锁后的第一个失败是 verifier 读第二段 clip 时 bits 对不上，而第一段读得对。`detect` 本身没有错。

**顺着往上找**：第一段对、第二段错，说明问题和“第几次调用”有关。`chips()` 从 `self._rng` 取值，这个 RNG 只在 `__init__` 里建了一次。stamper 盖第一段时取走了第 0 到 31999 个码片，盖第二段时接着取第 32000 到 63999 个。verifier 是另一个实例，读第二段时从第 0 个取起，当然对不上。docstring 写的是“每次调用、每个进程都从起点开始”。这一关想练的是：报错的是 verifier，出错的是 stamper。

**依次修四处**：

1. `chips()` 每次调用都新建 `random.Random(self.key)`，从密钥的起点取码片。只在开头加一句 `self._rng.seed(self.key)` 不够：两个迭代器同时存在时（比如同时检测两路通话），它们还是共用一个 RNG，互相抢码片。
2. `Evidence.scores()` 除以这一位样本能量的平方根：z = c / √e。音量乘以 g 时，分子乘以 g，分母乘以 |g|，分数不变。没有水印时，c 的方差正好是 e（码片是 ±1，和宿主不相关），所以 z 近似标准正态，阈值 4 才有意义。
3. `bit_accuracy` 的分母是载荷的位数。没有证据的位算错，不能从分母里拿掉；原来的写法遇到全是 None 还会除零。
4. `Evidence` 改成增量累加：构造时拿一个码片迭代器，每个样本只处理一次，每一位只记相关和与能量两个数。原来每次 `add` 都把收到的全部音频从头再算一遍，2 秒音频分 480 块喂进去要 0.75 秒，改完约 3 毫秒，内存也不再随通话时长增长。

**护栏**：

- 非盲检测。课里的 `detect_watermark(wave_original, wave_wm)` 要用原始音频相减。这里的 verifier 是另一个实例，手里只有 clip 和密钥，靠存原始音频的写法直接报 AttributeError。盲检测之所以可行，是因为宿主音频和伪随机码片不相关：对一位的 m 个样本求和，水印贡献 strength × m，宿主只贡献约 σ√m 的噪声，m 越大越容易分开。
- 复位的粒度。码片在每段 clip 或每条流的开头复位一次，块与块之间要接着取。如果每次 `add` 都从起点重新取，分块喂入的结果就和一次喂入不一样了。
- 两条流同时检测。测试最后交替给两个 Evidence 喂两段 clip，每个都要读出自己的载荷。码片的状态必须归迭代器自己，所以参考实现在 `chips()` 里新建 RNG，而不是复用 `self._rng`。

## Part 2 同意登记表

参考实现只有一张表：`consent_id INTEGER PRIMARY KEY AUTOINCREMENT` 给出 1、2、3 这样的 id，正好放进 16 位水印载荷；用途用排好序的 JSON 列表存，读回成 frozenset；时间用 `isoformat()` 存成文本，读回用 `datetime.fromisoformat()`，偏移和微秒都原样保留。

容易漏的五点：

- **原样读回**：带时区的 datetime 比较的是时刻，所以转成 UTC 再存，`==` 照样成立。测试因此比较 `isoformat()`。印度时间 4 月 22 日 01:15 签的字，在 UTC 是 4 月 21 日；同意书上写的是签字人当地的日期。
- **按时刻判断有效期**：有效区间是 [granted_at, expires_at)，两头都要查，签字之前不算有效。`Consent.allows` 在 Python 里比较 datetime。如果在 SQL 里比较 ISO 字符串，`2026-04-30T15:00:00+00:00` 排在 `2026-05-01T00:00:00+09:00` 前面，已经到期的同意还被当成有效。
- **commit 和重开**：用 `with self._db:` 自动提交；建表写 `IF NOT EXISTS`。
- **撤销**：只有 `revoked_at` 为空时才写入，第二次撤销保留第一次的时间，也不报错。有效的条件是 `at < revoked_at`，撤销那一刻就失效。
- **naive datetime**：授予、撤销、查询时都检查 `utcoffset()`，没有偏移就报 ValueError。

## Part 3 kNN-VC

`knn_convert` 先检查 k 在 1 到匹配集大小之间，k = 0 也报 ValueError；不查下限的话，k = 0 会悄悄返回空帧。然后对每个源帧，按余弦相似度从高到低给匹配集的下标排序。`sorted` 是稳定排序，平票时保持匹配集原来的顺序；先升序排再倒过来，平票就落到了最后一帧。排好后取前 k 个帧，逐维求平均。课里写的是“换成最近的一帧”，这里按课里列出的 kNN-VC 论文取 k 个最近帧的均值（论文用 k = 4），输出更平滑。用余弦而不用欧氏距离，是因为同一个音素换个音量，特征的方向不变、长度会变；论文在 WavLM 特征上用的也是余弦距离。

`CloneGate.convert` 只有三步：

```python
consent = self.registry.get(consent_id)            # 未知 id：KeyError
if not consent.allows(purpose, at):                # 用途、有效期、撤销
    raise PermissionError(...)
matching = [frame for owner, _, frame in self._frames if owner == consent_id]
```

`consent.allows` 查的是这一条同意。“alice 有没有覆盖广告的有效同意”是另一个问题：她有，但这次转换凭的是只覆盖配音的那一条，拿去做广告就要报 PermissionError。

为什么匹配集只能是这条同意下的帧：输出完全由匹配集里的帧拼成，匹配集里有谁的声音，输出就是谁的声音。混进 bob 自己的帧，bob 的每一帧最近邻都是他自己，转换等于没做。alice 的另一条同意覆盖广告和配音，这一刻也有效，它下面的录音同样不能用：输出的水印写的是这一条同意的 id，追溯和撤销都按这一条来；用了另一条同意下的录音，那条同意被撤销时，就查不出哪些输出用过它。所以不能直接拿 Part 2 的 `active()` 把她所有有效同意的帧都收进来。课里那一节的标题是 “The ethics bit, not a bolt-on”：同意决定的是转换用哪些数据，而不只是转换前的一个开关。

端到端那一段用的是玩具 WavLM 帧：音素向量加 0.5 倍的说话人向量再加噪声，思路和课里 `main.py` 的 `fake_tts` 一样，都是内容向量加说话人向量。转换后内容探针（最近的音素向量）不变，说话人探针从 bob 变成 alice。再用 `stamp` 盖上同意 id，`trace` 从音频里读出 id，查回这条同意记录，Part 1 和 Part 2 都在这里用上了。

## Part 4 实时流监测

一个 Evidence 从头累加到尾，按样本数在 1600 的整数倍处切开每一块：

```python
async for chunk in chunks:
    pos = 0
    while pos < len(chunk):
        take = step - evidence.samples % step
        evidence.add(chunk[pos : pos + take])
        pos += take
        if evidence.samples % step == 0:
            verdict = watermarker.verdict(evidence)
            if verdict.found:
                yield _watermark(verdict, evidence.samples / sample_rate)
                return
```

- 打分的时刻只由样本数决定，所以无论一次来 1 个样本还是整条流，`at` 都是 1.1 秒。
- 确认后 yield 一次就 return，生成器不再向上游要数据。测试拿到事件就关闭生成器时数一次，把生成器跑完再数一次，两次都只拉取了 44 块。
- 循环结束后再打一次分：截到 1.05 秒的流，在最后一个 0.1 秒边界（1.0 秒）还差一点，到结尾才过线。
- 没过线就以 `unmarked` 结束，秒数用整数样本数除以采样率。
- 格式由测试的解析代码决定：`event: ...\ndata: {...}\n\n`，最后的空行不能少。

Part 1 的增量 Evidence 在这里是前提：每打一次分都要重算全部音频的话，长通话会越来越慢。

## Part 5 同意策略

分两遍：先 `_check` 校验整棵策略，再 `_decide` 求值。只在求值时校验的话，一个这次走不到的分支里的笔误（比如 `regoin`）就漏过去了，这是 fail closed 的要求。`_check` 也检查叶子规则的参数：`purpose` 和 `region` 必须是字符串列表，给成字符串的话，`in` 会变成子串匹配。

`_decide(rule, request, pointer)` 返回（是否允许，负责拒绝的规则指针）：

| 规则 | 允许时 | 拒绝时由谁负责 |
|---|---|---|
| all | 每条子规则都允许（空 all 允许） | 第一条拒绝的子规则给出的指针 |
| any | 有一条子规则允许 | any 自己（空 any 也是） |
| not | 子规则拒绝 | not 自己 |
| purpose / region / from / until | 条件成立 | 这条叶子规则 |

指针按 RFC 6901 拼：根是 `""`，往下一层加 `/all/2`、`/not` 这样的片段。时间用 `fromisoformat` 解析，没有偏移就报错，比较的是时刻：UTC 4 月 21 日 19:00 已经是印度时间 22 日 0:30，过了 `until`。`until` 不含它自己那一刻，`from` 包含：UTC 4 月 30 日 18:30 正是印度时间 5 月 1 日 0:00，`from` 从这一刻起放行。请求的时间也先查偏移，否则 naive 和 aware 的 datetime 一比较就是 TypeError。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试有状态的伪随机序列、把相关检测归一化、建一张保留时区的同意表、实现 kNN-VC 并把同意检查放进转换流程、写一次性判定的流式生成器，以及递归求值并解释一棵策略树。它不涉及真实的模型（WavLM、vocoder、F5-TTS），不涉及感知域水印和抗 MP3 重编码，也不涉及深伪检测和同意在法律上是否有效。课里 Step 2 的 F5-TTS 零样本克隆，以及 Exercises 2 和 3，需要另外动手跑。
