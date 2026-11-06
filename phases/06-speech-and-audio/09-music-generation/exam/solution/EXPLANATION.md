# 参考答案讲解：MusicBox（06/09）

计时结束后再看。参考实现在同目录的 `musicbox/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修作曲和渲染

**现象**：解锁后的第一个错误是 `note_number` 里的 `KeyError: 'G#di'`，而 `note_number` 本身没有 bug。

**顺着往上找**：`note_number` 收到的音名是 "G#di"。它来自 `chord_tones("G#dim")`：代码先判断 `endswith("m")`，"dim" 恰好也以 m 结尾，于是 "G#dim" 被拆成根音 "G#di" 加小三和弦。巴洛克进行 I–IV–vii°–iii–vi–ii–V–I 的第 3 小节是 vii°，在 A 大调里就是 G#dim。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `chord_tones`：先判断 "dim"，再判断 "m"。
2. `parse_bpm`：这是课里 `fake_generate` 的原样写法。`split()` 把 "128 bpm" 切成 "128" 和 "bpm"，只有 "bpm" 以 bpm 结尾，`int("")` 抛出的 ValueError 被 `except ValueError: pass` 吞掉，速度静默回到 120。现象出现在两层之外的时长上：8 小节算出 16 s。改成正则 `(\d+)\s*bpm\b`。课里的 Pitfalls 说模型会偏离要求的 BPM，这份代码连提示词里的 BPM 都没传下去。
3. `seconds`：`tick // PPQ` 是整除，一拍以内的位置被截掉，一个十六分音符算成 0 秒。改成 `tick * 60 / (PPQ * bpm)`。
4. `render`：`_held_until` 为每个和弦音从头扫描整个音符列表，是 O(n²)，2000 小节大约 2 秒。要保持的音只可能来自上一小节，所以用一个 dict 记住上一小节每个和弦音在列表里的位置，每小节结束时换成这一小节的。

**护栏**：

- 速度要的是写在 bpm 前面的数。“取提示词里的第一个数”会把 "8 bars of lofi at 90 bpm" 读成 8，“取最后一个数”会把 "jazz at 140BPM for 32 bars" 读成 32。
- 提速不能改掉连音。rock 进行在 D 大调里是 D–G–A–D，第 4、5 小节都是 D，根音 D4（62）要从第 4 小节一直保持到第 5 小节末。只在最后三个音符里找会找不到，因为每小节的鼓点音符排在和弦音后面。
- 要保持的音不一定是上一小节才开始的。A4（69）同时在 A 和弦和 D 和弦里，从第 3 小节一直保持到第 5 小节末，所以“只在上一小节开始的音符里找”和“只有整个和弦重复时才保持”都不对。16 小节都是 D 和弦时，三个音从头保持到尾，“只看最近 N 个音符”的写法 N 取多大都会在这里断开。参考实现记的是上一小节每个和弦音在列表里的位置，不管这个音已经保持了多少小节。

## Part 2 曲库

参考实现只有一张表：`seq` 自增主键负责加入顺序，`track_id` 是 UUID 字符串，速度表、音符和 meta 各存一段 JSON。

存什么：音符存 tick（整数），时间轴由 tick 和速度表共同决定，秒数在用的时候再算。存浮点秒的话，改一次速度所有音符都要重算，小节线上的音还可能因为舍入落到线的另一边。

容易漏的几点：

- **commit**：sqlite3 在执行 INSERT 时会自动开启事务，`with self._db:` 负责提交。不提交的话，`close()` 之后数据就没了。
- **类型原样还原**：JSON 没有 tuple，速度表读回来要转回 tuple；音符要还原成 `Note`。
- **顺序**：音符按加入的顺序读回。测试里同一时刻的和弦音不是按音高排的，最后还有一个 tick 0 的鼓点，`ORDER BY start` 会改变顺序。`ids()` 也要 `ORDER BY seq`：track_id 上有 UNIQUE 约束，不写 ORDER BY 的查询会走这个索引，按 UUID 的字典序返回。
- **这个领域的精度陷阱**：140 bpm 换成 MIDI 文件里的整数“每拍微秒数”是 428571，读回来是 140.00014；400/3 bpm 要原样回来；64 位的生成种子放不进 SQLite 的 INTEGER（OverflowError），放进 REAL 又会丢精度。全部放在 JSON 里，Python 的 int 和 float 都能原样还原。
- **披露**：课里说 EU AI Act 和 California SB 942 要求披露 AI 生成的音乐，安全上线的做法之一是给生成结果打上元数据。`add` 拒收 meta 里没有 `ai_generated: True` 的曲子。
- **`Track.seconds`**：逐段累加。每一段从它的 tick 开始，到下一次变速或目标 tick 为止，用这一段的速度换算。一拍是这首曲子自己的 `ppq` 个 tick，不是 compose 里的 `PPQ`：

```python
for (at, bpm), end in zip(self.tempo, ends):
    if tick <= at:
        break
    total += (min(tick, end) - at) * 60 / (bpm * self.ppq)
```

## Part 3 FAD 评测

FAD = ‖μ_r − μ_g‖² + tr(Σ_r) + tr(Σ_g) − 2 tr√(Σ_r Σ_g)。二维时不需要矩阵库：M = Σ_r Σ_g 是两个半正定矩阵的乘积，和 Σ_r^½ Σ_g Σ_r^½ 相似，两个特征值 λ₁、λ₂ 都是非负实数，所以

tr√M = √λ₁ + √λ₂ = √(λ₁ + λ₂ + 2√(λ₁λ₂)) = √(tr M + 2√det M)。

容易错的地方：

- 均值项是平方距离。分布相同、均值在两个方向上各差 1.5 时，FAD 正好是 1.5² + 1.5² = 4.5。
- 协方差除以 n − 1。把参考集整体放大两倍时，FAD = ‖μ_r‖² + tr Σ_r，除以 n 会得到另一个数。
- 迹要对矩阵平方根取。逐元素开方，或者把 tr√M 当成 √(tr M)，“只平移均值”那条断言就不再是 4.5。
- 浮点误差：输出塌缩到一条直线上的模型，det M 应该是 0，参考实现的算法得到的是 −2e-22，要截到 0 再开方；和参考集完全相同的集合，结果是 −5.6e-17，距离也要截到 0。
- 两个集合都至少要有两个点，否则样本协方差的分母 n − 1 是 0。参考集和生成集都要检查。
- 测试里“平移”和“放大两倍”两组的协方差和参考集成比例，只用对角线、或者把 tr√(Σ_r Σ_g) 写成 tr(√Σ_r √Σ_g)，在那里都碰巧算对。塌缩的那一组和参考集的协方差方向不同，才能看出公式对不对。
- 排名：FAD 越低越好。

最后一段把 Part 1 串进来：每首曲子用一个二维的玩具 embedding（和弦音的平均音高、每秒鼓点数）代替 VGGish。lofi 生成和 lofi 参考集的 FAD 约 0.008，rock 生成约 9.3。课里说 FAD 适合做风格层面的回归测试，不能代替人工听评，这里量到的正是“风格像不像”。

## Part 4 流式输出小节

状态只有三样：当前小节号、当前小节的音符列表、还在响的音（音高和剩余步数，按开始的先后排列）。

```python
async for token in tokens:
    if token == "bar":
        if bar >= 0:
            yield event(bar, notes)        # 下一小节一开始，就发出上一小节
        bar += 1
        notes, ringing = carry(ringing)    # 还在响的音变成这一小节开头的 tied 音
    ...
yield event(bar, notes)
while ringing:                             # token 结束后，把还在响的音发完
    bar += 1
    notes, ringing = carry(ringing)
    yield event(bar, notes)
```

- 音符越过小节线时，这一小节只放到线为止，剩下的步数进入 `ringing`。
- `carry` 把每个还在响的音变成下一小节第 0 步的 tied 音，最长一整个小节，还剩下的继续留在 `ringing`。
- 两处判断都是严格大于：音符的步数大于这一小节剩下的步数，才有剩余；剩余的步数大于一整个小节，才继续往后带。正好在小节线上结束的音不会在下一小节留下一个 0 步的 tied 音。
- 每个 "bar" 都把位置清零。测试里第二小节的 62 前面没有 pos，它应该落在第 0 步。
- 空小节照样发出。
- 格式由测试的 `sse_events` 决定：每个事件一行 `data: <json>`，后面跟一个空行，也就是 `"\n\n"`。
- 下一个 "bar" 一到就 `yield`，所以第一个事件出来时只拉取了 4 个 token。

## Part 5 歌曲结构

两个互相递归的函数：`play(items, at, path)` 依次处理段落名和 repeat 组，返回结束时的 tick；`section(name, at, path)` 展开一个段落，返回它结束的 tick。

- 每个函数都返回“下一段从哪里开始”，偏移量自然地沿着嵌套重复累加。
- 小节长度 = beats × ppq × 4 / unit：4/4 是 1920，3/4 和 6/8 都是 1440。
- 有 endings 时，第 n 遍在主体之后接 `endings[n]`，下一遍从这个结尾之后开始。
- `path` 是从根到当前段落经过的名字。名字已经在 path 里才是循环，报 ValueError；同一个段落在别处再次出现是正常的复用。捕获 RecursionError 再改报 ValueError 也能过测试，但那是撞到递归上限之后才发现，不是检查。
- 音符的起点必须落在 [0, 小节长度) 里。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试、给生成结果建模并持久化、实现 FAD、写边生成边发送的流式生成器，以及展开带重复和结尾的嵌套结构。它不涉及 MusicGen、Stable Audio 这类模型本身，也不涉及真实音频、VGGish embedding 和 CLAP 打分。课里 Step 1、2 的生成和 Step 3 用真实音频算 FAD，需要另外动手跑。
