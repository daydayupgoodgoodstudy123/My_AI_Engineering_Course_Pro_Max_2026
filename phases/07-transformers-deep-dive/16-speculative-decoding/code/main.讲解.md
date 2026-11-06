# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 16 节 Speculative Decoding — 草稿、验证、重复 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.1 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

投机解码的工程实现很复杂（两个模型、KV 回滚、树注意力），但它的**数学内核**只有十几行。这份代码把内核单独拎出来，用一个 8 个 token 的玩具分布验证三件事：

1. **接受 / 拒绝 + 残差分布**：以 `min(1, q/p)` 接受草稿，拒绝时从 `(q − p)₊` 归一化后重采样——这是保持 verifier 分布的关键。
2. **分布等价**：投机采样得到的 token 频数与直接从 q 采样的频数在统计上无差异（Leviathan 定理的实证）。
3. **加速的理论上限**：接受率 α 与 draft 质量的关系，以及每次 verifier 调用期望能产出多少 token。

> 一句话：**先在 8 个 token 的分布上把"无损加速"的数学跑通，再去碰真实模型。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sample(probs, rng)` | 函数 | 按概率分布抽一个下标（逆 CDF 法） | 采样 |
| `residual(q, p)` | 函数 | `normalize(max(0, q − p))`，全零时兜底返回 q | 残差分布 |
| `kl(q, p)` | 函数 | `KL(q‖p) = Σ q·log(q/p)` | draft 与 verifier 的差距 |
| `spec_step_one_token(q, p, rng)` | 函数 | 起草 1 个 token 并验证 | 投机采样核心 |
| `spec_step_n(q, p, N, rng)` | 函数 | 起草 N 个 token 的简化版（`main` 中未使用） | 多 token 投机步 |
| `run_distribution_check(...)` | 函数 | 同时做投机采样与直接采样，统计频数 | 分布等价实验 |
| `chi_square(observed, expected)` | 函数 | 卡方统计量 | 统计检验 |
| `acceptance_rate(q, p, n, rng)` | 函数 | 蒙特卡洛估计接受率 α | α |
| `perturb(q, amount, rng)` | 函数 | 给 q 加高斯噪声得到"draft 分布" | 模拟不同质量的 draft |
| `expected_tokens_per_verify(alpha, N)` | 函数 | `(1 − α^(N+1)) / (1 − α)` | 理论加速 |
| `main()` | 函数 | 四段输出：q、分布等价、α vs KL、理论表 | — |

数据流：`main` 定义 verifier 分布 `q` → `perturb` 造出 draft 分布 `p` → `spec_step_one_token` 反复调用 `sample` 与 `residual` → 统计频数 / 接受率 → 打印。

---

## 3. 逐段精讲

### 3.1 `sample`：逆 CDF 采样

```python
def sample(probs, rng):
    u = rng.random()
    c = 0.0
    for i, p in enumerate(probs):
        c += p
        if u < c:
            return i
    return len(probs) - 1
```

- 在 `[0, 1)` 上抽一个均匀数 u，沿累积分布往前走，第一个让累积和超过 u 的下标就是结果。每个下标被选中的概率正好等于它的区间宽度 `probs[i]`。
- 最后的 `return len(probs) - 1` 是**浮点兜底**：概率和由于舍入可能是 0.9999999，u 恰好落在缝隙里时循环会走完而不返回。
- 复杂度 O(V)。真实框架用 `torch.multinomial` 或 Gumbel-max 技巧在 GPU 上并行完成。

### 3.2 `residual`：拒绝后的"补偿分布"

```python
def residual(q, p):
    raw = [max(0.0, qi - pi) for qi, pi in zip(q, p)]
    s = sum(raw)
    if s == 0.0:
        return list(q)
    return [r / s for r in raw]
```

- 只保留 verifier 比 draft **更偏好**的 token（`q > p` 的部分），负数截断为 0，再归一化。
- 直觉：draft 对某些 token "采多了"（p > q），接受规则按 `q/p` 的比例把多出来的部分拒掉；这些被拒的概率质量必须补给 draft "采少了"的 token（q > p），补多少正好是 `q − p`。
- `s == 0` 只在 `q == p` 时出现（两者和都为 1），此时理论上永远不会走到拒绝分支；保留这个分支是为了防止浮点误差导致除以 0。
- `list(q)` 返回一份拷贝，避免调用方修改到原始的 q。

### 3.3 `spec_step_one_token`：投机采样的核心

```python
def spec_step_one_token(q, p, rng):
    """Draft 1 token from p, verify with q. Returns (accepted_token, was_accepted)."""
    d = sample(p, rng)
    p_prob = p[d]
    q_prob = q[d]
    u = rng.random()
    if u < min(1.0, q_prob / p_prob if p_prob > 0 else float("inf")):
        return d, True
    return sample(residual(q, p), rng), False
```

- 三步：① 用 draft 分布 p 抽一个草稿 d；② 以 `min(1, q(d)/p(d))` 的概率接受；③ 否则从残差分布重采样。
- `q_prob / p_prob if p_prob > 0 else float("inf")`：条件表达式防止除以 0。实际上 `p(d) = 0` 的 token 不可能被 p 抽到，这只是防御性写法。
- **为什么输出分布恰好是 q**：接受 x 的概率是 `p(x)·min(1, q(x)/p(x)) = min(p(x), q(x))`；拒绝的总概率是 `Σ(q − p)₊`，拒绝后抽到 x 的概率是 `(q(x) − p(x))₊ / Σ(q − p)₊`；两者相加得 `min(p, q) + (q − p)₊ = q(x)`。完整推导见测验 Q9。
- 接受率的期望值：`α = Σ min(p(x), q(x))`，即 1 减去 p 与 q 的总变差距离。
- 返回 `(token, was_accepted)` 二元组：分布检验只需要 token，接受率统计只需要布尔值，一个函数两处复用。

### 3.4 `spec_step_n`：多 token 版本（简化且未被调用）

```python
def spec_step_n(q, p, N, rng):
    """Draft N tokens (same context), then verify in one pass.
    Returns (final_token, n_accepted). Simplified: q and p are fixed per call.
    """
    accepted = 0
    for _ in range(N):
        # ...（与单 token 版本相同的接受判断）
        if u < min(1.0, q_prob / p_prob if p_prob > 0 else float("inf")):
            accepted += 1
        else:
            return sample(residual(q, p), rng), accepted
    bonus = sample(q, rng)
    return bonus, accepted + 1
```

- 结构正是讲义算法：从左到右依次验证，第一次拒绝就从残差重采样并结束；全部接受则从 q 采一个**奖励 token**。
- ⚠️ docstring 已经说明简化：所有位置用同一组 q、p。真实模型中每个位置的分布依赖前缀（讲义 Step 3 的 `spec_step` 用 `q_model(prefix + drafts[:i])` 逐位置计算）。
- ⚠️ 返回值语义不一致：拒绝分支返回的 `accepted` 不含刚重采样的那个 token，全接受分支的 `accepted + 1` 却含奖励 token。两条分支实际产出的 token 数都是"接受数 + 1"。另外它只返回最后一个 token，丢掉了被接受的草稿。
- ⚠️ `main()` 中没有调用这个函数。测验 Q11 给出了返回 token 列表的修正版，并用模拟验证平均长度与 `(1 − α^(N+1))/(1 − α)` 吻合。

### 3.5 分布等价检验

```python
def run_distribution_check(q, p, n_samples, rng):
    spec_counts = [0] * len(q)
    direct_counts = [0] * len(q)
    for _ in range(n_samples):
        d, _ = spec_step_one_token(q, p, rng)
        spec_counts[d] += 1
        direct_counts[sample(q, rng)] += 1
    return spec_counts, direct_counts


def chi_square(observed, expected):
    total_obs = sum(observed)
    total_exp = sum(expected)
    if total_obs == 0 or total_exp == 0:
        return 0.0
    result = 0.0
    for o, e in zip(observed, expected):
        e_norm = e * total_obs / total_exp
        if e_norm > 0:
            result += (o - e_norm) ** 2 / e_norm
    return result
```

- 每轮各做一次投机采样和一次直接采样，分别计数，`[0] * len(q)` 初始化计数数组。
- `chi_square` 先把期望频数缩放到与观测总数相同（`e_norm`），再累加 `(O − E)² / E`。值越大说明两个分布差得越远。
- `main` 中的判定：`chi < 30` 即 PASS。
- ⚠️ 两处统计上的简化：①把另一组**随机样本**（direct counts）当成期望值，它本身也有抽样噪声，统计量的方差会变大；既然 q 已知，更标准的做法是直接用 `n·q` 做拟合优度检验。②自由度 7、显著性 0.05 的临界值约为 14.07，阈值 30 对应 p ≈ 1e-4，过于宽松。讲义练习 1 要求的是 p > 0.05。按理论 q 重算，本次 spec 频数的卡方约为 2.45（见测验 Q10），结论不变，但判定更严谨。

### 3.6 接受率与 draft 质量

```python
def acceptance_rate(q, p, n_samples, rng):
    hits = 0
    for _ in range(n_samples):
        _, was = spec_step_one_token(q, p, rng)
        if was:
            hits += 1
    return hits / n_samples


def perturb(q, amount, rng):
    p = [max(1e-6, qi + amount * rng.gauss(0, 1)) for qi in q]
    s = sum(p)
    return [pi / s for pi in p]
```

- `perturb` 给每个概率加上 `amount` 倍的高斯噪声，用 `max(1e-6, ...)` 防止出现负数或 0，再归一化——模拟一个"大致像 verifier 但不完全一样"的 draft。`amount` 越大，draft 越差。
- `acceptance_rate` 用蒙特卡洛估计 α，理论值是 `Σ min(p, q)`。
- `main` 里每个噪声档位用 `random.Random(noise * 1000)` 单独造 draft，保证每档的 p 固定可复现；而接受率估计共用外部的 `rng`。
- ⚠️ **KL 的读法**：噪声稍大时，部分 token 被截到约 1e-6，`KL(q‖p)` 中这些项 `q·log(q/1e-6)` 会非常大，所以表里 KL 从 0.002 一下跳到 0.2、0.85……而 α 只是从 0.98 缓慢降到 0.92、0.88。决定接受率的精确量是总变差距离（`α = 1 − TV`），KL 只是一个单调趋势相近的代理指标。

### 3.7 理论表：每次验证产出多少 token

```python
def expected_tokens_per_verify(alpha, N):
    if alpha >= 1.0:
        return N + 1
    if alpha == 0:
        return 1
    return (1 - alpha ** (N + 1)) / (1 - alpha)
```

- 推导：第 k 个草稿被接受的概率为 `α^k`（假设各位置独立、接受率相同），期望产出 = `1 + α + α² + … + α^N`（那个"1"是拒绝时的纠正 token 或全接受时的奖励 token），等比数列求和得 `(1 − α^(N+1))/(1 − α)`。
- `alpha >= 1.0` 和 `alpha == 0` 两个分支处理分母为 0 / 退化情况：全接受时每轮固定产出 N+1；完全不接受时每轮只产出 1 个纠正 token。
- 当 `α^(N+1)` 远小于 1 时，结果趋近 `1/(1 − α)`。这是**上限**：α=0.5 时无论 N 多大都不超过 2。
- ⚠️ 这里只数了 verifier 调用次数，没算 draft 的成本，所以表中 N 越大数字越大。真实加速比要除以 `(N·c + 1)`（c 为 draft/verifier 单步成本比），会出现最优 N（测验 Q12）。

### 3.8 `main` 的组织

```python
def main():
    rng = random.Random(7)
    V = 8
    q = [0.35, 0.20, 0.15, 0.10, 0.08, 0.06, 0.04, 0.02]
    p_good = perturb(q, amount=0.02, rng=rng)
    p_bad = perturb(q, amount=0.25, rng=rng)
    # ...
```

- verifier 分布 q 是手写的、单调递减的 8 维分布，和为 1，便于肉眼核对频数。
- `random.Random(7)` 固定种子，整份输出可复现。
- ⚠️ `p_bad` 定义了却没有使用（后面的扫描每档单独造 p）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用固定的手写分布代替模型 | 可以解析验证，接受率有闭式解 | 真实分布随上下文变化，需要逐位置计算 q、p |
| 单 token 投机步做主实验 | 分布等价在单 token 上最容易检验 | 多 token 时还要处理丢弃后续草稿、KV 回滚 |
| `perturb` 加噪声模拟 draft | 一个参数控制 draft 质量 | 真实 draft 的误差有结构（在长尾、罕见 token 上偏差大） |
| 两样本卡方 + 阈值 30 | 代码短，不依赖 SciPy | 应对理论 q 做拟合优度检验，用正确临界值 |
| 用 KL 作为横轴 | 常用、直观 | 与 α 精确对应的是总变差距离 |
| 理论表不含 draft 成本 | 聚焦"每次验证产出多少" | 真实决策要算墙钟加速比，选最优 N |
| 每次重新 `residual(q, p)` | 代码直白 | 生产中 q、p 是 GPU 上的张量，残差在验证内核里批量计算 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `enumerate` | `for i, p in enumerate(probs)` | 同时拿到下标和元素 |
| 列表乘法初始化 | `[0] * len(q)` | 生成指定长度的全 0 列表（元素是不可变的 int，安全） |
| 列表推导 | `[max(0.0, qi - pi) for qi, pi in zip(q, p)]` | 逐元素计算并截断 |
| `zip` | `for o, e in zip(observed, expected)` | 并行遍历两个列表 |
| 条件表达式 | `q_prob / p_prob if p_prob > 0 else float("inf")` | 一行内的 if/else，防止除以 0 |
| `float("inf")` | 同上 | 正无穷，`min(1.0, inf) == 1.0` |
| 多返回值与 `_` | `return d, True`；`d, _ = spec_step_one_token(...)` | 元组打包 / 解包，`_` 丢弃不用的值 |
| 文档字符串 | `"""Draft 1 token from p, ..."""` | 写在函数第一行，`help()` 可以看到 |
| `random.Random(seed)` | `rng = random.Random(7)`、`rng.random()`、`rng.gauss(0, 1)` | 独立的可复现随机数生成器 |
| `math.log` | `qi * math.log(qi / pi)` | 自然对数 |
| 幂运算 | `alpha ** (N + 1)` | α 的 N+1 次方 |
| f-string 宽度、小数位 | `{kl(q, p):>10.4f}`、`{alpha:>5.2f}`、`{N:>2}` | 右对齐、指定小数位 |
| f-string 嵌套引号 | `f"  {'PASS' if chi < 30 else 'FAIL'}: ..."` | 花括号里可以写表达式，内层用另一种引号 |
| `str.join` + 生成器 | `" ".join(f"{qi:.3f}" for qi in q)` | 拼接格式化后的数字 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中执行一次，耗时约 0.1 秒）。

```text
=== verifier distribution ===
  q: 0.350 0.200 0.150 0.100 0.080 0.060 0.040 0.020
```

verifier 的目标分布。

```text
=== speculative vs direct sampling (distribution equivalence) ===
  spec   counts (50000 samples): [17515, 10063, 7536, 4931, 3991, 2961, 2018, 985]
  direct counts (50000 samples): [17526, 9940, 7610, 4891, 4037, 2993, 2046, 957]
  chi^2 = 4.64   (V-1 = 7 df; large means distributions differ)
  PASS: spec-decoded tokens match verifier distribution
```

- 两行频数几乎一样，且都接近 `50000 × q = [17500, 10000, 7500, 5000, 4000, 3000, 2000, 1000]`。
- 卡方 4.64，远低于自由度 7 时 0.05 水平的临界值 14.07（更不用说代码用的 30），说明投机采样与直接采样没有显著差异——Leviathan 定理成立。
- 注意这里用的 `p_good`（噪声 0.02）理论接受率约为 0.96，大多数 token 直接被接受；即便如此，少数被拒绝后从残差重采样的 token 也恰好把分布"补"成了 q。

```text
=== acceptance rate vs KL(q || p) ===
    KL(q||p)    acceptance α
      0.0022           0.980
      0.2074           0.915
      0.8502           0.878
      1.8635           0.798
      4.5766           0.485
      5.9049           0.478
```

- 趋势正确：draft 与 verifier 差距越大，α 越低。
- 与理论值 `Σ min(p, q)` 对比：0.980、0.915、0.878、0.807、0.487、0.470——实测值都在 5000 次抽样的误差范围内。
- KL 从 0.0022 一下跳到 0.2074，是因为噪声 0.02 时已经有 token 被截到约 1e-6，KL 对这种"draft 认为几乎不可能"的 token 极其敏感；而 α 只关心重叠部分，下降平缓。

```text
=== expected tokens per verifier call (theory) ===
      α   N= 1  N= 3  N= 5  N= 7  N=10
   0.30   1.30  1.42  1.43  1.43  1.43
   0.50   1.50  1.88  1.97  1.99  2.00
   0.70   1.70  2.53  2.94  3.14  3.27
   0.85   1.85  3.19  4.15  4.85  5.55
   0.95   1.95  3.71  5.30  6.73  8.62
```

- 每行随 N 增大而饱和，上限为 `1/(1 − α)`：α=0.3 时 N 从 5 加到 10 几乎没有收益（1.43），α=0.95 时 N=10 仍在快速增长（上限 20）。
- 结论：**α 低时加大 N 是浪费**，这正是 skill 文件"α < 0.6 时把 N 降到 3"的依据。
- 最后的 takeaway 指出 α=0.85、N=5 时每次 verifier 调用约产出 4.1 个 token，"减去 draft 开销"后才是真实加速。

---

## 7. 动手改一改

1. 在接受率表中加一列理论值 `sum(min(a, b) for a, b in zip(q, p))`，再加一列总变差距离，对比 KL 与 TV 哪个更能"预测"α。
2. 把 `chi_square` 改成对理论分布 `n·q` 做拟合优度检验，并把阈值换成 14.07（参考测验 Q10）；故意把 `residual` 改成直接返回 `q`，看检验能否抓到分布偏差。
3. 修正 `spec_step_n`：返回本轮产出的 token 列表，并用模拟验证平均长度等于 `expected_tokens_per_verify(α, N)`（参考测验 Q11）。
4. 加入草稿成本 c，打印墙钟加速比 `E / (N·c + 1)` 表，找出每个 α 的最优 N（讲义练习 2，参考测验 Q12）。
5. 实现 greedy 版本：verifier 取 argmax，草稿与 argmax 相同就接受，否则替换为 argmax；验证输出与"直接 greedy"逐 token 相同。
6. 进阶：写一个依赖上下文的玩具 `q_model(prefix)` / `p_model(prefix)`（例如让分布随上一个 token 平移），实现讲义 Step 3 的 `spec_step`，并模拟 KV cache 回滚（讲义练习 4）。

---

## 8. 常见坑

- **拒绝后从 q 而不是残差重采样**：被 draft 高估的 token 会被多采，分布偏离 q；这是最常见的实现错误。
- **忘记残差的 `max(0, ·)` 截断**：得到带负数的"分布"，采样结果毫无意义。
- **残差全零时除以 0**：q 与 p 几乎相等时浮点误差可能触发，需要兜底。
- **统计检验用错基准**：用另一组随机样本当期望值、阈值随手写，检验会失去区分力。
- **只看每次验证产出的 token 数**：忽略 draft 成本，会得出"N 越大越好"的错误结论。
- **draft 与 verifier 不共享 tokenizer**：token id 对不上，`q[d]` 与 `p[d]` 指的不是同一个 token，整个等价性保证失效（skill 文件的第一条提醒）。
