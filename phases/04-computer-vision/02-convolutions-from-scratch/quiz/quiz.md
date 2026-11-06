# 测验 · 从零实现卷积（Convolutions from Scratch）

> **阶段 04 · 计算机视觉 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要卷积 | 全连接层在 224×224×3 上每个神经元要 150,528 个权重，且不知道"同一图案可以出现在任何位置"；卷积用**局部连接 + 参数共享**解决 |
| 2 | 平移等变（translation equivariance） | 输入平移 k 像素，输出也平移 k 像素；这是权重共享"免费"带来的性质 |
| 3 | 卷积的计算 | 核在输入上滑动，每个位置做逐元素相乘再求和得到一个输出像素；深度学习里的"卷积"数学上是互相关（不翻转核） |
| 4 | 输出尺寸公式 | `H_out = floor((H − K + 2P) / S) + 1`；奇数 K 时 `P = (K−1)/2` 即 same padding |
| 5 | padding 与 stride | padding 让核能以边缘像素为中心、保持尺寸；stride=2 把空间尺寸减半，现代网络常用它代替池化下采样 |
| 6 | 多通道与参数量 | 权重形状 `(C_out, C_in, K, K)`，参数量 `C_out·C_in·K·K + C_out`；每个输出通道在所有输入通道上求和 |
| 7 | im2col | 把每个感受窗口展平成一列，卷积就变成一次 `W_flat @ cols` 矩阵乘；代价是窗口重叠导致内存约放大 K² 倍 |
| 8 | 感受野 | stride 1 时 L 层 K×K 卷积的感受野为 `1 + L(K−1)`；有 stride 时每层的增量要乘以之前所有层 stride 的累积乘积 |
| 9 | 3×3 堆叠 | 两个 3×3 与一个 5×5 感受野相同，但参数 18C² < 25C²，且中间多一个非线性 |
| 10 | 手工卷积核 | identity、blur、sharpen、Sobel-x/y——训练后 CNN 第一层学到的正是类似的边缘/斑点检测器 |

### 核心技能（能动手做到）

- [ ] 只用 NumPy 写出 `pad2d`、四重循环的 `conv2d_naive`，以及 `im2col + matmul` 版本，并验证两者最大误差在 1e-5 量级
- [ ] 对任意 (H, K, P, S) 组合心算输出尺寸，能逐层推出一个网络每层的形状
- [ ] 能手算一层卷积的参数量，以及 depthwise 卷积（`groups = C`）的参数量
- [ ] 用累积 stride 的方法计算任意卷积栈的感受野，并说出 `receptive_field` 函数里两行代码的先后顺序为什么不能交换
- [ ] 手工设计 Sobel / blur / sharpen 核，并能预测它们在阶跃图像上的输出（包括零填充带来的边界效应）
- [ ] 能解释 im2col 的内存代价，并用 `sliding_window_view` 写出无 Python 循环的 im2col

---

## 二、基础自测（选择题）

**Q1.** 输入 64×64，卷积核 K=5，padding P=2，stride S=2，输出空间尺寸是：

- A. 30×30
- B. 31×31
- C. 32×32
- D. 64×64

**Q2.** 一个 `Conv2d(in_channels=64, out_channels=128, kernel_size=3)`（带 bias）的可学习参数量是：

- A. 1,152
- B. 73,728
- C. 73,856
- D. 147,584

**Q3.** 关于深度学习框架里的"卷积"，下列说法正确的是：

- A. 它严格等同于信号处理里的卷积，计算前会把核翻转 180°
- B. 它实际计算的是互相关（不翻转核）；对于可学习的核，翻不翻转没有区别，因为网络会自己学到对应的权重
- C. 它只能处理单通道输入
- D. 它在每个空间位置使用不同的权重

**Q4.** 忽略边界效应，把输入图像整体向右平移 3 个像素，一个 stride=1 的卷积层的输出会：

- A. 保持不变（平移不变）
- B. 同样向右平移 3 个像素（平移等变）
- C. 向右平移 1 个像素
- D. 变得完全不同，需要重新学习

**Q5.** 一个卷积栈依次为 `(K=3,S=1)`、`(K=3,S=2)`、`(K=3,S=1)`、`(K=3,S=2)`（即 `main.py` 中的第 4 组），最后一层一个神经元的感受野是：

- A. 9
- B. 11
- C. 13
- D. 19

**Q6.** 对 64 通道的特征图做 3×3 的 depthwise 卷积（`groups = C_in = C_out = 64`，不带 bias），参数量是普通 64→64 的 3×3 卷积（不带 bias）的多少？

- A. 1/3
- B. 1/9
- C. 1/64
- D. 相同

**Q7.** im2col 方法最主要的代价是：

- A. 结果与直接卷积不一致，只是近似
- B. 相邻窗口高度重叠，同一个输入像素会被复制到多达 K×K 列中，`cols` 矩阵的内存大约放大 K² 倍
- C. 无法支持 stride > 1
- D. 无法支持多输入通道

---

## 三、动手 / 代码题

**Q8.** `main.py` 用 `sobel_x` 核、`padding=1` 处理一张 16×16 的左黑右白阶跃图（第 8–15 列为 1，其余为 0）。讲义说"第 7 列会出现大的正值，其他地方都是 0"。请预测输出的第 0 行和第 5 行，并解释：①为什么第 7、8 两列都亮；②最右边一列为什么是负数；③为什么第 0 行的值是 3 而不是 4。

```python
"sobel_x": np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32),

def synthetic_step_image(size=16):
    img = np.zeros((1, size, size), dtype=np.float32)
    img[:, :, size // 2:] = 1.0
    return img

y = apply_kernel(x[0], KERNELS["sobel_x"])   # apply_kernel 内部 padding=1
```

**Q9.** 阅读 `receptive_field`：

```python
def receptive_field(layers):
    rf = 1
    stride_prod = 1
    for k, s in layers:
        rf = rf + (k - 1) * stride_prod
        stride_prod *= s
    return rf
```

(a) 计算一个类似 ResNet stem 的栈 `[(7, 2), (3, 2), (3, 1)]`（7×7 s2 卷积 → 3×3 s2 池化 → 3×3 卷积）的感受野。
(b) 如果有人把循环体里两行的顺序交换（先 `stride_prod *= s` 再更新 `rf`），对 Q5 的栈和 (a) 的栈分别会得到多少？为什么这是错的？

**Q10.** `im2col` 仍然有两层 Python 循环。请用 `numpy.lib.stride_tricks.sliding_window_view` 写一个**没有 Python 循环**的 `im2col_fast(x, kh, kw, stride=1, padding=0)`，要求返回值与原 `im2col` 完全相同（`np.array_equal` 为 True），包括 stride>1 的情况。

---

## 四、面试高频题

**Q11.**（基础必考）卷积层相比全连接层有哪些归纳偏置（inductive bias）？"平移等变"和"平移不变"有什么区别，CNN 的平移不变性从哪里来？

**Q12.**（原理深挖）讲讲 im2col + GEMM 实现卷积的原理。它的代价是什么？工业界还有哪些卷积实现方式，各适合什么场景？

**Q13.**（基础必考）如何计算感受野？为什么 VGG/ResNet 都偏爱堆叠 3×3 卷积，而不是直接用 5×5、7×7？

**Q14.**（原理深挖）用 im2col 的视角推导卷积层的反向传播：给定 `dL/dY`，如何求 `dL/dW` 和 `dL/dX`？col2im 为什么需要"累加"？

**Q15.**（工程实践）什么是 depthwise separable 卷积？它比普通卷积省多少计算量？代价是什么？

**Q16.**（追问型）1×1 卷积有什么用？它和全连接层是什么关系？

---

## 五、参考答案与解析

### Q1 — 答案：C

`H_out = floor((64 − 5 + 2×2) / 2) + 1 = floor(63/2) + 1 = 31 + 1 = 32`。注意公式中的 floor：63/2=31.5 向下取整为 31，忘记 floor 或忘记 +1 就会得到 A、B。D 是 stride=1 时的 same 卷积结果。

### Q2 — 答案：C

`C_out·C_in·K·K + C_out = 128 × 64 × 9 + 128 = 73,728 + 128 = 73,856`。B 漏了 bias；A 是 `128 × 9`，漏乘了输入通道数 C_in（误以为每个输出通道只有一个 3×3 核）；D 是 `128 × 128 × 9 + 128`，把 C_in 错当成了 C_out。卷积的参数量与输入的空间尺寸 H、W **无关**——这正是参数共享的威力。

### Q3 — 答案：B

`conv2d_naive` 里 `np.sum(patch * w[oc])` 直接用核与窗口逐元素相乘，没有翻转，这在数学上是**互相关（cross-correlation）**；讲义 Key Terms 也明确说"mathematically a cross-correlation, but everyone calls it convolution"。对于可学习的核，翻转与否只是参数的重新排列，网络会学到对应的权重，所以无所谓；但对**手工设计的非对称核**（如 Sobel），翻转会让输出符号相反（实测把 `sobel_x` 左右翻转后，阶跃边缘处从 +4 变成 −4）。C、D 都与卷积的定义相悖。

### Q4 — 答案：B

权重共享意味着"同一个检测器在每个位置都运行"，输入中的图案移动到哪里，它的响应就出现在哪里——这叫**等变**。A 描述的是**不变性**，单层卷积不具备，需要池化 / 全局平均池化等操作来近似获得。注意：stride>1 的卷积只对 stride 整数倍的平移严格等变，这也是"CNN 对小平移并不完全鲁棒"的原因之一。

### Q5 — 答案：C

逐层累加 `(K−1) × 之前所有层 stride 的乘积`：

| 层 | (K, S) | 增量 | 累计 RF | 之后的 stride_prod |
|----|--------|------|--------|-------------------|
| 1 | (3,1) | 2×1 = 2 | 3 | 1 |
| 2 | (3,2) | 2×1 = 2 | 5 | 2 |
| 3 | (3,1) | 2×2 = 4 | 9 | 2 |
| 4 | (3,2) | 2×2 = 4 | 13 | 4 |

`main.py` 的实际输出也是 `RF=13`。A 是 4 层 stride 1 的结果（`1 + 4×2`）；D 是"先乘 stride 再累加"的错误写法得到的结果（见 Q9）。关键点：**一层自己的 stride 不影响它自己的感受野，只影响后面的层**。

### Q6 — 答案：C

普通卷积：`64 × 64 × 3 × 3 = 36,864`。depthwise：每个输出通道只看对应的一个输入通道，参数 `64 × 1 × 3 × 3 = 576`，比例 `576 / 36,864 = 1/64`，即 `1/C`。这正是讲义练习 2 要证明的"`C·K·K` 而不是 `C·C·K·K`"。B 是把 1×1 卷积和 3×3 卷积参数量比较时的数字，属于干扰项。

### Q7 — 答案：B

stride=1 时，每个输入像素会出现在最多 K×K 个窗口里，所以 `cols` 的形状是 `(C_in·K·K, H_out·W_out)`，大约是输入的 K² 倍（3×3 卷积约 9 倍）。im2col 是精确算法（A 错，`main.py` 实测与朴素版本最大差 `2.86e-06`，只是浮点累加顺序不同）；它天然支持 stride 和多通道（C、D 错）。工业实现会分块（tiling）做 im2col，避免一次性展开整张图。

### Q8 — 参考答案

实际输出（第 0 行与第 5 行）：

```text
[ 0.  0.  0.  0.  0.  0.  0.  3.  3.  0.  0.  0.  0.  0.  0. -3.]
[ 0.  0.  0.  0.  0.  0.  0.  4.  4.  0.  0.  0.  0.  0.  0. -4.]
```

- ① Sobel-x 在第 j 列的响应约等于"右邻列 − 左邻列"（按 1、2、1 加权）。第 7 列：左邻第 6 列 = 0、右邻第 8 列 = 1 → `1+2+1 = 4`；第 8 列：左邻第 7 列 = 0、右邻第 9 列 = 1 → 同样是 4。核宽 3、中心列权重为 0，所以**边缘两侧各有一列**被点亮，讲义"只有第 7 列"的说法不准确。
- ② 第 15 列的右邻是**零填充**，左邻是 1：`0 − 1` 加权得 −4。这是零填充在"图像边缘处的值不为 0"时引入的**伪边缘**——讲义提到的 `reflect` / `replicate` 填充就能避免。
- ③ 第 0 行上方是零填充，3×3 窗口只有两行真实数据，权重只剩 `2 + 1 = 3`；最后一行同理。
- 结论：用"手工核 + 已知输入"做 sanity check 时，要把边界效应也算进预期，否则会误以为实现有 bug。

### Q9 — 参考答案

(a) `[(7,2), (3,2), (3,1)]`：

- 第 1 层：`rf = 1 + 6×1 = 7`，`stride_prod = 2`
- 第 2 层：`rf = 7 + 2×2 = 11`，`stride_prod = 4`
- 第 3 层：`rf = 11 + 2×4 = 19`

答案为 **19**。

(b) 交换顺序后，每层的增量会乘上**包含本层 stride** 的累积乘积：Q5 的栈得到 **19**（正确是 13），stem 栈得到 **29**（正确是 19），两者都已实测验证。错误原因：一层卷积的 stride 决定的是"**下一层**相邻两个神经元在输入上相隔多远"，它本层的窗口仍然是在**上一层**的网格上取 K 个相邻点，这些点在原图上的间距是**之前**各层 stride 的乘积。所以必须先用旧的 `stride_prod` 累加，再更新它。

### Q10 — 参考答案

```python
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

def im2col_fast(x, kh, kw, stride=1, padding=0):
    x_pad = pad2d(x, padding)
    win = sliding_window_view(x_pad, (kh, kw), axis=(1, 2))  # (C, H-kh+1, W-kw+1, kh, kw)，步长为 1 的全部窗口
    win = win[:, ::stride, ::stride]                         # 按 stride 抽取窗口起点
    c, h_out, w_out = win.shape[:3]
    cols = win.transpose(0, 3, 4, 1, 2).reshape(c * kh * kw, h_out * w_out)
    return cols, h_out, w_out
```

已在 `(3, 17, 15)` 的随机输入、`(stride, padding)` 取 `(1,0)`、`(1,1)`、`(2,1)`、`(3,2)` 四种组合下验证：形状与原 `im2col` 一致，`np.array_equal` 全为 True。

要点：

- `sliding_window_view` 通过修改 strides 返回**视图**，不复制数据；真正的复制发生在最后的 `reshape`（因为转置后不连续）。
- 原 `im2col` 中每一列是 `patch.reshape(-1)`，patch 形状 `(C, kh, kw)`，所以行的顺序是"C 最外、kw 最内"；列的顺序是"先行 i 后列 j"。因此要把轴排成 `(C, kh, kw, H_out, W_out)` 再 reshape，二者才能逐元素相等。
- 窗口起点间隔 stride 取样，等价于原代码中的 `hs = i * stride`；输出尺寸也自动满足 `floor((H+2P−K)/S)+1`。

### Q11 — 参考回答要点

- **两个核心归纳偏置**：①**局部性**：一个输出只依赖一个小邻域（相邻像素相关性强）；②**参数共享**：同一组权重在所有位置使用（同一图案可以出现在任何地方）。二者让参数量与图像尺寸无关（`C_out·C_in·K²+C_out`），并带来**平移等变**。
- **等变 vs 不变**：等变是"输入平移、输出跟着平移"，卷积层天然具有；不变是"输入平移、输出不变"，分类任务需要的是后者。CNN 的（近似）平移不变性来自**池化 / 带 stride 的下采样 / 最后的全局平均池化**。
- **加分点**：指出 stride 和池化会破坏严格的等变（只对 stride 整数倍平移等变），因此 CNN 对 1–2 像素的平移其实有时并不鲁棒（相关研究提出了抗混叠的下采样）；也可以对比 ViT：它的归纳偏置更弱，需要更多数据。

### Q12 — 参考回答要点

- **原理**：把每个感受窗口（`C_in×K×K` 个数）展平成 `cols` 的一列，共 `H_out·W_out` 列；把权重 reshape 成 `(C_out, C_in·K·K)`；于是 `Y = W_flat @ cols`，再 reshape 成 `(C_out, H_out, W_out)`。卷积变成了一次 GEMM，可以复用高度优化的 BLAS/cuBLAS。
- **代价**：`cols` 中有大量重复数据，内存约放大 K² 倍，带宽压力大。
- **其他实现**（讲义提到的）：
  - **direct conv**（直接卷积 + cache tiling）：避免展开，适合内存受限的场景；
  - **Winograd**：用变换减少乘法次数，适合 3×3 等小核；
  - **FFT 卷积**：卷积在频域变为逐点乘，适合大核。
- **加分点**：cuDNN 会针对具体形状自动挑选算法（PyTorch 中 `torch.backends.cudnn.benchmark = True` 会在首次运行时做基准测试选择最快算法）。

### Q13 — 参考回答要点

- **计算**：`rf = 1`，逐层 `rf += (K−1) × 之前所有层 stride 的乘积`。stride 全为 1 时简化为 `1 + L(K−1)`。
- **3×3 堆叠的好处**：
  1. 两个 3×3 的感受野 = 一个 5×5，三个 3×3 = 一个 7×7；
  2. 参数更少：`2×9C² = 18C²` vs `25C²`；`3×9C² = 27C²` vs `49C²`；
  3. 每层后都有非线性，表达能力更强；
  4. 3 是"最小的、有中心的奇数核"，same padding 取 P=1 即可。
- **加分点**：区分**理论感受野**与**有效感受野**（effective receptive field）——实际影响输出的区域往往只集中在理论感受野中心的一小块（近似高斯分布）；也可以提到 ConvNeXt 为了更大的感受野重新用了 7×7 的 depthwise 卷积。

### Q14 — 参考回答要点

- 前向：`Y_flat = W_flat @ cols`（`(C_out, CKK) @ (CKK, HW)`）。
- 反向（矩阵乘法的标准求导）：
  - `dW_flat = dY_flat @ colsᵀ`，再 reshape 回 `(C_out, C_in, K, K)`；
  - `db = dY_flat.sum(axis=1)`；
  - `dcols = W_flatᵀ @ dY_flat`，形状 `(CKK, HW)`；
  - `dX = col2im(dcols)`：把每一列"放回"它在输入中对应的窗口位置。
- **为什么要累加**：同一个输入像素出现在多个窗口（多列）中，前向时它对多个输出都有贡献，按多元链式法则，梯度要把这些路径的贡献**相加**（`+=`），而不是覆盖。如果有 padding，最后还要把填充区域的梯度裁掉。
- **加分点**：指出 `dX` 本质上是"用翻转后的核对 `dY` 做一次卷积（转置卷积）"，这也是转置卷积（反卷积）这个名字的来源。

### Q15 — 参考回答要点

- **定义**：把标准卷积拆成两步：①**depthwise**：`groups = C_in`，每个通道单独用一个 K×K 核；②**pointwise**：1×1 卷积在通道之间混合。
- **计算量**（输出 H×W）：标准卷积 `H·W·C_in·C_out·K²`；可分离卷积 `H·W·C_in·K² + H·W·C_in·C_out`。比值 `1/C_out + 1/K²`，3×3 核时约为 1/8～1/9。
- **代价**：表达能力略弱（空间与通道混合被解耦）；depthwise 计算强度（FLOPs/字节）低，在 GPU 上往往是**内存带宽受限**，实际加速比 FLOPs 的减少小得多。
- **应用**：MobileNet、Xception；ConvNeXt 用 7×7 depthwise（讲义 Key Terms 提到 depthwise 是 MobileNet 和 ConvNeXt 的骨干）。

### Q16 — 参考回答要点

- **作用**：①改变通道数（降维/升维），如 ResNet bottleneck 中先 1×1 降维、3×3、再 1×1 升维；②在每个像素位置做跨通道的线性组合 + 非线性，增加深度和表达能力；③在 depthwise separable 中负责通道混合。
- **与全连接的关系**：1×1 卷积 = 在每个空间位置上共享同一个 `C_in → C_out` 的全连接层。参数量 `C_in·C_out (+C_out)`。
- **加分点**：联系第 01 节——RGB→灰度、RGB→YCbCr 这类逐像素线性色彩变换，都可以写成一个 1×1 卷积。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 01 图像基础知识](../../01-image-fundamentals/docs/zh.md)：CHW 布局、通道的含义。
- [阶段 01 · 12 张量运算](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：reshape、转置、矩阵乘。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：Q14 卷积反向传播所需的链式法则。

### 本节被哪些后续内容用到
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：把卷积、池化、残差连接组装成经典网络。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：在真实数据上训练卷积网络。
- [阶段 04 · 07 语义分割 — U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：转置卷积 / 上采样，与 Q14 的 col2im 同源。
- [阶段 04 · 15 实时视觉 — 边缘部署](../../15-real-time-edge/docs/zh.md)：depthwise separable 卷积与移动端骨干网络。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：patch embedding 本质上就是一个 kernel=stride=patch 大小的卷积。
- [阶段 01 · 20 傅里叶变换](../../../01-math-foundations/20-fourier-transform/docs/zh.md)：卷积定理，FFT 卷积的数学基础。

### 延伸关键词
`dilated / atrous 卷积` · `转置卷积（transposed conv）` · `grouped conv` · `Winograd` · `FFT conv` · `有效感受野（ERF）` · `col2im` · `cudnn.benchmark` · `anti-aliased downsampling`
