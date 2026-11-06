# 测验 · 范数与距离（Norms and Distances）

> **阶段 01 · 数学基础 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/distances.py](../code/distances.py) ｜ 代码讲解：[code/distances.讲解.md](../code/distances.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 范数 ↔ 距离 | 范数衡量向量"大小"；两点距离就是差向量的范数 `d(a,b) = ‖a − b‖` |
| 2 | L1 / L2 / L∞ | L1 = 绝对值之和（曼哈顿），L2 = 平方和开根（欧氏），L∞ = 最大分量（切比雪夫）；恒有 `‖x‖∞ ≤ ‖x‖₂ ≤ ‖x‖₁` |
| 3 | Lp 族与单位球 | `‖x‖p = (Σ\|xᵢ\|ᵖ)^(1/p)`；p=1 菱形、p=2 圆、p→∞ 正方形；p 越大越只看最大的那个分量 |
| 4 | 余弦相似度 vs 点积 | `cos = a·b / (‖a‖‖b‖)` 只看方向；点积额外包含模长（可当作热度/置信度信号）；向量 L2 归一化后两者相同 |
| 5 | 马氏距离 | `√((x−y)ᵀ S⁻¹ (x−y))`：先用协方差"白化"再算 L2；S = I 时退化为欧氏距离；适合异常检测 |
| 6 | 集合与字符串距离 | Jaccard = 交集/并集（分割里的 IoU）；编辑距离用 DP 求最少插入/删除/替换次数，O(mn) |
| 7 | KL 散度不是距离 | 不对称、不满足三角不等式；P 有质量而 Q 为 0 的地方 KL = ∞ |
| 8 | Wasserstein 距离 | 搬土的最小代价，是真正的度量；分布不重叠时仍有限、仍有梯度（WGAN 的动机）；一维时 = CDF 差的绝对值之和 |
| 9 | 损失与正则就是距离 | MAE ↔ L1、MSE ↔ L2²、交叉熵 ↔ KL；Lasso（L1）产生稀疏，Ridge（L2）只收缩不置零 |
| 10 | 最近邻检索 | 精确搜索 O(n·d)/查询；ANN（HNSW、IVF、PQ、LSH）用少量精度换大量速度，是向量数据库的核心 |

### 核心技能（能动手做到）

- [ ] 不用 NumPy 从零实现 L1/L2/Lp/L∞、余弦、点积、马氏、Jaccard、编辑距离、KL、一维 Wasserstein，并用 `(3,4)` 验证 L1=7、L2=5、L∞=4
- [ ] 手填 `"kitten" → "sitting"` 的编辑距离 DP 表，并写出只用两行数组的 O(min(m,n)) 空间版本
- [ ] 用 CDF 法手算 `[0.5,0.5,0,0]` 与 `[0,0,0.5,0.5]` 的 Wasserstein 距离（= 2），并说明为什么此时 KL 为 ∞
- [ ] 能用一句话证明 `‖x‖∞ ≤ ‖x‖₂ ≤ ‖x‖₁`，并用随机向量验证
- [ ] 能解释（并用代码演示）为什么沿相关方向偏离的点马氏距离小、逆相关方向偏离的点马氏距离大
- [ ] 用 NumPy 写出"批量归一化 + 矩阵乘"的余弦相似度矩阵和 top-k 检索
- [ ] 给定一个任务（文本检索、推荐、去重、异常检测、GAN 训练），能选出距离并说清楚其他选项为什么不合适

---

## 二、基础自测（选择题）

**Q1.** `A = (1, 2, 3)`，`B = (4, 0, 6)`。它们的 L1、L2、L∞ 距离依次是：

- A. 8、≈4.69、3
- B. 8、22、3
- C. 4、≈4.69、3
- D. 8、≈4.69、6

**Q2.** 下列哪一个**不满足对称性** `d(a,b) = d(b,a)`？

- A. L1 距离
- B. Jaccard 距离
- C. KL 散度
- D. 一维 Wasserstein 距离

**Q3.** `a = [1, 2, 3]`，`b = [2, 4, 6]`。下列说法正确的是：

- A. 余弦相似度为 1，所以它们的 L2 距离也是 0
- B. 余弦相似度为 1，点积为 28，L2 距离约为 3.74
- C. 余弦相似度为 0.5，因为 b 的模长是 a 的 2 倍
- D. 把两者都 L2 归一化后，点积仍为 28

**Q4.** 关于"L1 正则产生稀疏解、L2 正则不会"，最准确的解释是：

- A. L1 的惩罚系数通常比 L2 大
- B. L1 约束区域是顶点落在坐标轴上的菱形，损失等高线更容易先碰到顶点（某些权重 = 0）；L2 约束是圆，没有顶点
- C. L1 的梯度随权重变大而变大，所以能把大权重压到 0
- D. L2 正则只作用在 bias 上，不作用在权重上

**Q5.** 某数据集中两个特征强正相关。点 P 沿相关方向偏离均值，点 Q 逆着相关方向偏离均值，两者到均值的 L2 距离差不多。下列说法正确的是：

- A. P 的马氏距离远大于 Q
- B. Q 的马氏距离远大于 P，Q 更可能是异常点
- C. 两者马氏距离相同，因为 L2 距离相同
- D. 特征相关时协方差矩阵不可逆，马氏距离无法计算

**Q6.** 按本节代码 `wasserstein_1d` 的约定（4 个箱、相邻箱间距为 1），`P = [1, 0, 0, 0]`、`Q = [0, 0, 0, 1]` 的 Wasserstein 距离和 `KL(P‖Q)` 分别是：

- A. 3 和 ∞
- B. 4 和 ∞
- C. 3 和 0
- D. ∞ 和 3

**Q7.** `"sunday"` 到 `"saturday"` 的编辑距离（Levenshtein）是：

- A. 2
- B. 3
- C. 4
- D. 5

**Q8.** 向量库中所有向量和查询都已 L2 归一化。按下列哪种方式排序，结果**可能与另外三种不同**？

- A. 点积从大到小
- B. 余弦相似度从大到小
- C. L2 距离从小到大
- D. L1 距离从小到大

---

## 三、动手 / 代码题

**Q9.** 不运行代码，写出下面四行的输出，并分别说明背后的实现细节（代码来自 `distances.py`）。

```python
print(cosine_similarity([0, 0], [1, 2]))
print(cosine_distance([0, 0], [0, 0]))
print(l2_distance([1, 2, 3], [1, 2]))
print(lp_norm([3, 4], float('inf')), lp_norm([3, 4], 1))
```

相关源码：

```python
def lp_norm(x, p):
    if p == float('inf'):
        return max(abs(xi) for xi in x)
    return sum(abs(xi) ** p for xi in x) ** (1 / p)

def l2_distance(a, b):
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

def cosine_similarity(a, b):
    dot = dot_product(a, b)
    norm_a = l2_norm(a)
    norm_b = l2_norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

**Q10.** `demo_regularization` 的真实输出如下（`random.seed(42)` 生成 10 个权重，学习率 0.1，各走 50 步）：

```text
  Original weights: [-0.288, -0.346, -0.223, 1.404, -0.255, -2.995, 0.665, -0.535, -0.434, 0.232]
  After L1 regularization (50 steps):
    Weights: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    Zeros:   10/10
  After L2 regularization (50 steps):
    Weights: [-0.0, -0.0, -0.0, 0.0, -0.0, -0.0, 0.0, -0.0, -0.0, 0.0]
    Zeros:   0/10
```

(a) 为什么 L1 把**所有**权重（包括 -2.995）都清零了？L2 为什么显示 `-0.0` 却统计为 `0/10` 个零？
(b) 这个演示和结尾那句 "L1 drives 'small' weights to exactly zero" 有什么不一致？
(c) 改写演示：加入数据拟合项 `½(w − w₀)²`，让 L1 只清零"小"权重、L2 均匀收缩，并给出你预期的结果。

**Q11.** `mahalanobis_distance(x, y, cov_matrix)` 每次调用都会执行 `invert_matrix(cov_matrix)`。

```python
def mahalanobis_distance(x, y, cov_matrix):
    n = len(x)
    diff = [xi - yi for xi, yi in zip(x, y)]
    inv_cov = invert_matrix(cov_matrix)
    temp = [0.0] * n
    for i in range(n):
        for j in range(n):
            temp[i] += diff[j] * inv_cov[j][i]
    result = sum(temp[i] * diff[i] for i in range(n))
    return math.sqrt(max(0, result))
```

(a) `temp` 计算的是什么？`max(0, result)` 防的是什么？
(b) 用 `find_k_nearest(query, dataset, mahalanobis_distance, k=5, cov_matrix=cov)` 在 n 个 d 维点上检索，总复杂度是多少？
(c) 写一个 `make_mahalanobis(cov_matrix)`，只求一次逆，返回可直接传给 `find_k_nearest` 的两参数距离函数。

**Q12.** `edit_distance` 用了完整的 `(m+1)×(n+1)` 二维表。写一个只保留两行的版本 `edit_distance_2rows(s1, s2)`，空间降到 O(min(m, n))，并说明为什么只需要"上一行"。

---

## 四、面试高频题

**Q13.**（场景设计）你们的 RAG 系统 embedding 模型训练时用的是余弦相似度，但向量库建索引时选了 L2 距离，而且入库前没有做归一化。会有什么后果？怎么修？

**Q14.**（原理深挖）为什么 L1 正则（Lasso）会产生稀疏解而 L2 正则（Ridge）不会？请从几何和梯度两个角度回答，并说明 Elastic Net 适合什么场景。

**Q15.**（基础必考）KL 散度为什么不是"距离"？前向 KL 与反向 KL 的行为有何不同？请举出至少两个它在大模型训练中的用处。

**Q16.**（原理深挖）为什么 WGAN 要用 Wasserstein 距离替代原始 GAN 的 JS/KL 类目标？一维情况下 Wasserstein 怎么算？

**Q17.**（工程实践）要为 1 亿条 768 维 embedding 搭建相似检索服务，你会如何选择距离、索引结构和评估方式？

**Q18.**（追问型）用马氏距离做多维异常检测时，协方差矩阵估计不可靠（特征多、样本少、有离群点污染）怎么办？阈值怎么定？

---

## 五、参考答案与解析

### Q1 — 答案：A

差向量为 `(3, −2, 3)`。L1 = 3+2+3 = 8；L2 = √(9+4+9) = √22 ≈ 4.69；L∞ = max(3, 2, 3) = 3。这正是 `demo_distances` 的真实输出（`8.0000 / 4.6904 / 3.0000`）。B 忘了开根号（22 是 L2²）；C 忘了取绝对值（3 − 2 + 3 = 4）；D 把 L∞ 当成了坐标最大值 6。

### Q2 — 答案：C

`KL(P‖Q) ≠ KL(Q‖P)`。代码中 `P=[0.9,0.1]`、`Q=[0.5,0.5]` 得到 0.3681 与 0.5108 nats，差 0.1428。L1、Jaccard 距离、Wasserstein 都是对称的真度量。补充：余弦距离 `1 − cos` 虽然对称，但**不满足三角不等式**（例如 `(1,0)`、`(1,1)/√2`、`(0,1)`：0.293 + 0.293 < 1），严格说也不是度量。

### Q3 — 答案：B

b = 2a，方向相同，cos = 1；点积 = 2+8+18 = 28；`‖a − b‖ = ‖−a‖ = √14 ≈ 3.74`。A 错在"方向相同 ≠ 位置相同"；C 混淆了余弦与模长；D 归一化后两者都是单位向量，点积 = cos = 1（代码 "After L2 normalization" 表格正是 `1.0000 / 1.0000`）。

### Q4 — 答案：B

几何解释见讲义"Connection to Regularization"。梯度角度同样重要：L1 的（次）梯度是常数 `±λ`，不管权重多小都以恒定速度推向 0，能"推过"零点；L2 的梯度是 `2λw`，权重越小推力越小，只会无限逼近 0。C 恰好说反了——随权重变大的是 L2 的梯度。A、D 是无关干扰项。

### Q5 — 答案：B

马氏距离用 `S⁻¹` 把"数据本来就分布得很开"的方向压缩、把"数据很集中"的方向放大。沿相关轴偏离是"正常的变化"，逆相关方向偏离在数据中几乎不存在。代码真实输出：沿轴点 L2 = 3.84、马氏 = 0.98；离轴点 L2 = 3.16、马氏 = 3.86。D 错：只要不是**完全**共线（相关系数 ±1），协方差矩阵就可逆。

### Q6 — 答案：A

CDF：`P → [1,1,1,1]`，`Q → [0,0,0,1]`，差的绝对值之和 = 1+1+1+0 = 3（代码 "Opposite ends" 输出 3.0000）。讲义里的例子用的是 5 个箱，所以是 4——B 是"背原文"的陷阱。KL(P‖Q)：P 在第 0 箱有质量而 Q 为 0，`kl_divergence` 直接返回 `inf`。

### Q7 — 答案：B

`sunday → s(a)(t)unday`：插入 a、t 两次；再把 n 替换为 r（`sunday` 的 n 对 `saturday` 的 r），共 3 次。代码输出 `'sunday' -> 'saturday':  distance = 3`。

### Q8 — 答案：D

单位向量有 `‖a − b‖₂² = 2 − 2·a·b`，所以 A、B、C 三者排序完全一致（点积 = 余弦，L2 距离是余弦的单调递减函数）。L1 距离与点积之间没有这种单调关系，排序可能不同。这也是"归一化后选点积/余弦/L2 都行"的理论依据。

### Q9 — 参考答案

```text
0.0
1.0
0.0
4 7.0
```

1. **零向量约定**：`cosine_similarity` 遇到零向量直接返回 `0.0`，而不是抛 `ZeroDivisionError`。这是一个"约定"而非数学事实——零向量没有方向，余弦无定义。
2. 于是 `cosine_distance([0,0],[0,0]) = 1 − 0 = 1.0`：两个**完全相同**的零向量，余弦距离却是 1。这说明 `d(x,x)=0` 在这个约定下被破坏，检索时零向量（如空文档的 embedding）需要单独处理。
3. **`zip` 静默截断**：`[1,2,3]` 和 `[1,2]` 只比较前两维，返回 `0.0`，维度不匹配完全不报错。生产代码应断言维度相等或用 `zip(..., strict=True)`（Python 3.10+）。
4. `p = inf` 分支返回 `max(...)`，输入是整数所以得到 `4`（int）；p = 1 时 `7 ** (1/1)` 是 `int ** float`，得到 `7.0`（float）。

### Q10 — 参考答案

(a) 演示**只有正则项、没有数据拟合项**。L1 每步把 |w| 减 `lr = 0.1`，50 步累计可减 5.0，而最大的 |w| 也只有 2.995，所以全部归零（`abs(w) < lr` 时直接置 0）。L2 每步 `w ← w − 0.1·2w = 0.8w`，50 步后乘以 `0.8⁵⁰ ≈ 1.43×10⁻⁵`，最大的权重只剩约 `−4.3×10⁻⁵`，`round(·, 3)` 显示成 `-0.0`，但并不精确等于 0，所以 `abs(w) < 1e-10` 的计数为 0。

(b) 结论说 L1 只清零"small"权重，但实际清零了全部，包括最大的一个；L2 虽然"没有精确为 0"，但打印出来也几乎全是 0。两者的区别没被真正展示出来——真正的对比只有在**数据项与正则项相互拉扯**时才出现。

(c) 加入 `½(w − w₀)²` 后，L1 的最优解就是著名的**软阈值**：`w = sign(w₀)·max(|w₀| − λ, 0)`；L2 的最优解是 `w₀ / (1 + 2λ)`。迭代版（近端梯度法）：

```python
import random
random.seed(42)
w0 = [random.gauss(0, 2) for _ in range(10)]
lam, lr, steps = 0.5, 0.1, 200

def soft_threshold(z, t):
    if z > t:
        return z - t
    if z < -t:
        return z + t
    return 0.0

w_l1 = w0[:]
for _ in range(steps):
    for i in range(len(w_l1)):
        z = w_l1[i] - lr * (w_l1[i] - w0[i])        # 数据项 ½(w - w0)² 的梯度步
        w_l1[i] = soft_threshold(z, lr * lam)        # L1 的近端（proximal）步 = 软阈值

w_l2 = w0[:]
for _ in range(steps):
    for i in range(len(w_l2)):
        w_l2[i] -= lr * ((w_l2[i] - w0[i]) + 2 * lam * w_l2[i])

print("L1:", [round(w, 3) for w in w_l1], "zeros =", sum(w == 0.0 for w in w_l1))
print("L2:", [round(w, 3) for w in w_l2], "zeros =", sum(w == 0.0 for w in w_l2))
```

实际输出：

```text
L1: [0.0, 0.0, 0.0, 0.904, 0.0, -2.495, 0.165, -0.035, 0.0, 0.0] zeros = 6
L2: [-0.144, -0.173, -0.111, 0.702, -0.128, -1.497, 0.332, -0.267, -0.217, 0.116] zeros = 0
```

|w₀| < 0.5 的 6 个权重被精确置 0，其余各减 0.5；L2 则把每个权重都除以 2，一个都不为 0——这才是"稀疏 vs 收缩"。

### Q11 — 参考答案

(a) `temp[i] = Σⱼ diff[j]·S⁻¹[j][i]`，即行向量 `diffᵀ S⁻¹`；再与 `diff` 点积得到二次型 `diffᵀ S⁻¹ diff`。理论上它 ≥ 0（S⁻¹ 正定），但浮点误差可能让接近 0 的结果变成 `-1e-17`，`math.sqrt` 会抛 `ValueError`，`max(0, ·)` 是防御。

(b) 每次调用：求逆 O(d³) + 二次型 O(d²)。检索 n 个点就是 **O(n·d³)**，求逆被重复了 n 次，完全浪费。

(c)

```python
def make_mahalanobis(cov_matrix):
    inv_cov = invert_matrix(cov_matrix)      # 只求一次逆
    n = len(inv_cov)

    def dist(x, y):
        diff = [xi - yi for xi, yi in zip(x, y)]
        result = sum(diff[i] * inv_cov[i][j] * diff[j]
                     for i in range(n) for j in range(n))
        return math.sqrt(max(0.0, result))

    return dist

m_dist = make_mahalanobis(cov)
find_k_nearest(query, dataset, m_dist, k=5)   # 不再需要 cov_matrix=cov
```

总复杂度降为 O(d³ + n·d²)。已验证与原函数结果一致。更进一步：对 S 做 Cholesky 分解 `S = LLᵀ`，把所有点预先变换为 `L⁻¹x`（白化），之后就是普通 L2 距离，可以直接用现成的 L2 ANN 索引。

### Q12 — 参考答案

`dp[i][j]` 只依赖 `dp[i-1][j]`（上）、`dp[i][j-1]`（左）、`dp[i-1][j-1]`（左上），也就是"上一行"和"当前行左边"。所以只需保留两行：

```python
def edit_distance_2rows(s1, s2):
    if len(s1) < len(s2):
        s1, s2 = s2, s1                      # 让 s2 是较短的那个，行长 = min(m, n) + 1
    prev = list(range(len(s2) + 1))          # 对应 dp[0][*]
    for i in range(1, len(s1) + 1):
        curr = [i] + [0] * len(s2)           # dp[i][0] = i
        for j in range(1, len(s2) + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
    return prev[-1]
```

已用代码中 6 组样例断言与原函数结果一致。交换 s1、s2 不影响结果，因为编辑距离是对称的（插入与删除互为逆操作）。时间仍是 O(mn)；如果还要**回溯出编辑路径**，就不能只留两行（或需要 Hirschberg 分治算法）。

### Q13 — 参考回答要点

- **后果**：未归一化时，L2 距离 `‖a−b‖² = ‖a‖² + ‖b‖² − 2a·b` 会被模长主导——模长大（或小）的文档系统性地被排后（或排前），与"语义方向"无关，召回质量下降且难以排查。
- **修复**：入库和查询时都做 L2 归一化，之后 L2、余弦、点积排序一致（`‖a−b‖² = 2 − 2cos`）；或直接改用内积/余弦索引（如 FAISS 的 `IndexFlatIP` 配合归一化）。
- **原则**：检索度量要与 embedding 模型训练时的度量一致；有的模型输出本就已归一化，要看模型说明。
- **验证**：抽样做精确检索对比 recall@k，确认修复后的排序与"余弦精确检索"一致。
- **常见误区**：认为"反正都是相似度，选哪个都一样"——只有归一化之后才成立。

### Q14 — 参考回答要点

- **几何**：约束形式 `‖w‖₁ ≤ t` 是菱形（高维是交叉多面体），顶点在坐标轴上；损失的椭圆等高线向外扩张时最先碰到顶点，此时部分坐标为 0。`‖w‖₂ ≤ t` 是圆球，切点一般不在轴上。
- **梯度**：L1 次梯度大小恒为 λ，小权重也被持续推向 0 并在 0 处"停住"（0 处次梯度集合 `[−λ, λ]` 能吸收数据梯度）；L2 梯度 `2λw` 随 w 变小而消失，只渐近收缩。闭式解对比：软阈值 `sign(w)·max(|w|−λ,0)` vs 缩放 `w/(1+2λ)`（见 Q10）。
- **Elastic Net**：`λ₁‖w‖₁ + λ₂‖w‖₂²`。特征高度相关时，Lasso 往往在一组相关特征里随意选一个；Elastic Net 倾向于成组保留/剔除，也更稳定。适合 p ≫ n、特征成组相关的场景（基因、文本）。
- **加分点**：深度学习里的 "weight decay" 就是 L2；对 Adam 而言，解耦的 weight decay（AdamW）与 L2 正则并不等价。

### Q15 — 参考回答要点

- **不是距离**：不对称（`KL(P‖Q) ≠ KL(Q‖P)`），不满足三角不等式；当 P 有质量而 Q 为 0 时为 ∞。它是"散度"：用 Q 编码来自 P 的样本多付出的信息量。
- **前向 KL `KL(P‖Q)`**（P 为目标、Q 为近似）：Q 在 P 有质量的地方必须也有质量，否则代价爆炸，所以 Q 会"覆盖所有模式"（mean-seeking / mode-covering），可能把质量摊在模式之间。
- **反向 KL `KL(Q‖P)`**：Q 只需避开 P 为 0 的区域，倾向于锁定单个模式（mode-seeking）。
- **大模型中的用处**（讲义列出）：RLHF 中用 KL 惩罚让策略不要偏离参考模型太远；知识蒸馏中学生拟合教师分布；VAE 的 ELBO 中 KL 项把后验拉向先验；策略梯度中约束每次更新幅度。
- **加分点**：交叉熵 = H(P) + KL(P‖Q)，P 固定时最小化交叉熵等价于最小化前向 KL；需要对称版本时可用 JS 散度。

### Q16 — 参考回答要点

- **问题**：真实分布与生成分布在高维空间中往往支撑集几乎不重叠。此时 KL 为 ∞ 或 JS 散度饱和为常数，判别器"完美"后，梯度对生成器几乎没有指导意义，训练不稳定、易模式坍塌。
- **Wasserstein**：衡量"把一堆土搬成另一堆的最小功"，即使不重叠也随分布间的距离连续变化——代码 `demo_wasserstein` 中平移 1 格、2 格、移到两端（3 格）分别得到 1、2、3，而 KL 全是 ∞。它是真度量（对称、三角不等式）。
- **一维算法**：`W₁ = ∫|F_P(x) − F_Q(x)| dx`，离散箱上就是累计和之差的绝对值求和（`wasserstein_1d`）。高维时一般没有闭式，WGAN 通过 Kantorovich–Rubinstein 对偶用一个 1-Lipschitz 的 critic 来估计（权重裁剪 → WGAN-GP 的梯度惩罚）。
- **常见误区**：以为 Wasserstein 在高维也能像一维那样用 CDF 直接算。

### Q17 — 参考回答要点

- **度量**：先确认 embedding 模型的训练度量；通常统一 L2 归一化，然后用内积（等价余弦），这样所有 ANN 库都能高效支持。
- **规模估算**：1e8 × 768 × 4 字节 ≈ 307 GB（float32），单机内存放不下原始向量 → 需要压缩或分片。
- **索引选择**（讲义中的 ANN 家族）：
  - HNSW：召回/延迟权衡最好，是向量库默认选择，但图结构额外占内存；
  - IVF：先聚类分桶、只搜最近的几个桶，适合十亿级，需要用代表性数据训练聚类中心；
  - PQ（乘积量化）：把向量压成几十字节，内存受限时与 IVF 组合（IVF-PQ）；
  - 精确 KNN 是 O(n·d)/查询，仅用于小规模或离线评估。
- **评估**：以精确检索为基准测 recall@k，同时测 P99 延迟、QPS、内存；调 HNSW 的搜索宽度或 IVF 的探测桶数，找到业务可接受的权衡点。
- **加分点**：高维下距离会"集中"（最近与最远的差距相对变小），这也是只用 L2 原始距离做阈值判断不可靠的原因；可提到过滤（metadata filter）与混合检索。

### Q18 — 参考回答要点

- **为什么难**：S 需要估计 d(d+1)/2 个参数。样本少于特征（n ≤ d）时样本协方差奇异，`invert_matrix` 会抛 "Matrix is singular or near-singular"；样本不多时也会病态，S⁻¹ 放大噪声方向。
- **对策**：
  - 正则化/收缩：`S + εI` 或 Ledoit-Wolf 收缩估计；
  - 先 PCA 降维，只在主成分上算马氏距离；
  - 离群点会"拉大"协方差、把自己藏起来（masking）→ 用鲁棒估计（如最小协方差行列式 MCD）；
  - 经验上每个特征需要足够多的样本（课程 outputs 中建议样本数至少为特征数的 10 倍）。
- **阈值**：若数据近似多元高斯，`d_M²` 服从自由度为 d 的卡方分布，可按 χ²_d 的 97.5% / 99% 分位数设阈值；否则用验证集上的经验分位数。
- **加分点**：马氏距离 = 白化后的 L2，说明它就是"先标准化 + 去相关"，S = I 时退化为欧氏距离。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 01 线性代数直觉](../../01-linear-algebra-intuition/docs/zh.md)：点积、模长、余弦相似度的几何意义。
- [阶段 01 · 02 向量、矩阵和运算](../../02-vectors-matrices-operations/docs/zh.md)：矩阵乘法、矩阵求逆（马氏距离要用）。
- [阶段 01 · 06 概率和分布](../../06-probability-and-distributions/docs/zh.md)：协方差、概率分布、CDF。
- [阶段 01 · 09 信息论](../../09-information-theory/docs/zh.md)：KL 散度、交叉熵的完整推导。

### 本节被哪些后续内容用到
- [阶段 01 · 10 降维](../../10-dimensionality-reduction/docs/zh.md)：PCA 白化与马氏距离是同一件事的两面。
- [阶段 01 · 18 凸优化](../../18-convex-optimization/docs/zh.md)：L1/L2 正则的约束视角与近端方法。
- [阶段 02 · 06 KNN 与距离](../../../02-ml-fundamentals/06-knn-and-distances/docs/zh.md)：距离选择直接决定 KNN 的预测。
- [阶段 02 · 07 无监督学习](../../../02-ml-fundamentals/07-unsupervised-learning/docs/zh.md)：聚类依赖距离定义。
- [阶段 02 · 16 异常检测](../../../02-ml-fundamentals/16-anomaly-detection/docs/zh.md)：马氏距离做多元异常检测。
- [阶段 02 · 18 特征选择](../../../02-ml-fundamentals/18-feature-selection/docs/zh.md)：L1 正则的稀疏性用于选特征。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：MSE/MAE/Huber/交叉熵 = 不同的距离。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：L1/L2、weight decay 在神经网络中的用法。
- [阶段 04 · 20 图像检索与度量学习](../../../04-computer-vision/20-image-retrieval-metric/docs/zh.md)：triplet / contrastive loss 学习距离。
- [阶段 08 · 03 GAN](../../../08-generative-ai/03-gans-generator-discriminator/docs/zh.md)：GAN 训练不稳定与 Wasserstein 的动机。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md) 与 [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md)：余弦/点积检索、向量数据库与 ANN。

### 延伸关键词
`MinHash / LSH` · `HNSW` · `IVF-PQ` · `Jaro-Winkler` · `DTW 动态时间规整` · `Jensen-Shannon 散度` · `Ledoit-Wolf 收缩` · `软阈值 / 近端梯度` · `维度灾难与距离集中` · `度量学习`
