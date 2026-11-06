# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 21 节 具身 VLA：RT-2、OpenVLA、π0、GR00T ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`；`dataclasses` 被导入但未使用），无需 GPU、无需机器人或仿真器

---

## 1. 这份代码在考察什么

VLA 与普通 VLM 的唯一本质区别是"输出是动作"。这份代码只关心**动作如何表示**这一个问题：

1. **离散分箱**（`discretize` / `undiscretize` / `round_trip_demo`）：把 `[-1, 1]` 的连续动作量化成 256 个 bin，再还原，观察量化误差——对应讲义 "Action tokenization (RT-2)"。
2. **FAST 式压缩**（`dct` / `fast_compress`）：对每个动作维度沿时间做 DCT，只保留前 4 个系数并量化——对应讲义 "FAST tokenizer"。
3. **token 数对比**（`compare_formats`）：30 步 × 10 维的轨迹在三种格式下需要多少 token——对应学习目标 "Describe action tokenization: discrete bin, FAST, continuous flow-matching"。
4. **谱系表与 co-fine-tune 比例**：打印 RT-2 → OpenVLA → Octo → π0 → GR00T 的演进和讲义给出的混合比例。

> 一句话：**动作表示决定了 VLA 的控制频率上限和动作平滑性**。代码的离散化有一个"截断 vs 四舍五入"的细节，FAST 部分只有编码没有解码，"flow-matching = 1 token"更是一个不可比的数字——把这三处看明白，就理解了三种格式的真正差异。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `discretize(action, bins)` | 函数 | 连续值 → bin 下标（`int` 截断 + 夹取） | RT-2 / OpenVLA 动作 token |
| `undiscretize(tokens, bins)` | 函数 | bin 下标 → 连续值（bin 左边界） | 反离散化 |
| `dct(x)` | 函数 | 朴素 O(n²) 未归一化 DCT-II | 频域变换 |
| `fast_compress(trajectory, keep_coeff, bins)` | 函数 | 每维 DCT → 取前 k 个系数 → 除以 n 后 32-bin 量化 | FAST 式压缩（只有编码） |
| `compare_formats()` | 函数 | 生成 30×10 正弦轨迹，比较三种格式的 token 数 | 动作格式对比 |
| `round_trip_demo()` | 函数 | 10 维动作往返一次，打印误差 | 量化误差 |
| `lineage_table()` | 函数 | 打印 7 个 VLA 的年份、模式、开闭源 | 谱系 |
| `main()` | 函数 | 依次运行并打印 co-fine-tune 比例 | — |

数据流：`main` → `round_trip_demo`（`discretize` → `undiscretize`）→ `compare_formats`（构造轨迹 → `discretize` 第一步 × 30 → `fast_compress` → 写死的 flow 计数）→ `lineage_table` → 打印比例。

---

## 3. 逐段精讲

### 3.1 离散分箱：RT-2 / OpenVLA 的动作 token

```python
def discretize(action: list[float], bins: int = 256) -> list[int]:
    """Map a [-1,1]^D action to D integer bins."""
    tokens = []
    for a in action:
        idx = int((a + 1) / 2 * (bins - 1))
        idx = max(0, min(bins - 1, idx))
        tokens.append(idx)
    return tokens


def undiscretize(tokens: list[int], bins: int = 256) -> list[float]:
    return [(2 * t / (bins - 1)) - 1 for t in tokens]
```

- 映射链：`a ∈ [-1, 1]` → `(a + 1) / 2 ∈ [0, 1]` → 乘 255 → 取整得 `0..255`。一个 D 维动作变成 D 个整数，每个整数在真实系统里再映射到 LLM 词表中预留的 256 个 token ID（讲义："map each bin to a vocabulary ID"）。
- `max(0, min(255, idx))` 把越界输入夹到边界：`1.5` → 255、`-2.0` → 0。不会报错，但会**静默失真**，上游归一化错了也察觉不到。
- 反离散化 `2t/255 − 1` 返回的是格点值，`t = 0` → −1，`t = 255` → +1。
- ⚠️ **截断导致误差翻倍**：`int()` 对非负数向下取整，值总被推到左侧格点，误差范围 `[0, 2/255)`，最坏约 0.0078；换成 `round()` 后最坏为 1/255 ≈ 0.0039（在 `[-1, 1]` 上取 10 万个点实测：0.00784 → 0.00392）。
- ⚠️ **0 不可表示**：`0.0` → `int(127.5) = 127` → −0.0039。256 个均匀格点里没有 0，而"保持不动"恰恰是机器人最常见的动作之一。
- 每一维用同一套 `[-1, 1]` 量化，意味着训练前必须按每个关节的实际范围做归一化（讲义 Open X-Embodiment 一节的 "normalize joint ranges"）。

### 3.2 朴素 DCT

```python
def dct(x: list[float]) -> list[float]:
    """Naive type-II DCT."""
    n = len(x)
    out = []
    for k in range(n):
        s = 0.0
        for i in range(n):
            s += x[i] * math.cos(math.pi / n * (i + 0.5) * k)
        out.append(s)
    return out
```

- 公式 `X_k = Σ_i x_i · cos(π/n · (i + 0.5) · k)`，没有归一化系数。`k = 0` 是直流分量（`X_0 = Σ x_i`，即 n 倍均值），`k` 越大频率越高。
- 平滑信号的能量集中在前几个系数：代码轨迹第 0 维的 `X_k / n` 依次约为 `0.660, −0.059, −0.195, −0.001, −0.040, …`，从第 3 个起基本都小于 0.04。这正是 FAST 能压缩的原因。
- 复杂度 O(n²)；真实实现用 `scipy.fft.dct`（O(n log n)，并可选正交归一化 `norm="ortho"`）。
- ⚠️ 只有正变换。没有逆变换就无法验证压缩后还能不能还原动作（逆变换实现见测验 Q10）。

### 3.3 FAST 式压缩

```python
def fast_compress(trajectory: list[list[float]], keep_coeff: int = 4,
                  bins: int = 32) -> list[int]:
    if not trajectory:
        return []
    D = len(trajectory[0])
    tokens = []
    for d in range(D):
        series = [step[d] for step in trajectory]
        coeffs = dct(series)[:keep_coeff]
        for c in coeffs:
            c_norm = max(-1.0, min(1.0, c / len(series)))
            idx = int((c_norm + 1) / 2 * (bins - 1))
            tokens.append(idx)
    return tokens
```

- `trajectory` 的形状是 `(T, D)`：外层是时间步，内层是动作维度。`[step[d] for step in trajectory]` 取出第 d 维的时间序列（相当于转置后的一行）。
- 每维保留 `keep_coeff = 4` 个低频系数，除以 `T` 后夹到 `[-1, 1]`，再用 32 个 bin 量化。输出 `D × keep_coeff = 40` 个整数。
- ⚠️ **与讲义的数字不一致**：讲义说 30 步轨迹压成 "~10 FAST tokens"，代码是 40 个。
- ⚠️ **量化方案会破坏重建**：我们补写逆 DCT 后实测（测验 Q10），只截断时保留 4 个系数误差 0.155、8 个 0.044；但加上代码的 32-bin 截断量化后，4 个系数误差 0.332，8 个反而升到 0.580，30 个系数全保留竟达 1.341——高频系数太小，被粗量化和 `int()` 的系统性偏差淹没。
- ⚠️ 对高频运动（如打鼓），只截断不量化、保留 4 个系数的误差就达 1.078，动作几乎被抹平（测验 Q11）。
- 据 FAST 论文，真实做法是给系数乘缩放因子后四舍五入（多数高频系数变为 0），再用 BPE 把整数序列压缩成数量可变的 token；本代码是一个只保留"形状"的示意版。

### 3.4 三种格式的 token 数对比

```python
    T = 30
    D = 10
    trajectory = [[math.sin(0.1 * t + 0.3 * d) for d in range(D)] for t in range(T)]
    ...
    per_step_discrete = len(discretize(trajectory[0]))
    total_discrete = per_step_discrete * T
    fast_tokens = fast_compress(trajectory, keep_coeff=4)
    total_fast = len(fast_tokens)
    continuous_flow_count = 1
```

- 轨迹：10 个维度都是正弦，相位相差 0.3，频率 0.1 rad/步（约 63 步一个周期），30 步内只走了半个周期左右，非常平滑——对 DCT 压缩是最有利的情形。
- 离散分箱：每步 10 个 token × 30 步 = 300；它只用 `trajectory[0]` 算出"每步 10 个"再乘以 30，并没有真的把每步都离散化。
- FAST：40 个。
- ⚠️ flow-matching 的 "1" 是**写死的常数**，表示"一次动作头输出"，并不是 token。π0 输出连续向量，需要多步去噪（讲义 "~5 denoising steps"），每步都是一次动作专家前向；用 token 数比较它与另两种格式没有意义。
- ⚠️ "speedup: FAST ~7.5x" 只是 `300 / 40`，是 token 数之比。讲义说的"3–5 倍推理加速"是论文的实测值，两者不是一回事。

### 3.5 往返演示、谱系表与 co-fine-tune 比例

```python
    action = [0.1, -0.5, 0.25, -0.75, 0.9, -0.1, 0.0, 0.33, -0.67, 0.5]
    tokens = discretize(action, bins=256)
    recovered = undiscretize(tokens, bins=256)
    ...
    max_err = max(abs(a - r) for a, r in zip(action, recovered))
```

- 10 维动作往返一次，最大误差 0.0069（来自 −0.75 → bin 31 → −0.7569），低于上界 2/255 ≈ 0.0078。所有恢复值都 ≤ 原值，这正是"截断总往下推"的特征。

```python
    rows = [
        ("RT-2",       "2023", "PaLM-X + discrete bin",  "closed"),
        ("OpenVLA",    "2024", "Llama 7B + discrete bin", "open"),
        ("Octo",       "2024", "small diffusion head",   "open"),
        ("pi0",        "2024", "flow-matching head",     "open"),
        ("pi0-FAST",   "2025", "flow + FAST tokenizer",  "open"),
        ("GR00T N1",   "2025", "dual-system humanoid",   "open"),
        ("GR00T N1.7", "2025", "sim-to-real data scale", "open"),
    ]
```

- 谱系表沿用讲义的说法。有两处建议对照原论文核实：RT-2 论文中的骨干是 PaLI-X 和 PaLM-E（并没有名为 "PaLM-X" 的模型）；讲义和代码都说 π0-FAST "combines FAST tokenization with flow matching"，而据 FAST 论文，π0-FAST 是用 FAST token 做**自回归**解码的版本，用来替代 flow-matching 动作头。
- 最后打印的 co-fine-tune 比例（RT-2 ~1:1、OpenVLA ~0.5:1、π0 类似）直接来自讲义，是硬编码文字。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 256 个 bin、`[-1, 1]` 统一范围 | 与 RT-2 / OpenVLA 一致，易复用 LLM 词表 | 需按每个关节的真实范围（常用 1%–99% 分位数）归一化；0 无法精确表示 |
| `int()` 截断 | 代码最短 | 误差上界翻倍；生产用四舍五入或 bin 中心 |
| 越界静默夹取 | 不会产生非法 token | 掩盖归一化错误；应统计越界率并告警 |
| 朴素 O(n²) DCT、无逆变换 | 零依赖 | 无法验证重建；生产用 `scipy.fft.dct/idct` |
| 每维固定保留 4 个系数、32-bin 量化 | 让 token 数固定、便于比较 | 高频动作被抹平；量化过粗导致"系数越多误差越大"；FAST 原方案是缩放取整 + BPE，token 数可变 |
| flow-matching 记为 1 token | 想表达"一次输出整块" | 不可比；应比较"每秒推理次数 × 每次计算量" |
| 演示轨迹是低频正弦 | 突出 DCT 的压缩优势 | 对 FAST 最友好的情形，结论不能外推到高频任务 |
| 谱系与比例硬编码 | 传达讲义结论 | 部分细节（PaLM-X、π0-FAST）需核实 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解 |
| 未使用的导入 | `from dataclasses import dataclass` | 导入了但没有用到，可删除 |
| `int()` 截断 | `int((a + 1) / 2 * (bins - 1))` | 向 0 取整（非负数即向下取整），与 `round()` 不同 |
| 夹取惯用法 | `max(0, min(bins - 1, idx))` | 把值限制在 `[0, bins-1]` |
| 嵌套循环求和 | `for k in range(n): for i in range(n): s += ...` | 朴素 DCT 的 O(n²) 实现 |
| 切片取前 k 个 | `dct(series)[:keep_coeff]` | 保留低频系数 |
| 推导式取一列 | `[step[d] for step in trajectory]` | 从 `(T, D)` 的二维列表取第 d 列 |
| 嵌套推导式造二维数据 | `[[math.sin(0.1 * t + 0.3 * d) for d in range(D)] for t in range(T)]` | 外层时间、内层维度 |
| 卫语句 | `if not trajectory: return []` | 空输入提前返回，避免 `trajectory[0]` 越界 |
| `zip` + 生成器表达式 + `max` | `max(abs(a - r) for a, r in zip(action, recovered))` | 一行求最大绝对误差 |
| f-string 格式 | `{max_err:.4f}`、`{count:>6}`、`{total_discrete / total_fast:.1f}` | 4 位小数；右对齐 6 宽；花括号内可直接写算式 |
| 元组列表 + 下标访问 | `for r in rows: print(f"{r[0]:<12}...")` | 元组按位置取字段 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成）：

```text
ROUND-TRIP: 10-DOF action through discretize + undiscretize
------------------------------------------------------------
  original  : [0.1, -0.5, 0.25, -0.75, 0.9, -0.1, 0.0, 0.33, -0.67, 0.5]
  tokens    : [140, 63, 159, 31, 242, 114, 127, 169, 42, 191]
  recovered : [0.098, -0.506, 0.247, -0.757, 0.898, -0.106, -0.004, 0.325, -0.671, 0.498]
  max abs error: 0.0069  (bin width = 2/255 ~ 0.0078)

ACTION TOKEN COUNTS (30-step trajectory, 10-DOF)
------------------------------------------------------------
  discrete 256-bin (RT-2)          300 tokens   (per-step autoregressive)
  FAST 4-coeff per dim              40 tokens   (sequence compressor)
  flow-matching (pi0)                1 tokens   (single head output)

  speedup: FAST ~7.5x vs discrete bin

VLA LINEAGE
  ...（7 行谱系表，略）

CO-FINE-TUNING RATIO (web VQA : robot trajectories)
  RT-2 ~1:1 / OpenVLA ~0.5:1 / pi0 similar balance
```

逐项解读：

- **往返**：每个恢复值都比原值略小或相等（截断向下），最大误差 0.0069 出现在 −0.75。`0.0` 变成 −0.004，说明 0 不在格点上。若改用 `round()`，token 变为 `[140, 64, 159, 32, 242, 115, 128, 170, 42, 191]`，最大误差降到 0.0039。
- **token 数**：300 = 30 步 × 10 维；40 = 10 维 × 4 个系数；1 是写死的。按 30 Hz 执行，离散分箱需要每秒解码 300 个 token，这就是讲义说它只能跑 3–5 Hz 的原因。
- **7.5x**：只是 token 数之比，不代表实际速度，也不代表 FAST 能无损还原动作（按代码的量化方式，重建误差达 0.33，见 3.3 节）。
- **谱系与比例**：纯文字，阅读时注意 3.5 节提到的两处待核实细节。

---

## 7. 动手改一改

1. **减半量化误差**：把 `discretize` 的 `int` 改为 `round`，在 `[-1, 1]` 上均匀取 10 万个点，验证最大误差从约 0.0078 降到约 0.0039；再试 `bins = 512`，看误差如何变化。
2. **补上 FAST 解码器**：实现 `idct(coeffs, n)` 和 `fast_decompress(tokens, T, D, keep_coeff, bins)`，打印保留 1/2/4/8/30 个系数时的最大重建误差（参考测验 Q10 的表格）。
3. **改进量化**：仿照 FAST 论文的思路，把每个系数乘以缩放因子（例如 10）后四舍五入成整数、丢掉为 0 的系数，统计非零系数个数作为"token 数"，比较它与代码固定 40 个 token 的精度差别。
4. **讲义练习 2**：把轨迹换成打鼓式高频运动 `sin(2π·0.4·t + d)`，看保留 4 个系数时轨迹被抹平成什么样；再找出把误差降到 0.05 以下至少需要多少系数。
5. **讲义练习 1/3**：写 `control_rate_check(dof, hz, fmt, tok_per_s)`，对离散分箱、FAST、动作块三种格式判断给定解码速度能否支撑目标控制频率（参考测验 Q12）。
6. **进阶**：加一个"安全层"函数 `safety_filter(action, prev_action, joint_limits, max_delta)`，对 VLA 输出做关节限位与速度限幅，统计在随机动作序列上被修正的比例——体会讲义"VLA 的输出是建议，不是命令"。

---

## 8. 常见坑

- **截断当四舍五入**：`int()` 让量化误差翻倍，而且有方向性偏差（总是偏小）。
- **归一化范围不统一**：不同机器人、不同关节的范围差别很大，统一到 `[-1, 1]` 前要用数据统计（如分位数）确定范围，否则大量动作会被夹在边界上。
- **只看 token 数不看重建误差**：压缩率再高，还原不出动作也没用；评估 FAST 类方法必须同时报告重建误差。
- **用平滑轨迹测试压缩**：低频正弦是 DCT 的最佳情形，高频任务要单独测试。
- **把 flow-matching 的"1 次输出"当成 1 个 token**：它需要多步去噪，每步都有计算成本；比较应基于每秒推理次数和每次延迟。
- **忽略动作块的开环风险**：一次输出 50 步，块内对环境变化无反应，需要重叠推理或缩短执行步数。
- **把安全寄托在模型上**：限位、限速、工作空间边界必须在 VLA 之外的控制层实现。
