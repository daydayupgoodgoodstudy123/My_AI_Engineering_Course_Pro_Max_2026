# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 02 节 奖励投机（Reward Hacking）与古德哈特定律 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，约 4 秒） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`），无需 NumPy、无需 GPU

---

## 1. 这份代码在考察什么

这份约 230 行的代码想复现 Gao、Schulman、Hilton (ICML 2023) 的**过度优化曲线**：

1. **gold 与 proxy**：gold 是 8 维特征上的已知线性函数；proxy 是用 n 条"gold + 噪声"标签做最小二乘拟合的线性 RM（n ∈ {100, 300, 1000, 10000}）。
2. **KL 约束下的策略**：策略是 `N(μ, I)`，与初始策略 `N(0, I)` 的 KL 为 `‖μ‖²/2`；在每个 KL 预算下取让 proxy 最大的 μ，记录 proxy 与 gold 的期望。
3. **重尾噪声**：把标签噪声换成 Student-t(3)，意在模拟 Catastrophic Goodhart。
4. **best-of-N**：从初始策略采样 n 个、选 proxy 最高的，记录 proxy、gold。

代码自带的高斯消元、最小二乘、KL 公式都值得学习。但核心结论**没有被复现**：在"线性 gold + 线性 proxy + 沿 proxy 方向平移"的设定下，gold 是 `sqrt(KL)` 的**线性单调函数**，任何曲线都不会"先升后降"。实际输出中，所有 "gold peak" 都落在预算网格的最大值上，代码结尾的 TAKEAWAY 与它自己的输出相矛盾。读懂"为什么不会出现峰值"，正好能精确理解 Goodhart 崩塌需要什么条件：**代理必须在优化器会去的区域失效**。

> 一句话：**一个结构清晰但模型设定过于线性的 Goodhart 模拟器——它测出了 regressional Goodhart（约 1% 的效率损失），却测不出讲义所说的 extremal/adversarial 崩塌；补上非线性之后曲线才会弯下来。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `D`、`GOLD_W` | 常量 | 8 维特征；真实奖励权重 | gold reward |
| `dot`、`gauss`、`student_t` | 函数 | 点积；标准正态；t 分布采样 | 基础工具、重尾噪声 |
| `sample_feature`、`gold_reward` | 函数 | 从 `N(0, I)` 采样特征；计算 gold | 初始策略、真值 |
| `ProxyRM` | dataclass | 线性权重 `w` + 样本数；`score(x)` | proxy RM |
| `train_proxy` | 函数 | 生成 n 条带噪标签，正规方程 + 岭项求解 | 有限数据拟合的 RM |
| `solve` | 函数 | 带部分主元的高斯消元 | 线性方程组 |
| `sqrt_kl_from_origin` | 函数 | `sqrt(‖μ‖²/2)` | `d = sqrt(KL)` |
| `expected_reward` | 函数 | `E_{N(μ,I)}[⟨w,x⟩] = ⟨w, μ⟩` | 策略的期望奖励 |
| `kl_constrained_policy_sweep` | 函数 | 每个 KL 预算下沿 proxy 方向取 μ，返回 (d, proxy, gold) | KL 约束优化 |
| `best_of_n_sweep` | 函数 | 1000 次试验的 BoN，返回 (伪 d, proxy, gold) | best-of-N |
| `print_curve` | 函数 | 打印表格与"gold 峰值" | 过度优化曲线 |
| `main` | 函数 | 4 条高斯曲线 + 1 条 t 曲线 + 1 条 BoN 曲线 | 驱动 |

数据流：模块级 `random.seed(42)` → 对每个 n：`train_proxy(n)` → `kl_constrained_policy_sweep(rm, budgets)` → `print_curve`；再做 t 噪声与 BoN 两组。

---

## 3. 逐段精讲

### 3.1 gold、特征与 t 分布

```python
D = 8
GOLD_W = [1.0, -0.6, 0.4, 0.2, -0.1, 0.3, -0.5, 0.8]

def student_t(df: float) -> float:
    u = random.gauss(0.0, 1.0)
    chi2 = sum(random.gauss(0.0, 1.0) ** 2 for _ in range(int(df)))
    if chi2 <= 0:
        chi2 = 1e-6
    return u * math.sqrt(df / chi2)
```

- `‖GOLD_W‖ = sqrt(2.55) ≈ 1.597`，后面推导会用到。
- **t 分布的构造**：标准正态 `u` 除以 `sqrt(χ²_df / df)` 就是 t(df)。`χ²_df` 用 df 个标准正态的平方和得到，所以 `int(df)` 要求自由度为整数。
- t(3) 的方差为 `df/(df−2) = 3`（我们抽 20 万个样本测得约 2.89），四阶矩无穷——docstring 说"variance finite but kurtosis infinite"是对的。
- `chi2 <= 0` 的保护几乎不会触发（连续分布取到 0 的概率为 0），属于防御性代码。

### 3.2 训练 proxy：正规方程 + 岭项

```python
    xs = [sample_feature() for _ in range(n_samples)]
    ys = []
    for x in xs:
        eps = gauss() if noise == "gauss" else student_t(3.0)
        ys.append(gold_reward(x) + eps)
    g = [[0.0] * D for _ in range(D)]
    b = [0.0] * D
    for x, y in zip(xs, ys):
        for i in range(D):
            b[i] += x[i] * y
            for j in range(D):
                g[i][j] += x[i] * x[j]
    for i in range(D):
        g[i][i] += 1e-3
    w = solve(g, b)
```

- 最小二乘解 `w = (XᵀX)⁻¹Xᵀy`：`g` 是 8×8 的 Gram 矩阵 `XᵀX`，`b` 是 `Xᵀy`。
- `g[i][i] += 1e-3` 是极小的岭正则（ridge），防止样本很少时矩阵奇异；n ≥ 100 时几乎不影响结果。
- `[[0.0] * D for _ in range(D)]`：二维列表必须这样建；写成 `[[0.0] * D] * D` 会让 8 行共享同一个列表对象（见第 8 节）。
- 拟合质量：100 样本时 `‖w_proxy‖ = 1.608`、与 gold 的夹角余弦 0.9914；10000 样本时余弦 0.9998。proxy 已经非常接近 gold——**这里的代理误差是"有限样本"的回归误差，方向近乎正确**。

### 3.3 `solve`：带部分主元的高斯消元

```python
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        piv = i
        for k in range(i + 1, n):
            if abs(m[k][i]) > abs(m[piv][i]):
                piv = k
        m[i], m[piv] = m[piv], m[i]
        for k in range(i + 1, n):
            f = m[k][i] / m[i][i]
            for j in range(i, n + 1):
                m[k][j] -= f * m[i][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
```

- `row[:] + [b[i]]` 拼成增广矩阵 `[A | b]`，`row[:]` 复制一行，避免修改调用方的 `g`。
- **部分主元**：每列选绝对值最大的行做主元，减少除以小数带来的数值误差。
- 前向消元把矩阵化成上三角，再**回代**从最后一行往上解。
- 对于正定的 Gram 矩阵（加了岭项），这一实现是可靠的；生产中会用 Cholesky 分解或直接调用 `numpy.linalg.lstsq`。

### 3.4 KL 与期望奖励

```python
def sqrt_kl_from_origin(mu: list[float]) -> float:
    return math.sqrt(0.5 * sum(m * m for m in mu))

def expected_reward(w: list[float], mu: list[float]) -> float:
    return dot(w, mu)
```

- 两个协方差同为单位阵的高斯：`KL(N(μ, I) ‖ N(0, I)) = ‖μ‖²/2`。这正是讲义横轴 `d = sqrt(KL)`。
- 线性奖励在高斯下的期望只依赖均值：`E[⟨w, x⟩] = ⟨w, μ⟩`，所以不需要采样就能精确算出 proxy 与 gold。

### 3.5 KL 约束下的"最优策略"——为什么不会有峰值

```python
    for kl in kl_budgets:
        norm = math.sqrt(sum(w * w for w in proxy.w))
        if norm < 1e-9:
            mu = [0.0] * D
        else:
            s = math.sqrt(2 * kl) / norm
            mu = [w * s for w in proxy.w]
        curve.append((
            sqrt_kl_from_origin(mu),
            expected_reward(proxy.w, mu),
            expected_reward(GOLD_W, mu),
        ))
```

- 在约束 `‖μ‖² ≤ 2·KL` 下最大化 `⟨w_proxy, μ⟩`，解是沿 `w_proxy` 方向走到球面上：`μ = s·w_proxy`，`‖μ‖ = sqrt(2·KL)`。代码直接给出这个闭式解（docstring 写的是"sweep lambda"，实际扫描的是 KL 预算，二者通过拉格朗日乘子等价；讲义 "Use It" 说的"hill-climbing"也并不存在）。
- 记 `d = sqrt(KL)`，则 `‖μ‖ = √2·d`：
  - `proxy(d) = ⟨w_proxy, μ⟩ = √2·d·‖w_proxy‖`
  - `gold(d) = ⟨w_gold, μ⟩ = √2·d·‖w_gold‖·cosθ`
  - `gap(d) = √2·d·(‖w_proxy‖ − ‖w_gold‖·cosθ)`
- **三者都是 d 的线性函数**。只要 cosθ > 0（这里约 0.99），gold 就随 d 单调上升，"峰值"只能出现在最大预算处。
- 这测到的是 Manheim & Garrabrant 意义下的 **regressional Goodhart**：代理有小误差，优化代理只损失 `1 − cosθ` 的效率。讲义所说的 extremal/adversarial 崩塌需要"代理在远离训练数据的区域失效"，而线性模型在任何地方都同样准（或同样不准）。

### 3.6 best-of-N

```python
        for _ in range(trials):
            xs = [sample_feature() for _ in range(n)]
            best = max(xs, key=proxy.score)
            proxies.append(proxy.score(best))
            golds.append(gold_reward(best))
            kls.append(math.sqrt(0.5 * sum(b * b for b in best)))
```

- `max(xs, key=proxy.score)`：用 proxy 打分挑出最好的样本——这就是 BoN 采样。
- ⚠️ 横轴不是 KL：`sqrt(0.5·‖best‖²)` 是被选样本到原点的距离，n = 1 时期望约 `sqrt(0.5 × 8) = 2`（打印 1.920）。BoN 分布相对原策略的 KL 有解析式 `log n − (n−1)/n`，n = 1 时为 0、n = 1024 时为 5.932（`sqrt` 为 2.436）。注释自己也承认"we compute a proxy"。
- 1000 次试验 × 最多 1024 个 8 维样本，是程序耗时的主要来源（约 4 秒中的大部分）。
- 在线性 gold 下，BoN 的 gold 同样单调上升（n = 1024 时 5.197）。

### 3.7 打印与 `main`

```python
    peak_gold = max(curve, key=lambda r: r[2])
    print(f"  gold peak at sqrt(KL) = {peak_gold[0]:.3f}, "
          f"gold = {peak_gold[2]:.3f}, proxy = {peak_gold[1]:.3f}")
```

- `max(..., key=lambda r: r[2])` 按元组第 3 项（gold）取最大行。曲线单调时它必然返回最后一行——"peak"只是网格边界，不是真正的峰。
- `main` 中的五条 KL 曲线共用预算网格 `[0, 0.2, 0.5, 1, 1.5, 2, 3, 5, 8]`（`sqrt` 后最大为 2.828）。
- 结尾 TAKEAWAY 的四句话中，只有"proxy reward climbs monotonically"被输出支持；"gold peaks and falls""More proxy samples push the peak further""Heavy-tailed noise moves the peak closer to the origin"都没有出现在结果里。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 线性 gold、线性 proxy | 期望奖励有闭式解，代码短 | gold 随 KL 线性上升，**无法出现峰值**；需要非线性 gold 或在尾部失效的 proxy |
| 策略为 `N(μ, I)`，只移动均值 | KL 有闭式 `‖μ‖²/2` | 策略无法"改变形状"去钻特定区域，表达不了 Catastrophic Goodhart |
| 闭式最优 μ（沿 proxy 方向） | 免去迭代优化 | 讲义说的 hill-climbing 并不存在；真实 RLHF 是逐步优化，可在途中早停 |
| 正规方程 + 手写高斯消元 + 1e-3 岭 | 纯标准库 | 生产用 `lstsq` / Cholesky；岭系数太小对 n < D 的情形帮助有限 |
| 标签噪声换成 t(3) | 想模拟"重尾" | 重尾在标签里，不在代理误差的输入空间分布里；OLS 仍无偏，不构成 Catastrophic Goodhart |
| BoN 横轴用样本范数 | 免算 KL | 横轴不是 KL，与 KL 约束曲线不可比；应使用 `log n − (n−1)/n` |
| 全局随机种子 | 可复现 | 各实验共享随机流，改动一处会改变后面所有结果 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，`list[list[float]]` 等写法更通用 |
| 模块级常量 | `D = 8`、`GOLD_W = [...]` | 约定用全大写表示"不应修改" |
| 生成器表达式求和 | `sum(x * y for x, y in zip(a, b))` | 点积的惯用写法，不创建中间列表 |
| `**` 幂运算 | `random.gauss(0.0, 1.0) ** 2` | 平方 |
| `@dataclass` | `class ProxyRM: w: list[float]; n_samples: int` | 自动生成构造函数；方法 `score` 照常定义 |
| 条件表达式 | `eps = gauss() if noise == "gauss" else student_t(3.0)` | 按参数选择噪声类型 |
| 二维列表的正确创建 | `[[0.0] * D for _ in range(D)]` | 每行是新列表；`[[0.0]*D]*D` 会共享行 |
| 切片复制 | `row[:]` | 浅复制一行，避免改动原矩阵 |
| 元组交换 | `m[i], m[piv] = m[piv], m[i]` | 一行交换两个元素，无需临时变量 |
| 倒序 `range` | `range(n - 1, -1, -1)` | 回代时从最后一行往上 |
| `max` 的 `key` 参数 | `max(xs, key=proxy.score)`、`max(curve, key=lambda r: r[2])` | 按自定义标准取最大；`proxy.score` 是绑定方法，可直接当函数传 |
| `lambda` | `lambda r: r[2]` | 匿名函数，取元组第 3 项 |
| 返回类型注解 | `-> list[tuple[float, float, float]]` | 说明返回"三元组列表" |
| 元组解包遍历 | `for sk, p, g in curve:` | 直接拆出三列 |
| f-string 对齐与符号 | `{sk:>9.3f}`、`{p - g:>+8.3f}`、`{'sqrt(KL)':>9}` | `>` 右对齐、宽度 9；`+` 强制显示正负号；f-string 内可写表达式 |
| 相邻 f-string 拼接 | `print(f"... {x:.3f}, " f"gold = {y:.3f}")` | 括号内的多段字符串自动拼接 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(42)`，约 4.3 秒）。节选：

```text
Proxy RM trained on 100 samples (Gaussian noise)
   sqrt(KL)     proxy      gold       gap
      0.000     0.000     0.000    +0.000
      0.447     1.017     1.001    +0.016
      1.000     2.274     2.239    +0.035
      2.828     6.433     6.333    +0.100
  gold peak at sqrt(KL) = 2.828, gold = 6.333, proxy = 6.433

Proxy RM trained on 1000 samples (Gaussian noise)
      2.828     6.268     6.377    -0.108        ← gap 为负
  gold peak at sqrt(KL) = 2.828 ...

Proxy RM trained on 10000 samples (Gaussian noise)
  gold peak at sqrt(KL) = 2.828, gold = 6.386, proxy = 6.418

Proxy RM, 300 samples, Student-t(3) noise (heavy tails)
      2.828     6.005     6.332    -0.327
  gold peak at sqrt(KL) = 2.828 ...

Best-of-N sampling (300-sample proxy)
      1.920     0.032     0.034    -0.002        ← n = 1，横轴却不是 0
      2.951     5.271     5.197    +0.074        ← n = 1024
  gold peak at sqrt(KL) = 2.951 ...
```

逐项解读：

- **gold 全部单调上升**：每条曲线的 "gold peak" 都是最后一行。用 `‖w_gold‖ = 1.597` 验证：100 样本时 `‖w_proxy‖ = 1.608`、cosθ = 0.9914，于是 `d = 1` 时 proxy = `√2 × 1.608 = 2.274`、gold = `√2 × 1.597 × 0.9914 = 2.239`，与输出一致。
- **gap 的符号**：取决于 `‖w_proxy‖` 是否大于 `‖w_gold‖·cosθ`。1000 样本拟合的 `‖w_proxy‖ = 1.567` 偏小，gap 为负；t 噪声拟合的 `‖w_proxy‖ = 1.501`，gap 更负。gap 的正负没有"过度优化"含义。
- **样本数的影响**：只改变 cosθ（0.991 → 0.9998），gold 在 `d = 2.828` 处从 6.333 增至 6.386，影响很小；不存在"峰值外移"。
- **t 噪声**：cosθ 仍为 0.991，曲线形状与高斯情形相同。
- **BoN**：横轴从 1.92 开始，是样本范数而非 KL；正确的 `sqrt(KL)` 应为 0、0.439、0.798、1.097、1.355、1.782、2.133、2.436。

**让曲线弯下来**：我们把 gold 改为 `⟨w_gold, x⟩ − 0.3·(‖x‖² − D)`（对极端特征的惩罚），proxy 仍做线性拟合。此时 `E[gold] = √2·d·‖w_gold‖·cosθ − 0.6·d²`，与讲义 `α·d − β·d²` 同形。实测（n = 100）：

| sqrt(KL) | 0.447 | 1.000 | 1.414 | 1.732 | 2.236 | 2.828 |
|----------|-------|-------|-------|-------|-------|-------|
| proxy | 1.110 | 2.483 | 3.511 | 4.300 | 5.551 | 7.022 |
| gold | 0.850 | 1.569 | 1.867 | **1.957** | 1.850 | 1.335 |

proxy 一路上升，gold 在约 1.73 处见顶后回落——这才是讲义描述的形状。线性 proxy 看不到二次项（对称分布下与线性特征不相关），在训练分布内很准、在尾部失效，正是 extremal Goodhart。

---

## 7. 动手改一改

1. **（讲义练习 1）** 用本代码跑 100、300、1000 样本，记录"峰值"位置，然后用 `d·√2·‖w‖·cosθ` 公式解释为什么它总在网格边界；再把预算网格扩大到 `[0, …, 50]`，确认依旧单调。
2. **让峰值出现**：按第 6 节加入 `−C·(‖x‖² − D)` 项，扫描 `C ∈ {0.1, 0.3, 1.0}`，验证峰值位置 `d* ≈ √2·‖w_gold‖·cosθ / (4C)`。
3. **让"更多数据推远峰值"出现**：给 proxy 加上二次特征（例如每个 `x_i²`），并让训练特征只来自 `‖x‖` 较小的区域；比较 100 与 10000 样本时的峰值位置。
4. **修正 BoN 横轴**：用 `math.log(n) - (n - 1) / n` 作为 KL；在非线性 gold 下重跑 BoN，并尝试拟合讲义练习 3 的 `d·(α − β·d)`。
5. **（讲义练习 2，改造版）** 不在标签上加 t 噪声，而是构造"代理误差在输入空间重尾"的 proxy：例如 `proxy(x) = gold(x) + 100·1[x_8 > 3]`；把策略族扩展为"原分布与该区域截断分布的混合"，计算不同 KL 下的最优混合比例，复现 Catastrophic Goodhart（参考测验 Q12）。
6. **进阶**：实现 3 个用不同子样本训练的 proxy 组成 ensemble，用"三者最小值"作为优化目标，在第 2 题的设定下比较 gold 峰值的位置与高度（对应讲义的 Coste 等方法）。

---

## 8. 常见坑

- **线性世界里没有 Goodhart 崩塌**：只要 proxy 与 gold 都是线性的、策略只能平移，gold 必然随优化单调变化。模拟 reward hacking 时，一定要让代理在优化器会去的区域失效。
- **把网格边界当峰值**：`max(curve, key=...)` 总能返回一个"最大值"；要判断是否真有峰，应检查峰值是否在内部、两侧是否下降。
- **横轴口径不一**：KL 约束曲线用 `sqrt(KL)`，BoN 若用样本范数就无法比较。Gao 的结论都是以 KL 为横轴给出的。
- **标签重尾 ≠ 代理误差重尾**：OLS 对零均值有限方差噪声无偏；Catastrophic Goodhart 讲的是 `proxy(x) − gold(x)` 在输入空间中的尾部。
- **gap 的符号没有意义**：proxy 与 gold 的尺度可以不同；关注 gold 曲线的形状与峰值，而不是二者之差的正负。
- **二维列表别用乘法复制行**：`[[0.0] * D] * D` 会让所有行指向同一对象，Gram 矩阵会被算错。
- **共享随机流**：调整一个实验的样本数，会改变之后所有实验的随机数；需要独立对比时，为每个实验单独 `random.Random(seed)`。
