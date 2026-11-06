# 测验 · Streaming 语音到语音 — Moshi、Hibiki 和全双工对话（Streaming Speech-to-Speech — Moshi, Hibiki, and Full-Duplex Dialogue）

> **阶段 06 · 语音与音频 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 流水线的延迟下限 | VAD → STT → LLM → TTS 每一级都有自己的最小延迟，调优和并行化之后仍有约 300–500 ms 的地板 |
| 2 | 全双工语音到语音 | 一个模型连续地"边听边说"：输入是用户音频 token，输出是自己的音频 token，没有串行的阶段 |
| 3 | 延迟账本 | 理论 160 ms = 80 ms（一个 Mimi 帧）+ 80 ms（声学延迟）；单张 L4 上实测约 200 ms |
| 4 | 三条并行流 | 用户音频流（Mimi 12.5 Hz × 8 码本）、Moshi 自己的音频流、Moshi 的文本流（inner monologue） |
| 5 | Temporal + Depth Transformer | 7B 的 Temporal Transformer 沿时间步建模；帧内 8 个码本有依赖，由小型 Depth Transformer 逐个预测 |
| 6 | 每一步的预测顺序 | 输入 `user_mimi[0..t]`、`moshi_mimi[0..t-1]`、`moshi_text[0..t-1]`；先预测 `moshi_text[t]`，再预测 `moshi_mimi[t]` 的 8 个码本 |
| 7 | inner monologue 的价值 | 强制模型输出自己"在说什么"的文本：语义更连贯、免费得到转写、更容易替换语言模型头 |
| 8 | Hibiki / Hibiki-Zero | 同一架构用翻译数据训练，做流式同传；Hibiki-Zero 用句级数据 + GRPO 强化学习优化延迟，新语言约需 1000 小时数据 |
| 9 | 全双工的短板 | 不擅长工具调用、长推理、冷门事实；单一人设；每个会话占一个 GPU 槽位——企业 agent 仍以流水线为主 |
| 10 | Sesame CSM | Llama-3 backbone + Mimi 输出头，但是**单向**（上下文 + 文本 → 语音），不是全双工 |

### 核心技能（能动手做到）

- [ ] 能画出 Moshi 一个 80 ms 步内的数据流：编码用户帧 → 预测文本 token → Depth Transformer 预测 8 个码本 → 解码输出音频
- [ ] 能把 `main.py` 的主循环逐行对应到讲义 Step 3 的训练目标（哪个变量是 `[0..t]`、哪个是 `[0..t-1]`）
- [ ] 能计算实时约束：每帧处理时间必须 < 80 ms，并据此估算实时因子（RTF）
- [ ] 能用 `asyncio.create_task` + `asyncio.gather` 写出"麦克风上行 / 扬声器下行"同时运行的全双工客户端骨架
- [ ] 能给出流水线方案与全双工方案的延迟分解，并说明 160 ms 理论下限的来源
- [ ] 能为给定场景（陪聊、同传、带工具的企业客服）选择全双工、流水线或混合架构，并做 GPU 容量估算

---

## 二、基础自测（选择题）

**Q1.** 讲义给出的 Moshi 理论延迟 160 ms 由哪两部分组成？

- A. 80 ms STT + 80 ms TTS
- B. 80 ms 的 Mimi 帧 + 80 ms 的声学延迟
- C. 120 ms LLM 推理 + 40 ms 网络
- D. 125 ms flush + 35 ms 解码

**Q2.** 在 Moshi 的每个 80 ms 步中，下列预测顺序正确的是：

- A. 先并行预测 8 个码本，再预测文本 token
- B. 先预测文本 token（inner monologue），再由 Depth Transformer 顺序预测 8 个码本
- C. 只预测音频 token，文本由外部 ASR 生成
- D. 先预测用户下一帧音频，再预测自己的音频

**Q3.** 为什么 Moshi 帧内的 8 个码本要交给一个小 Depth Transformer **顺序**预测，而不是一次并行输出？

- A. 为了减少显存
- B. 码本之间存在依赖（RVQ 的后一级是前一级的残差），独立并行预测会不一致
- C. 因为 Mimi 解码器只接受顺序输入
- D. 因为 Temporal Transformer 只能输出一个 token

**Q4.** 下列哪一项**不是** inner monologue（内部独白文本流）带来的好处？

- A. 提升语义连贯性
- B. 免费获得模型所说内容的转写
- C. 更容易替换语言模型头
- D. 让 Moshi 天然具备可靠的工具调用能力

**Q5.** 关于 Sesame CSM，正确的是：

- A. 与 Moshi 一样是全双工模型
- B. 基于 Llama-3 backbone + Mimi codec 头，是"上下文 + 文本 → 语音"的单向模型
- C. 是一个流式同传模型
- D. 使用 EnCodec 而不是 Mimi

**Q6.** 一家银行要做能查余额、办挂失的语音客服 agent，最符合讲义建议的架构是：

- A. 纯 Moshi，因为延迟最低
- B. 流水线（第 12 节），或"全双工前端 + 外部 LLM 处理工具调用"的混合方案
- C. Hibiki，因为支持多语言
- D. Sesame CSM，因为声音最自然

**Q7.** Moshi 的两路 Mimi 音频流都是 12.5 Hz × 8 码本。处理 1 秒对话时，模型在两路音频上一共要"看/写"多少个音频 token？

- A. 12.5
- B. 100
- C. 200
- D. 1000

**Q8.** Hibiki-Zero 相比 Hibiki 最主要的改进是：

- A. 改用 EnCodec，音质更好
- B. 不再需要词级对齐的训练数据，改用句级数据 + GRPO 强化学习优化延迟
- C. 把延迟降到了 20 ms
- D. 支持工具调用

---

## 三、动手 / 代码题

**Q9.**（预测输出 + 找 bug）运行 `main.py` 后，"per-frame latency" 一节大致会打印什么数量级？这些毫秒数主要来自哪里？另外，这一行实际打印出来的文字和作者的本意有什么出入？

```python
    print(f"  mean: {avg:.2f} ms   p95: {p95:.2f} ms   target: &lt; 80 ms per frame (realtime)")
```

**Q10.**（找 bug + 解释）`main.py` 用下面的函数"编码"用户音频，用户音频由 `simulate_user_speech` 生成：每帧 1920 个样本，幅度固定 0.15，频率从 220 Hz 每帧递增 20 Hz。

```python
def fake_mimi_encode(audio_80ms):
    s = sum(abs(x) for x in audio_80ms) / max(1, len(audio_80ms))
    rng = random.Random(int(s * 1000))
    return [rng.randint(0, 1023) for _ in range(CODEBOOKS)]
```

25 帧用户音频会被编码成多少种不同的 token 组合？为什么？请改写这个函数，让"内容不同的帧"大概率得到不同的 token（仍然只用标准库）。

**Q11.**（对照讲义解释代码顺序）主循环的核心如下：

```python
        user_tokens = fake_mimi_encode(user_chunk)
        user_mimi.append(user_tokens)

        next_text = inner_monologue_next_token(moshi_text, user_mimi)
        moshi_text.append(next_text)

        next_moshi_tokens = depth_transformer(
            context_text=moshi_text,
            context_user_mimi=user_mimi,
            context_moshi_mimi=moshi_mimi,
        )
        moshi_mimi.append(next_moshi_tokens)
```

(a) 在第 t 步调用 `depth_transformer` 时，`moshi_text`、`user_mimi`、`moshi_mimi` 分别包含哪些下标？与讲义 Step 3 的 "Input / Predict" 是否一致？
(b) 如果把"`moshi_text.append(next_text)`"挪到 `depth_transformer` 调用之后，会破坏 Moshi 的哪个设计？
(c) 这段代码没有体现"80 ms 声学延迟"。如果要模拟它，你会怎么改？

---

## 四、面试高频题

**Q12.**（基础必考）对比"级联式语音 agent（VAD + ASR + LLM + TTS）"和"端到端全双工模型（Moshi）"：延迟、能力、可控性、工程成本分别怎么取舍？

**Q13.**（原理深挖）Moshi 的 inner monologue 是什么？为什么文本 token 要先于音频 token 预测？Depth Transformer 解决了什么问题？

**Q14.**（原理深挖）讲清楚 Moshi 的延迟账：理论 160 ms 从哪来，为什么实测是 200 ms？为什么流水线方案很难低于 300 ms？

**Q15.**（场景设计）设计一个英法双语的语言学习陪练应用：要求 < 250 ms 响应、偶尔需要"给出语法提示 / 翻译一句话"这类工具能力。你会怎么设计架构？

**Q16.**（追问型 / 容量规划）上题的应用有 1 万日活，高峰并发率 10%。假设一张 L4 能稳定承载 4–6 个 Moshi 会话，高峰需要多少张 GPU？全双工模型在部署上还有什么特殊挑战？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Theoretical latency 160 ms (80 ms Mimi frame + 80 ms acoustic delay)."——模型至少要攒满一个 80 ms 的 Mimi 帧才能处理，声学 token 相对语义又有一帧的延迟。实际在单张 L4 上约 200 ms，多出来的是计算与 I/O 开销。A、C 描述的是流水线思维；D 混入了第 14 节的 flush trick 数字。

### Q2 — 答案：B

讲义 Step 3："Predict: `moshi_text[t]`, then `moshi_mimi[t, codebook_0..7]`. Text is predicted before audio (inner monologue); audio is predicted codebook-sequential within the depth transformer." D 错在 Moshi 并不预测用户的音频，用户音频是输入。

### Q3 — 答案：B

Mimi 用 RVQ：码本 k 量化的是前 k−1 级留下的残差，所以码本之间强相关（参见第 13 节）。并行独立地预测 8 个码本，会出现"每个码本单独看都合理、合起来却对不上"的情况。小 Depth Transformer 在一帧之内顺序预测 8 个码本（讲义说这是 AR codec LM 的标准分解，VALL-E、VibeVoice 也用），而大的 Temporal Transformer 只需每 80 ms 走一步。

### Q4 — 答案：D

讲义列出的好处是：提升语义连贯性、免费获得转写、更容易替换语言模型头。工具调用恰恰是 Moshi 的短板（"Tool calling (not trained for it; you need a separate LLM path)"）。

### Q5 — 答案：B

讲义："Sesame CSM (2025) uses a similar idea — a Llama-3 backbone with a Mimi codec head. But CSM is single-directional (takes context + text, produces speech) rather than full-duplex." 它是"最有临场感的 TTS"，但不是全双工。

### Q6 — 答案：B

讲义的 Use It 表："Enterprise agent with tools → Pipeline (Lesson 12), not Moshi"；skill 中也明确拒绝"只用全双工"来做需要工具调用 / 检索的企业 agent。混合方案（全双工负责对话手感，外部 LLM 负责工具调用）是常见折中。

### Q7 — 答案：C

每路每秒 12.5 帧 × 8 码本 = 100 个 token，两路共 200 个；如果再算上文本流，每秒还有 12.5 个文本 token。A 只算了一路的帧数；D 是第 13 节"10 秒单路"的数字。

### Q8 — 答案：B

讲义："Hibiki-Zero (Feb 2026) eliminates the need for word-level aligned training data — uses sentence-level data + GRPO reinforcement learning for latency optimization." 它依然基于 Mimi，也依然不做工具调用。

### Q9 — 参考答案

实测一次的输出（每次运行会有零点几毫秒的波动）：

```text
=== per-frame latency ===
  mean: 5.84 ms   p95: 6.46 ms   target: &lt; 80 ms per frame (realtime)
```

- 数量级是**每帧约 5–7 ms**。其中 5 ms 是两个 stub 里**故意写的 `time.sleep`**（`inner_monologue_next_token` 睡 2 ms，`depth_transformer` 睡 3 ms），剩下不到 1 ms 是 `fake_mimi_encode` / `fake_mimi_decode` 里对 1920 个样本的纯 Python 循环。也就是说这个"延迟"测的是模拟出来的占位耗时，不代表真实模型。
- 本意：每帧代表 80 ms 音频，处理一帧必须**少于 80 ms**才能跟上实时（实时因子 RTF = 5.84 / 80 ≈ 0.07）。
- 出入：字符串里写的是 HTML 实体 `&lt;`，Python 不会做 HTML 转义，所以终端上打印的就是字面量 `&lt; 80 ms`，而不是 `< 80 ms`。应改为 `target: < 80 ms per frame (realtime)`。这类问题通常是把代码从 HTML / Markdown 渲染结果中复制回来时引入的。

### Q10 — 参考答案

**只有 1 种。** 每帧都是幅度 0.15 的正弦，`mean(|0.15·sin|) ≈ 0.15 × 2/π ≈ 0.0955`，几乎与频率无关（每帧包含 17 个以上完整周期，平均绝对值很稳定）。于是 `int(s * 1000)` 对 25 帧都等于 **95**，随机数种子相同，生成的 8 个 token 也完全相同（实测 25 帧 → 1 种组合）。这个"编码器"只看了平均能量，丢掉了频率信息。

改写思路：让种子依赖帧的**完整内容**，例如对量化后的样本做稳定哈希：

```python
import hashlib


def fake_mimi_encode(audio_80ms):
    quantized = bytes((int((x + 1.0) * 127.5) & 0xFF) for x in audio_80ms)
    digest = hashlib.sha256(quantized).digest()
    return [int.from_bytes(digest[2 * k: 2 * k + 2], "big") % 1024 for k in range(CODEBOOKS)]
```

- 先把 [-1, 1] 的浮点样本量化到 0–255 的字节（同时 `& 0xFF` 防越界），再算 SHA-256，取前 16 字节拆成 8 个 0–1023 的整数。
- 不用内置 `hash()`：字符串 / 字节的 `hash()` 每次进程启动会随机加盐（`PYTHONHASHSEED`），结果不可复现；`hashlib` 是确定性的。
- 注意这仍然只是"占位"：真正的 Mimi 是学出来的编码器 + RVQ，相似的音频会得到相似的 token，而哈希恰恰相反（输入差一点，输出完全不同）。

### Q11 — 参考答案

(a) 第 t 步（t 从 0 开始）调用 `depth_transformer` 时：

| 变量 | 包含的下标 | 讲义 Step 3 |
|------|-----------|------------|
| `user_mimi` | `0..t`（本步刚 append 了第 t 帧） | Input: `user_mimi[0..t]` ✔ |
| `moshi_mimi` | `0..t-1`（第 t 帧尚未 append） | Input: `moshi_mimi[0..t-1]` ✔ |
| `moshi_text` | `0..t`（本步的文本 token 已经 append） | 先预测 `moshi_text[t]`，再以它为条件预测音频 ✔ |

调用 `inner_monologue_next_token` 时 `moshi_text` 还是 `0..t-1`，正好对应 "Input: `moshi_text[0..t-1]` → Predict `moshi_text[t]`"。所以代码的**append 顺序**精确编码了讲义的条件依赖。

(b) 那样音频 token 就看不到本步的文本 token，破坏了"**先文本、后音频**"的 inner monologue 设计——文本流本来是给音频生成提供"我接下来要说什么"的语义规划；挪到后面，文本就变成了对音频的事后描述。

(c) 一种做法是让声学码本（1–7）比语义码本（0）晚一帧输出：第 t 步生成 `moshi_mimi[t]` 的码本 0 和 `moshi_mimi[t-1]` 的码本 1–7，第 t 帧的完整音频要到第 t+1 步才能解码。这样第一帧可播放的音频出现在"用户第 0 帧到达（80 ms）+ 再等一帧（80 ms）"之后，正好对应 160 ms 的理论下限。代码上可以维护一个 `pending_acoustic` 变量保存上一帧的码本 0，在下一步补齐码本 1–7 后再调用 `fake_mimi_decode`。

### Q12 — 参考回答要点

| 维度 | 级联流水线 | 全双工（Moshi） |
|------|-----------|----------------|
| 延迟 | 每级都有最小延迟，地板约 300–500 ms | 理论 160 ms，L4 上约 200 ms |
| 对话手感 | 半双工，需 VAD / turn detector 管轮次；插话处理靠工程 | 天然边听边说，支持插话、附和（"mhm"） |
| 智能与工具 | 可接任意最强 LLM，工具调用、RAG、长推理都方便 | 约 7–8B 对话模型，工具调用、长推理、冷门事实都弱 |
| 可控性 | 每级可单独替换、调试、审计（有中间文本） | 一体化，调试难；有 inner monologue 可看文本 |
| 语言/音色 | 继承 LLM 多语言能力；TTS 可换音色 | 法英为主；单一人设，换声音要重新训练 |
| 部署 | 各级可共享、可弹性扩缩 | 每个会话占一个 GPU 槽位，不适合廉价多租户 |

- 结论：陪聊、同传等"对话手感优先"的场景用全双工；企业 agent 需要工具、检索、合规审计时用流水线或混合。
- 加分点：说出商业全双工 API（GPT-4o Realtime 约 300 ms、Gemini 2.5 Live 约 350 ms）是另一个折中——延迟略高但能力更强。

### Q13 — 参考回答要点

- inner monologue：Moshi 在输出音频的同时输出一条文本流，基本就是它自己所说内容的转写。
- 为什么需要：没有显式文本时，模型必须在声学 token 里隐式地建模语言，难度大、容易语义漂移。强制先出文本，相当于"先想好说什么再发声"。
- 为什么文本在前：音频 token 以本步的文本 token 为条件，文本提供语义规划；讲义 Step 3 的顺序正是 `text[t]` → `mimi[t, 0..7]`。
- 附带好处：免费转写（便于日志、审核、做字幕）、更容易替换语言模型头。
- Depth Transformer：帧内 8 个 RVQ 码本互相依赖，需要按顺序预测；如果把 8 个码本平铺到时间轴，序列长度变成 8 倍。拆成"大 Temporal Transformer 每 80 ms 走一步 + 小 Depth Transformer 在帧内走 8 步"，既保留依赖又控制计算量。
- 常见误区：以为 inner monologue 是"先 ASR 再 TTS"——它与音频在同一个模型里同步生成，不是串行阶段。

### Q14 — 参考回答要点

- 理论 160 ms：模型至少要拿到一个完整的 80 ms Mimi 帧才能开始处理（帧率 12.5 Hz），再加上声学 token 相对语义的一帧（80 ms）延迟。
- 实际 200 ms：在单张 L4 上加上 Temporal / Depth Transformer 的计算、Mimi 编解码、网络与音频 I/O 开销。
- 流水线地板：VAD 判定结束需要静音 hangover（第 14 节：500–800 ms，加语义 turn detector 可缩短）；STT 有 look-ahead（可用 flush trick 压缩）；LLM 有首 token 延迟；TTS 有首包延迟（TTFA）。各级串行相加，讲义给出的地板约 300–500 ms。
- 加分点：全双工模型根本不需要"判断用户说完了没有"这一步——它每 80 ms 都在决定"现在要不要说、说什么"，这才是延迟优势的根本来源。

### Q15 — 参考回答要点

（与本节 skill 示例一致）

- 架构：全双工（Moshi）为主。< 250 ms 的响应要求 + 以开放式对话为主，正是 Moshi 的强项；英法两种语言都是 Moshi 的强项。
- 工具：只有"语法提示""翻译这句"这类轻量能力，可以路由给一个小 LLM sidecar，结果以文本卡片展示或插回对话，不让工具调用阻塞语音主链路。
- 语言扩展：如需西 / 德 / 日，可考虑 Hibiki-Zero 式的适配，每种新语言约 1000 小时音频。
- 许可：Moshi 为 CC-BY 4.0，商用需遵守署名要求。
- 降级路径：网络或 GPU 紧张时，回退到"本地 ASR + 轻量 TTS"的半双工模式（skill 中提到用 Kyutai Pocket TTS 做端侧轻量模式）。
- 常见误区：为了"语法提示"这一小需求就整体换成流水线，牺牲了产品的核心卖点（低延迟、自然打断）。

### Q16 — 参考回答要点

- 计算：高峰并发 = 10,000 × 10% = **1,000 个会话**；每张 L4 承载 4–6 个 → 约 **167–250 张 GPU**，再留 20–30% 余量。（注意：本节 skill 文件示例写的是"~1500 GPUs"，按它自己给出的假设算不出这个数，应以计算为准。）
- 部署挑战：
  1. **会话粘性**：全双工会话在整个对话期间独占一个 GPU 槽位（讲义 Pitfall："A full Moshi session holds a GPU slot"），不能像无状态请求那样随意负载均衡。
  2. **并发上限**：单卡会话太多会争抢算力，导致每帧处理超过 80 ms、出现卡顿；skill 中建议单 GPU 不要超过约 4 个会话，需压测确定。
  3. **冷启动**：新开实例加载 7B 级模型较慢，要预热池。
  4. **成本**：空闲（用户沉默）时 GPU 仍被占用，需要会话超时与回收策略。
- 加分点：把关键指标定为"每帧处理时间 P95 < 80 ms"，以它驱动扩缩容，而不是 GPU 利用率。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：Mimi 的 12.5 Hz、8 码本、语义 / 声学分离是 Moshi 的地基。
- [阶段 06 · 11 实时音频处理](../../11-real-time-audio-processing/docs/zh.md)：帧、缓冲、实时因子。
- [阶段 07 · 05 完整的 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：Temporal / Depth Transformer 的基础。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：本节要对比的"流水线"方案。
- [阶段 06 · 14 语音活动检测与对话轮次交接](../../14-voice-activity-detection-turn-taking/docs/zh.md)：流水线方案中轮次判断与 flush trick 的延迟来源。

### 本节被哪些后续内容用到
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：如何评估 S2S 模型的延迟与质量。
- [阶段 12 · 16 MIO 任意模态流式](../../../12-multimodal-ai/16-mio-any-to-any-streaming/docs/zh.md)：多模态模型中的流式 token 生成。
- [阶段 12 · 20 Omni 模型 Thinker-Talker](../../../12-multimodal-ai/20-omni-models-thinker-talker/docs/zh.md)：另一种"边想边说"的架构。
- [阶段 14 · 22 语音 Agent（Pipecat / LiveKit）](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：生产语音 agent 中流水线与实时 API 的取舍。
- [阶段 19 · 03 实时语音助手（毕业项目）](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：端到端实践。
- [阶段 09 · 08 PPO](../../../09-reinforcement-learning/08-ppo/docs/zh.md)：理解 Hibiki-Zero 使用的 GRPO 这一类策略优化方法。

### 延伸关键词
`full-duplex` · `inner monologue` · `RQ-Transformer / Depth Transformer` · `acoustic delay` · `back-channeling` · `barge-in` · `Delayed Streams Modeling` · `Kyutai Unmute` · `GPT-4o Realtime` · `Gemini Live` · `simultaneous speech translation`
