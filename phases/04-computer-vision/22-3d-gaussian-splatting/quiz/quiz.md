# 测验 · 从零实现 3D Gaussian Splatting（3D Gaussian Splatting from Scratch）

> **阶段 04 · 计算机视觉 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 显式表示 vs 隐式表示 | NeRF 把场景存在 MLP 权重里，每个像素要沿光线查询上百次；3DGS 把场景存成数百万个显式 3D 高斯，可直接光栅化、直接编辑 |
| 2 | 每个高斯的参数 | 位置 μ（3）、旋转四元数 q（4）、log 尺度 s（3）、不透明度 α（1）、球谐系数（每通道 `(L+1)²`，L=3 时共 48），合计约 59 个浮点数 |
| 3 | 协方差构造 | `Σ = R S Sᵀ Rᵀ`，R 来自四元数、S 为对角尺度矩阵；保证 Σ 始终半正定，优化稳定 |
| 4 | 投影 | 3D 高斯投影为 2D 高斯：`μ' = project(μ)`，`Σ' = J W Σ Wᵀ Jᵀ`（W 为视图变换，J 为透视投影在该点的雅可比） |
| 5 | 光栅化流程 | 投影 → 分配到 16×16 屏幕 tile → tile 内按深度排序 → 从前到后 alpha 合成 → 像素颜色 |
| 6 | Alpha 合成 | `C = Σ αᵢ Tᵢ cᵢ`，`Tᵢ = Π_{j<i}(1 - αⱼ)`；与 NeRF 的体渲染是同一个方程 |
| 7 | 自适应致密化 | 梯度大且尺度小 → clone；梯度大且尺度大 → split；不透明度低于阈值 → prune；从约 10 万（SfM 点）长到 1–5 百万 |
| 8 | 球谐函数（SH） | 球面上的傅里叶基；用视角方向上的基函数与学到的系数做点积得到与视角相关的颜色 |
| 9 | 无约束参数 + 激活 | `log_scale → exp`、`opacity_logit → sigmoid`、`colour_logits → sigmoid`：优化器在实数空间自由更新，渲染时映射到合法范围 |
| 10 | 2026 生产栈 | 采集 → COLMAP/GLOMAP 求位姿 → nerfstudio/gsplat 训练 → SuperSplat 编辑 → 导出 `.ply` / glTF `KHR_gaussian_splatting` / OpenUSD |

### 核心技能（能动手做到）

- [ ] 用 `torch.einsum("gpi,gij,gpj->gp", ...)` 一次性计算所有（高斯, 像素）对的马氏距离二次型
- [ ] 从零写出 2D 高斯的前到后 alpha 合成光栅器，并手算两层合成的颜色和剩余透射率
- [ ] 用"角度 + log 尺度"构造 2D 协方差 `R S Rᵀ`，并说明它对应 3D 的 `R S Sᵀ Rᵀ`
- [ ] 指出 `self.depth` 虽然是 `nn.Parameter` 但拿不到梯度的原因（`argsort` 不可导）
- [ ] 给光栅器加上背景色项，解释为什么白底目标需要它
- [ ] 计算一个场景的存储量（高斯数 × 每高斯浮点数 × 4 字节），并比较不同 SH 阶数的开销
- [ ] 用 nerfstudio 的 `splatfacto` 跑通一次真实场景重建，并能为下游引擎选择导出格式

---

## 二、基础自测（选择题）

**Q1.** 3DGS 能在 2026 年成为照片级 3D 重建的生产默认方案，最核心的原因是：

- A. NeRF 的论文被撤回了
- B. 场景是显式的高斯集合：渲染变成 GPU 光栅化（100+ fps），训练只需分钟级，场景可以直接编辑，并且有了 glTF / OpenUSD 等标准格式
- C. 3DGS 在任何场景下画质都严格优于 NeRF
- D. PyTorch 不再支持 NeRF 的算子

**Q2.** 一个场景有 500 万个高斯，每个高斯存 59 个 float32（3 + 4 + 3 + 1 + 48）。这个场景的原始参数大约占多少存储？

- A. 约 24 MB
- B. 约 240 MB
- C. 约 1.2 GB
- D. 约 12 GB

**Q3.** 若把球谐阶数从 3 降到 2，每个高斯用于颜色的浮点数从多少变成多少？

- A. 16 → 9
- B. 48 → 27
- C. 48 → 12
- D. 64 → 27

**Q4.** 某像素被两个高斯覆盖，按深度排序后：前面的高斯 `α = 0.5`、颜色红 `(1, 0, 0)`；后面的高斯 `α = 0.8`、颜色蓝 `(0, 0, 1)`。从前到后合成后的像素颜色和剩余透射率分别是：

- A. `(0.5, 0, 0.8)`，0.0
- B. `(0.5, 0, 0.4)`，0.1
- C. `(0.1, 0, 0.8)`，0.1
- D. `(0.5, 0, 0.5)`，0.2

**Q5.** 关于 3DGS 训练中的致密化与剪枝，下列对应关系正确的是：

- A. 梯度大且尺度小 → split；梯度大且尺度大 → clone
- B. 梯度大且尺度小 → clone（需要更多局部细节）；梯度大且尺度大 → split（一个大高斯太平滑）；不透明度低于阈值 → prune
- C. 每个 epoch 随机复制 10% 的高斯
- D. 高斯数量在训练过程中固定不变

**Q6.** 为什么 3DGS 用 `Σ = R S Sᵀ Rᵀ`（旋转 + 尺度）来参数化协方差，而不是直接把 Σ 的 6 个独立元素当参数优化？

- A. 直接优化 Σ 更慢
- B. 协方差必须半正定；直接对矩阵元素做梯度下降很容易得到非法（非半正定）矩阵，而 `R S Sᵀ Rᵀ` 对任意参数取值都合法，且旋转/尺度的含义直观，便于致密化时缩放、分裂
- C. 这样可以省掉投影步骤
- D. 因为四元数比矩阵占用更少显存，这是唯一原因

**Q7.** 本节 `Splats2D` 把参数存成 `log_scale`、`opacity_logit`、`colour_logits`，渲染时再映射。下列映射关系正确的是：

- A. `scale = sigmoid(log_scale)`、`opacity = exp(opacity_logit)`
- B. `scale = exp(log_scale)` 保证为正；`opacity = sigmoid(opacity_logit)`、`colour = sigmoid(colour_logits)` 保证落在 (0, 1)
- C. 三者都直接使用，不需要映射
- D. `scale = log_scale ** 2`、`opacity = tanh(opacity_logit)`

---

## 三、动手 / 代码题

**Q8.** `Splats2D` 中有一个参数 `self.depth = nn.Parameter(torch.rand(num_splats, generator=g))`，它只在光栅器里这样被使用：

```python
    order = torch.argsort(depths)
    alphas = alphas[order]
    colours_sorted = colours[order]
```

1. 训练 300 步后，`model.depth` 会发生变化吗？`model.depth.grad` 是什么？为什么？
2. 讲义说"we use a learned per-Gaussian scalar for order"，这个说法在本代码中成立吗？这会对拟合产生什么影响？
3. 真实 3DGS 里深度从哪里来？排序本身可导吗？梯度如何流回高斯的位置？

**Q9.** `main()` 的目标图 `make_target(48)` 是**白色背景**（`np.ones`）上的红圆和蓝方块：

```python
    T = torch.ones(H, W, device=device)
    out = torch.zeros(H, W, 3, device=device)
    for i in range(means.size(0)):
        a = alphas[i]
        out = out + (T * a)[..., None] * colours_sorted[i][None, None, :]
        T = T * (1.0 - a)
    return out
```

1. 一个没有被任何高斯覆盖的像素，渲染出来是什么颜色？这对拟合白色背景意味着什么？
2. 修改 `rasterise_2d`，增加参数 `bg`（形状 `(3,)` 的背景色，默认黑色），让剩余透射率乘以背景色加到输出上。

**Q10.** 阅读 `eval_2d_gaussian`：

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

1. 在 `main()` 的设置下（48 个高斯、48×48 图像），写出 `flat`、`diff`、`d`、返回值的形状。
2. 用文字（或不用 einsum 的等价 PyTorch 代码）说明 einsum 那一行算的是什么。
3. 当场景有 100 万个高斯、渲染 1920×1080 的图像时，这种"每个高斯对每个像素都算一遍"的写法有什么问题？真实实现（讲义中的 tile-based CUDA 光栅器）是怎么解决的？

---

## 四、面试高频题

**Q11.**（基础必考）请完整讲一遍 3D Gaussian Splatting：场景如何表示、如何初始化、如何渲染、如何训练、训练中如何增删高斯。

**Q12.**（原理深挖）NeRF 与 3DGS 的渲染方程是同一个，为什么二者在速度、显存/存储、可编辑性、典型伪影上表现差异这么大？

**Q13.**（原理深挖）3DGS 为什么用球谐函数表示颜色？阶数怎么选？球谐系数在渲染时如何使用？

**Q14.**（场景设计）你要为房产平台搭建"拍几十张照片 → 网页/手机上实时漫游"的 3DGS 流水线。从采集到上线，每一步你会怎么做？手机端性能怎么保证？

**Q15.**（追问型）3DGS 光栅化为什么要排序？为什么按 tile 排序？按高斯中心深度排序会带来什么问题？排序这一步对训练的可微性有什么影响？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义列出的理由：显式高斯集合 → GPU 光栅化 100+ fps、训练分钟级、直接平移一部分高斯就能"挪椅子"；到 2026 年 Khronos 已为 glTF 制定高斯泼溅扩展、OpenUSD 26.03 提供了对应 schema。C 过于绝对——讲义的说法是二者积分的是同一个辐射场方程，所以画质"相当"，优势在速度与可编辑性；A、D 是无稽之谈。

### Q2 — 答案：C

`5×10⁶ × 59 × 4 字节 ≈ 1.18×10⁹ 字节 ≈ 1.2 GB`。⚠️ 讲义原文写"That is 240 MB for a five-million-Gaussian scene"，按它自己给出的每高斯约 60 个浮点数计算，240 MB 只对应约 100 万个高斯，500 万个应为约 1.2 GB——这是讲义的计算错误。这也说明了为什么 3DGS 社区非常重视压缩（量化、剪枝、降低 SH 阶数，以及 `.splat` 这类量化格式）。

### Q3 — 答案：B

每个颜色通道的 SH 系数数为 `(L+1)²`：L = 3 时 16 个，L = 2 时 9 个；RGB 三通道分别是 48 和 27。A 只算了单通道；C、D 算错。降一阶可以省下 21 个浮点数，约占每高斯总量的三分之一，是常见的轻量化手段（代价是高光等视角相关效果变弱）。

### Q4 — 答案：B

前到后合成：

- 第 1 个：`T₁ = 1`，贡献 `1 × 0.5 × (1,0,0) = (0.5, 0, 0)`，之后 `T = 1 × (1 - 0.5) = 0.5`；
- 第 2 个：贡献 `0.5 × 0.8 × (0,0,1) = (0, 0, 0.4)`，之后 `T = 0.5 × 0.2 = 0.1`。

合计 `(0.5, 0, 0.4)`，剩余透射率 0.1（这部分会"透出"背景色）。C 是顺序颠倒（蓝在前）的结果——说明**顺序很重要**，这就是必须按深度排序的原因。

### Q5 — 答案：B

讲义：Clone——梯度大但尺度小，说明这里需要更多细节，就地复制一个；Split——梯度大且尺度大，一个大高斯太平滑，拆成两个更小的；Prune——不透明度低于阈值，不再有贡献就删除。致密化每隔 N 次迭代执行一次，高斯数从约 10 万（SfM 点初始化）增长到 1–5 百万。

### Q6 — 答案：B

协方差矩阵必须对称半正定，才能定义合法的椭球。直接对 Σ 的元素做梯度更新，很容易走出合法区域（出现负特征值），之后 `exp(-½ dᵀΣ⁻¹d)` 就没有意义了。`R S Sᵀ Rᵀ` 对任意的四元数（归一化后）和任意尺度都合法，而且"旋转"和"各轴尺度"含义清楚，致密化时缩小尺度、沿主轴分裂都很方便。本节 2D 代码对应的写法是 `R @ diag(s²) @ Rᵀ`，R 由一个角度构造。

### Q7 — 答案：B

讲义："`log_scale`, `opacity_logit`, and `colour_logits` are all unconstrained parameters mapped through the right activation at render time. This is the standard pattern for every 3DGS implementation." `exp` 把任意实数映射到正数（尺度必须为正，且在对数空间更新相当于按比例缩放）；`sigmoid` 映射到 (0, 1)（不透明度和颜色的合法范围）。这样优化器可以在整个实数空间自由更新，不需要投影或截断。

### Q8 — 参考答案

1. **不会变化，`model.depth.grad` 始终是 `None`。** `torch.argsort` 返回整数下标，是不可导的离散操作；`depths` 只通过 `argsort` 参与计算，计算图里没有从 loss 到 `depth` 的路径。Adam 会跳过 `grad is None` 的参数，所以 `depth` 永远停留在随机初始值。
2. **不成立。** 合成顺序在训练全程固定为初始化时的随机顺序。影响：哪些高斯在前、哪些在后无法调整，模型只能通过移动位置、改变尺度/不透明度/颜色来"绕开"不合适的遮挡顺序。对这个 2D 平面拟合任务影响不大（重叠区域可以靠调整不透明度解决），但它说明"声明为参数"≠"能被学习"。
3. 真实 3DGS 中，深度是高斯中心在**相机坐标系下的 z**，由位置 μ 和相机位姿计算得出。排序本身同样不可导，但它只决定"顺序"；梯度通过 alpha 合成中的连续量（αᵢ、Tᵢ、cᵢ）以及投影后的 2D 均值和协方差流回 μ、q、s 等参数。位置 μ 改变后，下一次迭代的深度和顺序自然随之更新——顺序是"随着几何一起变"，而不是被直接优化。

### Q9 — 参考答案

1. 未被覆盖的像素 `T` 保持 1，`out` 保持 0，渲染为**黑色** `(0, 0, 0)`。光栅器隐含了黑色背景。目标图约 86% 的像素是白色，于是这 48 个高斯中相当一部分必须"浪费"在铺满白色背景上：要用接近 1 的不透明度、接近白色的颜色、足够大的尺度去覆盖大片区域，这与"用少量高斯描述两个形状"的初衷相悖，最终 MSE 也会受影响。讲义 Step 4 的目标是黑色背景（`np.zeros`），与光栅器一致；`main.py` 改成了白底，却没有加背景项。真实 3DGS 训练脚本有背景色选项，渲染时把剩余透射率乘以背景色加到结果上。
2. 参考修改：

```python
def rasterise_2d(means, covs, colours, opacities, depths, image_size, bg=None):
    H, W = image_size
    device = means.device
    yy, xx = torch.meshgrid(
        torch.arange(H, dtype=torch.float32, device=device),
        torch.arange(W, dtype=torch.float32, device=device),
        indexing="ij",
    )
    points = torch.stack([xx, yy], dim=-1)
    densities = eval_2d_gaussian(means, covs, points)
    alphas = (opacities[:, None, None] * densities).clamp(0.0, 0.99)

    order = torch.argsort(depths)
    alphas = alphas[order]
    colours_sorted = colours[order]

    T = torch.ones(H, W, device=device)
    out = torch.zeros(H, W, 3, device=device)
    for i in range(means.size(0)):
        a = alphas[i]
        out = out + (T * a)[..., None] * colours_sorted[i][None, None, :]
        T = T * (1.0 - a)
    if bg is None:
        bg = torch.zeros(3, device=device)
    return out + T[..., None] * bg[None, None, :]     # 剩余透射率透出背景色
```

调用时 `rasterise_2d(..., bg=torch.ones(3))`。对 Q4 的例子，剩余透射率 0.1 会让像素再加上 `0.1 × bg`。

### Q10 — 参考答案

1. `points` 为 `(48, 48, 2)`：
   - `flat = points.view(-1, 2)` → `(2304, 2)`
   - `diff = flat[None] - means[:, None]` → 广播得 `(48, 2304, 2)`，即每个高斯到每个像素的偏移
   - `d` → `(48, 2304)`
   - 返回 `density.view(48, 48, 48)`，即 `(G, H, W)`
2. 对每个高斯 g、每个像素 p 计算马氏距离平方 `d[g,p] = diff[g,p]ᵀ · Σ_g⁻¹ · diff[g,p]`。不用 einsum 的写法：

```python
    tmp = diff @ inv                     # (G, P, 2) @ (G, 2, 2) → (G, P, 2)
    d = (tmp * diff).sum(dim=-1)         # (G, P)
```

   之后 `exp(-0.5 * d)` 就是未归一化的高斯密度（峰值为 1）。
3. 问题：计算和内存都是 O(G·H·W)。100 万 × 1920 × 1080 ≈ 2×10¹² 个（高斯, 像素）对，单是 `diff` 张量（每对 2 个 float32）就要约 17 TB，完全不可行。而每个高斯其实只影响屏幕上一个很小的椭圆区域（3σ 之外密度几乎为 0）。真实实现：
   - 对每个投影后的 2D 高斯算出 3σ 包围盒，只分配给与之相交的 16×16 tile；
   - 每个 tile 只对落在其中的高斯按深度排序，每个像素只遍历本 tile 的列表；
   - 当累计透射率足够小时提前终止，α 过小的高斯直接跳过；
   - 用 CUDA kernel 让每个 tile 一个线程块并行执行。
   讲义也提醒：本节的 Python 循环版"Not fast … but exactly the right math and fully differentiable"。

### Q11 — 参考回答要点

- **表示**：数百万个 3D 高斯，每个有位置 μ、旋转四元数 q、log 尺度 s、不透明度（logit）、球谐颜色系数；协方差 `Σ = R S Sᵀ Rᵀ`。
- **初始化**：用 COLMAP/GLOMAP 做 SfM，得到相机位姿和稀疏点云，每个点初始化一个高斯（约 10 万个）。
- **渲染**：投影（`μ' = project(μ)`，`Σ' = J W Σ Wᵀ Jᵀ`）→ 按 3σ 范围分配到 16×16 tile → 每个 tile 按深度排序 → 每个像素前到后 alpha 合成 `C = Σ αᵢTᵢcᵢ`，其中 `αᵢ = opacityᵢ · exp(-½ dᵀΣ'⁻¹d)`，`cᵢ` 由 SH 在视角方向上求值。
- **训练**：渲染训练视角，与真实照片算像素损失，经可微光栅器反向传播更新所有高斯参数，约 3 万次迭代。
- **自适应密度控制**：clone / split / prune（见 Q5），高斯数增长到 1–5 百万。
- **加分点**：原论文的损失是 L1 与 D-SSIM 的加权组合；SH 阶数是从 0 阶开始、训练中逐步增加的；周期性地把不透明度重置为较小值，帮助清除漂浮物（floaters）。

### Q12 — 参考回答要点

- **同一个方程**：`C = Σ αᵢ Tᵢ cᵢ` 是经典体渲染；讲义指出这正是两者画质相当的原因。
- **差异来自表示和求值方式**：
  - NeRF：隐式 MLP，沿每条光线采样上百个点，每个点一次 MLP 前向——渲染慢（秒级/帧）、训练慢（小时级）；
  - 3DGS：显式稀疏高斯，投影后光栅化，只计算真正覆盖像素的少量高斯——渲染 100+ fps、训练分钟级。
- **存储**：NeRF 的 MLP 很小（原始 NeRF 论文中网络权重约 5 MB）；3DGS 要存数百万个高斯，原始数据可达数百 MB 到 GB 级（见 Q2），这是 3DGS 公认的短板，所以有大量压缩工作。
- **可编辑性**：3DGS 的高斯可直接选中、平移、删除；NeRF 的知识分散在权重里，局部编辑通常需要重训。
- **典型伪影**：3DGS 有漂浮物、视角远离训练分布时的拉伸/空洞、排序导致的"popping"；NeRF 有模糊和雾状伪影。
- **常见误区**：认为 3DGS 在所有方面都优于 NeRF——在存储和极少视角的泛化上它并不占优。

### Q13 — 参考回答要点

- **为什么需要**：真实物体的颜色随视角变化（高光、光泽），用一个固定 RGB 无法表达。SH 是球面上的傅里叶基，把"颜色随方向的函数"`c(direction)` 展开成少量系数。
- **阶数与系数**：截断到 L 阶，每通道 `(L+1)²` 个基函数；0 阶 1 个（常数颜色，等价于漫反射），3 阶 16 个（能表达朗伯着色、高光和轻微反射）；RGB 共 `3(L+1)²` 个系数，3 阶为 48 个。
- **渲染时**：计算从相机指向高斯中心的单位方向 → 在该方向上求出 16 个基函数值 → 与该高斯的 `(16, 3)` 系数做点积得到 RGB（本节 `eval_sh_degree_3` 就是这一步）。
- **选择**：阶数越高视角效果越好，但存储和过拟合风险也越大；移动端常降到 0–1 阶；高光强烈的场景（金属、玻璃）保留 3 阶。
- **加分点**：SH 基函数是**正交归一**的（我用蒙特卡洛积分验证过本节 16 个基函数的 Gram 矩阵约等于单位阵），所以不同阶的系数互不干扰；渐进地增加 SH 阶数能避免早期视角相关项过拟合噪声。

### Q14 — 参考回答要点

- **采集**：手机/无人机围绕场景拍摄，保证足够重叠（讲义的流程用 20–50 张照片起步，大场景更多）；固定曝光和白平衡，避免运动模糊、镜面和大面积无纹理区域；室内按房间分段、在门口做过渡。
- **位姿**：COLMAP 或 GLOMAP 求相机位姿和稀疏点；检查重投影误差，剔除失败帧。
- **训练**：nerfstudio `splatfacto` 或 gsplat，在 RTX 4090 上约 10–30 分钟。
- **编辑清理**：SuperSplat 等工具删除漂浮物、裁剪场景边界、分割出房间。
- **压缩与导出**：降低 SH 阶数、剪掉低不透明度高斯、量化（`.splat` 格式）；按目标平台导出 glTF `KHR_gaussian_splatting`（Web/跨引擎）或 OpenUSD（Omniverse / Vision Pro 管线）。
- **移动端性能**：限制高斯数量（如百万级以内）、LOD 分级加载、按视锥剔除、降低分辨率或帧率上限；渐进式流式加载。
- **质量把关**：留出部分照片作为测试视角计算 PSNR / SSIM / LPIPS，人工检查漫游路径上的空洞和伪影。

### Q15 — 参考回答要点

- **为什么要排序**：alpha 合成不满足交换律（Q4 中红蓝顺序互换结果完全不同），必须按从前到后（或从后到前）的顺序累乘透射率。
- **为什么按 tile**：每个像素单独排序代价太高；把屏幕分成 16×16 的 tile，每个 tile 只排序与之相交的高斯，一个 tile 内的所有像素共享同一个有序列表，GPU 可以每个 tile 一个线程块并行处理。
- **按中心深度排序的问题**：一个高斯有空间范围，按中心深度得到的顺序对某些像素并不准确；视角移动时两个高斯中心深度的先后可能突然交换，造成"popping"闪烁。
- **可微性**：排序是离散操作，没有梯度；梯度只流经合成公式里的连续量（α、T、颜色）和投影。所以 3DGS 是"在固定顺序下可微"，顺序随每次迭代的几何重新计算——本节代码里 `depth` 参数拿不到梯度正是这一点的直接体现。
- **加分点**：提前终止（透射率低于阈值即停止）和跳过极小 α 的高斯，是实时性能的关键。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 13 3D 视觉 — 点云和 NeRF](../../13-3d-vision-nerf/docs/zh.md)：NeRF 的体渲染方程，本节的直接对照对象。
- [阶段 01 · 12 张量运算](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：广播与 `einsum`。
- [阶段 01 · 03 矩阵变换](../../../01-math-foundations/03-matrix-transformations/docs/zh.md)：旋转矩阵、`R S Rᵀ` 的几何意义。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：多元高斯与协方差矩阵。
- [阶段 01 · 20 傅里叶变换](../../../01-math-foundations/20-fourier-transform/docs/zh.md)：球谐函数是"球面上的傅里叶基"。

### 本节被哪些后续内容用到
- [阶段 04 · 26 单目深度和几何估计](../../26-monocular-depth/docs/zh.md)：从图像恢复几何，可为重建提供先验。
- [阶段 04 · 28 世界模型与视频扩散](../../28-world-models-video-diffusion/docs/zh.md)：讲义提到的生成式 splat（文本生成整个场景）与 4D 动态场景。
- [阶段 08 · 12 3D 生成](../../../08-generative-ai/12-3d-generation/docs/zh.md)：以高斯为表示的 3D 生成模型。
- [阶段 04 · 15 实时视觉——边缘部署](../../15-real-time-edge/docs/zh.md)：移动端实时渲染与模型压缩的工程思路。

### 延伸关键词
`EWA splatting` · `tile-based rasterization` · `adaptive density control` · `spherical harmonics` · `COLMAP / GLOMAP` · `gsplat / splatfacto` · `4DGS / Deformable-3DGS` · `3DGS compression (quantization / pruning)` · `KHR_gaussian_splatting` · `OpenUSD` · `PSNR / SSIM / LPIPS`
