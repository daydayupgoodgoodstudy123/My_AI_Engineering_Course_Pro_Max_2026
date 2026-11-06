# 测验 · Chameleon：仅用 Token 的早期融合 Multimodal Models（Chameleon and Early-Fusion Token-Only Multimodal Models）

> **阶段 12 · 多模态 AI · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 提示：本节中文讲义机翻质量很差（例如把 Chameleon 译成"变色龙"、把 "say 32000" 译成"例如2000年"、把 "26-28 dB" 译成"2628 dB"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Late fusion vs early fusion | LLaVA / BLIP-2 / Qwen-VL 是"两条输入通路、中途汇合"（late fusion，后期融合），只能看图、只能输出文本；Chameleon 从第一步就把图像变成与文本**同一词表**里的离散 token（early fusion，早期融合） |
| 2 | VQ-VAE 作图像 tokenizer | encoder（CNN + ViT）→ 空间 feature 图 → 每个位置按 **L2 距离**找最近的 codebook 向量、换成整数索引 → decoder 把量化后的 feature 还原成像素；训练用重建损失 + commitment loss + codebook loss |
| 3 | Chameleon 的关键数字 | 512×512 图像 → 32×32 = **1024** 个 token，codebook 大小 **K = 8192**；讲义示意"文本 BPE 词表比如 32000，合计 40192"（论文实际是 65,536 的总词表，其中包含 8192 个图像 code） |
| 4 | 共享词表 + 单一 loss | 每个 token（文本、图像、分隔符）只有一个 ID；同一个 embedding 层、同一个输出投影、同一个 softmax、同一个 next-token 交叉熵 |
| 5 | 模态分隔符 | `<image>` / `</image>` 括住图像 token 段；推理时一旦输出 `<image>`，下游软件就知道接下来 1024 个 token 是要送进 VQ decoder 的 code |
| 6 | Mixed-modality generation | 一次推理里自主决定"先图后文 / 先文后图 / 交错"，同一个 decoder、同一个 loss；adapter VLM 做不到输出图像 |
| 7 | 训练稳定性 | 讲义列出 QK-Norm、dropout 位置、LayerNorm 顺序三招；论文第 2.3 节：问题表现为训练中后期 norm 缓慢增长（logit drift），7B 用 QK-Norm + dropout(0.1) + z-loss，34B 用 QK-Norm + Swin 式 norm 重排 + z-loss |
| 8 | Tokenizer 重建上限 | VQ 是有损的：K = 8192、1024 token/512² 时 PSNR 约 26–28 dB（讲义），连续空间扩散更高；tokenizer 是图像质量的天花板，Emu3 主要靠更好的 tokenizer 达到 SDXL 级质量 |
| 9 | 选型规则 | 需要生成图像 → Chameleon 家族；只需要理解 → adapter VLM 更简单、更便宜、可复用预训练 LLM；Fuyu 把原始 patch 线性投影进 LLM（无 tokenizer，但不能输出图像）；AnyGPT 把同一套思路扩展到文本/图像/语音/音乐 |
| 10 | 本节玩具代码 | 4×4 patch 经 2×2 平均池化成 4 维向量 → 最近码字；词表 = 文本 0..31 + 图像 32..47 + `<image>`=48 + `</image>`=49，共 50；用 bigram 计数表代替 transformer 演示"共享词表下的自回归采样" |

### 核心技能（能动手做到）

- [ ] 说清 adapter VLM 和 early-fusion 模型的输入/输出通路差异，并能据产品需求（是否要输出图像、能否重新预训练、质量要求）做选型
- [ ] 手写"最近码字量化"：给定 patch 向量和 codebook，算 L2 距离、处理平局，并把码字索引映射到共享词表的 ID 区间
- [ ] 估算 VQ token 化的压缩比与 token 预算（如 512² → 1024 token、4K 图 → 32,400 token），判断上下文和 KV cache 是否撑得住
- [ ] 读懂本节 `main.py` 的数据流，并指出它的 codebook 为什么让 4 类图像里 3 类得到完全相同的 token
- [ ] 用 bigram 计数表手算生成概率（某段图像恰好 4 个 token 的概率、caption 与图像一致的概率），解释为什么"共享词表"不等于"模态一致"
- [ ] 给序列加 BOS / EOS，用实验测出模型"先图后文 / 先文后图"的比例
- [ ] 用纯 Python 实现 QK-Norm，演示它如何让注意力 logit 与 Q/K 的尺度脱钩

---

## 二、基础自测（选择题）

**Q1.** 相对 LLaVA、BLIP-2 这类 adapter（late-fusion）VLM，Chameleon 式早期融合**最根本的新能力**是：

- A. 图像理解精度更高，因为不存在 tokenizer 瓶颈
- B. 可以直接接上现成的 Llama / Qwen 权重，只训练一个 projector
- C. 推理更便宜，生成一张图只需一次 forward pass
- D. 能在一次推理中自主输出交错的文本 token 与图像 token，即生成图文混排内容

**Q2.** VQ-VAE 把图像变成离散 token 的"量化"一步，做的是：

- A. 对 encoder 输出的每个空间 feature，按 L2 距离找最近的 codebook 向量，用它的整数索引替换这个连续 feature
- B. 对每个空间 feature 做 softmax，按概率加权平均所有 codebook 向量
- C. 推理时对当前图片的 feature 重新做一次 k-means，得到这张图专属的 codebook
- D. 把每个像素值从 8 bit 截断为 4 bit，再把像素直接当作 token

**Q3.** Chameleon 把 512×512 的 24-bit RGB 图像编码为 1024 个 token，codebook 大小 8192。只从"比特数"角度估算，压缩比大约是：

- A. 24 倍
- B. 96 倍
- C. 约 473 倍
- D. 约 6,000 倍

**Q4.** 在本节 `main.py` 中，codebook 索引为 5 的图像 code 对应的 token ID、`</image>` 的 ID、以及词表总大小分别是：

- A. 5、49、48
- B. 37、49、50
- C. 37、48、50
- D. 36、49、50

**Q5.** 关于 QK-Norm，下列说法正确的是：

- A. 在点积之前对 query 和 key 做 LayerNorm，直接控制进入 softmax 的 logit 量级，防止训练中后期 norm 增长导致发散
- B. 对注意力的输出做 LayerNorm，替代 Transformer block 里原有的 pre-norm
- C. 用 LayerNorm 代替 `1/√d_k` 缩放，从而省掉一次除法
- D. 对 KV cache 中的 K、V 做归一化后再量化，以减少推理显存

**Q6.** 运行 `main.py`，第 1 部分输出 `red`、`green`、`gray` 三种图像都被编码为 `[34, 36, 36, 36]`，只有 `blue` 是 `[38, 38, 38, 38]`。最根本的原因是：

- A. `image_to_tokens` 用整除 `// 4` 做平均，丢掉了小数部分
- B. `random.seed(42)` 让三种图像恰好采样到同一组码字
- C. `quantize_patch` 用的是 L1 距离而不是 L2 距离
- D. 手工构造的 `CODEBOOK` 只有 8 个不同向量，且每个码字的均值只在 2.5～4.5 之间，所有"亮度高于约 4.5"的平坦 patch 都会落到同一个码字上

**Q7.** 用本节的 bigram 模型执行 `generate(bigram, [1, 5], max_len=30)`，下列说法正确的是：

- A. 每段生成的图像都严格包含 4 个图像 token，因为训练数据里每张图都是 4 个 token
- B. 生成结果可能是"先图后文"，因为训练数据中约 40% 的序列是图像在前
- C. 生成在第一次出现 `</image>` 时停止；图像段的 token 数并不固定（1、2、5 个甚至更多都会出现），因为 bigram 只看前一个 token，不知道一张图应该有几个 token
- D. caption 与图像一定是匹配的，因为它们来自同一个共享词表

**Q8.** 某团队要做"票据/文档图片问答"产品，只需要理解图像、输出文本，并希望复用现成的 Qwen 语言模型权重。按讲义与本节 skill 的规则，最合适的选择是：

- A. Chameleon 式早期融合：一个 loss、一个 decoder，架构最简单
- B. LLaVA / BLIP-2 式 late fusion：视觉 encoder + projector 接到预训练 LLM 上
- C. Chameleon 式早期融合，但把 codebook 缩小到 K = 1024 以降低成本
- D. Fuyu 式方案，因为它可以同时生成图像

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 中的 codebook 与量化代码：

```python
CODEBOOK = [[(i * 7 + 3 * j) % 8 for j in range(4)] for i in range(VOCAB_IMG)]

def quantize_patch(patch: list[int]) -> int:
    best = 0
    best_d = float("inf")
    for k, code in enumerate(CODEBOOK):
        d = sum((p - c) ** 2 for p, c in zip(patch, code))
        if d < best_d:
            best_d = d
            best = k
    return best + IMG_OFFSET
```

已知 4 种合成图经 2×2 平均池化后的 patch 向量大致是常数向量：red ≈ `[8,7,7,8]`、green ≈ `[5,4,4,5]`、gray ≈ `[6,5,5,6]`、blue ≈ `[3,2,2,3]`。

1. 16 个码字里有几个互不相同？为什么？索引 8～15 会被选中吗？
2. 对一个常数向量 `c·[1,1,1,1]`，到码字 `v` 的平方距离可以写成 `4(c − mean(v))² + Σ(v_j − mean(v))²`。用这个分解解释为什么 red、green、gray 都落到码字 4（ID 36）。
3. 改写 `CODEBOOK`，让 4 类图像得到互不相同的 token，并写出新的编码结果。

**Q10.** 用 `random.seed(42)` 生成的 40 条训练序列统计出的 bigram 计数（节选）如下：

```text
<image> -> i2: 31, i6: 9
i2      -> i4: 31
i4      -> i4: 62, </image>: 31
i6      -> i6: 27, </image>: 9
w3      -> w7: 13, w8: 9, w9: 11, w10: 7
```

caption 与图像的对应关系是：`w7`(red)、`w9`(green)、`w10`(gray) 对应 `i2 i4 i4 i4`，`w8`(blue) 对应 `i6 i6 i6 i6`。以 `[1, 5]` 为 prompt 生成：

1. 图像段恰好是 4 个 token 的概率是多少？
2. 图像段 token 数的期望是多少？
3. 生成的图像 token 序列与 caption 完全对应的概率是多少？
4. 这些数字说明了"共享词表 + 单一 loss"的什么局限？真正的 Chameleon 靠什么避免？

**Q11.** 讲义练习 5 要求："给定只含文本的 prompt，测量模型在训练数据为 60% 文本在前 / 40% 图像在前时，选择先图还是先文的频率。"

1. 为什么用现有的 `make_dataset` + `train_bigram` + `generate` **无法**完成这个测量？（提示：`generate` 的 prompt 能否为空？模型从哪里学"序列的第一个 token"？）
2. 给数据加上 BOS / EOS token，写出训练与采样的改造代码，并预测结果。
3. 加了 EOS 之后，`generate` 中的停止条件应该怎么改？

**Q12.** 讲义练习 3：用纯 Python 实现 QK-Norm。给定 64 维的 q、k，分别计算 `q·k/√d` 与 `LN(q)·LN(k)/√d`；再把 q、k 同时放大 4 倍、16 倍重复计算。解释结果，并说明 QK-Norm 之后的注意力 logit 有什么上界（不考虑可学习的 γ）。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 early fusion 和 late fusion 的多模态模型？各举代表模型，比较它们在输入/输出模态、训练成本、能否复用预训练 LLM、图像质量上限上的差异。

**Q14.**（原理深挖）VQ-VAE 是怎么训练的？量化（argmin）不可导，梯度怎么回传到 encoder？三个 loss 各起什么作用？codebook 大小 K 和每张图 token 数如何影响重建质量与下游 LM 的建模难度？

**Q15.**（追问型）为什么图文早期融合的训练比纯文本 LLM 更容易发散？Chameleon 论文观察到的发散"信号"是什么，用了哪些手段稳定训练？讲义的描述与论文有哪些出入？

**Q16.**（场景设计）产品经理希望用 Chameleon 式模型"一次推理直接生成 4K（3840×2160）海报"。请评估可行性：会产生多少图像 token？最先撞上的是哪堵墙？你会提出什么替代方案？

**Q17.**（工程实践）你要上线一个早期融合的图文混排生成服务。从解码到出图的推理链路如何设计？如何保证模型输出的图像 token 段在结构上合法？延迟主要花在哪里？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Side effect: the model can generate mixed-modality outputs — alternating text and image tokens in a single inference call." 共享词表下，softmax 每一步都可能选到图像 token，于是"输出图像"不需要任何额外结构。

- A 错：恰恰相反，讲义说 late fusion "No tokenizer bottleneck for understanding"，早期融合的 VQ tokenizer 才是质量上限。
- B 错：早期融合要求从头预训练一个新模型（本节 skill："If the user wants to plug in existing Llama / Qwen LLM weights, refuse early-fusion"）；"接 projector"是 LLaVA 的做法。
- C 错：讲义把 Chameleon 标为 "Expensive: VQ-VAE decoder per generated image on inference path"，而且 1024 个图像 token 需要逐个自回归生成。

### Q2 — 答案：A

讲义："for each spatial feature, look up the nearest codebook entry by L2 distance. Replace the continuous feature with the integer index." 本节 `quantize_patch` 正是这个过程的最小版本。

- B 是"软量化"（soft assignment），输出仍是连续向量，得不到离散 token。
- C 错：codebook 是训练时学好的固定词表，推理时不变；否则同一个 ID 在不同图里含义不同，LM 无法建模。
- D 是普通的像素量化，不是 VQ；每个像素一个 token 会让序列长到 512×512×3。

### Q3 — 答案：C

原图：`512 × 512 × 24 = 6,291,456` bit。token：每个 token 是 8192 选 1，即 `log2(8192) = 13` bit，`1024 × 13 = 13,312` bit。比值 `6,291,456 / 13,312 ≈ 472.6`（已用 Python 计算）。

- A 只是"每像素 24 bit"本身；B 没有对应任何合理算法；D 大约是把每个 token 当作 1 bit 的结果。
- 这么高的压缩比必然有损——这就是讲义说的 "reconstruction PSNR caps around 26-28 dB"。（讲义练习 1。）

### Q4 — 答案：B

```python
VOCAB_TEXT = 32
VOCAB_IMG = 16
IMG_OFFSET = VOCAB_TEXT              # 32
SEP_OPEN = VOCAB_TEXT + VOCAB_IMG    # 48
SEP_CLOSE = SEP_OPEN + 1             # 49
VOCAB_SIZE = SEP_CLOSE + 1           # 50
```

`quantize_patch` 返回 `best + IMG_OFFSET`，索引 5 → `5 + 32 = 37`。运行输出也打印了 `image tokens : 32..47`、`</image> : 49`、`vocab total : 50`。

- A 忘了加 `IMG_OFFSET`，且把 `<image>` 的 48 当成了词表大小。
- C 把 `<image>`（48）当成了 `</image>`。
- D 把偏移算成了 31。

### Q5 — 答案：A

讲义："Apply LayerNorm to the query and key projections inside attention, before the dot product. Prevents logit magnitude explosion at depth." 论文原话："QK-Norm directly controls the norm growth of input to the softmax."

- B 描述的更像论文 34B 用的"把 norm 放到子层输出上"的重排，那不是 QK-Norm。
- C 错：QK-Norm 与 `1/√d` 缩放可以并存，目的不是省计算。
- D 是 KV cache 量化，与训练稳定性无关。

### Q6 — 答案：D

```text
0 [0, 3, 6, 1]   1 [7, 2, 5, 0]   2 [6, 1, 4, 7]   3 [5, 0, 3, 6]
4 [4, 7, 2, 5]   5 [3, 6, 1, 4]   6 [2, 5, 0, 3]   7 [1, 4, 7, 2]
8..15 与 0..7 完全相同
```

`(7i + 3j) % 8` 对 i 的周期是 8，所以 16 个码字只有 8 个不同；每个码字都是 0..7 的"锯齿"排列，均值只有 2.5、3.5、4.5 三种。合成图的 patch 接近常数向量（整除后 red ≈ 7.5、gray ≈ 5.5、green ≈ 4.5），离它们"最近"的都是均值 4.5 且方差项最小的码字 4 → ID 36。详细推导见 Q9。

- A 不是根因：把 `// 4` 换成 `/ 4` 保留小数后（已实际运行），red、green、gray 反而全部变成 `[36, 36, 36, 36]`，依然无法区分——亮度差异被 codebook 有限的均值范围吞掉了。
- B 错：`image_to_tokens` 里没有任何随机性。
- C 错：代码明确是平方差之和，即 L2。

这个现象的教训：**图像 token 的信息量由 tokenizer 决定**。在这个玩具里，图像 token 几乎不携带类别信息——"tokenizer 是质量天花板"的极端版本。

### Q7 — 答案：C

```python
def generate(bigram, prompt, max_len=40):
    out = list(prompt)
    while len(out) < max_len:
        nxt = sample_next(bigram, out[-1])
        out.append(nxt)
        if nxt == SEP_CLOSE and any(t < VOCAB_TEXT for t in out):
            break
    return out
```

prompt `[1, 5]` 本身就是文本 token，所以第一次出现 `</image>` 就停。bigram 只看前一个 token，`i4 → i4` 与 `i4 → </image>` 的概率是 2:1，图像段长度服从几何分布。本次运行就出现了 5 个 token（`i2 i4 i4 i4 i4`）和 2 个 token（`i6 i6`）的图像；20,000 次模拟中只有 13.8% 的图像段恰好是 4 个 token（见 Q10）。

- A 错，见上。
- B 错：prompt 已经以文本开头，生成必然"先文后图"。40% 的图像在前比例只影响训练数据，不影响以文本开头的续写。
- D 错：本次运行的第 3 条输出 `w1 w5 w3 w7 <image> i6 i6 </image>` 就是红色 caption 配蓝色图像 code。共享词表不保证模态间一致，一致性靠模型对长距离依赖的建模。

### Q8 — 答案：B

讲义："If you only need understanding, adapter-VLM is simpler and reuses more pretrained compute." skill 的硬性拒绝规则也写明：只做理解的产品不推荐 Chameleon；想复用现有 Llama / Qwen 权重时拒绝早期融合，因为它需要从头预训练。

- A 错：架构"一个 loss"不等于工程简单，早期融合需要训练 VQ tokenizer 并从头预训练。
- C 错：skill 明确拒绝 K < 4096 的生产级 VQ 方案，而且这个产品根本不需要生成图像。
- D 错：讲义说 Fuyu "loses the shared-vocab output generation"，它不能生成图像；它也不能直接复用 Qwen 权重而不训练。

### Q9 — 参考答案

1. `(7i + 3j) mod 8` 只依赖 `i mod 8`，所以码字 i 与 i+8 完全相同，**只有 8 个不同码字**。`quantize_patch` 用严格小于 `d < best_d` 更新，平局时保留先出现的（索引较小的）码字，因此 **8～15 永远不会被选中**，K = 16 实际上只有 8。我们穷举了 `0..9` 的全部 10⁴ 个 4 维整数向量，被选中的码字确实只有 0～7。

2. 8 个码字的均值和"内部方差项"`Σ(v_j − mean)²`：

   | 码字 | 向量 | 均值 | Σ(v_j − mean)² |
   |------|------|------|---------------|
   | 0 | `[0,3,6,1]` | 2.5 | 21 |
   | 6 | `[2,5,0,3]` | 2.5 | 13 |
   | 1、3、5、7 | … | 3.5 | 29 / 21 / 13 / 21 |
   | 2 | `[6,1,4,7]` | 4.5 | 21 |
   | 4 | `[4,7,2,5]` | 4.5 | 13 |

   对常数向量 `c`，距离 = `4(c − mean)² + 方差项`。只要 `c ≥ 4.5`（整除后 red ≈ 7.5、gray ≈ 5.5、green ≈ 4.5），第一项都让均值 4.5 的码字胜出，再在 2 和 4 中选方差项更小的 4，于是都落到 ID 36。例如 `c = 4.5` 时码字 4 的距离是 `0 + 13 = 13`，码字 5 是 `4 × 1 + 13 = 17`。（第一个 patch 出现 2、4、10、12 的四路平局，按顺序取 2 → ID 34，所以序列是 `[34, 36, 36, 36]`。）blue ≈ 2.5，选均值 2.5、方差项 13 的码字 6 → ID 38。**codebook 的均值只覆盖 2.5～4.5，而像素在 2～9 之间**，亮度信息被截断了。

3. 一个最简单的修法是让码字覆盖亮度范围（已实际运行验证）：

   ```python
   CODEBOOK = [[i] * 4 for i in range(VOCAB_IMG)]      # 16 个"平坦"码字，亮度 0..15
   # red   -> [39, 40, 40, 40]
   # blue  -> [34, 35, 35, 35]
   # green -> [36, 37, 37, 37]
   # gray  -> [37, 38, 38, 38]
   ```

   4 类图像的 token 序列互不相同（green 与 gray 共用了 ID 37，但序列整体可区分）。更"正宗"的做法是对训练集的 patch 向量做 k-means，用聚类中心当 codebook——这就是 VQ-VAE 里 codebook 学习的离线版本。

### Q10 — 参考答案

1. 从 `<image>` 出发有两条路径：
   - 走 `i2`（概率 31/40）：`i2 → i4` 必然发生，之后每个 `i4` 以 2/3 继续、1/3 结束。恰好 4 个 token = `i2 i4 i4 i4`，需要"继续、继续、结束"：`(2/3)² × (1/3) = 4/27`。
   - 走 `i6`（概率 9/40）：每个 `i6` 以 3/4 继续、1/4 结束。恰好 4 个 = `(3/4)³ × (1/4) = 27/256`。
   - 合计：`31/40 × 4/27 + 9/40 × 27/256 ≈ 0.1148 + 0.0237 = 0.1385`。20,000 次模拟得到 0.1382，吻合。
2. `i2` 路径：1 个 `i2` + 几何分布的 `i4` 个数（均值 3）= 4；`i6` 路径：几何分布（结束概率 1/4）均值 4。所以期望**恰好是 4**（模拟 3.99）——均值对了，但分布非常散：1 个 token 占 5.8%，2 个占 29.7%，10 个以上也不少见。
3. caption 由 `w3 → w7/w8/w9/w10` 决定（概率 13/40、9/40、11/40、7/40），图像由 `<image> → i2/i6` 决定，两者在 bigram 下**相互独立**。
   - caption 为 red/green/gray（概率 31/40）时需要 `i2 i4 i4 i4`：`31/40 × 4/27 ≈ 0.1148`；
   - caption 为 blue（概率 9/40）时需要 `i6 i6 i6 i6`：`9/40 × 27/256 ≈ 0.0237`；
   - 合计 `0.775 × 0.1148 + 0.225 × 0.0237 ≈ 0.0943`。模拟结果 0.094。
   - 另外，`w1 w5 w3 w8` 这种训练集里从未出现过的 caption（blue 的 caption 都以 `w2` 开头）也有 22.5% 的概率被生成。
4. 局限：共享词表只保证"所有模态能在同一个 softmax 里竞争"，**不保证**图像结构合法（长度固定为 1024）或跨模态一致（图要画的是 caption 说的东西）。这些都依赖模型对长距离依赖的建模：真正的 Chameleon 用 transformer 在整段上下文上做条件建模，`<image>` 之后的每个 token 都能"看到"前面的文本；同时推理端通常还会用规则强制图像段长度（见 Q17）。

### Q11 — 参考答案

1. 两个原因：
   - `generate` 用 `out[-1]` 取上一个 token，prompt 不能为空（空列表会 `IndexError`），而只要 prompt 里有文本，结果就必然是"先文后图"；
   - 训练序列没有 BOS（序列开始）token，bigram 从来没有学过"序列第一个 token 的分布"，60/40 这个信息根本不在模型里。同理没有 EOS，模型也不知道何时该结束。
2. 改造（已实际运行）：

   ```python
   BOS, EOS = VOCAB_SIZE, VOCAB_SIZE + 1          # 50、51，词表扩到 52

   def train_with_bos_eos(corpus):
       return train_bigram([[BOS] + seq + [EOS] for seq in corpus])

   bigram = train_with_bos_eos(make_dataset(2000))
   firsts = [sample_next(bigram, BOS) for _ in range(10000)]
   img_first = sum(t == SEP_OPEN for t in firsts) / len(firsts)
   ```

   `random.seed(7)` 下 2000 条数据里文本在前占 59.6%，BOS 一行的计数为 `{1: 894, 48: 809, 2: 297}`；从 BOS 采样 10,000 次，文本在前 60.4%、图像在前 39.6%。**bigram 的 MLE 会精确复现训练数据的首 token 分布**。注意：如果只用 `main.py` 默认的 40 条数据，文本在前其实是 21/40 = 52.5%，样本太少会偏离名义上的 60/40。
3. 停止条件改为 `if nxt == EOS: break`，删掉"见到 `</image>` 且已有文本就停"这条手写规则。`render` 也要为 BOS/EOS 增加分支，否则 ID ≥ 50 会被错误地渲染成 `i18`、`i19`。

### Q12 — 参考答案

```python
import math, random

def layer_norm(v, eps=1e-5):
    mu = sum(v) / len(v)
    var = sum((x - mu) ** 2 for x in v) / len(v)
    return [(x - mu) / math.sqrt(var + eps) for x in v]

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

random.seed(0)
d = 64
q = [random.gauss(0, 1) for _ in range(d)]
k = [0.6 * x + 0.8 * random.gauss(0, 1) for x in q]      # 与 q 相关的 key
for s in [1, 4, 16]:
    qs, ks = [s * x for x in q], [s * x for x in k]
    raw = dot(qs, ks) / math.sqrt(d)
    normed = dot(layer_norm(qs), layer_norm(ks)) / math.sqrt(d)
    print(s, round(raw, 3), round(normed, 3))
```

实际输出：

| 放大倍数 s | `q·k/√d` | `LN(q)·LN(k)/√d` |
|-----------|---------|-----------------|
| 1 | 5.605 | 5.095 |
| 4 | 89.673 | 5.095 |
| 16 | 1434.765 | 5.095 |

- 不做 QK-Norm 时，logit 随 Q、K 的尺度**平方增长**（s² 倍）。对 3 个分数 `[1.0, 0.5, −0.5]` 乘以 s² 后做 softmax：s = 1 时 `[0.547, 0.332, 0.122]`，s = 4 时已经是 `[0.9997, 0.0003, 0.0]`——注意力退化成 one-hot，梯度几乎为 0，且 bf16 下大数值更容易溢出。
- 做了 QK-Norm 后，结果与尺度无关。LayerNorm 之后向量均值为 0、方差为 1，范数为 `√d`，由 Cauchy-Schwarz，`|LN(q)·LN(k)| ≤ d`，除以 `√d` 后 logit 的绝对值不超过 `√d = 8`。实际实现里有可学习的 γ，上界由 γ 决定，但已不再随残差流的 norm 增长而失控。
- 为什么"深度/训练后期"更重要：残差流在层间累加，norm 会随深度和训练步数缓慢增长；论文观察到正是这种增长在训练中后期引发发散。

### Q13 — 参考回答要点

- **Late fusion（后期融合，adapter VLM）**：独立的视觉 encoder（CLIP/SigLIP ViT）→ projector / Q-Former → 作为"伪 token"拼进 LLM。代表：LLaVA、BLIP-2、Qwen-VL、InternVL。
- **Early fusion（早期融合）**：图像先被 VQ tokenizer 离散化成与文本同一词表的 token，模型从第一步就在交错序列上做 next-token prediction。代表：Chameleon、Emu3、AnyGPT（四种模态）；前身是 CM3 / CM3Leon。
- 对比：

  | 维度 | Late fusion | Early fusion |
  |------|-------------|--------------|
  | 输入 | 图 + 文 | 图 + 文（同一序列） |
  | 输出 | 只有文本 | 文本、图像或交错 |
  | 训练 | 可冻结/复用预训练 LLM，只训 projector + 指令微调 | 要训 VQ tokenizer，并从头预训练 |
  | 理解质量 | 视觉特征连续、无 tokenizer 瓶颈 | 受 VQ 重建上限影响 |
  | 推理成本 | 一次前向编码图像 | 生成图像需逐个解码 1024 token + VQ decoder |
  | 训练稳定性 | 相对成熟 | 规模变大时易发散，需要 QK-Norm 等 |

- 选型：需要输出图像 → 早期融合；只要理解 → late fusion。
- 加分点：提到 Fuyu（原始 patch 直接线性投影进 decoder，没有独立视觉 encoder，但仍是连续输入、不能生成图）和 Transfusion（同一个 transformer 里文本走自回归、图像走连续扩散，绕开 VQ 上限）；能说出 Chameleon 的数字（1024 token / 512²，K = 8192）。
- 常见误区：认为"early fusion 理解能力一定更强"——它的卖点是生成和统一建模，不是理解精度。

### Q14 — 参考回答要点

- **前向**：encoder 输出 `z_e`（如 32×32×256）→ 每个位置找最近码字 `e_k`（`k = argmin ‖z_e − e_j‖₂`）→ `z_q = e_k` → decoder 重建图像。
- **梯度问题**：argmin 不可导。标准做法是 **straight-through estimator**：前向用 `z_q`，反向把 decoder 对 `z_q` 的梯度原样复制给 `z_e`（实现上写作 `z_q = z_e + stopgrad(z_q − z_e)`）。
- **三个 loss**（讲义："VAE reconstruction loss + commitment loss + codebook loss"）：
  - 重建损失：让 decoder 输出接近原图；
  - codebook loss `‖stopgrad(z_e) − e_k‖²`：把码字拉向 encoder 输出；
  - commitment loss `β‖z_e − stopgrad(e_k)‖²`：让 encoder 输出"承诺"靠近所选码字，防止 encoder 输出漂移、无限增大。
  - 实践中 codebook 也常用 EMA 更新代替 codebook loss。
- **K 与 token 数的影响**：
  - K 越大、每图 token 越多 → 重建越好（讲义：K = 8192、1024 token 时 PSNR 约 26–28 dB）；
  - 但 token 越多，LM 的序列越长、生成越慢；K 越大，LM 的 softmax 越大、每个码字出现越少、越难学；
  - codebook collapse（大量码字从不被使用）是常见问题，本节玩具的 codebook 只有一半码字可达，是这个现象的"人为版本"。
- 加分点：更好的 tokenizer（讲义提到 MAGVIT-v2、IBQ、SBER-MoVQGAN）可以抬高上限；Emu3 主要靠 tokenizer 的提升。
- 常见误区：把 VQ-VAE 当成普通 VAE——VQ-VAE 的潜变量是离散的，没有 KL 采样那一步。

### Q15 — 参考回答要点

- **为什么更难**：图像 token 与文本 token 的统计性质（熵）差异很大，同一个 softmax 要同时服务两种分布。论文的解释：softmax 对 logit 平移不变，各模态在"竞争"中会不断推高自身的 norm，这种缓慢增长在训练中后期才显现，一旦数值超出 bf16 的有效范围就发散（单模态场景中也被称为 logit drift）。
- **发散信号**（论文 2.3 节）：监控**最后一层 transformer 输出的 norm**——"Uncontrolled growth of output norms is a strong indicator of future training divergence"，发散可能在训练进度的 20%～30% 之后才出现；不加 QK-Norm 的 7B 在约 20% 个 epoch 后发散。
- **手段**（论文）：
  - QK-Norm：直接控制进入 softmax 的 norm；
  - 7B：在注意力和 FFN 之后加 dropout（0.1），再加 QK-Norm 和 z-loss；
  - 34B：dropout 不够用，改为 Swin Transformer 式的 norm 重排：`h = x + attention_norm(attention(x))`，`output = h + ffn_norm(feed_forward(h))`，即对子层**输出**做 norm 后再加残差，限制 SwiGLU FFN 的 norm 增长；不用 dropout，配合 z-loss（对 softmax 配分函数 `log²Z` 正则，系数 1e-5）。
- **讲义与论文的出入**：讲义写"dropout after every residual-add"，论文是"在注意力和 FFN 之后"且只用于 7B；讲义写"pre-LN 加上最后一个 block 的 skip connection 上额外一个 LN"，论文是每个 block 都把 norm 放到子层输出上（34B）；讲义没有提 z-loss。
- 加分点：工程上把"output norm、注意力 logit 最大值"做成训练监控面板，在 loss 发散之前预警。

### Q16 — 参考回答要点

- **token 数**：Chameleon 的密度是 512² → 1024，即每个 token 对应 16×16 像素。`3840/16 × 2160/16 = 240 × 135 = 32,400` 个图像 token（讲义练习 2）。
- **最先撞墙的是上下文**：论文表 1 中 Chameleon 的上下文长度是 4k token，一张 4K 图就是它的约 8 倍，一次推理根本装不下。
- 即使扩展上下文：KV cache 与 token 数线性增长、并发能力大幅下降；32,400 个 token 逐个自回归解码，比 1024 token 慢 30 倍以上；tokenizer 上限仍在 26–28 dB 量级，放大分辨率不会让细节更好，海报上的文字尤其吃亏（论文也提到含大量文字的图像是该 tokenizer 的弱点）。
- **替代方案**：先生成 512²～1024² 再用超分辨率 / 扩散 upscaler 放大；换更高压缩率或更好的 tokenizer；用 next-scale prediction（VAR）由粗到细生成；质量要求高时按 skill 的规则转向连续空间生成（Transfusion / Stable Diffusion 3 / MMDiT）。
- 常见误区：只算 token 数而忽略"自回归逐 token 生成"的延迟。

### Q17 — 参考回答要点

- **链路**：自回归解码，文本 token 直接流式返回 → 采样到 `<image>` 进入"图像模式"并收集图像 token → 收满后把 32×32 的 code 网格送入 VQ decoder 得到像素，插回响应 → 回到文本模式。
- **结构合法性（约束解码）**：图像模式内用 logit mask 只允许图像 ID 区间（本节玩具中是 32..47）；恰好生成 1024 个后强制输出 `</image>`；文本模式下禁止单独出现图像 token。本节 bigram 输出 1～10+ 个不等的图像段，正好说明不加约束会怎样（见 Q10）；加上"恰好 4 个"的约束后，5,000 次采样全部是 4 个 token。
- **延迟**：1024 个图像 token 逐个 decode，通常远多于一段文字回复；skill 给出的经验值是 VQ decoder 每张图额外 50–200 ms，"often more than the LLM output time"——不能声称早期融合推理是免费的；KV cache 也随图像 token 快速膨胀。
- **其他工程点**：多张图时的上下文预算；输出图像的安全过滤；文本流式与图像异步渲染的协调。
- 加分点：指出"图像段 token 必须恰好 H×W 个，否则 decoder 无法 reshape"是硬约束；图像段可单独设置采样温度或使用 classifier-free guidance。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：late fusion 的标准形态（视觉 encoder + projector + LLM），本节的对照组。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：讲义"Chameleon vs BLIP-2"对比的另一方。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：patch 与"每张图多少 token"的算法；VQ tokenizer 的 encoder 也用 ViT。
- [阶段 08 · 02 自动编码器和变分自动编码器 (VAE)](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：VQ-VAE 的 encoder/decoder 与重建损失。
- [阶段 10 · 01 Tokenizers: BPE, WordPiece, SentencePiece](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：文本侧的离散化与词表；早期融合把图像也变成"词表里的条目"。
- [阶段 05 · 16 Transformers 之前的文本生成 — N-gram 语言模型](../../../05-nlp-foundations-to-advanced/16-text-generation-pre-transformer/docs/zh.md)：本节代码用 bigram 计数表代替 transformer。
- [阶段 07 · 07 GPT — 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：next-token prediction 与"单一 loss"。
- [阶段 03 · 08 Weight初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：理解 norm 增长、QK-Norm 背后的稳定性问题。

### 本节被哪些后续内容用到
- [阶段 12 · 12 Emu3：通过下一 Token 预测生成图像与视频](../../12-emu3-next-token-for-generation/docs/zh.md)：同一路线，靠更好的 tokenizer 把质量提到 SDXL 级。
- [阶段 12 · 13 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像](../../13-transfusion-autoregressive-diffusion/docs/zh.md)：放弃离散图像 token，用连续扩散绕开 VQ 上限。
- [阶段 12 · 14 Show-o 与离散扩散统一模型](../../14-show-o-discrete-diffusion-unified/docs/zh.md)：同样用离散图像 token，但改用离散扩散并行生成。
- [阶段 12 · 15 Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders](../../15-janus-pro-decoupled-encoders/docs/zh.md)：理解用连续 encoder、生成用 VQ tokenizer 的折中。
- [阶段 12 · 16 MIO 与任意模态互转的 Streaming Multimodal Models](../../16-mio-any-to-any-streaming/docs/zh.md)：AnyGPT 式的多模态离散 token 扩展。
- [阶段 08 · 19 视觉 Autoregressive 建模（VAR）：下一尺度预测](../../../08-generative-ai/19-visual-autoregressive-var/docs/zh.md)：解决"高分辨率自回归 token 太多"的另一条路。
- [阶段 08 · 14 Evaluation — FID、CLIP 分数、人类偏好](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：衡量生成图像质量（PSNR、FID）的方法。

### 延伸关键词
`early fusion / late fusion` · `VQ-VAE / VQGAN` · `codebook collapse` · `straight-through estimator` · `commitment loss` · `shared vocabulary` · `modality separator` · `mixed-modal generation` · `QK-Norm` · `z-loss` · `logit drift` · `Swin norm reordering` · `constrained decoding` · `CM3 / CM3Leon` · `AnyGPT` · `Fuyu` · `MAGVIT-v2`
