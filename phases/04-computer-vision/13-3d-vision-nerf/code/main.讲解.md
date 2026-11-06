# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 13 节 3D 视觉——点云和 NeRF ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，CPU 几秒跑完） ｜ **依赖**：`torch`（`torch.nn`）、标准库 `math`；无需联网

---

## 1. 这份代码在考察什么

一个文件里放了 3D 视觉两条路线的最小零件：点云分类（PointNet）和神经辐射场（NeRF）的三个核心步骤。

1. **置换不变性**：PointNet 怎样靠"逐点共享 MLP + max pool"让输出与点序无关，以及如何写一个检查函数去**验证**这一点。
2. **1×1 卷积 = 逐点 MLP**：把点云排成 `(N, 3, num_points)`，用 `Conv1d(kernel=1)` 高效地对每个点跑同一个 MLP。
3. **位置编码**：把 3D 坐标抬升到 60 维 Fourier 特征，克服 MLP 的低频偏置。
4. **NeRF 的网络分工**：密度 σ 只看位置，颜色同时看位置和视角方向。
5. **可微体渲染**：用 `cumprod` 算透射率，把一条光线上 64 个采样点合成一个像素颜色和一个深度。

> 一句话：**点云和 NeRF 都在回答"空间里哪里有什么"**——前者从传感器给的无序点出发，后者让一个 MLP 本身成为场景。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PointNet` | `nn.Module` | 两段共享 MLP（1×1 Conv1d）→ max pool → 3 层 MLP 分类头 | 点云分类、对称函数技巧 |
| `positional_encoding(x, L)` | 函数 | `(..., D) → (..., D·2·L)` 的 sin/cos 编码 | Fourier features、谱偏置 |
| `TinyNeRF` | `nn.Module` | 4 层 trunk → 密度头；trunk 特征 + 视角编码 → 颜色头 | NeRF MLP |
| `volumetric_render(sigma, rgb, t_vals)` | 函数 | 由密度和颜色计算权重、像素颜色、深度 | 体渲染方程 |
| `permutation_invariance_check()` | 函数 | 打乱点序前后输出的最大差 | 置换不变性的单元测试 |
| `main()` | 演示入口 | 依次跑四个部分并打印形状/数值 | — |

数据流：PointNet 部分独立；NeRF 部分在真实系统中是串起来的——光线上的采样点 `x` 和方向 `d` → `TinyNeRF` 输出 `(σ, rgb)` → `volumetric_render` 得到像素。本文件为了简单，体渲染直接用随机的 `σ`、`rgb` 演示，没有把两者接起来。

---

## 3. 逐段精讲

### 3.1 `PointNet`：共享 MLP + 对称聚合

```python
class PointNet(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.mlp1 = nn.Sequential(
            nn.Conv1d(3, 64, 1), nn.BatchNorm1d(64), nn.ReLU(inplace=True),
            nn.Conv1d(64, 64, 1), nn.BatchNorm1d(64), nn.ReLU(inplace=True),
        )
        self.mlp2 = nn.Sequential(
            nn.Conv1d(64, 128, 1), nn.BatchNorm1d(128), nn.ReLU(inplace=True),
            nn.Conv1d(128, 1024, 1), nn.BatchNorm1d(1024), nn.ReLU(inplace=True),
        )
        self.head = nn.Sequential(
            nn.Linear(1024, 512), nn.BatchNorm1d(512), nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.mlp1(x)
        x = self.mlp2(x)
        x = torch.max(x, dim=-1)[0]
        return self.head(x)
```

- **输入布局**：`x` 是 `(N, 3, num_points)`，通道（xyz）在中间、点在最后——这是 `Conv1d` 的约定 `(batch, channels, length)`。从文件读入的点云通常是 `(num_points, 3)`，要先 `transpose`。
- **`Conv1d(in, out, 1)`**：kernel 大小为 1，意味着每个位置（每个点）的输出只取决于这个点自己的输入通道，且所有点共用同一组权重——这正是讲义说的"shared MLP"。之所以用卷积而不是 `Linear`，是因为卷积直接在 `(N, C, L)` 上并行处理所有点，不需要 reshape。
- **维度路线**：`3 → 64 → 64 → 128 → 1024`，与讲义的 mermaid 图一致。最后升到 1024 维，是为了给 max pool 足够多的"特征槽位"——每个槽位最终只保留一个点的最大响应。
- **`torch.max(x, dim=-1)[0]`**：在点维度上逐通道取最大值，`(N, 1024, num_points) → (N, 1024)`。`torch.max` 带 `dim` 时返回 `(values, indices)` 二元组，`[0]` 取值。`indices` 其实很有用：它告诉你每个特征维由哪个点"胜出"，即 PointNet 论文里的关键点集。
- **为什么置换不变**：在 max 之前全是逐点运算（卷积核大小 1、BN、ReLU），打乱点序只会让特征矩阵的列同步打乱；max 是对称函数，与列的顺序无关。
- **head**：`Linear + BN + ReLU + Dropout(0.3)` 两次，再接输出层。Dropout 防止全局特征过拟合。
- ⚠️ 刻意的简化：原版 PointNet 还有两个 T-Net（学一个 3×3 和 64×64 的对齐矩阵，并对后者加正交正则），本代码省略了；也没有 PointNet++ 的局部邻域结构。
- ⚠️ 参数量：按层计算为 **807,626**（num_classes=10），约 0.81M，讲义写的 "About 1.6M" 偏大一倍。参数大头是 head 里的 `Linear(1024, 512)`（524,800）。

### 3.2 `positional_encoding`：把坐标变成多频率特征

```python
def positional_encoding(x, L=10):
    freqs = 2.0 ** torch.arange(L, dtype=x.dtype, device=x.device)
    args = x.unsqueeze(-1) * freqs * math.pi
    sinc = torch.cat([args.sin(), args.cos()], dim=-1)
    return sinc.reshape(*x.shape[:-1], -1)
```

- **频率**：`2.0 ** arange(L)` = `[1, 2, 4, …, 2^{L−1}]`，指数增长。乘以 π 后，最低频在 `p ∈ [−1, 1]` 上只走半个周期，最高频（L=10 时为 512π）能分辨非常细的变化。
- **广播**：`x.unsqueeze(-1)` 把 `(..., D)` 变成 `(..., D, 1)`，与 `(L,)` 相乘广播成 `(..., D, L)`——每个坐标分量乘上每个频率。
- **拼接与展平**：`cat` 后为 `(..., D, 2L)`，`reshape(*x.shape[:-1], -1)` 把最后两维压平成 `D·2L`。`-1` 让 PyTorch 自动推算这一维。
- **`dtype=x.dtype, device=x.device`**：保证频率张量与输入在同一设备、同一精度上，否则 GPU 输入会和 CPU 上的 `freqs` 相乘报错。
- **函数名 `sinc`**：这里只是"sin + cos"的缩写变量名，**不是**信号处理里的 sinc 函数 `sin(x)/x`，别被误导。
- **维度顺序**：每个坐标内先放 L 个 sin、再放 L 个 cos，与论文公式中 sin/cos 交替的顺序不同，但对 MLP 而言等价。
- ⚠️ 与官方 NeRF 的差别：官方实现还会把原始坐标拼进去（位置 63 维、方向 27 维），本函数没有。

### 3.3 `TinyNeRF`：密度看位置，颜色看位置 + 视角

```python
        pos_dim = 3 * 2 * L_pos
        dir_dim = 3 * 2 * L_dir
        self.trunk = nn.Sequential(
            nn.Linear(pos_dim, hidden), nn.ReLU(inplace=True),
            # ... 共 4 层 Linear + ReLU
        )
        self.sigma = nn.Linear(hidden, 1)
        self.color = nn.Sequential(
            nn.Linear(hidden + dir_dim, hidden // 2), nn.ReLU(inplace=True),
            nn.Linear(hidden // 2, 3), nn.Sigmoid(),
        )

    def forward(self, x, d):
        x_enc = positional_encoding(x, self.L_pos)
        d_enc = positional_encoding(d, self.L_dir)
        h = self.trunk(x_enc)
        sigma = torch.relu(self.sigma(h)).squeeze(-1)
        rgb = self.color(torch.cat([h, d_enc], dim=-1))
        return sigma, rgb
```

- **输入维度**：位置 `3·2·10 = 60`，方向 `3·2·4 = 24`。方向比位置平滑得多，所以只用 4 个频率。
- **分工**：`sigma` 只由 trunk 特征 `h` 决定（与视角无关），保证几何在多视角间一致；`color` 拼接了 `h` 和方向编码 `d_enc`，可以表达随视角变化的高光和反射。
- **激活函数的选择**：
  - `torch.relu` 让密度非负（密度是"单位长度上的吸收率"，不能为负）；
  - `nn.Sigmoid` 把颜色压到 [0, 1]。
- **`.squeeze(-1)`**：`(128, 1) → (128,)`，与体渲染函数期望的 `sigma: (..., N_samples)` 形状对齐。
- **`hidden // 2`**：整除，128 → 64，颜色分支比 trunk 窄。
- ⚠️ 简化之处：原始 NeRF 是 8 层、256 宽、带一次跳连（把输入编码在第 5 层重新拼进来），还分粗/细两个网络做分层采样；这里只有 4 层 128 宽，参数约 6.7 万，只用于演示结构。`main()` 里的方向 `d = torch.randn(128, 3)` 也没有归一化成单位向量——真实系统中方向都是单位向量。

### 3.4 `volumetric_render`：可微的光线积分

```python
def volumetric_render(sigma, rgb, t_vals):
    delta = torch.cat([t_vals[1:] - t_vals[:-1], torch.full_like(t_vals[:1], 1e10)])
    alpha = 1.0 - torch.exp(-sigma * delta)
    trans = torch.cumprod(
        torch.cat([torch.ones_like(alpha[..., :1]), 1.0 - alpha + 1e-10], dim=-1),
        dim=-1,
    )[..., :-1]
    weights = alpha * trans
    rendered = (weights.unsqueeze(-1) * rgb).sum(dim=-2)
    depth = (weights * t_vals).sum(dim=-1)
    return rendered, depth, weights
```

逐行对照公式 `C = Σ Tᵢ·αᵢ·cᵢ`：

| 代码 | 公式 | 说明 |
|------|------|------|
| `delta` | `δᵢ = t_{i+1} − tᵢ` | 相邻采样点间距；最后一个点没有"下一个"，补 `1e10` |
| `alpha` | `αᵢ = 1 − exp(−σᵢδᵢ)` | 第 i 段的不透明度，σ 越大或段越长越不透明 |
| `trans` | `Tᵢ = Π_{j<i}(1 − αⱼ)` | 用 `cumprod` 实现"累乘"；前面拼一个 1 再去掉最后一项，实现"严格小于 i" |
| `weights` | `wᵢ = Tᵢ·αᵢ` | 光线恰好终止在第 i 个点的概率 |
| `rendered` | `Σ wᵢ·cᵢ` | `unsqueeze(-1)` 让权重 `(N,)` 与颜色 `(N,3)` 广播相乘 |
| `depth` | `Σ wᵢ·tᵢ` | 期望深度 |

- **为什么 `Π(1−αⱼ)` 等于 `exp(−Σσⱼδⱼ)`**：`1 − αⱼ = exp(−σⱼδⱼ)`，指数的乘积等于和的指数——两种写法数学等价。用 `cumprod` 写法可以直接复用已经算好的 `alpha`。
- **`1e10` 的意义**：相当于在远平面放了一堵无限厚的墙。只要最后一个点的 σ > 0，`α_N ≈ 1`，剩余的光全部被吸收，于是 `Σwᵢ ≈ 1`，权重构成概率分布——这就是 `main()` 打印 `weights sum` 约为 1.000 的原因。
- **`+ 1e-10`**：沿用官方 NeRF 代码的数值保护，避免透射率精确为 0。在 float32 下，当 `1 − α` 远大于 `1e-10` 时这个数会被舍入吞掉，几乎不影响结果。
- **为什么要可微**：整个函数只有加、乘、`exp`、`cumprod`，梯度可以从像素颜色一路传回每个采样点的 σ 和 rgb，再传回 MLP——这就是"只用 2D 照片训练 3D 场景"的关键。
- ⚠️ 形状假设：`t_vals[1:] - t_vals[:-1]` 在**第 0 维**上切片，只适用于讲义注释中的 `t_vals: (N_samples,)`（所有光线共享同一组采样距离）。如果做分层随机采样（每条光线的 `t_vals` 不同，形状 `(..., N_samples)`），应改为 `t_vals[..., 1:] - t_vals[..., :-1]`，补齐项也要用 `t_vals[..., :1]`。
- ⚠️ 没有乘以光线方向的模长 `‖d‖`：官方 NeRF 会把 `δ` 换算成真实的欧氏距离。

### 3.5 `permutation_invariance_check`：把性质写成测试

```python
def permutation_invariance_check():
    pts = torch.randn(1, 3, 512)
    net = PointNet(num_classes=5).eval()
    idx = torch.randperm(512)
    shuffled = pts[:, :, idx]
    with torch.no_grad():
        out_a = net(pts)
        out_b = net(shuffled)
    return (out_a - out_b).abs().max().item()
```

- `torch.randperm(512)` 生成 0–511 的随机排列，`pts[:, :, idx]` 用整数数组索引在点维度上打乱。
- **`.eval()` 必不可少**：这里 batch 大小为 1，训练模式下 head 里的 `BatchNorm1d(512)` 每个通道只有 1 个值，会抛 `ValueError: Expected more than 1 value per channel when training`；而且 Dropout 在训练模式下是随机的，两次前向结果本来就不同，测试将失去意义。`.eval()` 返回模型自身，所以能链式写在构造之后。
- `torch.no_grad()` 关闭梯度记录，省内存；`.item()` 把单元素张量转成 Python 浮点数。
- 返回"最大绝对差"而不是布尔值，便于在打印时看到具体量级（期望为 0 或 1e-7 级浮点噪声）。

### 3.6 `main()`

```python
    torch.manual_seed(0)
    # ...
    pts = torch.randn(4, 3, 1024)
    net = PointNet(num_classes=10)
    print(f"  output: {tuple(net(pts).shape)}  params: {sum(p.numel() for p in net.parameters()):,}")
    # ...
    t_vals = torch.linspace(2.0, 6.0, 64)
    sigma_ray = torch.rand(64) * 0.5
    rgb_ray = torch.rand(64, 3)
```

- `torch.manual_seed(0)` 固定随机种子，保证每次运行数值一致。
- PointNet 这里是**训练模式**下前向（batch=4，BN 可以算统计量），只为看形状。
- 体渲染演示：一条光线，近平面 2、远平面 6，均匀采样 64 个点；`σ ~ U(0, 0.5)`、颜色随机——相当于一团半透明的彩色"雾"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 共享 MLP 用 `Conv1d(k=1)` | 一次处理所有点，无需 reshape | 与 `Linear` 作用在 `(N, P, C)` 上等价，选哪个看数据布局 |
| max pool 作对称函数 | 置换不变 + 点数可变，实验中优于 sum/mean | 丢失局部结构；PointNet++ 用分层局部聚合 |
| 省略 T-Net | 聚焦核心思想 | 原论文用 T-Net 做输入/特征对齐；实际中常改用旋转增强 |
| 位置 L=10、方向 L=4 | 位置需要高频细节，方向较平滑 | L 太大会过拟合出高频伪影；Instant-NGP 用哈希网格替代 |
| σ 只依赖位置 | 保证多视角几何一致 | 颜色依赖视角以表达高光 |
| 最后一个 δ 取 `1e10` | 远平面吸收剩余光，权重和为 1 | 白底数据需要额外用 `1 − Σw` 合成背景色 |
| `cumprod` 计算透射率 | 直接复用 α，代码简洁（与官方 NeRF 代码一致） | 另一种等价写法是 `exp(−cumsum(σδ))`（注意要错开一位，实现"j < i"） |
| 体渲染用随机 σ/rgb 演示 | 不必训练就能看到渲染的行为 | 真实系统中 σ/rgb 来自 NeRF，`t_vals` 还要分层随机采样 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import math` | `math.pi` | 标准库常量 π（讲义版本手写了 `3.141592653589793`） |
| 类继承与 `super()` | `class PointNet(nn.Module)`、`super().__init__()` | PyTorch 模块必须先初始化父类，参数才能被注册 |
| 默认参数 | `def __init__(self, L_pos=10, L_dir=4, hidden=128)` | 不传参时使用默认值 |
| 幂运算 `**` | `2.0 ** torch.arange(L, ...)` | 标量的张量次幂，逐元素计算 |
| 整除 `//` | `hidden // 2` | 结果是整数（128 → 64） |
| 关键字参数 | `torch.arange(L, dtype=x.dtype, device=x.device)` | 按名字传参 |
| 索引与切片 | `t_vals[1:] - t_vals[:-1]`、`alpha[..., :1]`、`[..., :-1]` | `...`（Ellipsis）表示"前面所有维度"，只对最后一维切片 |
| 元组返回值的下标 | `torch.max(x, dim=-1)[0]` | 函数返回 `(values, indices)`，`[0]` 取第一个 |
| 多返回值与解包 | `return sigma, rgb` / `sigma, rgb = nerf(x, d)` | Python 用元组返回多个值 |
| `*` 解包实参 | `sinc.reshape(*x.shape[:-1], -1)` | 把形状元组拆成多个位置参数 |
| 链式调用 | `PointNet(num_classes=5).eval()` | `.eval()` 返回模型本身，所以可以接在构造之后 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内关闭梯度跟踪，离开后自动恢复 |
| 生成器表达式 | `sum(p.numel() for p in net.parameters())` | 统计参数总数 |
| f-string 格式符 | `{...:,}`、`{...:.2e}`、`{...:.2f}`、`{...:.3f}` | 千位分隔、科学计数法、保留 2/3 位小数 |
| `.item()` / `.tolist()` | `depth.item()`、`rendered.tolist()` | 张量转 Python 数值 / 列表，便于打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 形状和参数量由代码确定性地推出（参数量已按层逐项计算），体渲染的公式已用 NumPy 按相同实现核对；具体随机数值依赖 PyTorch 的随机数生成器，无法在 NumPy 中复现。预期输出的结构如下：

```text
[pointnet]
  output: (4, 10)  params: 807,626
  permutation invariance  max|diff|=0.00e+00      ← 或 1e-7 量级

[positional encoding]
  input  (5, 3) -> encoded (5, 60)

[tiny nerf forward]
  sigma: (128,)   rgb: (128, 3)

[volumetric render]
  rendered colour:   [三个 0~1 之间的数]
  depth:             约 4.5（随随机数变化）
  weights sum:       1.000
```

逐行解读：

- **`output: (4, 10)`**：4 个点云，每个 1024 点 → 4 行 10 类 logits。**`params: 807,626`** 的构成：mlp1 4,672 + mlp2 142,720 + head 660,234。
- **`max|diff|`**：打乱 512 个点的顺序后输出几乎完全相同，PointNet 的置换不变性得到验证。
- **`(5, 3) -> (5, 60)`**：每个坐标 × 10 个频率 × (sin, cos) = 20 维，3 个坐标共 60 维。
- **`sigma: (128,)  rgb: (128, 3)`**：128 个采样点，每点一个密度、一个 RGB。
- **`depth`**：σ 平均 0.25，从 2 到 6 的光学厚度约 `0.25 × 4 = 1`，所以约 `e⁻¹ ≈ 37%` 的光穿透到最后一个点并被"墙"吸收。按此估算深度期望约 4.5（用 NumPy 按同样分布模拟 1000 条光线，均值 4.52、标准差约 0.1）。
- **`weights sum: 1.000`**：最后一个 δ = `1e10` 使剩余光全部被吸收，权重之和为 1（见 3.4）。
- **`rendered colour`**：64 个随机颜色的加权平均；最后一个点约占 37% 的权重，所以结果明显受它的颜色影响，三个通道一般落在 0.2–0.8 之间。

---

## 7. 动手改一改

1. **换聚合函数**：把 `torch.max` 换成 `x.mean(dim=-1)` 或 `x.sum(dim=-1)`，确认 `permutation_invariance_check` 仍接近 0；再换成 `x.flatten(1)`（需相应调整 head 输入维度），观察不变性被破坏。
2. **关键点可视化**：保存 `torch.max(x, dim=-1)[1]`（索引），统计有多少个不同的点"胜出"——这就是 PointNet 的关键点集。
3. **`include_input`**：给 `positional_encoding` 加上拼接原始坐标的选项，并同步修改 `TinyNeRF` 的 `pos_dim/dir_dim`（63 / 27）。
4. **白色背景**：在 `volumetric_render` 中返回 `acc = weights.sum(-1)`，并实现 `rendered + (1 − acc)`；用全 0 的 σ 验证输出变成白色。
5. **把 NeRF 和体渲染接起来**：写一个 `render_ray(nerf, o, d, near=2, far=6, N=64)`：生成 `t_vals`，算出采样点 `o + t·d`，查询 `TinyNeRF`，再调 `volumetric_render`。
6. **（进阶）讲义练习 3**：用简单的光线追踪渲染一个彩色立方体的多视角图像，训练 TinyNeRF，记录第 1、10、100 个 epoch 的渲染损失。

---

## 8. 常见坑

- **点云布局搞反**：文件读出来是 `(P, 3)`，`Conv1d` 要 `(N, 3, P)`；忘了 `transpose` 时若 P 恰好等于 3 不会报错，但结果全错。
- **单样本推理忘记 `.eval()`**：PointNet 的 head 有 `BatchNorm1d`，batch=1 时训练模式直接报错；Dropout 也会让输出随机。
- **把 `sinc` 当成 sinc 函数**：这里只是变量名。
- **`t_vals` 带 batch 维时的切片**：`t_vals[1:]` 切的是第 0 维；逐光线采样时必须写 `t_vals[..., 1:]`。
- **方向向量未归一化**：位置编码对方向的模长敏感，真实 NeRF 中视角方向要先归一化。
- **期望白底却渲染成黑底**：空的光线权重全为 0，输出黑色；合成数据集要显式合成背景色。
