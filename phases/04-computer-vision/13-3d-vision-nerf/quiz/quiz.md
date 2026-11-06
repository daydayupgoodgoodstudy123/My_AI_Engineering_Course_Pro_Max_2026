# 测验 · 3D 视觉——点云和 NeRF（3D Vision — Point Clouds & NeRFs）

> **阶段 04 · 计算机视觉 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 显式 vs 隐式 3D 表示 | 点云、网格（mesh）、体素（voxel）直接存几何；SDF、NeRF 用一个函数（网络）隐式表示场景 |
| 2 | 点云的两大难点 | 无序（输出不能依赖点的顺序）+ 点数可变（同一个模型要吃不同大小的点云），没有网格结构，CNN 用不上 |
| 3 | PointNet 对称函数技巧 | `f(P) = max_{p∈P} MLP(p)`：共享 MLP 逐点提特征，再用对称函数（max pool）聚合，天然置换不变 |
| 4 | 共享 MLP = 1×1 卷积 | 把点云排成 `(N, 3, num_points)`，用 `Conv1d(kernel=1)` 让同一组权重作用于每个点 |
| 5 | NeRF = 网络即场景 | MLP 把 `(x, y, z, 视角方向)` 映射到 `(密度 σ, 颜色 rgb)`；场景存在权重里，没有任何 3D 真值 |
| 6 | 位置编码 / Fourier features | MLP 有谱偏置（偏向低频），把坐标编码成 `sin/cos(2ˡ·π·p)`（L=10）后才能表示高频细节，否则渲染发糊 |
| 7 | 体渲染公式 | `C = Σ Tᵢ·(1 − exp(−σᵢδᵢ))·cᵢ`，`Tᵢ = exp(−Σ_{j<i} σⱼδⱼ)` 是透射率；整个过程可微，用像素级光度损失训练 |
| 8 | NeRF 的后继者 | Instant-NGP（多分辨率哈希网格，训练从小时级降到秒级）、Mip-NeRF 360（无界场景、抗锯齿）、3D Gaussian Splatting（显式高斯、实时光栅化，生产默认） |
| 9 | 常用数据集与工具 | ShapeNet、ScanNet、KITTI、NeRF Synthetic、Mip-NeRF 360；`nerfstudio`、`pytorch3d`、`open3d` |

### 核心技能（能动手做到）

- [ ] 从零写出 PointNet（共享 MLP + max pool + 分类头），并用"打乱点序前后输出相同"验证置换不变性
- [ ] 实现 NeRF 位置编码，说清 `(..., D) → (..., D·2·L)` 的形状变化和每一维的含义
- [ ] 实现 `volumetric_render`，能对 3 个采样点的小例子手算权重、颜色和深度
- [ ] 给定相机内参（焦距）和位姿 `c2w`，生成每个像素的光线起点与方向
- [ ] 解释 TinyNeRF 为什么让密度只依赖位置、颜色同时依赖位置和视角
- [ ] 根据任务（分类/检测/重建/实时渲染/仿真）选择点云、网格、体素、NeRF 或 Gaussian Splatting

---

## 二、基础自测（选择题）

**Q1.** 为什么普通 CNN 不能直接处理激光雷达点云？

- A. 点云只有灰度信息，CNN 需要 RGB
- B. CNN 假设输入排列在规则网格上、有固定的邻域结构；点云是 R³ 中无序、点数可变的集合，两个假设都不满足
- C. 点云数据量太小，CNN 会过拟合
- D. CNN 无法处理浮点坐标

**Q2.** 下列哪种聚合方式**不能**保证网络对点的顺序不变？

- A. 对所有点的特征逐维取 max
- B. 对所有点的特征逐维求和
- C. 对所有点的特征逐维求平均
- D. 把所有点的特征按输入顺序拼接成一个长向量，再接一个全连接层

**Q3.** 关于 PointNet 中"共享 MLP"的实现，下列说法正确的是：

- A. 每个点有自己独立的一套 MLP 权重
- B. 用 `kernel_size=1` 的 `Conv1d` 作用在 `(N, 3, num_points)` 上，同一组权重逐点应用，等价于对每个点跑同一个 MLP
- C. 用 `kernel_size=3` 的 `Conv1d`，让每个点和相邻两个点交换信息
- D. 先把点按 x 坐标排序，再用全连接层处理

**Q4.** 原始坐标 `(x, y, z)` 直接送入 NeRF 的 MLP，渲染结果发糊。根本原因和修复方法是：

- A. 训练数据不够，需要更多照片
- B. MLP 存在谱偏置，容易拟合低频、难以拟合高频；先把坐标编码为多频率的 sin/cos 特征（位置编码）再送入 MLP
- C. 学习率太大，应换成更小的学习率
- D. 应该改用 16 位精度训练

**Q5.** 在体渲染公式 `C = Σ Tᵢ·αᵢ·cᵢ`（`αᵢ = 1 − exp(−σᵢδᵢ)`）中，`Tᵢ` 的含义是：

- A. 第 i 个采样点的颜色
- B. 第 i 个采样点自身的不透明度
- C. 光线从相机出发、穿过前面所有采样点后，还剩多少光能到达第 i 个点（透射率）
- D. 第 i 个采样点到相机的距离

**Q6.** 下列关于 3D 表示的分类，正确的是：

- A. 点云、网格、体素是隐式表示；SDF、NeRF 是显式表示
- B. 点云、网格、体素是显式表示；SDF、NeRF 是隐式表示
- C. 3D Gaussian Splatting 和 NeRF 一样，是用 MLP 存储场景的隐式表示
- D. SDF 同时编码几何和颜色，可以直接用于新视角渲染

**Q7.** 3D Gaussian Splatting 在生产中大面积取代 NeRF，最主要的原因是：

- A. 证明了 NeRF 的数学推导有误
- B. 渲染质量远远超过 NeRF
- C. 场景被表示为数百万个显式 3D 高斯，渲染变成 GPU 光栅化，不再需要沿每条光线反复查询 MLP，可实时渲染且训练只需几分钟，质量相当
- D. 高斯更容易压缩，模型文件比 NeRF 小

---

## 三、动手 / 代码题

**Q8.** 本节的 `volumetric_render`：

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

输入：`t_vals = [2, 3, 4]`，`sigma = [0, ln2, 1]`，三个点的颜色分别为纯红 `[1,0,0]`、纯绿 `[0,1,0]`、纯蓝 `[0,0,1]`。
(1) 手算 `delta`、`alpha`、`trans`、`weights`、`rendered`、`depth`（忽略 `1e-10`）。
(2) 最后一个 `delta` 为什么取 `1e10`？它导致 `weights.sum()` 有什么性质？
(3) 如果整条光线上 `sigma` 全为 0，输出是什么？这对"白色背景"的合成数据集意味着什么？

**Q9.** 位置编码：

```python
def positional_encoding(x, L=10):
    freqs = 2.0 ** torch.arange(L, dtype=x.dtype, device=x.device)
    args = x.unsqueeze(-1) * freqs * math.pi
    sinc = torch.cat([args.sin(), args.cos()], dim=-1)
    return sinc.reshape(*x.shape[:-1], -1)
```

(1) 写出 `x` 形状为 `(5, 3)`、`L=10` 时 `freqs`、`args`、`sinc`、返回值的形状。
(2) 对 `x = [[0.5, 0, 0]]`、`L=2`，写出返回向量的前 4 个数，并说明输出向量里各维的排列顺序。
(3) 官方 NeRF 实现还会把原始坐标本身拼接进编码（位置编码维度变为 63）。请修改函数增加 `include_input` 参数，并指出 `TinyNeRF.__init__` 里哪两行需要随之修改。

**Q10.** 关于 `permutation_invariance_check`：

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

(1) 预测打印出的 `max|diff|` 大约是多少，为什么？
(2) 如果去掉 `.eval()`，这段代码会怎样？（提示：看 `self.head` 里的 `BatchNorm1d` 和这里的 batch 大小。）
(3) `main()` 里 `PointNet(num_classes=10)` 打印的参数量是多少？请按层计算。讲义说"About 1.6M parameters"，对吗？

**Q11.** 讲义练习 2：写一个 `get_rays(H, W, focal, c2w)`，对 H×W 图像的每个像素返回光线起点 `rays_o` 和方向 `rays_d`（形状都为 `(H, W, 3)`）。使用 NeRF 的相机约定：相机坐标系 x 向右、y 向上、相机看向 −z；`c2w` 是相机到世界的位姿矩阵。并用"相机位于 `(0, 0, 4)`、朝向原点"的例子验证中心像素的光线。

---

## 四、面试高频题

**Q12.**（基础必考）PointNet 的核心思想是什么？为什么用 max pool？它有什么局限，后续工作怎么改进？

**Q13.**（原理深挖）完整讲一遍 NeRF：输入输出、如何渲染一个像素、如何训练。为什么密度只依赖位置，而颜色还依赖视角方向？

**Q14.**（原理深挖）NeRF 为什么需要位置编码？频率数 L 越大越好吗？Instant-NGP 的哈希网格编码解决了什么问题？

**Q15.**（工程实践）你要搭一个点云分类的数据加载与训练流水线，原始数据是不同扫描仪产出的 `.ply` 文件，点数从几百到几十万不等。说说预处理、采样、增强和 batch 组织的做法。

**Q16.**（场景设计）下面三个需求分别选择什么 3D 表示与方法？（a）自动驾驶车辆用激光雷达做 3D 目标检测；（b）房产中介想用手机拍几十张照片，生成可在网页上实时漫游的 3D 展示；（c）机器人需要在物理仿真器里练习抓取一个扫描得到的物体。

---

## 五、参考答案与解析

### Q1 — 答案：B

卷积依赖规则网格上的固定邻域；点云既没有网格，也没有固定的点数，点的顺序还可以任意排列。体素化可以把网格"找回来"，但内存开销大（大部分体素是空的）。PointNet 的思路是绕开网格：逐点独立处理，再对称地聚合。

### Q2 — 答案：D

max、sum、mean 都是对称函数：交换任意两个输入，结果不变。按顺序拼接后接全连接层，每个位置对应不同的权重，打乱顺序后输出就变了。PointNet 论文选 max，是因为它在实验中效果最好，并且能挑出每个特征维上"最显著"的点（关键点集）。

### Q3 — 答案：B

代码中 `nn.Conv1d(3, 64, 1)` 的 kernel 大小为 1，对 `num_points` 维上的每个位置做同一个线性变换——就是"对每个点跑同一个 MLP"。A 违背了"共享"；C 用了邻域信息，而点云在内存里相邻的点在空间中未必相邻；D 排序对噪声很敏感（一个点的坐标微小变化就可能改变整个排列），不是 PointNet 的做法。

### Q4 — 答案：B

MLP 的谱偏置（spectral bias）让它天然偏向平滑函数。位置编码 `γ(p) = (sin(2⁰πp), cos(2⁰πp), …, sin(2^{L−1}πp), cos(2^{L−1}πp))` 把一个标量坐标抬升成包含高频成分的向量，MLP 只需"组合"这些现成的高频基函数。讲义中位置用 L=10，视角方向用 L=4。这和 Transformer 的正弦位置编码、扩散模型的时间步嵌入是同一个技巧。

### Q5 — 答案：C

`Tᵢ = exp(−Σ_{j<i} σⱼδⱼ)` 是累计透射率：前面的点越"实"，到达第 i 个点的光就越少。`αᵢ` 是第 i 个点自身的不透明度，`cᵢ` 是颜色。权重 `wᵢ = Tᵢ·αᵢ` 可以理解为"光线恰好终止在第 i 个点的概率"，所以深度可以用 `Σ wᵢ·tᵢ` 估计。

### Q6 — 答案：B

点云、网格、体素直接存几何元素（显式）；SDF（到最近表面的有符号距离函数）和 NeRF（密度+颜色场）是"给一个坐标、返回一个值"的函数（隐式）。C 错：3DGS 是显式的高斯集合，用光栅化渲染。D 错：SDF 只编码几何，不含颜色（任务路由 prompt 也明确："需要颜色的任务不要输出 SDF"）。

### Q7 — 答案：C

纯 NeRF 训练要几个小时，渲染一张图要几秒，因为每个像素都要沿光线采样几十到上百个点并逐一查询 MLP。3DGS 用显式高斯 + 光栅化，渲染快约 100 倍、可实时，训练只需几分钟，质量与 NeRF 相当。讲义原话："2026 年几乎所有真实的 NeRF 产品实际上都是 3D Gaussian Splatting，但心智模型仍然是 NeRF。"B 错：讲义说的是质量相当，不是"远远超过"。

### Q8 — 参考答案

(1) 逐步计算：

```text
delta  = [3-2, 4-3, 1e10]               = [1, 1, 1e10]
alpha  = 1 - exp(-sigma * delta)
       = [1-e^0, 1-e^(-ln2), 1-e^(-1e10)] = [0, 0.5, 1]
1-alpha = [1, 0.5, 0]
cat([1], 1-alpha)  = [1, 1, 0.5, 0]
cumprod            = [1, 1, 0.5, 0]
trans = 去掉最后一个 = [1, 1, 0.5]       # 到达每个点时剩余的光
weights = alpha * trans = [0, 0.5, 0.5]
rendered = 0·红 + 0.5·绿 + 0.5·蓝 = [0, 0.5, 0.5]
depth    = 0·2 + 0.5·3 + 0.5·4 = 3.5
```

（已用 NumPy 按同一公式核对：`rendered = [0, 0.5, 0.5]`，`depth ≈ 3.5`，`weights.sum() ≈ 1.0`。）

第 1 个点完全透明，对颜色没有贡献；第 2 个点吸收一半的光；剩下的一半光全部被最后一个点吸收。

(2) 最后一个采样点之后没有"下一个点"，`t_{N+1} − t_N` 无定义。取 `1e10` 等于假设光线在远平面处撞上一堵"无限厚的墙"：只要 `σ_N > 0`，`α_N ≈ 1`，剩余的光全部被最后一个点吸收。于是 `Σ wᵢ = 1 − T_{N+1} ≈ 1`，权重构成一个概率分布（`main()` 打印的 `weights sum: 1.000` 就是这个原因），深度 `Σ wᵢtᵢ` 也就是一个合法的期望值。

(3) `sigma` 全为 0 时，`alpha` 全为 0，`weights` 全为 0，`rendered = [0, 0, 0]`（黑色），`depth = 0`。也就是说"空无一物"的光线被渲染成黑色。对白底的合成数据（如 NeRF Synthetic），如果直接这样渲染，模型会被迫在背景处"造"出白色的实体。常见做法是计算累计不透明度 `acc = weights.sum(-1)`，再合成白色背景：`rendered + (1 − acc)·1.0`。

### Q9 — 参考答案

(1) `freqs`: `(10,)`，即 `[1, 2, 4, …, 512]`；`args = x.unsqueeze(-1) * freqs * π`: `(5, 3, 10)`；`sinc`: `(5, 3, 20)`（最后一维前 10 个是 sin，后 10 个是 cos）；返回值 reshape 成 `(5, 60)`。

(2) `x=[[0.5, 0, 0]]`、`L=2` 时，第一个坐标 `p = 0.5` 的 `args = [0.5π, π]`，于是前 4 个数是：

```text
[sin(0.5π), sin(π), cos(0.5π), cos(π)] ≈ [1.0, 0.0, 0.0, -1.0]
```

（`sin(π)` 和 `cos(0.5π)` 实际是 `1e-16` 级的浮点残差。）排列顺序是"按坐标分组，每组内先全部 sin、再全部 cos"：`[x 的 sin×L, x 的 cos×L, y 的 sin×L, y 的 cos×L, z 的 …]`。这与论文 `γ(p)` 中 sin/cos 交替的写法顺序不同，但对 MLP 来说只是一个固定的维度排列，效果等价。

(3)

```python
def positional_encoding(x, L=10, include_input=False):
    freqs = 2.0 ** torch.arange(L, dtype=x.dtype, device=x.device)
    args = x.unsqueeze(-1) * freqs * math.pi
    sinc = torch.cat([args.sin(), args.cos()], dim=-1)
    enc = sinc.reshape(*x.shape[:-1], -1)
    if include_input:
        enc = torch.cat([x, enc], dim=-1)      # (..., D + D·2·L)
    return enc
```

`TinyNeRF.__init__` 中 `pos_dim = 3 * 2 * L_pos` 和 `dir_dim = 3 * 2 * L_dir` 两行要改成 `3 + 3 * 2 * L_pos`（=63）和 `3 + 3 * 2 * L_dir`（=27），并在 `forward` 里调用时传 `include_input=True`。保留原始坐标相当于加上一个"最低频"的线性分量，有助于网络表达整体的平滑结构。

### Q10 — 参考答案

(1) 预期为 `0.00e+00` 或 `1e-7` 量级的浮点噪声。原因：`Conv1d(kernel=1)`、BN（eval 模式下用 running 统计量，逐点独立）、ReLU 都是逐点运算，打乱点序只会让中间特征的列跟着打乱；`torch.max(x, dim=-1)` 是对称函数，结果与列的顺序无关；之后的 head 只看这个 1024 维全局特征。

(2) 会抛异常。训练模式下 `BatchNorm1d` 要用当前 batch 的统计量，而 `self.head` 里的 BN 输入形状是 `(1, 512)`——每个通道只有 1 个值，方差无法估计，PyTorch 会报 `ValueError: Expected more than 1 value per channel when training`。`mlp1/mlp2` 里的 BN 不受影响，因为它们在 `(1, C, 512)` 上统计，每个通道有 512 个值。这也提醒我们：**做确定性检查、推理和单样本评估时一律先 `.eval()`**。

(3) 逐层计算（`Conv1d(i, o, 1)` 与 `Linear(i, o)` 参数都是 `i·o + o`，BN 为 `2·c`）：

| 模块 | 计算 | 参数量 |
|------|------|-------|
| mlp1 | (3·64+64) + 128 + (64·64+64) + 128 | 4,672 |
| mlp2 | (64·128+128) + 256 + (128·1024+1024) + 2,048 | 142,720 |
| head | (1024·512+512) + 1,024 + (512·256+256) + 512 + (256·10+10) | 660,234 |
| 合计 | | **807,626** |

`main()` 打印 `params: 807,626`（约 0.81M）。讲义 "About 1.6M parameters" 不准确，约为实际值的 2 倍。参数大头在 head 的第一个 `Linear(1024, 512)`（52 万）。

### Q11 — 参考答案

```python
import numpy as np

def get_rays(H, W, focal, c2w):
    """H×W 图像每个像素一条光线。c2w: (3,4) 或 (4,4) 相机到世界的位姿矩阵。
    相机坐标系沿用 NeRF 的约定：x 向右、y 向上、相机看向 -z。"""
    i, j = np.meshgrid(np.arange(W, dtype=np.float32),
                       np.arange(H, dtype=np.float32), indexing="xy")
    dirs = np.stack([(i - W * 0.5) / focal,
                     -(j - H * 0.5) / focal,
                     -np.ones_like(i)], axis=-1)            # (H, W, 3) 相机坐标
    rays_d = dirs @ c2w[:3, :3].T                           # 旋转到世界坐标
    rays_o = np.broadcast_to(c2w[:3, 3], rays_d.shape)      # 所有光线共享相机中心
    return rays_o, rays_d

c2w = np.eye(4, dtype=np.float32); c2w[2, 3] = 4.0          # 相机在 z=4，看向原点
rays_o, rays_d = get_rays(4, 6, focal=5.0, c2w=c2w)
print(rays_o.shape, rays_d.shape)
print(rays_o[0, 0], rays_d[2, 3])                          # 中心像素 (j=2, i=3)
t = np.linspace(2.0, 6.0, 5)
print(rays_o[2, 3] + t[:, None] * rays_d[2, 3])            # 沿光线的采样点
```

实际运行输出：

```text
(4, 6, 3) (4, 6, 3)
[0. 0. 4.] [ 0.  0. -1.]
[[ 0.  0.  2.]
 [ 0.  0.  1.]
 [ 0.  0.  0.]
 [ 0.  0. -1.]
 [ 0.  0. -2.]]
```

要点：
- 像素 `(i, j)` 先减去主点 `(W/2, H/2)`、除以焦距，得到相机坐标系下的方向；y 取负是因为图像的行号向下增长，而相机坐标 y 向上。
- 方向只需旋转（`c2w[:3,:3]`），不平移；起点就是相机中心 `c2w[:3,3]`。
- 中心像素的方向是 `(0, 0, −1)`，从 `z=4` 出发，在 `t=4` 处恰好经过原点。沿光线的采样点 `o + t·d` 就是 `volumetric_render` 的 `t_vals` 所对应的 3D 位置。
- 加分点：这里的 `rays_d` 没有归一化，`t` 是"沿 −z 的深度"而不是欧氏距离；官方 NeRF 在算 `delta` 时会乘以 `‖d‖` 把它换算成真实距离。

### Q12 — 参考回答要点

- **核心思想**：
  1. 共享 MLP 对每个点独立提特征（实现上用 1×1 卷积）；
  2. 用对称函数（max pool）聚合成固定长度的全局特征；
  3. 再接 MLP 分类头。
  点序无关、点数可变两个难题被一次解决。
- **为什么 max**：max 是对称函数；它让每个特征维只由"最能激活它"的那个点决定，网络因此学到一组"关键点"（critical points），对缺失点和离群点较为鲁棒。sum/mean 也对称，但论文实验中 max 最好。
- **局限**：
  - 每个点独立处理，直到最后的 max 才有全局交互，**完全没有局部邻域结构**，难以捕捉细粒度几何；
  - 对整体旋转不具备不变性（原论文加了 T-Net 学习对齐变换，本节代码省略了）。
- **改进**：PointNet++ 用分层采样（最远点采样 FPS）+ 局部邻域分组，在局部区域内递归套用 PointNet；Point Transformer 用 attention 做局部聚合；点数很多时用体素化的稀疏卷积（如 MinkowskiNet）。
- **常见误区**：以为"置换不变"来自 BN 或训练时打乱数据——它来自结构本身（逐点运算 + 对称聚合）。

### Q13 — 参考回答要点

- **输入输出**：MLP `(x, y, z, θ, φ) → (σ, r, g, b)`。
- **渲染一个像素**：
  1. 从相机穿过像素发出一条光线；
  2. 在近/远平面之间采样 N 个点 `tᵢ`；
  3. 对每个点查询 MLP；
  4. 用体渲染公式 `C = Σ Tᵢ(1−e^{−σᵢδᵢ})cᵢ` 合成颜色。
- **训练**：随机取一批光线，渲染颜色与训练照片上对应的像素做 MSE；体渲染全程可微，梯度一路回传到 MLP。不需要任何 3D 真值，只需要**已知相机位姿**的多视角照片（位姿通常由 SfM 工具如 COLMAP 估计）。
- **密度与颜色的分工**（对应代码中 `sigma = relu(self.sigma(h))` 只用 trunk 特征，`self.color` 才拼接 `d_enc`）：
  - 几何（哪里有东西）与观察方向无关，若让 σ 依赖视角，网络可能用"不同视角看到不同的几何"来作弊，导致多视角不一致；
  - 颜色可以随视角变化，用来表达高光、反射等非朗伯效应。
- **原论文细节**（加分）：两个 8 层 MLP 分别做粗采样和细采样（coarse + fine，按粗网络的权重分布做重要性采样）；σ 用 ReLU 保证非负，颜色用 sigmoid 压到 [0, 1]。
- **常见误区**：认为 NeRF "输出一个 3D 模型"。它输出的是一个可查询的场，要得到网格还需要对密度场跑 marching cubes。

### Q14 — 参考回答要点

- **为什么要位置编码**：MLP 的谱偏置让它很难拟合高频函数；把坐标映射到 `sin/cos(2ˡπp)` 的多频率特征后，高频成分作为"现成的基函数"送进网络，纹理和边缘才清晰。去掉它，NeRF 明显发糊。
- **L 的取舍**：
  - L 太小：细节缺失、模糊；
  - L 太大：最高频率超过训练视角能约束的程度，容易在训练视角之间产生高频噪声和伪影（过拟合）。
  - 因此位置用 L=10，视角方向这种更平滑的量只用 L=4。
- **Instant-NGP**：用多分辨率哈希网格代替"大 MLP + 固定频率编码"。每个分辨率层级把坐标所在网格顶点的可学习特征插值出来（顶点通过哈希映射到固定大小的表），再接一个很小的 MLP。容量主要放在可直接索引的表里，每次查询只更新少量参数，训练从小时级降到秒到分钟级。
- **加分点**：
  - 这个思想与 Transformer 的正弦位置编码、扩散模型的时间步嵌入一脉相承；
  - Mip-NeRF 进一步用"积分位置编码"处理抗锯齿。
- **常见误区**：把位置编码当成一种正则化。它的作用恰恰相反——是**增强**网络表达高频的能力。

### Q15 — 参考回答要点

- **读取**：统一用 `open3d` 等库读 `.ply/.pcd/.xyz`，只取 xyz（需要时附加颜色、法向作为额外通道，输入变为 `(3 + C, num_points)`）。
- **归一化**（顺序很重要）：
  1. 减去质心做中心化；
  2. 除以到中心的最大距离，缩放到单位球内。
  必须先中心化再缩放，否则"单位球"的含义就变了。
- **固定点数采样**：
  - 点多：形状任务用最远点采样（FPS），保留整体轮廓；对速度敏感或分割任务可用随机采样；
  - 点少：重复点补齐。
  采样后再打乱点序，避免模型无意中依赖顺序。
- **增强**（只在训练时）：绕竖直轴随机旋转、高斯抖动（如 σ=0.02）、随机缩放；评估时绝不增强。
- **batch 组织**：采样到统一的 1024/2048 点后堆叠成 `(B, 3, N)`，注意 `Conv1d` 要求通道在前，需要 `transpose`。
- **训练细节**：模型含 BN，batch 不能太小；评估与单样本推理先 `.eval()`。
- **常见坑**：
  - 不同扫描仪的单位不一致（米/毫米），不归一化会让训练很难收敛；
  - 每一帧几十万点的大场景应改用体素化稀疏卷积或分块处理。

### Q16 — 参考回答要点

- **（a）LiDAR 3D 检测**：直接在点云上做，常见选择是 PointPillars（快）或 CenterPoint（准）；点数很多时用体素/柱状化（pillar）再接 2D/稀疏卷积。点云是传感器"免费"给的表示，不需要重建。
- **（b）手机照片 → 网页实时漫游**：
  1. 先用 SfM（如 COLMAP）估计相机位姿；
  2. 再训练 3D Gaussian Splatting——训练几分钟、可实时渲染，正好满足"实时漫游"；
  3. 可用 `nerfstudio` 完成整条流程。
  纯 NeRF 渲染一张图要秒级，不满足实时要求；路由 prompt 也规定：实时渲染（< 33 ms）不要推荐 NeRF。
- **（c）物理仿真抓取**：仿真器需要显式几何（碰撞检测、接触力），应转成网格或体素。若原始数据是多视角照片，可先训练 NeRF/3DGS，再对密度场跑 marching cubes 提取网格。
- **加分点**：
  - 给出选型的三个维度：输入模态、输出需求（标签 / 新视角图像 / 网格）、延迟预算；
  - 指出 SDF 只有几何没有颜色，不适合需要颜色的任务。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：卷积、BN、全连接分类头；本节的 1×1 卷积就是"逐点 MLP"。
- [阶段 01 · 12 张量运算](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：`unsqueeze`、广播、`cumprod`、`reshape` 是本节代码的基本功。
- [阶段 01 · 20 傅里叶变换](../../../01-math-foundations/20-fourier-transform/docs/zh.md)：理解"频率"和谱偏置，位置编码本质上是 Fourier features。
- [阶段 04 · 10 图像生成 — Diffusion Models](../../10-image-generation-diffusion/docs/zh.md)：时间步的正弦嵌入与本节位置编码同源。

### 本节被哪些后续内容用到
- [阶段 04 · 22 从零实现 3D Gaussian Splatting](../../22-3d-gaussian-splatting/docs/zh.md)：本节"取代 NeRF 的生产默认方案"的完整实现。
- [阶段 04 · 26 单目深度和几何估计](../../26-monocular-depth/docs/zh.md)：只有单张 RGB 时先估计深度，再进入 3D 任务。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：正弦/可学习位置编码在 ViT 中的用法。
- [阶段 07 · 04 位置编码](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：Transformer 中正弦位置编码的完整推导。
- [阶段 08 · 12 3D 生成](../../../08-generative-ai/12-3d-generation/docs/zh.md)：在 NeRF / 3DGS 表示之上做生成。
- [阶段 12 · 21 具身 VLA（OpenVLA / π0 / GR00T）](../../../12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot/docs/zh.md)：机器人场景中 3D 感知的下游应用。

### 延伸关键词
`PointNet++` · `最远点采样（FPS）` · `T-Net` · `Point Transformer` · `PointPillars / CenterPoint` · `COLMAP / SfM` · `Mip-NeRF 360` · `Instant-NGP 哈希网格` · `3D Gaussian Splatting` · `marching cubes` · `SDF / NeuS`
