# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 15 节 Speculative Decoding 与 EAGLE-3 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`、`typing`），无需 GPU、无需模型

---

## 1. 这份代码在考察什么

这份代码不加载任何真实模型，而是用两个固定的离散分布——verifier 分布 `q`（8 个 token）和若干个"草稿"分布 `p`——把 speculative decoding 的数学和记账逻辑完整跑一遍：

1. **Leviathan 拒绝规则**：以 `min(1, q(d)/p(d))` 接受草稿，拒绝时从残差 `(q − p)₊` 采样。
2. **N 步串联的一个"投机步"**：草稿 N 个 → 一次验证 → 第一次拒绝即停 → 全部接受时加一个 bonus token。
3. **分布等价性的经验验证**：5 万次模拟，用卡方统计量比较"投机解码的输出"与"直接从 q 采样"。
4. **接受率 α 与草稿质量的关系**：用 KL 散度衡量 p 偏离 q 的程度，蒙特卡洛估计 α。
5. **加速比模型**：期望产出 `(1 − α^{N+1}) / (1 − α)` 与每 token 墙钟 `(1 + N·c) / E`。
6. **KV cache 的逻辑长度记账**（简化版）。

> 一句话：**用 260 行标准库代码证明"投机解码只改变速度、不改变分布"，并量化"α 是最大的杠杆"**。同时要注意：代码中的 KV 回滚并没有真正发生，卡方检验的统计口径也有问题（见 3.4、3.6）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sample` | 函数 | 按概率向量做逆 CDF 采样 | 采样原语 |
| `residual` | 函数 | `(q − p)₊` 归一化；p == q 时退回 q | 残差分布 |
| `kl` | 函数 | `KL(q‖p)` | 草稿质量度量 |
| `KVBuffer` | dataclass | 记录 verifier KV cache 的逻辑长度 | KV rollback（简化） |
| `spec_step` | 函数 | 一次完整投机步：草稿 N、逐个验证、残差纠正、bonus | 核心循环 |
| `direct_sample` | 函数 | 直接从 q 采样 n 次（未被 `main` 使用） | 对照组 |
| `distribution_check` | 函数 | N = 1 时统计首个产出 token 的分布，与直接采样对比 | Leviathan 定理验证 |
| `chi_square` | 函数 | 把一份计数当期望值计算卡方统计量 | 统计检验 |
| `measure_alpha` | 函数 | 蒙特卡洛估计单 token 接受率 | α |
| `expected_tokens_per_verify` | 函数 | `(1 − α^{N+1}) / (1 − α)` | 期望产出 |
| `wall_time_per_token` | 函数 | `(1 + N·c) / E` | 墙钟模型 |
| `perturb` | 函数 | 给 q 加高斯噪声并归一化，制造不同质量的草稿 | 模拟 vanilla / EAGLE-1 / EAGLE-3 |
| `main` | 函数 | 依次打印 5 个步骤 | 入口 |

数据流：`main` 定义 `q` → `perturb` 生成三个 `p` → Step 1 `distribution_check` + `chi_square` → Step 2 `kl` + `measure_alpha` → Step 3/4 理论表 → Step 5 循环调用 `spec_step` 1000 次并累计 token 与 KV 长度。

---

## 3. 逐段精讲

### 3.1 `sample` 与 `residual`：两个基础原语

```python
def sample(probs: List[float], rng: random.Random) -> int:
    u = rng.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if u < acc:
            return i
    return len(probs) - 1
```

- **逆 CDF 采样**：在 [0, 1) 上取均匀随机数 u，沿累计概率走，第一个超过 u 的位置就是样本。
- 最后的 `return len(probs) - 1` 是兜底：浮点累加可能让总和略小于 1（如 0.9999999），u 恰好落在缝隙里时返回最后一个 token。

```python
def residual(q: List[float], p: List[float]) -> List[float]:
    raw = [max(0.0, qi - pi) for qi, pi in zip(q, p)]
    s = sum(raw)
    if s == 0.0:
        return list(q)
    return [r / s for r in raw]
```

- `(q − p)₊`：只保留 q 比 p 大的部分——这些 token 是"草稿给得太少"的地方，拒绝后要在这里补足。
- `s` 恰好等于 `1 − α`（因为 `Σ(q − p)₊ = 1 − Σmin(p, q)`）。
- `s == 0` 只在 `p == q` 时出现，此时 α = 1、永远不会拒绝，返回 `list(q)` 只是防御性写法。
- 例：`q = [0.5, 0.3, 0.2]`、`p = [0.2, 0.5, 0.3]` → `raw = [0.3, 0, 0]` → 残差 `[1, 0, 0]`。

### 3.2 `kl`：衡量草稿偏离

```python
def kl(q, p):
    total = 0.0
    for qi, pi in zip(q, p):
        if qi > 0 and pi > 0:
            total += qi * math.log(qi / pi)
    return total
```

- 计算 `KL(q‖p) = Σ q log(q/p)`，只用于 Step 2 的展示。跳过 0 概率项是数值上的保护（严格定义下 `q > 0, p = 0` 时 KL 为无穷大，这里被静默忽略；`perturb` 已把 p 截断到 ≥ 1e-6，所以不会触发）。
- 与 α 的关系是单调的趋势而非精确公式：α 精确等于 `1 − TV(p, q)`，KL 越小 TV 一般越小。

### 3.3 `spec_step`：一次投机步

```python
    prefix_len = kv.length
    drafts: List[int] = []
    p_probs: List[float] = []
    for _ in range(N):
        d = sample(p, rng)
        drafts.append(d)
        p_probs.append(p[d])
```

- **草稿阶段**：从 p 连续采 N 个 token，并记下每个 token 在 p 下的概率（验证时要用）。真实系统中这是草稿模型的 N 次小前向。
- 简化：q、p 与位置/上下文无关（docstring 写明"context-free distributions shared across positions"），所以第 i 个草稿的 `p_i` 就是同一个 p。

```python
    emitted: List[int] = []
    for i, d in enumerate(drafts):
        u = rng.random()
        q_prob = q[d]
        p_prob = p_probs[i]
        ratio = q_prob / p_prob if p_prob > 0 else float("inf")
        if u < min(1.0, ratio):
            emitted.append(d)
            kv.extend(1)
        else:
            correction = sample(residual(q, p), rng)
            emitted.append(correction)
            kv.truncate_to(prefix_len + len(emitted))
            return emitted, 1

    bonus = sample(q, rng)
    emitted.append(bonus)
    kv.extend(1)
    return emitted, 1
```

- **验证阶段**：真实系统里 verifier 对 `prefix + d₁…d_N` 做**一次**前向得到 `q₁…q_{N+1}`；这里 q 不变，直接查表。
- 接受条件 `u < min(1, q/p)`：当 `q(d) ≥ p(d)` 时比值 ≥ 1，必然接受；否则按比值概率接受。`p_prob > 0` 的保护对应讲义 Step 1 中 `if p_prob <= 0: return True`（草稿是从 p 采出来的，实际不会出现 p = 0）。
- **第一次拒绝就停**：后面的草稿是以被拒绝的 token 为条件生成的，已经无效。纠正 token 从残差采样。
- **全部接受**：再从 `q_{N+1}` 采一个 bonus token，产出 N + 1 个。
- 返回值第二项恒为 1——"一次 verifier 前向"正是投机解码的意义所在。
- ⚠️ **KV 记账并没有回滚**：接受时 `extend(1)`，拒绝时 `truncate_to(prefix_len + len(emitted))`。在位置 j 拒绝时，调用前长度为 `prefix_len + j`，调用后为 `prefix_len + j + 1`——**变长了**。实测连续 5 步长度为 `0→1、1→6、6→7、7→9、9→10`，始终等于累计产出 token 数。原因是代码没有模拟"verifier 一次写入 N 个草稿位置"的物理写入，所以截断无事可做。测验 Q9 给出了 physical / logical 分开记账的版本。

### 3.4 `distribution_check` 与 `chi_square`：经验验证 Leviathan 定理

```python
    for _ in range(n_steps):
        kv = KVBuffer()
        tokens, _ = spec_step(q, p, N=1, kv=kv, rng=rng)
        spec_counts[tokens[0]] += 1
        direct_counts[sample(q, rng)] += 1
```

- 每次用 N = 1 跑一个投机步，只统计**第一个**产出 token（接受时是草稿，拒绝时是残差纠正）；同时直接从 q 采一个样本作对照。docstring 说明 bonus token 是第二次独立抽样，不应混入。
- 只验证了 N = 1 的首 token；N > 1 的后续位置与 bonus token 没有经验验证。

```python
def chi_square(observed, expected):
    ...
    for o, e in zip(observed, expected):
        e_norm = e * total_obs / total_exp
        if e_norm > 0:
            result += (o - e_norm) ** 2 / e_norm
```

- 把 `direct_counts`（另一份有限样本）按总数缩放后当作"期望值"。
- ⚠️ **统计口径不对**：两份样本都有抽样噪声，统计量近似是 `2·χ²(7)`，却用 `χ²(7)` 的 95% 临界值 14.07 判断。我们重复 1000 次（每次 3000 样本）测得误报率约 42%；改为直接对 q 的拟合优度检验 `Σ(o − n·q)² / (n·q)` 后误报率约 4.5%。本次运行碰巧 χ² = 11.60 判为 PASS；同一份 `spec counts` 用拟合优度检验得到 3.42。

### 3.5 `measure_alpha`、期望产出与墙钟

```python
def measure_alpha(q, p, n_samples, rng):
    hits = 0
    for _ in range(n_samples):
        d = sample(p, rng)
        u = rng.random()
        if p[d] > 0 and u < min(1.0, q[d] / p[d]):
            hits += 1
    return hits / n_samples
```

- 蒙特卡洛估计 α。精确值可以直接算：`α = Σ min(p, q)`。三档草稿的精确 α 分别是 0.798（vanilla）、0.932（eagle-1）、0.980（eagle-3），与输出的 0.797 / 0.934 / 0.982 吻合。
- 三次调用都用 `random.Random(7)`，即"共同随机数"：比较不同草稿时噪声相关，差异更可靠。

```python
def expected_tokens_per_verify(alpha, N):
    if alpha >= 1.0:
        return N + 1
    if alpha <= 0.0:
        return 1.0
    return (1.0 - alpha ** (N + 1)) / (1.0 - alpha)

def wall_time_per_token(alpha, N, c):
    return (1.0 + N * c) / expected_tokens_per_verify(alpha, N)
```

- **期望产出的推导**：第 i 个草稿（1 起）被接受的概率是 `α^i`（前面都要接受），加上必定产出的 1 个（correction 或 bonus），`E = 1 + α + α² + … + α^N = (1 − α^{N+1}) / (1 − α)`。这假设各位置接受事件独立且 α 相同。
- 边界：α = 1 时公式分母为 0，单独返回 N + 1；α = 0 时只产出 1 个纠正 token。
- **墙钟**：一次 verifier 成本记为 1，草稿每 token 成本 c，每轮 `1 + N·c`，除以期望产出得到每 token 时间；基线（不投机）为 1.0，加速比为其倒数。
- 这个模型假设 verifier 验证 N+1 个 token 的成本与验证 1 个相同（memory-bound 近似），所以会高估大 N 的收益（测验 Q11）。

### 3.6 `perturb` 与 `main`

```python
def perturb(q, amount, rng):
    p = [max(1e-6, qi + amount * rng.gauss(0, 1)) for qi in q]
    s = sum(p)
    return [pi / s for pi in p]
```

- 在 q 上加均值 0、标准差 `amount` 的高斯噪声，截断到 1e-6 后重新归一化。`amount` 越大，草稿越差。
- `main` 中三档分别用独立种子 `Random(1)/(2)/(3)` 生成，保证每次运行得到相同的 p。

```python
    q = [0.30, 0.22, 0.15, 0.10, 0.08, 0.07, 0.05, 0.03]
    p_eagle3 = perturb(q, amount=0.005, rng=random.Random(1))
    p_eagle1 = perturb(q, amount=0.02, rng=random.Random(2))
    p_vanilla = perturb(q, amount=0.08, rng=random.Random(3))
```

- ⚠️ 名字只是标签：这三档的 α（0.98 / 0.93 / 0.80）都高于讲义表格中同名方法的 α 范围（EAGLE-3 0.88–0.92、EAGLE-1 0.70–0.80、vanilla 0.55–0.70）。
- Step 5：用 `p_eagle3`、N = 5 跑 1000 轮，累计产出和 verifier 前向次数；最后打印的对照值写死为 `expected_tokens_per_verify(0.95, 5) = 5.30`，而 `p_eagle3` 的真实 α ≈ 0.98，对应期望 5.71——与实测 5.73 才是同一口径。
- 结尾的"takeaway"说 "alpha~0.9 at N=5 delivers ~4-5 tokens"，指的是 Step 3 表中 α = 0.9 那一行（4.69），而不是 Step 5 的模拟。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| q、p 与位置无关的固定分布 | 不需要模型就能验证数学 | 无法体现"草稿越往后越不准"（exposure bias）；真实系统中 `q_i`、`p_i` 随上下文变化 |
| 用 `perturb` 加噪声模拟不同草稿 | 一个参数控制草稿质量 | α 与讲义表格中的方法不对应，只是示意 |
| `KVBuffer` 只记一个整数 | 演示"逻辑长度"的概念 | 没有物理写入，`truncate_to` 从不缩短；生产用 scratch buffer 提交或每序列逻辑长度截断 |
| N = 1 首 token 的卡方检验 | 简单直接 | 两样本当单样本检验，误报率约 42%；应对 q 做拟合优度检验，并覆盖多位置与 bonus |
| 蒙特卡洛测 α | 与"实测遥测"的做法一致 | 精确值 `Σmin(p, q)` 一行即可算出 |
| 墙钟模型 `(1 + N·c) / E` | 讲义的标准公式 | 忽略 verifier 成本随 N 增长、batch 效应、拒绝浪费；最优 N 偏大 |
| 标准库实现、单序列 | 便于阅读 | 没有 batched 验证、树形草稿（讲义练习 3、4） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许在注解中使用 `tuple[List[int], int]` 等写法 |
| `typing.List` 与内置泛型 | `List[float]`、`tuple[List[int], int]` | 两种写法混用；Python 3.9+ 可直接写 `list[float]` |
| `random.Random(seed)` | `rng = random.Random(42)`、`random.Random(7)` | 独立的随机数生成器对象，互不干扰，可复现 |
| `rng.random()` / `rng.gauss(0, 1)` | `sample`、`perturb` 中 | [0,1) 均匀分布 / 标准正态分布 |
| `enumerate` | `for i, p in enumerate(probs):` | 同时得到下标和元素 |
| `zip` | `for qi, pi in zip(q, p):` | 并行遍历两个列表 |
| 列表推导式 | `[max(0.0, qi - pi) for qi, pi in zip(q, p)]`、`[pi / s for pi in p]` | 一行构造新列表 |
| `list(q)` 复制 | `return list(q)` | 返回新列表，避免调用方修改原分布 |
| `float("inf")` | `ratio = ... else float("inf")` | 正无穷，`min(1.0, inf) = 1.0` |
| 条件表达式 | `q_prob / p_prob if p_prob > 0 else float("inf")` | 一行 if/else，同时避免除零 |
| `**` 幂运算 | `alpha ** (N + 1)` | 浮点幂 |
| `math.log` | `qi * math.log(qi / pi)` | 自然对数 |
| `@dataclass` 带方法 | `class KVBuffer: length: int = 0; def extend(...)` | dataclass 也可以定义普通方法 |
| 早返回 | `return emitted, 1` 在循环内 | 第一次拒绝立即结束函数 |
| 返回元组并解包 | `tokens, _ = spec_step(...)`、`spec_c, direct_c = distribution_check(...)` | `_` 表示忽略的返回值 |
| `[0] * n` | `spec_counts = [0] * len(q)` | 创建长度为 n 的全零列表（元素是不可变 int，安全） |
| 嵌套 f-string | `f"{f'N={N}':>8}"` | 内层生成 `N=5`，外层右对齐到 8 宽 |
| f-string 格式符 | `{qi:.3f}`、`{name:<12}`、`{a:>8.3f}`、`{chi:.2f}` | 小数位、左/右对齐 |
| `str.join` + 生成器 | `" ".join(f"{qi:.3f}" for qi in q)`、`"".join(... for N in Ns)` | 拼接表格行 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行 `main()`，便于在测验中复用函数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 0.2 秒），输出节选：

```text
Step 1: Leviathan distribution-equivalence check (N=1, 50000 trials)
  spec   counts: [14948, 11111, 7439, 4990, 3963, 3481, 2543, 1525]
  direct counts: [14874, 10928, 7597, 5068, 4034, 3520, 2490, 1489]
  chi^2 = 11.60  (df=7; 95% crit ~14.07)
  verdict: PASS

Step 2: measured acceptance rate alpha per draft quality
  draft          KL(q||p)    alpha
  vanilla          0.1345    0.797
  eagle-1          0.0198    0.934
  eagle-3          0.0017    0.982

Step 3: expected tokens per verifier call (theory)
   alpha       N=1     N=3     N=5     N=7    N=10
    0.55      1.55    2.02    2.16    2.20    2.22
    0.70      1.70    2.53    2.94    3.14    3.27
    0.80      1.80    2.95    3.69    4.16    4.57
    0.90      1.90    3.44    4.69    5.70    6.86
    0.95      1.95    3.71    5.30    6.73    8.62

Step 4: wall time per token at c=0.04 (EAGLE-3-class draft cost)
   alpha       N=1     N=3     N=5     N=7    N=10
    0.55     0.671   0.555   0.555   0.581   0.631
    0.70     0.612   0.442   0.408   0.407   0.428
    0.80     0.578   0.379   0.325   0.308   0.306
    0.90     0.547   0.326   0.256   0.225   0.204
    0.95     0.533   0.302   0.226   0.190   0.162

Step 5: end-to-end simulated run, N=5, draft=eagle-3, 1000 rounds
  total tokens emitted : 5732
  verifier forwards    : 1000
  mean tokens / forward: 5.73
  kv logical length    : 5732   (tracks accepted prefix)
  expected at alpha=0.95, N=5: 5.30
```

逐项解读：

- **Step 1**：spec 计数与 `q × 50000 = [15000, 11000, 7500, 5000, 4000, 3500, 2500, 1500]` 非常接近，对 q 的拟合优度 χ² = 3.42，Leviathan 定理在经验上成立。代码给出的 11.60 是两样本口径，偏大（见 3.4）。注意这里用的是 α ≈ 0.93 的 `p_eagle1`，约 7% 的 token 来自残差纠正，正是残差把分布"补"成了 q。
- **Step 2**：KL 每降一个数量级，α 明显上升；精确 α（`Σmin`）为 0.798 / 0.932 / 0.980，与蒙特卡洛结果一致。
- **Step 3**：每行随 N 增长逐渐饱和，上限是 `1/(1−α)`（α = 0.55 时约 2.22，α = 0.9 时 10）。α = 0.9、N = 5 为 4.69——讲义正文写的 "4.1" 与这张表不符；α = 0.55 一行也说明草稿差时加长 N 几乎没用。
- **Step 4**：每格是每 token 时间（1.0 为不投机的基线），倒数是加速比：α = 0.9、N = 10 时 0.204 → 约 4.9×；α = 0.55 时在 N = 3–5 达到最优（约 1.8×），再加长反而变慢——这就是"最优 N 随 α 增大而增大"。
- **Step 5**：1000 次 verifier 前向产出 5732 个 token，平均 5.73，接近 N + 1 = 6 的上限，因为 α ≈ 0.98。`kv logical length` 恰好等于产出总数，印证了 3.3 中"它只是一个产出计数器"的结论。

---

## 7. 动手改一改

1. **修正对照值与检验**：Step 5 用 `sum(min(a, b) for a, b in zip(p_eagle3, q))` 算出真实 α 再求期望；Step 1 改用对 q 的拟合优度检验，并重复 200 次统计误报率，确认约为 5%。
2. **讲义练习 2**：α = 0.9、c = 0.04，N 从 1 扫到 20，打印期望产出、每 token 时间和加速比，找出最优 N（按此公式为 14–15），再给 verifier 成本加一项 `1 + k·N`（例如 k = 0.02），观察最优 N 如何变小。
3. **真正的 KV 回滚**：按测验 Q9 把 `KVBuffer` 拆成 `physical` 与 `logical`，验证一次投机步中 `physical` 先增加 N、拒绝后回落到 `logical`。
4. **讲义练习 4 · batched 回滚**：让 `spec_step` 一次处理两条序列（各自的 KVBuffer），构造 A 全部接受、B 在位置 2 拒绝的情形，打印两条序列的逻辑长度。
5. **位置相关的分布**：让 `p_i` 随位置 i 逐渐变差（例如 `perturb(q, amount=0.005 * (i + 1))`），模拟 exposure bias，观察后面位置的接受率下降，体会 EAGLE-3 TTT 要解决的问题。
6. **讲义练习 3 · 树形草稿**：每步生成形状 `[2, 2, 2]` 的树（8 条路径），对每条路径按 Leviathan 规则验证，取被接受最长的路径；与同等草稿计算量的单链比较平均产出。（提示：多分支时为保持分布严格等于 q，需要使用多候选版本的拒绝采样，而不是简单取"最长路径"——这是练习中值得思考的陷阱。）

---

## 8. 常见坑

- **拒绝后从 q 或 p 重新采样**：都会改变输出分布，必须从残差 `(q − p)₊` 采样。
- **拒绝后继续检查后面的草稿**：后续草稿以被拒绝的 token 为条件，已失效，必须立即停止。
- **以为接受率低会降低质量**：只影响速度。
- **把两份样本当"观测 vs 理论"做卡方**：统计量膨胀约一倍，误报率从 5% 升到约 40%。
- **混淆"产出计数"与"KV 长度"**：correction / bonus token 的 KV 要到下一次前向才写入；本代码的 `KVBuffer` 只是产出计数，没有体现回滚。
- **忽略 α = 1 的除零**：`expected_tokens_per_verify` 专门处理了 `alpha >= 1.0`，自己实现时容易漏掉。
- **照搬公式的最优 N**：公式假设验证成本与 N 无关，大 batch 下会严重高估；生产中 N 常取 3–7，并按 batch、温度动态调整。
- **拿名字当事实**：代码中的 `p_eagle3` 只是"噪声很小的 p"，其 α ≈ 0.98，不代表真实 EAGLE-3 的接受率。
