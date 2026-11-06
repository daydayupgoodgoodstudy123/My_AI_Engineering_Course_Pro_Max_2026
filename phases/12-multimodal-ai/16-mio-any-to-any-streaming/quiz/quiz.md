# 测验 · MIO 与任意模态互转的 Streaming Multimodal Models（MIO and Any-to-Any Streaming Multimodal Models）

> **阶段 12 · 多模态 AI · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Any-to-any 的含义 | 一个模型接收并输出文本、图像、语音、音乐中的任意组合；MIO 把四种模态都 token 化，用**一个**因果 Transformer 在交错序列上训练 |
| 2 | 管线式 vs 单模型 | 管线（视觉模型 → 文本 → 语音模型）每一跳都丢信息、加延迟、难联合训练；GPT-4o 展示了单模型、亚秒级响应的可能 |
| 3 | 四个 tokenizer | 文本 BPE（约 32K）、图像 SEED-Tokenizer（4,096 码本）、语音 SpeechTokenizer 残差 VQ（8 层码本）、音乐 Encodec 类残差 VQ（4–8 层） |
| 4 | 共享词表 | 各模态占据**互不重叠**的 ID 区间，再加若干分隔标签；讲义合计约 48K；输入 embedding 与输出投影覆盖整个词表 |
| 5 | 残差 VQ（RVQ） | 第 0 层是粗粒度内容，后面各层逐级补充韵律、说话人等细节；主干只预测第 0 层，后续层由并行的残差解码器补齐 |
| 6 | 流式解码 | 麦克风音频实时 token 化 → 增量 prefill → 输出 token 边生成边送入语音解码器 → 播放 |
| 7 | TTFAB | time-to-first-audio-byte：从用户说完到听见第一段音频；< 500 ms 才有对话感；讲义：GPT-4o 约 250 ms、Moshi 160 ms、MIO/AnyGPT 400–600 ms |
| 8 | 四阶段课程 | 对齐（模态对）→ 交错文档 → 语音增强 → SFT；跳过阶段 2 失去跨模态上下文，跳过阶段 3 语音变差 |
| 9 | Chain-of-visual-thought | 先生成中间图像 token 当"草稿纸"，再分析、再作答；空间推理收益明显，但增加延迟 |
| 10 | 同类方案 | AnyGPT（概念前身）、Unified-IO 2（加入动作、深度、法线）、NExT-GPT（LLM + 各模态扩散解码器，非单模型）、CoDi（可组合扩散） |

### 核心技能（能动手做到）

- [ ] 设计一个多模态共享词表：给每种模态分配不重叠的 ID 区间，算出总词表大小与 embedding 参数量
- [ ] 解释残差 VQ 的分层含义，并说明为什么残差层要并行解码
- [ ] 列出语音对话产品 TTFAB 的各项组成，按讲义数字估算总延迟，并判断是否达到对话标准
- [ ] 读懂 `code/main.py` 的 `build_vocab` / `streaming_decode_latency`，指出词表比讲义多出 4,096、延迟模型对 prompt 长度的依赖方向反了
- [ ] 说清四阶段课程每个阶段的数据与目的，以及缺失某阶段的后果
- [ ] 在 MIO/AnyGPT、Moshi、Unified-IO 2、管线式方案之间按延迟和质量要求做选型

---

## 二、基础自测（选择题）

**Q1.** 关于 MIO 的整体设计，正确的是：

- A. 每种模态一个独立的 Transformer，最后用投票合并输出
- B. 文本、图像、语音、音乐各用自己的 tokenizer 转成整数 token，放进同一个共享词表，用一个因果 Transformer 在交错序列上训练与生成
- C. 只有文本走 Transformer，其余模态用扩散解码器生成
- D. 用 CLIP 把所有模态映射到同一个连续向量空间，再做回归

**Q2.** 共享词表中各模态 token 必须分配**互不重叠**的 ID 区间，主要原因是：

- A. 让 embedding 矩阵更小
- B. 让 BPE 合并更快
- C. 方便 GPU 并行
- D. 同一个整数必须只代表一种东西；否则模型无法区分"图像码 17"和"语音码 17"，输出 softmax 时也无法知道自己生成的是哪个模态

**Q3.** 关于 SpeechTokenizer 的残差 VQ，下列说法正确的是：

- A. 第 0 层承载粗粒度内容，后续层逐步补充韵律和说话人特征；主干预测第 0 层，后续层由并行的残差解码器补齐
- B. 8 层码本彼此独立，分别编码 8 个不同的说话人
- C. 只有最后一层包含语义内容
- D. 残差层必须由主干逐层串行生成，否则无法解码

**Q4.** 讲义练习 3：词表为 32,000 文本 + 4,096 图像 + 4,096 语音 + 8,192 音乐 + 10 个分隔符。隐藏维 4,096 时，**输入 embedding 矩阵**约多少参数？

- A. 约 131M
- B. 约 168M
- C. 约 198M
- D. 约 396M

**Q5.** MIO 四阶段训练课程的正确顺序是：

- A. SFT → 对齐 → 交错 → 语音增强
- B. 交错 → 对齐 → SFT → 语音增强
- C. 语音增强 → 交错 → 对齐 → SFT
- D. 对齐 → 交错 → 语音增强 → SFT

**Q6.** 讲义认为语音对话要有"对话感"，TTFAB 应低于：

- A. 50 ms
- B. 500 ms
- C. 2 秒
- D. 5 秒

**Q7.** 关于 chain-of-visual-thought，正确的是：

- A. 模型先生成一张中间图像（token）作为推理草稿，再输出文本分析和最终答案；对空间推理有帮助，但增加延迟
- B. 模型在回答前检索一张网络图片
- C. 它是一种图像压缩算法
- D. 它只在训练时使用，推理时会被关掉

**Q8.** 讲义列出的 any-to-any 竞品中，哪一个**不是**单模型、纯 token 的方案？

- A. AnyGPT
- B. MIO
- C. NExT-GPT
- D. 以上都是单模型纯 token 方案

---

## 三、动手 / 代码题

**Q9.** 运行 `build_vocab()` 得到的布局（节选）：

```text
  slot                 start     end    size
  text BPE                 0   32000   32000
  image SEED           32000   36096    4096
  speech L0            36096   40192    4096
  speech L1..L7        40192   44288    4096
  music                44288   52480    8192
  <image>              52480   52481       1
  ...
  TOTAL                52486    (vocab size)
```

1. 讲义给出的布局总计约 48K，代码为什么是 52,486？差在哪里？
2. 讲义说"The transformer predicts the base (layer 0) speech tokens; a parallel-decoded residual quantizer predicts the subsequent layers"。按这个说法，`speech L1..L7` 这个槽位需不需要放进主干的词表？如果真的要让主干输出 L1..L7，一个 4,096 的槽位够用吗？
3. 代码表中的 `end` 与讲义 `text: 0..31999` 的写法差 1，为什么两者不矛盾？

**Q10.** 阅读延迟模型：

```python
def streaming_decode_latency(prompt_audio_seconds=2.0, model_size_b=8):
    trace.append(LatencyTrace("mic audio -> speech tokens", prompt_audio_seconds * 20))
    trace.append(LatencyTrace("prefill prompt tokens", 80 * (model_size_b / 8.0)))
    trace.append(LatencyTrace("first output token", 40 * (model_size_b / 8.0)))
    trace.append(LatencyTrace("residual-VQ layers 1..7", 30))
    trace.append(LatencyTrace("speech decoder (Encodec-like)", 80))
```

1. 用户说了 30 秒的话，代码估算的 TTFAB 是多少？其中哪一项最大？
2. 在**流式**系统中，"mic → speech tokens" 应该随整段语音时长增长吗？"prefill" 又应该和什么成正比？代码的依赖关系有什么问题？
3. 请改写这两项，使它们符合流式系统的实际。

**Q11.** 代码默认参数下输出 `total TTFAB: 270 ms` 并打印 `-> conversational feel (GPT-4o-class)`。

1. 按讲义 "Latency budget" 一节的数字（mic 约 50、prefill 约 100、首 token 约 50、残差 VQ + 语音解码约 100–150 ms）重新求和，结果是多少？与代码的 270 ms 相比如何？
2. 讲义还说 "MIO/AnyGPT are in the 400-600ms range per public benchmarks"，outputs 技能文件把 "Claiming MIO's TTFAB matches GPT-4o" 列为硬性拒绝项。代码的结论有什么问题？
3. （讲义练习 2）如果 7 个残差层**串行**由主干生成，每层一次前向约 40 ms（与代码"first output token"相同），首段音频要多等多久？并行解码为什么能省掉这部分？

**Q12.** 阅读路由函数：

```python
        if kind == "text":
            path = "BPE"
        elif kind == "image":
            path = "SEED-Tokenizer"
        elif kind in ("speech", "voice"):
            path = "SpeechTokenizer residual-VQ"
        elif kind == "music":
            path = "Encodec"
        else:
            path = "UNKNOWN"
```

1. 输入 `{"kind": "Speech"}` 和 `{"kind": "video"}` 会得到什么？这在生产中有什么风险？
2. 用字典重写路由，并让未知模态显式报错。
3. 如果要支持视频，你会把它路由到哪个 tokenizer？需要在词表里新增什么？

---

## 四、面试高频题

**Q13.**（基础必考）语音助手可以做成 "ASR → LLM → TTS" 管线，也可以做成 MIO/GPT-4o 式的端到端 any-to-any 模型。两者各有什么优缺点？

**Q14.**（原理深挖）为什么语音要用残差 VQ（多层码本）而不是单层 VQ？主干和残差解码器怎么分工？为什么残差层要并行解码？

**Q15.**（工程实践）请为一个"语音进、语音出"的对话产品拆解 TTFAB 预算，并给出把它压到 300 ms 以内的优化手段。

**Q16.**（场景设计）你要从零设计一个支持文本、图像、语音、音乐的 any-to-any 模型：词表怎么设计？训练课程怎么排？哪些地方最容易出问题？

**Q17.**（追问型）讲义练习 5：MIO 的 chain-of-visual-thought 和 Moshi 的 "inner monologue" 有什么异同？什么样的问题会因为额外的中间 token 反而变差？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："MIO tokenizes text, image, speech, and music, trains one causal transformer over the interleaved sequences, and generates any modality to any modality." A 是集成而非单模型；C 是 NExT-GPT 一类"LLM + 扩散解码器"的做法；D 是对比学习，不是生成模型。

### Q2 — 答案：D

讲义："The tokens get disjoint ID ranges in the shared vocabulary." 每个 ID 对应 embedding 矩阵中唯一一行、输出层唯一一个 logit；若区间重叠，同一个整数既是图像码又是语音码，embedding 无法区分，生成时也不知道该交给哪个解码器。A 恰好相反（区间不重叠会让词表更大）；B、C 与此无关。

### Q3 — 答案：A

讲义："first level is coarse content, later levels add prosody and speaker identity"，以及 "The transformer predicts the base (layer 0) speech tokens; a parallel-decoded residual quantizer predicts the subsequent layers." B 误解了"层"的含义（每层都描述同一段音频，只是逐级补充残差）；C 说反了；D 与讲义"并行解码"相反。

### Q4 — 答案：C

`32,000 + 4,096 + 4,096 + 8,192 + 10 = 48,394`，`48,394 × 4,096 ≈ 198.2M`（已用 Python 计算；若按"32k + 4k + 4k + 8k"的整千口径为 48,010，约 196.6M，同样最接近 C）。D 是输入 embedding 与**不共享**的输出投影合计（×2）；A 只算了文本部分；B 无对应。若按代码的 52,486 词表则为 215M。

### Q5 — 答案：D

讲义 Four-stage curriculum：Stage 1 alignment → Stage 2 interleaved → Stage 3 speech-enhanced → Stage 4 SFT，Key Terms 也写 "Alignment -> interleaved -> speech-enhanced -> SFT, in that order"。先建立各模态与文本的对齐，再学跨模态上下文，再专项提升语音，最后指令微调。

### Q6 — 答案：B

讲义 Key Terms："<500ms for conversational feel"；Problem 一节也写 "<500ms time-to-first-audio-byte"。A 连麦克风编码都不够；C、D 是"能用但明显卡顿"的量级。

### Q7 — 答案：A

讲义："the model emits intermediate image tokens as a reasoning step... The rendered intermediate image serves as a scratchpad. Benchmarks improve on spatial-reasoning tasks." 代码 `demo_chain_of_visual_thought` 也打印 "wins on spatial-reasoning benchmarks; hurts latency."

### Q8 — 答案：C

讲义："NExT-GPT: LLM + modality-specific diffusion decoders. Not a single-model approach." AnyGPT 与 MIO 都是纯 token、单模型（"MIO is the closest to pure-token any-to-any. AnyGPT is its conceptual ancestor."）。CoDi 是通过共享 latent 的可组合扩散，也不是纯 token 方案。

### Q9 — 参考答案

1. 代码比讲义多了一个 `speech L1..L7` 槽位（4,096）：讲义布局 `text 32000 + image 4096 + speech 4096 + music 8192 + 7 个分隔符 ≈ 48,391`，代码 `48,390 + 4,096 = 52,486`（代码只有 6 个分隔符）。讲义的 `speech` 区间写着 "plus residual layers"，但没有为残差层分配 ID。
2. **不需要**。如果残差层由主干之外的并行残差解码器预测，主干只需输出 L0，残差码从不作为主干的输入/输出 token，自然不占词表。反过来，如果确实要让主干生成 L1..L7，那么 7 层各有自己的码本（每层 K 个码字），需要 `7 × K` 个 ID（K = 4,096 时为 28,672），或者使用"码本层号 + 码字"的分组输出头；一个共享的 4,096 槽位会让"第 2 层的码 5"和"第 6 层的码 5"变成同一个 ID，信息丢失。这个槽位在概念上是自相矛盾的。
3. 代码的 `end = start + size` 是**半开区间** `[start, end)`：文本 `[0, 32000)` 就是 0..31999，与讲义的闭区间写法一致。Python 的 `range(start, end)` 和切片都是这个约定。

### Q10 — 参考答案

1. 已实际运行 `streaming_decode_latency(30, 8)`：`[600, 80, 40, 30, 80]`，合计 **830 ms**，其中 "mic → speech tokens" 600 ms 最大，判定为 "acceptable (first-gen open any-to-any)"。
2. 依赖关系**反了**：
   - **mic 编码**：流式系统中音频每 20–50 ms 就被 token 化一次，用户说话期间已经在持续编码；用户停下后只剩**最后一个 chunk** 要处理，延迟应是常数（讲义约 50 ms），与总时长无关。
   - **prefill**：流式系统可以在用户说话的同时增量 prefill（讲义："MIO consumes tokens as they arrive (prompt prefill + incremental forward)"），停顿后只需处理最后几个 token；若是非流式一次性 prefill，耗时应与**prompt token 数**（含历史对话）成正比。代码却让 prefill 只随模型大小变化、与 prompt 长度无关。
3. 改写示例：

   ```python
   def streaming_decode_latency(prompt_audio_seconds=2.0, model_size_b=8,
                                chunk_ms=50, streaming_prefill=True, tokens_per_s=50):
       trace = [LatencyTrace("mic tail chunk -> speech tokens", chunk_ms)]
       n_prompt = prompt_audio_seconds * tokens_per_s
       if streaming_prefill:
           prefill = 20 * (model_size_b / 8.0)                  # 只剩尾部少量 token
       else:
           prefill = 0.8 * n_prompt * (model_size_b / 8.0)      # 与 token 数成正比（示意系数）
       trace.append(LatencyTrace("prefill (remaining) tokens", prefill))
       ...
   ```

   这里的系数是示意值，关键是"谁和谁成正比"要对。

### Q11 — 参考答案

1. `50 + 100 + 50 + (100~150) = 300~350 ms`，讲义原话 "Total time-to-first-audio-byte: ~300ms minimum"。代码的各项（40、80、40、30、80）都比讲义小，合计 270 ms，低于讲义给出的"最低值"。
2. 代码用一组偏乐观的数字算出 270 ms，就宣称 "GPT-4o-class"，与讲义 "MIO/AnyGPT are in the 400-600ms range" 矛盾，也正好落入技能文件的硬性拒绝项。教训：延迟预算的结论必须基于实测或可引用的数字，玩具模型的阈值判断不能当作对真实系统的评价。另外讲义自身也有不一致：前文说 "~300-500ms in MIO paper"，后文说 "400-600ms range per public benchmarks"。
3. 串行：每段音频的首帧要多 7 次主干前向，`7 × 40 = 280 ms`，TTFAB 从 270 ms 涨到 520 ms 左右（代码中的 30 ms 换成 280 ms），直接越过 500 ms 的对话线。并行解码之所以可行，是因为在第 0 层已确定的前提下，残差层只需补细节，可以用一个轻量的残差解码器（或一次前向输出多层）同时预测，而不必让大主干走 7 步；代价是残差层之间的依赖被近似，音质略降。

### Q12 — 参考答案

1. `"Speech"`（大写）不在 `("speech", "voice")` 里，`"video"` 也没有分支，二者都得到 `"UNKNOWN"`（已实际运行验证）。风险：数据被**静默**地送到一个不存在的 tokenizer，上游拼写或大小写的小问题不会立刻报错，而是在下游变成难以排查的空输出或垃圾 token。
2. 改写：

   ```python
   TOKENIZER_BY_KIND = {
       "text": "BPE",
       "image": "SEED-Tokenizer",
       "speech": "SpeechTokenizer residual-VQ",
       "voice": "SpeechTokenizer residual-VQ",
       "music": "Encodec",
   }

   def route_inputs(inputs):
       routed = []
       for inp in inputs:
           kind = inp["kind"].strip().lower()
           if kind not in TOKENIZER_BY_KIND:
               raise ValueError(f"unsupported modality: {inp['kind']!r}")
           routed.append({**inp, "path": TOKENIZER_BY_KIND[kind]})
       return routed
   ```

3. 视频的两种常见做法：①逐帧（或抽帧）用图像 tokenizer，加上 `<frame>`/时间戳分隔符；②用 3D 时空 tokenizer（参见第 12 节 Emu3），需要新增一段视频码本 ID 区间和 `<video>`/`</video>` 标签。音轨则另走语音/音乐 tokenizer，与视频帧交错排列。

### Q13 — 参考回答要点

- **管线式（ASR → LLM → TTS）**：
  - 优点：每个组件可独立选型、替换、评估；可直接用最强的 LLM 和商用 TTS；工程成熟、可控性好。
  - 缺点：讲义 "Each hop loses information, adds latency"——语气、情绪、停顿、背景声在 ASR 处丢失；延迟逐级叠加；无法自然处理打断、重叠说话。
- **端到端 any-to-any**：
  - 优点：保留副语言信息；一次前向即可开始流式输出，延迟更低；支持跨模态任务（看图说话、对着画面唱歌）。
  - 缺点：讲义 "Why any-to-any stays hard"——开源模型语音质量（残差 VQ 有损，"robotic"）和跨模态推理仍落后；训练数据与课程复杂；难以单独升级某个模态。
- 选型：技能文件拒绝项 "Proposing separate models per modality when the requirement is conversational fluidity"；而需要录音棚级音质时又应拒绝开源 RVQ、改用 ElevenLabs 类 TTS 管线。

### Q14 — 参考回答要点

- **为什么多层**：单层 VQ 要同时编码内容、音色、韵律，码本需要极大才能达到可接受的音质；RVQ 逐层量化前一层的残差，用多个小码本的组合表达指数级的状态，码率可调。技能文件："Using a speech tokenizer with only 1 codebook layer. Quality will be robotic" 是拒绝项。
- **分层含义**：SpeechTokenizer 的第 0 层偏语义内容（"说了什么"），后续层补韵律、说话人（"怎么说、谁在说"）。
- **分工**：主干只需预测第 0 层（序列最短、语义最强，与文本最接近），后续层交给轻量的残差解码器，按第 0 层条件并行预测，再送入波形解码器。
- **为什么并行**：若主干逐层生成，每帧音频需要 8 次前向，首段音频延迟和总吞吐都恶化 8 倍量级（Q11 第 3 问：多出约 280 ms）；并行把它压到一次轻量计算。
- 加分点：其他方案还有"延迟模式（delay pattern）"把多层码本错位排列、在一次前向中同时预测多层（MusicGen 等采用），以及 Moshi 的深度 Transformer（depth transformer）分工方式。

### Q15 — 参考回答要点

- **组成**（讲义数字）：麦克风 → 音频 token 约 50 ms；prefill（音频 token + 历史）约 100 ms（8B）；首个输出 token 约 50 ms；并行残差 VQ + 语音解码器约 100–150 ms；合计约 300 ms 起。另外实际产品还要加 VAD 判定"用户说完了"的等待时间和网络往返。
- **优化手段**：
  - **流式增量 prefill**：用户说话时就把音频 token 喂进去，停顿后只剩尾部；
  - **更小/更专的模型**：技能文件："If target TTFAB <200ms, refuse MIO-scale (8B+) and recommend Moshi-class"；
  - **首包优化**：语音解码器支持小 chunk 输出，第一段音频尽早播放；
  - **残差层并行或延迟模式**；
  - **推理工程**：KV cache 复用对话历史、量化、投机解码、GPU 常驻与批处理策略；
  - **更快的 VAD / 打断检测**，避免为确认"说完"而等待过久。
- 加分点：讲义对比 GPT-4o 约 250 ms、Moshi 160 ms（单 GPU 往返）；能把每一项写成预算表并说明测量方法是加分项。

### Q16 — 参考回答要点

- **词表**：文本 BPE 区间 + 图像码本区间 + 语音第 0 层区间 + 音乐区间 + 成对分隔标签（`<image>`/`</image>` 等），全部不重叠，总量 40–50K（技能文件）。embedding 成本 `V × d`（d = 4,096 时约 2 亿参数，不共享输出层再翻倍）。残差层不进主干词表，或用分组输出头。
- **课程**：四阶段（对齐 → 交错 → 语音增强 → SFT）。每个阶段要有明确的数据配比，阶段 3 要监控文本能力不退化（讲义："lift speech quality without losing text capability"）。
- **易错点**：
  - tokenizer 码率差异巨大（语音每秒几十个 token，图像一次上千个），序列长度与上下文窗口要统一规划；
  - 模态不平衡：某些输入→输出组合（如图像 → 音乐）几乎没有成对数据，需要依赖组合泛化；
  - 分隔标签与 ID 区间要严格校验，生成时也要约束"在 `<speech>` 之后只采样语音区间的 token"（logit mask）；
  - 语音质量受 tokenizer 上限约束；
  - 延迟预算从设计之初就要定。

### Q17 — 参考回答要点

- **相同点**：都让模型在输出最终结果前先生成一段"中间表示"作为思考/对齐的支架，本质上是把 chain-of-thought 推广到非文本模态。
- **不同点**：
  - MIO 的 chain-of-visual-thought：中间产物是**图像 token**，用于空间推理（"猫是不是在爬树"），是推理时的可选步骤；
  - Moshi 的 inner monologue（练习 5 要求阅读原文）：在生成语音 token 的同时预测与之时间对齐的**文本 token**，作为语音的"内心独白"，主要提升语音内容的连贯性和语言质量，并且与流式语音生成同步进行，不额外增加串行步骤。
- **什么问题会变差**：
  - 简单事实问答、闲聊等不需要空间推理的请求——额外几百到上千个图像 token 只增加延迟和成本；
  - 对延迟敏感的实时语音对话——中间图像会显著推迟首包；
  - 生成的草图本身可能出错，错误草图会误导后续推理（"幻觉放大"）。
- 工程建议：按问题类型路由，只在空间/几何推理类问题上启用视觉草稿。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：统一词表与早期融合，本节把它扩展到语音与音乐。
- [阶段 06 · 13 神经音频编解码器 — EnCodec、SNAC、Mimi、DAC 和语义声学分离](../../../06-speech-and-audio/13-neural-audio-codecs/docs/zh.md)：残差 VQ 与语义/声学分离的基础。
- [阶段 06 · 15 Streaming 语音到语音 — Moshi、Hibiki 和全双工对话](../../../06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：Moshi 与流式语音对话。
- [阶段 06 · 12 构建语音助手管道——第 6 阶段综合项目](../../../06-speech-and-audio/12-voice-assistant-pipeline/docs/zh.md)：本节对比的 ASR → LLM → TTS 管线。
- [阶段 12 · 12 Emu3：通过下一 Token 预测生成图像与视频](../../12-emu3-next-token-for-generation/docs/zh.md)：离散 token 生成与 3D 视频 tokenizer。

### 本节被哪些后续内容用到
- [阶段 12 · 19 音频语言模型：从 Whisper 到 Audio Flamingo 3 的演进](../../19-audio-language-whisper-to-af3/docs/zh.md)：音频理解侧的发展。
- [阶段 12 · 20 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工](../../20-omni-models-thinker-talker/docs/zh.md)：讲义提到的 Qwen-Omni 系列，另一种流式全模态架构。
- [阶段 06 · 14 语音活动检测与对话轮次交接——Silero、Cobra 与 Flush Trick](../../../06-speech-and-audio/14-voice-activity-detection-turn-taking/docs/zh.md)：TTFAB 中常被忽略的 VAD 等待时间。
- [阶段 19 · 03 综合项目 03：实时语音助手——从 ASR 到 LLM 再到 TTS](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：把延迟预算落到工程实现。

### 延伸关键词
`any-to-any` · `shared vocabulary` · `residual VQ (RVQ)` · `SpeechTokenizer` · `SEED-Tokenizer` · `Encodec` · `TTFAB` · `streaming prefill` · `delay pattern` · `inner monologue` · `chain-of-visual-thought` · `AnyGPT` · `Unified-IO 2` · `NExT-GPT`
