# 测验 · 神经音频编解码器 — EnCodec、SNAC、Mimi、DAC 和语义声学分离（Neural Audio Codecs — EnCodec, SNAC, Mimi, DAC and the Semantic-Acoustic Split）

> **阶段 06 · 语音与音频 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要神经音频 codec | 语言模型只吃离散 token，音频是连续波形；codec = 把波形离散成小词表 token 的编码器 + 把 token 还原成波形的解码器 |
| 2 | 残差向量量化 RVQ | 一串小码本级联：第 1 级量化编码器输出，第 2 级量化"剩下的残差"，以此类推；解码时把每帧各级选中的码字**相加** |
| 3 | RVQ 的"组合词表" | 8 个 1024 码本可表示 `1024^8 ≈ 10^24` 种组合，但只需存储和搜索 `8 × 1024` 个码字 |
| 4 | 两大家族 | 重建优先（EnCodec、DAC，token 是"声学"的，什么都编进去）vs 语义优先（Mimi、SpeechTokenizer，码本 0 被迫编码语言/音素内容） |
| 5 | 帧率决定序列长度 | EnCodec-24k 75 Hz、DAC 86 Hz、SNAC 粗层约 12 Hz、Mimi 12.5 Hz；帧率越低，LM 序列越短、生成越快 |
| 6 | 码率与 token 数算术 | 码率 = 帧率 × 码本数 × log2(码本大小)；token 数 = 时长 × 帧率 × 码本数（例：Mimi 10 s × 12.5 × 8 = 1000） |
| 7 | 多尺度 RVQ（SNAC） | 粗码本用低帧率画"草图"，细码本用高帧率补细节，层级结构与 LM 生成天然契合（Orpheus-3B 采用） |
| 8 | 语义 / 声学分解生成 | 先由文本生成语义 token（码本 0），再以语义 + 说话人参考生成声学 token（码本 1–7）——这是 zero-shot 声音克隆的基础 |
| 9 | 指标与取舍 | 每比特感知质量上传统 Opus 仍然领先；神经 codec 胜在"产出离散 token"与"可被生成模型利用"；重建好 ≠ 适合做 LM tokenizer |

### 核心技能（能动手做到）

- [ ] 不依赖任何库，从零实现一维 k-means 学码本、RVQ 编码 `rvq_encode` 与解码 `rvq_decode`，并打印"码本数 vs MSE"表
- [ ] 能手算任意 codec 配置的码率与 10 秒音频的 token 数（如 EnCodec 75 Hz × 8 × 10 bit = 6 kbps；DAC 86 Hz × 8 码本 × 10 s = 6880 token）
- [ ] 能做"码本消融"实验：分别丢掉第 0 级和最后一级码本后解码，比较误差，并据此解释 Mimi 中码本 0 为什么最关键
- [ ] 能用 `encodec` 库按讲义的方式 `set_target_bandwidth(6.0)` 编码再解码，说出 `codes` 的形状 `(1, n_codebooks, n_frames)` 各维含义
- [ ] 能根据任务（AR-LM TTS、全双工对话、音乐生成、高保真重建、纯压缩）选出 codec，并用帧率、码本结构给出理由
- [ ] 能画出"文本 → 语义 token → 声学 token → codec 解码器 → 波形"的两阶段生成流程，并指出声音克隆发生在哪一步

---

## 二、基础自测（选择题）

**Q1.** 在 RVQ 中，第 k 级（k ≥ 2）码本量化的对象是：

- A. 编码器的原始输出
- B. 前 k−1 级量化之后剩下的残差
- C. 解码器输出与原始波形之间的误差
- D. 第 k−1 级码本选出的索引值

**Q2.** EnCodec-24k 的帧率为 75 Hz，每个码本 1024 个码字。把目标带宽设为 6 kbps 时，用到的码本数是：

- A. 4
- B. 6
- C. 8
- D. 32

**Q3.** 用 Mimi（12.5 Hz、8 个码本）编码一段 10 秒语音，自回归 LM 一共需要预测多少个 token？

- A. 125
- B. 1000
- C. 6880
- D. 7500

**Q4.** 关于 Mimi 的码本 0，下列说法正确的是：

- A. 码本 0 的码字数是其他码本的 8 倍
- B. 码本 0 通过辅助损失向 WavLM 特征蒸馏，主要承载"说了什么"；码本 1–7 是声学残差
- C. 码本 0 专门编码背景噪声，方便降噪
- D. 码本 0 的帧率比其他码本高

**Q5.** 讲义指出：直接用"纯重建型"codec 的 token 做文本到语音生成，常会得到模糊的语音。根本原因是：

- A. 这类 codec 的码率太低
- B. LM 必须在同一套码本里同时学习语言结构和声学结构，难以扩展
- C. 这类 codec 的解码器不能流式运行
- D. 这类 codec 没有对码本做 L2 归一化

**Q6.** 下列关于 SNAC 的描述，正确的是：

- A. 只用一个超大码本，避免残差累积误差
- B. 多尺度 RVQ：粗码本运行在较低帧率、细码本运行在较高帧率，对音频做层级建模
- C. 码本 0 从 WavLM 蒸馏而来，专门编码语义
- D. 44.1 kHz 全频带，是开源 codec 中重建保真度最高的

**Q7.** 讲义的重建质量表中，Opus（20 kbps）的 PESQ 高于所有神经 codec。最合理的解读是：

- A. 神经 codec 没有实际价值，应该全部换成 Opus
- B. 每比特感知质量上传统 codec 仍占优；神经 codec 的价值在于产出离散 token，并让生成模型能在 token 上建模
- C. PESQ 不适用于语音，所以这个表没有意义
- D. Opus 内部同样使用 RVQ，因此两者本质相同

**Q8.** 一个团队在 12.5 Hz 的 Mimi token 上预训练了语音 LM，然后直接换成 50 Hz 的 codec token 继续微调，训练 loss 看上去正常下降，但生成质量很差。这属于讲义中哪类坑？

- A. 码本过多（Too many codebooks）
- B. 帧率不匹配（Frame-rate mismatch），会"静默失败"
- C. 认为所有码本同等重要
- D. 只用重建质量做评估

---

## 三、动手 / 代码题

**Q9.**（找 bug / 改写）`main.py` 的 Step 2 中有这样几行：

```python
    for n_cb in [1, 2, 4, 8, 12]:
        indices, codebooks = rvq_encode(sig, codebook_size=8, n_codebooks=n_cb)
        recon = rvq_decode(indices, codebooks, length=len(sig))
        err = mse(sig, recon)
        bits_per_frame = n_cb * 3
        bitrate = bits_per_frame * 50
```

(a) 这里的 `3` 和 `50` 分别代表什么？
(b) 如果有人把 `codebook_size` 改成 1024，表格里哪一列会变成错的？请改写成不会出错的版本。
(c) 用改好的公式算一下：Mimi 若每个码本 2048 个码字，12.5 Hz × 8 个码本的码率是多少？

**Q10.**（预测输出 + 解释）在 `main.py` 的函数基础上做"码本消融"：用 4 级 RVQ 编码，然后分别**去掉第 0 级**和**去掉第 3 级（最后一级）**再解码。

```python
sig = generate_signal(1000)
ind, cbs = rvq_encode(sig, codebook_size=8, n_codebooks=4)
drop_first = rvq_decode(ind[1:], cbs[1:], len(sig))
drop_last  = rvq_decode(ind[:3], cbs[:3], len(sig))
print(mse(sig, drop_first), mse(sig, drop_last))
```

两个 MSE 大概各是什么量级？哪个大得多？这和 Mimi "码本 0 丢了就听不懂、码本 7 丢了几乎听不出"有什么联系？

**Q11.**（对比实验 + 原理）同样是每帧 6 bit：方案甲用**一个 64 码字**的码本（`learn_codebook(sig, 64)` 后量化），方案乙用 **2 级 × 8 码字**的 RVQ。实测哪一个 MSE 更低？既然如此，为什么真实 codec 还要用 RVQ？请从码本规模的角度定量说明。

---

## 四、面试高频题

**Q12.**（基础必考）什么是 RVQ？为什么现代神经音频 codec 几乎都用 RVQ，而不是一个大码本？

**Q13.**（原理深挖）解释"语义 token / 声学 token"分离（AudioLM、Mimi）。为什么它能让 TTS 更清晰、并且支持 zero-shot 声音克隆？

**Q14.**（场景设计）你要做一个基于自回归 LM 的英文 TTS，要求首包延迟（TTFA）约 200 ms。EnCodec、DAC、SNAC、Mimi 中你选哪个？请给出帧率、码本数、序列长度的估算，以及 LM 如何消费多码本 token。

**Q15.**（追问型）码本是不是越多越好？各级码本重要性一样吗？你会如何决定码本数量？

**Q16.**（工程实践）如何评估一个 codec 是否适合作为生成模型的 tokenizer？只看 PESQ / ViSQOL 够不够？

---

## 五、参考答案与解析

### Q1 — 答案：B

RVQ 是"逐级逼近"：第 1 级量化编码器输出 `z`，得到残差 `r₁ = z − q₁`；第 2 级量化 `r₁`，得到 `r₂ = r₁ − q₂`……解码时 `ẑ = q₁ + q₂ + … + q_N`。代码里 `rvq_encode` 每一轮都用上一轮 `quantize_with_codebook` 返回的 `residuals` 去学下一个码本，正是这个过程。A 只对第 1 级成立；C 是端到端重建误差，不是 RVQ 的量化对象；D 把"索引"和"值"混淆了。

### Q2 — 答案：C

每个码本 1024 个码字 = 10 bit；每帧每个码本 10 bit，75 帧/秒 → 每个码本 750 bps。6000 / 750 = 8 个码本，和讲义 Step 1 中 "`n_codebooks=8` at 6 kbps" 一致。32 是 EnCodec-24k 的最大码本数（对应 24 kbps）。

### Q3 — 答案：B

token 数 = 时长 × 帧率 × 码本数 = 10 × 12.5 × 8 = 1000。A 只算了帧数（125 帧）没乘码本数；C 是 DAC（86 Hz × 8 码本 × 10 s）的结果；D 是 EnCodec 75 Hz × 10 码本的结果。

### Q4 — 答案：B

Mimi 的关键设计就是"码本 0 = 语义"：训练时加一个辅助预测损失，让码本 0 去对齐 WavLM 的语音内容特征；码本 1–7 是声学残差（音色、说话人、韵律、噪声、细节）。A、D 都是编的；C 恰好相反——噪声属于声学码本。

### Q5 — 答案：B

重建型 codec（EnCodec、DAC）只优化"还原得像"，每个码本都同时混着内容和音色。LM 要在同一个码本里同时学会"语言结构"和"声学结构"，难以扩展，生成结果就容易糊。语义/声学分离把这两件事拆给不同码本（乃至不同模型），这正是 Moshi、Sesame CSM 能工作的原因。A 不对：码率高低与"能否学会语言结构"不是一回事。

### Q6 — 答案：B

SNAC 的特点是**多尺度** RVQ：粗码本约 12 Hz 画草图、细码本约 50 Hz 补细节，层级结构很适合 LM 生成，因此被 Orpheus-3B 采用。A 与 RVQ 思想相反；C 描述的是 Mimi；D 描述的是 DAC。

### Q7 — 答案：B

表中 Opus 用的是 20 kbps，比神经 codec 的 3–6 kbps 高得多，而且讲义明确说"传统 codec 每比特感知质量仍然胜出"。神经 codec 的优势不在压缩，而在**离散 token**（Opus 不产出可供 LM 预测的 token）和**生成模型能利用这些 token 做什么**。所以讲义的经验法则是：做生成模型选 Mimi/SNAC，做压缩管线用 Opus。

### Q8 — 答案：B

帧率决定了"一个 token 对应多少毫秒的音频"以及相邻 token 之间的统计关系。12.5 Hz 每帧 80 ms，50 Hz 每帧 20 ms，LM 学到的时间尺度完全对不上。loss 可能照常下降（模型在学新分布），但先前学到的知识大多作废，而且没有报错——讲义称之为"静默失败"。

### Q9 — 参考答案

(a) `3` 是 `log2(codebook_size) = log2(8) = 3`，即每个码本索引需要 3 bit；`50` 是假设的帧率 50 fps（演示用，并不是 toy 信号真实的采样率）。所以 `bitrate = 码本数 × 每码本比特数 × 帧率`。

(b) `bits_per_frame` 和 `bitrate` 两列会错：码本大小改成 1024 后应为 10 bit/码本，但代码仍按 3 bit 算。改写：

```python
import math

CODEBOOK_SIZE = 8
FPS = 50

for n_cb in [1, 2, 4, 8, 12]:
    indices, codebooks = rvq_encode(sig, codebook_size=CODEBOOK_SIZE, n_codebooks=n_cb)
    recon = rvq_decode(indices, codebooks, length=len(sig))
    err = mse(sig, recon)
    bits_per_frame = n_cb * math.ceil(math.log2(CODEBOOK_SIZE))
    bitrate = bits_per_frame * FPS
```

用 `math.ceil` 是因为码本大小不是 2 的幂时，索引仍需向上取整的比特数（不做熵编码的前提下）。

(c) `log2(2048) = 11`，码率 = 12.5 × 8 × 11 = 1100 bps ≈ 1.1 kbps。（顺带一提：讲义写的是 "8 codebooks @ 4.4 kbps"，按这个公式要到 4.4 kbps 需要每个码本 44 bit，与 8 个码本、12.5 Hz 的设定对不上；Moshi 论文给出的 Mimi 码率是 1.1 kbps。做题时以公式为准。）

### Q10 — 参考答案

实测（种子固定，可复现）：

```text
去掉第 0 级：MSE ≈ 0.586
去掉第 3 级：MSE ≈ 2.55e-05
```

- 去掉第 0 级时，剩下 1–3 级码本的码字都很小（第 1 级码字大致在 ±0.4 内），它们只是"修补残差"，根本拼不出原信号的主体。MSE ≈ 0.586，几乎等于信号本身的方差（约 0.60）——相当于什么都没还原。
- 去掉最后一级时，MSE 恰好等于"只用前 3 级"的误差 2.55e-5，损失微乎其微。
- 联系：RVQ 中**越靠前的码本承载越多能量/信息**，后面的码本只是精修。Mimi 更进一步，把码本 0 显式训练成语义码本，所以码本 0 被破坏 → 可懂度崩溃；码本 7 被破坏 → 几乎听不出来。这正是讲义"Hard"练习要你在真实 Mimi 上验证的结论；它也说明"所有码本同等重要"是错觉。

### Q11 — 参考答案

实测：一个 64 码字码本 MSE ≈ **3.30e-4**；2 × 8 RVQ MSE ≈ **5.21e-4**。同样 6 bit，**单个大码本更好**。

原因：RVQ 能表示的 64 个"组合点"受结构约束（必须是 `c₁[i] + c₂[j]` 形式），而单码本可以把 64 个点放在任意位置，理论上不会更差。

那为什么还用 RVQ？因为大码本的规模随比特数**指数**增长：

| 方案 | 每帧比特 | 需要存储/搜索的码字数 |
|------|---------|--------------------|
| 单码本 | 80 bit | `2^80 ≈ 1.2 × 10^24` 个（不可能训练、存储、做最近邻） |
| RVQ 8 × 1024 | 80 bit | `8 × 1024 = 8192` 个 |

RVQ 用"可加的级联结构"换来了**线性**的存储与计算，同时还能按需截断码本（码率可伸缩），并天然形成"粗 → 细"的层级，这对 LM 建模也很友好。牺牲的只是同比特下一点点量化精度。

### Q12 — 参考回答要点

- 定义：残差向量量化，用 N 个小码本级联；每级对上一级的残差做最近邻量化，输出一个索引；解码时把各级码字相加。
- 为什么不用大码本：要达到好音质需要极大的有效词表，单码本规模指数爆炸（`1024^8 ≈ 10^24`），无法训练和检索；RVQ 只需 `N × K` 个码字。
- 附带好处：①码率可伸缩——少用几级就是低码率版本（EnCodec 用同一模型支持 1.5–24 kbps 的不同带宽）；②粗到细的层级，前几级决定大局，后几级补细节；③每级码本小，训练更稳定。
- 加分点：能提到 SoundStream 是最早的可流式 RVQ codec；DAC 对码本做 L2 归一化来改善码本利用率；能说出 RVQ 训练中常见的"码本坍塌（dead codes）"问题——代码中 `learn_codebook` 遇到空桶时只是保留原中心，就是这个问题的最小化版本。
- 常见误区：说"码本越多音质线性变好"——实测误差是按级数**近似指数**下降、收益递减，而序列长度却线性增长。

### Q13 — 参考回答要点

- 定义：语义 token 编码"说了什么"（音素、词、内容）；声学 token 编码"怎么说、谁说的"（音色、说话人、韵律、噪声、细节）。
- 来源：AudioLM 首先提出两阶段范式；Mimi 把它做进一个 codec——码本 0 通过辅助损失向 WavLM 特征蒸馏，码本 1–7 是声学残差。
- 为什么 TTS 更清晰：文本 → 语义 token 是一个"词表小、结构接近语言"的映射，LM 很容易学；不用在同一个码本里同时啃语言和声学两块硬骨头。
- 为什么能 zero-shot 克隆：语义模型只管内容，声学模型条件于语义 token + **说话人参考音频**生成声学 token，换一段参考音频就换一个音色，无需针对该说话人再训练。
- 加分点：说出这是 Moshi、Sesame CSM 的基础；Mimi 帧率只有 12.5 Hz，10 秒仅 125 帧，适合流式全双工（见第 15 节）。
- 常见误区：把"语义 token"理解成文本 token——它仍是从音频中学到的离散单元，只是与语言内容高度对齐。

### Q14 — 参考回答要点

- 选择：**Mimi**（或 SNAC）。理由：帧率低、序列短；语义 + 声学分离便于"文本 → 码本 0 → 码本 1–7"的分解，还支持克隆。
- 估算：12.5 Hz × 8 码本；10 秒 = 125 帧 = 1000 token。对比 DAC：86 Hz × 8 × 10 = 6880 token，是 Mimi 的近 7 倍，对低延迟 AR 生成不划算。
- LM 如何消费多码本：①**先语义后声学**——先由文本 + 说话人参考预测码本 0，再条件于码本 0 预测码本 1–7；②时间维用大 Transformer，每帧内的多个码本用一个小的 depth transformer 逐个预测（讲义配套 skill 中提到的 depth-transformer 模式），这样时间维序列长度只有 125。
- 解码：直接用 Mimi 自带的解码器，不需要外部 vocoder；训练时冻结 Mimi，只训练 text-to-codec LM。
- 加分点：能把首包延迟拆成"文本编码 + 生成首若干帧 + codec 解码首帧"，并指出低帧率意味着生成第一帧要等的 token 更少；音乐场景不要用 Mimi（它是为语音调的）。

### Q15 — 参考回答要点

- 不是越多越好：保真度随码本数提升但**收益递减**（本节代码里误差每加一级大约缩小一个多数量级，到 8 级以后已经看不出差别），而 LM 序列长度/计算量随码本数**线性**增长。讲义建议停在 8–12 个。
- 重要性不同：RVQ 前几级承载主体能量，后几级只是细节；在 Mimi 中码本 0 还额外承载语义内容，丢了就听不懂，丢了码本 7 几乎无感。
- 如何决定：①画"码本数 vs 指标（PESQ / ViSQOL / 下游 WER）"曲线找拐点；②结合延迟预算反推每秒能生成多少 token；③生成任务关注下游 TTS 的可懂度和说话人相似度，而不仅是重建。
- 加分点：训练时可以对码本数做随机截断（让模型适应不同码率），推理按需选择。
- 常见误区：认为"码本 7 的预测错误和码本 0 的预测错误代价相同"，于是在 LM loss 上对所有码本等权——实践中常对前面的码本更重视。

### Q16 — 参考回答要点

- 只看重建不够：讲义明确列出"只用重建质量做指标"是坑——重建很好但语义结构差的 codec，对 LM 生成可能毫无用处。
- 评估维度：
  1. 重建：PESQ、ViSQOL、MSE、主观 MOS；
  2. 效率：帧率、码本数、码率、每 10 秒的 token 数、编解码延迟、是否可流式；
  3. 可建模性：在 token 上训练一个小 LM，看生成语音的可懂度（用 ASR 算 WER）、说话人相似度、自然度；
  4. 语义对齐：对码本 0 做消融（随机替换）看可懂度是否崩塌——这正是讲义 Hard 练习的做法；
  5. 领域匹配：语音 codec 不要用于音乐（skill 中明确拒绝用 Mimi 做音乐）。
- 加分点：强调"重建指标衡量的是 codec，生成指标衡量的是 codec + LM 这个系统"，两者都要看；音频评估指标的完整版图见第 17 节。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 01 音频基础知识](../../01-audio-fundamentals/docs/zh.md)：采样率、波形，理解"24 kHz / 44.1 kHz""帧率"的前提。
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：讲义列出的前置课，理解"编码器输出的帧"。
- [阶段 10 · 11 量化](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：把连续值映射到有限集合的基本思想。
- [阶段 05 · 19 子词分词](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：codec 就是"音频的 tokenizer"，词表大小与序列长度的权衡是同一回事。
- [阶段 02 · 07 无监督学习](../../../02-ml-fundamentals/07-unsupervised-learning/docs/zh.md)：k-means——本节代码学码本用的就是一维 k-means。

### 本节被哪些后续内容用到
- [阶段 06 · 07 文本转语音](../../07-text-to-speech/docs/zh.md)：基于 codec token 的现代 TTS。
- [阶段 06 · 08 语音克隆和语音转换](../../08-voice-cloning-conversion/docs/zh.md)：语义/声学分离让 zero-shot 克隆成为可能。
- [阶段 06 · 09 音乐生成](../../09-music-generation/docs/zh.md)：MusicGen 建立在 EnCodec token 之上。
- [阶段 06 · 15 Streaming 语音到语音](../../15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：Moshi 用 Mimi 12.5 Hz token 做全双工对话。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：PESQ、ViSQOL、MOS 等指标的系统介绍。
- [阶段 08 · 11 音频生成](../../../08-generative-ai/11-audio-generation/docs/zh.md)：生成模型视角下的音频 token。
- [阶段 12 · 20 Omni 模型 Thinker-Talker](../../../12-multimodal-ai/20-omni-models-thinker-talker/docs/zh.md)：多模态大模型如何输出语音 token。

### 延伸关键词
`SoundStream` · `AudioLM` · `SpeechTokenizer` · `VQ-VAE` · `码本坍塌 / dead codes` · `commitment loss` · `delay pattern（MusicGen）` · `depth transformer / RQ-Transformer` · `WavLM 蒸馏` · `Sesame CSM` · `Orpheus`
