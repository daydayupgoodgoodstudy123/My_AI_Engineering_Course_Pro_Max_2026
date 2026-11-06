# 测验 · 音频 Evaluation — WER、MOS、UTMOS、MMAU、FAD 和开放排行榜（Audio Evaluation — WER, MOS, UTMOS, MMAU, FAD, and the Open Leaderboards）

> **阶段 06 · 语音与音频 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 任务 → 主指标 | ASR→WER；TTS→MOS/UTMOS；声音克隆→SECS；说话人验证→EER；分离→DER；分类→top-1/mAP；音乐→FAD；音频语言模型→MMAU-Pro；流式 S2S→延迟 P50/P95 |
| 2 | WER / CER | `WER = (S + D + I) / N`（替换+删除+插入，除以参考词数），本质是词级编辑距离；插入多时可以 > 100%；CER 是字符级，用于中文、粤语等分词有歧义的语言 |
| 3 | 先规范化再打分 | 小写、去标点、数字展开（"5"→"five"）、缩写展开；必须在报告里写明规范化规则 |
| 4 | RTFx 与首 token 延迟 | RTFx = 每秒墙钟时间处理的音频秒数，越高越好（Parakeet-TDT 约 3380×、Whisper-large-v3 约 30×）；流式 ASR 还要看首 token 延迟 |
| 5 | MOS vs UTMOS | MOS：1–5 分人评，金标准但慢（20+ 听众 × 100+ 样本）；UTMOS：学习型 MOS 预测器，与人评相关约 0.9，但在噪声/克隆/情绪语音上外推不可靠 |
| 6 | 声音克隆三元组 | SECS（ECAPA embedding 余弦，> 0.75 可辨认）+ MOS + CER：SECS 高 MOS 低 = 音色对但不自然；反之 = 自然但不像本人 |
| 7 | TTS 往返 WER | TTS 输出 → Whisper 转写 → 与输入文本算 WER/CER，用来捕捉可懂度回退 |
| 8 | EER / minDCF / DER | EER：FAR = FRR 的点；minDCF：在选定工作点的加权代价，更贴近生产；DER = (误报 + 漏检 + 说话人混淆) / 总说话时长 |
| 9 | FAD | 真实与生成音频在 VGGish embedding 上拟合高斯后的 Fréchet 距离，越低越好；强烈依赖参考集，必须配人评 |
| 10 | 三条铁律 | 先规范化；报告分布而不是均值（P50/P95/P99、按类、按类别）；至少跑一个公认公开基准 + 自己的 held-out 集 |

### 核心技能（能动手做到）

- [ ] 能用动态规划从零实现编辑距离，并据此实现带规范化的 WER 与 CER，手算短句的 S/D/I
- [ ] 能为英文 ASR 写一份规范化规则（小写、去标点、缩写与数字展开），并说明它对 WER 的影响
- [ ] 能实现 EER 阈值扫描，并在交换"同人/异人"分数参数时识别出"EER ≈ 100%"这类方向错误
- [ ] 能实现对角协方差近似下的 FAD 形式距离，并通过"同分布两组样本"实验观察小样本偏差
- [ ] 能为 TTS / 声音克隆发布设计评估方案：UTMOS + 人评 MOS + SECS + 往返 CER + TTFA 分位数
- [ ] 能为一个模型发布列出：主指标、次指标、规范化规则、公开基准、内部集与切片、报告格式

---

## 二、基础自测（选择题）

**Q1.** 参考文本 "Please turn on the lights."，识别结果 "please turn on the light"。按"小写 + 去标点 + 去首尾空格"规范化后，WER 是：

- A. 约 0.17
- B. 0.20
- C. 0.25
- D. 0.04

**Q2.** 关于 WER，下列说法正确的是：

- A. WER 的取值范围严格在 [0, 1]
- B. 因为分母是参考词数 N，而插入错误不受限制，WER 可以超过 100%
- C. WER 只统计替换错误
- D. WER 越高越好

**Q3.** 讲义说 Parakeet-TDT 的 RTFx 约为 3380×。这意味着处理 1 小时的音频大约需要：

- A. 3380 秒
- B. 约 1 秒
- C. 约 1 分钟
- D. 约 18 秒

**Q4.** 你用 UTMOS 自动评估一个情感丰富、带背景音乐的有声书 TTS，分数偏低。最需要警惕的是：

- A. UTMOS 只能评估中文
- B. UTMOS 在干净朗读语音上训练，对噪声、克隆、情绪化语音外推不可靠，需要人评 MOS 复核
- C. UTMOS 分数越低说明模型越好
- D. UTMOS 衡量的是说话人相似度

**Q5.** 一个声音克隆模型 SECS = 0.86，但 MOS 只有 2.9。最合理的解读是：

- A. 声音像本人，但听起来不自然
- B. 声音自然，但不像本人
- C. 可懂度很差
- D. 模型完美

**Q6.** 说话人分离的 DER 由哪几项组成？

- A. 替换 + 删除 + 插入
- B. 误报语音 + 漏检语音 + 说话人混淆，除以总说话时长
- C. FAR + FRR
- D. 精确率 + 召回率

**Q7.** 讲义提到在 MMAU-Pro 的 multi-audio 类别上，各模型准确率都在约 22%，而 4 选 1 随机是 25%。这说明：

- A. 这些模型在多音频推理上与随机猜测无异甚至更差，聚合准确率会掩盖这个弱点
- B. 22% 是很好的成绩
- C. MMAU-Pro 题目有错
- D. multi-audio 类别是 2 选 1

**Q8.** A 论文报告 FAD = 3.1，B 论文报告 FAD = 4.5，但两篇用的参考集不同。下列做法正确的是：

- A. 直接认定 A 更好
- B. 直接认定 B 更好
- C. 不能直接比较；应在同一参考集、同一 embedding 模型、相近样本量下重新计算，并配合人评
- D. 把两个数取平均

---

## 三、动手 / 代码题

**Q9.**（预测输出 + 改进）`main.py` 的规范化与 WER 如下：

```python
def normalize(text):
    import re
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def wer(ref, hyp):
    r, h = normalize(ref).split(), normalize(hyp).split()
    return _edit_distance(r, h) / max(1, len(r))
```

(a) 写出 `wer("what's the weather today", "what is the weather today")` 和 `wer("set a 5 minute timer", "set a five minute timer")` 的结果，并用 S/D/I 解释。
(b) 这两个"错误"在用户看来是错误吗？请改进 `normalize`，让它们的 WER 变为 0。

**Q10.**（找不一致）同一文件里的 CER：

```python
def cer(ref, hyp):
    return _edit_distance(list(ref), list(hyp)) / max(1, len(ref))
```

(a) `wer("Play jazz", "play jazz")` 和 `cer("Play jazz", "play jazz")` 分别是多少？问题在哪？
(b) `wer("play jazz", "please please play some jazz music now")` 是多少？这说明 WER 的什么性质？

**Q11.**（原理 + 找问题）`main.py` 的 FAD 形式距离：

```python
def embedding_fad_like(real_embeds, fake_embeds):
    def mean_var(embs):
        n = len(embs[0])
        mean = [sum(e[i] for e in embs) / len(embs) for i in range(n)]
        var = [sum((e[i] - mean[i]) ** 2 for e in embs) / len(embs) for i in range(n)]
        return mean, var
    mu_r, v_r = mean_var(real_embeds)
    mu_f, v_f = mean_var(fake_embeds)
    mean_dist = sum((a - b) ** 2 for a, b in zip(mu_r, mu_f))
    var_dist = sum((math.sqrt(a) - math.sqrt(b)) ** 2 for a, b in zip(v_r, v_f))
    return math.sqrt(mean_dist + var_dist)
```

(a) 它和真正的 FAD 公式 `‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_r Σ_g)^½)` 是什么关系？做了哪两处改动？
(b) 程序打印 `FAD-like = 1.748 (MusicGen-small on MusicCaps: 4.5)`，这个对比有意义吗？
(c) 用两组**来自同一分布**的 32 维、各 50 个样本算这个距离，会得到 0 吗？这对 FAD 的使用有什么启示？

**Q12.**（预测输出）`eer_from_scores(same, diff)` 的约定是"分数越高越像同一人"。程序中 `same ~ N(0.80, 0.06)`、`diff ~ N(0.20, 0.15)`，打印 `EER = 0.10%`。如果有人把参数顺序写反，调用 `eer_from_scores(diff, same)`，会得到什么？为什么这种 bug 很危险？

---

## 四、面试高频题

**Q13.**（基础必考）WER 怎么定义、怎么算？为什么必须先做文本规范化？什么情况下用 CER 而不是 WER？

**Q14.**（原理深挖）怎么全面评估一个 TTS / 声音克隆模型？MOS、UTMOS、SECS、往返 WER、TTFA 分别衡量什么，各自有什么盲点？

**Q15.**（工程实践）你要发布一个新的英文 ASR 模型，请设计评估方案，让团队和外部评审都信服。

**Q16.**（追问型）FAD 的原理是什么？有哪些已知局限？为什么讲义的 skill 拒绝"只报 FAD"的音乐模型发布？

**Q17.**（场景设计）如何评估一个流式语音到语音的语音助手（如 Moshi 或流水线 agent）？请给出指标、测量方式和报告格式。

---

## 五、参考答案与解析

### Q1 — 答案：B

规范化后参考为 `please turn on the lights`（5 个词），识别为 `please turn on the light`，只有 `lights → light` 一个替换：WER = 1 / 5 = 0.20。（讲义 Step 1 的注释写的是 "~0.17"，但 0.17 ≈ 1/6，需要参考文本有 6 个词；按本题的规范化方式应为 0.20，用 `main.py` 的 `wer()` 实测也是 0.2。）

### Q2 — 答案：B

`WER = (S + D + I) / N`，N 是参考词数。识别结果里可以插入任意多的词，所以 WER 没有上界（Q10 中实测 2.5，即 250%）。WER 越低越好。

### Q3 — 答案：B

RTFx = 音频时长 / 处理时间。3600 秒 / 3380 ≈ 1.07 秒。对比 Whisper-large-v3 的约 30×：1 小时需要 2 分钟。RTFx 衡量的是**吞吐**，与流式场景关心的首 token 延迟是两回事。

### Q4 — 答案：B

讲义 Pitfall："UTMOS extrapolation. Trained on VCTK-style clean speech; scores noisy / cloned / emotional audio poorly." UTMOS 适合做快速回归检测，遇到分布外的音频（有声书、带背景音乐、强情绪）必须用人评 MOS 确认。D 是 SECS 的作用。

### Q5 — 答案：A

讲义："Cloning that scores high SECS but low MOS means timbre-right-but-unnatural; the opposite means natural voice but wrong speaker." SECS 0.86 超过 0.75 的"可辨认"线，音色像；MOS 2.9 偏低，自然度差。可懂度要看 CER / 往返 WER，C 无法从这两个数判断。

### Q6 — 答案：B

`DER = (FA + Miss + Confusion) / total_speaker_time`。A 是 WER 的组成；C 是说话人验证的错误率。讲义给出的参考：AMI 会议数据上 DER 10–20% 是现实水平。

### Q7 — 答案：A

22% 低于 25% 的随机水平，说明在"多段音频联合推理"上，模型基本没有能力。如果只报告整体准确率（Gemini 2.5 Pro 约 60%），这个短板会被其他类别的好成绩掩盖——这正是讲义"按类别报告"的原因。

### Q8 — 答案：C

讲义 Pitfall："FAD depends on reference set. Compare against the same reference distribution across models." FAD 衡量的是"生成分布离参考分布多远"，参考集一变，尺子就变了；embedding 模型和样本量（见 Q11）也会影响数值。

### Q9 — 参考答案

(a) 实测：

```text
wer("what's the weather today", "what is the weather today") = 0.500
wer("set a 5 minute timer", "set a five minute timer")      = 0.200
```

- 第一句：规范化把 `what's` 变成 `whats`（只删了撇号，没有展开缩写），参考为 `whats the weather today`（4 词），识别为 `what is the weather today`。最优对齐是 `whats → what`（1 个替换）+ 插入 `is`（1 个插入），WER = 2 / 4 = 0.5。
- 第二句：参考 `set a 5 minute timer`（5 词），识别 `set a five minute timer`，`5 → five` 1 个替换，WER = 1 / 5 = 0.2。

(b) 对用户来说两句都是**完全正确**的识别，只是书写形式不同。讲义要求"Lowercase, strip punctuation, normalize numbers before scoring"，而这份 `normalize` 没做数字和缩写展开。改进示例（仅演示思路，生产应使用完整的规则库，如讲义提到的 `whisper_normalizer`）：

```python
import re

CONTRACTIONS = {"what's": "what is", "it's": "it is", "don't": "do not"}
NUMBERS = {"5": "five", "10": "ten"}


def normalize(text):
    text = text.lower()
    for short, full in CONTRACTIONS.items():
        text = re.sub(rf"\b{re.escape(short)}\b", full, text)   # 先展开缩写，再删标点
    text = re.sub(r"[^a-z0-9\s]", "", text)
    words = [NUMBERS.get(w, w) for w in text.split()]           # 数字统一成英文单词
    return " ".join(words)
```

改进后两句的 WER 都是 0.0（实测），而 "Please turn on the lights." 仍为 0.2（`lights/light` 是真实错误，规范化不应抹掉它）。注意顺序：必须**先展开缩写再删标点**，否则撇号被删后就匹配不上了。

### Q10 — 参考答案

(a) `wer = 0.0`，`cer ≈ 0.111`（1 / 9）。`wer` 内部调用了 `normalize`，大小写被统一；`cer` 直接在原始字符串上比较，`P` 与 `p` 算一次替换。**同一个文件里两个指标的规范化不一致**，会导致"WER 为 0 但 CER 不为 0"的怪现象。修复：

```python
def cer(ref, hyp):
    r, h = normalize(ref), normalize(hyp)
    return _edit_distance(list(r), list(h)) / max(1, len(r))
```

（对中文等语言，CER 的规范化规则还应包括全半角统一、去除空格等。）

(b) 参考 `play jazz` 只有 2 个词，识别结果多出 5 个词，编辑距离 = 5 次插入，WER = 5 / 2 = **2.5**。说明 WER 没有上界；短句的 WER 波动极大，所以报告时应在整个测试集上**汇总编辑次数再除以总词数**（corpus-level），而不是对每句 WER 取平均。

### Q11 — 参考答案

(a) 真正的 FAD 对两组 embedding 各拟合一个**全协方差**高斯，然后计算 `‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_r Σ_g)^½)`。这份代码做了两处改动：
1. **对角近似**：只估计每一维的方差，忽略维度间相关性。此时迹项化简为 `Σᵢ (σ_r,i − σ_g,i)²`，正是代码里的 `var_dist`。
2. **多开了一次根号**：返回 `sqrt(mean_dist + var_dist)`，而通常报告的 FAD 是不开根号的平方距离形式。本例中开根号前是 3.057，开根号后是 1.748。

(b) 没有意义。真实 FAD 用的是 VGGish 的 128 维 embedding、全协方差、不开根号，并依赖特定参考集；这里是 32 维随机高斯、对角近似、开了根号。数值量纲都不同，只能用来理解"均值差 + 方差差"的结构。

(c) **不会是 0**。实测两组来自同一 N(0, 1) 的 32 维样本，各 50 个时距离约 1.36，各 500 个时约 0.44——与本例真假两组之间的 1.75 相差不大。原因是样本均值和方差本身有估计误差，维度越高、样本越少，偏差越大。启示：FAD 必须在**相同样本量**下比较；样本数要足够多（远大于 embedding 维度）；最好报告置信区间，或用"参考集自己对自己"的距离作为噪声底线。

### Q12 — 参考答案

会得到约 **99.9%**（实测 `eer_from_scores(diff, same)` 返回 0.999）。函数假设第一个参数是"同人"分数、越高越像同人：`far = P(diff ≥ t)`、`frr = P(same < t)`。参数交换后，两个"错误率"实际变成了"正确率"，在某个阈值处二者都接近 1、差值接近 0，于是返回接近 100% 的 EER。

危险在于：①不报错、不崩溃；②数字看起来"只是模型很差"，可能导致错误地否定一个好模型；③同样的方向问题在反欺骗检测里也很常见（第 16 节的代码就因分数方向不一致打印了 100% 的 EER）。防御：在函数文档里写明分数方向，并用一个人造的完美分类器做单元测试（EER 必须为 0）。

### Q13 — 参考回答要点

- 定义：`WER = (S + D + I) / N`，S/D/I 来自参考词序列与识别词序列之间的最小编辑距离（Levenshtein），用 `O(m·n)` 的动态规划求解；N 是参考词数。
- 规范化的必要性：大小写、标点、数字写法（5 / five）、缩写（what's / what is）这些"格式差异"不应被计为识别错误，否则不同系统之间、不同版本之间都不可比；必须报告所用的规范化规则（jiwer 的变换组合，或 Whisper 的 normalizer）。
- CER：同一公式在字符级计算。中文、粤语等分词有歧义的语言用 CER；评估字符级系统或 TTS 往返可懂度也常用 CER。
- 加分点：WER 可以 > 1；语料级 WER 应汇总编辑次数再除以总词数；按口音、性别、噪声条件等切片报告（讲义："A 5% WER overall can hide 30% WER on accented speech."）；吞吐看 RTFx，流式看首 token 延迟。

### Q14 — 参考回答要点

| 指标 | 衡量什么 | 盲点 |
|------|---------|------|
| MOS（人评） | 整体自然度，金标准 | 慢、贵；众包听众 ≠ 目标用户（讲义："20 Amazon Mechanical Turk workers ≠ 20 target users"） |
| UTMOS | 自动预测 MOS，与人评相关约 0.9 | 训练于干净朗读语音，对噪声/克隆/情绪语音外推差 |
| SECS | 克隆音色与参考音色的 ECAPA 余弦，> 0.75 可辨认 | 只看音色，不看自然度和内容 |
| 往返 WER/CER | TTS → Whisper → 对比原文，衡量可懂度 | 受 ASR 本身错误影响；对数字、专有名词的读法敏感 |
| TTFA | 首包音频延迟（Kokoro-82M 约 100 ms，F5-TTS 约 1 s） | 必须报告分位数而非均值 |

- 组合用法：克隆场景用 SECS + MOS + CER 三元组；发布时 UTMOS 做快速回归、人评 MOS 做最终确认。
- 加分点：结合 skill 示例——对比基线时做盲测 A/B、按语言和题材（金额、日期、专有名词、语码转换）分别报告，并列出失败模式。

### Q15 — 参考回答要点

- 主指标：WER（附明确的规范化规则，如 Whisper normalizer）。
- 次指标：CER（多语言时）、RTFx（吞吐）、首 token 延迟（流式时，报 P50/P95）。
- 公开基准：在 Hugging Face Open ASR Leaderboard 的标准数据集上报告，便于同行横向比较。
- 内部集：反映真实流量的 held-out 数据，并按口音、性别、年龄、噪声条件、领域词汇切片报告——聚合 WER 会掩盖少数群体上的高错误率。
- 报告格式：头条数字 + 分切片表 + 失败案例；评估 harness 固定下来，每次模型更新自动运行（讲义："Pair every deploy with a fixed eval harness that runs on every model update."）。
- 常见误区：只追公开基准——讲义指出前沿模型在公开基准上已接近饱和，必须有自己的 held-out 集。

### Q16 — 参考回答要点

- 原理：用预训练音频分类模型（VGGish）提取真实与生成音频的 embedding，各拟合一个多元高斯，计算两个高斯的 Fréchet 距离（均值差 + 协方差差），越低表示生成分布越接近真实分布。
- 局限：
  1. 依赖参考集——换参考集数值不可比；
  2. 依赖 embedding 模型——VGGish 是为分类训练的，未必捕捉音乐性；
  3. 小样本有偏——同分布两组样本的距离也不为 0（Q11）；
  4. 只衡量分布层面的相似度，不衡量与文本提示的对齐（需要 CLAP Score），也不保证单个样本好听。
- skill 拒绝"只报 FAD"：音乐最终由人耳评判，讲义说"Listening panel MOS. Still the final word for consumer-grade music."，所以必须搭配人评面板。
- 加分点：说出 CLAP Score > 0.3 可视为文本-音频对齐合理；参考值：讲义给出 MusicGen-small 在 MusicCaps 上约 4.5、MusicLM 约 4.0。

### Q17 — 参考回答要点

- 延迟：从"用户说完"到"第一声可听到的回复"的墙钟时间，报 P50 / P95 / P99（讲义：Moshi 约 200 ms，GPT-4o Realtime 约 300 ms）。
- 插话响应（barge-in）：从用户打断到助手静音的时间，目标 < 150 ms。
- 内容质量：输出语音的 WER（转写后与预期回复对比，或检查可懂度）和 MOS。
- 测量方式：用录制好的固定测试对话回放，在客户端侧打时间戳（含网络与播放缓冲），而不是只看服务端日志；不同网络条件、不同并发下分别测。
- 报告：延迟直方图与分位数、按场景（安静/嘈杂、短句/长句）切片、失败案例（误打断、长时间沉默）。
- 加分点：把第 14 节的 VAD/turn-taking 指标（误打断率、首字截断率）纳入同一 harness；流水线方案要拆分各级延迟（VAD hangover、STT、LLM 首 token、TTS TTFA）以便定位瓶颈。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：精确率、召回率、ROC、按类报告——讲义列出的前置课。
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：WER、CER 的来源。
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：EER、ECAPA embedding（讲义 Step 5 的 EER 代码与之相同）。
- [阶段 06 · 07 文本转语音](../../07-text-to-speech/docs/zh.md)：MOS、UTMOS、TTFA 的应用对象。
- [阶段 06 · 09 音乐生成](../../09-music-generation/docs/zh.md)：FAD、CLAP Score 的应用对象。
- [阶段 06 · 10 音频语言模型](../../10-audio-language-models/docs/zh.md)：MMAU、MMAU-Pro 评估的模型。

### 本节被哪些后续内容用到
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：PESQ、ViSQOL 等重建指标与本节指标的互补。
- [阶段 06 · 15 Streaming 语音到语音](../../15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：延迟分位数与插话响应的评估对象。
- [阶段 06 · 16 语音反欺骗和音频水印](../../16-anti-spoofing-audio-watermarking/docs/zh.md)：EER 在反欺骗中的应用、分数方向问题。
- [阶段 08 · 14 生成模型评估（FID、CLIP Score）](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：FID 与 FAD 同源，CLIP Score 与 CLAP Score 同源。
- [阶段 17 · 08 推理指标与 Goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：延迟分位数与吞吐的生产化度量。
- [阶段 19 · 03 实时语音助手（毕业项目）](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：把本节的评估 harness 用在完整系统上。

### 延伸关键词
`jiwer` · `whisper_normalizer` · `Levenshtein 距离` · `corpus-level WER` · `RTFx` · `UTMOS` · `SECS / ECAPA` · `minDCF` · `DER / JER` · `VGGish` · `CLAP Score` · `MMAU-Pro` · `Open ASR Leaderboard` · `TTS Arena / ELO`
