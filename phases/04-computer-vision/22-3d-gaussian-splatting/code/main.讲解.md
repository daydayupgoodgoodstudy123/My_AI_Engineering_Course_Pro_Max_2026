# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 22 节 从零实现 3D Gaussian Splatting ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，`device` 写死为 `"cpu"`） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`、`torch.linalg`）、标准库 `math`；无需 CUDA、无需联网

---

## 1. 这份代码在考察什么

3DGS 的工程实现（gsplat、inria 官方代码）都是上千行 CUDA。这份代码把它降到二维、降到一百多行纯 PyTorch，保留"数学上完全一样"的核心：

1. **高斯求值**：用 `einsum` 一次算出所有（高斯, 像素）对的马氏距离二次型 `dᵀΣ⁻¹d`。
2. **可微光栅化**：按深度排序后从前到后 alpha 合成——这正是 3DGS 与 NeRF 共享的体渲染方程 `C = Σ αᵢTᵢcᵢ`。
3. **参数化技巧**：`log_scale → exp`、`logit → sigmoid`、`角度 → 旋转矩阵 → R S Rᵀ`，让优化器在无约束空间里更新、渲染时永远合法。
4. **"梯度下降 + 显式几何图元"**：48 个 2D 高斯通过反向传播自己"找到"红圆和蓝方块的位置、形状和颜色。
5. **球谐函数**：完整的 3 阶（16 个基函数）实现，体现 3D 版本里"颜色随视角变化"的那一块。

> 一句话：**把场景当成一堆可微的彩色椭圆，渲染→对比照片→反向传播→更新椭圆**；3D 版只是多了投影、四元数和球谐。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `eval_2d_gaussian(means, covs, points)` | 函数 | 返回 `(G, H, W)`：每个高斯在每个像素上的未归一化密度 | 高斯足迹 `exp(-½ dᵀΣ⁻¹d)` |
| `rasterise_2d(...)` | 函数 | 算 α → 按 `depths` 排序 → 前到后合成 → `(H, W, 3)` 图像 | 可微光栅化、alpha 合成 |
| `Splats2D` | `nn.Module` 类 | 存 6 组可学习参数，`covs()` 构造协方差，`forward` 调用光栅器 | 每个高斯的参数与参数化 |
| `make_target(size=48)` | 函数（NumPy） | 白底上画红圆和蓝方块，作为拟合目标 | 训练"照片" |
| `sh_degree_3_basis(dirs)` | 函数 | 计算 16 个实球谐基函数在给定方向上的值 | 球谐基 |
| `eval_sh_degree_3(sh_coeffs, dirs)` | 函数 | 基函数与系数做点积，得到 RGB | 视角相关颜色 |
| `main()` | 演示入口 | 300 步拟合 + 打印 MSE；再做一次 SH 形状检查 | 端到端训练 |

数据流：`Splats2D` 参数 →（`exp/sigmoid/R S Rᵀ`）→ `rasterise_2d` → `eval_2d_gaussian` → α 合成 → 图像 → 与 `make_target` 算 MSE → 反向传播 → Adam 更新参数。SH 部分与训练独立，只做形状检查。

---

## 3. 逐段精讲

### 3.1 高斯求值：一个 einsum 算完所有（高斯, 像素）对

```python
def eval_2d_gaussian(means, covs, points):
    G = means.size(0)
    H, W, _ = points.shape
    flat = points.view(-1, 2)
    inv = torch.linalg.inv(covs)
    diff = flat[None, :, :] - means[:, None, :]
    d = torch.einsum("gpi,gij,gpj->gp", diff, inv, diff)
    density = torch.exp(-0.5 * d)
    return density.view(G, H, W)
```

- `points (H, W, 2)` 展平成 `flat (P, 2)`，P = H·W。`view` 要求张量内存连续，这里 `points` 来自 `torch.stack`，满足条件。
- `torch.linalg.inv(covs)`：对 `(G, 2, 2)` 批量求逆，得到每个高斯的 `Σ⁻¹`。
- `diff = flat[None] - means[:, None]`：`(1, P, 2) - (G, 1, 2)` 广播成 `(G, P, 2)`，即"每个高斯中心到每个像素的偏移向量"。
- **einsum 读法**：`"gpi,gij,gpj->gp"` 中 g = 高斯、p = 像素、i/j = 坐标分量。对每个 (g, p)，计算 `Σᵢⱼ diff[g,p,i]·inv[g,i,j]·diff[g,p,j]`，也就是马氏距离平方 `dᵀΣ⁻¹d`。没出现在输出里的 i、j 会被求和掉。
- `exp(-0.5 * d)`：**未归一化**的高斯，中心处为 1（不乘 `1/(2π√|Σ|)`），因为它要作为"覆盖程度"再乘不透明度，峰值为 1 更直观。这与讲义的 `exp(-0.5 * (p - μ')ᵀ Σ'⁻¹ (p - μ'))` 一致。
- ⚠️ 复杂度 O(G·H·W)：每个高斯对每个像素都算一遍。这里 48×48×48 ≈ 11 万个元素无所谓；真实场景（百万高斯 × 百万像素）必须用 3σ 包围盒 + tile 分配只算有效区域（见测验 Q10）。

### 3.2 光栅器：排序 + 前到后 alpha 合成

```python
def rasterise_2d(means, covs, colours, opacities, depths, image_size):
    H, W = image_size
    device = means.device
    yy, xx = torch.meshgrid(
        torch.arange(H, dtype=torch.float32, device=device),
        torch.arange(W, dtype=torch.float32, device=device),
        indexing="ij",
    )
    points = torch.stack([xx, yy], dim=-1)
    densities = eval_2d_gaussian(means, covs, points)
    alphas = opacities[:, None, None] * densities
    alphas = alphas.clamp(0.0, 0.99)
```

- `meshgrid(..., indexing="ij")` 生成行号 `yy` 和列号 `xx`；`torch.stack([xx, yy], dim=-1)` 让每个像素的坐标是 **(x, y)** 顺序，与 `means`（`[W, H]` 缩放的随机初始化）一致。
- `alphas = opacity × density`：讲义的 `αᵢ = opacityᵢ · exp(-½ dᵀΣ'⁻¹d)`。`opacities[:, None, None]` 把 `(G,)` 变成 `(G, 1, 1)` 以便与 `(G, H, W)` 广播。
- `clamp(0.0, 0.99)`：α 上限 0.99（官方 3DGS 也这样做），保证 `1 - α ≥ 0.01`，透射率不会一下变成 0，后面的高斯仍能拿到梯度，数值也更稳定。

```python
    order = torch.argsort(depths)
    alphas = alphas[order]
    colours_sorted = colours[order]

    T = torch.ones(H, W, device=device)
    out = torch.zeros(H, W, 3, device=device)
    for i in range(means.size(0)):
        a = alphas[i]
        out = out + (T * a)[..., None] * colours_sorted[i][None, None, :]
        T = T * (1.0 - a)
    return out
```

- `argsort(depths)` 升序：depth 小的在前（离相机近）。用同一个 `order` 重排 α 和颜色。
- 循环就是 `C = Σ αᵢTᵢcᵢ`、`Tᵢ₊₁ = Tᵢ(1 - αᵢ)`：`T` 是到当前为止"还没被挡住的比例"，每层贡献 `T·α·颜色`，然后 `T` 乘以 `(1 - α)`。
- 写成 `out = out + ...`、`T = T * ...` 而不是原地 `+=`、`*=`：讲义 Step 2 的版本用的是 `out += ...`，对加法来说其实也能正常反向传播（加法的反向不需要保存输入）；但 `T` 绝不能写成 `T *= (1.0 - a)`——上一行的 `T * a` 已经把 `T` 保存下来用于求梯度，原地修改会让 PyTorch 在反向时报"被原地修改"的版本错误。`main.py` 统一用非原地写法，是可微渲染中更稳妥的习惯。
- `(T * a)[..., None]`：`(H, W)` → `(H, W, 1)`，与 `colours_sorted[i][None, None, :]` 的 `(1, 1, 3)` 广播成 `(H, W, 3)`。
- ⚠️ **`depths` 拿不到梯度**：`argsort` 输出整数下标，不可导；`depths` 只经过 `argsort`，所以 `Splats2D.depth` 虽然是 `nn.Parameter`，`grad` 始终是 `None`，Adam 会跳过它，合成顺序全程停留在随机初始值。讲义说"use a learned per-Gaussian scalar for order"，在这份代码里并不成立。真实 3DGS 的深度来自相机坐标系下的 z，随位置 μ 的更新而自然变化（见测验 Q8）。
- ⚠️ **隐含黑色背景**：循环结束后剩余的 `T` 没有乘任何背景色，未被覆盖的像素是黑色。而 `main()` 的目标图是**白底**，于是一部分高斯必须专门去"涂白"背景（见 3.4 节和测验 Q9）。
- 讲义："Not fast — a real implementation uses tile-based CUDA kernels — but exactly the right math and fully differentiable."

### 3.3 `Splats2D`：参数与参数化

```python
class Splats2D(nn.Module):
    def __init__(self, num_splats=64, image_size=64, seed=0):
        super().__init__()
        g = torch.Generator().manual_seed(seed)
        H, W = image_size, image_size
        self.means = nn.Parameter(torch.rand(num_splats, 2, generator=g) * torch.tensor([W, H]))
        self.log_scale = nn.Parameter(torch.full((num_splats, 2), math.log(3.0)))
        self.rot = nn.Parameter(torch.zeros(num_splats))
        self.colour_logits = nn.Parameter(torch.randn(num_splats, 3, generator=g) * 0.3)
        self.opacity_logit = nn.Parameter(torch.zeros(num_splats))
        self.depth = nn.Parameter(torch.rand(num_splats, generator=g))
```

| 参数 | 形状 | 初始值 | 渲染时映射 | 对应 3D 参数 |
|------|------|--------|-----------|-------------|
| `means` | `(G, 2)` | 图内均匀随机 | 直接使用 | 位置 μ `(3,)` |
| `log_scale` | `(G, 2)` | `ln 3` | `exp` → σ = 3 像素 | log 尺度 `(3,)` |
| `rot` | `(G,)` | 0 | `cos/sin` → 旋转矩阵 | 四元数 `(4,)` |
| `colour_logits` | `(G, 3)` | `0.3 × N(0,1)` | `sigmoid` → 约 0.5 的灰色 | SH 系数 `(48,)` |
| `opacity_logit` | `(G,)` | 0 | `sigmoid` → 0.5 | 不透明度 `(1,)` |
| `depth` | `(G,)` | `U(0,1)` | 只用于排序（无梯度） | 由相机 z 决定 |

- 每个 2D 高斯 10 个数，48 个高斯共 480 个参数（其中 48 个 `depth` 实际上不会被训练）。
- 用独立的 `torch.Generator` 初始化，换 `seed` 就能得到不同的初始布局，且不受全局随机状态影响。
- 讲义强调的模式："unconstrained parameters mapped through the right activation at render time"——`exp` 保证尺度为正，`sigmoid` 保证颜色和不透明度在 (0, 1)。
- 与讲义 Step 3 相比，`main.py` 把初始尺度从 `ln 2` 改为 `ln 3`、颜色噪声从 0.5 改为 0.3，默认高斯数从 128 改为 64（`main` 里实际用 48）。

### 3.4 协方差构造：`R S Rᵀ`

```python
    def covs(self):
        s = torch.exp(self.log_scale)
        c, si = torch.cos(self.rot), torch.sin(self.rot)
        R = torch.stack([
            torch.stack([c, -si], dim=-1),
            torch.stack([si, c], dim=-1),
        ], dim=-2)
        S = torch.diag_embed(s ** 2)
        return R @ S @ R.transpose(-1, -2)

    def forward(self, image_size):
        covs = self.covs()
        colours = torch.sigmoid(self.colour_logits)
        opacities = torch.sigmoid(self.opacity_logit)
        return rasterise_2d(self.means, covs, colours, opacities, self.depth, image_size)
```

- 内层 `stack(dim=-1)` 拼出每一行 `[c, -s]`、`[s, c]`，外层 `stack(dim=-2)` 把两行叠成 `(G, 2, 2)` 的旋转矩阵 `R = [[cosθ, -sinθ], [sinθ, cosθ]]`。
- `torch.diag_embed(s ** 2)`：把 `(G, 2)` 变成 `(G, 2, 2)` 的对角矩阵 `diag(σx², σy²)`。这里直接用平方，等价于讲义 3D 公式 `R S Sᵀ Rᵀ` 中的 `S Sᵀ`。
- `R @ S @ R.transpose(-1, -2)`：批量矩阵乘法，`transpose(-1, -2)` 只交换最后两维（对每个高斯求 Rᵀ）。结果对任意 `rot`、`log_scale` 都是对称正定的——这就是用"旋转 + 尺度"而不是直接学习 Σ 元素的原因。
- 3D 版本的唯一区别：R 由单位四元数构造（3×3），S 有 3 个轴。

### 3.5 拟合目标

```python
def make_target(size=48):
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    img = np.ones((size, size, 3), dtype=np.float32)
    mask = (xx - 15) ** 2 + (yy - 15) ** 2 < 8 ** 2
    img[mask] = [0.95, 0.2, 0.15]
    mask = (np.abs(xx - 34) < 6) & (np.abs(yy - 32) < 6)
    img[mask] = [0.2, 0.35, 0.95]
    return torch.from_numpy(img)
```

- 白底（`np.ones`），圆心 (15, 15)、半径 8 的红圆，中心 (34, 32)、边长 11 像素的蓝方块。
- `img[mask] = [r, g, b]`：布尔掩码选出 `(k, 3)` 的像素，用长度 3 的列表广播赋值。
- `&` 是逐元素"与"，`np.abs(xx - 34) < 6` 两侧要加括号，因为 `&` 的优先级高于 `<`。
- ⚠️ 与讲义 Step 4 不同：讲义用的是黑底（`np.zeros`），与光栅器的隐含黑色背景一致；这里白色像素约占 86%，而初始化时大部分像素没被覆盖、渲染成黑色。我用 NumPy 按相同的初始化分布模拟了初始渲染，MSE 约 0.56–0.63（全黑图的 MSE 为 0.909）。要把这 86% 的白色"涂"出来，高斯得变大、变不透明、变白——给光栅器加背景色项（`out + T[..., None] * bg`）会让任务轻松得多。

### 3.6 球谐函数：3 阶 16 个基

```python
def sh_degree_3_basis(dirs):
    x, y, z = dirs[..., 0], dirs[..., 1], dirs[..., 2]
    # ...（常数 C0、C1、C2、C3 省略）
    basis = torch.stack([
        torch.full_like(x, C0),
        -C1 * y, C1 * z, -C1 * x,
        C2[0] * xy, C2[1] * yz, C2[2] * (2 * z2 - x2 - y2), C2[3] * xz, C2[4] * (x2 - y2),
        -C3[0] * y * (3 * x2 - y2), C3[1] * xy * z, -C3[2] * y * (4 * z2 - x2 - y2),
        C3[3] * z * (2 * z2 - 3 * x2 - 3 * y2), -C3[4] * x * (4 * z2 - x2 - y2),
        C3[5] * z * (x2 - y2), -C3[6] * x * (x2 - 3 * y2),
    ], dim=-1)
    return basis


def eval_sh_degree_3(sh_coeffs, dirs):
    basis = sh_degree_3_basis(dirs)
    return torch.einsum("...b,...bc->...c", basis, sh_coeffs)
```

- 第 0 阶 1 个（常数，`C0 = 1/(2√π)`）、第 1 阶 3 个（x、y、z 的线性项）、第 2 阶 5 个、第 3 阶 7 个，共 `(3+1)² = 16` 个。讲义正文只写到 2 阶并说"full 16-coefficient version in the code file"，这里就是完整版。
- `torch.full_like(x, C0)`：生成与 `x` 同形、全为 `C0` 的张量，让常数项也有正确的批量形状。
- `einsum("...b,...bc->...c")`：`...` 表示任意多个前导维度，并且这些维度可以**广播**。`main` 里 `basis` 是 `(3, 16)`、`sh` 是 `(1, 16, 3)`，前导维 `(3,)` 与 `(1,)` 广播成 `(3,)`，对 b（16 个基）求和，输出 `(3, 3)`：3 个方向 × RGB。
- 我用 NumPy 做蒙特卡洛积分（200 万个均匀方向）验证：这 16 个基函数的 Gram 矩阵 `∫YᵢYⱼdΩ` 与单位阵的最大偏差约 0.0025，确实是**正交归一**基。
- ⚠️ 符号约定细节：1 阶和 3 阶的奇数项带负号（Condon–Shortley 相位），与 inria 官方实现一致；但 2 阶的 `yz`、`xz` 两项这里用的是正号，而官方实现中对应常数为 `-1.0925…`。从零学习系数时这无关紧要（基函数取反仍然正交归一，系数会学成相反数）；但如果加载官方训练出的 `.ply` 文件里的 SH 系数，这两项会算反，颜色出错。
- ⚠️ 本文件只做了形状检查，SH 没有接入 2D 训练（2D 版本没有"视角方向"）。讲义练习 2 让你给 2D 版本加一个标量"视角"来体验这一点。

### 3.7 主流程

```python
    target = make_target(48).to(device)
    model = Splats2D(num_splats=48, image_size=48).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=0.08)

    print("Fitting 48 2D Gaussians to a red circle + blue square...")
    for step in range(300):
        pred = model((48, 48))
        loss = F.mse_loss(pred, target)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 50 == 0:
            print(f"  step {step:3d}  mse {loss.item():.4f}")

    with torch.no_grad():
        final = F.mse_loss(model((48, 48)), target).item()
    print(f"final mse: {final:.4f}")
```

- 学习率 0.08 偏大：位置以像素为单位（0–48），太小的学习率移动太慢。但所有参数共用一个学习率是简化——官方 3DGS 给位置、尺度、旋转、不透明度、颜色分别设置学习率，位置的学习率还会随训练衰减。
- 没有致密化和剪枝：48 个高斯从头到尾固定，这正是讲义"Densification and pruning"一节要解决的问题。
- `final` 在 `no_grad` 下再渲染一次，得到最后一步更新**之后**的 MSE（循环里打印的是更新**之前**的损失）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 2D 代替 3D | 去掉投影、四元数，聚焦光栅化与可微合成 | 3D 需要 `Σ' = J W Σ Wᵀ Jᵀ` 投影和相机模型 |
| 稠密 O(G·H·W) 求值 | 一个 einsum 写完，便于理解 | 生产用 3σ 包围盒 + 16×16 tile + CUDA |
| Python 循环做合成 | 与公式一一对应 | 慢；生产在 GPU 上每 tile 并行、提前终止 |
| α 上限 0.99 | 透射率不归零，梯度可以继续流动 | 官方实现还会跳过 α < 1/255 的高斯 |
| `exp` / `sigmoid` 参数化 | 无约束优化，渲染结果永远合法 | — （这就是生产标准做法） |
| 用可学习标量 `depth` 排序 | 2D 中没有真实深度 | `argsort` 不可导，`depth` 实际不会被学习 |
| 无背景色项 | 代码最短 | 与白底目标不匹配；生产中有可配置背景色 |
| 统一学习率、无致密化 | 演示简洁 | 生产按参数分组设学习率，并做 clone/split/prune |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组解包 | `H, W, _ = points.shape`、`c, si = torch.cos(...), torch.sin(...)` | 一次给多个变量赋值 |
| 默认参数 | `def __init__(self, num_splats=64, image_size=64, seed=0)` | 调用时可覆盖 |
| `math.log` | `math.log(3.0)` | 标准库自然对数，用于初始化 log 尺度 |
| 类继承与 `super()` | `class Splats2D(nn.Module)` | 注册参数 |
| `nn.Parameter` | `self.depth = nn.Parameter(...)` | 声明为可学习参数（但能否学习取决于是否有梯度） |
| 嵌套 `torch.stack` | `torch.stack([torch.stack([c, -si], -1), torch.stack([si, c], -1)], -2)` | 先拼行、再叠成矩阵 |
| `@` 批量矩阵乘 | `R @ S @ R.transpose(-1, -2)` | 对最后两维做矩阵乘，前面的维度批量处理 |
| 负数维度下标 | `transpose(-1, -2)`、`dim=-1` | 从后往前数维度 |
| `None` 增加维度 | `flat[None, :, :]`、`opacities[:, None, None]` | 等价于 `unsqueeze`，用于广播 |
| `...`（Ellipsis） | `(T * a)[..., None]`、`dirs[..., 0]`、`"...b,...bc->...c"` | 代表"前面所有维度" |
| `einsum` | `torch.einsum("gpi,gij,gpj->gp", diff, inv, diff)` | 用下标字符串描述张量缩并 |
| 列表常量与下标 | `C2 = [1.09..., ...]`、`C2[0] * xy` | 普通 Python 列表存放常数 |
| 布尔掩码与 `&` | `(np.abs(xx - 34) < 6) & (np.abs(yy - 32) < 6)` | 逐元素与；注意加括号 |
| `with` 上下文管理器 | `with torch.no_grad():` | 评估时不建计算图 |
| f-string 与 `tuple()` | `{tuple(rgb.shape)}`、`{loss.item():.4f}` | `torch.Size` 转元组打印 |
| 一行多语句 | `opt.zero_grad(); loss.backward(); opt.step()` | 分号分隔 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 我用 NumPy 按相同逻辑验证了：SH 基函数的正交归一性、`einsum` 广播后的输出形状 `(3, 3)`、初始渲染的 MSE 量级、以及两层 alpha 合成的数值。根据代码，输出格式如下：

```text
Fitting 48 2D Gaussians to a red circle + blue square...
  step   0  mse 0.????
  step  50  mse 0.????
  step 100  mse 0.????
  step 150  mse 0.????
  step 200  mse 0.????
  step 250  mse 0.????
final mse: 0.????

Spherical harmonics sanity check:
  SH(16, 3) evaluated at 3 directions -> (3, 3)
```

- **step 0** 的 MSE 预计在 0.6 左右（NumPy 按相同初始化分布模拟 50 次：均值约 0.59，范围 0.56–0.63）。原因：初始高斯 σ = 3、不透明度 0.5，只覆盖少量像素，其余像素渲染为黑色，而目标约 86% 是白色。
- 之后 MSE 应持续下降（6 行日志，每 50 步一次），具体降到多少取决于 PyTorch 的随机初始化和优化过程，这里不编造数值。由于隐含黑色背景，这 48 个高斯要同时负责"涂白背景"和"画两个形状"，最终 MSE 很可能明显高于讲义中黑底版本能达到的水平。
- **最后一行是确定值** `(3, 3)`：3 个方向，每个方向一个 RGB。`sh` 是随机系数，所以只检查形状，不检查数值。
- 运行时间：300 步 × 48 次合成循环，每次处理 48×48 像素，CPU 上几秒到几十秒。

---

## 7. 动手改一改

1. **加背景色**：按测验 Q9 给 `rasterise_2d` 加 `bg` 参数，用 `bg=torch.ones(3)` 重新训练，比较最终 MSE。
2. **验证 `depth` 没被学习**：训练后打印 `model.depth.grad`（应为 `None`），并比较训练前后 `model.depth` 是否完全相同；再把它改成 `self.register_buffer("depth", ...)`，确认训练结果不受影响。最后思考：为什么真实 3DGS 不需要深度梯度？
3. **高斯数量消融**（讲义练习 1）：`num_splats` 取 16、64、256，画 MSE–步数曲线，找到收益递减点。
4. **简易致密化**：每 100 步找出位置梯度最大的 8 个高斯，在附近复制一份（尺度缩小到 1/1.6），同时删除不透明度低于 0.05 的高斯；注意每次增删后要重建优化器。
5. **分组学习率**：用 `torch.optim.Adam([{"params": [model.means], "lr": 0.5}, {"params": [model.log_scale, model.rot], "lr": 0.05}, ...])` 给不同参数不同学习率，观察收敛速度。
6. **视角相关颜色**（讲义练习 2）：给每个高斯加一组系数，让颜色是标量"视角"θ 的 2 阶谐波函数 `c(θ) = a₀ + a₁cosθ + b₁sinθ + a₂cos2θ + b₂sin2θ`，用两张不同的目标图分别对应 θ = 0 和 θ = π/2 训练。

---

## 8. 常见坑

- **以为 `nn.Parameter` 就一定会被学习**：只经过 `argsort`、`argmax`、取整等不可导操作的参数没有梯度；训练后检查 `p.grad is None` 能快速发现问题。
- **原地操作破坏计算图**：在可微渲染里对需要反向传播的张量用 `+=`、`*=`，可能报错或得到错误梯度。
- **背景色不一致**：渲染器的背景与训练图片的背景不同（黑 vs 白），会让大量容量浪费在"补背景"上。
- **(x, y) 与 (row, col) 混用**：`means` 是 (x, y)，`meshgrid(indexing="ij")` 给出 (row, col)，代码用 `stack([xx, yy])` 对齐；搞反了高斯会出现在转置位置。
- **协方差变成奇异矩阵**：尺度趋近 0 时 `Σ⁻¹` 极大，数值爆炸；生产中会限制最小尺度，或在投影后给 2D 协方差加一个小的对角项。
- **SH 符号约定不一致**：自己实现的基函数与他人训练的系数约定不同，加载后颜色出错。
