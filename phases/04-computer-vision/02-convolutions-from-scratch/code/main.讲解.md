# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 02 节 从零实现卷积 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`numpy`（不需要 PyTorch）

---

## 1. 这份代码在考察什么

1. **卷积的定义**：用最直白的四重循环（输出通道 × 行 × 列 × 窗口内求和）写出卷积，作为"真值"（ground truth）。
2. **im2col 技巧**：把卷积改写成一次矩阵乘法，并与朴素版本对拍，证明两者等价。
3. **形状算术**：`output_size` 一行公式算清 padding、stride 对输出尺寸的影响。
4. **感受野**：用累积 stride 的递推公式计算任意卷积栈的感受野。
5. **手工卷积核**：用 Sobel 核在阶跃图上验证"卷积 = 模式检测器"。

> 一句话：**先写一个慢但绝对正确的版本，再写一个快的版本，用前者校验后者**——这是实现任何算子的标准工作流。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `pad2d` | 函数 | 在最后两个轴四周补零，支持任意前导维 | zero padding |
| `output_size` | 函数 | `(H + 2P − K) // S + 1` | 输出尺寸公式 |
| `conv2d_naive` | 函数 | 循环版多通道卷积（含 bias、stride、padding） | 卷积定义（互相关） |
| `im2col` | 函数 | 把所有窗口展平成矩阵的列 | im2col |
| `conv2d_im2col` | 函数 | `W_flat @ cols` 实现卷积 | GEMM 卷积 |
| `receptive_field` | 函数 | 逐层累加感受野 | 感受野 |
| `KERNELS` | 字典常量 | identity / blur / sharpen / sobel_x / sobel_y | 手工设计的核 |
| `apply_kernel` | 函数 | 把 2D 灰度图和 2D 核包装成卷积所需的形状 | 单通道卷积 |
| `synthetic_step_image` | 函数 | 左 0 右 1 的阶跃图 | 测试输入 |
| `test_against_naive` | 函数 | 随机输入下对拍两种实现 | 正确性验证 |
| `main` | 函数 | 依次打印对拍结果、Sobel 输出、尺寸表、感受野 | — |

调用关系：`conv2d_naive` 和 `im2col` 都依赖 `pad2d` 与 `output_size`；`conv2d_im2col` 依赖 `im2col`；`apply_kernel` 调用 `conv2d_im2col`。

---

## 3. 逐段精讲

### 3.1 `pad2d`：只填充最后两个轴

```python
def pad2d(x, p):
    if p == 0:
        return x
    h, w = x.shape[-2:]
    out = np.zeros(x.shape[:-2] + (h + 2 * p, w + 2 * p), dtype=x.dtype)
    out[..., p:p + h, p:p + w] = x
    return out
```

- `x.shape[:-2] + (新 H, 新 W)` 是**元组拼接**：保留所有前导维（C 或 N、C），只放大最后两维。所以同一个函数对 `(H,W)`、`(C,H,W)`、`(N,C,H,W)` 都适用——讲义称之为 "trailing-axes trick"。
- 先建一个全零的大数组，再把原图写进中间区域（`...` 表示所有前导维全选），就完成了零填充。
- `p == 0` 时直接返回原数组（不复制）。后续代码只读不写，所以没问题；⚠️ 但如果调用方修改返回值，会改到原数组——这是"返回视图/原对象"时需要注意的别名问题。
- ⚠️ 只实现了 `zero` 模式。讲义提到的 `reflect`、`replicate`、`circular` 可以用 `np.pad(x, ..., mode="reflect" / "edge" / "wrap")` 实现。

### 3.2 `output_size`：一行公式

```python
def output_size(h_in, k, p, s):
    return (h_in + 2 * p - k) // s + 1
```

- `//` 是**整除（向下取整）**，正好对应公式里的 `floor`。窗口放不下的"零头"会被丢弃，例如 64、K=5、P=2、S=2：`63 // 2 + 1 = 32`。
- `main` 中打印的尺寸速查表（H=32）就是讲义里的那张表：valid 卷积 30、same 卷积 32、stride 2 下采样 16、2×2 池化 16、7×7 s2 也是 16。

### 3.3 `conv2d_naive`：卷积的"定义式"

```python
def conv2d_naive(x, w, b=None, stride=1, padding=0):
    c_in, h, w_in = x.shape
    c_out, c_in_w, kh, kw = w.shape
    assert c_in == c_in_w

    x_pad = pad2d(x, padding)
    h_out = output_size(h, kh, padding, stride)
    w_out = output_size(w_in, kw, padding, stride)

    out = np.zeros((c_out, h_out, w_out), dtype=np.float32)
    for oc in range(c_out):
        for i in range(h_out):
            for j in range(w_out):
                hs = i * stride
                ws = j * stride
                patch = x_pad[:, hs:hs + kh, ws:ws + kw]
                out[oc, i, j] = np.sum(patch * w[oc])
        if b is not None:
            out[oc] += b[oc]
    return out
```

- 输入 `x` 是 `(C_in, H, W)`（单张图，不含 batch 维），权重 `w` 是 `(C_out, C_in, kh, kw)`——与 PyTorch `nn.Conv2d.weight` 的形状一致。
- 变量名 `w_in` 表示输入宽度，是为了避免和权重 `w` 重名。
- `assert c_in == c_in_w`：输入通道数必须和权重的第 2 维一致，否则直接报错。这和 PyTorch 在通道数不匹配时抛 RuntimeError 是同一个道理。
- 窗口左上角在 padded 图上的位置是 `(i*stride, j*stride)`；`patch` 形状 `(C_in, kh, kw)`，与 `w[oc]` 形状相同，逐元素相乘后 `np.sum` **同时在通道和空间上求和**——这就是"一个 3×3 卷积在 RGB 输入上实际是 3×3×3 的体"。
- 没有翻转核：数学上是**互相关**。对可学习的权重没有影响，对手工核（如 Sobel）决定了输出的正负号。
- bias 在每个输出通道的所有位置上加同一个数：`out[oc] += b[oc]`。
- ⚠️ 输出强制为 `float32`；没有 batch 维、没有 `groups`、没有 dilation——这些都是刻意的简化，讲义练习 2 要求你加上 `groups`。
- 复杂度：`O(C_out · H_out · W_out · C_in · K²)`，Python 循环在 `C_out·H_out·W_out` 层，非常慢，只用来做对拍。

### 3.4 `im2col` + `conv2d_im2col`：卷积 = 矩阵乘

```python
    cols = np.zeros((c_in * kh * kw, h_out * w_out), dtype=x.dtype)
    col = 0
    for i in range(h_out):
        for j in range(w_out):
            hs = i * stride
            ws = j * stride
            patch = x_pad[:, hs:hs + kh, ws:ws + kw]
            cols[:, col] = patch.reshape(-1)
            col += 1
    return cols, h_out, w_out
```

```python
def conv2d_im2col(x, w, b=None, stride=1, padding=0):
    c_out, c_in, kh, kw = w.shape
    cols, h_out, w_out = im2col(x, kh, kw, stride, padding)
    w_flat = w.reshape(c_out, -1)
    out = w_flat @ cols
    if b is not None:
        out += b[:, None]
    return out.reshape(c_out, h_out, w_out)
```

形状推演（以 `test_against_naive` 为例：C_in=3、16×16、K=3、P=1、C_out=8）：

| 张量 | 形状 | 说明 |
|------|------|------|
| `cols` | `(27, 256)` | 每列是一个 3×3×3 窗口展平，共 16×16 个窗口 |
| `w_flat` | `(8, 27)` | 每行是一个输出通道的核展平 |
| `w_flat @ cols` | `(8, 256)` | 每个元素 = 一个核 · 一个窗口 |
| 最终输出 | `(8, 16, 16)` | reshape 回空间布局 |

- **为什么两边能对上**：`patch.reshape(-1)` 和 `w.reshape(c_out, -1)` 都按 C 连续（行优先）顺序展平 `(C_in, kh, kw)`，所以第 k 行的 `cols` 元素与第 k 列的 `w_flat` 元素对应同一个 (通道, 行, 列) 位置。只要两边的展平顺序一致，点积就等于朴素版本中的 `np.sum(patch * w[oc])`。
- 列的顺序是"先 i 后 j"（行优先），所以最后 `reshape(c_out, h_out, w_out)` 能恢复正确的空间位置。
- `b[:, None]` 把 `(8,)` 变成 `(8, 1)`，广播到 `(8, 256)` 的每一列。
- 这里 `im2col` 本身仍有 Python 循环，但循环里只做拷贝，重活（乘加）全部交给一次高度优化的矩阵乘。测验 Q10 给出了用 `sliding_window_view` 去掉循环的版本。
- ⚠️ 代价：同一个输入像素被复制进最多 K² 列，`cols` 的内存约为输入的 K² 倍。

### 3.5 `receptive_field`：累积 stride

```python
def receptive_field(layers):
    rf = 1
    stride_prod = 1
    for k, s in layers:
        rf = rf + (k - 1) * stride_prod
        stride_prod *= s
    return rf
```

- 递推关系：第 l 层在上一层特征图上看 K 个相邻点，这些点在原图上的间距等于**之前所有层** stride 的乘积 `stride_prod`，所以感受野增加 `(K−1) × stride_prod`。
- **两行顺序不能交换**：本层的 stride 只影响后面的层。先乘再加会高估感受野（`main` 中第 4 组会从 13 变成 19，见测验 Q9）。
- stride 全为 1 时退化为讲义公式 `1 + L(K−1)`：1 层 3、2 层 5、3 层 7。

### 3.6 手工核与阶跃图

```python
KERNELS = {
    "identity": np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32),
    "blur_3x3": np.ones((3, 3), dtype=np.float32) / 9.0,
    "sharpen": np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32),
    "sobel_x": np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32),
    "sobel_y": np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32),
}


def apply_kernel(img2d, kernel):
    x = img2d[None].astype(np.float32)
    w = kernel[None, None]
    return conv2d_im2col(x, w, padding=1)[0]
```

| 核 | 权重和 | 作用 |
|----|--------|------|
| identity | 1 | 原样输出（检验实现的基准） |
| blur_3x3 | 1 | 3×3 均值，平滑噪声 |
| sharpen | 1 | 中心 5、四邻 −1 = 原图 + 拉普拉斯高频，增强边缘 |
| sobel_x | 0 | 水平方向的梯度（右减左）→ 检测**竖直**边缘 |
| sobel_y | 0 | 竖直方向的梯度（下减上）→ 检测**水平**边缘 |

- 权重和为 1 的核保持平均亮度；权重和为 0 的核在平坦区域输出 0，只对变化有响应——这就是"边缘检测器"。
- `img2d[None]`：`(H, W)` → `(1, H, W)`，补上通道维；`kernel[None, None]`：`(3, 3)` → `(1, 1, 3, 3)`，补上 `C_out` 和 `C_in`。最后 `[0]` 再取出唯一的输出通道。
- `padding=1` 让 3×3 卷积保持尺寸不变（same 卷积）。

### 3.7 `test_against_naive` 与 `main`

- 用固定种子生成随机 `x`、`w`、`b`，同时跑两种实现，返回输出形状和最大绝对误差。误差来源只是**浮点累加顺序不同**（矩阵乘的内部求和顺序与 `np.sum` 不同），不是 bug。
- `main` 依次打印：对拍结果 → Sobel 在阶跃图上的前 5 行 → 尺寸速查表 → 4 组卷积栈的感受野。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 先写四重循环的朴素版本 | 与公式一一对应，作为对拍基准 | 极慢；生产中永远不用 |
| im2col + 一次矩阵乘 | 把计算交给 BLAS，讲清 GPU 卷积的核心思路 | 内存放大约 K² 倍；cuDNN 会分块并在 im2col / Winograd / FFT 等算法间自动选择 |
| 单张图输入 `(C, H, W)`，不含 batch | 少一个维度，代码更短 | 实际框架都处理 NCHW 批量 |
| 只支持零填充 | 最常用、最简单 | 边界会出现伪边缘（见第 6 节最后一列的 −4）；可换 reflect/replicate |
| 不翻转核（互相关） | 与所有深度学习框架一致 | 与信号处理教科书的定义相差一个翻转 |
| 用 `assert` 检查通道数 | 简单直接 | `python -O` 会关闭 assert；生产代码应 `raise ValueError` |
| 手工核放在模块级字典 | 一目了然，便于按名字取用 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数与 `None` 哨兵 | `def conv2d_naive(x, w, b=None, stride=1, padding=0)`；`if b is not None:` | bias 可选；用 `is not None` 判断是否传入 |
| 元组解包 | `c_out, c_in_w, kh, kw = w.shape`；`for k, s in layers:` | 把形状元组拆成多个变量 |
| 元组拼接 | `x.shape[:-2] + (h + 2 * p, w + 2 * p)` | 元组可以用 `+` 拼接成新元组 |
| 负数下标与切片 | `x.shape[-2:]`、`x.shape[:-2]` | 取最后两个 / 除最后两个外的所有元素 |
| `assert` | `assert c_in == c_in_w` | 条件为假时抛 `AssertionError`，常用于检查内部假设 |
| 整除 `//` | `(h_in + 2 * p - k) // s + 1` | 向下取整的除法 |
| 增强赋值 | `col += 1`、`stride_prod *= s`、`out[oc] += b[oc]` | 原地更新 |
| `...` 与切片赋值 | `out[..., p:p + h, p:p + w] = x` | 把 `x` 写进大数组的中间区域 |
| `None` 增加新轴 | `img2d[None]`、`kernel[None, None]`、`b[:, None]` | 给数组补长度为 1 的维度，便于广播 |
| `reshape(-1)` | `patch.reshape(-1)`、`w.reshape(c_out, -1)` | `-1` 表示"这一维自动推算" |
| `@` 矩阵乘 | `w_flat @ cols` | 二维数组的矩阵乘法 |
| 多返回值 | `return cols, h_out, w_out`；`cols, h_out, w_out = im2col(...)` | 实际返回一个元组，调用时解包 |
| 字典常量 | `KERNELS = {"identity": ..., ...}`；`KERNELS["sobel_x"]` | 按名字查找核 |
| 嵌套列表 | `stacks = [[(3, 1)], [(3, 1), (3, 1)], ...]` | 列表里放列表，元素是 `(K, S)` 元组 |
| f-string 格式符 | `f"max|diff|={diff:.2e}"` | `.2e` 科学计数法保留 2 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.3 秒）：

```text
conv equivalence: naive vs im2col     shape=(8, 16, 16)   max|diff|=2.86e-06

sobel_x on a left/right step image (first five rows):
[[ 0.  0.  0.  0.  0.  0.  0.  3.  3.  0.  0.  0.  0.  0.  0. -3.]
 [ 0.  0.  0.  0.  0.  0.  0.  4.  4.  0.  0.  0.  0.  0.  0. -4.]
 [ 0.  0.  0.  0.  0.  0.  0.  4.  4.  0.  0.  0.  0.  0.  0. -4.]
 [ 0.  0.  0.  0.  0.  0.  0.  4.  4.  0.  0.  0.  0.  0.  0. -4.]
 [ 0.  0.  0.  0.  0.  0.  0.  4.  4.  0.  0.  0.  0.  0.  0. -4.]]

output size cheatsheet  (H=32):
  K=3 P=0 S=1  ->  H_out=30
  K=3 P=1 S=1  ->  H_out=32
  K=3 P=1 S=2  ->  H_out=16
  K=2 P=0 S=2  ->  H_out=16
  K=7 P=3 S=2  ->  H_out=16

receptive field grows with depth:
  layers=[(3, 1)]  ->  RF=3
  layers=[(3, 1), (3, 1)]  ->  RF=5
  layers=[(3, 1), (3, 1), (3, 1)]  ->  RF=7
  layers=[(3, 1), (3, 2), (3, 1), (3, 2)]  ->  RF=13
```

- **对拍**：形状 `(8,16,16)`（same 卷积保持 16×16），最大误差 `2.86e-06`，处在 float32 累加误差的正常量级（讲义说"约 1e-5"）。
- **Sobel 输出**：
  - 第 7、8 两列都是 4：Sobel-x 的中心列权重为 0，第 7 列看到"左 0 右 1"，第 8 列看到"左 0（第 7 列）右 1（第 9 列）"，所以边缘两侧各亮一列。讲义"只有第 7 列亮、其余全为 0"的描述不够准确。
  - 最后一列是 −4：右侧是零填充（0），左侧是 1，被当成了"由亮到暗"的边缘——**零填充造成的伪边缘**。
  - 第 0 行（以及完整输出的最后一行）是 3：上方（下方）是零填充，只有两行真实数据参与（权重 2+1）。
- **尺寸表**：与讲义表格逐行一致。注意 K=2、S=2 的池化和 K=3、P=1、S=2 的卷积都把 32 减半为 16。
- **感受野**：stride 为 1 时每层 +2；第 4 组含两个 stride 2 层，后面的层增量翻倍，得到 13。

---

## 7. 动手改一改

1. （易）给 `pad2d` 增加 `mode` 参数，用 `np.pad(x, [(0,0)]*(x.ndim-2) + [(p,p),(p,p)], mode="edge")` 实现 replicate 填充，重新跑 Sobel，看最后一列的 −4 是否消失。
2. （易）对阶跃图分别应用 `blur_3x3`、`sharpen`、`sobel_y`，预测并验证输出（`sobel_y` 在这张图上应几乎全为 0，边界行除外——为什么？）。
3. （中）给 `conv2d_naive` 和 `conv2d_im2col` 加上 `groups` 参数，验证 `groups = C_in = C_out` 时就是 depthwise 卷积，参数量为 `C·K·K`（讲义练习 2）。
4. （中）给两个函数加上 batch 维，输入 `(N, C, H, W)`；思考 im2col 时把 N 并到列维度（`H_out·W_out·N`）的做法。
5. （中）用 `time.perf_counter()` 比较 `conv2d_naive` 和 `conv2d_im2col` 在 `(16, 64, 64)` 输入、32 个输出通道下的耗时。
6. （难）实现 `conv2d_im2col` 的反向传播：`dW = dY @ colsᵀ`、`dcols = W_flatᵀ @ dY`，再写 `col2im` 把 `dcols` **累加**回输入位置；用数值梯度（有限差分）检查（讲义练习 3）。

---

## 8. 常见坑

- **忘记 floor 或 +1**：输出尺寸公式里的整除和 +1 缺一不可，用 `//` 天然实现 floor。
- **展平顺序不一致**：im2col 的列和 `w_flat` 的行必须按同一顺序展平 `(C, kh, kw)`，否则结果悄悄出错（形状完全正确）。
- **零填充的伪边缘**：图像边缘值不为 0 时，零填充会在边界产生假的强响应；对生成模型等场景考虑 reflect 填充。
- **感受野递推的顺序**：先用旧的 `stride_prod` 累加，再乘上本层 stride。
- **把互相关当卷积**：手工核拿到 SciPy 的 `convolve2d`（会翻转核）里用，正负号或方向会反过来。
- **`assert` 不是参数校验**：用 `python -O` 运行时会被跳过。
