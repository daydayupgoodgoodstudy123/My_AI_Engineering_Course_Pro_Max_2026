# 测验 · 语音反欺骗和音频水印 — ASVspoof 5、AudioSeal、WaveVerify（Voice Anti-Spoofing & Audio Watermarking — ASVspoof 5, AudioSeal, WaveVerify）

> **阶段 06 · 语音与音频 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三层防御 | 检测（anti-spoofing，对付不配合的攻击者）、水印（合规：让 AI 生成的音频可被识别）、来源认证（C2PA 签名清单）；三者互补 |
| 2 | ASVspoof 5 | 众包录音（非录音棚）、约 2000 名说话人、32 种攻击算法（TTS + 声音转换 + 对抗扰动）、CM 与 SASV 两个赛道 |
| 3 | EER（等错误率） | 扫描阈值，找到误接受率 FAR = 误拒绝率 FRR 的点；必须先明确"分数越高代表真还是假" |
| 4 | 难度落差 | ASVspoof 2019 LA 上最好约 0.42% EER；ASVspoof 5 上约 7.23%；真实野外音频预期 5–10% |
| 5 | 检测模型家族 | AASIST（频谱特征上的图注意力）、RawNet2（原始波形卷积前端 + TDNN）、NeXt-TDNN + WavLM 特征 + focal loss |
| 6 | AudioSeal | 生成器与检测器联合训练；局部化（样本级检测）；抗 MP3/AAC、EQ、±10% 变速、噪声；16-bit payload；检测极快 |
| 7 | WavMark 与 WaveVerify | WavMark：可逆网络、32 bit/s，同步暴力搜索慢、可被噪声/MP3 去除；WaveVerify：FiLM 生成器 + MoE 检测器，补上反转、变速等时域攻击 |
| 8 | 通用攻击：变调 | AudioMarkBench：变调（pitch shift）下所有水印的 Bit Recovery Accuracy 都低于 0.6，接近完全去除——所以必须有检测兜底 |
| 9 | C2PA 的边界 | 密码学签名的元数据清单，记录创作工具、作者、日期；重新编码即可剥离，只能和水印、检测一起用 |
| 10 | 生产集成 | 同意校验 → 合成 → 嵌水印 → 签 C2PA → 审计日志；检测器要真正在 CI / 发布前运行 |

### 核心技能（能动手做到）

- [ ] 能写出正确方向的 EER 计算函数，并解释"分数方向搞反"会让完美分类器的 EER 变成 100%
- [ ] 能用朴素 DFT（或 `numpy.fft.rfft`）计算加 Hann 窗的分帧幅度谱，并据此做高频能量占比、谱滚降（spectral rolloff）等特征
- [ ] 能实现一个真正可检出的玩具水印（非盲：与原始音频对比；或盲检：伪随机序列扩频 + 相关检测），并测出 Bit Recovery Accuracy
- [ ] 能按讲义写出 AudioSeal 的嵌入/检测调用流程（`load_generator` → `get_watermark` → 相加 → `detect_watermark`）
- [ ] 能为"声纹解锁 + AI 语音坐席"这类场景设计检测、水印、来源、活体检测、运营五个层面的防御方案
- [ ] 能解释为什么 AASIST 在 ASVspoof 2019 LA 上训练后需要在自己的渠道数据上做校准

---

## 二、基础自测（选择题）

**Q1.** 诈骗者用一个开源 TTS 模型在自己电脑上克隆了某高管的声音，打电话给财务。下列哪一层防御**最可能**起作用？

- A. 你们自家 TTS 产品输出里的 AudioSeal 水印
- B. 你们自家 TTS 产品签发的 C2PA 清单
- C. 部署在呼入电话上的反欺骗检测器（如 AASIST）
- D. 都不行，三层防御都只对自家生成的音频有效

**Q2.** 关于 EER（Equal Error Rate），正确的是：

- A. 准确率等于 50% 时的错误率
- B. 调节阈值使误接受率（FAR）与误拒绝率（FRR）相等时的错误率，越低越好
- C. 真阳性率与假阳性率之比
- D. 只和训练集大小有关

**Q3.** AudioMarkBench 发现，在变调（pitch shift）攻击下所有水印的 Bit Recovery Accuracy 都低于 0.6。这说明：

- A. 只要把 payload 从 16 bit 增加到 32 bit 就能解决
- B. 变调是通用攻击，水印几乎被完全去除，需要检测模型兜底
- C. 0.6 的比特准确率已经足以可靠地读出 payload
- D. 只有 WavMark 受影响，AudioSeal 不受影响

**Q4.** 下列关于 C2PA 的说法，正确的是：

- A. 它是一种把信号嵌进波形的神经网络水印
- B. 它是密码学签名的元数据清单；对方重新编码、剥掉元数据后就失效，所以要和水印一起用
- C. 它可以检测任意来源的深度伪造音频
- D. 它能抵抗变调攻击

**Q5.** AudioSeal 的"局部化（localized）"检测指的是：

- A. 只能在本地运行，不能上云
- B. 只能检测整段音频有没有水印
- C. 以样本级分辨率（16 kHz 下 1/16000 s）逐帧判断水印是否存在，因此能定位一段音频中哪些部分被加了水印
- D. 只对中文有效

**Q6.** 与以往的 ASVspoof 相比，ASVspoof 5 **没有**下列哪项变化？

- A. 使用众包录音，更接近真实条件
- B. 说话人数量从约 100 增加到约 2000
- C. 32 种攻击算法，包括 TTS、声音转换和对抗扰动
- D. 取消了说话人验证相关赛道，只保留单独的检测赛道

**Q7.** 声纹解锁系统要求用户朗读一段随机短语（活体挑战）。根据讲义，它能防住：

- A. 录音回放攻击，但防不住实时声音克隆
- B. 实时声音克隆，但防不住录音回放
- C. 两者都能防住
- D. 两者都防不住

**Q8.** 一个在 ASVspoof 2019 LA 上训练、EER 很低的 AASIST 模型，部署到呼叫中心后效果明显变差。最合理的第一步是：

- A. 直接换成能量阈值检测
- B. 在本渠道（电话编码、噪声、真实攻击样本）的数据上做阈值校准 / 微调
- C. 关闭检测，只靠水印
- D. 把 EER 指标换成准确率

---

## 三、动手 / 代码题

**Q9.**（找 bug）`main.py` 实测的分数范围是：真实语音 0.190–0.198，伪造语音 0.210–0.211——两类**完全分开**。但程序打印的是：

```text
=== Step 3: sweep threshold → EER ===
  EER ≈ 100.00%  at threshold 0.2101
```

相关代码：

```python
def toy_detector_score(audio):
    spec = magnitude_spectrum(audio)
    total = sum(spec) or 1e-9
    high_band = sum(spec[len(spec) // 2 :]) / total
    return high_band

    # ... main() 中：
    for t in candidates:
        far = sum(1 for s in fake_scores if s >= t) / len(fake_scores)
        frr = sum(1 for s in real_scores if s < t) / len(real_scores)
        if abs(far - frr) < best[0]:
            best = (abs(far - frr), t, far, frr)
```

为什么一个完美分开的检测器会得到 100% 的 EER？请修复，并给出修复后的 EER。

**Q10.**（找 bug + 改写）水印部分的输出是：

```text
  payload:   [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0]
  recovered: [0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1]
  bit accuracy: 31.2%
```

```python
def toy_watermark_embed(audio, payload_bits):
    out = list(audio)
    step = max(1, len(audio) // len(payload_bits))
    for i, bit in enumerate(payload_bits):
        idx = i * step
        if idx < len(out):
            out[idx] = out[idx] + (0.0005 if bit else -0.0005)
    return out


def toy_watermark_detect(audio, n_bits=16):
    step = max(1, len(audio) // n_bits)
    out = []
    for i in range(n_bits):
        idx = i * step
        if idx < len(audio):
            out.append(1 if audio[idx] > 0 else 0)
    return out
```

(a) 如果把**没加水印**的原始音频送进 `toy_watermark_detect`，结果会是什么？由此说明问题出在哪。
(b) 31.2% 比瞎猜（50%）还低，这说明检测器"反着用"就能达到 68.8% 吗？
(c) 改写成一个**盲检**（检测时拿不到原始音频）也能可靠恢复 payload 的玩具水印。

**Q11.**（复杂度分析 + 小 bug）`main.py` 跑一次约 14 秒，几乎全部耗在下面这个函数里：

```python
def magnitude_spectrum(audio, n_fft=256):
    result = [0.0] * (n_fft // 2 + 1)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n_fft - 1)) for i in range(n_fft)]
    chunks = [audio[i : i + n_fft] for i in range(0, len(audio) - n_fft, n_fft)]
    for chunk in chunks:
        for k in range(n_fft // 2 + 1):
            re, im = 0.0, 0.0
            for j in range(n_fft):
                angle = -2 * math.pi * k * j / n_fft
                re += window[j] * chunk[j] * math.cos(angle)
                im += window[j] * chunk[j] * math.sin(angle)
            result[k] += math.sqrt(re * re + im * im)
    return result
```

(a) 对 16000 个样本，`chunks` 有几个？最后一段完整的 256 样本为什么被漏掉了？
(b) 整个脚本大约做了多少次最内层循环？时间复杂度是多少？
(c) 给出两种提速方法。

---

## 四、面试高频题

**Q12.**（基础必考）反欺骗检测、音频水印、C2PA 来源认证分别解决什么问题？为什么讲义说"三者都要"，只上其中一个会有什么漏洞？

**Q13.**（原理深挖）EER 怎么计算？为什么同类方法在 ASVspoof 2019 LA 上约 0.42%，到了 ASVspoof 5 却是约 7.23%，真实场景还要更差？上线前应如何校准？

**Q14.**（原理深挖）AudioSeal 是怎么做到"听不见、压缩后还能检出、还能定位"的？与 WavMark 相比改进在哪里？变调攻击为什么能打穿几乎所有水印，WaveVerify 又补了哪一块？

**Q15.**（场景设计）一家银行的电话客服同时有"声纹解锁"和"AI 语音坐席"，月均 1000 万通电话，覆盖美国和欧盟。请设计完整的防御方案。

**Q16.**（工程实践）你负责上线一个声音克隆 API。请说明水印 payload 怎么设计（16 bit 能装下什么）、检测器如何进入 CI 与发布流程、以及有哪些运营层面的保障。

---

## 五、参考答案与解析

### Q1 — 答案：C

水印和 C2PA 都需要**生成方配合**：只有你们自家的模型才会嵌入水印、签发清单。攻击者用开源模型自行生成的音频不带任何水印或清单，只能靠分析音频本身的反欺骗检测器来识别。讲义："Detection handles adversaries who don't cooperate. Watermarking handles compliance."

### Q2 — 答案：B

阈值越严，误接受越少、误拒绝越多；反之亦然。EER 是两条曲线的交点，是 ASVspoof 的标准指标，越低越好。C 描述的是另一种比值，不是 EER。

### Q3 — 答案：B

payload 每比特被正确恢复的概率不到 0.6，接近 0.5 的瞎猜水平，等于水印被去除。增加比特数不能解决鲁棒性问题（A 错）。讲义："No 2026 watermark is fully robust to aggressive pitch modification. This is why you need detection (AASIST) alongside watermarking."

### Q4 — 答案：B

C2PA 不是 ML 技术，而是一种清单格式：用密码学签名记录创作工具、作者、日期。它能证明"这份文件出自谁之手且未被篡改"，但对方重新编码并丢掉元数据后，就只剩一段没有清单的音频。讲义："C2PA is trivially bypassable by re-encoding. Always add cryptographic + perceptual (watermark) defense together."

### Q5 — 答案：C

AudioSeal 的检测器对每个时间点输出"有水印"的概率，分辨率达到单个样本。好处是：一段音频被拼接、只有一部分是 AI 生成时，也能定位到那一部分。

### Q6 — 答案：D

ASVspoof 5 恰恰有两个赛道：独立检测（CM）和面向生物识别系统的抗欺骗说话人验证（SASV）。A、B、C 都是讲义列出的变化。

### Q7 — 答案：A

录音回放无法临时说出随机短语，所以活体挑战能防回放；但实时声音克隆可以把任意文本即时合成为目标音色，活体挑战就失效了。讲义："Prevents replay attacks but not real-time cloning."

### Q8 — 答案：B

讲义 Pitfall："AASIST trained on ASVspoof LA overfits; real-world accuracy drops. Calibrate on your domain." 电话渠道的编码、带宽、噪声和真实攻击者使用的生成器都与基准数据不同，需要在本渠道数据上重新定阈值，必要时微调。

### Q9 — 参考答案

**原因：分数方向搞反了。** `toy_detector_score` 返回的是高频能量占比，**越高越像伪造**。但 EER 循环里的写法是把分数当作"越高越像真实"的置信度：

- `far = P(fake ≥ t)`：伪造语音分数高于阈值的比例——对"越高越假"的分数来说，这其实是**伪造被正确检出**的比例；
- `frr = P(real < t)`：真实语音分数低于阈值的比例——这其实是**真实被正确接受**的比例。

在阈值 t = 0.2101（伪造分数的最小值）处，`far = 1.0`、`frr = 1.0`，差值为 0，被选中，于是打印 `(1.0 + 1.0) × 50 = 100%`。一个完美的检测器被算成了"完全错误"。

讲义 Step 3 的 `eer()` 写法本身没错——它默认分数是"真实度"（越高越像真人，与 ASVspoof 常用的 bona fide 分数方向一致）。问题在于代码的分数是"伪造度"，两者没有对齐。

修复（把分数方向和 FAR/FRR 定义对齐）：

```python
    for t in candidates:
        # 规则：score >= t 判为伪造（因为分数越高越像伪造）
        far = sum(1 for s in fake_scores if s < t) / len(fake_scores)    # 伪造被放过 = 误接受
        frr = sum(1 for s in real_scores if s >= t) / len(real_scores)   # 真人被拦下 = 误拒绝
        if abs(far - frr) < best[0]:
            best = (abs(far - frr), t, far, frr)
```

或者更简单：保持原循环不变，把分数取负（`real_scores = [-s for s in ...]`）。修复后实测：阈值 0.2101 处 `FAR = 0`、`FRR = 0`，**EER = 0.00%**——两类分数完全分开，这才是正确结果。

经验：写任何 EER/ROC 代码前，先用一句注释写下"分数越高代表什么"，再用一个人造的"完美分类器"做单元测试（EER 应为 0）。

### Q10 — 参考答案

(a) **结果与加了水印的完全一样**：`[0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1]`。检测器读的是"该位置样本的正负号"，而这个正负号由原始语音决定（这些位置的样本绝对值在 0.0025 到 0.23 之间，都大于 ±0.0005 的扰动），水印根本改变不了它。也就是说，**检测器检测的是宿主信号，不是水印**。

(b) 不能。31.2% = 16 位中碰巧对了 5 位，这是宿主信号的符号与 payload 之间的偶然吻合，换一段音频或换一个 payload，结果会在 50% 附近随机波动。"反着用"不会稳定地得到 68.8%。

(c) 两种思路：

- **非盲检测**：检测时拿到原始音频，用 `watermarked[idx] - clean[idx] > 0` 判比特，可以 100% 恢复（实测如此）。但现实中检测方通常拿不到原始音频，所以意义有限。
- **盲检测：伪随机序列扩频（spread spectrum）+ 相关检测**。把每个比特扩展到一整段（1000 个样本）上，乘一个只有收发双方知道的 ±1 伪随机序列；检测时用同一序列做相关，宿主信号与伪随机序列近似不相关，会被平均掉：

```python
import random


def pn_sequence(length, key):
    rng = random.Random(key)
    return [1.0 if rng.random() < 0.5 else -1.0 for _ in range(length)]


def ss_embed(audio, payload_bits, key=1234, alpha=0.01):
    out = list(audio)
    seg = len(audio) // len(payload_bits)
    pn = pn_sequence(seg, key)
    for i, bit in enumerate(payload_bits):
        sign = 1.0 if bit else -1.0
        for j in range(seg):
            out[i * seg + j] += alpha * sign * pn[j]
    return out


def ss_detect(audio, n_bits=16, key=1234):
    seg = len(audio) // n_bits
    pn = pn_sequence(seg, key)
    bits = []
    for i in range(n_bits):
        corr = sum(audio[i * seg + j] * pn[j] for j in range(seg))
        bits.append(1 if corr > 0 else 0)
    return bits
```

在 `synth_real_speech` 的 20 个不同种子上实测：`alpha = 0.01` 时 16 位全部恢复（平均 100%）；`alpha = 0.005` 时平均约 90%；`alpha = 0.0005`（原代码的强度）时约 52%，与瞎猜无异。这直观展示了水印的核心权衡：**强度（越强越好检出）vs 不可感知性（越弱越听不见）**，以及"用更长的段换取检测增益"。AudioSeal 用联合训练的生成器 + 检测器，在这个权衡上做得远比手工扩频好，并且能对抗压缩、EQ 等变换。

### Q11 — 参考答案

(a) `range(0, 16000 - 256, 256)` = `range(0, 15744, 256)`，起点为 0, 256, …, 15616，共 **62** 段。起点 15744 的那一段（15744–15999）恰好完整，但因为 `range` 的终点是开区间而被排除。应写成 `range(0, len(audio) - n_fft + 1, n_fft)`，得到 63 段。（对本例结论影响很小，但这是分帧代码的经典 off-by-one。）

(b) 每段：129 个频点 × 256 个样本 ≈ 3.3 万次内层循环（每次 2 次三角函数 + 4 次乘法）。每段音频 62 段 ≈ 205 万次；20 段真实 + 20 段伪造 = 40 段音频 ≈ **8200 万次**内层迭代。复杂度为 `O(帧数 × n_fft²)`，朴素 DFT 每帧是 `O(n²)`。

(c) 提速方法：
1. **预计算**：`cos`/`sin` 的值只与 `k·j mod n_fft` 有关，可预先算好一张 `n_fft` 长的表，再与窗函数合并，避免在最内层反复调用三角函数；
2. **用 FFT**：每帧 `O(n log n)`，`numpy.fft.rfft(window * frame)` 一行搞定，速度能快上几个数量级；
3. 也可用 `scipy.signal.stft` 等现成函数，一次处理所有帧。

### Q12 — 参考回答要点

- 反欺骗检测：分析音频本身判断真假，**不需要对方配合**，是对抗恶意克隆的唯一手段；弱点是对新生成器、新渠道泛化差（基准 0.42% → 野外 5–10%）。
- 水印：生成时嵌入、检测时提取，服务于**合规与溯源**（"这段是不是我们生成的、谁生成的"）；弱点是只覆盖配合方，且变调能打穿。
- C2PA：签名元数据，证明来源和完整性；弱点是重新编码即可剥离。
- 只上一个的漏洞：只有水印 → 开源克隆完全无感、变调可去除；只有检测 → 无法证明"某段音频出自我方模型"，监管合规缺失；只有 C2PA → 剥离元数据即失效。
- 加分点：说出讲义的结论"Ship both or do not ship voice cloning"，以及每次生成都要有水印 + 签名清单 + 合规的审计日志。

### Q13 — 参考回答要点

- 计算：对每个候选阈值算 FAR（伪造被当成真实的比例）和 FRR（真实被当成伪造的比例），取二者相等（或最接近）的点；先明确分数方向（见 Q9）。
- 落差原因：ASVspoof 2019 LA 是录音棚级干净数据、攻击种类有限；ASVspoof 5 用众包录音、约 2000 名说话人、32 种攻击（含对抗扰动），分布更接近真实；野外还有电话编解码、背景噪声、未见过的新生成器（如讲义 Hard 练习中的 F5-TTS 克隆）。
- 校准：在本渠道数据上重新扫描阈值，按业务能接受的 FAR/FRR 选工作点（不一定是 EER 点）；收集本域的真实/伪造样本做微调；持续用新出现的生成器样本做回归测试。
- 常见误区：只报 EER——生产中更关心特定 FAR 下的 FRR（例如本节 skill 示例中的 FAR 0.1% / FRR 1%）。

### Q14 — 参考回答要点

- AudioSeal 设计：生成器学习嵌入听不见的信号，检测器在各种数据增强（压缩、EQ、变速、加噪）下学习把它找出来，二者**联合训练**，因此鲁棒性是"训练出来的"；检测器逐样本输出概率，实现局部化；支持 16-bit payload；检测速度极快（讲义给出 485× 实时）。
- 相比 WavMark：WavMark 是可逆神经网络、32 bit/s，需要暴力搜索同步位置，慢、不适合实时，且加高斯噪声或 MP3 压缩就可能被去除。
- 变调为什么致命：变调改变了频率结构和时间-频率对应关系，嵌入在特定时频位置的信号被整体搬移或破坏，检测器找不到；AudioMarkBench 测得所有水印的比特恢复率都低于 0.6。
- WaveVerify：针对 AudioSeal 在时域操作（反转、变速）上的弱点，使用 FiLM 生成器 + MoE 检测器，在标准攻击上与 AudioSeal 相当，并能处理时域编辑。
- 加分点：指出"没有任何 2026 年的水印能完全抵抗激进变调"，所以架构上必须有检测兜底。

### Q15 — 参考回答要点

（与本节 skill 示例一致）

- 检测（CM）：商用方案（如 Pindrop）优先，或开源 NeXt-TDNN + WavLM；用 ASVspoof 5 + 本行通话样本训练/校准；在本域数据上设定目标 EER。反欺骗检测在**每一次**身份验证呼入上运行。
- 水印：每一条外呼 TTS 语音都嵌 AudioSeal 16-bit payload，发送前用检测器自检。
- 来源：导出给客户的音频附 C2PA 清单；纯内部通话可省略。
- 声纹验证：每次认证都做活体挑战（随机 4 位数字短语，用户复述，同时过检测器和转写）；生物识别阈值按渠道校准（例如 FAR 0.1%、FRR 1%）。
- 运营：同意记录和审计日志保留 7 年并按区域存储（欧盟数据留在欧盟）；克隆请求量突增（> 2σ）告警；滥用时一键熔断。
- 加分点：说明讲义的"拒绝清单"——不允许只靠余弦相似度做声纹认证（克隆可轻易绕过），不允许只靠 C2PA。

### Q16 — 参考回答要点

- payload 设计：16 bit 只有 65,536 种取值，不可能同时放下完整的模型 ID、用户 ID、时间戳。实用做法是把 payload 当作**索引/短键**：例如若干位表示模型版本、其余位是服务端审计日志里的短会话键，命中后再查日志拿到完整的 `(model_id, user_id, generation_ts)`。
- CI 与发布：每次生成后、返回给用户之前，用检测器验证水印存在且 payload 正确（讲义："Watermark without detector ever running. Pointless. Ship the detector in your CI."）；回归测试覆盖 MP3/AAC 压缩、加噪、变速、变调等攻击，跟踪各攻击下的 Bit Recovery Accuracy。
- 克隆前置：`clone_reference` 必须通过同意校验（讲义 Step 4 的 `verify_consent`），并留存同意证据。
- 运营：审计日志保留与合规；异常调用模式检测（突发量、提示词中出现知名人物）；熔断开关。
- 常见误区：只嵌水印不跑检测、或只在离线评估时跑检测——线上从未验证过的水印等于没有。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：讲义列出的前置课；ECAPA、EER、SASV 中的"ASV"部分。
- [阶段 06 · 08 语音克隆和语音转换](../../08-voice-cloning-conversion/docs/zh.md)：讲义列出的前置课；理解攻击是怎么产生的。
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：分帧、加窗、幅度谱——本节玩具检测器的基础。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：FAR/FRR、ROC、阈值选择。

### 本节被哪些后续内容用到
- [阶段 18 · 23 水印：SynthID、Stable Signature、C2PA](../../../18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa/docs/zh.md)：跨模态（文本、图像、音频）的水印与来源认证。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：EER 与其他音频指标的系统梳理。
- [阶段 06 · 07 文本转语音](../../07-text-to-speech/docs/zh.md)：每个 TTS 输出都应嵌水印。
- [阶段 14 · 22 语音 Agent（Pipecat / LiveKit）](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：在生产语音 agent 中接入检测与水印。
- [阶段 02 · 16 异常检测](../../../02-ml-fundamentals/16-anomaly-detection/docs/zh.md)：把"未知生成器"当作分布外样本来检测的思路。

### 延伸关键词
`ASVspoof 2019 LA / PA` · `ASVspoof 5` · `AASIST` · `RawNet2` · `SASV` · `min t-DCF` · `AudioSeal` · `WavMark` · `WaveVerify` · `AudioMarkBench` · `Bit Recovery Accuracy` · `spread-spectrum watermark` · `C2PA / Content Credentials` · `liveness detection`
