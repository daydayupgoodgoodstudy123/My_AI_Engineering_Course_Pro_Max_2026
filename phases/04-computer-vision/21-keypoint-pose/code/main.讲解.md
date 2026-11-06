# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 21 节 关键点检测和姿势估计 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，全程 CPU） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`）；无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

讲义的核心论断是"关键点检测器就是一个热图回归器，其余都是簿记工作"。这份代码把这句话完整实现了一遍：

1. **高斯热图目标**：如何用 `meshgrid` 一次性生成以关键点为中心的 2D 高斯。
2. **编码器–解码器热图网络**：stride-2 卷积下采样 + 转置卷积上采样，输出与输入同尺寸的 K 通道热图。
3. **坐标解码**：`reshape + argmax + // 和 %` 把热图峰值批量转成 `(x, y)`。
4. **亚像素细化**：在 argmax 附近用邻域差值修正整数坐标。
5. **评测**：预测坐标与真值的平均 L2 像素误差，对比"整数 argmax"和"亚像素"两种解码。
6. **（隐藏考点）任务是否可学**：本文件的合成数据让 4 个关键点外观完全相同、顺序随机，通道身份不可学——这是读懂代码后最值得发现的问题（见 3.5 节）。

> 一句话：**训练时把坐标"画"成高斯热图做像素级回归，推理时再从热图峰值"读"回坐标**——这就是 HRNet、ViTPose、MediaPipe 的共同骨架。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `gaussian_heatmap(size, cx, cy, sigma)` | 函数（NumPy） | 生成 `size×size` 的高斯热图，峰值 1 在 `(cx, cy)` | 热图目标 |
| `TinyKeypointNet` | `nn.Module` 类 | 2 次下采样 + 1 层中间卷积 + 2 次转置卷积上采样，输出 K 张热图 | 热图回归网络 |
| `heatmap_to_coords(heatmaps)` | 函数 | 每张热图取 argmax，返回 `(N, K, 2)` 的 `(x, y)` | 坐标解码 |
| `subpixel_refine(heatmaps)` | 函数 | 在整数峰值处按左右/上下邻居差值做小幅修正 | 亚像素定位 |
| `make_synthetic_sample(size, rng)` | 函数（NumPy） | 白底画 4 个黑块，并生成 4 张高斯热图和真值坐标 | 合成数据 |
| `main()` | 演示入口 | 训练 200 步（MSE），再在 8 张新图上比较两种解码的 L2 误差 | 训练与评测 |

数据流：`make_synthetic_sample` → `(img, hms, kps)` → 堆叠成 batch → `TinyKeypointNet` → `F.interpolate`（对齐尺寸）→ `F.mse_loss`；评测时 → `heatmap_to_coords` / `subpixel_refine` → 与 `kps` 求 L2 误差。

---

## 3. 逐段精讲

### 3.1 高斯热图

```python
def gaussian_heatmap(size, cx, cy, sigma=2.0):
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    return np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2)).astype(np.float32)
```

- `np.meshgrid(..., indexing="ij")` 生成两个 `(size, size)` 的网格：`yy[i, j] = i`（行号，即 y），`xx[i, j] = j`（列号，即 x）。`"ij"` 是"矩阵下标"约定，保证 `热图[行, 列] = 热图[y, x]`；如果用默认的 `"xy"`，对正方形图看不出区别，但对非正方形图形状会反过来，是常见 bug 源头。
- 公式正是讲义里的 `exp(-((x - cx)² + (y - cy)²) / (2σ²))`：中心处为 1，距离 σ 处约 0.61，距离 2σ 处约 0.14。σ = 2 意味着有效"光斑"直径大约 8–12 像素。
- 全程是**向量化**的：没有 Python 循环，`size×size` 个像素一次算完。
- `.astype(np.float32)`：PyTorch 默认用 float32，提前转好避免和模型输出 dtype 不一致。
- 讲义解释了为什么用高斯而不是"只有一个像素为 1"：预测偏了 1 像素，高斯目标给的损失很小，独热目标却和偏了 30 像素一样"全错"，学习信号更平滑。

### 3.2 热图网络：下采样再上采样

```python
class TinyKeypointNet(nn.Module):
    def __init__(self, num_keypoints=4, base=16):
        super().__init__()
        self.down1 = nn.Sequential(nn.Conv2d(3, base, 3, 2, 1), nn.ReLU(inplace=True))
        self.down2 = nn.Sequential(nn.Conv2d(base, base * 2, 3, 2, 1), nn.ReLU(inplace=True))
        self.mid = nn.Sequential(nn.Conv2d(base * 2, base * 2, 3, 1, 1), nn.ReLU(inplace=True))
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, 2)
        self.up2 = nn.ConvTranspose2d(base, num_keypoints, 2, 2)

    def forward(self, x):
        h1 = self.down1(x)
        h2 = self.down2(h1)
        h3 = self.mid(h2)
        u1 = self.up1(h3)
        return self.up2(u1)
```

输入 `(N, 3, 64, 64)` 的形状变化：

| 层 | 输出形状 | 说明 |
|----|---------|------|
| `down1`：Conv 3×3，stride 2，pad 1 | `(N, 16, 32, 32)` | 尺寸减半 |
| `down2`：Conv 3×3，stride 2，pad 1 | `(N, 32, 16, 16)` | 再减半 |
| `mid`：Conv 3×3，stride 1，pad 1 | `(N, 32, 16, 16)` | 尺寸不变 |
| `up1`：ConvTranspose 2×2，stride 2 | `(N, 16, 32, 32)` | 尺寸翻倍 |
| `up2`：ConvTranspose 2×2，stride 2 | `(N, 4, 64, 64)` | 再翻倍，通道数 = 关键点数 |

- 用 stride-2 卷积代替池化做下采样，用 kernel=2、stride=2 的转置卷积做上采样（每个输入像素"展开"成 2×2 输出块，互不重叠）。
- 输出通道数 = `num_keypoints`，**每个通道对应一个关键点**——这是热图方法的约定。
- 参数量 16,660（按层公式算出），非常小。
- ⚠️ 讲义称之为 "U-Net-style"，但它**没有跳跃连接**（U-Net 会把 `h1` 这类高分辨率特征拼到解码器里，对精确定位很关键），而且 `up1` 和 `up2` 之间**没有激活函数**，两个转置卷积合起来仍是线性映射。这是为了代码短小做的简化。
- 感受野很小：输出上一个点大约只能"看到"输入中十几个像素的范围，这一点在 3.5 节会变得重要。

### 3.3 坐标解码：argmax 的向量化写法

```python
def heatmap_to_coords(heatmaps):
    N, K, H, W = heatmaps.shape
    hm = heatmaps.reshape(N, K, -1)
    idx = hm.argmax(dim=-1)
    ys = (idx // W).float()
    xs = (idx % W).float()
    return torch.stack([xs, ys], dim=-1)
```

- `reshape(N, K, -1)` 把每张 `H×W` 热图展平成长度 `H·W` 的向量（`-1` 让 PyTorch 自动推断这一维）。
- 在展平向量上 `argmax` 得到一维下标 `idx`；行优先存储下，`行 = idx // W`、`列 = idx % W`。例：W = 64 时 `idx = 2085` → `y = 32, x = 37`。
- `torch.stack([xs, ys], dim=-1)` 返回 **(x, y)** 顺序，形状 `(N, K, 2)`。与真值 `kps`（第 0 列是 cx、第 1 列是 cy）一致。
- 讲义："One line at inference." 一次处理整个 batch 的所有关键点，没有循环。
- ⚠️ argmax 只能给出整数坐标，最大误差每轴 0.5 个热图像素；真实模型的热图常是输入的 1/4 分辨率，误差要再乘 4。

### 3.4 亚像素细化

```python
def subpixel_refine(heatmaps):
    N, K, H, W = heatmaps.shape
    coords = heatmap_to_coords(heatmaps)
    refined = coords.clone()
    for n in range(N):
        for k in range(K):
            x, y = int(coords[n, k, 0]), int(coords[n, k, 1])
            if 0 < x < W - 1 and 0 < y < H - 1:
                hm = heatmaps[n, k]
                dx = 0.25 * (hm[y, x + 1] - hm[y, x - 1])
                dy = 0.25 * (hm[y + 1, x] - hm[y - 1, x])
                refined[n, k, 0] = x + dx
                refined[n, k, 1] = y + dy
    return refined
```

- 思路：真实峰值往"右邻居比左邻居大"的方向偏，所以按左右差值把 x 往高的一侧挪一点，y 同理。
- `0 < x < W - 1` 是**链式比较**，保证左右上下邻居都存在，否则越界。
- `refined = coords.clone()`：先复制一份，边界上的点保持整数坐标不变。
- 双重 Python 循环：N×K 很小（8×4），清晰优先；真实批量推理会用张量操作向量化。
- ⚠️ **公式与经典实现不同**：SimpleBaseline / HRNet 的推理代码是 `coords += np.sign(diff) * 0.25`，即"朝高的一侧固定挪 1/4 像素"；这里写成了 `0.25 × 原始差值`。对 σ = 2、峰值 1 的高斯，相邻两点差值只有零点几，修正量被压缩约一个数量级——例如真实中心 30.3 时，代码给出约 30.033，`sign` 版本给 30.25，对数抛物线拟合给出精确的 30.300（我用 NumPy 验证过，见测验 Q10）。而且修正量会随热图整体幅值变化，不稳定。
- ⚠️ 另外，本文件的真值坐标都是**整数**（`rng.integers`），热图中心就在网格上——理想情况下 argmax 已经是精确答案，亚像素细化在这个演示里本来就没有提升空间。要观察它的价值，需要让真值带小数（例如 `rng.uniform`）。

### 3.5 合成数据（以及一个让任务不可学的缺陷）

```python
def make_synthetic_sample(size=64, rng=None):
    rng = rng or np.random.default_rng()
    img = np.ones((3, size, size), dtype=np.float32)
    kps = rng.integers(10, size - 10, size=(4, 2))
    for cx, cy in kps:
        img[:, cy - 2:cy + 2, cx - 2:cx + 2] = 0.0
    hms = np.stack([gaussian_heatmap(size, cx, cy) for cx, cy in kps])
    return img, hms, kps.astype(np.float32)
```

- 白色 3 通道画布上，随机 4 个位置（坐标在 [10, 53]，离边界至少 10 像素）画 4×4 黑块；每个关键点生成一张热图，`np.stack` 成 `(4, 64, 64)`。
- `rng = rng or np.random.default_rng()`：调用方传入生成器就用它（`main` 传入 `default_rng(0)`，结果可复现），否则新建一个。
- `for cx, cy in kps`：对 `(4, 2)` 数组按行迭代并解包。
- ⚠️ **致命问题：关键点身份不可辨认。** 4 个黑块长得完全一样，`kps` 的行顺序只是随机抽样的顺序，与位置无关。热图第 k 通道要预测"第 k 个关键点"，但网络仅凭图像无法知道哪个黑块是第 k 个。在 MSE 下，每个通道的最优输出都是"4 个高斯的平均"，所有通道输出相同、argmax 选中同一个黑块，最多 1 个通道正确。我用 NumPy 模拟这个"最优但分不清身份"的预测器：MSE ≈ 0.00225（全输出 0 时为 0.00307），平均 L2 误差 ≈ **16 像素**。真实人体关键点之所以可学，是因为"左手腕"和"右膝"在外观和上下文上本来就不同。修复办法：给每个关键点不同的颜色（例如第 k 个关键点只在特定颜色通道上置 0），或改成只预测一个"所有关键点"的通道、评测时做匹配（见测验 Q9）。
- ⚠️ 半像素偏差：`cy-2:cy+2` 覆盖 4 行，中心在 `cy - 0.5`；黑块中心 `(cx-0.5, cy-0.5)` 与热图中心 `(cx, cy)` 有固定的半像素偏移。网络能学会补偿，但做亚像素研究时这类约定必须统一。

### 3.6 训练循环

```python
    torch.manual_seed(0)
    rng = np.random.default_rng(0)

    model = TinyKeypointNet(num_keypoints=4)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)

    for step in range(200):
        batch = [make_synthetic_sample(rng=rng) for _ in range(16)]
        imgs = torch.from_numpy(np.stack([b[0] for b in batch]))
        hms = torch.from_numpy(np.stack([b[1] for b in batch]))
        pred = model(imgs)
        pred = F.interpolate(pred, size=hms.shape[-2:], mode="bilinear", align_corners=False)
        loss = F.mse_loss(pred, hms)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 40 == 0:
            print(f"step {step:3d}  mse {loss.item():.4f}")
```

- 两个种子分别控制模型初始化（`torch.manual_seed`）和数据（NumPy 的 `default_rng(0)`），整个脚本可复现。
- `[b[0] for b in batch]` 取出每个样本的图像，`np.stack` 堆成 `(16, 3, 64, 64)`；热图堆成 `(16, 4, 64, 64)`。
- `F.interpolate(..., size=hms.shape[-2:])`：把预测缩放到目标尺寸。⚠️ 这里网络输出已经是 64×64，缩放比例为 1、`align_corners=False` 时双线性插值等价于恒等映射，这一行**实际不起作用**；它是为"网络输出分辨率低于目标"的真实情形准备的防御代码。
- `F.mse_loss`：逐像素均方误差（讲义："Loss is per-pixel MSE against Gaussian targets"）。⚠️ 热图绝大部分是 0，"全输出 0"的 MSE 只有约 0.0031，所以 MSE 很小不代表定位准确，必须看坐标误差。

### 3.7 评测：两种解码的 L2 误差

```python
    model.eval()
    with torch.no_grad():
        eval_batch = [make_synthetic_sample(rng=rng) for _ in range(8)]
        imgs = torch.from_numpy(np.stack([b[0] for b in eval_batch]))
        gt = torch.from_numpy(np.stack([b[2] for b in eval_batch]))
        pred = model(imgs)
        pred = F.interpolate(pred, size=(64, 64), mode="bilinear", align_corners=False)
        coords = heatmap_to_coords(pred)
        refined = subpixel_refine(pred)
        l2_int = (coords - gt).norm(dim=-1).mean().item()
        l2_sub = (refined - gt).norm(dim=-1).mean().item()
```

- 8 张新图（生成器继续往下抽，不与训练样本重复），`gt` 形状 `(8, 4, 2)`。
- `(coords - gt).norm(dim=-1)`：每个关键点的欧氏距离 `(8, 4)`，`.mean()` 得到 32 个关键点的平均像素误差。这正是讲义练习 1 要求报告的指标。
- 输出打印两行，对比整数 argmax 与亚像素细化。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 高斯热图 + MSE | 空间对齐、监督平滑 | 前景像素少，MSE 被背景主导；生产中常加权或调 σ |
| 输出与输入同分辨率 | 坐标无需换算，演示简单 | 真实模型多在 1/4 分辨率出热图，省算力，但需要亚像素解码 |
| 无跳跃连接的编码器–解码器 | 代码极短 | 定位精度差；HRNet 全程保持高分辨率分支 |
| argmax 解码 | 简单、一行搞定 | 不可导、有量化误差；可用 soft-argmax 或抛物线拟合 |
| `0.25 × 差值` 的亚像素修正 | 形式简单 | 修正量过小且依赖幅值；经典实现用 `sign`，更精确用对数抛物线 |
| 4 个相同外观的黑块 | 生成简单 | 通道身份不可学；真实关键点语义各不相同，或需要分组/匹配机制 |
| 平均 L2 像素误差 | 直观 | 不考虑目标尺度与关键点难度；正式评测用 PCK / OKS |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def gaussian_heatmap(size, cx, cy, sigma=2.0)` | 不传时用默认值 |
| `or` 提供默认对象 | `rng = rng or np.random.default_rng()` | `rng` 为 `None` 时新建生成器 |
| 类继承与 `super()` | `class TinyKeypointNet(nn.Module)` | 注册子模块与参数 |
| 元组解包 | `N, K, H, W = heatmaps.shape`、`yy, xx = np.meshgrid(...)` | 一次取出多个值 |
| 对数组按行迭代解包 | `for cx, cy in kps:` | `(4, 2)` 数组每次给出一行的两个数 |
| 嵌套 `for` 循环 | `for n in range(N): for k in range(K):` | 遍历 batch 与关键点 |
| 链式比较 | `if 0 < x < W - 1 and 0 < y < H - 1:` | 等价于 `0 < x and x < W - 1` |
| `int()` 转换张量元素 | `int(coords[n, k, 0])` | 把 0 维张量转成 Python 整数，用作下标 |
| 整除与取余 | `idx // W`、`idx % W` | 一维下标 → 行、列 |
| 列表推导式 | `[make_synthetic_sample(rng=rng) for _ in range(16)]` | `_` 表示不使用循环变量 |
| 幂运算 | `(xx - cx) ** 2`、`sigma ** 2` | 平方 |
| `with` 上下文管理器 | `with torch.no_grad():` | 评测时不记录梯度 |
| f-string 格式符 | `{loss.item():.4f}`、`{l2_int:.3f} px`、`"\nmean L2 ..."` | 控制小数位；`\n` 先换行 |
| NumPy 网格与切片赋值 | `np.meshgrid(..., indexing="ij")`、`img[:, cy-2:cy+2, cx-2:cx+2] = 0.0` | 生成坐标网格；对所有通道的矩形区域赋值 |
| `np.stack` / `torch.stack` | `np.stack([b[0] for b in batch])`、`torch.stack([xs, ys], dim=-1)` | 沿新维度堆叠 |
| `-1` 自动推断维度 | `heatmaps.reshape(N, K, -1)` | 让框架算出这一维的大小 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 热图生成、坐标解码、亚像素公式和合成数据都只依赖 NumPy，我已按相同逻辑单独验证（包括 `exp(-0.5) ≈ 0.607` 的热图值、`2085 → (37, 32)` 的解码、亚像素公式在理想高斯上的修正量，以及关键点身份不可辨时的最优 MSE 和误差）。根据代码，输出格式如下：

```text
step   0  mse ?.????
step  40  mse ?.????
step  80  mse ?.????
step 120  mse ?.????
step 160  mse ?.????

mean L2 error (argmax):    ??.??? px
mean L2 error (subpixel):  ??.??? px
```

可以确定或合理预期的部分：

- 训练日志 5 行。随机初始化时输出不为 0，第一行 MSE 取决于初始化；很快会降到"全输出 0"的水平（约 0.0031）附近，之后最多降到约 0.0022 的平台——这是"4 个通道都输出 4 个高斯的平均"时的理论最优值（见 3.5 节），不会接近 0。
- 两行 L2 误差预计都在**十几像素**的量级（理想化模拟值约 16 px），而且两者几乎相同：真值是整数坐标，`0.25 × 差值`的修正量又只有零点零几像素。
- 如果你实际运行看到的误差很大，这不是训练步数不够——是数据本身没有告诉网络"哪个点是几号"。按 3.5 节修复数据后，误差应能降到 1–2 像素以内（需实际运行确认）。

---

## 7. 动手改一改

1. **修复身份问题**：让前 3 个关键点分别只在 R、G、B 某一个通道上置 0，第 4 个在三个通道上都置 0（共 4 种不同颜色），重新训练，对比 L2 误差的变化。
2. **亚像素有用武之地**：把 `kps` 改成 `rng.uniform(10, size - 10, size=(4, 2))` 的浮点坐标（画黑块时取整），再比较 argmax、代码公式、`sign` 版本、对数抛物线（测验 Q10）四种解码的误差（讲义练习 2）。
3. **低分辨率热图**：去掉 `up2`，让网络输出 32×32 的热图，训练时把**目标**下采样到 32×32，推理时再把坐标乘 2；观察整数 argmax 误差如何变大、亚像素细化如何变得重要。
4. **加跳跃连接**：把 `h1` 和 `u1` 在通道维拼接后再送入 `up2`（注意改 `up2` 的输入通道数），并在 `up1` 后加 ReLU，比较收敛速度。
5. **换评测指标**：实现 PCK@α（误差小于 α × 64 的比例，α 取 0.05），与平均 L2 误差一起报告。
6. **soft-argmax**：对每张热图做 `softmax` 后求坐标的期望，直接对坐标用 L1 损失训练，比较与热图 MSE 的效果。

---

## 8. 常见坑

- **(x, y) 与 (row, col) 搞反**：`hm[y, x]` 先行后列，`heatmap_to_coords` 返回 `(x, y)`；混用会让坐标沿对角线镜像。
- **`meshgrid` 的 `indexing`**：默认 `"xy"` 与 `"ij"` 的输出形状在非方形图上不同。
- **只看 MSE**：热图稀疏，"全输出 0"的 MSE 也很低，必须看坐标误差 / PCK / OKS。
- **关键点身份不可辨**：外观相同、顺序随机的点无法分到固定通道——要么让外观可区分，要么设计与顺序无关的输出与评测。
- **亚像素公式写错或用错场景**：`0.25 × 差值`与 `0.25 × sign(差值)` 不是一回事；真值本来就是整数时，细化不会带来提升。
- **边界越界**：峰值在热图边缘时没有左右邻居，必须像代码一样先检查 `0 < x < W - 1`。
