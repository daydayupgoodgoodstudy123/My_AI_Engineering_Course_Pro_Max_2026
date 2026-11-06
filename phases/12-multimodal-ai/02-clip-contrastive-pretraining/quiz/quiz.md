# 测验 · CLIP 与视觉语言对比 Pretraining（CLIP and Contrastive Vision-Language Pretraining）

> **阶段 12 · 多模态 AI · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 对比学习的监督信号 | 不要类别标签：一个 batch 里 N 张图配 N 条 caption，"自己的 caption 是正例，其余 N−1 条是负例"就是全部监督 |
| 2 | Dual encoder（双塔） | 图像 encoder `f`（ViT/ResNet）+ 文本 encoder `g`（小 Transformer），两边输出都 L2 归一化到单位长度，余弦相似度 = 点积 |
| 3 | 相似度矩阵 | `S[i, j] = cos(f(x_i), g(y_j)) / tau`，形状 `(N, N)`，对角线是正例 |
| 4 | 对称 InfoNCE | `(CE(S, I) + CE(Sᵀ, I)) / 2`：按行做"图找字"、按列做"字找图"；本质是 N 分类交叉熵，负例 = batch 内其它样本 |
| 5 | Temperature `tau` | 余弦被限制在 `[-1, 1]`，除以 tau 才能拉开 logit；tau 越小分布越尖、越强调 hard negative。CLIP 初始化 0.07，在 log 空间学习并裁剪防止塌缩 |
| 6 | Sigmoid loss（SigLIP） | 每个 `(i, j)` 当成独立的二分类：对角线标 1，其余标 0；配可学习 bias `b`。不需要整行 softmax 归一化，分布式训练更省 |
| 7 | Zero-shot 分类 | 每个类名套模板 `a photo of a {class}` → 文本 embedding；图像 embedding 与各类做余弦，取 argmax；目标类别零训练 |
| 8 | Prompt ensemble | 讲义："CLIP 原论文每类用 80 个模板并平均 embedding，ImageNet +3 点"；现代用法通常选 1–2 个模板 |
| 9 | 三种使用方式 | zero-shot（基线）< linear probe（冻结特征 + 一层线性）< 全量 finetune（域内最好，但可能损害 zero-shot 迁移） |
| 10 | 家族与现状 | ALIGN（1.8B 噪声对）、OpenCLIP（LAION 开源复现）、EVA-CLIP、SigLIP 2（NaFlex、多语言、1B 规模）；讲义："2026 年开放 VLM 默认视觉塔是 SigLIP 2 SO400m/14" |

### 核心技能（能动手做到）

- [ ] 给定一个 2×2 或 3×3 的相似度矩阵，手算对称 InfoNCE 与 sigmoid pairwise loss
- [ ] 用 log-sum-exp 写出数值稳定的 InfoNCE，并用 NumPy 写出向量化版本，与本节纯 Python 版本对拍
- [ ] 解释 tau 为什么必须远小于 1，以及 SigLIP 的 bias `b` 在"负例远多于正例"时起什么作用
- [ ] 写出 zero-shot 分类流程（模板 → 文本 embedding → 归一化 → 余弦 → argmax），并实现正确的 prompt ensemble（先归一化、再平均、再归一化）
- [ ] 读本节代码时能指出它与讲义/论文的不一致（sigmoid loss 的归一化系数、没有训练步骤、prompt 的伪 embedding）
- [ ] 能从通信与显存角度说清 softmax 对比损失与 sigmoid 损失在大 batch 分布式训练中的差别

---

## 二、基础自测（选择题）

**Q1.** 关于 CLIP 的训练目标，下列描述正确的是：

- A. 对相似度矩阵的每一行做 softmax 交叉熵即可，列方向是冗余的
- B. 对每个图像-文本对做均方误差回归，让余弦相似度逼近 1
- C. 先用 ImageNet 标签预训练图像塔，再用 caption 微调文本塔
- D. 对 `S` 按行（图→文）和按列（文→图）各做一次交叉熵，标签都是单位矩阵的对角线，再取平均

**Q2.** 设 batch 大小 N = 6，两个 encoder 完全没有学到东西，使得相似度矩阵 `S` 的所有元素都相等。此时本节代码 `infonce_loss(S)` 的值是：

- A. ln 6 ≈ 1.792
- B. 0
- C. ln 2 ≈ 0.693
- D. 6

**Q3.** 关于 temperature `tau`，下列说法正确的是：

- A. tau 只影响训练速度，不影响最终 embedding 的质量
- B. tau 越大，softmax 越尖锐，越强调 hard negative
- C. 因为归一化后的余弦相似度只在 `[-1, 1]` 之间，必须除以较小的 tau 才能让正负例的 logit 拉开足够差距；tau 越小越强调 hard negative
- D. CLIP 直接学习 tau 本身，并允许它取到任意接近 0 的值

**Q4.** 讲义认为 SigLIP 的 sigmoid loss 比 CLIP 的 softmax InfoNCE 更适合超大 batch 分布式训练，核心原因是：

- A. sigmoid 函数比 exp 计算更快
- B. 每个 `(i, j)` 对的损失彼此独立，不需要对整行（整个全局 batch）做 softmax 归一化，可以按设备分块计算再求和
- C. sigmoid loss 不需要负例
- D. sigmoid loss 不需要 temperature

**Q5.** 用 CLIP 做 4 类（cat / dog / bird / car）zero-shot 分类，正确的流程是：

- A. 把每个类名套进模板（如 `a photo of a {class}`）用文本 encoder 编码，图像用图像 encoder 编码，两边归一化后算余弦相似度，取最大者
- B. 冻结图像 encoder，在这 4 类的标注数据上训练一个线性分类头
- C. 把图像 embedding 输入文本 decoder，生成类名
- D. 对图像 embedding 做 k-means 聚成 4 类，再人工给每个簇命名

**Q6.** 讲义给出的 sigmoid loss 公式为 `L = -1/N Σ_(i,j) [...]`（与 SigLIP 论文一致，按 batch 大小 N 归一化）。本节代码 `sigmoid_loss` 中 `return total / count`，其中 `count` 统计的是所有 `(i, j)` 对的个数。两者的关系是：

- A. 完全相同
- B. 代码值是讲义公式的 N 倍
- C. 代码值是讲义公式的 2 倍，因为代码是对称损失
- D. 代码值是讲义公式的 1/N（代码除以 N²，讲义除以 N）

**Q7.** 运行本节代码 DEMO 1，得到（bias 默认为 0）：

```text
  tau=0.07  InfoNCE=0.0000  SigLIP=0.9268
  tau=0.10  InfoNCE=0.0003  SigLIP=0.7854
  tau=1.00  InfoNCE=0.7748  SigLIP=0.6197
```

为什么 tau 变小时 InfoNCE 下降、SigLIP 却**上升**？

- A. 代码的 sigmoid 函数实现错误，对负数输入返回了错误值
- B. SigLIP 本来就不应该在对齐的数据上取得低 loss
- C. 对角线 logit 变大让正例几乎无损，但 12 个负例的余弦在 0 附近有正有负，除以小 tau 后被放大到约 ±2；bias = 0 时负例的初始概率是 0.5，而 softplus 是凸函数，放大后的平均负例损失反而超过 ln 2。真实 SigLIP 用 `b = -10` 初始化来解决这个问题
- D. InfoNCE 在 tau = 0.07 时出现了数值下溢，结果是错的

**Q8.** 关于 zero-shot、linear probe 和全量 finetune 三种使用 CLIP 特征的方式，讲义的结论是：

- A. zero-shot 在任何任务上都优于 linear probe，因为它没有过拟合风险
- B. linear probe（冻结特征 + 训练一个线性层）在域内任务上通常胜过 zero-shot；全量 finetune 在域内更强，但可能损害 zero-shot 迁移能力
- C. 全量 finetune 能同时提升域内精度和 zero-shot 迁移，因此总是首选
- D. linear probe 需要重新训练文本 encoder

---

## 三、动手 / 代码题

**Q9.** 手算。给定 2×2 相似度矩阵（已经除过 tau）：

```text
S = [[2.0, 0.5],
     [0.0, 1.0]]
```

1. 按本节 `infonce_loss` 的定义，分别算出两行（i2t）和两列（t2i）的交叉熵，以及最终 loss。
2. 按本节 `sigmoid_loss`（bias = 0）算出结果；再按讲义公式（除以 N）算出结果。
3. 如果把 `S[0][1]` 从 0.5 改成 1.9（一个"hard negative"），哪一项损失变化最大？为什么？

**Q10.** 阅读 `demo_prompt_ensemble`：

```python
    for t in templates:
        prompt = t.format(**{"class": class_name})
        seed = sum(ord(c) for c in prompt)
        emb = make_fake_embedding(seed)
        for k in range(64):
            ensemble_vec[k] += emb[k]
        count += 1
    ensemble_vec = [x / count for x in ensemble_vec]
    ...
    print("  single-template: noisier; ensemble: +1-3 points on real benchmarks.")
```

1. 用"字符码之和"作随机种子有什么问题？请举一个具体的碰撞例子。
2. 这里的"文本 embedding"与类名的语义有关系吗？最后一行 "+1-3 points" 是代码算出来的吗？
3. 真实的 CLIP prompt ensemble 应该怎么做（写出关键三步），为什么要在平均前先归一化？

**Q11.** 讲义学习目标要求"实现数值稳定的**向量化**版本"，而本节代码是双重 for 循环。请用 NumPy 写出：

1. `infonce_np(img, txt, tau)`：输入未归一化的 `(N, D)` 图像、文本特征，返回对称 InfoNCE；
2. `siglip_np(img, txt, t, b)`：SigLIP 论文写法，logit = `t · cos + b`，标签 `z_ij = +1`（对角线）/ `−1`（其余），按 N 归一化；
3. 说明如何用 DEMO 1 的数据与本节纯 Python 实现对拍，以及对拍时需要注意哪一处归一化差异。

**Q12.** temperature 的下界分析。若 tau = 1，余弦相似度最大为 1、最小为 −1：

1. 对一个 N 分类的行，InfoNCE 行损失的理论最小值是多少（假设正例余弦 = 1、所有负例余弦 = −1）？分别算 N = 4 和 N = 32768。
2. 这说明了什么？CLIP 为什么把 tau 初始化为 0.07 并学习 `log(1/tau)`？

---

## 四、面试高频题

**Q13.**（基础必考）请完整讲一遍 CLIP：模型结构、训练数据、损失函数，以及它为什么能做 zero-shot 分类。

**Q14.**（原理深挖）对比 InfoNCE（softmax）与 SigLIP（sigmoid）损失：数学形式、temperature 与 bias 的作用、对 batch 大小的依赖分别有什么不同？

**Q15.**（工程实践）你要在 512 张 GPU 上以全局 batch 32k 训练一个 CLIP 类模型。用 softmax InfoNCE 时，分布式实现上需要做什么？显存和通信的瓶颈在哪里？换成 sigmoid loss 能带来什么变化？

**Q16.**（场景设计）一个电商平台想用 CLIP 类模型给商品图片自动打上 200 个类目标签，并支持"以文搜图"。你会怎么落地？如何评估、何时从 zero-shot 升级到 linear probe 或 finetune？

**Q17.**（追问型）既然 CLIP 的 ImageNet zero-shot 已经饱和在 76% 左右（讲义），为什么 2026 年几乎所有 VLM 仍然用 CLIP/SigLIP 系模型当视觉塔？它作为视觉塔有哪些已知短板？

---

## 五、参考答案与解析

### Q1 — 答案：D

代码原文：

```python
    for i in range(N):
        loss_i2t += -S[i][i] + log_sum_exp(S[i])
    ...
    for j in range(N):
        col = [S[i][j] for i in range(N)]
        loss_t2i += -S[j][j] + log_sum_exp(col)
    return (loss_i2t + loss_t2i) / (2 * N)
```

行方向是"每张图在 N 条 caption 里找自己的那条"，列方向是"每条 caption 在 N 张图里找自己的那张"。A 错：只做行方向时，同一列里可能有多张图都和某条 caption 很像，列方向的约束能防止文本 embedding 塌到少数"万能 caption"上，讲义也强调 "InfoNCE penalizes rows AND columns (symmetric)"。B 错：对比学习的关键是**相对**排序，不是把每对的余弦回归到 1（那样所有向量都挤到一处也能满足）。C 错：CLIP 的卖点就是零人工类别标签。

### Q2 — 答案：A

每行 `-S[i][i] + LSE(S[i]) = -c + (c + ln N) = ln N`，列同理，平均后仍是 `ln 6 ≈ 1.7918`（已实际运行 `infonce_loss([[0.0]*6]*6)` 验证，得 1.7917594692280547）。这和 GPT 训练"初始 loss ≈ ln V"是同一个健全性检查：InfoNCE 本质上是 N 分类交叉熵。C 是 sigmoid loss 在全部 logit 为 0 时的值（代码同一输入输出 0.6931）。注意：真实的"随机 embedding"不是所有元素相等，DEMO 2 的 misaligned 在 tau = 0.07 时 loss 为 2.9754，**高于** ln 6——因为小 tau 把随机的余弦差放大，模型对错误答案"很自信"。

### Q3 — 答案：C

单位向量的余弦在 `[-1, 1]`，tau = 1 时正负例 logit 最多差 2，softmax 永远分不开（见 Q12）。除以 0.07 相当于放大约 14.3 倍。tau 越小，softmax 越尖，与正例最接近的负例（hard negative）得到的梯度越大。B 说反了。D 错：讲义 "CLIP learns log(1/tau), clipped to prevent collapse"——在 log 空间学习并设上限，防止 tau 塌缩到接近 0。A 错：tau 直接改变每个负例对梯度的贡献权重，影响 embedding 结构。

### Q4 — 答案：B

softmax 交叉熵的分母要对**整行**（全局 batch 的所有负例）求和，因此必须先把所有设备的 embedding 汇总（all-gather），并且要能算出完整的 `N × N` 行归一化。sigmoid loss 每个 pair 独立，讲义："Each pair's loss is independent. No all-gather needed. Each GPU computes its local block and sums." C 错：sigmoid loss 仍然大量使用负例（非对角线全是负例）。D 错：SigLIP 同样有 temperature（论文写成乘法的 `t`），并额外加 bias `b`。A 不是本质原因。

### Q5 — 答案：A

这就是 `zero_shot_classify` 的做法：

```python
    img = normalize(image)
    for name, vec in class_texts.items():
        scores.append((name, cosine(img, normalize(vec))))
    scores.sort(key=lambda p: p[1], reverse=True)
```

B 是 linear probe（需要标注数据，不是 zero-shot）。C 错：CLIP 没有文本 decoder，只有 encoder；"生成描述"是 BLIP-2/LLaVA 等生成式 VLM 的能力。D 是无监督聚类，与 CLIP 的跨模态对齐无关。

### Q6 — 答案：D

代码 `count` 在双重循环里累加 N² 次，所以返回 `Σ / N²`；讲义与 SigLIP 论文是 `Σ / N`。代码值 = 讲义值 / N。用 DEMO 1 的数据实测：tau = 0.07 时代码输出 0.9268，按 N 归一化应为 3.7071（= 0.9268 × 4）。只差一个常数因子，对优化方向没有影响，但会改变 loss 的数值量级和与学习率的配合，也使"代码输出可以直接对照论文数字"的假设失效。

### Q7 — 答案：C

DEMO 1 中对角线余弦约 0.999，非对角线余弦在 −0.004 到 0.165 之间（实际打印 tau = 1 的矩阵可见）。tau = 0.07 时正例 logit ≈ 14.3，`softplus(-14.3)` ≈ 0；而 12 个负例 logit 约 −0.06 ～ +2.4，softplus 是凸函数，正值部分的惩罚增长得比负值部分的收益快，平均下来大于 ln 2。bias 的作用正在于此：用同一组数据实测，tau = 0.07 时 bias 取 0 / −2 / −5 / −10 的代码输出分别为 0.9268 / 0.2471 / 0.0162 / 0.0036。讲义练习 2 让你思考的就是这个问题：每行只有 1 个正例、N−1 个负例，负例占绝对多数，若初始 bias 为 0，训练初期绝大部分梯度都在"把负例往下压"。A 错：代码的 `sigmoid` 是分段的数值稳定写法，正确。D 错：0.0000 只是四舍五入，实际值 6.2e-6，数值上没问题。

### Q8 — 答案：B

讲义："A linear probe ... beats zero-shot on in-domain tasks. Full finetuning beats linear probe on in-domain but can hurt zero-shot transfer. Three regimes with three trade-offs." A 错：zero-shot 只是基线。C 错：全量 finetune 会让 embedding 空间偏向目标域，可能破坏与文本塔的对齐。D 错：linear probe 冻结 encoder，只训练线性层。

### Q9 — 参考答案

1. InfoNCE（逐项已用 Python 验证）：
   - 行 0：`-2 + ln(e² + e^0.5) = ln(1 + e^-1.5) ≈ 0.2014`
   - 行 1：`-1 + ln(e^0 + e^1) = ln(1 + e^-1) ≈ 0.3133`
   - 列 0（元素 2.0, 0.0）：`ln(1 + e^-2) ≈ 0.1269`
   - 列 1（元素 0.5, 1.0）：`ln(1 + e^-0.5) ≈ 0.4741`
   - loss = `(0.2014 + 0.3133 + 0.1269 + 0.4741) / (2 × 2) ≈ 0.2789`（代码输出 0.27891999）
2. sigmoid loss（bias = 0）：正例项 `softplus(-2) = 0.1269`、`softplus(-1) = 0.3133`；负例项 `softplus(0.5) = 0.9741`、`softplus(0) = 0.6931`。总和 2.1074。
   - 代码（除以 N² = 4）：**0.5269**（代码输出 0.52685）
   - 讲义公式（除以 N = 2）：**1.0537**
3. 改为 1.9 后，行 0 变为 `ln(1 + e^-0.1) ≈ 0.6444`，列 1 变为 `ln(1 + e^0.9) ≈ 1.2412`，sigmoid 中该负例项变为 `softplus(1.9) ≈ 2.0394`。hard negative 的 logit 接近（甚至超过）正例时，所在行与列的交叉熵都急剧上升，这正是对比学习要"重点惩罚"的对象；tau 越小，这种惩罚越集中。

### Q10 — 参考答案

1. 字符码之和与字符顺序无关，任何**字母重排**都会碰撞。实测：`"a photo of a cat"` 与 `"a photo of a act"` 的和都是 1401，会得到完全相同的"embedding"。不同模板、不同类名也可能凑出相同的和。
2. 没有关系。`make_fake_embedding(seed)` 只是用种子生成 64 维高斯向量，"golden retriever"与"tabby cat"的向量之间没有任何语义结构，平均三个这样的向量也只是三个随机向量的平均。最后一行的 "+1-3 points" 是**写死的字符串**，不是实验结果；讲义正文给的数字是"80 个模板，ImageNet +3 点"。这个 demo 只演示了"平均"这个动作。
3. 正确做法：
   - 对每个类、每个模板，用**真实的文本 encoder** 编码 `t.format(class=...)`；
   - 每个模板的 embedding 先 **L2 归一化**，再在模板维度上求平均；
   - 平均后的向量**再归一化一次**，作为该类的原型向量（class prototype）。

   先归一化是为了让每个模板等权：不同模板的 embedding 范数不同，不归一化时范数大的模板会主导平均方向。最后再归一化是为了让后续余弦 = 点积。（本节代码的 `zero_shot_classify` 在比较前会再调用 `normalize`，所以最后一步缺失不影响排序，但"先归一化再平均"这一步缺失会影响结果。）

### Q11 — 参考答案

```python
import numpy as np

def infonce_np(img, txt, tau):
    I = img / np.linalg.norm(img, axis=1, keepdims=True)
    T = txt / np.linalg.norm(txt, axis=1, keepdims=True)
    S = I @ T.T / tau                                   # (N, N)
    def ce(M):                                          # 每行以对角线为正例的交叉熵
        m = M.max(axis=1, keepdims=True)
        lse = (m + np.log(np.exp(M - m).sum(axis=1, keepdims=True))).ravel()
        return (lse - np.diag(M)).mean()
    return (ce(S) + ce(S.T)) / 2

def siglip_np(img, txt, t=10.0, b=-10.0):
    I = img / np.linalg.norm(img, axis=1, keepdims=True)
    T = txt / np.linalg.norm(txt, axis=1, keepdims=True)
    Z = t * (I @ T.T) + b                               # logits
    y = 2 * np.eye(len(I)) - 1                          # 对角线 +1，其余 -1
    return np.logaddexp(0, -y * Z).sum() / len(I)       # -log σ(y·z) = softplus(-y·z)，除以 N
```

对拍（已实际运行）：用 DEMO 1 的 4 对数据，`infonce_np` 在 tau = 0.07 / 0.1 / 1.0 时分别为 6.235e-06 / 2.904e-04 / 0.77476，与代码 `infonce_loss` 完全一致。`siglip_np(t = 1/tau, b = 0)` 的结果是代码 `sigmoid_loss` 的 **4 倍（= N 倍）**，例如 tau = 0.07 时 3.7071 vs 0.9268——这就是 Q6 的归一化差异，对拍前要先统一口径。另外 `np.logaddexp(0, x)` 是数值稳定的 softplus，比代码中 `log(p + 1e-9)` 的写法更好：后者在 logit 极大时会把单项损失截断在约 20.7。用 SigLIP 论文的初始化 `t = 10, b = -10` 计算同一数据，结果约 0.6994。

### Q12 — 参考答案

1. 最理想情况下行损失 = `ln(1 + (N−1)·e^(−2/tau))`。tau = 1 时：
   - N = 4：`ln(1 + 3e^-2) ≈ 0.3408`
   - N = 32768：`ln(1 + 32767·e^-2) ≈ 8.397`
   而 tau = 0.07 时，N = 32768 的下界约 1.3e-8，几乎可以降到 0。（数值均已用 Python 计算。）
2. 说明 tau = 1 时即便 embedding 完美，loss 也被"卡"在很高的水平，梯度永远在推着所有向量走，而且 batch 越大越严重——因为负例越多分母越大。必须用小 tau 把 logit 范围放大到约 `±1/tau`。CLIP 初始化 0.07 是经验值；在 log 空间学习 `log(1/tau)` 能让参数可以取任意实数、梯度尺度更合理；再设上限（讲义 "clipped to prevent collapse"）防止 tau 过小导致 softmax 过尖、训练不稳定。本节代码中 tau 是固定的超参数，没有学习，这是一处简化。

### Q13 — 参考回答要点

- **结构**：双塔。图像 encoder（ViT 或 ResNet）+ 文本 encoder（小 Transformer），各自投影到同一 D 维空间并 L2 归一化。
- **数据**：讲义："400M pairs"的网络图像–alt text 对，"Zero supervised labels"。
- **损失**：batch 内 N×N 相似度矩阵除以可学习 temperature，按行、按列各做交叉熵（对称 InfoNCE）。讲义："CLIP trained at batch 32k; scale matters"——负例越多信号越强。
- **为什么能 zero-shot**：文本塔把"任意自然语言描述"映射进与图像相同的空间，类名套模板后就成了一个"分类器权重向量"。分类 = 在这些向量中找与图像余弦最大的那个，不需要在目标类上训练。
- 加分点：zero-shot 分类本质上就是"用文本 encoder 生成线性分类头的权重"；prompt 模板与 ensemble 会影响 1–5 个点（讲义 Key Terms）。
- 常见误区：把 CLIP 说成生成模型。CLIP 不能生成描述，只能打分和检索。

### Q14 — 参考回答要点

- **InfoNCE（softmax）**：每行是 N 分类，`-log(exp(s_ii) / Σ_j exp(s_ij))`，加列方向取平均。负例之间**相互竞争**同一个分母，loss 依赖整行，因此与 batch 大小、全局归一化强绑定。
- **Sigmoid（SigLIP）**：每个 pair 一个二分类 `-log σ(z_ij · (t·cos_ij + b))`，`z_ij = ±1`。pair 之间独立，不需要行归一化。
- **temperature**：两者都需要把 `[-1, 1]` 的余弦放大；CLIP 学 `log(1/tau)` 并加上限，SigLIP 的写法是乘以 `t = exp(t')`。
- **bias**：SigLIP 特有。每行 1 正 N−1 负，极度不平衡；`b` 初始化为很大的负数（论文为 −10），让初始预测偏向"不匹配"，避免训练初期被大量负例的梯度淹没（见 Q7 的实测：bias 从 0 降到 −10，同一数据上的代码 loss 从 0.9268 降到 0.0036）。
- **batch 依赖**：讲义：SigLIP 能廉价地扩展到 32k–512k 的 batch；softmax 版本的分母在大 batch 下需要更多通信。
- 加分点：sigmoid loss 在小 batch 下也能工作得不错；softmax 版本对 batch 越大越好有更强的依赖。

### Q15 — 参考回答要点

- **softmax InfoNCE 的实现**：每张卡只有 `32768 / 512 = 64` 个样本。要用全局 32k 个负例，每张卡必须 all-gather 全部图像与文本 embedding（每个 `32768 × D`），才能计算本地 64 行与全部 32768 列的 logits，以及每行的 softmax 分母；列方向同理。
- **瓶颈**：
  - 通信：每一步都要 all-gather 两份全局 embedding，反向时还要把梯度送回各卡；
  - 显存：若在一处完整物化 `32768 × 32768` 的 logits 矩阵，FP32 下约 4.3GB（`32768² × 4` 字节），再加 softmax 中间量；实际实现会让每卡只算自己的 `64 × 32768` 行块。
- **换成 sigmoid**：讲义的说法是"每对独立，无需 all-gather，每卡算本地块再求和"。更精确地理解：如果仍想让每个样本看到全局负例，还需要在设备间交换 embedding，但因为没有行归一化，可以**分块**、**流式**地逐块累加损失（例如环形地轮换文本 embedding），不必同时持有全部 embedding 和整行 logits，峰值显存和同步压力都更小。讲义练习 4 要求你读 SigLIP 论文第 4 节，对比两者的复杂度。
- 加分点：提到梯度检查点、混合精度，以及 batch 继续增大时边际收益递减。
- 常见误区：以为"各卡只算本地 64 × 64 的块"就等价于 32k batch——那样负例只有 63 个，对比信号弱得多。

### Q16 — 参考回答要点

- **第一步：zero-shot 基线**。为 200 个类目设计模板（如 `a product photo of a {class}`），每类多个模板做 ensemble；类名要写成自然语言而非内部编码（"女士真皮短靴"而不是 `CAT_1043`）。多语言场景优先选多语言模型（讲义：SigLIP 2 覆盖 100+ 语言，CLIP 只有英文）。
- **以文搜图**：离线把全部商品图编码入向量库（ANN 索引），查询时编码文本、取 top-k；可再用更强的模型重排。
- **评估**：人工标注一个分层抽样的测试集，报告 top-1 / top-5 准确率、每类召回；检索看 Recall@K、nDCG。用 top-1 分数作为置信度，低于阈值转人工（本节 Ship It 技能建议低于 0.2 时告警）。
- **何时升级**：zero-shot 在长尾或细粒度类目（相近款式）上不够时，先用少量标注做 linear probe（便宜、可保留原始 embedding 用于检索）；如果仍不够且标注充足，再考虑 finetune，并评估对检索与其它类目的 zero-shot 是否有回退。
- 常见误区：直接比较不同 checkpoint 的相似度分数（技能文件："SigLIP and CLIP score on different scales"）；用单个类名不加模板。

### Q17 — 参考回答要点

- **为什么仍用作视觉塔**：讲义："The benchmark is saturating; the real value is the embedding space that downstream VLMs consume." 对比预训练让视觉特征天然"说语言的方言"，接到 LLM 上只需一个轻量 projector（下一节 Q-Former、第 05 节 LLaVA 的 MLP）。SigLIP 2 还加强了 dense features（分割、深度），并支持 NaFlex 任意分辨率（第 06 节）。
- **已知短板**：
  - 训练目标是"整图 ↔ 整句"的全局匹配，细粒度信息（小物体、文字、计数、空间关系）不一定被保留；
  - caption 是噪声 alt text，embedding 会继承网络数据的偏差；
  - 固定输入分辨率（如 224/336）会丢失高分辨率细节，这是后续 any-resolution 方案要解决的问题；
  - zero-shot 对预训练分布之外的类别不可靠（技能文件的 Honesty notice）。
- 加分点：VLM 接入的是 ViT 的**全部 patch tokens**（如 LLaVA 的 576 个），而不是 CLIP 训练时用于对比的那个 pooled 向量，以保留空间信息；LLaVA 系实现通常取倒数第二层的特征（实现细节，讲义未展开）。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：CLIP 的图像塔就是 ViT，patch token 是一切的起点。
- [阶段 04 · 18 开放词表（Open-Vocabulary）视觉——CLIP](../../../04-computer-vision/18-open-vocab-clip/docs/zh.md)：从计算机视觉角度第一次接触 CLIP。
- [阶段 04 · 17 自监督视觉 — SimCLR、DINO、MAE](../../../04-computer-vision/17-self-supervised-vision/docs/zh.md)：单模态对比学习（SimCLR 的 NT-Xent 与 InfoNCE 同源）。
- [阶段 03 · 05 Loss Functions](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵、BCE 与 log-sum-exp 数值稳定技巧。
- [阶段 07 · 09 Vision Transformers (ViT)](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：图像 encoder 的结构细节。

### 本节被哪些后续内容用到
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：冻结 CLIP 类视觉塔，再接到冻结的 LLM 上。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：CLIP ViT-L/14 作为 LLaVA 的视觉塔。
- [阶段 12 · 06 任意分辨率视觉：Patch-n'-Pack 与 NaFlex](../../06-any-resolution-patch-n-pack/docs/zh.md)：SigLIP 2 的 NaFlex 能力。
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../24-multimodal-rag-cross-modal/docs/zh.md)：用 CLIP 类 embedding 做以文搜图。
- [阶段 08 · 14 Evaluation — FID、CLIP 分数、人类偏好](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：CLIP 分数作为图文一致性指标。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：all-gather 等集合通信原语。
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../../19-capstone-projects/62-vision-language-pretraining/docs/zh.md)：综合项目中亲手实现对比预训练。

### 延伸关键词
`InfoNCE` · `NT-Xent` · `logit scale` · `SigLIP / SigLIP 2` · `learnable bias` · `all-gather` · `prompt ensemble` · `linear probe` · `OpenCLIP` · `LAION-2B` · `ALIGN` · `EVA-CLIP` · `hard negative mining`
