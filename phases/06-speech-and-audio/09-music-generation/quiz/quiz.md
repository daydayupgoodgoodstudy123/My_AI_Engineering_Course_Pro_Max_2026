# 测验 · 音乐生成——MusicGen、Stable Audio、Suno 与许可制度的剧变（Music Generation — MusicGen, Stable Audio, Suno, and the Licensing Earthquake）

> **阶段 06 · 语音与音频 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个子问题 | 纯器乐生成（MusicGen、Stable Audio、AudioLDM）；带人声和歌词的整首歌（Suno、Udio、YuE、ACE-Step）；可控生成（续写、重生成段落、换风格、分轨、inpainting） |
| 2 | 编解码器 token 上的语言模型 | MusicGen（2023）以文本/旋律 embedding 为条件，自回归预测 EnCodec token（32 kHz、4 个 codebook），再用 EnCodec 解码；300M–3.3B；超过 30 秒容易失去结构 |
| 3 | mel / latent 上的扩散 | Stable Audio、Stable Audio Open 在压缩音频的潜空间做扩散，擅长 loop、音效、氛围；AudioLDM2 把文生图式潜扩散推广到音乐、音效和语音；不擅长有结构的整首歌 |
| 4 | 闭源混合系统 | Suno v5（讲义称 ELO 1293 的质量领先者）、Udio v4（inpainting + 分轨下载）、Google Lyria；架构未公开，讲义推测为 AR 编解码器 LM + 扩散式 vocoder |
| 5 | 开源整首歌 | ACE-Step XL（4B，Apache-2.0，讲义称 2026 年 4 月发布）与 YuE（7B，多语种），时长可超过 2 分钟、带人声 |
| 6 | 旋律条件 | MusicGen-melody 输入 chromagram（每帧 12 维音高类别向量），保留旋律、替换音色 |
| 7 | 评测 | FAD：真实与生成音频在 VGGish / PANNs embedding 空间的分布距离，越低越好；CLAP score 衡量文本—音频对齐；人工偏好 / ELO；结构类伪影 |
| 8 | 法律格局 | 唱片公司与 Suno、Udio 的和解；EU AI Act 与 California SB 942 要求披露 AI 生成；安全上线路径：只做器乐、用带授权的商业 API、用自有/授权曲库训练、加水印和元数据 |
| 9 | 上线常见坑 | "某歌手风格"类提示词洗版权、30 秒后重复/漂移、速度漂移、开源模型歌词含糊、单声道或伪立体声 |
| 10 | "随时间的 token"（代码视角） | 音乐可以离散化为随时间排列的符号：和弦级数、16 步鼓点网格；神经模型做的是同样的事，只是 token 来自神经编解码器 |

### 核心技能（能动手做到）

- [ ] 能读懂 `main.py`：把和弦级数映射到具体调的和弦、把 16 步鼓点按小节平铺，并手算任意 `bars` 下的输出
- [ ] 能定位并修复 `fake_generate` 中的两个解析 bug（"128 bpm" 带空格时速度丢失；按首字母误判调性），并用正则重写
- [ ] 能说清 token-LM 与扩散两条路线各自擅长和不擅长的场景，并按讲义的 Use It 表为需求选型
- [ ] 能写出 FAD 的公式并解释它为什么不能代替人工听评，知道 CLAP score 衡量的是什么
- [ ] 能为一个 5 分钟背景音乐需求设计"分段生成 + 交叉淡化 + 固定 BPM/调/配器"的方案
- [ ] 能为音乐生成产品列出许可核查、提示词过滤、披露元数据与水印的上线清单

---

## 二、基础自测（选择题）

**Q1.** 关于 MusicGen 的生成方式，正确的是：

- A. 在 mel 频谱上做潜扩散
- B. 以文本/旋律 embedding 为条件，自回归预测 EnCodec 的离散 token（32 kHz、4 个 codebook），再由 EnCodec 解码
- C. 先生成 MIDI，再用采样器渲染
- D. 直接逐采样点生成 32 kHz 波形

**Q2.** 游戏音效团队要批量生成环境氛围音和可循环的 loop，讲义推荐优先考虑：

- A. Suno v5
- B. Stable Audio Open（潜扩散，擅长 loop、音效、氛围）
- C. YuE
- D. MusicGen-melody

**Q3.** 关于 FAD（Fréchet Audio Distance），下列说法**错误**的是：

- A. 比较的是真实音频与生成音频在预训练 embedding（如 VGGish、PANNs）空间中的分布
- B. 数值越低越好
- C. 适合做风格级别的回归测试
- D. FAD 足够低就说明音乐好听，可以替代人工听评

**Q4.** MusicGen-melody 的旋律条件输入 chromagram，它是：

- A. 每帧 12 维的音高类别（pitch class）向量
- B. 每帧 80 维的 mel 频谱
- C. 文本 embedding
- D. EnCodec 的离散 token

**Q5.** 用 MusicGen 一次生成 4 分钟的连续音乐，最可能遇到的问题与讲义建议的对策是：

- A. 音量过大，对策是降低采样率
- B. 超过约 30 秒后重复、漂移、失去结构；对策是多段生成后交叉淡化，或改用结构连贯性更好的 ACE-Step
- C. 无法生成鼓点；对策是换成 Stable Audio
- D. 只会生成人声；对策是加 "instrumental" 提示词

**Q6.** 想自动评估"生成的音乐是否符合文字描述"，最合适的指标是：

- A. FAD
- B. CLAP score（对比学习的音频—文本 embedding 相似度）
- C. WER
- D. SECS

**Q7.** 按讲义的 2026 模型表，以下哪个组合满足"开源权重、带人声、可超过 2 分钟、许可证为 Apache-2.0"？

- A. Stable Audio Open
- B. MusicGen-large
- C. ACE-Step XL
- D. Udio v4

---

## 三、动手 / 代码题

**Q8.** 运行 `main.py`，第一个提示词是 `"upbeat pop in G major at 128 bpm"`，第三个是 `"rock anthem in D at 140 bpm"`，但输出的 tempo 都是 `120 bpm`。阅读下面的代码找出原因，并写一个 `parse_bpm(prompt, default=120)` 修复它（要求同时支持 "128 bpm"、"128bpm"、"90BPM"）。

```python
    bpm = 120
    for token in prompt_lower.split():
        if token.endswith("bpm"):
            try:
                bpm = int(token[:-3])
            except ValueError:
                pass
```

**Q9.** 调性识别代码如下（`MAJOR_KEYS` 的键依次为 `"C"`、`"G"`、`"D"`、`"A"`）。预测 `"gentle ballad in D"` 和 `"chill lofi in A"` 会被识别成什么调，解释原因，并用正则写出更可靠的 `detect_key`。

```python
    key = "C"
    for k in MAJOR_KEYS:
        if f" {k.lower()}" in " " + prompt_lower:
            key = k
            break
```

**Q10.** 阅读 `chord_progression`：

```python
COMMON_PROGRESSIONS = {
    "pop":     [1, 5, 6, 4],
    "ballad":  [1, 6, 4, 5],
    "jazz":    [2, 5, 1, 6],
    # ...
}

def chord_progression(key, genre, bars=8):
    scale = MAJOR_KEYS[key]
    pat = COMMON_PROGRESSIONS.get(genre, COMMON_PROGRESSIONS["pop"])
    repeats = bars // len(pat) + 1
    seq = (pat * repeats)[:bars]
    return [scale[i - 1] for i in seq]
```

(1) 写出 `chord_progression("C", "jazz", bars=6)` 和 `chord_progression("G", "ballad", bars=3)` 的返回值。
(2) 为什么是 `scale[i - 1]` 而不是 `scale[i]`？
(3) `repeats = bars // len(pat) + 1` 在 `bars` 恰好是 4 的倍数时会多重复一次，这会出错吗？

---

## 四、面试高频题

**Q11.**（基础必考）比较音乐生成的两条主流技术路线：编解码器 token 上的自回归语言模型（MusicGen）与潜空间扩散（Stable Audio）。各自擅长什么、不擅长什么？

**Q12.**（原理深挖）为什么 MusicGen 这类自回归模型生成超过 30 秒就容易重复、漂移、失去结构？有哪些工程或建模手段可以缓解？

**Q13.**（原理深挖）FAD 是怎么计算的？它有哪些局限？一个音乐生成模型的完整评测方案应包含哪些部分？

**Q14.**（场景设计）冥想 App 需要纯器乐背景音乐，每首最长 5 分钟，要求完整商业权利。请给出模型、许可核查、长度方案、提示词和披露方案。

**Q15.**（工程实践）上线一个面向公众的文本生成歌曲功能，你需要做哪些合规与安全措施？"in the style of 某知名歌手"这类提示词怎么处理？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义原文：MusicGen "condition on text/melody embeddings, autoregressively predict EnCodec tokens (32 kHz, 4 codebooks), decode with EnCodec"。A 是 Stable Audio / AudioLDM 的路线；C 是符号音乐（本节代码的玩具做法）；D 是 WaveNet 式逐采样点生成，成本过高，不是 MusicGen 的做法。

### Q2 — 答案：B

讲义：Stable Audio / Stable Audio Open "Excels at loops, sound design, ambient textures"，Use It 表中 "Instrumental sound design → Stable Audio Open"。注意它在讲义表中标注为非商业许可，商用前要核查。Suno、YuE 主打带人声的整首歌；MusicGen-melody 适合"按哼唱旋律生成"。

### Q3 — 答案：D

讲义明确说 FAD "Useful for genre-level regression tests; not a substitute for human listeners"。FAD 只衡量分布层面的接近程度：模型可以在分布统计上接近真实音乐，但单首作品仍可能结构混乱、转场生硬。A、B、C 都是正确描述。

### Q4 — 答案：A

Key Terms："Chromagram — 12-dim per-frame vector; input to melody conditioning"。12 维对应十二平均律的 12 个音高类别（C、C#、…、B），与八度无关，所以能保留旋律轮廓、丢掉音色，正适合"同一旋律换成弦乐四重奏"。

### Q5 — 答案：B

讲义："Strong baseline; struggles past 30 seconds"，Pitfalls："AR models loop. Crossfade multiple generations, or use ACE-Step for structural coherence"。skill 文件的示例方案就是 30 秒一段、3 秒交叉淡化、拼接 10 段得到 5 分钟。

### Q6 — 答案：B

CLAP 是"音频版 CLIP"，把文本和音频映射到同一 embedding 空间，余弦相似度越高说明越贴合描述。FAD 不看提示词；WER 是语音识别指标；SECS 是说话人相似度指标。

### Q7 — 答案：C

讲义模型表：ACE-Step XL 4B、> 2 min、带人声、Apache-2.0。Stable Audio Open 无人声且为非商业许可；MusicGen-large 无人声、30 秒；Udio v4 是闭源商业服务。另外提醒：讲义把 MusicGen 标为 MIT，但按 audiocraft 官方仓库的说明，MIT 指的是**代码**，官方发布的预训练**权重**是 CC-BY-NC 4.0（非商业）——"代码许可 ≠ 权重许可"是选型时必须核查的点。

### Q8 — 参考答案

原因：`split()` 按空白切分，"128 bpm" 被切成 `"128"` 和 `"bpm"` 两个 token。`"128"` 不以 "bpm" 结尾被跳过；`"bpm"` 以 "bpm" 结尾，`int("")` 抛 `ValueError` 被 `except` 吞掉，`bpm` 保持默认值 120。只有写成 "128bpm"（无空格）才能解析成功。这也是讲义 Pitfalls 中"速度漂移"问题的缩影：连提示词里的 BPM 都没传下去。

修复（已验证："upbeat pop in G major at 128 bpm" → 128，"rock anthem in D at 140 bpm" → 140，"pop at 90BPM in E" → 90）：

```python
import re

def parse_bpm(prompt, default=120):
    m = re.search(r"(\d{2,3})\s*bpm\b", prompt.lower())
    return int(m.group(1)) if m else default
```

`\s*` 允许数字与 "bpm" 之间有零个或多个空格；`\d{2,3}` 限定 10–999 的合理范围；`\b` 防止匹配到 "bpmx" 之类。另外，`except ValueError: pass` 静默吞异常是这个 bug 难以发现的原因，至少应该记录日志。

### Q9 — 参考答案

- `"gentle ballad in D"` → **G**：按 C、G、D、A 的顺序检查，`" c"` 不存在，`" g"` 匹配到了 "gentle" 的开头，于是提前 `break`。
- `"chill lofi in A"` → **C**：`" c"` 匹配到 "chill" 的开头。
- 原因：`f" {k.lower()}" in " " + prompt_lower` 只检查"空格 + 字母"，任何以该字母开头的单词都会命中；再加上按字典顺序先到先得，结果取决于单词首字母而不是真正的调号。（类似地，`"pop punk at 170 BPM"` 会因为 "at" 被识别成 A 调。）

修复（已验证上述两例分别得到 D、A；没写调号时回落到默认 C）：

```python
import re

def detect_key(prompt, default="C"):
    m = re.search(r"\bin\s+([a-g][#b]?)\b", prompt.lower())
    if m and m.group(1).upper() in MAJOR_KEYS:
        return m.group(1).upper()
    return default
```

思路是只接受 "in X" 这种明确表示调性的结构，并要求字母后面是单词边界。更完整的做法还应处理 "F# minor"、"Bb major" 等写法，并在调不在支持列表中时显式提示，而不是静默回落。

### Q10 — 参考答案

(1) 已运行验证：

```text
chord_progression("C", "jazz", bars=6)  → ['Dm', 'G', 'C', 'Am', 'Dm', 'G']
chord_progression("G", "ballad", bars=3) → ['G', 'Em', 'C']
```

jazz 的级数是 ii–V–I–vi，在 C 大调中是 Dm–G–C–Am，6 小节时循环到第二轮的前两个；ballad 是 I–vi–IV–V，G 大调中取前 3 个。

(2) 乐理里级数从 1 开始（I 级 = 主和弦），而 Python 列表下标从 0 开始，`scale[0]` 才是 I 级和弦，所以要减 1。`MAJOR_KEYS` 中每个调的 7 个和弦正好按 I、ii、iii、IV、V、vi、vii° 排列。

(3) 不会出错，只是多算了一点。`bars=8` 时 `repeats = 8 // 4 + 1 = 3`，`pat * 3` 有 12 个元素，切片 `[:8]` 只取前 8 个。`+1` 是为了处理 `bars` 不是 4 的倍数时的余数（如 `bars=6` 需要 2 轮），用"多给一轮再截断"省去了向上取整的判断；更精确的写法是 `repeats = -(-bars // len(pat))`（向上取整除法）。

### Q11 — 参考回答要点

- **编解码器 token + 自回归 LM（MusicGen）**：先用神经编解码器（EnCodec，32 kHz、4 个 codebook）把音频离散化为 token，再用 Transformer 以文本/旋律为条件逐步预测 token。优点：复用 LLM 的整套技术栈；条件控制灵活（文本、旋律 chroma）；讲义称其为强基线。缺点：逐步生成，延迟随长度增长；超过约 30 秒容易重复漂移。
- **潜空间扩散（Stable Audio、AudioLDM2）**：在压缩后的连续潜空间里从噪声迭代去噪，整段同时生成。优点：音色质感好，擅长 loop、音效、氛围，适合声音设计。缺点：讲义评价"Not great at structured full songs"，长程的段落结构（主歌—副歌—桥段）难以保证。
- **生产系统（Suno、Udio、Lyria）**：讲义推测是两者的混合：AR 编解码器 LM 负责结构与内容，扩散式 vocoder 负责音质，另有人声/鼓/旋律等专门的 head。
- **加分点**：联系第 13 节神经音频编解码器——多 codebook 的残差量化是 token 路线的基础；按 MusicGen 论文，EnCodec 帧率为 50 Hz，4 个 codebook 意味着每秒约 200 个 token，30 秒就是约 6000 个 token，这也解释了长度上限。

### Q12 — 参考回答要点

- **原因**：
  - 序列长：多 codebook token 每秒上百个，几分钟的音乐远超训练时的上下文长度；
  - 训练数据多为短片段（讲义模型表中 MusicGen 为 30 秒），模型没见过长程的段落结构；
  - 自回归的误差累积：一旦进入某个模式，模型倾向于重复自己（讲义：AR models loop）；
  - 没有显式的结构规划（主歌、副歌、桥段的位置）。
- **缓解手段**：
  - 工程：分段生成 + 交叉淡化（skill 示例：30 秒一段、3 秒交叉淡化）；以上一段结尾作为下一段的续写提示；淡入淡出包络掩盖漂移；
  - 控制：提示词中固定 BPM、调、配器，生成后用 librosa 的 beat tracking 检测速度漂移并过滤；
  - 模型：换用面向整首歌的模型（ACE-Step、YuE）；使用 inpainting 只重生成有问题的段落（Udio 的能力）；先生成歌词/结构再按段落条件生成。
- **常见误区**：认为把上下文窗口调大就能解决——训练数据中缺乏长程结构才是根本。

### Q13 — 参考回答要点

- **计算**：用预训练音频分类模型（VGGish 或 PANNs）分别提取真实集与生成集的 embedding，各自拟合多元高斯 `(μ_r, Σ_r)` 与 `(μ_g, Σ_g)`，然后 `FAD = ‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_r Σ_g)^½)`，越低越好。它就是图像领域 FID 的音频版（Key Terms："Audio FID"）。
- **局限**：只比较分布，不评价单首作品；依赖 embedding 模型的偏好（VGGish 在音频事件分类上训练，对音乐结构、歌词不敏感）；需要足够多的样本才能稳定估计协方差；与参考集的选择强相关；完全不看提示词。
- **完整评测方案**：
  - 分布质量：FAD（固定参考集、固定 embedding 模型）；
  - 文本对齐：CLAP score；
  - 人工：偏好测试 / ELO（讲义：Suno v5 ELO 1293）；
  - 专项：速度稳定性（beat tracking）、30 秒后的结构、歌词可懂度（可用 ASR 转写评估）、立体声质量；
  - 合规：版权相似度检测、风格提示词过滤的命中率。
- **加分点**：讲义 Step 3 的 `frechet_audio_distance` 库默认使用 VGGish；不同 embedding 模型下的 FAD 数值不能直接比较。

### Q14 — 参考回答要点

- **模型与许可**：需求是纯器乐 + 完整商业权利。讲义 skill 示例选的是 MusicGen-large 并称其为 MIT；但务必核查权重许可——audiocraft 仓库的说明是代码 MIT、预训练权重 CC-BY-NC 4.0，若属实则不能用于付费产品。Stable Audio Open 在讲义中也标为非商业。可行路线：①使用提供逐次商业授权的 API（讲义的 safe-to-ship 第 2 条）；②在自有或已获授权的曲库上训练/微调（第 3 条，讲义说大多数企业最终走这条路）；③选择权重许可明确允许商用的开源模型。
- **长度方案**：30 秒一段、3 秒交叉淡化，10 段拼成 5 分钟；整体加淡入淡出包络掩盖漂移（skill 示例）。
- **提示词**：固定 BPM、调、配器，并显式排除打击乐，例如 skill 示例的 `"slow ambient meditation, 60 BPM, soft strings and low pad, in D minor, no drums"`。
- **披露**：在 App 中标注 "AI-generated music"，元数据记录模型、日期；可选加水印（如 AudioSeal）做纵深防御。
- **常见误区**：只看仓库首页的 License 徽章——代码、权重、训练数据、生成物可能各有不同的许可条款，要逐项记录权利链。

### Q15 — 参考回答要点

- **提示词过滤**：讲义 Pitfalls 指出商业 Suno/Udio 已经过滤 "in the style of 某歌手"，开源模型不会，必须自建过滤名单（名人、在世艺人、商标风格词）。skill 文件要求在开源模型上拒绝名人风格提示词。
- **输出侧**：生成后做版权相似度检测（与已知作品比对）；带人声的作品更敏感（声音肖像 + 词曲著作权）。
- **披露与水印**：讲义：EU AI Act 与 California SB 942 要求披露 AI 生成音乐；skill 文件要求带人声的音乐必须打披露标签（`isAIGenerated` 元数据、AI 披露提示）并在可行时加水印。
- **商业条款**：使用 Suno/Udio 时确认每次生成的授权；Udio 的分轨（stems）附带商业条款，不能当作免费素材再分发（skill 文件提示）。
- **背景**：讲义提到唱片公司与 Suno、Udio 的和解在 2025–2026 年重塑了行业边界，平台对 AI 相似度、用户生成曲目的管控在加强。
- **加分点**：把合规做成管线的一部分（生成前过滤、生成后检测、发布前校验水印/元数据、全程审计日志），而不是人工抽查。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：mel 频谱、chroma 等音频特征。
- [阶段 04 · 10 扩散模型图像生成](../../../04-computer-vision/10-image-generation-diffusion/docs/zh.md)：Stable Audio、AudioLDM 的扩散原理。
- [阶段 08 · 07 潜在扩散 / Stable Diffusion](../../../08-generative-ai/07-latent-diffusion-stable-diffusion/docs/zh.md)：AudioLDM 借鉴的"文生图式潜扩散"。

### 本节被哪些后续内容用到
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：EnCodec 等多 codebook 编解码器是 MusicGen 的 token 来源。
- [阶段 06 · 16 语音反欺骗和音频水印](../../16-anti-spoofing-audio-watermarking/docs/zh.md)：AudioSeal 等水印用于 AI 音乐的披露与溯源。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：FAD、MOS 等指标的系统对比。
- [阶段 08 · 11 音频生成](../../../08-generative-ai/11-audio-generation/docs/zh.md)：从生成模型谱系看音频生成。
- [阶段 08 · 14 生成模型评测：FID 与 CLIP Score](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：FAD 与 FID、CLAP 与 CLIP score 一一对应。
- [阶段 18 · 27 数据来源与训练治理](../../../18-ethics-safety-alignment/27-data-provenance-training-governance/docs/zh.md)：训练数据授权与版权治理。

### 延伸关键词
`EnCodec / RVQ` · `codebook interleaving (delay pattern)` · `chromagram` · `CLAP` · `FAD (VGGish / PANNs)` · `stem separation` · `audio inpainting` · `beat tracking` · `模型权重许可 vs 代码许可` · `AI 内容披露 (SB 942)`
