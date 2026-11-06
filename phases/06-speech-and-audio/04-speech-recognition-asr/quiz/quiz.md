# 测验 · 语音识别 (ASR) — CTC、RNN-T、Attention（Speech Recognition (ASR) — CTC, RNN-T, Attention）

> **阶段 06 · 语音与音频 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | ASR 的结构性难题 | 音频帧与字符不是一一对应：同一个词可能 200 ms 也可能 1200 ms，输出长度事先未知 |
| 2 | CTC | 每帧输出 `V+1` 个 token 的概率（多一个 blank），解码时合并相邻重复、删除 blank；训练时对所有能折叠成目标的对齐求和 |
| 3 | CTC 的条件独立假设 | 每帧预测互相独立，模型内部没有语言模型；需要外部 LM 通过 beam search / shallow fusion 补上 |
| 4 | RNN-T | 在 CTC 基础上加 predictor（编码已输出 token 历史）和 joiner（合并 predictor 与 encoder 帧），输出 `V+1`（+1 为 null/不输出）；可流式且自带 LM，训练更费内存（3D loss lattice） |
| 5 | Attention encoder-decoder | Encoder 处理 log-mel，decoder 自回归地 cross-attend 生成 token；离线质量最好，但延迟与输出长度成正比，需额外工程才能流式 |
| 6 | Greedy vs beam 解码 | Greedy：逐帧 argmax → 合并重复 → 删 blank；beam：保留多个候选前缀，正确实现要分别跟踪"以 blank 结尾 / 以非 blank 结尾"的概率 |
| 7 | WER | `(S + D + I) / N`，即词级 Levenshtein 距离除以参考词数；必须先做文本归一化（小写、去标点）；>20% 基本不可用 |
| 8 | 2026 选型 | 英文离线最高质量：Whisper-large-v3-turbo；流式低延迟：Parakeet-TDT；端侧：Whisper-Tiny 量化 / Moonshine；长音频：VAD 切分（WhisperX）；垂直领域：微调 wav2vec 2.0 + 领域 LM |
| 9 | 上线常见坑 | 不加 VAD 导致静音幻觉（"Thanks for watching!"）；未归一化就算 WER；自动语种识别漂移；超过 30 秒不切块 |

### 核心技能（能动手做到）

- [ ] 手工对一串逐帧 argmax 结果做 CTC greedy 解码，并解释为什么双字母之间必须有 blank
- [ ] 读懂简化版 CTC beam search，指出它为什么把 `hello` 解成 `helo`，并实现跟踪 `P_blank / P_nonblank` 的前缀 beam search
- [ ] 用动态规划从零实现 WER，能手算 S/D/I，并解释 WER 为什么可以超过 100%
- [ ] 发现并修复对数概率相加时 `log(exp(a) + exp(b))` 的下溢问题（改用 log-sum-exp）
- [ ] 对比 CTC / RNN-T / Attention 三种范式在对齐、流式、内部 LM、延迟、训练成本上的差异
- [ ] 为给定部署场景（流式助手、长会议、医疗领域、端侧）选出模型、解码策略、切块与 VAD 方案

---

## 二、基础自测（选择题）

**Q1.** CTC greedy 解码时，逐帧 argmax 的结果为 `a a _ _ a b b _ c`（`_` 为 blank），输出是：

- A. `abc`
- B. `aabc`
- C. `aabbc`
- D. `aaabbc`

**Q2.** CTC 通常需要外接语言模型才能达到最佳效果，根本原因是：

- A. CTC 不能处理变长输出
- B. CTC 假设各帧的预测在给定输入时条件独立，模型内部没有建模 token 之间的依赖
- C. CTC 只能输出字符，不能输出子词
- D. CTC 是自回归的，速度太慢

**Q3.** 既能天然流式、又在模型内部建模了 token 历史（自带"内部 LM"）的范式是：

- A. CTC
- B. RNN-T
- C. 标准 attention encoder-decoder（全局 attention）
- D. k-NN on MFCC

**Q4.** 参考文本 `hello world this is a test`，识别结果 `hello world this is the test`，WER 是：

- A. 0.0
- B. 约 0.167
- C. 约 0.333
- D. 1.0

**Q5.** 关于 attention encoder-decoder（如 Whisper），下列说法正确的是：

- A. 它必须严格单调地从左到右对齐音频
- B. 推理延迟与输出 token 数成正比，不做额外工程就无法流式
- C. 它不需要 encoder，decoder 直接读波形
- D. 它和 CTC 一样是非自回归的

**Q6.** RNN-T 的输出分布是 `V+1` 维，其中多出来的 1 表示：

- A. 句子结束符 EOS
- B. null / 不输出：当前编码帧不再输出 token，前进到下一帧
- C. 未知词 UNK
- D. 填充符 PAD

**Q7.** 把 Whisper 直接用于一段包含长时间静音的录音，最常见的问题和对策是：

- A. 输出全为空字符串；对策是调大 beam
- B. 在静音段产生幻觉文本（如 "Thanks for watching!"）；对策是先用 VAD 过滤非语音
- C. 识别速度变慢；对策是降低采样率
- D. 自动切换为 CTC 解码；对策是强制 attention 解码

**Q8.** 关于 WER，下列说法**错误**的是：

- A. WER = `(S + D + I) / N`，N 是参考文本的词数
- B. 报告 WER 前应做文本归一化（统一小写、去标点）
- C. WER 一定在 `[0, 1]` 区间内
- D. WER 等于词级 Levenshtein 编辑距离除以参考词数

---

## 三、动手 / 代码题

**Q9.** 阅读 `ctc_greedy`：

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

(a) 若逐帧 argmax 依次为 `h h h _ e e e _ l l l _ l l l _ o o o _`（即 `build_frame_probs("hello", 3, 1)` 的结构），输出是什么？如果去掉两段 `l l l` 之间的那个 `_`，输出又是什么？
(b) `prev = p` 写在 `if` 外面而不是里面，有什么区别？如果把它挪进 `if` 里面（只在输出时更新 `prev`），`a _ a` 和 `a a` 会分别解码成什么？
(c) `prev` 的初始值为什么是 `-1`？

**Q10.** 运行 `main.py`，greedy 输出 `'hello world'`，而 beam 输出 `'helo world'`。阅读 `ctc_beam` 的核心片段：

```python
            for t, lpt in enumerate(log_p):
                if t == BLANK:
                    new_seq = seq
                else:
                    if seq and seq[-1] == t:
                        new_seq = seq
                    else:
                        new_seq = seq + (t,)
```

(a) 解释它为什么丢了一个 `l`。
(b) 实现一个正确的 CTC 前缀 beam search：每个前缀分别维护 `log P_blank`（以 blank 结尾）和 `log P_nonblank`（以非 blank 结尾），并验证在同样的 `probs` 上输出 `'hello world'`。

**Q11.** 用代码里的 `wer` 计算：

```python
print(wer("the cat sat", "cat sat on the mat"))
print(wer("a b", "a b c d e"))
```

预测输出，并说明 WER 为什么可以大于 1。再说明 `wer("", "hello")` 返回什么，这个设计是否合理。

**Q12.** `ctc_beam` 合并相同前缀时用的是：

```python
new_beams[new_seq] = math.log(math.exp(new_beams[new_seq]) + math.exp(lp + lpt))
```

本例只有 44 帧，运行正常。但对一段 30 秒（约 1500 帧）的音频，这行代码可能直接崩溃。说明原因、复现方法，并写出数值稳定的替代函数。

---

## 四、面试高频题

**Q13.**（基础必考）对比 CTC、RNN-T、Attention encoder-decoder 三种 ASR 范式：它们分别怎么解决"音频帧与文字不对齐"的问题？在流式能力、内部语言模型、推理延迟、训练成本上各有什么取舍？

**Q14.**（原理深挖）详细解释 CTC loss：blank 的作用、"折叠函数"是什么、为什么要对所有对齐求和、如何高效计算？CTC 对输入长度 `T` 和标签长度 `U` 有什么约束？

**Q15.**（工程实践）你要给老板汇报新 ASR 模型的效果。WER 应该怎么算才可信？中文、日文这类语言用什么指标？哪些情况下 WER 会"失真"？

**Q16.**（场景设计）分别为以下三个场景选型并说明解码、切块、VAD、语言策略：(a) 车载语音助手（流式、低延迟、端侧算力有限）；(b) 2 小时会议录音离线转写；(c) 医院病历口述（大量医学术语）。

**Q17.**（追问型）Whisper 在静音或噪声片段上为什么会"幻觉"出文字？除了 VAD，还有哪些缓解手段？

---

## 五、参考答案与解析

### Q1 — 答案：B

两条规则：先合并相邻重复（`a a → a`、`_ _ → _`、`b b → b`），得到 `a _ a b _ c`；再删掉 blank，得 `a a b c`，即 `aabc`。讲义原文就用这个例子。关键在于第一个 `a` 和第三个 `a` 之间隔了 blank，所以不会被合并。A 是"先删 blank 再合并"的错误顺序。

### Q2 — 答案：B

讲义："conditional independence assumption — each frame prediction is independent of the others, so there is no internal language model"。给定 encoder 输出，CTC 把每帧的分布当作独立的，无法利用"上一个词是什么"。所以常在 beam search 中加入外部 LM 的加权对数概率（shallow fusion）。A 错：CTC 正是为变长输出设计的；C 错：CTC 的词表可以是子词；D 错：CTC 是非自回归的。

### Q3 — 答案：B

RNN-T 的 predictor 编码已输出的 token 历史，显式建模了 CTC 忽略的条件依赖；每一步只依赖过去的帧和过去的 token，所以可流式。A 可流式但没有内部 LM；C 有内部 LM（decoder 本身就是条件语言模型）但全局 attention 需要整段音频，不能天然流式。

### Q4 — 答案：B

`is → the` 是 1 次替换，参考共 6 个词，`1/6 ≈ 0.167`。代码 Step 5 的 `one substit` 输出 `WER = 0.167`。同样，1 次删除或 1 次插入也都是 `0.167`。

### Q5 — 答案：B

讲义："autoregressive latency is proportional to output length; cannot stream without engineering"，流式需要限制 attention（如分块的 Whisper-Streaming）。A 错：attention "can look anywhere in the audio"，没有单调对齐约束——这既是优点，也是幻觉和重复的来源；C、D 显然错误。

### Q6 — 答案：B

讲义："the `+1` is a null / no-emit"。RNN-T 在 `(编码帧 t, 已输出 token 数 u)` 的格点上移动：输出一个真实 token 则 `u+1`，输出 null 则 `t+1`。这与 CTC 的 blank 类似但语义不同：CTC 的 blank 每帧必须输出一个符号，RNN-T 的 null 表示"这一帧说完了，进入下一帧"，一帧可以输出多个 token。

### Q7 — 答案：B

讲义 Pitfalls："Running Whisper on silence produces hallucinations ('Thanks for watching!'). Always gate with VAD." 技能文件也要求"拒绝任何没有 VAD 门控的长音频 Whisper 部署"。A、C、D 都不是实际现象。

### Q8 — 答案：C

WER 的分母是参考词数 N，而插入错误 I 没有上限：参考只有 2 个词，识别出 5 个词，就有 3 次插入，WER = 1.5。A、B、D 都是正确表述。

### Q9 — 参考答案

(a) 第一种：合并重复后为 `h _ e _ l _ l _ o _`，删 blank 得 `hello`。两段 `l l l` 中间的 blank 把它们隔开，才能保留双字母。去掉这个 blank 后，六个连续的 `l` 被合并成一个，输出 `helo`。**这正是 CTC 需要 blank 的根本原因之一**：没有 blank 就无法表示连续的相同字符。

(b) `prev` 记录的是"上一帧的 argmax"，无论它是否被输出、是否为 blank。写在 `if` 外，blank 也会更新 `prev`，所以 `a _ a` 中第二个 `a` 的 `prev` 是 blank，不等于 `a`，会被输出 → `aa`；`a a` → `a`。
如果挪进 `if` 里，blank 帧不更新 `prev`，`a _ a` 时第二个 `a` 的 `prev` 仍是 `a`，被当作重复跳过 → `a`；`a a` → `a`。这样 blank 就失去了"分隔重复"的作用，双字母全部丢失。

(c) `-1` 不是任何合法的 token 下标（下标从 0 开始），保证第一帧无论是什么都不会被误判为"与上一帧重复"。

### Q10 — 参考答案

(a) 这个简化版只记录"前缀"本身，不记录"前缀最后一帧是不是 blank"。当前缀已是 `(h, e, l)`、新帧是 `l` 时，不管中间是否隔过 blank，`seq[-1] == t` 都成立，于是被当作重复合并——双字母 `ll` 永远无法生成。代码自己的提示也说明了这一点："a proper prefix-tree beam … tracks P_blank / P_nonblank and preserves double letters"。

(b) 正确的前缀 beam search（已验证在 `build_frame_probs("hello world", 3, 1)` 上输出 `'hello world'`）：

```python
import math

def logsumexp(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def ctc_prefix_beam(frame_probs, beam_width=8):
    NEG = -math.inf
    beams = {(): (0.0, NEG)}            # prefix -> (log P_blank, log P_nonblank)
    for p in frame_probs:
        log_p = [math.log(max(pi, 1e-10)) for pi in p]
        nxt = {}

        def get(s):
            return nxt.get(s, (NEG, NEG))

        for prefix, (pb, pnb) in beams.items():
            total = logsumexp(pb, pnb)
            # 1) 输出 blank：前缀不变，变成"以 blank 结尾"
            b, nb = get(prefix)
            nxt[prefix] = (logsumexp(b, total + log_p[BLANK]), nb)
            for t in range(1, len(p)):
                lpt = log_p[t]
                if prefix and prefix[-1] == t:
                    # 2a) 紧跟着重复同一字符（中间无 blank）：合并，前缀不变
                    b, nb = get(prefix)
                    nxt[prefix] = (b, logsumexp(nb, pnb + lpt))
                    # 2b) 隔着 blank 再出现同一字符：真正的双字母，扩展前缀
                    ext = prefix + (t,)
                    b, nb = get(ext)
                    nxt[ext] = (b, logsumexp(nb, pb + lpt))
                else:
                    # 3) 不同字符：扩展前缀
                    ext = prefix + (t,)
                    b, nb = get(ext)
                    nxt[ext] = (b, logsumexp(nb, total + lpt))
        beams = dict(sorted(nxt.items(), key=lambda kv: -logsumexp(*kv[1]))[:beam_width])
    best = max(beams.items(), key=lambda kv: logsumexp(*kv[1]))[0]
    return "".join(VOCAB[i] for i in best)
```

关键在 2a / 2b：同一个字符，只有当前缀**以 blank 结尾**（`pb`）时才能扩展成双字母；以非 blank 结尾（`pnb`）时只能并入原前缀。补充：在 Step 4 的被破坏输入上，这个正确版本的结果与 greedy 完全相同（`'hlhce llolo wolnrld'`）——没有外部 LM 时，CTC 的 beam search 很难比 greedy 好多少，这也是技能文件说"没有 LM 时 beam 宽度超过 16 没有意义"的原因。

### Q11 — 参考答案

输出：

```text
1.3333333333333333
1.5
```

- `the cat sat` → `cat sat on the mat`：最优对齐是删掉 `the`（D=1），保留 `cat sat`，再插入 `on the mat`（I=3），共 4 次编辑，`4/3 ≈ 1.333`。
- `a b` → `a b c d e`：插入 3 个词，`3/2 = 1.5`。
- WER 可以大于 1，因为分母是参考词数，而插入没有上限。模型"啰嗦"或幻觉（重复输出、静音段编造文字）都可能导致 WER > 100%。
- `wer("", "hello")` 返回 `1.0`：参考为空时，分母为 0，代码约定"假设为空返回 0，否则返回 1"。这只是避免除零的约定——严格说 5 个插入词在空参考上无法定义 WER。评测中通常在语料级别汇总 `Σ(S+D+I) / ΣN`，单条空参考不会单独成为分母。

### Q12 — 参考答案

原因：`lp + lpt` 是累积对数概率，随帧数线性下降。本例每帧最大概率约 0.46（`log ≈ −0.78`），被破坏的帧会降到 `log(1e-10) ≈ −23`；1500 帧后很容易低于 `−745`，此时 `math.exp(x)` **下溢为 0.0**，两项都为 0 时 `math.log(0.0)` 抛出 `ValueError: math domain error`。即便不崩溃，精度也会严重丢失。

复现：

```python
import math
x = -800.0
math.log(math.exp(x) + math.exp(x))   # ValueError: math domain error

# 直接用本文件的函数：1320 帧的干净输入就会崩溃（已实测）
ctc_beam(build_frame_probs("hello world" * 30, 3, 1), beam_width=8)   # ValueError
```

修复——log-sum-exp 技巧，先提出最大值：

```python
def logsumexp(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))

logsumexp(-800.0, -800.0)   # -799.3068528194401，即 -800 + log 2
```

`exp(a − m)` 和 `exp(b − m)` 中至少一个等于 1，不会下溢。PyTorch 中对应 `torch.logaddexp` / `torch.logsumexp`；CTC loss 的前向-后向算法同样必须在对数域里这样做。

### Q13 — 参考回答要点

| 维度 | CTC | RNN-T | Attention enc-dec |
|------|-----|-------|------------------|
| 解决对齐的方式 | 每帧输出 token 或 blank，对所有能折叠成目标的对齐求和 | 在（帧, 已输出 token）格点上走路径，null 表示前进到下一帧，对所有路径求和 | 不显式对齐，decoder 用 cross-attention 自己"找"该看哪一段 |
| 自回归 | 否 | 对 token 是 | 是 |
| 流式 | 天然支持 | 天然支持 | 需限制 attention（分块等） |
| 内部 LM | 无（条件独立） | 有（predictor） | 有（decoder） |
| 推理延迟 | 最低，一次前向 | 低 | 与输出长度成正比 |
| 训练成本 | 低 | 高，3D loss lattice 占内存 | 中，标准 seq2seq 工具 |
| 代表 | wav2vec 2.0、MMS | Google 端侧 ASR、Parakeet | Whisper、SeamlessM4T |

- 讲义观点：2026 年各范式在 LibriSpeech 上的 WER 差距很小（1.4% vs 1.58%），**部署层面的差异巨大**——选型看流式需求、延迟预算、硬件。
- 加分点：说出 attention 的"可以看任何地方"既是优势也是缺陷（容易重复、跳词、幻觉）；混合方案（CTC + attention 联合训练）也很常见。

### Q14 — 参考回答要点

- **定义**：encoder 输出 `T` 帧，每帧是 `V+1` 维分布（V 个 token + blank）。定义折叠函数 `B`：先合并相邻重复，再删 blank。目标序列 `y` 的概率 = 所有满足 `B(π) = y` 的帧级路径 `π` 的概率之和，每条路径的概率是各帧概率之积（条件独立）。loss = `−log P(y|x)`。
- **blank 的作用**：①表示"这一帧不输出"，容纳静音和长音素；②分隔重复字符，使 `ll`、`oo` 可以被表示。
- **高效计算**：路径数随 `T` 指数增长，用前向-后向动态规划（类似 HMM），在扩展标签序列（每个 token 两侧插 blank，长度 `2U+1`）上递推，复杂度 `O(T·U)`，且必须在对数域计算防止下溢。
- **长度约束**：`T ≥ U + (相邻重复字符对数)`，因为每个重复字符之间至少要插一个 blank 帧。所以 encoder 的下采样率不能太高（例如 10 ms 帧再 4 倍下采样到 40 ms，对快语速的字符级输出可能不够）。
- **推理**：greedy（逐帧 argmax + 折叠）或前缀 beam search + LM 融合。
- **常见误区**：认为 CTC 解码"先删 blank 再合并"；认为 beam search 不需要区分以 blank / 非 blank 结尾。

### Q15 — 参考回答要点

- **文本归一化先行**：统一大小写、去标点、数字/缩写统一写法（"10" vs "ten"）。讲义与技能文件都要求"不归一化就不报告 WER"。不同模型的输出风格不同（Whisper 带标点和大小写），不归一化会让 WER 虚高。
- **语料级汇总**：`Σ(S+D+I) / ΣN`，而不是对每句的 WER 求平均（短句权重会被放大）。
- **领域内测试集**：LibriSpeech 上的 1.4% 不代表你的业务数据；要在业务域的标注测试集上测，并按说话人、口音、噪声分桶。
- **中文 / 日文**：没有空格分词，常用 CER（字错误率）；或者先用固定的分词器再算 WER，但分词器本身会引入误差。
- **WER 失真的情况**：插入导致 > 100%；同义的不同写法被算错；关键实体（人名、药名）错一个词和虚词错一个词权重相同——可补充实体级准确率；对静音片段的幻觉率要单独统计（技能文件第 5 条）。
- 加分点：报告置信区间或在多个测试集上报告；说明 WER 与下游任务（如意图识别）的相关性不一定线性。

### Q16 — 参考回答要点

| 场景 | 模型 | 解码 | 切块 / VAD | 语言策略 |
|------|------|------|-----------|---------|
| (a) 车载流式 | Parakeet-TDT 或 Riva（流式）；算力很紧时用 Whisper-Tiny 量化 / Moonshine | greedy 或小 beam，延迟优先 | 分块 encoder attention + 状态延续；VAD 判断说话结束 | 固定语言，或少数几种语言的受限 LID |
| (b) 2 小时会议 | Whisper-large-v3-turbo + VAD 切分（WhisperX） | beam + 温度回退 | 必须用 VAD 切成 ≤30 秒片段，或 `chunk_length_s=30, stride=5` | 已知语言就强制 `language="en"` 等，避免 LID 漂移 |
| (c) 医疗口述 | 微调 wav2vec 2.0 + 领域 LM 融合 | 前缀 beam search + LM shallow fusion | VAD 去掉长静音 | 固定语言；加热词/术语表 |

- 依据：讲义 Use It 表 + Pitfalls。
- 加分点：(b) 还需说话人分离（diarization）与时间戳对齐；(c) 的评估要单独看术语准确率；所有场景都要在本域测试集上评测 WER 和静音幻觉率。

### Q17 — 参考回答要点

- **原因**：①attention decoder 本质是一个条件语言模型，没有"必须对齐到音频"的约束，输入缺乏有效语音时，decoder 的语言先验会接管，生成训练数据里高频的句子；②Whisper 用大规模弱监督的网络音视频字幕训练，静音片尾常配着"Thanks for watching!"之类的字幕，模型学会了这种关联；③自动语种识别在噪声上不稳定，会把片段误判成其他语言（讲义："mis-routes noisy clips to Japanese or Welsh"）。
- **缓解**：
  1. VAD 门控（讲义第一条坑），只把语音段送进模型；
  2. 已知语言时强制 `language`；
  3. 利用 Whisper 自带的启发式：no-speech 概率阈值、压缩比阈值（检测重复输出）、平均对数概率阈值，配合温度回退；
  4. 后处理：过滤已知的幻觉短语、检测重复 n-gram；
  5. 长音频切块时给足上下文重叠（stride），避免切在词中间。
- **评估**：单独构造静音/噪声测试集，统计幻觉率（技能文件："hallucination rate on silence clips"）。
- 加分点：对比 CTC 类模型——它们在静音上通常只输出 blank，几乎不会幻觉，这是条件独立的"副作用好处"。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：ASR 的输入是 80 维 log-mel、10 ms 帧移。
- [阶段 05 · 08 用于文本的 CNN 与 RNN](../../../05-nlp-foundations-to-advanced/08-cnns-rnns-for-text/docs/zh.md)：RNN-T 的 predictor 就是 RNN。
- [阶段 05 · 09 序列到序列](../../../05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/zh.md)：encoder-decoder 与 beam search 的基础。
- [阶段 05 · 10 注意力机制](../../../05-nlp-foundations-to-advanced/10-attention-mechanism/docs/zh.md)：cross-attention 是 Whisper 解码器的核心。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：log-sum-exp 技巧。

### 本节被哪些后续内容用到
- [阶段 06 · 05 Whisper——架构与 Fine-Tuning](../../05-whisper-architecture-finetuning/docs/zh.md)：深入 attention encoder-decoder 的代表模型。
- [阶段 06 · 11 实时音频处理](../../11-real-time-audio-processing/docs/zh.md)：流式 ASR 的分块、缓冲与延迟。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：ASR 作为语音助手的第一环。
- [阶段 06 · 14 语音活动检测与对话轮次交接](../../14-voice-activity-detection-turn-taking/docs/zh.md)：本节反复强调的 VAD 门控。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：WER 及其他音频指标的系统讲解。
- [阶段 07 · 10 音频 Transformer 与 Whisper](../../../07-transformers-deep-dive/10-audio-transformers-whisper/docs/zh.md)：从 Transformer 架构角度看 ASR。

### 延伸关键词
`CTC forward-backward` · `TDT (Token-and-Duration Transducer)` · `prefix beam search` · `shallow fusion / deep fusion` · `KenLM` · `CER` · `文本归一化 (Whisper EnglishTextNormalizer)` · `WhisperX` · `Silero VAD` · `热词增强`
