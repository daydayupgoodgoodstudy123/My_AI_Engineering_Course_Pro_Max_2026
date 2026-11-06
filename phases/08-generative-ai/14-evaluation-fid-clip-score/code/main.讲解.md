# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 14 节 Evaluation — FID、CLIP 分数、人类偏好 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / SciPy / CLIP 模型

---

## 1. 这份代码在考察什么

真实的 FID 要跑 Inception-v3、CLIP score 要加载 CLIP、Elo 要有人类标注。这份代码把这三者都换成**4 维合成特征向量**，只保留数学本身，让你看清：

1. **FID 的完整计算链**：均值 → 无偏协方差 → 协方差乘积的矩阵平方根（Denman–Beavers 迭代）→ Fréchet 距离。全部用嵌套列表手写，包括高斯-约当求逆。
2. **FID 的小样本偏差**：两组特征来自同一分布，FID 却不为 0，且 N 越小越大。
3. **FID 对分布偏移的敏感度**：均值平移 s 时 FID 大约按 `d·s²` 增长。
4. **CLIP-like 分数**：余弦相似度——只看方向、不看长度。
5. **Elo 聚合**：从一串 A/B 胜负结果在线更新评分，体会 K 因子、期望胜率和零和更新。

> 一句话：**FID 是距离，CLIP score 是贴合度，Elo 是偏好的汇总——三个数各有各的偏差，所以生产评估要三者并用再加人工审查。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `mean_vec(vectors)` | 函数 | 逐维求均值 | `μ` |
| `covariance(vectors, mu)` | 函数 | 无偏样本协方差（除以 n−1） | `Σ` |
| `trace(M)` | 函数 | 对角线求和 | `Tr(·)` |
| `matmul(A, B)` | 函数 | 三重循环矩阵乘 | `Σ_r·Σ_g` |
| `inverse(M)` | 函数 | 带部分主元的高斯-约当求逆 | 矩阵求逆 |
| `jacobi_sqrt(M, iters)` | 函数 | Denman–Beavers 迭代求矩阵平方根 | `(Σ_rΣ_g)^½` |
| `fid(real, gen)` | 函数 | 组合以上各步算出 FID | Fréchet 距离 |
| `clip_like(a, b)` | 函数 | 余弦相似度 | CLIP score |
| `elo_update(r_a, r_b, winner, k)` | 函数 | 一局比赛后的 Elo 更新 | 偏好聚合 |
| `make_features(center, n, d, rng, scale)` | 函数 | 生成 `N(center, scale²·I)` 的合成"特征" | 代替 Inception / CLIP 特征 |
| `main()` | 入口 | 四个实验：FID 偏差、FID 区分度、CLIP-like、Elo | — |

调用关系：`fid → mean_vec / covariance / matmul / jacobi_sqrt（内部反复调用 inverse）/ trace`；`main` 用 `make_features` 造数据后分别调用 `fid`、`clip_like`、`elo_update`。

---

## 3. 逐段精讲

### 3.1 均值与无偏协方差

```python
def mean_vec(vectors):
    d = len(vectors[0])
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(d)]


def covariance(vectors, mu):
    d = len(mu)
    n = len(vectors)
    cov = [[0.0] * d for _ in range(d)]
    for v in vectors:
        for i in range(d):
            for j in range(d):
                cov[i][j] += (v[i] - mu[i]) * (v[j] - mu[j])
    return [[cov[i][j] / max(n - 1, 1) for j in range(d)] for i in range(d)]
```

- 数据布局：`vectors` 是"样本的列表"，每个样本是长度 `d` 的列表，相当于形状 `(N, d)` 的矩阵。
- 协方差 `Σ[i][j] = Σ_v (v_i − μ_i)(v_j − μ_j) / (n − 1)`。除以 `n−1` 是**贝塞尔校正**，让协方差估计无偏；`max(n - 1, 1)` 防止只有 1 个样本时除以 0。
- 注意：即使 `Σ̂` 本身无偏，FID 仍然有偏——因为 FID 对 `μ̂`、`Σ̂` 做了平方和开方等非线性运算（见 3.4 与第 6 节）。
- `[[0.0] * d for _ in range(d)]` 是创建二维列表的正确写法。⚠️ 如果写成 `[[0.0] * d] * d`，`d` 行会指向**同一个**列表对象，改一行等于改所有行。
- 复杂度 O(N·d²)。真实 FID 里 d = 2048、N = 10k，这个三重循环在纯 Python 下会慢到不可用——生产用 NumPy 的 `np.cov`。

### 3.2 `inverse`：带部分主元的高斯-约当消元

```python
def inverse(M):
    n = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(A[r][col]) > abs(A[pivot][col]):
                pivot = r
        A[col], A[pivot] = A[pivot], A[col]
        piv = A[col][col]
        if abs(piv) < 1e-12:
            piv = 1e-12
        for j in range(2 * n):
            A[col][j] /= piv
        for r in range(n):
            if r == col: continue
            factor = A[r][col]
            for j in range(2 * n):
                A[r][j] -= factor * A[col][j]
    return [row[n:] for row in A]
```

- 经典做法：把 `[M | I]` 拼成增广矩阵，行变换把左半变成 `I`，右半就是 `M⁻¹`。
- **部分主元**：每列选绝对值最大的行做主元，减少舍入误差——比"找到第一个非零就用"更稳。
- `if abs(piv) < 1e-12: piv = 1e-12`：遇到（近似）奇异矩阵时不报错，而是除以一个极小数。⚠️ 这是"静默兜底"：结果会是巨大的数而不是异常。真实场景里协方差奇异很常见（N < d 时样本协方差必然秩亏），生产代码通常给对角线加一个小 ε（如 `Σ + 1e-6·I`）再计算，并在结果出现异常值时告警。
- `if r == col: continue` 写在同一行，合法但不符合 PEP 8 的风格建议。

### 3.3 `jacobi_sqrt`：其实是 Denman–Beavers 迭代

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

- 算法：`Y₀ = M`、`Z₀ = I`，迭代 `Y ← (Y + Z⁻¹)/2`、`Z ← (Z + Y⁻¹)/2`，则 `Y → M^½`、`Z → M^(−½)`。它本质上是对 `X² = M` 的牛顿法的一个数值更稳定的变体，二次收敛，30 次迭代对 4×4 矩阵绰绰有余。
- 注意两行更新都用的是**上一轮**的 `Y_inv`、`Z_inv`（先算好再更新），这一点很关键：如果先更新了 `Y` 再用新 `Y` 算 `Z`，就不是 DB 迭代了。
- ⚠️ 命名不当：函数叫 `jacobi_sqrt`，但与 Jacobi 特征值算法毫无关系，docstring 才是对的。读代码时以 docstring 为准。
- **为什么输入不对称也行**：`fid` 传进来的是 `cov_r @ cov_g`，两个对称正定矩阵的乘积一般**不对称**，docstring 里的 "PSD" 并不严格成立。但这个乘积与 `Σ_r^½ Σ_g Σ_r^½` 相似，特征值都是非负实数，DB 迭代照样收敛，而且相似矩阵的迹相同，所以 `trace(sqrt(Σ_rΣ_g))` 的值是对的。生产库 `scipy.linalg.sqrtm` 也是直接对乘积开方，再丢掉数值误差带来的微小虚部。
- 另一种常见实现：对称化后做特征分解 `Σ_r^½ Σ_g Σ_r^½ = QΛQᵀ`，平方根的迹就是 `Σ √λᵢ`。

### 3.4 `fid`：把各部分拼起来

```python
def fid(real_features, gen_features):
    mu_r = mean_vec(real_features)
    mu_g = mean_vec(gen_features)
    cov_r = covariance(real_features, mu_r)
    cov_g = covariance(gen_features, mu_g)
    mean_sq = sum((a - b) ** 2 for a, b in zip(mu_r, mu_g))
    prod = matmul(cov_r, cov_g)
    sqrt_prod = jacobi_sqrt(prod)
    return mean_sq + trace(cov_r) + trace(cov_g) - 2 * trace(sqrt_prod)
```

与讲义公式逐项对应：

| 代码 | 公式 | 含义 |
|------|------|------|
| `mean_sq` | `‖μ_r − μ_g‖²` | 两团特征云的"中心"差多远 |
| `trace(cov_r) + trace(cov_g)` | `Tr(Σ_r + Σ_g)` | 两团云各自的"总方差" |
| `- 2 * trace(sqrt_prod)` | `−2·Tr((Σ_rΣ_g)^½)` | 形状越相似，扣掉得越多；`Σ_r = Σ_g` 时协方差项恰为 0 |

- 直觉：对一维情形，协方差项退化为 `(σ_r − σ_g)²`，整个 FID 就是 `(μ_r − μ_g)² + (σ_r − σ_g)²`——均值差加标准差差，都取平方。
- ⚠️ 与讲义 Step 1 的伪代码略有不同：讲义写的是 `trace(cov_r) + trace(cov_g) - 2 * sqrt_cov_product(cov_r, cov_g)`，而真实代码是先 `jacobi_sqrt` 再 `trace`。以代码为准。
- 工程提示：真实集的 `(mu_r, cov_r)` 可以只算一次缓存（讲义 Production note 的 `.npz`），把函数拆成 `fid_from_stats(mu_r, cov_r, mu_g, cov_g)` 会更好复用（测验 Q10 有完整实现）。

### 3.5 `clip_like`：余弦相似度

```python
def clip_like(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / max(na * nb, 1e-8)
```

- `cos(a, b) = a·b / (‖a‖‖b‖)`，取值 [−1, 1]。真实 CLIP score 就是图像嵌入与文本嵌入的余弦（常见实现还会乘一个系数并截断负值，讲义里用的是原始余弦）。
- `max(na * nb, 1e-8)`：任一向量为零向量时避免除以 0，此时返回 0。
- **尺度不变**：`a` 乘以任何正数，分数不变。这意味着它只能告诉你"方向对不对"，不能告诉你"强度够不够"——第 6 节的输出会让你看到这一点的后果。
- 与讲义 Step 2 对比：讲义伪代码里的 `dot_self` 在真实代码中并不存在，代码直接用两个 `math.sqrt` 实现。

### 3.6 `elo_update`：一局比赛的评分更新

```python
def elo_update(r_a, r_b, winner, k=32):
    expected_a = 1 / (1 + 10 ** ((r_b - r_a) / 400))
    actual_a = 1.0 if winner == "a" else 0.0
    delta = k * (actual_a - expected_a)
    return r_a + delta, r_b - delta
```

- `expected_a` 是 A 的期望胜率：分差 400 分对应 10:1 的胜率比。两人同分时期望 0.5。
- `delta = K·(实际 − 期望)`：赢了"本该赢的比赛"加分少，爆冷加分多。
- A 加 `delta`、B 减 `delta`，所以**总分守恒**（零和）。`main` 里两者初始都是 1000，任何时刻 `r_a + r_b = 2000`。
- `K = 32` 是国际象棋里常见的"新手级"取值，更新快但波动大。⚠️ 简化：不支持平局（`actual = 0.5`）；而且在线 Elo 的结果依赖比赛顺序——见第 6 节的分析。
- 讲义术语表说 Elo 是 Bradley-Terry 的聚合：BT 模型假设 `P(A 胜 B) = 1/(1 + 10^((r_B − r_A)/400))`（同一个 logistic 形式），批量最大似然拟合就能得到不依赖顺序的评分。

### 3.7 `make_features`：合成"特征"

```python
def make_features(center, n, d, rng, scale=0.4):
    return [[center + rng.gauss(0, scale) for _ in range(d)] for _ in range(n)]
```

- 生成 `n` 个 `d` 维向量，每维独立服从 `N(center, 0.4²)`，所以真实协方差是 `0.16·I`、均值是 `[center]*d`。
- 有了解析的真值，我们就能算出 FID 的理论值：两组 `center` 差 `s` 时，真 FID = `d·s² = 4s²`（协方差相同，协方差项为 0）。这是验证实现正确性的"标准答案"。

### 3.8 `main`：四个实验

```python
def main():
    rng = random.Random(29)
    d = 4

    print("=== FID bias at small N ===")
    for n in [50, 200, 1000]:
        real = make_features(0.0, n, d, rng)
        gen = make_features(0.0, n, d, rng)  # same distribution
        score = fid(real, gen)
        # ...

    print("=== FID separates different distributions ===")
    real = make_features(0.0, 500, d, rng)
    for shift in [0.0, 0.2, 0.5, 1.0]:
        gen = make_features(shift, 500, d, rng)
        # ...

    prompt = [1.0, 0.5, -0.2, 0.3]
    for image_center in [1.0, 0.5, 0.0, -0.5]:
        image = [image_center + rng.gauss(0, 0.1) for _ in range(d)]
        # ...

    r_a, r_b = 1000, 1000
    for i in range(200):
        # Suppose model A wins 70% of the time
        winner = "a" if rng.random() < 0.7 else "b"
        r_a, r_b = elo_update(r_a, r_b, winner)
```

- 实验 1 用**同分布**测偏差：理论 FID = 0，任何正值都是估计偏差。
- 实验 2 固定一份 500 样本的真实集，逐步平移生成集，看 FID 是否随偏移单调增长。
- 实验 3 用一个固定的 "prompt 向量"，与四个不同中心的"图像向量"算余弦。
- 实验 4 模拟 200 局 A/B 盲评，A 每局以 70% 概率获胜。
- 所有随机性都来自同一个 `random.Random(29)`，结果可复现；但这也意味着改动任一实验的样本数都会改变后续实验的随机序列。
- ⚠️ 与讲义的小差异：讲义练习 1 说比较 N=100 与 N=1000，代码实际用的是 50 / 200 / 1000；讲义说 CLIP-like 比较"特征池"，代码比较的是单个向量。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 4 维合成高斯特征 | 有解析真值，能直接验证 FID 实现与偏差 | 真实 FID 用 2048 维 Inception pool 特征，N ≥ 10k |
| 纯 Python 列表做线性代数 | 每一步都看得见 | 用 NumPy / SciPy（`np.cov`、`scipy.linalg.sqrtm`）或 GPU 实现 |
| Denman–Beavers 求平方根 | 只需矩阵乘与求逆，容易手写 | 对称化后特征分解更稳；或直接用 `sqrtm` |
| 奇异主元用 1e-12 兜底 | 演示代码不崩溃 | 应加 `ε·I` 正则并检查结果；N < d 时协方差必然奇异 |
| 余弦当 CLIP score | 抓住"方向对齐"的本质 | 真实 CLIP score 用 CLIP 编码器，常乘系数并截断负值 |
| 在线 Elo、K=32 | 公式简单、一眼看懂 | 排行榜用 Bradley-Terry 批量拟合 + bootstrap 置信区间 |
| 共享一个 `rng` | 全程可复现 | 实验间相互影响；正式实验应各自独立播种并跑多个种子 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 | `[sum(v[i] for v in vectors) / n for i in range(d)]` | 逐维求均值 |
| 嵌套列表推导 | `[[cov[i][j] / max(n - 1, 1) for j in range(d)] for i in range(d)]` | 生成二维矩阵 |
| 二维列表的正确初始化 | `[[0.0] * d for _ in range(d)]` | 每行都是新列表；`[[0.0]*d]*d` 会共享同一行 |
| 生成器表达式 | `sum((a - b) ** 2 for a, b in zip(mu_r, mu_g))` | 不建中间列表直接求和 |
| 条件表达式 | `1.0 if i == j else 0.0`、`"a" if rng.random() < 0.7 else "b"` | 一行 if-else，用于造单位矩阵和模拟胜负 |
| 切片拷贝与列表拼接 | `row[:] + [...]`、`row[n:]` | 复制行再拼上单位阵；取右半部分 |
| `enumerate` | `for i, row in enumerate(M)` | 同时拿到下标和行 |
| 元组交换 | `A[col], A[pivot] = A[pivot], A[col]` | 无需临时变量交换两行 |
| 单行 `if ... continue` | `if r == col: continue` | 合法，但风格上建议换行 |
| 多返回值 | `return r_a + delta, r_b - delta`；`r_a, r_b = elo_update(...)` | 返回元组并解包 |
| 默认参数 | `def elo_update(r_a, r_b, winner, k=32)`、`scale=0.4`、`iters=30` | 调用时可省略 |
| docstring | `"""Matrix square root by Denman-Beavers iteration ..."""` | 函数的文档字符串，`help()` 可见 |
| 幂运算 | `10 ** ((r_b - r_a) / 400)`、`(a - b) ** 2` | 浮点指数也可以 |
| `max` 防除零 | `max(n - 1, 1)`、`max(na * nb, 1e-8)` | 给分母设下限 |
| f-string 格式符 | `f"{n:5d}"`、`f"{score:.4f}"`、`f"{image_center:+.1f}"`、`f"{r_a:.0f}"` | 宽度 5 的整数、4 位小数、带符号、取整显示 |
| `random.Random(seed)` | `rng = random.Random(29)` | 独立可复现的随机数生成器 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，耗时约 0.04 秒）的完整输出：

```text
=== FID bias at small N ===
  N=   50: FID (identical distributions) = 0.0431  (lower = more similar)
  N=  200: FID (identical distributions) = 0.0288  (lower = more similar)
  N= 1000: FID (identical distributions) = 0.0022  (lower = more similar)
  -> FID should be 0 for identical distributions but is biased up at small N

=== FID separates different distributions ===
  shift=0.0: FID = 0.010
  shift=0.2: FID = 0.185
  shift=0.5: FID = 1.146
  shift=1.0: FID = 4.124

=== CLIP-like cosine similarity ===
  image center +1.0: CLIP-like score = +0.659
  image center +0.5: CLIP-like score = +0.600
  image center +0.0: CLIP-like score = +0.578
  image center -0.5: CLIP-like score = -0.666

=== Elo from synthetic A/B preferences ===
  after 200 pairs (A wins 70%): r_A = 1014, r_B = 986

takeaway: FID is a distance; CLIP is an adherence score; Elo aggregates preferences.
          production evaluation uses all three plus qualitative failure audits.
```

**实验 1：FID 偏差。** 均值项的期望偏差是 `d·2σ²/N = 1.28/N`：N=50 时约 0.026，N=1000 时约 0.0013，剩下的来自协方差项。三个值都 > 0 并随 N 下降，这就是"小 N 偏高"。N=200 的 0.0288 比纯 1/N 规律预期的略大，是单次实验的随机波动——也说明为什么讲义要求报多种子。⚠️ 讲义文字里说小 N 会给出 "falsely low FID"，与这里的输出方向相反，以代码输出为准。

**实验 2：FID 区分度。** 理论值 `4s²`：0 / 0.16 / 1.0 / 4.0，实测 0.010 / 0.185 / 1.146 / 4.124，每个都比理论值高 0.01–0.15——正是实验 1 中那种 N=500 下的正偏差加上随机波动。FID 随偏移**平方**增长，大偏移时偏差可以忽略，小偏移时偏差与信号同量级——这就是"小改进在小 N 下根本测不出来"的原因。

**实验 3：CLIP-like。** 无噪声时 `[c,c,c,c]` 与 prompt 的余弦只取决于 c 的符号，c>0 时都是 `1.6/(2·√1.38) ≈ 0.681`。所以 `+1.0` 与 `+0.5` 理论上应相等，差异全来自噪声（c 越小，噪声占比越大）。`+0.0` 那一行的图像向量是纯噪声，方向随机，0.578 只是碰巧；4 维随机方向的余弦标准差约 0.5，换个种子可能是负数。`−0.5` 方向相反，接近 −0.681。**结论**：输出看起来"单调递减"，其实是巧合；余弦只看方向。

**实验 4：Elo。** 若真实胜率为 70%，均衡分差应为 `400·log10(0.7/0.3) ≈ 147`，即 r_A ≈ 1074。实际只有 1014。我回放了同一随机序列：这 200 局里 A 实际赢了 134 局（67%，对应均衡 r_A ≈ 1062）；r_A 最高到过 1130，后 100 局平均约 1055；但最后 10 局是 `baaaabbaab`，A 只赢一半，把分数拉了回来。K=32 的在线 Elo 对最近几局极其敏感——**单次顺序 Elo 是一个噪声很大的快照**。把这 200 局结果打乱顺序重复 200 次，r_A 的均值约 1063、5%–95% 区间约 1006–1120。

---

## 7. 动手改一改

1. **画偏差曲线**：对 N ∈ {50, 100, 200, 500, 1000, 2000}，每个 N 跑 10 个种子，打印 FID 的均值和标准差，验证均值大约按 `1/N` 衰减（讲义练习 1 的加强版）。
2. **拆出 `fid_from_stats`**：让真实集统计量只算一次；用 `Σ_r = aI`、`Σ_g = bI` 的解析解 `‖Δμ‖² + d(√a − √b)²` 写一个断言测试。
3. **实现一个简化的 MMD**：用 RBF 核 `k(x, y) = exp(−‖x−y‖²/(2h²))` 写无偏 MMD² 估计量，重复实验 1，观察它在同分布时是否在 0 附近上下波动而不是总为正（讲义练习 2 中 CMMD 的核心思想）。
4. **改变协方差而不是均值**：让生成集的 `scale` 从 0.4 变成 0.2（模拟"多样性下降 / 模式塌缩"），看 FID 的协方差项如何反映出来。
5. **支持平局并改用 Bradley-Terry**：给 `elo_update` 增加 `winner == "tie"` 时 `actual = 0.5`；再对两模型的胜负计数直接用 `400·log10(p/(1−p))` 计算分差，与在线 Elo 对比。
6. **加 bootstrap 置信区间**：对 200 局结果有放回重采样 1000 次，给出 A 胜率的 95% 区间，判断"A 比 B 好"是否显著。

---

## 8. 常见坑

- **以为同分布 FID 就是 0**：有限样本下 FID 恒有正偏差，不同 N 的数值不能比较。
- **跨分辨率 / 跨实现比较 FID**：缩放方式、图像格式、特征提取器版本都会改变数值。
- **协方差奇异**：N 小于特征维度时样本协方差必然秩亏，求逆 / 开方会数值爆炸；本代码用 1e-12 静默兜底，结果可能无声地出错。
- **`[[0.0] * d] * d` 共享行**：创建二维列表时的经典 Python 坑，本代码用推导式避开了。
- **把 CLIP score 当绝对质量**：余弦尺度不变、对组合关系不敏感，还能被 prompt 模板刷分。
- **把在线 Elo 的最终值当真实实力**：K 越大越受最近几局影响；应打乱顺序多次平均，或用 Bradley-Terry 批量拟合并给出置信区间。
