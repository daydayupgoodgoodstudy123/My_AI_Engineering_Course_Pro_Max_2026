# 测验 · 多模态 Evaluation（Multimodal Evaluation）

> **阶段 19 · 综合项目 · 第 63 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练 loss ≠ 评估 | 训练 loss 只衡量对训练分布的拟合；能否在 held-out 数据上排序、回答、写 caption 要用独立的评估面来测 |
| 2 | 三个评估面 | 检索（R@1/5/10）、VQA（exact match）、captioning（BLEU-4），分别对应 MS-COCO/Flickr30K、VQA v2/GQA、COCO Caption 等基准 |
| 3 | Recall@K | 由 `(N, N)` 相似度矩阵计算：每行取 top-K 列，正确列（对角线）落在其中的行所占比例；行方向是图→文，转置后是文→图 |
| 4 | 随机基线 | N 个候选时 R@K 的随机期望是 `K/N`（N=50：R@1 0.02、R@5 0.10、R@10 0.20）；VQA 随机为 `1/答案词表大小` |
| 5 | VQA exact match 与 soft accuracy | EM 是每个样本 0/1；VQA v2 有 10 个人工答案，`acc = min(#人类答案与预测相同 / 3, 1)` |
| 6 | BLEU-4 | `BP × exp(Σ ¼·log p_n)`，`p_n` 是 clipped（截断）的 n-gram 精确率，多参考时每个 n-gram 的上限取各参考中的最大出现次数 |
| 7 | Brevity penalty | 生成长度 g ≤ 参考长度 r 时 `BP = exp(1 − r/g)`，防止"只生成几个最稳的词"刷高精确率；代码取与 g 最接近的参考长度 |
| 8 | 平滑 | 短句子某阶 n-gram 精确率为 0 会让整句 BLEU 变成 0，需要平滑；但平滑也会给完全无关的输出一个不小的"保底分" |
| 9 | Held-out 与数据泄漏 | 评估集必须与训练集不相交；本节的"held-out"评估集 caption 与训练集 caption **逐条相同**，只有图像噪声不同 |
| 10 | 样本量与置信度 | N = 50 时 1 个样本就是 0.02；R@10 ≈ 0.2 的标准误约 0.057，小幅变化不足以下结论 |

### 核心技能（能动手做到）

- [ ] 给定一个小相似度矩阵，手算两个方向的 R@1、R@K 与 MRR
- [ ] 不借助任何库写出带 clipping、多参考、brevity penalty 的 BLEU-4，并与 NLTK 的 `sentence_bleu` 对照
- [ ] 计算一个"随机输出"在当前 BLEU 实现下的得分，作为 captioning 的真实随机基线
- [ ] 实现 VQA v2 的 soft accuracy，并说明为什么需要答案归一化
- [ ] 检查评估集与训练集是否有重叠（caption、图像、答案）并修复
- [ ] 解读 before/after 指标表：区分"真实提升"与"噪声 / 泄漏 / 语言先验"

---

## 二、基础自测（选择题）

**Q1.** 评估集有 N = 50 对图文，模型完全随机地给出相似度。R@10 的期望值约为：

- A. 0.20
- B. 0.10
- C. 0.02
- D. 0.50

**Q2.** 3 张图、3 段 caption 的相似度矩阵（行 = 图，列 = caption，第 i 张图与第 i 段 caption 匹配）：

```text
        c0    c1    c2
img0  0.90  0.80  0.10
img1  0.70  0.60  0.20
img2  0.30  0.95  0.50
```

`recall_at_k(sim, 1)` 返回的 `(i2t, t2i)` 是：

- A. `(1/3, 1/3)`
- B. `(2/3, 1/3)`
- C. `(1/3, 2/3)`
- D. `(2/3, 2/3)`

**Q3.** 生成序列 `[7, 7, 7, 7]`，唯一参考 `[7, 3, 5, 9]`。BLEU 的 **clipped 1-gram 精确率** p₁ 是：

- A. 1.0（生成的 4 个 token 都出现在参考中）
- B. 0.5
- C. 0
- D. 0.25（token 7 在参考中只出现 1 次，最多只能算 1 次命中）

**Q4.** 生成长度 g = 5，最接近的参考长度 r = 10，四阶精确率都是 1。按本节 `bleu4`，得分约为：

- A. 1.0
- B. 0.368
- C. 0.5
- D. 0.135

**Q5.** VQA v2 的 soft accuracy：某问题 10 位标注者中有 2 位给出了与模型预测相同的答案。该样本得分是：

- A. 0.2
- B. 0
- C. 1.0
- D. 约 0.667

**Q6.** 本节 demo 中，训练**前**的 BLEU-4 是 0.1220。我们用随机 token 生成 8 个词再算 BLEU，平均约 0.130。最主要的原因是：

- A. 平滑：任何一阶匹配数为 0 时，把该阶精确率记为 `1/(总数+1)`，于是完全不相关的输出也能拿到约 0.13 的"保底分"
- B. 随机初始化的模型已经学会了 caption 的规律
- C. brevity penalty 让短句得分偏高
- D. 参考 caption 有 3 条，所以分数被乘了 3

**Q7.** 讲义称评估集"sampled from a seed disjoint from the training corpus"，代码用 `build_eval_suite(seed=7777)` 而训练用 `make_mock_corpus(seed=1)`。实际情况是：

- A. 两者完全不相交，评估是真正的 held-out
- B. 两者的图像完全相同，只是 caption 不同
- C. 两者的 caption 逐条相同（caption 只由下标 i 决定、与 seed 无关），图像也属于同一亮度档，只是噪声不同——存在严重泄漏
- D. 评估集是训练集的随机子集

**Q8.** 某个 query 的正确结果排在第 3 位。下列说法正确的是：

- A. R@1 = 1，R@5 = 1，倒数排名 = 1/3
- B. R@1 = 0，R@5 = 1，倒数排名（reciprocal rank）= 1/3
- C. R@1 = 0，R@5 = 0，倒数排名 = 3
- D. R@K 与 MRR 对这个 query 给出的信息完全相同

---

## 三、动手 / 代码题

**Q9.** 阅读 `bleu4` 的平滑与长度处理：

```python
        if total == 0:
            return 0.0

        if clipped == 0:
            if smoothing:
                clipped = 1
                total = total + 1
            else:
                return 0.0
        log_p_sum += weights[n - 1] * math.log(clipped / total)
```

1. docstring 说这是 Chen & Cherry "method 1"。NLTK 的 `SmoothingFunction().method1` 是给 0 计数加一个 epsilon（默认 0.1）。对生成 `[1, 4, 7, 99, 13, 16, 50, 22]`、参考 `[[1, 4, 7, 10, 13, 16, 19]]`，本节实现得 0.2937，NLTK method1 得 0.1729、method2 得 0.3493。本节实现到底是哪一种？
2. 计算 `bleu4([7, 7, 7, 7], [[7, 3, 5, 9]])`（默认平滑）。这个结果说明了什么问题？
3. `bleu4([1, 4, 7], [[1, 4, 7, 10, 13]])` 返回多少？为什么平滑救不了它？这与讲义练习 3 的"NaN-safe"有什么关系？

**Q10.** 验证并修复评估集泄漏。

```python
    base_pairs = make_mock_corpus(seed=seed, n_pairs=n_samples,
                                  vocab_size=vocab_size, max_len=max_len)
```

1. 写几行代码检查 `build_eval_suite(7777, 50, 128, 10)` 的 caption 与 `make_mock_corpus(1, 200, 128, 10)` 前 50 条 caption 是否相同。我们实测结果是多少条相同？
2. 为什么不同的 seed 没能产生不同的 caption？
3. 给出两种修复方案，并说明哪种更接近真实基准的做法。

**Q11.** 阅读 VQA 部分：

```python
        answer_id = int(ids[0, 0].item())          # build_eval_suite 中
        ...
        vqa_logits = model.decoder(vqa_q, vqa_memory)
        last_non_pad = (vqa_q != PAD_ID).sum(dim=1).clamp(min=1) - 1
        last_step = vqa_logits[batch_idx, last_non_pad, :]
        preds = last_step.argmax(dim=-1).tolist()
```

1. 问题 token 是怎么生成的？答案又是什么？这个任务在原则上能否通过"看图 + 读问题"学会？
2. 模型从未在 VQA 数据上训练。它在最后一个问题 token 处预测的"下一个 token"实际上更可能是什么？（提示：我们实测 32% 的预测恰好等于"最后一个问题 token + 3"。）
3. 讲义 Build It 说训练后 "VQA improving above random"，实际运行结果是 0.02 → 0.00。如何解读？
4. 完成讲义练习 2：写 `vqa_soft_accuracy(pred, human_answers)`。

**Q12.** 完成讲义练习 4：给 `recall_at_k` 配一个 `mean_reciprocal_rank(sim)`（图→文方向），并回答：

1. N = 50 时随机模型的 MRR 期望值是多少？
2. 本节训练后的模型我们实测 MRR ≈ 0.107、正确结果的中位排名为 18。结合 R@10 = 0.26，这说明什么？
3. 如果两个正确候选的相似度并列，`topk` 和你的 MRR 实现分别会怎么处理？

---

## 四、面试高频题

**Q13.**（基础必考）多模态模型通常怎么评估？请分别说明检索、VQA、captioning 的标准指标、计算方法和代表基准。

**Q14.**（原理深挖）BLEU 用于图像描述评估有哪些缺陷？CIDEr 做了什么改进？为什么现在越来越多地使用基于模型的评估？

**Q15.**（工程实践）你要为团队搭一个多模态模型的评估流水线，会如何设计数据集划分、基线、指标与报告方式，避免"指标好看但模型没用"？

**Q16.**（场景设计）训练前后对比：R@10（文→图）从 0.20 升到 0.38，BLEU-4 从 0.122 升到 0.173，VQA EM 从 0.02 降到 0.00，评估集只有 50 个样本。你的老板问"模型变好了吗？"，你怎么回答？

**Q17.**（追问型）生成式 VLM 输出的是自由文本，比如问 "How many dogs?" 模型答 "There are two dogs."，参考答案是 "2"。exact match 怎么处理？还有哪些评估方法？

---

## 五、参考答案与解析

### Q1 — 答案：A

随机排序时，正确候选落在 50 个位置中任一位置的概率相等，落在前 10 位的概率是 `10/50 = 0.20`。讲义表格同样给出 R@10 随机基线 0.20。B 是 R@5 的基线；C 是 R@1 的基线；D 对应 K = 25。

### Q2 — 答案：C

- 图→文（按行看最大值）：img0 → c0（0.90）✓；img1 → c0（0.70）✗；img2 → c1（0.95）✗。R@1 = 1/3。
- 文→图（按列看最大值，即 `sim.T` 的行）：c0 → img0（0.90）✓；c1 → img2（0.95）✗；c2 → img2（0.50）✓。R@1 = 2/3。

已用 `recall_at_k` 实际验证：`(0.3333, 0.6667)`。两个方向可以不同，所以讲义要求两个都报告。A、B、D 都是看错方向或看错最大值的结果。

### Q3 — 答案：D

modified（clipped）precision：每个生成 n-gram 的计数最多截断到它在参考中出现的最大次数。token 7 生成了 4 次，但参考中只有 1 次，所以 clipped = 1，p₁ = 1/4 = 0.25。A 是未截断的朴素精确率——这正是 BLEU 要防止的"重复刷分"；B、C 没有依据。

### Q4 — 答案：B

g = 5 ≤ r = 10，`BP = exp(1 − 10/5) = exp(−1) ≈ 0.368`；精确率部分为 1，所以 BLEU ≈ 0.368（已实际计算）。A 忘了 brevity penalty；C 用了 g/r；D 是 `exp(−2)`。brevity penalty 存在的意义：如果只用精确率，模型只输出几个最有把握的词就能得高分。

### Q5 — 答案：D

`min(2/3, 1) ≈ 0.667`。讲义："accuracy is `min(human_count / 3, 1)` if any matches"——至少 3 位标注者同意即得满分。A 是简单的比例 2/10；B 是 exact match 对"多数答案"的判定；C 需要 ≥ 3 位同意。

### Q6 — 答案：A

当生成与参考完全不相关时，四阶的 clipped 计数都是 0，平滑后精确率分别为 `1/9, 1/8, 1/7, 1/6`（8 个 token 的 1–4 gram 总数分别是 8、7、6、5，再各加 1），几何平均 `≈ 0.135`（实际计算）；乘上 brevity penalty 后约 0.12–0.13。我们用随机 token 实测平均 0.130，与训练前的 0.122 基本相同——**训练前的 BLEU 就是随机水平**。B 错，未训练的模型没有学到任何东西；C 错，brevity penalty 只会降低分数；D 错，多参考只影响 clipping 上限与参考长度选择，不乘倍数。

### Q7 — 答案：C

`make_mock_corpus` 中 caption 的公式 `1 + (base + 3j + i%5) % (V−1)`、`base = (i*17) % (V−50)`、长度 `6 + i%8` 全都只依赖下标 i，seed 只影响图像噪声（`img_seed = seed*100 + i`）。我们实测：50 条评估 caption 与训练集前 50 条 caption **50/50 完全相同**；图像亮度档 `i % 7` 也相同（例如第 3 个样本均值 0.426 vs 0.431）。所以文本 encoder 在训练中已经见过全部评估 caption。A 是讲义的说法；B 说反了；D 不准确——不是子集抽样，而是"同下标同 caption、不同噪声的图"。

### Q8 — 答案：B

排在第 3 位：不在 top-1（R@1 = 0），在 top-5（R@5 = 1），倒数排名 1/3。讲义练习 4："MRR is sensitive to where the correct item lands beyond the top K; R@K is sensitive to whether it lands in the top K." A 的 R@1 错；C 把倒数排名写成了排名本身，且 R@5 错；D 错，排第 3 和排第 5 的 R@5 相同，但 MRR 不同。

### Q9 — 参考答案

1. 本节实现是"**只对 0 计数的阶做 add-one**（分子分母各加 1）"。它既不是 NLTK 的 method1（给 0 计数加 epsilon = 0.1，对应 0.1729），也不完全是 method2（对 n ≥ 2 的**所有**阶都分子分母加 1，对应 0.3493）。在不需要平滑的情况下，本节实现与 NLTK 完全一致（例如 `[1,4,7,…,22]` 对 6 token 参考都是 0.6804；`[1,2,3,4]` 对 8 token 参考都是 0.3679）。所以 docstring 与讲义中"method 1"的说法不准确。
2. 实测 `≈ 0.3195`：p₁ = 1/4（clipped），p₂ = 1/(3+1)，p₃ = 1/(2+1)，p₄ = 1/(1+1)，几何平均 `(1/96)^(1/4) ≈ 0.32`，BP = 1。一个只会重复同一个 token 的退化输出拿到了 0.32 分——平滑在短句、低计数场景下把分数抬得非常高，各阶 0 匹配反而被"奖励"成 1/2、1/3。另外完全不相交的 `[1]*8` 对 `[2]*8` 也能得 0.1349（测试 `test_disjoint_vocab_smoothed_is_below_match` 只要求它低于完美匹配）。
3. 返回 **0.0**。生成长度 3 < 4，4-gram 总数 `total == 0`，代码在平滑判断**之前**就 `return 0.0`。前三阶精确率都是 1 也没用。讲义练习 3 要求"NaN-safe 地处理空序列"——空序列这里已经直接返回 0；真正值得处理的是"长度 < 4"的情况：可以对 `total == 0` 的阶跳过并重新归一化权重（例如只用 1–3 gram），或按 method1 给一个 epsilon。

### Q10 — 参考答案

1. 检查代码：

```python
suite = build_eval_suite(7777, 50, 128, 10)
train = make_mock_corpus(1, 200, 128, 10)
same = sum(torch.equal(suite.retrieval[i].caption_ids, train[i][1]) for i in range(50))
print(same)   # 实测 50
```

   50 条全部相同。

2. caption 只由下标 i 计算，seed 只进入 `img_seed` 控制图像噪声，所以换 seed 只换了图像的噪声，没有换 caption；而亮度 `bias = (i % 7) / 7` 也只由 i 决定。
3. 两种方案：
   - **按下标切分**（推荐，最接近真实基准）：一次性生成 250 条，前 200 条训练、后 50 条评估，保证 i 不重叠；
   - **让 caption 依赖 seed**：例如 `base = (i * 17 + seed * 31) % (V − 50)`。但即便如此，等差数列的"+3"结构在训练和评估中仍然相同，模型靠文本规律也能在 captioning 上拿分。
   - 真实基准的做法：用官方固定的 train/val/test 划分（如 COCO Karpathy split），并对图像做去重（感知哈希）、对 caption 做 n-gram 重叠检查，防止网页级预训练数据泄漏到评估集。

### Q11 — 参考答案

1. 问题 token 是用 `q_rng.integers(1, vocab_size)` 生成的**随机 token**，长度 3–4（`max_len // 2 = 5`，`integers(3, 5)` 取 3 或 4），与图像、答案都无关；答案是对应 caption 的第一个 token `ids[0, 0]`，只由下标 i 决定（50 个样本中有 39 个不同答案）。图像只携带 `i % 7` 的亮度信息，无法唯一确定 i，所以这个任务**原则上学不会**（最多利用亮度档缩小范围）。
2. decoder 是在 caption 上训练的 LM，它在任何 token 序列末尾都会倾向于"续写等差数列"，即预测"最后一个 token + 3"。实测 32% 的预测恰好等于"最后一个问题 token + 3"——模型把随机问题当成 caption 在续写，而不是在回答问题。
3. 0.02 = 50 个里碰巧对 1 个，0.00 = 0 个；随机基线 `1/128 ≈ 0.008`。两者都在噪声范围内（p = 0.02、n = 50 的标准误约 0.02），不能说明任何提升或下降。讲义"VQA improving above random"与实际输出不符。要让 VQA 有意义，需要：答案确实可由图像 + 问题推出、模型在 VQA 数据上训练过（或有专门的答案头）、评估集足够大。
4. 参考实现：

```python
def vqa_soft_accuracy(pred, human_answers):
    """human_answers: 10 个标注答案（已归一化）。"""
    matches = sum(1 for a in human_answers if a == pred)
    return min(matches / 3.0, 1.0)

def vqa_soft_accuracy_mean(preds, all_human_answers):
    scores = [vqa_soft_accuracy(p, h) for p, h in zip(preds, all_human_answers)]
    return sum(scores) / max(1, len(scores))
```

   注：VQA v2 官方脚本还会在 10 选 9 的子集上取平均以减小方差，并在比较前做答案归一化（小写、去标点、数字词转数字、去冠词）。

### Q12 — 参考答案

```python
def mean_reciprocal_rank(sim: torch.Tensor) -> float:
    n = sim.shape[0]
    correct = sim.diag().unsqueeze(1)                 # (N, 1)
    ranks = (sim > correct).sum(dim=1) + 1            # 比正确项严格更高的个数 + 1
    return (1.0 / ranks.float()).mean().item()
```

1. 随机时正确项的排名在 1..N 上均匀分布，`E[1/rank] = H_N / N`。N = 50：`H_50 ≈ 4.499`，MRR ≈ **0.090**（已实际计算）。
2. MRR 0.107 只比随机的 0.090 略高；中位排名 18（随机约 25）；R@10 = 0.26 比随机 0.20 略高。三个指标一致地表明：模型有一点点排序信号，但离"能用"很远。MRR 提供了 R@K 看不到的信息：正确项大多排在 10–30 名之间，而不是"差一点就进 top-10"。
3. `topk` 在并列时的顺序不保证（实现相关），可能把正确项排在前也可能在后；上面的 MRR 用 `>` 严格比较，相当于"并列时对正确项最乐观"。严谨的做法是取并列的平均排名，或在相似度上加极小的确定性扰动。真实数据中因为浮点相似度几乎不会并列，但 batch 内存在**重复图像/重复 caption** 时必须考虑。

### Q13 — 参考回答要点

- **检索**：对图像和文本 embedding 计算余弦相似度矩阵，报告 R@1/5/10（图→文、文→图两个方向），有时加 MRR、mean/median rank。基准：MS-COCO 5K、Flickr30K；零样本分类（ImageNet）可视为"图→类别名文本"的检索。
- **VQA**：模型给出答案，与参考比较。单答案 exact match；VQA v2 用 10 人标注的 soft accuracy `min(n/3, 1)`。基准：VQA v2、GQA、OK-VQA。
- **Captioning**：生成 caption 与多条参考比较，BLEU-4（n-gram 精确率 + brevity penalty）、METEOR、CIDEr（TF-IDF 加权 n-gram 一致性）、SPICE（场景图）。基准：COCO Caption、NoCaps、Flickr30K。
- **共同原则**：held-out 数据、报告随机基线、两个方向、多参考。
- 加分点：讲义"Each metric is a thin function... Real benchmark suites plug into the same function shapes"——评估代码与数据加载分离。

### Q14 — 参考回答要点

- **BLEU 的缺陷**：
  - 只看 n-gram 表面重合，同义词、换种说法都被扣分；
  - 对所有 n-gram 一视同仁，"a / the / of" 这类高频词的匹配和关键名词的匹配权重相同；
  - 句子级 BLEU 在短句上方差很大，必须平滑，而平滑会给退化输出保底分（见 Q9：重复 token 得 0.32）；
  - 原本是 corpus 级指标（先累加全语料的计数再算），本节对每个样本算句子级 BLEU 再平均，两者不等价。
- **CIDEr**：对 n-gram 做 TF-IDF 加权，在所有图像的参考中都很常见的 n-gram 权重低、信息量大的 n-gram 权重高；用生成与参考 TF-IDF 向量的余弦相似度，对多参考取平均。COCO 上与人类判断相关性更高。
- **基于模型的评估**：CLIPScore（用 CLIP 计算图与生成 caption 的相似度，不需要参考）、用强 LLM/VLM 做裁判；能理解语义，但有模型偏差、成本和可复现性问题。
- 常见误区：只报 BLEU-4 就宣称 caption 质量提升。

### Q15 — 参考回答要点

- **数据划分**：固定的 train/val/test，test 只在最终报告时使用；检查训练集与评估集的图像去重（哈希/感知哈希）与文本 n-gram 重叠，预训练数据来自网络时尤其要做污染检测（本节 demo 就有 caption 完全重叠的问题）。
- **基线**：随机基线（R@K = K/N、BLEU 的随机输出得分）、**盲测基线**（不给图像只给文本，检查语言先验能拿多少分）、上一版本模型、公开模型。
- **指标**：每个能力至少一个主指标 + 辅助指标；检索两个方向；VQA 用 soft accuracy 并做答案归一化；captioning 用 CIDEr + 人工抽检。
- **统计**：报告样本量、置信区间（bootstrap），小评估集上的小变化不下结论。
- **报告**：before/after 表格 + 学习曲线（讲义练习 5：多个 checkpoint 上评估，确认指标轨迹与 loss 轨迹一致）+ 错误样例分析。
- **自动化**：评估函数与数据加载解耦，每次训练自动跑，结果入库可比较。

### Q16 — 参考回答要点

- **先看基线**：N = 50，R@10 随机基线 0.20；文→图 0.38 高于基线约 3 个标准误（`sqrt(0.2×0.8/50) ≈ 0.057`），可能是真实信号；图→文 R@10 0.26 只高出约 1 个标准误。
- **BLEU**：随机输出在此实现下约 0.13，0.122 → 0.173 的提升里有多少来自"学会等差数列"这种语言先验？我们实测训练后 50 张图只生成了 4 种不同的 caption——模型几乎不看图。
- **VQA**：0.02 和 0.00 分别是 1 个和 0 个样本答对，都在噪声范围内；而且这个任务原则上不可学、模型也没在 VQA 上训练过。
- **数据问题**：评估 caption 与训练 caption 完全相同，检索结果存在泄漏，真实 held-out 表现只会更差。
- **结论**：可以说"检索有初步信号，captioning 和 VQA 没有证据表明在利用图像"；下一步：修复泄漏、扩大评估集、加盲测基线与置信区间、用 CIDEr 或人工抽检。
- 加分点：不把"所有数字都上升了"当作结论，而是逐个指标对照基线和噪声。

### Q17 — 参考回答要点

- **答案归一化**：小写、去标点、去冠词（a/an/the）、数字词转数字（"two" → "2"）、去多余空格；VQA v2 官方评估脚本就包含这类规则。
- **约束输出**：在 prompt 中要求"用一个词或数字回答"，或在训练时使用短答案格式。
- **抽取**：用规则或小模型从长回答中抽出答案再比较。
- **选择题化**：把问题改成多选（如 MMBench 一类做法），比较选项字母，避免自由文本匹配问题。
- **LLM-as-judge**：让强模型判断回答与参考是否语义一致；需要校准与抽样人工复核。
- **soft accuracy**：多个人工答案覆盖不同说法。
- 常见误区：直接用字符串相等做 EM，会严重低估生成式模型的真实能力。本节代码把"预测 token id 与参考 id 相等"当作 EM，是单 token 分类式 VQA 的简化。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../62-vision-language-pretraining/docs/zh.md)：本节直接 import 它的 `MultimodalModel` 和 `make_mock_corpus`，评估它训练出的模型。
- [阶段 19 · 61 Cross-Attention 融合](../../61-cross-attention-fusion/docs/zh.md)：VQA 与 captioning 都通过它的 decoder 读取图像。
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：文本模型的评估流水线。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：基准评估与数据污染的一般原则。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：基于模型的评估方法。

### 本节被哪些后续内容用到
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：R@K、MRR 在 RAG 检索评估中再次出现。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：检索指标用于比较不同检索器。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：BLEU、ROUGE 等经典指标的系统讲解。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：把多个评估面组装成评估执行器。
- [阶段 12 · 22 文档与图解理解](../../../12-multimodal-ai/22-document-diagram-understanding/docs/zh.md)：文档 VQA 类基准。

### 延伸关键词
`Recall@K` · `MRR` · `median rank` · `VQA soft accuracy` · `answer normalization` · `BLEU-4` · `brevity penalty` · `BLEU smoothing` · `CIDEr` · `SPICE` · `CLIPScore` · `data contamination` · `blind baseline` · `bootstrap confidence interval`
