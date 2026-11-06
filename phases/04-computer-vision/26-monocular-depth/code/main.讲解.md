# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 26 节 单目深度和几何估计 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；会在系统临时目录写出 `depth_demo.ply`） ｜ **依赖**：`torch`、`numpy` + 标准库（`os`、`tempfile`）；不加载任何深度模型，无需联网

---

## 1. 这份代码在考察什么

真正的深度模型（Depth Anything、Marigold、UniDepth）调用起来只要几行。这份代码练的是**模型前后**的两件事——它们决定了你能不能正确评价模型、能不能把深度真正用起来：

1. **深度评测指标**：AbsRel 与 δ<1.25 怎么算、为什么要防除零、为什么要屏蔽无效像素。
2. **尺度-平移对齐**：相对深度模型的输出尺度和偏移是任意的，评测前要用最小二乘拟合 `a·pred + b ≈ gt`。代码故意构造了一个"放大 3 倍再加 0.7"的预测，让你亲眼看到不对齐时指标有多离谱。
3. **针孔相机反投影**：用内参 `(fx, fy, cx, cy)` 把每个像素的 `(u, v, d)` 抬升成 3D 点 `(X, Y, Z)`。
4. **点云导出**：手写 ASCII `.ply` 文件，可直接用 MeshLab / CloudCompare 打开。
5. **合成场景做冒烟测试**：没有真实数据也能验证整条链路。

> 一句话：**深度图只是一张单通道图像，"内参 + 反投影"才让它变成 3D；"对齐 + 指标"才让你知道它准不准。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `abs_rel_error(pred, target, mask)` | 函数（torch） | `mean(|pred - gt| / gt)` | AbsRel 指标 |
| `delta_accuracy(pred, target, threshold, mask)` | 函数（torch） | `max(pred/gt, gt/pred) < 1.25` 的比例 | δ 阈值准确率 |
| `align_scale_shift(pred, target, mask)` | 函数（torch） | 最小二乘求 `a, b`，返回 `a·pred + b` | 尺度-平移不变评测 |
| `depth_to_point_cloud(depth, intrinsics)` | 函数（numpy） | 每个像素反投影成 `(X, Y, Z)` | 针孔相机模型 |
| `synthetic_depth(size)` | 函数（numpy） | 一块渐变"地面" + 中间一个更近的"盒子" | 合成测试场景 |
| `write_ply(path, points, colors)` | 函数 | 写 ASCII PLY 点云文件 | 点云导出 |
| `main()` | 演示入口 | 指标 → 对齐 → 反投影 → 写文件 | — |

数据流：`synthetic_depth` 生成真值 `gt` → 加噪声得到 `pred`、再线性变换得到 `scaled_pred` → 三组指标对比 → `align_scale_shift` 对齐后再评测；另一条线：`gt` + 内参 → `depth_to_point_cloud` → `write_ply`。

---

## 3. 逐段精讲

### 3.1 AbsRel：相对误差的平均

```python
def abs_rel_error(pred, target, mask=None):
    if mask is not None:
        pred = pred[mask]
        target = target[mask]
    return (torch.abs(pred - target) / target.clamp(min=1e-6)).mean().item()
```

- 公式 `AbsRel = mean(|d_pred - d_gt| / d_gt)`，越低越好。讲义给出的经验值：生产级模型 0.05–0.1。
- **为什么除以真值**：深度误差的"严重程度"和距离有关——1 米处差 0.5 米很严重，50 米处差 0.5 米几乎可以忽略。除以真值把误差变成相对比例，远近一视同仁。
- `target.clamp(min=1e-6)`：防止真值为 0 时除零。但更重要的是 `mask` 参数——讲义强调"评测前一定要屏蔽无效像素（0、NaN、饱和值）"。clamp 只能防崩溃，防不了"真值为 0 的像素把平均值拉到天上去"。
- `pred[mask]`：用布尔张量索引，取出 mask 为 True 的元素，结果是**一维**张量。
- `.mean().item()`：求平均后转成 Python 浮点数，方便打印和记录。

### 3.2 δ<1.25：落在 25% 以内的像素比例

```python
def delta_accuracy(pred, target, threshold=1.25, mask=None):
    if mask is not None:
        pred = pred[mask]
        target = target[mask]
    ratio = torch.maximum(pred / target.clamp(min=1e-6), target / pred.clamp(min=1e-6))
    return (ratio < threshold).float().mean().item()
```

- `max(pred/gt, gt/pred)` 把高估和低估都变成 ≥ 1 的比值；比值 < 1.25 记为"正确"。越高越好，SOTA 在 0.9 以上。
- `torch.maximum` 是**逐元素**取两者较大值（区别于 `torch.max` 求整个张量的最大值）。
- 两边都 clamp：预测值也可能是 0 或负数（本例 `pred = gt + 0.4·噪声`，靠近 1 米的像素有小概率变负）。负的预测会让 `pred/gt` 为负，但 `gt / clamp(pred)` 会变成一个巨大的正数，于是比值远超 1.25，被正确地判为"错误"。
- `(ratio < threshold).float().mean()`：布尔 → 0/1 → 平均，就是比例。

### 3.3 尺度-平移对齐：一次最小二乘

```python
def align_scale_shift(pred, target, mask=None):
    if mask is not None:
        p = pred[mask]
        t = target[mask]
    else:
        p = pred.flatten()
        t = target.flatten()
    A = torch.stack([p, torch.ones_like(p)], dim=1)
    sol = torch.linalg.lstsq(A, t.unsqueeze(-1))
    a, b = sol.solution[:2, 0]
    return a * pred + b
```

- 目标：找 `a, b` 使 `Σ (a·pᵢ + b - tᵢ)²` 最小。写成矩阵形式就是 `A @ [a, b]ᵀ ≈ t`，其中 `A` 的每一行是 `[pᵢ, 1]`——那一列 1 就是用来拟合偏移 `b` 的。
- `torch.stack([p, torch.ones_like(p)], dim=1)`：把两个长度为 N 的向量按列拼成 `(N, 2)` 矩阵。
- `t.unsqueeze(-1)`：`lstsq` 要求右端是二维 `(N, 1)`，所以补一维。
- `sol.solution` 形状为 `(2, 1)`，`[:2, 0]` 取出两个系数，再用元组解包得到 `a`、`b`。
- **只在 mask 内拟合，但对整张 `pred` 应用**：`return a * pred + b` 用的是原始的完整 `pred`，保持输出形状不变，下游可以直接拿去和 `gt` 比。
- **为什么这样设计**：讲义要求"评测 MiDaS / Depth Anything 前先跑 `align_scale_shift`"。相对深度模型只对顺序和相对结构负责，不对齐就算 AbsRel，测的是尺度不匹配。
- ⚠️ 对齐只能消除**线性**的尺度和偏移，消除不了噪声；而且预测带噪声时，最小二乘拟合出的斜率会被"稀释"（小于真实的 1/3），等于把预测向均值收缩，这会让对齐后的误差甚至略低于原始 `pred`（见第 6 节）。
- ⚠️ 讲义 Step 2 写的是 `coeffs, *_ = torch.linalg.lstsq(...)`（按位置解包返回值），这里写的是 `sol.solution`（按字段名访问），两者等价；后者可读性更好。
- ⚠️ 有的相对深度模型输出的是**视差（disparity，约等于 1/深度）**而不是深度，这时应在视差空间对齐后再取倒数；本代码处理的是"预测已经是深度"的情形。

### 3.4 针孔反投影：从像素到 3D 点

```python
def depth_to_point_cloud(depth, intrinsics):
    H, W = depth.shape
    fx, fy, cx, cy = intrinsics
    v, u = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
    z = depth
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    return np.stack([x, y, z], axis=-1)
```

- 公式就是讲义里的 `X = (u - cx)·d / fx`，`Y = (v - cy)·d / fy`，`Z = d`。直观理解：`(u - cx) / fx` 是这个像素对应的射线在水平方向的"斜率"，乘以深度就得到真实的横向偏移。
- `np.meshgrid(..., indexing="ij")`：生成两张 `(H, W)` 的坐标网格，`v[i, j] = i`（行号）、`u[i, j] = j`（列号）。`"ij"` 表示"第一个输出对应第一个输入，按矩阵下标排列"。
- **为什么这样设计**：所有像素一次性向量化计算，没有 Python 循环；`np.stack(..., axis=-1)` 把三个 `(H, W)` 拼成 `(H, W, 3)`，保留图像的空间结构，后面要配颜色或按像素索引都方便。
- 坐标系约定：x 向右、y 向下、z 向前（OpenCV 风格）。导入 Open3D 或 OpenGL 系工具时，y、z 方向可能要取反。
- ⚠️ 去掉 `indexing="ij"` 的后果：默认 `"xy"` 会返回 `(W, H)` 形状。非正方形图像会报广播错误；而**正方形图像（比如这里的 96×96）不会报错，只会悄悄把 u、v 转置**——这是最难发现的一类坐标 bug（测验 Q9 有详细分析）。

### 3.5 合成深度场景

```python
def synthetic_depth(size=96):
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    depth = 1.0 + (yy / size) * 4.0
    mask = (np.abs(xx - size / 2) < size / 6) & (np.abs(yy - size * 0.6) < size / 6)
    depth[mask] = 2.0
    return depth.astype(np.float32)
```

- "地面"：深度从第 0 行的 1.0 线性增加到最后一行的约 4.96（讲义注释说"从上方的近处到下方的远处"）。注意这和真实照片相反——真实地面通常是**下方近、上方远**——但作为测试数据没有影响。
- "盒子"：`|x - 48| < 16` 且 `|y - 57.6| < 16`，即第 42–73 行、第 33–63 列，共 992 个像素，深度固定为 2.0。这几行的地面深度在 2.75–4.04 之间，所以盒子"更近"，在深度图上形成一个有清晰边界的台阶。
- `astype(np.float32)`：和 PyTorch 默认的 `float32` 对齐，`torch.from_numpy` 之后不用再转换类型。

### 3.6 写 PLY 点云文件

```python
def write_ply(path, points, colors=None):
    points = points.reshape(-1, 3)
    n = points.shape[0]
    header = [
        "ply", "format ascii 1.0",
        f"element vertex {n}",
        "property float x", "property float y", "property float z",
    ]
    if colors is not None:
        header += ["property uchar red", "property uchar green", "property uchar blue"]
    header.append("end_header")
    with open(path, "w") as f:
        f.write("\n".join(header) + "\n")
        # ... 有颜色时每行 6 个数，否则每行 3 个数
            for p in points:
                f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}\n")
```

- PLY 格式 = 文本头（声明有多少个顶点、每个顶点有哪些属性）+ 逐行数据。`reshape(-1, 3)` 把 `(H, W, 3)` 摊平成 `(H·W, 3)`，`-1` 表示"自动推算这一维"。
- 颜色是可选的：传入与点云同形状的 RGB 数组时，头部多三个 `uchar` 属性，每行多三个整数。
- `with open(...)`：退出代码块时自动关闭文件，即使中途异常也不会泄漏文件句柄。
- ⚠️ 简化：ASCII 格式人眼可读、便于调试，但体积大、写入慢（9,216 个点就有约 200 KB）。百万级点云应使用 `binary_little_endian` 格式，或直接用 Open3D 的 `write_point_cloud`。另外按行 `f.write` 的 Python 循环也比较慢。

### 3.7 `main()`：故意制造一个"尺度错误"的预测

```python
    gt_np = synthetic_depth(96)
    gt = torch.from_numpy(gt_np)
    pred = gt + 0.4 * torch.randn_like(gt)
    scaled_pred = 3.0 * pred + 0.7
```

- `pred`：真值 + 标准差 0.4 的高斯噪声，模拟"尺度正确但有噪声"的度量模型输出。
- `scaled_pred`：再乘 3 加 0.7，模拟"结构正确但尺度和偏移都不对"的相对深度模型输出。
- 随后依次打印三者的指标，然后对 `scaled_pred` 做对齐；最后用内参 `(96, 96, 48, 48)`（主点在图像中心、焦距等于图像宽度，水平视场角约 53°）把真值深度抬升为点云并写入 `tempfile.gettempdir()` 下的 `depth_demo.ply`。
- `torch.from_numpy` 与原数组**共享内存**：如果之后原地修改 `gt_np`，`gt` 也会跟着变。本代码没有原地修改，所以没问题。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用合成深度 + 人工噪声代替真实模型 | 无需下载模型，结果可控，能单独检验指标与对齐逻辑 | 不反映真实模型的误差分布（边界拖尾、玻璃区域等） |
| 指标函数都带可选 `mask` | 真实 GT（如 LiDAR）大量像素无效，必须屏蔽 | 本例未使用 mask；生产评测必须传入 |
| `clamp(min=1e-6)` 防除零 | 防止崩溃 | 不能替代 mask；无效像素仍会污染平均值 |
| `torch.linalg.lstsq` 做对齐 | 闭式解，一次搞定 | 对离群点敏感；可用中位数尺度或稳健回归 |
| 指标用 torch、反投影用 numpy | 指标常在训练循环里算（张量），点云常交给 numpy/Open3D | 两套库混用，注意 dtype 与共享内存 |
| `meshgrid(indexing="ij")` 向量化反投影 | 无循环、速度快、语义明确 | 需注意坐标系约定（OpenCV vs OpenGL） |
| ASCII PLY | 可读、零依赖 | 体积大、慢；生产用二进制 PLY 或 Open3D |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数与 `None` 哨兵 | `def abs_rel_error(pred, target, mask=None)`；`if mask is not None:` | 用 `None` 表示"没传"，判断用 `is not None` |
| 元组解包 | `H, W = depth.shape`、`fx, fy, cx, cy = intrinsics`、`a, b = sol.solution[:2, 0]` | 一次拆出多个值 |
| 布尔索引 | `pred[mask]` | 只取 mask 为 True 的元素，结果是一维 |
| 链式方法调用 | `(...).mean().item()`、`(ratio < threshold).float().mean().item()` | 逐步变换，最后转成 Python 数 |
| 逐元素比较与逻辑与 | `(np.abs(xx - size / 2) < size / 6) & (...)` | 数组的逻辑运算用 `&`，且要加括号 |
| `np.meshgrid(..., indexing="ij")` | `v, u = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")` | 生成坐标网格；`"ij"` 按矩阵下标顺序 |
| 省略号切片 | `pc[..., 0]` | `...` 代表"前面所有维度"，这里取最后一维的第 0 个分量（x） |
| `reshape(-1, 3)` | `points.reshape(-1, 3)` | `-1` 让 NumPy 自动推算该维大小 |
| 列表拼接 | `header += [...]`、`header.append("end_header")` | `+=` 追加多个，`append` 追加一个 |
| `str.join` | `"\n".join(header) + "\n"` | 用换行符把多行拼成一个字符串 |
| `with open(...) as f` | `write_ply` 中 | 上下文管理器，自动关闭文件 |
| `zip` | `for p, c in zip(points, colors)` | 点和颜色逐个配对 |
| f-string 格式符 | `f"{p[0]:.4f}"`、`f"element vertex {n}"` | `:.4f` 保留 4 位小数 |
| `os.path.join` + `tempfile.gettempdir()` | `os.path.join(tempfile.gettempdir(), "depth_demo.ply")` | 跨平台拼路径；取系统临时目录（Linux 上通常是 `/tmp`） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

> 未实际运行完整脚本（当前环境缺少 `torch`，按规范不安装依赖）。其中**只依赖 NumPy 的反投影和写 PLY 部分**，我把同样的函数单独拿出来用 NumPy 运行过，数值是确定的；指标部分依赖 torch 的随机数，下面给出的是用 NumPy 按同样分布、在 5 个随机种子上复算的近似值。

预期输出结构：

```text
[metrics]
  pred        absRel≈0.137  delta<1.25≈0.81
  scaled      absRel≈2.30   delta<1.25≈0.001
  aligned     absRel≈0.13   delta<1.25≈0.84

[depth -> point cloud]
  point cloud shape: (96, 96, 3)
  x range [-2.48, 2.43]
  y range [-0.56, 2.43]
  z range [1.00, 4.96]
  wrote /tmp/depth_demo.ply  (9216 points)
```

逐行解读：

- **`pred`**：噪声标准差 0.4、深度在 1–5 米之间，相对误差约 14%；约 81% 的像素落在 25% 以内。
- **`scaled`**：`(3·pred + 0.7 - gt) / gt ≈ 2 + 0.7/gt`，平均下来约 2.30；比值普遍在 3 左右，δ<1.25 接近 0。**这就是"相对深度不对齐直接评测"的样子**——数字荒唐，但模型的结构信息其实完全没坏。
- **`aligned`**：误差回到和 `pred` 同一量级，但**不会归零**（噪声无法被线性变换消除），甚至略好于 `pred`，原因是带噪声时最小二乘斜率被稀释（`a ≈ 0.30` 而非 1/3），预测被轻微地向均值收缩。
- **点云形状** `(96, 96, 3)`：每个像素一个 3D 点。
- **x 范围**：最左列 `u=0` 在最远的一行（z≈4.96）得到 `-48 × 4.96 / 96 ≈ -2.48`；最右列 `u=95` 得到 `47 × 4.96 / 96 ≈ 2.43`。左右不完全对称，是因为像素下标 0–95 关于 48 并不对称。
- **y 范围下界 -0.56**：不是出现在第 0 行（那里是 -0.50），而是在第 11 行附近——行号增大时 `|v - 48|` 变小，但深度在变大，乘积在那里最负。
- **z 范围** `[1.00, 4.96]`：就是真值深度的范围（`1 + 95/96 × 4 ≈ 4.96`）。
- **PLY 文件**：9,216 个点（96×96），文件 9,223 行（7 行头 + 9,216 行数据），约 200 KB。前两行数据是 `-0.5000 -0.5000 1.0000`、`-0.4896 -0.5000 1.0000`，对应左上角的前两个像素。

---

## 7. 动手改一改

1. **加 mask 评测**：在 `gt` 中随机把 10% 像素设为 0（模拟 LiDAR 空洞），对比"不传 mask"和"传 `mask = gt > 0`"时 AbsRel 的差异。
2. **稳健对齐**：实现 `align_median_scale(pred, gt)`，只拟合尺度 `s = median(gt) / median(pred)`；再给 `pred` 加 1% 的离群点（如 +100），对比它与最小二乘对齐的鲁棒性。
3. **视差空间对齐**：把 `pred` 换成 `1 / pred`（模拟输出视差的模型），写一个"先在视差空间对齐、再取倒数"的版本。
4. **由视场角构造内参**：写 `intrinsics_from_fov(W, H, fov_deg)`，返回 `(fx, fy, cx, cy)`，其中 `fx = (W/2) / tan(fov/2)`；用 60° 和 70° 分别生成点云，观察点云的"胖瘦"变化。
5. **带颜色的点云**：用深度值映射出一个灰度或伪彩色 `colors`（形状 `(96, 96, 3)`、`uint8`），调用 `write_ply(path, pc, colors)`，在 MeshLab 里查看盒子是否"凸"出来。
6. **框抬升**：实现测验 Q11 的 `box_to_3d`，把盒子所在的框抬升到 3D，验证结果为 `(≈0.010, ≈0.208, 2.0)`。

---

## 8. 常见坑

- **不 mask 无效像素**：真值为 0 的像素经过 `clamp(min=1e-6)` 后，相对误差会变成百万量级，直接毁掉平均值。clamp 只防崩溃，不防污染。
- **相对深度不对齐就评测**：会看到 AbsRel ≈ 2.3 这类荒唐数字，误以为模型很差；反过来，**度量模型不应该对齐**，否则掩盖了尺度误差。
- **深度与视差混淆**：很多相对深度模型输出的是视差（越大越近），直接当深度用会把远近完全搞反。
- **meshgrid 索引顺序**：默认 `"xy"` 和 `"ij"` 的输出形状不同；在正方形测试图上不会报错，只会悄悄转置。
- **假设的内参用于测量**：没有标定时假设 60–70° 视场角只够可视化，用来量尺寸会有系统误差。
- **坐标系约定**：OpenCV 是 y 向下、z 向前；Open3D 可视化或 OpenGL 渲染时常需翻转 y、z，否则点云"倒立"。
