# 测验 · 实时视觉——边缘部署（Real-Time Vision — Edge Deployment）

> **阶段 04 · 计算机视觉 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个预算 | 延迟（看 p50/p95/p99，不只看均值）、峰值内存（OOM 在嵌入式上是致命的）、功耗（每次推理的毫焦耳）；所有数字都要在**目标设备**上测 |
| 2 | 测量纪律 | 先 warmup 5–10 次；GPU 计时前后都要 `torch.cuda.synchronize()`；输入尺寸固定为生产分辨率 |
| 3 | FLOPs 只是代理 | 适合做架构比较和搜索，不能当作真实耗时；FLOPs 多 10% 的模型可能因为算子对硬件友好而快 2 倍 |
| 4 | INT8 量化 | 模型体积和内存带宽约降为 1/4，在有 INT8 内核的硬件上计算快 2–4 倍；视觉模型静态 PTQ 通常只损失 0.1–1 个点 |
| 5 | 三种量化方式 | dynamic（只量化权重，激活仍用浮点）、static PTQ（权重 + 用校准集确定激活范围）、QAT（训练中模拟量化，精度最好、需要带标签数据） |
| 6 | 剪枝与蒸馏 | 剪枝对过参数化模型有效，对已经很紧凑的架构收益小；蒸馏让小学生模型模仿大教师的 logits，是生产边缘模型的标配 |
| 7 | 推理运行时 | PyTorch → ONNX 是通用路线；再按目标选 ONNX Runtime、TensorRT（NVIDIA）、Core ML（Apple）、TFLite（Android/ARM）、OpenVINO（Intel） |
| 8 | 边缘架构选型 | MobileNetV3-Small、EfficientNet-Lite、ConvNeXt-Tiny、MobileViT 等按预算选择，并且默认都量化到 INT8 |
| 9 | ONNX 导出 | `torch.onnx.export` + `opset_version=17` + `dynamic_axes` 让 batch 维可变 |

### 核心技能（能动手做到）

- [ ] 写出一个"可信"的延迟基准函数：warmup、GPU 同步、`time.perf_counter()`、正确的百分位计算
- [ ] 用 forward hook 估算 Conv/Linear 的 FLOPs，并正确处理分组卷积（depthwise）和作用在多个空间位置上的 `nn.Linear`
- [ ] 跑通一次 eager 模式的静态 PTQ：插入 `QuantStub/DeQuantStub` → `fuse_modules` → `prepare` → 校准 → `convert`，并对比 FP32/INT8 的延迟与精度
- [ ] 把模型导出为 ONNX（带动态 batch），并能说出常见的导出失败原因
- [ ] 为多个候选 backbone 建出 (params, FLOPs, p50, p95, 内存, 精度) 对比表，并据此做出上线决策
- [ ] 根据设备与延迟 SLA 选择 backbone、精度格式和运行时

---

## 二、基础自测（选择题）

**Q1.** 同事汇报："模型在 4090 上平均 12 ms 一张图"。这个结论最缺什么？

- A. 数据集名称
- B. 模型参数量
- C. 百分位（p50/p95/p99）、是否 warmup、是否做了 CUDA 同步；只有均值会掩盖长尾，没同步可能只测到了 kernel 下发时间
- D. 什么都不缺，这已经是完整的基准

**Q2.** 在 GPU 上计时时，如果省略 `torch.cuda.synchronize()`，测出的时间通常会：

- A. 偏大，因为同步本身很耗时
- B. 偏小，因为 CUDA kernel 是异步启动的，Python 端拿到控制权时 kernel 可能还没执行完
- C. 完全准确，PyTorch 会自动等待
- D. 随机地偏大或偏小，没有规律

**Q3.** 按本节代码 `conv_hook` 的公式 `2 · c_in_per_group · c_out · kh · kw · h · w`，一个 `Conv2d(256, 256, 3, padding=1, groups=256)`（depthwise）在 14×14 输出上的 FLOPs 约为：

- A. 约 2.3 亿，和普通 3×3 卷积一样
- B. 约 90 万，是同尺寸普通 3×3 卷积的 1/256
- C. 约 2,570 万，与 1×1 卷积相同
- D. 0，depthwise 卷积不需要乘法

**Q4.** 关于 INT8 量化，下列说法正确的是：

- A. 模型体积降为 1/8，速度在任何硬件上都提升 8 倍
- B. 模型体积和内存带宽约降为 1/4；只有在有 INT8 计算内核的硬件上，计算才能提速 2–4 倍
- C. 视觉模型做静态 PTQ 通常会损失 5–10 个百分点
- D. 量化只作用于权重，激活永远保持 FP32

**Q5.** 三种量化方式中，哪一个需要"一小批有代表性的校准数据但不需要训练"？

- A. Dynamic 量化
- B. Static PTQ（训练后静态量化）
- C. QAT（量化感知训练）
- D. 三者都不需要任何数据

**Q6.** 下列"目标设备 → 推理运行时"的搭配中，**不合理**的是：

- A. NVIDIA Jetson → TensorRT
- B. iPhone → Core ML
- C. Android 手机 → TFLite
- D. Intel CPU 服务器 → Core ML

**Q7.** 模型 A 的 FLOPs 比模型 B 多 10%，但在目标设备上快 2 倍。最可能的解释是：

- A. FLOPs 计数器有 bug
- B. FLOPs 只统计运算次数；实际延迟还取决于算子在该硬件和运行时上的实现效率、内存带宽、kernel 启动开销等，A 用的算子对目标硬件更友好
- C. 模型 B 的参数更多
- D. A 一定用了 INT8

---

## 三、动手 / 代码题

**Q8.** 本节的 `measure_latency` 默认 `iters=20`，返回值这样计算：

```python
    times.sort()
    return {
        "p50_ms": times[len(times) // 2],
        "p95_ms": times[int(len(times) * 0.95)],
        "p99_ms": times[-1],
        "mean_ms": sum(times) / len(times),
    }
```

(1) `iters=20` 时，p50、p95、p99 分别取的是排序后的第几个下标？你发现了什么问题？
(2) 假设 20 次计时中 19 次在 10.0–11.8 ms 之间（每次递增 0.1 ms），有 1 次因为系统调度被拖到 30 ms。代码报告的 p50 / p95 / p99 / mean 各是多少？
(3) 写一个按"最近秩（nearest-rank）"定义计算百分位的函数 `pct(times, p)`，并说明要得到有意义的 p99，至少需要多少次迭代。
(4) 为什么计时循环中，`t0` 之前也要调用一次 `torch.cuda.synchronize()`？

**Q9.** 本节 `flops_estimate` 的两个 hook：

```python
    def conv_hook(m, inp, out):
        c_out, c_in_per_group, kh, kw = m.weight.shape
        h, w = out.shape[-2:]
        total[0] += 2 * c_in_per_group * c_out * kh * kw * h * w

    def linear_hook(m, inp, out):
        total[0] += 2 * m.in_features * m.out_features
```

torchvision 的 ConvNeXt block 中，逐点（pointwise）的 MLP 是用 `nn.Linear` 作用在 `permute` 成 `(N, H, W, C)` 的特征图上实现的。在 160×160 输入上，这个估算器给 `convnext_tiny` 的结果约为 0.35 GFLOPs，而按结构逐层计算的真实值约为 4.55 GFLOPs。
(1) 指出 bug 在哪里，并修复 `linear_hook`。
(2) `conv_hook` 还有一个隐含假设，当 `input_shape` 的 batch 维不是 1 时会出错，请一并修复。
(3) 为什么 `c_in_per_group` 这个写法对 depthwise 卷积是正确的？

**Q10.** 讲义 Step 3 的 `quantise_ptq` 直接对模型执行 `prepare → 校准 → convert`。对于一个普通的 `nn.Module`（例如 torchvision 的 `mobilenet_v3_small`），这样做转换后推理往往会直接报错。请说明原因，并为下面这个小网络写出完整、正确的 eager 模式静态 PTQ 流程：

```python
class SmallNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(3, 16, 3, padding=1)
        self.bn = nn.BatchNorm2d(16)
        self.relu = nn.ReLU()
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(16, 10)

    def forward(self, x):
        x = self.relu(self.bn(self.conv(x)))
        return self.fc(self.pool(x).flatten(1))
```

---

## 四、面试高频题

**Q11.**（基础必考）如何正确地测量一个视觉模型的推理延迟？请列出你会遵守的规则和报告的指标。

**Q12.**（原理深挖）讲讲 INT8 量化的原理：scale 和 zero-point 是什么？per-tensor 和 per-channel 有什么区别？为什么视觉 CNN 做 PTQ 损失通常很小？什么情况下必须上 QAT？

**Q13.**（工程实践）把 PyTorch 模型导出为 ONNX 并部署时，最常见的失败有哪些？分别怎么排查和修复？

**Q14.**（场景设计）产品要求在中端安卓手机上做实时图像分类：模型小于 10 MB，p95 延迟小于 10 ms，精度不比服务端模型低超过 2 个点。给出你的方案和验证步骤。

**Q15.**（追问型）depthwise 卷积的 FLOPs 只有普通卷积的几百分之一，为什么在 GPU 上它往往没有快那么多？由此说明 FLOPs 与延迟的关系。

---

## 五、参考答案与解析

### Q1 — 答案：C

实时系统是在长尾上出问题的，均值会被少数极慢样本拉高，也会掩盖抖动；不 warmup 时首次前向的 JIT 编译、缓存冷启动会污染结果；GPU 上不同步只测到 kernel 下发的时间。三者都对，数字才有意义。此外还应注明分辨率、batch 大小、精度格式、软件版本和设备型号（skill 文件要求记录 torch/CUDA 版本与设备名）。

### Q2 — 答案：B

CUDA kernel 的启动是异步的：`model(x)` 在 Python 中返回时，GPU 可能还在排队执行，此时停表测到的只是"下发"时间，通常远小于真实执行时间。`synchronize()` 会阻塞，直到 GPU 上所有已提交的工作完成。

### Q3 — 答案：B

depthwise：`groups=256`，权重形状 `(256, 1, 3, 3)`，`c_in_per_group = 1`。FLOPs = `2 × 1 × 256 × 9 × 196 = 903,168 ≈ 0.9M`。普通 3×3 卷积 = `2 × 256 × 256 × 9 × 196 = 231,211,008 ≈ 2.3 亿`，正好是 256 倍。C 是 1×1 卷积（`2 × 256 × 256 × 196 ≈ 2,569 万`）的数值——MobileNet 的 depthwise separable 就是"depthwise 3×3 + pointwise 1×1"，计算量主要集中在 1×1 那一步。

### Q4 — 答案：B

FP32 → INT8 是 4 字节 → 1 字节，体积和带宽约为 1/4。计算提速依赖硬件是否有 INT8 内核（讲义：每一款现代移动 SoC、每一块带 Tensor Core 的 NVIDIA GPU 都有），通常为 2–4 倍。C 错：讲义说典型损失为 0.1–1 个点。D 错：static PTQ 和 QAT 都会量化激活，只有 dynamic 量化的激活仍为浮点。

### Q5 — 答案：B

static PTQ 需要校准集来统计激活的取值范围（据此确定 scale/zero-point），但不更新权重。dynamic 量化在运行时动态计算激活范围，不需要校准集；QAT 要在训练中模拟量化，需要带标签的训练数据。

### Q6 — 答案：D

Core ML 是 Apple 的运行时（iOS/macOS）。Intel CPU 应选 OpenVINO 或 ONNX Runtime 的 CPU / OpenVINO provider。讲义的通用路线是：PyTorch → ONNX → 按目标选运行时，ONNX 是"通用语"。

### Q7 — 答案：B

讲义原话："FLOPs 多 10% 的模型在实践中可能快 2 倍，因为它使用了硬件友好的算子（depthwise 卷积编译得好，大的 7×7 卷积则不然）。"FLOPs 不反映访存量、算子融合、并行度、kernel 启动开销以及运行时对该算子的优化程度。规则：架构搜索用 FLOPs，部署决策用设备上实测的延迟。

### Q8 — 参考答案

(1) `n = 20`：p50 取下标 `20 // 2 = 10`（第 11 小，偶数个样本时的"上中位数"）；p95 取 `int(20 × 0.95) = 19`；p99 取 `-1`，即下标 19。**p95 和 p99 都等于最大值**——20 个样本根本区分不出 p95 和 p99，报告里看似有三个百分位，实际上 p95 被高估成了最坏的那一次。按最近秩定义，p95 应取第 `⌈0.95 × 20⌉ = 19` 小的样本，即下标 18。

(2) 已用 Python 实际验证：

```text
p50  = times[10] = 11.0 ms
p95  = times[19] = 30.0 ms   ← 一次调度抖动直接变成"p95"
p99  = times[-1] = 30.0 ms
mean = (10.0+…+11.8 + 30.0)/20 = 11.855 ms   ← 一个离群值让均值比 p50 高约 0.9 ms
```

按最近秩，p95 应为 11.8 ms。这个例子同时说明了两件事：样本太少时高百分位极不稳定；均值会被单个离群值拉高。

(3)

```python
import math

def pct(times_sorted, p):
    """最近秩百分位：第 ceil(p·n) 小的样本（1-based）。"""
    k = max(1, math.ceil(p * len(times_sorted)))
    return times_sorted[k - 1]

ts = sorted([10.0 + i * 0.1 for i in range(19)] + [30.0])
print(pct(ts, 0.5), pct(ts, 0.95), pct(ts, 0.99))   # 10.9 11.8 30.0
```

要让 p99 与最大值区分开，至少需要 100 次以上的迭代（n=100 时 p99 是第 99 小的值）；想要稳定的估计通常需要 1000 次量级。skill 文件默认 `iters=100`、`warmup=10`，本节代码为了让四个模型在 CPU 上快速跑完，只用了 20 次。

(4) 保证计时开始前 GPU 是"空闲"的：如果上一轮（或 warmup）还有未完成的 kernel，它们的执行时间会被算进这一轮，造成测量串扰。前后各同步一次，测到的才恰好是这一次前向的完整执行时间。

### Q9 — 参考答案

(1) `linear_hook` 默认 `nn.Linear` 只作用于一个向量，FLOPs 记为 `2 × in × out`。但 `nn.Linear` 作用在 `(N, H, W, C)` 上时，会对 `N·H·W` 个位置**各做一次**矩阵乘法。ConvNeXt 中占计算量大头的逐点 MLP 因此被少算了 `H·W` 倍（stage 1 是 40×40 = 1600 倍），导致整个模型从约 4.55 GFLOPs 被低估成约 0.35 GFLOPs，比 ResNet-18（约 1.85）看起来还"便宜"，对比表的结论会被误导。修复：

```python
    def linear_hook(m, inp, out):
        positions = out.numel() // out.shape[-1]          # 除最后一维外所有维度的乘积（含 batch）
        total[0] += 2 * m.in_features * m.out_features * positions
```

(2) `conv_hook` 只用了输出的 `h, w`，没有乘 batch 大小，`input_shape=(8, 3, 160, 160)` 时会少算 8 倍。修复：

```python
    def conv_hook(m, inp, out):
        c_out, c_in_per_group, kh, kw = m.weight.shape
        n, _, h, w = out.shape
        total[0] += 2 * c_in_per_group * c_out * kh * kw * h * w * n
```

（修复后的 `linear_hook` 用 `out.numel()`，已经自动包含了 batch。）

(3) PyTorch 中 `Conv2d` 的权重形状是 `(out_channels, in_channels // groups, kh, kw)`，每个输出通道只连接 `in_channels / groups` 个输入通道。depthwise 卷积 `groups = in_channels`，所以第二维是 1，每个输出像素只做 `kh × kw` 次乘加。直接从权重形状读出 `c_in_per_group`，就自然覆盖了普通卷积（groups=1）、分组卷积和 depthwise 卷积三种情况。讲义版本把这个变量命名为 `c_in`，数值上相同，但名字容易误导人以为"连接了全部输入通道"。

### Q10 — 参考答案

**为什么会报错**：PyTorch eager 模式的静态量化不会自动处理模型的"入口"和"出口"。`convert` 之后，`Conv2d/Linear` 被替换成只接受量化张量的 `quantized` 模块，但输入仍是浮点张量，第一个量化卷积就会报"该算子没有浮点 CPU 后端实现"之类的错误。正确流程需要：
1. 在 `forward` 开头用 `QuantStub` 把输入量化，结尾用 `DeQuantStub` 反量化；
2. 在 `prepare` **之前**用 `fuse_modules` 把 `Conv → BN → ReLU` 融合（讲义说的融合步骤，但代码片段里没有调用；`convert` 本身并不做融合）；
3. 带残差相加的模型（如 ResNet、MobileNetV3）还要把 `+` 换成 `FloatFunctional`。

因此实际项目更常用 torchvision 自带的可量化模型（`torchvision.models.quantization`），或 FX 图模式量化（`torch.ao.quantization.quantize_fx`），后者能自动处理这些细节。

```python
import torch
import torch.nn as nn
import torch.ao.quantization as tq

class SmallNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.quant = tq.QuantStub()          # 入口：float -> int8
        self.conv = nn.Conv2d(3, 16, 3, padding=1)
        self.bn = nn.BatchNorm2d(16)
        self.relu = nn.ReLU()
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(16, 10)
        self.dequant = tq.DeQuantStub()      # 出口：int8 -> float

    def forward(self, x):
        x = self.quant(x)
        x = self.relu(self.bn(self.conv(x)))
        x = self.fc(self.pool(x).flatten(1))
        return self.dequant(x)

model = SmallNet().eval()                                        # 融合 BN 必须在 eval 模式
tq.fuse_modules(model, [["conv", "bn", "relu"]], inplace=True)  # Conv+BN+ReLU -> ConvReLU2d（BN 折叠进卷积）
model.qconfig = tq.get_default_qconfig("x86")                    # ARM 设备用 "qnnpack"
tq.prepare(model, inplace=True)                                  # 插入 observer
with torch.no_grad():
    for _ in range(32):                                          # 校准：真实场景用几百张有代表性的图
        model(torch.randn(8, 3, 32, 32))
tq.convert(model, inplace=True)                                  # 换成量化模块
print(model(torch.randn(1, 3, 32, 32)).shape)                    # torch.Size([1, 10])
```

（当前环境无 torch，以上代码未实际运行。）

验证：对比 FP32 与 INT8 在同一验证集上的精度（目标是损失 < 1 个点），并用 Q8 修正后的计时函数对比延迟；如果精度损失过大，依次尝试 per-channel 权重量化、换校准集或增大校准集、对敏感层保留浮点，最后才考虑 QAT。

### Q11 — 参考回答要点

- **环境固定**：
  - 在目标设备上测，固定输入分辨率和 batch 大小；
  - 固定 CPU 线程数（`torch.set_num_threads`）、关闭其他负载；
  - 记录 torch / CUDA / 运行时版本和设备名。
- **流程**：
  1. `model.eval()` + `torch.no_grad()`（或 `inference_mode`）；
  2. warmup 5–10 次（或更多）；
  3. 每次前向前后都同步（CUDA 用 `torch.cuda.synchronize()`，MPS 用 `torch.mps.synchronize()`）；
  4. 用 `time.perf_counter()` 计时，迭代次数足够多（≥100）。
- **报告**：p50、p95、p99、均值、标准差；峰值内存（CUDA 用 `max_memory_allocated`，CPU 用 RSS）；需要时做 batch 扫描，给出吞吐量与延迟的取舍。
- **加分点**：
  - 区分单次延迟和吞吐量（batch 大时吞吐高、单次延迟也高）；
  - 端到端延迟还要包含预处理和后处理（解码、resize、NMS），模型本身往往只占一部分；
  - 用 profiler（nsys、Instruments）做逐层分解。
- **常见误区**：在工作站上测完就当作设备上的结论；只报均值。

### Q12 — 参考回答要点

- **仿射量化**：`q = clamp(round(x / s) + z, qmin, qmax)`，反量化 `x ≈ s·(q − z)`。scale `s` 决定步长，zero-point `z` 让浮点的 0 能被精确表示（对 ReLU 后的激活和零填充很重要）。
- **粒度**：
  - per-tensor：整个张量共用一组 `(s, z)`；
  - per-channel：每个输出通道一组。卷积权重各通道的取值范围差异很大，per-channel 能显著降低误差，是权重量化的默认选择。
- **校准**：用几百张有代表性的图跑前向，observer 统计激活范围（min/max、直方图、百分位）来确定 `s, z`。范围选得太宽，分辨率就粗；太窄，离群值会被截断。
- **视觉 CNN 为什么损失小**：Conv+BN+ReLU 融合后，激活分布比较规整，离群值少；网络对小扰动比较鲁棒。讲义给出的典型损失是 0.1–1 个点。
- **何时上 QAT**：PTQ 后精度掉得超过可接受范围时；常见于本身很紧凑、冗余少的小模型，以及激活离群值多的结构（某些 Transformer 层）。QAT 在训练中插入"伪量化"节点，让权重适应量化噪声。选型 prompt 建议用 5–10% 的训练时间做 QAT 微调；若仍不达标，再考虑从大教师蒸馏。
- **常见误区**：以为"INT8 一定更快"——没有 INT8 内核的硬件上，量化/反量化的开销反而会让模型变慢。

### Q13 — 参考回答要点

- **算子不支持**（`Unsupported operator`）：自定义算子或较新的算子在所选 opset 中没有映射。修复：换成等价的标准算子组合、升级 opset，或为运行时注册自定义算子。
- **控制流丢失**：`torch.onnx.export` 默认基于 tracing，只记录用示例输入实际走过的路径；依赖数据的 `if` / 循环会被"冻结"成一条固定路径，导出不报错但结果错误。修复：把控制流改写成张量运算，或对这部分使用 scripting。
- **形状被写死**：没有设置 `dynamic_axes`，导出的模型只能接受导出时的 batch / 分辨率；或者代码中用 Python 整数参与了形状计算。修复：设置 `dynamic_axes`，用张量运算计算形状。
- **数值不一致**：导出前忘了 `model.eval()`（BN/Dropout 行为不同），或者预处理在两端不一致。修复：用同一输入比较 PyTorch 与 onnxruntime 的输出（如 `np.allclose(atol=1e-4)`）。
- **排查工具**：`onnx.checker` 检查模型合法性，Netron 可视化计算图，`onnxruntime` 逐节点对比输出，TensorRT 的 `trtexec` 做独立压测。
- **加分点**：导出的是推理图，要先融合 Conv+BN；对 TensorRT 还要注意它对 INT64、动态形状的支持限制。

### Q14 — 参考回答要点

- **选型**：
  - backbone 选 MobileNetV3-Small 或 EfficientNet-Lite-B0；二者都是为这个预算设计的，能干净地编译到 TFLite / Core ML；
  - INT8 量化后体积只有几 MB；
  - ResNet-50、ViT-B 即使量化也超过 25 MB，直接出局。
- **精度保障**：
  1. 在任务数据上微调；
  2. 用服务端大模型做教师进行**蒸馏**，弥补小模型的精度差距；
  3. 静态 PTQ（几百张校准图）；
  4. 若掉点超过预算，再做 QAT。
- **部署路线**：PyTorch → ONNX → TFLite（Android，可用 GPU delegate），或直接用 TFLite 转换器；iOS 则走 Core ML。
- **验证**：
  - 在**目标机型**上用 warmup + 百分位的方式测 p50/p95/p99、峰值内存和功耗；
  - 端到端计时要包括相机帧解码和预处理；
  - 在保留集上对比服务端模型与端侧 INT8 模型的精度，确认差距 ≤ 2 个点；
  - 覆盖低端机型和发热降频场景。
- **常见误区**：只看模型推理时间，忽略预处理；在模拟器或电脑上测完就上线。

### Q15 — 参考回答要点

- **原因**：
  - depthwise 卷积每个输出只对 `k×k` 个输入做乘加，**算术强度**（每读取一个字节做多少次计算）很低，属于访存受限（memory-bound）：时间主要花在搬数据上，GPU 的计算单元和 Tensor Core 吃不饱；
  - 普通卷积和矩阵乘的数据复用率高，能把硬件算力打满；
  - 此外还有 kernel 启动开销、层数多导致的调度开销，以及运行时对某些算子的优化不足。
- **结论**：FLOPs 是与设备无关的粗略代理，适合在同一类结构之间比较或做架构搜索；部署决策必须看目标设备上实测的延迟（讲义："use FLOPs for architecture search, use on-device latency for deployment decisions"）。
- **补充**：反过来，在移动 CPU / NPU 上，depthwise 卷积往往有专门优化，是 MobileNet 系列在端侧仍然流行的原因。同一个算子在不同硬件上的"友好度"可能截然相反，这正是"每个数字都要在目标设备上测"的理由。
- **加分点**：提到 roofline 模型（算力上限 vs 带宽上限）以及算子融合对减少访存的作用。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：本节对比的都是分类 backbone。
- [阶段 10 · 11 量化](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：量化的数学原理与 LLM 场景。
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：理解卷积的参数量与计算量。
- [阶段 00 · 12 调试与性能分析](../../../00-setup-and-tooling/12-debugging-and-profiling/docs/zh.md)：profiler 的基本用法。

### 本节被哪些后续内容用到
- [阶段 04 · 16 构建完整的视觉流程（Capstone）](../../16-vision-pipeline-capstone/docs/zh.md)：把延迟预算落实到完整的检测服务中。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：为什么边缘端仍偏好 CNN，而服务端偏好 ViT。
- [阶段 10 · 12 推理优化](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：同样的测量纪律用于 LLM 推理。
- [阶段 17 · 09 生产环境量化](../../../17-infrastructure-and-production/09-production-quantization/docs/zh.md)：大规模部署中的量化取舍。
- [阶段 17 · 12 边缘推理](../../../17-infrastructure-and-production/12-edge-inference/docs/zh.md)：边缘推理的工程体系。
- [阶段 17 · 08 推理指标与 goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：延迟百分位、吞吐与 SLA。

### 延伸关键词
`roofline 模型` · `算术强度` · `per-channel 量化` · `FX graph mode quantization` · `QuantStub / FloatFunctional` · `知识蒸馏` · `结构化剪枝` · `ONNX opset` · `TensorRT / trtexec` · `TFLite GPU delegate` · `Core ML` · `OpenVINO`
