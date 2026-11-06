# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 08 节 语音克隆和语音转换 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`），无命令行参数 ｜ **依赖**：仅 Python 标准库（`hashlib`、`math`、`random`），没有真实的神经网络和音频

---

## 1. 这份代码在考察什么

docstring 自称是"克隆管线的乐高模型"（lego-model）：用 64 维的普通列表代替真实的音频和 embedding，把讲义里的核心思想压缩成几十行可以手算的代码：

1. **分解与重组**：语音 = 内容（content）+ 说话人（speaker）。用一个"内容向量"和一个"说话人向量"加权混合来模拟合成。
2. **探针（probe）**：用余弦相似度从混合结果里分别"认出"说话人和内容，模拟真实系统中的 speaker encoder 与内容识别。
3. **零样本克隆 vs 语音转换**：Step 2 是"文本内容 + alice 的音色"；Step 3 是"把 bob 说的话提取内容，再用 alice 重合成"。
4. **SECS**：直接计算目标说话人向量与克隆结果的余弦，对应讲义的音色相似度指标。
5. **水印的编码/解码约定**：嵌入 32 bit 载荷，再检测出来，计算位准确率。

> 一句话：**它不追求逼真，而是让"分解—交换—重组—验证—打水印"这条链路的每一步都能被打印、被检查**，读懂它就能讲清讲义的整体架构图。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `content_vector(text, dim)` | 函数 | 文本 → 确定性的 64 维向量（SHA-256 摘要） | 内容表示（docstring 称为 PPG 的替身） |
| `speaker_vector(seed, dim)` | 函数 | 种子 → 单位长度的高斯随机向量 | speaker embedding（docstring 称为 ECAPA-TDNN 的替身） |
| `fake_tts(content, speaker, mix)` | 函数 | 两个向量逐元素加权混合 | 以说话人为条件的 TTS / 重合成 |
| `extract_speaker` / `extract_content` | 函数 | 在候选字典中找余弦最高的一项 | speaker encoder / 内容识别（闭集） |
| `cosine(a, b)` | 函数 | 余弦相似度，带除零保护 | SECS 的计算方式 |
| `watermark` / `detect_watermark` | 函数 | 按位做直流偏移嵌入；与原始音频作差检测 | 音频水印（非盲的玩具版） |
| `bit_accuracy(a, b)` | 函数 | 两个比特串逐位相等的比例 | 水印检测指标 |
| `main()` | 函数 | 6 个步骤的演示 | 克隆 / 转换 / SECS / 水印 / 排行榜 |

数据流：`speaker_vector` 与 `content_vector` 生成"原料"→ `fake_tts` 混合成"音频"→ `extract_*` 和 `cosine` 做验证 → `watermark` / `detect_watermark` 打水印并检测。

---

## 3. 逐段精讲

### 3.1 `content_vector`：用哈希造一个确定性的内容表示

```python
def content_vector(text, dim=64):
    """Deterministic 'content' representation of text — toy PPG stand-in."""
    h = hashlib.sha256(text.encode()).digest()
    expanded = (h * ((dim + len(h) - 1) // len(h)))[:dim]
    return [b / 255.0 - 0.5 for b in expanded]
```

- `text.encode()` 把字符串编码成 UTF-8 字节，`sha256(...).digest()` 得到 32 字节的摘要。同一文本永远得到同一向量，不同文本的向量近似"随机且彼此无关"。
- `(dim + len(h) - 1) // len(h)` 是**向上取整除法**的经典写法：`ceil(64/32) = 2`。`h * 2` 把字节串重复两遍得到 64 字节，再切片 `[:dim]`。
- `b / 255.0 - 0.5` 把 0–255 的字节映射到 [−0.5, 0.5]，让向量大致零均值。
- ⚠️ 刻意简化：①哈希与发音毫无关系，"相似的句子"不会得到相似的向量；真实 PPG 是逐帧的音素后验概率，是一个**序列**而不是单个向量。②64 维其实只有 32 个独立数值（前后两半完全相同，已验证）。③没有做归一化，模长约 2.2–2.6，远大于单位长度的说话人向量，这直接影响后面的余弦（见 3.3）。

### 3.2 `speaker_vector`：单位长度的随机说话人 embedding

```python
def speaker_vector(seed, dim=64):
    """Deterministic 'speaker embedding' — toy ECAPA-TDNN stand-in."""
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / norm for x in v]
```

- `random.Random(seed)` 创建一个**局部**随机数生成器：同一个种子（如 `"alice_00001"`）每次生成同一个向量，又不会影响全局 `random` 状态。字符串也可以当种子。
- 高维高斯随机向量归一化后均匀分布在单位球面上，**任意两个这样的向量近似正交**（实测 `cos(alice, bob) ≈ −0.04`、`cos(alice, carol) ≈ 0.14`），用来模拟"不同人的声纹彼此可区分"。
- `... or 1e-12`：若模长为 0（实际上不可能），用一个极小数代替，防止除零。`x or y` 在 `x` 为假值（0.0）时返回 `y`。
- 真实的 ECAPA-TDNN embedding（第 06 节）也常做 L2 归一化，比较时用余弦，这一点与玩具版一致。

### 3.3 `fake_tts`：逐元素加权混合

```python
def fake_tts(content, speaker, mix=0.5):
    """Pretend TTS: element-wise mix content with speaker."""
    return [(1 - mix) * c + mix * s for c, s in zip(content, speaker)]
```

- `mix` 控制说话人成分的比重：0 表示"只有内容"，1 表示"只有音色"。
- 这模拟的是"条件生成"：输出同时携带内容信息和说话人信息，后面的探针能分别把它们找回来。
- ⚠️ 尺度不平衡：内容向量模长约 2.2–2.6，说话人向量模长 1，`mix=0.5` 时混合结果的方向主要由内容决定。所以运行结果里说话人余弦只有 0.44–0.46，内容余弦却有 0.91–0.94。实测把 `mix` 调到 0.7 左右，两者大致平衡（0.749 vs 0.708）。
- 真实系统不是简单相加：speaker embedding 通过拼接、AdaIN / FiLM 式调制或 cross-attention 注入解码器。但"条件信息需要合适的尺度才能起作用"这一点是共通的。

### 3.4 探针：`extract_speaker`、`extract_content` 与 `cosine`

```python
def extract_speaker(wave, reference_speakers):
    """Pretend speaker-encoder: return speaker with highest cosine."""
    sims = [(name, cosine(wave, vec)) for name, vec in reference_speakers.items()]
    sims.sort(key=lambda x: -x[1])
    return sims[0]

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)
```

- 对每个候选算余弦，按相似度从高到低排序（`key=lambda x: -x[1]` 取负号实现降序），返回第一名的 `(名字, 分数)` 元组。
- 这是一个**闭集识别**：答案只能是字典里已有的 alice/bob/carol。真实的说话人验证是开集的：给定阈值，判断"是不是同一个人"，并且要能拒绝陌生人（第 06 节）。
- `extract_content` 结构完全相同，只是候选换成了已知文本。
- 小优化提示：只要最大值时 `max(sims, key=lambda x: x[1])` 是 O(n)，比先排序 O(n log n) 更直接；这里候选只有 2–3 个，无所谓。

### 3.5 Step 2 与 Step 3：克隆 vs 转换

```python
    print("=== Step 2: zero-shot clone — alice's voice on bob's intended text ===")
    # bob's text + alice's speaker embedding
    wav_cloned = fake_tts(content_remind, alice, mix=0.5)
    # ...
    print("=== Step 3: voice conversion — rewrite bob's utterance into alice ===")
    wav_bob_orig = fake_tts(content_remind, bob, mix=0.5)
    # extract content, resynth with alice embedding
    matched_text, _ = extract_content(wav_bob_orig, contents)
    content_est = contents[matched_text]
    wav_converted = fake_tts(content_est, alice, mix=0.5)
```

- **Step 2（零样本克隆）**：输入是"文本内容"（这里直接用文本的内容向量）+ alice 的说话人向量，对应讲义 Step 1 的 `clone_pipeline`：`speaker_emb = target_embedder.encode(ref_audio)` → `tts_model(text, speaker=speaker_emb)`。
- **Step 3（语音转换）**：先有一段"bob 说的话"（`wav_bob_orig`），从中提取内容，再用 alice 的 embedding 重合成。这对应讲义的 **recognition-synthesis** 流派：先识别内容，再合成。
- `matched_text, _ = ...`：用 `_` 接住不需要的返回值（相似度分数），这是 Python 的惯例。
- ⚠️ 关键简化：`extract_content` 是在已知文本字典里检索，返回的 `content_est` 就是 Step 2 用过的 `content_remind` 本身，所以 `wav_converted` 与 `wav_cloned` **逐元素完全相同**（已验证），Step 3 打印的 `cos=0.462` 与 Step 2 一模一样。真实 VC 的内容表示是从音频中连续提取的（PPG、WavLM 逐帧特征），无法做到"完美还原"，也会保留源语音的韵律和时间结构；这里退化成了"识别文本 → 再 TTS"，源语音的韵律被丢掉了。

### 3.6 Step 4：SECS

```python
    secs_same = cosine(alice, wav_cloned)
    secs_diff = cosine(bob, wav_cloned)
    print(f"  alice (target) vs clone  SECS = {secs_same:.3f}  (should be high)")
    print(f"  bob (not target) vs clone SECS = {secs_diff:.3f}  (should be low)")
```

- SECS = 目标说话人 embedding 与克隆输出 embedding 的余弦。真实流程是：用 ECAPA-TDNN 之类的 speaker encoder 分别从参考音频和克隆音频中**提取** embedding，再算余弦。这里省去了"提取"这一步，直接拿混合向量算。
- 结果 0.462 vs −0.013：相对差距明显，但绝对值不高，原因还是 3.3 里的尺度问题。代码随后打印了一句参照："production ECAPA-TDNN on real clones lands SECS in 0.65 - 0.78 range"，与讲义表格中 0.65（XTTS v2）到 0.78（VoiceBox）的范围一致。
- 读数时注意：SECS 只能和**同一个 speaker encoder** 下的数值比较。

### 3.7 Step 5：玩具水印

```python
def watermark(wave, payload_bits, strength=0.003):
    n_bits = len(payload_bits)
    out = list(wave)
    for i in range(len(out)):
        bit_idx = i % n_bits
        sign = 1 if payload_bits[bit_idx] else -1
        out[i] += sign * strength
    return out

def detect_watermark(wave_original, wave_wm, n_bits=32):
    diff = [a - b for a, b in zip(wave_wm, wave_original)]
    bits = []
    for b in range(n_bits):
        chunk = diff[b::n_bits]
        avg = sum(chunk) / max(1, len(chunk))
        bits.append(1 if avg > 0 else 0)
    return bits
```

- **嵌入**：第 i 个采样点负责第 `i % n_bits` 位；该位为 1 就加 `+0.003`，为 0 就加 `−0.003`。`list(wave)` 先复制一份，不修改输入。
- **检测**：带水印信号减去原始信号得到差值，`diff[b::n_bits]` 用**步长切片**取出所有负责第 b 位的采样点，取平均看符号。`max(1, len(chunk))` 防止空切片时除零。
- 载荷 `[int(b) for b in bin(0xDEADBEEF)[2:].zfill(32)]`：`bin()` 返回 `'0b1101...'`，`[2:]` 去掉前缀，`zfill(32)` 左侧补零到 32 位，再逐字符转成整数。
- ⚠️ 这是**非盲检测**：必须有原始音频才能作差。实测如果拿不到原始音频（用全零代替），位准确率只有 46.9%，等于瞎猜。真实系统（讲义提到的 SilentCipher、PerTh）只需要带水印的音频就能检测，并且要抗 MP3 重编码和轻度噪声。
- ⚠️ 鲁棒性极弱：64 个采样点分给 32 位，每位只有 2 个点。实测叠加 σ=0.01 的高斯噪声后，即使有原始音频，准确率也只剩 71.9%。docstring 也坦白："This demo just proves the encode/decode contract holds."
- 改进方向是**扩频水印**：用密钥生成伪随机 ±1 序列调制每一位，检测时与同一序列做相关，宿主信号被平均掉，不再需要原始音频（参考测验 Q10 的实现）。

### 3.8 Step 6：排行榜

```python
    table = [
        ("VoiceBox",       0.78, 2.1, "330M"),
        ("VALL-E 2",       0.77, 2.4, "370M"),
        # ...
    ]
    print("  | Model          | SECS  | CER%  | Size |")
```

- 硬编码的讲义表格，按 SECS 降序。注意讲义表头的第三列是 "WER (intel.)"，代码里打印成了 "CER%"，两者是不同的指标（词错误率 vs 字符错误率），读数时以讲义为准。
- 可以读出的结论：参数量最大的 XTTS v2（470M）SECS 反而最低；VoiceBox、VALL-E 2 在音色相似度上领先，F5-TTS 在可懂度上与 VoiceBox 并列最好。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用单个 64 维向量代表"音频" | 能手算、能打印，聚焦分解—重组思想 | 真实音频是长序列；内容表示是逐帧的 PPG / WavLM 特征 |
| 内容用 SHA-256 哈希 | 确定性、无需任何模型 | 与发音无关；未归一化导致尺度失衡 |
| 说话人用单位高斯向量 | 高维下天然近似正交，模拟"不同人可区分" | 真实 embedding 由 ECAPA-TDNN 等模型提取，同一人的不同录音有波动 |
| 线性混合代替 TTS | 一行代码表达"条件生成" | 真实模型通过调制 / attention 注入条件 |
| 闭集余弦探针 | 便于验证"找回了谁、找回了什么" | 真实说话人验证是开集 + 阈值；真实 VC 不能检索已知文本 |
| 非盲直流偏移水印 | 最简单的编码/解码约定 | 需要原始音频、不抗噪；生产用感知域盲水印（SilentCipher、AudioSeal 等） |
| 硬编码排行榜 | 让学习者看到 2026 年的模型格局 | 数字会过时，跨 encoder 的 SECS 不可直接比较 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `str.encode()` 与字节串 | `text.encode()`、`h * 2` | 字符串转 UTF-8 字节；`bytes` 可以重复、切片，遍历时得到 0–255 的整数 |
| `hashlib` | `hashlib.sha256(...).digest()` | 计算哈希摘要；`digest()` 返回字节，`hexdigest()` 返回十六进制字符串 |
| 向上取整除法 | `(dim + len(h) - 1) // len(h)` | 不用 `math.ceil` 的整数写法 |
| 局部随机数生成器 | `rng = random.Random(seed)`、`rng.gauss(0, 1)` | 可复现且不影响全局 `random` 状态；种子可以是字符串 |
| `_` 占位变量 | `for _ in range(dim)`、`matched_text, _ = ...` | 表示"这个值不用" |
| `or` 提供默认值 | `math.sqrt(...) or 1e-12` | 左边为假值（如 0.0）时取右边，用来防除零 |
| 列表推导 + `zip` | `[(1 - mix) * c + mix * s for c, s in zip(content, speaker)]` | 逐元素运算 |
| 字典 `.items()` | `for name, vec in reference_speakers.items()` | 同时遍历键和值 |
| `sort(key=lambda ...)` | `sims.sort(key=lambda x: -x[1])` | 按元组第二个元素降序排序；`lambda` 是匿名函数 |
| 元组返回与解包 | `return sims[0]`；`name, score = extract_speaker(...)` | 一次返回、接收两个值 |
| 步长切片 | `diff[b::n_bits]` | 从下标 b 开始每隔 `n_bits` 取一个 |
| 条件表达式 | `sign = 1 if payload_bits[bit_idx] else -1` | 一行 if/else 赋值 |
| 生成器表达式计数 | `sum(1 for x, y in zip(a, b) if x == y)` | 带条件的计数 |
| `bin()`、`zfill` | `bin(0xDEADBEEF)[2:].zfill(32)` | 十六进制字面量转二进制字符串，去前缀、左补零 |
| `str.join` + 生成器 | `''.join(str(b) for b in payload)` | 把比特列表拼成字符串打印 |
| f-string 格式符 | `{score:.3f}`、`{txt!r}`、`{acc * 100:.1f}%`、`{name:<14}` | 3 位小数、repr 显示、表达式内联、左对齐 |
| 文档字符串 | 每个函数下的 `"""..."""` | 说明函数用途，`help()` 可读取 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.02 秒）的完整输出：

```text
=== Step 1: synthesize alice saying 'hello' ===
  speaker probe: alice (cos=0.437)
  content probe: 'hello this is a test' (cos=0.936)

=== Step 2: zero-shot clone — alice's voice on bob's intended text ===
  speaker probe: alice (cos=0.462)  -- should stay alice
  content probe: 'please remember to water plants' (cos=0.914)  -- should be remind text

=== Step 3: voice conversion — rewrite bob's utterance into alice ===
  post-conversion speaker: alice (cos=0.462)  -- should be alice
  content preserved:  'please remember to water plants'

=== Step 4: SECS — speaker cosine similarity of clone ===
  alice (target) vs clone  SECS = 0.462  (should be high)
  bob (not target) vs clone SECS = -0.013  (should be low)
  production ECAPA-TDNN on real clones lands SECS in 0.65 - 0.78 range.

=== Step 5: watermark + detect ===
  payload:   11011110101011011011111011101111
  detected:  11011110101011011011111011101111
  bit accuracy: 100.0%   (real SilentCipher: ~99% across MP3 re-encode)

=== Step 6: 2026 cloning leaderboard ===
  | Model          | SECS  | CER%  | Size |
  | VoiceBox       | 0.78  | 2.1   | 330M |
  | VALL-E 2       | 0.77  | 2.4   | 370M |
  | F5-TTS         | 0.72  | 2.1   | 335M |
  | OpenVoice v2   | 0.70  | 2.8   | 220M |
  | XTTS v2        | 0.65  | 3.5   | 470M |
```

逐段解读：

- **Step 1**：两个探针都答对了，但分数差异很大（0.437 vs 0.936），原因是内容向量模长约为说话人向量的 2–2.5 倍（见 3.3）。
- **Step 2**：把 remind 文本"贴"上 alice 的音色，说话人探针仍是 alice、内容探针是 remind 文本——"内容与音色可以独立替换"这一核心论点成立。
- **Step 3**：说话人变成 alice、内容保留。`cos=0.462` 与 Step 2 完全相同，因为闭集检索使两次合成的输入一模一样（见 3.5）。
- **Step 4**：目标 0.462 vs 非目标 −0.013，相对差距清晰；真实系统的绝对值通常在 0.65–0.78。
- **Step 5**：`0xDEADBEEF` 的 32 位二进制被完整还原，100% 准确率是必然的（无噪声 + 非盲检测），不代表鲁棒性。
- **Step 6**：讲义表格的复述，注意第三列名称与讲义不一致（CER vs WER）。

---

## 7. 动手改一改

1. 在 `content_vector` 的返回前加一步 L2 归一化，再用 `mix=0.5` 运行，观察说话人余弦和内容余弦如何变化。
2. 遍历 `mix` 从 0.1 到 0.9，打印两个探针的余弦，找出两者相等的交叉点。
3. 往 `speakers` 里加 20 个随机说话人，看看 `mix=0.3` 时说话人探针还能不能稳定选出 alice——体会"候选越多，识别越难"。
4. 给 `wav_cloned` 加 σ=0.01 的高斯噪声后再检测水印，记录位准确率；再把"音频"长度扩到 16000 个点，看准确率如何回升。
5. 实现测验 Q10 中的扩频水印 `ss_embed` / `ss_detect`，在不提供原始音频的情况下完成检测，并验证错误密钥检测不出来。
6. 进阶：把 `extract_content` 改成"返回加噪后的内容向量"（模拟不完美的 PPG 提取），观察 VC 输出的内容探针分数下降多少。

---

## 8. 常见坑

- **向量尺度不一致**：未归一化的向量做加权混合时，模长大的一方主导方向。比较余弦前先确认两边的尺度。
- **把闭集检索当成识别能力**：`extract_content` 能"完美还原"内容，只是因为答案就在字典里；换成开放内容就不成立。
- **非盲水印**：需要原始音频才能检测的方案在真实部署中几乎没用，因为检测方通常只拿得到可疑音频本身。
- **水印容量与载荷**：讲义说真实水印约 16–32 bit，载荷应当是短 ID，而不是一整段字符串（讲义 Step 4 的示例载荷有 31 字节 = 248 bit）。
- **表头与讲义不一致**：代码排行榜第三列写的是 CER%，讲义是 WER，引用数字时要说明口径。
- **跨 encoder 比较 SECS**：不同 speaker encoder 给出的余弦分布不同，0.46 和 0.72 不能放在一起比较。
