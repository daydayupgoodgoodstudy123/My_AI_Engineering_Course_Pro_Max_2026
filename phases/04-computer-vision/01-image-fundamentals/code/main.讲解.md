# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 01 节 图像基础知识——像素、通道、色彩空间 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy`（不需要 PIL/OpenCV/PyTorch，也不需要读取任何图片文件，完全离线）

---

## 1. 这份代码在考察什么

这份代码用一张**确定性合成的 RGB 图**，把"图像 = 张量"这件事从头到尾走一遍，目的是让你：

1. **看清一张图在内存里到底是什么**：`uint8`、形状 `(H, W, 3)`、值域 [0, 255]，以及如何用一行 `inspect` 把这些信息打印出来。
2. **熟练切换布局**：HWC ↔ CHW 只是轴的重排（`transpose`），不是 `reshape`。
3. **亲手实现色彩空间转换**：BT.601 加权灰度、分段公式的 RGB→HSV，以及其中的除零保护。
4. **复现 ImageNet 预处理/反处理**：`/255 → 减 mean 除 std → CHW`，再原路返回，并理解为什么往返误差是 1 而不是 0。
5. **从零写三种 resize**：nearest、bilinear、bicubic（Catmull-Rom），并用一个"粗糙度"指标量化它们的差异。

> 一句话：**把"读图之后、进模型之前"的每一步都拆开写一遍**，以后遇到"模型不报错但精度很差"的问题，你就知道该去哪一步找原因。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `IMAGENET_MEAN` / `IMAGENET_STD` | 模块常量 | ImageNet 在 [0,1] 空间的逐通道均值、标准差 | 标准化（standardize） |
| `synthetic_image` | 函数 | 生成 128×192 的渐变 + 噪声 RGB 图 | 像素 = 采样，`uint8` HWC |
| `inspect` | 函数 | 打印 dtype、shape、min/max、逐通道均值 | 张量检查 |
| `hwc_to_chw` / `chw_to_hwc` | 函数 | 布局互转 | HWC vs CHW |
| `rgb_to_grayscale` | 函数 | BT.601 加权灰度 | 亮度感知 |
| `rgb_to_hsv` | 函数 | 向量化 RGB→HSV | 色彩空间 |
| `preprocess_imagenet` / `deprocess_imagenet` | 函数 | 模型输入的正向/反向变换 | normalize + standardize + 布局 |
| `resize_coordinates` | 函数 | 计算输出网格对应的源坐标（端点对齐） | 重采样网格 |
| `nearest_resize` / `bilinear_resize` / `bicubic_resize` | 函数 | 三种插值 | 插值方法 |
| `cubic_weight` | 函数 | Keys 三次卷积核（`tension=-0.5` 即 Catmull-Rom） | 三次插值核 |
| `resize_compare` / `local_roughness` | 函数 | 3 倍放大并计算相邻像素差的平均值 | 平滑度 vs 锐度 |
| `main` | 函数 | 依次演示以上所有步骤 | — |

数据流：`synthetic_image()` 产出 `arr` → 分别送入 布局转换 / 色彩空间转换 / ImageNet 往返 / 三种 resize，彼此独立，互不修改 `arr`。

---

## 3. 逐段精讲

### 3.1 合成一张"可复现"的图

```python
def synthetic_image(height=128, width=192, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.linspace(0, 1, height), np.linspace(0, 1, width), indexing="ij")
    r = (np.sin(xx * 6) * 0.5 + 0.5) * 255
    g = (yy * 255)
    b = ((1 - yy) * xx * 255)
    noise = rng.normal(0, 6, (height, width, 3))
    rgb = np.stack([r, g, b], axis=-1) + noise
    return np.clip(rgb, 0, 255).astype(np.uint8)
```

- `np.meshgrid(..., indexing="ij")` 生成两个形状都是 `(height, width)` 的坐标网格：`yy[i, j]` 是第 i 行的纵坐标，`xx[i, j]` 是第 j 列的横坐标，都归一化到 [0,1]。`indexing="ij"` 保证第一维是行（矩阵索引习惯）；默认的 `"xy"` 会得到 `(width, height)` 形状，是常见坑。
- 三个通道分别是：R 沿水平方向做正弦波、G 从上到下变亮、B 在右上角最亮——每个通道有不同的空间结构，方便后面观察统计量。
- `np.stack([...], axis=-1)` 把三张 `(H, W)` 平面沿**最后一轴**堆起来，得到 `(H, W, 3)`——这就是 HWC。
- `np.clip(..., 0, 255).astype(np.uint8)`：先夹紧再转型。顺序很重要：如果先转 `uint8`，-3 会变成 253、258 会变成 2（整数回绕），图像上会出现"椒盐"噪点。
- `default_rng(seed)` 固定随机种子，保证每次运行输出完全一致。讲义强调这一步让实验"离线可跑"：解码图片是另一个边界，一旦拿到 RGB 字节，后面的张量操作完全一样。

### 3.2 `inspect`：一行看清张量的"身份证"

```python
def inspect(arr, label="image"):
    if arr.ndim == 2:
        print(...)
        return
    print(
        f"[{label}] dtype={arr.dtype} shape={arr.shape} "
        f"min={arr.min()} max={arr.max()} "
        f"per-channel mean="
        f"{arr.reshape(-1, arr.shape[-1]).mean(axis=0).round(2).tolist()}"
    )
```

- 灰度图（2 维）只打印整体均值；彩色图把 `(H, W, C)` `reshape` 成 `(H·W, C)`，再沿 axis=0 求均值，得到逐通道均值。
- 这里用 `reshape` 是**安全的**：它只是把前两轴"压平"，通道轴仍在最后不动。与"用 reshape 代替 transpose"那种 bug 完全不同。
- ⚠️ 假设通道在最后一轴（HWC）。如果传入 CHW 张量，`arr.shape[-1]` 是 W，打印出来的"逐通道均值"就是逐列均值。本节 outputs 里的 `skill-image-tensor-inspector` 会进一步去**猜测**布局和数值约定。
- 这几项（dtype、shape、min/max、均值）正是判断 raw / normalized / standardized 的依据：`uint8`+[0,255] 是 raw；`float32`+[0,1] 是 normalized；有负数、均值在 0 附近的是 standardized。

### 3.3 HWC ↔ CHW

```python
def hwc_to_chw(arr):
    return arr.transpose(2, 0, 1)


def chw_to_hwc(arr):
    return arr.transpose(1, 2, 0)
```

- `transpose(2, 0, 1)` 的读法：新轴 0 ← 旧轴 2（C），新轴 1 ← 旧轴 0（H），新轴 2 ← 旧轴 1（W）。逆变换 `(1, 2, 0)` 同理。
- NumPy 的 `transpose` 返回**视图**：只修改 strides，不复制数据，所以几乎零成本；代价是结果不再是 C 连续的内存。
- 为什么框架偏好 CHW：卷积核在 H、W 上滑动，每个通道是一整块连续的二维平面，便于向量化；磁盘格式保持 HWC 是因为扫描线按像素交错输出。

### 3.4 灰度：加权和，而不是平均

```python
def rgb_to_grayscale(rgb):
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return (rgb.astype(np.float32) @ weights).astype(np.uint8)
```

- `(H, W, 3) @ (3,)` → `(H, W)`：`@` 在最后一轴上做点积，等价于 `0.299·R + 0.587·G + 0.114·B`。一行完成，无需循环。
- 系数来自 ITU-R BT.601，反映人眼对绿最敏感、对蓝最不敏感。三个系数之和为 1，所以纯白 (255,255,255) 仍映射为 255，不会溢出。
- 先 `astype(np.float32)` 是必须的：`uint8` 直接参与运算容易溢出或被截断。
- ⚠️ 最后的 `.astype(np.uint8)` 是**截断**而不是四舍五入：`(210,140,30)` 的加权和是 148.39 → 148，148.9 也会变成 148。对显示无所谓，对精确比较（例如和 OpenCV 的结果逐像素对比）会差 1。
- 这个操作在神经网络里就是一个权重固定的 **1×1 卷积**（3 通道 → 1 通道），这正是讲义困难练习的内容。

### 3.5 RGB → HSV：向量化的分段函数

```python
def rgb_to_hsv(rgb):
    rgb_f = rgb.astype(np.float32) / 255.0
    r, g, b = rgb_f[..., 0], rgb_f[..., 1], rgb_f[..., 2]
    cmax = np.max(rgb_f, axis=-1)
    cmin = np.min(rgb_f, axis=-1)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    mask = delta > 0
    argmax = np.argmax(rgb_f, axis=-1)
    rmax = mask & (argmax == 0)
    gmax = mask & (argmax == 1)
    bmax = mask & (argmax == 2)
    h[rmax] = ((g[rmax] - b[rmax]) / delta[rmax]) % 6
    h[gmax] = ((b[gmax] - r[gmax]) / delta[gmax]) + 2
    h[bmax] = ((r[bmax] - g[bmax]) / delta[bmax]) + 4
    h = h * 60.0

    s = np.divide(delta, cmax, out=np.zeros_like(delta), where=cmax > 0)
    v = cmax
    return np.stack([h, s, v], axis=-1)
```

这是教科书 HSV 公式的**无循环**实现：

| 量 | 公式 | 含义 |
|----|------|------|
| V | `cmax` | 最亮的通道值，[0,1] |
| S | `delta / cmax`（cmax=0 时为 0） | 颜色有多"纯"，[0,1] |
| H | 依最大通道分三段，再 ×60 | 色环上的角度，[0,360) |

- `rgb_f[..., 0]` 中的 `...`（Ellipsis）表示"前面所有轴都取全部"，所以这个函数对 `(H,W,3)`、`(N,H,W,3)` 甚至单个像素 `(3,)` 都适用。
- **布尔掩码分派**：`rmax`、`gmax`、`bmax` 三个互斥的掩码把像素分成"红最大 / 绿最大 / 蓝最大"三组，每组用自己的公式；`h[rmax] = ...` 只写入掩码为 True 的位置。这是 NumPy 中替代 `if/elif` 的标准写法。
- `% 6` 只用在红色分支：当 g < b 时 `(g-b)/delta` 为负，取模把它折回 [0,6)，例如洋红色得到 300° 而不是 -60°。
- **两处除零保护**：①`mask = delta > 0` 让灰色像素（R=G=B）不参与色相计算，色相保持 0（灰色本来就没有色相）；②`np.divide(..., where=cmax > 0)` 让纯黑像素的饱和度为 0，而不是 0/0 = NaN。
- `np.argmax` 遇到并列最大值时返回**第一个**下标。所以纯黄 (255,255,0) 走红色分支：`(1-0)/1 % 6 = 1` → 60°，结果正确。
- ⚠️ 讲义说这个输出"与 OpenCV 的 `hsv_full` 约定一致"。更准确的说法是：H 用度 [0,360)、S/V 用 [0,1]，与 OpenCV 对 **float32** 输入调用 `COLOR_RGB2HSV` 的结果约定一致；OpenCV 的 `_FULL` 后缀只影响 `uint8` 输入（H 映射到 0–255，而非默认的 0–180）。

### 3.6 ImageNet 预处理与反处理

```python
def preprocess_imagenet(rgb_uint8):
    x = rgb_uint8.astype(np.float32) / 255.0
    x = (x - IMAGENET_MEAN) / IMAGENET_STD
    x = x.transpose(2, 0, 1)
    return x


def deprocess_imagenet(chw_float32):
    x = chw_float32.transpose(1, 2, 0)
    x = x * IMAGENET_STD + IMAGENET_MEAN
    x = np.clip(x * 255.0, 0, 255).astype(np.uint8)
    return x
```

- 三步依次对应讲义里的三个约定：raw → normalized（/255）→ standardized（减 mean 除 std）→ CHW。
- **顺序是刻意的**：在 HWC 上标准化时，`(H,W,3) - (3,)` 的广播天然对齐到通道轴；如果先转 CHW，`(3,H,W) - (3,)` 会对齐到 W 轴——宽度不是 3 时报错，宽度恰好是 3 时悄悄算错。
- `IMAGENET_MEAN` 声明为 `float32`，保证运算结果仍是 `float32`（与 `float64` 常量混算会被提升为 `float64`，模型输入 dtype 就不对了）。
- 反处理严格倒序：CHW→HWC、乘 std 加 mean、×255、夹紧、转 `uint8`。这和 torchvision 的 `transforms.Normalize` 及其逆变换做的事一模一样。
- ⚠️ `astype(np.uint8)` 截断导致往返误差为 1：float32 运算后理论值 120 可能算成 119.99999，截断成 119。实测有约 26% 的值差 1。改成 `np.clip(np.rint(x * 255.0), 0, 255)` 即可变为 0（见测验 Q9）。

### 3.7 `resize_coordinates`：先决定"在哪里采样"

```python
def resize_coordinates(source_length, target_length):
    if target_length < 1:
        raise ValueError("target length must be positive")
    if source_length < 1:
        raise ValueError("source length must be positive")
    if target_length == 1:
        return np.zeros(1, dtype=np.float32)
    return np.linspace(0, source_length - 1, target_length, dtype=np.float32)
```

- 所有 resize 的第一步都是：对输出的每个下标，求它对应源图中的**连续坐标**。这里用 `linspace(0, src-1, dst)`，即**端点对齐**——输出的第一个/最后一个像素正好落在源图的第一个/最后一个像素上（相当于 PyTorch 的 `align_corners=True`）。
- 例：源长 3、目标长 5 → `[0, 0.5, 1, 1.5, 2]`。
- `target_length == 1` 时单独处理，避免 `linspace` 只取起点的歧义，统一返回坐标 0。
- ⚠️ 刻意简化：讲义 Use It 部分的 PyTorch 代码用的是 `align_corners=False`（像素中心对齐），两种约定的采样位置不同，结果会有细微差别。工程中训练和推理必须使用同一种约定。

### 3.8 nearest：花式索引一步到位

```python
def nearest_resize(arr, target_height, target_width):
    y = np.rint(resize_coordinates(arr.shape[0], target_height)).astype(int)
    x = np.rint(resize_coordinates(arr.shape[1], target_width)).astype(int)
    return arr[y[:, None], x[None, :]]
```

- 先把连续坐标取整得到源像素下标，再用 `arr[y[:, None], x[None, :]]` 取值：`y[:, None]` 形状 `(th, 1)`、`x[None, :]` 形状 `(1, tw)`，两者广播成 `(th, tw)` 的下标网格，一次取出所有像素，结果形状 `(th, tw, 3)`。这就是 NumPy 的**花式索引 + 广播**，没有任何 Python 循环。
- 输出的值全部来自原图——这是 mask/标签图只能用 nearest 的原因。
- ⚠️ `np.rint` 是**银行家舍入**（0.5 → 0，1.5 → 2，2.5 → 2），所以 3→5 放大时下标是 `[0,0,1,2,2]`，左右并不对称（测验 Q8）。

### 3.9 bilinear：四个邻居、两次线性插值

```python
    y0 = np.floor(y).astype(int)
    x0 = np.floor(x).astype(int)
    y1 = np.minimum(y0 + 1, arr.shape[0] - 1)
    x1 = np.minimum(x0 + 1, arr.shape[1] - 1)
    wy = (y - y0)[:, None, None]
    wx = (x - x0)[None, :, None]

    source = arr.astype(np.float32)
    top = source[y0[:, None], x0[None, :]] * (1 - wx)
    top += source[y0[:, None], x1[None, :]] * wx
    bottom = source[y1[:, None], x0[None, :]] * (1 - wx)
    bottom += source[y1[:, None], x1[None, :]] * wx
    result = top * (1 - wy) + bottom * wy
    return np.clip(np.rint(result), 0, 255).astype(arr.dtype)
```

- `(y0, x0)` 是左上邻居，`(y1, x1)` 是右下邻居；`np.minimum(..., shape-1)` 防止最后一行/列越界。
- `wy`、`wx` 是小数部分，即"离左上邻居有多远"。它们被 reshape 成 `(th,1,1)` 和 `(1,tw,1)`，以便与 `(th,tw,3)` 的像素块广播——第三个维度的 1 让同一权重作用于 R、G、B 三个通道。
- 先在水平方向插值得到 `top`、`bottom`，再在竖直方向混合：这就是"双线性 = 两次一维线性插值"。
- 最后 `np.rint` 四舍五入、`clip`、转回原 dtype（`arr.dtype`，保持输入类型）。注意这里用了 `rint`，所以没有 3.6 中的截断问题。

### 3.10 bicubic：Catmull-Rom 核 + 可分离两遍

```python
def cubic_weight(distance, tension=-0.5):
    x = np.abs(distance)
    inner = (tension + 2) * x**3 - (tension + 3) * x**2 + 1
    outer = tension * x**3 - 5 * tension * x**2 + 8 * tension * x - 4 * tension
    return np.where(x <= 1, inner, np.where(x < 2, outer, 0.0))
```

- 这是 Keys 三次卷积核：距离 ≤1 用 `inner`，1~2 用 `outer`，≥2 为 0。`tension=-0.5` 时就是 Catmull-Rom 样条。
- 核值：距离 0 → 1，0.5 → 0.5625，1 → 0，1.5 → -0.0625。**负瓣**是 bicubic 比 bilinear 更"锐"的原因，也是它可能轻微过冲（overshoot）的原因。
- 嵌套 `np.where` 是向量化的分段函数：两个分支都会被计算，再按条件挑选。

```python
    offsets = np.arange(-1, 3)
    x_base = np.floor(x).astype(int)
    x_neighbors = x_base[:, None] + offsets[None, :]
    x_weights = cubic_weight(x[:, None] - x_neighbors)
    x_weights /= x_weights.sum(axis=1, keepdims=True)
    x_indices = np.clip(x_neighbors, 0, arr.shape[1] - 1)

    source = arr.astype(np.float32)
    horizontal = np.zeros((arr.shape[0], target_width, arr.shape[2]), dtype=np.float32)
    for tap in range(4):
        horizontal += source[:, x_indices[:, tap], :] * x_weights[None, :, tap, None]
    # ... 竖直方向同理，作用在 horizontal 上
```

- 每个输出坐标取 4 个邻居（偏移 -1, 0, 1, 2），得到 `(tw, 4)` 的邻居下标和权重。
- `x_weights /= sum`：归一化，保证权重和为 1（常数图像经过插值后仍是常数）。
- `np.clip(x_neighbors, ...)`：越界下标夹到边缘，相当于**边缘复制（replicate padding）**。⚠️ 这会让靠近边界的像素结果偏离"理想插值"，例如 `[0,100,200]` 放大到 5 时第二个值是 44 而不是 50（测验 Q8）。
- **可分离（separable）**：二维三次插值 = 先水平 4 抽头、再竖直 4 抽头。总计算量从每个像素 16 次乘加降为 8 次，并且每一遍都是向量化的；`for tap in range(4)` 只循环 4 次，开销可忽略。
- 和 bilinear 一样，最后 `rint + clip + astype`——三次核会产生 <0 或 >255 的过冲值，`clip` 不能省。

### 3.11 比较与 `main`

```python
def local_roughness(x):
    gy = np.diff(x.astype(np.float32), axis=0)
    gx = np.diff(x.astype(np.float32), axis=1)
    return float(np.abs(gy).mean() + np.abs(gx).mean())
```

- `np.diff` 计算相邻像素差（一阶差分，相当于最朴素的梯度）。平均绝对差越大，说明图像越"粗糙"、边缘越硬。先转 `float32` 是为了避免 `uint8` 相减时回绕（`3 - 5` 在 `uint8` 里是 254）。
- `resize_compare` 对 `scale` 做了类型与正数检查，然后把三种结果放进字典返回；`main` 用 `for name, out in ....items()` 逐一打印。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成图而非读取图片文件 | 完全离线、确定性、只依赖 NumPy | 真实场景要处理解码、EXIF 方向、RGBA、BGR 等问题，用 PIL / OpenCV / torchvision.io |
| 全部向量化（掩码、花式索引、广播） | 速度快、代码短，体现 NumPy 惯用法 | 可读性稍差；生产中直接用 `cv2.resize`、`F.interpolate` |
| 先在 HWC 上标准化，最后才转 CHW | 广播自动对齐通道轴 | 若必须在 CHW 上做，需要把 mean reshape 成 `(3,1,1)` |
| 端点对齐坐标（`linspace`） | 实现最简单，首尾像素不变 | 与 PyTorch 默认的 `align_corners=False`、OpenCV 的像素中心约定不同 |
| 边缘复制处理越界 | 实现简单、不会引入黑边 | 边界附近有偏差；也可以用镜像（reflect）填充 |
| 灰度/反处理用 `astype` 截断 | 代码简洁 | 存在 ±1 误差；需要精确时先 `np.rint` |
| 只做放大比较 | 放大不涉及 aliasing，便于比较插值核本身 | 缩小时还需要 antialias（让核随倍数变宽），讲义 PyTorch 示例用 `antialias=True` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""Runnable companion ..."""` | 描述模块用途，`help(main)` 可见 |
| 模块级常量 | `IMAGENET_MEAN = np.array(...)` | 全大写命名表示"不应被修改"的常量 |
| 默认参数 | `def synthetic_image(height=128, width=192, seed=0)` | 调用时可省略，也可按名字覆盖 |
| 元组解包 | `yy, xx = np.meshgrid(...)`；`r, g, b = rgb_f[..., 0], ...` | 一次给多个变量赋值 |
| f-string 格式符 | `f"{name:>8}"`、`f"{x:6.2f}"`、`f"{v:.1f}"` | `>8` 右对齐占 8 格；`6.2f` 总宽 6、保留 2 位小数 |
| 相邻字符串自动拼接 | `print(f"..." f"..." f"...")` | 括号内相邻的字符串字面量会被拼成一个 |
| 提前 `return` | `inspect` 里 `if arr.ndim == 2: ... return` | 处理特殊情况后直接退出，避免深层嵌套 |
| `raise ValueError` | `raise ValueError("target length must be positive")` | 参数不合法时主动报错 |
| `isinstance` | `isinstance(scale, int)` | 运行时检查类型 |
| 增强赋值 | `top += ...`、`x_weights /= ...`、`horizontal += ...` | 原地修改 NumPy 数组，省一次内存分配 |
| 幂运算 | `x**3`、`x**2` | 逐元素乘方 |
| `@` 矩阵乘 | `rgb.astype(np.float32) @ weights` | `(H,W,3) @ (3,)` 在最后一轴做点积 |
| `...`（Ellipsis） | `rgb_f[..., 0]`、`hsv[..., 1]` | 代表"前面所有轴"，让函数不依赖维数 |
| `None` 增加新轴 | `y[:, None]`、`x[None, :]`、`(y - y0)[:, None, None]` | 等同 `np.newaxis`，为广播准备形状 |
| 布尔掩码与 `&` | `rmax = mask & (argmax == 0)`；`h[rmax] = ...` | 逐元素与运算；按掩码读写数组。注意 `&` 优先级高于 `==`，必须加括号 |
| 花式索引 | `arr[y[:, None], x[None, :]]`、`source[:, x_indices[:, tap], :]` | 用整数数组做下标，一次取出多个元素 |
| `np.divide(..., out=, where=)` | `np.divide(delta, cmax, out=np.zeros_like(delta), where=cmax > 0)` | 只在条件为真处做除法，其余位置保留 `out` 的初值 |
| 嵌套 `np.where` | `np.where(x <= 1, inner, np.where(x < 2, outer, 0.0))` | 向量化的 if/elif/else |
| `keepdims=True` | `x_weights.sum(axis=1, keepdims=True)` | 求和后保留该轴（长度 1），便于广播回去 |
| 字典字面量与 `.items()` | `return {"nearest": ..., ...}`；`for name, out in ....items()` | 按名字组织多个结果并遍历键值对 |
| `float()` / `int()` / `.tolist()` | `float(arr.mean())`、`int(np.abs(...).max())`、`.round(3).tolist()` | NumPy 标量/数组转成 Python 原生类型，便于打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.2 秒）：

```text
source: deterministic synthetic RGB image (offline)
[raw] dtype=uint8 shape=(128, 192, 3) min=0 max=255 per-channel mean=[127.8, 126.99, 63.48]
HWC shape: (128, 192, 3)   CHW shape: (3, 128, 192)
grayscale shape: (128, 192)
hsv hue range:   [0.0, 359.7] deg
hsv sat range:   [0.02, 1.00]
hsv val range:   [0.33, 1.00]
preprocessed shape: (3, 128, 192)  dtype: float32
per-channel mean: [0.07100000232458115, 0.18799999356269836, -0.6980000138282776]
per-channel std:  [1.5700000524520874, 1.2999999523162842, 0.9879999756813049]
roundtrip max pixel diff: 1
 nearest  shape=(384, 576, 3)  roughness=  4.34
bilinear  shape=(384, 576, 3)  roughness=  3.23
 bicubic  shape=(384, 576, 3)  roughness=  3.98
```

逐行解读：

- **raw**：`uint8`、HWC、值域 [0,255]——标准的"解码后"表示。B 通道均值只有 63，因为 `b = (1-yy)·xx·255` 只在右上角（顶部 `yy≈0`、右侧 `xx≈1`）较亮，整体均值约 `0.5×0.5×255 ≈ 64`。
- **CHW**：`(3, 128, 192)`，只是轴重排，数据量不变。
- **HSV**：色相覆盖了几乎整个 [0,360)，饱和度、亮度在 [0,1] 内——符合预期的单位约定。
- **preprocessed 均值/标准差**：讲义说"应接近 0 和 1"，但实际是 `[0.071, 0.188, -0.698]` 和 `[1.57, 1.30, 0.988]`。原因：ImageNet 统计量只对 ImageNet 那样的分布才把它变成 0/1，这张合成图的 B 通道偏暗（均值 63/255≈0.25，低于 0.406）、R 通道正弦波的方差很大。**这正说明标准化是在"对齐训练分布"，不是"把每张图都变成 0/1"**。
- 一长串小数（`0.07100000232458115`）：`round(3)` 是在 float32 上做的，`.tolist()` 转成 Python 的 float64 时暴露了 float32 无法精确表示 0.071 的事实——不是 bug，只是显示问题。
- **roundtrip diff = 1**：截断误差，见 3.6 和测验 Q9。
- **roughness**：nearest 4.34 最大（块状硬边缘，相邻像素要么完全相等、要么突变）；bilinear 3.23 最小（线性混合最平滑）；bicubic 3.98 居中（负瓣带来锐化，比 bilinear 粗糙，但比 nearest 平滑）。注意这个指标同时包含了原图噪声被放大的部分，它衡量的是"平滑度"，不是"画质好坏"。

---

## 7. 动手改一改

1. （易）造一个 2×2 的四色 `uint8` 图，做 `hwc_to_chw` → `chw_to_hwc`，用 `np.array_equal` 证明往返无损；再试试用 `reshape(3, 2, 2)` 代替 `transpose`，打印结果看看"通道"里混进了什么。
2. （易）把 `deprocess_imagenet` 的最后一行改成先 `np.rint` 再转型，确认 `roundtrip max pixel diff` 变为 0；对 `rgb_to_grayscale` 做同样修改。
3. （中）写 `standardize(x, mean, std, channel_axis)` 和其逆函数，使其对单张 HWC（`channel_axis=-1`）和批量 NCHW（`channel_axis=1`）都适用（提示：根据 `channel_axis` 把 mean reshape 成可广播的形状）。这是讲义的中等练习。
4. （中）用 `np.einsum("hwc,c->hw", ...)` 或把 CHW 张量与权重做张量积，实现"1×1 卷积版"的灰度，并与 `rgb_to_grayscale` 比较（注意截断带来的 ±1 差异）。这是讲义困难练习的 NumPy 版本。
5. （中）把 `resize_coordinates` 改成像素中心对齐：`(np.arange(dst) + 0.5) * src / dst - 0.5`（再夹到合法范围），对比 nearest 输出与原版的差异。
6. （难）实现带 antialias 的 2 倍下采样：先对图像做 2×2 平均（或高斯模糊）再隔点采样，与"直接隔点采样"比较——用一张高频棋盘格图像来观察 aliasing。

---

## 8. 常见坑

- **先 `astype(np.uint8)` 再 `clip`**：负数和大于 255 的值会整数回绕（-3 → 253），图像出现噪点。永远是**先 clip 后转型**。
- **用 `reshape` 代替 `transpose`**：形状对、内容全错，而且不报错。
- **在 CHW 上直接减 `(3,)` 形状的 mean**：广播会对齐到 W 轴，宽度为 3 时悄悄出错。
- **`uint8` 直接做减法或求差分**：`np.diff` 或 `a - b` 在 `uint8` 上会回绕，先转 float。
- **`np.meshgrid` 默认 `indexing="xy"`**：返回 `(W, H)` 形状，与图像的 `(H, W)` 习惯相反。
- **以为 `np.rint` 是四舍五入**：它是 round half to even，0.5 → 0、2.5 → 2；Python 内置 `round` 也一样。
