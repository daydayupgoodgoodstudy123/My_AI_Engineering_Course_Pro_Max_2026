# 测验 · 说话人识别与验证（Speaker Recognition & Verification）

> **阶段 06 · 语音与音频 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三类任务 | 验证（verification，1:1，"这是 Alice 吗？"）、辨认（identification，1:N，"这是谁？"）、开集（open-set，测试者可能根本没注册） |
| 2 | 技术演进 | 2018 年前 GMM-UBM + i-vector（怕信道变化）→ x-vector（TDNN + 统计池化）→ 2020 年后 ECAPA-TDNN、WavLM 等 |
| 3 | 基本管线 | 注册：采集 5–30 秒语音算出定长 embedding（ECAPA 为 192 维）；验证：算测试语音的 embedding，与注册 embedding 求余弦，和阈值比较 |
| 4 | ECAPA-TDNN | 带 squeeze-excitation 的 1D 卷积块 + 注意力池化 + 线性层到 192 维；用 AAM-softmax 在 VoxCeleb 上训练 |
| 5 | AAM-softmax | 对正确类别把角度加上间隔 `m`，用 `cos(θ + m)` 代替 `cos θ`，再乘尺度 `s`；典型 `m = 0.2`、`s = 30`，强制类间角度分离 |
| 6 | EER | 调整阈值使误接受率（FAR）= 误拒绝率（FRR），此时的错误率即 EER；报告 EER 时要同时报告阈值 |
| 7 | 打分后端 | 余弦（最常用）、PLDA（概率线性判别分析，似然比打分）、S-norm / AS-norm（用冒认者 cohort 的均值和标准差归一化分数，跨域评估必备） |
| 8 | 说话人分离（diarization） | "谁在什么时候说话"：VAD → 分段 → 每段 embedding → 聚类 → 平滑边界；指标 DER = 漏检 + 虚警 + 说话人混淆 |
| 9 | 上线常见坑 | 信道不匹配（网络视频 vs 电话）、测试语音短于 3 秒 EER 急剧变差、带噪注册污染锚点、跨条件固定阈值、未 L2 归一化就算余弦 |
| 10 | 防欺骗 | 涉及资金安全的部署必须加反欺骗前端（AASIST、RawNet2）、活体挑战或回放检测 |

### 核心技能（能动手做到）

- [ ] 用 MFCC 统计量（均值 + 标准差）构造一个玩具说话人 embedding，并做 L2 归一化
- [ ] 从同一说话人 / 不同说话人的所有组合构造 trial 列表，算出两类分数的分布
- [ ] 从零实现 EER 计算，能手算一个小例子，并能发现"初始最优值设错导致永远不更新"一类的 bug
- [ ] 实现注册向量的平均与重新归一化，以及带"未知"拒识的开集辨认
- [ ] 解释 AAM-softmax 与普通 softmax、CosFace、SphereFace 的区别
- [ ] 为一个具体场景（银行声纹登录、会议转写）给出模型、注册协议、打分、阈值调优和防欺骗方案

---

## 二、基础自测（选择题）

**Q1.** 用户声称自己是 Alice，系统判断"这段语音是不是 Alice 说的"，这属于：

- A. 说话人辨认（identification，1:N）
- B. 说话人验证（verification，1:1）
- C. 说话人分离（diarization）
- D. 语音识别（ASR）

**Q2.** EER（Equal Error Rate）的定义是：

- A. 在默认阈值 0.5 处的错误率
- B. 误接受率（FAR）与误拒绝率（FRR）相等时的错误率
- C. 所有阈值下错误率的平均值
- D. 同一说话人分数的平均值减去不同说话人分数的平均值

**Q3.** 在基于余弦分数的验证系统中，把判决阈值调高，会导致：

- A. FAR 上升、FRR 下降
- B. FAR 下降、FRR 上升
- C. FAR 和 FRR 同时下降
- D. 二者都不变，只有 EER 改变

**Q4.** AAM-softmax（Additive Angular Margin）对正确类别 logit 的改动是：

- A. `s · cos(θ) − m`
- B. `s · cos(m · θ)`
- C. `s · cos(θ + m)`
- D. `s · cos(θ) · m`

**Q5.** 关于注册（enrollment），讲义推荐的做法是：

- A. 只用一段注册音频，越长越好，不在意是否有噪声
- B. 至少 3 段干净样本，分别算 embedding 后取平均
- C. 把所有注册音频拼接成一段再算一个 embedding，噪声段也一起拼
- D. 注册时用电话录音、验证时用高保真麦克风，以增加多样性

**Q6.** `code/main.py` 中的 `cosine(a, b)` 只计算了点积 `Σ aᵢbᵢ`，却能当余弦用，前提是：

- A. 两个向量维度相同
- B. 两个向量都已经做过 L2 归一化
- C. 两个向量的元素都是正数
- D. 两个向量来自同一说话人

**Q7.** 说话人分离（diarization）的典型流水线顺序是：

- A. 聚类 → VAD → 分段 → embedding → 平滑
- B. VAD → 分段 → embedding → 聚类 → 平滑边界
- C. embedding → VAD → 聚类 → 分段
- D. ASR → 聚类 → VAD

**Q8.** AS-norm（自适应分数归一化）的主要作用是：

- A. 把 embedding 的维度从 256 降到 192
- B. 用一组冒认者（imposter）cohort 的分数均值和标准差来归一化每个 trial 的分数，使分数在不同条件下可比，提升跨域表现
- C. 对音频做响度归一化
- D. 替代 VAD 去掉静音

---

## 三、动手 / 代码题

**Q9.** 阅读 `code/main.py` 中的 `eer`：

```python
def eer(same_scores, diff_scores):
    thresholds = sorted(set(same_scores + diff_scores))
    best_gap = float("inf")
    best_fa, best_fr, best_t = 1.0, 0.0, thresholds[0] if thresholds else 0.0
    for t in thresholds:
        fr = sum(1 for s in same_scores if s < t) / len(same_scores)
        fa = sum(1 for s in diff_scores if s >= t) / len(diff_scores)
        gap = abs(fa - fr)
        if gap < best_gap:
            best_gap = gap
            best_fa, best_fr, best_t = fa, fr, t
    return (best_fa + best_fr) / 2, best_t
```

不运行代码，手算 `eer([0.9, 0.8, 0.6], [0.7, 0.5, 0.4, 0.3])` 的返回值，列出每个候选阈值下的 FR 与 FA。

**Q10.** 讲义 Step 3 给出的 `eer` 是另一个版本：

```python
def eer(same_scores, diff_scores):
    thresholds = sorted(set(same_scores + diff_scores))
    best = (1.0, 1.0, 0.0)  # (fa, fr, threshold)
    for t in thresholds:
        fr = sum(1 for s in same_scores if s < t) / len(same_scores)
        fa = sum(1 for s in diff_scores if s >= t) / len(diff_scores)
        if abs(fa - fr) < abs(best[0] - best[1]):
            best = (fa, fr, t)
    return (best[0] + best[1]) / 2, best[2]
```

它对 Q9 的同一组输入返回什么？为什么？`code/main.py` 是怎么修好的？

**Q11.** 运行 `main.py` 得到：

```text
  same-speaker pairs: 50  mean cosine: 0.995
  diff-speaker pairs: 250  mean cosine: 0.558
  EER: 0.00%   at threshold: 0.989
  synthetic speakers are near-orthogonal, so this toy hits 0% EER.
```

(a) 5 个说话人、每人 5 条语音，为什么是 50 对同说话人、250 对不同说话人？推导一般公式。讲义练习 1 说"100-pair trial list"，对吗？
(b) 阈值 0.989 是怎么来的？在两类分数完全可分时，这是一个好的工作点吗？你会怎么选？
(c) "near-orthogonal"这句话与输出的数字相符吗？

**Q12.** 基于本文件的 `l2_normalize` 和 `cosine`，写两个函数：
(a) `make_enrollment(embs)`：把一个说话人的多条 embedding 合成一个注册向量；
(b) `identify(test_emb, enrolled, threshold)`：开集辨认，返回最相似的说话人名字，或在最高分低于阈值时返回 `"unknown"`。
并说明为什么 (a) 里平均之后还要再归一化一次。

---

## 四、面试高频题

**Q13.**（基础必考）说说一个说话人验证系统从注册到判决的完整流程。验证、辨认、开集辨认三者在系统设计和评估上有什么不同？

**Q14.**（原理深挖）为什么说话人 embedding 模型要用 AAM-softmax 这类带角度间隔的损失训练，而不是普通 softmax？`m` 和 `s` 分别起什么作用？它和 triplet loss 相比有什么优劣？

**Q15.**（工程实践）论文都报 EER，但上线时你会用 EER 对应的阈值吗？如何为一个实际业务确定阈值？跨域时分数漂移怎么办？

**Q16.**（场景设计）为一家银行的电话客服设计"声纹登录"：用户打进电话说一句话即可完成身份核验。请给出完整方案，并重点说明安全风险。

**Q17.**（追问型）会议录音的说话人分离怎么做？DER 由哪几部分组成？说话人数未知、多人同时说话时分别有什么难点？

---

## 五、参考答案与解析

### Q1 — 答案：B

"是不是 Alice"是一次 1:1 的比对，属于验证。A 是"在注册库里找出这是谁"（1:N）；C 是"谁在什么时候说话"；D 是"说了什么"。讲义开篇：ASR 问"说了什么"，说话人识别问"谁说的"。

### Q2 — 答案：B

讲义："Set your decision threshold so False Accept Rate = False Reject Rate. The crossover is EER." 它是一个与阈值无关的单一数字，便于比较模型；但上线时真正使用的阈值通常不是 EER 点（见 Q15）。

### Q3 — 答案：B

分数 ≥ 阈值才接受。阈值越高，冒认者越难被接受（FAR↓），但真实用户也更容易被拒（FRR↑）。两者此消彼长，EER 就是它们的交点。

### Q4 — 答案：C

讲义："`cos(θ + m)` for the correct class"。在角度上加间隔，要求正确类别的角度比其他类别小 `m` 弧度以上才能获得同样的 logit。A 是 CosFace / AM-softmax（在余弦上减间隔）；B 是 SphereFace（乘性角度间隔）；D 不是标准形式。

### Q5 — 答案：B

讲义 Pitfalls："One noisy enrollment poisons the anchor. Use ≥3 clean samples and average." 讲义 Step 4 的 SpeechBrain 例子也是对 3–5 段干净样本的 embedding 取平均。D 正好违反了"信道一致"的原则。

### Q6 — 答案：B

余弦 = `a·b / (|a||b|)`。如果 `|a| = |b| = 1`，余弦就等于点积。`embed_mfcc_stats` 在返回前调用了 `l2_normalize`，所以 `cosine` 可以省掉除法。讲义 Pitfalls 也强调："L2-normalize first; otherwise the magnitude dominates."——若误传未归一化的向量，例如 `cosine([3, 4], [3, 4])` 会返回 25 而不是 1。

### Q7 — 答案：B

讲义："VAD → segment → embed each segment → cluster (agglomerative or spectral) → smooth boundaries"。`pyannote.audio` 3.1 把分段、embedding、聚类封装在一次调用里。

### Q8 — 答案：B

S-norm / AS-norm 对每个分数，用测试端与注册端各自相对一组冒认者 cohort 的分数均值、标准差做 z 归一化（AS-norm 只取最相似的 top-K cohort）。不同信道、不同时长下分数的"刻度"不同，归一化后阈值更稳定。讲义："Essential for cross-domain eval."

### Q9 — 参考答案

候选阈值 = 所有分数去重排序：`[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]`。FR = 同说话人分数中 `< t` 的比例（分母 3），FA = 不同说话人分数中 `≥ t` 的比例（分母 4）：

| t | FR | FA | gap |
|---|----|----|-----|
| 0.3 | 0/3 = 0 | 4/4 = 1.00 | 1.000 |
| 0.4 | 0 | 3/4 = 0.75 | 0.750 |
| 0.5 | 0 | 2/4 = 0.50 | 0.500 |
| 0.6 | 0（0.6 不小于 0.6） | 1/4 = 0.25 | 0.250 |
| 0.7 | 1/3 ≈ 0.333 | 1/4 = 0.25 | **0.083** |
| 0.8 | 1/3 | 0 | 0.333 |
| 0.9 | 2/3 | 0 | 0.667 |

gap 最小在 `t = 0.7`，返回 `((0.25 + 0.333) / 2, 0.7) = (0.2917, 0.7)`（实测 `(0.29166666666666663, 0.7)`）。

要点：只在离散的观测分数上搜索阈值，FAR 与 FRR 往往不能恰好相等，所以取两者的平均作为 EER 近似。样本量大时这个近似足够；严格做法是在 ROC/DET 曲线上插值求交点。注意 `<` 与 `>=` 的搭配：分数恰好等于阈值时判为"接受"。

### Q10 — 参考答案

返回 `(1.0, 0.0)`——EER 100%、阈值 0.0，而且对**任何输入**都返回这个结果（对 `main.py` 的真实分数实测也是 `(1.0, 0.0)`）。

原因：初始值 `best = (1.0, 1.0, 0.0)` 的 gap 是 `|1.0 − 1.0| = 0`，而更新条件是 `abs(fa - fr) < 0`，绝对值不可能小于 0，所以 `best` 永远不会被更新。

`code/main.py` 的修复：用单独的 `best_gap = float("inf")` 记录"当前最小差距"，任何真实的 gap 都比无穷大小，第一轮必然更新。这是"求最小值时初始化为 +∞"的通用写法。这也提醒我们：讲义里的代码片段同样需要验证。

### Q11 — 参考答案

(a) 同说话人：每人 5 条语音两两配对 `C(5,2) = 10`，5 人共 50 对。不同说话人：说话人两两配对 `C(5,2) = 10` 组，每组 `5 × 5 = 25` 对，共 250 对。一般地，`S` 个说话人、每人 `n` 条：同说话人 `S·n(n−1)/2`，不同说话人 `C(S,2)·n²`。总数是 300 对，讲义练习 1 说的"100-pair trial list"与代码不符。另外，不同说话人的 trial 是同说话人的 5 倍——真实评测（如 VoxCeleb1-O）也常常不平衡，所以 EER 这类基于"比例"的指标比"准确率"更合适。

(b) 两类分数完全分开（实测同说话人最低 0.9888，不同说话人最高 0.7732），在 `(0.7732, 0.9888]` 区间内任何阈值都能得到 FAR = FRR = 0。代码只在观测分数上搜索，按升序第一个满足 gap = 0 的就是同说话人的最低分 0.989——这正好贴着同说话人分布的边缘，新来一条稍差的真实语音就会被拒。更合理的做法：取两类边界的中点（约 0.88），或者按业务要求的目标 FAR 在一个独立的开发集上调阈值（讲义："Always tune the threshold on a held-out dev set from the target domain"）。

(c) 不相符。"near-orthogonal"意味着不同说话人的余弦接近 0，而实测平均 0.558、最高 0.773（alice 与 eve 的谐波 200/400/600 与 260/520/780 很接近）。正确的说法是"两类分数完全可分"，而不是"正交"。这句话是硬编码打印的，并不依赖实际结果。

### Q12 — 参考答案

```python
def make_enrollment(embs):
    dim = len(embs[0])
    mean = [sum(e[i] for e in embs) / len(embs) for i in range(dim)]
    return l2_normalize(mean)


def identify(test_emb, enrolled, threshold):
    # enrolled: {name: 注册向量（已归一化）}
    best_name, best_score = "unknown", float("-inf")
    for name, ref in enrolled.items():
        score = cosine(test_emb, ref)
        if score > best_score:
            best_name, best_score = name, score
    if best_score < threshold:
        return "unknown", best_score
    return best_name, best_score
```

- 为什么要再归一化：多个单位向量的平均值，模长会**小于 1**（方向越分散越短）。本文件的 `cosine` 只是点积，若不重新归一化，注册向量越"分散"的说话人分数越低，阈值判决就会对不同说话人不公平。
- 开集的关键是**拒识**：最相似的那个人分数不够高时，应该判"未知"，而不是硬选一个——讲义的 open-set 定义："Test set can contain unenrolled speakers."
- 改进：用多条注册 embedding 分别打分再取均值/最大值，或在平均前先剔除离群样本（抵御带噪注册）。

### Q13 — 参考回答要点

- **注册**：采集 5–30 秒、至少 3 段干净语音（与使用场景同信道），分别提 embedding（ECAPA 192 维），L2 归一化后平均再归一化，存为声纹模板。
- **验证**：测试语音 → VAD 去静音 → embedding → 与模板算余弦（可加 PLDA / AS-norm）→ 与阈值比较。
- **三类任务的差异**：
  - 验证（1:1）：一次比对；指标 EER、目标 FAR 下的 FRR、DET 曲线；
  - 闭集辨认（1:N）：与 N 个模板比对取最大；指标 top-1 准确率；N 越大越难；
  - 开集辨认：在 1:N 的基础上还要能拒识未注册者，需要阈值；既看辨认准确率，也看误接受率。
- 加分点：讲义的"三个模型一个指标"——2026 年的主流是 ECAPA-TDNN、WavLM-SV、ReDimNet 一类，指标是 EER；并指出报告 EER 必须同时说明评测集、信道和语音时长分布（技能文件）。

### Q14 — 参考回答要点

- **为什么不用普通 softmax**：训练时说话人是固定的几千人，测试时是从没见过的新人（开集）。普通 softmax 只要求"分对"，学到的特征类内可能很分散、类间间隔很小，换到新说话人上做余弦比对时区分度不够。
- **AAM-softmax**：把特征和类别权重都归一化到单位球面上，logit 变成 `s·cos θ`；对正确类别用 `s·cos(θ + m)`，要求它的角度比其他类别再小 `m` 才能被判对——强迫类内更紧凑、类间角度间隔更大，正好契合推理时用余弦打分。
- **m 的作用**：间隔大小。越大越"苛刻"，太大训练难收敛；讲义典型值 0.2。**s 的作用**：归一化后余弦只在 `[-1, 1]`，softmax 的输出太平，`s`（如 30）放大 logit 让概率分布足够尖锐、梯度足够大。
- **与 triplet loss 对比**：triplet 直接优化"锚点-正样本-负样本"的距离关系，与验证任务目标一致，但需要精心挖掘难样本、收敛慢；AAM 是分类式训练，每个 batch 隐式地和所有类中心比较，训练稳定、实现简单，是 ECAPA 等模型的标准选择。
- 加分点：说出 CosFace（`cos θ − m`）、SphereFace（`cos(mθ)`）、ArcFace（`cos(θ + m)`，即 AAM）的区别，以及它们都源自人脸识别。

### Q15 — 参考回答要点

- **EER 只是比较模型的统一刻度**，不是业务工作点。银行登录关心"冒认者被放进来"的概率，可能要求 FAR ≤ 0.1%，此时 FRR 会远高于 EER；而客服场景的"个性化问候"更在意不打扰用户，可以接受较高 FAR。技能文件："Threshold. Target FAR (fraud risk) or EER"。
- **确定阈值**：在**目标领域**的开发集（同信道、同时长分布、足够多的冒认 trial）上画 DET 曲线，按目标 FAR 取阈值；上线后持续监控分数分布，定期重调。讲义："Always tune the threshold on a held-out dev set from the target domain."
- **跨域漂移**：训练在 VoxCeleb（网络视频），上线是电话语音，分数整体平移，固定阈值会失效（讲义：信道不匹配、固定阈值两条坑）。对策：AS-norm 等分数归一化、用目标域数据做后端（PLDA）自适应或微调、按信道分别设阈值。
- 加分点：提到 NIST 评测中的 minDCF（检测代价函数），它按业务设定的误接受/误拒绝代价和先验加权，比 EER 更接近真实决策。

### Q16 — 参考回答要点

1. **模型**：ECAPA-TDNN 或 WavLM-SV；电话信道是 8 kHz 窄带（第 01 节），而 VoxCeleb 是宽带网络视频——必须在电话信道数据上微调或至少做后端自适应。
2. **注册协议**：在电话信道上注册（信道匹配），≥3 段干净语音、总时长 ≥20 秒左右，注册时做质量门控（信噪比、时长、VAD 占比）。
3. **验证**：测试语音尽量 ≥3 秒（讲义：短于 3 秒 EER 急剧变差）；文本相关（固定口令）比文本无关更稳。
4. **打分与阈值**：余弦 + AS-norm；按目标 FAR（例如 0.1% 或更低）在电话域开发集上定阈值，并设置"灰区"——分数在灰区时转人工或追加知识问答。
5. **防欺骗（重点）**：录音回放、语音克隆（第 08 节）、TTS 合成都能骗过纯声纹系统。必须加反欺骗前端（AASIST、RawNet2）、随机口令的活体挑战（让攻击者无法预录），并检测回放。技能文件："Refuse any fraud-grade deployment without an anti-spoof front-end."
6. **其他**：声纹只作为多因素中的一因素；用户授权与数据合规；监控 FAR/FRR 与攻击事件，定期更新模板。

### Q17 — 参考回答要点

- **流程**：VAD 去掉非语音 → 切成短段（或用分割模型检测说话人变化点）→ 每段提说话人 embedding → 聚类（层次聚类 agglomerative 或谱聚类 spectral）→ 平滑边界、合并短段。`pyannote/speaker-diarization-3.1` 一次调用即可完成。
- **DER = 漏检（miss）+ 虚警（false alarm）+ 说话人混淆（confusion）**，均按时长占比计算。讲义：AMI 数据集上 2026 年 SOTA DER 约 15%。
- **说话人数未知**：聚类需要停止准则（距离阈值、特征值间隔等）；阈值太松会把一个人拆成多人，太紧会把多人合成一人。pyannote 支持 `num_speakers=None` 自动估计，也可给出上下界。
- **重叠语音**：传统"一段一个说话人"的假设失效，重叠段的 embedding 是两人的混合，聚类也只能分给一个人，导致漏检与混淆；需要能输出多标签的分割模型（pyannote 3.x 的分割模型支持重叠检测）。
- **短段**：段越短 embedding 越不可靠（与"短语音 EER 变差"同理），需要在时间分辨率和稳定性之间权衡。
- 加分点：说明 diarization 常与 ASR 结合（WhisperX 里的说话人标签），并把说话人标签对齐到词级时间戳上。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：MFCC 与 log-mel 是说话人 embedding 的输入。
- [阶段 06 · 03 音频分类](../../03-audio-classification/docs/zh.md)：同样是"变长音频 → 定长向量 + 余弦"，本节把统计池化换成了说话人 embedding。
- [阶段 05 · 22 Embedding 模型深入](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：embedding + 余弦检索的通用思想。
- [阶段 04 · 20 图像检索与度量学习](../../../04-computer-vision/20-image-retrieval-metric/docs/zh.md)：ArcFace / triplet 等度量学习损失的来源。

### 本节被哪些后续内容用到
- [阶段 06 · 08 语音克隆和语音转换](../../08-voice-cloning-conversion/docs/zh.md)：克隆系统用说话人 embedding 作为条件，也是声纹系统的主要威胁。
- [阶段 06 · 16 语音反欺骗和音频水印](../../16-anti-spoofing-audio-watermarking/docs/zh.md)：AASIST 等反欺骗前端。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：多用户助手中的说话人识别。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：EER、DER 等指标的系统讲解。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：ROC、阈值选择与误报/漏报权衡。

### 延伸关键词
`i-vector` · `x-vector` · `ECAPA-TDNN` · `ReDimNet` · `ArcFace / CosFace / SphereFace` · `PLDA` · `AS-norm` · `DET 曲线` · `minDCF` · `pyannote.audio` · `VoxCeleb` · `AASIST`
