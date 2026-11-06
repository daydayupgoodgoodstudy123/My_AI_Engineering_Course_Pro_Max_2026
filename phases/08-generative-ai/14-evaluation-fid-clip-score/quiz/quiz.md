# 测验 · Evaluation — FID、CLIP 分数、人类偏好（Evaluation — FID, CLIP Score, Human Preference）

> **阶段 08 · 生成式 AI · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 评估的两个维度 + 一个裁判 | 样本质量（FID）、条件贴合度（CLIP score）、人类偏好（胜率 / Elo）；没有任何一个有闭式"真值" |
| 2 | FID 的定义 | 用 Inception-v3 提取 2048 维特征，对真实 / 生成两组各拟合高斯，算 Fréchet 距离 `‖μ_r−μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_rΣ_g)^½)`，越低越好 |
| 3 | FID 的小样本偏差 | 有限 N 的估计有系统偏差：同分布在小 N 下 FID 也明显大于 0（代码实测 N=50 时 0.043、N=1000 时 0.002），讲义要求 N ≥ 10k，且只在相同 N 下比较 |
| 4 | FID 的特征依赖 | Inception 是 ImageNet 训练的，离 ImageNet 远的领域 FID 意义不大；分辨率不同（299×299 缩放）也不能比；可换 FD-DINO / CMMD |
| 5 | CLIP score | `cos(CLIP_image(x), CLIP_text(prompt))`，在大量样本上取平均；衡量 prompt 贴合度，越高越好 |
| 6 | CLIP score 的失效模式 | 组合推理弱（"蓝球上的红立方体"）、长 prompt 机械性得分更低、加 "4k, masterpiece" 等词可刷分 |
| 7 | CMMD | 用 CLIP 图像特征 + MMD（最大均值差异）比较真实与生成**图像分布**，无高斯假设、偏差更小 |
| 8 | 人类偏好与 Elo | 同 prompt 两模型盲评，胜负汇总成 Elo / Bradley-Terry 分；`E_a = 1/(1+10^((r_b−r_a)/400))`，`Δ = K·(实际 − 期望)`，零和 |
| 9 | 学习型偏好代理 | HPSv2、ImageReward、PickScore：在人类偏好数据上训练的小模型，用作自动裁判；PartiPrompts 是 1600 条、12 类的 prompt 集 |
| 10 | 生产评估协议 | 四根支柱：样本质量、贴合度、盲评偏好、失败案例审查；3 个种子报均值±标准差；held-out prompt；评估本身是离线推理负载（大 batch、缓存真实特征） |

### 核心技能（能动手做到）

- [ ] 能不用 NumPy 从零实现 FID：均值、无偏协方差、矩阵平方根（Denman–Beavers 迭代），并用对角协方差的解析解验证
- [ ] 能跑 `main.py` 复现"同分布、不同 N"的 FID 偏差，并估算均值项贡献的期望 `2dσ²/N`
- [ ] 能解释 CLIP-like 余弦分数的尺度不变性，指出演示中"中心 0.0"一行其实是随机噪声方向
- [ ] 能手算一次 Elo 更新，能由胜率 p 反推均衡分差 `400·log10(p/(1−p))`
- [ ] 能说明单次在线 Elo 的顺序依赖问题，并用"打乱顺序重复多次 / Bradley-Terry 拟合"给出更稳的估计
- [ ] 能为一个新文生图 checkpoint 写出四支柱评估计划：样本量、种子数、指标、失败探针、上线门槛

---

## 二、基础自测（选择题）

**Q1.** 下面哪一个是 FID 的正确公式（`μ`、`Σ` 为特征的均值与协方差）？

- A. `‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2·(Σ_r·Σ_g)^½)`
- B. `‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2·Σ_r·Σ_g)`
- C. `KL(N(μ_r, Σ_r) ‖ N(μ_g, Σ_g))`
- D. `1 − cos(μ_r, μ_g)`

**Q2.** 真实集和生成集来自**完全相同**的分布，只改变样本数 N 来估算 FID，会看到：

- A. 任何 N 下 FID 都精确为 0
- B. N 越小，FID 越偏高；N 增大时向 0 靠拢
- C. N 越小，FID 越偏低，容易误以为模型很好
- D. FID 与 N 无关，只与特征维度有关

**Q3.** 下列哪一项**不是** CLIP score 的典型失效模式？

- A. CLIP 组合推理弱，"蓝色球体上的红色立方体"这类 prompt 打分不可靠
- B. 长 prompt 的分数机械性地偏低
- C. 在 prompt 里加 "high quality, 4k, masterpiece" 能把分数刷高
- D. 必须至少 1 万个样本才能稳定估计协方差矩阵

**Q4.** 关于 CMMD，正确的是：

- A. 用 Inception 特征 + Fréchet 距离，只是换了个名字
- B. 用 CLIP 图像特征 + MMD 比较真实与生成图像的分布，无需高斯假设
- C. 计算生成图与其 prompt 的文本向量的余弦，用于衡量贴合度
- D. 是一种人类偏好标注协议

**Q5.** 两个模型当前 Elo 为 `r_A = 1200`、`r_B = 1000`，`K = 32`。下一局 A 获胜，更新后约为：

- A. 1216 / 984
- B. 1207.7 / 992.3
- C. 1224 / 976
- D. 1200 / 1000（强者赢了不加分）

**Q6.** 下列比较 FID 的做法中，**唯一合理**的是：

- A. 论文 A 在 256² 上报 FID，论文 B 在 1024² 上报 FID，直接比数值
- B. 自家模型用 N=1k 的 FID 对比别人 N=50k 的 FID
- C. 相同参考集、相同 N、相同分辨率与特征提取器，跑 3 个种子报均值±标准差
- D. 在人脸 / 医学图像上用 Inception 特征的 FID 作为绝对质量判断

**Q7.** 你的数据是 X 光片，离 ImageNet 很远。评估样本质量时最合适的调整是：

- A. 改用 Inception Score
- B. 换成 DINOv2 等自监督特征（FD-DINO）或领域专用特征提取器
- C. 继续用 Inception，只要把 N 增大到 10 万
- D. 只用 CLIP score

**Q8.** 跑 1 万张图的离线评估时，下列做法中**不推荐**的是：

- A. 用显存允许的最大 batch 做静态批处理，追求吞吐而非首 token 延迟
- B. 真实参考集的特征只提取一次，存成 `.npz` 复用
- C. 每次评估都重新提取真实集特征，"保证新鲜"
- D. 每个 PR 跑 500 样本的小规模 FID + CLIP，完整 10k 评估放到每晚

---

## 三、动手 / 代码题

**Q9.** `main.py` 的第一段输出是：

```text
  N=   50: FID (identical distributions) = 0.0431  (lower = more similar)
  N=  200: FID (identical distributions) = 0.0288  (lower = more similar)
  N= 1000: FID (identical distributions) = 0.0022  (lower = more similar)
```

特征由 `make_features(0.0, n, d, rng)` 生成：`d = 4`，每维独立、标准差 `scale = 0.4`。
(a) 估算 FID 里均值项 `‖μ_r − μ_g‖²` 在 N=50 时的期望值；(b) 为什么估计出来的 FID 在两组分布相同时也是正的、而且随 N 增大而减小？

**Q10.** `fid` 中的矩阵平方根函数如下：

```python
def jacobi_sqrt(M, iters=30):
    """Matrix square root by Denman-Beavers iteration (stable for PSD M)."""
    n = len(M)
    Y = [row[:] for row in M]
    Z = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(iters):
        Y_inv = inverse(Y)
        Z_inv = inverse(Z)
        Y = [[(Y[i][j] + Z_inv[i][j]) / 2 for j in range(n)] for i in range(n)]
        Z = [[(Z[i][j] + Y_inv[i][j]) / 2 for j in range(n)] for i in range(n)]
    return Y
```

(a) 函数名和 docstring 是否一致？它实际用的是什么算法？(b) 传进来的 `prod = cov_r @ cov_g` 一般**不是对称矩阵**，为什么取它的平方根再求迹仍然正确？(c) 把 `fid` 拆出一个 `fid_from_stats(mu_r, cov_r, mu_g, cov_g)`，并写一个用解析解验证它的小测试。

**Q11.** CLIP-like 一段的输出是：

```text
  image center +1.0: CLIP-like score = +0.659
  image center +0.5: CLIP-like score = +0.600
  image center +0.0: CLIP-like score = +0.578
  image center -0.5: CLIP-like score = -0.666
```

其中 `prompt = [1.0, 0.5, -0.2, 0.3]`，`image = [image_center + rng.gauss(0, 0.1) for _ in range(d)]`。有人据此得出"图像中心越靠近 prompt，分数越高，指标单调可靠"。这个解读对吗？请算出 `+1.0` 和 `+0.5` 两行在无噪声时的理论值，并解释 `+0.0` 那一行。

**Q12.** Elo 一段打印 `after 200 pairs (A wins 70%): r_A = 1014, r_B = 986`。我回放了同一随机序列：这 200 局里 A 实际赢了 134 局（67%），而最后 10 局是 `baaaabbaab`。
(a) 若真实胜率为 p，Elo 的均衡分差是多少？p = 0.67 时 r_A 大约应在多少？(b) 为什么最终只有 1014？(c) 写一段代码，给出比"单次顺序 Elo"更稳的估计。

---

## 四、面试高频题

**Q13.**（基础必考）请讲清楚 FID：怎么算、直觉是什么、有哪些已知缺陷、报告时要注意什么？

**Q14.**（原理深挖）为什么 FID 在小样本下有偏？偏向哪个方向？工程上和学术上分别怎么应对？

**Q15.**（工程实践）你负责给一个新的文生图 checkpoint 写上线评估报告，基线是上一版模型。请给出完整方案，包括样本量、指标、种子、失败分析和上线门槛。

**Q16.**（追问型）新模型的 CLIP score 比旧模型高了 0.02，FID 几乎不变，产品经理说"贴合度提升了，可以发"。你会怎么回应？

**Q17.**（场景设计）设计一个文生图模型的人类偏好竞技场（arena）。你会如何避免偏差、怎样把胜负聚合成可靠的排名？能否用 LLM / VLM 当裁判？

---

## 五、参考答案与解析

### Q1 — 答案：A

FID 是两个多元高斯之间的 Fréchet（2-Wasserstein）距离：均值差的平方 + 协方差项 `Tr(Σ_r + Σ_g − 2(Σ_rΣ_g)^½)`。B 漏了平方根，量纲都不对（协方差乘积是"方差²"）；C 是 KL 散度，不对称且不是 FID；D 是余弦距离，和 CLIP score 的思路混淆了。

### Q2 — 答案：B

代码第一段直接演示了这一点：同分布下 N=50 时 0.0431、N=200 时 0.0288、N=1000 时 0.0022，都大于 0 且随 N 增大下降。原因是有限样本的均值、协方差估计带噪声，噪声在"距离"里只会累加成正值（见 Q9）。⚠️ 讲义 "Failure modes" 里写的是小 N 会 "gives falsely low FID"，与代码输出（"biased up at small N"）相反；以代码和 Q9 的推导为准——小 N 下 FID 系统性偏高，而且偏多少还与模型有关，所以不同 N 的数值不可比。

### Q3 — 答案：D

D 是 FID 的问题（要估计 2048 维协方差），与 CLIP score 无关——CLIP score 是逐样本余弦再平均，不涉及协方差估计。A、B、C 都是讲义列出的 CLIP score 失效模式：组合推理弱、短 prompt 偏好、prompt 刷分。

### Q4 — 答案：B

CMMD（Jayasumana 等，2024）= CLIP 图像特征 + MMD，比较的是**真实图像集合 vs 生成图像集合**的分布，没有高斯假设，偏差更小，对细微质量差异更敏感。A 描述的是 FID；C 描述的是 CLIP score。⚠️ 讲义 "Use together" 第 2 条和 skill 文件把 CMMD 放在"对 prompt 的贴合度"一栏，这是混淆——CMMD 不使用文本，衡量的是样本质量 / 分布距离；讲义 "Use It" 表格把它放在 Sample quality 一行才是对的。

### Q5 — 答案：B

`E_A = 1/(1 + 10^((1000−1200)/400)) = 1/(1 + 10^(−0.5)) ≈ 1/1.3162 ≈ 0.760`。A 赢，实际 = 1，`Δ = 32 × (1 − 0.760) ≈ 7.7`。更新为 `1207.7 / 992.3`。A 是"等分时赢一局"的 +16；D 错在强者赢了也会加分，只是加得少（期望本来就高）。Elo 是零和的：A 加多少 B 就减多少。

### Q6 — 答案：C

讲义的 Pitfalls：不同分辨率下 Inception 的 299×299 缩放会改变特征分布（A 错）；N 不同时偏差不同（B 错）；远离 ImageNet 的领域 Inception 特征没有意义（D 错）；必须报多种子的均值和标准差。C 是唯一满足"同口径"的做法。

### Q7 — 答案：B

讲义：Inception-v3 在 ImageNet 上训练，领域差得远时 FID 无意义，应换领域专用的特征提取器；术语表里的 FD-DINO（DINOv2 特征的 Fréchet 距离）就是为 ImageNet 之外的领域准备的。A 的 IS 同样依赖 ImageNet 分类器，且已"退役"；C 增大 N 只降方差和偏差，不能修正"特征本身不懂 X 光"；D 衡量的是贴合度而非样本质量。

### Q8 — 答案：C

讲义的 Production note：评估是离线推理负载，要大 batch 追吞吐（A 对）；真实参考集特征算一次缓存起来（B 对，C 错）；CI 中每个 PR 跑 500 样本子集，完整 10k + HPSv2 + Elo 放到夜间（D 对）。真实集不变，特征也不会变，重复提取纯属浪费。

### Q9 — 参考答案

(a) 每维的样本均值方差为 `σ²/N`，两组独立，所以 `μ_r − μ_g` 每维的方差为 `2σ²/N`，期望

```
E‖μ_r − μ_g‖² = d · 2σ² / N = 4 × 2 × 0.16 / 50 ≈ 0.0256
```

N=200 时约 0.0064，N=1000 时约 0.0013。剩下的部分来自协方差项的估计误差（加上单次实验的随机波动，N=200 那行比纯 1/N 预期略大）。

(b) 两组分布相同时真 FID 为 0，而 FID 是一个"距离"——均值项是平方和，永远 ≥ 0；协方差项 `Tr(Σ_r + Σ_g − 2(Σ_rΣ_g)^½)` 在 `Σ_r = Σ_g` 时取最小值 0，估计出的两个协方差带独立噪声后一般不再相等，也只会 ≥ 0。所以估计噪声**只能把 FID 往上推**，期望值大约按 `1/N` 衰减。这就是代码打印的 "biased up at small N"。真实场景中特征是 2048 维，偏差项与维度成正比，所以需要上万样本。

### Q10 — 参考答案

(a) 不一致。docstring 写的是 Denman–Beavers 迭代，代码也确实是 DB：`Y₀ = M, Z₀ = I`，`Y_{k+1} = (Y_k + Z_k⁻¹)/2`，`Z_{k+1} = (Z_k + Y_k⁻¹)/2`，`Y → M^½`，`Z → M^(−½)`。函数名里的 "jacobi" 容易让人误以为是 Jacobi 特征值法，属于命名不当。

(b) `Σ_rΣ_g` 虽然不对称，但它与对称半正定矩阵 `Σ_r^½ Σ_g Σ_r^½` 相似（`Σ_rΣ_g = Σ_r^½ (Σ_r^½ Σ_g Σ_r^½) Σ_r^(−½)`），特征值都是非负实数；它的主平方根与 `(Σ_r^½ Σ_g Σ_r^½)^½` 相似，相似矩阵的迹相等。DB 迭代只要求矩阵没有负实轴上的特征值，所以能收敛。生产库（如 `scipy.linalg.sqrtm`）也是直接对乘积开方，数值误差导致的微小虚部再取实部丢掉。

(c) 参考代码（已在本地运行验证，三行输出依次为 `[[2.0, 0.0], [0.0, 3.0]]`、`4.0`、`0.0`）：

```python
def fid_from_stats(mu_r, cov_r, mu_g, cov_g):
    mean_sq = sum((a - b) ** 2 for a, b in zip(mu_r, mu_g))
    sqrt_prod = jacobi_sqrt(matmul(cov_r, cov_g))
    return mean_sq + trace(cov_r) + trace(cov_g) - 2 * trace(sqrt_prod)


# 测试 1：对角矩阵的平方根就是逐元素开方
print(jacobi_sqrt([[4.0, 0.0], [0.0, 9.0]]))          # [[2, 0], [0, 3]]

# 测试 2：Σ_r = aI, Σ_g = bI 时 FID = ‖Δμ‖² + d(√a − √b)²
#         Δμ = [1, 1], a = 1, b = 4, d = 2 → 2 + 2·(1−2)² = 4
print(fid_from_stats([0, 0], [[1, 0], [0, 1]], [1, 1], [[4, 0], [0, 4]]))   # 4.0

# 测试 3：完全相同的统计量 → 0
A = [[2.0, 0.5], [0.5, 1.0]]
print(fid_from_stats([0, 0], A, [0, 0], A))            # 0.0
```

拆出 `fid_from_stats` 还有工程价值：真实集的 `(μ, Σ)` 可以只算一次缓存（讲义 Production note 的 `.npz`），之后每次评估只算生成集的统计量。

### Q11 — 参考答案

解读不对。

- 无噪声时 `image = [c, c, c, c]`，与 prompt 的余弦与 c 的大小无关，只与符号有关：`cos = (1 + 0.5 − 0.2 + 0.3) / (2 × √1.38) = 1.6 / 2.349 ≈ 0.681`（c>0）或 −0.681（c<0）。所以 `+1.0` 和 `+0.5` 理论上**完全相同**，都是 0.681；观测到的 0.659 与 0.600 的差别全部来自噪声——c 越小，`N(0, 0.1)` 噪声相对越大，方向偏得越多。
- `+0.0` 一行：图像向量就是纯噪声，方向随机。4 维随机方向与固定向量的余弦均值为 0、标准差约 `1/√4 = 0.5`，这次碰巧抽到 0.578，换个种子可能是负的。
- 结论：余弦是**尺度不变**的，只比较方向；向量范数很小时方向几乎完全由噪声决定。演示中的"单调下降"一半是巧合。这也提示真实 CLIP score 的局限：它只看嵌入方向是否对齐，不衡量"有多像"，需要配合分布指标和人工评估。

### Q12 — 参考答案

(a) 均衡时期望胜率等于真实胜率：`1/(1 + 10^(−Δ/400)) = p` ⇒ `Δ = 400 · log10(p/(1−p))`。p = 0.70 时 Δ ≈ 147；p = 0.67 时 Δ ≈ 123。由于零和、总分恒为 2000，r_A ≈ 1000 + Δ/2 ≈ 1062。

(b) 在线 Elo 是"带遗忘的随机游走"：K=32 时每局都会把分数推 ±(10~20) 分，最终值强烈依赖**最近几局**的结果。最后 10 局 A 只赢了 5 局，把分数拉回到 1014。回放整条轨迹：r_A 最高到过 1130，后 100 局平均约 1055。单次快照既有噪声又依赖顺序。

(c) 两种更稳的做法：

```python
import math
import random

def elo_order_averaged(outcomes, n_perm=200, seed=0, k=32):
    rng = random.Random(seed)
    outcomes = list(outcomes)
    finals = []
    for _ in range(n_perm):
        rng.shuffle(outcomes)                 # 打乱比赛顺序，消除顺序依赖
        r_a, r_b = 1000, 1000
        for w in outcomes:
            r_a, r_b = elo_update(r_a, r_b, w, k)
        finals.append(r_a)
    finals.sort()
    return sum(finals) / len(finals), finals[len(finals) // 20], finals[-len(finals) // 20 - 1]


def bt_two_players(wins_a, n):
    p = wins_a / n                            # 两个选手时 Bradley-Terry 的最大似然解
    delta = 400 * math.log10(p / (1 - p))     # 换算到 Elo 尺度
    return 1000 + delta / 2, 1000 - delta / 2
```

我用 134 胜 / 66 负、200 种随机顺序跑过 `elo_order_averaged`：均值约 1063，5%–95% 区间约 1006–1120，与 BT 解 1062 一致，也说明单次的 1014 只是区间下沿的一个样本。多模型时用 Bradley-Terry 的批量最大似然拟合（或逻辑回归），再用 bootstrap 给置信区间——讲义术语表也说 Elo 本质上是 Bradley-Terry 的聚合。

### Q13 — 参考回答要点

- **怎么算**：真实集与生成集各取 N 张，过 Inception-v3 取 2048 维 pool 特征，各拟合一个高斯，算 `‖μ_r−μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_rΣ_g)^½)`。
- **直觉**：在"Inception 眼中"比较两团特征云的位置（均值）和形状（协方差）。均值项衡量"整体像不像"，协方差项同时反映质量和多样性——模式塌缩会让 Σ_g 变小，FID 上升。
- **缺陷**：①小 N 有偏（偏高、且偏差依模型而异）；②依赖 Inception / ImageNet 先验，跨领域无意义；③高斯假设过强；④分辨率与预处理（缩放、压缩格式）敏感；⑤可以"对 Inception 过拟合"刷分而视觉质量不变（讲义：用 CMMD 对抗）；⑥只看质量，不看 prompt 贴合度。
- **报告规范**：N ≥ 10k（讲义），同参考集、同 N、同分辨率、同实现；3 个种子报均值±标准差；给出绝对基线值而不是只说"提升了 x%"（skill 文件的要求）。
- **加分点**：知道 FD-DINO、CMMD、KID 等替代；知道不同 FID 实现（缩放插值方式）会造成数值差异，跨论文比较要用同一份代码。

### Q14 — 参考回答要点

- **为什么有偏**：FID 是对真实统计量的非线性函数（平方、矩阵开方）。把样本估计值代进非线性函数，期望不等于函数作用在真值上（Jensen 式偏差）。均值项 `E‖μ̂_r − μ̂_g‖² = ‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g)/N`，多出来的就是偏差；协方差项同理。
- **方向**：同分布时真值为 0，估计值只能 ≥ 0，所以小 N **偏高**（Q9 的代码输出）。更麻烦的是偏差大小与生成分布本身有关，所以两个模型在小 N 下的排序都可能翻转。
- **工程应对**：①固定且足够大的 N（讲义 ≥ 10k；skill 文件拒绝 N < 5000 的 FID）；②比较时 N 必须相同；③多种子报方差；④CI 中的小样本 FID 只用来做同口径回归检测，不对外宣称。
- **学术应对**：用无偏的核方法估计量（KID 基于 MMD 的无偏估计）；CMMD（CLIP 特征 + MMD）；也有工作在多个 N 上计算 FID 再外推到 N→∞。
- **常见误区**：以为"N 小 → FID 偏低 → 被刷分"；方向其实相反，但"不同 N 不可比"的结论是一样的。

### Q15 — 参考回答要点

按讲义的四支柱 + skill 文件的门槛来组织：

| 支柱 | 最低要求 | 推荐 |
|------|---------|------|
| 样本质量 | 10k 样本、held-out 真实集上的 FID，匹配分辨率 | + 5k 的 CMMD + 分类别 FID；领域远离 ImageNet 时用 FD-DINO |
| 贴合度 | 30k 样本的 CLIP score | + HPSv2 + ImageReward（+ PickScore）+ VQA 式问答检查 |
| 偏好 | 200 对盲评 vs 基线 | 2000 对人工 + LLM 裁判 + PartiPrompts 覆盖 |
| 失败分析 | 50 张人工标注 | 500 张 + 自动安全分类器；重点看手部结构、文字渲染、物体数量 |

- **口径**：3 个种子、均值±标准差；held-out prompt（训练中可能见过的 prompt 不能用）；按类别（人物、动物、文字、组合、风格）拆分，**整体变好但某类退化也要标红**。
- **安全**：NSFW 分类器、深伪检测、水印检查、对 top-K 生成做版权相似度扫描（skill 文件）。
- **门槛示例**（skill 文件）：FID 不劣于基线 5% **或** 人工胜率 > 55% **或** 有文档化的定性优势；任何"单指标宣称"都不接受。
- **成本**：评估本身是推理负载——讲义估算 50 步 SDXL 在单张 L4 上生成 1 万张约 11 小时；所以要大 batch 离线跑、缓存真实特征，PR 级跑 500 样本子集、夜间跑全量。
- **加分点**：讲义原话 "Any single metric is a lie. Three corroborating metrics + qualitative review are a claim."

### Q16 — 参考回答要点

- **先问口径**：样本数、种子数、标准差多少？0.02 是否超出种子间波动？prompt 集是否与训练集重叠？两次评估的 prompt 长度分布是否一样（长 prompt 天然得分低）？
- **排查刷分**：是否改了 prompt 模板（例如自动追加 "4k, masterpiece"）或 negative prompt？讲义提醒有的管线靠过度拟合 prompt 抬高 CLIP，要检查画面是否过饱和。
- **CLIP 自身盲区**：组合、计数、空间关系上 CLIP 不可靠，分数涨了不代表复杂 prompt 遵循得更好——补充 VQA 式问答检查、按类别拆分。
- **交叉验证**：看 HPSv2 / ImageReward / PickScore 是否同向；做至少 200 对盲评；抽 50–500 张人工看失败模式。
- **结论模板**："CLIP score 是一个信号，不是结论。三个互相印证的指标 + 定性审查才构成一个可以上线的主张。"
- **常见误区**：只报相对提升不报绝对值和方差；把 CMMD 当贴合度指标（它不看文本）。

### Q17 — 参考回答要点

- **盲评流程**：同一 prompt、两模型各出图，随机左右位置、隐藏模型名；允许"平局 / 都不好"；每对收集多名标注者。
- **prompt 分布**：使用公开且有分类的集合（如 PartiPrompts 1600 条 12 类）+ 业务真实 prompt；记录并公开分布，防止挑选对某一家有利的 prompt；确保 held-out（讲义：两模型都见过的基准 prompt 会让 Elo 失去意义）。
- **标注者**：众包（Prolific、MTurk）偏年轻、偏技术人群，要混入招募的艺术 / 设计专家（讲义），并分别报告；做一致性检验（Cohen's κ / 黄金题）。
- **聚合**：在线 Elo 对顺序敏感（Q12），排行榜应用 Bradley-Terry 批量拟合，bootstrap 出置信区间；只有区间不重叠才宣称"更好"；新模型上线前保证足够的对局数。
- **LLM / VLM 裁判**：可以扩大规模、降低成本，也有 HPSv2、ImageReward、PickScore 这类学习型代理；但讲义提醒强裁判模型会被"好看但错误"的结果骗（reward hacking），必须和人工评估三角验证；skill 文件拒绝只有 LLM 裁判结果的报告。还要处理位置偏差（交换左右再评一次）。
- **加分点**：能区分"偏好"与"正确性"（文字渲染、计数等可以自动判定的维度单独用规则 / VQA 检查）。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 01 生成模型——分类法和历史](../../01-generative-models-taxonomy-history/docs/zh.md)：知道要评估的是哪类模型、它们各自的失败方式。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：指标、置信区间、数据泄漏这些通用评估概念。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)、[阶段 01 · 15 机器学习中的统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：多元高斯、协方差、估计量的偏差与方差。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：CLIP score 背后的图文嵌入空间。

### 本节被哪些后续内容用到
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)：判断"4 步是否追上 20 步"要用分布级指标。
- [阶段 08 · 19 视觉自回归建模（VAR）](../../19-visual-autoregressive-var/docs/zh.md)：VAR 与扩散模型的对比主要以 ImageNet FID 为依据。
- [阶段 06 · 17 音频评估指标](../../../06-speech-and-audio/17-audio-evaluation-metrics/docs/zh.md)：音频领域的对应物（FAD、CLAP、MOS）。
- [阶段 05 · 27 LLM 评估框架](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)、[阶段 10 · 10 评估](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：LLM-as-judge、竞技场与 Elo 在文本模型上的同类问题。
- [阶段 18 · 02 奖励黑客与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：指标被"优化"后失效的一般规律。
- [阶段 19 · 74 排行榜聚合](../../../19-capstone-projects/74-leaderboard-aggregation/docs/zh.md)：把多指标、多对局汇总成排行榜的工程实现。

### 延伸关键词
`Inception Score (IS)` · `KID` · `CMMD` · `FD-DINO / DINOv2` · `MMD 与核方法` · `2-Wasserstein 距离` · `Bradley-Terry 模型` · `bootstrap 置信区间` · `HPSv2 / ImageReward / PickScore` · `PartiPrompts / MJHQ-30k` · `VQA 式评估（如 TIFA）` · `LLM-as-judge 位置偏差`
