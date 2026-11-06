# 测验 · 音频语言模型 — Qwen2.5-Omni、Audio Flamingo、GPT-4o Audio（Audio-Language Models — Qwen2.5-Omni, Audio Flamingo, GPT-4o Audio）

> **阶段 06 · 语音与音频 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LALM 是什么 | 音频语言模型（LALM / ALM）用一个模型、一个提示词回答转写、语义推理、音乐、长音频检索等问题，输出自由形式的自然语言，而不只是转写文本 |
| 2 | 三组件模板 | 音频 encoder（Whisper encoder、BEATs、CLAP、WavLM 或自研）→ projector（Linear / MLP）→ LLM decoder（Llama / Qwen / Gemma 系） |
| 3 | 三阶段训练 | 阶段 1：冻结 encoder 和 LLM，只用 ASR / captioning 数据训练 projector；阶段 2：在音频指令任务上全量或 LoRA 微调；阶段 3（可选）：加语音解码器实现 voice-in / voice-out |
| 4 | Projector 的本质 | 通常 1–3 层线性层，把音频帧特征映射到 LLM 的 token embedding 空间；输出是连续向量，直接与文本 embedding 拼在一起送入 LLM |
| 5 | 音频 token 预算 | 代码按 50 帧/秒模拟 Whisper 类 encoder：3 秒 = 150 帧，10 分钟 = 30000 帧，长音频会迅速吃满上下文 |
| 6 | 2026 模型地图 | 开源：Qwen2.5-Omni-7B / Qwen3-Omni（Apache-2.0，可输出语音）、Audio Flamingo 3 / Next（NVIDIA 非商业许可）、SALMONN（Whisper + BEATs 双 encoder）、LTU、GAMA；闭源：Gemini 2.5、GPT-4o Audio |
| 7 | MMAU-Pro 现实检验 | 讲义数据：Qwen2.5-Omni-7B 52.2% vs GPT-4o Audio 52.5%；但多音频（multi-audio）子集所有模型都在约 20–26%，4 选 1 的随机水平是 25% |
| 8 | 能用 / 不能用 | 能用：通话合规审计、给听障用户描述声音事件、内容审核、播客/会议分章、音乐曲库分析；还不行：和弦以下的细粒度乐理、10 分钟以上的说话人归属推理、多音频比较、实时流式推理 |
| 9 | 评测要用官方评分器 | 精确匹配循环只是 sanity check；MMAU-Pro 官方评分器用 NV-Embed-v2 做选项匹配、LLM 评判开放题、正则检查指令遵循，并要按类别分别报告 |
| 10 | 上线坑 | 过度信任多音频能力；长音频说话人归属崩溃（先做 diarization）；静音段幻觉（加 VAD 门控）；厂商博客挑最好看的类别 |

### 核心技能（能动手做到）

- [ ] 能读懂 `main.py` 的 encoder → projector → 拼接 → LLM 流程，并算出任意时长音频对应的帧数与张量形状
- [ ] 能计算讲义 `AudioProjector`（Linear 1280→4096 + GELU + Linear 4096→4096）的参数量（约 22M），并解释为什么阶段 1 只训练它
- [ ] 能用 numpy 实现一个 projector，并写出"在文本中的音频占位符处插入音频 embedding"的输入构造函数
- [ ] 能说出级联方案（ASR + LLM）与端到端 LALM 各自适合的场景，并为通话合规审计设计完整管线
- [ ] 能为一个 LALM 选型任务指定应验证的 benchmark 子集（speech / sound / music / multi-audio / LongAudioBench）
- [ ] 能解释为什么自己用精确匹配算出的 MMAU-Pro 准确率不能与排行榜直接比较

---

## 二、基础自测（选择题）

**Q1.** 讲义中 LALM 训练的阶段 1（Stage 1）通常是：

- A. 端到端全量训练 encoder、projector 和 LLM
- B. 冻结音频 encoder 和 LLM，只在 ASR / captioning 数据上训练 projector
- C. 只训练语音解码器
- D. 冻结 projector，只训练 LLM

**Q2.** 在 MMAU-Pro 的多音频（multi-audio）4 选 1 子集上，某模型得分 22%。最合理的解读是：

- A. 比随机好不少，可以上线"比较两段音频"的功能
- B. 与随机猜测（25%）相当甚至略低，模型基本不具备多音频比较能力
- C. 说明该模型的语音识别很差
- D. 说明题目太简单

**Q3.** 一个使用 Whisper encoder 的 LALM 在输入的静音段"听到"了不存在的对话。讲义建议的工程对策是：

- A. 把 LLM 换成更大的模型
- B. 在 LALM 之前加 VAD 门控，只送入有语音/声音活动的片段
- C. 提高采样率到 48 kHz
- D. 把 projector 换成 Q-Former

**Q4.** 要分析一段 90 分钟、多人参与的会议录音，回答"谁在什么时候提出了预算问题"。按讲义建议，合理的做法是：

- A. 直接把 90 分钟音频一次性送进 LALM
- B. 先做说话人分离（diarization），再按说话人分段送入模型做总结和推理
- C. 只用 MMAU-Pro 的 music 子集评测
- D. 用多音频比较功能对比每两段话

**Q5.** 关于 projector 的输出，正确的是：

- A. 一串离散的 token ID，需要再经过 LLM 的词表 embedding 查表
- B. 与 LLM 隐藏维度相同的连续向量，直接和文本 token 的 embedding 拼接成输入序列
- C. 一段文字转写
- D. 一个标量置信度

**Q6.** 你用"预测选项 == 标准答案"的循环在 MMAU-Pro 上测出 48%，而排行榜上同一模型是 52%。讲义对此的说明是：

- A. 一定是你的模型权重下载错了
- B. 精确匹配循环只是 sanity check；官方评分器用 embedding 相似度（NV-Embed-v2）匹配选项、用 LLM 评判开放题、用正则检查指令遵循，两种数字不可直接比较
- C. 排行榜一定造假
- D. MMAU-Pro 不包含选择题

**Q7.** 讲义 skill 文件建议：一个 LALM 不是每项能力都最强，遇到下列子任务时应"回退"到专用模型。下列配对**错误**的是：

- A. 转写 → Whisper
- B. 声音分类 → BEATs
- C. 说话人分离 → pyannote
- D. 多音频比较 → 直接信任任意 LALM，无需验证

**Q8.** 一家公司要在付费 SaaS 产品里使用开源 LALM 做音乐理解。按讲义模型表，需要特别注意许可的是：

- A. Qwen2.5-Omni-7B（Apache-2.0）
- B. Audio Flamingo 3 / Next（NVIDIA non-commercial）
- C. SALMONN（Apache-2.0）
- D. GAMA（Apache-2.0）

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 的 encoder 与 projector：

```python
def fake_audio_encoder(audio_seconds=3.0, dim=1280):
    rng = random.Random(0)
    n_frames = int(audio_seconds * 50)
    return [[rng.gauss(0, 0.5) for _ in range(dim)] for _ in range(n_frames)]

def projector(features, audio_dim=1280, llm_dim=4096):
    random.seed(1)
    W_down = [[random.gauss(0, 0.02) for _ in range(audio_dim)] for _ in range(llm_dim)]
    out = []
    for f in features:
        hidden = [sum(W_down[i][j] * f[j] for j in range(audio_dim)) for i in range(llm_dim)]
        hidden = [max(0.0, h) for h in hidden]
        out.append(hidden)
    return out
```

(1) 一段 30 秒和一段 10 分钟的音频分别产生多少帧？如果每帧都变成一个 LLM 输入位置，对上下文意味着什么？
(2) `main()` 只调用了 `projector(feats[:8])`，为什么不投影全部 150 帧？每帧需要多少次乘加？
(3) 经过 ReLU 后，大约多少比例的输出为 0？均值大约是多少？（提示：先估算 ReLU 之前每个元素的标准差）

**Q10.** 讲义 Step 2 的 projector 是 `Linear(1280, 4096) → GELU → Linear(4096, 4096)`。(1) 计算它的参数量（含 bias）。(2) 用 numpy 重写一个等价的 `AudioProjector`，要求使用局部随机数生成器，输入 `(T, 1280)` 输出 `(T, 4096)`。

**Q11.** `interleave_with_text` 的实现是：

```python
def interleave_with_text(audio_tokens, text_tokens):
    return [("AUDIO", a) for a in audio_tokens] + [("TEXT", t) for t in text_tokens]
```

而 `main()` 中传入的 `audio_tokens` 是 `list(range(len(projected)))`。指出这个函数与真实 LALM 输入构造的两点差异，并写一个函数：在文本 token 序列中遇到占位符 `AUDIO_SLOT` 时，插入 `<audio_start>` embedding、全部音频 embedding、`<audio_end>` embedding，其他位置查文本 embedding 表，最后返回 `(L, d)` 的矩阵。

---

## 四、面试高频题

**Q12.**（基础必考）介绍一下音频语言模型（LALM）的典型架构和训练流程。为什么阶段 1 要冻结 encoder 和 LLM、只训练 projector？

**Q13.**（原理深挖）为什么 2026 年几乎所有 LALM 在多音频比较任务上都接近随机水平？如果让你改进，你会从数据、模型输入、系统设计哪几方面入手？

**Q14.**（工程实践）设计一个银行客服通话的合规审计系统：每通电话约 10 分钟，要检查坐席是否读了法定披露声明，并给出依据。你会直接用 LALM 吗？

**Q15.**（场景设计）"ASR + 文本 LLM"的级联方案与端到端 LALM 怎么选？举出各自更合适的场景。

**Q16.**（追问型）某厂商博客宣称其音频模型"在 MMAU-Pro 上追平 GPT-4o Audio"。你会如何独立验证？需要关注哪些细节？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Stage 1. Freeze encoder + LLM; train projector only on ASR / captioning data." 这一步的目的是让音频特征"对齐"到 LLM 能理解的 embedding 空间，训练量小、稳定。全量或 LoRA 微调是阶段 2；语音解码器是可选的阶段 3。

### Q2 — 答案：B

4 选 1 的随机水平是 25%，22% 甚至低于随机。讲义："The multi-audio column is damning for everyone ... LALMs still struggle to compare two clips." skill 文件要求多音频子集低于 30% 时拒绝这类任务、低于 40% 时不得上线多音频比较功能。C 错，多音频与单段语音识别能力无直接关系。

### Q3 — 答案：B

讲义 Pitfalls："Hallucinations on silence. Same Whisper-style issue inherited by LALMs that use Whisper encoder. VAD-gate." Whisper 在静音或噪声上"编造"文本是已知问题，用 VAD（语音活动检测，第 14 节）过滤掉无活动片段是最直接的办法。

### Q4 — 答案：B

讲义："Long-audio degradation. Past 10 minutes, most models' speaker attribution breaks. Diarize first (Lesson 6), then summarize." skill 文件也要求 10 分钟以上输入必须先做上游 diarization。A 恰好是讲义警告的做法；C、D 与任务无关。

### Q5 — 答案：B

projector 把 encoder 的每一帧（如 1280 维）映射成 LLM 隐藏维度（如 4096 维）的**连续向量**，这些向量绕过词表查表，直接与文本 token 的 embedding 拼在同一个序列里。这也是它被称为"adapter"的原因。A 描述的是离散音频 token 路线（如神经编解码器 token），不是 projector 的输出。

### Q6 — 答案：B

讲义 Step 3 说明："This exact-match loop is a sanity check, not the benchmark scorer, so its number is not comparable with published MMAU-Pro results." 官方评分器对选择题用 NV-Embed-v2 做 embedding 相似度匹配（模型输出不一定逐字等于选项），开放题用 LLM 评判，指令遵循题用正则规则，并要求按 `category` 分别报告。

### Q7 — 答案：D

skill 文件的 Escalation 部分："Whisper for transcription, BEATs for classification, pyannote for diarization. LALM is not the best of each." 多音频比较恰恰是需要独立验证、并且多数模型接近随机的能力，D 与讲义完全相反。

### Q8 — 答案：B

讲义模型表中 Audio Flamingo 3 与 Audio Flamingo Next 的许可是 "NVIDIA non-commercial"，不能直接用于付费产品；其余三个标注为 Apache-2.0。讲义 Use It 表把 Audio Flamingo 列为音乐推理首选，所以"效果最好的那个未必能商用"是选型时的典型陷阱。

### Q9 — 参考答案

(1) 帧率是 50 帧/秒：30 秒 → 1500 帧，10 分钟 → 30000 帧。如果每帧都占一个 LLM 输入位置，10 分钟音频就要 3 万个位置，加上文本后很容易超出上下文窗口，attention 计算量也按序列长度平方增长。这就是讲义说"长音频退化""先 diarize 再总结"的工程背景；真实模型通常会在 encoder 之后做时间维度的下采样（池化或把相邻帧拼接后再投影）来减少音频 token 数。

(2) 纯 Python 实现中，每帧要做 `4096 × 1280 = 5,242,880` 次乘加；生成权重矩阵本身也要 524 万次 `random.gauss`。实测投影 8 帧时整个脚本约 4.8 秒，其中投影 2 帧约 2.3 秒（大部分花在生成权重上）。投影全部 150 帧会慢得多，而演示只需要展示形状 `(8, 4096)`。真实实现用矩阵乘法在 GPU 上一次算完 `(T, 1280) @ (1280, 4096)`。

(3) ReLU 前每个元素是 1280 项之和，每项是 `N(0, 0.02²)` 与 `N(0, 0.5²)` 的乘积，标准差约 `√1280 × 0.02 × 0.5 ≈ 0.358`，分布关于 0 对称，所以约 **50%** 的输出被 ReLU 置零（实测第一帧为 48.4%）；ReLU 后的均值为 `σ/√(2π) ≈ 0.143`（实测 0.146）。

### Q10 — 参考答案

(1) 参数量：

```text
Linear(1280, 4096): 1280 × 4096 + 4096 = 5,246,976
Linear(4096, 4096): 4096 × 4096 + 4096 = 16,781,312
合计 22,028,288 ≈ 22M
```

相比 7B 参数的 LLM，这只占约 0.3%，所以阶段 1 只训练它非常便宜。代码中的 `projector` 只有一层、没有 bias，参数为 `1280 × 4096 = 5,242,880`。注意：讲义里第一层叫 `down`、代码里叫 `W_down`，但它其实把维度从 1280 **升**到 4096，名字容易误导。

(2) numpy 实现（已运行验证：输入 `(150, 1280)` 输出 `(150, 4096)`，参数量 22,028,288）：

```python
import math
import numpy as np

def gelu(x):
    return 0.5 * x * (1 + np.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x**3)))

class AudioProjector:
    def __init__(self, audio_dim=1280, llm_dim=4096, seed=1):
        rng = np.random.default_rng(seed)          # 局部生成器，无全局副作用
        self.W1 = rng.normal(0, 0.02, (audio_dim, llm_dim))
        self.b1 = np.zeros(llm_dim)
        self.W2 = rng.normal(0, 0.02, (llm_dim, llm_dim))
        self.b2 = np.zeros(llm_dim)

    def n_params(self):
        return sum(a.size for a in (self.W1, self.b1, self.W2, self.b2))

    def __call__(self, feats):                     # feats: (T, audio_dim)
        return gelu(feats @ self.W1 + self.b1) @ self.W2 + self.b2
```

要点：①一次矩阵乘法处理所有帧，替代三重 Python 循环；②权重只在构造时生成一次，而原代码每次调用 `projector` 都重新生成 `W_down`；③GELU 用常见的 tanh 近似。

### Q11 — 参考答案

两点差异：

1. **不是真正的"交错"**：函数只是把所有音频项放在前面、文本放在后面。真实的聊天模板中，音频出现在用户消息内部的某个位置（例如"请听这段音频：<音频>，回答……"），前后有特殊的起止标记，多段音频还可以出现在不同位置。
2. **音频项不是向量**：传入的是下标 `0..7`，而真实输入应当是 projector 输出的 4096 维连续向量；文本是 token ID，需要查 embedding 表才变成向量。两者在送入 LLM 前必须统一成 `(L, d)` 的 embedding 矩阵。

参考实现（已运行验证：5 个文本 token + 150 帧音频 + 2 个标记 → `(157, 4096)`）：

```python
import numpy as np

AUDIO_SLOT = -1

def build_inputs(text_ids, audio_embs, embed_table, bos_id=1, eos_id=2):
    seq = []
    for tid in text_ids:
        if tid == AUDIO_SLOT:
            seq.append(embed_table[bos_id])        # <audio_start>
            seq.extend(audio_embs)                  # (T, d) 的每一行
            seq.append(embed_table[eos_id])         # <audio_end>
        else:
            seq.append(embed_table[tid])            # 文本 token 查表
    return np.stack(seq)                            # (L, d)
```

这里用 `bos_id=1`、`eos_id=2` 代表音频起止标记，只是示意；真实模型的特殊 token 由各自的 tokenizer 定义。

### Q12 — 参考回答要点

- **架构**：音频 encoder（Whisper encoder、BEATs、CLAP、WavLM 等，把波形或 mel 变成逐帧特征）→ projector（1–3 层 Linear / MLP，映射到 LLM embedding 空间）→ LLM decoder（接收交错的文本与音频 embedding，生成文本）。可选再接语音解码器实现语音输出（Qwen2.5-Omni、AF3-Chat）。
- **训练流程**：阶段 1 只训 projector（ASR / captioning 数据）；阶段 2 在音频 QA、推理、音乐理解等指令数据上全量或 LoRA 微调；阶段 3 可选加语音输出。
- **为什么阶段 1 冻结**：①encoder 与 LLM 都已经是强大的预训练模型，一开始 projector 是随机初始化的，若同时更新，巨大的随机梯度会破坏 LLM 的语言能力；②只训几千万参数，算力和数据需求都小；③ASR / captioning 是"音频 → 文本"的天然对齐任务，适合学习模态映射。这和视觉语言模型（LLaVA、BLIP-2）的做法一脉相承。
- **加分点**：提到 SALMONN 使用 Whisper + BEATs 双 encoder，分别覆盖语音与非语音声音；GAMA 使用 AST + Q-Former 作为桥接。

### Q13 — 参考回答要点

- **现象**：讲义表中多音频列在 20%–26.5% 之间，4 选 1 随机水平 25%。
- **可能原因**：
  - 训练数据几乎都是"一段音频 + 一个问题"，很少有成对比较的样本；
  - 多段音频被投影后简单拼接，模型难以区分哪些 token 属于哪一段（缺乏清晰的分段与位置标识）；
  - 比较需要在两段内容上做细粒度对齐，长序列下 attention 被稀释；
  - 评测题目更依赖推理，而不只是识别。
- **改进思路**：
  - 数据：构造成对或多段比较的指令数据（"哪一段节奏更快""两段是否是同一个人"）；
  - 输入：每段音频加独立的起止标记和片段编号，必要时加片段级 embedding；
  - 系统：先对每段音频单独生成结构化描述，再让文本 LLM 比较描述；对于"是否同一说话人"这类问题，直接调用专用模型（说话人验证）而不是让 LALM 硬猜。
- **工程结论**：在验证分数之前不要上线多音频功能（skill 文件：低于 40% 不得上线）。

### Q14 — 参考回答要点

- **不直接用 LALM 处理整段原始音频**：讲义指出 10 分钟以上的长音频说话人归属会崩溃；skill 文件的示例方案正是这个场景。
- **推荐管线**（参考 skill 示例）：
  1. VAD 去除静音（防止幻觉）；
  2. 用 pyannote 做说话人分离，区分坐席与客户；
  3. 用 Whisper-large-v3-turbo 转写，保留时间戳；
  4. 用 Gemini 2.5 Pro 等 LLM 在坐席的转写文本上判断是否完整读出了披露声明，必要时对政策文档做 RAG；
  5. 输出结论 + 证据（时间戳、原文片段）+ 每通电话的置信度日志。
- **评测**：用 MMAU-Pro speech 子集做能力参照，再在自己标注的约 50 通"金标准"通话上抽检（skill 示例）。
- **风险控制**：判定"未通过"时转人工复核，而不是自动处罚坐席；只输出文本，不需要语音输出。
- **常见误区**：只看 LALM 在 benchmark 上的总分，忽略了长音频和说话人归属这两个本场景最关键的弱点。

### Q15 — 参考回答要点

- **级联（ASR + LLM）更合适**：任务主要看"说了什么"（合规审计、会议纪要、客服质检）；音频很长；需要可审计的中间结果（转写稿可以人工复核）；需要最高的转写精度；成本敏感（文本 LLM 便宜）。
- **端到端 LALM 更合适**：答案依赖非文字信息——语气（威胁、讽刺）、背景声音（狗叫、警报、玻璃碎裂）、音乐属性；讲义的"狗叫 + 喊 stop + 沉默"场景、给听障用户描述声音事件、内容审核中的"威胁语气 + 背景"，都是转写会丢信息的场景。
- **混合**：先用专用模型（VAD、diarization、ASR）做结构化，再用 LALM 处理需要声学线索的片段。
- **加分点**：讲义的 voice-in / voice-out 模型（Qwen2.5-Omni、GPT-4o Audio）适合语音 Agent，但讲义也指出多数 LALM 仍是离线批处理，实时流式推理还不成熟，这时需要第 11、12、15 节的流式方案。

### Q16 — 参考回答要点

- **按类别看，不看总分**：讲义强调按 `category`（speech、sound、music、multi 等）分别报告，"Aggregate numbers hide where the model fails"；尤其要看多音频子集（skill 文件："Run MMAU-Pro multi-audio subset yourself"）。
- **用官方评分器**：把预测写入 `model_output` 列，运行 MMAU-Pro 仓库的 `evaluate_mmau_pro_comprehensive.py`；自己写的精确匹配循环只能做 sanity check。
- **控制变量**：同样的提示词模板、解码参数（温度、最大长度）、音频预处理（采样率 16 kHz、截断策略）、同一版本的数据集（音频在约 47 GB 的 `data.zip` 中）。
- **看误差范围**：讲义中 Qwen2.5-Omni-7B 52.2% 与 GPT-4o Audio 52.5% 相差 0.3 个百分点，在 1800 题左右的规模下这点差距完全可能落在抽样误差内，"追平"的说法要结合置信区间理解。
- **在自己的数据上复测**：benchmark 只是参照，最终以业务金标准集上的表现为准；skill 文件要求标记任何未经独立复核就使用厂商数字的部署。
- **常见误区**：被博客里挑出来的最佳类别（cherry-picking）误导。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：ASR 与 LALM 的区别，以及阶段 1 的 ASR 预训练任务。
- [阶段 06 · 05 Whisper——架构与 Fine-Tuning](../../05-whisper-architecture-finetuning/docs/zh.md)：最常用的 LALM 音频 encoder，50 帧/秒、1280 维的来源。
- [阶段 07 · 10 音频 Transformer（Whisper）](../../../07-transformers-deep-dive/10-audio-transformers-whisper/docs/zh.md)：音频 Transformer encoder 的结构。
- [阶段 12 · 03 BLIP-2 与 Q-Former](../../../12-multimodal-ai/03-blip2-qformer-bridge/docs/zh.md)：视觉侧"encoder + 桥接 + LLM"的同构设计，GAMA 也用 Q-Former。
- [阶段 12 · 05 LLaVA 视觉指令微调](../../../12-multimodal-ai/05-llava-visual-instruction-tuning/docs/zh.md)：先训 projector、再指令微调的两阶段范式。

### 本节被哪些后续内容用到
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：长音频场景中先做 diarization 的依据。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：级联 STT → LLM → TTS 与端到端模型的取舍。
- [阶段 06 · 14 语音活动检测与对话轮次](../../14-voice-activity-detection-turn-taking/docs/zh.md)：VAD 门控防止静音幻觉。
- [阶段 06 · 15 Streaming 语音到语音（Moshi、Hibiki）](../../15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：真正的实时 voice-in / voice-out。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：MMAU 等音频理解 benchmark 的系统讲解。
- [阶段 12 · 19 音频语言模型：从 Whisper 到 AF3](../../../12-multimodal-ai/19-audio-language-whisper-to-af3/docs/zh.md)：多模态视角下的 LALM 演进。
- [阶段 12 · 20 Omni 模型：Thinker-Talker](../../../12-multimodal-ai/20-omni-models-thinker-talker/docs/zh.md)：Qwen-Omni 类模型如何同时输出文本与语音。

### 延伸关键词
`modality projector / adapter` · `Q-Former` · `帧率下采样 (pooling / frame stacking)` · `SALMONN 双 encoder` · `Thinker-Talker` · `MMAU / MMAU-Pro` · `LongAudioBench` · `NV-Embed-v2 选项匹配` · `LLM-as-judge` · `VAD gating`
