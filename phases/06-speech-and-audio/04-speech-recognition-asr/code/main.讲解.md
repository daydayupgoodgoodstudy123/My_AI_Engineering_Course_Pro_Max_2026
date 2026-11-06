# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 04 节 语音识别 (ASR) — CTC、RNN-T、Attention ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`；另 import 了 `collections.Counter` 但未使用）

---

## 1. 这份代码在考察什么

这份脚本不训练任何声学模型，而是**手工构造"声学模型的输出"**（逐帧的 token 概率），专注于 ASR 后半段的三件事：

1. **CTC greedy 解码**：逐帧 argmax → 合并相邻重复 → 删除 blank。理解 blank 为什么能保住 `hello` 里的双 `l`。
2. **CTC beam search 的骨架**：多个候选前缀并行扩展、合并相同前缀的概率——以及这个简化版**为什么会把 `hello` 解成 `helo`**。
3. **WER**：词级 Levenshtein 编辑距离的动态规划实现，替换 / 删除 / 插入各算一次错误。
4. **对"beam 一定比 greedy 好"保持怀疑**：Step 4 显示，没有语言模型时 beam search 并不能真正修复被破坏的帧。
5. **建立数字直觉**：最后打印讲义中的 2026 年 LibriSpeech test-clean WER 表。

> 一句话：**CTC 的核心就是"折叠函数"——合并重复、删除 blank**；搞懂它，beam search、LM 融合、CTC loss 都只是在它上面加概率。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BLANK`、`VOCAB` | 全局常量 | 下标 0 是 blank，1–26 是字母，27 是空格 | CTC 词表 `V+1` |
| `ctc_greedy` | 函数 | 逐帧 argmax + 折叠 | CTC greedy 解码 |
| `ctc_beam` | 函数 | 简化版 beam search，合并相同前缀 | CTC beam search（有缺陷） |
| `wer` | 函数 | 词级编辑距离 / 参考词数 | WER = (S+D+I)/N |
| `one_hot_like` | 函数 | 构造"接近 one-hot"的概率向量 | 模拟声学模型输出 |
| `build_frame_probs` | 函数 | 每个字符重复若干帧 + blank | 模拟一条对齐路径 |
| `corrupt` | 函数 | 随机把某些帧的概率"挪"给别的 token | 模拟识别错误 |
| `main()` | 演示入口 | 6 个步骤 | — |

数据流：`build_frame_probs("hello world")` → `ctc_greedy` / `ctc_beam` 得到文本；`corrupt` → 再次解码；`wer` 独立演示。

---

## 3. 逐段精讲

### 3.1 词表与 blank

```python
BLANK = 0
VOCAB = "_abcdefghijklmnopqrstuvwxyz "  # index 0 is blank
```

- 共 28 个 token：blank + 26 个字母 + 空格。空格作为普通字符，使"词"的边界也由模型输出——这是字符级 CTC 的常见做法（wav2vec 2.0 的英文字符词表就用一个特殊符号表示词边界）。
- 用字符串当词表，`VOCAB[i]` 取字符、`VOCAB.index(c)` 取下标，简单直观。
- 讲义："encoder output `T` frame-level distributions over `V+1` tokens (V chars + blank)"。

### 3.2 Greedy 解码：折叠函数

```python
def ctc_greedy(frame_probs):
    preds = [max(range(len(p)), key=lambda i: p[i]) for p in frame_probs]
    out = []
    prev = -1
    for p in preds:
        if p != prev and p != BLANK:
            out.append(p)
        prev = p
    return "".join(VOCAB[i] for i in out)
```

- 第一行：对每帧求 argmax（纯 Python 写法）。
- 循环同时实现两条规则：`p != prev` → 合并相邻重复；`p != BLANK` → 删 blank。
- **`prev = p` 在 `if` 外面**是关键：blank 帧也会更新 `prev`，所以 `l l l _ l l l` 中第二段 `l` 的前一帧是 blank，不等于 `l`，会被输出——双字母得以保留。如果把这行挪进 `if`，blank 就失去了分隔作用。
- `prev = -1` 是哨兵值：不对应任何 token，保证第一帧不会被误判为重复。
- 讲义的版本带 `vocab=None` 参数，返回下标或字符串；代码直接用全局 `VOCAB`。
- 复杂度 `O(T·V)`，一次前向即可——这就是 CTC "非自回归、快"的体现。

### 3.3 简化版 beam search

```python
def ctc_beam(frame_probs, beam_width=8):
    beams = [((), 0.0)]
    for p in frame_probs:
        log_p = [math.log(max(pi, 1e-10)) for pi in p]
        new_beams = {}
        for seq, lp in beams:
            for t, lpt in enumerate(log_p):
                if t == BLANK:
                    new_seq = seq
                else:
                    if seq and seq[-1] == t:
                        new_seq = seq
                    else:
                        new_seq = seq + (t,)
                if new_seq in new_beams:
                    new_beams[new_seq] = math.log(math.exp(new_beams[new_seq]) + math.exp(lp + lpt))
                else:
                    new_beams[new_seq] = lp + lpt
        beams = sorted(new_beams.items(), key=lambda x: -x[1])[:beam_width]
    best = beams[0][0]
    return "".join(VOCAB[i] for i in best)
```

做了什么：

- 每个 beam 是 `(前缀元组, 累积对数概率)`。用**元组**而不是列表，是因为元组可哈希，能当字典的键。
- 对每个 beam、每个 token 生成候选：blank → 前缀不变；与前缀末尾相同 → 前缀不变（视为重复）；否则 → 追加。
- **合并相同前缀**：不同路径可能得到同一个前缀，它们的概率要**相加**（在对数域是 log-sum-exp）。这是比讲义 Step 2 进步的地方：讲义版本直接把重复前缀都塞进候选列表，beam 里会出现大量重复项。
- `max(pi, 1e-10)` 防止 `log(0)`，也防止 `corrupt` 产生的负概率导致 `math.log` 报错。
- 每帧只保留得分最高的 `beam_width` 个前缀。

刻意的简化与缺陷：

- ⚠️ **丢失双字母**：前缀只记录"内容"，不记录"最后一帧是不是 blank"。所以 `hel` 之后再来 `l`，即使中间隔了 blank 也会被当成重复。这就是 Step 3 输出 `helo world` 的原因。代码自己打印了说明：正确的前缀 beam search 要分别跟踪 `P_blank` 和 `P_nonblank`（测验 Q10 给出了完整实现）。
- ⚠️ **数值下溢**：`math.log(math.exp(a) + math.exp(b))` 在 `a、b < −745` 时 `exp` 下溢为 0，`log(0)` 抛 `ValueError`。44 帧时不会触发，但长音频（上千帧）很可能触发。应改用 log-sum-exp：`m + log(exp(a−m) + exp(b−m))`。
- ⚠️ 没有语言模型：真实系统在扩展前缀时加上 `λ·log P_LM(词)` 和长度奖励（shallow fusion），这才是 beam search 相对 greedy 的主要收益来源。
- 复杂度：每帧 `O(beam × V)` 个候选再排序；`V` 很大（子词词表上千）时生产实现会先剪枝只考虑每帧概率最高的若干 token。

### 3.4 WER：词级编辑距离

```python
def wer(ref, hyp):
    r = ref.split()
    h = hyp.split()
    nr = len(r)
    if nr == 0:
        return 0.0 if not h else 1.0
    dp = [[0] * (len(h) + 1) for _ in range(nr + 1)]
    for i in range(nr + 1):
        dp[i][0] = i
    for j in range(len(h) + 1):
        dp[0][j] = j
    for i in range(1, nr + 1):
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[nr][len(h)] / nr
```

- `dp[i][j]` = 参考前 `i` 个词变成假设前 `j` 个词的最少编辑次数。
- 边界：`dp[i][0] = i`（全部删除）、`dp[0][j] = j`（全部插入）。
- 状态转移三选一：`dp[i-1][j] + 1` 删除、`dp[i][j-1] + 1` 插入、`dp[i-1][j-1] + cost` 匹配或替换。
- 除以参考词数 `nr`——所以插入很多时 **WER 可以大于 1**（例如 `wer("a b", "a b c d e") = 1.5`）。
- 空参考的特殊处理：`nr == 0` 时假设为空返回 0，否则返回 1，避免除零。
- ⚠️ 没有文本归一化：`Hello,` 和 `hello` 会被算作不同的词。讲义和技能文件都强调"先归一化（小写、去标点）再算 WER"。
- ⚠️ 只返回总错误率，不返回 S/D/I 各自的数量；实际分析时常需要回溯 DP 表得到具体对齐（`jiwer` 等库会提供）。
- 时间、空间都是 `O(N·M)`；只需要距离时可以用两行滚动数组把空间降到 `O(M)`。

### 3.5 构造模拟的声学模型输出

```python
def one_hot_like(char, noise=0.02, vocab_size=len(VOCAB)):
    base = [noise] * vocab_size
    idx = VOCAB.index(char)
    base[idx] = 1.0 - noise * (vocab_size - 1)
    return base


def build_frame_probs(target, duration_per_char=3, blank_runs=1):
    random.seed(0)
    frames = []
    for c in target:
        for _ in range(duration_per_char):
            frames.append(one_hot_like(c))
        for _ in range(blank_runs):
            frames.append(one_hot_like("_"))
    return frames
```

- `one_hot_like`：目标 token 得到 `1 − 0.02 × 27 = 0.46`，其余 27 个各 0.02，总和为 1，是合法的概率分布。注意目标概率只有 0.46——并不"自信"，但仍是 argmax。
- `build_frame_probs`：每个字符 3 帧 + 1 个 blank 帧，"hello world" 11 个字符 → 44 帧。这模拟了一条**理想对齐路径**：每个字符持续几帧，字符之间有 blank。
- `vocab_size=len(VOCAB)` 作为默认参数，在函数**定义时**求值一次（值为 28）。
- ⚠️ `random.seed(0)` 在这里没有任何作用（函数里没有用随机数），可能是早期版本的残留。
- 真实声学模型的输出远没有这么规整：blank 往往占据绝大多数帧（"尖峰"现象），字符只在一两帧上出现高概率。

### 3.6 `corrupt`：模拟识别错误

```python
def corrupt(probs, n_swaps=3, swap_strength=0.4):
    random.seed(1)
    out = [list(p) for p in probs]
    for _ in range(n_swaps):
        i = random.randrange(len(out))
        j1 = random.randrange(len(out[i]))
        j2 = random.randrange(len(out[i]))
        swap = swap_strength
        out[i][j1] -= swap
        out[i][j2] += swap
    return out
```

- `[list(p) for p in probs]` 逐帧复制，避免修改原始 `probs`（浅拷贝外层 + 复制每个内层列表）。
- 每次随机挑一帧、两个 token，从 `j1` 挪走 0.6 给 `j2`。由于原本最大值只有 0.46，`j2` 被加到 0.62 后一定成为新的 argmax——一次 swap 基本就会改变一帧的 argmax。
- ⚠️ 减去 0.6 后概率可能变成负数（实测最小值 −0.58），不再是合法分布。`ctc_beam` 里的 `max(pi, 1e-10)` 恰好掩盖了这个问题。
- ⚠️ 函数内部调用 `random.seed(1)` 会**重置全局随机状态**，影响调用方后续的随机数。更好的写法是 `rng = random.Random(1)` 用独立的随机数生成器。

### 3.7 `main()` 的 Step 4 与 Step 6

```python
    corrupted = corrupt(probs, n_swaps=6, swap_strength=0.6)
    g2 = ctc_greedy(corrupted)
    b2 = ctc_beam(corrupted, beam_width=16)
```

- 标题写着 "beam should beat greedy"，但实际输出（见第 6 节）两者几乎相同，只差一个 `l`——而且 beam 少的这个 `l` 恰恰来自它"合并双字母"的缺陷，而不是真正的纠错。
- 原因：CTC 的条件独立假设下，每帧的概率互不影响；没有 LM 提供"哪个词序列更合理"的信息，beam search 能利用的只有"多条对齐路径的概率之和"，在这种逐帧被硬改的输入上几乎没有帮助。测验 Q10 中正确实现的前缀 beam search 在这里的输出与 greedy **完全相同**。
- Step 6 只是把讲义的 WER 表打印出来，其中 `wav2vec 2.0 Large 1.92%` 一行讲义正文只给了"1.8–2.1%"的区间。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手工构造逐帧概率，不训练模型 | 聚焦解码与评估，零依赖、秒级运行 | 真实输出是"尖峰"状，blank 占多数；生产用 wav2vec 2.0 / Parakeet 等真实模型 |
| 字符级词表 + 空格 | 最直观 | 真实系统常用子词（BPE/SentencePiece），词表上千 |
| 前缀不区分 blank / 非 blank 结尾 | 代码短 | 丢失双字母；生产用前缀 beam search（`pyctcdecode`、`torchaudio` 的 CTC decoder 等） |
| `log(exp+exp)` 合并概率 | 直观 | 长序列下溢崩溃；必须用 log-sum-exp |
| 没有 LM 融合 | 保持骨架清晰 | beam 收益有限；生产用 KenLM / 神经 LM shallow fusion |
| WER 不做归一化、不输出 S/D/I | 教学聚焦 DP | 生产用 `jiwer` 等库 + Whisper 风格文本归一化 |
| 函数内 `random.seed` | 保证每次结果相同 | 污染全局随机状态；应使用独立的 `random.Random` 实例 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `BLANK = 0`、`VOCAB = "_abc..."` | 全大写命名表示"不应被修改" |
| 字符串索引与查找 | `VOCAB[i]`、`VOCAB.index(char)` | 字符串可以像列表一样按下标取字符；`.index` 返回首次出现的位置 |
| 默认参数在定义时求值 | `def one_hot_like(char, noise=0.02, vocab_size=len(VOCAB))` | `len(VOCAB)` 只在定义函数时算一次 |
| 列表乘法 | `[noise] * vocab_size`、`[0] * (len(h) + 1)` | 生成重复元素的列表（元素是不可变的数字，安全） |
| 元组与元组拼接 | `beams = [((), 0.0)]`、`seq + (t,)` | `()` 空元组；`(t,)` 单元素元组必须带逗号；元组可哈希，能做字典键 |
| 字典的 `in` 判断与更新 | `if new_seq in new_beams: ...` | 合并相同前缀的概率 |
| `sorted(dict.items(), key=...)` | `sorted(new_beams.items(), key=lambda x: -x[1])[:beam_width]` | 按值降序排列键值对，取前 k |
| `max(..., key=...)` | `max(range(len(p)), key=lambda i: p[i])` | argmax |
| `str.join` + 生成器 | `"".join(VOCAB[i] for i in out)` | 把字符序列拼成字符串 |
| `str.split()` | `ref.split()` | 无参数时按任意空白切分，自动忽略多余空格 |
| 二维 DP 表 | `[[0] * (len(h) + 1) for _ in range(nr + 1)]` | 用推导式建二维表，避免行共享 |
| 条件表达式 | `0 if r[i - 1] == h[j - 1] else 1` | 一行 if-else |
| `random.randrange` | `random.randrange(len(out))` | 返回 `[0, n)` 内的随机整数 |
| f-string 的 `!r` 与对齐 | `f"{target!r}"`、`f"{label:<14}"`、`f"{w:.2f}"` | `!r` 用 `repr()` 显示（带引号）；`:<14` 左对齐宽 14 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.03 秒）：

```text
=== Step 1: build per-frame CTC outputs for target ===
  target: 'hello world'
  frames: 44  vocab: 28  (index 0 = blank)

=== Step 2: greedy decode (collapse repeats, drop blank) ===
  greedy decode: 'hello world'

=== Step 3: beam search decode (width 8, simplified) ===
  beam decode:   'helo world'
  note: this beam merges consecutive repeats without a blank-intervene state;
  a proper prefix-tree beam (e.g. ctcdecode) tracks P_blank / P_nonblank and
  preserves double letters like the two l's in 'hello'.

=== Step 4: corrupt logits; beam should beat greedy ===
  greedy: 'hlhce llolo wolnrld'
  beam:   'hlhce lolo wolnrld'

=== Step 5: WER ===
  perfect        WER = 0.000  hyp='hello world this is a test'
  one substit    WER = 0.167  hyp='hello world this is the test'
  one deletion   WER = 0.167  hyp='hello world this a test'
  one insert     WER = 0.167  hyp='hello world this is a big test'
  garbage        WER = 1.000  hyp='bye everyone nothing here'

=== Step 6: best model on LibriSpeech test-clean (2026) ===
  | Model                 | WER  | Params |
  | Parakeet-TDT-1.1B     | 1.40 | 1.1B   |
  | Canary-1B Flash       | 1.48 | 1B     |
  | Whisper-L-v3-turbo    | 1.58 | 809M   |
  | Seamless M4T v2       | 1.70 | 2.3B   |
  | wav2vec 2.0 Large     | 1.92 | 317M   |
```

逐段解读：

- **Step 1**：11 个字符 × (3 + 1) = 44 帧，词表 28。
- **Step 2**：greedy 完美还原，包括双 `l`——因为构造时两个 `l` 之间有 blank 帧。
- **Step 3**：beam 输出 `helo world`，丢了一个 `l`，原因见 3.3。这是一个"简化实现在边界情况上出错"的经典教学示例。
- **Step 4**：6 次 swap 让输出面目全非。每次 swap 往往插入一个错误字符，若落在一个字符的 3 帧中间，还会把这段拆成两半（如 `h h h` → `h l h`，解码成 `hlh`）。beam 与 greedy 只差一个 `l`；按字符编辑距离算，beam 的 CER 0.6 比 greedy 的 0.7 略低，但这只是"合并双字母"的缺陷碰巧删掉了一个插入错误，并非真正的纠错。**标题"beam should beat greedy"在这里并没有被证明**。
- **Step 5**：参考 6 个词，1 次替换 / 删除 / 插入都是 `1/6 = 0.167`；`garbage` 有 4 个词，最优编辑是 4 次替换 + 2 次删除 = 6 次，`6/6 = 1.0`。
- **Step 6**：打印讲义中的数字。讲义的观点是：各模型 WER 差距很小，部署特性（流式、延迟、体积）差异才是选型关键。

---

## 7. 动手改一改

1. 把 `build_frame_probs` 的 `blank_runs` 设为 0（字符之间不再有 blank），观察 greedy 也变成 `helo world`（已实测），理解 blank 的分隔作用。
2. 用 log-sum-exp 替换 `ctc_beam` 中的 `math.log(math.exp(...) + math.exp(...))`。验证方法：`build_frame_probs("hello world" * 30, 3, 1)` 得到 1320 帧，原版 `ctc_beam` 实测抛出 `ValueError: math domain error`，新版应正常输出。
3. 实现讲义练习 2：带 `P_blank / P_nonblank` 的前缀 beam search，确认 Step 3 输出 `hello world`（参考测验 Q10）。
4. 给前缀 beam search 加一个玩具"语言模型"：例如一个词表 `{"hello", "world"}`，每当前缀以空格结束时，若最后一个词在词表里就加 `+2.0` 的对数奖励，否则 `−2.0`。看在 Step 4 的被破坏输入上，beam 能否开始真正优于 greedy。
5. 修改 `wer`：①先做归一化（小写、去标点）；②回溯 DP 表，分别返回 S、D、I 的数量。
6. 把 `corrupt` 改为使用 `rng = random.Random(1)`，并保证修改后每帧概率仍非负且和为 1（例如把 `swap` 限制为 `min(swap_strength, out[i][j1])`）。

---

## 8. 常见坑

- **blank 的作用理解不全**：blank 不仅表示"静音"，还负责分隔重复字符；解码时 `prev` 必须随 blank 一起更新。
- **折叠顺序搞反**：必须先合并重复、再删 blank；反过来 `a _ a` 会变成 `a`。
- **对数概率直接 exp 再相加**：长序列必然下溢；凡是"概率相加"都要在对数域用 log-sum-exp。
- **以为 beam search 总比 greedy 好**：没有 LM 时，CTC beam search 的收益很有限；技能文件也提醒"没有 LM 的 beam 宽度 > 16 毫无意义"。
- **WER 不归一化**：大小写、标点、数字写法不统一会让 WER 虚高，不同模型之间不可比。
- **以为 WER ≤ 1**：插入错误没有上限，幻觉严重的系统 WER 可以超过 100%。
- **函数内部重置全局随机种子**：会让调用方的随机行为变得难以预测。
