# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 13 节 规模定律（Scaling Laws） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`）

---

## 1. 这份代码在考察什么

这份代码不训练任何模型，它把 Chinchilla 论文的 loss 公式当成一个"模拟器"，让你用几十行代码回答三个价值上亿美元的问题：

1. **公式本身**：`L(N, D) = A/N^α + B/D^β + E` 三项各代表什么，常数怎么代入。
2. **约束优化**：在 `C = 6ND` 的算力约束下，如何把二维问题变成一维搜索，找到计算最优的 `(N*, D*)`。
3. **"20 token/参数"到底准不准**：代码的输出会告诉你，用这组拟合常数算出的最优 D/N 并不是常数 20，而是随算力增长——这正是讲义里"经验法则 vs 拟合公式"的张力。
4. **过度训练的代价**：等算力下把模型缩小 10 倍，loss 只涨一点点，推理却便宜 10 倍。
5. **对照真实模型**：把 GPT-3、Chinchilla、Llama、DeepSeek-V3、Qwen 的 `(N, D)` 代入，看谁"欠训练"、谁"过度训练"。

> 一句话：**scaling law 是一个可以算的预算工具，而不是一句口号**——这份代码让你亲手算一遍。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `A, B_CONST, ALPHA, BETA, E_CONST` | 模块级常数 | Hoffmann 2022 参数化拟合给出的系数 | 公式里的 A、B、α、β、E |
| `chinchilla_loss(N, D, ...)` | 函数 | 计算给定参数量与 token 数下的预测 loss | Chinchilla loss 公式 |
| `compute_optimal(C_flops, n_grid=200)` | 函数 | 在 `6ND = C` 约束下，对 log N 做网格搜索求最小 loss | 计算最优前沿（compute-optimal frontier） |
| `pretty(n)` | 函数 | 把 `4.25e10` 显示成 `42.5B` | 工具函数 |
| `main()` | 函数 | 三个实验：最优前沿表、过度训练代价、真实模型对照 | 讲义 Build It 的 Step 2–4 |

数据流：`main` → 对每个 C 调 `compute_optimal` → 内部反复调 `chinchilla_loss` → 用 `pretty` 打印。

---

## 3. 逐段精讲

### 3.1 常数与 loss 公式

```python
A = 406.4
B_CONST = 410.7
ALPHA = 0.34
BETA = 0.28
E_CONST = 1.69


def chinchilla_loss(N, D, A=A, B=B_CONST, alpha=ALPHA, beta=BETA, E=E_CONST):
    return A / N ** alpha + B / D ** beta + E
```

- 三项相加：`A/N^α` 是**参数不够**带来的损失，`B/D^β` 是**数据不够**带来的损失，`E` 是数据本身的熵（不可约下限）。N、D 都趋于无穷时 loss → 1.69。
- `A / N ** alpha`：`**` 的优先级高于 `/`，所以等价于 `A / (N ** alpha)`，不需要括号。
- 常数写成**默认参数**：平时直接 `chinchilla_loss(N, D)`；想试另一组拟合常数（比如你在练习里自己拟合出来的）时可以 `chinchilla_loss(N, D, alpha=0.3)` 局部覆盖，而不用改全局变量。
- 默认值 `A=A` 看着奇怪：左边是形参名，右边是模块级常数 `A`，在 `def` 执行的那一刻求值并"冻结"。之后即使修改全局 `A`，函数默认值也不会变。
- ⚠️ 命名不统一：`A` 直接叫 `A`，而 `B`、`E` 加了 `_CONST` 后缀。读代码时知道它们是同一类东西即可。
- ⚠️ 讲义说 N 是**非 embedding 参数**；但后面"真实模型对照"里代入的是公开的总参数量，这是演示用的简化。

### 3.2 `compute_optimal`：把约束优化变成一维网格搜索

```python
def compute_optimal(C_flops, n_grid=200):
    """Find (N, D) minimizing loss subject to 6ND = C by grid search over log N."""
    # 6ND = C => D = C / (6N)
    log_N_min = math.log10(1e5)
    log_N_max = math.log10(1e13)
    best = (None, None, float("inf"))
    for i in range(n_grid):
        log_N = log_N_min + (log_N_max - log_N_min) * i / (n_grid - 1)
        N = 10 ** log_N
        D = C_flops / (6 * N)
        if D < 1e6:
            continue
        loss = chinchilla_loss(N, D)
        if loss < best[2]:
            best = (N, D, loss)
    return best
```

- **消元**：约束 `6ND = C` 让 D 完全由 N 决定（`D = C/(6N)`），二维问题变成"只扫 N"的一维问题。这是处理等式约束最朴素也最稳的办法。
- **为什么在 log 空间取点**：N 的搜索范围从 1e5 到 1e13，跨 8 个数量级。线性均匀取 200 个点，几乎所有点都会挤在 1e12 附近，小模型区间一个点都没有；在 `log10(N)` 上均匀取点，每个数量级约 25 个点，分辨率处处相同。
- `i / (n_grid - 1)` 让 i=0 时恰好取到下界、i=n_grid−1 时恰好取到上界（两端都包含）。
- 相邻格点的 N 相差 `10^(8/199) ≈ 1.097` 倍，约 9.7%。这决定了结果的精度——也解释了输出里 D/N 为什么不平滑（见第 6 节）。
- `if D < 1e6: continue`：小算力 + 大 N 会让 D 小得离谱（不到一百万 token），这种组合没有物理意义，直接跳过。
- `best = (None, None, float("inf"))`：用正无穷作初值，第一个合法点一定能更新它；这是"求最小值"循环的标准起手式。
- ⚠️ 如果所有格点都被 `D < 1e6` 过滤掉（算力极小的时候），函数会返回 `(None, None, inf)`，`main` 里的 `D / N` 会抛 `TypeError`。本文件用到的 C 都 ≥ 1e18，不会触发。
- **为什么不用闭式解**：其实可以求导得到 `N_opt = G·(C/6)^(β/(α+β))`（测验 Q10）。网格搜索的好处是**和 loss 公式解耦**：如果你把推理成本也加进目标函数，闭式解要重推，网格搜索一行不用改。

### 3.3 `pretty`：人类可读的数量级

```python
def pretty(n):
    """human-readable."""
    for unit, k in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if n >= k:
            return f"{n / k:.1f}{unit}"
    return f"{n:.0f}"
```

- 从大到小检查单位，命中第一个就返回，所以列表**必须按从大到小排列**；顺序反了，`4.25e10` 会被显示成 `42500000.0K`。
- `for` 循环里提前 `return`，循环走完都没命中才执行最后一行——小于 1000 的数原样输出。
- T/B/M/K 在这里同时用于参数量和 token 数：`42.5B` 参数、`3.9T` token。

### 3.4 实验一：计算最优前沿

```python
    for C in [1e18, 1e19, 1e20, 1e21, 1e22, 1e23, 1e24, 1e25]:
        N, D, L = compute_optimal(C)
        print(f"  {C:>10.0e}   {pretty(N):>9}   {pretty(D):>9}   {D / N:>6.1f}   {L:>6.3f}")
```

- 从 1e18（一个小实验）扫到 1e25（前沿大模型量级），每 10 倍一档。
- 打印 D/N 是为了"验证 20 这条规则"。但输出显示的是 25～120，代码紧接着打印了一段说明：用这组常数（α=0.34，β=0.28）算出的最优 D/N 会随 C 增长，"20"是论文针对其研究区间给出的标题结论，外推会漂移。
- 背后的数学：`D/N ∝ C^((α−β)/(α+β)) = C^0.097`，只有 α=β 时才是常数。
- ⚠️ 文件开头 docstring 写着 "Validates the D/N ≈ 20 rule numerically"，但实际输出并没有得到 20——读的时候要以输出为准。

### 3.5 实验二：过度训练的代价

```python
    C = 1e24
    N_opt, D_opt, L_opt = compute_optimal(C)
    N_under = N_opt / 10
    D_over = D_opt * 10
    L_over = chinchilla_loss(N_under, D_over)
    # ...
    print(f"loss penalty (over-train):      {L_over - L_opt:+.3f}")
    print(f"inference FLOP savings (~N):    {N_opt / N_under:.0f}x cheaper at inference")
```

- `N/10` 和 `D×10` 相乘不变，所以 `6·N·D` 不变——这是一次**等算力**对比：同样的训练账单，换一个小 10 倍的模型。
- 推理每 token 约 `2N` FLOPs，所以推理节省就是 `N_opt / N_under = 10` 倍。代码直接打印这个比值，是一个"恒等式"，但把结论显式写出来更直观。
- `{...:+.3f}` 中的 `+` 让正数也带符号，读者一眼看出是"变差了"。
- ⚠️ 这里只是"缩小 10 倍"一个点。真实决策会扫一整条曲线（1/2、1/4、1/10 ……），再结合推理流量算总成本最低点。

### 3.6 实验三：真实模型对照

```python
    models = [
        ("GPT-3 175B",          175e9,  300e9),
        ("Chinchilla 70B",       70e9, 1400e9),
        ("Llama 2 70B",          70e9, 2000e9),
        ("Llama 3 8B",            8e9, 15_000e9),
        ("Llama 3 70B",          70e9, 15_000e9),
        ("DeepSeek-V3 (active)", 37e9, 14_800e9),
        ("Qwen 2.5 72B",         72e9,  18_000e9),
    ]
    print(f"{'model':<24}  {'N':>8}  {'D':>8}  {'D/N':>7}  {'loss':>7}")
    for name, N, D in models:
        L = chinchilla_loss(N, D)
        print(f"  {name:<22}  {pretty(N):>7}  {pretty(D):>7}  {D / N:>6.1f}  {L:>6.3f}")
```

- 用"元组列表"存表格数据，`for name, N, D in models` 一次解包三列，比三个平行列表更不容易错位。
- `15_000e9`：数字字面量里的下划线只是分隔符，等于 `15000e9 = 1.5e13`（15T token）。
- DeepSeek-V3 代入的是 **37B 激活参数**，对应讲义"MoE 按每个激活 FLOP 看 scaling law"的说法。
- ⚠️ 这一列 loss 是**公式预测值**，不是各家报告的真实 loss。讲义 Step 4 说"比较预测与报告的 loss"，但代码只打印了预测值；而且不同模型的 tokenizer 和数据不同，真实 loss 本来也不能直接横向比较。这张表的意义在于看 D/N 和相对趋势。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、不用 NumPy/SciPy | 零依赖，公式一眼可见 | 生产中用 `scipy.optimize` 求解，或直接用闭式解 |
| 用消元把约束问题变一维 | 最简单、最稳，不需要拉格朗日乘子 | 多约束（如显存上限、推理预算）时需要更通用的优化器 |
| log 空间网格搜索 | 跨 8 个数量级时分辨率均匀 | 200 点约 9.7% 步长，D/N 有抖动；可加密网格或在最优点附近二次细化 |
| 常数做成默认参数 | 方便替换为自己拟合的常数 | 默认值在定义时冻结，改全局常数不会生效 |
| 等算力对比过度训练 | 公平：同一训练账单下比较 | 真实决策还要把推理流量、延迟、显存一起建模 |
| 真实模型只算预测 loss | 公开的 N、D 好找，真实 loss 不可比 | 严肃对比需用同一评测集上的下游指标 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常数（全大写命名） | `ALPHA = 0.34` | 约定俗成表示"不要修改"；Python 本身不强制 |
| 幂运算与优先级 | `A / N ** alpha` | `**` 优先级高于 `/`，等于 `A / (N ** alpha)` |
| 默认参数 | `def chinchilla_loss(N, D, A=A, ...)` | 不传时用默认值；默认值在 `def` 执行时求值一次 |
| `math.log10` | `math.log10(1e5)` | 以 10 为底的对数，返回 `5.0` |
| 科学计数法字面量 | `1e5`、`175e9` | 浮点数写法，`175e9` = 1.75×10¹¹ |
| 数字分隔下划线 | `15_000e9` | Python 3.6+，只为好读，不影响数值 |
| `float("inf")` | `best = (None, None, float("inf"))` | 正无穷，任何有限数都比它小，适合作最小值初值 |
| 元组与索引 | `best[2]`、`best = (N, D, loss)` | 用元组打包多个返回值，按下标访问 |
| 元组解包 | `N, D, L = compute_optimal(C)`、`for name, N, D in models` | 一次把多个值赋给多个变量 |
| `continue` 与循环中 `return` | `if D < 1e6: continue`；`pretty` 里命中就 `return` | 跳过本轮 / 直接结束函数 |
| f-string 宽度与对齐 | `{C:>10.0e}`、`{name:<22}`、`{'model':<24}` | `>` 右对齐、`<` 左对齐，数字是总宽度 |
| f-string 数字格式 | `:.0e` 科学计数、`:.1f` 一位小数、`:+.3f` 带符号 | `+` 让正数也显示 `+` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中执行）的完整输出：

```text
=== compute-optimal (N, D) across compute budgets ===
     compute          N*          D*      D/N     loss
       1e+18       78.4M        2.1B     27.1    3.535
       1e+19      238.2M        7.0B     29.4    2.986
       1e+20      659.3M       25.3B     38.3    2.600
       1e+21        1.8B       91.3B     50.0    2.329
       1e+22        5.1B      329.9B     65.3    2.139
       1e+23       14.0B        1.2T     85.2    2.005
       1e+24       42.5B        3.9T     92.4    1.911
       1e+25      117.6B       14.2T    120.5    1.845
```

- **N\* 每 10 倍算力约涨 2.8 倍**（78M → 238M → 659M …），符合 `N_opt ∝ C^0.452`（10^0.452 ≈ 2.83）。D\* 涨得略快（∝ C^0.548）。
- **D/N 不是 20**，而是从 27 一路涨到 120：这是 α ≠ β 的直接后果。
- **D/N 有抖动**（85.2 → 92.4 的增幅明显小于前后两档）：网格步长约 9.7%，N\* 的误差被反向传到 D\*，D/N 的误差约翻倍。把 `n_grid` 改成 20000，这一列变成 25.7、…、78.2、97.7、122.1，平滑递增。
- **loss 递减越来越慢**：1e18 → 1e19 降 0.55，1e24 → 1e25 只降 0.07，越来越贴近 E=1.69。这就是"边际收益递减"。

```text
=== over-training cost (Llama-style) ===
compute budget:                 1e+24 FLOPs
chinchilla optimal:             N=42.5B  D=3.9T  loss=1.911
over-trained  (N/10, D×10):     N=4.2B  D=39.2T  loss=1.971
loss penalty (over-train):      +0.059
inference FLOP savings (~N):    10x cheaper at inference
```

- 同一份训练账单，模型小 10 倍，loss 只高 0.059（约 3%），推理便宜 10 倍。这就是 2026 年"过度训练成为默认"的数学理由。
- 注意 39.2T token 已经超过讲义估计的高质量 web 文本总量，现实中会撞上数据墙。

```text
=== real models vs predicted loss ===
model                            N         D      D/N     loss
  GPT-3 175B               175.0B   300.0B     1.7   2.002
  Chinchilla 70B            70.0B     1.4T    20.0   1.937
  Llama 2 70B               70.0B     2.0T    28.6   1.921
  Llama 3 8B                 8.0B    15.0T  1875.0   1.949
  Llama 3 70B               70.0B    15.0T   214.3   1.857
  DeepSeek-V3 (active)      37.0B    14.8T   400.0   1.878
  Qwen 2.5 72B              72.0B    18.0T   250.0   1.852
```

- **GPT-3 预测 loss 最高**：参数最多，但 D/N 只有 1.7，数据项拖了后腿。
- **Chinchilla 70B 用 40% 的参数打败 GPT-3**（1.937 < 2.002），正是论文的核心卖点。
- **Llama 3 8B（1.949）只比 Chinchilla 70B 差 0.012**，参数却小近 9 倍——推理成本优势巨大。
- 后几个模型 D/N 都在 200～400，落在讲义所说"推理主导时 100–500 token/参数"的区间；Llama 3 8B 的 1875 是更极端的过度训练。

---

## 7. 动手改一改

1. 把 `n_grid` 改成 2000，观察 D/N 列是否变平滑、loss 列是否变化（提示：loss 几乎不变，说明最优点附近很平）。
2. 实现闭式解 `compute_optimal_closed(C)`，与网格搜索逐行对比（参考测验 Q10）。
3. 加一个函数 `tokens_to_match(N, target_loss)`：给定模型大小，求达到目标 loss 需要的 token 数；用它算"4.2B 模型要多少 token 才能追平 1.911"（答案是天文数字，参考测验 Q11）。
4. 把过度训练实验改成扫描：`shrink in [1, 2, 4, 10, 30, 100]`，打印每档的 loss 惩罚，画出"惩罚 vs 推理节省"的折线。
5. 讲义练习 2：沿计算最优前沿打印 loss 与 `log10(C)`，找出"下一次降低 0.1 loss"需要多少算力。
6. 进阶：把目标改成"训练 FLOPs + 一生推理 FLOPs（`2·N·推理 token 数`）"之和最小，在固定目标 loss 下求最优 N——这就是 Sardana & Frankle（2024）的思路。

---

## 8. 常见坑

- **把 20 当成定理**：这组拟合常数算出的最优 D/N 是 25～120，"20"只是经验法则；换算力区间、换数据，最优比例都会变。
- **线性网格扫数量级**：`range(1e5, 1e13, step)` 式的线性取点会让小模型区间完全没有分辨率，跨数量级的搜索一定要在 log 空间做。
- **忘记约束**：只在 N 上扫而 D 固定，比较的就不是"同一预算下"的方案，结论毫无意义。
- **把预测 loss 当真实 loss 对比**：不同模型的 tokenizer、数据分布不同，loss 数值不能横向比较；这张表只能看趋势。
- **MoE 用总参数代入**：DeepSeek-V3 若用总参数代入，D/N 和 FLOPs 都会严重失真；本文件用激活参数是有意为之。
- **默认参数"冻结"**：想用新常数时，修改全局 `ALPHA` 不会影响 `chinchilla_loss` 的默认值，要显式传参。
