# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 08 节 ControlNet、LoRA 与条件控制 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，不到 1 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码用两个极小的实验，把本节两大工具的**数学核心**单独拎出来：

1. **LoRA = 冻结的 `W` + 可训练的低秩 `B·A`**：给定一个冻结矩阵和一个"目标矩阵"，只训练 `A`、`B`，看低秩增量能不能补上两者的差。
2. **LoRA 的初始化技巧**：`B = 0`、`A` 随机，开局 `ΔW = 0`，但梯度能流动。
3. **ControlNet 的 zero-conv 思想**：旁路输出乘一个初始化为 0 的门控，开局 no-op，训练中门控逐渐打开。
4. **手推梯度**：两个实验都手写了梯度，能看清"零初始化的参数第一步谁先动"。

> 一句话：**LoRA 和 ControlNet 都是"冻结大模型 + 零初始化的小增量"**——开局不伤底座，再慢慢学出该学的东西。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `matmul_mat_vec` / `outer` / `zeros` / `randn_matrix` | 工具函数 | 纯列表的矩阵×向量、外积、全零矩阵、高斯随机矩阵 | 线性代数基础（`outer` 定义了但没被调用） |
| `lora_forward(W_frozen, A, B, x, alpha)` | 函数 | 计算 `(W + α·B·A)·x` | LoRA 前向 |
| `train_lora(W_frozen, W_target, r, rng, steps, lr)` | 函数 | 用 SGD 训练 `A`、`B`，返回 500 个测试样本上的平均平方误差 | LoRA 训练 |
| `controlnet_toy(steps, rng)` | 函数 | 训练 `out = x + gate·w_side·c`，记录 `gate`、`w_side` 轨迹 | ControlNet 的 zero-conv 门控 |
| `main()` | 函数 | 构造冻结矩阵与秩 1 目标增量 → 扫 r = 1/2/4 → 跑 ControlNet-lite | 实验编排 |

数据流：`main` 先生成 `W_frozen` 和 `W_target = W_frozen + 0.5·u·vᵀ`，对每个 r 调用 `train_lora`（内部反复调用 `lora_forward`）；再调用 `controlnet_toy` 打印门控轨迹。

---

## 3. 逐段精讲

### 3.1 LoRA 前向：`lora_forward`

```python
def lora_forward(W_frozen, A, B, x, alpha=1.0):
    """Compute (W + alpha * B @ A) @ x."""
    base = matmul_mat_vec(W_frozen, x)
    Ax = matmul_mat_vec(A, x)
    BAx = matmul_mat_vec(B, Ax)
    return [base[i] + alpha * BAx[i] for i in range(len(base))]
```

- **先算 `A·x` 再算 `B·(A·x)`**，而不是先构造 `d×d` 的 `B·A` 再乘 `x`。前者每次只需 `O(2dr)` 次乘法，后者需要 `O(d²r + d²)`。这正是生产中 LoRA 不合并时的计算方式：底座走一遍，旁路走一条"窄"路径（d → r → d），结果相加。
- `alpha` 是运行时强度旋钮，对应讲义 `W' = W + α·B·A`。训练时用默认值 1.0；推理时调它就能改变 LoRA 强度，**合并进权重后就没法再调了**。

### 3.2 LoRA 训练：`train_lora`

```python
    d = len(W_frozen)
    A = randn_matrix(r, d, rng, scale=0.2)
    B = [[0.0] * r for _ in range(d)]
    for step in range(steps):
        x = [rng.gauss(0, 1) for _ in range(d)]
        target = matmul_mat_vec(W_target, x)
        pred = lora_forward(W_frozen, A, B, x)
        err = [pred[i] - target[i] for i in range(d)]
        Ax = matmul_mat_vec(A, x)
        for i in range(d):
            for k in range(r):
                grad_B = err[i] * Ax[k]
                B[i][k] -= lr * grad_B
        for k in range(r):
            for j in range(d):
                grad_A = sum(err[i] * B[i][k] for i in range(d)) * x[j]
                A[k][j] -= lr * grad_A
```

- **初始化 = 标准 LoRA**：`A ~ N(0, 0.2²)`，`B = 0`，所以开局 `ΔW = 0`，模型行为与冻结底座完全一样。
- **训练数据**：每步随机采一个 `x`，目标是 `W_target·x`。因为 `W_frozen` 不动，LoRA 需要学的就是 `ΔW = W_target − W_frozen`。
- **梯度**（损失为 `½‖err‖²`）：
  - `∂/∂B[i][k] = err[i]·(Ax)[k]`，即 `err ⊗ (A·x)`；
  - `∂/∂A[k][j] = (Bᵀ·err)[k]·x[j]`，即 `(Bᵀ·err) ⊗ x`。
- ⚠️ 细节：代码**先更新 `B`，再用更新后的 `B` 算 `A` 的梯度**。若严格同时更新，第 0 步 `B = 0` 时 `grad_A = 0`；按这种写法，第 0 步 `A` 也会动。这是"顺序更新"而不是标准的联合梯度，学习率小时影响不大（测验 Q9）。
- **评估**：训练后再采 500 个新的 `x`，计算 `Σ(target − pred)²` 的平均。对 `x ~ N(0, I)`，`E‖R·x‖² = ‖R‖_F²`，所以它估计的是"剩余误差矩阵的 Frobenius 范数平方"。

### 3.3 `main` 里的目标增量：秩 1

```python
    W_frozen = randn_matrix(d, d, rng, scale=0.5)
    delta = rng.choice([1, 2, 3])
    delta_matrix = zeros(d, d)
    u = [rng.gauss(0, 1) for _ in range(d)]
    v = [rng.gauss(0, 1) for _ in range(d)]
    for i in range(d):
        for j in range(d):
            delta_matrix[i][j] = u[i] * v[j] * 0.5
    W_target = [[W_frozen[i][j] + delta_matrix[i][j] for j in range(d)] for i in range(d)]
```

- `delta_matrix = 0.5·u·vᵀ` 是一个外积，**秩恰好为 1**。
- ⚠️ `delta = rng.choice([1, 2, 3])` 选出来后**从未被使用**（种子 17 下取到 3），看起来作者原本想构造秩为 `delta` 的增量。因此本实验里 r = 1、2、4 全部 ≥ 真实秩 1，**没有"秩不够"的对照组**，结尾的 takeaway "LoRA needs rank >= true delta rank" 并没有被这次运行真正验证（改法见测验 Q10 与第 7 节练习 1）。
- 每个 r 都传入独立的 `random.Random(2 * r)`，保证不同 r 的实验互不干扰、可复现。

### 3.4 ControlNet-lite：`controlnet_toy`

```python
    w_side = rng.gauss(0, 0.1)
    gate = 0.0          # zero-conv init
    lr = 0.03
    trace = []
    for step in range(steps):
        x = rng.gauss(0, 1)
        c = rng.choice([-1.0, 1.0])
        target = x + 0.7 * c     # the "true" signal we want
        pred = x + gate * w_side * c
        err = pred - target
        grad_gate = 2 * err * w_side * c
        grad_wside = 2 * err * gate * c
        gate -= lr * grad_gate
        w_side -= lr * grad_wside
```

与真实 ControlNet 的对应关系：

| 玩具代码 | 真实 ControlNet |
|---------|----------------|
| `x`（直接透传） | 冻结的 SD 主干特征 |
| `c ∈ {−1, +1}` | 条件图（边缘/深度/姿态） |
| `w_side` | ControlNet 副本（从预训练编码器复制，非零） |
| `gate`（初始化为 0） | zero convolution |
| `target = x + 0.7c` | "正确使用条件后应该得到的结果" |

- **第 0 步**：`gate = 0`，所以 `pred = x`，与底座完全一致（no-op）；`grad_wside = 0`，`grad_gate ∝ w_side ≠ 0`，**门控先动**。门控离开 0 之后，`w_side` 才开始拿到梯度。这与讲义"Early training updates gate slowly — no catastrophic drift"一致。
- 若 `w_side` 也初始化为 0，两个梯度恒为 0，训练会卡死——这说明为什么真实 ControlNet 只把连接处置 0，副本本身保留预训练权重。
- 损失是 `err²`（不是半平方），所以梯度里有因子 2。
- `if (step + 1) % 100 == 0` 每 100 步记录一次三元组 `(step, gate, w_side)`。

### 3.5 打印轨迹

```python
    trace = controlnet_toy(steps=800, rng=rng)
    for step, gate, wside in trace[::2][:6]:
        print(f"  step {step:4d}: gate={gate:+.3f}  w_side={wside:+.3f}")
```

- 800 步、每 100 步记一次 → 8 条；`[::2]` 隔一条取 → 4 条（第 100/300/500/700 步）；`[:6]` 在这里不起作用。
- ⚠️ 因为第一条记录就在第 100 步，而门控在前 100 步内已经基本收敛，**输出里看不到"从 0 爬升"的过程**（见第 6 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `B = 0, A` 随机 | 开局 `ΔW = 0` 且梯度能流动 | 与 PEFT/diffusers 的默认初始化一致 |
| 先 `A·x` 再 `B·(·)` | 只付 `O(dr)` 的额外计算 | 生产中不合并时就是这条"窄路径"；合并后零额外开销但失去 `α` |
| 单样本 SGD + 手写梯度 | 透明、无依赖 | 真实训练用 autograd + AdamW + batch |
| 6×6 矩阵、秩 1 目标 | 秒级跑完，结论清晰 | 没有 r < 真实秩的对照组（`delta` 未使用） |
| 标量门控代替 1×1 卷积 | 只保留"零初始化连接"这一本质 | 真实 zero-conv 是逐通道的卷积权重 + 偏置 |
| 只在 100 步的整数倍记录轨迹 | 输出简短 | 错过了前 100 步的爬升过程 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 文档字符串 | `"""Compute (W + alpha * B @ A) @ x."""` | 函数首行的字符串，`help()` 能显示 |
| 默认参数 | `def lora_forward(..., alpha=1.0)`、`steps=4000, lr=0.01` | 调用时可省略 |
| 关键字参数调用 | `train_lora(W_frozen, W_target, r=r, rng=random.Random(2 * r))` | 按名字传参，可读性更好 |
| 列表推导式 / 嵌套推导 | `[[u[i] * v[j] for j in range(len(v))] for i in range(len(u))]` | 一行构造矩阵（外积） |
| `[[0.0] * cols for _ in range(rows)]` | `zeros` | 正确构造二维列表；写成 `[[0.0]*cols]*rows` 会让各行共享同一个列表 |
| 生成器表达式 + `sum` | `sum(err[i] * B[i][k] for i in range(d))` | 不建中间列表的求和 |
| 原地更新 | `B[i][k] -= lr * grad_B` | 直接修改列表元素 |
| `random.Random(seed)` 实例 | `random.Random(17)`、`random.Random(2 * r)` | 各实验独立的可复现随机源 |
| `rng.choice` | `rng.choice([-1.0, 1.0])` | 从序列中等概率选一个 |
| 元组列表 + 解包遍历 | `trace.append((step + 1, gate, w_side))`；`for step, gate, wside in ...` | 打包记录、解包使用 |
| 切片步长 | `trace[::2][:6]` | `[::2]` 每隔一个取；`[:6]` 取前 6 个 |
| f-string 格式符 | `f"{err:.5f}"`、`f"{step:4d}"`、`f"{gate:+.3f}"` | 小数位、宽度、强制正负号 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行输出：

```text
=== LoRA: approximate a known rank-1 delta ===
  rank r=1: residual MSE 0.00000
  rank r=2: residual MSE 0.00000
  rank r=4: residual MSE 0.00000

=== ControlNet-lite: zero-initialized gate on a side signal ===
  step  100: gate=+0.815  w_side=+0.823
  step  300: gate=+0.833  w_side=+0.840
  step  500: gate=+0.833  w_side=+0.840
  step  700: gate=+0.833  w_side=+0.840

takeaway: LoRA needs rank >= true delta rank to converge exactly.
          ControlNet-lite gate ramps from 0 as the side signal proves useful.
```

- **LoRA 三行全是 0**：目标增量秩为 1，r = 1 已经足够精确表示，r = 2、4 多出来的维度学成了冗余（多个秩 1 分量的组合仍等于同一个秩 1 矩阵）。要看到"秩不够"的效果，必须把目标改成秩 2：我们在临时副本里实测，r = 1 在 `lr=0.003` 时残差停在约 10.7（≈ `σ₂² = 11.30`，评估样本数有限所以略有偏差），在默认 `lr=0.01` 时直接发散为 `nan`；r = 2、4 仍为 0。
- **ControlNet-lite**：第 100 步时 `gate·w_side = 0.815 × 0.823 ≈ 0.671`，已接近目标 0.7；第 300 步起稳定在 `0.833 × 0.840 ≈ 0.700`，完全学到了目标系数。
- `gate ≈ w_side`：乘积参数化下，`gate² − w_side²` 在梯度流中近似守恒，开局它是 `−w_side₀²`（很小），所以两者最终几乎相等、`gate` 略小。
- **看不到爬升**：用另一个种子把前 100 步打印出来，可以看到 `gate·w_side` 依次为 0.001（第 1 步）→ 0.007（第 11 步）→ 0.09（第 41 步）→ 0.31（第 61 步）→ 0.67（第 100 步），呈典型的 S 形：开头很慢（因为 `w_side` 很小，门控的梯度也很小），中段加速，最后饱和。这就是讲义说的"gate ramps from 0"。

---

## 7. 动手改一改

1. **补上对照组**：用 `delta` 构造秩为 `delta` 的目标增量（循环叠加 `delta` 个外积，见测验 Q10），把 r 扫到 `[1, 2, 3, 4]`，找出残差降到 0 的最小秩；并用 `numpy.linalg.svd` 验证 r 不足时的残差 ≈ 剩余奇异值平方和。
2. **观察爬升**：把 `controlnet_toy` 的记录间隔改成每 5 步，打印前 120 步，画出 `gate·w_side` 的 S 形曲线。
3. **双零初始化**：把 `w_side` 也设为 0，验证训练完全卡住；再对 LoRA 做同样的实验（`A`、`B` 都设为 0）。
4. **改成联合梯度**：在 `train_lora` 里先算出 `grad_A`、`grad_B` 两个矩阵再统一更新，对比与原写法的收敛速度。
5. **运行时 α**：训练好 LoRA 后，用 `alpha ∈ {0, 0.5, 1, 1.5, 2}` 评估误差，体会"α=1 才精确、α 过大就过冲"——对应讲义 Pitfalls 中"把 α 调到 2–3 会过度风格化"。
6. **两个 LoRA 叠加**（讲义练习 2）：分别训练拟合 `Δ₁`、`Δ₂` 的两个 LoRA，再在同一次前向里相加。在这个纯线性的玩具里叠加是精确的；思考为什么在多层非线性网络里不再精确。

---

## 8. 常见坑

- **`A`、`B` 都初始化为 0**：鞍点，永远学不动；标准做法是 `B = 0`、`A` 随机。
- **先合并 `B·A` 再乘**：显式构造 `d×d` 矩阵会失去 LoRA 的计算优势；不合并时应该走 `B·(A·x)`。
- **秩选得比真实需要小**：残差有下界（剩余奇异值平方和），学习率偏大时甚至可能发散。
- **二维列表用 `[[0.0]*c]*r` 构造**：所有行指向同一个列表，改一行等于改全部。本文件用推导式规避了这一点。
- **误读实验结论**：本代码的 LoRA 实验没有 r < 真实秩的对照组，ControlNet 轨迹也没记录前 100 步；用它支撑结论前，先补齐对照。
- **训练和推理的 `α` 不一致**：训练时 `α = 1` 学到的增量，推理时调 `α` 只是线性缩放，不保证效果线性变化。
