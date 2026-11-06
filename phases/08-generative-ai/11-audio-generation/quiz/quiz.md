# 测验 · 音频生成（Audio Generation）

> **阶段 08 · 生成式 AI · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 原始波形太长 | 音频采样率 16–48 kHz，5 秒就是 8 万到 24 万个采样点，没有 transformer 能直接对这么长的序列做注意力 |
| 2 | 神经音频编解码器（codec） | Encodec、SoundStream、DAC：卷积编码器把波形压成每个时间步一个向量，经 RVQ 变成离散 token（约 50–75 Hz），解码器还原波形 |
| 3 | 残差向量量化（RVQ） | K 个码本级联，每一级量化上一级留下的残差，由粗到细；第 1 级的误差会向后传递 |
| 4 | 码率与 token 率 | token/秒 = 帧率 × 码本数；码率 = 帧率 × 码本数 × log₂(码本大小)。例：75 Hz × 8 = 600 token/s |
| 5 | Token 自回归范式 | 把 codec token 当"词"，用 decoder-only transformer 做 next-token 预测；MusicGen 用 delayed parallel 并行输出 K 路码本流，VALL-E 用 3 秒语音作为提示 |
| 6 | 潜空间扩散 / flow matching 范式 | 在连续音频潜变量上做扩散或 flow matching（如 Stable Audio 2.5），或走"文本 → mel → 音频"（AudioLDM 2） |
| 7 | 趋势与选型 | 音乐越来越多用 flow matching（推理快、样本干净）；语音仍以 token-AR 为主（天然因果、便于流式） |
| 8 | 流式是硬约束 | 用户边生成边听，TPOT 必须跟上播放速度；flow matching 一次渲染固定时长，要流式只能分块重叠，额外增加 100–300 ms |
| 9 | 质量上限与伦理 | codec 的保真度决定质量上限；长结构难建模；版权数据与声音克隆需要授权、滥用检测与水印 |

### 核心技能（能动手做到）

- [ ] 给定采样率、下采样倍数、码本数、码本大小，算出帧率、token/秒和码率，并能发现文档里的数字矛盾
- [ ] 运行 `code/main.py`，从 `make_tokens` 推导出各风格的合法转移和理论条件分布，并解释实际输出中的概率、熵和"跳变"
- [ ] 能解释温度 `p^(1/T)` 对分布和"非法转移"概率的影响
- [ ] 能手写 delayed parallel 的排布函数及其逆变换，并说出它把序列长度从 `K·T` 降到多少
- [ ] 能说明 bigram 模型为什么无法利用"3 秒语音提示"，真实 VALL-E 是怎么做的
- [ ] 能根据"实时语音对话 / 提交后渲染 30 秒配乐 / 带歌词的歌曲 / 音效"选出合适的技术路线

---

## 二、基础自测（选择题）

**Q1.** 所有生产级音频生成模型都先用神经 codec 把音频变成 token，最主要的原因是：

- A. 原始波形无法存储在 GPU 上
- B. 原始波形的序列太长（5 秒就有 8 万到 24 万个采样点），压缩到每秒几十帧的 token 后，transformer 或扩散模型才能处理
- C. transformer 只能处理整数输入
- D. 为了去除背景噪声

**Q2.** 关于残差向量量化（RVQ），下列说法正确的是：

- A. K 个码本彼此独立，各自量化原始向量的一部分维度
- B. 第 k 级码本量化的是前 k−1 级量化之后剩下的残差，越往后越精细
- C. 只有最后一级码本的输出会送给解码器
- D. 码本数越多，每秒的 token 数越少

**Q3.** 某 codec 在 24 kHz 音频上以 75 Hz 输出帧，每帧用 8 个 RVQ 码本，每个码本 1024 个条目。它每秒输出的 token 数和码率分别是：

- A. 75 token/s，0.75 kbps
- B. 600 token/s，2 kbps
- C. 600 token/s，6 kbps
- D. 8 token/s，6 kbps

**Q4.** MusicGen 的 "delayed parallel" 解码模式的作用是：

- A. 每个码本单独训练一个模型
- B. 把 K 路码本流错开偏移后，每个自回归步同时输出 K 个 token，序列长度从约 `K·T` 降到约 `T + K − 1`
- C. 先生成全部第 1 级 token，再生成第 2 级 token
- D. 延迟输出以等待用户输入

**Q5.** 要做一个"实时语音对话"产品，按讲义的建议，生成器应该优先选：

- A. 一次渲染固定时长片段的 flow matching 模型
- B. 天然因果、可以边生成边播放的 codec token 自回归模型
- C. 频谱图扩散模型（如 Riffusion）
- D. 先离线生成整段音频再播放

**Q6.** 在 `main.py` 的 `generate` 中，把 `temperature` 从 1.0 降到 0.7 会导致：

- A. 分布更平坦，随机性更高
- B. 高概率的 token 更突出、低概率的被压低，熵降低，罕见跳变更少
- C. 不影响分布，只影响速度
- D. 所有概率变成 0 或 1

**Q7.** 你换了一个参数量大 10 倍的生成器，但输出的高频细节仍然发闷、失真。讲义 Pitfalls 中最可能的原因是：

- A. 训练步数不够
- B. codec 本身无法忠实表示这类声音，codec 的质量决定了上限
- C. 温度设得太低
- D. 没有使用 CFG

**Q8.** 关于声音克隆，下列做法**不符合**讲义和配套 skill 要求的是：

- A. 克隆前核实声音所有者的授权
- B. 生产系统部署滥用检测和 opt-out 名单
- C. 给生成音频加水印
- D. 用户上传了 3 秒样本，就视为已获得授权

---

## 三、动手 / 代码题

**Q9.** 阅读数据生成函数：

```python
VOCAB = 16

def make_tokens(style, length, rng):
    """Synthetic 'audio token' sequences by style."""
    if style == 0:  # alternating, speech-like
        return [(i + rng.randint(0, 1)) % VOCAB for i in range(length)]
    return [(i * 3 + rng.randint(0, 1)) % VOCAB for i in range(length)]
```

(a) 对 style 0，相邻 token 之差 `next − prev (mod 16)` 可能取哪些值？各自的概率是多少？注释里的 "alternating" 准确吗？
(b) 写出理论上的 `p(next | style=0, prev=5)` 及其熵（单位：nats）。
(c) 实际运行输出 `top-3: [(6, 0.482), (7, 0.25), (5, 0.242)]`、`H = 1.201`，为什么与理论值不完全一样？

**Q10.** 实际运行中出现了几处"不合法"的跳变，比如 style 1 在 `temp 1.0` 时出现 `6, 13`，prompt continuation 中出现 `15, 12`。

(a) 这些跳变从何而来？
(b) 已知 style 0、`prev = 5` 这一行的计数总和是 508。计算温度为 1.0 时"非法转移"（落在 {5, 6, 7} 之外）的总概率，并估算长度 20 的序列（19 次转移）中至少出现一次非法跳变的概率。
(c) 温度降到 0.7 时，这个非法概率大约变成多少？对真实音频生成有什么启示？

**Q11.**（讲义练习 2 的前半部分）实现 MusicGen 式的 delay pattern：

```python
PAD = -1

def delay_pattern(codes):
    """codes[k][t]：K 个码本流，每个长度 T。返回 T+K-1 个时间步，每步一列 K 个 token。"""
    ...

def undelay(steps, K):
    ...
```

用 `codes = [[10,11,12,13],[20,21,22,23],[30,31,32,33]]` 测试，写出排布结果，并说明：为什么第 k 路码本要右移 k 步？与把 `K·T` 个 token 直接展平相比，自回归步数是多少？

---

## 四、面试高频题

**Q12.**（基础必考）讲讲神经音频 codec（Encodec / SoundStream / DAC）和 RVQ 的原理。为什么说它是现代音频生成的"地基"？

**Q13.**（原理深挖）对比 token 自回归（MusicGen、VALL-E）与潜空间扩散 / flow matching（Stable Audio）两条路线：建模方式、延迟、流式能力、质量，各适合什么场景？

**Q14.**（工程实践）你要做一个实时语音助手的 TTS 部分，目标是首包延迟低于 300 ms、播放不卡顿。请说明吞吐要求怎么算、架构怎么选，以及有哪些优化手段。

**Q15.**（追问型）`main.py` 里的"VALL-E 式提示续写"真的能让续写保持提示里的"音色"吗？真实的 VALL-E 是怎样利用 3 秒语音提示的？

**Q16.**（场景设计）给一款短视频 App 设计"一键生成 30 秒背景音乐"功能：说出模型选型、提示词格式、长结构的处理、评估指标和合规要求。

**Q17.**（原理深挖）RVQ 的"误差累积"是什么意思？为什么讲义建议在高层码本上使用温度 0（贪心）采样？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义开篇："A five-second clip is 80-240k samples. No transformer attends to that sequence directly." codec 把序列压到 50–75 Hz，5 秒只剩几百帧。A 错：存储不是问题，序列长度导致的注意力开销才是；C 错：transformer 处理的是 embedding；D 不是 codec 的目的。

### Q2 — 答案：B

RVQ 是级联的：第 1 级量化原始向量，第 2 级量化"原始向量 − 第 1 级结果"的残差，依此类推。解码时把各级码字**相加**（C 错）。码本越多，每帧的 token 越多，每秒 token 数是 `帧率 × K`，会更多（D 错）。

### Q3 — 答案：C

- token/秒 = `75 × 8 = 600`；
- 每个 token 占 `log₂(1024) = 10` bit，码率 = `600 × 10 = 6000 bit/s = 6 kbps`。

注意：讲义原文写的是 "24 kHz audio at 2 kbps using 8 RVQ codebooks at 75 Hz = 600 tokens/sec"，其中 600 token/s 正确，但 1024 条目码本、8 个码本对应的是 6 kbps；2 kbps 左右只对应 2–3 个码本（Encodec 24 kHz 的 1.5 kbps 档就是 2 个码本）。面试中能把这三个量互相换算，是基本功。

### Q4 — 答案：B

把第 k 路码本整体右移 k 步后，每个自回归步输出一"列" K 个 token，总步数约 `T + K − 1`，而不是展平后的 `K·T`。偏移保证生成第 t 帧的第 k 级 token 时，第 t 帧的前 k−1 级已经生成过（Q11）。C 描述的是"分层逐级生成"的另一种做法（VALL-E 式的先 AR 生成第 1 级、再 NAR 生成其余各级），不是 delay pattern。

### Q5 — 答案：B

讲义 Production note：实时语音对话或实时音乐续写选 codec AR 路线；"提交后渲染 30 秒片段"才选 flow matching，后者在质量和总延迟上占优。flow matching 一次渲染固定长度，流式需要分块重叠，会额外增加 100–300 ms。

### Q6 — 答案：B

`p^(1/T)` 再归一化，等价于 `softmax(logits / T)`。T < 1 时放大高概率与低概率之间的差距，分布更尖、熵更低。实测 style 0、prev=5 这一行：T=1 时熵约 1.20，T=0.7 时约 1.01（Q10）。D 是 T → 0 的极限（贪心）。

### Q7 — 答案：B

讲义 Pitfalls 第一条："Codec quality caps output quality."生成器生成的是 codec token，最终波形由 codec 解码器重建；codec 表示不了的细节，生成器再强也无法弥补。讲义认为 DAC 是当前最好的开源 codec。

### Q8 — 答案：D

配套 skill 文件的原话是："Refuse to clone any voice without verified consent from the owner ('3-second prompt' is not consent)"。A、B、C 都是要求：讲义 Pitfalls 要求滥用检测 + opt-out 名单，skill 文件要求授权、水印（PerTh / SynthID-audio）。

### Q9 — 参考答案

(a) 第 i 个 token 是 `(i + bᵢ) mod 16`，`bᵢ ∈ {0, 1}` 等概率且相互独立。相邻差为 `1 + bᵢ₊₁ − bᵢ`：

| 差值 | 条件 | 概率 |
|------|------|------|
| 0 | `bᵢ = 1, bᵢ₊₁ = 0` | 1/4 |
| 1 | `bᵢ = bᵢ₊₁` | 1/2 |
| 2 | `bᵢ = 0, bᵢ₊₁ = 1` | 1/4 |

所以 style 0 是一条**每步约 +1 的带抖动上升斜坡**，并不是"高低交替"。注释、`main` 中的标签 "speech-like (alternating)" 以及讲义 Build It 的描述都与实际不符。style 1 同理，差值为 `3 + bᵢ₊₁ − bᵢ ∈ {2, 3, 4}`，概率同样是 1/4、1/2、1/4，是步长约为 3 的斜坡。

(b) 理论分布：`p(5) = 0.25, p(6) = 0.5, p(7) = 0.25`，其余为 0。熵：

```text
H = −(0.25·ln0.25 + 0.5·ln0.5 + 0.25·ln0.25) ≈ 1.040 nats
```

(c) 两个原因：
- **加一平滑**：`init_counts` 把所有计数初始化为 1.0，13 个不可能的转移各有 1 个"伪计数"，这一行的总计数为 508，非法转移共占 `13/508 ≈ 2.6%` 的概率。这部分概率分散在 13 个 token 上，抬高了熵（1.040 → 1.201）。
- **有限样本**：真实计数只有约 492 次，比例在 1:2:1 附近随机波动。实测 0.482 / 0.25 / 0.242 与理论值 0.5 / 0.25 / 0.25 乘以 `(1 − 0.026)` 基本吻合。

### Q10 — 参考答案

(a) 来自**加一平滑**：训练数据里从未出现过的转移也有非零概率。`6 → 13`（+7）在 style 1 中不可能出现（合法差值只有 2、3、4）；`15 → 12`（−3）在 style 0 中也不可能出现。这些就是"平滑带来的毛刺"，类比到真实音频，就是一声突兀的爆音或咔哒声。

(b) 非法总概率 `≈ 13 / 508 ≈ 0.0256`。19 次转移中至少出现一次非法跳变的概率：

```text
1 − (1 − 0.0256)^19 ≈ 0.389
```

也就是说，约 **39%** 的序列会出现至少一次毛刺（这里粗略假设每一行的非法概率都相近）。

(c) 对这一行做 `p^(1/0.7)` 再归一化，实测非法概率降到约 **0.0028**（降低约 9 倍），熵从 1.201 降到 1.008；温度 0.5 时只剩约 0.00014。

启示：低温度 / top-k / top-p 截断能有效去掉"长尾里的垃圾 token"，代价是多样性下降。真实音频生成常对不同层采用不同策略，例如讲义 Pitfalls 建议在高层 RVQ 码本上用温度 0（见 Q17）。

### Q11 — 参考答案

```python
PAD = -1

def delay_pattern(codes):
    K, T = len(codes), len(codes[0])
    steps = []
    for s in range(T + K - 1):
        col = []
        for k in range(K):
            t = s - k                      # 第 k 路码本右移 k 步
            col.append(codes[k][t] if 0 <= t < T else PAD)
        steps.append(col)
    return steps

def undelay(steps, K):
    T = len(steps) - K + 1
    return [[steps[t + k][k] for t in range(T)] for k in range(K)]

codes = [[10, 11, 12, 13],
         [20, 21, 22, 23],
         [30, 31, 32, 33]]
steps = delay_pattern(codes)
for s, col in enumerate(steps):
    print(s, col)
assert undelay(steps, 3) == codes
```

输出（已实际运行验证）：

```text
0 [10, -1, -1]
1 [11, 20, -1]
2 [12, 21, 30]
3 [13, 22, 31]
4 [-1, 23, 32]
5 [-1, -1, 33]
```

- **为什么右移 k 步**：RVQ 的第 k 级依赖前面各级（它量化的是前面留下的残差）。错开之后，在第 s 步生成帧 `t = s − k` 的第 k 级 token 时，同一帧的第 0…k−1 级 token 已经在之前的步骤中生成了，模型可以以它们为条件。
- **步数**：展平需要 `K·T = 12` 步；delay pattern 只要 `T + K − 1 = 6` 步，每步并行输出 K 个 token（用 K 个输出头）。T 很大时，步数几乎从 `K·T` 降到 `T`，大约快 K 倍。
- **代价**：同一步内的 K 个 token 被视为条件独立，同一帧各级之间的依赖只能"跨步"获得，是近似。

### Q12 — 参考回答要点

- **结构**：卷积编码器（带步长下采样）把波形压成低帧率的连续向量序列 → RVQ 把每个向量变成 K 个码本索引 → 解码器把码字之和还原成波形。训练损失通常包括重建损失、频谱损失、对抗损失（判别器）以及码本/commitment 损失。
- **RVQ 的好处**：码率可变（用前几级码本就是低码率版本）、由粗到细；单个码本大小 1024–2048 就能达到很高的保真度。
- **为什么是地基**：
  - 把"音频生成"变成"离散序列建模"，可以直接复用 LLM 的整套技术（decoder-only transformer、采样、KV-cache、流式）；
  - 连续潜变量版本又能直接用于扩散 / flow matching；
  - 讲义："All three run on the same substrate: neural audio codec + token-AR or diffusion generator."
- **数字感**：Encodec 24 kHz 版本 75 Hz × 8 码本 = 600 token/s；MusicGen 用 32 kHz 版 Encodec。
- **常见误区**：以为 codec 只是"压缩格式"，忽略了它决定了质量上限（讲义 Pitfalls）。

### Q13 — 参考回答要点

| 维度 | Token 自回归 | 潜空间扩散 / flow matching |
|------|-------------|--------------------------|
| 建模对象 | 离散 codec token，next-token 交叉熵 | 连续音频潜变量（或 mel），去噪/速度场回归 |
| 代表 | MusicGen（delayed parallel）、VALL-E、ElevenLabs 类 TTS | Stable Audio 2.5、AudioLDM 2 |
| 流式 | 天然因果，边生成边播 | 一次生成固定时长，流式需分块重叠，额外 100–300 ms |
| 长度 | 可以无限续写，但长结构难（30 秒在 75 Hz 下是 2 万多 token） | 片段长度固定，长曲子靠拼接 + 交叉淡化 |
| 质量 / 速度 | 序列越长越慢；容易有采样毛刺 | 讲义：音乐上 flow matching 推理更快、样本更干净 |
| 适合 | 语音、实时对话、实时续写 | 提交后渲染的音乐、音效 |

- 讲义总结："flow matching is winning for music while token-AR still dominates speech because it is naturally causal and streams well."
- **加分点**：混合架构，例如先用 AR 生成语义/粗粒度 token，再用扩散/flow 细化。

### Q14 — 参考回答要点

- **吞吐要求**：用户的"听的速度"就是目标吞吐。讲义的例子是以约 75 Hz 的 token 帧率计算，服务端对每个用户每秒至少要生成 75 帧才能保证播放流畅。注意：如果每帧有 K 个码本，展平时就是 `75·K` token/s；用 delay pattern 时每步输出一帧（K 个 token），才是"每秒 75 步"。TPOT（每个输出 token 的时间）比吞吐总量更关键。
- **架构**：codec token 自回归 + 流式解码器（codec 解码器也要能逐块解码）。配套 skill 甚至规定：低于 200 ms 的实时目标必须使用流式 token-AR 模型，扩散类音频在 2026 年达不到 300 ms 以内的首字节时间。
- **首包延迟**：文本前端（分词/音素化）+ 首批 token 的生成（类似 LLM 的 prefill）+ 首块 codec 解码 + 网络传输。可以先生成很短的首块尽快播放。
- **优化**：KV-cache、量化、投机解码、减少码本数（低码率档）、把模型部署在离用户近的地方；讲义的生产对照：ElevenLabs V3 首 token 约 300 ms，GPT-4o audio 约 200 ms。
- **加分点**：与第 06 阶段的流式语音到语音（Moshi 等）联系，说明全双工对话还需要处理插话和轮次检测。

### Q15 — 参考回答要点

- **不能**。`main.py` 中的模型是 bigram（一阶马尔可夫），下一个 token 只依赖**最后一个** token。提示 `[0, 2, 2, 3, 5]` 中，只有最后的 `5` 影响续写；把前四个 token 换成任何值，续写的分布完全一样。所谓"音色"（说话人的特征）根本没有被利用。
- **真实 VALL-E**：
  - 把 3 秒提示语音用 codec 编码成多级 token，作为**前缀**放进 transformer 的上下文；把目标文本（音素）也放进上下文；
  - 用自回归模型生成第 1 级码本 token，再用非自回归模型并行生成其余各级；
  - transformer 的长上下文注意力能从提示中提取说话人的音色、语速、录音环境，延续到新内容上——本质上是 in-context learning。
- **启示**：要让提示起作用，模型的上下文必须覆盖提示（n-gram 至少要覆盖足够长的历史，更现实的是用 transformer），或者显式输入说话人 embedding（讲义 Key Terms："Speaker embedding or token prefix"）。
- **合规**：3 秒样本就能克隆声音，必须有授权验证与滥用检测。

### Q16 — 参考回答要点

- **选型**：快速出背景音乐选 Stable Audio 2.5 API、Suno 或 Udio（讲义 Use It）；需要歌词选 Suno v4 / Udio v1.5；要可控、可自托管，可以考虑 MusicGen 或 Stable Audio Open。"提交后渲染"属于离线场景，flow matching 在质量和总延迟上占优（Stable Audio 2.5 约 10 秒生成 1 分钟）。
- **提示词**（skill 文件）：流派 + 乐器 + 情绪 + BPM + 结构标记（intro / verse / chorus）。
- **长结构**：30 秒在 75 Hz 下是 2 万多 token，对 AR 模型很难；讲义提到 MusicGen 用滑动窗口 + 提示续写，Stable Audio 用较短片段 + 交叉淡化，拼接处要做 overlap-add，避免边界伪影。
- **评估**：CLAP score（文本与音频的匹配度）、用户 A/B 听测；固定 seed、锁定版本、记录提示词 hash 以便复现。
- **合规**：训练数据必须获得授权（讲义提到 2024 年 RIAA 对 Suno / Udio 的诉讼）；对输出做版权扫描；不要使用未授权的参考素材。

### Q17 — 参考回答要点

- **误差累积**：第 k 级码本建模的是前面各级留下的残差。如果第 1 级（最粗、能量最大）采样出一个"不太对"的 token，后面各级是在一个错误的基础上补残差，误差无法被纠正，还会叠加更多偏差；自回归时，错误的 token 还会进入后续时间步的上下文，继续传递。
- **为什么高层用温度 0**：高层码本表示的是细节（小残差），本身"应该是什么"比较确定；在这里引入随机性只会增加噪声和毛刺，不会带来有意义的多样性。多样性主要由第 1 级（粗结构，如旋律、音素）提供。所以常见做法是：低层正常采样，高层贪心或低温采样。
- **加分点**：联系 Q10 的实验——平滑 + 高温度会制造毛刺，降温能显著降低非法跳变的概率。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图与 Mel 特征](../../../06-speech-and-audio/02-spectrograms-mel-features/docs/zh.md)：采样率、mel 频谱，是 AudioLDM 和声码器的基础。
- [阶段 06 · 04 语音识别 ASR](../../../06-speech-and-audio/04-speech-recognition-asr/docs/zh.md)：语音的帧率与序列建模。
- [阶段 08 · 06 从头开始的 DDPM](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：扩散路线的基础。
- [阶段 05 · 16 Transformer 之前的文本生成](../../../05-nlp-foundations-to-advanced/16-text-generation-pre-transformer/docs/zh.md)：n-gram / bigram 语言模型、平滑与温度采样，正是本节代码的方法。

### 相关小节
- [阶段 06 · 13 神经音频编解码器](../../../06-speech-and-audio/13-neural-audio-codecs/docs/zh.md)：Encodec / SoundStream / DAC 与 RVQ 的深入讲解。
- [阶段 06 · 07 文本转语音](../../../06-speech-and-audio/07-text-to-speech/docs/zh.md)、[阶段 06 · 08 声音克隆与转换](../../../06-speech-and-audio/08-voice-cloning-conversion/docs/zh.md)、[阶段 06 · 09 音乐生成](../../../06-speech-and-audio/09-music-generation/docs/zh.md)：三大任务的专题。
- [阶段 06 · 15 流式语音到语音（Moshi / Hibiki）](../../../06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：实时对话的流式架构。
- [阶段 06 · 16 反欺骗与音频水印](../../../06-speech-and-audio/16-anti-spoofing-audio-watermarking/docs/zh.md)、[阶段 06 · 17 音频评估指标](../../../06-speech-and-audio/17-audio-evaluation-metrics/docs/zh.md)：合规与评估。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)：Stable Audio 等音乐模型的训练目标。
- [阶段 07 · 07 GPT 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：token-AR 路线的 decoder-only transformer。

### 延伸关键词
`Encodec / SoundStream / DAC` · `RVQ` · `codebook bitrate` · `delay pattern` · `VALL-E (AR + NAR)` · `MusicGen` · `Stable Audio` · `CLAP score` · `MOS / CER` · `TPOT / TTFB` · `audio watermark (SynthID / PerTh)`
