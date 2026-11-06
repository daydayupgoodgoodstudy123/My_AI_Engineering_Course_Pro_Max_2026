# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 05 节 生产环境中的 EAGLE-3 Speculative Decoding ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`、`statistics`），无需 GPU 或模型

---

## 1. 这份代码在考察什么

这是一个**投机解码（speculative decoding）的"账本 + 尾延迟"分析器**，不跑任何模型，只用公式和随机模拟回答讲义的核心问题："在我的 alpha 和并发下，投机解码到底划不划算？"

它做三件事：

1. `expected_speedup`：按讲义公式 `S = (1 + K·alpha) / (1 + epsilon_eff)` 计算期望加速比，其中 verify 开销随并发增大。
2. `breakeven_alpha`：令 S = 1 求出盈亏平衡 alpha。
3. `simulate_tail` / `plain_tail`：模拟 1,000 个 token 的逐 token 延迟，比较开/关投机解码时的均值与 P99。

对应讲义概念：接受率 alpha、草稿长度 K、verify 开销 epsilon、盈亏平衡、P99 尾部陷阱。

> 一句话：**投机解码的收益完全取决于 alpha，而且必须同时看均值和 P99**。但阅读时要注意：同一文件中的公式、模拟、结论文字三者互相不一致（见 3.2、3.4 与第 6 节），这些不一致恰好是理解投机解码细节的好材料。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SpecPoint` | `@dataclass` | 一个配置点：alpha、K、基础 verify 开销、并发 | 投机解码参数 |
| `expected_speedup` | 函数 | 讲义公式算期望加速比 | `S(alpha, K)` |
| `breakeven_alpha` | 函数 | `epsilon_eff / K` | 盈亏平衡 alpha |
| `simulate_tail` | 函数 | 逐轮模拟草稿接受、计算每 token 延迟，返回 (均值, P99) | 尾延迟、被拒轮次 |
| `plain_tail` | 函数 | 不开投机解码的每 token 延迟（随并发增大） | 基线 |
| `print_table` | 函数 | 打印表格，并按 P99 是否变差打 `OK` / `TAIL` 标签 | 上线判断 |
| `main` | 函数 | K=5、epsilon=0.15，扫描并发 {32,128,256} × alpha {0.30,…,0.80} | 实验设计 |

数据流：`main` 构造 `SpecPoint` → `expected_speedup` / `breakeven_alpha`（解析）+ `simulate_tail` 与 `plain_tail`（随机模拟）→ `print_table` → 打印 KEY FINDING。

---

## 3. 逐段精讲

### 3.1 `SpecPoint` 与有效 verify 开销

```python
@dataclass
class SpecPoint:
    alpha: float      # acceptance rate (0..1)
    k: int            # draft length
    verify_overhead: float  # fraction extra cost per target forward
    concurrency: int  # batch size at decode
```

三个函数里都出现同一个式子：

```python
    effective_overhead = p.verify_overhead * (1 + p.concurrency / 256)
```

- 并发 32 → `0.15 × 1.125 = 0.169`；128 → `0.225`；256 → `0.30`。
- 它表达讲义的观点："verify 开销随 batch 增大"——batch 越大，GPU 越接近 compute-bound，验证 K 个额外位置越不"免费"。
- 线性系数 `1/256` 是随手取的教学参数。同一式子被复制了三遍，改一处容易漏另两处；更好的写法是给 `SpecPoint` 加一个 `@property`。

### 3.2 `expected_speedup`：讲义公式

```python
def expected_speedup(p: SpecPoint) -> float:
    effective_overhead = p.verify_overhead * (1 + p.concurrency / 256)
    tokens_per_target = 1 + p.k * p.alpha
    cost_per_target = 1 + effective_overhead
    return tokens_per_target / cost_per_target
```

- 分子：每次目标前向期望产出 `1 + K·alpha` 个 token（被接受的草稿 + 目标自己产出的 1 个）。
- 分母：每次目标前向相对普通 decode 的成本（含草稿与验证开销）。
- ⚠️ `1 + K·alpha` 只有当 alpha 定义为"整体被接受比例"（`E[接受数] / K`）时才成立。下面 `simulate_tail` 里的 alpha 却是**逐位条件接受概率**（第一次拒绝就停止），此时期望 token 数是 `(1 − alpha^(K+1)) / (1 − alpha)`：

| 逐位 alpha | `1 + K·alpha` | 几何模型 | 公式高估倍数 |
|-----------|--------------|---------|------------|
| 0.30 | 2.50 | 1.43 | 1.75x |
| 0.55 | 3.75 | 2.16 | 1.74x |
| 0.70 | 4.50 | 2.94 | 1.53x |
| 0.80 | 5.00 | 3.69 | 1.36x |

讲义的例子"K=5、alpha=0.7、epsilon=0.1 → 4.1x"若按几何模型算是 `2.94 / 1.1 ≈ 2.67x`，正好落在讲义说的"实际多在 2–3x"。

### 3.3 `breakeven_alpha`

```python
def breakeven_alpha(k: int, verify_overhead: float, concurrency: int) -> float:
    effective_overhead = verify_overhead * (1 + concurrency / 256)
    return effective_overhead / k
```

- 由 `(1 + K·alpha) / (1 + eps) = 1` 解出 `alpha = eps / K`。代数正确，结果是 0.034 / 0.045 / 0.060。
- 讲义也给出了这个"原始 decode 数学"（0.03），但紧接着说实际门槛在 0.45–0.55。代码只实现了前者，没有实现"高并发下 batch 已摊薄读权重"这一机制，所以永远算不出 0.4 以上的门槛。

### 3.4 `simulate_tail`：逐轮模拟

```python
    rng = random.Random(seed)
    base_target_ms = 8.0
    effective_overhead = p.verify_overhead * (1 + p.concurrency / 256)
    verify_ms = base_target_ms * (1 + effective_overhead)
    reroll_ms = base_target_ms  # second pass when draft rejects early

    while tokens_emitted < n_tokens:
        accepted = 0
        for _ in range(p.k):
            if rng.random() < p.alpha:
                accepted += 1
            else:
                break
        batch_lat = verify_ms + (reroll_ms if accepted < p.k else 0)
        batch_tokens = max(1, accepted + 1)
        per_tok = batch_lat / batch_tokens
        for _ in range(batch_tokens):
            jitter = rng.gauss(0, per_tok * 0.1)
            latencies.append(max(0.1, per_tok + jitter))
            tokens_emitted += 1
            if tokens_emitted >= n_tokens:
                break
```

逐行理解：

- **草稿接受**：最多 K 次伯努利试验，第一次失败就 `break`——这是标准投机采样"从左到右验证、遇到第一个拒绝即截断"的结构。接受数服从截断几何分布，`accepted = 0` 的概率是 `1 − alpha`。
- **一轮的延迟**：`verify_ms`（一次带开销的目标前向）；只要不是全部接受，再加 `reroll_ms`（8ms，一次额外的目标前向）。
  - ⚠️ 这对应讲义"rejected tokens force a second target forward"的说法，但与标准投机采样不符：目标模型的验证前向已经算出了第一个被拒位置的分布，直接从修正分布 `(p − q)+` 采样即可，**不需要第二次前向**。这个额外惩罚让被拒轮次的延迟被高估了 8ms。
- **一轮产出的 token**：`accepted + 1`（被接受的草稿 + 1 个修正/奖励 token）。`max(1, …)` 是冗余的，因为 `accepted ≥ 0`。
- **延迟分配**：`per_tok = batch_lat / batch_tokens`，把整轮延迟平均分给每个 token，再加 10% 的高斯抖动。
  - ⚠️ 真实流式输出中，一轮的 token 是**同时**到达的：第一个间隔是整轮延迟，后面的间隔接近 0。平均分配会把 ITL 分布"抹平"。
- **为什么全是 TAIL**：全部被拒（概率 `1 − alpha ≥ 20%`）的轮次延迟 = `verify + reroll`（并发 32 时 `9.35 + 8 = 17.35ms`），只出 1 个 token；它们占全部 token 的比例远超 1%，P99 必然落在 17–22ms 附近，而 plain 的 P99 只有 10–14ms。
- `p99 = latencies[int(0.99 * len(latencies)) - 1]`：与上一节相同的下标取法，比标准最近秩略偏前一位。

### 3.5 `plain_tail`：基线

```python
def plain_tail(concurrency: int, n_tokens: int = 1000, seed: int = 5) -> tuple[float, float]:
    rng = random.Random(seed)
    base = 8.0 * (1 + concurrency / 512)
    lats = [max(0.1, base + rng.gauss(0, base * 0.08)) for _ in range(n_tokens)]
```

- 普通 decode 每 token 约 `8 × (1 + 并发/512)` ms，并发 32/128/256 分别为 8.5/10.0/12.0ms，加 8% 抖动。
- ⚠️ **与 `simulate_tail` 的成本模型不一致**：plain 的单步延迟随并发上升，但 spec 的 `base_target_ms = 8.0` 不随并发变化，只有 verify 开销上升。并发越高，plain 被罚得越多，spec 相对越划算——这与讲义"高并发下投机解码收益下降"的结论相反（见第 6 节）。

### 3.6 `print_table` 与 `main`

```python
    for label, speedup, be_alpha, mean, p99, delta_p99 in rows:
        tag = "  OK" if delta_p99 <= 0 else "  TAIL"
        print(f"{label:28} {speedup:8.2f} {be_alpha:10.3f} {mean:10.2f} {p99:10.2f}{tag}")
```

- 每行是一个 6 元组，`for` 中直接解包。`delta_p99 = spec_p99 − plain_p99`，> 0 就标 `TAIL`。
- 类型注解 `list[tuple[str, float, float, float, float, float]]` 精确描述了这个结构。
- `main` 固定 K=5、epsilon=0.15，三重循环外层并发、内层 alpha；每个配置的 `simulate_tail` 都用同一个种子 3，便于横向比较。
- 末尾的 KEY FINDING 写死了"32 并发约 0.1、256 并发约 0.4"，与表格里的 `be_alpha`（0.034–0.060）不符。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 解析公式 `1 + K·alpha` | 与讲义一致、易手算 | 与模拟中的逐位 alpha 定义不一致，高估 1.4–1.75 倍；应统一用几何模型或统一用"整体接受比例" |
| `epsilon` 随并发线性增长 | 体现"高并发收益变小" | 系数是拍脑袋的；生产中按实测的开/关单步耗时比得到 |
| 被拒加一次 `reroll_ms` | 跟随讲义描述 | 不符合标准投机采样；真实代价是验证中多算的位置和浪费的草稿 |
| 每轮延迟平均分给各 token | 实现简单 | 抹平了成簇到达，低估 ITL 方差 |
| plain 随并发变慢、spec 的目标前向不变 | 未统一 | 导致模拟盈亏平衡点随并发下降，与讲义相反；应让两者共享同一个 `target_step_ms(concurrency)` |
| 未建模草稿成本、K 的选择 | 聚焦 alpha | EAGLE-3 草稿头成本小但不为零；K 越大被拒浪费越多 |
| 结论文字写死 | 方便讲课 | 与输出矛盾；应从计算结果生成 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class SpecPoint` | 自动生成构造函数，`SpecPoint(alpha=0.7, k=5, ...)` |
| 关键字参数构造 | `SpecPoint(alpha=alpha, k=k, verify_overhead=..., concurrency=...)` | 比位置参数更清晰 |
| 返回元组 + 解包 | `mean_ms, p99_ms = simulate_tail(p)` | 函数一次返回多个值 |
| 复杂类型注解 | `list[tuple[str, float, float, float, float, float]]` | 描述"6 元组的列表" |
| `break` 提前退出循环 | `for _ in range(p.k): if rng.random() < p.alpha: ... else: break` | 这里的 `else` 属于 `if`（不是 Python 的 `for-else` 语法）；`break` 在第一次拒绝时跳出 for 循环 |
| 条件表达式 | `reroll_ms if accepted < p.k else 0`、`"  OK" if delta_p99 <= 0 else "  TAIL"` | 一行 if/else |
| `random.Random(seed)` | `rng.random()`、`rng.gauss(0, sigma)` | 独立可复现的随机流；均匀分布与正态分布 |
| 列表推导式 + `max` 截断 | `[max(0.1, base + rng.gauss(...)) for _ in range(n_tokens)]` | 生成样本并防止出现负延迟 |
| 原地排序 | `latencies.sort()` | 与 `sorted()` 不同，不返回新列表 |
| `statistics.mean` | `statistics.mean(latencies)` | 标准库均值 |
| f-string 格式 | `{alpha:.2f}`、`{speedup:8.2f}`、`{be_alpha:10.3f}`、`{label:28}` | 小数位与宽度 |
| f-string 里没有占位符 | `print_table(f"  spec decode", rows)` | 多余的 `f` 前缀，无害但无意义 |
| `"-" * 80` | 分隔线 | 字符串重复 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 1 秒），节选：

```text
Config: K=5, base verify_overhead=0.15

  --- concurrency 32 ---  plain P99 = 10.08 ms
config                        speedup   be_alpha    mean_ms     p99_ms
alpha=0.30 conc=32               2.14      0.034      12.32      20.74  TAIL
alpha=0.55 conc=32               3.21      0.034       8.02      20.18  TAIL
alpha=0.70 conc=32               3.85      0.034       5.66      19.03  TAIL
alpha=0.80 conc=32               4.28      0.034       3.92      18.95  TAIL

  --- concurrency 256 ---  plain P99 = 14.23 ms
alpha=0.30 conc=256              1.92      0.060      13.07      21.99  TAIL
alpha=0.70 conc=256              3.46      0.060       6.03      20.18  TAIL
alpha=0.80 conc=256              3.85      0.060       4.21      20.10  TAIL

KEY FINDING
  Break-even alpha rises with concurrency. At 32 concurrent you profit
  anywhere above ~0.1; at 256 concurrent the bar is ~0.4. ...
```

逐项解读：

- **speedup 列**（公式）：所有 alpha 都 > 1.9x，按公式投机解码永远划算。
- **be_alpha 列**：0.034 / 0.045 / 0.060，确实随并发上升，但远低于 KEY FINDING 所说的 0.1 / 0.4，也远低于讲义的 0.55。
- **mean_ms 列**（模拟）：与 plain 均值（并发 32/128/256 分别约 8.48 / 9.98 / 11.98ms）比较，得到模拟的"实际加速比"：

| alpha | 并发 32 | 并发 128 | 并发 256 |
|-------|--------|---------|---------|
| 0.30 | 0.69 | 0.79 | 0.92 |
| 0.45 | 0.89 | 1.02 | 1.18 |
| 0.55 | 1.06 | 1.21 | 1.41 |
| 0.70 | 1.50 | 1.72 | 1.99 |
| 0.80 | 2.16 | 2.47 | 2.85 |

  - 模拟显示低 alpha 时投机解码是**负收益**（0.69x），并发 32 时盈亏平衡在 0.5 附近，碰巧接近讲义的 0.55；
  - 但并发越高，模拟出的加速比越高、盈亏平衡点越低——与 KEY FINDING 和讲义都相反，原因是 3.5 节的成本模型不一致；
  - 公式（3.85x）与模拟（1.50x）在 alpha=0.7、并发 32 时相差 2.5 倍，来自 alpha 定义差异 + reroll 惩罚。
- **p99_ms 列**：全部在 19–22ms，全部 `TAIL`。这是"全拒轮次概率 = 1 − alpha ≥ 20%"在模型中的必然结果，见 3.4。
- **结论**：这份代码适合用来理解"均值与尾部会朝不同方向变化""alpha 定义很重要"，但它的数字不能直接支持"开/不开"的决策——这正是讲义反复强调的"先在自己的流量上测 alpha"。

---

## 7. 动手改一改

1. **统一 alpha 定义**：把 `expected_speedup` 的分子改成 `(1 - alpha**(k+1)) / (1 - alpha)`（alpha=1 时特判为 K+1），重新打印 speedup 列，并与模拟的实际加速比对比。
2. **去掉 reroll**：令 `reroll_ms = 0`（符合标准投机采样），观察 P99 与 `TAIL` 标签如何变化，再思考讲义中"两次前向"的说法。
3. **统一成本模型**：写 `target_step_ms(concurrency) = 8.0 * (1 + concurrency / 512)`，让 `plain_tail` 和 `simulate_tail` 都用它；再让 verify 开销随并发更快增长（例如 `0.15 × (1 + concurrency/64)`），看能否复现讲义"高并发门槛升到 0.45–0.55"。
4. **真实的成簇到达**：一轮的第一个 token 记整轮延迟，其余记 0（或很小的值），重新计算 P99 ITL，比较与"平均分配"的差别。
5. **讲义练习 1 与 2**：写函数求 2x / 3x 所需 alpha（线性公式与几何模型各一版），以及 70% 通用 + 30% 代码的混合收益（分别按 alpha 加权与按每轮 token 数加权）。
6. **选 K**：固定 alpha，扫描 K = 1…10，画出几何模型下的加速比曲线（假设 epsilon 随 K 线性增长，如 `0.03 × K`），找出最优 K。

---

## 8. 常见坑

- **混用两种 alpha 定义**：逐位条件接受率与整体被接受比例差别很大（0.7 vs 0.388），门槛 0.55 必须对应同一种定义。
- **相信 `1 + K·alpha` 的乐观数字**：在逐位接受模型下会高估 1.4–1.75 倍。
- **以为被拒需要第二次前向**：标准投机采样每轮至少产出 1 个 token，不需要重算；真实成本在验证开销与浪费的草稿上。
- **只看均值**：均值可能明显下降，同时 P99 变差；讲义要求看 P99 ITL。
- **对比的两边用不同的成本模型**：本文件中 plain 随并发变慢而 spec 的目标前向不变，导致结论方向反转。
- **结论文字与数据不符**：KEY FINDING 是写死的字符串，不要不看表格就引用。
- **在短输出或离线批处理上开启**：草稿开销占比高、收益为零，讲义明确列为不该用的场景。
