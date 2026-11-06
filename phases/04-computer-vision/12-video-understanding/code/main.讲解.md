# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 12 节 视频理解——时间建模 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，CPU 即可，几秒内跑完） ｜ **依赖**：`numpy`、`torch`（`torch.nn`）、`torchvision`（`resnet18`；默认 `pretrained=False`，不下载权重、无需联网）

---

## 1. 这份代码在考察什么

这份代码把讲义里三种"处理时间"的方式各做成一个最小可运行的零件，并用随机张量检查形状：

1. **帧采样**：`sample_uniform` / `sample_dense` 如何从任意长度的视频中取出固定 T 个下标，短视频怎么补齐，随机窗口的上界怎么取才不越界。
2. **2D + pool**：`FramePool` 用一个"把时间并入 batch → 逐帧 2D 特征 → 时间均值"的技巧，零改动地复用 ResNet-18。
3. **I3D inflation**：`inflate_2d_to_3d` 把一个 2D 卷积"膨胀"成 3D 卷积，权重沿时间复制后除以 `k_t`。
4. **(2+1)D 分解**：`Conv2Plus1D` 把 3D 卷积拆成空间 + 时间两步，并用公式选中间通道数。
5. **形状直觉**：视频张量有两种布局——`(N, T, C, H, W)`（给 2D 网络用）和 `(N, C, T, H, W)`（给 `Conv3d` 用），分清它们是写视频代码的第一步。

> 一句话：**视频模型的全部差异，在于"时间维在哪一步被处理"**；这份代码让你亲手摸到这三个位置。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sample_uniform(num_frames_total, T)` | 函数 | 在全片上等间隔取 T 个下标 | uniform 采样（2D+pool 的默认） |
| `sample_dense(num_frames_total, T, rng)` | 函数 | 随机取一个连续 T 帧窗口 | dense 采样（3D conv 常用） |
| `FramePool` | `nn.Module` | ResNet-18 逐帧提特征 → 时间均值 → 线性分类 | 2D + pool baseline |
| `inflate_2d_to_3d(conv2d, time_kernel)` | 函数 | 由 `nn.Conv2d` 构造等价初始化的 `nn.Conv3d` | I3D inflation |
| `Conv2Plus1D` | `nn.Module` | `1×k×k` 空间卷积 → BN → ReLU → `k×1×1` 时间卷积 | (2+1)D 分解卷积 |
| `main()` | 演示入口 | 依次打印采样结果、各模块的输出形状和参数量 | — |

数据流：采样器只产出**下标**（真实系统里用它去切视频张量）；三个模型零件彼此独立，各自吃一个随机张量并打印形状。注意 `FramePool` 吃 `(N, T, 3, H, W)`，而两个 3D 零件吃 `(N, C, T, H, W)`。

---

## 3. 逐段精讲

### 3.1 `sample_uniform`：全片均匀取帧

```python
def sample_uniform(num_frames_total, T):
    if num_frames_total <= 0:
        raise ValueError(f"num_frames_total must be positive, got {num_frames_total}")
    if num_frames_total <= T:
        return list(range(num_frames_total)) + [num_frames_total - 1] * (T - num_frames_total)
    step = num_frames_total / T
    return [int(i * step) for i in range(T)]
```

- **输入校验**：总帧数 ≤ 0 直接抛 `ValueError`（讲义版本没有这一步，代码补上了）。空视频如果不拦住，下一行会返回 `[-1, -1, …]` 这种看似合法、实则指向最后一帧的负下标——非常隐蔽的 bug。
- **短视频补齐**：总帧数不足 T 时，先取全部帧，再把**最后一帧重复**补到 T 个。`[x] * n` 生成 n 个相同元素的列表，`+` 拼接列表。这是 skill 文件里推荐的标准策略：保证所有下标都在 `[0, total−1]` 内。
- **等间隔**：`step = total / T` 是浮点数（Python 3 的 `/` 永远是真除法），`int()` 向零截断，所以取的是每一段的**起点**。
- ⚠️ 刻意的简化：取段起点会让结尾几帧永远采不到（30 帧取 8 帧时最后一个下标是 26）。TSN 一类方法取每段**中心** `int((i + 0.5) * step)`，或训练时在每段内随机取一帧。
- 当 `total == T` 时走第一个分支，补齐个数为 0，返回 `[0, 1, …, T−1]`，正好满足 skill 文件里的"边界检查"。

### 3.2 `sample_dense`：随机连续窗口

```python
def sample_dense(num_frames_total, T, rng=None):
    # ...（同样的输入校验）
    rng = rng or np.random.default_rng()
    if num_frames_total <= T:
        return list(range(num_frames_total)) + [num_frames_total - 1] * (T - num_frames_total)
    start = int(rng.integers(0, num_frames_total - T + 1))
    return list(range(start, start + T))
```

- **为什么连续**：3D kernel 的时间感受野只有几帧，必须看**相邻帧**才能感知运动。
- **上界的 `+1`**：`Generator.integers(low, high)` 的 `high` 是**开区间**。合法起点是 `0 … total−T`，所以写 `total − T + 1`。窗口最后一个下标 = `start + T − 1 ≤ total − 1`，永不越界。
- **`rng or np.random.default_rng()`**：`or` 的短路求值——`rng` 为 `None`（假值）时才新建一个随机数生成器。允许调用方传入带种子的 `rng`，这样验证集采样可复现（`main()` 就传了 `default_rng(0)`）。
- ⚠️ 不传 `rng` 时每次调用都新建一个**无种子**的生成器，结果不可复现。训练中这通常没问题，评估时一定要传固定种子。
- `int(...)` 把 NumPy 的 `np.int64` 转成 Python `int`，打印出来是干净的 `[19, 20, …]`，而不是带类型的 NumPy 标量。

### 3.3 `FramePool`：把时间"折叠"进 batch

```python
class FramePool(nn.Module):
    def __init__(self, num_classes=10, pretrained=False):
        super().__init__()
        weights = ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        backbone = resnet18(weights=weights)
        self.features = nn.Sequential(*list(backbone.children())[:-1])
        self.head = nn.Linear(512, num_classes)

    def forward(self, x):
        N, T = x.shape[:2]
        x = x.reshape(N * T, *x.shape[2:])
        feats = self.features(x).view(N, T, -1)
        pooled = feats.mean(dim=1)
        return self.head(pooled)
```

- **拆 backbone**：`backbone.children()` 按顺序给出 ResNet-18 的子模块 `conv1, bn1, relu, maxpool, layer1..4, avgpool, fc`；`[:-1]` 去掉最后的 `fc`，保留全局平均池化，所以每帧输出 `(512, 1, 1)`。`nn.Sequential(*list)` 用星号把列表拆成多个位置参数。
- **核心技巧**：`(N, T, 3, H, W) → (N·T, 3, H, W)`。2D 网络根本不知道"时间"的存在，只当成一个更大的 batch。这正是 2D+pool 能**零改动复用 ImageNet 权重**的原因。
- **`reshape` vs `view`**：`view` 要求张量内存连续，`reshape` 在必要时会复制。输入可能来自切片或 `permute`，内存不一定连续，所以第一步用 `reshape` 更稳（讲义版本用的是 `view`，代码做了加固）；而 backbone 的输出是新张量、一定连续，第二步用 `view` 没问题。
- **时间均值**：`feats.mean(dim=1)` 在 T 维求平均 → `(N, 512)`。这一步**与帧序无关**，是 2D+pool 无法区分"开门/关门"的根源。
- 默认 `pretrained=False`：演示时不联网下载权重。真实使用应设为 `True`，这是 2D+pool 的最大卖点。
- ⚠️ 显存：T 帧意味着 backbone 实际处理 `N·T` 张图，激活显存随 T 线性增长，T=32 时很容易爆显存。

### 3.4 `inflate_2d_to_3d`：I3D 的膨胀

```python
def inflate_2d_to_3d(conv2d, time_kernel=3):
    out_c, in_c, kh, kw = conv2d.weight.shape
    pad_h = conv2d.padding[0] if isinstance(conv2d.padding, tuple) else conv2d.padding
    # ... pad_w / stride_h / stride_w 同理
    has_bias = conv2d.bias is not None
    conv3d = nn.Conv3d(
        in_c, out_c,
        kernel_size=(time_kernel, kh, kw),
        padding=(time_kernel // 2, pad_h, pad_w),
        stride=(1, stride_h, stride_w),
        bias=has_bias,
    )
    weight_3d = conv2d.weight.data.unsqueeze(2).repeat(1, 1, time_kernel, 1, 1) / time_kernel
    conv3d.weight.data = weight_3d
    if has_bias:
        conv3d.bias.data = conv2d.bias.data.clone()
    return conv3d
```

- **权重形状**：2D `(out, in, kh, kw)` → `unsqueeze(2)` 插入时间维 `(out, in, 1, kh, kw)` → `repeat(1, 1, k_t, 1, 1)` 只在时间维复制 → `(out, in, k_t, kh, kw)`，这正是 `nn.Conv3d` 的权重布局。
- **为什么除以 `k_t`**：对一段每帧都相同的"静止视频"，时间维求和 `Σ (W/k_t)·x = W·x`，3D 输出与 2D 输出**完全一致**。膨胀后的网络从"已经认得物体"的状态起步，BN 统计量也不会被放大 `k_t` 倍。
- **bias 不除**：bias 每个输出位置只加一次，与时间 kernel 大小无关，直接 `clone()` 复制。
- **超参数继承**：空间 padding / stride 照抄 2D 卷积；时间 padding 取 `k_t // 2`（"same" 填充，T 不变），时间 stride 固定为 1（不在时间上下采样）。
- **`isinstance(..., tuple)` 判断**：PyTorch 的 `Conv2d` 内部会把整数 padding/stride 规范化成元组，这里的判断是防御式写法，兼容其他来源的对象。
- ⚠️ 简化之处：没有复制 `dilation`、`groups`；若 2D 卷积用了字符串 padding（如 `padding="same"`），`conv2d.padding` 是字符串，这里会出错。真实 I3D 的第一层还会在时间上做 stride 下采样。
- ⚠️ 边界效应：时间方向补零，所以在首尾两帧，静止视频的输出只有 2D 输出的 `(k_t−1)/k_t`。

### 3.5 `Conv2Plus1D`：空间 + 时间分解

```python
class Conv2Plus1D(nn.Module):
    def __init__(self, in_c, out_c, kernel_size=3):
        super().__init__()
        mid_c = max(8, (in_c * out_c * kernel_size * kernel_size * kernel_size) //
                    (in_c * kernel_size * kernel_size + out_c * kernel_size))
        self.spatial = nn.Conv3d(in_c, mid_c,
                                 kernel_size=(1, kernel_size, kernel_size),
                                 padding=(0, kernel_size // 2, kernel_size // 2),
                                 bias=False)
        self.bn = nn.BatchNorm3d(mid_c)
        self.act = nn.ReLU(inplace=True)
        self.temporal = nn.Conv3d(mid_c, out_c,
                                  kernel_size=(kernel_size, 1, 1),
                                  padding=(kernel_size // 2, 0, 0),
                                  bias=False)

    def forward(self, x):
        return self.temporal(self.act(self.bn(self.spatial(x))))
```

- **两步都用 `Conv3d`**：`(1, k, k)` 的 3D kernel 等价于逐帧 2D 卷积，`(k, 1, 1)` 等价于逐像素 1D 时间卷积。都用 `Conv3d` 实现，就不必在 `(N,C,T,H,W)` 与 `(N·T,C,H,W)` 之间来回 reshape。
- **`mid_c` 公式**：完整 3D 卷积的参数是 `in·out·k³`，分解后是 `in·mid·k² + mid·out·k`。令两者相等解出 `mid = in·out·k³ / (in·k² + out·k)`——这是 R(2+1)D 论文的做法：**参数量对齐**，公平比较。`in=out=64` 时 `mid_c = 144`，两者都是 110,592 个参数。
- **收益从哪来**：讲义提到"多一个非线性"——中间的 BN+ReLU 让每个块的表达能力更强；时空解耦也让优化更容易。⚠️ 讲义 Step 4 写"fewer parameters"，但在这个 `mid_c` 公式下参数量是刻意对齐的，并不更少。
- **`max(8, …)`**：通道很少时公式可能给出很小的中间宽度，下限 8 防止瓶颈过窄。代价是此时参数量略多于 3D 卷积（`(3,16)` 时为 1,309 vs 1,296）。
- **两个 `bias=False`**：spatial 后面紧跟 BN，BN 自带平移参数，再加 bias 是冗余；temporal 也不带 bias，与讲义版本一致——在完整的 R(2+1)D 网络里，这个块后面通常还会再接 BN。
- `nn.ReLU(inplace=True)` 直接在输入张量上改写以省显存；BN 的输出是新张量，所以这里安全。

### 3.6 `main()`：演示与形状检查

```python
    print("[frame samplers]")
    for total in [5, 30, 300]:
        print(f"  total={total:4d}  uniform(T=8)={sample_uniform(total, 8)}")
        print(f"  total={total:4d}  dense(T=8)={sample_dense(total, 8, np.random.default_rng(0))}")
    # ...
    model = FramePool(num_classes=10, pretrained=False)
    x = torch.randn(2, 8, 3, 64, 64)
    # ...
    c2d = nn.Conv2d(3, 16, kernel_size=3, padding=1, bias=False)
    c3d = inflate_2d_to_3d(c2d, time_kernel=3)
    y = c3d(torch.randn(1, 3, 8, 32, 32))
    # ...
    c21 = Conv2Plus1D(3, 16)
    y = c21(torch.randn(1, 3, 8, 32, 32))
```

- 三个 `total` 取值刻意覆盖了**短视频（5 < 8）**、**中等（30）**、**长视频（300）**三种情况。
- 每次 dense 采样都新建 `default_rng(0)`，所以结果是确定的，便于对照。
- FramePool 用 64×64 小图代替 224×224，CPU 上几秒就能跑完；ResNet-18 的全局平均池化让它对输入分辨率不敏感。
- 3D 零件的输入布局是 `(N, C, T, H, W) = (1, 3, 8, 32, 32)`——通道在时间前面，这是 `Conv3d` 的约定，与 FramePool 的 `(N, T, C, H, W)` 不同。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 采样器只返回下标 | 与视频解码解耦，可单独测试 | 生产中下标交给 decord / PyAV / torchvision 的视频读取器按需解码 |
| 短视频重复最后一帧 | 保证下标合法、长度恒为 T | 也可循环播放或均匀插值；策略要在训练与评估中保持一致 |
| uniform 取段起点 | 实现最简单 | 结尾帧采不到；TSN 式取段中心或段内随机更好 |
| FramePool 把 T 折进 batch | 零改动复用任何 2D backbone | 显存随 T 线性增长；时间均值丢失顺序信息 |
| 默认 `pretrained=False` | 演示不联网 | 实际应加载 ImageNet 权重，这是 2D+pool 的核心优势 |
| inflation 除以 `k_t` | 静止视频上与 2D 等价，保住激活尺度和 BN 统计量 | 也有"只把权重放在中心帧、其余置零"的初始化方式 |
| `mid_c` 按参数对齐公式 | 与 3D 卷积公平比较 | 小通道时 `max(8, …)` 打破对齐；真实 R(2+1)D 在整个 ResNet 里统一替换 |
| 只打印形状，不训练 | 聚焦结构，几秒跑完 | 真实效果要在 Kinetics / SSv2 上训练评估，见讲义练习 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 函数默认参数 | `def sample_dense(num_frames_total, T, rng=None)` | 不传就用默认值；可变对象（如列表）不要作默认值，所以这里用 `None` |
| `raise` 抛异常 | `raise ValueError(f"... got {num_frames_total}")` | 主动报错并附带出错的值，便于定位 |
| 列表乘法与拼接 | `[num_frames_total - 1] * (T - num_frames_total)`、`list(...) + [...]` | `[x] * n` 复制 n 个元素；`+` 连接两个列表 |
| `range` / `list(range(...))` | `list(range(start, start + T))` | 左闭右开的整数序列 |
| 真除法与截断 | `num_frames_total / T`、`int(i * step)` | `/` 总是返回浮点数；`int()` 向零截断 |
| 列表推导式 | `[int(i * step) for i in range(T)]` | 一行生成新列表 |
| `or` 短路求默认值 | `rng = rng or np.random.default_rng()` | 左边为假值（`None`）时取右边 |
| 条件表达式 | `ResNet18_Weights.IMAGENET1K_V1 if pretrained else None` | `A if 条件 else B` |
| 类继承与 `super()` | `class FramePool(nn.Module)`、`super().__init__()` | 必须先调用父类构造，PyTorch 才能注册子模块和参数 |
| 元组解包 | `N, T = x.shape[:2]`、`out_c, in_c, kh, kw = conv2d.weight.shape` | 一次拿到多个维度 |
| 切片 | `x.shape[2:]`、`list(...)[:-1]` | 取后几维 / 去掉最后一个元素 |
| `*` 解包实参 | `nn.Sequential(*list(...))`、`x.reshape(N * T, *x.shape[2:])` | 把序列拆成多个位置参数 |
| `isinstance` | `isinstance(conv2d.padding, tuple)` | 运行时判断类型 |
| `is not None` | `conv2d.bias is not None` | 判断"是否存在"用 `is`，不用 `==` |
| 关键字参数 | `nn.Conv3d(..., kernel_size=(...), padding=(...), bias=False)` | 按名字传参，可读性高 |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表，统计参数总数的惯用写法 |
| f-string 格式符 | `f"{total:4d}"`、`f"{...:,}"` | `:4d` 宽度 4 右对齐；`:,` 千位分隔符（`11,181,642`） |
| `tuple(...)` | `tuple(x.shape)` | 把 `torch.Size` 转成普通元组打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch` / `torchvision`）。** 采样器部分已在临时目录中用相同函数（只依赖 NumPy）实际执行核对；参数量按网络结构逐项计算。预期输出：

```text
[frame samplers]
  total=   5  uniform(T=8)=[0, 1, 2, 3, 4, 4, 4, 4]
  total=   5  dense(T=8)=[0, 1, 2, 3, 4, 4, 4, 4]
  total=  30  uniform(T=8)=[0, 3, 7, 11, 15, 18, 22, 26]
  total=  30  dense(T=8)=[19, 20, 21, 22, 23, 24, 25, 26]
  total= 300  uniform(T=8)=[0, 37, 75, 112, 150, 187, 225, 262]
  total= 300  dense(T=8)=[249, 250, 251, 252, 253, 254, 255, 256]

[frame-pool model]
  input:  (2, 8, 3, 64, 64)
  output: (2, 10)
  params: 11,181,642

[I3D inflation]
  2D weight shape: (16, 3, 3, 3)
  3D weight shape: (16, 3, 3, 3, 3)
  output: (1, 16, 8, 32, 32)

[(2+1)D conv]
  output: (1, 16, 8, 32, 32)
  params: 1,309
```

逐行解读：

- **total=5**：两种采样器都走"短视频"分支，先取 0–4，再把第 4 帧重复 3 次。dense 在这个分支里根本不碰 `rng`。
- **total=30 uniform**：`step = 3.75`，下标是 `int(0, 3.75, 7.5, …)`；最后一个是 26，第 27–29 帧采不到（见 3.1 的 ⚠️）。
- **total=30 / 300 dense**：起点由 `default_rng(0)` 在 `[0, 23)` / `[0, 293)` 中抽取，得到 19 和 249；窗口最后一帧 26 ≤ 29、256 ≤ 299，不越界。
- **frame-pool**：两段 8 帧视频 → 两行 10 类 logits。参数量 = ResNet-18 去掉 fc（11,689,512 − 513,000 = 11,176,512）+ 新 head（512×10+10 = 5,130）= 11,181,642，与讲义"约一千一百万参数"一致。
- **I3D inflation**：权重多了一个大小为 3 的时间维；`padding=(1,1,1)`、`stride=(1,1,1)`，所以 T、H、W 都保持不变。
- **(2+1)D**：`mid_c = max(8, 1296 // 75) = 17`；参数 = 空间 3·17·9 = 459 + BN 2·17 = 34 + 时间 17·16·3 = 816 = **1,309**；对照完整 3D 卷积 3·16·27 = 1,296，几乎相同。输出形状同样保持 `(1, 16, 8, 32, 32)`。

---

## 7. 动手改一改

1. **中心采样**：把 `sample_uniform` 改成取段中心 `int((i + 0.5) * step)`，对比 `total=30` 时的下标（应为 `[1, 5, 9, 13, 16, 20, 24, 28]`）。
2. **顺序不变性实验**：在 `model.eval()` 下比较 `model(x)` 与 `model(x.flip(1))`，确认两者相等（`torch.allclose`），亲眼看到 2D+pool 分不清正放和倒放。
3. **boring video 验证**：构造 8 帧相同的视频，比较 `c3d(video)[:, :, t]` 与 `c2d(img)`：中间帧应相等，首尾帧约为 2/3。
4. **参数对齐表**：对 `(in_c, out_c)` 取 `(3,16)`、`(64,64)`、`(128,256)`，打印 `Conv2Plus1D` 与 `nn.Conv3d(in_c, out_c, 3, bias=False)` 的参数量，观察 `max(8, …)` 何时打破对齐。
5. **有序时间头**：把 `feats.mean(dim=1)` 替换成 `nn.Conv1d(512, 512, 3, padding=1)` + 时间均值（注意先 `transpose` 成 `(N, 512, T)`），再做第 2 题的实验，看输出是否开始依赖帧序。
6. **（进阶）讲义练习 2**：生成"小球向左/向右移动"的合成视频，分别训练 FramePool 和一个由 `Conv2Plus1D` 堆成的小网络，比较准确率。

---

## 8. 常见坑

- **张量布局搞混**：2D+pool 用 `(N, T, C, H, W)`，`Conv3d` 要 `(N, C, T, H, W)`。错了不一定报错（比如 T 恰好等于 3 时），但语义全错。用 `x.permute(0, 2, 1, 3, 4)` 转换并 assert 形状。
- **`view` 遇到非连续张量**：`permute` 之后直接 `view` 会抛 `RuntimeError`，用 `reshape` 或先 `.contiguous()`。
- **`integers` 的开区间**：上界少写 `+1` 会永远采不到最后一个窗口，多写会越界——都是 off-by-one。
- **膨胀时忘记除以 `k_t`**：初始激活被放大 `k_t` 倍，BN 统计量失真，微调初期 loss 异常。
- **评估不可复现**：dense 采样不传固定种子，每次评估的 clip 不同，指标上下抖动。
- **同一 clip 内逐帧随机裁剪**：每帧裁剪框不同会人为制造"运动"，破坏时间一致性，增强必须按 clip 统一。
