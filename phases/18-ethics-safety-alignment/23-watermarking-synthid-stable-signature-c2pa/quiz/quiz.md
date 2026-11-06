# 测验 · 水印：SynthID、Stable Signature、C2PA（Watermarking — SynthID, Stable Signature, C2PA）

> **阶段 18 · 伦理、安全与对齐 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Token 水印（Kirchenbauer 式 green list） | 每个解码步用前 K 个 token 做哈希，把词表伪随机地分成 green / red 两半，再给 green logits 加 δ，使生成文本里的 green token 多于随机水平 |
| 2 | 检测 = 假设检验 | 重算每个前缀的 green 集合，数 green token 个数 G，`z = (G − γn) / √(nγ(1−γ))`；人写文本 z ≈ 0，带水印文本 z ≫ 0 |
| 3 | 信号强度随 √n 增长 | 每 token 的 green 概率为 p 时，`z ≈ (p − γ)·√n / √(γ(1−γ))`；本节代码 p = 0.9、γ = 0.5，`z = 0.8√n`，1000 token 时理论值 25.3，与实测 25.30 一致 |
| 4 | 检测需要"分区函数"（密钥） | 讲义："Detectable with access to the vocabulary partition function"。生产系统用密钥参与哈希；本节代码没有密钥，任何人都能检测、也能伪造/擦除 |
| 5 | 改写（paraphrase）脆弱性 | 改动一个 token 会同时破坏它自己和后面 K 个 token 的哈希上下文；随机替换比例 r 时，信号完好保留的比例约 `(1−r)^(K+1)` |
| 6 | 熵依赖 | 加 δ 只能在"模型本来就犹豫"的位置改变选择；低熵位置（答案几乎确定）几乎不携带水印。本节代码用均匀分布采样，是最乐观的情形 |
| 7 | Stable Signature | Fernandez 等，ICCV 2023：微调潜空间扩散模型的 decoder，让每张输出都嵌入固定比特消息；讲义：裁剪到 10% 内容仍以 >90% 检出、FPR < 1e-6 |
| 8 | "Stable Signature is Unstable" | arXiv:2405.07145（2024 年 5 月）：对 decoder 再做一次微调即可去除水印并保持画质——对抗鲁棒性有限 |
| 9 | C2PA | 加密签名、可检测篡改的元数据标准（讲义引 C2PA 2.2 Explainer，2025）；记录谁、何时、做了哪些变换。信息丰富但可以被剥离 |
| 10 | 分层与局限 | 水印"抗转码但比特少"，C2PA"信息全但可剥离"，两者互补；水印是模型特定的——"没检测到 SynthID"不等于"是人写/真实的" |

### 核心技能（能动手做到）

- [ ] 用标准库实现一个 green-list 文本水印的嵌入与 z-score 检测，并能手算给定 n、G 时的 z 值
- [ ] 推导"达到某个 z 阈值至少需要多少 token"，解释为什么短文本很难可靠检测
- [ ] 推导随机替换比例 r、上下文长度 K 下的信号保留率，并用实验验证
- [ ] 正确测量假阳性率（FPR）：知道 100 次抽样无法支撑"<1%"的结论，会用理论正态尾概率或更大样本
- [ ] 指出本节玩具实现与真实方案的差距（无密钥、只有两种分区、均匀分布、概率偏置而非 logit 偏置）
- [ ] 为一个多模态内容平台设计"水印 + C2PA"分层溯源方案，并说出每一层的失效方式

---

## 二、基础自测（选择题）

**Q1.** 关于 Kirchenbauer 式 token 水印的嵌入方式，下列描述正确的是：

- A. 每步用前 K 个 token 做哈希，伪随机地把词表分成 green / red 两组，并给 green 组 logits 加一个小的 δ
- B. 在输出文本末尾追加一段不可见的 Unicode 零宽字符，记录模型名称
- C. 用模型提供方的私钥对整段输出做数字签名，附在响应头里
- D. 在训练阶段往语料里混入特定短语，让模型学会输出它们

**Q2.** 一段 1000 个"可计分 token"的文本中，检测器数出 900 个 green token，γ = 0.5。z-score 最接近：

- A. 8.0
- B. 12.6
- C. 400
- D. 25.3

**Q3.** 讲义强调"no SynthID signal is not proof of authenticity"，最根本的原因是：

- A. SynthID 对人类文本的误报率很高
- B. SynthID 只给启用了 SynthID 的模型的输出打水印；其他模型生成的内容天然没有这个信号
- C. SynthID 的检测器没有开源
- D. SynthID 只能检测图像，不能检测文本

**Q4.** 关于 Stable Signature 及其后续攻击，说法正确的是：

- A. 它在图片角落叠加一个半透明 logo，裁剪后即失效
- B. 它用 C2PA 在上传时对图片签名
- C. 它微调潜空间扩散模型的 decoder，使每张生成图都嵌入固定消息；2024 年的研究表明再次微调 decoder 就能去掉水印且保持画质
- D. 它在数学上被证明无法被去除

**Q5.** C2PA 元数据与水印"互补"的含义是：

- A. 元数据记录完整溯源链但可以被剥离；水印能扛过转码但只携带少量比特，二者叠加才构成可用的溯源故事
- B. C2PA 会取代水印，两者只需选一个
- C. 水印和 C2PA 使用同一把签名密钥
- D. 水印负责加密内容，C2PA 负责压缩内容

**Q6.** 本节代码 `K = 4`，`paraphrase(ratio=0.3)` 对每个位置以 30% 概率替换为随机 token。一个位置要"仍携带完整水印信号"，需要它自己和它的哈希上下文都没被改动。这样的位置约占：

- A. 70%
- B. 49%
- C. 17%
- D. 24%

**Q7.** 若每个 token 落入 green 的概率为 0.9、γ = 0.5，要让期望 z-score 达到 4，至少需要多少个可计分 token？

- A. 5
- B. 25
- C. 100
- D. 400

**Q8.** 阅读本节代码的 `green_set`：

```python
    h = int(digest, 16)
    # partition: token is green iff (token + h) mod 2 == 0
    return {t for t in range(VOCAB) if (t + h) % 2 == 0}
```

关于它产生的"伪随机划分"，正确的是：

- A. 每个不同的上下文都会得到不同的 green 集合，共有 C(200,100) 种可能
- B. green 集合大小随哈希值变化，从 0 到 200 不等
- C. 它使用了密钥，攻击者无法复现
- D. 实际上只有两种划分：h 为偶数时 green = 全部偶数 token，h 为奇数时 green = 全部奇数 token

---

## 三、动手 / 代码题

**Q9.** 针对 Q8 发现的问题改造 `green_set`：

1. 说明"只有两种划分"和"没有密钥"各会带来什么安全后果。
2. 写一个 `green_set_keyed(prev_tokens, key, gamma=0.5)`：用 HMAC（带密钥）对前 K 个 token 做哈希，再用该哈希作种子打乱词表，取前 `γ·VOCAB` 个作为 green 集合。
3. 同时改造 `detect`，支持任意 γ，并验证"用对的密钥检测 → z 很高；用错的密钥 → z ≈ 0"。

**Q10.** 讲义写的是"Bias sampling toward the green set by adding δ to green logits"，而代码是 `use_green = random.random() < bias`（直接以 0.9 的概率从 green 中均匀抽一个）。

1. 在"基础分布为均匀分布、γ = 0.5"的前提下，代码的 `bias = 0.9` 等价于多大的 δ？δ = 2 时 green 概率是多少？
2. 假设真实模型某一步的分布是"top-1 token 概率为 q，其余 199 个均分剩下的概率"，top-1 是 green 还是 red 各占一半。δ = 2 时，q = 0.5 / 0.9 / 0.99 三种情况下该步的平均 green 概率分别约为多少？由此说明本节 `z = 25.3` 为什么是"最乐观情形"。

**Q11.** 本节一次运行的输出是：

```text
watermarked z-score       : 25.30
after 30% paraphrase      : 3.86
after 60% paraphrase      : 0.32
```

1. 用 `(1−r)^(K+1)` 推导 30% 和 60% 替换后的期望 z，并与实测比较。
2. 输出的 TAKEAWAY 说"paraphrase of 30% weakens the signal"。按代码自己的阈值 z ≥ 4，这次运行的 30% 改写版本还能被判为带水印吗？如果重复 30 次，大约多大比例仍能检出？
3. 把 K 从 4 改成 1、2、8，30% 改写后的期望 z 分别是多少？这揭示了 K 的什么取舍？

**Q12.** 代码用 100 次"人类文本"抽样估计 z ≥ 4 时的 FPR，得到 `0.000`，TAKEAWAY 据此说"<1% FPR at z=4"。

1. 0/100 能支撑"FPR < 1%"吗？（提示：rule of three）
2. 在 H0 下 z 近似标准正态，z ≥ 4 与 z ≥ 1.645 的单侧理论 FPR 各是多少？
3. 讲义练习 1 要求报告"95% 置信阈值下的 FPR"。代码需要怎么改才能回答这一问？

---

## 四、面试高频题

**Q13.**（基础必考）请解释 LLM 文本水印（green list 方案）的嵌入与检测流程。检测方需要掌握什么信息？检测结果怎么解读？

**Q14.**（原理深挖）为什么文本水印扛不住 paraphrase，而 Stable Signature 这类图像水印能扛住裁剪、压缩？既然图像水印更鲁棒，它又为何被"Stable Signature is Unstable"击破？

**Q15.**（工程实践）你要为一个同时生成文本和图片的产品设计溯源方案：使用 SynthID 类水印 + C2PA 元数据。请描述消费者最终看到的溯源链，并分别给出每一层的至少一种失效方式。

**Q16.**（场景设计）公司开源了一个带 Stable Signature 式水印的图像生成模型权重。如何在部署和发布流程上限制"微调 decoder 去水印"这类攻击？哪些是做不到的？

**Q17.**（追问型）学校想用"AI 文本水印检测器"判定学生作文是否由 AI 写成，你怎么看？

---

## 五、参考答案与解析

### Q1 — 答案：A

这是讲义"Text watermarking (SynthID-text style)"一节的三步：哈希前 K 个 token 得到伪随机分区 → 给 green logits 加 δ → 生成结果中 green token 多于随机水平。B 是一种很容易被清洗的"隐写"做法，不是本节机制；C 描述的是签名类元数据（更接近 C2PA 的思路），不改变文本本身；D 是数据投毒/后门思路。

### Q2 — 答案：D

`z = (900 − 0.5×1000) / √(1000×0.5×0.5) = 400 / 15.81 ≈ 25.3`。这恰好是本节代码的实测值 `watermarked z-score : 25.30`（bias = 0.9 时期望 green 数就是 900）。C 是没有除以标准差的"超出数"；A 是 `0.8×√100`，把 n 当成了 100；B 是 400/√1000，把方差里的 `γ(1−γ)` 漏掉了。

### Q3 — 答案：B

讲义 Limitations："SynthID watermarks generations from SynthID-enabled models. A generation from a model without SynthID is not watermarked." 水印检测只能回答"这是不是某个带水印模型生成的"，不能回答"这是不是人写的"。A 说反了：设计良好的检测器在人类文本上 z ≈ 0，FPR 可控；C 与结论无关（讲义还提到 SynthID-text 已于 2024 年 10 月开源）；D 错，SynthID 覆盖文本、图像、音频、视频。

### Q4 — 答案：C

讲义："Fine-tune the latent diffusion decoder so every generated image contains a fixed binary message"；"Stable Signature is Unstable"（arXiv:2405.07145）："fine-tuning the decoder removes the watermark while preserving image quality"。A 是可见水印；B 混淆了 C2PA；D 恰好被 2024 年的结果否定。

### Q5 — 答案：A

讲义列出三点互补：元数据可剥离而水印不易去除；元数据丰富（完整溯源链）而水印只带几个比特；C2PA 依赖平台采用而水印自动嵌入。B、D 错在把二者看成替代或功能完全不同；C 错，水印的"密钥"是检测分区用的，不是 C2PA 的签名证书。

### Q6 — 答案：C

位置 i 的 green 判定依赖 `tokens[i]` 本身和 `tokens[i-4:i]` 四个上下文 token，一共 5 个位置都不能被改：`0.7^5 ≈ 0.168`。A 只考虑了 token 本身；B 是 `0.7^2`（只算了 K = 1）；D 是 `0.7^4`（只算了上下文）。被破坏的位置 green 概率退化为 0.5，于是期望 green 比例 `0.168×0.9 + 0.832×0.5 ≈ 0.567`，期望 z ≈ 4.25（见 Q11）。

### Q7 — 答案：B

`z = (0.9 − 0.5)·n / √(0.25n) = 0.8√n ≥ 4 ⇒ √n ≥ 5 ⇒ n ≥ 25`。用代码实测 50 次平均：n = 25 时 z 均值 3.87，n = 50 时 5.65，n = 100 时 7.78（理论 4.00 / 5.66 / 8.00）。注意这是"均匀分布 + 0.9 的极强偏置"下的数字；真实 LLM 的每 token 信号弱得多（见 Q10），需要的长度远大于 25——这也是讲义只说"detection at 1000-token generations"的原因。

### Q8 — 答案：D

`(t + h) % 2 == 0` 只取决于 `h` 的奇偶：h 偶 → 偶数 token 为 green；h 奇 → 奇数 token 为 green。我们实际枚举 200 个不同上下文，只得到 **2** 种不同的 green 集合。哈希虽然是 SHA-256，但只有 1 个比特被用上了。A 是理想实现应有的样子；B 错，集合大小恒为 100；C 错，代码里没有任何密钥，`seed` 就是上下文 token 的拼接字符串。

### Q9 — 参考答案

1. **安全后果**：
   - 只有两种划分：攻击者只需观察少量带水印文本，就会发现"在某些上下文后，token 奇偶性高度一致"，从而反推出规律；green 集合与 token ID 的奇偶强相关，词表中 ID 相邻的 token 永远在不同组，统计结构非常明显。
   - 没有密钥：任何拿到代码的人都能 (a) 检测；(b) **擦除**——生成时故意选 red token 或在改写时专挑 red 替换；(c) **伪造**——让人写的文本里塞满 green token，诬陷某段文字为 AI 生成。讲义说"Detectable with access to the vocabulary partition function"，生产系统必须把这个函数当作秘密。
2. 参考实现（已实际运行）：

```python
import hashlib, hmac, random, math
VOCAB, K = 200, 4

def green_set_keyed(prev_tokens, key: bytes, gamma: float = 0.5) -> set[int]:
    ctx = ",".join(str(t) for t in prev_tokens[-K:]).encode()
    seed = int.from_bytes(hmac.new(key, ctx, hashlib.sha256).digest()[:8], "big")
    rng = random.Random(seed)              # 局部 RNG，不污染全局 random
    perm = list(range(VOCAB))
    rng.shuffle(perm)
    return set(perm[: int(gamma * VOCAB)])

def detect(tokens, key: bytes, gamma: float = 0.5) -> float:
    n = len(tokens) - K
    g = sum(tokens[i] in green_set_keyed(tokens[:i], key, gamma)
            for i in range(K, len(tokens)))
    return (g - gamma * n) / math.sqrt(n * gamma * (1 - gamma))
```

3. 验证结果：200 个上下文得到 **200** 种不同的 green 集合；用 bias = 0.9 生成 500 个 token，正确密钥检测 z = 17.35（理论 `0.8×√500 ≈ 17.9`），错误密钥 z = 0.45。要点：`γ` 可以小于 0.5（Kirchenbauer 论文常用 0.25），此时 z 的分母也要跟着改；用 `random.Random(seed)` 而不是 `random.seed(seed)`，避免与生成过程共用全局状态。

### Q10 — 参考答案

1. 均匀分布下 100 个 green、100 个 red，加 δ 后 `P(green) = e^δ / (e^δ + 1)`。令其等于 0.9 得 `δ = ln 9 ≈ 2.197`；δ = 2 时 `P(green) ≈ 0.881`。所以代码的 0.9 大致相当于 δ ≈ 2.2 的 logit 偏置，二者在均匀分布下等价，但在非均匀分布下完全不同。
2. 实际计算（δ = 2，对 top-1 为 green / red 两种情况取平均）：

| top-1 概率 q | top-1 是 green 时 | top-1 是 red 时 | 平均 P(green) |
|---|---|---|---|
| 0.5 | 0.957 | 0.713 | 0.835 |
| 0.9 | 0.993 | 0.281 | 0.637 |
| 0.99 | 0.999 | 0.036 | 0.518 |

   q = 0.99 时，这一步的 green 概率只比 0.5 多 0.018，几乎不携带水印：模型"非常确定"时，δ = 2 推不动它（这正是为了保持质量而有意为之）。本节代码每一步都从 200 个 token 里均匀抽样（熵最大），且 0.9 的偏置在每一步都完全生效，所以 z = 25.3 是上限式的乐观结果；真实 LLM 在代码、事实问答、固定格式这类低熵输出上需要长得多的文本才能检出。

### Q11 — 参考答案

1. r = 0.3：保留率 `0.7^5 = 0.168`，期望 green 比例 `0.168×0.9 + 0.832×0.5 = 0.567`，期望 `z = 0.067×1000/15.81 ≈ 4.25`；实测 3.86，30 次重复的均值 4.19。r = 0.6：保留率 `0.4^5 ≈ 0.010`，期望 z ≈ 0.26；实测 0.32，30 次均值 0.24。理论与实验吻合。
2. 不能。3.86 < 4，按代码自己的阈值这次 30% 改写版本已经**逃过检测**。30 次重复中 z 在 2.15～5.95 之间，只有约 60% 仍 ≥ 4。所以 TAKEAWAY 的"weakens"说轻了：在 1000 token、K = 4 时，30% 的随机替换就已处在检测边缘。
3. 理论值与实验值（每个 K 重复 20 次取均值）：

| K | 保留率 `0.7^(K+1)` | 期望 z（理论） | 实测均值 |
|---|---|---|---|
| 1 | 0.490 | 12.40 | 12.57 |
| 2 | 0.343 | 8.68 | 8.70 |
| 4 | 0.168 | 4.25 | 4.14 |
| 8 | 0.040 | 1.02 | 1.07 |

   取舍：K 小 → 抗改写更好，但可能的上下文少、分区重复多，攻击者更容易通过统计"上下文→green 集合"反推出水印规律；K 大 → 分区更难学，但任何一处改动都会连带破坏后面 K 个位置。Kirchenbauer 论文的主实验只用前 1 个 token 做哈希，本节代码的 K = 4 偏向"难反推"一侧，抗改写因此更差。

   另外要注意：代码的 `paraphrase` 是"随机 token 替换"，并不保持语义，与讲义练习 2 的"同义词替换"以及真实的 LLM 改写都不同；真实改写往往会重排整句，对水印的破坏通常更彻底。

### Q12 — 参考答案

1. 不能。0/100 的 95% 单侧置信上界约为 `3/100 = 3%`（rule of three），只能说"FPR 大概率 < 3%"，无法得出"< 1%"。要验证 1% 量级至少需要数百次无误报抽样；要验证 1e-5 量级则只能依赖理论分布。
2. 标准正态单侧尾概率：`P(Z ≥ 4) ≈ 3.17e-5`；`P(Z ≥ 1.645) ≈ 0.05`。我们用 1000 次"人类文本"抽样实测：z 均值 −0.022、标准差 1.034，z ≥ 1.645 的比例 4.2%，z ≥ 4 的比例 0，最大 z = 3.54——符合 H0 下的标准正态。
3. 在 `main()` 中补充：

```python
fpr_95 = sum(1 for z in fprs if z >= 1.645) / len(fprs)
print(f"FPR (z >= 1.645) : {fpr_95:.3f}  (theory 0.050)")
```

   并把抽样次数提高到 1000 以上。要点：在 95% 置信阈值下，FPR ≈ 5% 是**设计出来的**，不是缺陷——每 20 篇人写文章就会误判 1 篇，所以真实系统用 z = 4 这类严格阈值，同时要求足够长的文本。

### Q13 — 参考回答要点

- **嵌入**：解码第 t 步，用（带密钥的）哈希函数处理前 K 个 token，得到一个伪随机种子，把词表划分为比例 γ 的 green 集合和 1−γ 的 red 集合；给 green token 的 logits 加 δ，再正常采样。
- **检测**：对待测文本逐位置重算 green 集合，统计 green token 数 G；在 H0（与水印无关）下 G ~ Binomial(n, γ)，计算 `z = (G − γn) / √(nγ(1−γ))`；超过阈值（如 4）即判为带水印。
- **检测方需要**：tokenizer、哈希/分区函数和密钥；**不需要**模型本身，也不需要调用 LLM，计算量很小。
- **解读**：z 高 → 强证据表明由带该水印的模型生成；z 低 → 只能说明"没有该水印的证据"，不能证明是人写的（模型特定性、改写、低熵）。
- 加分点：z 随 √n 增长，短文本不可靠；低熵 token 信号弱；讲义提到 SynthID-text 于 2024 年 10 月通过 Responsible GenAI Toolkit 开源。
- 常见误区：把水印当作"AI 内容检测器"——它只能检测**自己家**的水印。

### Q14 — 参考回答要点

- **文本为什么脆弱**：文本是离散符号，每个 token 只携带约"一次有偏抛硬币"的信息；水印信号就存在于"具体选了哪个 token"之中。改写会替换 token、调整顺序，而每个 token 的 green 判定又依赖前 K 个 token，改一处会连带破坏后 K 个位置（见 Q11）。保持语义的改写空间非常大，水印没有冗余可依赖。
- **图像为什么抗裁剪/压缩**：图像水印把比特冗余地扩散到大量像素/潜变量中，并且训练时就把裁剪、JPEG、滤镜等变换作为数据增强，提取网络学会了在这些变换下解码。讲义：Stable Signature 裁剪到 10% 内容仍以 >90% 检出、FPR < 1e-6；SynthID 图像/视频水印扛得住压缩、裁剪、滤镜、帧率变化。
- **为什么仍被击破**：鲁棒性是针对"预期的良性变换"训练的，不是针对"知道水印存在、且能修改生成器"的攻击者。Stable Signature 的水印就住在 decoder 权重里；攻击者拿到权重后，用少量无水印图像再微调 decoder，就能让它不再输出该消息，同时画质几乎不变（arXiv:2405.07145）。讲义还提到 arXiv:2508.20228（2025）展示了能同时摧毁文本水印和许多图像水印的保义变换攻击。
- 加分点：区分"robustness（对良性失真）"与"adversarial robustness（对自适应攻击者）"；开放权重模型的水印天然更弱。

### Q15 — 参考回答要点

- **生成端**：文本加 SynthID-text 类水印，图片加图像水印；同时用平台签名密钥为每个输出生成 C2PA manifest（创建者、模型、时间、编辑历史）。
- **消费者看到的链路**：打开图片 → 浏览器/平台读取 C2PA manifest，验证签名链到可信证书 → 显示"由 X 公司的 Y 模型于某时生成，经过某些编辑"；如果元数据丢失，平台可退一步调用水印检测（讲义提到 Google 在 Search、Ads、"About this image"中集成两者，并在 2025 年 11 月推出跨模态统一检测器）。
- **各层失效方式**：
  - C2PA：截图、重新编码、上传到会剥离元数据的平台即丢失；依赖平台采用；签名只证明"谁签的"，不证明内容真实。
  - 图像水印：开源权重被微调去除（Stable Signature is Unstable）；保义变换攻击（arXiv:2508.20228）。
  - 文本水印：改写、翻译回译、混入人写内容；低熵文本信号弱；短文本无法检出。
  - 跨层：其他厂商模型生成的内容两层都没有——"缺失信号"不能当成真实性证明。
- 加分点：把 EU AI Act 第 50 条作为合规驱动（讲义：透明度守则 2025 年 12 月第一稿、2026 年 3 月第二稿、预计 2026 年 6 月定稿，截至 2026 年 4 月仍是草案），并给出检测 API 的访问控制与审计。

### Q16 — 参考回答要点

- **能做的控制**：
  - 发布侧：只发布已嵌入水印的 decoder；对官方 checkpoint 签名，发布哈希清单；托管平台只接受签名的微调版本（讲义练习 5 的思路：require signed releases of fine-tuned checkpoints）。
  - 许可证：禁止去除水印的用途条款，提供法律追责基础。
  - 托管 API：对外只提供 API、不开放权重时，攻击者碰不到 decoder，风险大幅降低。
  - 检测侧：除水印外，叠加 C2PA 签名、平台级生成日志（谁在何时生成了什么），把"溯源"建立在多个独立信号上。
  - 研究侧：评估时把"微调去除"列入威胁模型，报告需要多少数据/算力才能去除。
- **做不到的**：一旦权重公开，任何人都能本地微调；签名只能证明"官方版本是哪个"，无法阻止"非官方版本存在"。所以对开放权重模型，水印只能作为"善意用户默认开启"的信号，不能作为对抗性保证。
- 常见误区：认为"把水印嵌入权重"就能防止恶意使用。

### Q17 — 参考回答要点

- **只能回答一个窄问题**：检测器只能判断"是否由带这个水印的模型生成"。学生用没有水印的模型、本地开源模型，或对输出做改写/翻译，检测器都会给出"无信号"（Q3、Q11）。
- **误报的代价**：即使阈值取 z = 4（理论 FPR ≈ 3e-5），一个大学一学期成千上万篇作文仍可能出现个别误判；若阈值取 95%（FPR 5%），每 20 篇就会冤枉 1 篇。对个人的处分决策必须考虑基础比率。
- **短文本与低熵**：几百字的作文、格式化的回答信号弱，z 值不稳定（Q7、Q10）。
- **结论**：可以作为"线索"之一，不能作为唯一证据；不应把"没检出"解读为"一定是原创"，也不应只凭"检出"处分学生，应配合面谈、写作过程记录等。
- 加分点：讲义 Ship It 的硬性规则——"Any 'authenticity' claim based only on absence of watermark"直接拒绝；对"能否检测所有 AI 内容"的问题拒绝给出二元答案。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：temperature 采样与 logits，是"给 green logits 加 δ"的基础。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵决定每个 token 能携带多少水印信号（Q10）。
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：z 检验、假阳性率、置信阈值。
- [阶段 08 · 07 潜空间扩散（Latent Diffusion）与 Stable Diffusion](../../../08-generative-ai/07-latent-diffusion-stable-diffusion/docs/zh.md)：理解 Stable Signature 微调的"潜空间 decoder"是什么。

### 本节被哪些后续内容用到
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：EU AI Act 第 50 条等要求这些技术措施的监管层。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：把水印机制与其局限写进系统卡。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../27-data-provenance-training-governance/docs/zh.md)：从"输出溯源"走向"训练数据溯源"。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：生产合规清单中的内容标识要求。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../22-differential-privacy-for-llms/docs/zh.md)：同属"模型输出了什么"这一组议题（讲义："Lessons 22-23 are about what the model emits"）。

### 延伸关键词
`green list / red list` · `z-test` · `γ（green 比例）与 δ（logit 偏置）` · `spike entropy / 低熵 token` · `SynthID-Text` · `tournament sampling` · `Stable Signature` · `watermark removal attack` · `C2PA manifest` · `Content Credentials` · `EU AI Act Article 50` · `false positive rate` · `rule of three`
