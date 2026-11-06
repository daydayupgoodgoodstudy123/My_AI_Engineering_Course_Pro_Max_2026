# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 12 节 3D 生成 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，不到 1 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

3D Gaussian Splatting（3DGS）的核心只有两件事：**把一堆高斯"画"出来（前向渲染）**，以及**通过比较渲染结果与目标图像来调整高斯参数（拟合）**。这份代码把它缩到 2D：

1. **用高斯表示图像**：12×12 的目标图由两个模糊亮斑组成，用 2/4/8 个各向同性的 2D 高斯去逼近。
2. **前向渲染**：每个像素的值 = 所有高斯在该点的贡献之和。
3. **可微拟合**：用**有限差分**估计损失对每个参数（位置、σ、颜色）的梯度，再做梯度下降。
4. **"高斯越多，表达能力越强"**：比较 2、4、8 个高斯的最终 MSE。
5. **ASCII 可视化**：在终端里直接看拟合效果。

> 一句话：**3DGS = 可微的"高斯画笔" + 梯度下降**。真实系统把这里的"相加"换成按深度排序的 alpha 合成，把有限差分换成 CUDA 上的解析反向传播，把 8 个 2D 高斯换成 100 万个 3D 高斯。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SIZE = 12` | 常量 | 图像边长 | 渲染分辨率 |
| `make_target(size)` | 函数 | 生成目标图：左上亮斑 + 右下暗斑 | 真实照片（监督信号） |
| `init_gaussians(n, rng)` | 函数 | 随机初始化 n 个高斯（位置、σ、颜色） | 3DGS 初始化（真实系统常从 SfM 点云初始化） |
| `gaussian_value(x, y, g)` | 函数 | 计算一个高斯在像素 (x, y) 的贡献 | 单个 splat 的足迹 |
| `render(gaussians)` | 函数 | 每个像素累加所有高斯的贡献 | 前向渲染（真实系统用 alpha 合成） |
| `mse(a, b)` | 函数 | 两幅图的均方误差 | 光度损失（真实 3DGS：L1 + D-SSIM） |
| `finite_diff_step(gaussians, target, lr, eps)` | 函数 | 前向差分估计梯度并逐参数更新 | 梯度下降（真实系统用自动微分） |
| `ascii_img(img, chars)` | 函数 | 把图像按亮度映射成字符 | 可视化 |
| `main()` | 函数 | 打印目标图 → 分别拟合 2/4/8 个高斯各 30 步 → 打印 MSE 与 ASCII 图 | 实验编排 |

调用关系：`main → init_gaussians → (finite_diff_step → render → gaussian_value, mse) × 30 → ascii_img(render(...))`。

---

## 3. 逐段精讲

### 3.1 目标图像：`make_target`

```python
SIZE = 12  # small image grid for speed


def make_target(size):
    """Target: a smooth bright blob in the upper-left, dimmer one in the lower-right."""
    target = [[0.0] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            d1 = ((x - 3) ** 2 + (y - 3) ** 2) / 6.0
            d2 = ((x - 8) ** 2 + (y - 8) ** 2) / 8.0
            target[y][x] = math.exp(-d1) + 0.5 * math.exp(-d2)
    return target
```

- 目标本身就是**两个高斯之和**：中心 (3, 3)、峰值 1，`exp(−d²/6)` 对应 `σ² = 3`（σ ≈ 1.73）；中心 (8, 8)、峰值 0.5，`σ² = 4`（σ = 2）。所以理论上 **2 个高斯就能完美拟合**（MSE = 0），这是检验优化器好坏的绝佳基准。
- 图像用 `img[y][x]` 存储：先行（y）后列（x），与 NumPy、图像库的习惯一致。
- 全零图像与目标的 MSE 是 0.0889（我们在临时副本中算的），可以作为"什么也没学到"的参照。

### 3.2 高斯与初始化：`init_gaussians` / `gaussian_value`

```python
def init_gaussians(n, rng):
    return [{
        "pos": [rng.uniform(2, SIZE - 2), rng.uniform(2, SIZE - 2)],
        "sigma": rng.uniform(0.8, 2.5),
        "color": rng.uniform(0.2, 0.8),
    } for _ in range(n)]


def gaussian_value(x, y, g):
    dx = x - g["pos"][0]
    dy = y - g["pos"][1]
    d2 = dx * dx + dy * dy
    return g["color"] * math.exp(-d2 / (2 * g["sigma"] ** 2))
```

- 每个高斯是一个字典，共 4 个参数：位置 (x, y)、尺度 σ、颜色（灰度强度）。
- 与真实 3DGS（每个高斯 59 个参数）对比：

| 本代码 | 真实 3DGS |
|--------|----------|
| 2D 位置 `pos` | 3D 位置（3） |
| 各向同性 `sigma` | 各向异性协方差：四元数（4）+ 缩放（3） |
| 灰度 `color` | 3 阶球谐颜色（48，随视角变化） |
| 无 | 不透明度（1） |

- ⚠️ 讲义 Build It 说要优化 "covariances"，但代码只有一个标量 `sigma`，是圆形高斯，不能表示椭圆和旋转。
- `gaussian_value` 就是 `c · exp(−‖p − μ‖² / 2σ²)`，与讲义 Step 1 的 `gaussian_at` 相比多乘了颜色。
- ⚠️ `color` 和 `sigma` 都没有约束：颜色可以变成负数（第 6 节会看到后果）；`sigma` 如果被更新到 0 会除零。真实系统用 `exp(scale)`、`sigmoid(opacity)` 这样的参数化来保证合法范围。

### 3.3 渲染：`render`

```python
def render(gaussians):
    img = [[0.0] * SIZE for _ in range(SIZE)]
    for y in range(SIZE):
        for x in range(SIZE):
            for g in gaussians:
                img[y][x] += gaussian_value(x, y, g)
    return img
```

- 三重循环：每个像素 × 每个高斯，复杂度 `O(SIZE² · n)`。
- ⚠️ 这里是**直接相加**，讲义也说明了 "Our 2D toy just sums"。真实 3DGS 先按深度排序，再做 alpha 合成 `C = Σ cᵢ·αᵢ·Π_{j<i}(1 − αⱼ)`，前面的高斯会遮挡后面的。2D 玩具没有深度，相加是最自然的简化。
- 真实系统还会把屏幕切成 16×16 的 tile，每个 tile 只处理与它相交的高斯，而不是"每个像素遍历所有高斯"——这是 3DGS 能实时渲染的关键之一。

### 3.4 损失与梯度：`mse` / `finite_diff_step`

```python
def finite_diff_step(gaussians, target, lr, eps=0.1):
    base = render(gaussians)
    base_loss = mse(base, target)
    for g in gaussians:
        for key in ("pos", "sigma", "color"):
            if isinstance(g[key], list):
                for i in range(len(g[key])):
                    g[key][i] += eps
                    up = mse(render(gaussians), target)
                    g[key][i] -= eps
                    grad = (up - base_loss) / eps
                    g[key][i] -= lr * grad
            else:
                g[key] += eps
                up = mse(render(gaussians), target)
                g[key] -= eps
                grad = (up - base_loss) / eps
                g[key] -= lr * grad
    return base_loss
```

- **前向差分**：`∂L/∂θᵢ ≈ (L(θ + eps·eᵢ) − L(θ)) / eps`。把参数加 eps → 重新渲染 → 算损失 → 恢复参数。
- `isinstance(g[key], list)` 区分向量参数（`pos`）和标量参数（`sigma`、`color`），两个分支逻辑相同。
- **开销**：每一步要做 `4n + 1` 次完整渲染，每次 `O(SIZE²·n)`，总计 `O(SIZE²·n²)`。n 增大 8 倍，单步开销约增大 64 倍。100 万个高斯时有限差分完全不可行，这就是真实系统必须用**反向传播**的原因（测验 Q11 给出了颜色的解析梯度）。
- ⚠️ **基线过期的 bug**：`base_loss` 只在开头算一次，但每个参数的梯度一算完就**立即更新**。到后面的参数时，`up` 是在"已经被前面更新过的参数"上算的，减去的却是更新前的 `base_loss`，于是梯度里混入了"前面更新带来的损失变化 / eps"。参数少时影响有限；我们在临时副本中实测，按 `main` 的方式用 **64 个高斯**（讲义练习 1 的要求）跑，第 0 步就有一个 `sigma` 被推到约 `10²³⁸`，随后抛出 `OverflowError`。改成"先基于同一基线算完所有梯度、再统一更新"后，64 个高斯 30 步可以收敛到 MSE ≈ 0.0121（测验 Q9）。
- ⚠️ `eps = 0.2`（`main` 中传入）很大，前向差分有 `O(eps)` 的截断误差；中心差分 `(L(θ+eps) − L(θ−eps)) / 2eps` 的误差是 `O(eps²)`。
- 返回的是本步**更新前**的损失，所以 `main` 打印的 "final loss" 其实是第 30 步更新之前的值（与更新后差别很小：例如 8 个高斯时报告 0.0365，更新后实测 0.0361）。

### 3.5 可视化：`ascii_img`

```python
def ascii_img(img, chars=" .:;+*#@"):
    peak = max(max(row) for row in img) or 1.0
    lines = []
    for row in img:
        line = "".join(chars[min(len(chars) - 1, int(v / peak * (len(chars) - 1)))]
                       for v in row)
        lines.append(line)
    return "\n".join(lines)
```

- 8 个字符从暗到亮：空格 `.` `:` `;` `+` `*` `#` `@`。每个像素按 `v / peak` 映射到 0–7 的下标。
- `max(...) or 1.0`：如果最大值是 0（全黑图），用 1.0 防止除零（`0.0` 在布尔上下文中为假）。
- **每张图按自己的峰值归一化**，所以不同图之间的亮度不可直接比较，只能看形状。
- ⚠️ **负值 bug**：`min(...)` 只限制了上界。像素为负时 `int(...)` 是负数，Python 的负下标会从字符串**末尾**取字符，于是负像素被画成 `@`、`#` 这样**最亮**的字符。应改为 `max(0, min(len(chars) - 1, ...))`（见第 6 节与测验 Q10）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 2D、12×12 图像 | 纯 Python 也能瞬间跑完 | 没有相机、投影、深度和遮挡 |
| 目标本身是两个高斯之和 | 有已知最优解（2 个高斯、MSE = 0），便于判断优化器好坏 | 真实场景的结构远比这复杂 |
| 各向同性 σ | 参数少、易理解 | 真实 3DGS 用各向异性协方差（四元数 + 缩放） |
| 直接相加 | 2D 无深度，最简单 | 真实系统按深度排序 + alpha 合成 |
| 有限差分求梯度 | 不需要推导反向传播 | `O(n²)` 开销、截断误差、基线过期的 bug；生产中用自动微分 / CUDA 反向传播 |
| 参数无约束 | 代码短 | 颜色变负、σ 可能为 0；生产中用 `exp` / `sigmoid` 参数化 |
| 不做致密化与剪枝 | 固定高斯数量便于比较 | 真实 3DGS 依赖致密化 + 剪枝控制数量和质量 |
| ASCII 输出 | 无需绘图库 | 负值显示错误；分辨率低 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 + 行尾注释 | `SIZE = 12  # small image grid for speed` | 全局配置 |
| 二维列表 | `[[0.0] * size for _ in range(size)]` | 每行独立的列表；`img[y][x]` 先行后列 |
| 字典表示对象 | `{"pos": [...], "sigma": ..., "color": ...}` | 轻量的"结构体"，用键名访问字段 |
| 推导式生成字典列表 | `[{...} for _ in range(n)]` | 一次创建 n 个高斯 |
| `rng.uniform(a, b)` | `rng.uniform(0.8, 2.5)` | 区间内均匀分布的浮点数 |
| 元组作为可迭代对象 | `for key in ("pos", "sigma", "color")` | 遍历固定的键名 |
| `isinstance` | `isinstance(g[key], list)` | 区分向量与标量参数 |
| 原地修改与恢复 | `g[key][i] += eps` … `g[key][i] -= eps` | 有限差分的"扰动—恢复"模式 |
| 嵌套 `max` + 生成器 | `max(max(row) for row in img)` | 二维列表的最大值 |
| `or` 提供默认值 | `peak = ... or 1.0` | 左边为假值（如 0.0）时取右边 |
| 负下标 | `chars[-1]` 即 `'@'` | 从末尾取值——也是本文件 ASCII bug 的根源 |
| `str.join` + 生成器 | `"".join(chars[...] for v in row)` | 拼接字符串 |
| `"\n".join(lines)` | `ascii_img` 末尾 | 多行拼成一个字符串 |
| f-string 格式符 | `f"{loss:.4f}"` | 保留 4 位小数 |
| `random.Random(seed)` | `random.Random(7 + n)` | 每个 n 使用独立、可复现的随机源 |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
=== target image ===
  ...
 .;;;.
.;***;.
.;*@*;.
.;***;.
 .;;;:....
  ......:..
     ..:;:..
     .:;;;:.
     ..:;:..
      ..:..
       ...

=== fit 2 Gaussians ===
final loss (MSE): 0.0602
...（亮斑出现在第 5 行附近、两个目标亮斑之间）

=== fit 4 Gaussians ===
final loss (MSE): 0.0578
...（亮斑跑到了右下方）

=== fit 8 Gaussians ===
final loss (MSE): 0.0365
   .:::. @#@
  .:+++: ###
  :;*#*; #**
 .:+*@#+.@##
  :;*##+:  @
  .:+++;::.
   .:;;:;++:
   ..:::;++:
   ...
```

逐段解读：

- **目标图**：左上（中心约在第 3 行第 3 列）是亮斑 `@`，右下是较暗的 `;` 斑。
- **2 个高斯，MSE 0.0602**：理论上 2 个高斯能做到 0，但 30 步只从全零水平（0.0889）降了一点，亮斑停在两个目标中间。原因：步数少、`eps = 0.2` 的粗糙前向差分、基线过期的更新方式。
- **4 个高斯，MSE 0.0578**：亮斑偏到了右下，左上的主亮斑反而没拟合好。
- **8 个高斯，MSE 0.0365**：左侧终于出现了主亮斑的形状，但**右上角的 `@#@`、`###` 是假象**——目标在那里几乎为 0。实际情况是：8 个高斯中有负颜色（−0.37、−0.18），右上角的像素值是负数（最小约 −0.246），被 `ascii_img` 的负下标映射成了最亮的字符。
- **结论**：MSE 确实随高斯数量增加而下降，但这个优化器很弱。我们在临时副本中用中心差分（`eps = 1e-3`）、统一更新、跑 300 步，2/4/8 个高斯的 MSE 可以降到 0.034 / 0.021 / 0.005。

---

## 7. 动手改一改

1. **修复 ASCII 负值 bug**：把下标夹到 `[0, 7]`，重新看 8 个高斯的输出，确认右上角其实是"暗"的。
2. **修复基线过期**：先算所有梯度再统一更新（测验 Q9 有参考代码），用 64 个高斯重跑讲义练习 1，确认不再溢出（注意 64 个高斯时有限差分很慢，30 步约需几十秒）。
3. **约束参数**：把颜色改成 `exp(log_color)`、σ 改成 `exp(log_sigma)` 来优化，保证两者为正；比较 MSE 与图像。
4. **换成解析梯度**：先为颜色写解析梯度（测验 Q11），再推导位置和 σ 的梯度：`∂B/∂μx = B·(x − μx)/σ²`，`∂B/∂σ = B·d²/σ³`，与数值梯度对比。
5. **alpha 合成版本**：给每个高斯加一个"深度"和不透明度 `α = sigmoid(a)`，按深度排序后用 `C = Σ cᵢαᵢΠ(1−αⱼ)` 渲染，体会遮挡效果。
6. **讲义练习 2（彩色）**：把 `color` 改成 RGB 三元组，目标图改成两个不同颜色的亮斑，验证拟合结果的颜色是否正确。

---

## 8. 常见坑

- **顺序更新却用同一个基线损失**：这是"伪梯度"，参数一多就可能发散甚至溢出。
- **有限差分步长太大**：`eps = 0.2` 相对于 σ ≈ 1–2 的尺度来说很粗；太小又会被浮点误差淹没，中心差分 + `1e-3 ~ 1e-5` 通常更好。
- **参数越界**：负颜色、σ → 0、σ 爆炸。用 `exp` / `sigmoid` 参数化，或者每步之后裁剪到合法范围。
- **负下标的隐蔽行为**：`chars[-1]` 不会报错，只会悄悄返回最后一个字符。处理下标时要同时检查上下界。
- **把相加当成 alpha 合成**：真实渲染中前面的高斯会遮挡后面的，不能简单叠加，否则颜色会"过曝"。
- **只看 MSE 不看图**（反过来也一样）：8 个高斯的 MSE 最低，但图像中存在负亮度区域；可视化本身也可能有 bug。
