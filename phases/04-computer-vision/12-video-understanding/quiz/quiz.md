# 测验 · 视频理解——时间建模（Video Understanding — Temporal Modeling）

> **阶段 04 · 计算机视觉 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 视频建模的三大范式 | 时间要么是"再池化一次"（2D+pool），要么是卷积的一个新轴（3D conv），要么是 attention 的一个 token 维度（时空 Transformer） |
| 2 | 2D + pool 与顺序无关 | 逐帧跑 2D CNN 再对时间求平均；平均是置换不变的，"开门"和"关门"得到同一个向量 |
| 3 | 3D 卷积 | kernel 形状为 (T, H, W)，能直接捕捉相邻帧之间的运动；每层计算量约是逐帧 2D 卷积的 `k_t` 倍 |
| 4 | I3D inflation（膨胀） | 把 ImageNet 预训练的 2D kernel 沿新时间轴复制 `k_t` 份再除以 `k_t`，3D 网络一开始就拥有强初始化 |
| 5 | (2+1)D 分解卷积 | 3D 卷积拆成 `1×k×k` 空间卷积 + `k×1×1` 时间卷积，中间夹 BN+ReLU；中间通道数 `mid_c` 按公式取，使参数量与完整 3D 卷积相当 |
| 6 | 时空 attention 模式 | joint：对全部 `T·H·W` 个 token 做一次 attention，二次方代价；divided：每个 block 先时间后空间两次 attention；factorised：时间/空间 attention 在不同 block 间交替 |
| 7 | 帧采样 | uniform（全片均匀取 T 帧，适合 2D+pool）、dense（随机连续 T 帧窗口，适合 3D conv）、multi-clip（测试时取多个窗口再平均）；T 常取 8/16/32/64 |
| 8 | clip 级 vs video 级准确率 | clip 级只看一个 T 帧窗口；video 级对多个 clip 的预测求平均，更高更稳；两者都要报告 |
| 9 | 常见数据集 | Kinetics-400/600/700（通用动作）、Something-Something V2（由运动定义的动作）、UCF-101 / HMDB-51（较老较小）、AVA（时空动作定位） |

### 核心技能（能动手做到）

- [ ] 实现 `sample_uniform` / `sample_dense`，并能说清短视频（总帧数 < T）时"重复最后一帧"的补齐策略和窗口上界为什么是 `num_frames_total - T + 1`
- [ ] 写出 FramePool 的形状变换链：`(N,T,3,H,W) → (N·T,3,H,W) → (N·T,512,1,1) → (N,T,512) → mean → (N,512) → (N,num_classes)`
- [ ] 实现 `inflate_2d_to_3d`，并验证：输入"每帧都一样的静止视频"时，3D 输出在时间内部位置等于 2D 输出
- [ ] 手算 `Conv2Plus1D` 的 `mid_c` 和参数量，并与同尺寸 3D 卷积对比
- [ ] 估算 joint 与 divided attention 的 token 对数量，说出两者的复杂度表达式
- [ ] 能根据"外观主导还是运动主导、数据量、算力预算"在 2D+pool / I3D / (2+1)D / 视频 Transformer 之间做选型，并设计 clip/video 两级评估

---

## 二、基础自测（选择题）

**Q1.** 一个 2D+pool 模型在 Kinetics 上表现不错，但在 Something-Something V2 上接近乱猜。最根本的原因是：

- A. Something-Something V2 的分辨率太低，2D CNN 提不出特征
- B. 时间维度上的平均池化是置换不变的，打乱或倒放帧序得到的表示完全相同，而该数据集的标签恰恰由运动方向定义
- C. 2D+pool 无法使用 ImageNet 预训练权重
- D. Something-Something V2 的类别数太多，线性分类头容量不够

**Q2.** I3D 把 2D kernel 沿时间轴复制 `k_t` 份后要**除以 `k_t`**。这一步的主要目的是：

- A. 减少参数量，防止过拟合
- B. 让时间方向的权重学得更快
- C. 使网络在"每帧都相同的静止视频"上输出与原 2D 网络一致，保持激活尺度，不破坏 BatchNorm 统计量
- D. 让 3D 卷积具有平移不变性

**Q3.** 关于本节代码中的 `Conv2Plus1D`，下列描述正确的是：

- A. 先做 `k×1×1` 时间卷积再做 `1×k×k` 空间卷积，中间没有非线性，参数量是 3D 卷积的 1/3
- B. 先做 `1×k×k` 空间卷积，经 BN+ReLU 后再做 `k×1×1` 时间卷积；`mid_c` 按公式选取，使总参数量与一个完整的 `k×k×k` 3D 卷积大致相当
- C. 先做 `1×k×k` 空间卷积，经 BN+ReLU 后再做 `k×1×1` 时间卷积；`mid_c` 固定等于 `out_c`
- D. 它是深度可分离卷积，每个通道单独做 3D 卷积

**Q4.** 输入 8 帧 224×224，patch 16×16（每帧 196 个 patch）。joint 时空 attention 与 divided attention 各自需要计算的 query-key 对数量大约是：

- A. 都是约 246 万，divided 只是换了计算顺序
- B. joint 约 246 万；divided 约 32 万（每个 token 只看同位置的 8 个 + 同帧的 196 个），约省 7.7 倍
- C. joint 约 1568；divided 约 204
- D. joint 约 246 万；divided 约 3.8 万（196² ）

**Q5.** 训练一个 3D CNN 时，通常更推荐哪种采样方式？

- A. uniform：在整段视频上均匀取 T 帧，覆盖面最广
- B. dense：随机取一个连续的 T 帧窗口，因为 3D kernel 要靠相邻帧之间的差异来感知运动
- C. 只取第一帧复制 T 次
- D. 随机取 T 个不重复且不排序的帧

**Q6.** 模型 A：clip 级 78%、video 级 82%；模型 B：clip 级 80%、video 级 81%。下列说法最合理的是：

- A. A 更好，因为 video 级准确率才是唯一重要的指标
- B. A 对"采到哪个窗口"更敏感，较依赖测试时多 clip 平均；B 的单 clip 预测更稳健，在只能看一个 clip 的实时场景里可能更合适
- C. 两者完全等价，差别只是测试集噪声
- D. clip 级准确率按定义一定比 video 级低 4 个点

**Q7.** 下面哪个场景最适合先用 2D+pool 作为 baseline？

- A. 判断一段视频里的物体是"从左推到右"还是"从右推到左"
- B. 判断工人是在"拧紧"还是"拧松"螺丝
- C. 在一个只有几千条视频的小数据集上识别体育项目（篮球/游泳/体操），且算力有限
- D. 在 AVA 上做时空动作定位

---

## 三、动手 / 代码题

**Q8.** 阅读本节的两个采样器：

```python
def sample_uniform(num_frames_total, T):
    if num_frames_total <= 0:
        raise ValueError(f"num_frames_total must be positive, got {num_frames_total}")
    if num_frames_total <= T:
        return list(range(num_frames_total)) + [num_frames_total - 1] * (T - num_frames_total)
    step = num_frames_total / T
    return [int(i * step) for i in range(T)]


def sample_dense(num_frames_total, T, rng=None):
    if num_frames_total <= 0:
        raise ValueError(f"num_frames_total must be positive, got {num_frames_total}")
    rng = rng or np.random.default_rng()
    if num_frames_total <= T:
        return list(range(num_frames_total)) + [num_frames_total - 1] * (T - num_frames_total)
    start = int(rng.integers(0, num_frames_total - T + 1))
    return list(range(start, start + T))
```

(1) 写出 `sample_uniform(5, 8)` 和 `sample_uniform(30, 8)` 的返回值。
(2) `sample_uniform(30, 8)` 有一个系统性偏差：哪些帧永远不会被取到？把它改成"取每段的中心帧"，并写出改后 `(30, 8)` 的结果。
(3) 如果有人把 `sample_dense` 的上界写成 `rng.integers(0, num_frames_total - T + 2)`，会出什么问题？写成 `num_frames_total - T` 又会怎样？

**Q9.** 对照 `FramePool.forward`：

```python
    def forward(self, x):
        N, T = x.shape[:2]
        x = x.reshape(N * T, *x.shape[2:])
        feats = self.features(x).view(N, T, -1)
        pooled = feats.mean(dim=1)
        return self.head(pooled)
```

(1) `main()` 中输入 `x = torch.randn(2, 8, 3, 64, 64)`，写出 `x`、`self.features(x)`、`feats`、`pooled`、输出各自的形状，以及 `main()` 打印的参数量（提示：标准 ResNet-18 共 11,689,512 个参数，其中 fc 层 512×1000+1000）。
(2) 若把 `feats.mean(dim=1)` 误写成 `feats.mean(dim=0)`，代码会报错吗？结果的语义错在哪？
(3) 在 `model.eval()` 下，把输入沿 T 维倒序（`x.flip(1)`），输出会变吗？这说明了什么？

**Q10.** 下面是 `inflate_2d_to_3d` 的核心一行：

```python
    weight_3d = conv2d.weight.data.unsqueeze(2).repeat(1, 1, time_kernel, 1, 1) / time_kernel
```

构造一个"静止视频"：8 帧完全相同，每帧都是同一张图 `img`（形状 `(1,3,32,32)`）。用 `c2d` 和 `c3d = inflate_2d_to_3d(c2d, 3)` 分别计算输出。请说明：在时间位置 `t = 1..6` 和 `t = 0, 7` 上，3D 输出与 2D 输出各是什么关系？为什么？写一段验证代码。

**Q11.** `Conv2Plus1D` 的中间通道数：

```python
        mid_c = max(8, (in_c * out_c * kernel_size * kernel_size * kernel_size) //
                    (in_c * kernel_size * kernel_size + out_c * kernel_size))
```

(1) 计算 `Conv2Plus1D(3, 16)` 的 `mid_c` 和 `main()` 中打印的参数量，并与 `nn.Conv3d(3, 16, 3, bias=False)` 的参数量对比。
(2) 再算 `Conv2Plus1D(64, 64)` 的 `mid_c`，说明这个公式的设计意图。
(3) `max(8, ...)` 起什么作用？

---

## 四、面试高频题

**Q12.**（基础必考）视频理解有哪几种主流建模范式？分别说说它们的优缺点和适用场景。

**Q13.**（原理深挖）I3D 的 inflation 是怎么做的？为什么能把 ImageNet 预训练迁移到 3D 网络？(2+1)D 相比完整 3D 卷积的优势到底来自哪里？

**Q14.**（原理深挖）视频 Transformer 的 token 数为什么是个大问题？joint / divided / factorised attention 各自怎么降低代价？还有哪些减少 token 的手段？

**Q15.**（工程实践）你负责一个视频动作识别项目的训练与评估流水线，帧采样和评估协议怎么设计？有哪些容易踩的坑？

**Q16.**（场景设计 / 追问型）现有一个已部署的 2D+pool 模型，产品新增了"区分开门与关门"的需求，但不允许换成重型 3D backbone、推理预算最多增加 20%。你会怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：B

`mean(f₁, …, f_T)` 与帧序无关，`pool(f₁…f_T) = pool(f_T…f₁)`。Something-Something V2 的标签是"把 X 从左推到右"这类运动描述，单帧里只是两个静止物体，平均后正反两个方向的表示一模一样。A、D 不是根本原因；C 恰恰说反了——2D+pool 的最大优点就是能直接用 ImageNet 预训练。

### Q2 — 答案：C

把 2D kernel `W` 复制 `k_t` 份再除以 `k_t`，对一段静止视频（I3D 论文称为 "boring video"），3D 卷积在每个时间位置的输出 = `Σ_τ (W/k_t)·x = W·x`，恰好等于 2D 卷积的输出。这样膨胀后的网络在第一次前向时激活尺度与原 2D 网络一致，BN 的统计量不会突然失真。A 错：除法不改变参数个数；B、D 与此无关。

### Q3 — 答案：B

代码中 `self.spatial` 的 kernel 是 `(1, k, k)`、`self.temporal` 是 `(k, 1, 1)`，中间是 `BatchNorm3d + ReLU`。`mid_c` 的公式 `in·out·k³ / (in·k² + out·k)` 正是让 `in·mid·k² + mid·out·k ≈ in·out·k³`，即**参数量与完整 3D 卷积相当**（R(2+1)D 论文的做法）。所以 (2+1)D 的收益主要来自多出来的一个非线性和更容易优化的时空分解，而不是"省参数"。A 顺序和参数量都错；C 的 `mid_c` 错；D 混淆了深度可分离卷积。

### Q4 — 答案：B

token 总数 `N = 8 × 196 = 1568`。joint：每个 token 看全部 1568 个，共 `1568² ≈ 2,458,624` 对，复杂度 `O((T·S)²)`。divided：每个 token 先看同一空间位置的 8 个（时间 attention），再看同一帧的 196 个（空间 attention），共 `1568 × (8+196) = 319,872` 对，复杂度 `O(T·S·(T+S))`，约省 7.7 倍；T 越大差距越大。D 只算了一帧的空间 attention，漏掉了 T 帧和时间 attention。

### Q5 — 答案：B

3D kernel 的时间感受野很小（如 3 帧），它要从**相邻帧之间的变化**里学运动；uniform 采样在长视频里帧间隔很大（300 帧取 8 帧，间隔 37 帧），相邻采样帧之间的运动已不连贯。讲义原话：dense 采样"常用于 3D 卷积，因为运动需要相邻帧"。uniform 是 2D+pool 的默认选择。D 打乱顺序会直接破坏时间结构。

### Q6 — 答案：B

clip 与 video 的差距衡量的是"模型对采到哪个窗口有多敏感"。A 的 4 个点差距说明它很依赖测试时的多 clip 平均（相当于 test-time augmentation）；B 的单 clip 预测本身就稳。若线上只能对一个窗口推理（如实时流），B 更可靠。D 错：video 级通常更高，但差距不是定义出来的固定值。

### Q7 — 答案：C

体育项目类别主要由外观（场地、器材、服装）决定，几乎每一帧都能看出来；数据小、算力有限时，复用 ImageNet 预训练的 2D+pool 最划算，讲义指出它在外观主导任务上常常只比 3D 模型差 5–10 个点，有时甚至更好。A、B 由运动方向定义，平均池化分不开；D 是时空定位任务，比分类更难。

### Q8 — 参考答案

(1)

```text
sample_uniform(5, 8)  → [0, 1, 2, 3, 4, 4, 4, 4]     # 不足 T 帧：先全取，再重复最后一帧
sample_uniform(30, 8) → [0, 3, 7, 11, 15, 18, 22, 26] # step = 3.75，int 向下取整
```

(2) `int(i * step)` 取的是每段的**起点**，最后一个下标是 `int(7 × 3.75) = 26`，第 27、28、29 帧永远取不到——视频结尾的动作（比如"把杯子放下"的最后一瞬）被系统性忽略。改为每段中心（TSN 风格）：

```python
def sample_uniform_center(num_frames_total, T):
    if num_frames_total <= 0:
        raise ValueError(f"num_frames_total must be positive, got {num_frames_total}")
    if num_frames_total <= T:
        return list(range(num_frames_total)) + [num_frames_total - 1] * (T - num_frames_total)
    step = num_frames_total / T
    return [int((i + 0.5) * step) for i in range(T)]

print(sample_uniform_center(30, 8))   # [1, 5, 9, 13, 16, 20, 24, 28]
```

首尾两端都留出半段余量，覆盖更对称。

(3) `rng.integers(low, high)` 的 `high` 是**开区间**。合法起点是 `0 … total − T`，所以上界应为 `total − T + 1`（原代码正确）。
- 写成 `+ 2`：起点可能取到 `total − T + 1`，窗口最后一个下标为 `total`，**越界**（如 300 帧时取到第 300 帧），解码或索引时报错，或者在某些加载器里被静默截断。
- 写成 `total − T`：不会崩，但永远取不到"贴着结尾"的那个窗口，是一个很难发现的 off-by-one 偏差。

### Q9 — 参考答案

(1) 形状链：

| 变量 | 形状 | 说明 |
|------|------|------|
| 输入 `x` | `(2, 8, 3, 64, 64)` | N=2 段视频，每段 T=8 帧 |
| reshape 后 `x` | `(16, 3, 64, 64)` | 把时间并进 batch，2D 网络当 16 张图处理 |
| `self.features(x)` | `(16, 512, 1, 1)` | ResNet-18 去掉 fc，保留全局平均池化（64→32→16→8→4→2→1） |
| `feats` | `(2, 8, 512)` | 拆回 (N, T, 特征) |
| `pooled` | `(2, 512)` | 沿时间求均值 |
| 输出 | `(2, 10)` | 线性分类头 |

参数量：ResNet-18 去掉 fc 后为 `11,689,512 − 513,000 = 11,176,512`，新 head 为 `512×10 + 10 = 5,130`，合计打印 `params: 11,181,642`。

(2) 不会报错。`feats.mean(dim=0)` 得到 `(8, 512)`，head 输出 `(8, 10)`——变成"把 batch 里两段不同视频的同一帧位置平均"，混淆了不同样本，输出的第一维也从 N 变成了 T。形状"恰好能跑"是这类 bug 最危险的地方，所以要在关键处 `assert out.shape == (N, num_classes)`。

(3) 不变（只有浮点求和顺序带来的 1e-7 级误差）。每帧特征独立计算，平均与顺序无关——这就是"2D+pool 分不清开门和关门"的直接证明。`train()` 模式下 BN 用的是整个 `N·T` 批次的统计量，帧的排列也不影响它，结论相同。

### Q10 — 参考答案

- **内部位置 `t = 1..6`**：时间 kernel 覆盖 `t−1, t, t+1` 三帧，三帧内容相同，`Σ_τ (W/3)·img = W·img`，**与 2D 输出完全相等**。
- **边界 `t = 0` 和 `t = 7`**：时间方向 `padding = time_kernel // 2 = 1` 补的是 0，只有两帧真实内容参与，输出 = **2D 输出的 2/3**（`c2d` 无 bias；若有 bias，代码把 bias 原样复制、不除以 `k_t`，所以是 `2/3·W·img + b`）。

验证代码（需要 PyTorch；当前环境无 torch，未实际运行，结论由上式推出）：

```python
import torch
import torch.nn as nn
from main import inflate_2d_to_3d

torch.manual_seed(0)
c2d = nn.Conv2d(3, 16, kernel_size=3, padding=1, bias=False)
c3d = inflate_2d_to_3d(c2d, time_kernel=3)

img = torch.randn(1, 3, 32, 32)
video = img.unsqueeze(2).repeat(1, 1, 8, 1, 1)   # (1, 3, 8, 32, 32) 静止视频

with torch.no_grad():
    y2d = c2d(img)                               # (1, 16, 32, 32)
    y3d = c3d(video)                             # (1, 16, 8, 32, 32)

for t in range(8):
    ratio = (y3d[:, :, t] / y2d).mean().item()
    print(t, torch.allclose(y3d[:, :, t], y2d, atol=1e-5), round(ratio, 3))
# 预期：t=0 和 t=7 为 False、比值约 0.667；t=1..6 为 True、比值约 1.0
```

这就是 I3D 论文所说的 "boring video" 不动点：膨胀后的 3D 网络在静止视频上和原 2D 网络等价，因此 ImageNet 学到的外观特征被原封不动地带进了视频模型。

### Q11 — 参考答案

(1) `Conv2Plus1D(3, 16)`：

```text
mid_c = max(8, (3·16·27) // (3·9 + 16·3)) = max(8, 1296 // 75) = max(8, 17) = 17
spatial  Conv3d(3→17, 1×3×3) : 3·17·9  = 459
bn       BatchNorm3d(17)      : 2·17    = 34     (weight + bias；running_mean/var 是 buffer 不计入)
temporal Conv3d(17→16, 3×1×1): 17·16·3 = 816
合计 = 1,309                                  ← main() 打印 params: 1,309
完整 3D 卷积 Conv3d(3, 16, 3, bias=False)    : 3·16·27 = 1,296
```

两个卷积合计 1,275，与 3D 卷积的 1,296 几乎一样，加上 BN 的 34 个参数后为 1,309。

(2) `Conv2Plus1D(64, 64)`：`mid_c = (64·64·27) // (64·9 + 64·3) = 110592 // 768 = 144`，两个卷积参数 `64·144·9 + 144·64·3 = 110,592`，与 3D 卷积 `64·64·27 = 110,592` **完全相等**。设计意图：在**参数量相同**的前提下公平比较，(2+1)D 的增益来自中间多出的非线性（BN+ReLU）以及把时空分开后更容易优化，而不是靠堆参数。

(3) 当 `in_c`、`out_c` 很小时公式可能给出很小的 `mid_c`（例如 1 或 2），中间瓶颈过窄会严重损失表达能力，`max(8, …)` 给中间通道设了下限；代价是此时参数量不再与 3D 卷积严格匹配。

### Q12 — 参考回答要点

- **2D + pool**：逐帧跑 2D CNN/ViT，时间上平均（或 max / attention pooling）后分类。
  - 优点：直接用 ImageNet 预训练、实现最简单、计算量 = T × 单图推理。
  - 缺点：不建模运动，平均池化与顺序无关。
  - 适用：外观主导任务、小数据集迁移、快速 baseline。
- **3D 卷积**（C3D、I3D、SlowFast；以及 R(2+1)D 这种分解版本）：kernel 覆盖 (T,H,W)。
  - 优点：原生建模局部运动；I3D inflation 能复用 2D 预训练。
  - 缺点：每层计算约为逐帧 2D 的 `k_t` 倍；时间感受野小，长程运动要靠金字塔或双路结构。
  - 适用：运动定义的动作（SSv2、Kinetics 中运动性强的类）。
- **时空 Transformer**（TimeSformer、ViViT、Video Swin、VideoMAE）：把视频切成时空 patch 做 attention。
  - 优点：主流 benchmark 精度最高，能从 ViT 迁移，可通过稀疏 attention 处理长视频。
  - 缺点：计算量大，attention 模式选错代价会爆炸。
  - 适用：大数据、高精度、视频+文本多模态任务。
- **加分点**：一句话概括"时间在哪一步被建模"——池化时、卷积时、attention 时；并指出选型的三个维度：外观 vs 运动、数据量、算力。
- **常见误区**：认为 3D 模型一定比 2D+pool 好。在外观主导任务上，用更强 ImageNet backbone 的 2D+pool 常常只差 5–10 个点，有时更好。

### Q13 — 参考回答要点

- **inflation 做法**：`W2d (out,in,kh,kw)` → `unsqueeze` 出时间维 → 复制 `k_t` 份 → 除以 `k_t`，得到 `(out,in,k_t,kh,kw)`；空间 padding / stride 照搬，时间 padding 取 `k_t // 2`、时间 stride 取 1（本节代码的选择）。
- **为什么有效**：除以 `k_t` 保证在静止视频上 3D 输出 = 2D 输出（"boring video" 不动点），所以膨胀后的网络从"已经会认物体和纹理"的状态出发，训练只需学会利用时间维的差异，而不是从零学外观。I3D 也因此成为第一个明显超过 2D+pool 的 3D 模型。
- **(2+1)D 的优势**：
  1. 在 `mid_c` 公式下参数量与 3D 卷积相当，但每个块多一个非线性，函数表达能力更强；
  2. 空间和时间分开，优化更容易（R(2+1)D 论文报告训练误差更低）；
  3. 空间部分仍是 `1×k×k`，与 2D 预训练权重形状更接近。
- **常见误区**：说"(2+1)D 的主要好处是省参数"。按论文的 `mid_c` 公式，参数量是刻意对齐的；本节代码 `(64,64)` 时两者恰好都是 110,592。

### Q14 — 参考回答要点

- **问题**：8 帧 × 196 patch = 1568 个 token，joint attention 需要约 246 万个 query-key 对；帧数翻倍，代价翻 4 倍。长视频根本放不下。
- **三种模式**：
  - joint：一次 attention 覆盖全部 `T·S` 个 token，`O((T·S)²)`，表达最强但最贵；
  - divided（TimeSformer）：每个 block 先时间 attention（同一空间位置跨帧），再空间 attention（同一帧内），`O(T·S·(T+S))`；
  - factorised：时间与空间 attention 在不同 block 之间交替。
- **其他减 token 手段**：降低采样帧数 T 或分辨率；用更大的 patch / 时空 tube 做 embedding（ViViT 的 tubelet embedding）；层级结构与局部窗口（Video Swin）；稀疏 attention（讲义提到的长视频支持方式）；自监督预训练时大比例 mask 掉 token（VideoMAE）。
- **加分点**：能写出 divided 的复杂度式子并代入数字；指出视频帧间高度冗余，这正是能大幅减 token 的根本原因。

### Q15 — 参考回答要点

- **采样**：
  - 2D+pool 用 uniform 覆盖全片；3D 用 dense 连续窗口；T 按任务和预算取 8/16/32/64；
  - 短视频（总帧数 < T）统一用"重复最后一帧"补齐，保证返回下标都在 `[0, total−1]`；
  - dense 窗口上界用开区间 `total − T + 1`，防止越界。
- **评估**：同时报告 clip 级（单窗口）和 video 级（多 clip 平均）top-1/top-5；multi-clip 的 clip 数要写进实验配置，否则数字不可比。
- **数据增强**：随机裁剪、翻转必须**按 clip 一致**——同一个 clip 内所有帧用同一个裁剪框，否则会人为制造"运动"。
- **可复现性**：dense 采样显式传入带种子的 `rng`；验证集采样固定。
- **常见坑**：
  - off-by-one 越界；
  - 帧率不同的视频统一按帧数采样，导致时间尺度不一致（可按秒采样）；
  - Kinetics 很多 YouTube 链接已失效，不同团队的测试集其实不一样；
  - 解码往往才是瓶颈，要预解码或用 GPU 解码。
- **加分点**：提到 clip/video 差距能诊断模型对窗口位置是否敏感，差距大说明要用更长 clip 或更强的增强。

### Q16 — 参考回答要点

- **诊断**：开门/关门在任何单帧上外观相似，均值池化与顺序无关，所以问题出在**时间聚合方式**，而不是 backbone 不够强。
- **低成本方案**（保持 2D backbone 不变）：
  1. 把均值池化换成**有序的时间头**：在 `(N, T, 512)` 的帧特征上加 1D 时间卷积、小型 Transformer（带时间位置编码）或 GRU，计算量只占 backbone 的很小一部分；
  2. 加入**运动信号**：特征差分 `f_{t+1} − f_t` 或帧差图作为额外输入（双流思想的轻量版）；
  3. 在 backbone 内部做零 FLOPs 的时间交互，例如 temporal shift（沿时间维平移部分通道）。
- **数据与验证**：
  - 构造"倒放视频"作对照，开门倒放就是关门，可以直接做数据增强并交换标签；
  - 验证模型对倒序输入的预测是否随之翻转，这是检验时间建模是否生效的单元测试。
- **评估与上线**：分别看 clip 和 video 两级准确率；压测确认推理成本增加不超过 20%。
- **常见误区**：一上来就换 I3D/视频 Transformer，推理成本可能翻几倍，而问题本质只是"聚合方式丢失了顺序"。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：ResNet-18 结构，FramePool 的 backbone。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：逐帧分类与 top-k 评估。
- [阶段 04 · 05 迁移学习与微调](../../05-transfer-learning/docs/zh.md)：I3D inflation 本质上是一种跨维度的迁移学习。
- [阶段 04 · 02 从零实现卷积](../../02-convolutions-from-scratch/docs/zh.md)：理解卷积 kernel 形状、padding、stride，才能把它推广到 3D。

### 本节被哪些后续内容用到
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：patch token 与 attention，是时空 Transformer 的基础。
- [阶段 04 · 17 自监督视觉](../../17-self-supervised-vision/docs/zh.md)：MAE 的视频版本 VideoMAE 是讲义推荐的主流视频预训练方案。
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：从"整段视频一个标签"走向"逐帧跟踪每个物体"。
- [阶段 04 · 28 世界模型与视频扩散](../../28-world-models-video-diffusion/docs/zh.md)：从理解视频走向生成视频。
- [阶段 08 · 10 视频生成](../../../08-generative-ai/10-video-generation/docs/zh.md)：时空建模在生成侧的对应。
- [阶段 12 · 09 Qwen-VL 系列与动态帧率](../../../12-multimodal-ai/09-qwen-vl-family-dynamic-fps/docs/zh.md)：视频大模型如何采样帧、控制 token 数。
- [阶段 12 · 17 视频-语言时间定位](../../../12-multimodal-ai/17-video-language-temporal-grounding/docs/zh.md)：把"何时发生"与文本对齐。
- [阶段 19 · 12 视频理解流水线](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：综合项目中完整落地。

### 延伸关键词
`SlowFast` · `TSN（Temporal Segment Networks）` · `TSM（Temporal Shift Module）` · `双流网络与光流` · `TimeSformer` · `ViViT tubelet embedding` · `Video Swin` · `VideoMAE` · `multi-clip / multi-crop 测试`
